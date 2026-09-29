"""Claude Code hooks: corpus statements applied to an agent's tool calls, judged by Jev.

  PreToolUse   secret scan (code) on every hooked tool, then the `tool` statements whose
               `Tools:` regex matches, judged by Jev on the call itself
               -> deny | ask | warn | log, from RFC status + statement level (`hooks.actions`)
  PostToolUse  after a Write/Edit: the code statements eligible for the file, judged by Jev on
               the written lines plus context -> warn | log only. A fragment is not evidence
               (JTOOL-0002.6): the setting that makes it fine may live in another file.
  Stop         the working-tree change through `jrfc review` (selection, reviewer, verification)
               -> block only on verified blocking findings, at most `stop.max_blocks` per session

Fail-open by design: a Jev error or a timeout lets the call run, and the decision log says so.
The secret scanner redacts every input before it reaches Jev or the log.

Transports share `Hooks.handle`: `jrfc hook` (command hook, one process per call) and
`jrfc hookd` (a localhost HTTP server for `type: http` hooks; the Jev connection stays warm).
"""

from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from .artifact import Chunk, parse_diff
from .config import Config
from .corpus import Corpus, Rfc, Statement
from .jev import Jev, noul

RANK = {"log": 1, "warn": 2, "ask": 3, "deny": 4}


# ---------------------------------------------------------------- secret scanner

