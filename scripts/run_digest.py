#!/usr/bin/env python3
"""Build the delta digest from the ledger, if enough has moved.

    scripts/run_digest.py                 build if due, and say why either way
    scripts/run_digest.py --force         build regardless (still never pads)
    scripts/run_digest.py --dry           decide and report, write nothing

The cadence is adaptive and per-beat: a beat enters an issue only when its own
state changed since the last issue it appeared in. Nothing is scheduled. This
can therefore be run as often as you like — on a day when little moved it
declines to publish and explains itself, which is the correct behaviour for a
delta and the reason it can share the daily cron with the front page.

No model, no cost. Every value is a field transition already on the record.
"""
from __future__ import annotations
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
LEDGER = str(ROOT / "ledger-data")

from ledger.beats import beats_from_ledger                   # noqa: E402
from ledger.digest import (compose, due_beats, lapsed_triggers,  # noqa: E402
                           should_fire)
from ledger.masthead import editorial_day                    # noqa: E402
from ledger.render import build                              # noqa: E402
from ledger.store import Ledger                              # noqa: E402

STATE = "digests/last_seen.json"


def _read(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def beat_deltas(led: Ledger, slugs, day: str) -> list:
    """The most recent field transitions per beat, from its latest article.

    Articles carry the delta they were written from — {k, from, to, since} —
    which is exactly what a digest entry needs. Reading it from the article
    rather than recomputing it guarantees the digest and the story agree.
    """
    out = []
    for slug in slugs:
        arts = sorted((ROOT / "ledger-data" / "beats" / slug / "articles")
                      .glob("*.json")) if (ROOT / "ledger-data" / "beats" / slug
                                           / "articles").is_dir() else []
        if not arts:
            continue
        a = _read(arts[-1], {})
        changes = [c for c in (a.get("changed") or []) if c.get("k")]
        if not changes:
            continue
        out.append({"beat": slug, "changed_on": a.get("day") or arts[-1].stem,
                    "changes": changes})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", default=time.strftime("%Y-%m-%d"))
    ap.add_argument("--force", action="store_true",
                    help="publish even if the cadence says hold")
    ap.add_argument("--dry", action="store_true",
                    help="decide and report; write nothing")
    args = ap.parse_args()

    try:
        day = editorial_day(args.day)
    except ValueError as e:
        print(f"refusing to build: {e}")
        return 2

    led = Ledger(LEDGER)
    registry = beats_from_ledger(LEDGER)
    names = {b.id: b.name for b in registry}
    slugs = [b.id for b in registry]

    deltas = beat_deltas(led, slugs, day)
    seen_path = ROOT / "ledger-data" / STATE
    seen = _read(seen_path, {})
    last_issue = str(seen.get("_last_issue") or "")

    due = due_beats(deltas, {k: v for k, v in seen.items()
                             if not k.startswith("_")})
    data = build(LEDGER, None, day)
    lapsed = lapsed_triggers(data.get("triggers") or [], day)

    days_since = 999
    if len(last_issue) == 10:
        from datetime import date
        days_since = (date.fromisoformat(day) - date.fromisoformat(last_issue)).days

    fires, why = should_fire(due, lapsed, days_since, day)
    print(f"\n  {len(slugs)} beat(s) open, {len(due)} due, {len(lapsed)} lapsed "
          f"obligation(s), {days_since if days_since < 999 else 'no'} day(s) "
          "since the last issue")
    print(f"  {'PUBLISH' if fires else 'HOLD'} — {why}")

    if not fires and not args.force:
        return 0
    if args.force and not fires:
        print("  --force: publishing anyway")

    issue = compose(due, quiet=max(0, len(slugs) - len(due)), lapsed=lapsed,
                    day=day, names=names)
    if issue["empty"]:
        print("  nothing to say; no issue written")
        return 0

    print(f"\n── THE DELTA · {day} " + "─" * 44)
    for t in issue["lapsed"]:
        print(f"  LAPSED  {t.get('sort')}  {t.get('t')}")
    for e in issue["entries"]:
        print(f"\n  {e['name']}")
        for c in e["changes"]:
            if c["new"]:
                print(f"     {c['k']}: {c['to']}   (new)")
            else:
                print(f"     {c['k']}: {c['from']} → {c['to']}")
    if issue["quiet"]:
        print(f"\n  {issue['quiet']} beat(s) quiet")

    if args.dry:
        print("\n  --dry: nothing written")
        return 0

    w = Ledger(LEDGER, writer="editor")
    w._write_json(f"digests/{day}.json", issue)
    for e in issue["entries"]:
        seen[e["beat"]] = e["changed_on"]
    seen["_last_issue"] = day
    seen_path.parent.mkdir(parents=True, exist_ok=True)
    seen_path.write_text(json.dumps(seen, indent=1, sort_keys=True),
                         encoding="utf-8")
    print(f"\n  written to digests/{day}.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
