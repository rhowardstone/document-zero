"""Is this the beat we already have, under a different name?

A beat is the persistent object in this system. Everything else — the delta,
the history, the article that says what changed — depends on today's reporting
landing on the SAME beat as yesterday's.

It did not. The desk agent names a story freshly each run, and a name that
varies produces a new slug, which produces a new beat:

    democrats-2028-calendar-and-party-direction
    democrats-2028-primary-calendar
    indiana-record-flooding
    indiana-record-flooding-august-2026
    us-iran-war-and-hormuz-blockade
    us-iran-war-and-stalled-ceasefire-talks

Six beats, three stories. Left alone this compounds daily: nothing accumulates
history, every beat is permanently on its first day, and "news as persistent
state" degrades into a feed with extra steps — the exact failure this project
exists to avoid.

Identity is therefore what a story is ABOUT, not what an agent called it today.
Entities are the stable part: "Hormuz", "Iran", "Lincoln" survive a rewording
that turns "stalled ceasefire talks" into "Hormuz blockade".

Deliberately conservative. A wrong merge welds two stories into one beat whose
state contradicts itself and cannot be separated afterwards; a missed merge
leaves a duplicate that can be merged later. When unsure, do not merge.
"""
from __future__ import annotations
import re

# Words that appear in half the news and identify nothing.
GENERIC = frozenset("""
news update latest report reports says said new first last next week month year
today live breaking analysis explainer what why how amid after before during
crisis talks deal plan push move state states united america american federal
national government administration policy officials official
the and for but its was are has had not all any out off own per via who nor yet
too she him her his they them their this that with from into over under
""".split())
# NOTE the three-letter entries above are stopwords, not a length rule. "DOJ",
# "FBI", "oil", "gas", "war", "law" and "tax" are three letters and identify a
# story; "the" and "and" are three letters and identify nothing.

# Measured on real duplicate pairs using NAMES ALONE, which is the weakest
# signal this will ever run on: same-story pairs scored 0.50 to 1.00, unrelated
# pairs scored 0.00 without exception. 0.40 sits in an empty gap.
#
# In production the signature also carries the beat's state fields and up to
# twenty-five claims, so a real comparison has far more to go on than a name.
MERGE_THRESHOLD = 0.40
# Hyphens SPLIT. "US-Iran" kept whole never matches a later "Iran ceasefire",
# and the entity is the half that identifies the story.
_TOKEN = re.compile(r"[A-Za-z][A-Za-z']{1,}")


def signature(*texts) -> set[str]:
    """The identifying words of a story: distinctive, lowercased, deduplicated."""
    out = set()
    for t in texts:
        for w in _TOKEN.findall(str(t or "").replace("-", " ")):
            lw = w.lower().strip("'-")
            if len(lw) >= 3 and lw not in GENERIC:
                out.add(lw)
    return out


def overlap(a: set, b: set) -> float:
    """Containment, not Jaccard.

    A beat that has run for a week carries far more vocabulary than one day's
    cluster, so a symmetric measure would score a correct match low purely
    because the older side knows more. What matters is whether the smaller of
    the two is largely contained in the other.
    """
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


# A signature far smaller than the one it is compared against is trivially
# "contained" in it. Measured: a 42-token beat scored 0.62 against a 339-token
# beat on shared PROCESS vocabulary — complaint, investigation, department — and
# would have been welded onto a different story. Genuine duplicates were
# comparably sized and shared ENTITIES: adnoc, hormuz, carrier.
MIN_SIZE_RATIO = 0.25


def match(proposal_sig: set, existing: dict, threshold: float = MERGE_THRESHOLD,
          min_size_ratio: float = MIN_SIZE_RATIO):
    """Return (slug, score) for the beat this proposal continues, or (None, score).

    `existing` maps slug -> signature set.
    """
    best, best_score = None, 0.0
    for slug, sig in existing.items():
        if not sig or not proposal_sig:
            continue
        ratio = min(len(sig), len(proposal_sig)) / max(len(sig), len(proposal_sig))
        if ratio < min_size_ratio:
            continue          # too lopsided to trust containment
        score = overlap(proposal_sig, sig)
        if score > best_score:
            best, best_score = slug, score
    return (best, best_score) if best_score >= threshold else (None, best_score)


def signatures_for(ledger, slugs) -> dict:
    """Build signatures for existing beats from their name, state and claims.

    Claims are the richest signal and the most stable: a story's entities recur
    in the reporting even when the framing shifts.
    """
    out = {}
    for slug in slugs:
        texts = [slug.replace("-", " ")]
        state = ledger.get_state(slug) or {}
        for f in state.get("fields", []):
            texts.append(f.get("k", ""))
            texts.append(f.get("v", ""))
        for c in ledger.list_claims(slug)[:25]:
            texts.append(c.get("claim_text", ""))
        out[slug] = signature(*texts)
    return out
