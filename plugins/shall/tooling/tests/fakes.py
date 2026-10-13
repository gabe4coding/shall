"""The test doubles every test shares: one fake Jev (shall.jev.JevLike) and one Finding factory.

Use these instead of a local copy: a copy drifts from the real interface and the tests then pass
against an interface that no longer exists.
"""

import asyncio
from typing import TYPE_CHECKING, Any

from shall.findings import Finding


class FakeJev:
    """p per question id from `table` (or per file: {path: table}); `#applies` questions answer
    0.95, every other question 0.02. For scores that depend on the state, subclass and override `p`.
    `states` records each state asked; `asked` records each question set."""

    model = "fake-jev"

    def __init__(self, table=None, fail=None, delay=0.0, per_file=None):
        self.table, self.fail, self.delay, self.per_file = table or {}, fail, delay, per_file or {}
        self.usage = {"requests": 0, "cached": 0, "input_tokens": 0}
        self.states = []
        self.asked = []

    def available(self):
        return True

    def save(self):
        pass

    async def gather(self, aws):
        return list(await asyncio.gather(*aws))

    def p(self, state, qid):
        table = {**self.table, **self.per_file.get(state.get("file"), {})}
        return table.get(qid, 0.95 if qid.endswith("#applies") else 0.02)

    async def ask(self, state, questions):
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.fail:
            raise self.fail
        self.usage["requests"] += 1
        self.usage["input_tokens"] += 1000
        self.states.append(state)
        self.asked.append(set(questions))
        return {q: {"p": self.p(state, q)} for q in questions}


def make_finding(**kw) -> Finding:
    """A validated finding: blocking (enforced MUST) unless `corpus_blocking=False`."""
    base: dict[str, Any] = dict(statement_id="JTOOL-0002.1", title="t", level="MUST", corpus_blocking=True,
                path="shall.yaml", line=2, quote="command: [claude, -p]", message="agent runs with tools",
                suggestion="", statement_text="The review agent MUST run with no tools.", source="x#L1",
                chunk="c0", depends_on=())
    base.update(kw)
    base.setdefault("rfc", base["statement_id"].split(".")[0])
    base["depends_on"] = tuple(base["depends_on"])
    return Finding(**base)


if TYPE_CHECKING:  # `make typecheck` fails when FakeJev drifts from the real interface
    from shall.jev import JevLike

    _: JevLike = FakeJev()
