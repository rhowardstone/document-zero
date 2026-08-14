"""Object schemas. Validation is the enforcement point for the provenance rules.

Structural guarantees, not prompt instructions:
  - no claim without a source pointer
  - no claim without an exact quote
  - no confidence without a justification
  - no confidence above its source type's ceiling
  - DOI required for article / inproceedings / preprint
  - no beat with fewer than two changeable state fields
"""
from __future__ import annotations
import re
from .ceilings import check_confidence, requires_doi, CeilingError

TIERS = frozenset({"documented_fact", "credible_allegation", "question"})


class SchemaError(ValueError):
    """An object does not satisfy the ledger schema."""


def _require(obj, field, msg=None):
    v = obj.get(field)
    if v is None or (isinstance(v, str) and not v.strip()):
        raise SchemaError(msg or f"missing required field: {field}")
    return v


def validate_claim(c: dict) -> None:
    for f in ("id", "beat", "claim_text", "source_type", "extracted_by", "extracted_at"):
        _require(c, f)
    _require(c, "quote", "missing required field: quote (must be exact source text)")
    _require(c, "confidence_justification", "missing required field: confidence_justification")

    if not (c.get("source_url") or c.get("source_doi")):
        raise SchemaError("claim needs at least one source pointer: source_url or source_doi")

    st = c["source_type"]
    if requires_doi(st) and not c.get("source_doi"):
        raise SchemaError(f"source_type {st!r} requires a doi (source_doi)")

    tier = c.get("tier")
    if tier not in TIERS:
        raise SchemaError(f"unknown tier {tier!r}; expected one of {sorted(TIERS)}")

    conf = c.get("confidence")
    if not isinstance(conf, (int, float)):
        raise SchemaError("missing or non-numeric confidence")
    try:
        check_confidence(st, float(conf))
    except CeilingError as e:
        raise SchemaError(f"ceiling: {e}") from e


def validate_source(s: dict) -> None:
    for f in ("sha256", "url", "title", "source_name", "source_type", "published_at"):
        _require(s, f)
    _require(s, "first_seen",
             "missing required field: first_seen (needed for recirculation detection)")
    if not isinstance(s.get("candidate_beats"), list):
        raise SchemaError("candidate_beats must be a list")


# ── A state field describes the world, not the ledger ────────────────────────
# The premise of the whole format is that a beat is STATE, not a stream. A field
# whose value is "the most recent claim", or whose value is a count of how many
# claims we hold, changes every day by construction — so every beat always
# moves, "material change" stops meaning anything, and the delta degenerates
# into a feed with extra steps.
#
# This was not hypothetical. The dry-run state proposer emitted exactly those two
# fields and the site rendered eight beats of confident, meaningless movement.
# Nothing in the schema objected, because the fields cited their claims properly.
# Grounded and vacuous are different failures.
LEDGER_SELF_REFERENCE = (
    r"^(?:most[ _-]?recent|latest|newest|last|current)\b",
    r"\bclaims?[ _-]on[ _-]record\b", r"\bnumber[ _-]of[ _-]claims?\b",
    r"\bclaim[ _-]count\b", r"\bsources?[ _-]count\b", r"\bcoverage[ _-]volume\b",
    r"\barticles?[ _-]seen\b", r"\bstories[ _-]published\b",
)


def _self_referential(key: str) -> bool:
    k = str(key or "").strip().lower()
    return any(re.search(p, k) for p in LEDGER_SELF_REFERENCE)


def _restates_a_claim(value, claim_texts) -> bool:
    """Is this value just the beginning of one of its own citations?

    A truncating restatement has a characteristic shape: the field value is a
    verbatim prefix of the claim it cites. A genuine state value ("Filed 5 Aug
    2026, D.D.C.") is a fact ABOUT the world that a claim happens to support; a
    restatement IS the claim, shortened.
    """
    v = " ".join(str(value or "").split()).rstrip(".…").lower()
    if len(v) < 25:
        return False
    return any(" ".join(str(t or "").split()).lower().startswith(v)
               for t in (claim_texts or ()))


def validate_beat_state(st: dict, claim_texts=None) -> None:
    for f in ("beat", "as_of"):
        _require(st, f)
    fields = st.get("fields")
    if not isinstance(fields, list):
        raise SchemaError("fields must be a list")
    if len(fields) < 2:
        raise SchemaError("a beat needs at least two changeable state fields to exist")
    for f in fields:
        if "k" not in f or "v" not in f:
            raise SchemaError("each state field needs k and v")
        # EVERY STATE FIELD MUST CITE THE CLAIMS THAT SUPPORT IT.
        # The design says the delta is computed rather than written, but a diff
        # over ungrounded model output is still ungrounded: without this, a state
        # proposer can invent a field and its value, and the deterministic diff
        # faithfully reports an invention as a change.
        cites = f.get("claims")
        if not isinstance(cites, list) or not cites:
            raise SchemaError(
                f"state field {f.get('k')!r} cites no claims; a field the ledger "
                "cannot trace to evidence may not exist")
        # ...and a grounded field can still be vacuous.
        if _self_referential(f.get("k")):
            raise SchemaError(
                f"state field {f.get('k')!r} describes the ledger, not the world. "
                "A field that restates the newest claim or counts our own records "
                "changes every day by construction, so the beat always 'moves' and "
                "material change stops meaning anything.")
        if _restates_a_claim(f.get("v"), claim_texts):
            raise SchemaError(
                f"state field {f.get('k')!r} restates the claim it cites rather than "
                "describing a condition of the world. A beat is state, not a stream.")
