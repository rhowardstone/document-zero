# Standards

The editorial constitution. Every routine reads this first, every run.

**This file is human-owned and changes only by hand.** It is deliberately *not*
writable by any routine — and specifically not by the scout, whose entire job is
reading the untrusted open wire. The verification rules, the privacy rules and
the process-narration policy must not sit inside the writable scope of the
routine most exposed to hostile input, guarded only by attention on a daily,
usually-boring pull request. Boring-PR fatigue is how a poisoned hunk ships.

The roster lives in `beats.yaml`, which the scout may change by PR. This file
says what counts; that file says what we cover. CI enforces the split.

---

## 1. The disclosure

This exact string appears in the masthead and the footer of every edition, at the
top of every Delta, and at the top of every Substack draft. Four prompts invoke
"the disclosure in its fixed wording"; this is the wording. Do not paraphrase it,
do not shorten it, do not work it into the body of a story.

> **AI-generated · not reviewed by a human.** Every claim here was extracted from
> public sources and checked against them by language models. No editor read this
> page before you did.

That is an ethical duty to the reader, not a description of tooling, which is why
it is the one permitted exception to the rule below.

---

## 2. No process narration

**Canonical statement. The routine prompts reference this section rather than
restating it, so the wording cannot drift between them.**

Readers are not engineers. They don't know what a 403 is, they don't know what a
verifier is, and they don't care. Talk only about what you found — never about
what you couldn't reach or couldn't establish.

None of this may appear in anything published:

- "no article survived this cycle", "no story written for this beat"
- "the claim could not be verified", "unverified this cycle"
- "N beats quiet", "no change to report"
- "the feed returned nothing", "inaccessible", "rate-limited"
- any mention of feeds, fetches, paywalls, login walls, timeouts, rate limits,
  models, verifiers, subagents, refusals, or this repository

Not even one clause tacked onto an otherwise-fine sentence. If a beat had nothing
to report, don't mention that beat — omit it silently. Immediately before your
final commit, re-read everything you wrote hunting specifically for this pattern
and cut what slipped through. That pass is mandatory.

**Everything you could not do belongs in your run summary,** which goes in the
heartbeat ping body where an operator reads it. Never on the page.

---

## 3. Never render a failure to know as a fact about the world

Every serious bug this project has had was this. A rate-limited history lookup
became "this story is 2 days old". An unrecognised publisher became "source
unclassifiable". A crashed agent became "the beat was quiet". A hardcoded noon
became the publication time.

If you could not measure something, say nothing about it publicly and record the
gap in your run summary. Never print a placeholder that looks like data — an
em-dash where a timestamp belongs is indistinguishable from a real value.

---

## 4. Confirmation

**If a finding cannot be confirmed, drop it entirely.** If it is confirmed but
contested, state it plainly with attribution. Do not hedge in public.

The earlier wording — "either state it plainly or drop it entirely" — read as
permission to state unconfirmed findings, which is the opposite of the intent.
The intent was anti-hedging, not anti-verification.

---

## 5. Verification

**Two verifiers per factual sentence, blinded, with different jobs.** Each sees
only the sentence and the evidence — never the writer's reasoning, never the rest
of the piece.

- **A:** does this evidence support the sentence as written?
- **B:** state the strongest reason the sentence overreaches its evidence — a
  dropped attribution, a missing qualification, a date that doesn't match, a
  stronger claim than the source makes.

Both say no, or they disagree: **cut the sentence.** A verifier errors: re-run
once, then cut. **Never rewrite a sentence to get it past a verifier** — that
produces prose optimised against the check rather than supported by evidence.

**Verification covers, explicitly:** every sentence making a factual claim, the
headline, the standfirst, and every `was`/`now`/`attested` triple. The last three
are not sentences and would otherwise escape on a technicality, and they are the
most load-bearing claims written — the headline is what most readers read, and a
wrong `was:` propagates into every future issue.

**For load-bearing claims, verifier B gets the source URL rather than the
writer's excerpt** and locates the support itself. The writer chose the passages,
and motivated selection survives blinded review: an article can say "X happened"
in paragraph 4 and "investigators later determined X had not happened" in
paragraph 12.

### Causal and surprising claims need two origins

A firing "caused by" X. A resignation "in response to" Y. A document that
"proves" Z. Tag these sentences, and **their verifier packet must contain
passages from two independent reporting origins** or the sentence is cut. A
single source that does state the connection would otherwise pass both verifiers
while violating this rule.

### Claims of non-occurrence

"The deadline passed without the required filing" is epistemically different from
ordinary reporting, because proving absence requires having checked the
authoritative universe. **A search failing to find something is not evidence that
it does not exist.**

Such a sentence survives only if somebody inspected the authoritative record —
the docket, the agency register, the official calendar — after the deadline. The
verifier's question is: *does this evidence establish absence, or does it merely
fail to show presence?*

### Never supply a link the sources don't make

Joining two facts with "and its formal request" asserts one produced the other.
If the sources don't say two things are connected, write two sentences. A
connection you supplied yourself is the commonest way a paragraph here turns out
to be wrong, and cross-beat synthesis is where it feels most like observation.

### Document citations

