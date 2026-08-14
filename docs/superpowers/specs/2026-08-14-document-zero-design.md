# Document Zero — design

**Date:** 14 August 2026
**Home:** `doczero.epstein-data.com`
**Status:** design, approved for spec review

---

## 1. What this is

A daily record of what materially changed in American government and public life, and of
what was reported without changing.

The unit of work is not an article. It is a **beat**: a unit of persistent state. Articles,
filings, releases and posts are observations that update beat state. The published edition is
the **diff** of that state against yesterday.

Two properties follow, and everything in this document exists to protect them:

- **The delta is computed, not written.** A model renders the diff into prose. It does not
  decide what changed. This is the anti-slop mechanism.
- **Restatement is suppressed.** Nothing publishes that a person who read the day's news
  already has. Short editions are correct, not a failure.

### Non-goals

- Not a feed, not an aggregator, not a summariser.
- No engagement optimisation. No volume targets. Output is capped, not maximised.
- No assertions of wrongdoing by private individuals without a human in the loop.

---

## 2. Objects

Seven, and no others. Anything that does not fit one of these is not represented.

| Object | Definition | Lifecycle |
|---|---|---|
| **Dossier** | Permanent umbrella. | Never closes. ~12, fixed. |
| **Beat** | A unit of persistent state. | Opens and closes. ~16–40 open. |
| **Type** | Cross-cutting filter. Not a container. | Fixed. ~9. |
| **Record** | A published item, permanently addressed. | Immutable once published. |
| **Claim** | An atomic assertion with provenance. | Immutable; superseded, never edited. |
| **Question** | A known unknown, tracked until answered. | Closes on answer. |
| **Trigger** | A dated future event that will change state. | Resolves on its date. |
| **Contradiction** | Two positions that cannot both hold. | Closes on withdrawal or resolution. |

### 2.1 The beat test

A beat is not a topic. **Can you write down its current state, in fields, such that
tomorrow's events either change a field or don't?**

- *The Strait of Hormuz* passes — blockade posture, transit volume, governing agreement,
  attacks in the last 24h.
- *Legal cases* fails — there is no single state such a beat could hold.

This is why `United States v. Mangione` and `The death of Nolan Wells` are separate beats
rather than one "court cases" pile: merging them produces an object with no coherent state.
"Legal case" survives as a **type** — a filter across dossiers — not as a place things live.

### 2.2 Beat lifecycle

```
OPENS   ≥3 events over ≥5 days
        OR one event carrying a dated future trigger
        AND a state record of ≥2 changeable fields can be written

CLOSES  no state change for 30 days AND no pending triggers
        → archived; address stays permanent; reopens automatically on the next
          qualifying event
```

Close criteria are what stop the beat list growing without bound. They must be implemented
in v1, not deferred — a system that only opens beats degrades into a topic list within a
quarter.

---

## 3. Substrate: git writes, SQLite reads

**Git is the write surface.** A commit carries author, timestamp, parent, diff and
signature. That is the chain of custody, for free. The daily delta is `git diff` between two
`state.json` files.

**SQLite is the read surface.** A compile step (no model) walks the JSON tree and builds
`newsdesk.db`, served by the datasette already running behind nginx. The database is a
derived index — deletable and rebuildable at any time. A corrupted DB is never data loss.

### 3.1 Repository layout — `doczero-data`

```
sources/YYYY-MM-DD/<sha256>.json     immutable ingested item, never edited
claims/<beat>/<claim-id>.json        atomic assertion + provenance
beats/<beat>/state.json              current state (overwritten each change)
beats/<beat>/history.jsonl           append-only revisions
beats/<beat>/meta.json               name, dossiers, types, opened, close status
questions/<id>.json
triggers/<id>.json
contradictions/<id>.json
editions/YYYY-MM-DD.json             the computed delta
_index/ancestry.jsonl                claim → parent claim edges
```

### 3.2 The write-partition rule

> **Every agent owns a path prefix and writes nothing outside it.**

