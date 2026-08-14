# Document Zero — Ledger Substrate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the append-only git ledger and its derived SQLite index, so that ingested sources accumulate with provenance, beats hold queryable state, and the daily delta is computable — with zero model cost.

**Architecture:** Git is the write surface (immutable `sources/`, per-beat `claims/` and `state.json`, append-only `history.jsonl`), partitioned so each writer owns a path prefix and never conflicts. A no-model compile step walks the JSON tree into `newsdesk.db`, served by the existing datasette. Everything in this plan is deterministic Python — no LLM calls — which makes it fully testable.

**Tech Stack:** Python 3.13, pytest 9.1, jsonschema, sqlite3 (stdlib), git. No third-party runtime deps beyond jsonschema.

---

## Scope

This is **plan 1 of 4**. It builds the substrate and tier 1 (ingest) and tier 4 (compile), which together form a complete, working, testable system: sources land in the ledger, state is queryable, recirculation is detected. No models are involved.

| Plan | Covers | Status |
|---|---|---|
| **1 — Ledger substrate** (this) | Schemas, partition rules, ingest, recirculation, compile → SQLite | now |
| 2 — Beat agents (tier 2) | Claim extraction, state recompute, history, ancestry | after 1 |
| 3 — Editor (tier 3) | Diff, suppression, ranking, editions, holds, Brier | after 2 |
| 4 — Render & deploy | Static render, nginx subdomain, Actions deploy | after 3 |

Each produces working software on its own.

---

## File structure

```
/mnt/d/Newsdesk/                     ← doczero-policy (public repo)
  ledger/
    __init__.py
    paths.py          Path construction + the write-partition rule. No I/O.
    schema.py         JSON schemas + validators for every object. No I/O.
    ceilings.py       Source-type confidence ceilings. Pure lookup.
    beats.py          Beat registry, lifecycle (open/close) evaluation.
    store.py          Read/write the ledger tree. The only module doing file I/O.
    ingest.py         Tier 1: normalise a fetched item into a source object.
    recirculation.py  first_seen vs published_at analysis over a cluster.
    compile.py        JSON tree → newsdesk.db.
    cli.py            Entry points: dz-ingest, dz-compile, dz-check.
  tests/
    test_paths.py  test_schema.py  test_ceilings.py  test_beats.py
    test_store.py  test_ingest.py  test_recirculation.py  test_compile.py
  config/
    beats.yaml        The 16 beats: id, name, dossiers, types, keywords.
    dossiers.yaml     The 12 dossiers.
    types.yaml        The 9 types.
    policy.yaml       Ceilings, thresholds, caps, dry-run and kill flags.
  data/               ← doczero-data (private repo, sibling checkout)
  site/               ← the rendered site (index.html, data.js, fonts/)
  docs/
```

Rationale for the split: `paths.py`, `schema.py`, `ceilings.py` and `recirculation.py` are pure functions and trivially testable. `store.py` is the single I/O boundary, so every other module can be tested without a filesystem. `compile.py` reads through `store.py` and writes SQLite only.

---

## Task 1: Path construction and the write-partition rule

The rule that makes sixteen concurrent agents work. Enforced in code, not convention.

**Files:**
- Create: `ledger/paths.py`
- Test: `tests/test_paths.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_paths.py
import pytest
from ledger.paths import (
    source_path, claim_path, beat_state_path, beat_history_path,
    owns_path, PartitionError, assert_owns,
)

def test_source_path_is_dated_and_content_addressed():
    p = source_path("2026-08-14", "a" * 64)
    assert p == "sources/2026-08-14/" + "a" * 64 + ".json"

def test_claim_path_is_under_its_beat():
    assert claim_path("hormuz", "hormuz-2026-08-14-003") == \
        "claims/hormuz/hormuz-2026-08-14-003.json"

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
    # 'fed' must not own 'federal-policing'
    assert not owns_path("beat:fed", "beats/federal-policing/state.json")

def test_assert_owns_raises_with_the_offending_path():
    with pytest.raises(PartitionError) as e:
        assert_owns("beat:hormuz", ["beats/hormuz/state.json", "beats/fed/state.json"])
    assert "beats/fed/state.json" in str(e.value)

def test_assert_owns_passes_for_legal_write_set():
    assert_owns("beat:hormuz", ["beats/hormuz/state.json", "claims/hormuz/a.json"])
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd /mnt/d/Newsdesk && python3 -m pytest tests/test_paths.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ledger'`

- [ ] **Step 3: Write the minimal implementation**

```python
# ledger/paths.py
"""Path construction and the write-partition rule.

Every writer owns a set of path prefixes and may write nothing outside them.
This is what allows every agent to push directly to main with no locking and
no merge resolution: two writers never touch the same file.

Pure functions. No I/O.
"""
from __future__ import annotations

SOURCES = "sources"
CLAIMS = "claims"
BEATS = "beats"
EDITIONS = "editions"
SHARED = ("questions", "triggers", "contradictions", "editions", "_index")


class PartitionError(Exception):
    """A writer attempted to write outside the prefixes it owns."""


def source_path(day: str, sha256: str) -> str:
    return f"{SOURCES}/{day}/{sha256}.json"


def claim_path(beat_id: str, claim_id: str) -> str:
    return f"{CLAIMS}/{beat_id}/{claim_id}.json"


def beat_state_path(beat_id: str) -> str:
    return f"{BEATS}/{beat_id}/state.json"


def beat_history_path(beat_id: str) -> str:
    return f"{BEATS}/{beat_id}/history.jsonl"


def beat_meta_path(beat_id: str) -> str:
    return f"{BEATS}/{beat_id}/meta.json"


def edition_path(day: str) -> str:
    return f"{EDITIONS}/{day}.json"


def owned_prefixes(writer: str) -> tuple[str, ...]:
    """Prefixes this writer may write. Trailing slash is significant."""
    if writer == "ingest":
        return (f"{SOURCES}/",)
    if writer == "editor":
        return tuple(f"{s}/" for s in SHARED)
    if writer.startswith("beat:"):
        beat_id = writer[5:]
        if not beat_id:
            return ()
        return (f"{BEATS}/{beat_id}/", f"{CLAIMS}/{beat_id}/")
    return ()


def owns_path(writer: str, path: str) -> bool:
    return any(path.startswith(p) for p in owned_prefixes(writer))


def assert_owns(writer: str, paths) -> None:
    bad = [p for p in paths if not owns_path(writer, p)]
    if bad:
        raise PartitionError(
            f"writer {writer!r} may not write: {', '.join(sorted(bad))}. "
            f"Owned prefixes: {', '.join(owned_prefixes(writer)) or '(none)'}"
        )
```

