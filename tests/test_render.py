import json, pytest
from ledger.render import build, write_data_js
from ledger.store import Ledger

CFG = "config/beats.yaml"

@pytest.fixture
def led(tmp_path):
    l = Ledger(tmp_path / "data")
    l.put_state("compliance", {"beat": "compliance", "as_of": "2026-08-14", "fields": [
        {"k": "Contempt", "v": "Noticed", "since": "13 Aug", "flag": "hot",
         "claims": ["compliance-1"]},
        {"k": "Notes", "v": "Withheld", "since": "13 Aug", "claims": ["compliance-1"]}]})
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


def test_one_claim_on_several_beats_renders_once(tmp_path):
    """A source routed to eight beats produced eight identical records — the
    single most disfiguring bug on the page."""
    l = Ledger(tmp_path / "data")
    shared = {"quote": "identical quote text", "source_sha": "a"*64,
              "claim_text": "The same finding.", "source_type": "news",
              "source_url": "https://apnews.com/x", "confidence": 0.6,
              "confidence_justification": "j", "tier": "credible_allegation",
              "extracted_by": "t", "extracted_at": "n"}
    for beat in ("compliance", "nm-records", "epstein-network"):
        l.put_claim(dict(shared, id=f"{beat}-1", beat=beat))
    Ledger(l.root, writer="editor")._write_json("editions/2026-08-14.json", {
        "day": "2026-08-14", "omissions": [], "holds": [], "counts": {}, "publish": False,
        "wire": [{"id": b, "beat": b} for b in ("compliance", "nm-records", "epstein-network")]})
    d = build(l.root, CFG, "2026-08-14")
    same = [i for i in d["items"] if i["title"] == "The same finding."]
    assert len(same) == 1, "one finding is one record"
    assert set(same[0]["beats"]) == {"compliance", "nm-records", "epstein-network"}

def test_distinct_claims_from_the_same_source_stay_separate(tmp_path):
    l = Ledger(tmp_path / "data")
    base = {"source_sha": "a"*64, "source_type": "news", "beat": "compliance",
            "source_url": "https://apnews.com/x", "confidence": 0.6,
            "confidence_justification": "j", "tier": "credible_allegation",
            "extracted_by": "t", "extracted_at": "n"}
    l.put_claim(dict(base, id="c1", claim_text="First", quote="first quote"))
    l.put_claim(dict(base, id="c2", claim_text="Second", quote="second quote"))
    Ledger(l.root, writer="editor")._write_json("editions/2026-08-14.json", {
        "day": "2026-08-14", "omissions": [], "holds": [], "counts": {}, "publish": False,
        "wire": [{"id": "compliance", "beat": "compliance"}]})
    assert len(build(l.root, CFG, "2026-08-14")["items"]) == 2


def test_a_held_beat_that_also_has_claims_still_reports_the_hold(tmp_path):
    """Regression: the placement record was shadowed by the claim record, so a
    beat with both a hold and claims silently lost its 'unknown' entries."""
    l = Ledger(tmp_path / "data")
    l.put_claim({"id": "compliance-1", "beat": "compliance", "claim_text": "X",
                 "quote": "q", "source_type": "news", "source_url": "https://apnews.com/x",
                 "confidence": 0.6, "confidence_justification": "j",
                 "tier": "credible_allegation", "extracted_by": "t", "extracted_at": "n"})
    Ledger(l.root, writer="editor")._write_json("editions/2026-08-14.json", {
        "day": "2026-08-14", "wire": [], "omissions": [],
        "holds": [{"id": "compliance", "beat": "compliance",
                   "reason": "single_root_multi_source", "rejected_claims": 4}],
        "counts": {}, "publish": False})
    b = next(b for b in build(l.root, CFG, "2026-08-14")["beats"] if b["id"] == "compliance")
    assert b["status"] == "unresolved"
    assert any("single_root_multi_source" in u for u in b["unknown"])
    assert any("4 extracted claim(s) failed validation" in u for u in b["unknown"])


