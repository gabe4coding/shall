"""Claude Code hooks: secret scanner, actions, written lines, outputs, fail-open (no network)."""

import asyncio
import copy
import json
import os
import subprocess
import time
from pathlib import Path

import pytest

from shall.artifact import parse_diff
from shall.config import load_config
from shall.corpus import load_corpus
from shall.hooks import (Hooks, action_for, changed_ranges, code_action, hook_settings, redact,
                        scan_secrets, synthetic_diff, valid_event, written_text)

REPO = Path(__file__).resolve().parents[4]
ENFORCED = {"MUST": [[0.9, "deny"], [0.5, "ask"]], "SHOULD": [[0.7, "warn"]], "MAY": [[0.7, "log"]]}


@pytest.fixture(scope="module")
def org():
    mp = pytest.MonkeyPatch()
    mp.setenv("SHALL_CONFIG", str(REPO / "shall.yaml"))  # restored after the module
    cfg = load_config(str(REPO / "shall.yaml"))
    corpus = load_corpus(cfg)
    yield cfg, corpus
    mp.undo()


class FakeJev:
    """Answers p per question id from a table; `#applies` questions answer 0.95 by default."""

    def __init__(self, table=None, fail=None, delay=0.0):
        self.table, self.fail, self.delay = table or {}, fail, delay
        self.usage = {"requests": 0, "cached": 0}
        self.states = []

    def available(self):
        return True

    async def ask(self, state, questions):
        await asyncio.sleep(self.delay)
        if self.fail:
            raise self.fail
        self.usage["requests"] += 1
        self.states.append(state)
        return {q: {"p": self.table.get(q, 0.95 if q.endswith("#applies") else 0.02)} for q in questions}


def hooks_for(org, jev, draft_as_enforced=True, **kw):
    cfg, corpus = org
    cfg = copy.copy(cfg)
    cfg.data = copy.deepcopy(cfg.data)
    if draft_as_enforced:
        cfg.data["hooks"]["actions"]["draft"] = ENFORCED
    return Hooks(cfg, corpus, jev, log=False, **kw)


