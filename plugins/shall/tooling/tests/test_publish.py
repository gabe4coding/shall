"""Idempotent PR publishing across several pushes, against an in-memory fake of `gh`."""

import json

from shall.artifact import build_artifact
from shall.publish import SUMMARY_MARKER, publish
from shall.review import render_github

BOT, HUMAN = "shall-bot", "alice"
SELECTION = {"applicable": [], "model": "jev-test", "strategy": "layered"}


class FakeGitHub:
    """Implements just the gh calls shall publish makes, and records every write."""

    def __init__(self):
        self.threads = []        # {id, key_body, path, isResolved, resolvedBy}
        self.comments = {}       # issue comment id -> body
        self.writes = []

    def __call__(self, args, stdin):
        payload = json.loads(stdin) if stdin else None
        if args[:2] == ["api", "graphql"]:
            query = next(a for a in args if a.startswith("query="))
            if "reviewThreads" in query:
                return json.dumps({"data": {"repository": {"pullRequest": {"reviewThreads": {
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                    "nodes": [{
                        "id": t["id"], "isResolved": t["isResolved"], "path": t["path"],
                        "resolvedBy": {"login": t["resolvedBy"]} if t["resolvedBy"] else None,
                        "comments": {"nodes": [{"body": t["body"], "author": {"login": BOT}}]},
                    } for t in self.threads],
                }}}}})
            tid = next(a for a in args if a.startswith("id=")).split("=", 1)[1]
            thread = next(t for t in self.threads if t["id"] == tid)
            resolve = "unresolveReviewThread" not in query
            thread.update(isResolved=resolve, resolvedBy=BOT if resolve else None)
            self.writes.append(("resolve" if resolve else "unresolve", tid))
            return "{}"
        if "--paginate" in args:
            return "\n".join(str(i) for i, b in self.comments.items() if SUMMARY_MARKER in b)
        method, path = args[args.index("--method") + 1], args[args.index("--method") + 2]
        if path.endswith("/reviews"):
            for c in payload["comments"]:
                self.threads.append({"id": f"T{len(self.threads)}", "body": c["body"], "path": c["path"],
                                     "isResolved": False, "resolvedBy": None})
            self.writes.append(("review", len(payload["comments"])))
        elif method == "POST":
            self.comments[len(self.comments) + 1] = payload["body"]
            self.writes.append(("summary-create",))
        else:
            self.comments[int(path.rsplit("/", 1)[1])] = payload["body"]
            self.writes.append(("summary-update",))
        return "{}"


def diff(lines: list[str], start: int = 10) -> str:
    body = "\n".join("+" + line for line in lines)
    return (f"diff --git a/src/a.ts b/src/a.ts\n--- a/src/a.ts\n+++ b/src/a.ts\n"
            f"@@ -{start},0 +{start},{len(lines)} @@\n{body}\n")


def review_for(lines: list[str], findings: list[tuple[str, str]], start: int = 10) -> dict:
    """findings: (statement_id, exact added line text) -> the GitHub payload shall renders."""
    art = build_artifact("pr.diff", diff(lines, start), "diff", 40000)
    by_text = {t: n for n, t in art.chunks[0].line_text.items()}
    kept = [{
        "statement_id": sid, "rfc": sid.split(".")[0], "title": "t", "level": "MUST", "blocking": True,
        "path": "src/a.ts", "line": by_text[text], "quote": text, "message": "m", "suggestion": "",
        "statement_text": "s", "source": "x#L1",
    } for sid, text in findings]
    return render_github(art, SELECTION, kept, [])


LOG = 'logger.info("booking for " + guest.email)'
FETCH = "await fetch(url)"
FIXED_LOG = 'logger.info("booking", { guestId: guest.id })'


def run(gh, review):
    return publish(review, "org/app", 7, dry_run=False, runner=gh)[0].to_json()


def test_repeated_push_posts_nothing_new_and_updates_one_summary():
    gh = FakeGitHub()
    first = run(gh, review_for([LOG, FETCH], [("JRFC-0003.1", LOG), ("JRFC-0006.1", FETCH)]))
    assert len(first["new"]) == 2 and first["summary"] == "create"
    # same code pushed again, shifted by 5 lines: keys use line content, so nothing is new
    second = run(gh, review_for([LOG, FETCH], [("JRFC-0003.1", LOG), ("JRFC-0006.1", FETCH)], start=15))
    assert second["new"] == [] and len(second["kept"]) == 2 and second["summary"] == "update"
    assert [w for w in gh.writes if w[0] == "review"] == [("review", 2)]
    assert len(gh.comments) == 1


def test_fixed_line_resolves_thread_and_regression_reopens_it():
    gh = FakeGitHub()
    run(gh, review_for([LOG, FETCH], [("JRFC-0003.1", LOG), ("JRFC-0006.1", FETCH)]))
    fixed = run(gh, review_for([FIXED_LOG, FETCH], [("JRFC-0006.1", FETCH)]))
    assert [r["key"] for r in fixed["resolve"]] and fixed["new"] == []
    log_thread = fixed["resolve"][0]["thread"]
    back = run(gh, review_for([LOG, FETCH], [("JRFC-0003.1", LOG), ("JRFC-0006.1", FETCH)]))
    assert [u["thread"] for u in back["unresolve"]] == [log_thread] and back["new"] == []


def test_agent_variance_does_not_close_a_thread_while_the_line_is_still_there():
    gh = FakeGitHub()
    run(gh, review_for([LOG, FETCH], [("JRFC-0003.1", LOG), ("JRFC-0006.1", FETCH)]))
    missed = run(gh, review_for([LOG, FETCH], [("JRFC-0006.1", FETCH)]))  # agent skipped the log finding
    assert missed["resolve"] == [] and missed["new"] == []
    assert not any(t["isResolved"] for t in gh.threads)


def test_thread_resolved_by_a_person_is_respected_and_recorded():
    gh = FakeGitHub()
    run(gh, review_for([LOG], [("JRFC-0003.1", LOG)]))
    gh.threads[0].update(isResolved=True, resolvedBy=HUMAN)
    again = run(gh, review_for([LOG], [("JRFC-0003.1", LOG)]))
    assert again["new"] == [] and again["unresolve"] == []
    assert [d["by"] for d in again["dismissed"]] == [HUMAN]


def test_changed_line_is_a_new_finding():
    gh = FakeGitHub()
    run(gh, review_for([LOG], [("JRFC-0003.1", LOG)]))
    other = 'logger.info("booking for " + guest.phone)'
    nxt = run(gh, review_for([other], [("JRFC-0003.1", other)]))
    assert len(nxt["new"]) == 1 and len(nxt["resolve"]) == 1


def test_dry_run_reads_but_never_writes():
    gh = FakeGitHub()
    plan, _ = publish(review_for([LOG], [("JRFC-0003.1", LOG)]), "org/app", 7, dry_run=True, runner=gh)
    assert len(plan.new) == 1 and gh.writes == []


def test_hidden_fields_are_not_sent_to_github():
    gh = FakeGitHub()
    sent = {}
    original = gh.__call__

    def spy(args, stdin):
        if stdin and "/reviews" in " ".join(args):
            sent.update(json.loads(stdin))
        return original(args, stdin)

    publish(review_for([LOG], [("JRFC-0003.1", LOG)]), "org/app", 7, dry_run=False, runner=spy)
    assert sent["event"] == "COMMENT"
    assert all(not k.startswith("shall_") for c in sent["comments"] for k in c)
    assert "<!-- shall:finding key=" in sent["comments"][0]["body"]
