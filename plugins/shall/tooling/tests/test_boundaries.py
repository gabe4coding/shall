"""Architecture rules that types and import-linter cannot express. Each failure message says what
is wrong, what to use instead, where a good example is, and why (the JTOOL statement).

Layers checked elsewhere: `make typecheck` (pyright: Literal types, exhaustive match) and
`make lint-imports` (import-linter: deterministic modules never import a model module).
"""

import argparse
import ast
import re
import subprocess
import sys
import typing
from pathlib import Path

import pytest

from shall import cli
from shall.claude import ISOLATION_FLAGS, claude_command
from shall.config import DEFAULTS, load_config, unknown_keys
from shall.findings import FINDINGS_SCHEMA, RawFinding

SRC = Path(cli.__file__).resolve().parent
PLUGIN = SRC.parents[2]
REPO = PLUGIN.parents[1]

# module -> the one program it may start (and why only there)
PROCESS_OWNERS = {"git.py": "git", "claude.py": "claude", "publish.py": "gh", "hooks.py": "shall (Stop review)"}
DETERMINISTIC_CMDS = ("lint", "build", "new", "show", "list", "catalog", "init", "validate", "bundle", "publish")


def sources() -> dict[str, str]:
    return {p.name: p.read_text(encoding="utf-8") for p in sorted(SRC.glob("*.py"))}


# ---------------------------------------------------------------- one owner per external program

def process_starts(text: str) -> list[int]:
    tree = ast.parse(text)
    lines = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in node.names] + ([node.module] if isinstance(node, ast.ImportFrom) else [])
            if any(n and n.split(".")[0] == "subprocess" for n in names):
                lines.append(node.lineno)
        elif isinstance(node, ast.Attribute) and node.attr in ("create_subprocess_exec", "create_subprocess_shell",
                                                                 "system", "popen", "Popen", "spawnv"):
            lines.append(node.lineno)
    return lines


def test_only_owner_modules_start_processes():
    bad = [f"{name}:{n}" for name, text in sources().items() if name not in PROCESS_OWNERS
           for n in process_starts(text)]
    assert not bad, (f"process started outside its owner module: {bad}. Use shall.git.run/git (git), "
                     "shall.claude.run_claude/run_claude_text (claude) or shall.publish (gh); see "
                     "plugins/shall/tooling/src/shall/git.py. Why: one place sets the timeout, the "
                     "tool-less flags and the error handling (JTOOL-0002.1, JTOOL-0003.1).")


def test_process_check_catches_a_bad_snippet():
    assert process_starts("import subprocess\nsubprocess.run(['git', 'status'])\n") == [1]
    assert process_starts("import asyncio\nasyncio.create_subprocess_exec('claude')\n") == [2]
    assert process_starts("from . import git\ngit.git('.', 'status')\n") == []


def test_findings_are_built_only_by_validation():
    bad = [f"{name}:{node.lineno}" for name, text in sources().items() if name != "findings.py"
           for node in ast.walk(ast.parse(text))
           if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "Finding"]
    assert not bad, (f"Finding(...) built outside findings.py: {bad}. Agent output is a RawFinding: "
                     "pass it to shall.findings.validate_findings; read a findings.json with "
                     "Finding.from_json. Why: severity comes from the corpus, never from an agent "
                     "(JTOOL-0002.2, JTOOL-0002.5).")


def test_findings_schema_matches_raw_finding():
    schema_keys = set(FINDINGS_SCHEMA["properties"]["findings"]["items"]["properties"])
    typed_keys = set(typing.get_type_hints(RawFinding)) - {"chunk"}   # chunk: added by code
    assert schema_keys == typed_keys, ("FINDINGS_SCHEMA and RawFinding (plugins/shall/tooling/src/shall/"
                                       "findings.py) differ: change both. Why: the schema is what the "
                                       "agent returns, RawFinding is how code reads it.")


def test_every_claude_call_is_tool_less():
    cfg = type("Cfg", (), {"get": lambda self, key: ["claude", "-p"]})()
    for schema in (None, {"type": "object"}):
        cmd = claude_command(cfg, "m", "system", schema)  # type: ignore[arg-type]
        tail = cmd[len(cmd) - len(ISOLATION_FLAGS):]
        assert tuple(tail) == ISOLATION_FLAGS, ("claude_command must end with ISOLATION_FLAGS "
                                                "(plugins/shall/tooling/src/shall/claude.py). Why: a "
                                                "pipeline agent has no tools (JTOOL-0002.1).")


