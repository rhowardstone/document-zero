"""Tier 3. The editor: place, score, assemble, write.

The only writer of shared state, which is why it runs alone after the sweep.
It reads every beat's computed delta and decides where each lands. It does not
decide what changed — the diff already did that.
"""
from __future__ import annotations
from .placement import classify, PlacementInput, Placement
from .rank import score_item
from .recirculation import Verdict
from .edition import assemble
from . import paths as P

DEFAULT_CONSEQUENCE = 5


def build_records(results, clusters, policy, beat_meta) -> list:
    """One record per beat, plus one counted record per refusal."""
    records = []
    for r in results:
        meta = (beat_meta or {}).get(r.beat, {})

        # Refusals are per-claim and never appear in a lane. They are recorded so
        # the aggregate can publish: what the system will not say is part of the record.
        for gate in (r.refused or []):
            records.append({"id": f"{r.beat}:refused:{gate}", "beat": r.beat,
                            "placement": Placement.REFUSED, "reason": gate, "score": 0.0})

        # A beat whose agent failed is held, never silently dropped: an unexplained
        # absence is indistinguishable from a quiet day, and they are not the same.
        if r.error:
            records.append({"id": f"{r.beat}:error", "beat": r.beat,
                            "placement": Placement.HOLD,
                            "reason": f"agent_error: {r.error}", "score": 0.0})
            continue

        pi = PlacementInput(
            delta=r.delta,
            recirculation=(clusters or {}).get(r.beat, Verdict.FRESH),
            refused=None,
            single_root=bool(r.single_root),
            cascade_survived=(r.cascade_failures == 0 or r.claims_written > 0),
        )
        placed = classify(pi)

        s = score_item({
            "material_changes": getattr(r.delta, "material_changes", 0),
            "beat_was_quiet": meta.get("was_quiet", False),
            "derived": meta.get("derived", False),
            "consequence": meta.get("consequence", DEFAULT_CONSEQUENCE),
            "evidence": getattr(r, "mean_confidence", None) or meta.get("evidence", 0.6),
            "coverage": meta.get("coverage", DEFAULT_CONSEQUENCE),
        })
        # THE DELTA IS THE PRODUCT. It was computed, used for ranking, then
        # dropped — so the page could only show claims, never the change itself.
        d = r.delta
        records.append({
            "changes": [{"k": c.k, "from": c.old, "to": c.new}
                        for c in getattr(d, "changed", ())],
            "added": [{"k": a.k, "v": a.v} for a in getattr(d, "added", ())],
            "removed": [{"k": x.k, "v": x.v} for x in getattr(d, "removed", ())],
            "unchanged": getattr(d, "unchanged", 0),
            "id": r.beat, "beat": r.beat, "placement": placed.placement,
            "reason": placed.reason, "score": s.total, "components": s.components,
            "distortion": None if s.distortion == float("inf") else s.distortion,
            "undercovered": s.undercovered,
            "material_changes": getattr(r.delta, "material_changes", 0),
            "claims": r.claims_written,
            "injection_attempts": r.injection_attempts,
            "rejected_claims": len(getattr(r, "rejected", []) or []),
        })
    return records


def run_editor(ledger, results, day, policy, clusters=None, beat_meta=None,
               policy_revision=None):
    recs = build_records(results, clusters, policy, beat_meta)
    ed = assemble(recs, day=day, policy=policy, policy_revision=policy_revision)
    ledger._write_json(P.edition_path(day), ed.to_dict())
    return ed