# Whole match is secret.
TOKEN_PATTERNS = [
    ("private-key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?(?:-----END [A-Z ]*PRIVATE KEY-----|\Z)")),
    ("aws-access-key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("github-token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{22,})")),
    ("slack-token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
    ("stripe-key", re.compile(r"\b[rs]k_live_[0-9a-zA-Z]{20,}")),
    ("google-api-key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
]
# Only the `v` group is secret: the name around it stays readable for Jev.
VALUE_PATTERNS = [
    ("url-password", re.compile(r"[a-z][a-z0-9+.-]*://[^/\s:@'\"]+:(?P<v>[^@\s/'\"]{3,})@", re.I)),
    ("assigned-secret", re.compile(
        r"(?i)[\w.-]*(?:password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|private[_-]?key)[\w.-]*"
        r"[\"']?\s*(?::|=|=>)\s*[\"'](?P<v>[^\"'\s]{8,})[\"']")),
    ("shell-secret", re.compile(
        r"\b[A-Z0-9_]*(?:PASSWORD|PASSWD|SECRET|TOKEN|API_KEY|APIKEY|ACCESS_KEY)[A-Z0-9_]*="
        r"(?P<v>[^\s\"'$`(<{][^\s\"';|&)]{7,})")),
]
# A value that says it is not real is not a credential (placeholders, fixtures, references).
PLACEHOLDER_RE = re.compile(
    r"(?i)^[x*.]+$|changeme|example|placeholder|dummy|sample|fake|mock|test|your[_-]|redacted|<|\$\{|\{\{|%\(")


@dataclass
class Secret:
    kind: str
    start: int
    end: int


def scan_secrets(text: str) -> list[Secret]:
    found: list[Secret] = []
    for kind, rx in TOKEN_PATTERNS:
        found += [Secret(kind, m.start(), m.end()) for m in rx.finditer(text)]
    for kind, rx in VALUE_PATTERNS:
        for m in rx.finditer(text):
            value = m.group("v")
            if not PLACEHOLDER_RE.search(value):
                found.append(Secret(kind, m.start("v"), m.end("v")))
    found.sort(key=lambda s: (s.start, -s.end))
    merged: list[Secret] = []
    for s in found:  # overlapping hits: keep the first, widest one
        if merged and s.start < merged[-1].end:
            merged[-1].end = max(merged[-1].end, s.end)
            continue
        merged.append(s)
    return merged


def redact(text: str) -> tuple[str, list[str]]:
    """Replace secrets with `[REDACTED:kind]`, keeping line breaks so line numbers hold."""
    secrets = scan_secrets(text)
    out, pos = [], 0
    for s in secrets:
        out.append(text[pos:s.start])
        out.append(f"[REDACTED:{s.kind}]" + "\n" * text.count("\n", s.start, s.end))
        pos = s.end
    out.append(text[pos:])
    return "".join(out), [s.kind for s in secrets]


def redact_value(value, max_chars: int):
    """Redact (and cut) every string in a JSON-like value."""
    if isinstance(value, str):
        text, _ = redact(value)
        return text if len(text) <= max_chars else text[:max_chars] + f"…[cut {len(text) - max_chars} chars]"
    if isinstance(value, dict):
        return {k: redact_value(v, max_chars) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_value(v, max_chars) for v in value]
    return value


def written_text(tool_input: dict) -> str:
    """The text a tool call puts somewhere. `old_string` is left out: removing a secret is fine."""
    parts = []
    for key, value in tool_input.items():
        if key == "old_string":
            continue
        if key == "edits" and isinstance(value, list):
            parts += [str(e.get("new_string", "")) for e in value if isinstance(e, dict)]
        elif isinstance(value, str):
            parts.append(value)
        elif isinstance(value, (dict, list)):
            parts.append(json.dumps(value, ensure_ascii=False))
    return "\n".join(parts)


# ---------------------------------------------------------------- questions and actions

def tool_question(st: Statement):
    return noul(
        f"Does this tool call break the requirement? Requirement: \"{st.text}\" "
        "Answer yes only when the tool call itself, as written, does what the requirement forbids. "
        "Answer no when the call follows the requirement or has nothing to do with it.",
        true=st.violated_when or "The tool call clearly does what the requirement forbids.",
        false="The tool call follows the requirement, or it is about something else.",
    )


def tool_applies_question(rfc: Rfc, st: Statement):
    return noul(
        f"Is this requirement about the kind of action this tool call does? Requirement: \"{st.text}\" "
        "Answer yes when the call does the kind of thing the requirement is about, whether or not it "
        "follows the requirement. Answer no when the call does nothing of that kind.",
        true=st.applies_when or rfc.applies_when,
        false=st.not_applies_when or rfc.not_applies_when,
    )


def code_question(st: Statement):
    return noul(
        f"Does the code added by this change break the requirement? Requirement: \"{st.text}\" "
        "Judge only the added lines (marked '+'); the other lines are context. Answer yes only when "
        "the added code itself clearly breaks the requirement. Answer no when it follows the "
        "requirement, when it contains nothing the requirement is about, or when the lines shown "
        "are not enough to tell.",
        true=st.violated_when or "The added code clearly breaks the requirement.",
        false="The added code follows the requirement, is unrelated to it, or the lines shown are not enough to tell.",
    )


def action_for(actions: dict, rfc: Rfc, st: Statement, p: float) -> str | None:
    for threshold, action in (actions.get(rfc.status) or {}).get(st.level or "", []):
        if p >= float(threshold):
            return action
    return None


def code_action(actions: dict, code_warn: float, rfc: Rfc, st: Statement, p: float) -> str | None:
    """After a write nothing can be denied, and a fragment is not evidence: at most a warning."""
    action = action_for(actions, rfc, st, p)
    if action is None:
        return None
    if RANK[action] >= RANK["warn"]:
        return "warn" if p >= code_warn else "log"
    return action


def strongest(findings: list[dict]) -> str | None:
    acted = [f["action"] for f in findings if f.get("action")]
    return max(acted, key=RANK.__getitem__) if acted else None


def _line(f: dict) -> str:
    p = "scanner" if f["by"] == "scanner" else f"p={f['p']:.2f}"
    where = f" (lines {f['lines']})" if f.get("lines") else ""
    return (f"- {f['id']} {f['title']} [{f['level']}, {f['status']}, {p}]{where}: "
            f"{f['text'][:300]}{' Found: ' + ', '.join(f['secrets']) if f.get('secrets') else ''}")


def pre_output(findings: list[dict]) -> dict:
    top = strongest(findings)
    if top in ("deny", "ask"):
        lines = [_line(f) for f in findings if f.get("action") in ("deny", "ask")]
        verb = "breaks" if top == "deny" else "may break"
        reason = f"jrfc: this tool call {verb} the engineering standards below.\n" + "\n".join(lines)
        if top == "deny":
            reason += "\nDo not retry it as is: follow the requirement, or ask the user for help."
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": top,
                                       "permissionDecisionReason": reason}}
    if top == "warn":
        lines = [_line(f) for f in findings if f.get("action") == "warn"]
        return {"hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "additionalContext": "jrfc: this tool call may go against these engineering standards "
                                         "(recommendations; explain if you keep it):\n" + "\n".join(lines)},
                "systemMessage": "jrfc: " + ", ".join(f["id"] for f in findings if f.get("action") == "warn")}
    return {}