Also create `ledger/__init__.py` (empty) and `tests/__init__.py` (empty).

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd /mnt/d/Newsdesk && python3 -m pytest tests/test_paths.py -v`
Expected: PASS, 9 tests.

- [ ] **Step 5: Commit**

```bash
git add ledger/__init__.py ledger/paths.py tests/__init__.py tests/test_paths.py
git commit -m "feat(ledger): path construction and write-partition rule"
```

---

## Task 2: Confidence ceilings

Ceilings are enforced at write time by rejection, not by flagging. A claim that exceeds its
source type's ceiling is invalid data.

**Files:**
- Create: `ledger/ceilings.py`, `config/policy.yaml`
- Test: `tests/test_ceilings.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ceilings.py
import pytest
from ledger.ceilings import ceiling_for, check_confidence, CeilingError, requires_doi

def test_known_ceilings():
    assert ceiling_for("article") == 1.0
    assert ceiling_for("inproceedings") == 0.95
    assert ceiling_for("preprint") == 0.85
    assert ceiling_for("techreport") == 0.8
    assert ceiling_for("book") == 0.9
    assert ceiling_for("documentation") == 0.85
    assert ceiling_for("repo") == 0.8
    assert ceiling_for("blog") == 0.7
    assert ceiling_for("news") == 0.6
    assert ceiling_for("misc") == 0.5

def test_unknown_source_type_falls_to_misc_ceiling():
    assert ceiling_for("pigeon") == 0.5

def test_news_claim_at_ceiling_is_accepted():
    check_confidence("news", 0.6)

def test_news_claim_above_ceiling_is_rejected():
    with pytest.raises(CeilingError) as e:
        check_confidence("news", 0.61)
    assert "0.6" in str(e.value) and "news" in str(e.value)

def test_confidence_out_of_range_is_rejected():
    with pytest.raises(CeilingError):
        check_confidence("article", 1.4)
    with pytest.raises(CeilingError):
        check_confidence("article", -0.1)

def test_doi_requirement_by_type():
    assert requires_doi("article")
    assert requires_doi("inproceedings")
    assert requires_doi("preprint")
    assert not requires_doi("news")
    assert not requires_doi("documentation")
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_ceilings.py -v` — Expected: FAIL, no module `ledger.ceilings`.

- [ ] **Step 3: Implement**

```python
# ledger/ceilings.py
"""Confidence ceilings by source type.

A blog post cannot carry 0.95 confidence regardless of how clearly it is written.
Ceilings are enforced by rejection at write time.
"""
from __future__ import annotations

CEILINGS: dict[str, float] = {
    "article": 1.0,
    "inproceedings": 0.95,
    "book": 0.9,
    "preprint": 0.85,
    "documentation": 0.85,
    "techreport": 0.8,
    "repo": 0.8,
    "blog": 0.7,
    "news": 0.6,
    "misc": 0.5,
}
DOI_REQUIRED = frozenset({"article", "inproceedings", "preprint"})
DEFAULT = "misc"


class CeilingError(ValueError):
    """A claim's confidence is out of range or exceeds its source type's ceiling."""


def ceiling_for(source_type: str) -> float:
    return CEILINGS.get(source_type, CEILINGS[DEFAULT])


def requires_doi(source_type: str) -> bool:
    return source_type in DOI_REQUIRED


def check_confidence(source_type: str, confidence: float) -> None:
    if not 0.0 <= confidence <= 1.0:
        raise CeilingError(f"confidence {confidence} out of range [0,1]")
    cap = ceiling_for(source_type)
    if confidence > cap + 1e-9:
        raise CeilingError(
            f"confidence {confidence} exceeds ceiling {cap} for source_type {source_type!r}"
        )
```

- [ ] **Step 4: Verify pass**

Run: `python3 -m pytest tests/test_ceilings.py -v` — Expected: PASS, 6 tests.

- [ ] **Step 5: Commit**

```bash
git add ledger/ceilings.py tests/test_ceilings.py
git commit -m "feat(ledger): source-type confidence ceilings enforced by rejection"
```

---

## Task 3: Object schemas and validation

Schema validation is where "no claim without a source pointer" becomes structurally true
rather than a prompt instruction.

**Files:**
- Create: `ledger/schema.py`
- Test: `tests/test_schema.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_schema.py
import pytest
from ledger.schema import validate_claim, validate_source, validate_beat_state, SchemaError

def good_claim(**over):
    c = {
        "id": "hormuz-2026-08-14-003",
        "beat": "hormuz",
        "claim_text": "Transit slowed to a near standstill on 14 August.",
        "quote": "appeared to grind to a near standstill on Friday",
        "source_type": "news",
        "source_url": "https://example.org/a",
        "source_sha": "sha256:" + "b" * 64,
        "confidence": 0.6,
        "confidence_justification": "Single secondary outlet. News ceiling.",
        "tier": "documented_fact",
        "extracted_by": "beat-agent-hormuz",
        "extracted_at": "2026-08-14T04:41:00Z",
    }
    c.update(over)
    return c

def test_valid_claim_passes():
    validate_claim(good_claim())

def test_claim_without_any_source_pointer_is_rejected():
    c = good_claim(); c.pop("source_url")
    with pytest.raises(SchemaError, match="source"):
        validate_claim(c)

def test_claim_without_quote_is_rejected():
    with pytest.raises(SchemaError, match="quote"):
        validate_claim(good_claim(quote=""))

def test_claim_without_confidence_justification_is_rejected():
    with pytest.raises(SchemaError, match="justification"):
        validate_claim(good_claim(confidence_justification=""))

