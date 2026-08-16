# Document Zero v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn Document Zero from a rendered state-diff into a newspaper that writes articles from its ledger, fed by news it discovers rather than news someone listed.

**Architecture:** The existing ledger becomes the newsroom's memory. New layers sit on top: a scout that opens and closes beats from the wire, a reporter that writes a 400–800 word article per moved beat, and an entailment gate that refuses any article containing a sentence its cited claims do not support. Every agent is a Claude Code subprocess behind an injected callable, so the whole pipeline runs for free with stubs in tests.

**Tech Stack:** Python 3.13, pytest, feedparser, SQLite, static HTML/CSS/JS. Claude Code CLI (`claude -p`) as the agent runtime. **No metered API — see `ledger/NO_PAID_APIS.md`.**

**Spec:** `docs/superpowers/specs/2026-08-16-document-zero-v2-design.md`

---

## Read this before Task 1

**The money rule.** Nothing in this plan may call a paid API. The operator was
billed $0.36 without consent on 2026-08-14 and the paid client was deleted. Every
agent is invoked as `claude -p` on the operator's subscription. If you find
yourself writing `import anthropic`, stop — you have taken a wrong turn.

**The live host.** `epstein-data.com` serves ~15k people/day from the same box.
It runs no agents and receives static files only. Never install a runtime there,
never restart nginx, never edit `/etc/nginx/sites-enabled/datasette`.

**Existing seams you will use, not rebuild.**

| Thing | Where | Note |
|---|---|---|
| `Ledger(root, writer=...)` | `ledger/store.py` | enforces write partitioning on every write |
| `owned_prefixes(writer)` | `ledger/paths.py:46` | `ingest`, `editor`, `beat:<id>` today |
| `BeatAgent(..., extractor=, passes=, state_proposer=)` | `ledger/agent.py:41` | callables — this is where Claude Code plugs in |
| `run_editor(ledger, results, day, policy, ...)` | `ledger/editor.py:75` | already ranks and lanes |
| `wire.fetch()` / `emerge.cluster()` | `ledger/wire.py`, `ledger/emerge.py` | built 2026-08-16, free, working |
| `build(root, beats_cfg, day)` | `ledger/render.py` | projection → page data |

**Run the suite before you start:** `python3 -m pytest tests/ -q` → expect **380 passed**.

---

## File structure

| File | Responsibility |
|---|---|
| `ledger/article.py` | **new.** The Article object and its schema. Word bounds, dateline, timestamp, per-paragraph claim citations. |
| `ledger/entail.py` | **new.** The entailment gate. Splits prose into sentences, runs verifiers, refuses on any unentailed sentence. |
| `ledger/scout.py` | **new.** Beat proposals, the beat test, opening and closing. |
| `ledger/reporter.py` | **new.** Builds the writing prompt from a beat's state delta + claims; parses the article back. |
| `ledger/frontpage.py` | **new.** Editor play: lead, secondary, also-moving, did-not-publish. |
| `ledger/claudecode.py` | **new.** The only module that spawns an agent. `claude -p` subprocess adapter. |
| `ledger/paths.py` | modify: add `scout` writer owning `proposals/`. |
| `ledger/render.py` | modify: project articles, not field diffs, into page data. |
| `index.html` | rewrite: article-first front page. |
| `scripts/stub_newsroom.py` | **new.** Full pipeline with deterministic stubs. No model, no cost. |

---

## Task 1: The Article object

