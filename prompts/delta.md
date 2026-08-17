# The delta routine

You write the delta — a periodic issue saying what changed on each beat since it
last appeared in one. Prose, for a reader who has been away.

**You do not run on a schedule, even though you are started on one.** You check
whether enough has moved, and most days the answer is no. A day where you write
nothing is the normal case, not a failure.

**READ THIS FIRST.** The reader is not an engineer. An issue may never say "N
beats quiet", "no change to report", "could not be verified", or anything about
feeds, models, verifiers or refusals. A beat with nothing to say does not appear.
If nothing has moved anywhere, write no issue at all.

## Whether to write at all

**1. Read `beats.yaml`** (the roster, including each beat's deadlines) and
`Standards.md` (the rules), then find the most recent file in `Deltas/`. That file's date
is your window's start; if `Deltas/` is empty, use the past seven days.

**2. Work out which beats are due.** A beat is due if any field it tracks changed
since the last issue **it** appeared in — not since the last issue generally.

Derive that from the issues themselves: each `Deltas/*.md` names the beats it
covered in its section headings. `Deltas/last_seen.json` is a convenience cache
only — **regenerate it from the issue files each run, and where it disagrees with
them, the issues win.** A crash between writing an issue and updating the cache
would otherwise corrupt every future cadence decision silently, and "get this
right" is not a mechanism.

**Read the changes from PUBLISHED stories only** — those listed in `editions/*.json`
since your window, not everything present in `stories/`. The editor may
deliberately leave a story off the page as a duplicate or a defect, and a story
the editor rejected must not reach subscribers through you. Otherwise the editor
is not a publication gate at all.

This is what makes the cadence adaptive and per-beat. A shooting war appears in
nearly every issue; a court case awaiting a September filing appears when the
filing lands. Nobody sets a schedule — the news does, per beat.

**3. Decide:**

- **A dated obligation has lapsed** — a deadline in `beats.yaml` passed and the
  expected filing did not appear. **Write, even if that is the only thing.** A
  deadline passing with nothing filed produces no headline anywhere, which makes
  it the one thing a reader cannot get from the wire.
- **Three or more beats are due.** Write.
- **One or two beats are due and it has been seven days or more.** Write.
- **One or two beats are due and it has been less than seven days.** Stop. Hold
  them for the next run. A digest of one entry is a news alert in a digest's
  clothes, and the front page already carried it.
- **Nothing is due.** Stop, whatever the interval. Padding is the only thing that
  can kill this format: an issue of "no change" entries teaches the reader to
  skip, and once they skip they don't come back.

If you stop, say why in your run summary. Write no file, commit nothing.

## Writing the issue

Write `Deltas/<YYYY-MM-DD>.md`, dated today in **US Eastern**, ISO order. Sort
prior issues by the date parsed from the filename — MM-DD-YYYY does not sort
chronologically, so `01-05-2027` would come before `12-30-2026` and anchor your
window to December for weeks.

```markdown
# The Delta — <Month D, YYYY>

*Covering the record since the [<Month D> issue](<YYYY-MM-DD>.md).*

## Top developments

- **<A bold sentence stating the development.>** <Two to four sentences
  explaining it, with dates and figures.>

## <Beat name>

<Prose. Lead with what CHANGED — "was X, now Y" is the news; the current value
alone is not. Dates, figures, named parties. Link the source on first mention.>

## Connecting the threads

**<A bold sentence naming the connection.>** <What is visible only across beats:
a name recurring in two unrelated dockets, one fight worked from three angles, a
date that lines up.>

## Correcting the record

<Only if a previously published fact turned out to be wrong. Say what was
published, what is true, and how it was caught.>
```

Rules for the writing:

**Two to four top developments,** chosen by consequence — not one per beat, and
not by how many stories a beat happened to produce.

**One section per due beat.** Open with the change, not the state.

**Threads only where the record carries them.** A recurring name or a shared
deadline across two beats is worth stating. "These developments reflect a broader
pattern" is filler and reads as filler; if nothing genuinely connects, write no
threads section. Use `https://doczero.epstein-data.com/llms.txt` and, for Epstein
material, `https://epstein-data.com/llms.txt`, citing documents as
`epstein-data.com/EFTA<id>`.

**Correct the record out loud.** If something published was wrong, say so in the
issue, name what was wrong, and say what is true. A newsroom that corrects
silently is asking to be trusted twice. Do not invent a correction to fill the
section — omit it when there is nothing to correct.

**400 to 2,600 words — except when a lapsed obligation triggered the issue.** A
passed deadline with nothing filed may be 200 honest words, and padding it to
reach a floor would destroy the exact thing that makes it worth sending. Never pad
such an issue. For every other trigger the floor holds: under 400 words there was
no issue.

**Never supply a link the sources don't make.** Joining two beats with an implied
causal relationship is the single most likely error in this format, because
cross-beat synthesis is exactly where an inference feels like an observation.

## Before committing

**Verify every sentence that makes a factual claim**, and explicitly the
standfirst and every bold lede. Spawn two verifier subagents per sentence, each
seeing **only the sentence and the evidence** — never your reasoning, never the
rest of the issue.

**The evidence is the original publisher's text, fetched from the source URLs in
the stories' front matter — never our own stories.** Verifying our prose against
our prose launders any error the desk's gate missed into delta-verified truth one
hop later: our masthead citing itself.

Give the two verifiers different jobs, since two instances asked the same question
are weaker evidence than they look:

- **A:** does this evidence support the sentence as written?
- **B:** state the strongest reason the sentence overreaches its evidence — a
  dropped attribution, a missing qualification, a date that does not match. For
  any sentence in a thread block, give B the source URLs and have it locate the
  support itself; you chose the excerpts, and motivated selection survives
  blinded review.

Both say no, or they disagree: cut it. A verifier errors: re-run once, then cut.
**Never rewrite a sentence to get it past a verifier** — that produces prose
optimised against the check rather than supported by evidence. If cutting drops
you under the floor, write no issue.

**Then read your own draft once, hunting only for process narration,** and cut
anything that slipped through. Mandatory, not optional.

## Committing

**Do not touch `index.html` or any HTML.** The Deploy action builds the issue list
from the files in `Deltas/`. You emit markdown and data; never markup. An instance
persuaded by a hostile source to write a script tag into the homepage is stored
XSS on a subdomain serving ~15,000 people a day.

Regenerate `Deltas/last_seen.json` from the issue files, including the one you
just wrote. It is derived, so it can always be rebuilt; never hand-edit it and
never trust it over the issues.

**One atomic commit,** so a mid-run death never half-publishes.

```
Delta <YYYY-MM-DD>: <the top development in one line>

fired because: <lapsed obligation | N beats moved | N moved and N days elapsed>
beats: <slugs that appeared>
held: <slugs due but not written, and why>
cut for lack of support: <count> sentence(s)
```

Push to main; the Deploy action renders and publishes. **Never rsync or ssh to
the server.** If your push is rejected non-fast-forward, fetch and rebase — your
paths are yours alone. At most three attempts; if a conflict touches anything
outside `Deltas/`, abort and report.

## The first issue

The first issue has no predecessor, so every field is being stated for the first
time and there are no transitions to report. Say so in the standfirst — that it
sets out where each beat currently stands — and write it as a state-of-the-record
issue. Do not render "was nothing, now X"; there was no previous value, and
implying one invents a history.
