"""Confidence ceilings by source type.

A blog post cannot carry 0.95 confidence regardless of how clearly it is written.
Ceilings are enforced by rejection at write time, not by flagging afterwards.
"""
from __future__ import annotations

CEILINGS: dict[str, float] = {
    "article": 1.0, "inproceedings": 0.95, "book": 0.9, "preprint": 0.85,
    "documentation": 0.85, "techreport": 0.8, "repo": 0.8, "blog": 0.7,
    "news": 0.6, "misc": 0.5,
}
DOI_REQUIRED = frozenset({"article", "inproceedings", "preprint"})
DEFAULT = "misc"


class CeilingError(ValueError):
    """A claim's confidence is out of range or exceeds its source type's ceiling."""


def ceiling_for(source_type: str) -> float:
    return CEILINGS.get(source_type, CEILINGS[DEFAULT])


def requires_doi(source_type: str) -> bool:
    return source_type in DOI_REQUIRED


def check_confidence(source_type: str, confidence: float) -> None:
    if not 0.0 <= confidence <= 1.0:
        raise CeilingError(f"confidence {confidence} out of range [0,1]")
    cap = ceiling_for(source_type)
    if confidence > cap + 1e-9:
        raise CeilingError(
            f"confidence {confidence} exceeds ceiling {cap} for source_type {source_type!r}"
        )