def test_the_same_finding_from_several_outlets_is_one_record_with_several_sources(tmp_path):
    """Corroboration, not repetition. Three outlets is one record."""
    l = Ledger(tmp_path / "data")
    base = {"beat": "compliance", "claim_text": "DoJ missed the deadline.",
            "source_type": "news", "confidence": 0.6,
            "confidence_justification": "j", "tier": "credible_allegation",
            "extracted_by": "t", "extracted_at": "n"}
    for i, host in enumerate(("apnews.com", "reuters.com", "npr.org")):
        l.put_claim(dict(base, id=f"c{i}", quote=f"quote {i}",
                         source_sha=f"{i}"*64, source_url=f"https://{host}/x"))
    Ledger(l.root, writer="editor")._write_json("editions/2026-08-14.json", {
        "day": "2026-08-14", "omissions": [], "holds": [], "counts": {}, "publish": False,
        "wire": [{"id": "compliance", "beat": "compliance"}]})
    items = build(l.root, CFG, "2026-08-14")["items"]
    assert len(items) == 1, "one finding is one record"
    assert items[0]["corroboration"] == 3
    assert {s["n"] for s in items[0]["sources"]} == {"apnews.com", "reuters.com", "npr.org"}

def test_the_same_outlet_twice_does_not_inflate_corroboration(tmp_path):
    l = Ledger(tmp_path / "data")
    base = {"beat": "compliance", "claim_text": "Same finding.", "source_type": "news",
            "source_url": "https://apnews.com/x", "confidence": 0.6,
            "confidence_justification": "j", "tier": "credible_allegation",
            "extracted_by": "t", "extracted_at": "n"}
    l.put_claim(dict(base, id="c1", quote="q1", source_sha="a"*64))
    l.put_claim(dict(base, id="c2", quote="q2", source_sha="b"*64))
    Ledger(l.root, writer="editor")._write_json("editions/2026-08-14.json", {
        "day": "2026-08-14", "omissions": [], "holds": [], "counts": {}, "publish": False,
        "wire": [{"id": "compliance", "beat": "compliance"}]})
    items = build(l.root, CFG, "2026-08-14")["items"]
    assert len(items) == 1 and items[0]["corroboration"] == 1

def test_sources_show_the_publisher_not_the_raw_url(tmp_path):
    l = Ledger(tmp_path / "data")
    l.put_claim({"id": "c1", "beat": "compliance", "claim_text": "X", "quote": "q",
                 "source_type": "news", "source_url": "https://www.reuters.com/a/b/c",
                 "confidence": 0.6, "confidence_justification": "j",
                 "tier": "credible_allegation", "extracted_by": "t", "extracted_at": "n"})
    Ledger(l.root, writer="editor")._write_json("editions/2026-08-14.json", {
        "day": "2026-08-14", "omissions": [], "holds": [], "counts": {}, "publish": False,
        "wire": [{"id": "compliance", "beat": "compliance"}]})
    assert build(l.root, CFG, "2026-08-14")["items"][0]["sources"][0]["n"] == "reuters.com"


def test_corroboration_counts_publishers_not_urls(tmp_path):
    """Three bing.com links are one aggregator, not three witnesses."""
    l = Ledger(tmp_path / "data")
    base = {"beat": "compliance", "claim_text": "Same finding.", "source_type": "misc",
            "confidence": 0.4, "confidence_justification": "j",
            "tier": "credible_allegation", "extracted_by": "t", "extracted_at": "n"}
    for i in range(3):
        l.put_claim(dict(base, id=f"c{i}", quote=f"q{i}", source_sha=f"{i}"*64,
                         source_url=f"https://www.bing.com/news/{i}"))
    l.put_claim(dict(base, id="c9", quote="q9", source_sha="9"*64,
                     source_url="https://apnews.com/real"))
    Ledger(l.root, writer="editor")._write_json("editions/2026-08-14.json", {
        "day": "2026-08-14", "omissions": [], "holds": [], "counts": {}, "publish": False,
        "wire": [{"id": "compliance", "beat": "compliance"}]})
    it = build(l.root, CFG, "2026-08-14")["items"][0]
    assert len(it["sources"]) == 4
    assert it["corroboration"] == 2, "bing.com x3 + apnews.com = two publishers"


