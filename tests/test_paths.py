import pytest
from ledger.paths import (source_path, claim_path, beat_state_path, beat_history_path,
                          owns_path, PartitionError, assert_owns)

def test_source_path_is_dated_and_content_addressed():
    assert source_path("2026-08-14", "a"*64) == "sources/2026-08-14/" + "a"*64 + ".json"

def test_claim_path_is_under_its_beat():
    assert claim_path("hormuz", "hormuz-2026-08-14-003") == "claims/hormuz/hormuz-2026-08-14-003.json"

def test_beat_paths():
    assert beat_state_path("hormuz") == "beats/hormuz/state.json"
    assert beat_history_path("hormuz") == "beats/hormuz/history.jsonl"

def test_beat_agent_owns_only_its_own_prefixes():
    assert owns_path("beat:hormuz", "beats/hormuz/state.json")
    assert owns_path("beat:hormuz", "claims/hormuz/x.json")
    assert not owns_path("beat:hormuz", "beats/fed/state.json")
    assert not owns_path("beat:hormuz", "claims/fed/x.json")
    assert not owns_path("beat:hormuz", "editions/2026-08-14.json")

def test_editor_owns_shared_state_but_no_beat_prefix():
    assert owns_path("editor", "editions/2026-08-14.json")
    assert owns_path("editor", "questions/q1.json")
    assert owns_path("editor", "triggers/t1.json")
    assert owns_path("editor", "contradictions/c1.json")
    assert not owns_path("editor", "beats/hormuz/state.json")
    assert not owns_path("editor", "claims/hormuz/x.json")

def test_ingest_owns_only_sources():
    assert owns_path("ingest", "sources/2026-08-14/abc.json")
    assert not owns_path("ingest", "claims/hormuz/x.json")

def test_beat_id_prefix_is_not_confused_with_a_longer_id():
    assert not owns_path("beat:fed", "beats/federal-policing/state.json")

def test_assert_owns_raises_with_the_offending_path():
    with pytest.raises(PartitionError) as e:
        assert_owns("beat:hormuz", ["beats/hormuz/state.json", "beats/fed/state.json"])
    assert "beats/fed/state.json" in str(e.value)

def test_assert_owns_passes_for_legal_write_set():
    assert_owns("beat:hormuz", ["beats/hormuz/state.json", "claims/hormuz/a.json"])


# ── The digest is the editor's ──────────────────────────────────────────────

def test_the_editor_owns_the_digests():
    """The delta digest is an editorial artifact: it decides what goes in an
    issue and when one goes out. The partition rule blocked the first attempt
    to write one, which is the rule working — an unowned prefix is a bug, not a
    permission to be assumed."""
    from ledger.paths import owns_path
    assert owns_path("editor", "digests/2026-08-17.json")
    assert owns_path("editor", "digests/last_seen.json")


def test_a_beat_may_not_write_the_digest():
    """A beat writing itself into the issue would be a beat deciding its own
    prominence. The editor composes; beats supply."""
    from ledger.paths import owns_path
    assert not owns_path("beat:nm-records", "digests/2026-08-17.json")
    assert not owns_path("scout", "digests/2026-08-17.json")
    assert not owns_path("ingest", "digests/2026-08-17.json")
