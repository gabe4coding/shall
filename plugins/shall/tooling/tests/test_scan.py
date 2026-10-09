"""`shall scan`: file listing, secret scanner, Jev warnings, redaction, skips, failures (no network)."""

import asyncio
import copy
import subprocess
from pathlib import Path

import pytest

from shall.config import load_config
from shall.corpus import load_corpus
from shall.scan import excluded, list_files, render_lines, render_markdown, run_scan

REPO = Path(__file__).resolve().parents[4]
TOKEN = "ghp_8fK2mQ9xLpR4tV7wZ1aB3cD5eF6gH0iJ2kL4"


@pytest.fixture(scope="module")
def org():
    mp = pytest.MonkeyPatch()
    mp.setenv("SHALL_CONFIG", str(REPO / "shall.yaml"))
    cfg = load_config(str(REPO / "shall.yaml"))
    yield cfg, load_corpus(cfg)
    mp.undo()


class FakeJev:
    """p per question id from a table (or per file: {path: table}); `#applies` answers 0.95,
    violations 0.02 by default."""

    def __init__(self, table=None, fail=None, per_file=None):
        self.table, self.fail, self.per_file = table or {}, fail, per_file or {}
        self.usage = {"requests": 0, "cached": 0, "input_tokens": 0}
        self.states = []

    def available(self):
        return True

    async def ask(self, state, questions):
        if self.fail:
            raise self.fail
        self.usage["requests"] += 1
        self.usage["input_tokens"] += 1000
        self.states.append(state)
        table = {**self.table, **self.per_file.get(state.get("file"), {})}
        return {q: {"p": table.get(q, 0.95 if q.endswith("#applies") else 0.02)} for q in questions}


def write(root: Path, files: dict[str, str]) -> None:
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")


def git_repo(root: Path, files: dict[str, str]) -> Path:
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    write(root, files)
    return root


def scan(org, jev, root, paths=(".",), **kw):
    cfg, corpus = org
    cfg = copy.copy(cfg)
    cfg.data = copy.deepcopy(cfg.data)
    for k, v in kw.pop("settings", {}).items():
        cfg.data["scan"][k] = v
    return asyncio.run(run_scan(cfg, corpus, jev, [str(root / p) for p in paths], root=root, **kw))


FILES = {
    "src/client.py": "import requests\n\n\ndef fetch(url: str) -> bytes:\n    return requests.get(url).content\n",
    "src/keys.py": f"# service settings\nGITHUB = \"{TOKEN}\"\n",
    "src/ok.py": "def add(a: int, b: int) -> int:\n    return a + b\n",
    "node_modules/lib/index.js": "module.exports = 1\n",
    "README.md": "# docs are for shall review\n",
    "notes.txt": "not a known language\n",
    ".gitignore": "ignored.py\n",
    "ignored.py": "x = 1\n",
}


def test_warns_blocks_redacts_and_skips(org, tmp_path):
    root = git_repo(tmp_path / "repo", {**FILES, "big.py": "x = 1\n" * 50})
    jev = FakeJev(per_file={"src/client.py": {"JRFC-0006.1": 0.86}})
    report = scan(org, jev, root, settings={"max_file_chars": 200})
    by_path = {f["path"]: f for f in report["files"]}
    # listing: git (untracked included, .gitignore respected), known languages, no docs, excludes
    assert sorted(by_path) == ["src/client.py", "src/keys.py", "src/ok.py"]
    assert [s["path"] for s in report["skipped"]] == ["big.py"] and "max_file_chars" in report["skipped"][0]["reason"]
    # Jev warning at p >= threshold, never blocking
    client = {f["id"]: f for f in by_path["src/client.py"]["findings"]}
    assert client["JRFC-0006.1"]["p"] == 0.86 and client["JRFC-0006.1"]["blocking"] is False
    # secret scanner: exact, with the line, blocking on an enforced MUST; the token never reaches Jev
    keys = [f for f in by_path["src/keys.py"]["findings"] if f["by"] == "scanner"]
    assert keys and keys[0]["id"] == "JRFC-0004.1" and keys[0]["lines"] == "2" and keys[0]["blocking"]
    assert all(TOKEN not in str(s) for s in jev.states)
    assert by_path["src/ok.py"]["findings"] == [] and by_path["src/ok.py"]["candidates"] > 0
    s = report["summary"]
    assert (s["scanned"], s["warnings"], s["blocking"], s["files_with_warnings"], s["jev_requests"]) == (3, 2, 1, 2, 3)
    assert report["errors"] == []
    md, lines = render_markdown(report), render_lines(report)
    assert "## src/client.py" in md and "## Skipped" in md and "big.py" in md
    assert "src/keys.py:2: JRFC-0004.1 [MUST, secret] BLOCKING No secrets in source" in lines


def test_threshold_and_statuses(org, tmp_path):
    root = git_repo(tmp_path / "repo", {"src/client.py": FILES["src/client.py"]})
    assert scan(org, FakeJev({"JRFC-0006.1": 0.69}), root)["summary"]["warnings"] == 0
    assert scan(org, FakeJev({"JRFC-0006.1": 0.69}), root, threshold=0.6)["summary"]["warnings"] == 1
    # default statuses (approved, enforced) skip drafts; JRFC-0011 (python typing) is a draft
    untyped = git_repo(tmp_path / "repo2", {"a.py": "def f(x):\n    return x\n"})
    assert "JRFC-0011.1" not in scan(org, FakeJev(), untyped)["files"][0]["scores"]
    assert "JRFC-0011.1" in scan(org, FakeJev(), untyped, statuses=["draft", "approved", "enforced"])["files"][0]["scores"]


def test_jev_failure_is_reported_not_hidden(org, tmp_path):
    root = git_repo(tmp_path / "repo", {"src/client.py": FILES["src/client.py"]})
    report = scan(org, FakeJev(fail=RuntimeError("503")), root)
    assert report["errors"] and report["errors"][0]["path"] == "src/client.py"
    assert "Not checked (Jev failed)" in render_markdown(report)


def test_paths_and_walk_outside_git(org, tmp_path):
    root = tmp_path / "plain"
    write(root, {"a/x.py": "x = 1\n", "b/y.ts": "export const y = 1\n", ".hidden/z.py": "z = 1\n"})
    assert list_files(root, [str(root)], []) == ["a/x.py", "b/y.ts"]
    assert list_files(root, [str(root / "a")], []) == ["a/x.py"]
    assert list_files(root, [str(root)], ["b/*"]) == ["a/x.py"]
    with pytest.raises(SystemExit):
        list_files(root, [str(tmp_path)], [])


def test_exclude_globs_match_top_level_folders():
    pats = ["*/node_modules/*", "*.min.js"]
    assert excluded("node_modules/a.js", pats) and excluded("web/node_modules/a.js", pats)
    assert excluded("static/app.min.js", pats) and not excluded("src/app.js", pats)
