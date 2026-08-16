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


def _subprocess_runner(cmd, **kw) -> Completed:
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
