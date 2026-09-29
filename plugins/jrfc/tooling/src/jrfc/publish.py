"""Publish a jrfc review to a GitHub PR idempotently. Deterministic: no model calls.

Each run on a PR:
  - posts inline comments only for findings whose key has no thread yet (one review);
  - resolves open jrfc threads whose line no longer exists in the PR diff (fixed);
  - reopens threads that jrfc resolved earlier when the finding comes back;
  - leaves threads resolved by a person alone and records them as dismissed (feedback);
  - keeps one summary comment per PR, updated in place.

A finding that is still in the diff but that the agent did not report this time is left
open: only a change of the line itself closes a thread, so model variance cannot flap it.

With a `triage.json` (`jrfc triage`) next to the review, the summary also lists the triage of
other AI reviewers' comments, and `--resolve-noise` replies to each noise thread with the
reason and resolves it. A thread a person replied to, resolved or reopened is left alone.
All GitHub access goes through `gh`, so auth is whatever `gh` uses (GH_TOKEN in CI).
"""

from __future__ import annotations

import hashlib
import json
import re
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
# Every thread with its comments: the input of `jrfc triage` and the state `--resolve-noise`
# checks again right before it writes.
ALL_THREADS_QUERY = """
query($owner: String!, $name: String!, $number: Int!, $endCursor: String) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      reviewThreads(first: 100, after: $endCursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          isResolved
          isOutdated
          path
          line
          comments(first: 50) { nodes { databaseId body url author { __typename login } } }
        }
      }
    }
  }
}
"""
TRIAGE_MARKER_RE = re.compile(r"<!-- jrfc:triage key=([0-9a-f]+) -->")
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

    def review_threads(self) -> list[dict]:
        """Every review thread as {thread, comment_id, author, author_type, path, line, outdated,
        resolved, body, url, replies: [{author, author_type, body}]}; the first comment is the root."""
        out, cursor = [], None
        while True:
            args = ["graphql", "-f", f"query={ALL_THREADS_QUERY}", "-F", f"owner={self.owner}",
                    "-F", f"name={self.name}", "-F", f"number={self.pr}"]
            if cursor:
                args += ["-f", f"endCursor={cursor}"]
            page = json.loads(self.api(args))["data"]["repository"]["pullRequest"]["reviewThreads"]
            for node in page["nodes"]:
                comments = [{"id": c.get("databaseId"), "body": c.get("body") or "", "url": c.get("url"),
                             "author": (c.get("author") or {}).get("login") or "ghost",
                             "author_type": (c.get("author") or {}).get("__typename") or "User"}
                            for c in node["comments"]["nodes"]]
                if not comments:
                    continue
                root = comments[0]
                out.append({
                    "thread": node["id"], "comment_id": root["id"], "author": root["author"],
                    "author_type": root["author_type"], "path": node.get("path") or "",
                    "line": node.get("line"), "outdated": bool(node.get("isOutdated")),
                    "resolved": bool(node["isResolved"]), "body": root["body"], "url": root["url"],
                    "replies": [{k: c[k] for k in ("author", "author_type", "body")} for c in comments[1:]],
                })
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


def summary_body(review: dict, plan: Plan, triage_md: str | None = None) -> str:
    status = (f"new {len(plan.new)} · still open {len(plan.kept) + len(plan.unresolve)} · "
              f"fixed {len(plan.resolve)} · dismissed by reviewers {len(plan.dismissed)}")
    triage = f"\n{triage_md.rstrip()}\n" if triage_md else ""
    return f"{SUMMARY_MARKER}\n{review['jrfc']['summary']}{triage}\n<sub>jrfc: {status}</sub>\n"


# ---------------------------------------------------------------- triage of other AI reviewers

JRFC_MARKERS = ("<!-- jrfc:finding", "<!-- jrfc:triage", SUMMARY_MARKER)


def login_matches(login: str, pattern: str) -> bool:
    """`*` is the only wildcard: `*[bot]` means a login ending in `[bot]` (fnmatch would read
    `[bot]` as one of b, o, t)."""
    return re.fullmatch(".*".join(re.escape(part) for part in pattern.split("*")), login) is not None


