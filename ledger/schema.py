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


def validate_beat_state(st: dict) -> None:
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
