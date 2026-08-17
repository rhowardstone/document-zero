"""The only module that spawns an agent.

This replaces `ledger/client.py`, which called a metered API, billed the
operator $0.36 without consent, and was deleted. See `ledger/NO_PAID_APIS.md`.

Every agent in this newsroom is a Claude Code invocation running on the
operator's existing subscription. That changes the engineering as well as the
bill: cost is no longer a variable, so parallelism and retries are cheap, and
the binding constraints become rate limits and wall-clock.

Design notes that are not stylistic:

  The prompt is one argv element, never a shell string. Everything this system
  reasons about arrived from a scraped web page, and a prompt built by string
  interpolation into a shell is an injection waiting to be found.

  Tools are restricted by the caller. An agent that can write anywhere defeats
  the write-partition rule that lets 22 agents run concurrently without locking.

  Failure raises. It never returns empty. v1's beat agents rendered as "quiet"
  when they errored, which made an unexplained absence indistinguishable from a
  still day; the same mistake here would be invisible one level lower.

  A timeout is always set. An agent with no timeout can hang a scheduled run
  forever, and a run that never finishes never publishes.
"""
from __future__ import annotations
import json
import subprocess
from dataclasses import dataclass

CLI = "claude"
DEFAULT_TIMEOUT = 900          # seconds; a beat agent that takes 15 min has failed


class AgentFailed(RuntimeError):
    """The agent did not produce a usable result. Never swallowed."""


@dataclass
class Completed:
    returncode: int
    stdout: str
    stderr: str


def build_command(prompt: str, *, allowed_tools=None, as_json: bool = False,
                  system_append: str | None = None,
                  permission_mode: str | None = None) -> list[str]:
    """Assemble the argv. Pure function, so it can be asserted on in tests."""
    cmd = [CLI, "-p", prompt]
    if as_json:
        cmd += ["--output-format", "json"]
    if allowed_tools:
        cmd += ["--allowedTools", ",".join(allowed_tools)]
    if system_append:
        cmd += ["--append-system-prompt", system_append]
    if permission_mode:
        cmd += ["--permission-mode", permission_mode]
    return cmd


# Credentials that make Claude Code authenticate as an API client and bill per
# token instead of running on the operator's subscription. Claude Code states
# plainly that ANTHROPIC_API_KEY "takes precedence over your claude.ai login",
# so merely having one in the shell silently converts every agent call into a
# metered one. This project deletes its paid client and then spawns agents; if
# it does not also scrub the environment, it has changed nothing.
BILLING_VARS = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL",
                "ANTHROPIC_API_URL", "CLAUDE_API_KEY")


def subscription_env(base=None) -> dict:
    """A copy of the environment with every billing credential removed."""
    import os
    env = dict(base if base is not None else os.environ)
    for var in BILLING_VARS:
        env.pop(var, None)
    return env


class WouldBill(RuntimeError):
    """Refusing to run: this invocation would be billed rather than covered."""


_verified = {"ok": False}


def assert_subscription(force: bool = False) -> dict:
    """Prove, before any model call, that agents run on the subscription.

    `claude auth status` is free — it makes no model call — and reports exactly
    what is needed:

        with a key in the environment   apiKeySource: ANTHROPIC_API_KEY
                                        subscriptionType: null
        with the environment scrubbed   subscriptionType: max

    Scrubbing the environment is the fix; this is the proof. The two are not the
    same thing, and the difference is what cost the operator real money: the
    project had already deleted its paid client and still spent, because nothing
    ever checked what the spawned agent actually authenticated as.

    Raises WouldBill unless the answer is a subscription.
    """
    if _verified["ok"] and not force:
        return {"cached": True}

    try:
        p = subprocess.run([CLI, "auth", "status"], capture_output=True, text=True,
                           timeout=60, env=subscription_env())
        status = json.loads(p.stdout)
    except Exception as e:                                  # noqa: BLE001
        raise WouldBill(
            f"could not verify how {CLI!r} authenticates ({type(e).__name__}: {e}). "
            "Refusing to run: an unverified auth mode is one that might bill.") from None

    if status.get("apiKeySource"):
        raise WouldBill(
            f"{CLI} is authenticating with {status['apiKeySource']}, which BILLS "
            "PER TOKEN. Unset it before running anything here:\n"
            "    unset ANTHROPIC_API_KEY\n"
            "and remove it from ~/.bashrc so it does not come back.")

    if not status.get("subscriptionType"):
        raise WouldBill(
            "no subscription found on this login, so every call would be billed. "
            f"Run `{CLI} auth login` and sign in to the account with the plan.")

    _verified["ok"] = True
    return status


def _subprocess_runner(cmd, **kw) -> Completed:
    kw.setdefault("env", subscription_env())
    # The agent gets NO stdin. The prompt is an argument, so nothing here has
    # any reason to read a descriptor — and inheriting one is actively harmful:
    # the CLI waits on stdin when it is attached ("no stdin data received in
    # 3s"), and concurrent beat workers then contend for the same descriptor.
    # A full daily run launched without a terminal lost 11 of 12 beats to this,
    # each one reported as "reporter failed" — a pipeline failure wearing the
    # costume of an editorial one, which is the worst kind this system can
    # produce, because it looks like the gate doing its job.
    kw.setdefault("stdin", subprocess.DEVNULL)
    p = subprocess.run(cmd, capture_output=True, text=True, **kw)
    return Completed(p.returncode, p.stdout, p.stderr)


def run(prompt: str, *, cwd: str | None = None, allowed_tools=None,
        as_json: bool = False, system_append: str | None = None,
        permission_mode: str | None = None, timeout: float = DEFAULT_TIMEOUT,
        _runner=None):
    """Invoke Claude Code and return its result.

    Returns the result string, or the parsed object when `as_json`. Raises
    AgentFailed on any outcome that is not a usable result — including an empty
    one, because silence from an agent is a failure and not an answer.
    """
    # Prove we are on the subscription BEFORE spending anything. Skipped only
    # when a runner is injected, which is how tests avoid shelling out.
    if _runner is None:
        assert_subscription()

    runner = _runner or _subprocess_runner
    cmd = build_command(prompt, allowed_tools=allowed_tools, as_json=True,
                        system_append=system_append,
                        permission_mode=permission_mode)
    try:
        done = runner(cmd, cwd=cwd, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise AgentFailed(f"agent timed out after {timeout}s") from None
    except FileNotFoundError:
        raise AgentFailed(
            f"{CLI!r} not on PATH. The reporters are Claude Code instances; "
            "there is deliberately no API fallback.") from None

    if done.returncode != 0:
        raise AgentFailed(
            f"agent exited {done.returncode}: "
            f"{(done.stderr or done.stdout or '').strip()[:400]}")

    try:
        envelope = json.loads(done.stdout)
    except (json.JSONDecodeError, TypeError):
        raise AgentFailed(
            f"could not parse the agent envelope: {str(done.stdout)[:200]!r}") from None

    result = envelope.get("result") if isinstance(envelope, dict) else None
    if not str(result or "").strip():
        raise AgentFailed("agent returned an empty result; silence is a failure, "
                          "not an answer")

    if not as_json:
        return result

    try:
        return json.loads(_strip_fence(result))
    except json.JSONDecodeError as e:
        raise AgentFailed(f"could not parse the agent's JSON result: {e}") from None


def _strip_fence(text: str) -> str:
    """Agents wrap JSON in code fences more often than not."""
    t = str(text).strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[-1]
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    return t.strip()
