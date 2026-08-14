import pytest
from ledger.placement import classify, Placement, PlacementInput
from ledger.recirculation import Verdict
from ledger.diff import diff_state

S1 = {"beat":"b","as_of":"1","fields":[{"k":"x","v":"1","claims":["a"]},{"k":"y","v":"2","claims":["b"]}]}
S2 = {"beat":"b","as_of":"2","fields":[{"k":"x","v":"CHANGED","claims":["a"]},{"k":"y","v":"2","claims":["b"]}]}
MOVED = diff_state(S1, S2)
STILL = diff_state(S1, S1)

def inp(**over):
    d = dict(delta=MOVED, recirculation=Verdict.FRESH, refused=None,
             single_root=False, cascade_survived=True)
    d.update(over); return PlacementInput(**d)

def test_a_moved_beat_with_clean_provenance_goes_to_the_wire():
    assert classify(inp()).placement is Placement.WIRE

def test_a_refusal_beats_everything_else():
    r = classify(inp(refused="wrongdoing_by_private_individual", recirculation=Verdict.FRESH))
    assert r.placement is Placement.REFUSED
    assert r.reason == "wrongdoing_by_private_individual"

def test_a_date_conflict_is_held_not_published():
    r = classify(inp(recirculation=Verdict.DATE_CONFLICT))
    assert r.placement is Placement.HOLD and r.reason == "date_conflict"

def test_a_single_root_cluster_is_held():
    r = classify(inp(single_root=True))
    assert r.placement is Placement.HOLD and r.reason == "single_root_multi_source"

def test_a_failed_cascade_is_held():
    r = classify(inp(cascade_survived=False))
    assert r.placement is Placement.HOLD and r.reason == "consensus_failure"

def test_recirculation_moves_an_unchanged_item_to_the_omissions_lane():
    r = classify(inp(delta=STILL, recirculation=Verdict.RECIRCULATION))
    assert r.placement is Placement.OMISSION and r.reason == "recirculation"

def test_no_state_change_drops_the_item_entirely():
    assert classify(inp(delta=STILL)).placement is Placement.DROP

def test_recirculation_with_no_state_change_is_still_an_omission():
    """Flock: heavy coverage, zero underlying change. That IS the finding."""
    r = classify(inp(delta=STILL, recirculation=Verdict.RECIRCULATION))
    assert r.placement is Placement.OMISSION

def test_hold_outranks_omission():
    r = classify(inp(delta=STILL, recirculation=Verdict.RECIRCULATION, single_root=True))
    assert r.placement is Placement.HOLD


def test_a_material_change_outranks_recirculation():
    """Regression: a beat whose state actually moved was labelled 'covered again,
    nothing new' — publishing a false statement about the record."""
    r = classify(inp(delta=MOVED, recirculation=Verdict.RECIRCULATION))
    assert r.placement is Placement.WIRE

def test_recirculation_still_applies_when_nothing_changed():
    r = classify(inp(delta=STILL, recirculation=Verdict.RECIRCULATION))
    assert r.placement is Placement.OMISSION
