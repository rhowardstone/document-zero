"""Merging a beat that opened twice under two names.

continuity.py stops NEW duplicates. These three pairs predate it and are on
disk:

    indiana-record-flooding            / indiana-record-flooding-august-2026
    democrats-2028-calendar-and-...    / democrats-2028-primary-calendar
    us-iran-war-and-hormuz-blockade    / us-iran-war-and-stalled-ceasefire-talks

Each is one story wearing two beats, which is the failure the whole persistent-
state premise rests on avoiding: neither copy accumulates the history, and both
are permanently on their first day.

Merging is destructive and cannot be undone by re-running the pipeline, so the
rules here are conservative:

  - Claims are never dropped. If both sides hold the same claim it appears
    once; if they disagree, both survive and the reader sees both.
  - The surviving state is the one with the later as_of. Guessing field-by-field
    would invent a state that neither beat ever actually had.
  - The merge is RECORDED. A beat that silently vanishes takes its URL with it,
    and anyone holding a link is owed an explanation rather than a 404.
"""
import json

from ledger.merge import apply, plan


def beat(root, slug, *, as_of, fields, claims=(), history=()):
    d = root / "beats" / slug
    (d / "articles").mkdir(parents=True)
    (d / "state.json").write_text(json.dumps(
        {"beat": slug, "as_of": as_of,
         "fields": [{"k": k, "v": v} for k, v in fields]}))
    if history:
        (d / "history.jsonl").write_text(
            "\n".join(json.dumps(h) for h in history) + "\n")
    c = root / "claims" / slug
    c.mkdir(parents=True)
    for i, text in enumerate(claims):
        (c / f"claim_{i:03d}.json").write_text(
            json.dumps({"id": f"{slug}_{i}", "claim_text": text}))
    return d


# ── Planning ────────────────────────────────────────────────────────────────

def test_the_beat_with_the_later_state_survives(tmp_path):
    beat(tmp_path, "old", as_of="2026-08-14", fields=[("a", "1")])
    beat(tmp_path, "new", as_of="2026-08-17", fields=[("a", "2")])
    p = plan(tmp_path, ["old", "new"])
    assert p.winner == "new" and p.losers == ["old"]


def test_a_tie_is_broken_by_the_beat_with_more_claims(tmp_path):
    """More claims means more of the story is on the record there."""
    beat(tmp_path, "thin", as_of="2026-08-17", fields=[("a", "1")], claims=["x"])
    beat(tmp_path, "full", as_of="2026-08-17", fields=[("a", "1")],
         claims=["x", "y", "z"])
    assert plan(tmp_path, ["thin", "full"]).winner == "full"


def test_a_single_beat_is_not_a_merge(tmp_path):
    beat(tmp_path, "only", as_of="2026-08-17", fields=[("a", "1")])
    assert plan(tmp_path, ["only"]).losers == []


# ── Applying ────────────────────────────────────────────────────────────────

def test_claims_from_both_sides_survive(tmp_path):
    beat(tmp_path, "old", as_of="2026-08-14", fields=[("a", "1")],
         claims=["the river crested", "seven are dead"])
    beat(tmp_path, "new", as_of="2026-08-17", fields=[("a", "2")],
         claims=["power is out"])
    apply(tmp_path, plan(tmp_path, ["old", "new"]))
    texts = {json.loads(f.read_text())["claim_text"]
             for f in (tmp_path / "claims" / "new").glob("*.json")}
    assert texts == {"the river crested", "seven are dead", "power is out"}


def test_an_identical_claim_is_not_duplicated(tmp_path):
    beat(tmp_path, "old", as_of="2026-08-14", fields=[("a", "1")], claims=["same"])
    beat(tmp_path, "new", as_of="2026-08-17", fields=[("a", "2")], claims=["same"])
    apply(tmp_path, plan(tmp_path, ["old", "new"]))
    assert len(list((tmp_path / "claims" / "new").glob("*.json"))) == 1


def test_the_loser_is_removed(tmp_path):
    beat(tmp_path, "old", as_of="2026-08-14", fields=[("a", "1")])
    beat(tmp_path, "new", as_of="2026-08-17", fields=[("a", "2")])
    apply(tmp_path, plan(tmp_path, ["old", "new"]))
    assert not (tmp_path / "beats" / "old").exists()
    assert not (tmp_path / "claims" / "old").exists()


def test_the_merge_is_recorded_so_a_dead_link_can_be_explained(tmp_path):
    beat(tmp_path, "old", as_of="2026-08-14", fields=[("a", "1")])
    beat(tmp_path, "new", as_of="2026-08-17", fields=[("a", "2")])
    apply(tmp_path, plan(tmp_path, ["old", "new"]))
    rec = json.loads((tmp_path / "merges" / "old.json").read_text())
    assert rec["merged_into"] == "new" and rec["beat"] == "old"


def test_history_from_both_sides_is_kept_in_order(tmp_path):
    beat(tmp_path, "old", as_of="2026-08-14", fields=[("a", "1")],
         history=[{"day": "2026-08-12", "e": "first"}])
    beat(tmp_path, "new", as_of="2026-08-17", fields=[("a", "2")],
         history=[{"day": "2026-08-16", "e": "second"}])
    apply(tmp_path, plan(tmp_path, ["old", "new"]))
    rows = [json.loads(l) for l in
            (tmp_path / "beats" / "new" / "history.jsonl").read_text().splitlines() if l.strip()]
    assert [r["e"] for r in rows] == ["first", "second"]


def test_the_winners_state_is_kept_whole(tmp_path):
    """Field-by-field merging would invent a state neither beat ever had."""
    beat(tmp_path, "old", as_of="2026-08-14", fields=[("a", "old"), ("gone", "x")])
    beat(tmp_path, "new", as_of="2026-08-17", fields=[("a", "new")])
    apply(tmp_path, plan(tmp_path, ["old", "new"]))
    st = json.loads((tmp_path / "beats" / "new" / "state.json").read_text())
    assert [f["k"] for f in st["fields"]] == ["a"]
    assert st["fields"][0]["v"] == "new"


def test_applying_an_empty_plan_changes_nothing(tmp_path):
    beat(tmp_path, "only", as_of="2026-08-17", fields=[("a", "1")])
    apply(tmp_path, plan(tmp_path, ["only"]))
    assert (tmp_path / "beats" / "only").exists()
