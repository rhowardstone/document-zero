# There is no paid API path in this project. Do not add one.

`ledger/client.py`, `scripts/live_run.py` and `tests/test_client.py` were
deleted on 2026-08-16. They called the Anthropic API directly, which bills per
token. They should never have existed.

**The reporters are Claude Code instances.** They run on the operator's existing
subscription. Nothing in this repository may call a metered API.

If you are an agent working on this project and you find yourself reaching for
`import anthropic`, an `ANTHROPIC_API_KEY`, or any other billable service:
stop. That is the wrong architecture for this project, and spending the
operator's money without being asked has already happened once here.

The correct shape is a Claude Code invocation that reads the ledger, does the
work, and writes files back into it. Cost is covered by the subscription; the
constraint is rate limits, not dollars.

Recoverable from git history if ever needed for reference:
`git show 652d104:ledger/client.py`
