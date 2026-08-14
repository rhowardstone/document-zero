"""Anthropic adapters: the only modules in the ledger that call a model.

Everything editorial lives upstream in extract/refusal/verify/agent, which are
tested with plain callables. This file is the thin edge where those callables
are backed by real API calls, so the blast radius of an SDK change is one file.

Three properties are enforced here rather than prompted:

  - Structured output. Every call constrains the response with a JSON schema,
    so a malformed answer is an API-level failure rather than a parsing
    surprise downstream.
  - Refusal is not an exception. A safety refusal on extraction is recorded and
    the run writes nothing; a refusal on verification counts as REFUTED, because
    the cascade defaults to refusal under uncertainty and a model that will not
    engage has not cleared the claim.
  - Cost is measured, not estimated. Every call accumulates real token counts.
"""
from __future__ import annotations
import json
import os
from dataclasses import dataclass, field

from .verify import Pass, Verdict

# Distinct families for the verification cascade. Same vendor, different model
# lines — the strongest independence available here, and weaker than a genuine
# cross-vendor split. Recorded on every claim so the limit is legible.
EXTRACTOR_MODEL = "claude-opus-5"
REFUTE_MODEL = "claude-sonnet-5"
LENS_MODEL = "claude-haiku-4-5"

CLAIMS_SCHEMA = {
    "type": "object",
    "properties": {
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim_text": {"type": "string"},
                    "quote": {"type": "string"},
                    "source_sha": {"type": "string"},
                    "confidence": {"type": "number"},
                    "confidence_justification": {"type": "string"},
                    "tier": {"type": "string",
                              "enum": ["documented_fact", "credible_allegation", "question"]},
                },
                "required": ["claim_text", "quote", "source_sha", "confidence",
                             "confidence_justification", "tier"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["claims"],
    "additionalProperties": False,
}

VERDICT_SCHEMA = {
    "type": "object",
    "properties": {
        "refuted": {"type": "boolean"},
        "reason": {"type": "string"},
    },
    "required": ["refuted", "reason"],
    "additionalProperties": False,
}

REFUTE_SYSTEM = (
    "You are a verifier for a provenance ledger. You see a claim and the sources "
    "it cites — never the reasoning of whoever wrote it.\n\n"
    "Your job is to REFUTE the claim, not to agree with it. Refute when: the quote "
    "does not appear in the cited source; the claim says more than the quote supports; "
    "the tier overstates the evidence (an allegation dressed as a documented fact); or "
    "the confidence exceeds what a single source of that type can carry.\n\n"
    "Default to refuted=true when uncertain. Agreement is what the claim has to earn."
)

LENS_SYSTEM = (
    "You are a second verifier for a provenance ledger, reading with a different lens "
    "than the first. You see a claim and its sources only.\n\n"
    "Check three things: (1) internal consistency — does the claim contradict itself or "
    "its own quote? (2) sourcing — is the cited source the kind of source that can "
    "establish this kind of fact? (3) reproducibility — could a reader with only these "
    "sources reach this claim?\n\n"
    "Refute if any of the three fails. Default to refuted=true when uncertain."
)


class RefusalError(RuntimeError):
    """The model declined the request. Not a bug — a recordable outcome."""


@dataclass
class Cost:
    """Measured, never estimated."""
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    by_model: dict = field(default_factory=dict)

    def add(self, model: str, usage) -> None:
        self.calls += 1
        self.input_tokens += getattr(usage, "input_tokens", 0) or 0
        self.output_tokens += getattr(usage, "output_tokens", 0) or 0
        self.cache_read_tokens += getattr(usage, "cache_read_input_tokens", 0) or 0
        m = self.by_model.setdefault(model, {"calls": 0, "in": 0, "out": 0})
        m["calls"] += 1
        m["in"] += getattr(usage, "input_tokens", 0) or 0
        m["out"] += getattr(usage, "output_tokens", 0) or 0

    def summary(self) -> str:
        parts = [f"{k}: {v['calls']} calls, {v['in']}in/{v['out']}out"
                 for k, v in sorted(self.by_model.items())]
        return f"{self.calls} calls | " + " | ".join(parts)


class PaidCallsDisabled(RuntimeError):
    """A paid API call was attempted without explicit opt-in."""


# Every call in this file costs the operator money. Having credentials in the
# environment is NOT consent to spend them — an API key is there for many
# reasons, and a tool finding one is not the same as being told to use it.
# Spending is therefore opt-in per process and off by default: nothing here can
# bill anyone unless a human sets DZ_ALLOW_PAID_CALLS=1 for that run.
PAID_CALLS_ENV = "DZ_ALLOW_PAID_CALLS"


def paid_calls_allowed() -> bool:
    return os.environ.get(PAID_CALLS_ENV, "").strip().lower() in {"1", "true", "yes"}


def _client():
    import anthropic
    if not paid_calls_allowed():
        raise PaidCallsDisabled(
            "Refusing to make a paid API call.\n"
            f"Every request in ledger.client bills the operator. Set {PAID_CALLS_ENV}=1 "
            "to authorise spending for this run — deliberately, and only when you mean "
            "to. Credentials being present in the environment is not authorisation.\n"
            "Everything except this module runs for free: the full pipeline is testable "
            "with injected callables (see tests/) and runnable with a deterministic stub "
            "extractor (see scripts/dryrun_real.py)."
        )
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        raise RuntimeError("no Anthropic credentials in the environment")
    # The SDK already retries 429/5xx with backoff; two is the default and enough
    # for a nightly job that can simply re-run.
    return anthropic.Anthropic(max_retries=3)


# Models that rejected `effort` at runtime. Capability varies by model and moves
# faster than any table we could hard-code, so it is learned once and remembered
# rather than asserted.
_NO_EFFORT: set[str] = set()


def _json_call(client, *, model, system, prompt, schema, effort, cost, max_tokens=8000):
    # output_config goes through extra_body: the API accepts it, but SDK typings
    # lag (0.75.0 rejects it as an unexpected keyword). extra_body forwards it
    # unchanged, so this works on old and new SDKs alike.
    def call(with_effort: bool):
        cfg = {"format": {"type": "json_schema", "schema": schema}}
        if with_effort:
            cfg["effort"] = effort
        return client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=[{"type": "text", "text": system,
                     "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": prompt}],
            extra_body={"output_config": cfg},
        )

    try:
        resp = call(model not in _NO_EFFORT)
    except Exception as e:                    # noqa: BLE001 - narrowed immediately
        if "effort" not in str(e).lower() or model in _NO_EFFORT:
            raise
        # Learn it, then proceed without the hint. Effort tunes cost, not
        # correctness, so losing it degrades the run rather than failing it.
        _NO_EFFORT.add(model)
        resp = call(False)
    cost.add(model, resp.usage)
    # Check stop_reason before touching content: on a refusal, content may be
    # empty and indexing it would crash the run.
    if resp.stop_reason == "refusal":
        cat = getattr(getattr(resp, "stop_details", None), "category", None)
        raise RefusalError(f"{model} declined ({cat})")
    text = next((b.text for b in resp.content if b.type == "text"), "")
    return json.loads(text)


