"""Parse and lint the RFC corpus. Pure and deterministic: no model calls here."""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .config import Config, Layer

STATUSES = ("draft", "approved", "enforced", "deprecated")
ARTIFACTS = ("diff", "code", "spec", "doc", "tool")  # tool: an agent tool call (hooks.py)
ENFORCEMENTS = ("agent", "linter", "human")
REQUIRED_FRONT = (
    "id", "title", "status", "domain", "artifacts", "languages", "owner",
    "review_by", "summary", "applies_when", "not_applies_when",
)

PREFIX_RE = re.compile(r"^[A-Z][A-Z0-9]{1,9}$")
STATEMENT_HEAD_RE = re.compile(r"^###\s+([A-Z][A-Z0-9]{1,9}-\d{4}\.\d+)\s+(.+?)\s*$")
LOOSE_HEAD_RE = re.compile(r"^###\s+[A-Z][A-Z0-9]{1,9}-\d")
SECTION_HEAD_RE = re.compile(r"^#{1,3}\s")
META_RE = re.compile(
    r"^-\s+(Applies when|Not applies when|Enforcement|Artifacts|Tools|Violated when|Pattern):\s*(.*)$", re.I)
# Longest alternatives first so "MUST NOT" wins over "MUST".
KEYWORD_RE = re.compile(
    r"\b(MUST NOT|SHALL NOT|SHOULD NOT|NOT RECOMMENDED|MUST|SHALL|REQUIRED|SHOULD|RECOMMENDED|MAY|OPTIONAL)\b"
)
CODE_SPAN_RE = re.compile(r"`[^`]*`")
LOWER_KEYWORD_RE = re.compile(r"\b(must|shall|should)\b")
LEVEL_OF = {
    "MUST": "MUST", "MUST NOT": "MUST", "SHALL": "MUST", "SHALL NOT": "MUST", "REQUIRED": "MUST",
    "SHOULD": "SHOULD", "SHOULD NOT": "SHOULD", "RECOMMENDED": "SHOULD", "NOT RECOMMENDED": "SHOULD",
    "MAY": "MAY", "OPTIONAL": "MAY",
}
LEVEL_RANK = {"MUST": 3, "SHOULD": 2, "MAY": 1}


@dataclass
class Issue:
    path: str
    line: int
    severity: str  # error | warning
    code: str
    message: str
    layer: str = "local"

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.severity} [{self.code}] {self.message}"


@dataclass
class Domain:
    id: str
    title: str
    description: str
    owner: str
    applies_when: str
    not_applies_when: str
    layer: str = "local"


@dataclass
class Statement:
    id: str
    rfc_id: str
    title: str
    text: str
    level: str | None
    keywords: list[str]
    applies_when: str | None
    not_applies_when: str | None
    enforcement: str
    line: int
    artifacts: list[str] | None = None  # narrower than the RFC's, e.g. [spec]
    tools: str | None = None            # tool-name regex for `tool` statements, e.g. Bash|mcp__.*
    violated_when: str | None = None    # hook Jev criterion: what a violating tool call looks like
    pattern: str | None = None          # linter `tool` statements: regex searched in the command


@dataclass
class Rfc:
    id: str
    title: str
    status: str
    domain: str
    artifacts: list[str]
    languages: list[str]
    owner: str
    review_by: str
    summary: str
    applies_when: str
    not_applies_when: str
    supersedes: list[str]
    superseded_by: str | None
    retired: list[str]
    path: Path
    statements: list[Statement] = field(default_factory=list)
    layer: str = "local"

    def statement_blocking(self, st: Statement) -> bool:
        return self.status == "enforced" and st.level == "MUST"


@dataclass
class Corpus:
    root: Path
    domains: dict[str, Domain]
    rfcs: dict[str, Rfc]
    issues: list[Issue]
    layers: list[Layer] = field(default_factory=list)
    effects: list = field(default_factory=list)   # effects.Effect entries of every layer

    def statements(self) -> list[tuple[Rfc, Statement]]:
        return [(r, s) for r in self.rfcs.values() for s in r.statements]

    def statement(self, sid: str) -> tuple[Rfc, Statement] | None:
        rfc = self.rfcs.get(sid.split(".")[0])
        if rfc:
            for st in rfc.statements:
                if st.id == sid:
                    return rfc, st
        return None

    def layer_of(self, rfc: Rfc) -> Layer | None:
        return next((layer for layer in self.layers if layer.name == rfc.layer), None)

    def rel(self, path: Path) -> str:
        """Path for display: from the repo root for the local layer (`.jrfc/rfcs/...` in an
        app repo), `<parent label>/<path>` for the extended corpus. The most specific layer
        root wins, since a local workspace may sit inside the parent's checkout."""
        owners = [layer for layer in self.layers if path.is_relative_to(layer.root)]
        layer = max(owners, key=lambda la: len(la.root.parts), default=None)
        if layer is not None and not layer.local:
            return f"{layer.name}/{path.relative_to(layer.root)}"
        base = self.root.parent if self.root.name == ".jrfc" else self.root
        try:
            return str(path.relative_to(base))
        except ValueError:
            return str(path)

    def source(self, rfc: Rfc, line: int) -> str:
        """Where a statement lives: a GitHub permalink for a pinned parent, else a path."""
        layer = self.layer_of(rfc)
        if layer and not layer.local and layer.parent and layer.parent.url_base:
            return f"{layer.parent.url_base}/{rfc.path.relative_to(layer.root)}#L{line}"
        return f"{self.rel(rfc.path)}#L{line}"

    def local_statements(self) -> list[tuple[Rfc, Statement]]:
        return [(r, s) for r, s in self.statements() if r.layer == "local"]

    @property
    def errors(self) -> list[Issue]:
        """Errors in the local layer (the one this workspace owns)."""
        return [i for i in self.issues if i.severity == "error" and i.layer == "local"]

    @property
    def all_errors(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "error"]


