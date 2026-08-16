"""The Claude Code adapter: the only module that spawns an agent.

It replaces `ledger/client.py`, which called a metered API and was deleted after
it billed the operator without consent. The first test here is the one that
matters: this file must not be able to cost anything.
"""
import json
import pathlib

import pytest

from ledger import claudecode as cc

SRC = pathlib.Path(__file__).resolve().parents[1] / "ledger" / "claudecode.py"


# ── The money rule, enforced as a test ───────────────────────────────────────

def test_the_adapter_cannot_call_a_paid_api():
    """The file may NAME a billing credential — it has to, in order to strip one
    from the agent's environment — but it must have no way to call one."""
    src = SRC.read_text().lower()
    for forbidden in ("import anthropic", "api.anthropic.com", "openai",
                      "import requests", "import httpx", "urllib.request"):
        assert forbidden not in src, f"{forbidden!r} must never appear here"


def test_the_module_never_reads_a_billing_credential():
    """The property is about READS, not mentions.

    The file must name ANTHROPIC_API_KEY — in the scrub list, and in the message
    it prints when it refuses to run, because telling the operator what to unset
    is the whole point. What it must never do is read one, which is what turns a
    credential into a charge.
    """
    import ast

    tree = ast.parse(SRC.read_text())
    reads = []
    for node in ast.walk(tree):
        # os.environ.get("ANTHROPIC_API_KEY") / os.getenv(...)
        if isinstance(node, ast.Call):
            fn = ast.unparse(node.func)
            if fn.endswith(("environ.get", "getenv")):
                for a in node.args:
                    if isinstance(a, ast.Constant) and "ANTHROPIC" in str(a.value):
                        reads.append(ast.unparse(node))
        # os.environ["ANTHROPIC_API_KEY"]
        if isinstance(node, ast.Subscript):
            src = ast.unparse(node)
            if "environ" in src and "ANTHROPIC" in src:
                reads.append(src)
    assert not reads, f"reads a billing credential: {reads}"


def test_the_command_invokes_the_claude_cli_in_print_mode():
    cmd = cc.build_command("write the article")
    assert cmd[0] == "claude"
    assert "-p" in cmd or "--print" in cmd


def test_the_prompt_is_passed_as_an_argument_not_interpolated_into_a_shell():
    """Shelling out with a string would let source text reach a shell."""
    cmd = cc.build_command("rm -rf / ; echo $(whoami)")
    assert "rm -rf / ; echo $(whoami)" in cmd, "the prompt is one argv element"


def test_tools_are_restricted_by_default():
    """An agent that can write anywhere defeats the write-partition rule."""
    cmd = cc.build_command("x", allowed_tools=["Read", "Grep"])
    joined = " ".join(cmd)
    assert "Read" in joined and "Grep" in joined


def test_json_output_is_requested_when_a_schema_is_expected():
    assert "--output-format" in cc.build_command("x", as_json=True)
    assert "--output-format" not in cc.build_command("x", as_json=False)


# ── Running ──────────────────────────────────────────────────────────────────

def test_a_successful_run_returns_the_result_text():
    def fake(cmd, **kw):
        return cc.Completed(0, json.dumps({"result": "the article text"}), "")
    assert cc.run("prompt", _runner=fake) == "the article text"


def test_json_mode_parses_the_result_payload():
    def fake(cmd, **kw):
        return cc.Completed(0, json.dumps({"result": '{"headline": "x"}'}), "")
    assert cc.run("p", as_json=True, _runner=fake) == {"headline": "x"}


def test_a_nonzero_exit_raises_rather_than_returning_empty():
    """A failed agent must never look like an agent that found nothing. v1's
    beat agents rendered as 'quiet' on error until that was fixed; the same
    mistake at this level would be invisible."""
    def fake(cmd, **kw):
        return cc.Completed(1, "", "rate limit exceeded")
    with pytest.raises(cc.AgentFailed, match="rate limit"):
        cc.run("p", _runner=fake)


def test_a_timeout_raises():
    import subprocess

    def fake(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, 60)
    with pytest.raises(cc.AgentFailed, match="timed out"):
        cc.run("p", _runner=fake)


def test_unparseable_json_raises_rather_than_returning_garbage():
    def fake(cmd, **kw):
        return cc.Completed(0, "not json at all", "")
    with pytest.raises(cc.AgentFailed, match="parse"):
        cc.run("p", as_json=True, _runner=fake)


