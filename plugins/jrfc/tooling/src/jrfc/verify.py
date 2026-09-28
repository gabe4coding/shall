"""Verify findings whose truth may depend on code outside the reviewed chunk.

The reviewer sees one chunk. A finding such as "claude runs with tools" can be wrong because
another file adds `--tools ""`. Which findings are verified is decided by code, not by the
reviewer: every blocking finding, plus advisory findings that declare `depends_on`.

    terms (depends_on + identifiers of the quote)          code
      -> excerpts from the repository (git grep)           code
      -> excerpts that are relevant to the finding         Jev, one Noul per excerpt
      -> confirmed | refuted | unknown                     tool-less verifier agent
      -> applied                                           code

Code applies the verdict and can only lower severity:
  confirmed -> unchanged
  refuted   -> dropped, but only when the verdict cites evidence that exists
  unknown   -> kept as advisory: a finding blocks only if its evidence was seen
"""

from __future__ import annotations

import asyncio
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .artifact import Artifact
from .config import Config
from .corpus import Corpus
from .jev import Jev, noul
from .review import agent_prompt, run_claude

VERDICT_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["confirmed", "refuted", "unknown"]},
        "reason": {"type": "string"},
        "evidence": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["verdict", "reason", "evidence"],
}

IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:[.-][A-Za-z_][A-Za-z0-9_]*)*")
STOPWORDS = {
    "and", "the", "for", "with", "from", "this", "that", "true", "false", "null", "none", "self",
    "const", "let", "var", "function", "return", "await", "async", "import", "export", "default",
    "def", "class", "new", "string", "number", "int", "str", "dict", "list", "bool", "any", "void",
    "promise", "if", "else", "elif", "try", "catch", "except", "raise", "throw", "not", "in", "is",
    "defaults", "default", "value", "values", "code", "file", "config", "library", "outside", "chunk",
}
MAX_TERMS = 8
HITS_PER_TERM = 8
CONTEXT_LINES = 6
MAX_EXCERPTS = 20
KEEP_EXCERPTS = 5
SELECT_THRESHOLD = 0.4
GREP_TIMEOUT = 30
SKIP_DIRS = {".git", ".venv", "node_modules", ".jrfc-out", ".jrfc-cache", "__pycache__", "dist", "build"}


@dataclass
class Excerpt:
    id: str
    path: str
    start: int
    end: int
    text: str        # numbered lines
    terms: list[str]


def needs_verification(finding: dict) -> bool:
    return bool(finding.get("blocking") or finding.get("depends_on"))


CODE_SPAN_RE = re.compile(r"`([^`]+)`")
DOC_EXTS = {".md", ".markdown", ".txt", ".rst", ".adoc"}


def yaml_key_path(line_text: dict[int, str], line: int | None) -> str | None:
    """Dotted key of a YAML line from indentation: `  command: [...]` under `review:` ->
    review.command. Code reads configuration through that exact string."""
    if line is None or line not in line_text:
        return None
    m = re.match(r"^(\s*)([A-Za-z0-9_-]+)\s*:", line_text[line])
    if not m:
        return None
    keys, indent = [m.group(2)], len(m.group(1))
    for n in range(line - 1, 0, -1):
        pm = re.match(r"^(\s*)([A-Za-z0-9_-]+)\s*:", line_text.get(n, ""))
        if pm and len(pm.group(1)) < indent:
            keys.insert(0, pm.group(2))
            indent = len(pm.group(1))
            if indent == 0:
                break
    return ".".join(keys) if len(keys) > 1 else None


def search_terms(finding: dict, key_path: str | None = None) -> list[str]:
    """Most specific first: the config key path, the reviewer's depends_on, literal code spans
    of the statement (e.g. `--tools ""` -> --tools), then identifiers of the quote."""
    out: list[str] = []

    def add(term: str) -> None:
        if len(term) >= 4 and term.lower() not in STOPWORDS and term not in out:
            out.append(term)

    if key_path:
        add(key_path)
    for source in finding.get("depends_on", []):
        for token in IDENT_RE.findall(source):
            add(token)
            add(token.split(".")[-1])
    for span in CODE_SPAN_RE.findall(finding.get("statement_text", "")):
        add(span.split()[0].strip("\"'"))
    for token in IDENT_RE.findall(finding.get("quote", "")):
        add(token)
        add(token.split(".")[-1])
    return out[:MAX_TERMS]