# ---------------------------------------------------------------- CLI: exit codes, model-free commands

def test_every_command_returns_an_exit_code():
    bad = [name for name, fn in vars(cli).items() if name.startswith("cmd_")
           and typing.get_type_hints(fn).get("return") is not cli.ExitCode]
    assert not bad, (f"{bad} must be annotated `-> ExitCode` and return ExitCode.OK/ERROR/BLOCKING/SERVICE "
                     "(plugins/shall/tooling/src/shall/cli.py). Why: CI and hooks read 0/1/2/3 only "
                     "(JTOOL-0003.1).")


def test_usage_error_exits_1_not_2():
    # argparse exits 2 on a usage error, and 2 means "blocking findings" to CI (JTOOL-0003.1)
    with pytest.raises(SystemExit) as err:
        cli.main(["review", "--no-such-flag"])
    assert err.value.code == cli.ExitCode.ERROR


def test_scripts_exit_with_shall_codes_only():
    bad = []
    for script in (PLUGIN / "bin").iterdir():
        for n, line in enumerate(script.read_text(encoding="utf-8").splitlines(), 1):
            bad += [f"{script.name}:{n}: exit {c}" for c in re.findall(r"\bexit\s+(\d+)", line) if int(c) > 3]
    assert not bad, (f"{bad}: plugins/shall/bin scripts exit 0 (ok), 1 (error), 2 (blocking) or 3 "
                     "(service failed); see plugins/shall/bin/shall-pr-review. Why: JTOOL-0003.1.")


def _local_imports(fn: ast.FunctionDef, funcs: dict[str, ast.FunctionDef], seen: set[str]) -> set[str]:
    """Modules imported inside `fn` and inside the cli helpers it calls."""
    out: set[str] = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module:
            out.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in funcs \
                and node.func.id not in seen:
            seen.add(node.func.id)
            out |= _local_imports(funcs[node.func.id], funcs, seen)
    return out


def model_modules() -> set[str]:
    """shall.jev, shall.claude and every module that imports them, directly or not."""
    imports = {}
    for name, text in sources().items():
        mods = set()
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.ImportFrom) and node.level == 1:
                mods |= {node.module.split(".")[0]} if node.module else {a.name for a in node.names}
        imports[name.removesuffix(".py")] = mods
    found = {"jev", "claude"}
    while grown := {m for m, deps in imports.items() if deps & found} - found:
        found |= grown
    return found


def model_imports_of(cmd: str, text: str) -> set[str]:
    tree = ast.parse(text)
    funcs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    return _local_imports(funcs[f"cmd_{cmd}"], funcs, {f"cmd_{cmd}"}) & model_modules()


def test_deterministic_commands_reach_no_model_module():
    text = (SRC / "cli.py").read_text(encoding="utf-8")
    bad = {cmd: sorted(mods) for cmd in DETERMINISTIC_CMDS if (mods := model_imports_of(cmd, text))}
    assert not bad, (f"deterministic commands import model modules: {bad}. Move the model step to "
                     "its own command (see cmd_validate vs cmd_review in cli.py). Why: these "
                     "commands run in CI without keys (JTOOL-0003.2).")


def test_model_import_check_catches_a_bad_snippet():
    bad = "def cmd_lint(args, cfg):\n    return helper()\n\ndef helper():\n    from .select import Selector\n"
    assert model_imports_of("lint", bad) == {"select"}  # select imports jev
    assert {"select", "review", "verify", "hooks", "scan"} <= model_modules()
    assert not {"corpus", "config", "findings", "git"} & model_modules()


