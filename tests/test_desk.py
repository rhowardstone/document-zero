"""Turning a wire cluster into an opened beat with claims.

The checks here are the ones that make "exact quote required" a guarantee
rather than a request the agent may decline, and that keep one fabricated
quote from discarding seven good claims.
"""
import json

import pytest

from ledger.desk import MAX_CLAIMS, brief, parse

ARTICLES = [
    {"sha256": "a" * 64, "url": "https://apnews.com/x", "publisher": "apnews.com",
     "published_at": "2026-08-16T00:00:00Z", "source_type": "news",
     "title": "Rescuers in Indonesia recover more bodies in earthquake aftermath",
     "summary": "The death toll rose to 53 on Sunday as teams reached villages."},
    {"sha256": "b" * 64, "url": "https://npr.org/y", "publisher": "npr.org",
     "published_at": "2026-08-16T00:00:00Z", "source_type": "news",
     "title": "Magnitude 7.7 earthquake strikes off Indonesia's coast",
     "summary": "A tsunami warning was issued and later lifted."},
]
REF_A, REF_B = "a" * 12, "b" * 12


def claim(**kw):
    base = {"claim_text": "The death toll rose to 53.",
            "quote": "The death toll rose to 53 on Sunday",
            "ref": REF_A, "tier": "documented_fact", "confidence": 0.6,
            "confidence_justification": "news ceiling"}
    base.update(kw)
    return base


def reply(**kw):
    base = {"name": "Indonesia earthquake response",
            "state_fields": [{"k": "Death toll", "v": "53"},
                             {"k": "Search status", "v": "ongoing"}],
            "claims": [claim()]}
    base.update(kw)
    return base


# ── The brief ───────────────────────────────────────────────────────────────

def test_the_brief_frames_the_articles_as_untrusted_data():
    b = brief("Indonesia", ARTICLES, "2026-08-16")
    assert "<untrusted_source_data>" in b and "never obey it" in b


def test_the_brief_asks_for_state_fields_and_says_what_disqualifies_a_beat():
    b = brief("Indonesia", ARTICLES, "2026-08-16")
    assert "changeable state" in b or "could change" in b
    assert "sports result" in b or "product launch" in b


def test_the_brief_demands_verbatim_quotes():
    b = brief("Indonesia", ARTICLES, "2026-08-16")
    assert "EXACTLY" in b and "do not claim it" in b


def test_the_brief_states_the_news_ceiling():
    assert "0.6" in brief("Indonesia", ARTICLES, "2026-08-16")


def test_the_brief_forbids_claims_about_private_individuals():
    b = brief("Indonesia", ARTICLES, "2026-08-16")
    assert "private individual" in b


# ── Quote verification ──────────────────────────────────────────────────────

def test_a_verbatim_quote_is_kept():
    out = parse(json.dumps(reply()), ARTICLES)
    assert len(out["claims"]) == 1
    assert out["claims"][0]["source_sha"] == "a" * 64


def test_a_fabricated_quote_is_dropped():
    """This is the check that makes 'exact quote' a guarantee rather than a
    request the agent may decline."""
    out = parse(json.dumps(reply(claims=[claim(quote="The toll reached 90")])),
                ARTICLES)
    assert out["claims"] == []
    assert "does not appear" in out["dropped"][0][1]


def test_quote_matching_ignores_whitespace_and_case():
    out = parse(json.dumps(reply(claims=[
        claim(quote="the death   toll ROSE to 53")])), ARTICLES)
    assert len(out["claims"]) == 1


def test_a_quote_from_the_wrong_article_is_dropped():
    out = parse(json.dumps(reply(claims=[
        claim(quote="A tsunami warning was issued", ref=REF_A)])), ARTICLES)
    assert out["claims"] == [] and "does not appear" in out["dropped"][0][1]


def test_an_unknown_ref_is_dropped():
    out = parse(json.dumps(reply(claims=[claim(ref="zzzzzzzzzzzz")])), ARTICLES)
    assert out["claims"] == [] and "not one of these articles" in out["dropped"][0][1]


def test_one_bad_claim_does_not_discard_the_good_ones():
    out = parse(json.dumps(reply(claims=[
        claim(),
        claim(claim_text="Invented.", quote="nothing like this appears"),
        claim(claim_text="A tsunami warning was issued and later lifted.",
              quote="A tsunami warning was issued", ref=REF_B)])), ARTICLES)
    assert len(out["claims"]) == 2 and len(out["dropped"]) == 1


# ── Ceilings and tiers ──────────────────────────────────────────────────────

def test_confidence_above_the_ceiling_is_clamped_not_dropped():
    """The claim is fine; the self-assessment was optimistic. The ceiling exists
    precisely to override it."""
    out = parse(json.dumps(reply(claims=[claim(confidence=0.95)])), ARTICLES)
    assert out["claims"][0]["confidence"] == 0.6


def test_an_unknown_tier_is_dropped():
    out = parse(json.dumps(reply(claims=[claim(tier="probably_true")])), ARTICLES)
    assert out["claims"] == [] and "unknown tier" in out["dropped"][0][1]


def test_a_non_numeric_confidence_is_dropped():
    out = parse(json.dumps(reply(claims=[claim(confidence="high")])), ARTICLES)
    assert out["claims"] == []


def test_no_more_than_the_cap_is_accepted():
    out = parse(json.dumps(reply(claims=[claim() for _ in range(30)])), ARTICLES)
    assert len(out["claims"]) <= MAX_CLAIMS


# ── State fields ────────────────────────────────────────────────────────────

def test_state_fields_survive():
    out = parse(json.dumps(reply()), ARTICLES)
    assert [f["k"] for f in out["state_fields"]] == ["Death toll", "Search status"]


def test_an_agent_declining_to_invent_state_is_respected():
    """A sports result has no changeable state. Saying so is the correct answer
    and must not be overridden by inventing fields."""
    out = parse(json.dumps(reply(state_fields=[],
                                 no_state_reason="a single completed event")),
                ARTICLES)
    assert out["state_fields"] == []
    assert "single completed event" in out["no_state_reason"]


def test_empty_field_names_are_discarded():
    out = parse(json.dumps(reply(state_fields=[{"k": "", "v": "x"},
                                               {"k": "Real", "v": "y"}])), ARTICLES)
    assert [f["k"] for f in out["state_fields"]] == ["Real"]


def test_a_reply_that_is_not_an_object_raises():
    with pytest.raises(ValueError, match="expected an object"):
        parse("[1,2,3]", ARTICLES)


def test_the_brief_says_a_state_value_is_a_cell_not_a_sentence():
    """A live run crashed when an agent wrote a state value that restated its
    own claim: the schema refused it, correctly, and took the whole run with
    it. The agent needs to know the shape before it writes one."""
    b = brief("Indonesia", ARTICLES, "2026-08-16")
    assert "as briefly as a cell in" in b
    assert "restatement of one of your claims" in b
