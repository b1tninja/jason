"""docs/instance-limits.md, section 6: a limit is a row and one call. The lint reads the syntax of ``src/jason`` (it runs nothing):
no bare number for a registered size limit where a registry key exists, every registered key is read somewhere, and nothing reads
a key the registry does not hold."""

import ast
from pathlib import Path

from jason import limits

SRC = Path(__file__).resolve().parents[1] / "src" / "jason"
READERS = {"value", "check", "refusal", "effective", "limit", "default"}


def _modules():
    for path in sorted(SRC.rglob("*.py")):
        if path != SRC / "limits.py":
            yield path, ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _fold(node):
    """An integer constant expression's value (``100 * 1024 * 1024``), or None."""
    if isinstance(node, ast.Constant) and type(node.value) is int:
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Mult, ast.Add)):
        a, b = _fold(node.left), _fold(node.right)
        if a is not None and b is not None:
            return a * b if isinstance(node.op, ast.Mult) else a + b
    return None


def _reads(tree):
    """(key, line) for each ``limits.value("key")``-style call with a literal first argument."""
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in READERS and node.args
                and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)
                and isinstance(node.func.value, ast.Name) and node.func.value.id in {"limits", "_limits"}):
            yield node.args[0].value, node.lineno


def test_every_registered_key_is_read_somewhere():
    read = {key for _, tree in _modules() for key, _ in _reads(tree)}
    assert not [l.key for l in limits.LIMITS if l.key not in read], "registered but read nowhere: add the call or remove the row"


def test_nothing_reads_a_key_the_registry_does_not_hold():
    held = {l.key for l in limits.LIMITS}
    unknown = [f"{path.name}:{line} {key}" for path, tree in _modules() for key, line in _reads(tree) if key not in held]
    assert not unknown, unknown


def test_no_bare_number_stands_for_a_registered_size_limit():
    """A size limit's default or maximum written out where its key exists is a second copy of the number."""
    numbers = {}
    for l in limits.LIMITS:
        if l.unit == "bytes":
            for n in (l.default, l.maximum):
                numbers.setdefault(n, l.key)
    found = []
    for path, tree in _modules():
        for node in ast.walk(tree):
            if isinstance(node, (ast.BinOp, ast.Constant)):
                n = _fold(node)
                if n in numbers:
                    found.append((path.relative_to(SRC).as_posix(), f"{path.relative_to(SRC)}:{node.lineno} is {numbers[n]}'s number; ask jason.limits"))
    assert not found, [text for _, text in found]


def test_every_applies_to_point_names_a_real_module():
    for l in limits.LIMITS:
        for point in l.applies_to:
            module = SRC.joinpath(*point.split(".")[:-1]).with_suffix(".py")
            assert module.is_file(), f"{l.key}: {point}"
            assert point.split(".")[-1] in module.read_text(encoding="utf-8"), f"{l.key}: {point}"
