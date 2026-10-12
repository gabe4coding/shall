#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""Drives shall end to end for /verify and prints the evidence as JSON (SKILL.md reads it).

  hook   one headless Claude Code session with this repo's plugin, in a new git repository
         (`dir`/repo) whose `.shall/` extends this repo's corpus (`shall init --path`)
  cli    one `shall` command from the repo root; `{out}` in an argument is the output folder
  clean  removes a run folder

Each run keeps its folder (`dir`) until `clean`. Nothing goes to ~/.claude.
"""

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import uuid
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
SHALL = ROOT / "plugins" / "shall" / "bin" / "shall"
PLUGIN = ROOT / "plugins" / "shall"
PREFIX = "shall-verify-"
# shall's own folders are never part of the change (hooks.NOT_CHANGE)
NOT_CHANGE = ["--", ".", ":(exclude,glob)**/.shall-cache/**", ":(exclude,glob)**/.shall-out/**"]
# the stream messages the evidence reads
KEEP = {"assistant", "user", "result"}


def cut(text: str, n: int = 800) -> str:
    return text if len(text) <= n else f"{text[:n]}… ({len(text)} chars)"


def cut_values(data: dict, n: int = 400) -> dict:
    return {k: cut(v, n) if isinstance(v, str) else v for k, v in data.items()}


def read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def free_port() -> int:
    """A port with nothing on it: shall-hook then finds no hookd and runs `shall hook` itself."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def clean_env() -> dict:
    """The caller's environment without this script's uv environment (its python must not reach
    shall or the session's hooks) and without shall settings that would change the run."""
    env = {k: v for k, v in os.environ.items()
           if k not in ("VIRTUAL_ENV", "SHALL_HOOKS_DISABLED", "SHALL_CONFIG", "SHALL_EXTENDS")}
    env["PATH"] = os.pathsep.join(p for p in env.get("PATH", "").split(os.pathsep)
                                  if not p.startswith(sys.prefix))
    return env


ENV = clean_env()


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True).stdout


def new_run(base: str | None) -> Path:
    return Path(tempfile.mkdtemp(prefix=PREFIX, dir=base))


def findings_summary(out: Path) -> dict:
    """The parts of a review output folder that a check reads."""
    res: dict = {"files": sorted(str(p.relative_to(out)) for p in out.rglob("*") if p.is_file())}
    f = out / "findings.json"
    if f.is_file():
        data = json.loads(f.read_text(encoding="utf-8"))
        res["findings"] = [{"id": x.get("statement_id"), "path": x.get("path"), "line": x.get("line"),
                            "blocking": x.get("blocking"),
                            "verdict": (x.get("verification") or {}).get("verdict")}
                           for x in data.get("findings", [])]
        res["dropped"] = len(data.get("dropped", []))
    h = out / "health.json"
    if h.is_file():
        res["healthWarnings"] = json.loads(h.read_text(encoding="utf-8")).get("warnings", [])
    return res


# ---------------------------------------------------------------- hook

def merge(base: dict, override: dict) -> dict:
    """Nested dict merge, as shall merges settings (config._merge)."""
    out = dict(base)
    for key, value in override.items():
        out[key] = merge(out[key], value) if isinstance(value, dict) and isinstance(out.get(key), dict) else value
    return out


def decision_log(cwd: Path) -> Path:
    """`hooks.log` of the run's workspace, relative to its root (.shall/)."""
    data = yaml.safe_load((cwd / ".shall" / "shall.yaml").read_text(encoding="utf-8"))
    return cwd / ".shall" / ((data.get("hooks") or {}).get("log") or ".shall-cache/hooks/decisions.jsonl")


def make_repo(cwd: Path, args) -> None:
    """A git repository with a shall workspace on this repo's corpus, all committed, so the
    Stop review sees only what the agent changes."""
    cwd.mkdir()
    if args.repo:
        shutil.copytree(ROOT / args.repo, cwd, dirs_exist_ok=True)
    else:
        (cwd / "README.md").write_text("# demo\n", encoding="utf-8")
    init = subprocess.run([str(SHALL), "init", "--prefix", "VFY", "--path", str(ROOT)], cwd=cwd, env=ENV,
                          capture_output=True, text=True)
    if init.returncode:
        raise SystemExit(f"shall init failed (exit {init.returncode}):\n{init.stderr or init.stdout}")
    config = cwd / ".shall" / "shall.yaml"
    data = merge(yaml.safe_load(config.read_text(encoding="utf-8")), yaml.safe_load(args.yaml or "{}") or {})
    if args.no_stop:
        data = merge(data, {"hooks": {"stop": {"enabled": False}}})
    config.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    git(cwd, "init", "-q", "-b", "main")
    git(cwd, "add", "-A")
    git(cwd, "-c", "user.name=verify", "-c", "user.email=verify@example.com", "commit", "-q", "-m", "start")