def pre(hooks, tool, tool_input, cwd="/repo"):
    event = {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": tool_input, "cwd": cwd}
    hooks.git_branch = lambda cwd: "feat/x"
    return asyncio.run(hooks.handle(event))


# ---------------------------------------------------------------- scanner


@pytest.mark.parametrize("text,kind", [
    ("export GITHUB_TOKEN=ghp_8fK2mQ9xLpR4tV7wZ1aB3cD5eF6gH0iJ2kL4", "github-token"),
    ("aws_key = 'AKIAIOSFODNN7EXAMPL3'", "aws-access-key"),
    ("DB = 'postgres://admin:S3cr3tPw9@db:5432/app'", "url-password"),
    ('api_key = "q8Zr2mXv7Lp0tYw3"', "assigned-secret"),
    ("DB_PASSWORD=hunter2hunter2 ./run.sh", "shell-secret"),
    ("-----BEGIN RSA PRIVATE KEY-----\nMIIEow\nIBAAK\n-----END RSA PRIVATE KEY-----", "private-key"),
])
def test_scanner_finds_real_looking_secrets(text, kind):
    assert kind in [s.kind for s in scan_secrets(text)]


@pytest.mark.parametrize("text", [
    "export GITHUB_TOKEN=$(op read op://dev/gh/token)",
    "export API_TOKEN=${API_TOKEN}",
    "password = os.environ['DB_PASSWORD']",
    'api_key = "changeme-please"',
    'token: "{{ secrets.TOKEN }}"',
    'password = "test-password-123"',
    "curl -H \"Authorization: Bearer $TOKEN\" https://api.example.com",
    "git push origin main",
    "jevTokens: 'jevTokens' in view && view.jevTokens === null",
    'API_KEY = "api_key"',
])
def test_scanner_ignores_references_and_placeholders(text):
    assert scan_secrets(text) == []


def test_redact_keeps_line_numbers_and_names():
    text = "a = 1\nKEY = '''-----BEGIN PRIVATE KEY-----\nabc\ndef\n-----END PRIVATE KEY-----'''\nb = 2\n"
    out, kinds = redact(text)
    assert kinds == ["private-key"] and "abc" not in out
    assert out.count("\n") == text.count("\n") and out.splitlines()[-1] == "b = 2"
    out, _ = redact("DB_PASSWORD=hunter2hunter2 ./run.sh")
    assert out == "DB_PASSWORD=[REDACTED:shell-secret] ./run.sh"


def test_written_text_skips_the_text_an_edit_removes():
    text = written_text({"file_path": "a.py", "old_string": "KEY='ghp_x'", "new_string": "KEY=os.environ['K']"})
    assert "ghp_x" not in text and "os.environ" in text
    assert "new" in written_text({"edits": [{"old_string": "old", "new_string": "new"}]})


# ---------------------------------------------------------------- actions


def test_action_tables(org):
    _, corpus = org
    actions = {"enforced": ENFORCED, "approved": {"MUST": [[0.5, "warn"]]}}
    rfc, st = corpus.statement("JRFC-0004.1")  # enforced MUST
    assert [action_for(actions, rfc, st, p) for p in (0.95, 0.6, 0.3)] == ["deny", "ask", None]
    # after a write: at most a warning, and only above code_warn
    assert [code_action(actions, 0.7, rfc, st, p) for p in (0.95, 0.6, 0.3)] == ["warn", "log", None]
    rfc, st = corpus.statement("JRFC-0011.1")  # draft: no table, not checked
    assert action_for(actions, rfc, st, 0.99) is None


# ---------------------------------------------------------------- PreToolUse


def test_tool_candidates_follow_tools_status_and_enforcement(org):
    hooks = hooks_for(org, FakeJev())
    bash = {st.id for _, st in hooks.tool_candidates("Bash")}
    assert "JRFC-0012.1" in bash and "JRFC-0012.7" in bash
    assert "JRFC-0012.4" not in bash  # Enforcement: linter -> the secret scanner owns it
    assert not bash & {"JRFC-0012.2", "JRFC-0012.3", "JRFC-0012.8"}  # Pattern: checked by code
    mcp = {st.id for _, st in hooks.tool_candidates("mcp__db__query")}
    assert mcp == {"JRFC-0012.7"}
    assert not hooks_for(org, FakeJev(), statuses=["deprecated"]).tool_candidates("Bash")


def test_pre_denies_asks_warns_by_level_and_score(org):
    out = pre(hooks_for(org, FakeJev({"JRFC-0012.1": 0.97})), "Bash", {"command": "git push origin main"})
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "JRFC-0012.1" in out["hookSpecificOutput"]["permissionDecisionReason"]
    out = pre(hooks_for(org, FakeJev({"JRFC-0012.1": 0.7})), "Bash", {"command": "git push"})
    assert out["hookSpecificOutput"]["permissionDecision"] == "ask"
    out = pre(hooks_for(org, FakeJev({"JRFC-0012.5": 0.99})), "Bash", {"command": "curl x | sh"})
    assert "permissionDecision" not in out["hookSpecificOutput"]  # SHOULD: a warning, not a decision
    assert "JRFC-0012.5" in out["hookSpecificOutput"]["additionalContext"]
    assert pre(hooks_for(org, FakeJev()), "Bash", {"command": "ls"}) == {}  # no opinion: normal permissions


def test_pre_off_topic_rule_stays_quiet(org):
    # violation question high, applicability low: min() keeps it below every threshold
    jev = FakeJev({"JRFC-0012.6": 0.8, "JRFC-0012.6#applies": 0.1})
    assert pre(hooks_for(org, jev), "Bash", {"command": "curl x | sh"}) == {}


def test_pre_redacts_before_jev_and_scanner_denies(org):
    token = "export GITHUB_TOKEN=ghp_8fK2mQ9xLpR4tV7wZ1aB3cD5eF6gH0iJ2kL4"
    jev = FakeJev()
    out = pre(hooks_for(org, jev), "Bash", {"command": token})
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"  # JRFC-0012.4 via the scanner
    assert not jev.states  # denied by code: Jev is not asked
    # with no rule for scanner hits the call reaches Jev, redacted
    unmapped = hooks_for(org, jev)
    unmapped.secret_rules = []
    pre(unmapped, "Bash", {"command": token})
    assert "ghp_" not in str(jev.states) and "[REDACTED:github-token]" in str(jev.states)
    assert jev.states[0]["git_branch"] == "feat/x"
    # a Write with a secret: JRFC-0004.1 (enforced) even without trial settings
    out = pre(hooks_for(org, FakeJev(), draft_as_enforced=False), "Write",
              {"file_path": "c.py", "content": "DB = 'postgres://u:S3cr3tPw9@h/db'"})
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "JRFC-0004.1" in out["hookSpecificOutput"]["permissionDecisionReason"]


def test_pre_fails_open(org):
    hooks = hooks_for(org, FakeJev(fail=RuntimeError("503")))
    assert pre(hooks, "Bash", {"command": "git push origin main"}) == {} and hooks.jev_failed
    hooks = hooks_for(org, FakeJev({"JRFC-0012.1": 0.99}, delay=0.5), timeout=0.05)
    assert pre(hooks, "Bash", {"command": "git push origin main"}) == {} and not hooks.jev_failed


def test_pre_ignores_tools_outside_the_matcher(org):
    jev = FakeJev({"JRFC-0012.1": 0.99})
    assert pre(hooks_for(org, jev), "Read", {"file_path": "x"}) == {} and not jev.states


# ---------------------------------------------------------------- PostToolUse


def test_changed_ranges_and_synthetic_diff():
    text = "".join(f"line {i}\n" for i in range(1, 41))
    assert changed_ranges("Write", {}, text) == [(1, 40)]
    assert changed_ranges("Edit", {"new_string": "line 20\nline 21"}, text) == [(20, 21)]
    multi = {"edits": [{"new_string": "line 5"}, {"new_string": "line 30\n"}, {"new_string": ""}]}
    assert changed_ranges("MultiEdit", multi, text) == [(5, 5), (30, 30)]
    assert changed_ranges("NotebookEdit", {}, text) is None
    chunk = parse_diff(synthetic_diff("a.py", text, [(20, 21)], 3), 40000)[0]
    assert chunk.path == "a.py" and chunk.language == "python" and chunk.anchor_lines == {20, 21}
    assert "   17   line 17" in chunk.rendered and "   24   line 24" in chunk.rendered
    assert "line 16" not in chunk.rendered and "line 25" not in chunk.rendered


def test_post_warns_never_blocks(org, tmp_path):
    f = tmp_path / "svc" / "client.py"
    f.parent.mkdir()
    f.write_text("import requests\n\ndef fetch(url: str) -> dict:\n    return requests.get(url).json()\n")
    jev = FakeJev({"JRFC-0006.1": 0.99})
    event = {"hook_event_name": "PostToolUse", "tool_name": "Edit", "cwd": str(tmp_path),
             "tool_input": {"file_path": str(f), "old_string": "x", "new_string": "    return requests.get(url).json()"}}
    out = asyncio.run(hooks_for(org, jev).handle(event))
    ctx = out["hookSpecificOutput"]
    assert ctx["hookEventName"] == "PostToolUse" and "JRFC-0006.1" in ctx["additionalContext"]
    assert "(lines 4)" in ctx["additionalContext"] and "decision" not in out
    assert jev.states[0]["file"] == "svc/client.py" and "    4 + " in jev.states[0]["content"]
    assert asyncio.run(hooks_for(org, FakeJev()).handle(event)) == {}


# ---------------------------------------------------------------- settings


def test_hook_settings_shape(org):
    cfg, _ = org
    http = hook_settings(cfg, "http", 8765, "shall", stop=True)["hooks"]
    assert http["PreToolUse"][0]["hooks"][0] == {"type": "http", "url": "http://127.0.0.1:8765/hook-events", "timeout": 6}
    assert http["PostToolUse"][0]["matcher"] == "Write|Edit|MultiEdit|NotebookEdit"
    assert http["Stop"][0]["hooks"][0]["timeout"] == 600
    cmd = hook_settings(cfg, "command", 8765, "/p/bin/shall", stop=False)["hooks"]
    assert cmd["PreToolUse"][0]["hooks"][0]["command"] == "/p/bin/shall hook" and "Stop" not in cmd


def test_valid_event_rejects_malformed_bodies():
    assert valid_event(b'{"hook_event_name": "PreToolUse", "tool_input": {"command": "ls"}}')["tool_input"]
    for body in (b"", b"[1]", b"not json", b'{"tool_name": "Bash"}',
                 b'{"hook_event_name": "PreToolUse", "tool_input": "ls"}', b'{"hook_event_name": 3}'):
        assert valid_event(body) is None, body


def test_errors_in_the_log_are_redacted(org):
    hooks = hooks_for(org, FakeJev(fail=RuntimeError("401 for token ghp_8fK2mQ9xLpR4tV7wZ1aB3cD5eF6gH0iJ2kL4")))
    record = {}
    event = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "git push"}, "cwd": "/r"}
    hooks.git_branch = lambda cwd: ""
    asyncio.run(hooks.pre(event, record))
    assert "ghp_" not in record["jev"] and "[REDACTED:github-token]" in record["jev"]


