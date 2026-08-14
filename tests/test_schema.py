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

def test_beat_state_with_two_fields_passes():
    validate_beat_state({"beat":"hormuz","as_of":"2026-08-14","fields":[
        {"k":"Blockade","v":"In force","since":"Aug"},
        {"k":"Transit","v":"Near standstill","since":"14 Aug"}]})