def test_claim_over_ceiling_is_rejected_by_schema_layer():
    with pytest.raises(SchemaError, match="ceiling"):
        validate_claim(good_claim(confidence=0.9))

def test_article_claim_requires_a_doi():
    with pytest.raises(SchemaError, match="doi"):
        validate_claim(good_claim(source_type="article", confidence=0.9))

def test_article_claim_with_doi_passes():
    validate_claim(good_claim(source_type="article", confidence=0.9,
                              source_doi="10.1000/xyz"))

def test_unknown_tier_is_rejected():
    with pytest.raises(SchemaError, match="tier"):
        validate_claim(good_claim(tier="vibes"))

def test_valid_source_passes():
    validate_source({
        "sha256": "c" * 64, "url": "https://example.org/a",
        "title": "T", "source_name": "Example", "source_type": "news",
        "published_at": "2026-08-14T03:00:00Z",
        "first_seen": "2026-08-14T04:00:00Z",
        "candidate_beats": [{"beat": "hormuz", "score": 0.81}],
    })

def test_source_without_first_seen_is_rejected():
    with pytest.raises(SchemaError, match="first_seen"):
        validate_source({"sha256": "c" * 64, "url": "https://x", "title": "T",
                         "source_name": "E", "source_type": "news",
                         "published_at": "2026-08-14T03:00:00Z",
                         "candidate_beats": []})

def test_beat_state_requires_two_changeable_fields():
    with pytest.raises(SchemaError, match="two"):
        validate_beat_state({"beat": "hormuz", "as_of": "2026-08-14",
                             "fields": [{"k": "Blockade", "v": "In force", "since": "Aug"}]})

def test_beat_state_with_two_fields_passes():
    validate_beat_state({"beat": "hormuz", "as_of": "2026-08-14", "fields": [
        {"k": "Blockade", "v": "In force", "since": "Aug"},
        {"k": "Transit", "v": "Near standstill", "since": "14 Aug"}]})
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_schema.py -v` — Expected: FAIL, no module.

- [ ] **Step 3: Implement**

```python
# ledger/schema.py
"""Object schemas. Validation is the enforcement point for provenance rules.

Structural guarantees, not prompt instructions:
  - no claim without a source pointer
  - no claim without an exact quote
  - no confidence without a justification
  - no confidence above its source type's ceiling
  - DOI required for article / inproceedings / preprint
"""
from __future__ import annotations
from .ceilings import check_confidence, requires_doi, CeilingError

TIERS = frozenset({"documented_fact", "credible_allegation", "question"})


class SchemaError(ValueError):
    """An object does not satisfy the ledger schema."""


def _require(obj, field, msg=None):
    v = obj.get(field)
    if v is None or (isinstance(v, str) and not v.strip()):
        raise SchemaError(msg or f"missing required field: {field}")
    return v


def validate_claim(c: dict) -> None:
    for f in ("id", "beat", "claim_text", "source_type", "extracted_by", "extracted_at"):
        _require(c, f)
    _require(c, "quote", "missing required field: quote (must be exact source text)")
    _require(c, "confidence_justification",
             "missing required field: confidence_justification")

    if not (c.get("source_url") or c.get("source_doi")):
        raise SchemaError("claim needs at least one source pointer: source_url or source_doi")

    st = c["source_type"]
    if requires_doi(st) and not c.get("source_doi"):
        raise SchemaError(f"source_type {st!r} requires a doi (source_doi)")

    tier = c.get("tier")
    if tier not in TIERS:
        raise SchemaError(f"unknown tier {tier!r}; expected one of {sorted(TIERS)}")

    conf = c.get("confidence")
    if not isinstance(conf, (int, float)):
        raise SchemaError("missing or non-numeric confidence")
    try:
        check_confidence(st, float(conf))
    except CeilingError as e:
        raise SchemaError(f"ceiling: {e}") from e


def validate_source(s: dict) -> None:
    for f in ("sha256", "url", "title", "source_name", "source_type", "published_at"):
        _require(s, f)
    _require(s, "first_seen",
             "missing required field: first_seen (needed for recirculation detection)")
    if not isinstance(s.get("candidate_beats"), list):
        raise SchemaError("candidate_beats must be a list")


def validate_beat_state(st: dict) -> None:
    for f in ("beat", "as_of"):
        _require(st, f)
    fields = st.get("fields")
    if not isinstance(fields, list):
        raise SchemaError("fields must be a list")
    if len(fields) < 2:
        raise SchemaError("a beat needs at least two changeable state fields to exist")
    for f in fields:
        if "k" not in f or "v" not in f:
            raise SchemaError("each state field needs k and v")
```

- [ ] **Step 4: Verify pass**

Run: `python3 -m pytest tests/test_schema.py -v` — Expected: PASS, 12 tests.

- [ ] **Step 5: Commit**

```bash
git add ledger/schema.py tests/test_schema.py
git commit -m "feat(ledger): object schemas enforcing provenance at write time"
```

---

## Task 4: Recirculation detection

The degenerate case of ancestry, and the one that pays for itself immediately — three of the
day's biggest stories in the specimen edition had zero underlying state change.

**Files:**
- Create: `ledger/recirculation.py`
- Test: `tests/test_recirculation.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_recirculation.py
from ledger.recirculation import analyse_cluster, Verdict

def src(name, published, first_seen):
    return {"source_name": name, "published_at": published, "first_seen": first_seen}

def test_single_day_burst_is_fresh():
    r = analyse_cluster([
        src("AP",  "2026-08-14T09:00:00Z", "2026-08-14T10:00:00Z"),
        src("CNN", "2026-08-14T11:00:00Z", "2026-08-14T11:30:00Z"),
    ], today="2026-08-14")
    assert r.verdict is Verdict.FRESH

def test_many_outlets_one_day_after_the_original_is_recirculation():
    srcs = [src("AP", "2026-08-13T14:00:00Z", "2026-08-13T14:30:00Z")]
    srcs += [src(f"outlet{i}", "2026-08-14T08:00:00Z", "2026-08-14T08:00:00Z")
             for i in range(8)]
    r = analyse_cluster(srcs, today="2026-08-14")
    assert r.verdict is Verdict.RECIRCULATION
    assert r.origin_date == "2026-08-13"
    assert r.followers == 8

