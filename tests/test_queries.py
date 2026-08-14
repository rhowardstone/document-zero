"""The query surface answers questions; it does not merely index the data.

The views most worth testing are the ones that expose weakness, because those
are the ones a naive consumer skips and a careful one leads with.
"""
import pytest

from ledger.queries import build_queries, query_index


def rec(rid, beats, sources, stamp="documented", corr=None):
    return {"id": rid, "kind": "wire", "title": f"claim {rid}", "stamp": stamp,
            "beats": beats, "corroboration": corr if corr is not None else len({s["n"] for s in sources}),
            "sources": sources}


def src(host, url=None, t="news", c="0.6"):
    return {"n": host, "u": url or f"https://{host}/a", "t": t, "c": c}


@pytest.fixture
def data():
    return {
        "edition": {"date": "2026-08-14", "counts": {"wire": 3, "holds": 1}},
        "beats": [
            {"id": "b1", "name": "Beat One", "status": "moved", "unknown": ["nothing filed"],
             "history": [{"d": "2026-08-05", "c": "suit filed", "s": "3 sources"},
                         {"d": "2019-07-23", "c": "stand-down", "s": "1 source"}]},
            {"id": "b2", "name": "Beat Two", "status": "unresolved", "unknown": ["Held: x"],
             "history": [{"d": "2026-08-01", "c": "held", "s": ""}]},
            {"id": "b3", "name": "Beat Three", "status": "quiet", "unknown": [], "history": []},
        ],
        "items": [
            rec("r1", ["b1"], [src("nbcnews.com")]),
            rec("r2", ["b1", "b2"], [src("abq.com", "https://abq.com/x"),
                                      src("pbs.org", "https://abq.com/x")], stamp="open"),
            rec("r3", ["b2"], [src("abq.com", "https://abq.com/x")]),
            {"id": "om", "kind": "omission", "beats": ["b3"], "sources": [], "corroboration": 0},
        ],
        "triggers": [{"id": "t1", "sort": "2026-09-05"}],
        "questions": [{"id": "q1", "q": "who?"}],
        "contradictions": [{"id": "c1", "a": "x", "b": "not x"}],
    }


def test_uncorroborated_finds_single_publisher_claims(data):
    q = build_queries(data)["uncorroborated"]
    assert {r["id"] for r in q["results"]} == {"r1", "r3"}
    assert "publisher hosts, not URLs" in q["method"]


def test_omissions_are_not_counted_as_published_claims(data):
    """kind=omission is a record ABOUT non-publication, not a published claim."""
    for name in ("uncorroborated", "tier-documented", "tier-open"):
        assert all(r["id"] != "om" for r in build_queries(data)[name]["results"])


def test_single_publisher_beats_names_the_publisher():
    d = {"edition": {}, "items": [
            rec("r1", ["solo"], [src("onlyoutlet.com")]),
            rec("r2", ["solo"], [src("onlyoutlet.com", "https://onlyoutlet.com/b")]),
            rec("r3", ["broad"], [src("a.com"), src("b.com")])],
         "beats": [{"id": "solo", "name": "Solo", "status": "moved", "history": []},
                   {"id": "broad", "name": "Broad", "status": "moved", "history": []},
                   {"id": "empty", "name": "Empty", "status": "quiet", "history": []}]}
    got = {r["beat"]: r["only_publisher"] for r in build_queries(d)["single-publisher-beats"]["results"]}
    assert got == {"solo": "onlyoutlet.com"}, got
    assert "empty" not in got, "a beat with no published records has no publisher"


def test_unknowns_are_surfaced_as_a_first_class_view(data):
    q = build_queries(data)["unknowns"]
    assert {r["beat"] for r in q["results"]} == {"b1", "b2"}


def test_cross_beat_sources_group_by_url_not_by_publisher(data):
    """Two publisher names on one URL is one source, not two."""
    q = build_queries(data)["cross-beat-sources"]
    assert [r["url"] for r in q["results"]] == ["https://abq.com/x"]
    assert q["results"][0]["beats"] == ["b1", "b2"]


def test_the_timeline_is_chronological_across_every_beat(data):
    q = build_queries(data)["timeline"]
    assert [r["date"] for r in q["results"]] == ["2019-07-23", "2026-08-01", "2026-08-05"]
    assert q["results"][0]["beat"] == "b1"


def test_withheld_carries_the_reason_not_just_the_status(data):
    q = build_queries(data)["withheld"]
    assert q["results"] == [{"beat": "b2", "name": "Beat Two", "status": "unresolved",
                             "reason": "Held: x"}]
    assert q["lane_counts"]["holds"] == 1


def test_source_types_show_what_the_ceiling_follows_from(data):
    q = build_queries(data)["source-types"]
    assert {r["source_type"]: r["sources"] for r in q["results"]} == {"news": 4}


def test_every_view_states_its_method(data):
    for name, v in build_queries(data).items():
        assert v["method"].strip(), name
        assert v["question"].strip(), name
        assert v["count"] == len(v["results"]), name


def test_the_catalogue_points_at_every_view(data):
    q = build_queries(data)
    idx = query_index(q, base="https://x/")
    assert {e["query"] for e in idx["queries"]} == set(q)
    assert all(e["url"].startswith("https://x/api/query/") for e in idx["queries"])
    assert "sql" in idx and "newsdesk.db" in idx["sql"]


def test_the_catalogue_says_which_views_expose_weakness(data):
    idx = query_index(build_queries(data))
    assert "weakness" in idx["caution"].lower()


def test_a_single_primary_document_is_not_counted_as_thin_sourcing():
    """A court filing is not "uncorroborated" the way a single-sourced news
    story is: it is not relaying a claim, it IS the record."""
    d = {"edition": {}, "beats": [], "items": [
        rec("news1", ["b"], [src("outlet.com", t="news")]),
        rec("doc1", ["b"], [src("courtlistener.com", t="documentation")]),
        rec("both", ["b"], [src("a.com", t="news"), src("b.com", t="news")], corr=2)]}
    q = build_queries(d)["uncorroborated"]
    assert [r["id"] for r in q["results"]] == ["news1"]
    assert [r["id"] for r in q["single_primary_document"]] == ["doc1"]
    assert q["count"] == 1 and q["single_primary_document_count"] == 1
