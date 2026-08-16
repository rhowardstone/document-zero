"""The beat registry is the ledger, not a file someone typed.

v1 read the beat list from config/beats.yaml. A beat that emerged from the news
therefore did not exist as far as the renderer was concerned — and on
2026-08-17 exactly that happened: three articles passed the entailment gate,
were stored under beats/<slug>/articles/, and the front page rendered EMPTY,
because none of the three slugs appeared in a config file written weeks
earlier. Beats that can open by themselves must be discoverable by themselves.
"""
import json

from ledger.beats import Beat, beats_from_ledger


def make(tmp_path, slug, *, proposal_name=None, day="2026-08-17"):
    b = tmp_path / "beats" / slug
    (b / "articles").mkdir(parents=True)
    (b / "state.json").write_text(json.dumps({"beat": slug, "as_of": day}))
    if proposal_name:
        p = tmp_path / "proposals"
        p.mkdir(exist_ok=True)
        (p / f"{day}-{slug}.json").write_text(
            json.dumps({"name": proposal_name, "slug": slug, "opened": True}))
    return b


def test_a_beat_on_disk_is_in_the_registry(tmp_path):
    make(tmp_path, "us-iran-war-and-hormuz-blockade")
    assert [b.id for b in beats_from_ledger(tmp_path)] == \
        ["us-iran-war-and-hormuz-blockade"]


def test_the_proposal_supplies_the_display_name(tmp_path):
    """The scout named the story in prose; the slug is a lossy encoding of it."""
    make(tmp_path, "us-iran-war-and-hormuz-blockade",
         proposal_name="US-Iran war and Hormuz blockade")
    assert beats_from_ledger(tmp_path)[0].name == "US-Iran war and Hormuz blockade"


def test_a_beat_with_no_proposal_still_gets_a_readable_name(tmp_path):
    """Never render a raw slug at the reader. A missing proposal is a gap in
    our records, not a reason to print machine text on the page."""
    make(tmp_path, "indiana-record-flooding-august-2026")
    assert beats_from_ledger(tmp_path)[0].name == "Indiana record flooding august 2026"


def test_the_newest_proposal_wins_when_a_beat_was_named_twice(tmp_path):
    slug = "us-iran-war-and-hormuz-blockade"
    make(tmp_path, slug, proposal_name="Old name", day="2026-08-15")
    make_p = tmp_path / "proposals" / f"2026-08-17-{slug}.json"
    make_p.write_text(json.dumps({"name": "Newer name", "slug": slug}))
    assert beats_from_ledger(tmp_path)[0].name == "Newer name"


def test_beats_are_returned_in_a_stable_order(tmp_path):
    for s in ("zulu-story", "alpha-story", "mike-story"):
        make(tmp_path, s)
    ids = [b.id for b in beats_from_ledger(tmp_path)]
    assert ids == sorted(ids)


def test_an_empty_ledger_yields_no_beats_rather_than_raising(tmp_path):
    assert beats_from_ledger(tmp_path) == []
    (tmp_path / "beats").mkdir()
    assert beats_from_ledger(tmp_path) == []


def test_a_stray_file_among_the_beat_directories_is_ignored(tmp_path):
    make(tmp_path, "real-story")
    (tmp_path / "beats" / ".DS_Store").write_text("junk")
    assert [b.id for b in beats_from_ledger(tmp_path)] == ["real-story"]


def test_a_malformed_proposal_does_not_lose_the_beat(tmp_path):
    """A beat with real articles must render even if its metadata is corrupt.
    Losing the story to protect the name is the wrong trade."""
    slug = "real-story"
    make(tmp_path, slug)
    (tmp_path / "proposals").mkdir(exist_ok=True)
    (tmp_path / "proposals" / f"2026-08-17-{slug}.json").write_text("{not json")
    out = beats_from_ledger(tmp_path)
    assert [b.id for b in out] == [slug] and out[0].name == "Real story"


def test_registry_entries_are_beats(tmp_path):
    make(tmp_path, "real-story")
    assert isinstance(beats_from_ledger(tmp_path)[0], Beat)
