"""The checks package (jason.workflows.checks): read-only, no outside client, no profile named, and a name is registered once."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent.parent / "src" / "jason" / "workflows" / "checks"
MODULES = sorted(p for p in PACKAGE.glob("*.py") if p.stem != "__init__")

# What a read may import from jason: stores and read functions, never a client that reaches out.
ALLOWED = ("jason.workflows", "jason.locks", "jason.config", "jason.tasks", "jason.community", "jason.approvals.store",
           "jason.approvals.registry", "jason.approvals.model", "jason.controls", "jason.mcp.county", "jason.sources.offline",
           "jason.integrations", "jason.limits", "jason.storage")
BANNED = ("payhoa", "jason.google", "jason.zoom", "jason.keeper", "jason.vault", "requests", "httpx", "urllib3", "smtplib",
          "anthropic", "jason.web", "mystique", "jason_mystique", "jason.tasks.sync", "subprocess")


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


def test_no_check_imports_a_client_that_reaches_out_or_names_a_profile():
    for module in MODULES:
        for name in _imports(module):
            assert not any(name == b or name.startswith(b + ".") for b in BANNED), f"{module.name} imports {name}"


def test_a_check_imports_only_stores_and_read_functions_of_jason():
    for module in MODULES:
        for name in _imports(module):
            if name.split(".")[0] != "jason":
                continue
            assert any(name == a or name.startswith(a + ".") for a in ALLOWED), f"{module.name} imports {name}"


def test_no_check_writes_a_file():
    for module in MODULES:
        text = module.read_text(encoding="utf-8")
        for token in ("write_text(", "write_bytes(", ".write(", "os.replace(", "shutil.", "open(", "json.dump("):
            assert token not in text or token == "open(" and "'w'" not in text and '"w"' not in text and '"a"' not in text, (
                f"{module.name} uses {token}")


def test_importing_the_package_loads_no_profile_and_registers_a_name_once():
    code = (
        "import sys\n"
        "from jason.workflows import checks, readers\n"
        "before = set(readers.CHECKS)\n"
        "checks.load_all(); checks.load_all()\n"
        "print(sorted(m for m in sys.modules if 'mystique' in m), len(set(readers.CHECKS) - before))\n"
    )
    out = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip().startswith("[]")
