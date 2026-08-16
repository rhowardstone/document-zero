"""The Article is what a reporter produces and a reader reads.

v1's central artifact was a diff of state fields — a database row. These tests
pin the editorial judgements that make an article an article: it has a date on
it, it is long enough to be a story and short enough not to be padding, and
every paragraph rests on evidence the ledger actually holds.
"""
import pytest

from ledger.article import Article, ArticleError, validate


def art(**kw):
    base = dict(
        beat="fed", day="2026-08-16",
        headline="Fed signals a hold as September decision nears",
        standfirst="Two governors break with the chair in remarks a day apart",
        dateline="WASHINGTON", published_at="2026-08-16T14:02:00Z",
        paragraphs=[{"text": "word " * 450, "claims": ["fed-1"]}],
        changed=[{"k": "Dissents", "from": "1", "to": "3", "since": "2026-08-14"}],
        written_by="claude-code/beat:fed", verified_by=["e1", "e2"])
    base.update(kw)
    return base


def test_a_well_formed_article_validates():
    a = validate(art())
    assert isinstance(a, Article) and a.word_count == 450


def test_an_article_under_the_floor_is_refused():
    """Below the floor there was no story — the beat degrades to a line."""
    with pytest.raises(ArticleError, match="300"):
        validate(art(paragraphs=[{"text": "word " * 120, "claims": ["fed-1"]}]))


def test_an_article_over_eight_hundred_words_is_refused():
    """Above 800 the reporter is padding."""
    with pytest.raises(ArticleError, match="800"):
        validate(art(paragraphs=[{"text": "word " * 900, "claims": ["fed-1"]}]))


def test_a_paragraph_citing_no_claims_is_refused():
    """Prose the ledger cannot trace to evidence may not publish. This is the
    whole point of the project, applied one level up from claims."""
    with pytest.raises(ArticleError, match="cites no claims"):
        validate(art(paragraphs=[{"text": "word " * 450, "claims": []}]))


@pytest.mark.parametrize("missing", ["headline", "dateline", "published_at"])
def test_the_mandatory_fields_are_mandatory(missing):
    """v1 shipped with no dates and it was the first thing a reader noticed."""
    with pytest.raises(ArticleError, match=missing):
        validate(art(**{missing: ""}))


def test_a_headline_that_is_a_sentence_fragment_is_refused():
    with pytest.raises(ArticleError, match="headline"):
        validate(art(headline="Fed"))


def test_claims_cited_anywhere_are_collected():
    a = validate(art(paragraphs=[
        {"text": "word " * 220, "claims": ["fed-1", "fed-2"]},
        {"text": "word " * 230, "claims": ["fed-2", "fed-3"]}]))
    assert a.cited == {"fed-1", "fed-2", "fed-3"}


def test_an_article_with_no_paragraphs_is_refused():
    with pytest.raises(ArticleError, match="paragraph"):
        validate(art(paragraphs=[]))


def test_the_article_is_immutable_once_validated():
    """An article is a published record. Editing one in place would make the
    ledger's history a lie, the same reason claims are immutable."""
    a = validate(art())
    with pytest.raises(Exception):
        a.headline = "something else"


def test_a_headline_that_is_really_a_lede_is_refused():
    """Told only "a sentence, not a fragment", the reporter wrote a 20-word
    restatement of its own first paragraph, which rendered as six lines of
    display type on the live site."""
    with pytest.raises(ArticleError, match="lede"):
        validate(art(headline="The State of New Mexico has sued the Justice "
                              "Department in federal court for unredacted "
                              "Epstein records the department has withheld"))


def test_a_headline_of_normal_length_passes():
    validate(art(headline="New Mexico sues Justice Department over withheld records"))
