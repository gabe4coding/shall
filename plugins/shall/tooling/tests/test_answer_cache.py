"""Incremental re-review: agent answers are reused only for an identical prompt (no model)."""

import asyncio
import sys

from shall.review import AnswerCache, run_claude

FAKE = """
import json, pathlib, sys
calls = pathlib.Path(sys.argv[1])
calls.write_text(calls.read_text() + "x" if calls.exists() else "x")
prompt = sys.stdin.read()
if "FAIL" in prompt:
    sys.exit(1)
print(json.dumps({"structured_output": {"findings": [], "echo": prompt}, "total_cost_usd": 0.05}))
"""


class Cfg:
    def __init__(self, command):
        self.values = {"review.command": command, "review.model": "claude-test", "review.timeout": 30}

    def get(self, key, default=None):
        return self.values.get(key, default)


def setup(tmp_path):
    script = tmp_path / "fake_claude.py"
    script.write_text(FAKE)
    calls = tmp_path / "calls"
    return Cfg([sys.executable, str(script), str(calls)]), calls


def ask(cfg, prompt, cache, system="reviewer"):
    return asyncio.run(run_claude(cfg, prompt, system, {"type": "object"}, asyncio.Semaphore(1), cache=cache))


def n_calls(calls):
    return len(calls.read_text()) if calls.exists() else 0


def test_identical_prompt_is_reused_and_persisted(tmp_path):
    cfg, calls = setup(tmp_path)
    path = tmp_path / "review.json"
    cache = AnswerCache(path)
    out1, meta1 = ask(cfg, "chunk A + statements", cache)
    out2, meta2 = ask(cfg, "chunk A + statements", cache)
    assert n_calls(calls) == 1 and out1 == out2
    assert meta1["cost_usd"] == 0.05 and meta2 == {"cost_usd": 0.0, "cached": True}
    cache.save()
    out3, meta3 = ask(cfg, "chunk A + statements", AnswerCache(path))   # next push, new process
    assert n_calls(calls) == 1 and out3 == out1 and meta3["cached"]


def test_any_change_is_a_new_call(tmp_path):
    cfg, calls = setup(tmp_path)
    cache = AnswerCache(None)
    ask(cfg, "chunk A", cache)
    ask(cfg, "chunk A, line 12 changed", cache)        # the diff changed
    ask(cfg, "chunk A", cache, system="reviewer v2")    # the agent prompt changed
    assert n_calls(calls) == 3


def test_failures_are_not_cached(tmp_path):
    cfg, calls = setup(tmp_path)
    cache = AnswerCache(None)
    assert ask(cfg, "FAIL", cache)[0] is None
    assert ask(cfg, "FAIL", cache)[0] is None
    assert n_calls(calls) == 2


def test_no_cache_means_no_reuse(tmp_path):
    cfg, calls = setup(tmp_path)
    ask(cfg, "chunk A", None)
    ask(cfg, "chunk A", None)
    assert n_calls(calls) == 2
