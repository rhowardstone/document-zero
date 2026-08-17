#!/usr/bin/env python3
"""Lint the roster. The lint failing blocks the merge.

Every routine treats `beats.yaml` as authoritative state, which makes a
malformed entry a newsroom-wide outage that announces itself as a quiet day: the
desks find no beats, report a normal outcome, and because empty runs are silent
nothing alerts. The site sits under yesterday's honest date indefinitely.

That is not hypothetical. It is what shipped: the roster was prose, listing beats
under "Standing beats" and never naming a desk, while desk.md looked for beats
"listed under your name". Four desks, zero beats, no alarm.

Prose cannot be checked, so the state moved into YAML and got this.

    scripts/lint_beats.py [path]      exit 0 clean, 1 with errors on stderr
"""
from __future__ import annotations
import re
import sys

TIERS = ("standing", "watch")
MIN_FIELDS = 2
ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Fields that increment by definition. A beat resting on one is due in every
# issue forever, which permanently inflates the delta's "three beats are due"
# threshold and destroys the adaptive cadence the delta exists for.
CLOCK_DERIVED = re.compile(
    r"(?i)^(days?|weeks?|months?|years?|hours?|time) (at|since|until|to|in|"
    r"elapsed|remaining)\b|\b(days?|weeks?|months?) (elapsed|remaining|so far)\b"
    r"|^time (to|until)\b")

# Fields describing our own bookkeeping rather than the world. A reader learns
# nothing from them, and they can never fail to change.
SELF_REFERENTIAL = re.compile(
    r"(?i)\b(most recent|last updated|claims? on record|number of (sources?|"
    r"claims?|articles?)|record count|our records|latest claim|entries)\b")


class LintError(Exception):
    """The file could not be read as a roster at all."""


def lint(doc) -> list:
    """Return a list of human-readable errors. Empty means clean."""
    if not isinstance(doc, dict):
        raise LintError(f"roster is {type(doc).__name__}, not a mapping")

    errs = []
    desks = list(doc.get("desks") or [])
    if not desks:
        errs.append("no desks declared")

    beats = doc.get("beats")
    if beats is None:
        errs.append("no beats key: the roster must list its beats explicitly")
        return errs
    if not isinstance(beats, list) or not beats:
        errs.append("no beats in the roster — this is an outage, not a quiet day")
        return errs

    seen, owned = set(), set()
    for i, b in enumerate(beats):
        if not isinstance(b, dict):
            errs.append(f"beat {i}: not a mapping")
            continue
        slug = str(b.get("slug") or "")
        where = f"beat {i} ({slug or 'no slug'})"

        if not slug:
            errs.append(f"{where}: no slug")
        elif slug in seen:
            errs.append(f"{where}: duplicate slug — one story cannot be two beats")
        seen.add(slug)

        if not str(b.get("name") or "").strip():
            errs.append(f"{where}: no name. The slug is machine text and must "
                        "never be shown to a reader")

        desk = b.get("desk")
        if not desk:
            errs.append(f"{where}: no desk. Nothing will report this beat")
        elif desk not in desks:
            errs.append(f"{where}: unknown desk {desk!r} — that desk is not "
                        f"scheduled, so this beat is silently unreported")
        else:
            owned.add(desk)

        tier = b.get("tier")
        if tier not in TIERS:
            errs.append(f"{where}: tier {tier!r} is not one of {list(TIERS)}")

        # A field is either a plain name, or a mapping carrying flags.
        names, movable = [], 0
        for f in (b.get("fields") or []):
            if isinstance(f, dict):
                nm = str(f.get("name") or "")
                is_clock = bool(f.get("clock"))
            else:
                nm = str(f)
                is_clock = bool(CLOCK_DERIVED.search(nm))
                if is_clock:
                    errs.append(
                        f"{where}: field {nm!r} looks clock-derived but is not "
                        "marked. Write it as {name: ..., clock: true} — an "
                        "unmarked ticking field makes this beat due in every "
                        "issue forever and destroys the delta's cadence")
            if not nm:
                errs.append(f"{where}: a field has no name")
                continue
            names.append(nm)
            if not is_clock:
                movable += 1

        if movable < MIN_FIELDS:
            errs.append(f"{where}: {movable} non-clock field(s); a beat needs at "
                        f"least {MIN_FIELDS} that tomorrow's events could change "
                        "AND that could fail to change. Clock fields increment by "
                        "definition and never count")
        for nm in names:
            if SELF_REFERENTIAL.search(nm):
                errs.append(f"{where}: field {nm!r} describes our own records, "
                            "not the world. It can never fail to change")

        opened = str(b.get("opened") or "")
        if not ISO.match(opened):
            errs.append(f"{where}: opened {opened!r} is not an ISO date "
                        "(YYYY-MM-DD). MM-DD-YYYY does not sort chronologically")

        for j, d in enumerate(b.get("deadlines") or []):
            if not isinstance(d, dict):
                errs.append(f"{where}: deadline {j} is not a mapping")
                continue
            if not ISO.match(str(d.get("date") or "")):
                errs.append(f"{where}: deadline {j} has no ISO date. A deadline "
                            "with no date can never lapse")
            if not str(d.get("what") or "").strip():
                errs.append(f"{where}: deadline {j} has no description")
            if not str(d.get("authority") or "").strip():
                errs.append(f"{where}: deadline {j} has no `authority` — the "
                            "record where absence must be checked. Without it, "
                            "'the deadline passed with nothing filed' cannot be "
                            "verified: a search failing to find a filing is not "
                            "evidence that none exists")

    for d in desks:
        if d not in owned:
            errs.append(f"desk {d!r} owns no beats: it is scheduled to run and "
                        "do nothing. Assign it a beat or stop scheduling it")
    return errs


def main(argv) -> int:
    import yaml
    path = argv[1] if len(argv) > 1 else "beats.yaml"
    try:
        doc = yaml.safe_load(open(path, encoding="utf-8"))
    except OSError as e:
        print(f"cannot read {path}: {e}", file=sys.stderr)
        return 1
    try:
        errs = lint(doc)
    except LintError as e:
        print(f"{path}: {e}", file=sys.stderr)
        return 1

    if errs:
        print(f"{path}: {len(errs)} problem(s)", file=sys.stderr)
        for e in errs:
            print(f"  {e}", file=sys.stderr)
        return 1

    n = len(doc.get("beats") or [])
    desks = ", ".join(doc.get("desks") or [])
    print(f"{path}: {n} beat(s) across {desks} — clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
