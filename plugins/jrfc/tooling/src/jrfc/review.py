"""Agent review of the selected statements, then deterministic validation and reports.

The agent (Claude Code in print mode, with the plugin's jrfc-reviewer prompt) only sees
one chunk and the statements Jev selected for it. Code then checks every finding:
the statement was selected for that chunk, the line is a changed line (or the quote
exists), and severity is recomputed from the corpus instead of trusted from the model.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import time
from pathlib import Path

from .artifact import Artifact, Chunk
from .config import Config
from .corpus import Corpus

FINDINGS_SCHEMA = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "statement_id": {"type": "string"},
                    "line": {"type": ["integer", "null"]},
                    "quote": {"type": "string"},
                    "message": {"type": "string"},
                    "suggestion": {"type": "string"},
                    "depends_on": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["statement_id", "line", "quote", "message", "depends_on"],
            },
        }
    },
    "required": ["findings"],
}


def plugin_root() -> Path:
    env = os.environ.get("JRFC_PLUGIN_ROOT")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[3]  # tooling/src/jrfc/review.py -> plugins/jrfc


def agent_prompt(name: str) -> str:
    """The body of agents/<name>.md: one prompt for interactive and CI use (JTOOL-0004.2)."""
    text = (plugin_root() / "agents" / f"{name}.md").read_text(encoding="utf-8")
    if text.startswith("---"):
        text = text.split("---", 2)[2]
    return text.strip()


def reviewer_prompt() -> str:
    return agent_prompt("jrfc-reviewer")


def render_statements(corpus: Corpus, ids: list[str]) -> str:
    lines = []
    for sid in ids:
        rfc, st = corpus.statement(sid)
        flag = "blocking" if rfc.statement_blocking(st) else "non-blocking"
        lines.append(f"- {sid} [{st.level}, {flag}] {st.title}: {st.text}")
        lines.append(f"  Applies when: {st.applies_when or rfc.applies_when}")
    return "\n".join(lines)


def chunk_prompt(corpus: Corpus, chunk: Chunk, ids: list[str], facts: list[str] | None = None) -> str:
    anchor = (
        "Only lines marked '+' (added) can carry a finding; use their line number."
        if chunk.kind == "diff" else
        "Use the line number shown before '|'. Use line null for a finding about something missing from the whole document."
    )
    return (
        f"<chunk kind=\"{chunk.kind}\" file=\"{chunk.path}\" language=\"{chunk.language}\">\n"
        f"{chunk.rendered}\n</chunk>\n\n"
        + (f"<known_effects>\nFacts found by code (effects registry and code graph) about what the "
           f"code in the chunk calls:\n" + "\n".join(f"- {x}" for x in facts) + "\n</known_effects>\n\n"
           if facts else "")
        + f"<standards>\n{render_statements(corpus, ids)}\n</standards>\n\n"
        f"{anchor}\nReturn only violations of the standards listed above. "
        "Return an empty findings list when the chunk complies."
    )


def write_bundle(corpus: Corpus, artifact: Artifact, selection: dict, out: Path) -> Path:
    """Human/agent-readable review bundle for interactive use inside Claude Code."""
    chunks = {c.id: c for c in artifact.chunks}
    parts = [
        f"# jrfc review bundle — {artifact.source}",
        "",
        "For each chunk, check only the listed standards. Write all findings to one JSON file",
        "with the shape `{\"findings\": [{\"chunk\": \"c0\", \"statement_id\": ..., \"line\": ..., "
        "\"quote\": ..., \"message\": ..., \"suggestion\": ...}]}`, then run",
        f"`jrfc validate <findings.json> --selection <selection.json> {artifact.source}`.",
        "",
    ]
    for c in selection["chunks"]:
        if not c["selected"]:
            continue
        parts += [f"## Chunk {c['id']} — {c['path']}", "", chunk_prompt(corpus, chunks[c["id"]], c["selected"], c.get("known_effects")), ""]
    out.write_text("\n".join(parts), encoding="utf-8")
    return out


class AnswerCache:
    """Agent answers keyed by exactly what the agent was given (model, system prompt, schema,
    prompt). A re-run on a new push reuses the answer for every chunk whose prompt did not
    change (same diff, same selected statements, same known effects), and for every
    verification whose evidence did not change. Only successful answers are stored; entries
    unused for `MAX_AGE_DAYS` are dropped on save. Merge-safe like the Jev cache."""

    MAX_AGE_DAYS = 30

    def __init__(self, path: Path | None):
        self.path = path
        self.entries: dict = {}
        self.reused = 0
        if path is not None and path.is_file():
            try:
                self.entries = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                self.entries = {}

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
        self.path.parent.mkdir(parents=True, exist_ok=True)
        merged: dict = {}
        if self.path.is_file():
            try:
                merged = json.loads(self.path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                merged = {}
        merged.update(self.entries)
        cutoff = time.time() - self.MAX_AGE_DAYS * 86400
        merged = {k: v for k, v in merged.items() if v.get("used", 0) >= cutoff}
        tmp = self.path.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(merged, sort_keys=True), encoding="utf-8")
        os.replace(tmp, self.path)


def answer_cache(cfg: Config, enabled: bool = True) -> AnswerCache:
    """The review answer cache next to the Jev cache (`review.cache: false` disables it)."""
    if not enabled or not cfg.get("review.cache", True):
        return AnswerCache(None)
    return AnswerCache(cfg.cache_file.parent / "review.json")


async def run_claude(cfg: Config, prompt: str, system: str, schema: dict,
                     sem: asyncio.Semaphore, model: str | None = None,
                     cache: AnswerCache | None = None) -> tuple[dict | None, dict]:
    """One tool-less Claude call with a JSON schema (JTOOL-0002.1). Returns (output, meta).
    With `cache`, an identical earlier call is reused (meta has `cached: True`, no cost)."""
    model = model or cfg.get("review.model")
    key = AnswerCache.key(model, system, schema, prompt) if cache is not None else None
    if key is not None:
        hit = cache.get(key)
        if hit is not None:
            return hit, {"cost_usd": 0.0, "cached": True}
    cmd = list(cfg.get("review.command")) + [
        "--model", model,
        "--output-format", "json",
        "--json-schema", json.dumps(schema),
        "--system-prompt", system,
        "--tools", "",
        "--no-session-persistence",
        "--strict-mcp-config",
        "--setting-sources", "",
    ]
    async with sem:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            # a pipeline agent never triggers jrfc hooks: its Stop would start another review
            env={**os.environ, "JRFC_HOOKS_DISABLED": "1"},
        )
        try:
            out, err = await asyncio.wait_for(proc.communicate(prompt.encode()),
                                              timeout=float(cfg.get("review.timeout")))
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return None, {"error": f"agent timed out after {cfg.get('review.timeout')}s"}
    if proc.returncode != 0:
        return None, {"error": err.decode()[-2000:] or out.decode()[-2000:]}
    data = json.loads(out.decode())
    result = data.get("structured_output")
    if result is None:  # fall back to parsing the text result
        m = re.search(r"\{.*\}", data.get("result", ""), re.S)
        result = json.loads(m.group(0)) if m else None
    if key is not None and result is not None:
        cache.put(key, result)
    return result, {"cost_usd": data.get("total_cost_usd", 0.0), "usage": data.get("usage") or {},
                    "models": sorted(data.get("modelUsage") or {})}


async def _run_agent(cfg: Config, prompt: str, sem: asyncio.Semaphore,
                     cache: AnswerCache | None = None) -> tuple[list[dict], dict]:
    result, meta = await run_claude(cfg, prompt, reviewer_prompt(), FINDINGS_SCHEMA, sem, cache=cache)
    return (result or {}).get("findings", []), meta


async def run_agents(cfg: Config, corpus: Corpus, artifact: Artifact, selection: dict,
                     prompts_dir: Path | None = None, cache: AnswerCache | None = None) -> tuple[list[dict], dict]:
    chunks = {c.id: c for c in artifact.chunks}
    sem = asyncio.Semaphore(int(cfg.get("review.concurrency")))
    jobs = []
    for c in selection["chunks"]:
        if not c["selected"]:
            continue
        prompt = chunk_prompt(corpus, chunks[c["id"]], c["selected"], c.get("known_effects"))
        if prompts_dir:
            prompts_dir.mkdir(parents=True, exist_ok=True)
            (prompts_dir / f"{c['id']}.md").write_text(prompt, encoding="utf-8")
        jobs.append((c["id"], _run_agent(cfg, prompt, sem, cache)))
    results = await asyncio.gather(*(job for _, job in jobs))
    raw, stats = [], {"agent_calls": 0, "reused": 0, "cost_usd": 0.0, "errors": []}
    for (cid, _), (findings, meta) in zip(jobs, results):
        stats["reused" if meta.get("cached") else "agent_calls"] += 1
        for f in findings:
            raw.append({"chunk": cid, **f})
        if "error" in meta:
            stats["errors"].append({"chunk": cid, "error": meta["error"]})
        stats["cost_usd"] = round(stats["cost_usd"] + meta.get("cost_usd", 0.0), 6)
    return raw, stats


def _norm(text: str) -> str:
    return " ".join((text or "").split())


def _anchor(chunk: Chunk, line, quote: str) -> tuple[int | None, str | None]:
    """Resolve the line a finding points at. The quote wins over the line number."""
    def text(n: int) -> str:
        return _norm(chunk.line_text.get(n, ""))
    if line in chunk.anchor_lines and (not quote or quote in text(line)):
        return line, None
    hits = [n for n in sorted(chunk.anchor_lines) if quote and quote in text(n)]
    if hits:
        return min(hits, key=lambda n: abs(n - (line or n))), None
    if line in chunk.anchor_lines:
        return line, None  # quote paraphrased, but the line is a real changed line
    if line is None and chunk.kind != "diff":
        return None, None  # document-level finding ("section X is missing")
    return None, f"line {line} / quote not found among commentable lines of {chunk.path}"


def validate_findings(corpus: Corpus, artifact: Artifact, selection: dict, raw: list[dict],
                      max_comments: int) -> tuple[list[dict], list[dict]]:
    chunks = {c.id: c for c in artifact.chunks}
    selected = {c["id"]: set(c["selected"]) for c in selection["chunks"]}
    kept, dropped, seen = [], [], set()
    for f in raw:
        reason = None
        cid = f.get("chunk")
        chunk = chunks.get(cid)
        sid = f.get("statement_id", "")
        line = f.get("line")
        quote = _norm(f.get("quote", ""))
        if chunk is None:
            reason = f"unknown chunk {cid!r}"
        elif sid not in selected.get(cid, set()):
            reason = f"{sid} was not selected for chunk {cid}"
        elif corpus.statement(sid) is None:
            reason = f"{sid} does not exist in the corpus"
        else:
            line, reason = _anchor(chunk, line, quote)
        if reason:
            dropped.append({**f, "reason": reason})
            continue
        rfc, st = corpus.statement(sid)
        key = (sid, chunk.path, line)
        if key in seen:
            dropped.append({**f, "reason": "duplicate"})
            continue
        seen.add(key)
        kept.append({
            "statement_id": sid, "rfc": rfc.id, "title": st.title, "level": st.level,
            "blocking": rfc.statement_blocking(st),  # recomputed, never trusted from the model
            "path": chunk.path, "line": line, "quote": f.get("quote", ""),
            "message": f.get("message", ""), "suggestion": f.get("suggestion", ""),
            "depends_on": [str(d) for d in f.get("depends_on") or []][:8],
            "chunk": cid, "statement_text": st.text,
            "source": corpus.source(rfc, st.line),
        })
    kept.sort(key=lambda k: (not k["blocking"], k["path"], k["line"] or 0, k["statement_id"]))
    if len(kept) > max_comments:
        for k in kept[max_comments:]:
            dropped.append({**k, "reason": f"over max_comments={max_comments}"})
        kept = kept[:max_comments]
    return kept, dropped


def render_markdown(artifact: Artifact, selection: dict, findings: list[dict], dropped: list[dict],
                    health: dict | None = None) -> str:
    blocking = sum(1 for f in findings if f["blocking"])
    out = [
        f"## jrfc review — `{artifact.source}`",
        "",
        f"**{len(findings)} finding(s)**, {blocking} blocking · "
        f"{len(selection['applicable'])} applicable statement(s) selected by `{selection['model']}` "
        f"({selection['strategy']}) · {len(dropped)} finding(s) dropped by validation or verification",
        "",
    ]
    if health is not None:
        from .health import render_health
        out += render_health(health)
    if selection["applicable"]:
        out += ["<details><summary>Applicable standards</summary>", ""]
        for a in selection["applicable"]:
            out.append(f"- `{a['id']}` {a['title']} ({a['level']}, p={a['p_max']:.2f})")
        out += ["", "</details>", ""]
    for f in findings:
        where = f"`{f['path']}:{f['line']}`" if f["line"] else f"`{f['path']}` (whole document)"
        tag = "🚫 blocking" if f["blocking"] else "💬 advisory"
        out.append(f"- {tag} **{f['statement_id']}** {f['title']} — {where}")
        out.append(f"  {f['message']}")
        if f.get("suggestion"):
            out.append(f"  _Suggestion:_ {f['suggestion']}")
        if f.get("verification"):
            out.append(f"  {verification_line(f)}")
    return "\n".join(out).rstrip() + "\n"


def line_hash(text: str) -> str:
    """Hash of a line's content: stable when the line moves, new when the line changes."""
    return hashlib.sha1(_norm(text).encode()).hexdigest()[:12]


