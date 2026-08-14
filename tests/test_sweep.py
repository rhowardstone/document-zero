import json, pytest
from ledger.sweep import run_sweep, SweepPlan, plan_sweep

SRC = lambda sha, beat: {"sha256": sha, "url": f"https://x/{sha}", "title": "T",
    "snippet": "grind to a near standstill", "source_name": "AP", "source_type": "news",
    "published_at": "2026-08-14T09:00:00Z", "first_seen": "2026-08-14T09:05:00Z",
    "candidate_beats": [{"beat": beat, "score": 0.4}]}

SOURCES = [SRC("a"*64, "hormuz"), SRC("b"*64, "hormuz"), SRC("c"*64, "fed")]

def test_plan_routes_sources_to_their_assigned_beats():
    p = plan_sweep(SOURCES, beat_ids=["hormuz", "fed", "wells"], policy={})
    assert set(p.by_beat) == {"hormuz", "fed"}
    assert len(p.by_beat["hormuz"]) == 2

def test_plan_skips_beats_with_no_new_sources():
    p = plan_sweep(SOURCES, beat_ids=["hormuz", "fed", "wells"], policy={})
    assert "wells" not in p.by_beat
    assert p.skipped == ["wells"]

def test_plan_caps_sources_per_beat_and_carries_the_overflow():
    many = [SRC(f"{i:064d}", "hormuz") for i in range(10)]
    p = plan_sweep(many, beat_ids=["hormuz"],
                   policy={"sweep": {"max_sources_per_beat_per_run": 4}})
    assert len(p.by_beat["hormuz"]) == 4
    assert p.overflow["hormuz"] == 6

def test_plan_is_oldest_first_so_nothing_starves():
    a = SRC("a"*64, "hormuz"); a["published_at"] = "2026-08-14T12:00:00Z"
    b = SRC("b"*64, "hormuz"); b["published_at"] = "2026-08-14T01:00:00Z"
    p = plan_sweep([a, b], beat_ids=["hormuz"],
                   policy={"sweep": {"max_sources_per_beat_per_run": 1}})
    assert p.by_beat["hormuz"][0]["sha256"] == "b"*64

def test_a_source_matching_two_beats_is_handed_to_both():
    s = SRC("a"*64, "hormuz"); s["candidate_beats"].append({"beat": "prices", "score": 0.2})
    p = plan_sweep([s], beat_ids=["hormuz", "prices"], policy={})
    assert set(p.by_beat) == {"hormuz", "prices"}

# --- the claim that concurrency is a wall-clock choice, not a correctness one ---
def _fake_agent_factory(log):
    def factory(beat):
        class A:
            def run(self, srcs):
                log.append((beat, len(srcs)))
                from ledger.agent import AgentResult
                from ledger.diff import diff_state
                return AgentResult(beat=beat, claims_written=len(srcs),
                                   delta=diff_state(None, {"beat": beat, "as_of": "2026-08-14",
                                       "fields": [{"k": "a", "v": "1"}, {"k": "b", "v": "2"}]}))
        return A()
    return factory

def _summary(results):
    return sorted((r.beat, r.claims_written, r.delta.material_changes) for r in results)

def test_sequential_and_concurrent_sweeps_produce_identical_results():
    l1, l2 = [], []
    seq = run_sweep(plan_sweep(SOURCES, ["hormuz", "fed"], {}), _fake_agent_factory(l1),
                    concurrency=1)
    par = run_sweep(plan_sweep(SOURCES, ["hormuz", "fed"], {}), _fake_agent_factory(l2),
                    concurrency=4)
    assert _summary(seq) == _summary(par)

def test_results_are_returned_in_a_stable_order_regardless_of_concurrency():
    order1 = [r.beat for r in run_sweep(plan_sweep(SOURCES, ["hormuz", "fed"], {}),
                                        _fake_agent_factory([]), concurrency=4)]
    order2 = [r.beat for r in run_sweep(plan_sweep(SOURCES, ["hormuz", "fed"], {}),
                                        _fake_agent_factory([]), concurrency=1)]
    assert order1 == order2 == sorted(order1)

def test_one_failing_beat_does_not_abort_the_sweep():
    def factory(beat):
        class A:
            def run(self, srcs):
                if beat == "fed":
                    raise RuntimeError("boom")
                from ledger.agent import AgentResult
                return AgentResult(beat=beat, claims_written=1)
        return A()
    res = run_sweep(plan_sweep(SOURCES, ["hormuz", "fed"], {}), factory, concurrency=2)
    by = {r.beat: r for r in res}
    assert by["hormuz"].claims_written == 1
    assert by["fed"].error and "boom" in by["fed"].error
