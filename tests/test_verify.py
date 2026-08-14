import pytest
from ledger.verify import (Pass, Verdict, run_cascade, CascadeResult, band_down)

CLAIM = {"id": "c1", "beat": "hormuz", "claim_text": "Transit slowed to a standstill.",
         "quote": "grind to a near standstill", "source_type": "news",
         "source_url": "https://x", "confidence": 0.6,
         "confidence_justification": "single outlet", "tier": "documented_fact",
         "extracted_by": "a", "extracted_at": "2026-08-14T05:00:00Z"}
SOURCES = [{"sha256": "a" * 64, "title": "T", "snippet": "grind to a near standstill"}]

def agree(name, family):      return Pass(name, family, lambda c, s: Verdict(False, "holds"))
def refute(name, family):     return Pass(name, family, lambda c, s: Verdict(True, "unsupported"))

# --- consensus ----------------------------------------------------------
def test_claim_survives_when_two_of_three_passes_do_not_refute():
    r = run_cascade(CLAIM, SOURCES, [agree("refute", "B"), agree("lens", "C"), refute("x", "D")],
                    consensus_required=2)
    assert r.survived and r.agreeing == 2

def test_claim_dies_when_two_of_three_refute():
    r = run_cascade(CLAIM, SOURCES, [refute("refute", "B"), refute("lens", "C"), agree("x", "D")],
                    consensus_required=2)
    assert not r.survived

def test_single_refutation_below_threshold_still_kills_when_threshold_is_all():
    r = run_cascade(CLAIM, SOURCES, [agree("a", "B"), refute("b", "C")], consensus_required=2)
    assert not r.survived

# --- model family independence -----------------------------------------
def test_distinct_families_do_not_trigger_the_cap():
    r = run_cascade(CLAIM, SOURCES, [agree("a", "B"), agree("b", "C")], consensus_required=2)
    assert not r.single_family
    assert r.claim["confidence"] == 0.6

def test_same_family_passes_cap_confidence_one_band_lower():
    r = run_cascade(CLAIM, SOURCES, [agree("a", "B"), agree("b", "B")], consensus_required=2)
    assert r.single_family
    assert r.claim["confidence"] == 0.5
    assert r.claim["single_family_verified"] is True

def test_extractor_family_never_counts_as_an_independent_verifier():
    r = run_cascade(dict(CLAIM, extracted_by_family="B"), SOURCES,
                    [agree("a", "B"), agree("b", "C")], consensus_required=2)
    assert r.single_family is False
    assert "B" in r.families_used

def test_band_down_walks_the_ladder():
    assert band_down(0.6) == 0.5
    assert band_down(0.95) == 0.9
    assert band_down(0.5) == 0.5   # floor

# --- rounds -------------------------------------------------------------
def test_a_failed_claim_is_re_extracted_with_the_refutation():
    seen = []
    def reextract(claim, refutations):
        seen.append(refutations)
        return dict(claim, claim_text="narrowed claim")
    calls = {"n": 0}
    def flaky(c, s):
        calls["n"] += 1
        return Verdict(True, "too broad") if c["claim_text"] != "narrowed claim" else Verdict(False, "ok")
    r = run_cascade(CLAIM, SOURCES, [Pass("refute", "B", flaky), Pass("lens", "C", flaky)],
                    consensus_required=2, rounds_max=3, reextract=reextract)
    assert r.survived and r.rounds == 2
    assert seen and "too broad" in seen[0][0]

def test_three_failed_rounds_discards_the_claim():
    r = run_cascade(CLAIM, SOURCES, [refute("a", "B"), refute("b", "C")],
                    consensus_required=2, rounds_max=3,
                    reextract=lambda c, ref: dict(c))
    assert not r.survived and r.rounds == 3 and r.discarded

def test_without_a_reextractor_a_failure_is_final_after_one_round():
    r = run_cascade(CLAIM, SOURCES, [refute("a", "B"), refute("b", "C")], consensus_required=2)
    assert not r.survived and r.rounds == 1

# --- verifier isolation -------------------------------------------------
def test_verifiers_never_receive_the_extractors_reasoning():
    captured = {}
    def spy(c, s):
        captured.update(c)
        return Verdict(False, "ok")
    run_cascade(dict(CLAIM, _reasoning="because I felt like it"), SOURCES,
                [Pass("a", "B", spy), Pass("b", "C", spy)], consensus_required=2)
    assert "_reasoning" not in captured, "verifier must not see extractor reasoning"
    assert "quote" in captured and "source_url" in captured

def test_result_records_every_verdict_for_the_audit_trail():
    r = run_cascade(CLAIM, SOURCES, [agree("a", "B"), refute("b", "C")], consensus_required=1)
    assert len(r.verdicts) == 2
    assert {v.passname for v in r.verdicts} == {"a", "b"}
