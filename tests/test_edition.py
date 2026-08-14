import pytest
from ledger.edition import assemble, Edition
from ledger.placement import Placement

def rec(rid, placement, score=1.0, reason=None, **kw):
    return dict(id=rid, placement=placement, score=score, reason=reason,
                title=f"title {rid}", beat="b", **kw)

def test_wire_items_are_ordered_by_score_descending():
    e = assemble([rec("a", Placement.WIRE, 1.0), rec("c", Placement.WIRE, 9.0),
                  rec("b", Placement.WIRE, 5.0)], day="2026-08-14", policy={})
    assert [r["id"] for r in e.wire] == ["c", "b", "a"]

def test_the_cap_truncates_the_wire_and_records_what_it_dropped():
    e = assemble([rec(str(i), Placement.WIRE, float(i)) for i in range(12)],
                 day="2026-08-14", policy={"publication": {"max_records_per_edition": 4}})
    assert len(e.wire) == 4
    assert e.counts["capped_out"] == 8, "silent truncation reads as 'we covered everything'"

def test_omissions_and_holds_are_separate_lanes():
    e = assemble([rec("a", Placement.WIRE), rec("b", Placement.OMISSION, reason="recirculation"),
                  rec("c", Placement.HOLD, reason="date_conflict")],
                 day="2026-08-14", policy={})
    assert len(e.wire) == 1 and len(e.omissions) == 1 and len(e.holds) == 1

def test_refused_items_are_counted_but_never_appear_in_any_lane():
    e = assemble([rec("a", Placement.REFUSED, reason="wrongdoing_by_private_individual")],
                 day="2026-08-14", policy={})
    assert e.counts["refused"] == 1
    body = e.wire + e.omissions + e.holds
    assert not body, "a refused record must not appear anywhere in the edition"

def test_refusal_reasons_are_published_in_aggregate():
    e = assemble([rec("a", Placement.REFUSED, reason="wrongdoing_by_private_individual"),
                  rec("b", Placement.REFUSED, reason="wrongdoing_by_private_individual"),
                  rec("c", Placement.REFUSED, reason="uncorroborated_criminal_conduct")],
                 day="2026-08-14", policy={})
    assert e.refusal_summary == {"wrongdoing_by_private_individual": 2,
                                 "uncorroborated_criminal_conduct": 1}

def test_dropped_items_are_counted_not_carried():
    e = assemble([rec("a", Placement.DROP)], day="2026-08-14", policy={})
    assert e.counts["dropped"] == 1 and not e.wire

def test_an_empty_day_produces_a_valid_edition():
    e = assemble([], day="2026-08-14", policy={})
    assert e.day == "2026-08-14" and e.is_empty and e.counts["wire"] == 0

def test_dry_run_marks_the_edition_unpublished():
    e = assemble([rec("a", Placement.WIRE)], day="2026-08-14",
                 policy={"publication": {"dry_run": True}})
    assert e.publish is False and e.publish_blocked_by == "dry_run"

def test_kill_switch_blocks_publication_but_the_edition_still_builds():
    e = assemble([rec("a", Placement.WIRE)], day="2026-08-14",
                 policy={"publication": {"kill_switch": True}})
    assert e.publish is False and e.publish_blocked_by == "kill_switch"
    assert len(e.wire) == 1, "ingestion and assembly continue; only publication stops"

def test_edition_serialises_to_json_safe_primitives():
    import json
    e = assemble([rec("a", Placement.WIRE), rec("b", Placement.HOLD, reason="date_conflict")],
                 day="2026-08-14", policy={})
    json.dumps(e.to_dict())
