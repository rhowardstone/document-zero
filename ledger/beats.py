"""Beat registry, lifecycle rules, and keyword assignment.

A beat is a unit of persistent state: something whose current condition can be
written in fields, so that each new event either changes a field or does not.

Close criteria are not optional. A system that only opens beats degrades into a
topic list within a quarter.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date
import re

OPEN_MIN_EVENTS = 3
OPEN_MIN_SPAN_DAYS = 5
OPEN_MIN_STATE_FIELDS = 2
CLOSE_QUIET_DAYS = 30


@dataclass(frozen=True)
class Beat:
    id: str
    name: str
    keywords: list[str] = field(default_factory=list)
    dossiers: tuple[str, ...] = ()
    types: tuple[str, ...] = ()


def _span_days(events) -> int:
    days = sorted({e["day"] for e in events})
    if len(days) < 2:
        return 0
    return (date.fromisoformat(days[-1]) - date.fromisoformat(days[0])).days


def should_open(events, has_trigger: bool, state_fields: int) -> bool:
    if state_fields < OPEN_MIN_STATE_FIELDS:
        return False
    if has_trigger and len(events) >= 1:
        return True
    return len(events) >= OPEN_MIN_EVENTS and _span_days(events) >= OPEN_MIN_SPAN_DAYS


def should_close(days_since_change: int, pending_triggers: int) -> bool:
    return pending_triggers == 0 and days_since_change >= CLOSE_QUIET_DAYS


def assign_beats(text: str, beats, threshold: float = 0.0):
    """Score beats by keyword overlap. Returns [(beat_id, score)] descending.

    Deliberately dumb and model-free: this runs on every ingested item at tier 1.
    Every assignment is logged with its score so misassignment can be measured
    before deciding whether a classifier is warranted.
    """
    low = text.lower()
    scored = []
    for b in beats:
        if not b.keywords:
            continue
        hits = sum(1 for k in b.keywords if re.search(r"\b" + re.escape(k.lower()), low))
        if hits:
            scored.append((b.id, hits / len(b.keywords)))
    scored.sort(key=lambda x: (-x[1], x[0]))
    return [s for s in scored if s[1] > threshold]


def load_beats(path) -> list[Beat]:
    """Load the beat registry from config. Beats are data, not code."""
    import yaml
    rows = yaml.safe_load(open(path, encoding="utf-8"))
    return [Beat(id=r["id"], name=r["name"], keywords=list(r.get("keywords", [])),
                 dossiers=tuple(r.get("dossiers", ())), types=tuple(r.get("types", ())))
            for r in rows]


def load_beat_meta(path) -> dict:
    """Per-beat editorial inputs for ranking. Consequence is a judgement; it is
    published as config rather than hidden inside a model, so it can be argued with."""
    import yaml
    rows = yaml.safe_load(open(path, encoding="utf-8"))
    return {r["id"]: {"consequence": r.get("consequence", 5),
                      "coverage": r.get("coverage", 5),
                      "name": r["name"]} for r in rows}