def start_hookd(cwd: Path, env: dict, port: int, log: Path) -> subprocess.Popen:
    proc = subprocess.Popen([str(SHALL), "hookd", "--port", str(port)], cwd=cwd, env=env,
                            stdout=log.open("w"), stderr=subprocess.STDOUT)
    for _ in range(100):  # the first start can build the uv environment
        try:
            # a full request: a bare connect makes hookd log an IncompleteReadError
            urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=0.5).close()
            return proc
        except OSError:
            time.sleep(0.2)
    proc.kill()
    raise SystemExit(f"shall hookd did not listen on port {port}; see {log}")


def run_session(dir: Path, args, env: dict) -> tuple[int | str, list[dict]]:
    argv = ["claude", "-p", "--input-format", "stream-json", "--output-format", "stream-json", "--verbose",
            "--include-hook-events", "--no-session-persistence",
            "--plugin-dir", str(PLUGIN),
            # only this plugin's hooks: no user settings (their hooks, plugins, permission mode)
            "--setting-sources", "project,local", "--strict-mcp-config",
            *(["--mcp-config", args.mcp_config] if args.mcp_config else []),
            "--allowedTools", args.allow,
            "--permission-prompts", "none",  # an `ask` decision becomes a denial, never a hang
            "--debug-file", str(dir / "debug.log"),
            "--session-id", str(uuid.uuid4()), "--max-budget-usd", str(args.budget),
            "--model", args.model]
    prompts = args.prompts
    stream: list[dict] = []
    results = 0
    child = subprocess.Popen(argv, cwd=dir / "repo", env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=(dir / "stderr.txt").open("w"), text=True)
    timer = threading.Timer(args.timeout, child.kill)
    timer.daemon = True  # an error below must not leave the process waiting for the timer
    timer.start()

    def ask(text: str) -> None:
        try:
            child.stdin.write(json.dumps({"type": "user", "message": {"role": "user", "content": [
                {"type": "text", "text": text}]}}) + "\n")
            child.stdin.flush()
        except BrokenPipeError:
            pass  # claude has exited: its exit code and stderr.txt tell why

    with (dir / "out.jsonl").open("w", encoding="utf-8") as out:
        ask(prompts[0])
        for line in child.stdout:
            out.write(line)
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if msg.get("type") in KEEP or msg.get("subtype") == "hook_response":
                stream.append(msg)
            if msg.get("type") != "result":
                continue
            results += 1
            if results < len(prompts):
                ask(prompts[results])
            else:
                child.stdin.close()
    code = child.wait()
    killed = not timer.is_alive()
    timer.cancel()
    return ("timeout" if killed else code), stream


def hook_evidence(dir: Path, prompts: list[str], exit, stream: list[dict]) -> dict:
    cwd = dir / "repo"
    blocks = [b for m in stream if m.get("type") in ("assistant", "user")
              for b in (m.get("message") or {}).get("content") or [] if isinstance(b, dict)]

    def text_of(content) -> str:
        return content if isinstance(content, str) else "\n".join(c.get("text", "") for c in content or [])

    results = [m for m in stream if m.get("type") == "result"]
    # what Claude Code got back from a hook: shall's answers and any failed hook (managed and
    # project hooks run too, and the stream does not name the plugin of a hook)
    hooks = [cut_values({k: m[k] for k in ("hook_event", "hook_name", "exit_code", "outcome", "stdout", "stderr")
                         if m.get(k) not in (None, "")})
             for m in stream if m.get("subtype") == "hook_response"
             and ("shall" in str(m.get("stdout")) or m.get("outcome") != "success")]
    stop_dirs = sorted((cwd / ".shall" / ".shall-out" / "hooks").glob("stop-*"))
    return {
        "dir": str(dir),
        "exit": exit,
        "turns": [{"prompt": prompts[i] if i < len(prompts) else None, "isError": r.get("is_error"),
                   "result": cut(str(r.get("result") or "")), "totalCostUsd": r.get("total_cost_usd")}
                  for i, r in enumerate(results)],
        "toolUses": [{"name": b["name"], "input": cut_values(b.get("input") or {})}
                     for b in blocks if b.get("type") == "tool_use"],
        "toolResults": [{"isError": bool(b.get("is_error")), "content": cut(text_of(b.get("content")))}
                        for b in blocks if b.get("type") == "tool_result"],
        "hookEvents": hooks,
        "decisions": read_jsonl(decision_log(cwd)),
        "stopReviews": {p.name: findings_summary(p) for p in stop_dirs},
        "changed": git(cwd, "status", "--short", "--untracked-files=all", *NOT_CHANGE).splitlines(),
        "pluginLog": plugin_log(dir / "debug.log"),
    }


