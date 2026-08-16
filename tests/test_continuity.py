"""Beat identity: is this the beat we already have, under a different name?

Every pair below is taken from a real run in which the same story opened twice
because the desk agent worded its name differently the second time. Six beats,
three stories — and left alone it compounds daily until nothing has any history
and the persistent-state premise is dead.
"""
import pytest

from ledger.continuity import (GENERIC, MERGE_THRESHOLD, match, overlap,
                               signature)


# ── Signatures ──────────────────────────────────────────────────────────────

def test_generic_news_words_carry_no_identity():
    sig = signature("Latest news update: what to know about the federal plan")
    assert not (sig & GENERIC)


def test_distinctive_entities_survive():
    sig = signature("US-Iran war and Hormuz blockade")
    assert "hormuz" in sig and "iran" in sig


def test_short_words_are_dropped():
    assert "the" not in signature("the war") and "war" in signature("the war")


def test_signature_is_case_and_punctuation_insensitive():
    assert signature("Democrats' 2028 Calendar") == signature("democrats 2028 calendar")


# ── The real duplicate pairs ────────────────────────────────────────────────

REAL_PAIRS = [
    ("Democrats' 2028 calendar and party direction",
     "Democrats' 2028 primary calendar"),
    ("Indiana record flooding",
     "Indiana record flooding, August 2026"),
    ("US-Iran war and Hormuz blockade",
     "US-Iran war and stalled ceasefire talks"),
    ("Korean Peninsula tensions and US-South Korea drills",
     "US-South Korea alliance and inter-Korean tensions"),
]


@pytest.mark.parametrize("a,b", REAL_PAIRS)
def test_the_same_story_named_twice_is_recognised_as_one_beat(a, b):
    slug, score = match(signature(b), {"existing": signature(a)})
    assert slug == "existing", f"{a!r} vs {b!r} scored only {score:.2f}"


# ── It must NOT merge unrelated stories ─────────────────────────────────────

DIFFERENT = [
    ("US-Iran war and Hormuz blockade", "Indiana record flooding"),
    ("Democrats' 2028 primary calendar", "Tropical Storm Lala in Hawaii"),
    ("USS Abraham Lincoln deployment conditions",
     "Democrats' 2028 primary calendar"),
    ("Indonesia earthquake response", "Fed September rate decision"),
]


@pytest.mark.parametrize("a,b", DIFFERENT)
def test_unrelated_stories_are_not_merged(a, b):
    """A wrong merge welds two stories into one beat whose state contradicts
    itself and cannot be separated afterwards. A missed merge leaves a duplicate
    that can be merged later."""
    slug, score = match(signature(b), {"existing": signature(a)})
    assert slug is None, f"{a!r} wrongly merged with {b!r} at {score:.2f}"


# ── Containment, not Jaccard ────────────────────────────────────────────────

def test_a_long_running_beat_still_matches_a_small_new_cluster():
    """A beat that has run a week carries far more vocabulary than one day's
    cluster. A symmetric measure would score a correct match low purely because
    the older side knows more."""
    old = signature("Hormuz blockade Iran tankers ceasefire negotiations carrier "
                    "Lincoln sanctions oil shipping insurance Tehran Washington")
    new = signature("Hormuz blockade Iran tankers")
    assert overlap(new, old) >= MERGE_THRESHOLD


def test_overlap_of_empty_sets_is_zero_not_an_error():
    assert overlap(set(), {"a"}) == 0.0 and overlap(set(), set()) == 0.0


def test_the_best_match_wins_when_several_beats_are_close():
    existing = {"iran": signature("US-Iran war and Hormuz blockade"),
                "korea": signature("Korean Peninsula tensions and drills"),
                "flood": signature("Indiana record flooding")}
    slug, _ = match(signature("Hormuz blockade and Iran ceasefire"), existing)
    assert slug == "iran"


def test_no_existing_beats_means_no_match():
    assert match(signature("Anything at all here"), {}) == (None, 0.0)


def test_the_threshold_sits_in_an_empty_gap():
    """Measured on the real pairs using NAMES ALONE — the weakest signal this
    will ever see, since production signatures also carry state fields and
    twenty-five claims. Same stories score 0.50-1.00, unrelated stories score
    0.00 without exception. There is no tuning fudge: the separation is total
    and any threshold in the gap would do."""
    same = [overlap(signature(a), signature(b)) for a, b in REAL_PAIRS]
    diff = [overlap(signature(a), signature(b)) for a, b in DIFFERENT]
    assert min(same) > max(diff), f"same {min(same):.2f} vs different {max(diff):.2f}"
    assert max(diff) < MERGE_THRESHOLD < min(same)


# ── The lopsided-containment trap ───────────────────────────────────────────

def test_a_tiny_signature_is_not_merged_into_a_huge_one():
    """Measured on real beats: a 42-token beat scored 0.62 against a 339-token
    beat purely on shared PROCESS vocabulary — complaint, investigation,
    department — and would have been welded onto a different story. Genuine
    duplicates were comparably sized and shared ENTITIES."""
    small = signature("Transparency Act compliance redaction records department")
    big = signature(" ".join([
        "New Mexico sued the Justice Department over withheld records",
        "complaint investigation criminal filing court judge docket ruling",
        "Zorro Ranch auction LLC Huffines Santa Fe excavation substrate permits",
        "Touhy request protective orders exhaustion deadline response",
        "stand down prosecutors evidence survivors trafficking grooming",
        "carrier deployment morale sailors conditions inspection report"]))
    slug, score = match(small, {"big": big})
    assert slug is None, f"lopsided pair merged at {score:.2f}"


def test_comparably_sized_beats_still_merge():
    a = signature("Hormuz blockade Iran tankers ceasefire carrier Lincoln ADNOC")
    b = signature("Hormuz blockade Iran tankers ceasefire carrier Washington oil")
    assert match(b, {"a": a})[0] == "a"


def test_an_empty_signature_never_matches():
    assert match(set(), {"a": signature("Hormuz blockade Iran")})[0] is None
    assert match(signature("Hormuz blockade Iran"), {"a": set()})[0] is None