def post_output(findings: list[dict], path: str) -> dict:
    warns = [f for f in findings if f.get("action") == "warn"]
    if not warns:
        return {}
    return {"hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": f"jrfc: the code just written to {path} may break these engineering "
                                     "standards. Check each one against the full code; fix it, or keep it if "
                                     "the context shows it is fine:\n" + "\n".join(_line(f) for f in warns)},
            "systemMessage": f"jrfc: {path}: " + ", ".join(f["id"] for f in warns)}


# ---------------------------------------------------------------- written lines -> diff chunk

def changed_ranges(tool: str, tool_input: dict, text: str) -> list[tuple[int, int]] | None:
    """1-based inclusive line ranges the call wrote, found in the file as it is now."""
    lines = text.count("\n") + (0 if text.endswith("\n") else 1)
    if tool == "Write":
        return [(1, max(lines, 1))]
    news = []
    if tool == "Edit":
        news = [(tool_input.get("new_string") or "", bool(tool_input.get("replace_all")))]
    elif tool == "MultiEdit":
        news = [(e.get("new_string") or "", bool(e.get("replace_all"))) for e in tool_input.get("edits") or []]
    else:
        return None  # NotebookEdit and others: not supported yet
    ranges = []
    for new, every in news:
        if not new.strip():
            continue  # a deletion adds no code
        pos = text.find(new)
        while pos != -1:
            first = text.count("\n", 0, pos) + 1
            ranges.append((first, first + new.rstrip("\n").count("\n")))
            if not every:
                break
            pos = text.find(new, pos + len(new))
    return sorted(set(ranges))


def synthetic_diff(rel: str, text: str, ranges: list[tuple[int, int]], context: int) -> str:
    """A unified diff that marks the written lines as added, with context lines around them."""
    lines = text.splitlines()
    added = {n for a, b in ranges for n in range(a, b + 1)}
    windows: list[list[int]] = []
    for a, b in ranges:
        lo, hi = max(1, a - context), min(len(lines), b + context)
        if windows and lo <= windows[-1][1] + 1:
            windows[-1][1] = max(windows[-1][1], hi)
        else:
            windows.append([lo, hi])
    out = [f"diff --git a/{rel} b/{rel}", f"--- a/{rel}", f"+++ b/{rel}"]
    for lo, hi in windows:
        n = hi - lo + 1
        n_old = sum(1 for i in range(lo, hi + 1) if i not in added)
        out.append(f"@@ -{lo},{n_old} +{lo},{n} @@")
        out += [("+" if i in added else " ") + lines[i - 1] for i in range(lo, hi + 1)]
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- git helpers

def _git(cwd: str | Path, *args: str, ok=(0,)) -> str | None:
    try:
        r = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout if r.returncode in ok else None


# jrfc's own caches and outputs are never part of the change, even where .gitignore misses them
NOT_CHANGE = ["--", ".", ":(exclude,glob)**/.jrfc-cache/**", ":(exclude,glob)**/.jrfc-out/**"]


