"""Known side effects of library calls, turned into facts that Jev can read.

Jev judges the text it is given. `get_parser(lang)` or `h.DB.Query(...)` do not say "network
call", so the timeout rule is not selected (measured: p 0.14 without the fact, 0.77 with it).
Code supplies the fact, Jev judges it:

    effects.yaml (reviewed, per corpus layer)       what a library call does
      -> direct: imports + calls in the chunk text   code, no repository needed
      -> indirect: calls the chunk makes, followed   code graph (repository needed),
         through the repository to a library call    e.g. send_email -> smtplib.SMTP
      -> `known_effects` in the Jev state and in the reviewer prompt

An entry matches when the code imports its `module` (prefix match on the import spec) and
  - calls one of `calls` through that import (`requests.post`, `from x import get; get()`), or
  - calls one of `methods` on any receiver (`db.Query` after importing `database/sql`).
An entry with `languages` and no `module` matches bare calls of built-ins (`fetch` in JS).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .artifact import Artifact, Chunk
from .codegraph import RepoIndex, expand, names_in, parse_import

MAX_FACTS = 8
IMPORT_START = re.compile(r"^\s*(?:import\b|from\s+\S+\s+import\b|use\s|using\s|(?:const|let|var)\s+\w+\s*=\s*require\(|"
                          r"require(?:_relative)?\s*\(?[\"'])")
RUBY_REQUIRE = re.compile(r"^require(?:_relative)?\s*\(?[\"']([^\"']+)[\"']")


@dataclass
class Effect:
    id: str
    effect: str
    module: str | None = None
    calls: list[str] = field(default_factory=list)
    methods: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    owner: str = ""
    source: str = ""          # file the entry comes from (for lint messages)


def load_effects(files: list[Path], issues: list | None = None) -> list[Effect]:
    """Entries of every existing effects file; malformed entries become lint issues."""
    from .corpus import Issue
    out: list[Effect] = []
    seen: set[str] = set()
    for path in files:
        if path is None or not path.is_file():
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for i, raw in enumerate(data.get("effects") or [], 1):
            where = f"{path.name} entry {i}"
            problem = None
            if not isinstance(raw, dict) or not raw.get("id") or not raw.get("effect"):
                problem = f"{where}: needs `id` and `effect`"
            elif not (raw.get("calls") or raw.get("methods")):
                problem = f"{where} ({raw['id']}): needs `calls` or `methods`"
            elif not raw.get("module") and not raw.get("languages"):
                problem = f"{where} ({raw['id']}): needs `module`, or `languages` for a built-in"
            elif raw["id"] in seen:
                problem = f"{where}: duplicate id {raw['id']}"
            if problem:
                if issues is not None:
                    issues.append(Issue(str(path), 1, "error", "effects", problem))
                continue
            seen.add(raw["id"])
            out.append(Effect(id=raw["id"], effect=" ".join(str(raw["effect"]).split()),
                              module=raw.get("module"), calls=list(raw.get("calls") or []),
                              methods=list(raw.get("methods") or []),
                              languages=list(raw.get("languages") or []), owner=raw.get("owner", ""),
                              source=str(path)))
    return out


# ---------------------------------------------------------------- matching


def import_statements(lines: list[str]) -> list[str]:
    """Import statements in source lines, multi-line forms joined (Go blocks, Python and JS
    parenthesised/braced lists). Works on diff fragments: no parse tree needed."""
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if re.match(r"^import\s*\($", line):                    # Go import block
            i += 1
            while i < len(lines) and lines[i].strip() != ")":
                if lines[i].strip():
                    out.append("import " + lines[i].strip())
                i += 1
        elif IMPORT_START.match(line):
            stmt = line
            opened = stmt.count("(") + stmt.count("{") - stmt.count(")") - stmt.count("}")
            while opened > 0 and i + 1 < len(lines):
                i += 1
                stmt += " " + lines[i].strip()
                opened = stmt.count("(") + stmt.count("{") - stmt.count(")") - stmt.count("}")
            out.append(stmt)
        i += 1
    return out


def import_paths(statements: list[str]) -> set[str]:
    """Full import paths, kept apart from `bindings` because namespace imports collide on the
    local name (`using System.Net.Http;` and `using Booking.Http;` both bind `Http`)."""
    return {_full(orig, spec) for stmt in statements for _, orig, spec in parse_import(stmt) if orig}


def bindings(statements: list[str]) -> dict[str, tuple[str | None, str]]:
    """local name -> (imported name, module spec)."""
    out: dict[str, tuple[str | None, str]] = {}
    for stmt in statements:
        ruby = RUBY_REQUIRE.match(stmt.strip())
        if ruby:  # require "faraday" binds the gem's constant (Faraday), matched case-insensitively
            out[ruby.group(1).rstrip("/").split("/")[-1]] = (None, ruby.group(1))
            continue
        for local, orig, spec in parse_import(stmt):
            out[local] = (orig, spec)
    return out


def _full(orig: str | None, spec: str) -> str:
    spec = spec.strip().strip("\"'")
    return f"{spec}.{orig}" if orig else spec


def _bound(imports: dict[str, tuple[str | None, str]], module: str) -> dict[str, str]:
    """Local names bound to `module` -> the imported name (the local name for `import mod`)."""
    out = {}
    for local, (orig, spec) in imports.items():
        if _module_matches(spec, module) or _module_matches(_full(orig, spec), module):
            out[local] = orig or local
            out.setdefault(local.lower(), orig or local)
    return out


def _module_matches(spec: str, module: str) -> bool:
    spec = spec.strip().strip("\"'")
    return spec == module or spec.startswith(module + ".") or spec.startswith(module + "/")


STRING_RE = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|`[^`]*`')


def calls_in(text: str) -> list[str]:
    """Call chains with the arguments removed, so `URL("x").readText()` reads `URL.readText`."""
    out: list[str] = []
    for line in text.splitlines():
        t = STRING_RE.sub('""', line)
        out += names_in(t)  # as written too: `get_parser(lang).parse()` keeps `get_parser`
        prev = None
        while prev != t:
            prev = t
            t = re.sub(r"\(([^()]*)\)(?=\s*(?:\.|\?\.|->))", "", t)  # call results used as receivers
        out += names_in(t)
        out += re.findall(r"\b([A-Za-z_]\w*\.[A-Z]\w*)\s*\{", t)  # Go: &http.Client{...}
        out += re.findall(r"\bnew\s+([A-Z][\w.]*)\s*(?:[({]|$)", t)   # new HttpClient { ... }
        out += re.findall(r"\b([A-Z]\w*(?:(?:\.|::)[A-Z]\w*)*(?:\.|::)new)\b", t)  # Ruby: Faraday.new
    return list(dict.fromkeys(out))


def typed_names(text: str, module_names: set[str]) -> set[str]:
    """Variables and fields whose value or type comes from the module: `DB *sql.DB`,
    `consumer = Consumer(...)`, `engine: Engine`, then one step further (`cur = conn.cursor()`)."""
    typed: set[str] = set()
    for _ in range(2):
        names = module_names | typed
        if not names:
            break
        alt = "|".join(sorted(map(re.escape, names), key=len, reverse=True))
        patterns = [
            rf"\b(\w+)\s*:?\s*[*&]?\s*(?:{alt})\.\w+\b(?!\s*\()",      # DB *sql.DB, x: mod.Type
            rf"\b(\w+)\s*:\s*(?:{alt})\b",                             # x: ImportedType
            rf"\b(\w+)\s*:?=\s*(?:await\s+|new\s+)?(?:{alt})(?:\.\w+)*\s*\(",  # x = mod.f(...), x := f(...)
            rf"\b(?:{alt})\??\s+(\w+)\s*[=;,)]",                        # HttpClient _client = ... (C#, Java)
        ]
        for pattern in patterns:
            typed |= {m.group(1) for m in re.finditer(pattern, text)}
    return typed - {"return", "var", "val", "let", "const", "self", "this"}


def match(effects: list[Effect], imports: dict[str, tuple[str | None, str]], calls: list[str],
          language: str, text: str = "", paths: set[str] | None = None) -> list[tuple[Effect, str]]:
    """(effect, call chain) pairs for the calls that an entry describes. A `methods` hit counts
    only when its receiver is traceably from the module (a false fact misleads more than none)."""
    found: list[tuple[Effect, str]] = []
    for eff in effects:
        if eff.languages and language not in eff.languages:
            continue
        if eff.module is None:
            hits = [c for c in calls if c.split(".")[-1] in eff.calls and
                    (len(c.split(".")) == 1 or c.split(".")[0] in ("window", "globalThis"))]
        else:
            local = _bound(imports, eff.module)
            namespace = eff.module in (paths if paths is not None else
                                       {_full(orig, spec) for orig, spec in imports.values() if orig})
            qualified = eff.module.replace("::", ".").replace("/", ".").replace("\\", ".").split(".")
            classes = {c for c in eff.calls if c[:1].isupper()} if namespace else set()
            receivers = set(local) | (typed_names(text, set(local) | classes) if eff.methods else set())
            hits = []
            for c in calls:
                parts = c.split(".")
                head, last = parts[0], parts[-1]
                bound = local.get(head) or local.get(head.lower())   # Ruby: require "faraday" -> Faraday
                via_module = bound is not None and (
                    len(parts) > 1 and (last in eff.calls or bound in eff.calls) or   # mod.f(), Cls.builder()
                    len(parts) == 1 and bound in eff.calls)                          # from mod import f; f()
                via_namespace = namespace and head in eff.calls                      # using System.Net.Http
                via_path = parts[:len(qualified)] == qualified and any(
                    q in eff.calls for q in parts[len(qualified):])                   # reqwest::blocking::Client
                via_method = len(parts) > 1 and last in eff.methods and bool(set(parts[:-1]) & receivers)
                if via_module or via_namespace or via_path or via_method:
                    names = set(eff.calls) | set(eff.methods)
                    cut = next((i for i, x in enumerate(parts) if i and x in names), len(parts) - 1)
                    hits.append(".".join(parts[:cut + 1]))  # `requests.get.json` -> `requests.get`
        for c in hits[:1]:  # one fact per entry is enough for a judgment
            found.append((eff, c))
    return found


def _code_lines(chunk: Chunk) -> list[str]:
    return [chunk.line_text[n] for n in sorted(chunk.line_text)]


def direct_facts(effects: list[Effect], chunk: Chunk) -> list[str]:
    lines = _code_lines(chunk)
    text = "\n".join(lines)
    statements = import_statements(lines)
    return [f"`{call}` ({eff.module or 'built-in'}) {eff.effect}"
            for eff, call in match(effects, bindings(statements), calls_in(text), chunk.language, text,
                                   import_paths(statements))]


def _file_imports(index: RepoIndex, rel: str) -> list[str]:
    try:
        return import_statements((index.root / rel).read_text(encoding="utf-8").splitlines())
    except (OSError, UnicodeDecodeError):
        return []


def indirect_facts(effects: list[Effect], chunk: Chunk, index: RepoIndex, max_depth: int = 2) -> list[str]:
    """Follow the calls on the chunk's changed lines through the repository; report library
    calls with a known effect that the followed code makes."""
    if not (index.root / chunk.path).is_file():
        return []
    changed = [chunk.line_text[n] for n in sorted(chunk.anchor_lines) if n in chunk.line_text]
    seeds = names_in("\n".join(changed))
    if not seeds:
        return []
    windows, _ = expand(index, seeds, chunk.path, max_depth=max_depth)
    out: list[str] = []
    for w in windows:
        if w.path == chunk.path:
            continue  # the chunk's own file: direct_facts reads its text
        info = index.file(w.path)
        statements = _file_imports(index, w.path)
        imports = bindings(statements)  # text-level too: the graph does not see Ruby's require
        imports.update({local: (imp.name, imp.spec) for local, imp in info.imports.items()})
        for eff, call in match(effects, imports, calls_in(w.text), info.lang or "", w.text,
                               import_paths(statements)):
            out.append(f"`{' -> '.join(w.via)}` reaches `{call}` in {w.path}:{w.start} "
                       f"({eff.module or 'built-in'}), which {eff.effect}")
    return out


def chunk_facts(effects: list[Effect], artifact: Artifact, index: RepoIndex | None = None,
                max_depth: int = 2) -> dict[str, list[str]]:
    """chunk id -> facts (only chunks of code; prose has no calls to follow)."""
    out: dict[str, list[str]] = {}
    if not effects:
        return out
    for chunk in artifact.chunks:
        if chunk.kind not in ("diff", "code"):
            continue
        facts = direct_facts(effects, chunk)
        if index is not None and index.enabled:
            facts += indirect_facts(effects, chunk, index, max_depth)
        facts = list(dict.fromkeys(facts))[:MAX_FACTS]
        if facts:
            out[chunk.id] = facts
    return out