def test_a_beat_in_the_omissions_lane_gets_a_record_on_the_page(tmp_path):
    """Heavy coverage with no state change IS the finding — if it renders as
    nothing, the format's central argument is invisible."""
    l = Ledger(tmp_path / "data")
    Ledger(l.root, writer="editor")._write_json("editions/2026-08-14.json", {
        "day": "2026-08-14", "wire": [], "holds": [],
        "omissions": [{"id": "flock", "beat": "flock", "reason": "recirculation"}],
        "counts": {}, "publish": False})
    d = build(l.root, CFG, "2026-08-14")
    om = [i for i in d["items"] if i["kind"] == "omission"]
    assert len(om) == 1
    assert om[0]["beats"] == ["flock"] and "recirculation" in om[0]["short"]

def test_a_wire_beat_produces_no_omission_record(tmp_path):
    l = Ledger(tmp_path / "data")
    Ledger(l.root, writer="editor")._write_json("editions/2026-08-14.json", {
        "day": "2026-08-14", "omissions": [], "holds": [],
        "wire": [{"id": "flock", "beat": "flock"}], "counts": {}, "publish": False})
    assert not [i for i in build(l.root, CFG, "2026-08-14")["items"]
                if i["kind"] == "omission"]


def _editor(l):
    e = Ledger(l.root, writer="editor")
    e._write_json("editions/2026-08-14.json", {"day": "2026-08-14", "wire": [],
                  "omissions": [], "holds": [], "counts": {}, "publish": False})
    return e

def test_questions_are_rendered_and_attached_to_their_beat(tmp_path):
    l = Ledger(tmp_path / "data"); e = _editor(l)
    e._write_json("questions/q1.json", {"id": "q1", "beat": "compliance",
                                        "q": "Why were notes withheld?", "status": "Open"})
    d = build(l.root, CFG, "2026-08-14")
    assert [q["id"] for q in d["questions"]] == ["q1"]
    b = next(b for b in d["beats"] if b["id"] == "compliance")
    assert b["questions"] == ["q1"]

def test_triggers_render_in_date_order(tmp_path):
    l = Ledger(tmp_path / "data"); e = _editor(l)
    e._write_json("triggers/t2.json", {"id": "t2", "sort": "2026-09-01", "d": "1 SEP",
                                       "t": "Later", "beat": "compliance"})
    e._write_json("triggers/t1.json", {"id": "t1", "sort": "2026-08-20", "d": "20 AUG",
                                       "t": "Sooner", "beat": "compliance"})
    d = build(l.root, CFG, "2026-08-14")
    assert [t["id"] for t in d["triggers"]] == ["t1", "t2"], "soonest first"

def test_contradictions_render(tmp_path):
    l = Ledger(tmp_path / "data"); e = _editor(l)
    e._write_json("contradictions/c1.json", {"id": "c1", "a": "X", "b": "not X",
                                             "beat": "compliance", "c": "0.7"})
    assert build(l.root, CFG, "2026-08-14")["contradictions"][0]["id"] == "c1"

def test_empty_rails_stay_empty_rather_than_erroring(tmp_path):
    l = Ledger(tmp_path / "data"); _editor(l)
    d = build(l.root, CFG, "2026-08-14")
    assert d["questions"] == [] and d["triggers"] == [] and d["contradictions"] == []


# ===========================================================================
# Regressions from an adversarial external review. Each of these was a real
# defect in shipped code, not a hypothetical.
# ===========================================================================

def test_hostile_source_text_cannot_reach_the_dom(tmp_path):
    """Stored DOM XSS: scraped text was interpolated raw into fields the site
    renders with innerHTML."""
    l = Ledger(tmp_path / "data")
    l.put_claim({"id": "c1", "beat": "compliance",
                 "claim_text": '<img src=x onerror="alert(1)">',
                 "quote": "</script><script>alert(2)</script>",
                 "source_type": "news", "source_url": "https://apnews.com/x",
                 "confidence": 0.6,
                 "confidence_justification": '"><svg onload=alert(3)>',
                 "tier": "credible_allegation", "extracted_by": "t", "extracted_at": "n"})
    Ledger(l.root, writer="editor")._write_json("editions/2026-08-14.json", {
        "day": "2026-08-14", "omissions": [], "holds": [], "counts": {}, "publish": False,
        "wire": [{"id": "compliance", "beat": "compliance"}]})
    it = build(l.root, CFG, "2026-08-14")["items"][0]
    blob = json.dumps(it)
    assert "<img" not in blob and "<script" not in blob and "<svg" not in blob
    assert "onerror" not in blob or "&" in it["title"]
    assert "&lt;img" in it["title"]