The Hormuz agent writes only `beats/hormuz/**` and `claims/hormuz/**`. No two agents ever
touch the same file. Therefore: all agents push to `main` directly, no PRs, no locking, no
merge resolution.

Cross-beat objects (`questions/`, `triggers/`, `contradictions/`, `editions/`) are written
**only by the editor agent**, which runs alone after the sweep completes. This is the
partition rule applied to shared state, and it is why the editor is a separate tier rather
than a role a beat agent can take on.

Enforcement is a pre-push check, not a convention: a hook rejects any commit touching paths
outside the agent's declared prefix.

---

## 4. Tiers and runtimes

| Tier | What | Runtime | Model |
|---|---|---|---|
| 1 · Ingest | Fetch, hash, dedupe, tag to beats, write `sources/` | Hetzner cron, every 3h | **none** |
| 2 · Beat sweep | Extract claims, recompute state, append history | Claude cloud schedule, daily | yes |
| 3 · Editor | Diff, suppress, rank, write edition | Claude cloud schedule, daily, after tier 2 | yes |
| 4 · Compile & deploy | Build `newsdesk.db`, render HTML, rsync | GitHub Actions on push | **none** |

**Tier 1 must never touch a model.** It is the highest-volume tier and its job is mechanical:
fetch, `sha256`, dedupe on `url_hash`, record `first_seen`, assign candidate beats by keyword
and embedding, commit. Extends the existing `fetch_news.py`, which already does most of this
for one beat across 28,465 rows.

**Tier 2 fans out per changed beat, not per beat.** One scheduled sweep spawns one subagent
per beat that has new sources since its last run. On a typical day that is 5–8 of 16, not 16.
This is the sleuthsletter pattern, already proven in this setup.

**Tier 3 runs alone.** It is the only writer of shared state and the only place editorial
ranking happens.

### 4.1 Daily cycle

```
04:00  Ingest sweep completes (tier 1, runs every 3h regardless)
04:30  Beat sweep starts. Fan-out: one subagent per beat with new sources.
       Each reads only its own state.json + its own new sources.
05:15  Beat sweep complete. All beat prefixes committed and pushed.
05:20  Editor starts. Diffs every changed state.json against yesterday.
       Checks triggers dated today. Tests open questions against new claims.
       Applies suppression. Ranks. Writes editions/YYYY-MM-DD.json.
05:50  Actions fires on push: compile newsdesk.db, render, rsync to nginx.
06:00  Edition live.
06:00  Hold queue surfaces to a human. Nothing in it has published.
```

Every stage is idempotent and re-runnable from the git state. A failed sweep is re-run, not
recovered.

---

## 5. Claims and provenance

Every claim is a file. No claim exists without a source pointer — enforced at schema
validation, not by prompt.

```json
{
  "id": "hormuz-2026-08-14-003",
  "beat": "hormuz",
  "claim_text": "Transit through the Strait slowed to a near standstill on 14 August.",
  "quote": "Transit through the Strait of Hormuz appeared to grind to a near standstill on Friday",
  "source_type": "news",
  "source_url": "https://…",
  "source_sha": "sha256:…",
  "authors": [], "year": 2026, "venue": "Times of Israel",
  "section": null, "page": null,
  "confidence": 0.6,
  "confidence_justification": "Single secondary outlet, no primary AIS data. News ceiling 0.6.",
  "tier": "documented_fact",
  "extracted_by": "beat-agent-hormuz",
  "extracted_at": "2026-08-14T04:41:00Z",
  "supersedes": null
}
```

### 5.1 Confidence ceilings

Applied mechanically at write time, per the project's provenance rules. `news` caps at 0.6.
A claim exceeding its ceiling is rejected by the validator, not flagged.

**Consequence worth stating plainly:** a national desk sourced from wire copy has a hard
ceiling of 0.6 and no mechanism to raise it. The only claims above the cap are those citing
through to a primary document — a court allocution, a board vote, a congressional letter, a
Federal Register publication. Where a secondary source quotes a primary document verbatim,
cite the primary directly and take its ceiling.