def working_diff(root: Path) -> str:
    """Tracked changes against HEAD plus untracked (not ignored) files as new files."""
    diff = _git(root, "diff", "--no-color", "HEAD", *NOT_CHANGE) or _git(root, "diff", "--no-color", *NOT_CHANGE) or ""
    for name in (_git(root, "ls-files", "--others", "--exclude-standard", "-z", *NOT_CHANGE) or "").split("\0"):
        if name:
            diff += _git(root, "diff", "--no-color", "--no-index", "/dev/null", name, ok=(0, 1)) or ""
    return diff


# ---------------------------------------------------------------- the hooks

class Hooks:
    def __init__(self, cfg: Config, corpus: Corpus, jev: Jev, statuses: list[str] | None = None,
                 timeout: float | None = -1, log: bool = True, score: str = "both"):
        self.cfg = cfg
        self.corpus = corpus
        self.jev = jev
        self.actions = cfg.get("hooks.actions") or {}
        self.statuses = set(statuses if statuses is not None else self.actions)
        self.timeout = float(cfg.get("hooks.timeout")) if timeout == -1 else timeout
        self.max_chars = int(cfg.get("hooks.max_input_chars"))
        self.pre_rx = re.compile(cfg.get("hooks.pre_matcher"))
        self.code_rx = re.compile(cfg.get("hooks.code_tools"))
        self.secret_rules = [(re.compile(rx), sid) for rx, sid in cfg.get("hooks.secrets") or []]
        self.log_path = (cfg.root / cfg.get("hooks.log")) if log else None
        self.jev_failed = False  # a Jev error (not a timeout) happened in this process
        # both: a statement counts as broken with p = min(applies, violates), asked in the same
        # request (no extra latency); the "applies" question keeps off-topic rules quiet.
        # violation: the violation question alone (eval A/B).
        self.score = score

    # -- entry point shared by `jrfc hook` and `jrfc hookd`
    async def handle(self, event: dict) -> dict:
        if os.environ.get("JRFC_HOOKS_DISABLED") or not self.cfg.get("hooks.enabled", True):
            return {}  # env: set for the agents jrfc itself runs (review.run_claude)
        name = event.get("hook_event_name")
        t0 = time.perf_counter()
        record: dict = {"event": name, "session": event.get("session_id")}
        try:
            if name == "PreToolUse":
                out = await self.pre(event, record)
            elif name == "PostToolUse":
                out = await self.post(event, record)
            elif name == "Stop":
                out = await self.stop(event, record)
            else:
                out = {}
        except Exception as err:  # fail-open: a bug in a hook must not stop the agent
            record["error"] = f"{type(err).__name__}: {redact(str(err))[0][:300]}"
            out = {"systemMessage": f"jrfc hook error, call not checked: {record['error']}"}
        record["ms"] = round((time.perf_counter() - t0) * 1000)
        record["output"] = (out.get("hookSpecificOutput") or {}).get("permissionDecision") or \
            out.get("decision") or ("warn" if out else "none")
        self._log(record)
        return out

    def _log(self, record: dict) -> None:
        if not self.log_path:
            return
        record = {"ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), **record}
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _finding(self, rfc: Rfc, st: Statement, p: float, action: str | None, by: str, **extra) -> dict:
        return {"id": st.id, "title": st.title, "level": st.level, "status": rfc.status, "text": st.text,
                "p": round(p, 4), "action": action, "by": by, **extra}

    async def _judge(self, state, cands: list[tuple[Rfc, Statement]], violated, applies,
                     record: dict) -> dict[str, float] | None:
        """p per statement id that the content breaks it, or None when Jev did not answer."""
        questions = {st.id: violated(st) for _, st in cands}
        if self.score == "both":
            questions |= {f"{st.id}#applies": applies(rfc, st) for rfc, st in cands}
        ans = await self._ask(state, questions, record)
        if ans is None:
            return None
        if self.score != "both":
            return {st.id: ans[st.id]["p"] for _, st in cands}
        record.setdefault("applies", {}).update({st.id: ans[f"{st.id}#applies"]["p"] for _, st in cands})
        record.setdefault("violates", {}).update({st.id: ans[st.id]["p"] for _, st in cands})
        return {st.id: min(ans[st.id]["p"], ans[f"{st.id}#applies"]["p"]) for _, st in cands}

    async def _ask(self, state, questions: dict, record: dict) -> dict | None:
        """Jev answers, or None when Jev is slow or down: the call then runs unchecked."""
        if not self.jev.available():
            record["jev"] = "no TYPESAFE_API_KEY"  # the secret scanner still runs
            return None
        requests_before = self.jev.usage["requests"]
        task = asyncio.ensure_future(self.jev.ask(state, questions))
        try:
            # shield: past the timeout the answer still lands in the cache for the next call
            ans = await (asyncio.wait_for(asyncio.shield(task), self.timeout) if self.timeout else task)
        except asyncio.TimeoutError:
            record["jev"] = "timeout"
            return None
        except Exception as err:
            self.jev_failed = True
            record["jev"] = f"error: {type(err).__name__}: {redact(str(err))[0][:200]}"
            return None
        record["jev"] = "request" if self.jev.usage["requests"] > requests_before else "cached"
        return ans

    # -- PreToolUse
    def git_branch(self, cwd: str) -> str:
        """A fact for Jev: `git push` alone pushes the current branch."""
        return (_git(cwd, "symbolic-ref", "--short", "HEAD") or "").strip()  # also on an unborn branch

    def tool_candidates(self, tool: str) -> list[tuple[Rfc, Statement]]:
        out = []
        for rfc, st in self.corpus.statements():
            if rfc.status not in self.statuses or "tool" not in (st.artifacts or rfc.artifacts):
                continue
            if st.enforcement != "agent":
                continue  # linter: the secret scanner or another check owns it; human: not for hooks
            if st.tools and not re.fullmatch(st.tools, tool):
                continue
            out.append((rfc, st))
        return out

    def scan(self, tool: str, tool_input: dict) -> list[dict]:
        kinds = [s.kind for s in scan_secrets(written_text(tool_input))]
        if not kinds:
            return []
        sid = next((sid for rx, sid in self.secret_rules if rx.fullmatch(tool)), None)
        hit = self.corpus.statement(sid) if sid else None
        if not hit:
            return []
        rfc, st = hit
        action = action_for(self.actions, rfc, st, 1.0) if rfc.status in self.statuses else None
        return [self._finding(rfc, st, 1.0, action, "scanner", secrets=sorted(set(kinds)))]

    async def pre(self, event: dict, record: dict) -> dict:
        tool = event.get("tool_name") or ""
        tool_input = event.get("tool_input") or {}
        record["tool"] = tool
        if not self.pre_rx.fullmatch(tool):
            return {}
        findings = self.scan(tool, tool_input)
        record["scanner"] = [f["id"] for f in findings]
        cands = self.tool_candidates(tool)
        safe_input = redact_value(tool_input, self.max_chars)
        record["input"] = redact_value(tool_input, 500)
        record["candidates"] = len(cands)
        if cands:
            state = {"tool": tool, "input": safe_input, "cwd": event.get("cwd") or ""}
            if tool == "Bash" and event.get("cwd"):
                branch = self.git_branch(event["cwd"])
                if branch:
                    state["git_branch"] = branch
            ps = await self._judge(state, cands, tool_question, tool_applies_question, record)
            if ps:
                record["scores"] = ps
                for rfc, st in cands:
                    p = ps[st.id]
                    findings.append(self._finding(rfc, st, p, action_for(self.actions, rfc, st, p), "jev"))
        record["findings"] = [{k: f[k] for k in ("id", "p", "action", "by")} for f in findings if f["action"]]
        return pre_output(findings)

    # -- PostToolUse
    def code_chunks(self, event: dict, record: dict) -> tuple[list[Chunk], str] | None:
        tool = event.get("tool_name") or ""
        tool_input = event.get("tool_input") or {}
        raw_path = tool_input.get("file_path")
        if not raw_path:
            return None
        cwd = Path(event.get("cwd") or ".")
        path = Path(raw_path) if Path(raw_path).is_absolute() else cwd / raw_path
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            record["skip"] = "unreadable file"
            return None
        ranges = changed_ranges(tool, tool_input, text)
        if not ranges:
            record["skip"] = "no written lines found" if ranges is not None else f"{tool} not supported"
            return None
        rel = os.path.relpath(path, cwd) if path.is_relative_to(cwd) else str(path)
        safe_text, _ = redact(text)
        diff = synthetic_diff(rel, safe_text, ranges, int(self.cfg.get("hooks.context_lines")))
        record["lines"] = ",".join(f"{a}-{b}" if a != b else str(a) for a, b in ranges)
        return parse_diff(diff, int(self.cfg.get("jev.max_chunk_chars"))), rel

    async def post(self, event: dict, record: dict) -> dict:
        from .select import Selector, statement_question
        tool = event.get("tool_name") or ""
        record["tool"] = tool
        if not self.code_rx.fullmatch(tool):
            return {}
        built = self.code_chunks(event, record)
        if not built:
            return {}
        chunks, rel = built
        record["file"] = rel
        selector = Selector(self.cfg, self.corpus, self.jev, include_status=sorted(self.statuses))
        code_warn = float(self.cfg.get("hooks.code_warn"))
        findings: list[dict] = []
        scores: dict[str, float] = {}
        for chunk in chunks:
            cands = selector.eligible(chunk)
            record["candidates"] = record.get("candidates", 0) + len(cands)
            if not cands:
                continue
            ps = await self._judge(chunk.state(), cands, code_question,
                                   lambda rfc, st: statement_question(rfc, st, "diff"), record)
            if not ps:
                continue
            for rfc, st in cands:
                p = ps[st.id]
                scores[st.id] = max(scores.get(st.id, 0.0), p)
                findings.append(self._finding(rfc, st, p, code_action(self.actions, code_warn, rfc, st, p),
                                              "jev", lines=record.get("lines")))
        record["scores"] = scores
        record["findings"] = [{k: f[k] for k in ("id", "p", "action")} for f in findings if f["action"]]
        return post_output(findings, rel)

    # -- Stop
    async def stop(self, event: dict, record: dict) -> dict:
        if not self.cfg.get("hooks.stop.enabled"):
            return {}
        cwd = event.get("cwd") or "."
        top = (_git(cwd, "rev-parse", "--show-toplevel") or "").strip()
        if not top:
            return {}
        root = Path(top)
        diff = working_diff(root)
        if not diff.strip():
            return {}
        sha = hashlib.sha256(diff.encode()).hexdigest()[:16]
        session = re.sub(r"[^A-Za-z0-9_-]", "_", str(event.get("session_id") or "default"))
        state_path = self.cfg.root / ".jrfc-cache" / "hooks" / f"stop-{session}.json"
        state = json.loads(state_path.read_text()) if state_path.is_file() else {"blocks": 0}
        record["diff"] = sha
        if state.get("reviewed") == sha:
            record["skip"] = "change already reviewed"
            return {}
        if len(diff) > int(self.cfg.get("hooks.stop.max_diff_chars")):
            record["skip"] = "change too large"
            return {"systemMessage": f"jrfc: the change is too large for the stop review ({len(diff)} chars); "
                                     "run `jrfc review` on it"}
        # one review per change at a time, whatever the session: a nested agent session (or a
        # second window) that stops on the same change must not start a second review
        lock = self.cfg.root / ".jrfc-cache" / "hooks" / f"stop-running-{sha}"
        if lock.is_file() and time.time() - lock.stat().st_mtime < 900:
            record["skip"] = "same change is being reviewed"
            return {}
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text(session, encoding="utf-8")
        try:
            return await self._stop_review(diff, sha, session, root, state, state_path, record)
        finally:
            lock.unlink(missing_ok=True)

    async def _stop_review(self, diff: str, sha: str, session: str, root: Path, state: dict,
                           state_path: Path, record: dict) -> dict:
        out_dir = self.cfg.root / ".jrfc-out" / "hooks" / f"stop-{session}"
        out_dir.mkdir(parents=True, exist_ok=True)
        diff_path = out_dir / "change.diff"
        diff_path.write_text(diff, encoding="utf-8")
        cmd = [sys.executable, "-m", "jrfc.cli", *(["--config", str(self.cfg.path)] if self.cfg.path else []),
               "review", str(diff_path), "--out-dir", str(out_dir), "--search-root", str(root)]
        proc = await asyncio.create_subprocess_exec(*cmd, cwd=str(root), stdout=asyncio.subprocess.DEVNULL,
                                                    stderr=asyncio.subprocess.PIPE,
                                                    env={**os.environ, "JRFC_HOOKS_DISABLED": "1"})
        _, err = await proc.communicate()
        record["review_exit"] = proc.returncode
        findings_path = out_dir / "findings.json"
        if proc.returncode not in (0, 2) or not findings_path.is_file():
            return {"systemMessage": f"jrfc: stop review failed (exit {proc.returncode}): "
                                     f"{redact(err.decode(errors='replace').strip()[-300:])[0]}"}
        findings = json.loads(findings_path.read_text(encoding="utf-8"))["findings"]
        blocking = [f for f in findings if f.get("blocking")]
        state["reviewed"] = sha
        record["findings"] = [{"id": f["statement_id"], "blocking": f["blocking"]} for f in findings]
        out: dict = {}
        if blocking and state.get("blocks", 0) < int(self.cfg.get("hooks.stop.max_blocks")):
            state["blocks"] = state.get("blocks", 0) + 1
            lines = [f"- {f['statement_id']} {f['title']} at {f['path']}:{f.get('line') or '?'}: "
                     f"{f['message']}" + (f" Suggestion: {f['suggestion']}" if f.get("suggestion") else "")
                     for f in blocking]
            out = {"decision": "block",
                   "reason": "jrfc review found verified blocking findings in the change. Fix them before "
                             f"you finish (full report: {out_dir / 'review.md'}):\n" + "\n".join(lines)}
        elif findings:
            out = {"systemMessage": f"jrfc: stop review: {len(findings)} finding(s), {len(blocking)} blocking; "
                                    f"see {out_dir / 'review.md'}"}
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(state), encoding="utf-8")
        return out