def test_a_javascript_url_is_neutralised(tmp_path):
    l = Ledger(tmp_path / "data")
    l.put_claim({"id": "c1", "beat": "compliance", "claim_text": "X", "quote": "q",
                 "source_type": "misc", "source_url": "javascript:alert(1)",
                 "confidence": 0.5, "confidence_justification": "j",
                 "tier": "credible_allegation", "extracted_by": "t", "extracted_at": "n"})
    Ledger(l.root, writer="editor")._write_json("editions/2026-08-14.json", {
        "day": "2026-08-14", "omissions": [], "holds": [], "counts": {}, "publish": False,
        "wire": [{"id": "compliance", "beat": "compliance"}]})
    assert build(l.root, CFG, "2026-08-14")["items"][0]["sources"][0]["u"] == "#"

def test_hostile_state_and_history_are_escaped_too(tmp_path):
    l = Ledger(tmp_path / "data")
    l.put_state("compliance", {"beat": "compliance", "as_of": "2026-08-14", "fields": [
        {"k": "<b>k</b>", "v": "<script>x</script>", "since": "now", "claims": ["c1"]},
        {"k": "ok", "v": "fine", "since": "now", "claims": ["c1"]}]})
    l.append_history("compliance", {"d": "2026-08-14", "c": "<img src=x>", "s": "s"})
    Ledger(l.root, writer="editor")._write_json("editions/2026-08-14.json", {
        "day": "2026-08-14", "wire": [], "omissions": [], "holds": [],
        "counts": {}, "publish": False})
    b = next(b for b in build(l.root, CFG, "2026-08-14")["beats"] if b["id"] == "compliance")
    assert "<script" not in json.dumps(b) and "<img" not in json.dumps(b)

def test_a_held_beats_claims_never_reach_the_wire(tmp_path):
    """The renderer was bypassing the editor entirely: every stored claim was
    emitted as wire regardless of lane, which falsified the system's core claim."""
    l = Ledger(tmp_path / "data")
    l.put_claim({"id": "c1", "beat": "compliance", "claim_text": "Held finding.",
                 "quote": "q", "source_type": "news", "source_url": "https://apnews.com/x",
                 "confidence": 0.6, "confidence_justification": "j",
                 "tier": "credible_allegation", "extracted_by": "t", "extracted_at": "n"})
    Ledger(l.root, writer="editor")._write_json("editions/2026-08-14.json", {
        "day": "2026-08-14", "wire": [], "omissions": [],
        "holds": [{"id": "compliance", "beat": "compliance", "reason": "single_root_multi_source"}],
        "counts": {}, "publish": False})
    d = build(l.root, CFG, "2026-08-14")
    assert not [i for i in d["items"] if i["kind"] == "wire"]

def test_a_recirculating_beats_claims_never_reach_the_wire(tmp_path):
    l = Ledger(tmp_path / "data")
    l.put_claim({"id": "c1", "beat": "flock", "claim_text": "Old news.", "quote": "q",
                 "source_type": "news", "source_url": "https://apnews.com/x",
                 "confidence": 0.6, "confidence_justification": "j",
                 "tier": "credible_allegation", "extracted_by": "t", "extracted_at": "n"})
    Ledger(l.root, writer="editor")._write_json("editions/2026-08-14.json", {
        "day": "2026-08-14", "wire": [], "holds": [],
        "omissions": [{"id": "flock", "beat": "flock", "reason": "recirculation"}],
        "counts": {}, "publish": False})
    kinds = {i["kind"] for i in build(l.root, CFG, "2026-08-14")["items"]}
    assert kinds == {"omission"}, "a beat cannot both say 'nothing new' and publish claims"
