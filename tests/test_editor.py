import pytest
from ledger.editor import build_records, run_editor
from ledger.agent import AgentResult
from ledger.diff import diff_state
from ledger.recirculation import Verdict
from ledger.store import Ledger

S1 = {"beat":"hormuz","as_of":"1","fields":[{"k":"x","v":"1","claims":["a"]},{"k":"y","v":"2","claims":["b"]}]}
S2 = {"beat":"hormuz","as_of":"2","fields":[{"k":"x","v":"CHANGED","claims":["a"]},{"k":"y","v":"2","claims":["b"]}]}

def res(beat="hormuz", moved=True, **kw):
    d = diff_state(S1, S2 if moved else S1)
    return AgentResult(beat=beat, delta=d, claims_written=1 if moved else 0, **kw)

def test_a_moved_beat_becomes_a_wire_record():
    recs = build_records([res()], clusters={}, policy={}, beat_meta={})
    wire = [r for r in recs if r["placement"].value == "wire"]
    assert len(wire) == 1 and wire[0]["beat"] == "hormuz"

def test_each_refusal_becomes_its_own_counted_record():
    recs = build_records([res(refused=["wrongdoing_by_private_individual",
                                       "uncorroborated_criminal_conduct"])],
                         clusters={}, policy={}, beat_meta={})
    ref = [r for r in recs if r["placement"].value == "refused"]
    assert len(ref) == 2
    assert {r["reason"] for r in ref} == {"wrongdoing_by_private_individual",
                                          "uncorroborated_criminal_conduct"}

def test_recirculation_on_an_unchanged_beat_routes_it_to_the_omissions_lane():
    recs = build_records([res(moved=False)], clusters={"hormuz": Verdict.RECIRCULATION},
                         policy={}, beat_meta={})
    assert [r["placement"].value for r in recs] == ["omission"]

def test_recirculation_does_not_suppress_a_beat_that_actually_moved():
    recs = build_records([res(moved=True)], clusters={"hormuz": Verdict.RECIRCULATION},
                         policy={}, beat_meta={})
    assert [r["placement"].value for r in recs] == ["wire"]

def test_a_beat_whose_agent_errored_is_held_not_silently_dropped():
    recs = build_records([AgentResult(beat="fed", error="boom", delta=diff_state(S1, S1))],
                         clusters={}, policy={}, beat_meta={})
    assert recs[0]["placement"].value == "hold"
    assert "boom" in recs[0]["reason"]

def test_consequence_weight_comes_from_config_and_is_exposed():
    recs = build_records([res()], clusters={}, policy={},
                         beat_meta={"hormuz": {"consequence": 9}})
    r = recs[0]
    assert r["components"]["consequence"] > 0
    assert r["score"] > 0

def test_evidence_component_uses_mean_claim_confidence():
    lo = build_records([res(mean_confidence=0.5)], clusters={}, policy={}, beat_meta={})[0]
    hi = build_records([res(mean_confidence=0.85)], clusters={}, policy={}, beat_meta={})[0]
    assert hi["score"] > lo["score"]

def test_run_editor_writes_the_edition_into_the_ledger(tmp_path):
    led = Ledger(tmp_path / "data", writer="editor")
    e = run_editor(led, [res()], day="2026-08-14", policy={}, clusters={}, beat_meta={})
    assert e.counts["wire"] == 1
    assert led._read_json("editions/2026-08-14.json")["day"] == "2026-08-14"

def test_editor_writes_only_inside_the_editor_partition(tmp_path):
    led = Ledger(tmp_path / "data", writer="editor")
    run_editor(led, [res()], day="2026-08-14", policy={}, clusters={}, beat_meta={})
    assert all(p.startswith("editions/") for p in led.written)

def test_dry_run_still_writes_the_edition_but_marks_it_unpublished(tmp_path):
    led = Ledger(tmp_path / "data", writer="editor")
    e = run_editor(led, [res()], day="2026-08-14",
                   policy={"publication": {"dry_run": True}}, clusters={}, beat_meta={})
    assert e.publish is False and e.publish_blocked_by == "dry_run"
    assert led._read_json("editions/2026-08-14.json") is not None