**Files:**
- Create: `ledger/article.py`
- Test: `tests/test_article.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_article.py
import pytest
from ledger.article import Article, ArticleError, validate

def art(**kw):
    base = dict(
        beat="fed", day="2026-08-16",
        headline="Fed signals a hold as September decision nears",
        standfirst="Two governors break with the chair in remarks a day apart",
        dateline="WASHINGTON", published_at="2026-08-16T14:02:00Z",
        paragraphs=[{"text": "word " * 450, "claims": ["fed-1"]}],
        changed=[{"k": "Dissents", "from": "1", "to": "3", "since": "2026-08-14"}],
        written_by="claude-code/beat:fed", verified_by=["e1", "e2"])
    base.update(kw)
    return base

def test_a_well_formed_article_validates():
    a = validate(art())
    assert isinstance(a, Article) and a.word_count == 450

def test_an_article_under_four_hundred_words_is_refused():
    """Below 400 words there was no story — the beat should degrade to a line."""
    with pytest.raises(ArticleError, match="400"):
        validate(art(paragraphs=[{"text": "word " * 120, "claims": ["fed-1"]}]))

def test_an_article_over_eight_hundred_words_is_refused():
    """Above 800 the reporter is padding."""
    with pytest.raises(ArticleError, match="800"):
        validate(art(paragraphs=[{"text": "word " * 900, "claims": ["fed-1"]}]))

def test_a_paragraph_citing_no_claims_is_refused():
    """Every paragraph must rest on evidence the ledger holds."""
    with pytest.raises(ArticleError, match="cites no claims"):
        validate(art(paragraphs=[{"text": "word " * 450, "claims": []}]))

@pytest.mark.parametrize("missing", ["headline", "dateline", "published_at"])
def test_the_mandatory_fields_are_mandatory(missing):
    """v1 shipped with no dates and it was the first thing a reader noticed."""
    with pytest.raises(ArticleError, match=missing):
        validate(art(**{missing: ""}))

def test_a_headline_that_is_a_sentence_fragment_is_refused():
    with pytest.raises(ArticleError, match="headline"):
        validate(art(headline="Fed"))

def test_claims_cited_anywhere_are_collected():
    a = validate(art(paragraphs=[
        {"text": "word " * 220, "claims": ["fed-1", "fed-2"]},
        {"text": "word " * 230, "claims": ["fed-2", "fed-3"]}]))
    assert a.cited == {"fed-1", "fed-2", "fed-3"}
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_article.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'ledger.article'`

- [ ] **Step 3: Implement**

```python
# ledger/article.py
"""The Article: what a reporter produces and a reader reads.

v1's central artifact was a diff of state fields, which is a database row. This
is the replacement. The state delta still decides WHAT is worth writing; this
object is what gets written.

The bounds are editorial judgements encoded as validation. Below 400 words there
was no story and the beat should degrade to a one-line entry. Above 800 the
reporter is padding. A paragraph citing no claims is prose the ledger cannot
support, which is the failure mode this whole project exists to prevent.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field

MIN_WORDS, MAX_WORDS = 400, 800
REQUIRED = ("beat", "day", "headline", "standfirst", "dateline",
            "published_at", "written_by")


class ArticleError(ValueError):
    """An article does not satisfy the schema and may not publish."""


@dataclass(frozen=True)
class Article:
    beat: str
    day: str
    headline: str
    standfirst: str
    dateline: str
    published_at: str
    paragraphs: tuple
    changed: tuple = ()
    written_by: str = ""
    verified_by: tuple = ()
    word_count: int = 0
    cited: frozenset = field(default_factory=frozenset)


def _words(text: str) -> int:
    return len([w for w in re.split(r"\s+", (text or "").strip()) if w])


def validate(obj: dict) -> Article:
    for f in REQUIRED:
        if not str(obj.get(f) or "").strip():
            raise ArticleError(f"missing required field: {f}")

    if len(str(obj["headline"]).split()) < 4:
        raise ArticleError("headline must be a sentence, not a fragment")

    paras = obj.get("paragraphs") or []
    if not paras:
        raise ArticleError("an article needs at least one paragraph")

    cited = set()
    total = 0
    for i, p in enumerate(paras):
        text = str(p.get("text") or "")
        claims = p.get("claims") or []
        if not claims:
            raise ArticleError(f"paragraph {i} cites no claims; prose the ledger "
                               "cannot trace to evidence may not publish")
        cited.update(claims)
        total += _words(text)

    if total < MIN_WORDS:
        raise ArticleError(f"{total} words: below {MIN_WORDS}, there was no story")
    if total > MAX_WORDS:
        raise ArticleError(f"{total} words: above {MAX_WORDS}, the reporter is padding")

    return Article(
        beat=obj["beat"], day=obj["day"], headline=obj["headline"],
        standfirst=obj["standfirst"], dateline=obj["dateline"],
        published_at=obj["published_at"],
        paragraphs=tuple(dict(p) for p in paras),
        changed=tuple(dict(c) for c in obj.get("changed") or ()),
        written_by=obj["written_by"],
        verified_by=tuple(obj.get("verified_by") or ()),
        word_count=total, cited=frozenset(cited))
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest tests/test_article.py -q` → Expected: **8 passed**

