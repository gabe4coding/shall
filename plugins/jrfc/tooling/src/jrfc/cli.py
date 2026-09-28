"""jrfc command line. Run `jrfc <command> -h` for details."""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import re
import sys
from pathlib import Path

from .artifact import build_artifact, detect_kind, read_source
from .config import load_config
from .corpus import check_against, load_corpus

EXIT_OK, EXIT_ERROR, EXIT_BLOCKING, EXIT_SERVICE = 0, 1, 2, 3


def _dump(data, path: str | None) -> None:
    text = json.dumps(data, indent=2, ensure_ascii=False)
    if path:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)


# ---------------------------------------------------------------- corpus


def cmd_lint(args, cfg) -> int:
    corpus = load_corpus(cfg)
    issues = [i for i in corpus.issues if args.all or i.layer == "local"]
    if args.against:
        issues += check_against(corpus, json.loads(Path(args.against).read_text(encoding="utf-8")))
    for issue in issues:
        if issue.severity == "error" or not args.quiet:
            print(issue)
    errors = sum(1 for i in issues if i.severity == "error")
    warnings = len(issues) - errors
    local = [r for r in corpus.rfcs.values() if r.layer == "local"]
    parent = f" (+ {len(corpus.rfcs) - len(local)} from {cfg.parent.name})" if cfg.parent else ""
    print(f"jrfc lint: {len(local)} local RFCs{parent}, {len(corpus.local_statements())} local statements, "
          f"{errors} error(s), {warnings} warning(s)", file=sys.stderr)
    return EXIT_ERROR if errors or (args.strict and warnings) else EXIT_OK


def cmd_build(args, cfg) -> int:
    from .index import build_index, check_index, write_index
    corpus = load_corpus(cfg)
    if corpus.errors:
        for issue in corpus.errors:
            print(issue)
        print("jrfc build: fix lint errors first", file=sys.stderr)
        return EXIT_ERROR
    index = build_index(corpus)
    if args.check:
        stale = check_index(index, cfg.index_dir)
        if stale:
            print(f"jrfc build --check: stale index files: {', '.join(stale)} — run `jrfc build`", file=sys.stderr)
            return EXIT_ERROR
        print("jrfc build --check: index is up to date", file=sys.stderr)
        return EXIT_OK
    import os
    for path in write_index(index, cfg.index_dir):
        print(f"wrote {os.path.relpath(path, Path.cwd())}")
    return EXIT_OK


TEMPLATE = """---
id: {id}
title: {title}
status: draft
domain: {domain}
artifacts: [diff, code]
languages: [any]
owner: {owner}
review_by: {review_by}
supersedes: []
summary: >
  TODO one or two sentences: what this standard covers.
applies_when: >
  TODO the concrete code, text or situation this standard governs (literal, matchable).
not_applies_when: >
  TODO what looks close but is out of scope.
---

# {id}: {title}

## Context

TODO why this standard exists; link incidents, ADRs or external references.

## Requirements

### {id}.1 TODO short title
TODO one requirement with exactly one level of RFC 2119 keyword (MUST, SHOULD or MAY).

- Applies when: TODO
- Enforcement: agent
"""


def cmd_new(args, cfg) -> int:
    corpus = load_corpus(cfg)
    prefix = cfg.prefix
    if prefix is None:
        print("this workspace has no `prefix:` in its jrfc.yaml; add one (e.g. prefix: BOOK)", file=sys.stderr)
        return EXIT_ERROR
    if args.domain not in corpus.domains:
        print(f"unknown domain '{args.domain}'. Known: {', '.join(sorted(corpus.domains))}", file=sys.stderr)
        return EXIT_ERROR
    used = [int(r.id.split("-")[1]) for r in corpus.rfcs.values() if r.layer == "local"]
    used += [int(m.group(1)) for p in cfg.corpus_dir.glob(f"{prefix}-*.md")
             if (m := re.match(rf"{prefix}-(\d{{4}})", p.name))]
    rid = f"{prefix}-{(max(used) + 1 if used else 1):04d}"
    cfg.corpus_dir.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", args.title.lower()).strip("-")
    path = cfg.corpus_dir / f"{rid}-{slug}.md"
    path.write_text(TEMPLATE.format(
        id=rid, title=args.title, domain=args.domain,
        owner=corpus.domains[args.domain].owner or "TODO",
        review_by=(dt.date.today() + dt.timedelta(days=180)).isoformat(),
    ), encoding="utf-8")
    import os
    print(os.path.relpath(path, Path.cwd()))
    return EXIT_OK


