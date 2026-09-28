"""Applicability selection with Jev.

Code prunes what it can decide exactly (status, artifact kind, language, linter rules).
Jev answers only semantic questions, one Noul per candidate, so each answer is an
absolute "does this apply" and several candidates can apply at once.

flat:    statement Nouls only (default). Questions are packed into as many requests as the
         token budget needs, so cost grows linearly: ~$0.003 per case at ~540 statements.
layered: domain Nouls -> RFC Nouls -> statement Nouls. Fewer tokens, but a domain or RFC
         whose description does not cover all of its rules silently drops them; at ~540
         statements it lost 11 points of recall (eval/scale).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from .artifact import Artifact, Chunk
from .config import Config
from .corpus import Corpus, Rfc, Statement
from .jev import Jev, choice, noul

APPLIES_NOTE = (
    "Answer yes when the content contains the kind of code or text this is about, "
    "whether or not the content already follows the rule. Answer no when nothing in "
    "the content is of that kind."
)
# A task is planned work: nothing exists yet, so ask about the code the work will produce.
TASK_NOTE = (
    "The `content` describes work that is about to be done. Answer yes when doing that "
    "work will very likely involve writing the kind of code this is about. Answer no when "
    "the work does not need it."
)


def _note(kind: str) -> str:
    return TASK_NOTE if kind == "task" else APPLIES_NOTE


def domain_question(d, kind: str = "diff"):
    verb = "Will the work described in the `content` touch" if kind == "task" else "Does the `content` touch"
    return noul(
        f"{verb} this engineering area: {d.title}? {d.description}",
        true=d.applies_when,
        false=d.not_applies_when,
    )


def rfc_question(rfc: Rfc, kind: str = "diff"):
    what = "the work described in the `content`" if kind == "task" else "anything in the `content`"
    return noul(
        f"Does the engineering standard \"{rfc.title}\" govern {what}? "
        f"The standard covers: {rfc.summary} {_note(kind)}",
        true=rfc.applies_when,
        false=rfc.not_applies_when,
    )


def statement_question(rfc: Rfc, st: Statement, kind: str = "diff"):
    lead = ("Will the work described in the `content` have to follow this requirement?"
            if kind == "task" else "Is this requirement relevant to check against the `content`?")
    return noul(
        f"{lead} Requirement: \"{st.text}\" {_note(kind)}",
        true=st.applies_when or rfc.applies_when,
        false=st.not_applies_when or rfc.not_applies_when,
    )


DOC_KIND_QUESTION = choice(
    "What kind of document is the `content`?",
    {
        "spec": "A technical design document that proposes how to build or change a system "
                "(architecture, components, APIs, data, rollout).",
        "doc": "Any other document: README, guide, runbook, incident report, meeting notes, "
               "product brief, or an engineering standard.",
    },
)


async def classify_document(jev: Jev, name: str, raw: str) -> tuple[str, dict]:
    head = raw[:12000]
    ans = await jev.ask({"file": name, "content": head}, {"kind": DOC_KIND_QUESTION})
    return ans["kind"]["choice"], ans["kind"]


@dataclass
class ChunkSelection:
    chunk: Chunk
    domains: dict[str, float] = field(default_factory=dict)
    rfcs: dict[str, float] = field(default_factory=dict)
    statements: dict[str, float] = field(default_factory=dict)
    selected: list[str] = field(default_factory=list)


class Selector:
    def __init__(self, cfg: Config, corpus: Corpus, jev: Jev, strategy: str | None = None,
                 include_status: list[str] | None = None):
        self.cfg = cfg
        self.corpus = corpus
        self.jev = jev
        self.strategy = strategy or cfg.get("selection.strategy")
        self.th = cfg.get("selection.thresholds")
        self.always = set(cfg.get("selection.always_domains") or [])
        self.status = set(include_status or cfg.get("selection.include_status"))

    def eligible(self, chunk: Chunk) -> list[tuple[Rfc, Statement]]:
        """Deterministic prefilter: everything code can decide exactly."""
        out = []
        for rfc, st in self.corpus.statements():
            if rfc.status not in self.status:
                continue
            kinds = set(st.artifacts or rfc.artifacts)
            # a task will produce code, so it is checked against code-level statements
            if (chunk.kind == "task" and not kinds & {"diff", "code"}) or \
                    (chunk.kind != "task" and chunk.kind not in kinds):
                continue
            if "any" not in rfc.languages and chunk.language not in rfc.languages and chunk.kind != "task":
                continue
            if st.enforcement == "linter":
                continue  # mechanically checkable: the linter owns it, not the agent
            out.append((rfc, st))
        return out

    async def select_chunk(self, chunk: Chunk) -> ChunkSelection:
        sel = ChunkSelection(chunk=chunk)
        cands = self.eligible(chunk)
        if not cands:
            return sel
        state = chunk.state()
        if self.strategy == "layered":
            domain_ids = sorted({r.domain for r, _ in cands})
            ans = await self.jev.ask(state, {d: domain_question(self.corpus.domains[d], chunk.kind) for d in domain_ids})
            sel.domains = {d: ans[d]["p"] for d in domain_ids}
            kept_domains = {d for d, p in sel.domains.items() if p >= self.th["domain"] or d in self.always}
            rfcs = sorted({r.id: r for r, _ in cands if r.domain in kept_domains}.values(), key=lambda r: r.id)
            ans = await self.jev.ask(state, {r.id: rfc_question(r, chunk.kind) for r in rfcs})
            sel.rfcs = {r.id: ans[r.id]["p"] for r in rfcs}
            kept_rfcs = {rid for rid, p in sel.rfcs.items() if p >= self.th["rfc"]}
            cands = [(r, s) for r, s in cands if r.id in kept_rfcs]
        ans = await self.jev.ask(state, {s.id: statement_question(r, s, chunk.kind) for r, s in cands})
        sel.statements = {s.id: ans[s.id]["p"] for _, s in cands}
        sel.selected = sorted(sid for sid, p in sel.statements.items() if p >= self.th["statement"])
        return sel

    async def select(self, artifact: Artifact) -> list[ChunkSelection]:
        return list(await self.jev.gather(self.select_chunk(c) for c in artifact.chunks))


def selection_to_json(artifact: Artifact, results: list[ChunkSelection], corpus: Corpus,
                      strategy: str, cfg: Config, jev: Jev, extra: dict | None = None) -> dict:
    applicable: dict[str, dict] = {}
    for r in results:
        for sid in r.selected:
            entry = applicable.setdefault(sid, {"id": sid, "p_max": 0.0, "chunks": []})
            entry["p_max"] = max(entry["p_max"], r.statements[sid])
            entry["chunks"].append(r.chunk.id)
    for sid, entry in applicable.items():
        rfc, st = corpus.statement(sid)
        entry.update({"rfc": rfc.id, "title": st.title, "level": st.level,
                      "blocking": rfc.statement_blocking(st), "status": rfc.status})
    return {
        "artifact": {"source": artifact.source, "kind": artifact.kind, "sha": artifact.sha,
                     "chunks": len(artifact.chunks)},
        "model": cfg.get("jev.model"),
        "strategy": strategy,
        "thresholds": cfg.get("selection.thresholds"),
        "usage": dict(jev.usage),
        "corpora": [{"name": layer.name, "prefix": layer.prefix,
                     "ref": layer.parent.ref if layer.parent else None,
                     "sha": layer.parent.sha if layer.parent else None} for layer in cfg.layers],
        **(extra or {}),
        "applicable": sorted(applicable.values(), key=lambda e: e["id"]),
        "chunks": [
            {"id": r.chunk.id, "path": r.chunk.path, "kind": r.chunk.kind, "language": r.chunk.language,
             "domains": r.domains, "rfcs": r.rfcs, "statements": r.statements, "selected": r.selected}
            for r in results
        ],
    }