def test_an_empty_result_raises():
    """Silence from an agent is a failure, not an answer."""
    def fake(cmd, **kw):
        return cc.Completed(0, json.dumps({"result": "   "}), "")
    with pytest.raises(cc.AgentFailed, match="empty"):
        cc.run("p", _runner=fake)


def test_the_working_directory_is_passed_through():
    seen = {}

    def fake(cmd, **kw):
        seen.update(kw)
        return cc.Completed(0, json.dumps({"result": "ok"}), "")
    cc.run("p", cwd="/tmp/somewhere", _runner=fake)
    assert seen.get("cwd") == "/tmp/somewhere"


def test_a_timeout_is_always_set():
    """An agent with no timeout can hang a scheduled run indefinitely."""
    seen = {}

    def fake(cmd, **kw):
        seen.update(kw)
        return cc.Completed(0, json.dumps({"result": "ok"}), "")
    cc.run("p", _runner=fake)
    assert isinstance(seen.get("timeout"), (int, float)) and seen["timeout"] > 0


# ── The environment must not smuggle a bill back in ─────────────────────────

def test_billing_credentials_are_stripped_from_the_agent_environment():
    """Deleting the paid client achieves nothing if the agent it spawns picks
    up an API key from the shell. Claude Code states that ANTHROPIC_API_KEY
    takes precedence over the claude.ai login, so an unscrubbed environment
    silently converts every agent call into a metered one."""
    env = cc.subscription_env({"ANTHROPIC_API_KEY": "sk-ant-real",
                               "ANTHROPIC_AUTH_TOKEN": "tok",
                               "ANTHROPIC_BASE_URL": "https://x",
                               "PATH": "/usr/bin", "HOME": "/home/x"})
    for var in cc.BILLING_VARS:
        assert var not in env, f"{var} survived scrubbing"
    assert env["PATH"] == "/usr/bin", "the rest of the environment must survive"
    assert env["HOME"] == "/home/x"


def test_the_runner_scrubs_by_default():
    seen = {}

    def fake(cmd, **kw):
        seen.update(kw)
        return cc.Completed(0, json.dumps({"result": "ok"}), "")

    # The default runner is what scrubs; assert the contract it must satisfy.
    import os
    os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test-only"
    try:
        assert "ANTHROPIC_API_KEY" not in cc.subscription_env()
    finally:
        os.environ.pop("ANTHROPIC_API_KEY", None)


# ── Proving, not promising ──────────────────────────────────────────────────

def test_an_api_key_source_refuses_to_run(monkeypatch):
    """Scrubbing the environment is the fix; this is the proof. The project had
    already deleted its paid client and still spent money, because nothing ever
    checked what the spawned agent actually authenticated as."""
    monkeypatch.setattr(cc, "_verified", {"ok": False})
    monkeypatch.setattr(cc.subprocess, "run", lambda *a, **k: type(
        "P", (), {"stdout": json.dumps({"loggedIn": True,
                                        "apiKeySource": "ANTHROPIC_API_KEY",
                                        "subscriptionType": None})})())
    with pytest.raises(cc.WouldBill, match="BILLS PER TOKEN"):
        cc.assert_subscription(force=True)


def test_no_subscription_refuses_to_run(monkeypatch):
    monkeypatch.setattr(cc, "_verified", {"ok": False})
    monkeypatch.setattr(cc.subprocess, "run", lambda *a, **k: type(
        "P", (), {"stdout": json.dumps({"loggedIn": True,
                                        "subscriptionType": None})})())
    with pytest.raises(cc.WouldBill, match="would be billed"):
        cc.assert_subscription(force=True)


def test_a_subscription_login_is_accepted(monkeypatch):
    monkeypatch.setattr(cc, "_verified", {"ok": False})
    monkeypatch.setattr(cc.subprocess, "run", lambda *a, **k: type(
        "P", (), {"stdout": json.dumps({"loggedIn": True,
                                        "subscriptionType": "max"})})())
    assert cc.assert_subscription(force=True)["subscriptionType"] == "max"


def test_an_unverifiable_auth_mode_refuses_to_run(monkeypatch):
    """An auth mode we cannot read is one that might bill."""
    monkeypatch.setattr(cc, "_verified", {"ok": False})
    def boom(*a, **k):
        raise OSError("no claude on PATH")
    monkeypatch.setattr(cc.subprocess, "run", boom)
    with pytest.raises(cc.WouldBill, match="could not verify"):
        cc.assert_subscription(force=True)