@pytest.mark.parametrize("cmd", [["list"], ["lint"], ["show", "JRFC-0001"]])
def test_deterministic_commands_do_not_load_the_sdk(cmd):
    """The lazy imports hold at run time too: no shall.jev, so no TypeSafe SDK (~190 ms) to load."""
    code = ("import sys\nfrom shall import cli\ntry:\n    cli.main(sys.argv[1:])\nexcept SystemExit:\n    pass\n"
            "print('LOADED' if 'shall.jev' in sys.modules else 'CLEAN', file=sys.stderr)")
    proc = subprocess.run([sys.executable, "-c", code, "--config", str(REPO / "shall.yaml"), *cmd],
                          capture_output=True, text=True, cwd=REPO)
    assert proc.stderr.strip().endswith("CLEAN"), proc.stderr[-500:]


# ---------------------------------------------------------------- config: models, keys

MOVING = re.compile(r"^(sonnet|opus|haiku|claude|jev)$|-(latest|preview)$")


def model_values(node=DEFAULTS, path=""):
    for key, value in node.items():
        if isinstance(value, dict):
            yield from model_values(value, f"{path}{key}.")
        elif key.endswith("model") and isinstance(value, str):
            yield f"{path}{key}", value


def test_default_models_are_pinned_and_defined_once():
    for path, value in model_values():
        assert not MOVING.search(value), f"{path}: {value} is a moving alias; pin a version (JTOOL-0001.4)"
    literals =[(name, m) for name, text in sources().items() if name != "config.py"
                for m in re.findall(r"""["']((?:claude|jev)-[a-z]+-[\w.-]+|jev-\d[\w.]*)["']""", text)]
    assert not literals, (f"model ids hard-coded outside DEFAULTS: {literals}. Read them with "
                          "cfg.get('review.model') etc. (plugins/shall/tooling/src/shall/config.py). Why: "
                          "one pinned value per setting (JTOOL-0001.4).")


def test_agent_models_are_pinned_to_the_review_model():
    """The in-session agents use the model that CI uses (review.model), not a moving alias."""
    review_model = DEFAULTS["review"]["model"]
    bad = {}
    for path in sorted((PLUGIN / "agents").glob("*.md")):
        m = re.search(r"^model:\s*(\S+)", path.read_text(encoding="utf-8").split("---", 2)[1], re.M)
        if m and m.group(1) != review_model:
            bad[path.name] = m.group(1)
    assert not bad, (f"agent model differs from review.model ({review_model}): {bad}. Set `model: "
                     f"{review_model}` in the frontmatter. Why: the in-session review must match CI (JTOOL-0001.4).")


@pytest.mark.parametrize("value,moving", [("sonnet", True), ("jev-latest", True), ("claude-sonnet-5", False),
                                          ("jev-1.13.0", False)])
def test_moving_alias_pattern(value, moving):
    assert bool(MOVING.search(value)) is moving


def config_paths_read(text: str) -> list[tuple[int, str]]:
    return [(n, m) for n, line in enumerate(text.splitlines(), 1)
            for m in re.findall(r"""\bcfg\.get\(\s*["']([a-z_]+\.[a-z_.]+)["']""", line)]


def test_every_setting_read_has_a_default():
    bad = [f"{name}:{n}: {path}" for name, text in sources().items() for n, path in config_paths_read(text)
           if unknown_keys(_nested(path))]
    assert not bad, (f"settings read but missing from DEFAULTS: {bad}. Add each with its default and a "
                     "comment to DEFAULTS in plugins/shall/tooling/src/shall/config.py. Why: DEFAULTS is "
                     "the list of keys shall.yaml may set; an unknown key fails at load.")


def _nested(path: str) -> dict:
    out: dict = {}
    node = out
    *parents, last = path.split(".")
    for part in parents:
        node = node.setdefault(part, {})
    node[last] = 0
    return out


@pytest.mark.parametrize("yaml_text,error", [
    ("review:\n  modle: x\n", "unknown key(s): review.modle"),
    ("hooks:\n  actions:\n    enforced:\n      MUST: [[0.9, block]]\n", "action one of log, warn, ask, deny"),
    ("hooks:\n  actions:\n    enforced: [[0.9, deny]]\n", "hooks.actions.enforced = [[0.9, 'deny']]"),
])
def test_bad_config_fails_at_load(tmp_path, monkeypatch, yaml_text, error):
    monkeypatch.setenv("SHALL_CONFIG", "")  # load_config sets it; monkeypatch restores it
    (tmp_path / "shall.yaml").write_text(yaml_text)
    with pytest.raises(SystemExit, match=re.escape(error)):
        load_config(str(tmp_path / "shall.yaml"))
    (tmp_path / "shall.yaml").write_text("hooks:\n  actions:\n    draft:\n      MUST: [[0.9, deny]]\n")
    assert load_config(str(tmp_path / "shall.yaml")).get("hooks.actions.draft.MUST") == [[0.9, "deny"]]


