# Document Zero v2 — the newsroom writes

**Status:** design, approved 2026-08-16
**Supersedes:** parts of `2026-08-14-document-zero-design.md` (v1). Where the two
disagree, this document wins. Where this document is silent, v1 still holds.

---

## 0. What went wrong in v1, stated plainly

v1 shipped and was wrong in two ways that no amount of polish would have fixed.

**The backend was rendered as the front end.** v1's central artifact was a
before→after diff of state fields:

```
Records sought   was  Unredacted Epstein investigative files
                 now  Unredacted 'Epstein Library' records, EFTA §2(a)(1)-(9)
```

That is a database row. It is how the system should *think*; it is not what a
person reads. A reader wants a sentence, a dateline, and a reason to care. v1
had none of the three, and the effort went into typography for a changelog.

**The machine was never fed.** `config/beats.yaml` declared 22 beats with
keyword lists, and ingestion pulled only what matched them. Twenty sat
permanently empty. The single feed that existed queried one subject, so the
corpus was 96% that subject and the front page showed two beats, both of them
the same story. A system whose coverage is a list someone typed cannot discover
anything.

Both failures share a root: v1 treated its internal representation as the
product, and its author's guesses as the world.

**What v1 got right and survives untouched:** the ledger, claim provenance,
confidence ceilings by source type, the adversarial verification cascade, the
refusal gates, the write-partition rule, the query API, and the static-file
deployment path. Those were correct. They are the newsroom's memory. They were
just never given a writer.

---

## 1. The reframe

> The ledger is the newsroom's memory. It is not the newspaper.

A state change is the **input to a reporter**, not the output to a reader. What
publishes is what a reporter wrote *from* that change, with the state table
demoted to the reporting behind the story.

Every v1 mechanism keeps its job. The diff still decides *what is worth
writing about*, still suppresses recirculation, still proves the system is not
merely restating a feed. It simply stops being the thing on the page.

---

## 2. Runtime: Claude Code instances, never a metered API

**There is no paid API path in this project.** `ledger/client.py`,
`scripts/live_run.py` and `tests/test_client.py` were deleted on 2026-08-16;
`ledger/NO_PAID_APIS.md` is the tombstone. The operator was billed $0.36 without
consent on 2026-08-14 and that must never recur.

Every agent in this system is a **Claude Code instance** running on the
operator's existing subscription. Cost is not a variable. The binding constraint
is rate limits and wall-clock, which changes the engineering: parallelism is
cheap, retries are cheap, and a run that has to be repeated costs patience
rather than money.

```
GitHub (public repo) — the shared write surface. Every change is a commit.
      │
  ① ingest         no model.  GDELT DOC 2.0 + Google/Bing News RSS,
      │                       per-beat queries. Free, no keys.
      │
  ② beat agents    Claude Code, N in parallel. Each owns beats/<id>/ and
      │            writes nothing outside it. May spawn its own subagents
      │            to pull a docket, a filing, a dataset.
      │
  ③ scout          Claude Code. Proposes new beats; closes quiet ones.
      │
  ④ editor         Claude Code, runs ALONE after all beat agents finish.
      │            Plays the page, kills recirculation, enforces refusals.
      │            The only writer of editions/.
      │
  ⑤ build + ship   no model.  Render, then rsync static files to the host.
```

### 2.1 The live host runs no agents

`epstein-data.com` serves ~15,000 people a day from a box with ~3.4 GB free.
It has no Node runtime and will not get one. It receives 856 KB of static files
over rsync and nothing else. See v1 §10.0, which still governs.

### 2.2 Scheduling

Scheduled cloud runs, centrally managed through the GitHub repository. Daily
cadence. The runtime is deliberately swappable: every agent is invoked as a
subprocess with a prompt and a working directory, so moving between local cron,
Claude Cloud and GitHub Actions is a launcher change, not a redesign.

---

## 3. The article — the new central artifact

A beat that moved materially produces an **article**, stored at
`beats/<id>/articles/<YYYY-MM-DD>.json`:

```json
{
  "beat": "fed",
  "day": "2026-08-16",
  "headline": "Fed signals a hold as September decision nears",
  "standfirst": "Two governors break with the chair in remarks a day apart",
  "dateline": "WASHINGTON",
  "published_at": "2026-08-16T14:02:00Z",
  "paragraphs": [
    {"text": "Federal Reserve officials moved further apart this week over…",
     "claims": ["fed-2026-08-16-a1b2c3", "fed-2026-08-15-9f8e7d"]}
  ],
  "changed": [{"k": "Governors dissenting", "from": "1", "to": "3",
               "since": "2026-08-14"}],
  "written_by": "claude-code/beat:fed",
  "verified_by": ["claude-code/entail:1", "claude-code/entail:2"],
  "word_count": 612
}
```

Rules:

- **400–800 words.** Below 400 there was no story; above 800 the reporter is
  padding. Outside the range the article is rejected and the beat degrades to a
  one-line entry.
- **Every paragraph cites the claims it rests on.** Not shown to the reader;
  used by the entailment gate and available in the API.
- **A dateline and a timestamp are mandatory.** A news page without dates is not
  a news page. v1 shipped without them and it was the first thing a reader
  noticed.
- **`changed` is the diff**, carried for display under the article and for the
  editor's ranking. It is no longer the article.

---

## 4. The entailment gate

This is the hard part and the reason this design is worth writing down.

A state field either matches the docket or it does not. A 600-word article can
introduce a causal claim, an implication, or a single adjective that no source
supports, and it will read fluently while doing so. Fluency is not accuracy, and
an automated newsroom with no human editor cannot rely on anyone noticing.

**The gate:**

1. The writing agent produces the article with per-paragraph claim citations.
2. A **separate** Claude Code instance receives *the article text and the cited
   claims only*. It never sees the writer's reasoning, the sources beyond the
   claims, or the beat's history. Asymmetry of information is the point: a
   verifier that can see the writer's justification will adopt it.
3. It marks each sentence `entailed` or `not_entailed`, with the claim it rests
   on or the reason it fails.
4. A second instance from a different model line repeats the check independently.
5. **Any sentence marked not-entailed by either verifier refuses the whole
   article.** The beat falls back to a one-line "also moving" entry naming what
   changed, which is a bare fact and needs no prose to support it.
6. Ambiguity resolves to not-entailed.

Refusing the article rather than editing the sentence is deliberate. An article
patched to survive a check is an article optimised against the check.

**Known limit, to be stated on the site:** the verifiers are Claude Code
instances from the same vendor as the writer. Different model lines are the
strongest independence available here and are weaker than two newsrooms. v1
already discloses this for claims; it now applies to prose.

---

## 5. Beats come from the news, not from a file

v1's beats were 22 lines of YAML. They could not open and could not close, which
is why coverage never grew and never shrank.

**The scout** runs after ingest and before the beat agents. It reads the day's
unassigned wire and proposes beats.

A proposal is **opened** when it meets the v1 §2.1 beat test — which is retained
verbatim because it was correct:

- ≥3 events over ≥5 days, **or** one dated trigger (a filing deadline, a
  scheduled vote, a hearing), **and**
- ≥2 state fields that tomorrow's events could change.

A proposal that fails is recorded as rejected, with the reason, so the record
shows what was considered and not merely what was covered.

A beat **closes** after 30 days with no material change and no pending trigger.
Closed beats keep their pages and their URLs; they stop being polled.

The existing 22 become a **seed**, not a ceiling.

### 5.1 Coverage is not "all the news"

This is an accountability publication, not a wire service. The beat test itself
enforces the boundary: a thing with no changeable state — a match result, a
product launch, a weather event that resolves in a day — cannot become a beat.
Breadth comes from the scout finding institutional stories nobody listed, not
from covering everything that happened.

---

## 6. The front page

The editor runs alone, after every beat agent has finished, and is the only
writer of `editions/`.

**Play** is ranked by the v1 §8 score — consequence × material change ×
corroboration — with recirculation suppressed as in v1 §7.1:

- **Lead**: one article, full text.
- **Secondary**: 3–5 articles, headline + standfirst + first paragraph.
- **Also moving**: one line per beat that changed but whose article was refused
  or ranked below the fold. Bare facts, no prose.
- **What did not publish**: holds and refusal counts, with reasons and without
  refused content. Retained from v1; it is the strongest thing on the site.

