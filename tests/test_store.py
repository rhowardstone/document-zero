import pytest
from ledger.store import Ledger
from ledger.paths import PartitionError

@pytest.fixture
def led(tmp_path): return Ledger(tmp_path)

SRC = {"sha256":"a"*64,"url":"https://x","title":"T","source_name":"E","source_type":"news",
       "published_at":"2026-08-14T03:00:00Z","first_seen":"2026-08-14T04:00:00Z","candidate_beats":[]}
ST = {"beat":"hormuz","as_of":"2026-08-14","fields":[{"k":"a","v":"1"},{"k":"b","v":"2"}]}

def test_write_and_read_source(led):
    p = led.put_source("2026-08-14", SRC)
    assert led.get_source("2026-08-14","a"*64) == SRC
    assert p in led.written

def test_sources_are_immutable(led):
    led.put_source("2026-08-14", SRC)
    with pytest.raises(FileExistsError):
        led.put_source("2026-08-14", dict(SRC, title="changed"))

def test_history_appends_and_preserves_order(led):
    led.append_history("hormuz", {"d":"2026-08-13","c":"first"})
    led.append_history("hormuz", {"d":"2026-08-14","c":"second"})
    assert [r["c"] for r in led.read_history("hormuz")] == ["first","second"]

def test_state_is_overwritten_not_appended(led):
    led.put_state("hormuz", dict(ST, as_of="2026-08-13"))
    led.put_state("hormuz", dict(ST, as_of="2026-08-14"))
    assert led.get_state("hormuz")["as_of"] == "2026-08-14"

def test_invalid_state_is_rejected_before_touching_disk(led):
    with pytest.raises(Exception):
        led.put_state("hormuz", {"beat":"hormuz","as_of":"2026-08-14","fields":[{"k":"a","v":"1"}]})
    assert led.get_state("hormuz") is None

def test_writer_partition_is_enforced(led):
    led.writer = "beat:hormuz"
    with pytest.raises(PartitionError):
        led.put_state("fed", {"beat":"fed","as_of":"2026-08-14","fields":[{"k":"a","v":"1"},{"k":"b","v":"2"}]})

def test_writer_partition_allows_own_beat(led):
    led.writer = "beat:hormuz"
    led.put_state("hormuz", ST)
    assert led.get_state("hormuz") is not None

def test_list_beats_and_sources(led):
    led.put_state("hormuz", ST)
    assert led.list_beats() == ["hormuz"]
