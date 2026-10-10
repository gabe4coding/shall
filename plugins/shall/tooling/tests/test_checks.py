"""Deterministic code checks (`Enforcement: linter` + `Check:`): exact lines, no model."""

from shall.checks import CHECKS, python_typed_public
from shall.corpus import _parse_statements

CODE = '''\
import functools


def typed(a: int, *args: str, flag: bool = False, **kw: int) -> int:
    return a


def untyped_param(a, b: int) -> int:
    return b


async def no_return(a: int):
    def nested(x):          # nested helper: not public
        return x
    return nested(a)


def _private(x):
    return x


class Service:
    def __init__(self, url: str):   # __init__ needs no return type
        self.url = url

    def get(self, path):
        return path

    @staticmethod
    def build(self_like: str) -> "Service":
        return Service(self_like)

    @classmethod
    def make(cls) -> "Service":
        return cls("x")

    def _hidden(self, y):
        return y


class _Internal:
    def run(self, z):
        return z
'''


def test_python_typed_public_finds_exact_lines():
    assert python_typed_public("svc.py", CODE) == [8, 12, 26]


def test_python_typed_public_skips_what_it_cannot_judge():
    assert python_typed_public("app.ts", "function f(x) { return x }") is None
    assert python_typed_public("bad.py", "def f(:\n") is None
    assert python_typed_public("ok.py", "X = 1\n") == []
    assert "python-typed-public" in CHECKS


def test_lint_checks_the_check_field():
    body = ["### XY-0001.1 One", "Code SHOULD do it.", "- Check: no-such-check", "- Enforcement: linter", "",
            "### XY-0001.2 Two", "Code SHOULD do that.", "- Check: python-typed-public", "- Enforcement: agent", "",
            "### XY-0001.3 Three", "Code SHOULD do this.", "- Check: python-typed-public", "- Enforcement: linter"]
    issues = []
    sts = _parse_statements("XY-0001", body, 0, "x.md", issues)
    by_sid = {}
    for i in issues:
        by_sid.setdefault(i.message.split()[0], set()).add(i.code)
    assert by_sid["XY-0001.1"] >= {"check"} and by_sid["XY-0001.2"] >= {"check-enforcement"}
    assert not by_sid["XY-0001.3"] & {"check", "check-enforcement"} and sts[2].check == "python-typed-public"
