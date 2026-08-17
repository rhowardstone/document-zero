"""Has this beat already been written up today?

Articles are immutable — a correction is a new day's article, never an edit to
an old one. That rule is correct and stays. But it turned a normal operation
into what looked like a newsroom-wide collapse. The second full run of
2026-08-16 reported:

    5 article(s) survived, 7 did not
      indiana-record-flooding-august-2026    reporter failed
      nm-records                             reporter failed
      us-iran-war-and-hormuz-blockade        reporter failed

Every one of those had been written, verified and published hours earlier.
Nothing failed. Worse, the run paid for a reporter call and two verifier calls
per beat before discovering the result could not be stored.

So: check before writing. A beat already on the record today is DONE, which is
neither a failure nor a reason to spend anything.

The distinction matters beyond tidiness. "reporter failed" is what this system
says when the writing did not work; using the same words for "we already did
this" leaves the operator unable to tell the two apart — the same defect as the
inherited-stdin bug, where a pipeline condition wore an editorial costume.

No model, no cost.
"""
from __future__ import annotations
from pathlib import Path

from . import paths as P


def already_published(root, beat: str, day: str) -> bool:
    """True if an article for this beat and day is already on the record.

    Keys on the file EXISTING, deliberately not on it parsing. Immutability
    keys on existence too, so a corrupt article still blocks the write — and a
    check that disagreed with the store would send the run off to pay for an
    article it cannot keep.
    """
    return (Path(root) / P.article_path(beat, day)).exists()
