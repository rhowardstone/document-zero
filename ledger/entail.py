"""The entailment gate: prose may not assert what its claims do not support.

A state field either matches the docket or it does not. A 600-word article can
introduce a causal claim, an implication, or a single adjective that no source
supports, and it will read fluently while doing so. Fluency is not accuracy, and
an automated newsroom with no human editor cannot rely on anyone noticing.

This is the v1 verification cascade moved up a level, from claims to sentences.
Three properties are enforced here rather than prompted:

  ASYMMETRY. Verifiers see the sentence and the CITED CLAIMS ONLY — never the
  writer's reasoning, never the wider source set, never the beat's history. A
  verifier shown the justification adopts it; a verifier shown uncited evidence
  reaches for it. Withholding both is what makes the check independent.

  REFUSE THE ARTICLE, NOT THE SENTENCE. One unentailed sentence kills the whole
  piece. Editing the offending sentence and re-checking would produce an article
  optimised against the check rather than supported by the evidence, and the
  beat has a safe fallback: a one-line entry stating the bare fact, which needs
  no prose to support it.

  UNCERTAINTY IS REFUSAL. A verifier that errors, times out, or hedges counts
  as not-entailed. This matches the claim cascade, which defaults to refuted.

Verifiers are injected callables so the whole gate runs for free in tests. In
production each is a Claude Code instance from a different model line.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field

from .sentences import split as _split

# Splitting is delegated to ledger/sentences.py, which is abbreviation-aware.
# The naive version here cut "…in the U.S. District Court" and "Judge Amir H.
# Ali" into fragments, and the verifiers refused the fragments — correctly,
# since a fragment asserts something incomplete. A publishable article was
# thrown away by the splitter rather than by any fault in the writing.


class Refused(RuntimeError):
    """The article did not survive the gate and may not publish."""


@dataclass(frozen=True)
class Verdict:
    entailed: bool
    reason: str = ""


@dataclass(frozen=True)
class Refusal:
    sentence: str
    reason: str
    verifier: int


@dataclass
class Result:
    passed: bool
    refusals: list = field(default_factory=list)
    checked: int = 0

    def require_pass(self) -> None:
        if self.passed:
            return
        first = self.refusals[0] if self.refusals else None
        raise Refused(
            f"{len(self.refusals)} unentailed sentence(s); first: "
            f"{first.sentence[:90]!r} — {first.reason}"
            if first else "article refused")


def sentences(text: str) -> list[str]:
    return _split(text)


def check(article, claims, verifiers, workers: int = 8) -> Result:
    """Run every sentence past every verifier.

    `verifiers` are callables (sentence, cited_claims) -> Verdict.

    Checks run CONCURRENTLY. Measured on the first live run: 34 sentences x 2
    verifiers is 68 agent calls, and sequentially that took 964 seconds for a
    single beat — unworkable for a newsroom of any size. The checks are
    independent by construction (each sees one sentence and its own claims and
    shares no state), so concurrency changes wall-clock and nothing else.

    Order is preserved in `refusals` regardless of completion order, so the same
    article always produces the same report.
    """
    from concurrent.futures import ThreadPoolExecutor

    by_id = {c["id"]: c for c in claims}
    jobs = []
    for para in article.paragraphs:
        # Only the claims this paragraph cites. A citation the ledger does not
        # hold is dropped rather than raising: the verifier then sees less
        # evidence, which can only make it more likely to refuse.
        cited = [by_id[cid] for cid in (para.get("claims") or []) if cid in by_id]
        for sentence in sentences(para.get("text", "")):
            for i, verifier in enumerate(verifiers):
                jobs.append((sentence, cited, i, verifier))

    def one(job):
        sentence, cited, i, verifier = job
        try:
            return sentence, i, verifier(sentence, cited)
        except Exception as e:                              # noqa: BLE001
            return sentence, i, Verdict(False,
                                        f"verifier error: {type(e).__name__}: {e}")

    if workers > 1 and len(jobs) > 1:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            outcomes = list(pool.map(one, jobs))
    else:
        outcomes = [one(j) for j in jobs]

    res = Result(passed=True)
    res.checked = len(jobs) // max(len(verifiers), 1)
    for sentence, i, verdict in outcomes:
        if not verdict.entailed:
            res.passed = False
            res.refusals.append(Refusal(sentence, verdict.reason, i))
    return res