def _clean(value) -> str:
    return " ".join(str(value or "").split())


def _as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value]
    return [str(value)]


def load_domains(path: Path, issues: list[Issue]) -> dict[str, Domain]:
    if not path.is_file():
        issues.append(Issue(str(path), 1, "error", "domains-missing", "domains file not found"))
        return {}
    raw = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("domains", {}) or {}
    domains = {}
    for did, d in raw.items():
        d = d or {}
        for key in ("title", "description", "applies_when", "not_applies_when"):
            if not d.get(key):
                issues.append(Issue(str(path), 1, "error", "domain-field", f"domain '{did}' is missing '{key}'"))
        domains[did] = Domain(
            id=did,
            title=_clean(d.get("title")),
            description=_clean(d.get("description")),
            owner=_clean(d.get("owner")),
            applies_when=_clean(d.get("applies_when")),
            not_applies_when=_clean(d.get("not_applies_when")),
        )
    return domains


def _split_front_matter(text: str) -> tuple[dict | None, list[str], int]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, lines, 0
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            front = yaml.safe_load("\n".join(lines[1:i])) or {}
            return front, lines[i + 1:], i + 1
    return None, lines, 0


def _parse_statements(rfc_id: str, body: list[str], offset: int, rel: str, issues: list[Issue]) -> list[Statement]:
    statements: list[Statement] = []
    i = 0
    while i < len(body):
        head = STATEMENT_HEAD_RE.match(body[i])
        if not head:
            if LOOSE_HEAD_RE.match(body[i]):
                issues.append(Issue(rel, offset + i + 1, "error", "statement-heading",
                                    f"malformed statement heading: {body[i].strip()!r}"))
            i += 1
            continue
        sid, title = head.group(1), head.group(2).lstrip("—-– ").strip()
        start = i
        i += 1
        text_lines: list[str] = []
        meta: dict[str, str] = {}
        while i < len(body) and not SECTION_HEAD_RE.match(body[i]):
            m = META_RE.match(body[i].strip())
            if m:
                meta[m.group(1).lower()] = m.group(2).strip()
            elif body[i].strip():
                text_lines.append(body[i].strip())
            i += 1
        text = " ".join(text_lines)
        normative = CODE_SPAN_RE.sub("", text)  # `MUST` in backticks is a mention, not a use
        keywords = KEYWORD_RE.findall(normative)
        levels = sorted({LEVEL_OF[k] for k in keywords}, key=lambda lv: -LEVEL_RANK[lv])
        statements.append(Statement(
            id=sid,
            rfc_id=rfc_id,
            title=title,
            text=text,
            level=levels[0] if levels else None,
            keywords=keywords,
            applies_when=meta.get("applies when") or None,
            not_applies_when=meta.get("not applies when") or None,
            enforcement=(meta.get("enforcement") or "agent").lower(),
            line=offset + start + 1,
            artifacts=[a.strip() for a in meta["artifacts"].split(",")] if meta.get("artifacts") else None,
            tools=meta.get("tools") or None,
            violated_when=meta.get("violated when") or None,
            pattern=meta.get("pattern") or None,
        ))
        # lint per statement
        line = offset + start + 1
        if not sid.startswith(rfc_id + "."):
            issues.append(Issue(rel, line, "error", "statement-prefix", f"{sid} does not belong to {rfc_id}"))
        if not keywords:
            issues.append(Issue(rel, line, "error", "no-keyword", f"{sid} has no RFC 2119 keyword in UPPERCASE"))
        if len(levels) > 1:
            issues.append(Issue(rel, line, "error", "mixed-levels",
                                f"{sid} mixes levels {'/'.join(levels)}; split it (JRFC-0001.1)"))
        lower = LOWER_KEYWORD_RE.findall(normative)
        if lower:
            issues.append(Issue(rel, line, "warning", "lowercase-keyword",
                                f"{sid} uses lowercase '{lower[0]}'; RFC 8174 gives it no normative meaning"))
        if not meta.get("applies when"):
            issues.append(Issue(rel, line, "warning", "no-applies-when",
                                f"{sid} has no 'Applies when:' line; the RFC-level one is used (JRFC-0001.3)"))
        if meta.get("tools"):
            try:
                re.compile(meta["tools"])
            except re.error as err:
                issues.append(Issue(rel, line, "error", "tools", f"{sid} Tools is not a valid regex: {err}"))
        if meta.get("pattern"):
            try:
                re.compile(meta["pattern"])
            except re.error as err:
                issues.append(Issue(rel, line, "error", "pattern", f"{sid} Pattern is not a valid regex: {err}"))
        enf = (meta.get("enforcement") or "agent").lower()
        if meta.get("pattern") and enf != "linter":
            issues.append(Issue(rel, line, "error", "pattern-enforcement",
                                f"{sid} has a Pattern, so it is checked by code: use 'Enforcement: linter'"))
        if enf not in ENFORCEMENTS:
            issues.append(Issue(rel, line, "error", "enforcement", f"{sid} has unknown enforcement '{enf}'"))
    return statements