def rfc_with_a_typo_in_status(tmp_path, issues: list):
    from shall.corpus import parse_rfc
    rfc_file = tmp_path / "JRFC-0001-x.md"
    rfc_file.write_text("---\nid: JRFC-0001\nstatus: enforcd\ndomain: d\ntitle: X\n---\n"
                        "### JRFC-0001.1 X\nCode MUST do x.\n")
    return parse_rfc(rfc_file, tmp_path, issues)


def test_invalid_rfc_status_is_an_error_and_never_active(tmp_path):
    issues: list = []
    rfc = rfc_with_a_typo_in_status(tmp_path, issues)
    assert rfc is not None and rfc.status is None   # in no include_status, no hooks.actions table
    assert any(i.code == "status" for i in issues)


def test_list_shows_an_rfc_with_an_invalid_status(tmp_path, monkeypatch, capsys):
    from types import SimpleNamespace

    rfc = rfc_with_a_typo_in_status(tmp_path, [])
    monkeypatch.setattr(cli, "load_corpus", lambda cfg: SimpleNamespace(rfcs={"JRFC-0001": rfc}))
    args = argparse.Namespace(domain=None, status=None)
    assert cli.cmd_list(args, None) == cli.ExitCode.OK
    assert "invalid" in capsys.readouterr().out


def test_unknown_config_keys_are_reported():
    assert unknown_keys({"review": {"model": "m", "modle": "m"}, "reveiw": {}}) == ["review.modle", "reveiw"]
    assert unknown_keys({"extends": "org/x@v1", "prefix": "BOOK", "hooks": {"actions": {"draft": {}}}}) == []


# ---------------------------------------------------------------- docs and skills name real commands

CODE_RE = re.compile(r"```[^\n]*\n(.*?)```|`([^`\n]+)`", re.S)
SHALL_CMD_RE = re.compile(r"(?:^|[\s|;&])(?:\S*/)?shall(?:[ \t]+--config[ \t]+\S+)?[ \t]+([a-z][a-z-]+)([^\n|;&]*)",
                          re.M)


def documented_commands(text: str):
    for m in CODE_RE.finditer(text):
        code = m.group(1) or m.group(2)
        for c in SHALL_CMD_RE.finditer(code):
            yield c.group(1), re.findall(r"(?<![\w-])(--[a-z][a-z-]*)", c.group(2))


def test_docs_and_skills_use_existing_commands_and_flags():
    parser = cli.build_parser()
    sub = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    flags = {name: {o for a in sp._actions for o in a.option_strings} | {"--config"}
             for name, sp in sub.choices.items()}
    files = [*(PLUGIN / "skills").rglob("*.md"), *(PLUGIN / "agents").glob("*.md"),
             *(REPO / "docs").glob("*.mdx"), REPO / "README.md"]
    bad = []
    for f in files:
        for cmd, used in documented_commands(f.read_text(encoding="utf-8")):
            if cmd not in flags:
                bad.append(f"{f.relative_to(REPO)}: shall {cmd}")
            else:
                bad += [f"{f.relative_to(REPO)}: shall {cmd} {flag}" for flag in used if flag not in flags[cmd]]
    assert not bad, (f"docs or skills name commands or flags the CLI does not have: {sorted(set(bad))}. "
                     "Fix the text, or add the flag in build_parser (plugins/shall/tooling/src/shall/cli.py). "
                     "Why: an agent runs what a skill says (JTOOL-0004.3).")


def test_command_check_reads_code_only():
    assert list(documented_commands("Run `shall lint --strict` here.")) == [("lint", ["--strict"])]
    assert list(documented_commands("shall review is a tool.")) == []
    assert list(documented_commands("```\ncd plugins/shall\nmake test\n```")) == []
