# Running the newsroom on a schedule

One command produces an edition:

```bash
python3 scripts/daily.py --day $(date -u +%F)
```

It runs the whole pipeline: wire → cluster → desk → beat agents → entailment
gate → edition → render → deploy. Add `--no-deploy` to build without shipping.

## What it costs

Nothing. Every agent call goes through the `claude` CLI on the Claude Code
subscription, and `ledger/claudecode.py` refuses to run at all if it detects a
billing credential:

```
$ ANTHROPIC_API_KEY=sk-... python3 scripts/daily.py
WouldBill: claude is authenticating with ANTHROPIC_API_KEY, which BILLS PER TOKEN
```

That check is not advisory — it raises before any call is made. It exists
because an `ANTHROPIC_API_KEY` left in `~/.bashrc` once took precedence over the
claude.ai login and silently metered about 133 calls.

## Setting up the free cloud schedule

Claude Code's scheduled sessions run on the subscription. Create one at
[claude.ai/code](https://claude.ai/code) → the repository
`rhowardstone/document-zero` → **Schedule**, and give it this prompt:

> Run `python3 scripts/daily.py --day $(date -u +%F)` from the repository root.
> Report how many articles survived the entailment gate and how many did not.
> If the wire stage fails, publish nothing and say so — a partial edition is
> worse than a stale one. Do not modify the entailment gate, the refusal gates,
> or the confidence ceilings to make an article pass. If an article is refused,
> that is the system working; report the refusal and leave it refused.
>
> Commit the day's ledger and the rebuilt site with a message naming the lead
> story, and push.

Once a day is right. The beat test needs events spread over days, GDELT's free
tier allows roughly one request every nine seconds, and a newsroom that runs
hourly mostly re-reads the same wire.

## What must never be automated away

The gate is the product. A scheduled run that "fixes" a refusal by loosening a
threshold has produced a newspaper that asserts things nothing supports, which
is worse than no newspaper. Every quality problem this project has had so far
turned out to be a **starved input** — thin claims, a padded stub, a truncated
headline — and never an over-strict check. Feed the reporter better evidence;
do not lower the bar.

## Checking a run afterwards

```bash
python3 -m pytest tests/ -q            # 648 tests
curl -s https://doczero.epstein-data.com/api/index.json | head
git log --oneline -3
```

The front page states its own condition: the masthead shows the edition date,
how many beats moved, and whether the edition published. If something went
wrong, the page says so rather than showing a confident empty page — that is
the one behaviour worth protecting above all the others.
