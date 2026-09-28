"""Load an artifact (diff, code, spec, doc, task) and split it into reviewable chunks."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

LANG_BY_EXT = {
    ".ts": "typescript", ".tsx": "typescript", ".js": "javascript", ".jsx": "javascript",
    ".mjs": "javascript", ".cjs": "javascript", ".py": "python", ".sql": "sql",
    ".java": "java", ".kt": "kotlin", ".go": "go", ".rb": "ruby", ".php": "php",
    ".rs": "rust", ".cs": "csharp", ".swift": "swift", ".md": "markdown",
    ".yaml": "yaml", ".yml": "yaml", ".json": "json", ".css": "css", ".scss": "css",
    ".html": "html", ".tf": "terraform", ".sh": "shell",
}
DOC_EXTS = {".md", ".markdown", ".txt", ".rst", ".adoc"}

KIND_DESCRIPTIONS = {
    "diff": "a unified code diff; lines marked '+' are added, '-' removed, others are context",
    "code": "a source code file",
    "spec": "a technical design spec proposing how to build or change a system",
    "doc": "a document",
    "task": "a description of work an engineer or agent is about to do",
}

HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def language_of(path: str) -> str:
    return LANG_BY_EXT.get(Path(path).suffix.lower(), "text")


@dataclass
class Chunk:
    id: str
    kind: str
    path: str
    language: str
    rendered: str                 # what the model and the reviewer see (with line numbers)
    anchor_lines: set[int] = field(default_factory=set)   # lines a comment may point at
    line_text: dict[int, str] = field(default_factory=dict)

    def state(self) -> dict:
        return {
            "artifact_kind": KIND_DESCRIPTIONS[self.kind],
            "file": self.path,
            "language": self.language,
            "content": self.rendered,
        }


@dataclass
class Artifact:
    kind: str
    source: str
    sha: str
    chunks: list[Chunk]


def looks_like_diff(text: str) -> bool:
    return text.startswith("diff --git") or bool(
        re.search(r"^--- .+\n\+\+\+ .+\n@@ ", text, re.M)
    )


def _split_by_size(blocks: list[list[str]], max_chars: int) -> list[list[str]]:
    groups, current, size = [], [], 0
    for block in blocks:
        block_size = sum(len(line) + 1 for line in block)
        if current and size + block_size > max_chars:
            groups.append(current)
            current, size = [], 0
        current.extend(block)
        size += block_size
    if current:
        groups.append(current)
    return groups


def parse_diff(text: str, max_chars: int) -> list[Chunk]:
    files: list[tuple[str, list[str]]] = []
    current_path, current_lines = None, []
    old_path = None
    for line in text.splitlines():
        if line.startswith("diff --git"):
            if current_path is not None:
                files.append((current_path, current_lines))
            current_path, current_lines, old_path = None, [], None
            m = re.match(r"diff --git a/(.+?) b/(.+)$", line)
            if m:
                old_path, current_path = m.group(1), m.group(2)
            continue
        if line.startswith("--- "):
            old = line[4:].strip()
            old_path = old[2:] if old.startswith("a/") else old
            continue
        if line.startswith("+++ "):
            new = line[4:].strip()
            if current_path is not None and new != "/dev/null" and current_lines:
                files.append((current_path, current_lines))
                current_lines = []
            current_path = old_path if new == "/dev/null" else (new[2:] if new.startswith("b/") else new)
            continue
        if current_path is not None:
            current_lines.append(line)
    if current_path is not None:
        files.append((current_path, current_lines))

    chunks: list[Chunk] = []
    for path, lines in files:
        hunks: list[list[str]] = []
        anchor: set[int] = set()
        line_text: dict[int, str] = {}
        new_no = 0
        for line in lines:
            m = HUNK_RE.match(line)
            if m:
                new_no = int(m.group(3))
                hunks.append([line])
                continue
            if not hunks:
                continue  # index/mode lines before the first hunk
            if line.startswith("+"):
                hunks[-1].append(f"{new_no:>5} + {line[1:]}")
                anchor.add(new_no)
                line_text[new_no] = line[1:]
                new_no += 1
            elif line.startswith("-"):
                hunks[-1].append(f"{'':>5} - {line[1:]}")
            elif line.startswith("\\"):
                continue
            else:
                hunks[-1].append(f"{new_no:>5}   {line[1:] if line.startswith(' ') else line}")
                line_text[new_no] = line[1:] if line.startswith(" ") else line
                new_no += 1
        if not hunks:
            continue  # binary or mode-only change
        for part in _split_by_size(hunks, max_chars):
            chunks.append(Chunk(
                id=f"c{len(chunks)}",
                kind="diff",
                path=path,
                language=language_of(path),
                rendered=f"File: {path}\n" + "\n".join(part),
                anchor_lines=anchor,
                line_text=line_text,
            ))
    return chunks


def _numbered(lines: list[str], start: int) -> str:
    return "\n".join(f"{start + i:>5} | {line}" for i, line in enumerate(lines))


def parse_document(text: str, path: str, kind: str, max_chars: int) -> list[Chunk]:
    lines = text.splitlines()
    line_text = {i + 1: line for i, line in enumerate(lines)}
    # A whole document is one chunk when it fits: "is a rollback section present?"
    # is a whole-document judgment that a per-section split would break.
    if len(text) <= max_chars:
        sections = [(1, lines)]
    else:
        sections, start = [], 0
        for i, line in enumerate(lines):
            if i > start and (line.startswith("## ") or line.startswith("# ")):
                sections.append((start + 1, lines[start:i]))
                start = i
        sections.append((start + 1, lines[start:]))
    chunks = []
    for first, sec in sections:
        chunks.append(Chunk(
            id=f"c{len(chunks)}",
            kind=kind,
            path=path,
            language=language_of(path) if kind in ("code", "diff") else "text",
            rendered=f"File: {path}\n" + _numbered(sec, first),
            anchor_lines=set(range(first, first + len(sec))),
            line_text=line_text,
        ))
    return chunks


def read_source(source: str | None, text: str | None) -> tuple[str, str]:
    """Return (name, raw text) for a file path, '-' (stdin) or inline text."""
    if text is not None:
        return "task.txt", text
    if source == "-":
        import sys
        return "stdin", sys.stdin.read()
    return str(source), Path(source).read_text(encoding="utf-8")


def detect_kind(name: str, raw: str, inline_text: bool = False) -> str:
    """diff | code | task, or 'document' when prose must be classified (spec vs doc)."""
    if inline_text:
        return "task"
    if looks_like_diff(raw) or Path(name).suffix in (".diff", ".patch"):
        return "diff"
    if Path(name).suffix.lower() in DOC_EXTS or name == "stdin":
        return "document"
    return "code"


def build_artifact(name: str, raw: str, kind: str, max_chars: int) -> Artifact:
    assert kind in KIND_DESCRIPTIONS, kind
    sha = hashlib.sha256(raw.encode()).hexdigest()[:16]
    chunks = parse_diff(raw, max_chars) if kind == "diff" else parse_document(raw, name, kind, max_chars)
    return Artifact(kind=kind, source=name, sha=sha, chunks=chunks)