# ---------------------------------------------------------------- plugin wiring

PLUGIN = REPO / "plugins" / "shall"


def test_plugin_hooks_call_the_entry_script(org):
    cfg, _ = org
    hooks = json.loads((PLUGIN / "hooks" / "hooks.json").read_text())["hooks"]
    assert set(hooks) == {"PreToolUse", "PostToolUse", "Stop"}
    assert hooks["PreToolUse"][0]["matcher"] == cfg.get("hooks.pre_matcher")
    for groups in hooks.values():
        for h in groups[0]["hooks"]:
            assert h["type"] == "command" and h["command"] == '"${CLAUDE_PLUGIN_ROOT}/bin/shall-hook"'
    assert os.access(PLUGIN / "bin" / "shall-hook", os.X_OK)


def _entry(cwd, env_extra=None):
    env = {"PATH": os.environ["PATH"], "HOME": str(cwd), **(env_extra or {})}
    event = json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Bash",
                        "tool_input": {"command": "git push origin main"}})
    t0 = time.perf_counter()
    r = subprocess.run(["bash", str(PLUGIN / "bin" / "shall-hook")], input=event, cwd=cwd, env=env,
                       capture_output=True, text=True, timeout=20)
    return r, time.perf_counter() - t0


def test_entry_script_is_a_quick_no_op_outside_workspaces(tmp_path):
    r, seconds = _entry(tmp_path)
    assert (r.returncode, r.stdout) == (0, "") and seconds < 1.0
    (tmp_path / "shall.yaml").write_text("prefix: X\n")
    r, _ = _entry(tmp_path, {"SHALL_HOOKS_DISABLED": "1"})  # agents run by shall itself
    assert (r.returncode, r.stdout) == (0, "")