def cmd_show(args, cfg) -> int:
    corpus = load_corpus(cfg)
    for ident in args.ids:
        if "." in ident:
            found = corpus.statement(ident)
            if not found:
                print(f"{ident}: not found", file=sys.stderr)
                return EXIT_ERROR
            rfc, st = found
            if args.json:
                _dump({"id": st.id, "rfc": rfc.id, "title": st.title, "text": st.text, "level": st.level,
                       "status": rfc.status, "blocking": rfc.statement_blocking(st),
                       "applies_when": st.applies_when or rfc.applies_when,
                       "layer": rfc.layer, "source": corpus.source(rfc, st.line)}, None)
            else:
                print(f"{st.id} [{st.level}, {rfc.status}{', blocking' if rfc.statement_blocking(st) else ''}] {st.title}")
                print(f"  {st.text}")
                print(f"  Applies when: {st.applies_when or rfc.applies_when}")
                print(f"  Source: {corpus.source(rfc, st.line)}")
        else:
            rfc = corpus.rfcs.get(ident)
            if not rfc:
                print(f"{ident}: not found", file=sys.stderr)
                return EXIT_ERROR
            print(rfc.path.read_text(encoding="utf-8"))
    return EXIT_OK


def cmd_list(args, cfg) -> int:
    corpus = load_corpus(cfg)
    for rfc in sorted(corpus.rfcs.values(), key=lambda r: r.id):
        if args.domain and rfc.domain != args.domain:
            continue
        if args.status and rfc.status != args.status:
            continue
        layer = "" if rfc.layer == "local" else f"  [{rfc.layer}]"
        print(f"{rfc.id:<10} {rfc.status:<10} {rfc.domain:<14} {rfc.title}  ({len(rfc.statements)} statements){layer}")
    return EXIT_OK


def cmd_prefetch(args) -> int:
    """Download the tree-sitter grammars for the languages in this repository (CI caches them)."""
    from .codegraph import RepoIndex, treesitter_available
    if not treesitter_available():
        print("tree-sitter is not installed; verification uses keyword search only", file=sys.stderr)
        return EXIT_OK
    from tree_sitter_language_pack import cache_dir, detect_language_from_path, download
    langs = sorted({lang for f in RepoIndex(Path.cwd()).all_files() if (lang := detect_language_from_path(f))})
    count = download(langs) if langs else 0
    print(f"grammars for {', '.join(langs) or 'no language'} ({count} downloaded) in {cache_dir()}")
    return EXIT_OK


def cmd_catalog(args, cfg) -> int:
    from .index import build_index, render_catalog
    corpus = load_corpus(cfg)
    print(render_catalog(build_index(corpus, {layer.name for layer in cfg.layers})), end="")
    return EXIT_OK


def cmd_fetch(args, cfg) -> int:
    parent = cfg.parent
    if parent is None:
        print("no `extends:` in this workspace; nothing to fetch")
        return EXIT_OK
    p = parent.parent
    print(f"{parent.name} -> {p.root}" + (f" (commit {p.sha[:12]})" if p.sha else ""))
    return EXIT_OK


INIT_CONFIG = """# jrfc workspace: repository-specific standards on top of the organisation corpus.
# Local rules may add or tighten requirements; they must not weaken organisation rules
# (`jrfc conflicts --local` fails CI when one does).
prefix: {prefix}
extends:
{extends}
# settings (jev, selection, review) are inherited from the organisation corpus;
# override them here only when this repository needs it.
"""


