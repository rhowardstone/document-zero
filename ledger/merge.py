"""Merge a beat that opened twice under two names.

continuity.py stops new duplicates from opening. It cannot fix the ones already
on disk, and three pairs predate it:

    indiana-record-flooding            / indiana-record-flooding-august-2026
    democrats-2028-calendar-and-...    / democrats-2028-primary-calendar
    us-iran-war-and-hormuz-blockade    / us-iran-war-and-stalled-ceasefire-talks

Each is one story wearing two beats. That is not cosmetic: a beat is the
persistent object this whole system is built on, so a split beat means neither
half accumulates history and both are permanently on their first day — the
"news as a feed with extra steps" failure the project exists to avoid.

Merging is destructive and re-running the pipeline will not undo it, so every
rule here fails toward keeping material rather than losing it:

  - Claims are never dropped. Identical claims collapse to one; claims that
    differ all survive, because deciding which version of a disputed fact to
    discard is not a decision a file-mover should be making.
  - The surviving state is one side's, whole. Merging field by field would
    synthesise a state that neither beat ever actually had, and the state is
    supposed to be a record of something.
  - The merge is recorded. A beat that silently disappears takes its URL with
    it, and anyone holding that link is owed an explanation rather than a 404.

No model, no cost.
"""
from __future__ import annotations
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Plan:
    winner: str
    losers: list = field(default_factory=list)


def _state(root: Path, slug: str) -> dict:
    try:
        return json.loads((root / "beats" / slug / "state.json").read_text("utf-8"))
    except (OSError, ValueError):
        return {}


def _claim_files(root: Path, slug: str) -> list:
    d = root / "claims" / slug
    return sorted(d.glob("*.json")) if d.is_dir() else []


def plan(root, slugs) -> Plan:
    """Decide which of a duplicate set survives.

    The later state wins: it is the one the newsroom most recently believed.
    Ties go to whichever beat has more claims, since that is where more of the
    story is actually on the record.
    """
    root = Path(root)
    slugs = list(slugs)
    if len(slugs) < 2:
        return Plan(winner=slugs[0] if slugs else "", losers=[])

    def rank(slug):
        return (str(_state(root, slug).get("as_of") or ""),
                len(_claim_files(root, slug)),
                slug)

    ordered = sorted(slugs, key=rank, reverse=True)
    return Plan(winner=ordered[0], losers=ordered[1:])


def apply(root, p: Plan) -> Plan:
    """Carry out the merge. Returns the plan it executed."""
    root = Path(root)
    if not p.losers:
        return p

    win_claims = root / "claims" / p.winner
    win_claims.mkdir(parents=True, exist_ok=True)
    # Identity is the claim TEXT. Two extractions of the same sentence from the
    # same story are one fact reaching us twice, not corroboration.
    seen = {_identity(f) for f in _claim_files(root, p.winner)}

    history = _history(root, p.winner)

    for loser in p.losers:
        for f in _claim_files(root, loser):
            ident = _identity(f)
            if ident in seen:
                continue
            seen.add(ident)
            # Prefix the filename with the beat it came from so a collision
            # between two beats' claim_001.json cannot silently overwrite.
            shutil.copy2(f, win_claims / f"{loser}__{f.name}")

        history += _history(root, loser)

        (root / "merges").mkdir(parents=True, exist_ok=True)
        (root / "merges" / f"{loser}.json").write_text(json.dumps({
            "beat": loser, "merged_into": p.winner,
            "reason": "duplicate beat: the same story opened under two names",
        }, indent=1), encoding="utf-8")

        shutil.rmtree(root / "beats" / loser, ignore_errors=True)
        shutil.rmtree(root / "claims" / loser, ignore_errors=True)

    if history:
        history.sort(key=lambda r: str(r.get("day") or r.get("at") or ""))
        (root / "beats" / p.winner / "history.jsonl").write_text(
            "".join(json.dumps(r) + "\n" for r in history), encoding="utf-8")
    return p


def _identity(f: Path) -> str:
    try:
        return " ".join(str(json.loads(f.read_text("utf-8"))
                            .get("claim_text", "")).lower().split())
    except (OSError, ValueError):
        return f.name


def _history(root: Path, slug: str) -> list:
    hp = root / "beats" / slug / "history.jsonl"
    if not hp.exists():
        return []
    out = []
    for line in hp.read_text("utf-8").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out
