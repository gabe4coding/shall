"""The layering guard (`shall conflicts`): code, not Jev, decides which pairs fail and in what order."""

import asyncio
from types import SimpleNamespace

from fakes import FakeJev
from shall.conflicts import FAILING, compare


class RelationJev(FakeJev):
    """Answers per new statement text: the relation probabilities and the two Noul gates."""

    def __init__(self, answers):
        super().__init__()
        self.answers = answers

    async def ask(self, state, questions):
        await super().ask(state, questions)
        probs, permits, violates = self.answers[state["new_statement"]]
        return {"relation": {"probabilities": probs}, "permits": {"p": permits}, "violates": {"p": violates}}


def pair(sid, text, status="enforced", layer="org"):
    return SimpleNamespace(id=sid.split(".")[0], status=status, layer=layer), SimpleNamespace(id=sid, text=text)


def run(answers, new, existing, fail_p=0.6, report_p=0.5):
    return asyncio.run(compare(RelationJev(answers), new, existing, fail_p, report_p))


def test_failing_classes_are_summed_so_a_split_pair_still_fails():
    # conflict 0.35 + weakens 0.33: neither class passes 0.6 alone, the sum does
    found = run({"a": ({"conflict": 0.35, "weakens": 0.33, "unrelated": 0.32}, 0.1, 0.1)},
                [pair("L-1.1", "a")], [pair("O-1.1", "x")])
    assert [(f["relation"], f["p"]) for f in found] == [("conflict", 0.68)]


def test_a_noul_gate_alone_fails_the_pair():
    found = run({"a": ({"overlap": 0.6, "unrelated": 0.4}, 0.9, 0.1)}, [pair("L-1.1", "a")], [pair("O-1.1", "x")])
    assert found[0]["relation"] in FAILING and found[0]["p"] == 0.9


def test_below_the_gate_a_related_pair_is_overlap_and_an_unrelated_one_is_dropped():
    answers = {"a": ({"overlap": 0.7, "unrelated": 0.3}, 0.1, 0.1),
               "b": ({"overlap": 0.2, "unrelated": 0.8}, 0.1, 0.1)}
    found = run(answers, [pair("L-1.1", "a"), pair("L-1.2", "b")], [pair("O-1.1", "x", layer="org")])
    assert [(f["new"], f["relation"], f["p"], f["existing_layer"]) for f in found] == [("L-1.1", "overlap", 0.7, "org")]


def test_failing_pairs_come_first_then_by_p():
    answers = {"a": ({"overlap": 0.9, "unrelated": 0.1}, 0.0, 0.0),
               "b": ({"duplicate": 0.65, "unrelated": 0.35}, 0.0, 0.0),
               "c": ({"weakens": 0.8, "unrelated": 0.2}, 0.0, 0.0)}
    found = run(answers, [pair("L-1.1", "a"), pair("L-1.2", "b"), pair("L-1.3", "c")], [pair("O-1.1", "x")])
    assert [(f["new"], f["relation"]) for f in found] == [("L-1.3", "weakens"), ("L-1.2", "duplicate"),
                                                          ("L-1.1", "overlap")]


def test_every_new_statement_is_asked_against_every_existing_one():
    jev = RelationJev({t: ({"unrelated": 1.0}, 0.0, 0.0) for t in "ab"})
    asyncio.run(compare(jev, [pair("L-1.1", "a"), pair("L-1.2", "b")], [pair("O-1.1", "x"), pair("O-2.1", "y")],
                        0.6, 0.5))
    assert sorted((s["new_statement"], s["existing_statement"]) for s in jev.states) == [
        ("a", "x"), ("a", "y"), ("b", "x"), ("b", "y")]