- [ ] **Step 5: Commit**

```bash
git add ledger/article.py tests/test_article.py
git commit -m "feat: the Article object replaces the state diff as the artifact"
```

---

## Task 2: The entailment gate

This is the load-bearing new safety mechanism. Read spec §4 before starting.

**Files:**
- Create: `ledger/entail.py`
- Test: `tests/test_entail.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_entail.py
import pytest
from ledger.article import validate
from ledger.entail import check, sentences, Verdict, Refused

CLAIMS = [
    {"id": "c1", "claim_text": "The Federal Reserve held rates unchanged in August 2026."},
    {"id": "c2", "claim_text": "Two governors dissented from the August decision."},
]

def article(text, claims=("c1", "c2")):
    return validate({
        "beat": "fed", "day": "2026-08-16",
        "headline": "Fed holds rates as September nears",
        "standfirst": "Two governors dissent", "dateline": "WASHINGTON",
        "published_at": "2026-08-16T14:02:00Z", "written_by": "t",
        "paragraphs": [{"text": text + " filler" * 400, "claims": list(claims)}]})

def yes(_s, _c): return Verdict(True, "supported")
def no(_s, _c):  return Verdict(False, "nothing supports this")

def test_sentences_are_split_for_checking():
    s = sentences("The Fed held rates. Two governors dissented! Did they? Yes.")
    assert len(s) == 4

def test_an_article_every_sentence_of_which_is_entailed_passes():
    r = check(article("The Fed held rates."), CLAIMS, verifiers=[yes, yes])
    assert r.passed is True and r.refusals == []

def test_one_unentailed_sentence_refuses_the_WHOLE_article():
    """Refusing the article rather than editing the sentence is deliberate: an
    article patched to survive a check is an article optimised against it."""
    def first_fails(s, c):
        return Verdict(False, "unsupported") if "cut" in s else Verdict(True, "ok")
    r = check(article("The Fed held rates. A cut is now inevitable."),
              CLAIMS, verifiers=[first_fails, yes])
    assert r.passed is False
    assert any("inevitable" in x.sentence for x in r.refusals)

def test_either_verifier_can_refuse():
    """Consensus is not required to refuse. One is enough."""
    assert check(article("The Fed held rates."), CLAIMS,
                 verifiers=[yes, no]).passed is False
    assert check(article("The Fed held rates."), CLAIMS,
                 verifiers=[no, yes]).passed is False

def test_a_verifier_that_errors_counts_as_refusal():
    """Uncertainty resolves to not-entailed."""
    def boom(_s, _c): raise RuntimeError("timeout")
    assert check(article("The Fed held rates."), CLAIMS,
                 verifiers=[boom, yes]).passed is False

def test_verifiers_receive_only_the_sentence_and_the_cited_claims():
    """Asymmetry of information is the point: a verifier shown the writer's
    justification adopts it."""
    seen = []
    def spy(s, c):
        seen.append((s, c)); return Verdict(True, "ok")
    a = article("The Fed held rates.")
    check(a, CLAIMS + [{"id": "c9", "claim_text": "unrelated"}], verifiers=[spy, yes])
    for _sentence, claims in seen:
        assert {c["id"] for c in claims} == {"c1", "c2"}, "uncited claims leaked in"

def test_refused_articles_raise_when_asked_to_publish():
    r = check(article("The Fed held rates."), CLAIMS, verifiers=[no, no])
    with pytest.raises(Refused):
        r.require_pass()
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_entail.py -q` → Expected: FAIL, no module `ledger.entail`

- [ ] **Step 3: Implement**

