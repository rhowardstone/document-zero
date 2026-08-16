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
    assert "threatens DOJ sanctions" in it["quote"]

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
    assert om[0]["beats"] == ["flock"] and om[0]["reason"] == "recirculation"
    assert om[0]["beat_name"] and "claims_standing" in om[0]

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

def test_hostile_source_text_survives_as_data_not_markup(tmp_path):
    """The projection emits DATA. It used to escape here, and the page trusted
    that it had; that contract failed twice and each failure was stored XSS.
    Escaping now happens at DOM insertion (see test_page_escaping.py), so what
    this layer must guarantee is the opposite: the text is not mangled, so the
    JSON API and the database carry what the source actually said."""
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
    assert it["title"] == '<img src=x onerror="alert(1)">'
    assert it["quote"] == "</script><script>alert(2)</script>"
    assert "&amp;" not in json.dumps(it), "no double-encoding on the way to JSON"

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

def test_hostile_state_and_history_survive_verbatim(tmp_path):
    l = Ledger(tmp_path / "data")
    l.put_state("compliance", {"beat": "compliance", "as_of": "2026-08-14", "fields": [
        {"k": "<b>k</b>", "v": "<script>x</script>", "since": "now", "claims": ["c1"]},
        {"k": "ok", "v": "fine", "since": "now", "claims": ["c1"]}]})
    l.append_history("compliance", {"d": "2026-08-14", "c": "<img src=x>", "s": "s"})
    Ledger(l.root, writer="editor")._write_json("editions/2026-08-14.json", {
        "day": "2026-08-14", "wire": [], "omissions": [], "holds": [],
        "counts": {}, "publish": False})
    b = next(b for b in build(l.root, CFG, "2026-08-14")["beats"] if b["id"] == "compliance")
    assert b["state"][0] == {"k": "<b>k</b>", "v": "<script>x</script>",
                             "since": "now", "flag": None}
    assert b["history"][0]["c"] == "<img src=x>"

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


def test_the_page_receives_the_before_and_after_of_every_change(tmp_path):
    l = Ledger(tmp_path / "data")
    Ledger(l.root, writer="editor")._write_json("editions/2026-08-14.json", {
        "day": "2026-08-14", "omissions": [], "holds": [], "counts": {"wire": 1},
        "publish": False, "publish_blocked_by": "dry_run",
        "wire": [{"id": "compliance", "beat": "compliance",
                  "changes": [{"k": "Contempt", "from": "Available", "to": "Noticed"}],
                  "added": [{"k": "Notes", "v": "Withheld"}], "removed": [],
                  "unchanged": 3}]})
    d = build(l.root, CFG, "2026-08-14")
    b = next(b for b in d["beats"] if b["id"] == "compliance")
    assert b["changes"] == [{"k": "Contempt", "from": "Available", "to": "Noticed"}]
    assert b["added"] == [{"k": "Notes", "v": "Withheld"}] and b["unchanged"] == 3

def test_the_publish_state_travels_with_the_data(tmp_path):
    """The page must not be able to imply it is published when it is not."""
    l = Ledger(tmp_path / "data")
    Ledger(l.root, writer="editor")._write_json("editions/2026-08-14.json", {
        "day": "2026-08-14", "wire": [], "omissions": [], "holds": [],
        "counts": {"wire": 0}, "publish": False, "publish_blocked_by": "dry_run"})
    ed = build(l.root, CFG, "2026-08-14")["edition"]
    assert ed["publish"] is False and ed["blocked_by"] == "dry_run"

def test_a_hostile_change_value_survives_verbatim(tmp_path):
    l = Ledger(tmp_path / "data")
    Ledger(l.root, writer="editor")._write_json("editions/2026-08-14.json", {
        "day": "2026-08-14", "omissions": [], "holds": [], "counts": {}, "publish": False,
        "wire": [{"id": "compliance", "beat": "compliance",
                  "changes": [{"k": "<img src=x>", "from": "a", "to": "<script>y</script>"}]}]})
    b = next(b for b in build(l.root, CFG, "2026-08-14")["beats"] if b["id"] == "compliance")
    assert b["changes"][0] == {"k": "<img src=x>", "from": "a", "to": "<script>y</script>"}


def test_questions_and_triggers_pass_through_unmangled(tmp_path):
    """These are ledger objects a model can write. They reach the DOM through
    the page's escaper like everything else."""
    l = Ledger(tmp_path / "data")
    (l.root / "questions").mkdir(parents=True, exist_ok=True)
    (l.root / "questions" / "q1.json").write_text(json.dumps({
        "id": "q1", "beat": "compliance", "q": "<img src=x onerror=alert(1)>",
        "who": ["<script>a</script>"]}))
    q = build(l.root, CFG, "2026-08-14")["questions"][0]
    assert q["q"] == "<img src=x onerror=alert(1)>"


