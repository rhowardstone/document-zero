# Running the newsroom on a schedule

## Where the articles come from

The scheduled session is **not** the newsroom. It runs one command, and that
command spawns the newsroom. Measured on a real run of twelve beats:

| Stage | Agents | What each one sees |
|---|---|---|
| Desk | 1 per cluster | The clustered wire reports. Names the story, names its changeable state, extracts claims. |
| Reporter | 1 per beat (**12**) | Only that beat's claims and the day's delta. Never the sources, never the beat's history, never another beat. |
| Verifier | 2 per sentence (**264**) | One sentence and the claims it cites. Nothing else — not the reporter's reasoning, not the rest of the article. |

That is roughly **290 `claude -p` instances per edition**, each a separate
process with a scrubbed environment. `scripts/daily.py` orchestrates them;
`ledger/claudecode.py` is the only module that spawns one.

The scheduled session's own Claude writes nothing. It starts the run, reports
what happened, and commits. Every editorial decision — what opens as a beat,
what gets written, what publishes — is made by tested code (668 tests) rather
than by a prompt, because a prompt drifts and a test does not.

## The command

```bash
python3 scripts/daily.py
```

**Do not pass `--day $(date -u +%F)`.** The editorial day is *local*, and the
code already defaults to it. UTC rolls over at 8pm Eastern, so a UTC day would
datelined an evening edition tomorrow — a paper whose masthead disagrees with
every source in it. That bug reached the live site once already.

`--no-deploy` builds without shipping. `--dry` stops after the wire stage.

## What it costs

Nothing. Every call goes through the `claude` CLI on the subscription, and the
runtime refuses to start if it finds a billing credential:

```
$ ANTHROPIC_API_KEY=sk-... python3 scripts/daily.py
WouldBill: claude is authenticating with ANTHROPIC_API_KEY, which BILLS PER TOKEN
```

That check raises before any call is made. It exists because a key left in
`~/.bashrc` once took precedence over the claude.ai login and silently metered
about 133 calls.

## The scheduled session prompt

Create a scheduled session at [claude.ai/code](https://claude.ai/code) against
`rhowardstone/document-zero`, and give it this:

> Run `python3 scripts/daily.py` from the repository root. It spawns the
> reporters and verifiers itself; you are starting the run, not writing the
> paper.
>
> **You must not write, edit, extend, or repair any article.** If no article
> survives, the correct edition is an empty one that says so. A page with a
> story you wrote by hand is unverified prose on a site that promises every
> sentence was checked — the single worst failure this system can produce.
>
> **You must not modify** the entailment gate (`ledger/entail.py`), the refusal
> gates, the confidence ceilings, the word bounds, or any threshold, to make an
> article pass. A refusal is the system working. Report it and leave it.
>
> If the wire stage fails, publish nothing and say so — a partial edition is
> worse than a stale one. If the run crashes, report the traceback and stop;
> do not work around it.
>
> Then report: how many articles survived, how many were refused and why, and
> any beat that moved without producing a story. Commit the day's ledger and
> the rebuilt site with a message naming the lead story, and push.
>
> If something in the pipeline looks broken rather than merely unproductive,
> say so plainly instead of producing a thin edition that hides it.

Once a day is right. The beat test needs events spread across days, GDELT's free
tier allows about one request every nine seconds, and a newsroom that runs
hourly mostly re-reads the same wire.

## Why the prompt is thin

Because everything it could usefully say is already enforced in code, and code
cannot be talked out of its position:

- An unsupported sentence is refused by `ledger/entail.py`, not by instruction.
- A beat opens only if it passes `ledger/scout.py:beat_test`.
- A claim cannot exceed its source type's confidence ceiling.
- An article already on the record today is not rewritten — articles are
  immutable, and a correction is a new day's article.

The prompt's real job is to stop a *helpful* agent from repairing what should
be left broken. Every quality problem this project has had turned out to be a
**starved input** — thin claims, a padded stub, missing full text — and never
an over-strict check. Feed the reporter better evidence; never lower the bar.

## Checking a run afterwards

```bash
python3 -m pytest tests/ -q
curl -s https://doczero.epstein-data.com/api/index.json | jq .counts
curl -s https://doczero.epstein-data.com/api/articles.json | jq '.articles[].headline'
git log --oneline -3
```

The front page states its own condition: the edition date, how many beats moved,
and whether it published. If something went wrong it says so rather than
showing a confident empty page — the one behaviour worth protecting above all
the others.