```python
# ledger/entail.py
"""The entailment gate: prose may not assert what its claims do not support.

A state field either matches the docket or it does not. A 600-word article can
introduce a causal claim, an implication, or a single adjective that no source
supports, and it will read fluently while doing so. Fluency is not accuracy, and
an automated newsroom with no human editor cannot rely on anyone noticing.

Three properties are enforced here rather than prompted:

  - Verifiers see the sentence and the CITED CLAIMS ONLY. Never the writer's
    reasoning, never the wider source set, never the beat's history. A verifier
    shown the justification adopts it.
  - One unentailed sentence refuses the WHOLE article. Not the sentence — the
    article. An article patched to survive a check is an article optimised
    against the check.
  - A verifier that errors, times out or is unsure counts as a refusal.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field

_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'“])")


class Refused(RuntimeError):
    """The article did not survive the gate and may not publish."""


@dataclass(frozen=True)
class Verdict:
    entailed: bool
    reason: str = ""


@dataclass(frozen=True)
class Refusal:
    sentence: str
    reason: str
    verifier: int


@dataclass
class Result:
    passed: bool
    refusals: list = field(default_factory=list)
    checked: int = 0

    def require_pass(self) -> None:
        if not self.passed:
            first = self.refusals[0] if self.refusals else None
            raise Refused(
                f"{len(self.refusals)} unentailed sentence(s); first: "
                f"{first.sentence[:80]!r} — {first.reason}" if first else "refused")


def sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT.split((text or "").strip()) if s.strip()]


def check(article, claims, verifiers) -> Result:
    """Run every sentence past every verifier. Refuse on the first failure of any.

    `verifiers` are callables (sentence, cited_claims) -> Verdict. They are
    injected so tests run for free; in production each is a Claude Code
    instance from a different model line.
    """
    by_id = {c["id"]: c for c in claims}
    res = Result(passed=True)

    for para in article.paragraphs:
        cited = [by_id[cid] for cid in para.get("claims", []) if cid in by_id]
        for sentence in sentences(para.get("text", "")):
            res.checked += 1
            for i, v in enumerate(verifiers):
                try:
                    verdict = v(sentence, cited)
                except Exception as e:                      # noqa: BLE001
                    verdict = Verdict(False, f"verifier error: {type(e).__name__}: {e}")
                if not verdict.entailed:
                    res.passed = False
                    res.refusals.append(Refusal(sentence, verdict.reason, i))
    return res
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest tests/test_entail.py -q` → Expected: **7 passed**

- [ ] **Step 5: Commit**

```bash
git add ledger/entail.py tests/test_entail.py
git commit -m "feat: entailment gate — one unsupported sentence refuses the article"
```

---

## Task 3: Adversarial fixtures for the gate

Spec §9 requires these specifically. A gate that only sees well-formed input is untested.

**Files:**
- Test: `tests/test_entail_adversarial.py`

- [ ] **Step 1: Write the tests**

```python
# tests/test_entail_adversarial.py
"""The four shapes the gate must distinguish. A gate that only sees well-formed
input is untested, and this gate is the only thing standing between the ledger
and a machine that writes confident fiction under a real domain name.

The verifier here is a deterministic stand-in that models what a careful reader
does: it entails a sentence only if the claim text covers its content words.
"""
import pytest
from ledger.article import validate
from ledger.entail import check, Verdict

CLAIMS = [{"id": "c1",
           "claim_text": "The Justice Department declined to search the property in 2019."}]

def strict(sentence, claims):
    """Entailed only if every content word appears in some cited claim."""
    blob = " ".join(c["claim_text"].lower() for c in claims)
    words = [w for w in sentence.lower().replace(".", "").split() if len(w) > 4]
    missing = [w for w in words if w not in blob]
    return Verdict(not missing, f"unsupported: {missing[:3]}" if missing else "ok")

def art(text):
    return validate({"beat": "b", "day": "2026-08-16",
                     "headline": "Department declined to search property",
                     "standfirst": "s", "dateline": "WASHINGTON",
                     "published_at": "2026-08-16T00:00:00Z", "written_by": "t",
                     "paragraphs": [{"text": text + " padding" * 420,
                                     "claims": ["c1"]}]})

def test_a_supported_sentence_passes():
    a = art("The Justice Department declined to search the property in 2019.")
    assert check(a, CLAIMS, verifiers=[strict]).passed is True

def test_a_sentence_supported_by_nothing_is_refused():
    a = art("The Justice Department declined to search the property in 2019. "
            "Investigators later found human remains at the site.")
    assert check(a, CLAIMS, verifiers=[strict]).passed is False

def test_a_sentence_that_OVERSTATES_its_claim_is_refused():
    """The claim says 'declined'. The article says 'covered up'. This is the
    failure mode fluent prose makes easy and a field/value pair makes impossible."""
    a = art("The Justice Department deliberately covered up evidence in 2019.")
    assert check(a, CLAIMS, verifiers=[strict]).passed is False

def test_a_true_but_UNCITED_sentence_is_still_refused():
    """Being true is not the standard. Being supported by the cited claims is."""
    a = art("The Justice Department declined to search the property in 2019. "
            "Washington is the capital of the United States.")
    assert check(a, CLAIMS, verifiers=[strict]).passed is False
```