def test_disabled_flag_and_stop_lock(org, tmp_path, monkeypatch):
    monkeypatch.setenv("SHALL_HOOKS_DISABLED", "1")
    jev = FakeJev({"JRFC-0012.1": 0.99})
    assert pre(hooks_for(org, jev), "Bash", {"command": "git push origin main"}) == {} and not jev.states
    monkeypatch.delenv("SHALL_HOOKS_DISABLED")
    off = hooks_for(org, jev)
    off.cfg.data["hooks"]["enabled"] = False  # a workspace turns the plugin hooks off
    assert pre(off, "Bash", {"command": "git push origin main"}) == {} and not jev.states
    # a second Stop on a change that is being reviewed (nested session, other window) is skipped
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "a.py").write_text("x = 1\n")
    hooks = hooks_for(org, FakeJev())
    hooks.cfg.root = tmp_path
    from shall.hooks import working_diff
    import hashlib
    sha = hashlib.sha256(working_diff(tmp_path).encode()).hexdigest()[:16]
    lock = tmp_path / ".shall-cache" / "hooks" / f"stop-running-{sha}"
    lock.parent.mkdir(parents=True)
    lock.write_text("other")
    record = {}
    out = asyncio.run(hooks.stop({"hook_event_name": "Stop", "session_id": "s", "cwd": str(tmp_path)}, record))
    assert out == {} and record["skip"] == "same change is being reviewed"