# ---------------------------------------------------------------- settings and daemon

def hook_settings(cfg: Config, transport: str, port: int, command: str, stop: bool) -> dict:
    """The `hooks` block for .claude/settings.json (deterministic, no model call)."""
    def handler(timeout: int) -> dict:
        if transport == "http":
            h = {"type": "http", "url": f"http://127.0.0.1:{port}/hook-events", "timeout": timeout}
            if os.environ.get("JRFC_HOOK_TOKEN"):
                h |= {"headers": {"Authorization": "Bearer $JRFC_HOOK_TOKEN"}, "allowedEnvVars": ["JRFC_HOOK_TOKEN"]}
            return h
        return {"type": "command", "command": f"{command} hook", "timeout": timeout}
    fast = int(float(cfg.get("hooks.timeout")) + 3)
    out = {"PreToolUse": [{"matcher": cfg.get("hooks.pre_matcher"), "hooks": [handler(fast)]}],
           "PostToolUse": [{"matcher": cfg.get("hooks.code_tools"), "hooks": [handler(fast)]}]}
    if stop:
        out["Stop"] = [{"hooks": [handler(600)]}]
    return {"hooks": out}


EVENT_FIELDS = {"hook_event_name": str, "session_id": str, "cwd": str, "tool_name": str, "tool_input": dict}