def _priority(path: str) -> int:
    """Code and configuration are evidence of behavior; prose describes intent."""
    return 1 if Path(path).suffix.lower() in DOC_EXTS else 0


def _git_root(start: Path) -> Path | None:
    try:
        proc = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=start, capture_output=True,
                              text=True, timeout=GREP_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return Path(proc.stdout.strip()) if proc.returncode == 0 else None


def _hits(root: Path, term: str, excluded: set[str]) -> list[tuple[str, int]]:
    """(relative path, line) for a fixed-string match; git grep in a repo, a walk otherwise."""
    hits: list[tuple[str, int]] = []
    if (root / ".git").exists():
        try:
            proc = subprocess.run(["git", "grep", "-n", "-I", "-F", "--untracked", "-e", term],
                                  cwd=root, capture_output=True, text=True, timeout=GREP_TIMEOUT)
            for line in proc.stdout.splitlines():
                path, lineno, _ = line.split(":", 2)
                hits.append((path, int(lineno)))
        except (OSError, subprocess.TimeoutExpired, ValueError):
            pass
    else:
        for path in sorted(root.rglob("*")):
            if not path.is_file() or any(p in SKIP_DIRS for p in path.relative_to(root).parts):
                continue
            try:
                for n, text in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                    if term in text:
                        hits.append((str(path.relative_to(root)), n))
            except (UnicodeDecodeError, OSError):
                continue
    hits = [h for h in hits if not any(h[0] == e or h[0].startswith(e.rstrip("/") + "/") for e in excluded)
            and not any(part in SKIP_DIRS for part in Path(h[0]).parts)]
    return sorted(hits, key=lambda h: (_priority(h[0]), h[0], h[1]))[:HITS_PER_TERM]


def gather_excerpts(root: Path, terms: list[str], excluded: set[str]) -> list[Excerpt]:
    windows: dict[str, list[list]] = {}
    for term in terms:
        for path, line in _hits(root, term, excluded):
            spans = windows.setdefault(path, [])
            lo, hi = max(1, line - CONTEXT_LINES), line + CONTEXT_LINES
            for span in spans:  # merge overlapping windows of the same file
                if lo <= span[1] + 1 and hi >= span[0] - 1:
                    span[0], span[1] = min(span[0], lo), max(span[1], hi)
                    span[2].add(term)
                    break
            else:
                spans.append([lo, hi, {term}])
    ranked = sorted(((len(s[2]), path, s) for path, spans in windows.items() for s in spans),
                    key=lambda t: (-t[0], _priority(t[1]), t[1], t[2][0]))[:MAX_EXCERPTS]
    excerpts = []
    for i, (_, path, (lo, hi, found)) in enumerate(ranked):
        try:
            lines = (root / path).read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, OSError):
            continue
        hi = min(hi, len(lines))
        text = "\n".join(f"{n:>5} | {lines[n - 1]}" for n in range(lo, hi + 1))
        excerpts.append(Excerpt(id=f"e{i}", path=path, start=lo, end=hi, text=text, terms=sorted(found)))
    return excerpts


def relevance_question():
    return noul(
        "Does `excerpt` contain code or configuration that shows how the thing quoted in "
        "`finding.quote` is actually configured, called, wrapped or given a default, so that it "
        "helps decide whether `finding.requirement` is met?",
        true="The excerpt defines, calls, wraps, configures or sets a default for what the quote uses.",
        false="The excerpt only mentions similar words, or is documentation or a standard's text.",
    )


def chunk_context(artifact: Artifact, finding: dict, radius: int = 20) -> str:
    chunk = next((c for c in artifact.chunks if c.id == finding.get("chunk")), None)
    if chunk is None:
        return ""
    line = finding.get("line")
    if line is None:
        return chunk.rendered[:8000]
    numbers = sorted(n for n in chunk.line_text if abs(n - line) <= radius)
    return "\n".join(f"{n:>5} | {chunk.line_text[n]}" for n in numbers)


def verifier_prompt(finding: dict, context: str, excerpts: list[Excerpt]) -> str:
    evidence = "\n\n".join(f'<excerpt id="{e.id}" file="{e.path}" lines="{e.start}-{e.end}">\n{e.text}\n</excerpt>'
                           for e in excerpts) or "(no excerpt found)"
    return (
        f"<finding>\nstatement: {finding['statement_id']} [{finding['level']}] {finding['statement_text']}\n"
        f"file: {finding['path']}:{finding['line']}\nquote: {finding['quote']}\n"
        f"reviewer: {finding['message']}\ndepends_on: {', '.join(finding.get('depends_on') or []) or '-'}\n"
        f"</finding>\n\n<chunk file=\"{finding['path']}\">\n{context}\n</chunk>\n\n<evidence>\n{evidence}\n</evidence>"
    )