def cmd_init(args) -> int:
    dot = Path.cwd() / ".jrfc"
    if (dot / "jrfc.yaml").exists():
        print(f"{dot / 'jrfc.yaml'} already exists", file=sys.stderr)
        return EXIT_ERROR
    if not re.fullmatch(r"[A-Z][A-Z0-9]{1,9}", args.prefix) or args.prefix == "JRFC":
        print("prefix must be 2-10 characters A-Z/0-9 and not JRFC (e.g. BOOK)", file=sys.stderr)
        return EXIT_ERROR
    if args.path:
        import os
        # stored relative to .jrfc/, where the config is resolved from
        extends = f"  path: {os.path.relpath(Path(args.path).resolve(), dot)}"
    else:
        extends = f"  repo: {args.repo}\n  ref: {args.ref}   # pin a tag or commit sha"
    (dot / "rfcs").mkdir(parents=True)
    (dot / "jrfc.yaml").write_text(INIT_CONFIG.format(prefix=args.prefix, extends=extends), encoding="utf-8")
    (dot / ".gitignore").write_text(".jrfc-cache/\n", encoding="utf-8")
    (dot / "rfcs" / ".gitkeep").write_text("", encoding="utf-8")
    print(f"created {dot}/ (jrfc.yaml, rfcs/, .gitignore). Next: jrfc fetch && jrfc new --domain <d> --title <t>")
    return EXIT_OK


# ---------------------------------------------------------------- selection and review


def _facts(cfg, corpus, artifact, index) -> dict:
    """known_effects per chunk (effects.py); indirect ones need the repository index."""
    if not cfg.get("selection.facts") or not corpus.effects:
        return {}
    from .effects import chunk_facts
    return chunk_facts(corpus.effects, artifact, index, int(cfg.get("selection.facts_depth")))


def _index(cfg, corpus, args):
    from .verify import repo_index, repo_root
    root = repo_root(Path(args.search_root) if getattr(args, "search_root", None) else None)
    return repo_index(cfg, corpus, root)


async def _select(args, cfg, corpus, jev, index=None):
    from .select import Selector, classify_document, selection_to_json
    name, raw = read_source(args.path, args.text)
    kind = args.kind or detect_kind(name, raw, inline_text=args.text is not None)
    extra = {}
    if kind == "document":
        kind, answer = await classify_document(jev, name, raw)
        extra["kind_classification"] = answer
    artifact = build_artifact(name, raw, kind, int(cfg.get("jev.max_chunk_chars")))
    statuses = cfg.get("selection.include_status") + (["draft"] if args.include_draft else [])
    facts = _facts(cfg, corpus, artifact, index)
    selector = Selector(cfg, corpus, jev, strategy=args.strategy, include_status=statuses, facts=facts)
    results = await selector.select(artifact)
    return artifact, selection_to_json(artifact, results, corpus, selector.strategy, cfg, jev, extra)


def _selection_summary(sel: dict) -> str:
    lines = [f"{sel['artifact']['source']} ({sel['artifact']['kind']}, {sel['artifact']['chunks']} chunk(s)) "
             f"-> {len(sel['applicable'])} applicable statement(s) [{sel['strategy']}, {sel['model']}]"]
    for a in sel["applicable"]:
        lines.append(f"  {a['id']:<14} p={a['p_max']:.2f}  {a['level']:<6} "
                     f"{'blocking' if a['blocking'] else a['status']:<9} {a['title']}")
    u = sel["usage"]
    lines.append(f"  jev: {u['requests']} request(s), {u['cached']} cached, {u['input_tokens']} input tokens")
    return "\n".join(lines)


def cmd_select(args, cfg) -> int:
    from .jev import Jev
    corpus = load_corpus(cfg)

    async def run():
        async with Jev(cfg, use_cache=not args.no_cache) as jev:
            return await _select(args, cfg, corpus, jev, _index(cfg, corpus, args))

    _, sel = asyncio.run(run())
    if args.out:
        _dump(sel, args.out)
    if args.json and not args.out:
        _dump(sel, None)
    else:
        print(_selection_summary(sel))
    return EXIT_OK


def _load_selection_artifact(args, cfg, selection: dict):
    name, raw = read_source(args.path, None)
    artifact = build_artifact(name, raw, selection["artifact"]["kind"], int(cfg.get("jev.max_chunk_chars")))
    if artifact.sha != selection["artifact"]["sha"]:
        raise SystemExit("jrfc: artifact changed since selection (sha mismatch); run select again")
    return artifact


def _write_outputs(cfg, out_dir: Path, artifact, selection, findings, dropped, fmt: str,
                   health: dict | None = None) -> int:
    from .review import render_github, render_markdown
    out_dir.mkdir(parents=True, exist_ok=True)
    _dump({"findings": findings, "dropped": dropped}, str(out_dir / "findings.json"))
    if health is not None:
        _dump(health, str(out_dir / "health.json"))
    md = render_markdown(artifact, selection, findings, dropped, health)
    (out_dir / "review.md").write_text(md, encoding="utf-8")
    if fmt == "github":
        _dump(render_github(artifact, selection, findings, dropped, health), str(out_dir / "github-review.json"))
    print(md)
    return sum(1 for f in findings if f["blocking"])