def valid_event(body: bytes) -> dict | None:
    """The event if it has the shape of a Claude Code hook event, else None (answered 400)."""
    try:
        event = json.loads(body or b"null")
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(event, dict) or not isinstance(event.get("hook_event_name"), str):
        return None
    if any(k in event and not isinstance(event[k], t) for k, t in EVENT_FIELDS.items()):
        return None
    return event


async def serve(hooks: Hooks, host: str, port: int, root: Path) -> None:
    """Minimal HTTP/1.1 server for Claude Code `type: http` hooks: POST /hook-events, GET /health.

    Localhost only. Browsers cannot send a cross-origin `application/json` POST without a
    preflight (answered 404), and JRFC_HOOK_TOKEN, when set, is required as a bearer token.
    Events whose `cwd` is outside this repository get 421: Claude Code lets the call run, and
    the plugin's `jrfc-hook` falls back to `jrfc hook` for that repository.
    """
    token = os.environ.get("JRFC_HOOK_TOKEN")

    async def respond(writer, status: str, body: dict | None = None) -> None:
        code, _, title = status.partition(" ")
        # errors as RFC 9457 problem details, without internal exception text (JRFC-0002.3)
        kind = "application/json" if code == "200" else "application/problem+json"
        payload = body if code == "200" else {"type": "about:blank", "title": title, "status": int(code)}
        data = json.dumps(payload).encode()
        writer.write(f"HTTP/1.1 {status}\r\nContent-Type: {kind}\r\nContent-Length: {len(data)}\r\n"
                     "Connection: close\r\n\r\n".encode() + data)
        await writer.drain()

    async def on_conn(reader, writer):
        try:
            head = (await reader.readuntil(b"\r\n\r\n")).decode("latin-1").split("\r\n")
            method, target = head[0].split(" ")[:2]
            headers = {k.strip().lower(): v.strip() for k, _, v in (h.partition(":") for h in head[1:] if h)}
            body = await reader.readexactly(int(headers.get("content-length") or 0))
            if method == "GET" and target == "/health":
                await respond(writer, "200 OK", {"ok": True, "root": str(root), "usage": hooks.jev.usage})
            elif method != "POST" or target != "/hook-events" or "json" not in headers.get("content-type", ""):
                await respond(writer, "404 Not Found")
            elif token and headers.get("authorization") != f"Bearer {token}":
                await respond(writer, "401 Unauthorized")
            elif (event := valid_event(body)) is None:
                await respond(writer, "400 Bad Request")
            else:
                cwd = Path(event.get("cwd") or root).resolve()
                if cwd == root or cwd.is_relative_to(root):
                    await respond(writer, "200 OK", await hooks.handle(event))
                else:
                    await respond(writer, "421 Misdirected Request")
        except Exception as err:  # fail-open: Claude Code treats a non-2xx answer as a non-blocking error
            hooks._log({"event": "hookd", "error": f"{type(err).__name__}: {redact(str(err))[0][:300]}"})
            try:
                await respond(writer, "500 Internal Server Error")
            except Exception:
                pass
        finally:
            writer.close()

    async def save_cache():
        seen = -1
        while True:
            await asyncio.sleep(30)
            if hooks.jev.usage["requests"] != seen:
                seen = hooks.jev.usage["requests"]
                hooks.jev.save()

    server = await asyncio.start_server(on_conn, host, port)
    saver = asyncio.create_task(save_cache())
    print(f"jrfc hookd: listening on http://{host}:{port}/hook-events for {root}", file=sys.stderr)
    try:
        async with server:
            await server.serve_forever()
    finally:
        saver.cancel()
