import pytest
from ledger.refusal import (asserts_wrongdoing, identifies_person, refusal_check,
                            Decision, Subject)

PUB = Subject("Todd Blanche", "public_official")
PARTY = Subject("Luigi Mangione", "named_party")
PRIV = Subject("Jane Doe", "private")
UNK = Subject("Chris Smith", "unknown")

def claim(text, **over):
    c = {"claim_text": text, "source_type": "news", "source_url": "https://x",
         "quote": text, "tier": "documented_fact"}
    c.update(over); return c

# --- wrongdoing lexicon -------------------------------------------------
def test_detects_wrongdoing_language():
    assert asserts_wrongdoing("He defrauded investors of $4m")
    assert asserts_wrongdoing("was accused of assault")
    assert asserts_wrongdoing("illegally withheld the documents")

def test_neutral_language_is_not_wrongdoing():
    assert not asserts_wrongdoing("The board voted 20-3 to rename the building")
    assert not asserts_wrongdoing("Transit slowed to a near standstill")

# --- the gates ----------------------------------------------------------
def test_wrongdoing_about_a_public_official_is_allowed():
    d = refusal_check(claim("The attorney general withheld documents in violation of the order"),
                      [PUB])
    assert d.allowed

def test_wrongdoing_about_a_named_party_to_a_proceeding_is_allowed():
    d = refusal_check(claim("He stalked and killed the executive"), [PARTY])
    assert d.allowed

def test_wrongdoing_about_a_private_individual_is_refused():
    d = refusal_check(claim("Jane Doe embezzled from the fund"), [PRIV])
    assert not d.allowed and d.gate == "wrongdoing_by_private_individual"

def test_unknown_status_defaults_to_refusal():
    d = refusal_check(claim("Chris Smith assaulted a colleague"), [UNK])
    assert not d.allowed, "uncertainty must default to refusal, not publication"

def test_neutral_claim_about_a_private_individual_is_allowed():
    assert refusal_check(claim("Jane Doe attended the hearing"), [PRIV]).allowed

def test_identifying_a_private_individual_is_refused():
    d = refusal_check(claim("Jane Doe lives at 14 Elm Street, Dayton"), [PRIV])
    assert not d.allowed and d.gate == "identification_of_private_individual"

def test_identifying_a_public_official_by_office_is_allowed():
    assert refusal_check(claim("The attorney general's office is at Main Justice"), [PUB]).allowed

def test_identifies_person_detects_address_and_plate():
    assert identifies_person("lives at 14 Elm Street")
    assert identifies_person("plate number 8XKJ221")
    assert not identifies_person("spoke at the hearing")

def test_criminal_conduct_without_a_filing_is_refused_even_for_officials():
    d = refusal_check(claim("The senator committed wire fraud", source_type="news"), [PUB])
    assert not d.allowed and d.gate == "uncorroborated_criminal_conduct"

def test_criminal_conduct_with_a_charging_document_is_allowed():
    d = refusal_check(claim("The senator was charged with wire fraud",
                            source_type="documentation", docket="1:26-cr-00123"), [PUB])
    assert d.allowed

def test_no_subjects_means_no_person_gate_applies():
    assert refusal_check(claim("The blockade was reimposed in early August"), []).allowed

def test_decision_carries_a_human_readable_reason():
    d = refusal_check(claim("Jane Doe embezzled funds"), [PRIV])
    assert "Jane Doe" in d.reason