class AnthropicExtractor:
    """Backs BeatAgent's `extractor` callable. Returns the JSON array parse_claims wants."""

    family = "opus-5"

    def __init__(self, cost: Cost, model: str = EXTRACTOR_MODEL, effort: str = "high"):
        self.cost, self.model, self.effort = cost, model, effort
        self._c = _client()

    def __call__(self, prompt: str) -> str:
        out = _json_call(self._c, model=self.model,
                         system="You extract atomic claims for a provenance ledger. "
                                "Every claim must quote the cited source verbatim.",
                         prompt=prompt, schema=CLAIMS_SCHEMA, effort=self.effort,
                         cost=self.cost)
        return json.dumps(out.get("claims", []))


def _verifier(cost: Cost, model: str, system: str, effort: str):
    c = _client()

    def run(claim: dict, sources) -> Verdict:
        # The sources are identical for every claim in a beat's run, so they go in
        # the cached system block and the volatile claim goes in the user turn.
        # Measured: this is where the input tokens actually are.
        src_block = json.dumps(
            [{k: s.get(k) for k in ("sha256", "title", "snippet",
                                    "source_name", "published_at")} for s in sources],
            indent=2)
        try:
            out = _json_call(c, model=model,
                             system=system + "\n\nSOURCES AVAILABLE:\n" + src_block,
                             prompt="CLAIM UNDER REVIEW (this and the sources above are "
                                    "the whole of what you may consider):\n"
                                    + json.dumps(claim, indent=2),
                             schema=VERDICT_SCHEMA, effort=effort, cost=cost,
                             max_tokens=2000)
        except RefusalError as e:
            # A verifier that will not engage has not cleared the claim.
            return Verdict(True, f"verifier declined: {e}")
        return Verdict(bool(out["refuted"]), str(out.get("reason", "")))

    return run


def refute_pass(cost: Cost, model: str = REFUTE_MODEL, effort: str = "medium") -> Pass:
    return Pass("refute", model, _verifier(cost, model, REFUTE_SYSTEM, effort))


def lens_pass(cost: Cost, model: str = LENS_MODEL, effort: str = "low") -> Pass:
    return Pass("lens", model, _verifier(cost, model, LENS_SYSTEM, effort))
