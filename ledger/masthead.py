"""Whether the day publishes, and what the masthead may claim.

Both halves of this module exist because of the same failure, which this
project keeps re-committing in new places: rendering a failure to know, or a
leftover default, as a statement about the world.

`publish: false, blocked_by: "dry_run"` was a literal written during the
stub-reporter era and never removed. On 2026-08-17 three articles passed the
entailment gate and the live page told readers the editor had blocked
publication. Nobody had blocked anything. Publication is a decision about the
day's material, so it is computed from the day's material.

The masthead printed `updated: "—"` and `next: "—"` unconditionally. An em-dash
where a timestamp belongs looks like restraint and is actually noise: it is
indistinguishable from a genuine gap. So the masthead returns None for anything
the ledger cannot support, and the page decides how to show not-knowing — but
it can no longer be handed a confident-looking placeholder.

`next` is the sharpest case. Nothing is scheduled yet. A next-edition time on
the masthead would be the newsroom asserting a fact about its own future that
no cron entry backs up, which is exactly the kind of claim the entailment gate
would refuse if a reporter wrote it in prose.

No model, no cost.
"""
from __future__ import annotations

NOTHING_SURVIVED = ("nothing survived the entailment gate; "
                    "no article could be supported by its claims")


def decide(articles, blocked: str | None = None) -> tuple[bool, str | None]:
    """Does the paper come out? Returns (publish, reason_it_did_not).

    An explicit hold always wins: a human or the editor stage stopping the
    paper is a decision, and its reason is shown verbatim, because a blocked
    edition with an unexplained cause is worse than no edition at all.
    """
    if blocked:
        return False, str(blocked)
    if not articles:
        return False, NOTHING_SURVIVED
    return True, None


def masthead(articles, next_run: str | None = None) -> dict:
    """What the top of the page may state as fact.

    Every value is either drawn from the ledger or None. There are no
    placeholders here, because a placeholder that looks like data is the bug.
    """
    stamps = sorted(s for s in (_stamp(a) for a in (articles or [])) if s)
    return {
        "updated": stamps[-1] if stamps else None,
        "next": next_run or None,
        "articles": len(articles or []),
    }


def _stamp(article) -> str | None:
    """An ISO timestamp, or nothing. A string that is not a time is not a time."""
    v = str((article or {}).get("published_at") or "").strip()
    if len(v) < 10 or v[4] != "-" or v[7] != "-":
        return None
    return v


def editorial_day(day, today: str | None = None) -> str:
    """Validate the day an edition is being built for.

    The editorial day is LOCAL, deliberately. UTC rolls over at 8pm Eastern, so
    a UTC day would datelined an evening edition tomorrow — and that reached the
    live site: an edition built for 2026-08-17 while every source in it was
    filed on the 16th. A masthead that disagrees with its own reporting is
    wrong in the one field a reader checks first.

    A past day is fine. Rebuilding an old edition is legitimate, and that day's
    articles are already fixed. Only the future is refused, because there is no
    reporting from it.
    """
    import re
    import time

    d = str(day or "")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
        raise ValueError(f"editorial day {day!r} is not an ISO date (YYYY-MM-DD)")
    now = today or time.strftime("%Y-%m-%d")     # local, not UTC
    if d > now:
        raise ValueError(
            f"editorial day {d} is in the future (today is {now}). A paper "
            "datelined tomorrow contradicts every source in it — check whether "
            "the caller used UTC instead of local time.")
    return d