- [ ] **Step 2: Run** → `python3 -m pytest tests/test_entail_adversarial.py -q` → **4 passed**

- [ ] **Step 3: Commit**

```bash
git add tests/test_entail_adversarial.py
git commit -m "test: adversarial fixtures for the entailment gate"
```

---

## Task 4: The scout — beats come from the news

**Files:**
- Create: `ledger/scout.py`
- Modify: `ledger/paths.py:46` (add the `scout` writer)
- Test: `tests/test_scout.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_scout.py
import pytest
from ledger.scout import Proposal, beat_test, should_close
from ledger.paths import owned_prefixes, owns_path

def prop(events=4, span_days=6, fields=("Status", "Next hearing"), trigger=None):
    return Proposal(name="Fifth Circuit v. NLRB", slug="fifth-circuit-nlrb",
                    events=events, span_days=span_days,
                    state_fields=list(fields), dated_trigger=trigger,
                    articles=[], publishers={"apnews.com", "reuters.com"})

def test_three_events_over_five_days_with_two_fields_opens():
    ok, why = beat_test(prop())
    assert ok is True, why

def test_too_few_events_is_rejected():
    ok, why = beat_test(prop(events=2))
    assert ok is False and "events" in why

def test_too_short_a_span_is_rejected():
    ok, why = beat_test(prop(span_days=2))
    assert ok is False and "days" in why

def test_one_dated_trigger_substitutes_for_the_event_threshold():
    """A scheduled hearing is a beat on day one — the sequence is guaranteed."""
    ok, why = beat_test(prop(events=1, span_days=0, trigger="2026-09-05"))
    assert ok is True, why

def test_fewer_than_two_changeable_fields_is_rejected():
    """This is the whole beat test: no changeable state, no beat. It is what
    stops a match result or a product launch becoming a tracked story."""
    ok, why = beat_test(prop(fields=("Status",), trigger="2026-09-05"))
    assert ok is False and "state field" in why

def test_a_beat_quiet_for_thirty_days_closes():
    assert should_close(days_since_change=31, pending_triggers=0) is True

def test_a_quiet_beat_with_a_pending_trigger_stays_open():
    """A beat awaiting a filing deadline is not dead, it is waiting."""
    assert should_close(days_since_change=90, pending_triggers=1) is False

def test_the_scout_owns_proposals_and_nothing_else():
    assert owned_prefixes("scout") == ("proposals/",)
    assert owns_path("scout", "proposals/2026-08-16.json") is True
    assert owns_path("scout", "beats/fed/state.json") is False
```

- [ ] **Step 2: Run** → FAIL, no module `ledger.scout`

- [ ] **Step 3: Implement the partition change**

In `ledger/paths.py`, add before the `beat:` branch in `owned_prefixes`:

```python
    if writer == "scout":
        return (f"{PROPOSALS}/",)
```

and near the other constants:

```python
PROPOSALS = "proposals"
```

- [ ] **Step 4: Implement the scout**

