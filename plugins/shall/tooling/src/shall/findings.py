"""Findings: what the reviewer agent returns, what code accepts, and the reports made from them.

Deterministic: no model call in this module (JTOOL-0003.2). The trust boundary:

    RawFinding        agent JSON, untrusted            (FINDINGS_SCHEMA)
      -> validate_findings                             statement selected, line or quote found (JTOOL-0002.2)
    Finding           severity from the corpus         (corpus_blocking)
      -> Finding.with_verification(Verification)       (verify.py)
    Finding.blocking  computed, never stored: only a `confirmed` verdict keeps it (JTOOL-0002.5, .6)

Only this module makes a Finding from data (tests/test_boundaries.py checks it). `from_json` reads
back a findings.json that shall itself wrote; agent output always goes through `validate_findings`.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Literal, TypedDict, get_args

from .artifact import Artifact, Chunk
from .corpus import Corpus, Level

Verdict = Literal["confirmed", "refuted", "unknown"]
VERDICTS: tuple[Verdict, ...] = get_args(Verdict)


class RawFinding(TypedDict, total=False):
    """One finding as the reviewer agent returns it (an item of FINDINGS_SCHEMA), plus the chunk
    id that code adds. Untrusted: read it only in `validate_findings`."""
    chunk: str
    statement_id: str
    line: int | None
    quote: str
    message: str
    suggestion: str
    depends_on: list[str]


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


@dataclass(frozen=True)
class Verification:
    """A verifier verdict as code accepted it (verify.verification_of)."""
    verdict: Verdict
    reason: str
    evidence: tuple[str, ...] = ()   # cited excerpts as path:start-end, or "chunk"
    shown: tuple[str, ...] = ()      # audit: every excerpt the verifier saw

    def to_json(self) -> dict:
        return {"verdict": self.verdict, "reason": self.reason, "evidence": list(self.evidence),
                "shown": list(self.shown)}

    @classmethod
    def from_json(cls, data: dict) -> Verification:
        verdict = data.get("verdict")
        return cls(verdict=verdict if verdict in VERDICTS else "unknown", reason=str(data.get("reason", "")),
                   evidence=tuple(data.get("evidence") or ()), shown=tuple(data.get("shown") or ()))


@dataclass(frozen=True)
class Finding:
    """A finding that code validated. There is no `blocking` field: see the property."""
    statement_id: str
    rfc: str
    title: str
    level: Level
    corpus_blocking: bool          # Rfc.statement_blocking: RFC status and statement level
    path: str
    line: int | None
    quote: str
    message: str
    suggestion: str
    statement_text: str
    source: str
    chunk: str
    depends_on: tuple[str, ...] = ()
    verification: Verification | None = field(default=None)

    @property
    def blocking(self) -> bool:
        """The corpus decides, and only a `confirmed` verdict keeps it: a finding that was not
        verified (`--no-verify`, `review.verify: false`, `shall validate`) is advisory (JTOOL-0002.6)."""
        return self.corpus_blocking and self.verification is not None and self.verification.verdict == "confirmed"

    @property
    def downgraded(self) -> bool:
        """Blocking by the corpus, advisory because no verifier confirmed it."""
        return self.corpus_blocking and not self.blocking

    def with_verification(self, verification: Verification) -> Finding:
        return replace(self, verification=verification)

    def to_json(self) -> dict:
        out = {
            "statement_id": self.statement_id, "rfc": self.rfc, "title": self.title, "level": self.level,
            "blocking": self.blocking, "corpus_blocking": self.corpus_blocking,
            "path": self.path, "line": self.line, "quote": self.quote,
            "message": self.message, "suggestion": self.suggestion, "depends_on": list(self.depends_on),
            "chunk": self.chunk, "statement_text": self.statement_text, "source": self.source,
        }
        if self.verification is not None:
            out["verification"] = self.verification.to_json()
        if self.downgraded:
            out["downgraded"] = True  # not confirmed: a comment, never a failed check
        return out

    @classmethod
    def from_json(cls, data: dict) -> Finding:
        """A finding from a findings.json that shall wrote (`to_json`). Never use it for agent output."""
        v = data.get("verification")
        return cls(
            statement_id=data["statement_id"], rfc=data["rfc"], title=data["title"], level=data["level"],
            # findings.json before corpus_blocking existed: blocking, or blocking until downgraded
            corpus_blocking=bool(data.get("corpus_blocking", data.get("blocking") or data.get("downgraded"))),
            path=data["path"], line=data.get("line"), quote=data.get("quote", ""),
            message=data.get("message", ""), suggestion=data.get("suggestion", ""),
            statement_text=data.get("statement_text", ""), source=data.get("source", ""),
            chunk=data.get("chunk", ""), depends_on=tuple(data.get("depends_on") or ()),
            verification=Verification.from_json(v) if v else None,
        )


def read_findings(path: Path) -> list[Finding]:
    """The findings in a findings.json that shall wrote: {"findings": [...]} or a bare list."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return [Finding.from_json(f) for f in (data.get("findings", []) if isinstance(data, dict) else data)]


