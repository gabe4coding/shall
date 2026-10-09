"""`jrfc scan`: lint whole files against the corpus (the post-write hook's judgment, per file).

  files      `git ls-files` (tracked and untracked, not ignored) under the given paths, or a
             directory walk outside git; known code and config languages (not Markdown docs);
             `scan.exclude` globs; `scan.max_file_chars` cap
  scanner    the secret scanner on the raw text: a hit is exact (p = 1) and may block
  Jev        the whole file (secrets redacted) as one added-lines chunk -> the code prefilter's
             eligible statements, one request per chunk, p = min(applies, violates); a warning
             at p >= threshold, never blocking: one file is not evidence (JTOOL-0002.6)

Jev answers are cached like everywhere else, so a second scan of unchanged files is free.
Measured on 100 real files (eval/scan, docs/results.mdx): ~$0.0005 and ~0.4 s per file.
"""

from __future__ import annotations

import asyncio
import fnmatch
import os
import subprocess
from pathlib import Path

from .artifact import DOC_EXTS, language_of, parse_diff
from .config import Config
from .corpus import Corpus
from .hooks import Hooks, redact, scan_secrets, synthetic_diff
from .jev import Jev

JEV_PRICE_IN = 0.042  # $ per 1M input tokens (evaluate.py uses the same rate)


def _git(root: Path, *args: str) -> str | None:
    proc = subprocess.run(["git", "-C", str(root), *args], capture_output=True)
    return proc.stdout.decode("utf-8", "surrogateescape") if proc.returncode == 0 else None


def repo_root(start: Path) -> Path:
    top = (_git(start, "rev-parse", "--show-toplevel") or "").strip()
    return Path(top) if top else start


def excluded(rel: str, patterns: list[str]) -> bool:
    # "/" + rel lets "*/node_modules/*" also match a top-level node_modules/
    return any(fnmatch.fnmatch(rel, p) or fnmatch.fnmatch("/" + rel, p) for p in patterns)


def list_files(root: Path, paths: list[str], exclude: list[str]) -> list[str]:
    """Repository-relative paths of the files to scan, sorted."""
    targets = []
    for p in paths:
        full = Path(p).resolve()
        if not full.is_relative_to(root):
            raise SystemExit(f"jrfc scan: {p} is outside the repository {root}")
        targets.append(full.relative_to(root).as_posix() or ".")
    listed = _git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", *targets)
    if listed is not None:
        names = [n for n in listed.split("\0") if n]
    else:  # not a git work tree
        names = []
        for t in targets:
            full = root / t
            if full.is_file():
                names.append(t)
                continue
            for dirpath, dirnames, filenames in os.walk(full):
                dirnames[:] = [d for d in dirnames if not d.startswith(".")]
                names += [(Path(dirpath) / f).relative_to(root).as_posix() for f in filenames]
    # documents are specs or docs for `jrfc review`, not code to lint
    return sorted({n for n in names if language_of(n) != "text" and Path(n).suffix.lower() not in DOC_EXTS
                   and not excluded(n, exclude)})


def read_text(path: Path, max_chars: int) -> tuple[str | None, str | None]:
    """(text, None) or (None, reason it is skipped)."""
    try:
        data = path.read_bytes()
    except OSError as err:
        return None, f"unreadable: {err.strerror or err}"
    if b"\0" in data[:8192]:
        return None, "binary"
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None, "not UTF-8"
    if len(text) > max_chars:
        return None, f"larger than scan.max_file_chars ({len(text)} > {max_chars})"
    if not text.strip():
        return None, "empty"
    return text, None


def secret_statement(cfg: Config, corpus: Corpus, statuses: set[str]):
    """The statement a secret-scanner hit in written code breaks (`hooks.secrets`, as for Write)."""
    import re
    for tool_rx, sid in cfg.get("hooks.secrets") or []:
        if re.fullmatch(tool_rx, "Write"):
            hit = corpus.statement(sid)
            if hit and hit[0].status in statuses:
                return hit
            return None
    return None


async def scan_file(hooks: Hooks, rel: str, text: str, threshold: float, secret_rule, max_chunk_chars: int) -> dict:
    record: dict = {}
    findings: list[dict] = []
    secrets = scan_secrets(text)
    if secrets and secret_rule:
        rfc, st = secret_rule
        lines = sorted({text.count("\n", 0, s.start) + 1 for s in secrets})
        findings.append({**hooks._finding(rfc, st, 1.0, "warn", "scanner", secrets=sorted({s.kind for s in secrets})),
                         "lines": ",".join(map(str, lines)), "blocking": rfc.statement_blocking(st)})
    n = text.count("\n") + (0 if text.endswith("\n") else 1)
    chunks = parse_diff(synthetic_diff(rel, redact(text)[0], [(1, max(n, 1))], 0), max_chunk_chars)
    judged = await hooks.judge_code(chunks, record, lambda rfc, st, p: "warn" if p >= threshold else None)
    findings += [{**f, "lines": None, "blocking": False} for f in judged if f["action"]]
    jev = record.get("jev", "none")
    return {"path": rel, "language": language_of(rel), "lines": n, "chunks": len(chunks),
            "candidates": record.get("candidates", 0), "jev": jev,
            "error": jev if jev.startswith(("error", "timeout", "no TYPESAFE")) else None,
            "scores": {k: round(v, 4) for k, v in sorted(record.get("scores", {}).items())},
            "findings": sorted(findings, key=lambda f: (-f["p"], f["id"]))}


