import pytest
from ledger.schema import validate_claim, validate_source, validate_beat_state, SchemaError

def good_claim(**over):
    c = {"id":"hormuz-2026-08-14-003","beat":"hormuz",
         "claim_text":"Transit slowed to a near standstill on 14 August.",
         "quote":"appeared to grind to a near standstill on Friday",
         "source_type":"news","source_url":"https://example.org/a",
         "source_sha":"sha256:"+"b"*64,"confidence":0.6,
         "confidence_justification":"Single secondary outlet. News ceiling.",
         "tier":"documented_fact","extracted_by":"beat-agent-hormuz",
         "extracted_at":"2026-08-14T04:41:00Z"}
    c.update(over); return c

def test_valid_claim_passes(): validate_claim(good_claim())

def test_claim_without_any_source_pointer_is_rejected():
    c = good_claim(); c.pop("source_url")
    with pytest.raises(SchemaError, match="source"): validate_claim(c)

def test_claim_without_quote_is_rejected():
    with pytest.raises(SchemaError, match="quote"): validate_claim(good_claim(quote=""))

def test_claim_without_confidence_justification_is_rejected():
    with pytest.raises(SchemaError, match="justification"):
        validate_claim(good_claim(confidence_justification=""))

def test_claim_over_ceiling_is_rejected_by_schema_layer():
    with pytest.raises(SchemaError, match="ceiling"): validate_claim(good_claim(confidence=0.9))

def test_article_claim_requires_a_doi():
    with pytest.raises(SchemaError, match="doi"):
        validate_claim(good_claim(source_type="article", confidence=0.9))

def test_article_claim_with_doi_passes():
    validate_claim(good_claim(source_type="article", confidence=0.9, source_doi="10.1000/xyz"))

def test_unknown_tier_is_rejected():
    with pytest.raises(SchemaError, match="tier"): validate_claim(good_claim(tier="vibes"))

def test_valid_source_passes():
    validate_source({"sha256":"c"*64,"url":"https://example.org/a","title":"T",
        "source_name":"Example","source_type":"news","published_at":"2026-08-14T03:00:00Z",
        "first_seen":"2026-08-14T04:00:00Z","candidate_beats":[{"beat":"hormuz","score":0.81}]})

def test_source_without_first_seen_is_rejected():
    with pytest.raises(SchemaError, match="first_seen"):
        validate_source({"sha256":"c"*64,"url":"https://x","title":"T","source_name":"E",
            "source_type":"news","published_at":"2026-08-14T03:00:00Z","candidate_beats":[]})

def test_beat_state_requires_two_changeable_fields():
    with pytest.raises(SchemaError, match="two"):
        validate_beat_state({"beat":"hormuz","as_of":"2026-08-14",
            "fields":[{"k":"Blockade","v":"In force","since":"Aug"}]})

def test_beat_state_with_two_grounded_fields_passes():
    validate_beat_state({"beat":"hormuz","as_of":"2026-08-14","fields":[
        {"k":"Blockade","v":"In force","since":"Aug","claims":["h-1"]},
        {"k":"Transit","v":"Near standstill","since":"14 Aug","claims":["h-2"]}]})


def test_a_state_field_must_cite_the_claims_that_support_it():
    """Regression: the diff was deterministic but ran over ungrounded model
    output, so an invented field reported faithfully as a real change."""
    with pytest.raises(SchemaError, match="cites no claims"):
        validate_beat_state({"beat": "b", "as_of": "2026-08-14", "fields": [
            {"k": "Blockade", "v": "In force"},
            {"k": "Transit", "v": "Slowed"}]})

def test_a_grounded_state_passes():
    validate_beat_state({"beat": "b", "as_of": "2026-08-14", "fields": [
        {"k": "Blockade", "v": "In force", "claims": ["b-1"]},
        {"k": "Transit", "v": "Slowed", "claims": ["b-2", "b-3"]}]})

def test_an_empty_citation_list_is_not_a_citation():
    with pytest.raises(SchemaError, match="cites no claims"):
        validate_beat_state({"beat": "b", "as_of": "2026-08-14", "fields": [
            {"k": "A", "v": "1", "claims": []},
            {"k": "B", "v": "2", "claims": ["x"]}]})


# ── State must describe the world, not the ledger ───────────────────────────

def _st(k, v, claims=("c1",)):
    return {"beat": "b", "as_of": "2026-08-14", "fields": [
        {"k": k, "v": v, "claims": list(claims)},
        {"k": "Docket status", "v": "Response due", "claims": ["c2"]}]}


@pytest.mark.parametrize("key", [
    "Most recent claim", "Latest development", "Claims on record",
    "Number of claims", "Claim count", "Current headline", "Articles seen",
])
def test_a_field_about_the_ledger_itself_is_rejected(key):
    """These change every day by construction, so the beat always 'moves'."""
    with pytest.raises(SchemaError, match="describes the ledger"):
        validate_beat_state(_st(key, "anything at all"))


def test_a_field_that_restates_its_own_claim_is_rejected():
    claim = "The Justice Department missed the 5 August deadline for the ranch files."
    with pytest.raises(SchemaError, match="restates the claim"):
        validate_beat_state(_st("Status", claim[:52]), claim_texts=[claim])


def test_a_genuine_state_field_supported_by_a_claim_is_fine():
    claim = "The Justice Department missed the 5 August deadline for the ranch files."
    validate_beat_state(_st("Federal suit", "Filed 5 Aug 2026, D.D.C."), claim_texts=[claim])


def test_a_short_value_is_not_treated_as_a_restatement():
    """Real state values are short. The prefix test only fires on long ones."""
    validate_beat_state(_st("Venue", "D.D.C."), claim_texts=["D.D.C. is where it was filed"])