def cmd_bundle(args, cfg) -> int:
    from .review import write_bundle
    corpus = load_corpus(cfg)
    selection = json.loads(Path(args.selection).read_text(encoding="utf-8"))
    artifact = _load_selection_artifact(args, cfg, selection)
    print(write_bundle(corpus, artifact, selection, Path(args.out)))
    return EXIT_OK


def cmd_validate(args, cfg) -> int:
    from .review import validate_findings
    corpus = load_corpus(cfg)
    selection = json.loads(Path(args.selection).read_text(encoding="utf-8"))
    artifact = _load_selection_artifact(args, cfg, selection)
    raw = json.loads(Path(args.findings).read_text(encoding="utf-8"))
    raw = raw.get("findings", raw) if isinstance(raw, dict) else raw
    findings, dropped = validate_findings(corpus, artifact, selection, raw, int(cfg.get("review.max_comments")))
    blocking = _write_outputs(cfg, Path(args.out_dir), artifact, selection, findings, dropped, args.format)
    return EXIT_BLOCKING if (blocking and args.fail_on_blocking) else EXIT_OK


def cmd_review(args, cfg) -> int:
    from .jev import Jev
    from .review import answer_cache, run_agents, validate_findings
    from .verify import verify_findings
    corpus = load_corpus(cfg)
    out_dir = Path(args.out_dir)
    verify = cfg.get("review.verify") and not args.no_verify
    # incremental re-review: unchanged chunks and unchanged evidence reuse earlier answers
    cache = answer_cache(cfg, enabled=not args.no_cache)

    async def run():
        async with Jev(cfg, use_cache=not args.no_cache) as jev:
            index = _index(cfg, corpus, args)
            artifact, selection = await _select(args, cfg, corpus, jev, index)
            _dump(selection, str(out_dir / "selection.json"))
            print(_selection_summary(selection), file=sys.stderr)
            if args.dry_run:
                return artifact, selection, [], [], {"agent_calls": 0}
            raw, stats = await run_agents(cfg, corpus, artifact, selection, out_dir / "prompts", cache)
            _dump({"findings": raw, "stats": stats}, str(out_dir / "findings.raw.json"))
            findings, dropped = validate_findings(corpus, artifact, selection, raw,
                                                  int(cfg.get("review.max_comments")))
            if verify and findings:
                findings, refuted, vstats = await verify_findings(cfg, corpus, artifact, jev, findings,
                                                                  index=index, cache=cache)
                dropped += refuted
                stats["verification"] = vstats
                stats["cost_usd"] = round(stats["cost_usd"] + vstats["cost_usd"], 6)
            stats["codegraph_events"] = list(index.events)
            return artifact, selection, findings, dropped, stats

    try:
        artifact, selection, findings, dropped, stats = asyncio.run(run())
    finally:
        cache.save()  # also after a failure: answers already paid for are kept
    if args.dry_run:
        from .review import write_bundle
        print(write_bundle(corpus, artifact, selection, out_dir / "bundle.md"))
        return EXIT_OK
    for err in stats.get("errors", []):
        print(f"jrfc review: agent error on {err['chunk']}: {err['error'][:300]}", file=sys.stderr)
    from .health import build_health
    health = build_health(cfg, selection, stats, findings, dropped, stats.get("codegraph_events", []))
    blocking = _write_outputs(cfg, out_dir, artifact, selection, findings, dropped, args.format, health)
    for w in health["warnings"]:
        print(f"jrfc review: health: {w}", file=sys.stderr)
    v = stats.get("verification")
    vtext = (f", verified {v['verified']} ({v['confirmed']} confirmed, {v['refuted']} refuted, "
             f"{v['unknown']} unknown)") if v else ""
    reused = stats.get("reused", 0) + (v or {}).get("reused", 0)
    rtext = f", {reused} answer(s) reused from earlier runs" if reused else ""
    print(f"jrfc review: {stats['agent_calls']} review call(s){vtext}{rtext}, ${stats.get('cost_usd', 0):.4f}, "
          f"outputs in {out_dir}", file=sys.stderr)
    if stats.get("errors"):
        return EXIT_ERROR
    return EXIT_BLOCKING if (blocking and args.fail_on_blocking) else EXIT_OK


