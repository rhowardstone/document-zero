"""The daily runner's decisions, tested without running a newsroom.

Most of scripts/daily.py is orchestration, but two judgements in it are policy
and both have bitten this project before:

  a beat with claims but no state is NOT ready for a reporter
  a beat whose agent failed is NOT a quiet beat
"""
import importlib.util
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ledger.store import Ledger  # noqa: E402

spec = importlib.util.spec_from_file_location("daily", ROOT / "scripts" / "daily.py")
daily = importlib.util.module_from_spec(spec)
spec.loader.exec_module(daily)


CLAIM = {"claim_text": "A thing happened.", "quote": "A thing happened",
         "source_type": "news", "source_url": "https://apnews.com/x",
         "confidence": 0.6, "confidence_justification": "news ceiling",
         "tier": "documented_fact", "extracted_by": "t", "extracted_at": "n"}


def seed(root, beat, claims=2, fields=2):
    led = Ledger(root, writer=f"beat:{beat}")
    for i in range(claims):
        led.put_claim({**CLAIM, "id": f"{beat}-{i}", "beat": beat})
    if fields:
        led.put_state(beat, {"beat": beat, "as_of": "2026-08-16", "fields": [
            {"k": f"Field {n}", "v": str(n), "since": "16 Aug",
             "claims": [f"{beat}-0"]} for n in range(fields)]})


def test_a_beat_with_claims_and_state_is_ready_to_write(tmp_path, monkeypatch):
    monkeypatch.setattr(daily, "LEDGER", tmp_path / "d")
    seed(tmp_path / "d", "ready")
    assert daily.open_beats("2026-08-16") == ["ready"]


def test_a_beat_with_claims_but_no_state_is_not_ready(tmp_path, monkeypatch):
    """Without state there is no delta, so there is nothing to report ON — only
    a pile of claims. That is the v1 failure mode, one layer down."""
    monkeypatch.setattr(daily, "LEDGER", tmp_path / "d")
    seed(tmp_path / "d", "stateless", fields=0)
    assert daily.open_beats("2026-08-16") == []


def test_a_beat_with_a_single_state_field_is_not_ready(tmp_path, monkeypatch):
    """Two changeable fields is the beat test. One is not a beat."""
    monkeypatch.setattr(daily, "LEDGER", tmp_path / "d")
    with pytest.raises(Exception):
        seed(tmp_path / "d", "thin", fields=1)


def test_an_empty_ledger_yields_no_beats(tmp_path, monkeypatch):
    monkeypatch.setattr(daily, "LEDGER", tmp_path / "empty")
    assert daily.open_beats("2026-08-16") == []


def test_beats_are_returned_in_a_stable_order(tmp_path, monkeypatch):
    """A front page that reorders itself for no reason makes every reader
    wonder what changed."""
    monkeypatch.setattr(daily, "LEDGER", tmp_path / "d")
    for b in ("zebra", "alpha", "middle"):
        seed(tmp_path / "d", b)
    assert daily.open_beats("2026-08-16") == ["alpha", "middle", "zebra"]


def test_the_runner_cannot_bill():
    src = (ROOT / "scripts" / "daily.py").read_text()
    assert "assert_subscription" in src, "must verify auth before the first agent"
    assert "import anthropic" not in src


def test_the_failure_policy_is_documented_where_someone_will_read_it():
    """Both of these were real bugs in v1: a failed agent rendering as a quiet
    beat, and a partial edition publishing as if complete."""
    # Normalise whitespace: a docstring assertion that depends on where the
    # line happens to wrap fails for reasons that have nothing to do with the
    # policy it is checking. This has now caught three tests in this project.
    import re
    doc = re.sub(r"\s+", " ", daily.__doc__ or "")
    assert "must never look like a still day" in doc
    assert "A partial edition is worse than a stale one" in doc
