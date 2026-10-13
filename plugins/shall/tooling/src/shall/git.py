"""The only module that runs `git`. Every call has a timeout and none raises on a git failure.

Other modules call `run` (needs the exit code or stderr) or `git` (stdout or None).
tests/test_boundaries.py fails when another module starts a `git` process itself.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

TIMEOUT = 30  # seconds; a slow `git grep` on a large repository must not hang a hook or a review


@dataclass(frozen=True)
class GitResult:
    code: int | None  # None: git is not installed or timed out
    out: str
    err: str

    @property
    def ok(self) -> bool:
        return self.code == 0


def run(cwd: str | Path, *args: str, options: tuple[str, ...] = (), timeout: float = TIMEOUT) -> GitResult:
    """`git <options> -C <cwd> <args>`. Output is decoded with surrogateescape: a path with
    bytes that are not UTF-8 survives a round trip."""
    try:
        proc = subprocess.run(["git", *options, "-C", str(cwd), *args], capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return GitResult(None, "", f"timed out after {timeout:g}s")
    except OSError as err:
        return GitResult(None, "", str(err))
    return GitResult(proc.returncode, proc.stdout.decode("utf-8", "surrogateescape"),
                     proc.stderr.decode("utf-8", "replace"))


def git(cwd: str | Path, *args: str, ok: tuple[int, ...] = (0,), timeout: float = TIMEOUT) -> str | None:
    """stdout, or None when git fails, is missing, times out or exits with a code not in `ok`."""
    r = run(cwd, *args, timeout=timeout)
    return r.out if r.code is not None and r.code in ok else None


def init(path: Path) -> None:
    """`git init` for a fixture copy (the code graph and the evidence search use `git grep`)."""
    r = run(path, "init", "-q")
    if not r.ok:
        raise RuntimeError(f"git init {path} failed: {r.err.strip()[-300:]}")


def toplevel(start: str | Path, timeout: float = TIMEOUT) -> Path | None:
    top = (git(start, "rev-parse", "--show-toplevel", timeout=timeout) or "").strip()
    return Path(top) if top else None
