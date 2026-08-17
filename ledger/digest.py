"""The delta digest: what moved since each beat last appeared.

This is the Sleuthsletter form — "here is what changed" across every beat — but
generated rather than curated by people, and on an ADAPTIVE cadence rather than
a clock.

Cadence is per-beat by construction, which is the point. A beat appears in an
issue only when its own state has changed since the last issue it appeared in.
A shooting war shows up in nearly every issue; a court case awaiting a September
filing shows up when the filing lands, or when the deadline passes and it
doesn't. Nobody configures a schedule — the news sets it, per beat, and the
digest simply reports who has something to say.

Two rules carry the format:

  It must never pad. An issue full of "no change" entries is a status page, not
  a digest, and it teaches the reader to skip. So the digest refuses to fire on
  nothing, and quiet beats are counted rather than enumerated.

  A lapsed deadline is news by itself. A dated obligation passing without the
  expected filing is a finding, and it is the one thing a reader cannot get by
  watching the wire — nothing happening produces no headline anywhere.

Everything here is a projection of field transitions already on the record. No
model, no cost, and nothing it can say that the ledger does not already hold.
"""
from __future__ import annotations

# One beat moving is a story, and the front page already carries it. A digest of
# a single entry is a news alert in a digest's clothes.
MIN_DUE = 3
# ...but a slow week still gets an issue, so the reader can tell a quiet
# newsroom from a broken one. This only applies when something is actually due.
MAX_WAIT_DAYS = 7


def lapsed_triggers(triggers, today: str) -> list:
    """Dated obligations whose date has passed.

    Strictly before today: a deadline falling today has not yet been missed,
    and reporting it as lapsed would be asserting a failure that has not
    happened.
    """
    out = []
    for t in triggers or []:
        d = str((t or {}).get("sort") or "")
        if len(d) == 10 and d < str(today):
            out.append(dict(t))
    return sorted(out, key=lambda t: (t.get("sort", ""), t.get("beat", "")))


def due_beats(beats, last_seen: dict) -> list:
    """Beats whose state has changed since they last appeared in an issue.

    `beats` are {beat, changed_on, changes}; `last_seen` maps beat -> the day of
    the last issue it appeared in. A beat with no recorded change is never due:
    a beat can be open, monitored, and simply have nothing to say.
    """
    out = []
    for b in beats or []:
        changed_on = str((b or {}).get("changed_on") or "")
        if not changed_on or not (b or {}).get("changes"):
            continue
        if changed_on > str(last_seen.get(b.get("beat"), "")):
            out.append(dict(b))
    return sorted(out, key=lambda b: str(b.get("beat") or ""))


def should_fire(due, lapsed, days_since_last: int,
                today: str) -> tuple[bool, str]:
    """Does an issue go out? Returns (fires, the reason either way).

    The reason is returned in both directions on purpose. "Nothing has moved"
    is a legitimate state for a newsroom to be in and the operator should be
    able to read it, rather than having to infer it from an absence.
    """
    if lapsed:
        first = lapsed[0]
        return True, (f"{len(lapsed)} dated obligation(s) lapsed, including "
                      f"{first.get('t', 'one')!r} due {first.get('sort')}")
    if not due:
        return False, ("nothing has moved since the last issue; an issue of "
                       "'no change' entries teaches the reader to skip")
    if len(due) >= MIN_DUE:
        return True, f"{len(due)} beats moved"
    if days_since_last >= MAX_WAIT_DAYS:
        return True, (f"{len(due)} beat(s) moved and {days_since_last} days "
                      "since the last issue")
    return False, (f"only {len(due)} beat(s) moved and it has been "
                   f"{days_since_last} day(s); holding for more")


def compose(due, quiet: int, lapsed, day: str, names: dict) -> dict:
    """Build the issue. Does NOT decide whether it publishes — should_fire does.

    A field appearing for the first time is marked `new` rather than rendered as
    a change from nothing: "-> Approved" is a dangling arrow, and "from: ''"
    invites a reader to think a previous value existed.
    """
    entries = []
    for b in due or []:
        slug = b.get("beat")
        changes = []
        for c in b.get("changes") or []:
            was = str(c.get("from") or "")
            changes.append({"k": c.get("k"), "from": was,
                            "to": str(c.get("to") or ""), "new": was == ""})
        entries.append({
            "beat": slug,
            "name": names.get(slug) or str(slug or "").replace("-", " ").capitalize(),
            "changed_on": b.get("changed_on"),
            "changes": changes,
        })

    return {
        "day": day,
        "entries": entries,
        # Counted, never listed. Naming twelve beats to say nothing happened to
        # them is exactly the padding this format cannot survive.
        "quiet": int(quiet or 0),
        "lapsed": [dict(t) for t in (lapsed or [])],
        "empty": not entries and not lapsed,
    }
