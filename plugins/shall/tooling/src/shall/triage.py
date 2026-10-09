"""Triage the review comments that other AI reviewers left on a pull request.

Bots such as Copilot or CodeRabbit comment on many lines. A few comments point to real
problems; the rest is noise: praise, summaries, nits, generic advice, claims that code
elsewhere already refutes, the same concern twice. Triage keeps what is relevant and says
why the rest was set aside, with the same split of work as `shall review`:

    bot comments, anchored on the PR diff (outdated ones set aside)      code
    which statements apply to the chunk? (the selection of `review`)    Jev, one Noul each
    actionable? which applicable statement covers it? said twice?       Jev, one Noul each
    is the claim true, given evidence from the repository?              tool-less agent
    relevant | unverified | noise | outdated, with the reason           code

A comment is noise only for a reason code can show: Jev scored it not actionable, it repeats
an earlier comment or a shall finding, or the verifier refuted it citing evidence that exists.
A comment the verifier could not decide stays (unverified): dropping a real problem is worse
than showing one comment too many. Triage never blocks a merge: severity comes only from the
corpus and shall's own review (JTOOL-0002.5).
"""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

from .artifact import Artifact, Chunk
from .config import Config
from .corpus import Corpus
from .jev import Jev, noul
from .publish import is_bot, is_shall, login_matches
from .review import agent_prompt, run_claude
from .select import Selector
from .verify import VERDICT_SCHEMA, gather_evidence, render_evidence, verification_scope

STATUSES = ("relevant", "unverified", "noise", "outdated")
MAX_JEV_TEXT = 4000
MAX_AGENT_TEXT = 8000
DUPLICATE_WINDOW = 5      # lines: two comments further apart are never compared
MAX_STANDARDS = 3

ACTIONABLE = noul(
    "Does the `review_comment` point to a specific problem in the `code` that a change to the "
    "code would fix? The commented line is marked `>>`.",
    true="It names a concrete defect, risk or gap in this code: a bug, a wrong result, a security "
         "or personal-data issue, an unhandled error or edge case, a missing check, a broken "
         "contract, a resource leak, or a violated project rule.",
    false="It praises or summarizes the change, asks a question without claiming a problem, gives "
          "generic advice not tied to this code, speculates without a concrete failure, suggests an "
          "optional extra (more logging, tests, comments or docs) without naming something that fails, "
          "or only asks for renaming, formatting or a style fix that a linter or formatter would make.",
)

SAME_CONCERN = noul(
    "Do the `first` and the `second` review comment point to the same problem in the `code`?",
    true="Fixing the problem named in one comment would also fix the problem named in the other.",
    false="They name different problems, even when they are on the same line or about the same code.",
)


def covers_question(st):
    return noul(
        "Does the `review_comment` say that the `code` breaks this requirement, or ask for exactly "
        f"what this requirement asks for? Requirement: \"{st.text}\"",
        true="The problem the comment names is a case of what this requirement forbids or requires.",
        false="The comment names a different problem, praises or summarizes the code, or only touches "
              "the same topic.",
    )


# ---------------------------------------------------------------- input (code)

DETAILS_RE = re.compile(r"<details>.*?</details>", re.S | re.I)
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
CODE_SPAN_RE = re.compile(r"`([^`\n]+)`")


def clean_body(text: str) -> str:
    """What the bot claims, without hidden markers and folded extras (prompts for agents,
    tool output, committable suggestions) that are not part of the claim."""
    text = HTML_COMMENT_RE.sub("", text or "")
    while True:
        stripped = DETAILS_RE.sub("", text)
        if stripped == text:
            break
        text = stripped
    return re.sub(r"\n{3,}", "\n\n", text).strip()


EMPHASIS_RE = re.compile(r"\*\*|__|(?<![\w`])_|_(?![\w`])")


