"""Which story leads the page.

The lead slot is the one piece of pure editorial judgement a front page makes.
It says: of everything that happened, this mattered most. Getting it by accident
is worse than getting it wrong on purpose, because nobody can argue with an
accident.

On 2026-08-17 three articles passed the entailment gate and the page ordered
them by beat slug — so record flooding in Indiana led over a shooting war and a
carrier deployment, because "i" sorts before "u".

The rule is deliberately measurable rather than clever: lead with the story the
most independent newsrooms put on the record. Corroboration is the only free
signal that is about the WORLD rather than about our own processing — how many
claims we happened to extract, or how long the reporter wrote, are facts about
us. It is also the only one a reader could check for themselves.

What this rule does NOT encode is consequence. A story on six wires is not
necessarily more important than a story on two; it is more widely reported, and
that is all this claims. v1 kept a hand-scored "consequence" number per beat in
config, which is a real judgement, but one that cannot be made for a beat that
opened this morning — and it silently became a ranking of the config file's
author rather than of the news.

No model, no cost. Pure function of its inputs.
"""
from __future__ import annotations


def weight(article: dict) -> tuple:
    """Sort key for the front page, highest first.

    A tuple rather than a number so the tiers stay separable and no amount of
    one signal can buy a position in another: corroboration is decided before
    claim count is consulted at all.

    Missing counts read as zero. A gap in our records must not crash the page,
    and must not promote a story either.
    """
    a = article or {}
    return (
        _n(a.get("publishers")),      # independent newsrooms on the record
        _n(a.get("claims")),          # how much of it we could establish
        # Ties fall back to the beat id, DESCENDING, because the caller sorts
        # descending — so the alphabetically first beat still wins a true tie.
        # Stability matters: a page that reshuffles between runs with no new
        # facts makes every reader wonder what changed.
        _invert(str(a.get("beat") or "")),
    )


def _n(v) -> int:
    try:
        return max(0, int(v))
    except (TypeError, ValueError):
        return 0


def _invert(s: str) -> tuple:
    """Reverse a string's sort order inside a descending sort."""
    return tuple(-ord(c) for c in s)


def order(articles):
    """The day's articles, lead first."""
    return sorted(articles or [], key=weight, reverse=True)