def sort_key(f: Finding) -> tuple:
    # corpus_blocking second: before verification nothing blocks, and the comment cap
    # (validate_findings) must still keep the findings that can block
    return (not f.blocking, not f.corpus_blocking, f.path, f.line or 0, f.statement_id)


# ---------------------------------------------------------------- prompts and bundle


def render_statements(corpus: Corpus, ids: list[str]) -> str:
    lines = []
    for sid in ids:
        rfc, st = corpus.require(sid)
        flag = "blocking" if rfc.statement_blocking(st) else "non-blocking"
        lines.append(f"- {sid} [{st.level}, {flag}] {st.title}: {st.text}")
        lines.append(f"  Applies when: {st.applies_when or rfc.applies_when}")
    return "\n".join(lines)


def chunk_prompt(corpus: Corpus, chunk: Chunk, ids: list[str], facts: list[str] | None = None) -> str:
    """The data of one review call. The instructions are only in agents/shall-reviewer.md (JTOOL-0004.2)."""
    return (
        f"<chunk kind=\"{chunk.kind}\" file=\"{chunk.path}\" language=\"{chunk.language}\">\n"
        f"{chunk.rendered}\n</chunk>\n\n"
        + ("<known_effects>\nFacts found by code (effects registry and code graph) about what the "
           "code in the chunk calls:\n" + "\n".join(f"- {x}" for x in facts) + "\n</known_effects>\n\n"
           if facts else "")
        + f"<standards>\n{render_statements(corpus, ids)}\n</standards>"
    )


def write_bundle(corpus: Corpus, artifact: Artifact, selection: dict, out: Path) -> Path:
    """Human/agent-readable review bundle for interactive use inside Claude Code."""
    chunks = {c.id: c for c in artifact.chunks}
    parts = [
        f"# shall review bundle — {artifact.source}",
        "",
        "Give each chunk section below to the `shall-reviewer` agent. Collect its findings in one JSON",
        "file as `{\"findings\": [{\"chunk\": \"c0\", ...}]}`, then run `shall validate` and `shall verify`",
        "(skill shall-review, references/in-session.md). Only a verified finding blocks.",
        "",
    ]
    for c in selection["chunks"]:
        if not c["selected"]:
            continue
        parts += [f"## Chunk {c['id']} — {c['path']}", "", chunk_prompt(corpus, chunks[c["id"]], c["selected"], c.get("known_effects")), ""]
    out.write_text("\n".join(parts), encoding="utf-8")
    return out


# ---------------------------------------------------------------- validation


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


def validate_findings(corpus: Corpus, artifact: Artifact, selection: dict, raw: list[RawFinding],
                      max_comments: int) -> tuple[list[Finding], list[dict]]:
    """The only way from agent output to a Finding (JTOOL-0002.2). Returns (kept, dropped)."""
    chunks = {c.id: c for c in artifact.chunks}
    selected = {c["id"]: set(c["selected"]) for c in selection["chunks"]}
    kept: list[Finding] = []
    dropped: list[dict] = []
    seen: set[tuple[str, str, int | None]] = set()
    for f in raw:
        cid = str(f.get("chunk", ""))
        chunk = chunks.get(cid)
        sid = str(f.get("statement_id", ""))
        line = f.get("line")
        quote = _norm(f.get("quote", ""))
        found = corpus.statement(sid)
        reason = None
        if chunk is None:
            reason = f"unknown chunk {cid!r}"
        elif sid not in selected.get(cid, set()):
            reason = f"{sid} was not selected for chunk {cid}"
        elif found is None:
            reason = f"{sid} does not exist in the corpus"
        else:
            line, reason = _anchor(chunk, line, quote)
        if reason or chunk is None or found is None:
            dropped.append({**f, "reason": reason})
            continue
        rfc, st = found
        key = (sid, chunk.path, line)
        if key in seen:
            dropped.append({**f, "reason": "duplicate"})
            continue
        seen.add(key)
        kept.append(Finding(
            statement_id=sid, rfc=rfc.id, title=st.title, level=st.level or "MAY",
            corpus_blocking=rfc.statement_blocking(st),  # recomputed, never trusted from the model
            path=chunk.path, line=line, quote=f.get("quote", ""),
            message=f.get("message", ""), suggestion=f.get("suggestion", ""),
            depends_on=tuple(str(d) for d in f.get("depends_on") or [])[:8],
            chunk=cid, statement_text=st.text, source=corpus.source(rfc, st.line),
        ))
    kept.sort(key=sort_key)
    if len(kept) > max_comments:
        for k in kept[max_comments:]:
            dropped.append({**k.to_json(), "reason": f"over max_comments={max_comments}"})
        kept = kept[:max_comments]
    return kept, dropped