```python
# ledger/scout.py
"""Beats come from the news, not from a file.

v1 declared 22 beats in YAML. They could not open and could not close, so
coverage never grew and never shrank, and twenty of them sat permanently empty
while the front page showed two.

The scout reads the day's unassigned wire, clusters it (ledger/emerge.py), and
proposes beats. The beat test from the v1 spec §2.1 decides — it was correct and
is retained verbatim. Rejected proposals are RECORDED, so the ledger shows what
was considered and not merely what was covered.

No model, no cost.
"""
from __future__ import annotations
from dataclasses import dataclass, field

MIN_EVENTS = 3
MIN_SPAN_DAYS = 5
MIN_STATE_FIELDS = 2
QUIET_DAYS_TO_CLOSE = 30


@dataclass
class Proposal:
    name: str
    slug: str
    events: int
    span_days: int
    state_fields: list
    dated_trigger: str | None = None
    articles: list = field(default_factory=list)
    publishers: set = field(default_factory=set)


def beat_test(p: Proposal) -> tuple[bool, str]:
    """The v1 §2.1 test. Returns (opens, reason).

    A beat is a unit of persistent STATE. The question is not 'is this
    interesting' but 'can I write its current condition as fields such that
    tomorrow's events either change one or do not'. Everything else is a story,
    and a story without changeable state is a line in the paper, not a beat.
    """
    if len(p.state_fields) < MIN_STATE_FIELDS:
        return False, (f"{len(p.state_fields)} state field(s); a beat needs "
                       f"{MIN_STATE_FIELDS} that tomorrow could change")
    if p.dated_trigger:
        return True, f"dated trigger {p.dated_trigger}"
    if p.events < MIN_EVENTS:
        return False, f"{p.events} events; needs {MIN_EVENTS} or a dated trigger"
    if p.span_days < MIN_SPAN_DAYS:
        return False, (f"{p.span_days} days; needs {MIN_SPAN_DAYS} — a single "
                       "day's flurry is an event, not a beat")
    return True, f"{p.events} events over {p.span_days} days"


def should_close(days_since_change: int, pending_triggers: int) -> bool:
    """A beat awaiting a filing deadline is not dead, it is waiting."""
    if pending_triggers > 0:
        return False
    return days_since_change > QUIET_DAYS_TO_CLOSE
```

- [ ] **Step 5: Run** → `python3 -m pytest tests/test_scout.py -q` → **8 passed**

- [ ] **Step 6: Commit**

```bash
git add ledger/scout.py ledger/paths.py tests/test_scout.py
git commit -m "feat: scout opens and closes beats from the wire"
```

---

## Task 5: The stub newsroom — watch it run, for free

Spec §9. Nothing after this point should be built until you have seen a fake front page assemble end to end.

**Files:**
- Create: `scripts/stub_newsroom.py`
- Test: `tests/test_stub_newsroom.py`

- [ ] **Step 1: Write the test**

```python
# tests/test_stub_newsroom.py
"""The whole pipeline must stay runnable with no model, no key and no network.
That property is what let v1's 380 tests survive a complete runtime change."""
import subprocess, sys, json, pathlib

def test_the_stub_newsroom_produces_a_front_page(tmp_path):
    out = subprocess.run(
        [sys.executable, "scripts/stub_newsroom.py", "--out", str(tmp_path)],
        capture_output=True, text=True, timeout=180)
    assert out.returncode == 0, out.stderr
    edition = json.loads((tmp_path / "edition.json").read_text())
    assert edition["lead"], "a front page needs a lead story"
    assert edition["lead"]["word_count"] >= 400
    assert edition["date"], "every edition is dated"
    for a in [edition["lead"], *edition["secondary"]]:
        assert a["dateline"] and a["published_at"]

def test_the_stub_newsroom_costs_nothing(tmp_path):
    """Guard against a future edit reintroducing a paid path."""
    src = pathlib.Path("scripts/stub_newsroom.py").read_text()
    assert "anthropic" not in src.lower()
    assert "ANTHROPIC_API_KEY" not in src
```

- [ ] **Step 2: Implement `scripts/stub_newsroom.py`**

Wire the real modules together with deterministic stubs:
- ingest: `wire.fetch()` (real, free) or a cached fixture with `--offline`
- scout: `emerge.cluster()` → `Proposal` → `beat_test`
- reporter: a stub that assembles 450 words from claim texts — **it must be
  obviously mechanical**, so nobody mistakes stub output for the real thing
- entailment: the `strict` verifier from Task 3
- editor: `run_editor` (real)
- render: `frontpage.play()` (Task 6)

- [ ] **Step 3: Run it and LOOK at the output**

```bash
python3 scripts/stub_newsroom.py --out /tmp/dz && cat /tmp/dz/edition.json | head -40
```

Expected: a lead story, secondaries, also-moving lines, all dated.

