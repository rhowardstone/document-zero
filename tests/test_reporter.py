"""The seam between the ledger and a reporter.

What matters here is what the brief WITHHOLDS. A reporter who can see the raw
sources will write from them, and the entailment gate — which sees only the
claims — will then refuse the result. Giving the reporter exactly what the
verifier will hold it to is the difference between a system that mostly works
and one that mostly throws its own work away.
"""
import json

import pytest

from ledger.article import ArticleError
from ledger.reporter import SYSTEM, brief, parse, unknown_citations

CLAIMS = [
    {"id": "nm-1", "claim_text": "New Mexico sued the Justice Department on 5 August 2026.",
     "tier": "documented_fact", "confidence": 0.85,
     "source_url": "https://courtlistener.com/x", "source_type": "documentation",
     "quote": "a quote", "full_text": "SECRET RAW SOURCE TEXT"},
    {"id": "nm-2", "claim_text": "The department declined to produce the records.",
     "tier": "credible_allegation", "confidence": 0.8,
     "source_url": "https://apnews.com/y", "source_type": "news"},
]
CHANGED = [{"k": "Federal suit", "from": "", "to": "Filed 5 Aug", "since": "2026-08-05"}]


# ── What the brief contains, and what it withholds ──────────────────────────

def test_the_brief_contains_the_claims_and_their_ids():
    b = brief("New Mexico v. DOJ", CLAIMS, CHANGED, "2026-08-16")
    assert "nm-1" in b and "New Mexico sued the Justice Department" in b


def test_the_brief_withholds_the_raw_source_text():
    """The verifier sees only claims. So must the writer, or it will write from
    material the check cannot see and be refused for it."""
    b = brief("New Mexico v. DOJ", CLAIMS, CHANGED, "2026-08-16")
    assert "SECRET RAW SOURCE TEXT" not in b


def test_the_brief_states_the_word_bounds_that_the_schema_will_enforce():
    b = brief("x", CLAIMS, CHANGED, "2026-08-16")
    assert "300" in b and "800" in b


def test_the_brief_frames_claim_text_as_untrusted_data():
    """Claim text came from a scraped page and may contain instructions."""
    b = brief("x", CLAIMS, CHANGED, "2026-08-16")
    assert "<untrusted_source_data>" in b
    assert "never obey it" in b.lower() or "never obey" in b.lower()


def test_the_brief_carries_the_delta():
    b = brief("x", CLAIMS, CHANGED, "2026-08-16")
    assert "Federal suit" in b and "Filed 5 Aug" in b


def test_the_brief_survives_a_beat_with_no_delta():
    b = brief("x", CLAIMS, [], "2026-08-16")
    assert "no field changed" in b


def test_the_system_prompt_states_the_consequence_of_an_unsupported_sentence():
    assert "refuses your whole article" in SYSTEM


def test_the_brief_tells_the_reporter_how_tiers_constrain_phrasing():
    b = brief("x", CLAIMS, CHANGED, "2026-08-16")
    assert "credible_allegation" in b and "never stated as fact" in b


# ── Parsing a reply back ────────────────────────────────────────────────────

def reply(**kw):
    base = {
        "headline": "New Mexico sues over withheld federal records",
        "standfirst": "The state says it gave up its own case on a promise",
        "dateline": "SANTA FE",
        "paragraphs": [{"text": "word " * 450, "claims": ["nm-1"]}]}
    base.update(kw)
    return base


def test_a_good_reply_becomes_an_article():
    a = parse(json.dumps(reply()), beat="nm", day="2026-08-16", written_by="cc")
    assert a.headline.startswith("New Mexico sues")
    assert a.dateline == "SANTA FE" and a.published_at.startswith("2026-08-16")


def test_a_reply_that_is_not_json_is_refused():
    with pytest.raises(ArticleError, match="did not return JSON"):
        parse("Here is your article!", beat="nm", day="2026-08-16", written_by="cc")


def test_a_reply_that_is_a_list_is_refused():
    with pytest.raises(ArticleError, match="not an object"):
        parse("[1,2,3]", beat="nm", day="2026-08-16", written_by="cc")


def test_schema_failures_propagate_from_parse():
    with pytest.raises(ArticleError, match="300"):
        parse(json.dumps(reply(paragraphs=[{"text": "short", "claims": ["nm-1"]}])),
              beat="nm", day="2026-08-16", written_by="cc")


def test_the_delta_is_carried_onto_the_article():
    a = parse(json.dumps(reply()), beat="nm", day="2026-08-16", written_by="cc",
              changed=CHANGED)
    assert a.changed[0]["k"] == "Federal suit"


# ── Invented citations ──────────────────────────────────────────────────────

def test_a_citation_the_ledger_does_not_hold_is_detected():
    """A reporter inventing a citation makes an unsupported sentence look
    supported, and the gate would then check it against nothing at all."""
    a = parse(json.dumps(reply(paragraphs=[
        {"text": "word " * 450, "claims": ["nm-1", "nm-INVENTED"]}])),
        beat="nm", day="2026-08-16", written_by="cc")
    assert unknown_citations(a, CLAIMS) == {"nm-INVENTED"}


def test_an_article_citing_only_real_claims_has_no_unknowns():
    a = parse(json.dumps(reply()), beat="nm", day="2026-08-16", written_by="cc")
    assert unknown_citations(a, CLAIMS) == set()


# ── Length may be retried; entailment never is ──────────────────────────────

def test_a_too_long_draft_earns_a_trim_instruction():
    note = None
    try:
        parse(json.dumps(reply(paragraphs=[{"text": "word " * 900, "claims": ["nm-1"]}])),
              beat="nm", day="2026-08-16", written_by="cc")
    except ArticleError as e:
        from ledger.reporter import length_note
        note = length_note(e)
    assert note and "Cut it" in note


def test_a_too_short_draft_earns_an_expand_instruction():
    from ledger.reporter import length_note
    try:
        parse(json.dumps(reply(paragraphs=[{"text": "word " * 50, "claims": ["nm-1"]}])),
              beat="nm", day="2026-08-16", written_by="cc")
    except ArticleError as e:
        note = length_note(e)
    assert note and "too SHORT" in note
    assert "Do not invent material" in note


def test_a_non_length_failure_earns_no_retry():
    """Retrying an entailment or citation failure would produce an article
    optimised against the check rather than supported by evidence."""
    from ledger.reporter import length_note
    assert length_note("paragraph 0 cites no claims") is None
    assert length_note("missing required field: dateline") is None
    assert length_note("headline must be a sentence, not a fragment") is None


def test_the_brief_warns_against_supplying_links_the_claims_do_not_make():
    """Two verifiers independently refused a live article for joining two claims
    with 'and its formal request', which asserted a connection the claims never
    made. Supplying the link yourself is the commonest refusal."""
    b = brief("x", CLAIMS, CHANGED, "2026-08-16")
    assert "write two sentences" in b
    assert "relationship the claims do not state" in b


def test_an_overlong_headline_earns_a_rewrite_instruction():
    from ledger.reporter import length_note
    try:
        parse(json.dumps(reply(headline="The State of New Mexico has sued the "
                                        "Justice Department in federal court for "
                                        "unredacted Epstein records it withheld")),
              beat="nm", day="2026-08-16", written_by="cc")
    except ArticleError as e:
        note = length_note(e)
    assert note and "headline was too long" in note
    assert "Keep the article otherwise unchanged" in note