def cmd_verify(args, cfg) -> int:
    """Verify already-validated findings (in-session flow: bundle -> agent -> validate -> verify)."""
    from .jev import Jev
    from .verify import verify_findings
    corpus = load_corpus(cfg)
    selection = json.loads(Path(args.selection).read_text(encoding="utf-8"))
    artifact = _load_selection_artifact(args, cfg, selection)
    data = json.loads(Path(args.findings).read_text(encoding="utf-8"))

    async def run():
        async with Jev(cfg) as jev:
            return await verify_findings(cfg, corpus, artifact, jev, data["findings"],
                                         Path(args.search_root) if args.search_root else None)

    findings, refuted, stats = asyncio.run(run())
    blocking = _write_outputs(cfg, Path(args.out_dir), artifact, selection, findings,
                              data.get("dropped", []) + refuted, args.format)
    print(f"jrfc verify: {stats}", file=sys.stderr)
    return EXIT_BLOCKING if (blocking and args.fail_on_blocking) else EXIT_OK


def cmd_publish(args, cfg) -> int:
    import os
    from .publish import publish
    repo = args.repo or os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        raise SystemExit("jrfc publish: pass --repo owner/name or set GITHUB_REPOSITORY")
    out_dir = Path(args.dir)
    review = json.loads((out_dir / "github-review.json").read_text(encoding="utf-8"))
    plan = publish(review, repo, args.pr, args.dry_run)
    _dump(plan.to_json(), str(out_dir / "publish-plan.json"))
    # Threads resolved by a person while the finding is still reported: feedback labels
    # for tuning selection thresholds and statement wording.
    _dump([{"key": t.key, "path": t.path, "resolved_by": t.resolved_by} for t in plan.dismissed],
          str(out_dir / "dismissed.json"))
    verb = "would" if args.dry_run else "did"
    p = plan.to_json()
    print(f"jrfc publish ({repo}#{args.pr}): {verb} post {len(p['new'])} new comment(s), "
          f"keep {len(p['kept'])}, resolve {len(p['resolve'])}, reopen {len(p['unresolve'])}, "
          f"{p['summary']} summary; {len(p['dismissed'])} dismissed by reviewers", file=sys.stderr)
    return EXIT_OK


def cmd_conflicts(args, cfg) -> int:
    from .conflicts import FAILING, find_conflicts, find_local_conflicts
    from .jev import Jev
    if bool(args.file) == bool(args.local):
        raise SystemExit("jrfc conflicts: give an RFC file or --local")
    corpus = load_corpus(cfg)

    async def run():
        async with Jev(cfg) as jev:
            if args.local:
                return await find_local_conflicts(cfg, corpus, jev, args.all_domains, args.min_p)
            return await find_conflicts(cfg, corpus, jev, Path(args.file), args.all_domains, args.min_p)

    found = asyncio.run(run())
    if args.json:
        _dump(found, None)
    else:
        if not found:
            print("no duplicates, weakenings, conflicts or overlaps above threshold")
        for f in found:
            mark = "FAIL" if f["relation"] in FAILING else "info"
            print(f"[{mark}] {f['new']} ~ {f['existing']}: {f['relation']} (p={f['p']:.2f})\n"
                  f"    {f['existing_text']}")
    return EXIT_ERROR if any(f["relation"] in FAILING for f in found) else EXIT_OK


def cmd_eval(args, cfg) -> int:
    from .evaluate import render_eval, run_eval
    from .jev import Jev
    corpus = load_corpus(cfg)
    strategies = ["layered", "flat"] if args.strategy == "both" else [args.strategy]

    async def run():
        async with Jev(cfg) as jev:
            return await run_eval(cfg, corpus, jev, Path(args.labels), strategies, facts=not args.no_facts)

    report = asyncio.run(run())
    if args.out:
        _dump(report, args.out)
    print(render_eval(report))
    return EXIT_OK


