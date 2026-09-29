"""Workspace configuration and corpus layers.

A workspace has one *local* layer (the corpus next to the config file) and at most one
*parent* layer declared with `extends:` (the organisation corpus, pinned to a ref).

Discovery, first match wins:
  1. --config / $JRFC_CONFIG
  2. walking up from the cwd: `<dir>/.jrfc/jrfc.yaml`, then `<dir>/jrfc.yaml`
  3. $JRFC_EXTENDS ("owner/name@ref" or a path): org corpus only, no local layer
  4. ~/.config/jrfc/config.yaml (user default, usually just an `extends:`)

Layer paths default to `rfcs/`, `domains.yaml`, `index/`, `effects.yaml` inside a `.jrfc/`
folder and to `corpus/rfcs`, `corpus/domains.yaml`, `corpus/index`, `corpus/effects.yaml` for a
root-level jrfc.yaml.
Settings (`jev`, `selection`, `review`) are inherited from the parent and overridden locally.
"""

from __future__ import annotations

import copy
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .fetch import Parent, resolve_parent

CONFIG_NAME = "jrfc.yaml"
DOT_DIR = ".jrfc"
SETTINGS = ("jev", "selection", "review", "conflicts", "codegraph", "triage", "hooks")

DEFAULTS: dict[str, Any] = {
    "jev": {
        "model": "jev-1.13.0",
        "cache": ".jrfc-cache/jev.json",
        "concurrency": 4,
        "max_chunk_chars": 40000,
        "max_request_tokens": 56000,
    },
    "selection": {
        "strategy": "flat",
        "thresholds": {"domain": 0.25, "rfc": 0.30, "statement": 0.50},
        "always_domains": [],
        "include_status": ["approved", "enforced"],
        "facts": True,      # known_effects from effects.yaml in the Jev state (effects.py)
        "facts_depth": 3,   # call hops followed through the repository (as verification)
        "near_margin": 0.15,  # health: statements this far below the threshold are reported
    },
    "codegraph": {
        # false: never download a tree-sitter grammar during a run (run `jrfc prefetch` first);
        # a missing grammar is then reported in health.json instead of a hidden network call
        "download_grammars": True,
    },
    "conflicts": {
        "fail_threshold": 0.75,   # duplicate / weakens / conflict at or above this fails
        "report_threshold": 0.60,  # shown as info (overlap) at or above this
        "exclude_domains": [],     # meta domains never compared (e.g. governance)
    },
    "hooks": {
        # Claude Code hooks (hooks.py). Pre: tool statements judged by Jev before a call.
        # Post: code statements on the lines a Write/Edit produced (warn only). Stop: full review.
        "pre_matcher": "Bash|Write|Edit|MultiEdit|NotebookEdit|mcp__.*",
        "code_tools": "Write|Edit|MultiEdit|NotebookEdit",
        "timeout": 3.0,           # seconds for the Jev step; past it the call runs (fail-open)
        "max_input_chars": 12000,  # longer tool inputs are cut before they reach Jev
        "context_lines": 15,      # lines kept around an edit for code statements
        # status -> level -> [[min p, action], ...] (first match wins). A status without an
        # entry is not checked; add e.g. `draft:` in a workspace to trial draft rules.
        "actions": {
            "enforced": {"MUST": [[0.9, "deny"], [0.5, "ask"]], "SHOULD": [[0.7, "warn"]], "MAY": [[0.7, "log"]]},
            "approved": {"MUST": [[0.5, "warn"]], "SHOULD": [[0.7, "log"]], "MAY": [[0.7, "log"]]},
        },
        "code_warn": 0.7,         # code statements after a write: warn at or above, never block
        "secrets": [],            # [[tool regex, statement id]]: which rule a secret-scanner hit breaks
        "stop": {"enabled": True, "max_blocks": 2, "max_diff_chars": 200000},
        "log": ".jrfc-cache/hooks/decisions.jsonl",
        "port": 8765,
    },
    "review": {
        "command": ["claude", "-p"],
        "model": "claude-sonnet-5",
        "concurrency": 4,
        "max_comments": 25,
        "timeout": 300,  # seconds per agent call
        "verify": True,  # verify blocking findings (and those with depends_on) before they block
        "cache": True,   # reuse agent answers when the prompt is identical (incremental re-review)
    },
    "triage": {
        # comments of other AI reviewers (`jrfc triage`): authors with GraphQL type Bot always
        # count; `*` is the only wildcard. Copilot's GraphQL login has no [bot] suffix.
        "authors": ["*[bot]", "copilot-pull-request-reviewer", "Copilot", "coderabbitai",
                    "gemini-code-assist", "sourcery-ai", "greptile-apps", "cursor"],
        "ignore_authors": ["github-actions*", "dependabot*", "renovate*"],
        "thresholds": {"actionable": 0.5, "statement": 0.5, "duplicate": 0.7},
        "verify": True,  # check each actionable comment against repository evidence (agent)
    },
}


def _merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


