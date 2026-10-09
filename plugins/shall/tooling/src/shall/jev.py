"""Thin async wrapper over the TypeSafe SDK: caching, request packing, usage accounting."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path

from typesafe_sdk import AsyncTypeSafeClient, Choice, Noul, NoulCriteria, RetryPolicy

from .config import Config

# The API budgets are 64k tokens per request and 32k for state + the longest question.
STATE_PLUS_QUESTION_TOKENS = 30000


def est_tokens(value) -> int:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return len(text) // 3 + 1  # conservative: code and JSON tokenize densely


def noul(instructions: str, true: str | None = None, false: str | None = None) -> Noul:
    if true or false:
        return Noul(instructions=instructions, criteria=NoulCriteria(true=true, false=false))
    return Noul(instructions=instructions)


def choice(instructions: str, options: dict[str, str | None]) -> Choice:
    return Choice(instructions=instructions, criteria=options)


class Jev:
    def __init__(self, cfg: Config, use_cache: bool = True):
        self.model = cfg.get("jev.model")
        self.max_request_tokens = int(cfg.get("jev.max_request_tokens"))
        self.cache_path: Path = cfg.cache_file
        self.use_cache = use_cache
        self.sem = asyncio.Semaphore(int(cfg.get("jev.concurrency")))
        self.cache: dict = {}
        if use_cache and self.cache_path.is_file():
            self.cache = json.loads(self.cache_path.read_text(encoding="utf-8"))
        # est_input_tokens counts cached calls too: a cache-independent cost measure for evals
        self.usage = {"requests": 0, "cached": 0, "input_tokens": 0, "est_input_tokens": 0}
        self._client: AsyncTypeSafeClient | None = None

    async def __aenter__(self) -> "Jev":
        return self

    async def __aexit__(self, *exc) -> None:
        if self._client is not None:
            await self._client.aclose()
        self.save()

    def available(self) -> bool:
        """False without an API key: callers that must not fail (hooks) skip Jev instead."""
        return bool(os.environ.get("TYPESAFE_API_KEY"))

    def client(self) -> AsyncTypeSafeClient:
        if self._client is None:
            if not os.environ.get("TYPESAFE_API_KEY"):
                raise SystemExit("shall: TYPESAFE_API_KEY is not set (needed for Jev calls)")
            self._client = AsyncTypeSafeClient(
                model=self.model,
                timeout=120.0,
                retry=RetryPolicy(max_retries=5, backoff_initial=1.0, backoff_max=20.0, backoff_jitter=0.25),
            )
        return self._client

    def save(self) -> None:
        """Merge with what is on disk, then replace atomically: parallel runs sharing one
        cache (CI matrix, two local commands) keep each other's answers."""
        if not self.use_cache:
            return
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        merged = {}
        if self.cache_path.is_file():
            try:
                merged = json.loads(self.cache_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                merged = {}
        merged.update(self.cache)
        tmp = self.cache_path.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(merged, sort_keys=True), encoding="utf-8")
        os.replace(tmp, self.cache_path)

    def _key(self, state, questions: dict) -> str:
        payload = {
            "m": self.model,
            "s": state,
            "q": {k: q.model_dump(mode="json", exclude_none=True) for k, q in questions.items()},
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    async def _ask_one(self, state, questions: dict) -> dict:
        key = self._key(state, questions)
        self.usage["est_input_tokens"] += est_tokens(state) + sum(
            est_tokens(q.model_dump(mode="json", exclude_none=True)) for q in questions.values())
        if key in self.cache:
            self.usage["cached"] += 1
            return self.cache[key]
        async with self.sem:
            resp = await self.client().system_one(state=state, questions=questions, model=self.model)
        out = {}
        for qid, ans in resp.answers.items():
            if ans.type == "noul":
                out[qid] = {"p": round(ans.noul, 4)}
            elif ans.type == "choice":
                out[qid] = {
                    "choice": ans.choice,
                    "confidence": round(ans.confidence, 4),
                    "probabilities": {k: round(v, 4) for k, v in ans.probabilities.items()},
                }
            else:
                out[qid] = ans.model_dump(mode="json")
        self.usage["requests"] += 1
        self.usage["input_tokens"] += (resp.usage.input_tokens or 0) if resp.usage else 0
        self.cache[key] = out
        return out

    def pack(self, state, questions: dict) -> list[dict]:
        """Split questions into requests that respect the per-request token budgets."""
        state_tokens = est_tokens(state)
        if state_tokens + 2000 > STATE_PLUS_QUESTION_TOKENS:
            raise ValueError(f"state too large for Jev (~{state_tokens} tokens); lower jev.max_chunk_chars")
        budget = self.max_request_tokens - state_tokens
        batches, current, used = [], {}, 0
        for qid, q in questions.items():
            cost = est_tokens(q.model_dump(mode="json", exclude_none=True))
            if current and used + cost > budget:
                batches.append(current)
                current, used = {}, 0
            current[qid] = q
            used += cost
        if current:
            batches.append(current)
        return batches

    async def gather(self, aws) -> list:
        """Like asyncio.gather, but let every request finish (and be cached) before raising
        the first failure, so a rerun after a transient outage resumes instead of restarting."""
        results = await asyncio.gather(*aws, return_exceptions=True)
        for r in results:
            if isinstance(r, BaseException):
                raise r
        return results

    async def ask(self, state, questions: dict) -> dict:
        if not questions:
            return {}
        results = await self.gather(self._ask_one(state, b) for b in self.pack(state, questions))
        merged: dict = {}
        for r in results:
            merged.update(r)
        return merged