def summary_of(text: str, limit: int = 160) -> str:
    """The first line with some content, without markdown emphasis; label lines such as
    "⚠️ Potential issue" are skipped when a longer line follows."""
    lines = [EMPHASIS_RE.sub("", ln).strip(" #*>-") for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    first = next((ln for ln in lines if len(ln.split()) >= 4), lines[0] if lines else "")
    return first if len(first) <= limit else first[: limit - 1].rstrip() + "…"


def load_threads(path: Path) -> list[dict]:
    """Threads from a JSON file: a list, or {"comments": [...]}, in the shape of
    `GitHub.review_threads()`. Missing fields get defaults, so a hand-written file needs only
    author, path, line and body."""
    data = json.loads(path.read_text(encoding="utf-8"))
    data = data.get("comments", data) if isinstance(data, dict) else data
    out = []
    for i, t in enumerate(data):
        out.append({"thread": None, "comment_id": None, "author_type": None, "outdated": False,
                    "resolved": False, "url": None, "replies": [], **t,
                    "id": str(t.get("id") or t.get("comment_id") or t.get("thread") or f"k{i}")})
    return out


def bot_comments(cfg: Config, threads: list[dict]) -> tuple[list[dict], dict]:
    """The threads started by an AI reviewer that are still open, and counts of the rest."""
    patterns = list(cfg.get("triage.authors") or [])
    ignored = list(cfg.get("triage.ignore_authors") or [])
    kept, skipped = [], {"human": 0, "shall": 0, "ignored": 0, "resolved": 0}
    for i, t in enumerate(threads):
        t = {**t, "id": str(t.get("id") or t.get("comment_id") or t.get("thread") or f"k{i}")}
        if is_shall(t.get("body", "")):
            skipped["shall"] += 1
        elif any(login_matches(t["author"], p) for p in ignored):
            skipped["ignored"] += 1
        elif not is_bot(t["author"], t.get("author_type"), patterns):
            skipped["human"] += 1
        elif t.get("resolved"):
            skipped["resolved"] += 1
        else:
            kept.append(t)
    return kept, skipped


def anchor(artifact: Artifact, c: dict) -> tuple[Chunk | None, str | None]:
    """The chunk that shows the commented line, or why there is none (the comment is outdated)."""
    chunks = [ch for ch in artifact.chunks if ch.path == c.get("path")]
    if not chunks:
        return None, "outdated: the file is not in the diff any more"
    line = c.get("line")
    if c.get("outdated") or (line is not None and line not in chunks[0].line_text):
        return None, "outdated: the commented code changed after the comment"
    if line is None:
        return chunks[0], None  # a comment on the whole file
    shown = re.compile(rf"^{line:>5} [+ |]", re.M)
    return next((ch for ch in chunks if shown.search(ch.rendered)), chunks[0]), None


def code_context(chunk: Chunk, line: int | None, radius: int = 12) -> str:
    if line is None:
        return chunk.rendered[:MAX_AGENT_TEXT]
    numbers = sorted(n for n in chunk.line_text if abs(n - line) <= radius)
    return "\n".join(f"{'>>' if n == line else '  '}{n:>5} | {chunk.line_text[n]}" for n in numbers)


# ---------------------------------------------------------------- triage

def _item(c: dict, status: str, reason: str, **extra) -> dict:
    return {"id": c["id"], "thread": c.get("thread"), "comment_id": c.get("comment_id"), "url": c.get("url"),
            "author": c["author"], "path": c.get("path"), "line": c.get("line"),
            "summary": summary_of(c["text"]), "status": status, "reason": reason, **extra}


def comment_prompt(c: dict, context: str, standard: dict | None, evidence: str) -> str:
    std = (f"<standard>\n{standard['id']} [{standard['level']}] {standard['text']}\n</standard>\n\n"
           if standard else "")
    return (f"<comment author=\"{c['author']}\" file=\"{c['path']}\" line=\"{c.get('line')}\">\n"
            f"{c['text'][:MAX_AGENT_TEXT]}\n</comment>\n\n{std}"
            f"<chunk file=\"{c['path']}\">\n{context}\n</chunk>\n\n<evidence>\n{evidence}\n</evidence>")


def apply_comment_verdict(verdict: dict | None, excerpts) -> tuple[str, dict]:
    """(status, verification record). Noise needs a refutation that cites evidence that exists;
    relevant needs a confirmation that cites it; everything else stays as unverified."""
    known = {e.id: e for e in excerpts}
    if verdict is None:
        verdict = {"verdict": "unknown", "reason": "verification did not return a verdict", "evidence": []}
    cited = [i for i in verdict.get("evidence", []) if i == "chunk" or i in known]
    record = {
        "verdict": verdict.get("verdict", "unknown"),
        "reason": verdict.get("reason", ""),
        "evidence": [i if i == "chunk" else f"{known[i].path}:{known[i].start}-{known[i].end}" for i in cited],
        "shown": [f"{e.path}:{e.start}-{e.end}" for e in excerpts],
    }
    if record["verdict"] in ("refuted", "confirmed") and not cited:
        record["reason"] = f"{record['verdict']} without citing evidence: " + record["reason"]
        record["verdict"] = "unknown"
    return {"refuted": "noise", "confirmed": "relevant"}.get(record["verdict"], "unverified"), record


async def triage_comments(cfg: Config, corpus: Corpus, artifact: Artifact, jev: Jev, comments: list[dict],
                          findings: list[dict] | None = None, agent=None, index=None,
                          cache=None, search_root: Path | None = None,
                          facts: dict[str, list[str]] | None = None) -> tuple[list[dict], dict]:
    th = {"actionable": 0.5, "statement": 0.5, "duplicate": 0.7, **(cfg.get("triage.thresholds") or {})}
    verify = bool(cfg.get("triage.verify", True))
    model = cfg.get("review.verify_model") or None
    agent = agent or (lambda prompt, sem: run_claude(cfg, prompt, agent_prompt("shall-comment-verifier"),
                                                     VERDICT_SCHEMA, sem, model=model, cache=cache))
    # the same selection as `shall review` (same Jev questions, so cached answers are shared):
    # a comment is matched only against the statements that apply to its chunk
    selector = Selector(cfg, corpus, jev, facts=facts)
    stats = {"comments": len(comments), "agent_calls": 0, "reused": 0, "cost_usd": 0.0, "errors": []}
    items: dict[str, dict] = {}

    # 1. code: anchor on the diff
    live: list[tuple[dict, Chunk]] = []
    for c in comments:
        c["text"] = clean_body(c.get("body", ""))
        chunk, reason = anchor(artifact, c)
        if reason:
            items[c["id"]] = _item(c, "outdated", reason)
        else:
            c["context"] = code_context(chunk, c.get("line"))
            live.append((c, chunk))

    # 2. Jev: which statements apply to the chunk (as in review)? is the comment actionable?
    #    which of the applicable statements covers its concern?
    chunks = {chunk.id: chunk for _, chunk in live}
    selections = dict(zip(chunks, await jev.gather(selector.select_chunk(ch) for ch in chunks.values())))

    async def ask(c: dict, chunk: Chunk):
        cands = [corpus.statement(sid)[1] for sid in selections[chunk.id].selected]
        state = {"review_comment": c["text"][:MAX_JEV_TEXT], "file": c["path"], "language": chunk.language,
                 "code": c["context"]}
        return await jev.ask(state, {"actionable": ACTIONABLE, **{st.id: covers_question(st) for st in cands}})

    answers = await jev.gather(ask(c, chunk) for c, chunk in live)
    actionable: list[tuple[dict, Chunk]] = []
    for (c, chunk), ans in zip(live, answers):
        p_act = ans["actionable"]["p"]
        standards = []
        for sid, a in sorted(ans.items(), key=lambda kv: -kv[1].get("p", 0)):
            if sid != "actionable" and a["p"] >= th["statement"] and len(standards) < MAX_STANDARDS:
                rfc, st = corpus.statement(sid)
                standards.append({"id": sid, "level": st.level, "title": st.title, "text": st.text,
                                  "p": round(a["p"], 2)})
        c["p_actionable"], c["standards"] = round(p_act, 2), standards
        if p_act < th["actionable"]:
            items[c["id"]] = _item(c, "noise", f"not actionable (p={p_act:.2f}): no concrete problem in the code",
                                   p_actionable=c["p_actionable"], standards=standards)
        else:
            actionable.append((c, chunk))

    # 3. Jev: the same concern as a shall finding or an earlier comment? (nearby lines only)
    earlier: list[dict] = [{"id": f"shall:{f['statement_id']}:{f['path']}:{f.get('line')}", "path": f["path"],
                            "line": f.get("line"), "text": f"{f['title']}: {f['message']}",
                            "label": f"shall finding {f['statement_id']}"} for f in findings or []]
    pairs = []
    for c, _ in actionable:
        for e in earlier:
            if e["path"] == c["path"] and (
                    (e["line"] is None and c.get("line") is None) or
                    (e["line"] is not None and c.get("line") is not None
                     and abs(e["line"] - c["line"]) <= DUPLICATE_WINDOW)):
                pairs.append((e, c))
        earlier.append({"id": c["id"], "path": c["path"], "line": c.get("line"), "text": c["text"],
                        "label": f"{c['author']} on {c['path']}:{c.get('line')}"})
    same = await jev.gather(
        jev.ask({"first": e["text"][:MAX_JEV_TEXT], "second": c["text"][:MAX_JEV_TEXT], "file": c["path"],
                 "code": c["context"]}, {"same": SAME_CONCERN})
        for e, c in pairs)
    duplicate_of: dict[str, dict] = {}
    for (e, c), ans in zip(pairs, same):
        # the earlier one must itself survive: a chain of duplicates points at its head
        if ans["same"]["p"] >= th["duplicate"] and c["id"] not in duplicate_of and e["id"] not in duplicate_of:
            duplicate_of[c["id"]] = {**e, "p": ans["same"]["p"]}
    to_verify = []
    for c, chunk in actionable:
        d = duplicate_of.get(c["id"])
        if d:
            items[c["id"]] = _item(c, "noise", f"duplicate of {d['label']} (p={d['p']:.2f})",
                                   p_actionable=c["p_actionable"], standards=c["standards"], duplicate_of=d["id"])
        else:
            to_verify.append((c, chunk))

    # 4. agent: is the claim true, given evidence from the repository? 5. code applies it
    if not verify:
        for c, _ in to_verify:
            items[c["id"]] = _item(c, "unverified", "not verified (triage.verify is off)",
                                   p_actionable=c["p_actionable"], standards=c["standards"])
    else:
        root, excluded, index = verification_scope(cfg, corpus, index, search_root)
        sem = asyncio.Semaphore(int(cfg.get("review.concurrency")))

        async def check(c: dict, chunk: Chunk):
            top = c["standards"][0] if c["standards"] else None
            claim = {"path": c["path"], "line": c.get("line"), "chunk": chunk.id,
                     "quote": chunk.line_text.get(c.get("line"), "") if c.get("line") else "",
                     "message": c["text"][:MAX_JEV_TEXT],
                     "statement_text": top["text"] if top else c["text"][:MAX_JEV_TEXT],
                     "depends_on": [s for s in CODE_SPAN_RE.findall(c["text"]) if len(s) <= 80][:8]}
            excerpts, notes = await gather_evidence(artifact, jev, claim, root, excluded, index)
            verdict, meta = await agent(comment_prompt(c, c["context"], top, render_evidence(excerpts, notes)), sem)
            return excerpts, verdict, meta

        results = await asyncio.gather(*(check(c, chunk) for c, chunk in to_verify))
        for (c, _), (excerpts, verdict, meta) in zip(to_verify, results):
            stats["reused" if meta.get("cached") else "agent_calls"] += 1
            stats["cost_usd"] = round(stats["cost_usd"] + meta.get("cost_usd", 0.0), 6)
            if "error" in meta:
                stats["errors"].append({"comment": c["id"], "error": meta["error"]})
            status, record = apply_comment_verdict(verdict, excerpts)
            reason = {"relevant": "confirmed by the code", "noise": "refuted",
                      "unverified": "could not be verified"}[status] + f": {record['reason']}"
            items[c["id"]] = _item(c, status, reason, p_actionable=c["p_actionable"], standards=c["standards"],
                                   verification=record)
        stats["codegraph_events"] = list(index.events) if index is not None else []

    order = {s: i for i, s in enumerate(STATUSES)}
    out = sorted(items.values(), key=lambda i: (order[i["status"]], not i.get("standards"),
                                                i["path"] or "", i["line"] or 0, i["id"]))
    stats.update({s: sum(1 for i in out if i["status"] == s) for s in STATUSES})
    return out, stats


# ---------------------------------------------------------------- report

def render_triage(items: list[dict], stats: dict) -> str:
    authors = sorted({i["author"] for i in items})
    out = [
        "## shall triage — comments from other AI reviewers",
        "",
        f"**{len(items)} open comment(s)** from {', '.join(f'`{a}`' for a in authors) or 'no AI reviewer'} · "
        f"{stats.get('relevant', 0)} relevant · {stats.get('unverified', 0)} unverified · "
        f"{stats.get('noise', 0)} noise · {stats.get('outdated', 0)} outdated",
        "",
    ]

    def where(i: dict) -> str:
        loc = f"{i['path']}:{i['line']}" if i.get("line") else f"{i['path']}"
        return f"[`{loc}`]({i['url']})" if i.get("url") else f"`{loc}`"

    def std(i: dict) -> str:
        s = i.get("standards") or []
        return f" · _Standard:_ `{s[0]['id']}` {s[0]['title']} ({s[0]['level']})" if s else ""

    for status, title in (("relevant", "Relevant"), ("unverified", "Unverified — check by hand")):
        rows = [i for i in items if i["status"] == status]
        if rows:
            out += [f"### {title}", ""]
            for i in rows:
                out.append(f"- **{i['author']}** {where(i)} — {i['summary']}")
                out.append(f"  {i['reason']}{std(i)}")
            out.append("")
    for status, title in (("noise", "Noise"), ("outdated", "Outdated")):
        rows = [i for i in items if i["status"] == status]
        if rows:
            out += [f"<details><summary>{title} ({len(rows)})</summary>", ""]
            out += [f"- {i['author']} {where(i)} — {i['summary']}<br>_{i['reason']}_" for i in rows]
            out += ["", "</details>", ""]
    if stats.get("errors"):
        out.append(f"<sub>⚠️ {len(stats['errors'])} verification call(s) failed: those comments are unverified.</sub>")
    return "\n".join(out).rstrip() + "\n"
