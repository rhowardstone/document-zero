"""Full pipeline: ingest -> sweep -> verify -> editor -> edition -> compile.

No API calls. The model is a deterministic stub, which is exactly the point: every
editorial rule in this path is testable without one.
"""
import json, sqlite3, pytest
from ledger.store import Ledger
from ledger.ingest import normalise
from ledger.beats import load_beats
from ledger.sweep import plan_sweep, run_sweep
from ledger.agent import BeatAgent
from ledger.editor import run_editor
from ledger.compile import compile_db
from ledger.verify import Pass, Verdict
from ledger.recirculation import analyse_cluster, Verdict as RV

BEATS = load_beats("config/beats.yaml")
BEAT_IDS = [b.id for b in BEATS]

def stub_extractor(prompt):
    """Quotes the first framed source verbatim, so quote-verification really runs."""
    body = prompt.split(">\n", 1)[1].split("\n</untrusted_source>", 1)[0]
    line = [l for l in body.splitlines() if len(l) > 25][0]
    ref = prompt.split('ref="', 1)[1].split('"', 1)[0]
    return json.dumps([{ "claim_text": f"Recorded: {line[:70]}", "quote": line[:60],
        "source_sha": ref, "confidence": 0.6,
        "confidence_justification": "single wire outlet; news ceiling",
        "tier": "documented_fact"}])

def agree(n, f): return Pass(n, f, lambda c, s: Verdict(False, "holds"))

def proposer(beat):
    def p(old, claims):
        return {"beat": beat, "as_of": "2026-08-14", "fields": [
            {"k": "Latest claim", "v": claims[0]["claim_text"][:48], "since": "14 Aug"},
            {"k": "Claims on record", "v": str(len(claims)), "since": "14 Aug"}]}
    return p

@pytest.fixture
def sources():
    raw = [
        {"url": "https://apnews.com/hormuz", "title": "Hormuz transit slows",
         "snippet": "Transit through the Strait appeared to grind to a near standstill as the blockade held.",
         "source_name": "AP", "published_at": "2026-08-14T09:00:00Z"},
        {"url": "https://cnbc.com/fed", "title": "Fed hike odds fall",
         "snippet": "Market implied odds of a September rate hike from the Federal Reserve fell to 34 percent.",
         "source_name": "CNBC", "published_at": "2026-08-14T08:00:00Z"},
    ]
    return [normalise(r, BEATS, now="2026-08-14T10:00:00Z") for r in raw]

def _factory(root, sha_index):
    def f(beat):
        led = Ledger(root, writer=f"beat:{beat}")
        return BeatAgent(ledger=led, beat=beat, policy={}, extractor=stub_extractor,
                         extractor_family="A", passes=[agree("refute","B"), agree("lens","C")],
                         state_proposer=proposer(beat), subject_resolver=lambda c: [],
                         now="2026-08-14T10:00:00Z", consensus_required=2)
    return f

def test_full_pipeline_produces_a_valid_edition_and_a_queryable_db(tmp_path):
    root = tmp_path / "data"
    srcs = [normalise(r, BEATS, now="2026-08-14T10:00:00Z") for r in [
        {"url": "https://apnews.com/hormuz", "title": "Hormuz transit slows",
         "snippet": "Transit through the Strait appeared to grind to a near standstill as the blockade held.",
         "source_name": "AP", "published_at": "2026-08-14T09:00:00Z"},
        {"url": "https://cnbc.com/fed", "title": "Fed hike odds fall",
         "snippet": "Market implied odds of a September rate hike from the Federal Reserve fell to 34 percent.",
         "source_name": "CNBC", "published_at": "2026-08-14T08:00:00Z"}]]

    ing = Ledger(root, writer="ingest")
    for s in srcs:
        ing.put_source("2026-08-14", s)

    plan = plan_sweep(srcs, BEAT_IDS, policy={})
    assert set(plan.by_beat) >= {"hormuz", "fed"}

    results = run_sweep(plan, _factory(root, {s["sha256"]: s for s in srcs}), concurrency=2)
    assert all(r.error is None for r in results), [r.error for r in results if r.error]
    assert sum(r.claims_written for r in results) >= 2

    ed = run_editor(Ledger(root, writer="editor"), results, day="2026-08-14",
                    policy={"publication": {"dry_run": True}}, clusters={}, beat_meta={})
    assert ed.counts["wire"] >= 2
    assert ed.publish is False and ed.publish_blocked_by == "dry_run"
    json.dumps(ed.to_dict())

    db = tmp_path / "newsdesk.db"
    compile_db(root, db)
    con = sqlite3.connect(db)
    assert con.execute("select count(*) from sources").fetchone()[0] == 2
    assert con.execute("select count(*) from claims").fetchone()[0] >= 2
    assert con.execute("select count(*) from beat_state where beat='hormuz'").fetchone()[0] == 2

def test_a_second_run_over_the_same_sources_publishes_nothing(tmp_path):
    """The suppression property, end to end: no state change means no edition."""
    root = tmp_path / "data"
    srcs = [normalise({"url": "https://apnews.com/hormuz", "title": "Hormuz transit slows",
        "snippet": "Transit through the Strait appeared to grind to a near standstill as the blockade held.",
        "source_name": "AP", "published_at": "2026-08-14T09:00:00Z"},
        BEATS, now="2026-08-14T10:00:00Z")]
    plan = plan_sweep(srcs, BEAT_IDS, policy={})
    fac = _factory(root, {})
    run_sweep(plan, fac, concurrency=1)
    second = run_sweep(plan, fac, concurrency=1)
    ed = run_editor(Ledger(root, writer="editor"), second, day="2026-08-15",
                    policy={}, clusters={}, beat_meta={})
    assert ed.counts["wire"] == 0
    assert ed.counts["dropped"] >= 1

def test_recirculated_cluster_lands_in_omissions_not_the_wire(tmp_path):
    root = tmp_path / "data"
    srcs = [normalise({"url": "https://apnews.com/flock", "title": "Flock announces changes",
        "snippet": "The license plate reader network cut its retention window to seven days.",
        "source_name": "AP", "published_at": "2026-08-13T14:00:00Z"},
        BEATS, now="2026-08-14T10:00:00Z")]
    results = run_sweep(plan_sweep(srcs, BEAT_IDS, policy={}), _factory(root, {}), concurrency=1)
    cluster = [{"source_name": f"o{i}", "published_at": "2026-08-14T08:00:00Z"} for i in range(6)]
    cluster.append({"source_name": "AP", "published_at": "2026-08-13T14:00:00Z"})
    verdict = analyse_cluster(cluster, today="2026-08-14")
    assert verdict is not None and verdict.verdict is RV.RECIRCULATION
    ed = run_editor(Ledger(root, writer="editor"), results, day="2026-08-14", policy={},
                    clusters={"flock": verdict.verdict}, beat_meta={})
    assert ed.counts["omissions"] == 1 and ed.counts["wire"] == 0
