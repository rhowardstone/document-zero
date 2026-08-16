"""The whole pipeline must stay runnable with no model, no key and no network.

That property is what let v1's tests survive a complete runtime change, and it
is what lets anyone watch this newsroom work before authorising it to run.
"""
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "stub_newsroom.py"


def run(out_dir, ledger=None):
    cmd = [sys.executable, str(SCRIPT), "--out", str(out_dir)]
    if ledger:
        cmd += ["--ledger", str(ledger)]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=180, cwd=ROOT)


def test_the_stub_newsroom_produces_a_dated_front_page(tmp_path):
    r = run(tmp_path)
    assert r.returncode == 0, r.stderr
    page = json.loads((tmp_path / "edition.json").read_text())
    assert page["date"], "every edition is dated"
    assert page["lead"], "the seeded ledger should support a lead story"
    assert page["lead"]["word_count"] >= 300
    for a in [page["lead"], *page["secondary"]]:
        assert a["dateline"] and a["published_at"], "no article without a date"


def test_an_empty_ledger_publishes_a_page_that_says_nothing_survived(tmp_path):
    """Silence and failure must never look the same."""
    empty = tmp_path / "empty-ledger"
    empty.mkdir()
    out = tmp_path / "out"
    r = run(out, ledger=empty)
    assert r.returncode == 0, r.stderr
    page = json.loads((out / "edition.json").read_text())
    assert page["lead"] is None
    assert page["nothing_survived"] is True
    assert page["date"]


def test_the_stub_newsroom_cannot_cost_anything(tmp_path):
    """Guard against a future edit reintroducing a paid path."""
    src = SCRIPT.read_text()
    assert "anthropic" not in src.lower()
    assert "ANTHROPIC_API_KEY" not in src
    assert "api_key" not in src.lower()


def test_the_stub_reporter_announces_that_it_is_not_a_model(tmp_path):
    """Stub output must never be mistaken for the real thing."""
    r = run(tmp_path)
    assert r.returncode == 0, r.stderr
    page = json.loads((tmp_path / "edition.json").read_text())
    assert "NOT a model" in page["lead"]["written_by"]


def test_every_published_paragraph_cites_claims(tmp_path):
    r = run(tmp_path)
    page = json.loads((tmp_path / "edition.json").read_text())
    for a in [page["lead"], *page["secondary"]]:
        for para in a["paragraphs"]:
            assert para["claims"], "prose the ledger cannot trace may not publish"