def plugin_log(debug: Path) -> list[str]:
    """What the engine said about the plugin: that it loaded, each hook run with its status and
    time, and errors. Each line once, without its time stamp."""
    if not debug.is_file():
        return []
    keep = re.compile(r"shall@inline|Loaded inline plugin from path: shall|plugin shall.*(error|fail|skip|bypass|invalid)",
                      re.I)
    with debug.open(encoding="utf-8") as fh:
        lines = (line.rstrip("\n").split(" ", 1)[-1].replace(str(ROOT) + "/", "") for line in fh if keep.search(line))
        return list(dict.fromkeys(lines))


def cmd_hook(args) -> int:
    dir = new_run(args.base)
    make_repo(dir / "repo", args)
    port = free_port()
    env = {**ENV, "SHALL_HOOKD_PORT": str(port)}
    hookd = start_hookd(dir / "repo", env, port, dir / "hookd.log") if args.hookd else None
    try:
        exit, stream = run_session(dir, args, env)
    finally:
        if hookd:
            hookd.terminate()
            hookd.wait()
    print(json.dumps(hook_evidence(dir, args.prompts, exit, stream), indent=1, ensure_ascii=False))
    return 0


# ---------------------------------------------------------------- cli

def cmd_cli(args) -> int:
    dir = new_run(args.base)
    out = dir / "out"
    argv = [a.replace("{out}", str(out)) for a in args.shall_args]
    t0 = time.perf_counter()
    proc = subprocess.run([str(SHALL), *argv], cwd=ROOT, env=ENV, capture_output=True, text=True)
    res = {"dir": str(dir), "argv": argv, "exit": proc.returncode, "seconds": round(time.perf_counter() - t0, 1),
           "stdout": cut(proc.stdout, 2000), "stderr": cut(proc.stderr, 2000)}
    if out.is_dir():
        res["out"] = findings_summary(out)
    print(json.dumps(res, indent=1, ensure_ascii=False))
    return 0


def cmd_clean(args) -> int:
    dir = Path(args.dir)
    if not dir.name.startswith(PREFIX) or not dir.is_dir():
        raise SystemExit(f"not a run folder: {dir}")
    shutil.rmtree(dir)
    print(f"removed {dir}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(prog="drive.py", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    h = sub.add_parser("hook", help="one headless Claude Code session with the plugin")
    h.add_argument("prompts", nargs="+")
    h.add_argument("--allow", default="Bash,Read,Write,Edit",
                   help="tools the session may use without a prompt (default %(default)s)")
    h.add_argument("--repo", help="fixture folder (relative to the repo root) copied into the new repository")
    h.add_argument("--no-stop", action="store_true", help="turn off the Stop review (no `shall review` run)")
    h.add_argument("--yaml", help="YAML merged into the run's .shall/shall.yaml (hooks.log is followed)")
    h.add_argument("--hookd", action="store_true", help="start `shall hookd` for the run (http path)")
    h.add_argument("--mcp-config", help="MCP servers for the session (JSON file or string)")
    h.add_argument("--model", default="claude-haiku-5-5")  # pinned (JTOOL-0001.4)
    h.add_argument("--budget", type=float, default=0.5, help="--max-budget-usd of the session")
    h.add_argument("--timeout", type=float, default=900, help="seconds before the session is killed")
    h.add_argument("--base", help="parent folder of the run folder (default: the temp folder)")
    h.set_defaults(fn=cmd_hook)
    c = sub.add_parser("cli", help="one shall command from the repo root")
    c.add_argument("--base")
    c.add_argument("shall_args", nargs=argparse.REMAINDER, help="after --: the shall arguments; {out} = output folder")
    c.set_defaults(fn=cmd_cli)
    k = sub.add_parser("clean", help="remove a run folder")
    k.add_argument("dir")
    k.set_defaults(fn=cmd_clean)
    args = p.parse_args()
    if args.cmd == "cli":
        args.shall_args = args.shall_args[1:] if args.shall_args[:1] == ["--"] else args.shall_args
        if not args.shall_args:
            p.error("cli needs the shall arguments after --")
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