@dataclass
class Layer:
    name: str                 # "local" or the parent label (owner/name@ref)
    local: bool
    root: Path
    prefix: str | None        # id prefix of this layer's RFCs, e.g. JRFC or BOOK
    rfcs_dir: Path
    domains_file: Path
    index_dir: Path
    effects_file: Path | None = None   # optional: known side effects of library calls (effects.py)
    parent: Parent | None = None


def _layer(name: str, local: bool, root: Path, raw: dict, in_dot: bool, default_prefix: str | None,
           parent: Parent | None = None) -> Layer:
    d = (("rfcs", "domains.yaml", "index", "effects.yaml") if in_dot else
         ("corpus/rfcs", "corpus/domains.yaml", "corpus/index", "corpus/effects.yaml"))
    return Layer(
        name=name, local=local, root=root,
        prefix=raw.get("prefix", default_prefix),
        rfcs_dir=(root / raw.get("corpus", d[0])).resolve(),
        domains_file=(root / raw.get("domains", d[1])).resolve(),
        index_dir=(root / raw.get("index", d[2])).resolve(),
        effects_file=(root / raw.get("effects", d[3])).resolve(),
        parent=parent,
    )


@dataclass
class Config:
    root: Path
    data: dict
    path: Path | None
    layers: list[Layer] = field(default_factory=list)

    def get(self, dotted: str, default: Any = None) -> Any:
        node: Any = self.data
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    @property
    def local(self) -> Layer:
        return next(layer for layer in self.layers if layer.local)

    @property
    def parent(self) -> Layer | None:
        return next((layer for layer in self.layers if not layer.local), None)

    # local-layer shortcuts (authoring commands work on the local layer)
    @property
    def corpus_dir(self) -> Path:
        return self.local.rfcs_dir

    @property
    def domains_file(self) -> Path:
        return self.local.domains_file

    @property
    def index_dir(self) -> Path:
        return self.local.index_dir

    @property
    def prefix(self) -> str | None:
        return self.local.prefix

    @property
    def cache_file(self) -> Path:
        return (self.root / self.get("jev.cache")).resolve()


def _find() -> tuple[str, Path | None, dict]:
    """Return (kind, path, raw) with kind in workspace | extends-env | user | none."""
    explicit = os.environ.get("JRFC_CONFIG")
    if explicit:
        path = Path(explicit).expanduser().resolve()
        path = path / CONFIG_NAME if path.is_dir() else path
        if not path.is_file():
            raise SystemExit(f"jrfc: config {path} not found")
        return "workspace", path, _read(path)
    for folder in [Path.cwd(), *Path.cwd().parents]:
        for candidate in (folder / DOT_DIR / CONFIG_NAME, folder / CONFIG_NAME):
            if candidate.is_file():
                return "workspace", candidate, _read(candidate)
    if os.environ.get("JRFC_EXTENDS"):
        return "extends-env", None, {"extends": os.environ["JRFC_EXTENDS"]}
    user = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "jrfc" / "config.yaml"
    if user.is_file():
        return "user", user, _read(user)
    return "none", None, {}


def _read(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_config(explicit: str | None = None, update: bool = False) -> Config:
    if explicit:
        os.environ["JRFC_CONFIG"] = explicit
    kind, path, raw = _find()
    if kind == "none":
        raise SystemExit(
            f"jrfc: no config found. Looked for {DOT_DIR}/{CONFIG_NAME} or {CONFIG_NAME} from "
            f"{Path.cwd()} upwards, $JRFC_EXTENDS, and ~/.config/jrfc/config.yaml. "
            "Run `jrfc init` or pass --config."
        )
    has_local = kind == "workspace"
    # without a workspace file there is no local corpus; relative paths anchor at the cwd
    root = path.parent if has_local else Path.cwd()
    in_dot = path.parent.name == DOT_DIR if has_local else True  # no local corpus: .jrfc/rfcs is absent
    if not has_local and not raw.get("extends"):
        raise SystemExit(f"jrfc: {path} has no `extends:`; nothing to load")

    layers: list[Layer] = []
    parent_raw: dict = {}
    if raw.get("extends"):
        parent = resolve_parent(raw["extends"], root, update=update)
        parent_cfg = next((c for c in (parent.root / CONFIG_NAME, parent.root / DOT_DIR / CONFIG_NAME)
                           if c.is_file()), None)
        if parent_cfg is None:
            raise SystemExit(f"jrfc: extended corpus {parent.name} has no {CONFIG_NAME}")
        parent_raw = _read(parent_cfg)
        if parent_raw.get("extends"):
            raise SystemExit(f"jrfc: {parent.name} extends another corpus; only one level is supported")
        layers.append(_layer(parent.name, False, parent_cfg.parent, parent_raw,
                             parent_cfg.parent.name == DOT_DIR, "JRFC", parent))
    local_raw = raw if has_local else {}
    layers.append(_layer("local", True, root, local_raw, in_dot, None if raw.get("extends") else "JRFC"))

    settings = copy.deepcopy(DEFAULTS)
    for source in (parent_raw, raw):
        settings = _merge(settings, {k: v for k, v in source.items() if k in SETTINGS})
    return Config(root=root, data=settings, path=path, layers=layers)
