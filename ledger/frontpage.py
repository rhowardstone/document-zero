"""Front page play: what leads, what follows, and what the page admits to.

The editor decides which beats moved and how much they matter (ledger/rank.py,
ledger/editor.py). This module turns that ranking into the shape of a page.

Two things here are not layout decisions and should not be treated as such.

A beat whose ARTICLE was refused still moved. Its prose failed the entailment
gate; the underlying fact did not. It drops to a one-line entry stating the bare
change, which needs no prose to support it. Dropping it entirely would mean the
page is quieter on days when the writing was worst, which is exactly backwards.

A day on which nothing survived still publishes a page that says so. Silence and
failure must never look the same to a reader. `nothing_survived` is set so the
front end can say which one happened, and the refusal counts are carried so a
reader can tell restraint from having nothing to say.

No model, no cost. Pure function of its inputs.
"""
from __future__ import annotations

SECONDARY_MAX = 5


def play(scored, day: str, refused=(), holds=(), counts=None) -> dict:
    """Compose the page.

    scored   — [(Article, score)], any order
    refused  — [{beat, name, changed, reason}] for articles that failed the gate
    holds    — beats the editor placed in the hold lane
    counts   — {refused: n, holds: n, ...} lane counts from the edition

    Returns plain dicts, ready for the renderer.
    """
    # Sort by score descending, then by beat id, so a tie does not shuffle the
    # page between runs. A front page that reorders itself for no reason makes
    # every reader wonder what changed.
    ordered = sorted(scored, key=lambda pair: (-float(pair[1]), pair[0].beat))
    articles = [a for a, _ in ordered]

    lead = articles[0].as_dict() if articles else None
    secondary = [a.as_dict() for a in articles[1:1 + SECONDARY_MAX]]

    also = [{"beat": a.beat, "name": a.beat, "headline": a.headline,
             "changed": a.standfirst, "reason": "below the fold"}
            for a in articles[1 + SECONDARY_MAX:]]
    also += [{"beat": r.get("beat"), "name": r.get("name") or r.get("beat"),
              "headline": None, "changed": r.get("changed", ""),
              "reason": r.get("reason", "article refused")}
             for r in refused]

    c = dict(counts or {})
    return {
        "date": day,
        "lead": lead,
        "secondary": secondary,
        "also_moving": also,
        "nothing_survived": lead is None,
        "holds": [dict(h) for h in holds],
        # Counts only. The content of a refused item is the thing the refusal
        # exists to withhold; the count is what lets a reader tell restraint
        # from having nothing to say.
        "did_not_publish": {k: int(v) for k, v in c.items()
                            if isinstance(v, (int, float))},
    }
