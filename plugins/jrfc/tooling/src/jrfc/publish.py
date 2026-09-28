"""Publish a jrfc review to a GitHub PR idempotently. Deterministic: no model calls.

Each run on a PR:
  - posts inline comments only for findings whose key has no thread yet (one review);
  - resolves open jrfc threads whose line no longer exists in the PR diff (fixed);
  - reopens threads that jrfc resolved earlier when the finding comes back;
  - leaves threads resolved by a person alone and records them as dismissed (feedback);
  - keeps one summary comment per PR, updated in place.

A finding that is still in the diff but that the agent did not report this time is left
open: only a change of the line itself closes a thread, so model variance cannot flap it.
All GitHub access goes through `gh`, so auth is whatever `gh` uses (GH_TOKEN in CI).
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from typing import Callable

from .review import MARKER_RE, SUMMARY_MARKER

Runner = Callable[[list[str], str | None], str]

THREADS_QUERY = """
query($owner: String!, $name: String!, $number: Int!, $endCursor: String) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      reviewThreads(first: 100, after: $endCursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          isResolved
          resolvedBy { login }
          path
          comments(first: 1) { nodes { body author { login } } }
        }
      }
    }
  }
}
"""
RESOLVE = "mutation($id: ID!) { resolveReviewThread(input: {threadId: $id}) { thread { id } } }"
UNRESOLVE = "mutation($id: ID!) { unresolveReviewThread(input: {threadId: $id}) { thread { id } } }"


GH_TIMEOUT = 60  # seconds per gh call; the job timeout is the outer bound


def gh_runner(args: list[str], stdin: str | None) -> str:
    try:
        proc = subprocess.run(["gh", *args], input=stdin, capture_output=True, text=True, timeout=GH_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise SystemExit(f"jrfc publish: gh {' '.join(args[:3])} timed out after {GH_TIMEOUT}s")
    if proc.returncode != 0:
        raise SystemExit(f"jrfc publish: gh {' '.join(args[:3])} failed: {proc.stderr.strip()[-500:]}")
    return proc.stdout


@dataclass
class Thread:
    id: str
    key: str
    line_hash: str
    path: str
    resolved: bool
    resolved_by: str | None
    author: str | None


@dataclass
class Plan:
    new: list[dict] = field(default_factory=list)          # comments to post
    kept: list[str] = field(default_factory=list)          # keys already open on the PR
    resolve: list[Thread] = field(default_factory=list)    # line gone from the diff
    unresolve: list[Thread] = field(default_factory=list)  # jrfc resolved it, finding is back
    dismissed: list[Thread] = field(default_factory=list)  # a person resolved it, finding is back
    summary_comment_id: int | None = None

    def to_json(self) -> dict:
        return {
            "new": [{"key": c["jrfc_key"], "path": c["path"], "line": c["line"]} for c in self.new],
            "kept": self.kept,
            "resolve": [{"thread": t.id, "key": t.key, "path": t.path} for t in self.resolve],
            "unresolve": [{"thread": t.id, "key": t.key, "path": t.path} for t in self.unresolve],
            "dismissed": [{"thread": t.id, "key": t.key, "path": t.path, "by": t.resolved_by}
                          for t in self.dismissed],
            "summary": "update" if self.summary_comment_id else "create",
        }


class GitHub:
    def __init__(self, repo: str, pr: int, runner: Runner = gh_runner):
        self.owner, self.name = repo.split("/", 1)
        self.repo, self.pr, self.run = repo, pr, runner

    def api(self, args: list[str], payload: dict | None = None) -> str:
        return self.run(["api", *args] + (["--input", "-"] if payload is not None else []),
                        json.dumps(payload) if payload is not None else None)

    def threads(self) -> list[Thread]:
        out, cursor = [], None
        while True:
            args = ["graphql", "-f", f"query={THREADS_QUERY}", "-F", f"owner={self.owner}",
                    "-F", f"name={self.name}", "-F", f"number={self.pr}"]
            if cursor:
                args += ["-f", f"endCursor={cursor}"]
            page = json.loads(self.api(args))["data"]["repository"]["pullRequest"]["reviewThreads"]
            for node in page["nodes"]:
                first = (node["comments"]["nodes"] or [{}])[0]
                m = MARKER_RE.search(first.get("body") or "")
                if not m:
                    continue  # not a jrfc thread
                out.append(Thread(
                    id=node["id"], key=m.group(1), line_hash=m.group(2), path=node.get("path") or "",
                    resolved=node["isResolved"],
                    resolved_by=(node.get("resolvedBy") or {}).get("login"),
                    author=(first.get("author") or {}).get("login"),
                ))
            if not page["pageInfo"]["hasNextPage"]:
                return out
            cursor = page["pageInfo"]["endCursor"]

    def summary_comment_id(self) -> int | None:
        out = self.api(["--paginate", f"repos/{self.repo}/issues/{self.pr}/comments",
                        "--jq", f'.[] | select(.body | contains("{SUMMARY_MARKER}")) | .id'])
        ids = [int(x) for x in out.split()]
        return ids[0] if ids else None


def make_plan(review: dict, threads: list[Thread], summary_id: int | None) -> Plan:
    plan = Plan(summary_comment_id=summary_id)
    current = {c["jrfc_key"]: c for c in review["comments"]}
    added = {p: set(h) for p, h in review["jrfc"]["added_line_hashes"].items()}
    by_key: dict[str, Thread] = {}
    for t in threads:
        by_key.setdefault(t.key, t)
    for key, comment in current.items():
        t = by_key.get(key)
        if t is None:
            plan.new.append(comment)
        elif not t.resolved:
            plan.kept.append(key)
        elif t.resolved_by and t.resolved_by == t.author:
            plan.unresolve.append(t)       # jrfc closed it as fixed, but it is back
        else:
            plan.dismissed.append(t)       # a person resolved it: respect that, record it
    for t in threads:
        if t.key in current or t.resolved:
            continue
        if t.line_hash not in added.get(t.path, set()):
            plan.resolve.append(t)         # the commented line is no longer in the PR diff
    return plan


def summary_body(review: dict, plan: Plan) -> str:
    status = (f"new {len(plan.new)} · still open {len(plan.kept) + len(plan.unresolve)} · "
              f"fixed {len(plan.resolve)} · dismissed by reviewers {len(plan.dismissed)}")
    return f"{SUMMARY_MARKER}\n{review['jrfc']['summary']}\n<sub>jrfc: {status}</sub>\n"


def execute(gh: GitHub, review: dict, plan: Plan) -> None:
    if plan.new:
        comments = [{k: v for k, v in c.items() if not k.startswith("jrfc_")} for c in plan.new]
        # Always COMMENT: blocking is enforced by the required check (exit code), not by a
        # bot "changes requested" review that people must dismiss by hand.
        gh.api(["--method", "POST", f"repos/{gh.repo}/pulls/{gh.pr}/reviews"], {
            "event": "COMMENT",
            "body": f"jrfc: {len(comments)} new finding(s). See the jrfc summary comment on this PR.",
            "comments": comments,
        })
    for t in plan.resolve:
        gh.api(["graphql", "-f", f"query={RESOLVE}", "-f", f"id={t.id}"])
    for t in plan.unresolve:
        gh.api(["graphql", "-f", f"query={UNRESOLVE}", "-f", f"id={t.id}"])
    body = {"body": summary_body(review, plan)}
    if plan.summary_comment_id:
        gh.api(["--method", "PATCH", f"repos/{gh.repo}/issues/comments/{plan.summary_comment_id}"], body)
    else:
        gh.api(["--method", "POST", f"repos/{gh.repo}/issues/{gh.pr}/comments"], body)


def publish(review: dict, repo: str, pr: int, dry_run: bool, runner: Runner = gh_runner) -> Plan:
    gh = GitHub(repo, pr, runner)
    plan = make_plan(review, gh.threads(), gh.summary_comment_id())
    if not dry_run:
        execute(gh, review, plan)
    return plan
