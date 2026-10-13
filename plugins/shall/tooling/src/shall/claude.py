"""The only module that runs `claude`. Every call is tool-less (JTOOL-0002.1).

`claude_command` builds the command line with the flags that keep the agent tool-less and
isolated; `run_claude` (JSON with a schema) and `run_claude_text` (plain text) are the two ways
to call it. The agent prompts (`plugins/shall/agents/*.md`) are read by `agent_prompt`, one
prompt for interactive and CI use (JTOOL-0004.2). tests/test_boundaries.py fails when another
module starts a process with `review.command`.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import random
import re
import tempfile
import time
from pathlib import Path

from .config import Config, load_json, merge_save_json

# The flags that make the agent unable to act: no tools, no MCP servers, no user or project
# settings (hooks, permissions), no saved session. Every `claude` call gets all of them.
ISOLATION_FLAGS = ("--tools", "", "--no-session-persistence", "--strict-mcp-config", "--setting-sources", "")

# one more try for agent failures that a second call usually does not repeat
RETRY_ERRORS = ("error_max_structured_output_retries", "no stdin data received")
RETRY_BACKOFF = 1.0  # seconds before the one retry, plus up to as much jitter


def plugin_root() -> Path:
    env = os.environ.get("SHALL_PLUGIN_ROOT")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[3]  # tooling/src/shall/claude.py -> plugins/shall


def agent_prompt(name: str) -> str:
    """The body of agents/<name>.md: one prompt for interactive and CI use (JTOOL-0004.2)."""
    text = (plugin_root() / "agents" / f"{name}.md").read_text(encoding="utf-8")
    if text.startswith("---"):
        text = text.split("---", 2)[2]
    return text.strip()


def claude_command(cfg: Config, model: str, system: str, schema: dict | None = None) -> list[str]:
    """`review.command` plus the model, the output form, the system prompt and ISOLATION_FLAGS."""
    output = ["--output-format", "json", "--json-schema", json.dumps(schema)] if schema is not None else \
        ["--output-format", "text"]
    return [*cfg.get("review.command"), "--model", model, *output, "--system-prompt", system, *ISOLATION_FLAGS]


async def _spawn(cmd: list[str], prompt: str, timeout: float) -> tuple[int, bytes, bytes] | None:
    """(exit code, stdout, stderr), or None after `timeout` seconds (the process is killed)."""
    # the prompt is a file on stdin: it is there when the process starts. Written through
    # the event loop, it could come after `claude -p` stopped to wait for it (3 s), when
    # blocking work (git grep for evidence) held the loop.
    with tempfile.TemporaryFile() as fh:
        fh.write(prompt.encode())
        fh.seek(0)
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdin=fh, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            # a pipeline agent never triggers shall hooks: its Stop would start another review
            env={**os.environ, "SHALL_HOOKS_DISABLED": "1"},
        )
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return None
    return proc.returncode or 0, out, err


class AnswerCache:
    """Agent answers keyed by exactly what the agent was given (model, system prompt, schema,
    prompt). A re-run on a new push reuses the answer for every chunk whose prompt did not
    change (same diff, same selected statements, same known effects), and for every
    verification whose evidence did not change. Only successful answers are stored; entries
    unused for `MAX_AGE_DAYS` are dropped on save. Merge-safe like the Jev cache."""

    MAX_AGE_DAYS = 30

    def __init__(self, path: Path | None):
        self.path = path
        self.entries: dict = load_json(path) if path is not None else {}
        self.reused = 0

    @staticmethod
    def key(model: str, system: str, schema: dict, prompt: str) -> str:
        payload = json.dumps({"m": model, "s": system, "j": schema, "p": prompt}, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()

    def get(self, key: str) -> dict | None:
        entry = self.entries.get(key)
        if entry is None:
            return None
        entry["used"] = time.time()
        self.reused += 1
        return entry["output"]

    def put(self, key: str, output: dict) -> None:
        self.entries[key] = {"output": output, "used": time.time()}

    def save(self) -> None:
        if self.path is None:
            return
        cutoff = time.time() - self.MAX_AGE_DAYS * 86400
        merge_save_json(self.path, self.entries, keep=lambda v: v.get("used", 0) >= cutoff)


def answer_cache(cfg: Config, enabled: bool = True) -> AnswerCache:
    """The review answer cache next to the Jev cache (`review.cache: false` disables it)."""
    if not enabled or not cfg.get("review.cache", True):
        return AnswerCache(None)
    return AnswerCache(cfg.cache_file.parent / "review.json")


async def run_claude(cfg: Config, prompt: str, system: str, schema: dict,
                     sem: asyncio.Semaphore, model: str | None = None,
                     cache: AnswerCache | None = None) -> tuple[dict | None, dict]:
    """One tool-less Claude call with a JSON schema. Returns (output, meta).
    With `cache`, an identical earlier call is reused (meta has `cached: True`, no cost)."""
    model = model or str(cfg.get("review.model"))
    key = AnswerCache.key(model, system, schema, prompt)
    if cache is not None:
        hit = cache.get(key)
        if hit is not None:
            return hit, {"cost_usd": 0.0, "cached": True}
    cmd = claude_command(cfg, model, system, schema)
    timeout = float(cfg.get("review.timeout"))
    out = b""
    for attempt in range(2):
        async with sem:
            done = await _spawn(cmd, prompt, timeout)
        if done is None:
            return None, {"error": f"agent timed out after {timeout:g}s"}
        code, out, err = done
        if code == 0:
            break
        error = err.decode()[-2000:] or out.decode()[-2000:]
        if attempt or not any(m in error for m in RETRY_ERRORS):
            return None, {"error": error}
        # JRFC-0006.2: exponential backoff with jitter, outside the semaphore
        await asyncio.sleep(RETRY_BACKOFF * 2 ** attempt + random.uniform(0, RETRY_BACKOFF))
    data = json.loads(out.decode())
    result = data.get("structured_output")
    if result is None:  # fall back to parsing the text result
        m = re.search(r"\{.*\}", data.get("result", ""), re.S)
        result = json.loads(m.group(0)) if m else None
    if cache is not None and result is not None:
        cache.put(key, result)
    return result, {"cost_usd": data.get("total_cost_usd", 0.0), "usage": data.get("usage") or {},
                    "models": sorted(data.get("modelUsage") or {})}


async def run_claude_text(cfg: Config, model: str, system: str, prompt: str) -> str | None:
    """One tool-less Claude call that answers in plain text; None on a failure or a timeout."""
    done = await _spawn(claude_command(cfg, model, system), prompt, float(cfg.get("review.timeout")))
    if done is None or done[0] != 0:
        return None
    return done[1].decode(errors="replace")
