"""The engine's boundaries (engine doc section 1 and test 7): it loads no profile, imports nothing that sends, files, or
writes outside its data folder, names no association, and keeps its roles in step with the console's offices."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

import jason.workflows as pkg
from jason.workflows.types import ClockBasis, Role, followup_basis

PACKAGE = Path(pkg.__file__).parent
EDGE = {"readers", "definitions_general", "guide_reads"}
"""The two modules at the engine's edge: the readers that look at jason's stores, and the general definitions built over
the procedures. They are held to the rules in ``test_the_edge_*`` below; the core is everything else."""
ALL_MODULES = sorted(PACKAGE.glob("*.py"))
MODULES = [m for m in ALL_MODULES if m.stem not in EDGE]
EXPECTED = {"__init__", "types", "store", "fold", "resume", "steps", "definitions", "api", "guide", "nudge"}

# The only jason modules the package may import, and why: the locks it appends under, the follow-ups' clock basis (mapped
# lazily), the approvals registry (its kinds, read lazily when a definition is checked), and the procedures (read lazily
# for the drift check). Everything else in jason, and every outside client, is refused.
ALLOWED = ("jason.workflows", "jason.locks", "jason.tasks.followups", "jason.approvals.registry", "jason.community.procedures")


def imports(path: Path) -> set[str]:
    out = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            out.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, f"{path.name}: a relative import"
            base = node.module or ""
            out.add(base)
            out.update(f"{base}.{a.name}" for a in node.names)     # `from jason import locks` names jason.locks
    return out


def test_the_package_has_the_planned_modules():
    assert {m.stem for m in MODULES} == EXPECTED
    assert {m.stem for m in ALL_MODULES} - EXPECTED == EDGE


# The edge reads jason's stores; it may import these (lazily, inside the reads) and nothing else of jason. Each is a reader of
# a store on disk: none sends, files, or writes. The queue is imported to look at it, never to add to it. The controls' record
# and the decisions store are read for control-adoption (only ``load``, ``get``, ``in_force``, and ``roster_problem`` are called).
EDGE_ALLOWED = ("jason.workflows", "jason.locks", "jason.tasks.followups", "jason.tasks.campaigns", "jason.tasks.response_inbox",
                "jason.tasks.notice_ledger", "jason.community.response_inbox", "jason.community.law_text",
                "jason.community.procedures", "jason.community", "jason.approvals.registry", "jason.approvals.store",
                "jason.approvals.model", "jason.jobs", "jason.controls", "jason.tasks.decisions")


def test_the_edge_imports_only_the_stores_it_reads_and_no_client():
    stdlib = set(sys.stdlib_module_names)
    banned = ("payhoa", "google", "jason.google", "smtplib", "imaplib", "email", "requests", "httpx", "urllib", "http", "socket",
              "keepersdk", "jason.secrets", "jason.vault", "jason.payhoa_tx", "jason.payhoa_session", "jason.integrations",
              "jason.zoom", "jason.mcp", "jason.web", "jason.agent", "jason.cli", "jason.commands", "jason.approvals.kinds",
              "jason.approvals.engine", "idoxs", "smud", "asspy", "subprocess", "webbrowser")
    for module in ALL_MODULES:
        if module.stem not in EDGE:
            continue
        for name in imports(module):
            top = name.split(".")[0]
            if top == "jason":
                ok = any(name == a or name.startswith(a + ".") or a.startswith(name + ".") for a in EDGE_ALLOWED) or name == "jason"
                assert ok, f"{module.name} imports {name}, which the edge may not"
            else:
                assert top in stdlib or top == "__future__", f"{module.name} imports {name}, which is not the standard library"
            for bad in banned:
                assert not (name == bad or name.startswith(bad + ".")), f"{module.name} imports {name}"


def test_the_edge_names_no_profile():
    for module in ALL_MODULES:
        if module.stem in EDGE:
            text = module.read_text(encoding="utf-8").lower()
            assert "mystique" not in text and "jason_mystique" not in text, module.name


def test_no_module_imports_a_client_or_anything_outside_the_allowed_few():
    stdlib = set(sys.stdlib_module_names)
    for module in MODULES:
        for name in imports(module):
            top = name.split(".")[0]
            if top == "jason":
                ok = any(name == a or name.startswith(a + ".") or a.startswith(name + ".") for a in ALLOWED) or name == "jason"
                assert ok, f"{module.name} imports {name}, which the engine may not"
            else:
                assert top in stdlib or top == "__future__", f"{module.name} imports {name}, which is not the standard library"


def test_no_module_imports_a_sending_filing_or_writing_client():
    banned = ("payhoa", "google", "jason.google", "smtplib", "imaplib", "email", "requests", "httpx", "urllib", "http", "socket",
              "ftplib", "keepersdk", "jason.secrets", "jason.vault", "jason.payhoa_tx", "jason.payhoa_session", "jason.integrations",
              "jason.zoom", "jason.mcp", "jason.web", "jason.agent", "jason.cli", "jason.commands", "jason.approvals.kinds",
              "jason.jobs", "jason.tasks.", "idoxs", "smud", "asspy", "subprocess", "webbrowser")
    for module in MODULES:
        for name in imports(module):
            if name == "jason.tasks.followups" or name.startswith("jason.tasks.followups."):
                continue                                               # the one follow-ups module: its clock basis
            for bad in banned:
                assert not (name == bad.rstrip(".") or name.startswith(bad.rstrip(".") + ".")), f"{module.name} imports {name}"


def test_no_module_names_an_association_a_vendor_or_a_profile():
    for module in MODULES:
        text = module.read_text(encoding="utf-8").lower()
        for word in ("mystique", "jason_mystique", "payhoa", "smud", "idoxs", "keeper", "zoom", "gmail"):
            assert word not in text, f"{module.name} names {word}"


def test_importing_the_engine_loads_no_profile_and_no_other_jason_module():
    code = (
        "import sys, json\n"
        "import jason\n"
        "before = set(sys.modules)\n"
        "import jason.workflows, jason.workflows.api, jason.workflows.definitions, jason.workflows.resume\n"
        "new = sorted(m for m in set(sys.modules) - before)\n"
        "profile = sorted(m for m in sys.modules if 'mystique' in m)\n"
        "print(json.dumps({'new': new, 'profile': profile}))\n"
    )
    out = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    got = json.loads(out.stdout.strip().splitlines()[-1])
    assert got["profile"] == []                                    # no profile package was imported
    outside = [m for m in got["new"] if m.split(".")[0] in ("jason", "payhoa", "mystique")
               and not (m.startswith("jason.workflows") or m == "jason.locks")]
    assert outside == [], outside


def test_registering_and_validating_a_definition_loads_no_profile():
    code = (
        "import sys, json\n"
        "from jason.workflows import definitions\n"
        "from jason.workflows.types import Workflow, StepDef, StepKind\n"
        "wf = Workflow('w', 'W', 'f', 'unit', steps=(StepDef('w.1', 'Do it', StepKind.PERSON),))\n"
        "definitions.register(wf)\n"
        "print(json.dumps({'profile': sorted(m for m in sys.modules if 'mystique' in m), 'n': len(definitions.all_definitions())}))\n"
    )
    out = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    assert json.loads(out.stdout.strip().splitlines()[-1]) == {"profile": [], "n": 1}


def test_the_roles_are_the_consoles_offices_plus_the_engines_own():
    access = pytest.importorskip("jason.web.access")
    holders = {r.holder for r in access.SEE_RULES} - {access.ROSTER}
    assert holders <= {r.value for r in Role}, holders - {r.value for r in Role}
    assert {r.value for r in Role} - holders == {"administrator", "developer", "reviewer", "jason", "scheduler", "anyone"}
    assert Role.parse("Vice President") is Role.VICE_PRESIDENT and Role.parse("wizard") is None and Role.parse(Role.JASON) is Role.JASON


def test_the_clock_bases_map_to_the_followups_bases_and_counterparty_has_none_yet():
    from jason.tasks.followups import Basis

    assert {b.value for b in ClockBasis} == {"law", "documents", "counterparty", "provider", "proposed policy", "person"}
    assert followup_basis(ClockBasis.LAW) is Basis.LAW and followup_basis(ClockBasis.PROPOSED_POLICY) is Basis.PROPOSED_POLICY
    assert followup_basis(ClockBasis.COUNTERPARTY) is None or followup_basis(ClockBasis.COUNTERPARTY).value == "counterparty"
    assert followup_basis(ClockBasis.PROVIDER) is None or followup_basis(ClockBasis.PROVIDER).value == "provider"