def finding_key(statement_id: str, path: str, lhash: str) -> str:
    return hashlib.sha1(f"{statement_id}|{path}|{lhash}".encode()).hexdigest()[:16]


MARKER_RE = re.compile(r"<!-- jrfc:finding key=([0-9a-f]+) line=([0-9a-f]+) -->")
SUMMARY_MARKER = "<!-- jrfc:summary -->"


def verification_line(f: dict) -> str:
    v = f["verification"]
    where = f" ({', '.join(v['evidence'])})" if v.get("evidence") else ""
    if v["verdict"] == "confirmed":
        return f"_Verified{where}:_ {v['reason']}"
    note = "not blocking: the evidence it depends on was not seen" if f.get("downgraded") else "could not be verified"
    return f"_Unverified — {note}:_ {v['reason']}"


def comment_body(f: dict, key: str | None = None, lhash: str | None = None) -> str:
    tag = "🚫 **blocking**" if f["blocking"] else "💬 advisory"
    body = f"{tag} · **{f['statement_id']}** {f['title']} ({f['level']})\n\n{f['message']}"
    if f.get("suggestion"):
        body += f"\n\n**Suggestion:** {f['suggestion']}"
    if f.get("verification"):
        body += f"\n\n{verification_line(f)}"
    body += f"\n\n> {f['statement_text']}\n\n<sub>Standard: `{f['source']}`</sub>"
    if key:
        body += f"\n\n<!-- jrfc:finding key={key} line={lhash} -->"
    return body