- [ ] **Step 4: Commit**

```bash
git add scripts/stub_newsroom.py tests/test_stub_newsroom.py
git commit -m "feat: stub newsroom runs the whole pipeline for free"
```

---

## Task 6: Front page play

**Files:**
- Create: `ledger/frontpage.py`
- Test: `tests/test_frontpage.py`

Key behaviours to test:

```python
def test_the_highest_scoring_article_leads(): ...
def test_beats_whose_article_was_refused_appear_as_one_line_entries(): ...
def test_a_day_with_no_surviving_article_still_publishes_a_page_that_says_so():
    """A day where nothing is publishable is a legitimate outcome and must be
    reportable as one. Silence and failure must not look the same."""
def test_refusal_counts_appear_without_refused_content(): ...
def test_secondary_is_capped_at_five(): ...
```

`play(articles, refused, holds, counts)` → `{lead, secondary, also_moving, did_not_publish, date}`.

- [ ] Steps: failing test → run → implement → pass → commit.

---

## Task 7: Article-first front page (HTML)

**Files:**
- Modify: `ledger/render.py` (project articles, not diffs)
- Rewrite: `index.html`
- Modify: `tests/test_render.py`, `tests/test_page_escaping.py`

**Carry forward from v1, do not regress:**
- escaping happens at DOM insertion (`H()`), never in the projection
- every route has a permanent hash URL
- the AI-generated / not-human-reviewed disclosure is sticky on every route
- counts come from the edition, never from the whole ledger

**New:** the field/value table moves *behind* each article at a stable URL, as
the reporting. It is no longer the page.

- [ ] Steps: failing test → run → implement → pass → commit.

---

## Task 8: The Claude Code adapter

**This is the only module that spawns an agent. It must never call a paid API.**

**Files:**
- Create: `ledger/claudecode.py`
- Test: `tests/test_claudecode.py`

```python
# tests/test_claudecode.py
def test_the_adapter_never_references_a_paid_api():
    src = pathlib.Path("ledger/claudecode.py").read_text()
    assert "anthropic" not in src.lower() and "api_key" not in src.lower()

def test_the_command_is_claude_dash_p():
    cmd = build_command("write the article", cwd="/tmp/x", allowed_tools=["Read"])
    assert cmd[0] == "claude" and "-p" in cmd

def test_a_nonzero_exit_raises_rather_than_returning_empty():
    """A failed agent must not look like an agent that found nothing."""

def test_output_is_parsed_as_json_when_requested(): ...
def test_a_timeout_raises(): ...
```

Implementation: `subprocess.run(["claude", "-p", prompt, "--output-format", "json", ...])`
with `cwd`, `--allowedTools`, `--append-system-prompt`, and an explicit timeout.
Returns parsed JSON or raises. No retries here — the caller decides.

- [ ] Steps: failing test → run → implement → pass → commit.

---

## Task 9: One real beat, read the output

**Do not schedule anything before this.**

- [ ] Run the real reporter against `nm-records` only (it has 17 documented claims already).
- [ ] Read the article. Judge the prose, not the plumbing.
- [ ] Check the entailment gate actually fired on something.
- [ ] Measure wall-clock and how much of the rate limit one beat consumes — spec §12 lists this as the top unknown.
- [ ] **Stop and show the operator before proceeding.**

---

## Task 10: Scheduling and the public repo

Only after Task 9 is approved.

- [ ] Verify no refused content is on disk anywhere (`grep` the ledger for refusal records carrying claim text) — spec §12 requires this before the first push.
- [ ] Confirm the Cloudflare token is not in the repo (`~/.config/doczero/cloudflare.env`, mode 600 — already verified).
- [ ] Create the public GitHub repo, push.
- [ ] Add the scheduled workflow. Start at **one beat**, then widen as rate-limit data arrives.
- [ ] `bash scripts/deploy.sh files` to ship. Never `nginx` again unless the vhost changes.

---

## Definition of done

- `python3 -m pytest tests/ -q` passes, and the count is higher than 380.
- `python3 scripts/stub_newsroom.py` produces a dated front page with a lead story, offline and free.
- No file in the repo references a paid API.
- The live site's md5s and nginx master pid are unchanged by any deploy.
