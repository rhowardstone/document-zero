# Document Zero

An automated newsroom. It reads public news wires, works out which stories have
enough substance to track, writes them up, and checks every sentence it wrote
against the evidence it cited. Anything it cannot support, it refuses to
publish — and says that it refused.

Live at **[doczero.epstein-data.com](https://doczero.epstein-data.com)**.

No human reads the copy before it goes out. That is stated at the top of every
page, because a reader is entitled to know what they are reading.

## What makes it different from a summariser

A summariser turns an article into a shorter article and hopes for the best.
This one is built around a single constraint:

> **A sentence that the cited claims do not support does not publish.**

After a reporter writes an article, every sentence goes to two other models
that see *only* that sentence and the claims it cites — never the reporter's
reasoning, never the sources, never the rest of the article. They are asked one
question: does the evidence carry this sentence? A majority saying no refuses
it. A model that errors counts as "unverified", which counts as no.

The gate is not decorative. It has refused whole articles, and every time it
did, the article was wrong to have been written:

- A reporter joined two claims with "and its formal request", asserting a
  connection the claims never made. Refused.
- A stub reporter padded its copy to reach the word floor. The gate refused 22
  of its 29 sentences. The stub was fixed, not the gate.

The repeated lesson, in four separate incidents, is that an apparent quality
problem was always a **starved input** — thin claims, missing full text, a
truncated headline — and never an over-strict check.

## Beats, not topics

A beat is a unit of *persistent state*, not a subject heading. It opens only if
its story has at least three events over five days, or one dated trigger, **and**
at least two fields whose values tomorrow's news could change. It closes after
thirty quiet days.

Beats are proposed by a scout reading the wire and are opened by that test.
Nothing is hardcoded — an earlier version had 22 beats typed into a config file,
twenty of which were permanently empty, and could neither discover a story nor
retire one.

## The rule underneath all of it

**Never render a failure to know as a fact about the world.**

Almost every real bug in this project has been a violation of that one rule: a
rate-limited history lookup became "this story is 2 days old"; an unrecognised
publisher became "source unclassifiable"; a crashed agent became "the beat was
quiet"; a hardcoded noon became the publication time. Each fix makes the system
say *"I could not measure this"* instead.

## Running it

```bash
python3 scripts/daily.py --day $(date -u +%F)     # the whole pipeline
python3 -m pytest tests/ -q                        # 650 tests
```

Costs nothing. Every model call goes through the Claude Code CLI on a
subscription, and the runtime refuses to start if it finds a billing credential
in the environment — see `ledger/claudecode.py` and `ledger/NO_PAID_APIS.md`.

Scheduling: [`docs/SCHEDULE.md`](docs/SCHEDULE.md).

## Layout

| Path | What it does |
|---|---|
| `ledger/wire.py` | Publisher feeds, direct rather than aggregated |
| `ledger/fulltext.py` | Fetches article bodies; a blocked page yields thinner claims, never wrong ones |
| `ledger/emerge.py` | IDF-weighted clustering into candidate stories |
| `ledger/scout.py` | The beat test — what may open, and why a rejection was recorded |
| `ledger/continuity.py` | Is this the beat we already have, under a different name? |
| `ledger/desk.py` | Names a story, names its state, extracts claims |
| `ledger/reporter.py` | Builds the writing brief; the reporter sees claims and nothing else |
| `ledger/entail.py` | The gate. Majority-to-refuse, errors count as refuse |
| `ledger/lead.py` | Which story leads, decided on corroboration rather than the alphabet |
| `ledger/masthead.py` | What the top of the page is allowed to claim |
| `ledger/claudecode.py` | The only module that spawns an agent, and the billing guard |

Everything else is a projection of the ledger. If a fact is not in the ledger it
cannot appear on the page, and correcting the ledger re-renders the page.
