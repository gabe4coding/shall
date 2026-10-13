"""Scan-eval checkout resolution. The private repo keeps its url and path out of cases.yaml."""

import importlib.util
import os
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[4]


def load_run():
    path = REPO / "eval/scan/run.py"
    spec = importlib.util.spec_from_file_location("scan_eval_run", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def run():
    return load_run()


def test_committed_private_repo_has_no_url_or_name(run, monkeypatch):
    monkeypatch.setattr(run, "LOCAL_REPOS", REPO / "eval/scan/no-such-local.yaml")
    monkeypatch.delenv("SHALL_SCAN_URL_PRIVATE_PY", raising=False)
    monkeypatch.delenv("SHALL_SCAN_CHECKOUT_PRIVATE_PY", raising=False)
    text = run.CASES.read_text(encoding="utf-8")
    inputs = (REPO / "eval/scan/inputs.md").read_text(encoding="utf-8")
    assert "embedded third-party data; must not go to TypeSafe" in text
    assert "embedded third-party data; must not go to TypeSafe" in inputs
    assert "## private-py @" in inputs
    repos, cases = run.load_cases(None)
    assert set(repos) == {"private-py", "plainwright"}
    assert "url" not in repos["private-py"]
    assert "checkout" not in repos["private-py"]
    assert repos["private-py"]["sha"].startswith("fc89f0d")
    assert run.checkout_of("private-py", repos["private-py"]) == os.path.expanduser("~/Repositories/private-py")
    private = [c for c in cases if c["repo"] == "private-py"]
    assert len(private) == 39
    assert all("private-py" in c["tags"] for c in private)


def test_yaml_checkout_remains_when_env_is_unset(run, monkeypatch):
    monkeypatch.delenv("SHALL_SCAN_CHECKOUT_PLAINWRIGHT", raising=False)
    repos, _ = run.load_cases(None)
    assert repos["plainwright"]["checkout"] == "~/Repositories/plainwright"
    assert run.checkout_of("plainwright", repos["plainwright"]) == os.path.expanduser("~/Repositories/plainwright")


def test_env_overrides_checkout(run, monkeypatch, tmp_path):
    monkeypatch.setenv("SHALL_SCAN_CHECKOUT_PRIVATE_PY", str(tmp_path))
    repos, _ = run.load_cases(None)
    assert repos["private-py"]["checkout"] == str(tmp_path)
    assert run.checkout_of("private-py", repos["private-py"]) == str(tmp_path)


def test_local_file_then_env(run, monkeypatch, tmp_path):
    local = tmp_path / "repos.local.yaml"
    local.write_text(
        "repos:\n  private-py:\n    sha: deadbeef\n    checkout: /from-file\n"
        "    url: git@example.com:org/private.git\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(run, "LOCAL_REPOS", local)
    monkeypatch.delenv("SHALL_SCAN_CHECKOUT_PRIVATE_PY", raising=False)
    repos, _ = run.load_cases(None)
    assert repos["private-py"]["checkout"] == "/from-file"
    assert repos["private-py"]["url"] == "git@example.com:org/private.git"
    assert repos["private-py"]["sha"].startswith("fc89f0d")  # a local file must not retarget the sha
    monkeypatch.setenv("SHALL_SCAN_CHECKOUT_PRIVATE_PY", "/from-env")
    repos, _ = run.load_cases(None)
    assert repos["private-py"]["checkout"] == "/from-env"


def test_missing_checkout_names_key_and_path(run):
    expected = os.path.expanduser("~/Repositories/private-py")
    if os.path.isdir(expected):
        pytest.skip("a clone is already at the default checkout")
    with pytest.raises(SystemExit) as exc:
        run.read_file({"private-py": {"sha": "abc"}}, {"repo": "private-py", "path": "a.py"})
    msg = exc.value.code
    assert isinstance(msg, str)
    assert "checkout for private-py is not at" in msg
    assert expected in msg
    assert "SHALL_SCAN_CHECKOUT_PRIVATE_PY" in msg


def test_read_file_shows_the_pinned_blob(run, tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "scan-eval@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "scan-eval"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=tmp_path, check=True)
    (tmp_path / "a.py").write_text("print(1)\n", encoding="utf-8")
    subprocess.run(["git", "add", "a.py"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "add"], cwd=tmp_path, check=True)
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=tmp_path, text=True).strip()
    text = run.read_file({"demo": {"sha": sha, "checkout": str(tmp_path)}}, {"repo": "demo", "path": "a.py"})
    assert text == "print(1)\n"


def test_git_show_failure_names_the_repo(run, tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    with pytest.raises(SystemExit) as exc:
        run.read_file({"demo": {"sha": "deadbeef", "checkout": str(tmp_path)}},
                      {"repo": "demo", "path": "missing.py"})
    msg = exc.value.code
    assert "demo" in msg
    assert "missing.py" in msg
    assert str(tmp_path) in msg