def cmd_eval_verify(args, cfg) -> int:
    from .evaluate import render_verify_eval, run_verify_eval
    from .jev import Jev
    corpus = load_corpus(cfg)
    models = [m for m in args.models.split(",") if m]
    retrievals = ["keyword", "treesitter"] if args.retrieval == "all" else [args.retrieval]

    async def run():
        async with Jev(cfg) as jev:
            return await run_verify_eval(cfg, corpus, jev, Path(args.cases), models, retrievals)

    report = asyncio.run(run())
    if args.out:
        _dump(report, args.out)
    print(render_verify_eval(report))
    return EXIT_OK


# ---------------------------------------------------------------- parser


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="jrfc", description=(
        "jrfc: RFC-2119 engineering standards for humans and agents. "
        "Corpus: lint/build/new/show/list. Review: select (Jev) -> agent -> validate."))
    p.add_argument("--config", help="path to jrfc.yaml (default: search upwards, or $JRFC_CONFIG)")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("lint", help="check RFC format, IDs, levels and references")
    s.add_argument("--against", help="previous index.json (e.g. from the base branch) to check ID stability")
    s.add_argument("--strict", action="store_true", help="fail on warnings too")
    s.add_argument("--quiet", action="store_true", help="print errors only")
    s.add_argument("--all", action="store_true", help="also report issues of the extended corpus")
    s.set_defaults(fn=cmd_lint)

    s = sub.add_parser("build", help="build the deterministic index (index.json, catalog.md)")
    s.add_argument("--check", action="store_true", help="fail if the committed index is stale (CI)")
    s.set_defaults(fn=cmd_build)

    s = sub.add_parser("init", help="create .jrfc/ for repository-specific standards")
    s.add_argument("--prefix", required=True, help="id prefix for this repository, e.g. BOOK")
    g = s.add_mutually_exclusive_group(required=True)
    g.add_argument("--repo", help="organisation corpus repo, owner/name")
    g.add_argument("--path", help="organisation corpus as a local path")
    s.add_argument("--ref", default="main", help="tag or commit sha to pin (with --repo)")
    s.set_defaults(fn=cmd_init, no_config=True)

    s = sub.add_parser("fetch", help="download (or --update) the extended corpus into the cache")
    s.add_argument("--update", action="store_true", help="re-fetch even if cached (for branch refs)")
    s.set_defaults(fn=cmd_fetch)

    s = sub.add_parser("prefetch", help="download tree-sitter grammars for this repository's languages (CI)")
    s.set_defaults(fn=cmd_prefetch, no_config=True)

    s = sub.add_parser("catalog", help="print the merged catalog (organisation + local)")
    s.set_defaults(fn=cmd_catalog)

    s = sub.add_parser("new", help="scaffold a draft RFC with the next free id")
    s.add_argument("--domain", required=True)
    s.add_argument("--title", required=True)
    s.set_defaults(fn=cmd_new)

    s = sub.add_parser("show", help="print an RFC (JRFC-0003) or a statement (JRFC-0003.1)")
    s.add_argument("ids", nargs="+")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_show)

    s = sub.add_parser("list", help="list RFCs")
    s.add_argument("--domain")
    s.add_argument("--status")
    s.set_defaults(fn=cmd_list)

    def artifact_args(s):
        s.add_argument("path", nargs="?", help="diff, spec, doc or code file ('-' for stdin)")
        s.add_argument("--text", help="inline text instead of a file (kind: task)")
        s.add_argument("--kind", choices=["diff", "code", "spec", "doc", "task"], help="skip kind detection")
        s.add_argument("--strategy", choices=["layered", "flat"])
        s.add_argument("--include-draft", action="store_true", help="also consider draft RFCs")
        s.add_argument("--no-cache", action="store_true", help="ignore the Jev answer cache")
        s.add_argument("--search-root", help="repository for facts and verification evidence (default: git toplevel)")

    s = sub.add_parser("select", help="find the statements that apply to an artifact (Jev)")
    artifact_args(s)
    s.add_argument("--out", help="write selection JSON here")
    s.add_argument("--json", action="store_true", help="print selection JSON")
    s.set_defaults(fn=cmd_select)

    s = sub.add_parser("review", help="select + agent review + validate + report")
    artifact_args(s)
    s.add_argument("--out-dir", default=".jrfc-out")
    s.add_argument("--format", choices=["markdown", "github"], default="markdown")
    s.add_argument("--fail-on-blocking", action="store_true", help=f"exit {EXIT_BLOCKING} on blocking findings")
    s.add_argument("--dry-run", action="store_true", help="select only and write bundle.md, no agent call")
    s.add_argument("--no-verify", action="store_true", help="skip verification of blocking findings")
    s.set_defaults(fn=cmd_review)

    s = sub.add_parser("verify", help="verify validated findings against repository evidence (Jev + agent)")
    s.add_argument("findings", help="findings.json written by `jrfc validate`")
    s.add_argument("path")
    s.add_argument("--selection", required=True)
    s.add_argument("--out-dir", default=".jrfc-out")
    s.add_argument("--format", choices=["markdown", "github"], default="markdown")
    s.add_argument("--search-root")
    s.add_argument("--fail-on-blocking", action="store_true")
    s.set_defaults(fn=cmd_verify)

    s = sub.add_parser("bundle", help="write the review bundle for an in-session agent")
    s.add_argument("path")
    s.add_argument("--selection", required=True)
    s.add_argument("--out", default=".jrfc-out/bundle.md")
    s.set_defaults(fn=cmd_bundle)

    s = sub.add_parser("validate", help="validate agent findings and write reports")
    s.add_argument("findings")
    s.add_argument("path")
    s.add_argument("--selection", required=True)
    s.add_argument("--out-dir", default=".jrfc-out")
    s.add_argument("--format", choices=["markdown", "github"], default="markdown")
    s.add_argument("--fail-on-blocking", action="store_true")
    s.set_defaults(fn=cmd_validate)

    s = sub.add_parser("publish", help="post a review to a GitHub PR idempotently (via gh)")
    s.add_argument("--pr", type=int, required=True)
    s.add_argument("--repo", help="owner/name (default: $GITHUB_REPOSITORY)")
    s.add_argument("--dir", default=".jrfc-out/pr", help="review output dir with github-review.json")
    s.add_argument("--dry-run", action="store_true", help="read the PR and write the plan, change nothing")
    s.set_defaults(fn=cmd_publish)

    s = sub.add_parser("conflicts", help="duplicate / weakens / conflict / overlap checks (Jev)")
    s.add_argument("file", nargs="?", help="a (draft) RFC to compare with the corpus")
    s.add_argument("--local", action="store_true",
                   help="compare every local statement with the extended corpus (app-repo CI)")
    s.add_argument("--all-domains", action="store_true")
    s.add_argument("--min-p", type=float, default=None,
                   help="fail threshold (default: conflicts.fail_threshold in jrfc.yaml)")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_conflicts)

    s = sub.add_parser("eval-verify", help="measure verification verdicts and evidence recall on fixture repos")
    s.add_argument("--cases", default="eval/verify")
    s.add_argument("--models", default="claude-sonnet-5", help="comma-separated verifier models")
    s.add_argument("--retrieval", choices=["keyword", "treesitter", "all"], default="all")
    s.add_argument("--out")
    s.set_defaults(fn=cmd_eval_verify)

    s = sub.add_parser("eval", help="measure selection recall/precision on labelled cases")
    s.add_argument("--labels", default="eval/labels.yaml")
    s.add_argument("--strategy", choices=["layered", "flat", "both"], default="both")
    s.add_argument("--no-facts", action="store_true", help="leave known_effects out of the Jev state (A/B)")
    s.add_argument("--out")
    s.set_defaults(fn=cmd_eval)
    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if getattr(args, "path", "x") is None and getattr(args, "text", None) is None and args.cmd in ("select", "review"):
        raise SystemExit("jrfc: give a file path, '-' for stdin, or --text")
    if getattr(args, "no_config", False):
        sys.exit(args.fn(args))
    cfg = load_config(args.config, update=getattr(args, "update", False))
    if (cfg.path and cfg.path.parent.name == ".jrfc" and (cfg.path.parent.parent / "jrfc.yaml").is_file()
            and args.cmd in ("lint", "build", "new", "list")):
        print("note: using .jrfc/ (this repository's own rules); "
              "pass --config jrfc.yaml for the corpus defined at the root", file=sys.stderr)
    from typesafe_sdk import TypeSafeError
    try:
        sys.exit(args.fn(args, cfg))
    except TypeSafeError as err:
        # distinct exit code: CI can tell "the service failed" from "the change is blocked"
        print(f"jrfc: Jev (TypeSafe) request failed after retries: {str(err)[:300]}", file=sys.stderr)
        sys.exit(EXIT_SERVICE)


if __name__ == "__main__":
    main()
