"""Module-level state that could hold one community's data past a request: found, and held to a ratchet.

docs/tenancy.md, section 2: a process serves one community today, and nothing in the code makes a second community's
data safe in the same interpreter. This finds, by reading the syntax of ``src/jason`` and running nothing:

- ``container``: a module-level name bound to an empty, mutable container (``{}``, ``[]``, ``set()``, ``defaultdict``,
  ``threading.local()``, ...): filled at run time, by whoever ran first;
- ``global``: a name a function rebinds with ``global`` (a lazily built singleton);
- ``cache``: an ``lru_cache`` or ``cache`` on a function whose parameters name no profile, folder, or path, so the
  community cannot be part of its key;
- ``environ``: an assignment to ``os.environ`` of the setting that names the community (or its data or private-facts
  folder), or to ``tempfile.tempdir``;
- ``data-path``: ``Path("data")``, the working directory's data folder;
- ``default-call``: a default argument that asks for the active community or its folder when the module is imported.

Each finding is ``module:kind:name``. ``tests/fixtures/tenancy_state.json`` lists the ones that exist today, each with a
status and a one-line reason (``keyed``: the key holds the community or a path under it; ``shared``: public content
every community may read; ``program-start``: set once as a program starts; ``process-global``: holds one community's
data in the process, which is the work of phase 2). A finding the baseline does not list fails the test, and so does a
baseline entry the code no longer bears out: the ratchet only shrinks (``python -m jason.community.tenancy_state --update``
removes the cleared ones; a new one is a decision, written by hand with its reason).
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

EMPTY_CONTAINERS = {"dict", "list", "set", "defaultdict", "OrderedDict", "deque", "Counter", "WeakValueDictionary",
                    "WeakKeyDictionary", "local", "ChainMap"}
CACHES = {"lru_cache", "cache"}
KEY_WORDS = ("profile", "communit", "data", "root", "dir", "folder", "path", "file", "base", "env", "slug", "where")
ENV_NAMES = {"JASON_PROFILE", "JASON_COMMUNITY", "JASON_DATA_DIR", "JASON_SPEC_DIR", "JASON_COMMUNITY_VIA"}
ACTIVE_CALLS = {"community", "profile_name", "data_dir", "default_data_dir", "load_profile", "data_root"}
STATUSES = ("keyed", "shared", "program-start", "process-global")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def baseline_path(root: Path | None = None) -> Path:
    return (root or repo_root()) / "tests" / "fixtures" / "tenancy_state.json"


def _module_name(path: Path, src: Path) -> str:
    parts = list(path.relative_to(src).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _name_of(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _is_empty_container(value: ast.AST | None) -> bool:
    if isinstance(value, ast.Dict):
        return not value.keys
    if isinstance(value, (ast.List, ast.Set)):
        return not value.elts
    if isinstance(value, ast.Call):
        name = _name_of(value.func)
        if name == "defaultdict":
            return True
        return name in EMPTY_CONTAINERS and not value.args and not value.keywords
    return False


def _module_level(body: list[ast.stmt]):
    """Statements at module level, including inside ``if``/``try``/``with`` blocks there, not inside a def or class."""
    for node in body:
        yield node
        if isinstance(node, (ast.If, ast.Try, ast.With)):
            for block in (getattr(node, "body", []), getattr(node, "orelse", []), getattr(node, "finalbody", []),
                          *[h.body for h in getattr(node, "handlers", [])]):
                yield from _module_level(block)


def _cache_decorated(func: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for dec in func.decorator_list:
        target = dec.func if isinstance(dec, ast.Call) else dec
        if _name_of(target) in CACHES:
            return True
    return False


def _keyed(func: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    args = [a.arg for a in (*func.args.posonlyargs, *func.args.args, *func.args.kwonlyargs)]
    return any(any(word in arg.lower() for word in KEY_WORDS) for arg in args)


def _environ_target(node: ast.AST) -> str:
    """``os.environ["X"]`` as a target: ``X``."""
    if isinstance(node, ast.Subscript) and _name_of(node.value) == "environ":
        key = node.slice
        if isinstance(key, ast.Constant) and isinstance(key.value, str):
            return key.value
    return ""


def scan_source(source: str, module: str) -> dict[str, int]:
    """The findings in one module's text: ``kind:name`` -> first line."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}
    found: dict[str, int] = {}

    def add(key: str, line: int) -> None:
        found.setdefault(key, line)

    for node in _module_level(tree.body):
        targets: list[ast.AST] = []
        value = None
        if isinstance(node, ast.Assign):
            targets, value = list(node.targets), node.value
        elif isinstance(node, ast.AnnAssign):
            targets, value = [node.target], node.value
        if _is_empty_container(value):
            for target in targets:
                if isinstance(target, ast.Name):
                    add(f"container:{target.id}", node.lineno)

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if _cache_decorated(node) and not _keyed(node):
                add(f"cache:{node.name}", node.lineno)
            for default in (*node.args.defaults, *[d for d in node.args.kw_defaults if d is not None]):
                for inner in ast.walk(default):
                    if isinstance(inner, ast.Call) and _name_of(inner.func) in ACTIVE_CALLS:
                        add(f"default-call:{node.name}", node.lineno)
            for inner in ast.walk(node):
                if isinstance(inner, ast.Global):
                    for name in inner.names:
                        add(f"global:{name}", inner.lineno)
        if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            for target in (node.targets if isinstance(node, ast.Assign) else [node.target]):
                var = _environ_target(target)
                if var in ENV_NAMES:
                    add(f"environ:{var}", node.lineno)
                if isinstance(target, ast.Attribute) and target.attr == "tempdir" and _name_of(target.value) == "tempfile":
                    add("environ:tempfile.tempdir", node.lineno)
        if isinstance(node, ast.Call):
            func = node.func
            if (_name_of(func) == "Path" and node.args and isinstance(node.args[0], ast.Constant)
                    and node.args[0].value == "data"):
                add("data-path:Path('data')", node.lineno)
            if (_name_of(func) in ("setdefault", "update", "pop") and isinstance(func, ast.Attribute)
                    and _name_of(func.value) == "environ" and node.args
                    and isinstance(node.args[0], ast.Constant) and node.args[0].value in ENV_NAMES):
                add(f"environ:{node.args[0].value}", node.lineno)
    return {f"{module}:{key}": line for key, line in found.items()}