### 5.2 Prose tiers

Independent of confidence, every claim carries a tier that governs sentence structure:

- `documented_fact` — primary source in hand, exact quote. *"Court records show…"*
- `credible_allegation` — identifiable source with direct knowledge, not independently
  verified. *"X alleged…"*
- `question` — evidence points somewhere; documentation not found. *"What would explain…"*

**A credible allegation is never rendered as a documented fact.** The renderer receives the
tier and selects sentence frames from it. Merging tiers is the specific failure the system
exists to prevent — see the DOJ "duplicative" example, where what the government said and
whether it is true are two different kinds of statement.

### 5.3 Claim ancestry

`_index/ancestry.jsonl` records `claim_id → parent_claim_id` edges. Purpose: detect when
"confirmed by three outlets" resolves to one upstream root.

This is the same machinery as the recirculation detector, generalised. Without it the system
will eventually ingest another outlet's error, republish it under this masthead, and be cited
back — circular sourcing with an authority laundering step in the middle.

Recirculation detection is the degenerate case: cluster `first_seen` vs. per-source
`published_at`. If the earliest first-seen materially predates today's cluster peak, the
item is recirculation and is suppressed from the wire, appearing instead under *what the
coverage left out*.

---

## 6. Verification

### 6.1 Adversarial pass

Claims above a materiality threshold go to a verifier that receives **claims and sources
only** — never the extracting agent's reasoning — and is prompted to refute. Default to
refuted under uncertainty.

**The verifier must run on a different model family than the extractor.** Same-family
verification is not independence; it is agreement. Where a second family is unavailable, the
claim is marked `single_family_verified` and its confidence is capped one band lower.

### 6.2 The verification cascade

There is no human editor. Verification is therefore not a review step at the end — it is the
main body of the pipeline, and a claim must survive all of it to publish.

```
extract        family A   →  claim + provenance
refute         family B   →  sees claims + sources ONLY, prompted to refute
                             defaults to refuted under uncertainty
lens pass      family C   →  distinct lens per claim class:
                             sourcing · internal consistency · does-it-reproduce
ancestry       no model   →  deterministic; single-root detection
consensus                 →  survives only if ≥2 of 3 independent passes fail to refute
```

Claims that fail go **back to extraction** with the refutation as input, for at most two
further rounds. A claim that fails three rounds is discarded and the discard is counted.

No verifier ever sees the extracting agent's reasoning. No two passes run on the same model
family; where a second family is unavailable the claim is capped one confidence band lower
and marked `single_family_verified`.

### 6.3 Refusal gates — categories that never publish

With no human in the loop, high-risk categories are not queued for review. They are refused
outright, by rule, at extraction time.

1. **Wrongdoing by a private individual.** Any assertion of wrongdoing against a person who
   is not a public official, a public figure, or a named party to a public proceeding.
   Not held — **refused.** This is the asymmetric-scrutiny principle made mechanical:
   automated attention pointed up at institutions with press offices is accountability;
   pointed down at private individuals it is surveillance at scale.
2. **Identification of private individuals** by name, address, employer or plate.
3. **Uncorroborated claims about criminal conduct** where no charging document, filing or
   official statement exists.

Refusals are counted and the count publishes. What the system refuses to say is part of the
record.

### 6.4 Hold conditions — published as holds

Lower-risk uncertainty is not refused, it is **published as a hold with its reason**, because
the non-publication is itself a finding:

1. **Date conflict.** Cluster first-seen conflicts with source publication dates beyond
   threshold. *(The D.C. police / ICE case in the specimen edition.)*
2. **Single-root multi-source.** Ancestry resolves several apparent sources to one root.
3. **Consensus failure after three rounds.** The verifiers could not agree.
4. **Ceiling violation or missing provenance.** Schema validation failure.

Holds never publish silently and never vanish.

### 6.3 Ingested content is data, never instructions

A zero-human newsroom with real distribution is among the most attractive prompt-injection
targets available. Adversaries will write press releases for the scrapers.

