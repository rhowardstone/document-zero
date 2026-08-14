import pytest
from ledger.rank import score_item, Score

def item(**over):
    d = dict(material_changes=1, beat_was_quiet=False, derived=False,
             consequence=5, evidence=0.6, coverage=5)
    d.update(over); return d

def test_score_exposes_every_component():
    s = score_item(item())
    assert set(s.components) == {"novelty", "consequence", "evidence", "derivation"}
    assert abs(s.total - sum(s.components.values())) < 1e-9

def test_more_material_changes_scores_higher():
    assert score_item(item(material_changes=4)).total > score_item(item(material_changes=1)).total

def test_a_beat_waking_from_quiet_scores_higher_than_a_busy_one():
    assert score_item(item(beat_was_quiet=True)).total > score_item(item(beat_was_quiet=False)).total

def test_derived_items_are_privileged_over_restatement():
    """A conclusion drawn from stored records is the product; restatement is not."""
    assert score_item(item(derived=True)).total > score_item(item(derived=False)).total

def test_consequence_dominates_coverage():
    low_cov_high_con = score_item(item(consequence=9, coverage=1))
    high_cov_low_con = score_item(item(consequence=2, coverage=9))
    assert low_cov_high_con.total > high_cov_low_con.total

def test_evidence_quality_raises_the_score():
    assert score_item(item(evidence=0.85)).total > score_item(item(evidence=0.5)).total

def test_distortion_ratio_is_reported_and_flags_undercoverage():
    s = score_item(item(consequence=9, coverage=1))
    assert s.distortion > 1.0 and s.undercovered

def test_distortion_flags_overcoverage():
    s = score_item(item(consequence=2, coverage=9))
    assert s.distortion < 1.0 and not s.undercovered

def test_score_is_deterministic():
    assert score_item(item()).total == score_item(item()).total