def scan(root: Path | None = None) -> dict[str, int]:
    """Every finding under ``src/jason``: ``module:kind:name`` -> line."""
    src = (root or repo_root()) / "src"
    out: dict[str, int] = {}
    for path in sorted((src / "jason").rglob("*.py")):
        out.update(scan_source(path.read_text(encoding="utf-8", errors="replace"), _module_name(path, src)))
    return out


def load_baseline(root: Path | None = None) -> dict[str, dict[str, str]]:
    path = baseline_path(root)
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8")).get("state", {})


def load_crosses(root: Path | None = None) -> dict[str, str]:
    """The reads that cross communities in one interpreter today (tests/test_tenancy.py): ``module.function`` -> why."""
    path = baseline_path(root)
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8")).get("crosses", {})


def compare(found: dict[str, int], baseline: dict[str, dict[str, str]]) -> tuple[list[str], list[str]]:
    """(new, cleared): findings the baseline does not list, and baseline entries the code no longer has."""
    return sorted(set(found) - set(baseline)), sorted(set(baseline) - set(found))


def problems(baseline: dict[str, dict[str, str]]) -> list[str]:
    """Baseline entries without a known status or a reason."""
    out = []
    for key, row in baseline.items():
        if row.get("status") not in STATUSES:
            out.append(f"{key}: status must be one of {', '.join(STATUSES)}")
        if not (row.get("reason") or "").strip():
            out.append(f"{key}: a reason, one line")
    return out


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    found = scan()
    baseline = load_baseline()
    new, cleared = compare(found, baseline)
    if "--update" in args:
        kept = {k: v for k, v in baseline.items() if k in found}
        whole = json.loads(baseline_path().read_text(encoding="utf-8")) if baseline_path().is_file() else {}
        whole["state"] = dict(sorted(kept.items()))
        baseline_path().write_text(json.dumps(whole, indent=1) + "\n", encoding="utf-8")
        print(f"removed {len(cleared)} cleared; {len(new)} new need a status and a reason by hand")
        for key in new:
            print("  NEW", key)
        return 0
    for key in new:
        print("NEW    ", key, "line", found[key])
    for key in cleared:
        print("CLEARED", key)
    return 1 if new or cleared else 0


if __name__ == "__main__":
    raise SystemExit(main())