async def run_scan(cfg: Config, corpus: Corpus, jev: Jev, paths: list[str], root: Path | None = None,
                   threshold: float | None = None, statuses: list[str] | None = None,
                   exclude: list[str] | None = None) -> dict:
    root = root or repo_root(Path.cwd())
    threshold = float(cfg.get("scan.threshold") if threshold is None else threshold)
    statuses = list(statuses or cfg.get("scan.statuses") or cfg.get("selection.include_status"))
    exclude = list(cfg.get("scan.exclude") or []) + list(exclude or [])
    max_chars = int(cfg.get("scan.max_file_chars"))
    max_chunk = int(cfg.get("jev.max_chunk_chars"))
    hooks = Hooks(cfg, corpus, jev, statuses=statuses, timeout=None, log=False)
    secret_rule = secret_statement(cfg, corpus, set(statuses))
    names = list_files(root, paths, exclude)
    sem = asyncio.Semaphore(int(cfg.get("scan.concurrency")))
    skipped: list[dict] = []
    before = dict(jev.usage)

    async def one(rel: str) -> dict | None:
        text, why = read_text(root / rel, max_chars)
        if text is None:
            skipped.append({"path": rel, "reason": why})
            return None
        async with sem:
            return await scan_file(hooks, rel, text, threshold, secret_rule, max_chunk)

    files = [f for f in await asyncio.gather(*(one(n) for n in names)) if f]
    used = {k: jev.usage.get(k, 0) - before.get(k, 0) for k in jev.usage}
    warnings = [f for x in files for f in x["findings"]]
    return {
        # paths are repository-relative and there is no absolute path: the report does not depend on the checkout
        "paths": [Path(p).resolve().relative_to(root).as_posix() or "." for p in paths],
        "threshold": threshold, "statuses": statuses,
        "files": files, "skipped": sorted(skipped, key=lambda s: s["path"]),
        "errors": [{"path": f["path"], "error": f["error"]} for f in files if f["error"]],
        "summary": {"scanned": len(files), "skipped": len(skipped), "warnings": len(warnings),
                    "files_with_warnings": sum(1 for f in files if f["findings"]),
                    "blocking": sum(1 for w in warnings if w["blocking"]),
                    "jev_requests": used.get("requests", 0), "jev_cached": used.get("cached", 0),
                    "jev_cost_usd": round(used.get("input_tokens", 0) * JEV_PRICE_IN / 1e6, 6)},
    }


def _line(f: dict) -> str:
    how = "secret scanner" if f["by"] == "scanner" else f"p={f['p']:.2f}"
    where = f", lines {f['lines']}" if f.get("lines") else ""
    found = f" Found: {', '.join(f['secrets'])}." if f.get("secrets") else ""
    block = " **blocking**" if f.get("blocking") else ""
    return f"- **{f['id']}** {f['title']} [{f['level']}, {f['status']}, {how}{where}]{block}: {f['text']}{found}"


def render_markdown(report: dict) -> str:
    s = report["summary"]
    out = ["# jrfc scan", "",
           f"{s['scanned']} file(s) scanned, {s['skipped']} skipped; {s['warnings']} warning(s) in "
           f"{s['files_with_warnings']} file(s), {s['blocking']} blocking. Threshold p >= {report['threshold']}, "
           f"statuses: {', '.join(report['statuses'])}. Jev: {s['jev_requests']} request(s), {s['jev_cached']} "
           f"cached, ~${s['jev_cost_usd']:.4f}.", "",
           "Warnings are Jev's judgment on one whole file: check each against the code, since the setting "
           "that makes it fine can live in another file. Only secret-scanner hits can block; `jrfc review` "
           "verifies findings with repository evidence.", ""]
    for f in report["files"]:
        if f["findings"]:
            out += [f"## {f['path']}", ""] + [_line(x) for x in f["findings"]] + [""]
    if report["errors"]:
        out += ["## Not checked (Jev failed)", ""] + [f"- {e['path']}: {e['error']}" for e in report["errors"]] + [""]
    if report["skipped"]:
        out += ["## Skipped", ""] + [f"- {x['path']}: {x['reason']}" for x in report["skipped"]] + [""]
    if not s["warnings"] and not report["errors"]:
        out += ["No warnings.", ""]
    return "\n".join(out)


def render_lines(report: dict) -> list[str]:
    """One line per warning, linter style: `path[:lines]: ID [level, p] title`."""
    lines = []
    for f in report["files"]:
        for x in f["findings"]:
            where = f":{x['lines']}" if x.get("lines") else ""
            how = "secret" if x["by"] == "scanner" else f"p={x['p']:.2f}"
            lines.append(f"{f['path']}{where}: {x['id']} [{x['level']}, {how}]"
                         f"{' BLOCKING' if x.get('blocking') else ''} {x['title']}")
    return lines
