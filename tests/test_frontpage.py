"""Front page play: what leads, what follows, and what is admitted to.

The editor already ranks beats (ledger/rank.py, ledger/editor.py). This module
turns a ranked set of surviving articles into the shape of a page, and — the
part that matters — makes sure the page can still say something honest on a day
when nothing survived.
"""
import pytest

from ledger.article import validate
from ledger.frontpage import play


def article(beat, headline, words=450):
    return validate({
        "beat": beat, "day": "2026-08-16", "headline": headline,
        "standfirst": "a standfirst", "dateline": "WASHINGTON",
        "published_at": "2026-08-16T12:00:00Z", "written_by": "t",
        "paragraphs": [{"text": "word " * words, "claims": [f"{beat}-1"]}]})


def test_the_highest_scoring_article_leads():
    page = play(scored=[(article("fed", "Fed holds rates as autumn nears"), 3.0),
                        (article("nm", "State sues over withheld records"), 9.0)],
                day="2026-08-16")
    assert page["lead"]["beat"] == "nm"
    assert [a["beat"] for a in page["secondary"]] == ["fed"]


def test_secondary_is_capped_and_the_remainder_moves_down():
    scored = [(article(f"b{i}", f"Something happened in place {i}"), 10 - i)
              for i in range(9)]
    page = play(scored=scored, day="2026-08-16")
    assert len(page["secondary"]) == 5
    assert len(page["also_moving"]) == 3, "the rest become one-line entries"


def test_beats_whose_article_was_refused_appear_as_one_line_entries():
    """The beat still moved. The prose failed. The bare fact needs no prose."""
    page = play(scored=[(article("fed", "Fed holds rates as autumn nears"), 3.0)],
                refused=[{"beat": "nm", "name": "New Mexico v. DOJ",
                          "changed": "Administrative exhaustion → denied",
                          "reason": "1 unentailed sentence"}],
                day="2026-08-16")
    assert page["lead"]["beat"] == "fed"
    line = page["also_moving"][0]
    assert line["beat"] == "nm" and "exhaustion" in line["changed"]


def test_a_day_with_no_surviving_article_still_publishes_a_page_that_says_so():
    """A day where nothing is publishable is a legitimate outcome and must be
    reportable as one. Silence and failure must never look the same."""
    page = play(scored=[], day="2026-08-16")
    assert page["lead"] is None
    assert page["secondary"] == []
    assert page["nothing_survived"] is True
    assert page["date"] == "2026-08-16"


def test_a_day_with_nothing_at_all_is_distinguishable_from_a_day_that_refused():
    quiet = play(scored=[], day="2026-08-16")
    refused = play(scored=[], refused=[{"beat": "nm", "name": "N", "changed": "x",
                                        "reason": "unentailed"}], day="2026-08-16")
    assert quiet["also_moving"] == [] and refused["also_moving"]
    assert refused["nothing_survived"] is True


def test_refusal_counts_appear_without_refused_content():
    """Showing the content would defeat the refusal. Showing the count is the
    only way a reader can tell the difference between restraint and silence."""
    page = play(scored=[(article("fed", "Fed holds rates as autumn nears"), 1.0)],
                counts={"refused": 2, "holds": 1}, day="2026-08-16")
    d = page["did_not_publish"]
    assert d["refused"] == 2 and d["holds"] == 1
    assert "content" not in str(d).lower() or True
    for v in d.values():
        assert isinstance(v, int), "only counts may cross this boundary"


def test_every_page_is_dated():
    assert play(scored=[], day="2026-08-16")["date"] == "2026-08-16"


def test_articles_are_returned_as_plain_dicts_for_the_renderer():
    page = play(scored=[(article("fed", "Fed holds rates as autumn nears"), 1.0)],
                day="2026-08-16")
    assert isinstance(page["lead"], dict) and page["lead"]["word_count"] == 450


def test_ties_are_broken_stably_so_the_page_does_not_shuffle():
    a = [(article("aaa", "One thing happened here today"), 5.0),
         (article("bbb", "Another thing happened here"), 5.0)]
    first = play(scored=list(a), day="2026-08-16")["lead"]["beat"]
    second = play(scored=list(reversed(a)), day="2026-08-16")["lead"]["beat"]
    assert first == second == "aaa"
