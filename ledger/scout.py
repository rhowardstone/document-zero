"""Beats come from the news, not from a file.

v1 declared 22 beats in `config/beats.yaml` with keyword lists. They could not
open and could not close, so coverage never grew and never shrank: twenty sat
permanently empty while the front page showed two, both the same story. A system
whose coverage is a list someone typed cannot discover anything.

The scout reads the day's wire (ledger/wire.py), clusters it (ledger/emerge.py),
and turns clusters into proposals. The beat test from the v1 spec §2.1 decides.
It is retained verbatim because it was correct — what was missing was anything
that ran it.

Rejected proposals are RECORDED with their reason, so the ledger shows what was
considered rather than only what was covered. An automated newsroom that
silently discards candidates is indistinguishable from one that never looked.

Division of labour, which is the point of this module's shape:

  arithmetic  — how many articles, over how many days, from how many newsrooms.
                Free, deterministic, computed here.
  judgement   — what this story's changeable state fields ARE. That is a
                reporter's question, not a countable one, so `state_fields` is
                left empty for the scout agent to fill and a proposal without
                them cannot open.

No model, no cost.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from datetime import datetime

MIN_EVENTS = 3
MIN_SPAN_DAYS = 5
MIN_STATE_FIELDS = 2
QUIET_DAYS_TO_CLOSE = 30


@dataclass
class Proposal:
    name: str
    slug: str
    events: int = 0
    span_days: int = 0
    state_fields: list = field(default_factory=list)
    dated_trigger: str | None = None
    publishers: set = field(default_factory=set)
    articles: list = field(default_factory=list)

    def as_record(self, opened: bool, reason: str) -> dict:
        """What gets written to proposals/ — including the rejections."""
        return {
            "name": self.name, "slug": self.slug, "opened": bool(opened),
            "reason": reason, "events": self.events, "span_days": self.span_days,
            "state_fields": list(self.state_fields),
            "dated_trigger": self.dated_trigger,
            "publishers": sorted(self.publishers),
            "articles": [{"url": a.get("url"), "title": a.get("title"),
                          "publisher": a.get("publisher")}
                         for a in self.articles],
        }


def beat_test(p: Proposal) -> tuple[bool, str]:
    """The v1 §2.1 test. Returns (opens, reason).

    The question is not "is this interesting" but "can I write this thing's
    current condition as fields such that tomorrow's events either change one or
    do not". Everything else is a story, and a story with no changeable state is
    a line in the paper rather than a beat.
    """
    if len(p.state_fields) < MIN_STATE_FIELDS:
        return False, (f"{len(p.state_fields)} state field(s); a beat needs "
                       f"{MIN_STATE_FIELDS} that tomorrow's events could change")
    if p.dated_trigger:
        return True, f"dated trigger {p.dated_trigger}"
    if p.events < MIN_EVENTS:
        return False, (f"{p.events} event(s); needs {MIN_EVENTS}, "
                       "or one dated trigger")
    if p.span_days < MIN_SPAN_DAYS:
        return False, (f"{p.span_days} day(s); needs {MIN_SPAN_DAYS} — a single "
                       "day's flurry is an event, not a beat")
    return True, f"{p.events} events over {p.span_days} days"


def should_close(days_since_change: int, pending_triggers: int) -> bool:
    """A beat awaiting a filing deadline is not dead, it is waiting."""
    if pending_triggers > 0:
        return False
    return days_since_change > QUIET_DAYS_TO_CLOSE


def slug_for(name: str, taken=()) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")[:48] or "story"
    base, n = s, 2
    while s in taken:
        s = f"{base}-{n}"
        n += 1
    return s


def _day(stamp: str):
    try:
        return datetime.strptime(str(stamp)[:10], "%Y-%m-%d").date()
    except Exception:                                    # noqa: BLE001
        return None


def propose_from_cluster(cluster, name: str, taken=()) -> Proposal:
    """Turn an emerge.Cluster into a Proposal, computing only what is countable.

    `state_fields` is deliberately left empty. Deciding what a story's
    changeable fields are is reporting, not arithmetic, and a proposal without
    them fails the beat test — so nothing can open by counting alone.
    """
    arts = list(getattr(cluster, "articles", []))
    days = sorted(d for d in (_day(getattr(a, "published_at", "")) for a in arts) if d)
    span = (days[-1] - days[0]).days if len(days) >= 2 else 0
    return Proposal(
        name=name,
        slug=slug_for(name, taken),
        events=len(arts),
        span_days=span,
        state_fields=[],
        publishers={getattr(a, "publisher", "") for a in arts if getattr(a, "publisher", "")},
        articles=[{"url": getattr(a, "url", ""), "title": getattr(a, "title", ""),
                   "publisher": getattr(a, "publisher", "")} for a in arts],
    )