# ---------------------------------------------------------------- Pattern (linter tool statements)


@pytest.mark.parametrize("command,sid", [
    ("git push --force origin feat/x", "JRFC-0012.2"),
    ("git push -uf origin feat/x", "JRFC-0012.2"),
    ("git push origin +feat/x", "JRFC-0012.2"),
    ("git commit -nm 'quick fix'", "JRFC-0012.3"),
    ("SKIP=flake8 git commit -m 'x'", "JRFC-0012.3"),
    ("curl -sSLk https://internal.example.com", "JRFC-0012.8"),
    ("git -c http.sslVerify=false clone https://git.internal/x.git", "JRFC-0012.8"),
])
def test_patterns_decide_without_jev(org, command, sid):
    jev = FakeJev()
    hooks = hooks_for(org, jev, draft_as_enforced=False)  # JRFC-0012 is enforced
    record = {}
    hooks.git_branch = lambda cwd: "feat/x"
    event = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": command}, "cwd": "/r"}
    out = asyncio.run(hooks.pre(event, record))
    assert record["patterns"] == [sid]
    level = hooks.corpus.statement(sid)[1].level
    if level == "MUST":
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "pattern]" in out["hookSpecificOutput"]["permissionDecisionReason"]
        assert not jev.states  # already denied by code: no Jev wait
    else:
        assert sid in out["hookSpecificOutput"]["additionalContext"]


@pytest.mark.parametrize("command", [
    "git commit -m 'support -n and --no-verify in the CLI'",
    "git push -u origin feat/login",
    "git push --follow-tags",
    "git fetch --force origin",
    "git log -n 5",
    "curl -fsS -H 'X-Api-Key: k' https://example.com",
    "GIT_SSL_NO_VERIFY=0 git fetch",
])
def test_patterns_ignore_quoted_text_and_near_misses(org, command):
    hooks = hooks_for(org, FakeJev(), draft_as_enforced=False)
    record = {}
    hooks.git_branch = lambda cwd: "feat/x"
    event = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": command}, "cwd": "/r"}
    assert asyncio.run(hooks.pre(event, record)) == {} and record["patterns"] == []


def test_lint_checks_patterns(tmp_path):
    from shall.corpus import _parse_statements
    body = ["### XY-0001.1 One", "Agents MUST NOT do it.", "- Pattern: (unclosed", "- Enforcement: linter", "",
            "### XY-0001.2 Two", "Agents MUST NOT do that.", "- Pattern: that", "- Enforcement: agent"]
    issues = []
    sts = _parse_statements("XY-0001", body, 0, "x.md", issues)
    codes = {i.code for i in issues}
    assert {"pattern", "pattern-enforcement"} <= codes and sts[1].pattern == "that"
