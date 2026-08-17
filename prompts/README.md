# The cast

Nine scheduled routines. Each is a Claude Code instance on the subscription,
started by a scheduled session; each spawns subagents for the parallel work.
Nothing here bills per token, and nothing here touches the server directly.

The shape is taken from `rhowardstone/sleuths`, which works: a roster file that
is really an editorial style guide, markdown committed to a repo, and a GitHub
Action that deploys on push. The quality lives in these prompts, not in code.

## Why subdesks are routines, not subagents

A scheduled instance can spawn subagents. A subagent cannot spawn its own. So
depth comes from the cron table, not from nesting: each desk is its own routine,
which is what lets each one run on its own cadence and keep its own context.

```
cron entry  ─▶  desk instance  ─▶  researcher subagents (one per beat)
                              └─▶  verifier subagents (two per story)
```

## The routines

| Routine | Cadence (ET) | Prompt | Writes |
|---|---|---|---|
| scout | daily 05:00 | `prompts/scout.md` | **PR only** — `Beats.md` |
| justice desk | daily 06:00 | `prompts/desk.md` | `stories/justice/` |
| foreign desk | daily 06:00 | `prompts/desk.md` | `stories/foreign/` |
| politics desk | Mon, Thu 06:00 | `prompts/desk.md` | `stories/politics/` |
| disaster desk | daily 06:00 | `prompts/desk.md` | `stories/disaster/` |
| editor | daily 07:30 | `prompts/editor.md` | `editions/`, `index.html` |
| delta | daily 08:00 | `prompts/delta.md` | `Deltas/` |
| critic | daily 09:00 | `prompts/critic.md` | GitHub issues only |
| courier | after delta | `prompts/courier.md` | `Deltas/couriered.json` |

Cadence is per desk on purpose. A war moves daily; the 2028 primary calendar
does not. The disaster desk retires itself when its beats go quiet.

## The cron prompts

Each scheduled session gets exactly this text. Keep them this short — the
procedure belongs in the prompt file, where it can be reviewed in a diff.

```
Follow prompts/scout.md exactly.
```
```
You are the JUSTICE desk. Follow prompts/desk.md exactly.
```
```
You are the FOREIGN desk. Follow prompts/desk.md exactly.
```
```
You are the POLITICS desk. Follow prompts/desk.md exactly.
```
```
You are the DISASTER desk. Follow prompts/desk.md exactly.
```
```
Follow prompts/editor.md exactly.
```
```
Follow prompts/delta.md exactly.
```
```
Follow prompts/critic.md exactly.
```
```
Follow prompts/courier.md exactly.
```

## Write partitions

Four desks run at once. They are safe to do so only because each owns a path
prefix and writes nothing outside it. A routine that needs to change something
it does not own files an issue or opens a PR instead.

| Routine | May write | May never write |
|---|---|---|
| scout | `Beats.md` (via PR) | anything on the site |
| a desk | `stories/<desk>/` | another desk's stories, `Beats.md`, `editions/` |
| editor | `editions/`, `index.html`, `data.js` | `stories/`, `Beats.md` |
| delta | `Deltas/`, `index.html` issue list | `stories/`, `editions/` |
| critic | nothing | **everything** — it files issues |
| courier | `Deltas/couriered.json` | the copy, everything else |

The critic writing nothing is the point. A checker that can fix what it finds
starts fixing instead of reporting, and the record of what was wrong disappears
with it.

## Deploy

`push to main` → the Deploy action rsyncs with a key confined server-side to the
site directory, then verifies the site returns 200. **Never rsync or ssh to the
server from a routine.** epstein-data.com serves ~15,000 people a day from the
same box; the confined key is what makes an automated deploy safe.

## The rules every routine inherits

Read `Beats.md` first, every run. Two rules do the most work:

**No process narration.** The reader is not an engineer. Never publish what you
could not reach or could not establish. The exception is the standing disclosure
that the edition is machine-written and unreviewed — that is an ethical duty,
stated in fixed wording in the masthead and footer, never in the body.

**Never render a failure to know as a fact about the world.** Every serious bug
in this project has been that: a rate-limited lookup became "this story is 2
days old", an unrecognised publisher became "source unclassifiable", a crashed
agent became "the beat was quiet". If you could not measure something, the
honest output is to say nothing about it publicly and note it in the commit
message, which is where an operator reads.

**A refusal is the system working.** Every apparent quality problem here has
turned out to be a starved input — thin sources, a headline read instead of an
article — and never an over-strict check. Feed the writer better evidence. Never
loosen a rule to get something published.
