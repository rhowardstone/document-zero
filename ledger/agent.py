"""The beat agent. Tier 2.

Reads its own beat's state and its own new sources, extracts claims, runs them
through the refusal gates and the verification cascade, writes what survives, and
recomputes state. It writes only inside its own partition, so sixteen of these can
run concurrently and push to the same branch without ever conflicting.

Every model touchpoint is injected: the extractor, the verifier passes, the state
proposer and the subject resolver are all callables. The orchestration — which is
where the editorial rules live — is therefore fully testable with no API calls.

Failure is atomic at the ledger level: a run that cannot parse its model output
writes nothing at all, rather than leaving half a beat behind.
"""
from __future__ import annotations
from dataclasses import dataclass, field

from .extract import build_extraction_prompt, parse_claims, looks_like_injection, ExtractionError
from .refusal import refusal_check
from .ancestry import detect_single_root
from .verify import run_cascade
from .diff import diff_state


@dataclass
class AgentResult:
    beat: str
    claims_written: int = 0
    refused: list = field(default_factory=list)
    cascade_failures: int = 0
    injection_attempts: int = 0
    single_root: bool = False
    delta: object = None
    mean_confidence: float | None = None   # evidence quality, for the editor's ranking
    error: str | None = None


class BeatAgent:
    def __init__(self, ledger, beat, policy, extractor, extractor_family,
                 passes, state_proposer, subject_resolver, now,
                 consensus_required: int = 2, rounds_max: int = 1, reextract=None):
        self.led = ledger
        self.beat = beat
        self.policy = policy or {}
        self.extractor = extractor
        self.extractor_family = extractor_family
        self.passes = passes
        self.state_proposer = state_proposer
        self.subject_resolver = subject_resolver
        self.now = now
        self.consensus_required = consensus_required
        self.rounds_max = rounds_max
        self.reextract = reextract

    def run(self, sources) -> AgentResult:
        r = AgentResult(beat=self.beat)
        old_state = self.led.get_state(self.beat)

        # Hostile-data check. A source attempting to instruct us is reportable,
        # but it is still read — as data, exactly as before.
        for s in sources:
            body = " ".join(filter(None, [s.get("title"), s.get("snippet"),
                                          s.get("full_text")]))
            if looks_like_injection(body):
                r.injection_attempts += 1

        prompt = build_extraction_prompt(self.beat, old_state or {"fields": []}, sources)
        index = {s["sha256"]: s for s in sources}

        try:
            raw = self.extractor(prompt)
            claims = parse_claims(raw, beat=self.beat, extracted_by=f"beat-agent-{self.beat}",
                                  now=self.now, source_index=index)
        except ExtractionError as e:
            r.error = str(e)
            return r                      # nothing written; the ledger is untouched

        # Refusal gates run before verification: a refusal is absolute and is not
        # curable by better sourcing, so there is no point verifying first.
        allowed = []
        for c in claims:
            d = refusal_check(c, self.subject_resolver(c))
            if d.allowed:
                allowed.append(c)
            else:
                r.refused.append(d.gate)
        if not allowed:
            r.delta = diff_state(old_state, old_state)
            return r

        r.single_root = detect_single_root(allowed).single_root

        survivors = []
        for c in allowed:
            c = dict(c, extracted_by_family=self.extractor_family)
            res = run_cascade(c, sources, self.passes,
                              consensus_required=self.consensus_required,
                              rounds_max=self.rounds_max, reextract=self.reextract)
            if res.survived:
                survivors.append(res.claim)
            else:
                r.cascade_failures += 1

        if not survivors:
            r.delta = diff_state(old_state, old_state)
            return r

        for c in survivors:
            self.led.put_claim(c)
        r.claims_written = len(survivors)
        r.mean_confidence = sum(float(c.get("confidence", 0)) for c in survivors) / len(survivors)

        new_state = self.state_proposer(old_state, survivors)
        r.delta = diff_state(old_state, new_state)

        if not r.delta.is_empty:
            self.led.put_state(self.beat, new_state)
            self.led.append_history(self.beat, {
                "d": (new_state.get("as_of") or self.now)[:10],
                "c": self._describe(r.delta),
                "s": f"{len(survivors)} claim(s) from {len(sources)} source(s)",
            })
        return r

    @staticmethod
    def _describe(delta) -> str:
        """A history row states what changed, in field terms. Deterministic:
        the prose layer may render it, but it may not invent it."""
        parts = [f"{c.k} → {c.new}" for c in delta.changed]
        parts += [f"{a.k} recorded as {a.v}" for a in delta.added]
        parts += [f"{x.k} no longer tracked" for x in delta.removed]
        return ". ".join(parts) + "." if parts else "No change."
