"""State diff. The edition is this function applied to every changed beat.

A model renders the result into prose; it does not decide what changed.
"""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Changed:
    k: str
    old: str
    new: str


@dataclass(frozen=True)
class Field:
    k: str
    v: str


@dataclass(frozen=True)
class StateDelta:
    beat: str
    from_date: str | None
    to_date: str | None
    changed: tuple[Changed, ...] = ()
    added: tuple[Field, ...] = ()
    removed: tuple[Field, ...] = ()
    unchanged: int = 0

    @property
    def is_empty(self) -> bool:
        return not (self.changed or self.added or self.removed)

    @property
    def material_changes(self) -> int:
        return len(self.changed) + len(self.added) + len(self.removed)


def _as_map(state):
    return {f["k"]: f for f in (state or {}).get("fields", [])}


def diff_state(old, new) -> StateDelta:
    """Compare two beat states by field VALUE.

    A change to `since` with no change to `v` is bookkeeping, not news, and is
    deliberately not counted as a change.
    """
    o, n = _as_map(old), _as_map(new)
    changed = tuple(Changed(k, o[k].get("v"), n[k].get("v"))
                    for k in n if k in o and o[k].get("v") != n[k].get("v"))
    added = tuple(Field(k, n[k].get("v")) for k in n if k not in o)
    removed = tuple(Field(k, o[k].get("v")) for k in o if k not in n)
    unchanged = sum(1 for k in n if k in o and o[k].get("v") == n[k].get("v"))
    return StateDelta(
        beat=(new or old or {}).get("beat"),
        from_date=(old or {}).get("as_of"),
        to_date=(new or {}).get("as_of"),
        changed=changed, added=added, removed=removed, unchanged=unchanged,
    )
