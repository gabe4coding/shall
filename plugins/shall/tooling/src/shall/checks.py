"""Deterministic code checks for `Enforcement: linter` statements with a `Check:` name.

Some rules are mechanical: Jev judges "how typed does this file look", it cannot count which
functions lack type hints (eval/scan: 30 of 36 missed violations were JRFC-0011.1). A named
check gives exact lines instead. `shall scan` and the post-write hook run the checks of the
eligible linter statements next to the Jev questions; no model is called.

A check takes (path, text) and returns the 1-based lines that break the rule, or None when it
cannot judge the file (another language, a syntax error).
"""

from __future__ import annotations

import ast
from typing import Callable


def python_typed_public(path: str, text: str) -> list[int] | None:
    """Public module-level functions and methods of public module-level classes whose
    parameters or return value have no type hint. `self`/`cls` and the return of `__init__`
    need none; nested helpers and `_private` names are not public."""
    if not path.endswith((".py", ".pyi")):
        return None
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return None
    out: list[int] = []

    def check(fn: ast.FunctionDef | ast.AsyncFunctionDef, method: bool) -> None:
        name = fn.name
        if name.startswith("_") and name != "__init__":
            return
        a = fn.args
        params = a.posonlyargs + a.args
        static = any(isinstance(d, ast.Name) and d.id == "staticmethod" for d in fn.decorator_list)
        if method and not static and params and params[0].arg in ("self", "cls", "mcs", "metacls"):
            params = params[1:]
        params = params + a.kwonlyargs + [x for x in (a.vararg, a.kwarg) if x is not None]
        missing = any(p.annotation is None for p in params)
        if fn.returns is None and name != "__init__":
            missing = True
        if missing:
            out.append(fn.lineno)

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            check(node, method=False)
        elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            for member in node.body:
                if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    check(member, method=True)
    return sorted(out)


CHECKS: dict[str, Callable[[str, str], list[int] | None]] = {
    "python-typed-public": python_typed_public,
}
