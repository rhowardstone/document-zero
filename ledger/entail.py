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

  A SENTENCE IS REFUSED BY AGREEMENT, NOT BY ONE VOTE. This was originally a
  single-verifier veto, on the reasoning that refusing under uncertainty is the
  safe direction. Measured on the first live run, that reasoning was wrong at
  the article level: per-sentence false refusals COMPOUND. At a 3% false-refusal
  rate across 29 sentences, only 41% of correct articles survive — and the
  observed rate was worse. Two of the three refusals in that run were plainly
  wrong, one of them contradicting its own stated reason.

  A veto that silences most correct work does not make the system safe, it makes
  it quiet, and a newsroom that publishes nothing has no accuracy to protect. So
  a sentence is refused when a MAJORITY of verifiers refuse it. A genuinely
  unsupported sentence is caught by both; a verifier having a bad moment is not
  enough on its own. This also matches the claim cascade, which has required
  consensus since v1.

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
    # True when the verifier never actually reached a judgement — it crashed,
    # timed out, or returned nothing. This is NOT the same as deciding the
    # sentence is unsupported, and majority voting must not treat it as a vote.
    errored: bool = False


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
    # Minority objections: a verifier refused but was outvoted. These do not
    # block publication, and a rising count is the early warning that the
    # verifiers and the writer are drifting apart.
    dissents: list = field(default_factory=list)

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


def without(article, refusals, validate=None):
    """A copy of the article with the refused sentences deleted.

    This is NOT the same as letting the reporter rewrite them, which the design
    forbids and still forbids: a rewritten sentence is optimised against the
    check, and each attempt teaches the writer what the checker will accept.

    Deletion cannot do that. It introduces no new text, so it cannot introduce
    anything unsupported — every surviving sentence is one the verifiers already
    passed, individually, on its own claims. The article gets shorter and says
    less; it cannot come to say something new.

    The schema still applies afterwards. An article that falls under the word
    floor once its unsupported sentences are gone had less to say than it
    appeared to, and degrades to a one-line entry like any other.
    """
    from .article import validate as _validate
    bad = {r.sentence.strip() for r in refusals}
    paras = []
    for p in article.paragraphs:
        kept = [s for s in sentences(p.get("text", "")) if s.strip() not in bad]
        if kept:
            paras.append({**p, "text": " ".join(kept)})
    obj = article.as_dict()
    obj["paragraphs"] = paras
    return (validate or _validate)(obj)


def cleared(article, verifier_names):
    """The same article, with the verifiers that cleared it on the record.

    Every article on the live site carried `verified_by: []` while the page
    told readers each sentence "was checked against those claims by two further
    models". The check had genuinely run — but the record could not show it, so
    the strongest claim this system makes about itself was the one claim a
    sceptical reader could not audit.

    Nothing about the prose changes. This adds attribution, never content.
    """
    from .article import validate
    d = article.as_dict()
    d["verified_by"] = [str(n) for n in (verifier_names or ())]
    return validate(d)


def check(article, claims, verifiers, workers: int = 8,
          refuse_threshold: int | None = None) -> Result:
    """Run every sentence past every verifier.

    `verifiers` are callables (sentence, cited_claims) -> Verdict.

    Checks run CONCURRENTLY. Measured on the first live run: 34 sentences x 2
    verifiers is 68 agent calls, and sequentially that took 964 seconds for a
    single beat — unworkable for a newsroom of any size. The checks are
    independent by construction (each sees one sentence and its own claims and
    shares no state), so concurrency changes wall-clock and nothing else.

    `refuse_threshold` is how many verifiers must refuse a sentence before it is
    refused. Defaults to a majority, so one verifier having a bad moment cannot
    kill an article on its own.

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
            return sentence, i, Verdict(
                False, f"verifier error: {type(e).__name__}: {e}", errored=True)

    if workers > 1 and len(jobs) > 1:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            outcomes = list(pool.map(one, jobs))
    else:
        outcomes = [one(j) for j in jobs]

    need = refuse_threshold or (len(verifiers) // 2 + 1)

    # Group by sentence, preserving first-seen order so the report is stable.
    order, votes = [], {}
    for sentence, i, verdict in outcomes:
        if sentence not in votes:
            votes[sentence] = []
            order.append(sentence)
        votes[sentence].append((i, verdict))

    res = Result(passed=True)
    res.checked = len(order)
    for sentence in order:
        cast = [(i, v) for i, v in votes[sentence] if not v.errored]
        errored = [(i, v) for i, v in votes[sentence] if v.errored]

        # A verifier that errored did not check the sentence. If too few
        # verifiers actually reached a judgement, the sentence is unverified,
        # and unverified is refused — that is different from being outvoted.
        if len(cast) < need:
            res.passed = False
            for i, v in (errored or cast):
                res.refusals.append(Refusal(
                    sentence, f"unverified ({len(cast)}/{need} verdicts): {v.reason}", i))
            continue

        against = [(i, v) for i, v in cast if not v.entailed]
        if len(against) >= need:
            res.passed = False
            for i, v in against:
                res.refusals.append(Refusal(sentence, v.reason, i))
        elif against:
            # A minority objection. Recorded so a pattern of near-misses is
            # visible, but it does not refuse.
            res.dissents.extend(Refusal(sentence, v.reason, i) for i, v in against)
    return res