# ---------------------------------------------------------------- reports


def verification_line(f: Finding) -> str:
    v = f.verification
    if v is None:
        return "_Not verified — not blocking._" if f.corpus_blocking else ""
    where = f" ({', '.join(v.evidence)})" if v.evidence else ""
    if v.verdict == "confirmed":
        return f"_Verified{where}:_ {v.reason}"
    note = "not blocking: the evidence it depends on was not seen" if f.downgraded else "could not be verified"
    return f"_Unverified — {note}:_ {v.reason}"


def render_markdown(artifact: Artifact, selection: dict, findings: list[Finding], dropped: list[dict],
                    health: dict | None = None) -> str:
    blocking = sum(1 for f in findings if f.blocking)
    out = [
        f"## shall review — `{artifact.source}`",
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
        where = f"`{f.path}:{f.line}`" if f.line else f"`{f.path}` (whole document)"
        tag = "🚫 blocking" if f.blocking else "💬 advisory"
        out.append(f"- {tag} **{f.statement_id}** {f.title} — {where}")
        out.append(f"  {f.message}")
        if f.suggestion:
            out.append(f"  _Suggestion:_ {f.suggestion}")
        if note := verification_line(f):
            out.append(f"  {note}")
    return "\n".join(out).rstrip() + "\n"


def line_hash(text: str) -> str:
    """Hash of a line's content: stable when the line moves, new when the line changes."""
    return hashlib.sha1(_norm(text).encode()).hexdigest()[:12]


def finding_key(statement_id: str, path: str, lhash: str) -> str:
    return hashlib.sha1(f"{statement_id}|{path}|{lhash}".encode()).hexdigest()[:16]


MARKER_RE = re.compile(r"<!-- shall:finding key=([0-9a-f]+) line=([0-9a-f]+) -->")
SUMMARY_MARKER = "<!-- shall:summary -->"


def comment_body(f: Finding, key: str | None = None, lhash: str | None = None) -> str:
    tag = "🚫 **blocking**" if f.blocking else "💬 advisory"
    body = f"{tag} · **{f.statement_id}** {f.title} ({f.level})\n\n{f.message}"
    if f.suggestion:
        body += f"\n\n**Suggestion:** {f.suggestion}"
    if note := verification_line(f):
        body += f"\n\n{note}"
    body += f"\n\n> {f.statement_text}\n\n<sub>Standard: `{f.source}`</sub>"
    if key:
        body += f"\n\n<!-- shall:finding key={key} line={lhash} -->"
    return body


def render_github(artifact: Artifact, selection: dict, findings: list[Finding], dropped: list[dict],
                  health: dict | None = None) -> dict:
    """Review payload plus the state `shall publish` needs to dedupe across pushes.

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
    inline = [f for f in findings if f.line and artifact.kind == "diff"]
    general = [f for f in findings if f not in inline]
    comments = []
    for f in inline:
        lh = line_hash(text_by_path.get(f.path, {}).get(f.line or 0, ""))
        key = finding_key(f.statement_id, f.path, lh)
        comments.append({"path": f.path, "line": f.line, "side": "RIGHT",
                         "body": comment_body(f, key, lh),
                         "shall_key": key, "shall_line": lh, "shall_blocking": f.blocking})
    return {
        "event": "REQUEST_CHANGES" if any(f.blocking for f in findings) else "COMMENT",
        "body": render_markdown(artifact, selection, general, dropped),
        "comments": comments,
        "shall": {
            "summary": render_markdown(artifact, selection, findings, dropped, health),
            "blocking": sum(1 for f in findings if f.blocking),
            "added_line_hashes": {p: sorted(h) for p, h in sorted(added.items())},
        },
    }
