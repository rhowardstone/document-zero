"""Articles live in the ledger, under the beat that wrote them.

An article is a published record. It is written by exactly one beat agent, into
that agent's own path prefix, and it is immutable once written — the same rule
claims follow, for the same reason: a published record edited in place makes
the ledger's history a lie.
"""
import pytest

from ledger.article import validate
from ledger.paths import article_path, owns_path
from ledger.store import Ledger


def art(beat="fed", day="2026-08-16", headline="Fed holds rates as autumn nears"):
    return validate({
        "beat": beat, "day": day, "headline": headline,
        "standfirst": "Two governors dissent", "dateline": "WASHINGTON",
        "published_at": f"{day}T12:00:00Z", "written_by": "t",
        "paragraphs": [{"text": "word " * 450, "claims": [f"{beat}-1"]}]})


def test_the_path_is_under_the_beat_that_wrote_it():
    assert article_path("fed", "2026-08-16") == "beats/fed/articles/2026-08-16.json"


def test_only_that_beats_agent_may_write_it():
    assert owns_path("beat:fed", article_path("fed", "2026-08-16")) is True
    assert owns_path("beat:nm", article_path("fed", "2026-08-16")) is False
    assert owns_path("editor", article_path("fed", "2026-08-16")) is False


def test_an_article_round_trips(tmp_path):
    led = Ledger(tmp_path / "d", writer="beat:fed")
    led.put_article(art())
    got = Ledger(tmp_path / "d").get_article("fed", "2026-08-16")
    assert got["headline"] == "Fed holds rates as autumn nears"
    assert got["word_count"] == 450


def test_rewriting_a_published_article_with_different_content_is_refused(tmp_path):
    """A correction is a new day's article that supersedes, never an edit."""
    led = Ledger(tmp_path / "d", writer="beat:fed")
    led.put_article(art())
    with pytest.raises(FileExistsError, match="immutable"):
        led.put_article(art(headline="Actually something else happened here"))


def test_rewriting_an_identical_article_is_a_no_op(tmp_path):
    """Reruns must be safe: the same run twice is not a conflict."""
    led = Ledger(tmp_path / "d", writer="beat:fed")
    led.put_article(art())
    led.put_article(art())


def test_an_agent_cannot_write_another_beats_article(tmp_path):
    from ledger.paths import PartitionError
    led = Ledger(tmp_path / "d", writer="beat:nm")
    with pytest.raises(PartitionError):
        led.put_article(art(beat="fed"))


def test_articles_are_listed_newest_first(tmp_path):
    led = Ledger(tmp_path / "d", writer="beat:fed")
    for day in ("2026-08-14", "2026-08-16", "2026-08-15"):
        led.put_article(art(day=day))
    days = [a["day"] for a in Ledger(tmp_path / "d").list_articles("fed")]
    assert days == ["2026-08-16", "2026-08-15", "2026-08-14"]


def test_a_missing_article_returns_none_rather_than_raising(tmp_path):
    assert Ledger(tmp_path / "d").get_article("fed", "2026-08-16") is None


def test_only_validated_articles_can_be_stored(tmp_path):
    """The schema is the gate; the store must not be a way around it."""
    from ledger.article import ArticleError
    led = Ledger(tmp_path / "d", writer="beat:fed")
    with pytest.raises(ArticleError):
        led.put_article({"beat": "fed", "day": "2026-08-16", "headline": "no"})
