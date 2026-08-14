"""Detect whether a cluster is new information or yesterday's news re-datelined.

  FRESH          the cluster originates today
  RECIRCULATION  a small origin followed by many same-day republishers
  DATE_CONFLICT  the origin materially predates the cluster; hold, do not publish
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

RECIRC_MIN_FOLLOWERS = 3
RECIRC_MIN_GAP_DAYS = 1
CONFLICT_GAP_DAYS = 60


class Verdict(Enum):
    FRESH = "fresh"
    RECIRCULATION = "recirculation"
    DATE_CONFLICT = "date_conflict"


@dataclass(frozen=True)
class Result:
    verdict: Verdict
    origin_date: str | None
    gap_days: int
    followers: int


def _parse(s):
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def analyse_cluster(sources, today: str) -> Result:
    today_dt = _parse(today + "T00:00:00Z")
    parsed = [(s, _parse(s.get("published_at"))) for s in sources]
    parsed = [(s, d) for s, d in parsed if d is not None]
    if not parsed:
        # Nothing datable. If anything was supplied but unparseable, prefer a hold.
        return Result(Verdict.DATE_CONFLICT if sources else Verdict.FRESH, None, 0, 0)

    _, origin = min(parsed, key=lambda p: p[1])
    # Day arithmetic must be on calendar dates, not timestamps: an origin ten hours
    # before midnight is one day earlier, not zero days earlier.
    origin_day = origin.date()
    gap_days = (today_dt.date() - origin_day).days
    followers = sum(1 for _, d in parsed
                    if (d.date() - origin_day).days >= RECIRC_MIN_GAP_DAYS)

    if gap_days >= CONFLICT_GAP_DAYS:
        return Result(Verdict.DATE_CONFLICT, origin_day.isoformat(), gap_days, followers)
    if gap_days >= RECIRC_MIN_GAP_DAYS and followers >= RECIRC_MIN_FOLLOWERS:
        return Result(Verdict.RECIRCULATION, origin_day.isoformat(), gap_days, followers)
    return Result(Verdict.FRESH, origin_day.isoformat(), gap_days, followers)