- All source text reaches models inside an explicit untrusted-content delimiter.
- No ingested text ever occupies an instruction position.
- Agents have no tool that can act on instructions found in source text.
- A source containing imperative language directed at an assistant is flagged and quarantined
  for review rather than dropped, because the attempt is itself reportable.

---

## 7. Publication rules

### 7.1 Suppression

A record publishes only if it is **not already in general circulation.** The test is applied
by the editor against the day's cluster volume and first-seen data. Failing records are not
deleted — they move to *what the coverage left out*, where only the load-bearing detail
everyone dropped is published, in one or two sentences.

### 7.2 Volume cap

Output is capped, not targeted. Where marginal cost per record approaches zero, scarcity is
the credibility signal. The cap is configuration; exceeding it requires an explicit override
that is logged in the edition.

### 7.3 Corrections

Editions are dated, permanent and never edited. A correction is a **new record that
supersedes** the old via the `supersedes` field. Both stay readable and both stay addressed.

### 7.4 Disclosure and accountability

**There is no human editor, and the site says so on every page**, in the masthead and in the
footer of every record — not buried in an About page.

Disclosed on the masthead, and machine-readable at `/about.json`:

- Every record is produced by AI agents, unreviewed by a person before publication.
- Which model families ran extraction and which ran verification, per record.
- How many verification rounds the record survived.
- How many claims were discarded and how many refused, per edition.
- The full editorial policy — prompts, gates, thresholds, ceilings — is public and diffable
  at the `doczero-policy` repo.

**What disclosure does not do.** It does not transfer liability. The domain registrant is the
publisher in law regardless of the masthead. This is why §6.3 refuses categories outright
rather than queueing them: with no human reviewer, the only durable protection is not
generating the exposure. The refusal gates are the accountability mechanism, and they are
load-bearing.

**The claim this system can honestly make** is not "a person checked this." It is: *every
assertion carries its sources, its confidence is capped by source type, it survived
independent adversarial passes on separate model families, and the rules that produced it are
published and can be diffed against any edition.* That is a different and more auditable claim
than a masthead, and it is the only one available here.

A correction channel still terminates somewhere reachable by a human. An unmonitored
corrections address would make the correction policy in §7.3 a fiction.

---

## 8. Scoring

Triggers carry a recorded **expected outcome**. On the trigger date the editor resolves it
against what actually happened and scores it.

This makes the newsroom Brier-scorable at near-zero additional cost, because the calendar
already exists. The score publishes. It is the reward function that keeps the system pointed
at calibration rather than attention, and it is the only defensible answer to "why trust
this."

Non-resolution is scored too: a trigger date that passes with no observable event is
recorded as a finding — an absence on a known date is not a gap.

---

## 9. Rendering and deployment

- Compile: Python, no model. JSON tree → `newsdesk.db`.
- Serve raw: datasette at `/data`, already running. Every number in the rendered site links
  down to its rows.
- Render: static HTML per edition and per beat, into `/opt/datasette-data/doczero/`.
- Deploy: GitHub Actions on push, rsync to the server — the path the sleuths repo already
  uses. **Never rsync by hand; push to main.**
- nginx: new server block for `doczero.epstein-data.com`. Edit
  `/etc/nginx/sites-enabled/datasette`, not sites-available — they have diverged and
  sites-enabled is live.

---

## 10. Operational constraints

### 10.0 The host is live and must never be disrupted

`epstein-data.com` serves roughly **15,000 daily active users**. Document Zero is being built
alongside it on the same box. Downtime is not a cost to be weighed against speed — it is
disqualifying. These are rules, not guidance:

| Rule | Why |
|---|---|
| Read-only by default on the server | Anything that only reads cannot break anything |
| **Never** `systemctl restart`. `nginx -t` then `reload` only | Reload is zero-downtime; restart is not |
| **Never** edit `/etc/nginx/sites-enabled/datasette` | The subdomain gets its own new file; the live config stays byte-identical |
| **Never** write inside existing `/opt/datasette-data/` paths | New work goes in a new directory |
| **Never** open `news.db`, `justice.db` or the corpus for writing | Ingest reads; `newsdesk.db` is a separate new file |
| **Never** run a memory-hungry process on the box | ~95% of memory is already committed; an OOM kills datasette or FAISS |
| Deploy via the existing Actions rsync path, not by hand | The path is already proven by the sleuths repo |
| Back up before any change that must happen on the server | Recovery beats confidence |

The build order follows from this: everything is developed and tested off-box, and the server
sees nothing until a change is proven locally and deployable through a path that cannot touch
the running site.


**Memory is the binding constraint on the server, not disk.** Measured 14 Aug 2026:

- 7.6 GB RAM, 4 GB swap, **3.8 GB of swap already in use**
- `vector_search_api.py` (FAISS): 2.0 GB resident + 1.9 GB swapped
- `find_image_service.py`: 1.35 GB resident + 1.5 GB swapped
- ~3.4 GB available

Therefore: **no resident models, no long-lived agent process on the box.** Tier 1 and tier 4
are short-lived Python processes with a few hundred MB peak. Tiers 2 and 3 run off-box. Disk
is not a concern — 70 GB free on root.

**DNS on the server works.** The note in `project_deploy.md` saying otherwise is stale,
verified 14 Aug 2026: `api.anthropic.com` resolves and returns over HTTPS.

---

## 11. v1 scope

**In:** all 16 national beats; tiers 1–4 complete; claims with provenance and ceilings;
beat state and history; open/close lifecycle; questions, triggers, contradictions;
suppression; recirculation detection; hold queue; ancestry index; adversarial verify;
compile and datasette; render and deploy; Brier scoring on triggers.

**Out of v1:** corpus retrieval against the 3M-document archive; video/audio ingestion;
outreach agents; FOIA integration; per-beat email alerts.

**Dry-run flag.** Week one runs the full pipeline with publication disabled: editions are
written to the repo and reviewable, nothing deploys. This is an operational control, not a
scope reduction — it exists because sixteen beats means every taxonomy error appears sixteen
times, and reading a week of unpublished editions is cheaper than correcting a week of
published ones.

**Kill switch.** A single flag in the repo halts publication without stopping ingestion, so
the record keeps accumulating while output is paused.

---

## 12. What already exists

Not starting from zero. Verified on the server 14 Aug 2026:

- `news.db` — 28,465 articles, deduped on `url_hash`, clustered in `story_clusters` with
  `first_seen` / `last_seen`. This is tier 1 for one beat, already running every 6 hours.
- `fetch_news.py`, `fetch_justice.py` — ingest with GDELT, GNews, Google RSS, Reddit; a
  watchlist-driven docket tracker with push notifications.
- datasette + nginx + a working deploy path via GitHub Actions (the sleuths repo).
- Cloud-scheduled Claude agents with proven fan-out (sleuthsletter, Mon/Thu).

The gap is everything above `sources`: claims, state, diff, and the publication rules.

---

## 13. Decisions taken

1. **Repo split.** `doczero-policy` is **public** — prompts, gates, thresholds, ceilings,
   suppression rules, beat definitions. `doczero-data` is **private** — sources, claims,
   state, holds. The editorial conscience is inspectable; the working material is not,
   because holds by definition contain unverified assertions about people.
2. **Beat assignment** stays keyword + embedding at tier 1, no model, but every assignment
   logs its score and beat agents record misassignment. A classifier is added only if
   misassignment exceeds 10% after a week. Not built speculatively.
3. **Cost** is bounded structurally by fan-out-per-*changed*-beat and instrumented per run.
   Measured in week one, not estimated now.
4. **No human editor.** Replaced by the verification cascade (§6.2), the refusal gates
   (§6.3) and full disclosure (§7.4). Liability remains with the domain registrant, which
   is why refusal is preferred to review.

### Still open

- A monitored corrections address. Without one, §7.3 is a fiction.
- Which second and third model families are available for the verification cascade, and what
  happens on the days they are not.