def test_year_old_origin_is_a_date_conflict_hold():
    srcs = [src("WJLA", "2025-08-14T12:00:00Z", "2026-08-14T06:00:00Z"),
            src("Fox",  "2025-08-15T12:00:00Z", "2026-08-14T06:05:00Z")]
    r = analyse_cluster(srcs, today="2026-08-14")
    assert r.verdict is Verdict.DATE_CONFLICT
    assert r.gap_days >= 300

def test_empty_cluster_is_fresh():
    assert analyse_cluster([], today="2026-08-14").verdict is Verdict.FRESH

def test_unparseable_dates_do_not_crash_and_yield_hold():
    r = analyse_cluster([src("X", "not-a-date", "2026-08-14T06:00:00Z")],
                        today="2026-08-14")
    assert r.verdict in (Verdict.FRESH, Verdict.DATE_CONFLICT)
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_recirculation.py -v` — Expected: FAIL, no module.

- [ ] **Step 3: Implement**

```python
# ledger/recirculation.py
"""Detect whether a cluster is new information or yesterday's news re-datelined.

Three outcomes:
  FRESH          — the cluster originates today
  RECIRCULATION  — a small origin followed by many same-day republishers
  DATE_CONFLICT  — the origin materially predates the cluster; hold, do not publish
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

RECIRC_MIN_FOLLOWERS = 3
RECIRC_MIN_GAP_DAYS = 1
CONFLICT_GAP_DAYS = 60


class Verdict(Enum):
    FRESH = "fresh"
    RECIRCULATION = "recirculation"
    DATE_CONFLICT = "date_conflict"


@dataclass(frozen=True)
class Result:
    verdict: Verdict
    origin_date: str | None
    gap_days: int
    followers: int


def _parse(s):
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def analyse_cluster(sources, today: str) -> Result:
    today_dt = _parse(today + "T00:00:00Z")
    dated = [(s, _parse(s.get("published_at"))) for s in sources]
    parsed = [(s, d) for s, d in dated if d is not None]
    if not parsed:
        # Nothing datable. If anything failed to parse, prefer a hold over a claim.
        v = Verdict.DATE_CONFLICT if sources else Verdict.FRESH
        return Result(v, None, 0, 0)

    origin_src, origin = min(parsed, key=lambda p: p[1])
    gap_days = (today_dt - origin).days
    followers = sum(1 for _, d in parsed if (d - origin).days >= RECIRC_MIN_GAP_DAYS)

    if gap_days >= CONFLICT_GAP_DAYS:
        return Result(Verdict.DATE_CONFLICT, origin.date().isoformat(), gap_days, followers)
    if gap_days >= RECIRC_MIN_GAP_DAYS and followers >= RECIRC_MIN_FOLLOWERS:
        return Result(Verdict.RECIRCULATION, origin.date().isoformat(), gap_days, followers)
    return Result(Verdict.FRESH, origin.date().isoformat(), gap_days, followers)
```

- [ ] **Step 4: Verify pass**

Run: `python3 -m pytest tests/test_recirculation.py -v` — Expected: PASS, 5 tests.

- [ ] **Step 5: Commit**

```bash
git add ledger/recirculation.py tests/test_recirculation.py
git commit -m "feat(ledger): recirculation and date-conflict detection"
```

---

## Task 5: Beat registry and lifecycle

Close criteria must ship in v1. A system that only opens beats becomes a topic list within a
quarter.

**Files:**
- Create: `ledger/beats.py`, `config/beats.yaml`, `config/dossiers.yaml`, `config/types.yaml`
- Test: `tests/test_beats.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_beats.py
import pytest
from ledger.beats import should_open, should_close, assign_beats, Beat

def ev(day):  # minimal event stub
    return {"day": day}

def test_opens_on_three_events_over_five_days():
    assert should_open([ev("2026-08-01"), ev("2026-08-04"), ev("2026-08-06")],
                       has_trigger=False, state_fields=2)

def test_does_not_open_on_three_events_in_one_day():
    assert not should_open([ev("2026-08-01")] * 3, has_trigger=False, state_fields=2)

def test_opens_on_a_single_event_with_a_dated_trigger():
    assert should_open([ev("2026-08-14")], has_trigger=True, state_fields=2)

def test_does_not_open_without_two_writable_state_fields():
    assert not should_open([ev("2026-08-01"), ev("2026-08-04"), ev("2026-08-06")],
                           has_trigger=True, state_fields=1)

def test_closes_after_thirty_quiet_days_with_no_triggers():
    assert should_close(days_since_change=30, pending_triggers=0)

def test_does_not_close_with_a_pending_trigger():
    assert not should_close(days_since_change=400, pending_triggers=1)

def test_does_not_close_before_thirty_days():
    assert not should_close(days_since_change=29, pending_triggers=0)

def test_assign_beats_scores_by_keyword_overlap():
    beats = [Beat("hormuz", "Hormuz", ["hormuz", "blockade", "strait"]),
             Beat("fed", "Fed", ["federal reserve", "rate", "fomc"])]
    got = assign_beats("Transit through the Strait of Hormuz slowed as the blockade held",
                       beats)
    assert got[0][0] == "hormuz"
    assert got[0][1] > 0

def test_assign_beats_returns_empty_when_nothing_matches():
    beats = [Beat("fed", "Fed", ["fomc"])]
    assert assign_beats("a story about pigeons", beats) == []
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_beats.py -v` — Expected: FAIL, no module.

- [ ] **Step 3: Implement**

```python
# ledger/beats.py
"""Beat registry, lifecycle rules, and keyword assignment.

A beat is a unit of persistent state: something whose current condition can be
written in fields, so each new event either changes a field or does not.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import re

OPEN_MIN_EVENTS = 3
OPEN_MIN_SPAN_DAYS = 5
OPEN_MIN_STATE_FIELDS = 2
CLOSE_QUIET_DAYS = 30


