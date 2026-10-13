"""The reviewer agent: one tool-less `claude -p` call per chunk with the selected statements.

The agent (Claude Code in print mode, with the plugin's shall-reviewer prompt) only sees one
chunk and the statements Jev selected for it. Its output is RawFinding JSON; findings.py then
validates every finding and computes severity from the corpus instead of trusting the model.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from .artifact import Artifact
from .claude import AnswerCache, agent_prompt, run_claude
from .config import Config, make_dir
from .corpus import Corpus
from .findings import FINDINGS_SCHEMA, RawFinding, chunk_prompt


def reviewer_prompt() -> str:
    return agent_prompt("shall-reviewer")


async def _run_agent(cfg: Config, prompt: str, sem: asyncio.Semaphore,
                     cache: AnswerCache | None = None) -> tuple[list[RawFinding], dict]:
    result, meta = await run_claude(cfg, prompt, reviewer_prompt(), FINDINGS_SCHEMA, sem, cache=cache)
    return (result or {}).get("findings", []), meta


async def run_agents(cfg: Config, corpus: Corpus, artifact: Artifact, selection: dict,
                     prompts_dir: Path | None = None, cache: AnswerCache | None = None) -> tuple[list[RawFinding], dict]:
    chunks = {c.id: c for c in artifact.chunks}
    sem = asyncio.Semaphore(int(cfg.get("review.concurrency")))
    jobs = []
    for c in selection["chunks"]:
        if not c["selected"]:
            continue
        prompt = chunk_prompt(corpus, chunks[c["id"]], c["selected"], c.get("known_effects"))
        if prompts_dir:
            make_dir(prompts_dir)
            (prompts_dir / f"{c['id']}.md").write_text(prompt, encoding="utf-8")
        jobs.append((c["id"], _run_agent(cfg, prompt, sem, cache)))
    results = await asyncio.gather(*(job for _, job in jobs))
    raw: list[RawFinding] = []
    errors: list[dict] = []
    stats: dict = {"agent_calls": 0, "reused": 0, "cost_usd": 0.0, "errors": errors}
    for (cid, _), (findings, meta) in zip(jobs, results):
        stats["reused" if meta.get("cached") else "agent_calls"] += 1
        for f in findings:
            item = f.copy()
            item["chunk"] = cid  # code knows the chunk; an agent-supplied one is overwritten
            raw.append(item)
        if "error" in meta:
            errors.append({"chunk": cid, "error": meta["error"]})
        stats["cost_usd"] = round(stats["cost_usd"] + meta.get("cost_usd", 0.0), 6)
    return raw, stats
