"""No class or module in jason defines the same name twice: Python lets the second silently replace the first, so a
new ``Community.developers`` (meaning jason's maintainers) once replaced the subdividers' ``developers``, and 78 tests
far from it failed (lesson ``shadowed-community-method``)."""

from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path

ROOTS = [Path(__file__).resolve().parents[1] / "src" / "jason", Path(__file__).resolve().parents[1] / "mystique"]


def _defined(body: list[ast.stmt]) -> list[str]:
    return [n.name for n in body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]


def _overloads(body: list[ast.stmt]) -> set[str]:
    """Names a ``@typing.overload`` or a property setter legitimately repeats."""
    out = set()
    for n in body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for d in n.decorator_list:
                text = ast.unparse(d)
                if text.endswith("overload") or text.endswith(".setter") or text.endswith(".deleter"):
                    out.add(n.name)
    return out


def test_no_name_is_defined_twice_in_one_scope():
    found = []
    for root in ROOTS:
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            scopes = [("<module>", tree.body)] + [(n.name, n.body) for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
            for scope, body in scopes:
                twice = {k for k, v in Counter(_defined(body)).items() if v > 1} - _overloads(body)
                found += [f"{path.relative_to(root.parent)}: {scope}.{name}" for name in sorted(twice)]
    assert not found, "defined twice (the second silently replaces the first): " + ", ".join(found)