def is_bot(author: str, author_type: str | None, patterns: list[str]) -> bool:
    """A GitHub App (GraphQL type Bot, REST login `name[bot]`) or a login in `triage.authors`."""
    return author_type == "Bot" or any(login_matches(author, p) for p in patterns)


def is_jrfc(body: str) -> bool:
    return any(m in (body or "") for m in JRFC_MARKERS)


def triage_key(item: dict) -> str:
    return hashlib.sha1(f"{item.get('thread')}|{item.get('comment_id')}".encode()).hexdigest()[:16]


@dataclass
class TriagePlan:
    resolve: list[dict] = field(default_factory=list)   # noise: reply with the reason, then resolve
    human: list[dict] = field(default_factory=list)     # a person replied: left alone
    done: list[dict] = field(default_factory=list)      # resolved already, or jrfc replied before

    def to_json(self) -> dict:
        def row(i: dict) -> dict:
            return {"thread": i.get("thread"), "author": i.get("author"), "path": i.get("path"),
                    "line": i.get("line"), "reason": i.get("reason")}
        return {"resolve": [row(i) for i in self.resolve], "human": [row(i) for i in self.human],
                "done": [row(i) for i in self.done]}


def make_triage_plan(triage: dict, threads: list[dict], bot_patterns: list[str]) -> TriagePlan:
    """Noise threads to answer and resolve, from the current thread state (not the state
    `jrfc triage` read): a thread resolved, reopened or answered by a person since then is
    not touched."""
    plan = TriagePlan()
    by_id = {t["thread"]: t for t in threads}
    for item in triage["comments"]:
        if item["status"] != "noise" or not item.get("thread"):
            continue
        t = by_id.get(item["thread"])
        if t is None or not is_bot(t["author"], t.get("author_type"), bot_patterns):
            continue  # gone, or not a bot's thread: triage.json is never trusted for that
        item = {**item, "comment_id": t["comment_id"]}   # reply to the live root comment
        replies = t.get("replies", [])
        if t["resolved"] or any(TRIAGE_MARKER_RE.search(r["body"] or "") for r in replies):
            plan.done.append(item)       # handled already; if a person reopened it, that stands
        elif any(not is_bot(r["author"], r.get("author_type"), bot_patterns) and not is_jrfc(r["body"])
                 for r in replies):
            plan.human.append(item)      # a person engaged in the thread: their call
        else:
            plan.resolve.append(item)
    return plan


def triage_reply(item: dict) -> str:
    return (f"jrfc triage: noise — {item['reason']}\n\n"
            "<sub>Resolved by jrfc. Reopen the thread if you disagree; jrfc will not resolve it again.</sub>\n\n"
            f"<!-- jrfc:triage key={triage_key(item)} -->")


def execute_triage(gh: GitHub, plan: TriagePlan) -> None:
    for item in plan.resolve:
        gh.api(["--method", "POST", f"repos/{gh.repo}/pulls/{gh.pr}/comments/{item['comment_id']}/replies"],
               {"body": triage_reply(item)})
        gh.api(["graphql", "-f", f"query={RESOLVE}", "-f", f"id={item['thread']}"])


def execute(gh: GitHub, review: dict, plan: Plan, triage_md: str | None = None) -> None:
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
    body = {"body": summary_body(review, plan, triage_md)}
    if plan.summary_comment_id:
        gh.api(["--method", "PATCH", f"repos/{gh.repo}/issues/comments/{plan.summary_comment_id}"], body)
    else:
        gh.api(["--method", "POST", f"repos/{gh.repo}/issues/{gh.pr}/comments"], body)


def publish(review: dict, repo: str, pr: int, dry_run: bool, runner: Runner = gh_runner,
            triage: dict | None = None, resolve_noise: bool = False,
            bot_patterns: list[str] | None = None) -> tuple[Plan, TriagePlan | None]:
    gh = GitHub(repo, pr, runner)
    plan = make_plan(review, gh.threads(), gh.summary_comment_id())
    tplan = None
    if triage is not None and resolve_noise:
        tplan = make_triage_plan(triage, gh.review_threads(), bot_patterns or [])
    if not dry_run:
        execute(gh, review, plan, triage["markdown"] if triage else None)
        if tplan is not None:
            execute_triage(gh, tplan)
    return plan, tplan