Every EFTA/Bates citation is probed before publishing:
`https://epstein-data.com/full_text_corpus/pages.json?efta_number=<ID>&_shape=array&_size=1`.
Empty means the number may be a stamp on a page inside a differently-numbered
document — search `https://epstein-data.com/api/corpus/search/<ID>`, cite the
document that actually contains it, or cut the citation.

---

## 6. Naming people

**Public figures may be named in connection with alleged wrongdoing:** office
holders, candidates, executives acting in their corporate capacity, and people
who have sought public attention on the matter at hand.

**Party status alone does not make someone a public figure.** Being sued, or
suing, does not make a private person public. A private litigant may be named
only where their identity is independently newsworthy.

**Never identify a protected person because a filing does.** Victims, witnesses,
minors, and relatives of the above are not named and not identified — including
by detail specific enough to identify them — even where a court document, a
police report, or another outlet names them.

Where this is breached, it is urgent: the critic escalates it at the top of its
run summary rather than only filing an issue.

---

## 7. State fields

A beat is a unit of **persistent state**, not a topic. Its fields must be about
the world, and each must be able to *fail* to change.

**Clock-derived fields are display values, never movement.** "Days at sea", "days
since last port call", "time to midterms" increment by definition. A beat resting
on them is due in every issue forever, which permanently inflates the delta's
"three or more beats are due" threshold and quietly destroys the adaptive cadence
that the delta exists for.

So: **a field changes only when a source-attested event changes it.** The clock
turning over is not an event. Keep such fields if they are useful to a reader —
mark them `clock: true` in the roster — and never count them as movement.

**Fields about our own records are forbidden entirely.** "Most recent claim",
"Claims on record", "Last updated" teach a reader nothing and can never fail to
change. `scripts/lint_beats.py` rejects them.

**Delta due-ness is story-driven.** A beat is due if and only if a desk published
a story for it since its last appearance in an issue. Stories are already the
change ledger; keying cadence to them makes it computable from the repository and
immune to ticking fields.

---

## 8. Slugs and names

**The slug is the identifier and never changes.** History lives under it, so
renaming a beat orphans everything already published about it.

**The name is display and may change freely.** A divergence between a beat's name
and its slug is therefore expected and correct — it means the story was renamed —
and must not be read as a duplicate signal when comparing entities.

Never show a reader a slug.

---

## 9. Sources

**Publisher-direct, never aggregator-wrapped.** An aggregator wrapper hides the
real publisher, which has caused a misclassified source three separate times.
This includes our own corpus API: `epstein-data.com/api/corpus/news` is a
**discovery layer only** — find the story there, then open and cite the
underlying publisher.

**Record the origin, not just the publisher.** Twelve papers running one AP wire
story is one reporting origin; a signed court order available only from the court
is one origin that outranks all twelve. Every source entry carries:

```yaml
- url: <url>
  publisher: <who published this page>
  origin: <who did the reporting: the wire, the outlet, or the institution>
  source_type: primary_document | original_reporting | wire_republication | analysis
```

Corroboration counts origins. Ranking is by consequence, with corroboration as
evidence — not as importance.

**Read the article, not the headline.** A feed carries about forty words per
report; claims built on forty words are fragments that produce prose saying
nothing. Open the piece. Open embedded document scans, charts and photographs and
describe what they actually show rather than what the caption claims.

**Check every candidate's real publish date.** A headline that looks like today's
news is often two months old wearing a today's-date snippet.

Per-desk feeds are in `beats.yaml` under `sources:`, so a researcher reads the
feeds relevant to its beat rather than wading through all of them.

---

## 10. The beat test

**A beat opens** when it has, in `curation/candidates.json`:

- at least three events over at least five days from three independent reporting
  origins, **or** one authoritative primary source establishing a dated
  obligation, **and**
- at least two non-clock fields tomorrow's events could plausibly change.

The second condition does the work. The question is not "is this interesting" but
"can I write this thing's current condition as fields, such that tomorrow's
events either change one or don't".

**Stricter test, applied to every proposed beat:** complete the sentence *"the
current state of this beat is fully described by these fields: …"*. If the field
list reads like five unrelated newspaper desks emptied onto a table, the beat is
too broad and is really a topic. That is how a state-based roster degenerates back
into sections called "Trump", "Democrats" and "DOJ".

**Tiers.**

- `standing` — a continuing institution or condition, expected to stay relevant
  indefinitely. Closes after 30 quiet days with no pending obligation.
- `watch` — event-driven, expected to terminate on resolution. Closes after **10**
  quiet days. Promote to `standing` only on passing the full beat test afresh.

A beat with a pending dated obligation is not quiet, it is waiting, and does not
close on either clock.

**If you cannot measure how long a story has run, defer it — do not reject it.**
Recording a failed lookup as "one day" states something the record does not know.

---

## 11. Dated obligations

A deadline passing with nothing filed produces no headline anywhere, which makes
it the one thing a reader cannot get from the wire. It fires a Delta issue on its
own.

That only works if the obligations are written down. Every one lives in
`beats.yaml`:

```yaml
deadlines:
  - date: 2026-09-05        # ISO, or it can never lapse
    what: <what is expected to happen>
    why: <why it matters>
    authority: docket | register | calendar   # where absence must be checked
```

`authority` is what makes a non-occurrence claim verifiable under §5.