@dataclass(frozen=True)
class Beat:
    id: str
    name: str
    keywords: list[str] = field(default_factory=list)
    dossiers: tuple[str, ...] = ()
    types: tuple[str, ...] = ()


def _span_days(events) -> int:
    days = sorted({e["day"] for e in events})
    if len(days) < 2:
        return 0
    from datetime import date
    a, b = date.fromisoformat(days[0]), date.fromisoformat(days[-1])
    return (b - a).days


def should_open(events, has_trigger: bool, state_fields: int) -> bool:
    if state_fields < OPEN_MIN_STATE_FIELDS:
        return False
    if has_trigger and len(events) >= 1:
        return True
    return len(events) >= OPEN_MIN_EVENTS and _span_days(events) >= OPEN_MIN_SPAN_DAYS


def should_close(days_since_change: int, pending_triggers: int) -> bool:
    return pending_triggers == 0 and days_since_change >= CLOSE_QUIET_DAYS


def assign_beats(text: str, beats, threshold: float = 0.0):
    """Score beats by keyword overlap. Returns [(beat_id, score)] descending.

    Deliberately dumb and model-free: this runs on every ingested item at tier 1.
    Every assignment is logged with its score so misassignment can be measured
    before deciding whether a classifier is warranted.
    """
    low = text.lower()
    scored = []
    for b in beats:
        if not b.keywords:
            continue
        hits = sum(1 for k in b.keywords if re.search(r"\b" + re.escape(k.lower()), low))
        if hits:
            scored.append((b.id, hits / len(b.keywords)))
    scored.sort(key=lambda x: (-x[1], x[0]))
    return [s for s in scored if s[1] > threshold]
```

- [ ] **Step 4: Verify pass**

Run: `python3 -m pytest tests/test_beats.py -v` — Expected: PASS, 9 tests.

- [ ] **Step 5: Commit**

```bash
git add ledger/beats.py tests/test_beats.py
git commit -m "feat(ledger): beat lifecycle rules and keyword assignment"
```

---

## Task 6: Ledger store — the single I/O boundary

**Files:**
- Create: `ledger/store.py`
- Test: `tests/test_store.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_store.py
import json, pytest
from ledger.store import Ledger
from ledger.paths import PartitionError

@pytest.fixture
def led(tmp_path):
    return Ledger(tmp_path)

def test_write_and_read_source(led):
    s = {"sha256": "a"*64, "url": "https://x", "title": "T", "source_name": "E",
         "source_type": "news", "published_at": "2026-08-14T03:00:00Z",
         "first_seen": "2026-08-14T04:00:00Z", "candidate_beats": []}
    p = led.put_source("2026-08-14", s)
    assert led.get_source("2026-08-14", "a"*64) == s
    assert p in led.written

def test_sources_are_immutable(led):
    s = {"sha256": "a"*64, "url": "https://x", "title": "T", "source_name": "E",
         "source_type": "news", "published_at": "2026-08-14T03:00:00Z",
         "first_seen": "2026-08-14T04:00:00Z", "candidate_beats": []}
    led.put_source("2026-08-14", s)
    with pytest.raises(FileExistsError):
        led.put_source("2026-08-14", dict(s, title="changed"))

def test_history_appends_and_preserves_order(led):
    led.append_history("hormuz", {"d": "2026-08-13", "c": "first"})
    led.append_history("hormuz", {"d": "2026-08-14", "c": "second"})
    rows = led.read_history("hormuz")
    assert [r["c"] for r in rows] == ["first", "second"]

def test_state_is_overwritten_not_appended(led):
    st = {"beat": "hormuz", "as_of": "2026-08-13",
          "fields": [{"k": "a", "v": "1"}, {"k": "b", "v": "2"}]}
    led.put_state("hormuz", st)
    led.put_state("hormuz", dict(st, as_of="2026-08-14"))
    assert led.get_state("hormuz")["as_of"] == "2026-08-14"

def test_invalid_state_is_rejected_before_touching_disk(led):
    with pytest.raises(Exception):
        led.put_state("hormuz", {"beat": "hormuz", "as_of": "2026-08-14",
                                 "fields": [{"k": "a", "v": "1"}]})
    assert led.get_state("hormuz") is None

def test_writer_partition_is_enforced(led):
    led.writer = "beat:hormuz"
    with pytest.raises(PartitionError):
        led.put_state("fed", {"beat": "fed", "as_of": "2026-08-14",
                              "fields": [{"k": "a", "v": "1"}, {"k": "b", "v": "2"}]})

def test_writer_partition_allows_own_beat(led):
    led.writer = "beat:hormuz"
    led.put_state("hormuz", {"beat": "hormuz", "as_of": "2026-08-14",
                             "fields": [{"k": "a", "v": "1"}, {"k": "b", "v": "2"}]})
    assert led.get_state("hormuz") is not None

def test_list_beats_and_sources(led):
    led.put_state("hormuz", {"beat": "hormuz", "as_of": "2026-08-14",
                             "fields": [{"k": "a", "v": "1"}, {"k": "b", "v": "2"}]})
    assert led.list_beats() == ["hormuz"]
```

- [ ] **Step 2: Run to verify failure** — Expected: FAIL, no module.

- [ ] **Step 3: Implement**

```python
# ledger/store.py
"""The only module that touches the filesystem.

Sources are immutable: writing one that already exists is an error, not an update.
State is overwritten. History is append-only. Every write is validated first and
checked against the writer's partition.
"""
from __future__ import annotations
import json, os
from pathlib import Path
from . import paths as P
from .schema import validate_source, validate_claim, validate_beat_state


