"""Beat registry, lifecycle rules, and keyword assignment.

A beat is a unit of persistent state: something whose current condition can be
written in fields, so that each new event either changes a field or does not.

Close criteria are not optional. A system that only opens beats degrades into a
topic list within a quarter.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date
import json
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


def beats_from_ledger(root) -> list[Beat]:
    """The registry IS the ledger. Beats that open by themselves are found here.

    v1 read the beat list from config/beats.yaml, so a beat that emerged from
    the news did not exist as far as the renderer was concerned. On 2026-08-17
    three articles passed the entailment gate, were stored under
    beats/<slug>/articles/, and the front page rendered EMPTY — every one of
    the three slugs was absent from a file typed weeks earlier.

    That is the same defect as the twenty-two beats that could never open or
    close, in its last hiding place: coverage decided by a static file rather
    than by what the newsroom actually did.

    Nothing here can fail loudly enough to lose a story. A beat with articles on
    disk is returned even if its name is unreadable, because dropping the story
    to protect the label is the wrong trade in both directions.
    """
    from pathlib import Path
    root = Path(root)
    bdir = root / "beats"
    if not bdir.is_dir():
        return []

    # Slugs are lossy: "us-iran-war-and-hormuz-blockade" is not what a reader
    # should be shown. The scout named the story in prose when it proposed it.
    names: dict[str, str] = {}
    pdir = root / "proposals"
    if pdir.is_dir():
        for f in sorted(pdir.glob("*.json")):      # date-prefixed: newest wins
            try:
                rec = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue   # unreadable metadata never costs us the story
            if rec.get("slug") and rec.get("name"):
                names[rec["slug"]] = rec["name"]

    return [Beat(id=d.name, name=names.get(d.name, _readable(d.name)))
            for d in sorted(bdir.iterdir()) if d.is_dir()]


def _readable(slug: str) -> str:
    """A last-resort display name. Never show a reader raw machine text."""
    return slug.replace("-", " ").strip().capitalize() or slug


def load_beat_meta(path) -> dict:
    """Per-beat editorial inputs for ranking. Consequence is a judgement; it is
    published as config rather than hidden inside a model, so it can be argued with."""
    import yaml
    rows = yaml.safe_load(open(path, encoding="utf-8"))
    return {r["id"]: {"consequence": r.get("consequence", 5),
                      "coverage": r.get("coverage", 5),
                      "name": r["name"]} for r in rows}
