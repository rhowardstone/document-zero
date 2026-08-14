"""Sweep orchestration: route sources to beats, run their agents, collect results.

Beats are independent by construction — the write-partition rule guarantees it — so
the sweep produces identical results at any concurrency. Width is a wall-clock
choice and never a correctness one, which means the whole system degrades
gracefully to fully sequential wherever agent concurrency is constrained.

Results are always returned in sorted beat order so an edition built from a
4-wide sweep is byte-identical to one built from a 1-wide sweep.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor

DEFAULT_MAX_PER_BEAT = 60


@dataclass
class SweepPlan:
    by_beat: dict = field(default_factory=dict)
    skipped: list = field(default_factory=list)
    overflow: dict = field(default_factory=dict)


def plan_sweep(sources, beat_ids, policy) -> SweepPlan:
    cap = int(((policy or {}).get("sweep") or {}).get(
        "max_sources_per_beat_per_run", DEFAULT_MAX_PER_BEAT))
    buckets: dict[str, list] = {}
    for s in sources:
        for cb in s.get("candidate_beats", []):
            b = cb.get("beat")
            if b in beat_ids:
                buckets.setdefault(b, []).append(s)

    plan = SweepPlan()
    for b in sorted(beat_ids):
        got = buckets.get(b)
        if not got:
            plan.skipped.append(b)
            continue
        # Oldest first, so a busy beat never starves its own backlog.
        got = sorted(got, key=lambda s: s.get("published_at") or "")
        if len(got) > cap:
            plan.overflow[b] = len(got) - cap
            got = got[:cap]
        plan.by_beat[b] = got
    return plan


def run_sweep(plan: SweepPlan, agent_factory, concurrency: int = 1):
    """Run one agent per beat that has new sources. Never aborts the sweep on a
    single beat's failure: a broken beat is a recorded error, not an outage."""
    beats = sorted(plan.by_beat)

    def one(beat):
        try:
            return agent_factory(beat).run(plan.by_beat[beat])
        except Exception as e:                    # noqa: BLE001 - isolation is the point
            from .agent import AgentResult
            return AgentResult(beat=beat, error=f"{type(e).__name__}: {e}")

    if concurrency <= 1:
        return [one(b) for b in beats]
    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        return list(ex.map(one, beats))          # map preserves input order