def test_opened_and_last_change_come_from_the_dates_not_the_file_order(tmp_path):
    """append_history writes in production order, not event order. A backfilled
    beat rendered as opened seven years after its last change."""
    l = Ledger(tmp_path / "data")
    w = Ledger(l.root, writer="beat:compliance")
    for d, c in [("2026-08-05", "newest"), ("2019-07-23", "oldest"),
                 ("2023-01-09", "middle")]:
        w.append_history("compliance", {"d": d, "c": c, "s": ""})
    b = next(b for b in build(l.root, CFG, "2026-08-14")["beats"] if b["id"] == "compliance")
    assert b["opened"] == "2019-07-23"
    assert b["lastChange"] == "2026-08-05"
    assert [h["d"] for h in b["history"]] == ["2026-08-05", "2023-01-09", "2019-07-23"]


def test_one_obligation_renders_as_one_row_whoever_recorded_it(tmp_path):
    """Two agents noticing the same court date wrote two triggers for it."""
    l = Ledger(tmp_path / "data")
    (l.root / "triggers").mkdir(parents=True, exist_ok=True)
    for i, (tid, note) in enumerate([("t-a", "short"), ("t-b", "a much longer note")]):
        (l.root / "triggers" / f"{tid}.json").write_text(json.dumps({
            "id": tid, "beat": "compliance", "sort": "2026-09-05", "d": "SEP",
            "t": "Government response due, New Mexico v. DOJ", "s": note}))
    trig = build(l.root, CFG, "2026-08-14")["triggers"]
    assert len(trig) == 1, trig
    assert trig[0]["s"] == "a much longer note", "the more specific note should win"


def test_genuinely_different_obligations_are_both_kept(tmp_path):
    l = Ledger(tmp_path / "data")
    (l.root / "triggers").mkdir(parents=True, exist_ok=True)
    for tid, sort, text in [("t-a", "2026-09-05", "Response due"),
                            ("t-b", "2026-09-15", "Response due"),
                            ("t-c", "2026-09-05", "Subpoena returns")]:
        (l.root / "triggers" / f"{tid}.json").write_text(json.dumps({
            "id": tid, "beat": "compliance", "sort": sort, "d": "SEP", "t": text, "s": ""}))
    assert len(build(l.root, CFG, "2026-08-14")["triggers"]) == 3


def test_the_hold_reason_reaches_the_page_as_data(tmp_path):
    """The hold reason was the last field the old design forgot to escape. Under
    the new design there is nothing to forget: it travels as text."""
    l = Ledger(tmp_path / "data")
    payload = '<img src=x onerror=alert(1)>'
    Ledger(l.root, writer="editor")._write_json("editions/2026-08-14.json", {
        "day": "2026-08-14", "wire": [], "omissions": [], "publish": False,
        "counts": {"holds": 1},
        "holds": [{"id": "compliance", "beat": "compliance", "reason": payload,
                   "changes": [], "added": [{"k": payload, "v": payload}]}]})
    (l.root / "questions").mkdir(parents=True, exist_ok=True)
    (l.root / "questions" / "q.json").write_text(json.dumps(
        {"id": "q", "beat": "compliance", "q": payload, "known": payload}))
    b = next(b for b in build(l.root, CFG, "2026-08-14")["beats"] if b["id"] == "compliance")
    assert b["unknown"][0] == f"Held: {payload}"


def test_one_open_question_renders_once_however_many_agents_recorded_it(tmp_path):
    """A later agent narrowed a question and wrote it under a new id, so the
    page showed it twice — once narrowed, once not."""
    l = Ledger(tmp_path / "data")
    (l.root / "questions").mkdir(parents=True, exist_ok=True)
    for qid, known in [("q-a", "short"), ("q-b", "a much longer, narrowed answer")]:
        (l.root / "questions" / f"{qid}.json").write_text(json.dumps({
            "id": qid, "beat": "compliance",
            "q": "What evidentiary value was lost at the site?", "known": known}))
    qs = build(l.root, CFG, "2026-08-14")["questions"]
    assert len(qs) == 1, qs
    assert qs[0]["known"] == "a much longer, narrowed answer"


def test_the_month_label_comes_from_the_date_not_from_the_stored_string(tmp_path):
    """Seeds wrote "SEP" and "3 NOV", and the page rendered "3 NOV / 03"."""
    l = Ledger(tmp_path / "data")
    (l.root / "triggers").mkdir(parents=True, exist_ok=True)
    (l.root / "triggers" / "t.json").write_text(json.dumps({
        "id": "t", "beat": "compliance", "sort": "2026-11-03",
        "d": "3 NOV", "t": "Texas Comptroller election", "s": ""}))
    t = build(l.root, CFG, "2026-08-14")["triggers"][0]
    assert t["d"] == "NOV" and t["day"] == "03"
