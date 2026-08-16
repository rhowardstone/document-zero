"""Which story leads the page.

The three articles that passed the gate on 2026-08-17 were ordered by beat slug,
so `indiana-record-flooding-august-2026` led the paper over a shooting war and a
carrier deployment purely because "i" sorts before "u". That is not a decision,
it is an accident wearing a decision's clothes — and on a front page the lead
slot IS the editorial judgement, the one thing a reader reads as us saying "this
mattered most today".

The rule here is deliberately measurable rather than clever: lead with the story
that the most independent newsrooms put on the record. Corroboration is the only
signal available for free that is about the WORLD rather than about our own
processing, and it is the one a reader could check.
"""
from ledger.lead import weight


def art(beat, publishers=1, claims=1, words=500):
    return {"beat": beat, "publishers": publishers, "claims": claims,
            "word_count": words}


def test_more_independent_publishers_leads():
    a, b = art("flood", publishers=2), art("war", publishers=7)
    assert weight(b) > weight(a)


def test_claim_count_breaks_a_publisher_tie():
    """Same corroboration, more established on the record."""
    a, b = art("a", publishers=3, claims=4), art("b", publishers=3, claims=11)
    assert weight(b) > weight(a)


def test_length_never_outranks_corroboration():
    """Otherwise the lead goes to whichever reporter wrote the most, which is a
    fact about the writer and not about the news."""
    thorough_but_lonely = art("a", publishers=1, claims=2, words=800)
    widely_reported = art("b", publishers=6, claims=2, words=310)
    assert weight(widely_reported) > weight(thorough_but_lonely)


def test_the_order_is_stable_for_identical_stories():
    """A page that reshuffles between runs makes every reader wonder what
    changed. Ties fall back to the beat id, which does not vary."""
    same = [art("zulu", publishers=3), art("alpha", publishers=3)]
    assert sorted(same, key=weight, reverse=True)[0]["beat"] == "alpha"


def test_a_story_with_no_measured_corroboration_still_places():
    """A missing count is a gap in OUR records. It must not crash the page and
    must not silently promote the story either."""
    assert weight(art("a", publishers=0, claims=0)) <= weight(art("b", publishers=1))
    assert isinstance(weight({"beat": "x"}), tuple)


def test_weight_reads_missing_fields_as_zero_not_as_an_error():
    assert weight({}) == weight({"beat": "", "publishers": 0, "claims": 0})
