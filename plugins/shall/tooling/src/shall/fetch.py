"""Resolve `extends:` to a local folder: a path, or a pinned git ref fetched into a cache.

    extends:
      repo: your-org/engineering-standards   # GitHub owner/name (or `url:` for any git remote)
      ref: v2026.09                         # tag or commit sha; a branch is cached until `shall fetch --update`

    extends:
      path: ../engineering-standards        # a local checkout (monorepo, development)

Cache: $SHALL_CACHE_DIR or ~/.cache/shall/<owner>__<name>@<ref>/. Private repos: set
SHALL_GIT_TOKEN (sent as an HTTP header, never put in a URL or printed).
"""

from __future__ import annotations

import base64
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

RESOLVED = ".shall-resolved"
GIT_TIMEOUT = 120  # seconds per git command (a shallow fetch of the corpus)


@dataclass
class Parent:
    root: Path              # folder that holds the parent shall.yaml
    name: str               # label shown in sources, e.g. your-org/engineering-standards@v2026.09
    repo: str | None
    ref: str | None
    sha: str | None
    url_base: str | None    # https://github.com/<repo>/blob/<sha> for clickable sources


def cache_root() -> Path:
    if os.environ.get("SHALL_CACHE_DIR"):
        return Path(os.environ["SHALL_CACHE_DIR"]).expanduser()
    return Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "shall"


def parse_spec(spec) -> dict:
    """Accept a mapping, 'owner/name@ref', or a path string."""
    if isinstance(spec, dict):
        return spec
    text = str(spec)
    m = re.fullmatch(r"([\w.-]+/[\w.-]+)@([\w./-]+)", text)
    return {"repo": m.group(1), "ref": m.group(2)} if m else {"path": text}


def _git(args: list[str], cwd: Path, url: str | None = None) -> str:
    cmd = ["git", "-c", "advice.detachedHead=false"]
    token = os.environ.get("SHALL_GIT_TOKEN")
    if token and url and url.startswith("https://"):
        basic = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        cmd += ["-c", f"http.extraHeader=Authorization: Basic {basic}"]
    try:
        proc = subprocess.run(cmd + args, cwd=cwd, capture_output=True, text=True, timeout=GIT_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise SystemExit(f"shall: git {args[0]} timed out after {GIT_TIMEOUT}s")
    if proc.returncode != 0:
        raise SystemExit(f"shall: git {args[0]} failed: {proc.stderr.strip()[-400:]}")
    return proc.stdout.strip()


def _fetch(url: str, ref: str, dest: Path) -> str:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=".fetch-", dir=dest.parent))
    try:
        _git(["init", "-q"], tmp)
        _git(["fetch", "-q", "--depth", "1", url, ref], tmp, url)
        _git(["checkout", "-q", "FETCH_HEAD"], tmp)
        sha = _git(["rev-parse", "HEAD"], tmp)
        shutil.rmtree(tmp / ".git")
        (tmp / RESOLVED).write_text(sha + "\n", encoding="utf-8")
        if dest.exists():
            shutil.rmtree(dest)
        tmp.rename(dest)
        return sha
    finally:
        if tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)


def resolve_parent(spec, base: Path, update: bool = False) -> Parent:
    spec = parse_spec(spec)
    if "path" in spec:
        root = (base / spec["path"]).resolve()
        if not root.is_dir():
            raise SystemExit(f"shall: extends.path {root} does not exist")
        sha = None
        if (root / ".git").exists():
            proc = subprocess.run(["git", "rev-parse", "--verify", "-q", "HEAD"], cwd=root,
                                  capture_output=True, text=True, timeout=GIT_TIMEOUT)
            sha = proc.stdout.strip() if proc.returncode == 0 else None
        return Parent(root=root, name=spec.get("name") or root.name, repo=None, ref=None, sha=sha, url_base=None)
    repo, ref = spec.get("repo"), spec.get("ref")
    if not repo or not ref:
        raise SystemExit("shall: extends needs `repo` and `ref` (a tag or commit sha), or `path`")
    url = spec.get("url") or f"https://github.com/{repo}.git"
    dest = cache_root() / f"{repo.replace('/', '__')}@{re.sub(r'[^A-Za-z0-9._-]', '_', ref)}"
    marker = dest / RESOLVED
    sha = marker.read_text(encoding="utf-8").strip() if marker.is_file() and not update else _fetch(url, ref, dest)
    url_base = f"https://github.com/{repo}/blob/{sha}" if url.startswith("https://github.com/") else None
    return Parent(root=dest, name=f"{repo}@{ref}", repo=repo, ref=ref, sha=sha, url_base=url_base)
