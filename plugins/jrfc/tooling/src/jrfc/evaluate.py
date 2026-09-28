"""Selection evaluation against hand-labelled cases (eval/labels.yaml)."""

from __future__ import annotations

import asyncio
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


async def _run_case(cfg: Config, corpus: Corpus, jev: Jev, base: Path, case: dict, strategy: str) -> dict:
    name, raw = read_source(str(base / case["file"]), None)
    kind = case.get("kind") or detect_kind(name, raw)
    if kind == "document":
        kind, _ = await classify_document(jev, name, raw)
    artifact = build_artifact(name, raw, kind, int(cfg.get("jev.max_chunk_chars")))
    results = await Selector(cfg, corpus, jev, strategy=strategy).select(artifact)
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
        "recall": recall, "precision": precision, "p_max": p_max,
    }


async def run_eval(cfg: Config, corpus: Corpus, jev: Jev, labels_path: Path, strategies: list[str]) -> dict:
    labels = yaml.safe_load(labels_path.read_text(encoding="utf-8"))
    base = labels_path.parent
    report = {}
    for strategy in strategies:
        cases = await asyncio.gather(*(_run_case(cfg, corpus, jev, base, c, strategy) for c in labels["cases"]))
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
            "cases": cases, "sweep": sweep,
        }
    report["usage"] = dict(jev.usage)
    return report


def render_eval(report: dict) -> str:
    out = []
    for strategy, r in report.items():
        if strategy == "usage":
            continue
        out.append(f"## strategy: {strategy}")
        out.append(f"micro recall {r['micro_recall']:.2f} · micro precision {r['micro_precision']:.2f} "
                   f"· {r['selected']} selected / {r['expected']} expected")
        out.append("")
        out.append("| case | kind | recall | precision | missed | extra |")
        out.append("|---|---|---|---|---|---|")
        for c in r["cases"]:
            out.append(f"| {c['case']} | {c['kind']} | {c['recall']:.2f} | {c['precision']:.2f} | "
                       f"{', '.join(c['missed']) or '-'} | {', '.join(c['extra']) or '-'} |")
        out.append("")
        out.append("statement-threshold sweep: " + " · ".join(
            f"t={s['threshold']:.1f} R={s['recall']:.2f} P={s['precision']:.2f}" for s in r["sweep"]))
        out.append("")
    out.append(f"Jev usage: {report['usage']}")
    return "\n".join(out)