def parse_rfc(path: Path, root: Path, issues: list[Issue], prefix: str | None = "JRFC") -> Rfc | None:
    rel = str(path.relative_to(root)) if path.is_relative_to(root) else str(path)
    front, body, offset = _split_front_matter(path.read_text(encoding="utf-8"))
    if front is None:
        issues.append(Issue(rel, 1, "error", "front-matter", "missing YAML front matter"))
        return None
    for key in REQUIRED_FRONT:
        if front.get(key) in (None, "", []):
            issues.append(Issue(rel, 1, "error", "front-field", f"missing front matter field '{key}'"))
    rid = str(front.get("id", ""))
    if prefix is None:
        issues.append(Issue(rel, 1, "error", "no-prefix",
                            "this corpus layer has no `prefix:` in its jrfc.yaml (e.g. prefix: BOOK)"))
    elif not re.fullmatch(rf"{prefix}-\d{{4}}", rid):
        issues.append(Issue(rel, 1, "error", "rfc-id", f"id '{rid}' must look like {prefix}-0000 in this corpus"))
    elif not path.name.startswith(rid):
        issues.append(Issue(rel, 1, "error", "file-name", f"file name must start with '{rid}'"))
    status = str(front.get("status", ""))
    if status not in STATUSES:
        issues.append(Issue(rel, 1, "error", "status", f"status '{status}' not in {STATUSES}"))
    artifacts = _as_list(front.get("artifacts"))
    for a in artifacts:
        if a not in ARTIFACTS:
            issues.append(Issue(rel, 1, "error", "artifacts", f"artifact '{a}' not in {ARTIFACTS}"))
    review_by = str(front.get("review_by", ""))
    try:
        if review_by and dt.date.fromisoformat(review_by) < dt.date.today():
            issues.append(Issue(rel, 1, "warning", "review-overdue", f"review_by {review_by} is in the past"))
    except ValueError:
        issues.append(Issue(rel, 1, "error", "review-by", f"review_by '{review_by}' is not an ISO date"))
    rfc = Rfc(
        id=rid,
        title=_clean(front.get("title")),
        status=status,
        domain=str(front.get("domain", "")),
        artifacts=artifacts,
        languages=_as_list(front.get("languages")) or ["any"],
        owner=_clean(front.get("owner")),
        review_by=review_by,
        summary=_clean(front.get("summary")),
        applies_when=_clean(front.get("applies_when")),
        not_applies_when=_clean(front.get("not_applies_when")),
        supersedes=_as_list(front.get("supersedes")),
        superseded_by=front.get("superseded_by"),
        retired=_as_list(front.get("retired")),
        path=path,
    )
    rfc.statements = _parse_statements(rid, body, offset, rel, issues)
    if not rfc.statements and status != "deprecated":
        issues.append(Issue(rel, 1, "error", "no-statements", f"RFC has no '### {rid or 'PREFIX-0000'}.n' statements"))
    if status == "deprecated" and not rfc.superseded_by:
        issues.append(Issue(rel, 1, "warning", "superseded-by", "deprecated RFC should name superseded_by"))
    return rfc