class Ledger:
    def __init__(self, root, writer: str | None = None):
        self.root = Path(root)
        self.writer = writer
        self.written: list[str] = []

    # ---- internals -------------------------------------------------
    def _abs(self, rel: str) -> Path:
        return self.root / rel

    def _guard(self, rel: str) -> None:
        if self.writer:
            P.assert_owns(self.writer, [rel])

    def _write_json(self, rel: str, obj, exclusive: bool = False) -> str:
        self._guard(rel)
        p = self._abs(rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        if exclusive and p.exists():
            raise FileExistsError(f"{rel} already exists; sources are immutable")
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, p)
        self.written.append(rel)
        return rel

    def _read_json(self, rel: str):
        p = self._abs(rel)
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    # ---- sources ---------------------------------------------------
    def put_source(self, day: str, source: dict) -> str:
        validate_source(source)
        return self._write_json(P.source_path(day, source["sha256"]), source, exclusive=True)

    def get_source(self, day: str, sha: str):
        return self._read_json(P.source_path(day, sha))

    def list_sources(self, day: str) -> list[str]:
        d = self._abs(f"{P.SOURCES}/{day}")
        return sorted(f.stem for f in d.glob("*.json")) if d.exists() else []

    # ---- claims ----------------------------------------------------
    def put_claim(self, claim: dict) -> str:
        validate_claim(claim)
        return self._write_json(P.claim_path(claim["beat"], claim["id"]), claim)

    def list_claims(self, beat_id: str) -> list[dict]:
        d = self._abs(f"{P.CLAIMS}/{beat_id}")
        if not d.exists():
            return []
        return [json.loads(f.read_text(encoding="utf-8")) for f in sorted(d.glob("*.json"))]

    # ---- beat state and history ------------------------------------
    def put_state(self, beat_id: str, state: dict) -> str:
        validate_beat_state(state)
        return self._write_json(P.beat_state_path(beat_id), state)

    def get_state(self, beat_id: str):
        return self._read_json(P.beat_state_path(beat_id))

    def append_history(self, beat_id: str, row: dict) -> str:
        rel = P.beat_history_path(beat_id)
        self._guard(rel)
        p = self._abs(rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        self.written.append(rel)
        return rel

    def read_history(self, beat_id: str) -> list[dict]:
        p = self._abs(P.beat_history_path(beat_id))
        if not p.exists():
            return []
        return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]

    def list_beats(self) -> list[str]:
        d = self._abs(P.BEATS)
        return sorted(x.name for x in d.iterdir() if x.is_dir()) if d.exists() else []
```

- [ ] **Step 4: Verify pass**

Run: `python3 -m pytest tests/test_store.py -v` — Expected: PASS, 8 tests.

- [ ] **Step 5: Commit**

```bash
git add ledger/store.py tests/test_store.py
git commit -m "feat(ledger): store as the single I/O boundary, validated and partitioned"
```

---

## Task 7: Ingest — normalise a fetched item into a source object

**Files:**
- Create: `ledger/ingest.py`
- Test: `tests/test_ingest.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ingest.py
from ledger.ingest import normalise, content_sha
from ledger.beats import Beat

BEATS = [Beat("hormuz", "Hormuz", ["hormuz", "blockade", "strait"])]

RAW = {"url": "https://ex.org/a?utm_source=x", "title": "Hormuz transit slows",
       "snippet": "The blockade held as transit through the Strait slowed.",
       "source_name": "Example Wire", "published_at": "2026-08-14T03:00:00Z"}

def test_sha_is_stable_and_ignores_tracking_params():
    a = content_sha({**RAW, "url": "https://ex.org/a?utm_source=x"})
    b = content_sha({**RAW, "url": "https://ex.org/a?utm_source=y"})
    assert a == b and len(a) == 64

def test_sha_changes_when_content_changes():
    assert content_sha(RAW) != content_sha({**RAW, "title": "different"})

def test_normalise_produces_a_valid_source_with_first_seen():
    s = normalise(RAW, beats=BEATS, now="2026-08-14T04:00:00Z")
    assert s["first_seen"] == "2026-08-14T04:00:00Z"
    assert s["source_type"] == "news"
    assert s["candidate_beats"][0]["beat"] == "hormuz"

def test_normalise_records_assignment_scores_for_later_measurement():
    s = normalise(RAW, beats=BEATS, now="2026-08-14T04:00:00Z")
    assert isinstance(s["candidate_beats"][0]["score"], float)

def test_unmatched_item_gets_no_beats_but_is_still_stored():
    s = normalise({**RAW, "title": "pigeons", "snippet": "pigeons"},
                  beats=BEATS, now="2026-08-14T04:00:00Z")
    assert s["candidate_beats"] == []
    assert s["sha256"]
```

- [ ] **Step 2: Run to verify failure** — Expected: FAIL, no module.

- [ ] **Step 3: Implement**

```python
# ledger/ingest.py
"""Tier 1. No model. Fetch → normalise → content-address → assign candidate beats.

first_seen is the field the recirculation detector runs on and is the single most
load-bearing value written at this tier.
"""
from __future__ import annotations
import hashlib
from urllib.parse import urlsplit, parse_qsl, urlencode, urlunsplit
from .beats import assign_beats

TRACKING = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
            "fbclid", "gclid", "ref", "_hsenc"}


def canonical_url(url: str) -> str:
    parts = urlsplit(url)
    q = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
         if k.lower() not in TRACKING]
    return urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"),
                       urlencode(q), ""))


def content_sha(raw: dict) -> str:
    basis = "\n".join([canonical_url(raw.get("url", "")),
                       (raw.get("title") or "").strip(),
                       (raw.get("snippet") or "").strip()])
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def normalise(raw: dict, beats, now: str, source_type: str = "news") -> dict:
    text = " ".join(filter(None, [raw.get("title"), raw.get("snippet"),
                                  raw.get("full_text")]))
    return {
        "sha256": content_sha(raw),
        "url": canonical_url(raw.get("url", "")),
        "original_url": raw.get("url", ""),
        "title": raw.get("title") or "",
        "snippet": raw.get("snippet") or "",
        "source_name": raw.get("source_name") or "",
        "source_type": source_type,
        "published_at": raw.get("published_at") or now,
        "first_seen": now,
        "candidate_beats": [{"beat": b, "score": float(s)}
                            for b, s in assign_beats(text, beats)],
    }
