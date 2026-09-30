"""Selection evaluation against hand-labelled cases (eval/labels.yaml)."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

import yaml

from .artifact import build_artifact, detect_kind, read_source
from .config import Config
from .corpus import Corpus
from .jev import Jev
from .select import Selector, classify_document

SWEEP = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]


def _pr(expected: set[str], got: set[str]) -> tuple[float, float]:
    recall = len(expected & got) / len(expected) if expected else (1.0 if not got else 1.0)
    precision = len(expected & got) / len(got) if got else (1.0 if not expected else 0.0)
    return recall, precision


def _case_facts(cfg: Config, corpus: Corpus, base: Path, case: dict, artifact) -> dict:
    """known_effects as in a real run; `repo:` (a fixture directory) enables indirect facts."""
    import shutil
    import subprocess
    import tempfile

    from .codegraph import RepoIndex
    from .effects import chunk_facts
    depth = int(cfg.get("selection.facts_depth"))
    if not case.get("repo"):
        return chunk_facts(corpus.effects, artifact, None, depth)
    with tempfile.TemporaryDirectory(prefix="jrfc-eval-") as tmp:
        root = Path(tmp) / "repo"
        shutil.copytree(base / case["repo"], root)
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)  # the index uses `git grep`
        return chunk_facts(corpus.effects, artifact, RepoIndex(root), depth)


async def _run_case(cfg: Config, corpus: Corpus, jev: Jev, base: Path, case: dict, strategy: str,
                    facts: bool = True) -> dict:
    name, raw = read_source(str(base / case["file"]), None)
    kind = case.get("kind") or detect_kind(name, raw)
    if kind == "document":
        kind, _ = await classify_document(jev, name, raw)
    artifact = build_artifact(case.get("path", name), raw, kind, int(cfg.get("jev.max_chunk_chars")))
    known = _case_facts(cfg, corpus, base, case, artifact) if facts and cfg.get("selection.facts") else {}
    results = await Selector(cfg, corpus, jev, strategy=strategy, facts=known).select(artifact)
    got = {sid for r in results for sid in r.selected}
    p_max: dict[str, float] = {}
    for r in results:
        for sid, p in r.statements.items():
            p_max[sid] = max(p_max.get(sid, 0.0), p)
    expected = set(case.get("expected", []))
    recall, precision = _pr(expected, got)
    return {
        "case": case["file"], "kind": kind, "expected": sorted(expected), "selected": sorted(got),
        "missed": sorted(expected - got), "extra": sorted(got - expected),
        "lost_at": {sid: _lost_at(corpus, results, sid) for sid in sorted(expected - got)},
        "facts": known,
        "recall": recall, "precision": precision, "p_max": p_max,
    }


LAYERS = ("prefilter", "domain", "rfc", "statement")


def _lost_at(corpus: Corpus, results, sid: str) -> str:
    """The layer that dropped a missed statement: the deepest layer it reached in any chunk."""
    rfc, _ = corpus.statement(sid)
    reached = "prefilter"
    for r in results:
        if sid in r.statements:
            return "statement"
        if rfc.id in r.rfcs:
            reached = "rfc"
        elif rfc.domain in r.domains and reached == "prefilter":
            reached = "domain"
    return reached


async def run_eval(cfg: Config, corpus: Corpus, jev: Jev, labels_path: Path, strategies: list[str],
                   facts: bool = True) -> dict:
    labels = yaml.safe_load(labels_path.read_text(encoding="utf-8"))
    base = labels_path.parent
    report = {}
    for strategy in strategies:
        before, started = dict(jev.usage), time.perf_counter()
        cases = await asyncio.gather(*(_run_case(cfg, corpus, jev, base, c, strategy, facts) for c in labels["cases"]))
        usage = {k: jev.usage[k] - before.get(k, 0) for k in jev.usage}
        usage["calls"] = usage["requests"] + usage["cached"]
        usage["seconds"] = round(time.perf_counter() - started, 1)
        exp = sum(len(c["expected"]) for c in cases)
        hit = sum(len(set(c["expected"]) & set(c["selected"])) for c in cases)
        sel = sum(len(c["selected"]) for c in cases)
        sweep = []
        for t in SWEEP:  # statement threshold sweep on the recorded probabilities
            h = s = 0
            for c in cases:
                got = {sid for sid, p in c["p_max"].items() if p >= t}
                h += len(set(c["expected"]) & got)
                s += len(got)
            sweep.append({"threshold": t, "recall": h / exp if exp else 1.0, "precision": h / s if s else 1.0,
                          "selected": s})
        report[strategy] = {
            "micro_recall": hit / exp if exp else 1.0,
            "micro_precision": hit / sel if sel else 1.0,
            "expected": exp, "selected": sel,
            "cases": cases, "sweep": sweep, "usage": usage,
            "lost_at": {layer: sum(1 for c in cases for v in c["lost_at"].values() if v == layer)
                        for layer in LAYERS},
        }
    report["usage"] = dict(jev.usage)
    return report


def render_eval(report: dict) -> str:
    out = []
    for strategy, r in report.items():
        if strategy == "usage":
            continue
        out.append(f"## strategy: {strategy}")
        u = r["usage"]
        out.append(f"micro recall {r['micro_recall']:.2f} · micro precision {r['micro_precision']:.2f} "
                   f"· {r['selected']} selected / {r['expected']} expected")
        out.append(f"cost: {u['calls']} Jev calls ({u['cached']} cached) · ~{u['est_input_tokens']:,} input tokens "
                   f"(~${u['est_input_tokens'] * 0.042 / 1e6:.4f}) · {u['seconds']}s")
        out.append("missed statements lost at: " + ", ".join(f"{k} {v}" for k, v in r["lost_at"].items()))
        out.append("")
        out.append("| case | kind | recall | precision | missed | extra |")
        out.append("|---|---|---|---|---|---|")
        for c in r["cases"]:
            missed = ", ".join(f"{m} ({c['lost_at'][m]})" for m in c["missed"])
            out.append(f"| {c['case']} | {c['kind']} | {c['recall']:.2f} | {c['precision']:.2f} | "
                       f"{missed or '-'} | {', '.join(c['extra']) or '-'} |")
        out.append("")
        out.append("statement-threshold sweep: " + " · ".join(
            f"t={s['threshold']:.1f} R={s['recall']:.2f} P={s['precision']:.2f}" for s in r["sweep"]))
        out.append("")
    out.append(f"Jev usage: {report['usage']}")
    return "\n".join(out)


# ---------------------------------------------------------------- verification eval


async def _verify_case(cfg: Config, corpus: Corpus, jev: Jev, case_dir: Path, model: str | None) -> dict:
    import shutil
    import subprocess
    import tempfile
    import time

    from .artifact import build_artifact
    from .verify import verify_findings

    meta = yaml.safe_load((case_dir / "case.yaml").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="jrfc-verify-") as tmp:
        root = Path(tmp) / "repo"
        shutil.copytree(case_dir / "repo", root)
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)  # search runs `git grep` like in CI
        raw = (root / meta["artifact"]).read_text(encoding="utf-8")
        artifact = build_artifact(meta["artifact"], raw, meta.get("kind", "code"), int(cfg.get("jev.max_chunk_chars")))
        chunk = artifact.chunks[0]
        f = meta["finding"]
        line = next(n for n, t in sorted(chunk.line_text.items()) if f["quote"] in t)
        rfc, st = corpus.statement(f["statement_id"])
        finding = {
            "statement_id": st.id, "rfc": rfc.id, "title": st.title, "level": st.level,
            "blocking": rfc.statement_blocking(st), "path": meta["artifact"], "line": line,
            "quote": f["quote"], "message": f["message"], "suggestion": "", "depends_on": f.get("depends_on", []),
            "chunk": chunk.id, "statement_text": st.text, "source": corpus.source(rfc, st.line),
        }
        # expected evidence is "path: text on the evidence line" -> (path, line number)
        targets = []
        for spec in meta["expected"].get("evidence", []):
            path, _, text = spec.partition(": ")
            lines = (root / path).read_text(encoding="utf-8").splitlines()
            targets.append((path, next(n for n, t in enumerate(lines, 1) if text in t)))
        started = time.perf_counter()
        kept, dropped, stats = await verify_findings(cfg, corpus, artifact, jev, [finding], search_root=root,
                                                     model=model)
        seconds = time.perf_counter() - started
    result = (kept or dropped)[0]["verification"]
    expected = meta["expected"]
    ranges = []
    for shown in result.get("shown", []):
        path, _, span = shown.rpartition(":")
        lo, _, hi = span.partition("-")
        ranges.append((path, int(lo), int(hi)))
    covered = all(any(p == path and lo <= line <= hi for p, lo, hi in ranges) for path, line in targets)
    return {
        "case": case_dir.name, "expected": expected["verdict"], "verdict": result["verdict"],
        "correct": result["verdict"] == expected["verdict"],
        "evidence_expected": expected.get("evidence", []),
        "evidence_shown": covered,
        "shown": result.get("shown", []), "reason": result["reason"],
        "cost_usd": stats["cost_usd"], "seconds": round(seconds, 1),
    }


async def run_verify_eval(cfg: Config, corpus: Corpus, jev: Jev, cases_root: Path, models: list[str],
                          retrievals: list[str]) -> dict:
    cases = sorted(p for p in cases_root.iterdir() if (p / "case.yaml").is_file())
    report = {}
    for retrieval in retrievals:
        for model in models:
            cfg.data.setdefault("review", {})["verify_retrieval"] = retrieval
            rows = []
            for case in cases:  # sequential: cases share the verifier concurrency and the API budget
                rows.append(await _verify_case(cfg, corpus, jev, case, model))
            report[f"{retrieval} / {model}"] = {
                "accuracy": sum(r["correct"] for r in rows) / len(rows),
                "evidence_recall": sum(r["evidence_shown"] for r in rows if r["evidence_expected"])
                / max(1, sum(1 for r in rows if r["evidence_expected"])),
                "wrong_refutes": sum(1 for r in rows if r["verdict"] == "refuted" and r["expected"] != "refuted"),
                "cost_usd": round(sum(r["cost_usd"] for r in rows), 4),
                "seconds": round(sum(r["seconds"] for r in rows), 1),
                "cases": rows,
            }
    report["usage"] = dict(jev.usage)
    return report


def render_verify_eval(report: dict) -> str:
    out = ["| retrieval / model | accuracy | evidence recall | wrong refutes | cost | time |", "|---|---|---|---|---|---|"]
    for key, r in report.items():
        if key == "usage":
            continue
        out.append(f"| {key} | {r['accuracy']:.2f} | {r['evidence_recall']:.2f} | {r['wrong_refutes']} | "
                   f"${r['cost_usd']:.3f} | {r['seconds']:.0f}s |")
    for key, r in report.items():
        if key == "usage":
            continue
        out += ["", f"### {key}", "", "| case | expected | verdict | evidence shown |", "|---|---|---|---|"]
        for c in r["cases"]:
            mark = "" if c["correct"] else " ❌"
            ev = "-" if not c["evidence_expected"] else ("yes" if c["evidence_shown"] else "**no**")
            out.append(f"| {c['case']} | {c['expected']} | {c['verdict']}{mark} | {ev} |")
    out.append("")
    out.append(f"Jev usage: {report['usage']}")
    return "\n".join(out)


# ---------------------------------------------------------------- triage of other AI reviewers' comments

async def _triage_case(cfg: Config, corpus: Corpus, jev: Jev, case_dir: Path, cache=None) -> dict:
    import shutil
    import subprocess
    import tempfile

    from .artifact import build_artifact
    from .triage import bot_comments, triage_comments
    from .verify import repo_index

    meta = yaml.safe_load((case_dir / "case.yaml").read_text(encoding="utf-8"))
    raw = (case_dir / meta.get("diff", "pr.diff")).read_text(encoding="utf-8")
    artifact = build_artifact("pr.diff", raw, "diff", int(cfg.get("jev.max_chunk_chars")))
    default_path = artifact.chunks[0].path
    threads = [{"thread": None, "comment_id": None, "author_type": None, "outdated": False, "resolved": False,
                "url": None, "replies": [], "path": default_path, **c} for c in meta["comments"]]
    expected = {c["id"]: c["expected"] for c in meta["comments"] if "expected" in c}
    comments, skipped = bot_comments(cfg, threads)
    with tempfile.TemporaryDirectory(prefix="jrfc-triage-") as tmp:
        root = Path(tmp) / "repo"
        shutil.copytree(case_dir / "repo", root)
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)  # the code graph runs `git grep`
        index = repo_index(cfg, corpus, root)
        facts = {}
        if cfg.get("selection.facts") and corpus.effects:
            from .effects import chunk_facts
            facts = chunk_facts(corpus.effects, artifact, index, int(cfg.get("selection.facts_depth")))
        items, stats = await triage_comments(cfg, corpus, artifact, jev, comments, index=index, cache=cache,
                                             search_root=root, facts=facts)
    rows = []
    for i in items:
        exp = expected.get(i["id"])
        kept = i["status"] in ("relevant", "unverified")
        rows.append({"id": i["id"], "expected": exp, "status": i["status"], "reason": i["reason"],
                     "correct": exp == i["status"] or (exp == "relevant" and kept),
                     "p_actionable": i.get("p_actionable"),
                     "standards": [f"{s['id']}={s['p']}" for s in i.get("standards") or []]})
    return {"case": case_dir.name, "rows": rows, "skipped": skipped, "unlabelled": sorted(set(expected) - {r["id"] for r in rows}),
            "cost_usd": stats.get("cost_usd", 0.0), "agent_calls": stats.get("agent_calls", 0),
            "errors": stats.get("errors", [])}


async def run_triage_eval(cfg: Config, corpus: Corpus, jev: Jev, cases_root: Path, cache=None) -> dict:
    """Per labelled comment: was a relevant one kept (relevant or unverified), was noise removed?
    The costly error is a relevant comment marked noise: it is counted separately."""
    cases = sorted(p for p in cases_root.iterdir() if (p / "case.yaml").is_file())
    results = [await _triage_case(cfg, corpus, jev, c, cache) for c in cases]
    rows = [r for c in results for r in c["rows"] if r["expected"]]

    def rate(exp: str, ok) -> float | None:
        sel = [r for r in rows if r["expected"] == exp]
        return round(sum(1 for r in sel if ok(r)) / len(sel), 2) if sel else None

    return {
        "comments": len(rows),
        "relevant_kept": rate("relevant", lambda r: r["status"] in ("relevant", "unverified")),
        "relevant_confirmed": rate("relevant", lambda r: r["status"] == "relevant"),
        "noise_removed": rate("noise", lambda r: r["status"] == "noise"),
        "outdated_found": rate("outdated", lambda r: r["status"] == "outdated"),
        "relevant_dropped": [f"{c['case']}/{r['id']}" for c in results for r in c["rows"]
                             if r["expected"] == "relevant" and r["status"] == "noise"],
        "cost_usd": round(sum(c["cost_usd"] for c in results), 4),
        "cases": results,
        "usage": dict(jev.usage),
    }


def render_triage_eval(report: dict) -> str:
    def pct(x):
        return "-" if x is None else f"{x:.2f}"
    out = [f"{report['comments']} labelled comment(s): relevant kept {pct(report['relevant_kept'])} "
           f"(confirmed {pct(report['relevant_confirmed'])}) · noise removed {pct(report['noise_removed'])} · "
           f"outdated found {pct(report['outdated_found'])} · relevant dropped as noise: "
           f"{', '.join(report['relevant_dropped']) or 'none'} · ${report['cost_usd']:.3f}", ""]
    for c in report["cases"]:
        out += [f"### {c['case']}", "", "| comment | expected | status | reason |", "|---|---|---|---|"]
        for r in c["rows"]:
            mark = "" if r["correct"] else " ❌"
            out.append(f"| {r['id']} | {r['expected'] or '-'} | {r['status']}{mark} | {r['reason'][:140]} |")
        out.append("")
    out.append(f"Jev usage: {report['usage']}")
    return "\n".join(out)


# ---------------------------------------------------------------- hooks

HOOK_THRESHOLDS = [0.5, 0.7, 0.9]


def _pct(values: list[float], q: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[min(len(ordered) - 1, int(q * len(ordered)))])


async def run_hooks_eval(cfg: Config, corpus: Corpus, jev: Jev, cases_path: Path, score: str = "both") -> dict:
    """Jev as the judge of tool calls and written code (eval/hooks/cases.yaml).

    Measures the judgment, not the policy: every status is included (drafts too) and each
    candidate statement's score is compared with the labelled `violates` set at the thresholds
    the action tables use. Cases run one at a time, so latency is what a hook waits.
    """
    import tempfile

    from .hooks import Hooks
    data = yaml.safe_load(cases_path.read_text(encoding="utf-8"))
    hooks = Hooks(cfg, corpus, jev, statuses=["draft", "approved", "enforced"], timeout=None, log=False,
                  score=score, skip_when_denied=False)
    rows = []
    with tempfile.TemporaryDirectory(prefix="jrfc-hooks-eval-") as tmp:
        for case in data["cases"]:
            kind = "tool" if case["event"] == "PreToolUse" else "code"
            event = {"hook_event_name": case["event"], "session_id": "eval", "cwd": case.get("cwd", tmp),
                     "tool_name": case["tool"], "tool_input": dict(case.get("input") or {})}
            if kind == "code":
                path = Path(tmp) / case["file"]
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(case["content"], encoding="utf-8")
                event["cwd"] = tmp
                event["tool_input"].setdefault("file_path", str(path))
                if case["tool"] == "Write":
                    event["tool_input"].setdefault("content", case["content"])
            hooks.git_branch = lambda cwd, b=case.get("branch", ""): b
            record: dict = {}
            t0 = time.perf_counter()
            await (hooks.pre(event, record) if kind == "tool" else hooks.post(event, record))
            ms = (time.perf_counter() - t0) * 1000
            scores = {**record.get("scores", {}),
                      **{sid: 1.0 for sid in record.get("scanner", []) + record.get("patterns", [])}}
            rows.append({"id": case["id"], "kind": kind, "expected": sorted(case.get("violates") or []),
                         "scores": scores, "ms": round(ms), "jev": record.get("jev", "none"),
                         "candidates": record.get("candidates", 0), "skip": record.get("skip")})
    summary: dict = {}
    for kind in ("tool", "code"):
        krows = [r for r in rows if r["kind"] == kind]
        per_t = {}
        for t in HOOK_THRESHOLDS:
            tp = fp = fn = 0
            for r in krows:
                got = {sid for sid, p in r["scores"].items() if p >= t}
                exp = set(r["expected"])
                tp, fp, fn = tp + len(got & exp), fp + len(got - exp), fn + len(exp - got)
            per_t[str(t)] = {"tp": tp, "fp": fp, "fn": fn,
                             "precision": round(tp / (tp + fp), 3) if tp + fp else None,
                             "recall": round(tp / (tp + fn), 3) if tp + fn else None}
        fresh = [r["ms"] for r in krows if r["jev"] == "request"]
        summary[kind] = {"cases": len(krows), "thresholds": per_t,
                         "latency_ms": {"requests": len(fresh), "p50": _pct(fresh, 0.5), "p95": _pct(fresh, 0.95),
                                        "max": round(max(fresh)) if fresh else None}}
    # the actions a user would see, with draft rules trialled as enforced (the JRFC-0012 trial)
    from .hooks import action_for, code_action
    policy = dict(cfg.get("hooks.actions") or {})
    policy.setdefault("draft", policy.get("enforced", {}))
    code_warn = float(cfg.get("hooks.code_warn"))
    for kind in ("tool", "code"):
        acts = {a: {"right": 0, "wrong": 0} for a in ("deny", "ask", "warn")}
        missed = []
        for r in (r for r in rows if r["kind"] == kind):
            for sid, p in r["scores"].items():
                rfc, st = corpus.statement(sid)
                act = action_for(policy, rfc, st, p) if kind == "tool" else code_action(policy, code_warn, rfc, st, p)
                if act in acts:
                    acts[act]["right" if sid in r["expected"] else "wrong"] += 1
                elif sid in r["expected"]:
                    missed.append(f"{r['id']}:{sid}")
            missed += [f"{r['id']}:{sid}" for sid in set(r["expected"]) - set(r["scores"])]
        summary[kind]["actions"] = {**acts, "missed": sorted(missed)}
    errors = []
    for r in rows:
        for sid, p in sorted(r["scores"].items()):
            exp = sid in r["expected"]
            if (p >= 0.5) != exp:
                errors.append({"case": r["id"], "statement": sid, "p": p, "type": "FP" if not exp else "FN"})
        for sid in set(r["expected"]) - set(r["scores"]):
            errors.append({"case": r["id"], "statement": sid, "p": None, "type": "FN (not a candidate)"})
    return {"model": cfg.get("jev.model"), "score": score, "cases": len(rows), "summary": summary, "errors": errors,
            "rows": rows, "usage": dict(jev.usage)}


def render_hooks_eval(report: dict) -> str:
    lines = [f"jrfc eval-hooks: {report['cases']} case(s), {report['model']}, score={report['score']}"]
    for kind, s in report["summary"].items():
        th = "  ".join(f"t={t}: P={v['precision']} R={v['recall']} (fp {v['fp']}, fn {v['fn']})"
                       for t, v in s["thresholds"].items())
        lat = s["latency_ms"]
        lines.append(f"  {kind:<5} {s['cases']:>3} case(s)  {th}")
        lines.append(f"        latency of {lat['requests']} Jev request(s): p50 {lat['p50']} ms, "
                     f"p95 {lat['p95']} ms, max {lat['max']} ms")
        acts = s.get("actions")
        if acts:
            lines.append("        actions (drafts as enforced): " + ", ".join(
                f"{a} {v['right']} right / {v['wrong']} wrong" for a, v in acts.items() if a != "missed")
                + f"; missed {len(acts['missed'])}" + (f" ({', '.join(acts['missed'])})" if acts["missed"] else ""))
    if report["errors"]:
        lines.append("  errors at t=0.5:")
        lines += [f"    {e['type']:<3} {e['case']:<28} {e['statement']:<13} p={e['p']}" for e in report["errors"]]
    u = report["usage"]
    lines.append(f"  jev: {u['requests']} request(s), {u['cached']} cached")
    return "\n".join(lines)