def apply_verdict(finding: dict, verdict: dict | None, excerpts: list[Excerpt]) -> tuple[dict | None, dict | None]:
    """Return (kept finding or None, dropped entry or None). Severity only goes down."""
    known = {e.id: e for e in excerpts}
    if verdict is None:
        verdict = {"verdict": "unknown", "reason": "verification did not return a verdict", "evidence": []}
    cited = [i for i in verdict.get("evidence", []) if i == "chunk" or i in known]
    record = {
        "verdict": verdict.get("verdict", "unknown"),
        "reason": verdict.get("reason", ""),
        "evidence": [i if i == "chunk" else f"{known[i].path}:{known[i].start}-{known[i].end}" for i in cited],
    }
    if record["verdict"] == "refuted" and cited:
        return None, {**finding, "verification": record, "reason": f"refuted by verification: {record['reason']}"}
    if record["verdict"] in ("refuted", "confirmed") and not cited:
        # a drop and a block both need evidence that exists (JTOOL-0002.6)
        record["reason"] = f"{record['verdict']} without citing evidence: " + record["reason"]
        record["verdict"] = "unknown"
    kept = {**finding, "verification": record}
    if record["verdict"] != "confirmed" and kept["blocking"]:
        kept["blocking"] = False
        kept["downgraded"] = True  # evidence not seen: a comment, never a failed check
    return kept, None


async def verify_findings(cfg: Config, corpus: Corpus, artifact: Artifact, jev: Jev, findings: list[dict],
                          search_root: Path | None = None, agent=None) -> tuple[list[dict], list[dict], dict]:
    agent = agent or (lambda prompt, sem: run_claude(cfg, prompt, agent_prompt("jrfc-verifier"),
                                                     VERDICT_SCHEMA, sem))
    root = search_root or _git_root(Path.cwd()) or Path.cwd()
    excluded = {".jrfc-out"}
    for layer in corpus.layers:  # the standards' own text is not evidence about the code
        for folder in (layer.rfcs_dir, layer.index_dir):
            try:
                excluded.add(str(folder.relative_to(root)))
            except ValueError:
                pass
    sem = asyncio.Semaphore(int(cfg.get("review.concurrency")))
    stats = {"verified": 0, "confirmed": 0, "refuted": 0, "unknown": 0, "agent_calls": 0, "cost_usd": 0.0}

    async def one(f: dict):
        if not needs_verification(f):
            return f, None
        chunk = next((c for c in artifact.chunks if c.id == f.get("chunk")), None)
        key_path = yaml_key_path(chunk.line_text, f.get("line")) if chunk and chunk.language == "yaml" else None
        excerpts = gather_excerpts(root, search_terms(f, key_path), excluded | {f["path"]})
        if excerpts:
            base = {"requirement": f["statement_text"], "quote": f["quote"], "message": f["message"]}
            answers = await jev.gather(
                jev.ask({"finding": base, "excerpt_file": e.path, "excerpt": e.text}, {"relevant": relevance_question()})
                for e in excerpts
            )
            scored = sorted(zip(excerpts, answers), key=lambda t: -t[1]["relevant"]["p"])
            excerpts = [e for e, a in scored if a["relevant"]["p"] >= SELECT_THRESHOLD][:KEEP_EXCERPTS]
        verdict, meta = await agent(verifier_prompt(f, chunk_context(artifact, f), excerpts), sem)
        stats["agent_calls"] += 1
        stats["cost_usd"] = round(stats["cost_usd"] + meta.get("cost_usd", 0.0), 6)
        return apply_verdict(f, verdict, excerpts)

    results = await asyncio.gather(*(one(f) for f in findings))
    kept, dropped = [], []
    for f, (k, d) in zip(findings, results):
        if needs_verification(f):
            stats["verified"] += 1
            stats[(k or d)["verification"]["verdict"] if (k or d).get("verification") else "unknown"] += 1
        if k is not None:
            kept.append(k)
        if d is not None:
            dropped.append(d)
    kept.sort(key=lambda k: (not k["blocking"], k["path"], k["line"] or 0, k["statement_id"]))
    return kept, dropped, stats