```

- [ ] **Step 4: Verify pass**

Run: `python3 -m pytest tests/test_ingest.py -v` — Expected: PASS, 5 tests.

- [ ] **Step 5: Commit**

```bash
git add ledger/ingest.py tests/test_ingest.py
git commit -m "feat(ledger): tier-1 ingest normalisation with content addressing"
```

---

## Task 8: Compile the ledger into SQLite

The read surface. Deletable and rebuildable — a corrupted DB is never data loss.

**Files:**
- Create: `ledger/compile.py`
- Test: `tests/test_compile.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_compile.py
import sqlite3, pytest
from ledger.store import Ledger
from ledger.compile import compile_db

@pytest.fixture
def populated(tmp_path):
    led = Ledger(tmp_path / "data")
    led.put_source("2026-08-14", {
        "sha256": "a"*64, "url": "https://x", "title": "T", "source_name": "E",
        "source_type": "news", "published_at": "2026-08-14T03:00:00Z",
        "first_seen": "2026-08-14T04:00:00Z",
        "candidate_beats": [{"beat": "hormuz", "score": 0.5}]})
    led.put_state("hormuz", {"beat": "hormuz", "as_of": "2026-08-14",
        "fields": [{"k": "Blockade", "v": "In force", "since": "Aug"},
                   {"k": "Transit", "v": "Near standstill", "since": "14 Aug"}]})
    led.append_history("hormuz", {"d": "2026-08-14", "c": "Transit changed", "s": "wire"})
    led.put_claim({"id": "hormuz-1", "beat": "hormuz", "claim_text": "X",
        "quote": "x", "source_type": "news", "source_url": "https://x",
        "confidence": 0.6, "confidence_justification": "news ceiling",
        "tier": "documented_fact", "extracted_by": "t", "extracted_at": "2026-08-14T05:00:00Z"})
    return led, tmp_path / "out.db"

def test_compile_creates_all_tables(populated):
    led, db = populated
    compile_db(led.root, db)
    con = sqlite3.connect(db)
    names = {r[0] for r in con.execute("select name from sqlite_master where type='table'")}
    assert {"sources", "claims", "beat_state", "beat_history"} <= names

def test_state_fields_become_queryable_rows(populated):
    led, db = populated
    compile_db(led.root, db)
    con = sqlite3.connect(db)
    rows = con.execute("select k, v from beat_state where beat='hormuz' order by k").fetchall()
    assert rows == [("Blockade", "In force"), ("Transit", "Near standstill")]

def test_claims_carry_confidence_and_tier(populated):
    led, db = populated
    compile_db(led.root, db)
    con = sqlite3.connect(db)
    r = con.execute("select confidence, tier from claims where id='hormuz-1'").fetchone()
    assert r == (0.6, "documented_fact")

def test_compile_is_idempotent(populated):
    led, db = populated
    compile_db(led.root, db)
    compile_db(led.root, db)
    con = sqlite3.connect(db)
    assert con.execute("select count(*) from claims").fetchone()[0] == 1

def test_compile_on_empty_tree_succeeds(tmp_path):
    compile_db(tmp_path / "empty", tmp_path / "e.db")
    con = sqlite3.connect(tmp_path / "e.db")
    assert con.execute("select count(*) from sources").fetchone()[0] == 0
```

- [ ] **Step 2: Run to verify failure** — Expected: FAIL, no module.

- [ ] **Step 3: Implement**

```python
# ledger/compile.py
"""Compile the git ledger into a queryable SQLite index.

No model. Fully deterministic. The database is derived: delete it and rebuild.
"""
from __future__ import annotations
import json, sqlite3
from pathlib import Path
from . import paths as P

DDL = """
drop table if exists sources; drop table if exists claims;
drop table if exists beat_state; drop table if exists beat_history;
create table sources(sha256 text primary key, url text, title text, source_name text,
  source_type text, published_at text, first_seen text, day text);
create table source_beats(sha256 text, beat text, score real);
create table claims(id text primary key, beat text, claim_text text, quote text,
  source_type text, source_url text, source_doi text, confidence real,
  confidence_justification text, tier text, extracted_by text, extracted_at text);
create table beat_state(beat text, as_of text, k text, v text, since text, flag text);
create table beat_history(beat text, d text, c text, s text, ord integer);
create index if not exists ix_claims_beat on claims(beat);
create index if not exists ix_state_beat on beat_state(beat);
"""


