import json, pytest
from ledger.publish import publish, llms_txt, SCHEMA

DATA = {
    "edition": {"n": "001", "date": "2026-08-14"},
    "beats": [
        {"id": "hormuz", "name": "Hormuz", "status": "moved", "dossiers": ["iran"],
         "types": ["conflict"], "events": 2, "lastChange": "2026-08-14",
         "state": [{"k": "Blockade", "v": "In force"}], "history": [],
         "unknown": ["Transit tonnage not ingested."]},
        {"id": "fed", "name": "Fed", "status": "quiet", "dossiers": ["econ"],
         "types": ["market"], "events": 0, "lastChange": "—",
         "state": [], "history": [], "unknown": []},
    ],
    "items": [
        {"id": "r1", "kind": "wire", "beats": ["hormuz"], "title": "Transit slowed.",
         "stamp": "open", "corroboration": 2,
         "sources": [{"n": "apnews.com", "u": "https://apnews.com/a", "t": "news", "c": "0.6"},
                     {"n": "reuters.com", "u": "https://reuters.com/b", "t": "news", "c": "0.6"}]},
        {"id": "r2", "kind": "wire", "beats": ["hormuz", "fed"], "title": "Prices rose.",
         "stamp": "open", "corroboration": 1,
         "sources": [{"n": "apnews.com", "u": "https://apnews.com/a", "t": "news", "c": "0.6"}]},
    ],
}

@pytest.fixture
def out(tmp_path):
    publish(DATA, tmp_path, base_url="https://doczero.example")
    return tmp_path

def _j(root, rel): return json.loads((root / rel).read_text())

def test_writes_an_index_naming_every_endpoint(out):
    idx = _j(out, "api/index.json")
    assert set(idx["endpoints"]) >= {"beats", "beat", "records", "sources", "schema"}
    assert {k: idx["counts"][k] for k in ("beats", "records", "sources")} \
        == {"beats": 2, "records": 2, "sources": 2}
    assert idx["counts"]["queries"] > 0

def test_each_beat_gets_its_own_endpoint(out):
    assert _j(out, "api/beat/hormuz.json")["beat"]["name"] == "Hormuz"
    assert (out / "api/beat/fed.json").exists()

def test_a_beat_endpoint_carries_its_records(out):
    recs = _j(out, "api/beat/hormuz.json")["records"]
    assert {r["id"] for r in recs} == {"r1", "r2"}

def test_a_record_on_two_beats_appears_under_both(out):
    assert "r2" in {r["id"] for r in _j(out, "api/beat/fed.json")["records"]}

def test_the_source_join_is_exposed_because_the_page_never_shows_it(out):
    srcs = {s["url"]: s for s in _j(out, "api/sources.json")["sources"]}
    ap = srcs["https://apnews.com/a"]
    assert sorted(ap["records"]) == ["r1", "r2"]
    assert ap["beats"] == ["fed", "hormuz"], "a source cited across beats is the interesting join"

def test_schema_states_what_corroboration_counts(out):
    s = _j(out, "api/schema.json")
    assert "PUBLISHERS" in s["record"]["corroboration"]
    assert s["confidence_ceilings"]["news"] == 0.6

def test_schema_says_a_stamp_is_not_an_importance_rating(out):
    assert "NOT an importance rating" in _j(out, "api/schema.json")["record"]["stamp"]

# --- llms.txt ---------------------------------------------------------------

def test_llms_txt_leads_with_the_disclosure():
    t = llms_txt(DATA)
    assert t.startswith("# Document Zero")
    assert "not reviewed by a person" in t

def test_llms_txt_warns_against_restating_an_open_record_as_fact():
    assert "Do not" in llms_txt(DATA) and "established fact" in llms_txt(DATA)

def test_llms_txt_explains_that_a_quiet_beat_is_not_evidence_of_absence():
    assert "Absence is not evidence of absence" in llms_txt(DATA)

def test_llms_txt_lists_every_beat_with_a_queryable_link():
    t = llms_txt(DATA, base_url="https://doczero.example")
    assert "https://doczero.example/api/beat/hormuz.json" in t
    assert "https://doczero.example/api/beat/fed.json" in t

