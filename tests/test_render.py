import json, pytest
from ledger.render import build, write_data_js
from ledger.store import Ledger

CFG = "config/beats.yaml"

@pytest.fixture
def led(tmp_path):
    l = Ledger(tmp_path / "data")
    l.put_state("compliance", {"beat": "compliance", "as_of": "2026-08-14", "fields": [
        {"k": "Contempt", "v": "Noticed", "since": "13 Aug", "flag": "hot"},
        {"k": "Notes", "v": "Withheld", "since": "13 Aug"}]})
    l.append_history("compliance", {"d": "2026-08-14", "c": "Contempt → Noticed", "s": "1 claim"})
    l.put_claim({"id": "compliance-1", "beat": "compliance",
                 "claim_text": "A judge threatened sanctions.", "quote": "threatens DOJ sanctions",
                 "source_type": "news", "source_url": "https://x", "confidence": 0.55,
                 "confidence_justification": "single headline", "tier": "credible_allegation",
                 "extracted_by": "t", "extracted_at": "2026-08-14T05:00:00Z",
                 "verification_rounds": 1, "verifier_families": ["claude-sonnet-5"]})
    Ledger(l.root, writer="editor")._write_json("editions/2026-08-14.json", {
        "day": "2026-08-14", "wire": [{"id": "compliance", "beat": "compliance", "score": 9.0}],
        "omissions": [], "holds": [], "counts": {"wire": 1}, "publish": False,
        "publish_blocked_by": "dry_run"})
    return l

def test_every_configured_beat_appears(led):
    d = build(led.root, CFG, "2026-08-14")
    from ledger.beats import load_beats
    assert len(d["beats"]) == len(load_beats(CFG))

def test_state_fields_come_from_the_ledger(led):
    b = next(b for b in build(led.root, CFG, "2026-08-14")["beats"] if b["id"] == "compliance")
    assert [f["k"] for f in b["state"]] == ["Contempt", "Notes"]
    assert b["state"][0]["flag"] == "hot"

def test_history_is_newest_first(led):
    led.append_history("compliance", {"d": "2026-08-15", "c": "later", "s": "s"})
    b = next(b for b in build(led.root, CFG, "2026-08-14")["beats"] if b["id"] == "compliance")
    assert b["history"][0]["d"] == "2026-08-15"

def test_a_beat_the_edition_placed_on_the_wire_reads_as_moved(led):
    b = next(b for b in build(led.root, CFG, "2026-08-14")["beats"] if b["id"] == "compliance")
    assert b["status"] == "moved"

def test_a_beat_with_no_state_or_claims_reads_as_quiet(led):
    b = next(b for b in build(led.root, CFG, "2026-08-14")["beats"] if b["id"] == "uk-inquiry")
    assert b["status"] == "quiet" and b["state"] == []

def test_a_held_beat_reads_as_unresolved(tmp_path):
    l = Ledger(tmp_path / "data")
    Ledger(l.root, writer="editor")._write_json("editions/2026-08-14.json", {
        "day": "2026-08-14", "wire": [], "omissions": [],
        "holds": [{"id": "compliance", "beat": "compliance", "reason": "agent_error: boom"}],
        "counts": {}, "publish": False})
    b = next(b for b in build(l.root, CFG, "2026-08-14")["beats"] if b["id"] == "compliance")
    assert b["status"] == "unresolved"
    assert any("boom" in u for u in b["unknown"])

def test_claims_become_records_carrying_their_tier_and_confidence(led):
    d = build(led.root, CFG, "2026-08-14")
    it = next(i for i in d["items"] if i["id"] == "compliance-1")
    assert it["stamp"] == "open", "a credible_allegation must not render as documented"
    assert "0.55" in it["derived"] and "claude-sonnet-5" in it["derived"]
    assert "threatens DOJ sanctions" in it["body"][0]

def test_a_documented_fact_renders_with_the_documented_stamp(led):
    led.put_claim({"id": "compliance-2", "beat": "compliance", "claim_text": "X",
                   "quote": "q", "source_type": "documentation", "source_url": "https://y",
                   "confidence": 0.8, "confidence_justification": "primary",
                   "tier": "documented_fact", "extracted_by": "t", "extracted_at": "n"})
    d = build(led.root, CFG, "2026-08-14")
    assert next(i for i in d["items"] if i["id"] == "compliance-2")["stamp"] == "documented"

def test_a_beat_with_no_surviving_claim_says_so(led):
    b = next(b for b in build(led.root, CFG, "2026-08-14")["beats"] if b["id"] == "fed")
    assert any("No claim has survived" in u for u in b["unknown"])

def test_rejected_claims_are_surfaced_not_hidden(tmp_path):
    l = Ledger(tmp_path / "data")
    Ledger(l.root, writer="editor")._write_json("editions/2026-08-14.json", {
        "day": "2026-08-14", "wire": [{"id": "compliance", "beat": "compliance",
                                        "rejected_claims": 3}],
        "omissions": [], "holds": [], "counts": {}, "publish": False})
    b = next(b for b in build(l.root, CFG, "2026-08-14")["beats"] if b["id"] == "compliance")
    assert any("3 extracted claim(s) failed validation" in u for u in b["unknown"])

def test_archive_records_that_publication_was_blocked(led):
    d = build(led.root, CFG, "2026-08-14")
    assert "dry_run" in d["archive"][0]["note"]

def test_output_is_json_serialisable_and_written_as_a_js_assignment(led, tmp_path):
    out = write_data_js(build(led.root, CFG, "2026-08-14"), tmp_path / "data.js")
    txt = out.read_text()
    assert txt.startswith("/* generated from the ledger")
    assert "window.DZ = {" in txt
    json.loads(txt.split("window.DZ = ", 1)[1].rstrip().rstrip(";"))

def test_render_on_an_empty_ledger_does_not_crash(tmp_path):
    d = build(tmp_path / "nothing", CFG, "2026-08-14")
    assert d["items"] == [] and all(b["status"] == "quiet" for b in d["beats"])