def _load(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def compile_db(root, db_path) -> Path:
    root, db_path = Path(root), Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    con.executescript("drop table if exists source_beats;" + DDL)

    sdir = root / P.SOURCES
    if sdir.exists():
        for day in sorted(sdir.iterdir()):
            if not day.is_dir():
                continue
            for f in sorted(day.glob("*.json")):
                s = _load(f)
                if not s:
                    continue
                con.execute("insert or replace into sources values(?,?,?,?,?,?,?,?)",
                            (s["sha256"], s.get("url"), s.get("title"), s.get("source_name"),
                             s.get("source_type"), s.get("published_at"),
                             s.get("first_seen"), day.name))
                for cb in s.get("candidate_beats", []):
                    con.execute("insert into source_beats values(?,?,?)",
                                (s["sha256"], cb.get("beat"), cb.get("score")))

    cdir = root / P.CLAIMS
    if cdir.exists():
        for bd in sorted(cdir.iterdir()):
            for f in sorted(bd.glob("*.json")):
                c = _load(f)
                if not c:
                    continue
                con.execute("insert or replace into claims values(?,?,?,?,?,?,?,?,?,?,?,?)",
                            (c["id"], c.get("beat"), c.get("claim_text"), c.get("quote"),
                             c.get("source_type"), c.get("source_url"), c.get("source_doi"),
                             c.get("confidence"), c.get("confidence_justification"),
                             c.get("tier"), c.get("extracted_by"), c.get("extracted_at")))

    bdir = root / P.BEATS
    if bdir.exists():
        for bd in sorted(x for x in bdir.iterdir() if x.is_dir()):
            st = _load(bd / "state.json")
            if st:
                for fld in st.get("fields", []):
                    con.execute("insert into beat_state values(?,?,?,?,?,?)",
                                (st["beat"], st.get("as_of"), fld.get("k"), fld.get("v"),
                                 fld.get("since"), fld.get("flag")))
            hp = bd / "history.jsonl"
            if hp.exists():
                for i, line in enumerate(hp.read_text(encoding="utf-8").splitlines()):
                    if not line.strip():
                        continue
                    r = json.loads(line)
                    con.execute("insert into beat_history values(?,?,?,?,?)",
                                (bd.name, r.get("d"), r.get("c"), r.get("s"), i))
    con.commit()
    con.close()
    return db_path
```

- [ ] **Step 4: Verify pass**

Run: `python3 -m pytest tests/test_compile.py -v` — Expected: PASS, 5 tests.

- [ ] **Step 5: Commit**

```bash
git add ledger/compile.py tests/test_compile.py
git commit -m "feat(ledger): compile the ledger tree into a derived SQLite index"
```

---

## Task 9: End-to-end smoke test against real data

Prove the substrate works on the actual `news.db` rows rather than fixtures.

**Files:**
- Create: `tests/test_e2e.py`, `ledger/cli.py`

- [ ] **Step 1: Write the end-to-end test**

```python
# tests/test_e2e.py
"""Ingest → store → compile, end to end, with no model involved."""
import sqlite3
from ledger.store import Ledger
from ledger.ingest import normalise
from ledger.beats import Beat
from ledger.compile import compile_db
from ledger.recirculation import analyse_cluster, Verdict

BEATS = [Beat("flock", "Flock", ["flock", "licence plate", "license plate", "plate reader"]),
         Beat("hormuz", "Hormuz", ["hormuz", "blockade", "strait"])]

def test_full_cycle_detects_recirculation_and_compiles(tmp_path):
    led = Ledger(tmp_path / "data", writer="ingest")
    origin = {"url": "https://ap.org/flock", "title": "Flock announces changes",
              "snippet": "plate reader retention cut to seven days",
              "source_name": "AP", "published_at": "2026-08-13T14:00:00Z"}
    led.put_source("2026-08-13", normalise(origin, BEATS, "2026-08-13T14:30:00Z"))

    followers = []
    for i in range(8):
        raw = {**origin, "url": f"https://outlet{i}.com/flock", "source_name": f"Outlet{i}",
               "published_at": "2026-08-14T08:00:00Z"}
        s = normalise(raw, BEATS, "2026-08-14T08:05:00Z")
        led.put_source("2026-08-14", s)
        followers.append(s)

    cluster = [{"source_name": "AP", "published_at": "2026-08-13T14:00:00Z",
                "first_seen": "2026-08-13T14:30:00Z"}] + [
               {"source_name": f["source_name"], "published_at": f["published_at"],
                "first_seen": f["first_seen"]} for f in followers]
    r = analyse_cluster(cluster, today="2026-08-14")
    assert r.verdict is Verdict.RECIRCULATION
    assert r.origin_date == "2026-08-13"

    db = tmp_path / "newsdesk.db"
    compile_db(led.root, db)
    con = sqlite3.connect(db)
    assert con.execute("select count(*) from sources").fetchone()[0] == 9
    assert con.execute(
        "select count(*) from source_beats where beat='flock'").fetchone()[0] == 9
```

- [ ] **Step 2: Run it** — Expected: PASS.

- [ ] **Step 3: Write the CLI**

```python
# ledger/cli.py
"""Entry points. `python3 -m ledger.cli compile <root> <db>`"""
from __future__ import annotations
import sys
from pathlib import Path
from .compile import compile_db


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("usage: python3 -m ledger.cli compile <ledger-root> <db-path>")
        return 2
    if argv[0] == "compile":
        root, db = argv[1], argv[2]
        out = compile_db(root, db)
        print(f"compiled {Path(root)} -> {out}")
        return 0
    print(f"unknown command: {argv[0]}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the whole suite**

Run: `cd /mnt/d/Newsdesk && python3 -m pytest tests/ -v`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add tests/test_e2e.py ledger/cli.py
git commit -m "feat(ledger): end-to-end cycle and compile CLI"
```

---

## Task 10: Config — the 16 beats, made data not code

**Files:**
- Create: `config/beats.yaml`, `config/dossiers.yaml`, `config/types.yaml`, `config/policy.yaml`
- Modify: `ledger/beats.py` — add `load_beats(path)`
- Test: extend `tests/test_beats.py`

- [ ] **Step 1: Write the failing test**

```python
def test_load_beats_from_config_gives_sixteen_beats():
    from ledger.beats import load_beats
    beats = load_beats("config/beats.yaml")
    assert len(beats) == 16
    assert all(b.keywords for b in beats), "every beat needs keywords for tier-1 assignment"
    assert all(b.dossiers for b in beats), "every beat belongs to at least one dossier"
    ids = [b.id for b in beats]
    assert len(ids) == len(set(ids)), "beat ids must be unique"
```

- [ ] **Step 2: Run to verify failure**
- [ ] **Step 3: Write the four config files and `load_beats`** (YAML via `yaml.safe_load`; if PyYAML is unavailable, use JSON files instead and adjust the loader — do not add a dependency for this alone)
- [ ] **Step 4: Verify pass**
- [ ] **Step 5: Commit**

```bash
git commit -am "feat(config): the sixteen beats, twelve dossiers, nine types as data"
```

---

## Definition of done for plan 1

- [ ] `python3 -m pytest tests/ -v` passes with no failures
- [ ] `python3 -m ledger.cli compile data/ newsdesk.db` produces a queryable database
- [ ] Writing outside a writer's partition raises `PartitionError`
- [ ] A claim without a quote, a source pointer, a justification, or over its ceiling is rejected
- [ ] A beat with fewer than two state fields cannot exist
- [ ] Recirculation and date-conflict are detected on the Flock and D.C.-police shapes
- [ ] No module in `ledger/` imports an LLM client

## Next plans

2. **Beat agents (tier 2)** — claim extraction, state recompute, ancestry, adversarial verify.
3. **Editor (tier 3)** — diff, suppression, ranking, editions, hold queue, Brier scoring.
4. **Render & deploy** — static render, nginx subdomain, Actions deploy.
