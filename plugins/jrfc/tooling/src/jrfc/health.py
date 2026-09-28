"""Run health: make the silent failures of a review visible.

A missed rule, a file that could not be parsed or evidence that was not found all look the
same on the PR: fewer comments. health.json records them per run, and the summary shows the
warnings, so a quiet review can be told apart from a blind one.
"""

from __future__ import annotations

from .config import Config

EVENT_TEXT = {
    "parse_error": "file(s) could not be parsed (less evidence and fewer facts)",
    "grammar_missing": "language(s) without a cached grammar (run `jrfc prefetch`)",
    "grammar_download": "grammar(s) downloaded during the run (a network call; `jrfc prefetch` avoids it)",
    "tags_query_error": "tags query error(s) (definitions of that language are partly invisible)",
}


def near_threshold(cfg: Config, selection: dict) -> list[dict]:
    """Statements that scored just below the statement threshold: the likeliest silent misses."""
    th = float(cfg.get("selection.thresholds")["statement"])
    margin = float(cfg.get("selection.near_margin", 0.15))
    out = []
    for c in selection["chunks"]:
        for sid, p in c["statements"].items():
            if th - margin <= p < th:
                out.append({"id": sid, "chunk": c["id"], "path": c["path"], "p": round(p, 2)})
    return sorted(out, key=lambda x: -x["p"])


def build_health(cfg: Config, selection: dict, stats: dict, findings: list[dict], dropped: list[dict],
                 events: list[dict]) -> dict:
    chunks = selection["chunks"]
    near = near_threshold(cfg, selection)
    v = stats.get("verification") or {}
    verified = int(v.get("verified", 0))
    unknown = int(v.get("unknown", 0))
    counts: dict[str, list] = {}
    for e in events:
        counts.setdefault(e["kind"], []).append(e.get("path") or e.get("lang"))
    health = {
        "selection": {
            "chunks": len(chunks),
            "eligible": sum(c.get("eligible", 0) for c in chunks),
            "selected": sum(len(c["selected"]) for c in chunks),
            "chunks_with_facts": sum(1 for c in chunks if c.get("known_effects")),
            "facts": sum(len(c.get("known_effects") or []) for c in chunks),
            "near_threshold": near,
        },
        "review": {
            "agent_calls": stats.get("agent_calls", 0),
            "reused": stats.get("reused", 0) + int(v.get("reused", 0)),   # incremental re-review
            "agent_errors": len(stats.get("errors", [])),
            "findings": len(findings),
            "blocking": sum(1 for f in findings if f["blocking"]),
            "dropped": len(dropped),
        },
        "verification": {
            "verified": verified,
            "confirmed": int(v.get("confirmed", 0)),
            "refuted": int(v.get("refuted", 0)),
            "unknown": unknown,
            "unknown_rate": round(unknown / verified, 2) if verified else None,
            "downgraded": int(v.get("downgraded", 0)),
        },
        "codegraph": {kind: sorted(set(map(str, items))) for kind, items in counts.items()},
    }
    warnings = []
    if health["review"]["agent_errors"]:
        warnings.append(f"{health['review']['agent_errors']} review call(s) failed: those chunks were not reviewed")
    if health["verification"]["downgraded"]:
        warnings.append(f"{health['verification']['downgraded']} blocking finding(s) downgraded to advisory: "
                        "their evidence was not found")
    if verified >= 2 and unknown / verified >= 0.5:
        warnings.append(f"verification could not decide {unknown} of {verified} finding(s)")
    for kind, items in health["codegraph"].items():
        warnings.append(f"{len(items)} {EVENT_TEXT.get(kind, kind)}: {', '.join(items[:5])}")
    # near-threshold statements are information, not a warning: almost every PR has some
    health["warnings"] = warnings
    return health


def render_health(health: dict) -> list[str]:
    s, v = health["selection"], health["verification"]
    near = s["near_threshold"]
    line = (f"Health: {s['eligible']} statement(s) checked, {s['selected']} selected, {s['facts']} known effect(s)"
            + (f", {len(near)} just below the threshold ({', '.join(n['id'] for n in near[:3])})" if near else "")
            + (f", {health['review']['reused']} answer(s) reused from earlier runs" if health["review"].get("reused") else "")
            + (f" · verification {v['confirmed']} confirmed / {v['refuted']} refuted / {v['unknown']} unknown"
               if v["verified"] else ""))
    if not health["warnings"]:
        return [f"<sub>{line} · no warnings</sub>", ""]
    return ["<details><summary>⚠️ " + f"{len(health['warnings'])} health warning(s)" + "</summary>", "",
            line, "", *[f"- {w}" for w in health["warnings"]], "", "</details>", ""]
