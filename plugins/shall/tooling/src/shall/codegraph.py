"""A deterministic, language-generic code graph for evidence retrieval.

Keyword search finds the first file of a chain and stops: `gateway.hold(...)` finds
`gateway.ts`, but the timeout lives in `request()` one call further. This graph follows the
chain the way a reader would: calls on the flagged line -> their definitions -> the calls,
base classes and decorators inside them -> ... up to MAX_DEPTH hops.

It is generic across languages; nothing in here is written for one language:
  - tree-sitter grammars and their standard *tags* queries (the ones behind GitHub code
    navigation) give definitions (`definition.*`) and references (`reference.*`) for every
    mainstream language (Python, TS/JS, Java, Kotlin, Go, PHP, Ruby, C#, Rust, Scala, Swift,
    C/C++, Elixir, ...);
  - generic tree rules add what tags do not capture: `this.x =`, `self.x =`, `@x =`,
    `$this->x =` members, top-level constants, and decorators/annotations on a definition;
  - imports are resolved from their text to repository files by path suffix
    (`com.tf.http.Requests`, `crate::http::client`, `App\\Http\\Client`, `../http/client`,
    Go package directories); a package listed in a dependency manifest is external and is
    never matched to same-named local code;
  - files are parsed lazily: `git grep` finds the files that mention a name, only those are
    parsed, so the cost follows the chain and not the repository size.

A file with no grammar or tags query (YAML, SQL, Terraform, Dockerfile, ...) contributes
nothing here; keyword search covers it. Every hop is recorded in `via`; a hop resolved only by
matching a name (no import, not in the same file) is marked "(by name)" so the verifier knows
it may be a different symbol. No model is involved.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

MAX_DEPTH = 3
MAX_GLOBAL_DEFS = 3       # a name with more same-named definitions than this is too ambiguous
MAX_FRONTIER = 40
MAX_WINDOWS = 24
MAX_GREP_FILES = 40
WINDOW_LINES = 60
MAX_FILE_BYTES = 400_000
# Evidence goes into a Jev state and the verifier prompt: a minified file or a one-line JSON
# cache must not make an excerpt larger than the request budget.
MAX_LINE_CHARS = 400
MAX_EXCERPT_CHARS = 12_000
GIT_TIMEOUT = 30

SKIP_PARTS = {".git", ".venv", "venv", "node_modules", ".shall-out", ".shall-cache", "__pycache__", "dist",
              "build", "target", "vendor", ".gradle", ".idea"}
MANIFESTS = ("package.json", "requirements.txt", "requirements-dev.txt", "pyproject.toml", "setup.py",
             "setup.cfg", "Pipfile", "go.mod", "pom.xml", "build.gradle", "build.gradle.kts",
             "settings.gradle", "composer.json", "Cargo.toml", "Gemfile", "Package.swift", "mix.exs",
             "build.sbt", "packages.config", "Directory.Packages.props")
NOT_NAMES = {
    "if", "for", "while", "switch", "catch", "function", "return", "await", "new", "typeof", "delete",
    "this", "self", "super", "cls", "constructor", "print", "len", "str", "int", "float", "dict", "list",
    "set", "tuple", "bool", "isinstance", "range", "open", "require", "JSON", "Math", "Object", "Array",
    "Promise", "String", "Number", "Boolean", "Error", "console", "process", "env", "then", "string",
    "error", "void", "any", "unknown", "var", "val", "let", "const", "fun", "fn", "func", "def", "end",
}
REF_KINDS = ("reference.call", "reference.send", "reference.class", "reference.implementation",
             "reference.type")
CLASS_KINDS = ("definition.class", "definition.interface", "definition.module", "definition.struct",
               "definition.trait", "definition.enum", "definition.object", "definition.impl")
IDENT_RE = re.compile(r"[A-Za-z_$][\w$]*")
MEMBER_ASSIGN_RE = re.compile(r"^\s*(?:this\s*\.|self\s*\.|@|\$this\s*->)\s*([A-Za-z_]\w*)\s*(?::[^=]+)?=(?!=)")
DECORATION_TYPES = ("decorator", "annotation", "attribute_item", "attribute_list", "marker_annotation")
# tree-sitter's `; inherits:` convention: some packaged tags queries hold only the
# language-specific patterns. Run the parent's query too (data, not per-language logic).
QUERY_PARENTS = {"typescript": ["javascript"], "tsx": ["javascript", "typescript"], "cpp": ["c"]}
CLASSY = ("class", "interface", "struct", "trait", "enum", "impl", "module", "object", "protocol", "record")
CALL_FIELDS = ("function", "method", "name", "constructor", "macro")
BASE_TYPES = ("heritage", "extends", "superclass", "base_list", "base_class", "delegation", "inheritance",
              "super_interfaces", "implements")


@dataclass
class Def:
    name: str
    path: str
    line: int
    end: int
    kind: str = "definition"
    header: int | None = None                        # enclosing class/module line of a member
    calls: list[str] = field(default_factory=list)   # chains used inside the definition


def numbered_lines(lines: list[str], numbers) -> str:
    """`  n | text` lines for an excerpt, each line and the whole text cut to the caps."""
    out, size = [], 0
    for n in numbers:
        text = lines[n - 1]
        if len(text) > MAX_LINE_CHARS:
            text = text[:MAX_LINE_CHARS] + f"…[cut {len(text) - MAX_LINE_CHARS} chars]"
        row = f"{n:>5} | {text}"
        if out and size + len(row) + 1 > MAX_EXCERPT_CHARS:
            out.append("  ... | [excerpt cut]")
            break
        out.append(row)
        size += len(row) + 1
    return "\n".join(out)


@dataclass
class Window:
    path: str
    start: int
    end: int
    text: str
    depth: int
    via: list[str]


@dataclass
class Imported:
    kind: str                 # file | dir | external | unresolved
    targets: list[str]        # repo-relative files (for dir: files of the package directory)
    name: str | None          # the imported (original) name, when the import names one
    spec: str = ""


@dataclass
class FileInfo:
    lang: str | None
    defs: list[Def] = field(default_factory=list)
    refs: list[tuple[int, int, str]] = field(default_factory=list)   # (start, end, chain)
    imports: dict[str, Imported] = field(default_factory=dict)


def treesitter_available() -> bool:
    try:
        import tree_sitter  # noqa: F401
        import tree_sitter_language_pack  # noqa: F401
        return True
    except ImportError:
        return False


def normalize_chain(text: str) -> str:
    """`await new LegacyClient(url).send` -> `LegacyClient.send`; `$this->client->post` ->
    `client.post`; `self.client.post(id).send` -> `client.post.send`."""
    t = " ".join(text.split())
    prev = None
    while prev != t:  # drop call arguments and generic arguments, innermost first
        prev = t
        t = re.sub(r"\([^()]*\)", "", t)
        t = re.sub(r"<[^<>]*>", "", t)
    t = t.replace("?.", ".").replace("->", ".").replace("::", ".").replace("\\", ".")
    t = t.split()[-1] if t.split() else ""
    t = re.sub(r"^(?:\$?this|self|cls|@)\.?", "", t).lstrip("@$.")
    return ".".join(p for p in t.split(".") if IDENT_RE.fullmatch(p))


def names_in(text: str) -> list[str]:
    """Fallback seeds from a quote when its file cannot be parsed: call chains in the text."""
    out = []
    for m in re.finditer(r"((?:new\s+)?[A-Za-z_$@][\w$]*(?:\s*(?:\.|->|::|\?\.)\s*[A-Za-z_$][\w$]*)*)\s*[(<]", text):
        chain = normalize_chain(m.group(1))
        if chain and chain.split(".")[-1] not in NOT_NAMES:
            out.append(chain)
    return list(dict.fromkeys(out))


class RepoIndex:
    """Lazy, per-file index over the repository at `root`."""

    def __init__(self, root: Path, excluded: set[str] | None = None, download_grammars: bool = True):
        self.root = root
        self.excluded = excluded or set()
        self.files: dict[str, FileInfo] = {}
        self.enabled = treesitter_available()
        self.download_grammars = download_grammars
        # what went wrong or happened on the network, for health.json: a failure here means
        # less evidence, which is silent unless it is recorded
        self.events: list[dict] = []
        self._event_keys: set[tuple] = set()
        self._cached_grammars: set[str] | None = None
        self._grep_cache: dict[str, list[str]] = {}
        self._all_files: list[str] | None = None
        self._manifest_text: str | None = None
        self._queries: dict[str, object] = {}

    # ------------------------------------------------------------ repository access

    def _skip(self, rel: str) -> bool:
        return any(p in SKIP_PARTS for p in Path(rel).parts) or \
            any(rel == e or rel.startswith(e.rstrip("/") + "/") for e in self.excluded)

    def all_files(self) -> list[str]:
        if self._all_files is None:
            files: list[str] = []
            try:
                proc = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"],
                                      cwd=self.root, capture_output=True, text=True, timeout=GIT_TIMEOUT)
                if proc.returncode == 0:
                    files = proc.stdout.splitlines()
            except (OSError, subprocess.TimeoutExpired):
                pass
            if not files:
                files = [str(p.relative_to(self.root)) for p in self.root.rglob("*") if p.is_file()]
            self._all_files = sorted(f for f in files if not self._skip(f))
        return self._all_files

    def grep_files(self, name: str) -> list[str]:
        """Files that mention `name` as a word (candidates for its definition)."""
        if name not in self._grep_cache:
            found: list[str] = []
            try:
                proc = subprocess.run(["git", "grep", "-l", "-I", "-w", "-F", "--untracked", "-e", name],
                                      cwd=self.root, capture_output=True, text=True, timeout=GIT_TIMEOUT)
                if proc.returncode in (0, 1):
                    found = proc.stdout.splitlines()
                else:
                    raise OSError
            except (OSError, subprocess.TimeoutExpired):
                pattern = re.compile(rf"\b{re.escape(name)}\b")
                for rel in self.all_files():
                    try:
                        if pattern.search((self.root / rel).read_text(encoding="utf-8", errors="ignore")):
                            found.append(rel)
                    except OSError:
                        continue
            self._grep_cache[name] = [f for f in found if not self._skip(f)][:MAX_GREP_FILES]
        return self._grep_cache[name]

    def manifest_text(self) -> str:
        """Dependency manifests, lowercased with '-' as '_': is a module an external package?"""
        if self._manifest_text is None:
            parts = []
            for rel in self.all_files():
                if Path(rel).name in MANIFESTS:
                    try:
                        parts.append((self.root / rel).read_text(encoding="utf-8", errors="ignore"))
                    except OSError:
                        pass
            self._manifest_text = "\n".join(parts).lower().replace("-", "_")
        return self._manifest_text

    def lines(self, rel: str) -> list[str]:
        try:
            return (self.root / rel).read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return []

    # ------------------------------------------------------------ parsing

    def _event(self, kind: str, **detail) -> None:
        key = (kind, detail.get("lang"), detail.get("path"))
        if key not in self._event_keys:
            self._event_keys.add(key)
            self.events.append({"kind": kind, **detail})

    def _grammar_ready(self, lang: str) -> bool:
        """True when the grammar is cached, or may be downloaded (recorded: a network call)."""
        if self._cached_grammars is None:
            try:
                from tree_sitter_language_pack import downloaded_languages
                self._cached_grammars = set(downloaded_languages())
            except Exception:  # noqa: BLE001 - older pack: cannot tell, assume present
                self._cached_grammars = {"*"}
        if lang in self._cached_grammars or "*" in self._cached_grammars:
            return True
        if not self.download_grammars:
            self._event("grammar_missing", lang=lang)
            return False
        self._event("grammar_download", lang=lang)
        self._cached_grammars.add(lang)
        return True

    def _tags_queries(self, lang: str) -> list:
        """The language's tags query plus its parents'; each compiled on its own so one
        pattern that does not fit the grammar cannot disable the rest."""
        if lang not in self._queries:
            from tree_sitter import Query
            from tree_sitter_language_pack import get_language, get_tags_query
            compiled = []
            for source_lang in [lang, *QUERY_PARENTS.get(lang, [])]:
                try:
                    source = get_tags_query(source_lang)
                    if source:
                        compiled.append(Query(get_language(lang), source))
                except Exception as err:  # noqa: BLE001 - a broken or missing query only disables tags
                    self._event("tags_query_error", lang=source_lang, error=f"{type(err).__name__}: {err}"[:200])
                    continue
            self._queries[lang] = compiled
        return self._queries[lang]

    def file(self, rel: str) -> FileInfo:
        if rel in self.files:
            return self.files[rel]
        info = FileInfo(lang=None)
        self.files[rel] = info
        if not self.enabled or self._skip(rel):
            return info
        path = self.root / rel
        try:
            if not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
                return info
            from tree_sitter_language_pack import detect_language_from_path, get_parser
            lang = detect_language_from_path(rel)
            if not lang or not self._grammar_ready(lang):
                return info
            src = path.read_bytes()
            tree = get_parser(lang).parse(src)
        except Exception as err:  # noqa: BLE001 - unknown grammar, download failure, parse error
            self._event("parse_error", path=rel, error=f"{type(err).__name__}: {err}"[:200])
            return info
        info.lang = lang
        _Extractor(self, rel, lang, src, tree, info).run()
        return info

    # ------------------------------------------------------------ imports

    def resolve_spec(self, spec: str, from_file: str, name: str | None) -> Imported:
        spec = spec.strip()
        files = self.all_files()
        stems = {}
        for f in files:
            stems.setdefault(str(Path(f).with_suffix("")), []).append(f)
        dirs: dict[str, list[str]] = {}
        for f in files:
            dirs.setdefault(str(Path(f).parent), []).append(f)

        def lookup(base: str) -> Imported | None:
            base = base.strip("/")
            if base in stems:
                return Imported("file", stems[base], name, spec)
            for index_name in ("index", "__init__", "mod"):
                if f"{base}/{index_name}" in stems:
                    return Imported("file", stems[f"{base}/{index_name}"], name, spec)
            if base in dirs:
                return Imported("dir", dirs[base], name, spec)
            return None

        if spec.startswith("."):
            # ./x, ../x (JS, Ruby require_relative) or .x, ..x (Python relative modules)
            if "/" in spec or spec in (".", ".."):
                parts: list[str] = list(Path(from_file).parent.parts)
                for p in spec.split("/"):
                    if p == "..":
                        parts = parts[:-1]
                    elif p not in (".", ""):
                        parts.append(p)
                candidates = ["/".join(parts)]
            else:
                dots = len(spec) - len(spec.lstrip("."))
                parts = list(Path(from_file).parent.parts)[: max(0, len(Path(from_file).parent.parts) - (dots - 1))]
                rest = spec.lstrip(".").replace(".", "/")
                candidates = ["/".join([*parts, rest]).strip("/")]
            if name:
                candidates = [f"{candidates[0]}/{name}"] + candidates
            for c in candidates:
                hit = lookup(c)
                if hit:
                    return hit
            return Imported("unresolved", [], name, spec)

        segs = [s for s in re.split(r"[./\\:]+", spec.replace("->", ".")) if s and s not in ("crate", "super", "self", "@")]
        variants = []
        if name and (not segs or segs[-1] != name):
            variants.append([*segs, name])
        variants += [segs, segs[:-1]]
        for v in variants:
            for k in range(len(v), 0, -1):
                if k == 1 and len(v) > 1:
                    break  # a single trailing segment ("http") is too weak to trust
                suffix = "/".join(v[-k:])
                matches = [s for s in stems if s == suffix or s.endswith("/" + suffix)]
                if matches:
                    return Imported("file", sorted(f for m in matches for f in stems[m]), name, spec)
                dmatch = [d for d in dirs if d == suffix or d.endswith("/" + suffix)]
                if dmatch:
                    return Imported("dir", sorted(f for d in dmatch for f in dirs[d]), name, spec)
        package = spec.split("/")[0] if spec.startswith("@") else (segs[0] if segs else spec)
        if package and package.lower().replace("-", "_") in self.manifest_text():
            return Imported("external", [], name, spec)
        return Imported("unresolved", [], name, spec)

    # ------------------------------------------------------------ definitions

    def defs_named(self, name: str, paths: list[str] | None = None) -> list[Def]:
        candidates = paths if paths is not None else self.grep_files(name)
        return [d for p in candidates for d in self.file(p).defs if d.name == name]

    def seeds_at(self, path: str, line: int, quote: str) -> list[str]:
        """Chains used on the flagged line, from the syntax tree when the file parses."""
        refs = self.file(path).refs
        starting = [c for s, e, c in refs if s == line]
        spanning = [c for s, e, c in refs if s <= line <= e]
        found = list(dict.fromkeys(starting or spanning))
        return found or names_in(quote)

    def window(self, d: Def, depth: int, via: list[str]) -> Window:
        lines = self.lines(d.path)
        end = min(d.end, d.line + WINDOW_LINES - 1, len(lines))
        if d.kind in CLASS_KINDS and d.end - d.line + 1 > WINDOW_LINES:
            end = min(d.line + 2, len(lines))  # members are indexed on their own
        text = numbered_lines(lines, range(d.line, end + 1))
        start = d.line
        if d.header is not None and d.header < d.line:
            text = numbered_lines(lines, [d.header]) + "\n  ... |\n" + text
            start = d.header
        return Window(path=d.path, start=start, end=end, text=text, depth=depth, via=via)


class _Extractor:
    """Fills a FileInfo from one syntax tree: tags queries + generic rules."""

    def __init__(self, index: RepoIndex, rel: str, lang: str, src: bytes, tree, info: FileInfo):
        self.index, self.rel, self.lang, self.src, self.tree, self.info = index, rel, lang, src, tree, info

    def text(self, node) -> str:
        return self.src[node.start_byte:node.end_byte].decode("utf-8", "replace")

    def run(self) -> None:
        defs: list[tuple[object, object, str]] = []   # (range node, name node, kind)
        from tree_sitter import QueryCursor
        for query in self.index._tags_queries(self.lang):
            for _, caps in QueryCursor(query).matches(self.tree.root_node):
                name_nodes = caps.get("name")
                kinds = [k for k in caps if k != "name" and not k.startswith("doc")]
                if not name_nodes or not kinds:
                    continue
                kind, node, name = kinds[0], caps[kinds[0]][0], name_nodes[0]
                if kind.startswith("definition."):
                    defs.append((node, name, kind))
                elif kind in REF_KINDS:
                    ref_name = self.text(name)
                    if kind == "reference.type" and not ref_name[:1].isupper():
                        continue  # primitive and builtin types are noise
                    chain = normalize_chain(self.src[node.start_byte:name.end_byte].decode("utf-8", "replace"))
                    if not chain.endswith(ref_name):
                        chain = ref_name
                    if chain and ref_name not in NOT_NAMES:
                        self.info.refs.append((node.start_point[0] + 1, node.end_point[0] + 1, chain))
        self._generic_defs(defs)
        self._generic_structure(defs)
        self._imports()
        class_nodes = [(n.start_byte, n.end_byte, n.start_point[0] + 1) for n, _, k in defs if k in CLASS_KINDS]
        refs, seen_refs = [], set()
        for ref in self.info.refs:  # tags and generic rules may both report a call
            if (ref[0], ref[2]) not in seen_refs:
                seen_refs.add((ref[0], ref[2]))
                refs.append(ref)
        # a bare `hold` next to `gateway.hold` on the same line adds only by-name noise
        qualified = {(s, c.split(".")[-1]) for s, _, c in refs if "." in c}
        self.info.refs = [r for r in refs if "." in r[2] or (r[0], r[2]) not in qualified]
        seen = set()
        for node, name, kind in defs:
            rng = self._with_decorations(node)
            start, end = rng.start_point[0] + 1, rng.end_point[0] + 1
            nm = self.text(name) if not isinstance(name, str) else name
            key = (nm, start)
            if key in seen or not nm or nm in NOT_NAMES:
                continue
            seen.add(key)
            header = None
            enclosing = [c for c in class_nodes if c[0] < node.start_byte and node.end_byte <= c[1]]
            if enclosing:
                header = max(enclosing, key=lambda c: c[0])[2]
            calls = [c for s, e, c in self.info.refs if start <= s <= end]
            if header is not None:  # a member also depends on its class's base classes
                calls += [c for s, e, c in self.info.refs if s == header]
            self.info.defs.append(Def(nm, self.rel, start, end, kind, header, list(dict.fromkeys(calls))))

    def _generic_structure(self, defs: list) -> None:
        """Grammar-agnostic definitions and calls, unioned with the tags query results:
        any `*_definition` / `*_declaration` / `*_item` node with a `name` field is a definition;
        any call/invocation node is a reference."""
        stack = [self.tree.root_node]
        while stack:
            n = stack.pop()
            stack.extend(reversed(n.children))
            t = n.type
            if not n.is_named:
                continue
            if t.endswith(("_definition", "_declaration", "_item", "_specifier")) and "import" not in t:
                name = n.child_by_field_name("name")
                if name is not None and ("identifier" in name.type or name.type in ("name", "constant")):
                    kind = "definition.class" if any(k in t for k in CLASSY) else "definition.function"
                    defs.append((n, name, kind))
            # base classes / implemented interfaces, whatever the grammar calls them
            if any(k in t for k in BASE_TYPES) or (t == "argument_list" and n.parent is not None
                                                   and n.parent.type == "class_definition"):
                for c in n.children:
                    for leaf in ([c] if "identifier" in c.type or c.type in ("constant", "name", "attribute")
                                 else [x for x in c.children if "identifier" in x.type]):
                        chain = normalize_chain(self.text(leaf))
                        if chain:
                            self.info.refs.append((n.start_point[0] + 1, n.start_point[0] + 1, chain))
            if "call" in t or "invocation" in t or t in ("new_expression", "object_creation_expression"):
                target = next((n.child_by_field_name(f) for f in CALL_FIELDS if n.child_by_field_name(f) is not None),
                              None)
                if target is None:
                    target = next((c for c in n.children if c.is_named), None)
                if target is None:
                    continue
                if t == "method_invocation" and n.child_by_field_name("object") is not None:
                    text = self.text(n.child_by_field_name("object")) + "." + self.text(target)
                else:
                    text = self.src[n.start_byte:target.end_byte].decode("utf-8", "replace")
                chain = normalize_chain(text)
                if chain and chain.split(".")[-1] not in NOT_NAMES:
                    self.info.refs.append((n.start_point[0] + 1, n.end_point[0] + 1, chain))

    def _with_decorations(self, node):
        """Extend a definition to its decorators/annotations (Python decorated_definition,
        preceding decorator or attribute siblings)."""
        parent = node.parent
        if parent is not None and parent.type.endswith("decorated_definition"):
            return parent
        return node

    def _generic_defs(self, defs: list) -> None:
        tagged = {(n.start_byte, n.end_byte) for n, _, _ in defs}
        root = self.tree.root_node
        stack = [root]
        while stack:
            n = stack.pop()
            stack.extend(reversed(n.children))
            if (n.start_byte, n.end_byte) in tagged or not n.is_named:
                continue
            t = n.type
            parent = n.parent
            # members assigned through the instance: this.x = / self.x = / @x = / $this->x =
            if "assignment" in t:
                m = MEMBER_ASSIGN_RE.match(self.text(n))
                if m:
                    stmt = parent if parent is not None and "statement" in parent.type else n
                    defs.append((stmt, m.group(1), "definition.field"))
                    continue
            # top-level constants and variables: `_session = make_session()`, `const http = ...`
            top = parent is not None and (parent == root or (parent.parent == root and "export" in parent.type))
            if top and any(k in t for k in ("assignment", "declaration", "expression_statement")):
                for name in self._declared_names(n):
                    defs.append((parent if "export" in parent.type else n, name, "definition.constant"))
            # class fields and properties
            if any(k in t for k in ("field_declaration", "field_definition", "property_declaration")):
                for name in self._declared_names(n):
                    defs.append((n, name, "definition.field"))

    def _declared_names(self, n) -> list[str]:
        name = n.child_by_field_name("name")
        if name is not None and "identifier" in name.type:
            return [self.text(name)]
        out = []
        # declarators may be nested (C#: field_declaration > variable_declaration > variable_declarator);
        # the name is the declarator's, never the first identifier (that can be the type)
        stack = list(n.children)
        depth_left = {id(c): 3 for c in stack}
        while stack:
            c = stack.pop(0)
            if c.type.endswith("declarator") or c.type.endswith("_spec"):
                inner = c.child_by_field_name("name") or next((x for x in c.children if "identifier" in x.type), None)
                if inner is not None and "identifier" in inner.type:
                    out.append(self.text(inner))
                continue
            if c.type in ("variable_declaration", "variable_declarations", "property_declaration") and depth_left.get(id(c), 0) > 0:
                for x in c.children:
                    depth_left[id(x)] = depth_left[id(c)] - 1
                    stack.append(x)
                continue
            if c.type == "assignment" or c.type.endswith("assignment_expression"):
                left = c.child_by_field_name("left")
                if left is not None and left.type == "identifier":
                    out.append(self.text(left))
        left = n.child_by_field_name("left")
        if not out and left is not None and left.type == "identifier":
            out.append(self.text(left))
        return [o for o in out if IDENT_RE.fullmatch(o)]

    def _imports(self) -> None:
        stack = [self.tree.root_node]
        while stack:
            n = stack.pop()
            t = n.type
            if t in ("import_statement", "import_declaration", "import_from_statement", "import_header",
                     "import_spec", "use_declaration", "namespace_use_declaration", "using_directive",
                     "import_clause") and not (t == "import_declaration" and any(
                         c.type in ("import_spec", "import_spec_list") for c in n.children)):
                for local, orig, spec in parse_import(self.text(n)):
                    self.info.imports.setdefault(local, self.index.resolve_spec(spec, self.rel, orig))
                continue
            if t in ("call", "call_expression", "method_call", "command") and \
                    re.match(r"^\s*(require|require_relative|load)\b", self.text(n)):
                strings = re.findall(r"[\"']([^\"']+)[\"']", self.text(n))
                if strings:
                    spec = strings[0]
                    if self.text(n).lstrip().startswith("require_relative") and not spec.startswith("."):
                        spec = "./" + spec
                    target = self.index.resolve_spec(spec, self.rel, None)
                    for f in target.targets:  # Ruby-style requires expose what the file defines
                        self.info.imports.setdefault(Path(f).stem, target)
            stack.extend(reversed(n.children))


def parse_import(text: str) -> list[tuple[str, str | None, str]]:
    """(local name, imported name, module spec) for one import statement, in any common syntax."""
    t = " ".join(text.replace("\n", " ").split()).rstrip(";").strip()
    out: list[tuple[str, str | None, str]] = []
    quoted = re.findall(r"[\"']([^\"']+)[\"']", t)
    m = re.match(r"^from\s+(\S+)\s+import\s+\(?(.+?)\)?$", t)                         # Python
    if m:
        for item in m.group(2).split(","):
            orig, _, alias = item.strip().partition(" as ")
            if orig.strip() and orig.strip() != "*":
                out.append(((alias or orig).strip(), orig.strip(), m.group(1)))
        return out
    m = re.match(r"^(?:import|use)\s+(?:static\s+|type\s+)?([^{}\"';]*?)\s*[:\\]*\{([^}]*)\}", t)   # grouped
    if m and not quoted:
        base = m.group(1).rstrip(":\\.")
        for item in m.group(2).split(","):
            orig, _, alias = item.strip().partition(" as ")
            orig = orig.strip().replace("type ", "")
            if orig and orig != "*":
                out.append(((alias or orig).strip(), orig.split("::")[-1].split("\\")[-1], base))
        return out
    if quoted:                                                                        # JS/TS, Go
        spec = quoted[0]
        braces = re.search(r"\{([^}]*)\}", t)
        if braces:
            for item in braces.group(1).split(","):
                orig, _, alias = item.strip().replace("type ", "").partition(" as ")
                if orig.strip():
                    out.append(((alias or orig).strip(), orig.strip(), spec))
        default = re.match(r"^import\s+(?:type\s+)?([A-Za-z_$][\w$]*)\s*(?:,|from)", t)
        star = re.search(r"\*\s+as\s+([A-Za-z_$][\w$]*)", t)
        req = re.match(r"^(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*require", t)
        go_alias = re.match(r"^(?:import\s+)?([A-Za-z_.][\w]*)\s+[\"']", t)
        for local in (default, star, req):
            if local:
                out.append((local.group(1), None, spec))
        if go_alias and go_alias.group(1) not in ("import", "from", "."):
            out.append((go_alias.group(1), None, spec))
        elif not out:
            out.append((spec.rstrip("/").split("/")[-1], None, spec))  # Go: package name = last element
        return out
    m = re.match(r"^(?:import|use|using)\s+(?:static\s+)?([\w.\\:]+?)(?:\s+as\s+(\w+))?(?:\s*=\s*([\w.]+))?$", t)
    if m:                                                                             # Java, Kotlin, PHP, Rust, C#, Python
        path = m.group(3) or m.group(1)
        alias = m.group(2) or (m.group(1) if m.group(3) else None)
        last = re.split(r"[.\\:]+", path)[-1]
        if last == "*":
            return out
        module = re.sub(r"[.\\:]+[^.\\:]+$", "", path)
        out.append((alias or last, last, module if module != path else path))
        if not alias and "." in path and t.startswith("import ") and not re.search(r"[A-Z]", last[:1]):
            out.append((path.split(".")[0], None, path.split(".")[0]))  # Python `import a.b` binds `a`
    return out


def resolve(index: RepoIndex, chain: str, from_file: str) -> tuple[list[Def], str | None, bool]:
    """Definitions of `chain` seen from `from_file`: (defs, note, by_name_only)."""
    parts = chain.split(".")
    head, last = parts[0], parts[-1]
    imp = index.file(from_file).imports.get(head)
    if imp is not None:
        if imp.kind == "external":
            return [], f"`{head}` comes from the external package `{imp.spec}` (not in the repository)", False
        if imp.kind in ("file", "dir") and imp.targets:
            if len(parts) > 1:
                found = index.defs_named(last, imp.targets)
                if imp.name and imp.name != head:
                    found = index.defs_named(imp.name, imp.targets) + found
                elif imp.kind == "file" and not found:
                    found = index.defs_named(head, imp.targets)
            else:
                found = index.defs_named(imp.name or head, imp.targets)
            return found, None, False
        note = f"`{head}` is imported from `{imp.spec}`, which was not found in the repository"
    else:
        note = None
    local = index.defs_named(head, [from_file]) if len(parts) == 1 else \
        index.defs_named(last, [from_file]) or index.defs_named(head, [from_file])
    if local:
        return local, note, False
    everywhere = index.defs_named(last)
    if 0 < len(everywhere) <= MAX_GLOBAL_DEFS:
        return everywhere, note, True
    return [], note, False


def expand(index: RepoIndex, seeds: list[str], from_file: str, max_depth: int = MAX_DEPTH,
           hide: set[str] | None = None) -> tuple[list[Window], list[str]]:
    """Follow `seeds` from `from_file`. Files in `hide` are traversed but not returned (the
    verifier already sees them, e.g. the whole reviewed file)."""
    hide = hide or set()
    windows: list[Window] = []
    notes: list[str] = []
    seen: set[tuple[str, int]] = set()
    frontier = [(s, from_file, []) for s in seeds]
    for depth in range(1, max_depth + 1):
        nxt: list[tuple[str, str, list[str]]] = []
        for chain, origin, via in frontier:
            found, note, by_name = resolve(index, chain, origin)
            if note and note not in notes:
                notes.append(note)
            hop = f"{chain} (by name)" if by_name else chain
            for d in found[:3]:
                if (d.path, d.line) in seen:
                    continue
                seen.add((d.path, d.line))
                if d.path not in hide:
                    windows.append(index.window(d, depth, [*via, hop]))
                for callee in d.calls:
                    if callee != chain and callee.split(".")[-1] != d.name:
                        nxt.append((callee, d.path, [*via, hop]))
        keys: set[tuple[str, str]] = set()
        frontier = []
        for item in nxt:
            if (item[0], item[1]) not in keys:
                keys.add((item[0], item[1]))
                frontier.append(item)
        frontier = frontier[:MAX_FRONTIER]
        if len(windows) >= MAX_WINDOWS:
            break
    return windows[:MAX_WINDOWS], notes