If no article survives its entailment gate, the front page says so. A day with
nothing publishable is a legitimate outcome and must be reportable as one.

---

## 7. Write partitioning

Retained from v1 §3.2 and now load-bearing, because N agents run concurrently:

| Agent | May write |
|---|---|
| ingest | `sources/` |
| scout | `proposals/` |
| beat agent `<id>` | `beats/<id>/` only |
| editor | `editions/` only |
| build | `site/` (generated, never hand-edited) |

An agent that writes outside its prefix has its commit rejected. This makes 22
concurrent writers safe without locking, and makes every change attributable to
a named agent in git history.

---

## 8. Failure modes and what happens

| Failure | Behaviour |
|---|---|
| Beat agent errors or times out | Beat renders as **unresolved**, not quiet. An unexplained absence must never look like a still day. |
| Article fails entailment | Article refused; beat degrades to a one-line entry. Counted and shown. |
| Article outside 400–800 words | Rejected as above. |
| Scout proposes nonsense | Fails the beat test, logged as rejected with reason. |
| Ingest returns nothing for a beat | Beat is quiet. Quiet is a valid state and is labelled, not hidden. |
| Editor errors | No edition is published. The previous day's page stays up with its own date visible. Never publish a partial edition. |
| Rate limit hit mid-run | Run aborts before the editor. No edition published. Retry is free. |
| Two agents race the same path | Impossible by partition; if it occurs, the commit is rejected and the run fails loudly. |

---

## 9. Testing

The pipeline must remain fully exercisable **for free**, as it is today: 380
tests, no credentials, no network.

- **Agent boundaries are callables.** Every Claude Code invocation sits behind an
  injected function, so tests substitute deterministic stubs. This is why v1's
  tests survive the runtime change unaltered.
- **The entailment gate gets adversarial fixtures**: articles containing a
  sentence supported by nothing, a sentence that overstates its claim, a
  sentence true but uncited, and a correct article. The gate must refuse the
  first three and pass the fourth.
- **The scout gets beat-test fixtures**: proposals that should open, proposals
  that should be rejected for too few events, and for having no changeable
  state.
- **Write-partition violations are tested**, not assumed.
- **The stub reporter** replaces `scripts/dryrun_real.py`'s stub extractor and
  exercises the whole path — ingest → scout → beats → editor → render — with no
  model and no cost.

---

## 10. What is deleted

- The field/value front page. It becomes the **record view** behind each
  article, at a stable URL, which is where it always belonged.
- `ledger/client.py`, `scripts/live_run.py`, `tests/test_client.py` — already
  deleted. No metered API path may be reintroduced.
- `config/beats.yaml` as a source of truth for coverage. It becomes a seed file.

## 11. What survives unchanged

The ledger and its schema, claim provenance and quote verification, confidence
ceilings by source type, prose tiers, claim ancestry, the verification cascade,
the refusal gates and the subject resolver behind them, the suppression and
volume rules, the query API and `llms.txt`, the compiled SQLite, and the
static-file deploy path with all of its safety rails.

---

## 12. Risks

- **Rate limits, not money, now bound the system.** 22+ beat agents plus
  subagents plus two verifiers per article is a lot of concurrent Claude Code.
  Unknown until measured. Mitigation: agents are independent and the run is
  resumable; a partial run publishes nothing rather than something wrong.
- **The verifiers share a vendor with the writer.** Disclosed, not solved.
- **The scout could drift** toward whatever is loudest. The beat test is the
  brake, and rejected proposals are recorded so drift is visible.
- **A public repo publishes the newsroom's internals**, including hold reasons
  and refusal counts. Refused *content* is never written to disk — the gate
  refuses at extraction — but this must be verified before the first push.
- **Prose quality is unknown.** Nothing in this design guarantees the writing is
  good, only that it is supported. Read the first real output before scheduling
  anything.

---

## 13. Open questions

1. Cadence beyond daily — does a dated trigger firing mid-day warrant an
   out-of-cycle run?
2. Corrections: v1 supersedes claims rather than editing them. What does a
   correction to a published *article* look like on the page?
3. How many beat agents can run concurrently before rate limits bite? Measure
   before scheduling.
