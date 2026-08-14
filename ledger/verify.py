"""The verification cascade.

There is no human editor, so verification is not a review step at the end — it is
the main body of the pipeline, and a claim must survive all of it to publish.

Two properties are structural rather than prompted:
  1. A verifier receives claims and sources ONLY. It never sees the extracting
     agent's reasoning, so it cannot be led.
  2. Passes must run on distinct model families. Same-family verification is not
     independence, it is agreement — so it caps confidence instead of conferring it.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable

# The ladder confidence is capped down along when independence is unavailable.
BANDS = (0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 1.0)

# Fields a verifier is allowed to see. Anything else is stripped.
VISIBLE = ("id", "beat", "claim_text", "quote", "source_type", "source_url",
           "source_doi", "source_sha", "confidence", "tier", "docket")


@dataclass(frozen=True)
class Verdict:
    refuted: bool
    reason: str = ""
    passname: str = ""
    family: str = ""


@dataclass(frozen=True)
class Pass:
    name: str
    family: str
    fn: Callable[[dict, list], Verdict]


@dataclass
class CascadeResult:
    claim: dict
    survived: bool
    agreeing: int
    rounds: int
    verdicts: tuple[Verdict, ...] = ()
    single_family: bool = False
    families_used: tuple[str, ...] = ()
    discarded: bool = False


def band_down(conf: float) -> float:
    """Step one band down the ladder, and NEVER upward.

    The ladder starts at 0.5, so a confidence already below it (0.38, say) found
    no lower band and fell through to BANDS[0] — degraded verification raised
    confidence to 0.5. Penalising a claim must never reward it, so the result is
    clamped to the input.
    """
    lower = [b for b in BANDS if b < conf - 1e-9]
    return min(conf, lower[-1] if lower else BANDS[0])


def _visible(claim: dict) -> dict:
    """The verifier's view: claim and provenance, never reasoning."""
    return {k: claim[k] for k in VISIBLE if k in claim}


def run_cascade(claim: dict, sources, passes, consensus_required: int,
                rounds_max: int = 1, reextract=None) -> CascadeResult:
    """Run every pass, count agreement, re-extract on failure up to rounds_max.

    A claim survives a round when at least `consensus_required` passes fail to
    refute it. Passes are prompted to refute and default to refuted under
    uncertainty, so agreement is the exception the claim has to earn.
    """
    current = dict(claim)
    all_verdicts: list[Verdict] = []
    rounds = 0

    extractor_family = claim.get("extracted_by_family")
    verifier_families = tuple(dict.fromkeys(p.family for p in passes))
    families_used = tuple(dict.fromkeys(
        ([extractor_family] if extractor_family else []) + list(verifier_families)))
    # Independence is a property of the VERIFIERS. The extractor's family is
    # recorded for the audit trail but never counts toward independence.
    single_family = len(verifier_families) < 2

    while rounds < max(1, rounds_max):
        rounds += 1
        view = _visible(current)
        verdicts = []
        for p in passes:
            v = p.fn(view, sources)
            verdicts.append(Verdict(v.refuted, v.reason, p.name, p.family))
        all_verdicts.extend(verdicts)
        agreeing = sum(1 for v in verdicts if not v.refuted)

        if agreeing >= consensus_required:
            out = dict(current)
            if single_family:
                out["confidence"] = band_down(float(out.get("confidence", BANDS[0])))
                out["single_family_verified"] = True
            out["verification_rounds"] = rounds
            out["verifier_families"] = list(verifier_families)
            return CascadeResult(out, True, agreeing, rounds, tuple(all_verdicts),
                                 single_family, families_used)

        if reextract is None or rounds >= rounds_max:
            break
        refutations = [v.reason for v in verdicts if v.refuted]
        current = reextract(current, refutations)

    return CascadeResult(current, False, 0, rounds, tuple(all_verdicts),
                         single_family, families_used, discarded=True)