def render_github(artifact: Artifact, selection: dict, findings: list[dict], dropped: list[dict],
                  health: dict | None = None) -> dict:
    """Review payload plus the state `jrfc publish` needs to dedupe across pushes.

    Each inline comment carries a hidden key = hash(statement, path, line content). The
    line content (not the line number) is used so a finding keeps its key when code above
    it moves, and gets a new key when the line itself is changed.
    """
    text_by_path: dict[str, dict[int, str]] = {}
    added: dict[str, set[str]] = {}
    for c in artifact.chunks:
        text_by_path.setdefault(c.path, {}).update(c.line_text)
        if artifact.kind == "diff":
            added.setdefault(c.path, set()).update(line_hash(c.line_text.get(n, "")) for n in c.anchor_lines)
    inline = [f for f in findings if f["line"] and artifact.kind == "diff"]
    general = [f for f in findings if f not in inline]
    comments = []
    for f in inline:
        lh = line_hash(text_by_path.get(f["path"], {}).get(f["line"], ""))
        key = finding_key(f["statement_id"], f["path"], lh)
        comments.append({"path": f["path"], "line": f["line"], "side": "RIGHT",
                         "body": comment_body(f, key, lh),
                         "jrfc_key": key, "jrfc_line": lh, "jrfc_blocking": f["blocking"]})
    return {
        "event": "REQUEST_CHANGES" if any(f["blocking"] for f in findings) else "COMMENT",
        "body": render_markdown(artifact, selection, general, dropped),
        "comments": comments,
        "jrfc": {
            "summary": render_markdown(artifact, selection, findings, dropped, health),
            "blocking": sum(1 for f in findings if f["blocking"]),
            "added_line_hashes": {p: sorted(h) for p, h in sorted(added.items())},
        },
    }