def test_llms_txt_puts_moved_beats_before_quiet_ones():
    t = llms_txt(DATA)
    assert t.index("api/beat/hormuz.json") < t.index("api/beat/fed.json")

def test_llms_txt_suggests_questions_the_page_cannot_answer():
    t = llms_txt(DATA)
    assert "single publisher" in t and "more than one beat" in t

def test_publish_is_idempotent(tmp_path):
    a = publish(DATA, tmp_path); b = publish(DATA, tmp_path)
    assert a == b


def test_the_query_catalogue_is_published_and_self_describing(out):
    idx = _j(out, "api/query/index.json")
    names = [e["query"] for e in idx["queries"]]
    assert "uncorroborated" in names and "timeline" in names and "withheld" in names
    for e in idx["queries"]:
        # every advertised view must actually exist on disk
        v = _j(out, f"api/query/{e['query']}.json")
        assert v["question"] == e["question"] and v["count"] == e["count"]


def test_llms_txt_answers_questions_rather_than_pointing_at_a_dump(out):
    txt = (out / "llms.txt").read_text(encoding="utf-8")
    assert "## Ask a question" in txt
    assert "api/query/uncorroborated.json" in txt
    assert "newsdesk.db" in txt and "```sql" in txt
    # and it must still say where the record is weak
    assert "single-publisher-beats" in txt


def test_the_json_api_does_not_serve_html_entities_to_machines(tmp_path):
    """render.py escapes for the DOM. Carrying that into JSON hands an agent
    "defendant&#39;s death" — markup for a consumer that renders no markup."""
    data = {"edition": {"date": "2026-08-14"}, "beats": [], "items": [
        {"id": "r1", "kind": "wire", "beats": [], "corroboration": 1, "stamp": "documented",
         "title": "The defendant&#39;s death ended it &amp; closed the file",
         "sources": [{"n": "x.com", "u": "https://x.com/a", "t": "news", "c": "0.6"}]}]}
    publish(data, tmp_path)
    txt = (tmp_path / "api/records.json").read_text(encoding="utf-8")
    assert "&#39;" not in txt and "&amp;" not in txt
    assert "The defendant's death ended it & closed the file" in txt


def test_an_ampersand_in_the_source_round_trips(tmp_path):
    """AT&T escapes to AT&amp;T in render and must come back as AT&T, not AT&amp;T."""
    from ledger.render import esc
    data = {"edition": {"date": "2026-08-14"}, "beats": [], "items": [
        {"id": "r1", "kind": "wire", "beats": [], "corroboration": 1, "stamp": "documented",
         "title": esc("AT&T settled with M&S"), "sources": []}]}
    publish(data, tmp_path)
    import json as _json
    got = _json.loads((tmp_path / "api/records.json").read_text())["records"][0]["title"]
    assert got == "AT&T settled with M&S"


def test_every_sql_example_in_llms_txt_actually_runs(tmp_path):
    """Documentation an agent cannot execute is a trap. llms.txt advertised
    `beat_history.beat_id`, which does not exist, and a join on a column the
    compiler had dropped."""
    import re, sqlite3
    from ledger.compile import compile_db
    from ledger.store import Ledger

    led = Ledger(tmp_path / "data")
    led.put_source("2026-08-14", {"sha256": "b" * 64, "url": "https://x", "title": "T",
                                  "source_name": "E", "source_type": "news",
                                  "published_at": "2026-08-14T03:00:00Z",
                                  "first_seen": "2026-08-14T04:00:00Z", "candidate_beats": []})
    db = tmp_path / "n.db"
    compile_db(led.root, db)

    publish({"edition": {"date": "2026-08-14"}, "beats": [], "items": []}, tmp_path)
    txt = (tmp_path / "llms.txt").read_text(encoding="utf-8")
    blocks = re.findall(r"```sql\r?\n(.*?)```", txt, re.S)
    assert blocks, "llms.txt advertises SQL; if that stops being true, drop the claim"

    con = sqlite3.connect(db)
    ran = 0
    for block in blocks:
        for raw in block.split(";"):
            stmt = "\n".join(l for l in raw.splitlines()
                             if not l.strip().startswith("--")).strip()
            if not stmt:
                continue
            con.execute(stmt)      # raises if the example is wrong
            ran += 1
    assert ran >= 2, f"only {ran} statements exercised"
