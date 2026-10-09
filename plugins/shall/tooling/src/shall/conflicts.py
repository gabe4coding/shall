"""Authoring aid and layering guard: compare statements pairwise with Jev.

- `shall conflicts FILE`: a (draft) RFC against the rest of the corpus.
- `shall conflicts --local`: every local statement against the extended (organisation)
  corpus. Local rules may add or tighten requirements; `duplicate`, `conflict` and
  `weakens` fail, because a repository must not restate or relax organisation rules.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from .config import Config
from .corpus import Corpus, Issue, Rfc, Statement, parse_rfc
from .jev import Jev, choice, noul

RELATION = {
    "duplicate": "Both statements require the same thing, or the new statement repeats the existing "
                 "requirement for a narrower case that the existing statement already covers.",
    "weakens": "The new statement relaxes, delays or makes optional something the existing statement "
               "requires, or allows something the existing statement forbids.",
    "conflict": "Following one statement would violate the other, or they set incompatible rules or values.",
    "overlap": "They govern the same situation and partly repeat, extend or tighten each other "
               "without relaxing either one.",
    "unrelated": "They govern different things; there is no meaningful overlap.",
}
FAILING = ("duplicate", "weakens", "conflict")


async def compare(jev: Jev, new: list[tuple[Rfc, Statement]], existing: list[tuple[Rfc, Statement]],
                  fail_p: float, report_p: float) -> list[dict]:
    """One small request per pair (packing the corpus into one state and pointing at
    `existing[i]` failed badly: indirection + distracting state).

    The Choice names the relation, but it is relative: when a pair is both a conflict and a
    weakening, the mass splits (0.51 / 0.49) and neither class passes a threshold. So the
    failing classes are summed, and two absolute Nouls on the same state act as the gate.
    """
    questions = {
        "relation": choice(
            "How does the rule in `new_statement` relate to the rule in `existing_statement`?", RELATION),
        "permits": noul("Does `new_statement` allow or permit something that `existing_statement` forbids?"),
        "violates": noul("Would someone who does what `new_statement` permits or requires "
                         "violate `existing_statement`?"),
    }
    pairs = [(n, e) for n in new for e in existing]
    answers = await jev.gather(
        jev.ask({"new_statement": n[1].text, "existing_statement": e[1].text}, questions) for n, e in pairs
    )
    findings = []
    for ((_, ns), (erfc, es)), ans in zip(pairs, answers):
        probs = ans["relation"]["probabilities"]
        gate = max(sum(probs.get(k, 0.0) for k in FAILING), ans["permits"]["p"], ans["violates"]["p"])
        if gate >= fail_p:
            relation = max(FAILING, key=lambda k: probs.get(k, 0.0))
            p = gate
        else:
            # below the gate: report as info when the pair is related at all, using the
            # summed probability of every non-"unrelated" option (JTOOL-0001.3)
            p = 1.0 - probs.get("unrelated", 0.0)
            if p < report_p:
                continue
            relation = "overlap"
        findings.append({"new": ns.id, "existing": es.id, "relation": relation, "p": round(p, 4),
                         "permits": ans["permits"]["p"], "violates": ans["violates"]["p"],
                         "probabilities": probs,
                         "existing_text": es.text, "existing_status": erfc.status,
                         "existing_layer": erfc.layer})
    return sorted(findings, key=lambda f: (f["relation"] not in FAILING, -f["p"]))


def _scope(corpus: Corpus, cfg: Config, domains: set[str], all_domains: bool, exclude_rfc: str | None,
           layer: str | None) -> list[tuple[Rfc, Statement]]:
    always = set(cfg.get("selection.always_domains") or [])
    excluded = set(cfg.get("conflicts.exclude_domains") or [])
    return [
        (r, s) for r, s in corpus.statements()
        if r.id != exclude_rfc and r.status != "deprecated" and r.domain not in excluded
        and (layer is None or r.layer == layer)
        and (all_domains or r.domain in domains or r.domain in always)
    ]


def _thresholds(cfg: Config, fail_p: float | None) -> tuple[float, float]:
    return (fail_p if fail_p is not None else float(cfg.get("conflicts.fail_threshold")),
            float(cfg.get("conflicts.report_threshold")))


async def find_conflicts(cfg: Config, corpus: Corpus, jev: Jev, path: Path, all_domains: bool,
                         fail_p: float | None = None) -> list[dict]:
    issues: list[Issue] = []
    draft = parse_rfc(path.resolve(), cfg.root, issues, cfg.prefix or "JRFC")
    if draft is None:
        raise SystemExit("\n".join(str(i) for i in issues))
    existing = _scope(corpus, cfg, {draft.domain}, all_domains, draft.id, None)
    return await compare(jev, [(draft, s) for s in draft.statements], existing, *_thresholds(cfg, fail_p))


async def find_local_conflicts(cfg: Config, corpus: Corpus, jev: Jev, all_domains: bool = True,
                               fail_p: float | None = None) -> list[dict]:
    if cfg.parent is None:
        raise SystemExit("shall conflicts --local: this workspace does not extend another corpus")
    local = [(r, s) for r, s in corpus.local_statements() if r.status != "deprecated"]
    if not local:
        return []
    # always all domains: a local rule in a local domain can still relax an organisation
    # rule elsewhere ("booking events MAY carry the guest email" vs the PII rule)
    existing = _scope(corpus, cfg, set(), True, None, cfg.parent.name)
    return await compare(jev, local, existing, *_thresholds(cfg, fail_p))