def _load_layer(layer: Layer, root: Path, domains: dict[str, Domain], rfcs: dict[str, Rfc],
                has_parent: bool) -> list[Issue]:
    issues: list[Issue] = []
    if layer.domains_file.is_file() or not (layer.local and has_parent):
        for did, d in load_domains(layer.domains_file, issues).items():
            if did in domains:
                issues.append(Issue(str(layer.domains_file), 1, "error", "domain-redefined",
                                    f"domain '{did}' already exists in {domains[did].layer}; reuse it"))
                continue
            d.layer = layer.name
            domains[did] = d
    if layer.prefix is not None and not PREFIX_RE.match(layer.prefix):
        issues.append(Issue(str(layer.rfcs_dir), 1, "error", "prefix", f"prefix '{layer.prefix}' must be 2-10 A-Z/0-9"))
    paths = sorted(layer.rfcs_dir.glob("*.md")) if layer.rfcs_dir.is_dir() else []
    for path in paths:
        rfc = parse_rfc(path, root, issues, layer.prefix)
        if rfc is None:
            continue
        rfc.layer = layer.name
        rel = str(path.relative_to(root)) if path.is_relative_to(root) else str(path)
        if rfc.id in rfcs:
            issues.append(Issue(rel, 1, "error", "duplicate-rfc", f"{rfc.id} also defined in {rfcs[rfc.id].path.name}"))
            continue
        seen: set[str] = set()
        for st in rfc.statements:
            if st.id in seen:
                issues.append(Issue(rel, st.line, "error", "duplicate-statement", f"{st.id} is defined twice"))
            for a in st.artifacts or []:
                if a not in rfc.artifacts:
                    issues.append(Issue(rel, st.line, "error", "statement-artifacts",
                                        f"{st.id} artifact '{a}' is not in the RFC artifacts {rfc.artifacts}"))
            if "tool" in (st.artifacts or rfc.artifacts) and not st.tools:
                issues.append(Issue(rel, st.line, "warning", "no-tools",
                                    f"{st.id} applies to tool calls but has no 'Tools:' line; it matches every hooked tool"))
            if st.id in rfc.retired:
                issues.append(Issue(rel, st.line, "error", "retired-reused",
                                    f"{st.id} is retired and must not be reused (JRFC-0001.2)"))
            seen.add(st.id)
        rfcs[rfc.id] = rfc
    for i in issues:
        i.layer = layer.name
    return issues


def load_corpus(cfg: Config) -> Corpus:
    """Load the parent layer (if any) then the local layer into one corpus."""
    issues: list[Issue] = []
    domains: dict[str, Domain] = {}
    rfcs: dict[str, Rfc] = {}
    has_parent = cfg.parent is not None
    prefixes = [layer.prefix for layer in cfg.layers if layer.prefix]
    if len(prefixes) != len(set(prefixes)):
        issues.append(Issue(str(cfg.path or cfg.root), 1, "error", "prefix-collision",
                            f"the local prefix must differ from the extended corpus prefix ({', '.join(prefixes)})"))
    for layer in cfg.layers:
        issues += _load_layer(layer, cfg.root, domains, rfcs, has_parent)
    for rfc in rfcs.values():
        rel = str(rfc.path.relative_to(cfg.root)) if rfc.path.is_relative_to(cfg.root) else str(rfc.path)
        if rfc.domain and rfc.domain not in domains:
            issues.append(Issue(rel, 1, "error", "unknown-domain",
                                f"domain '{rfc.domain}' is not defined in any corpus layer", rfc.layer))
        for sup in rfc.supersedes + ([rfc.superseded_by] if rfc.superseded_by else []):
            if sup not in rfcs:
                issues.append(Issue(rel, 1, "error", "unknown-ref", f"references unknown RFC {sup}", rfc.layer))
            elif rfcs[sup].layer != rfc.layer:
                issues.append(Issue(rel, 1, "error", "cross-layer-ref",
                                    f"{rfc.id} and {sup} are in different corpus layers; a local RFC cannot "
                                    "supersede an organisation RFC (propose the change upstream)", rfc.layer))
    from .effects import load_effects
    effects = load_effects([layer.effects_file for layer in cfg.layers], issues)
    return Corpus(root=cfg.root, domains=domains, rfcs=rfcs, issues=issues, layers=cfg.layers, effects=effects)


def check_against(corpus: Corpus, old_index: dict) -> list[Issue]:
    """Compare with a previous index (for example the base branch) to keep IDs stable."""
    issues: list[Issue] = []
    current = {s.id: (r, s) for r, s in corpus.statements()}
    for old in old_index.get("statements", []):
        sid = old["id"]
        rfc = corpus.rfcs.get(sid.split(".")[0])
        if sid not in current:
            if rfc is None or sid not in rfc.retired:
                if rfc is not None and rfc.layer != "local":
                    continue  # the parent corpus checks its own ids
                path = corpus.rel(rfc.path) if rfc else sid
                issues.append(Issue(path, 1, "error", "statement-removed",
                                    f"{sid} was removed; add it to 'retired:' instead of deleting silently (JRFC-0001.2)"))
    return issues
