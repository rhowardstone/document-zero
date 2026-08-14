"""Ingest -> store -> compile, end to end, with no model involved."""
import sqlite3
from ledger.store import Ledger
from ledger.ingest import normalise
from ledger.beats import load_beats
from ledger.compile import compile_db
from ledger.recirculation import analyse_cluster, Verdict

BEATS = load_beats("config/beats.yaml")

def test_full_cycle_detects_recirculation_and_compiles(tmp_path):
    led = Ledger(tmp_path / "data", writer="ingest")
    origin = {"url": "https://ap.org/flock", "title": "Flock announces changes",
              "snippet": "The plate reader network cut retention to seven days.",
              "source_name": "AP", "published_at": "2026-08-13T14:00:00Z"}
    led.put_source("2026-08-13", normalise(origin, BEATS, "2026-08-13T14:30:00Z"))

    followers = []
    for i in range(8):
        raw = {**origin, "url": f"https://outlet{i}.com/flock", "source_name": f"Outlet{i}",
               "published_at": "2026-08-14T08:00:00Z"}
        s = normalise(raw, BEATS, "2026-08-14T08:05:00Z")
        led.put_source("2026-08-14", s)
        followers.append(s)

    cluster = [{"source_name": "AP", "published_at": "2026-08-13T14:00:00Z",
                "first_seen": "2026-08-13T14:30:00Z"}] + \
              [{"source_name": f["source_name"], "published_at": f["published_at"],
                "first_seen": f["first_seen"]} for f in followers]
    r = analyse_cluster(cluster, today="2026-08-14")
    assert r.verdict is Verdict.RECIRCULATION
    assert r.origin_date == "2026-08-13"

    db = tmp_path / "newsdesk.db"
    compile_db(led.root, db)
    con = sqlite3.connect(db)
    assert con.execute("select count(*) from sources").fetchone()[0] == 9
    assert con.execute("select count(*) from source_beats where beat='flock'").fetchone()[0] == 9

def test_dc_police_shape_is_a_date_conflict_hold(tmp_path):
    """The specimen edition's honest failure: an order circulating as current whose
    earliest matching source is a year old. Must hold, never publish."""
    cluster = [{"source_name": "WJLA", "published_at": "2025-08-14T12:00:00Z",
                "first_seen": "2026-08-14T06:00:00Z"},
               {"source_name": "Fox5", "published_at": "2025-08-15T09:00:00Z",
                "first_seen": "2026-08-14T06:02:00Z"},
               {"source_name": "NBC4", "published_at": "2026-08-14T07:00:00Z",
                "first_seen": "2026-08-14T07:10:00Z"}]
    r = analyse_cluster(cluster, today="2026-08-14")
    assert r.verdict is Verdict.DATE_CONFLICT
    assert r.gap_days >= 365
