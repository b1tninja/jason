"""The jobs registry (jason.workflows.jobs) and the list of what the six families still want (docs/workflows-engine.md,
"Jobs and kinds still wanted"): a descriptor points at a real jason command, only a ready family's are registered, and the doc's
generated block equals the diff of every family's WANTED against what is registered. When this fails because a family changed
its WANTED or registered something, run ``python -m jason.workflows.jobs.wanted --write``."""

from __future__ import annotations

import argparse
import ast
from pathlib import Path

import pytest

from jason.workflows import checks, jobs
from jason.workflows.jobs import wanted
from jason.workflows.readers import CHECKS, JOBS, JobSpec

PACKAGE = Path(jobs.__file__).parent


@pytest.fixture(scope="module")
def commands() -> dict[str, set[str]]:
    from jason import cli

    sub = next(a for a in cli.build_parser()._actions if isinstance(a, argparse._SubParsersAction))
    return {name: {o for a in p._actions for o in a.option_strings} for name, p in sub.choices.items()}


# --- the descriptors -------------------------------------------------------------------------------------------------------

def test_a_descriptor_points_at_a_real_command_and_names_only_flags_it_has(commands):
    for d in jobs.DESCRIPTORS:
        assert d.first in commands, f"{d.name}: jason has no command {d.first}"
        for word in d.require:
            assert word in commands[d.first] or not word.startswith("--") and word in d.command.split(), f"{d.name}: {word}"
        assert d.command.startswith(f"jason {d.first}") and all(w in d.command.split() for w in d.require), d.name
        assert not set(d.require) & set(d.forbid), d.name


def test_descriptor_names_are_unique_and_none_is_also_given_a_reason_for_having_no_command():
    names = [d.name for d in jobs.DESCRIPTORS]
    assert len(names) == len(set(names))
    assert not set(names) & set(jobs.UNDESCRIBED)


def test_a_command_that_can_write_with_yes_is_not_the_read_a_descriptor_recognizes(commands):
    for d in jobs.DESCRIPTORS:
        assert "--yes" not in d.command.split() and "--send" not in d.require, d.name
        if "--yes" in commands[d.first]:
            assert "--yes" in d.forbid, f"{d.name}: a line with --yes is a confirmed write, not this job"


def test_a_job_spec_with_a_first_word_matches_only_that_command():
    spec = next(s for s in (JobSpec(d.name, d.words, d.forbid, first=d.first) for d in jobs.DESCRIPTORS) if s.name == "mail-sync")
    assert spec.matches(["mail"]) and spec.matches(["mail", "--limit", "5"])
    assert not spec.matches(["gmail", "--sync"]) and not spec.matches(["responses", "--check", "mail"]) and not spec.matches([])
    old = JobSpec("old", ("notices", "--sync"))
    assert old.first == "" and old.matches(["--sync", "notices"])                       # a spec without it matches as before
    sync = JobSpec("gmail-sync", ("gmail", "--sync"), ("--yes",), first="gmail")
    assert sync.matches(["gmail", "--sync"]) and not sync.matches(["gmail", "--sync", "--yes"])


# --- what is registered ----------------------------------------------------------------------------------------------------

def test_only_a_ready_familys_descriptors_are_registered_in_the_jobs_the_engine_knows():
    ready = {d.name for d in jobs.registered()}
    assert ready == {d.name for d in jobs.DESCRIPTORS if d.family in jobs.READY} and ready
    assert ready <= set(JOBS)
    held_back = {d.name for d in jobs.DESCRIPTORS if d.family not in jobs.READY} - ready
    assert held_back and not held_back & set(JOBS)
    assert {"payhoa-form-test", "owner-info-send-plan", "owner-info-email-test", "notices-sync"} <= set(JOBS)   # the first four stay
    for name in ready:
        assert JOBS[name].first and JOBS[name].require[0] == JOBS[name].first


def test_the_property_jobs_are_registered_and_no_longer_wanted():
    from jason.workflows.defs import property as prop

    assert {d.name for d in jobs.DESCRIPTORS if d.family == "property"} == {
        "life-safety-read-report", "life-safety-propose", "contract-terms", "paint-refresh", "vendor-portal-sync"}
    left = {w.split(":", 1)[1].split(" -- ")[0] for w in prop.WANTED if w.startswith("job:")}
    assert left == {"gmail-sync"}                                       # the platform family describes it; it is not registered yet
    assert not left & set(JOBS)


def test_the_registry_modules_import_no_jason_module_and_register_no_approvals_kind():
    text = (PACKAGE / "wanted.py").read_text(encoding="utf-8")
    assert "registry.register(" not in text and ".write_text(" in text            # the doc is its only write
    top = [n for n in ast.parse((PACKAGE / "__init__.py").read_text(encoding="utf-8")).body if isinstance(n, (ast.Import, ast.ImportFrom))]
    assert {getattr(n, "module", None) or n.names[0].name for n in top} == {"__future__", "dataclasses"}
    head = [n for n in ast.parse(text).body if isinstance(n, (ast.Import, ast.ImportFrom))]
    assert not [n for n in head if (getattr(n, "module", None) or "").startswith("jason")]


# --- the wanted list -------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("line, got", [
    ("job:life-safety-propose -- jason life-safety --propose (deficiency propose)", ("job", "life-safety-propose")),
    ("plan:gmail-drafts/insurer-notice -- a draft notice", ("plan", "gmail-drafts/insurer-notice")),
    ("check:executive-note-open", ("check", "executive-note-open")),
    ("job notices-sync-any-key", ("job", "notices-sync-any-key")),
    ("kind payhoa-request-create", ("plan", "payhoa-request-create")),
    ("case gmail-drafts/acknowledgment", ("plan", "gmail-drafts/acknowledgment")),
    ("kind:google.calendar+google.tasks", ("plan", "google.calendar+google.tasks")),
    ("case:gmail-drafts/election-notice", ("plan", "gmail-drafts/election-notice")),
    ("job bill-dry-run: jason sync-bills --dry-run (reads PayHOA)", ("job", "bill-dry-run")),
    ("job mail-sync (mail-triage.2): `jason mail`", ("job", "mail-sync")),
    ("plan annual-packet-docs: --make-templates --yes", ("plan", "annual-packet-docs")),
    ("template:contract-notice -- a notice", None),
    ("command:jason programs -- a program's lifecycle", None),
    ("role:reviewer -- the committee role", None),
    ("clock basis provider: a vendor's published limit", None),
    ("per-step item sets: the letters of a period", None),
])
def test_parse_reads_every_familys_style_and_ignores_templates_commands_roles_and_engine_items(line, got):
    assert wanted.parse(line) == got


def test_every_family_is_read_and_each_wanted_job_is_registered_described_or_given_a_reason():
    found = wanted.wants()
    assert {w.family for w in found} == set(wanted.FAMILIES)
    rows = wanted.report()
    assert set(rows) == set(wanted.FAMILIES)
    assert all(not r["bare"] for r in rows.values()), {f: r["bare"] for f, r in rows.items() if r["bare"]}
    for r in rows.values():
        assert r["jobs"] == r["jobs_met"] + len(r["waiting"]) + len(r["undescribed"]) + len(r["bare"])
        assert r["plans_total"] == r["plans_met"] + len(r["plans"])


def test_a_wanted_plan_kind_counts_as_met_only_when_the_approvals_registry_holds_it():
    kinds, cases = wanted.registered_plans()
    assert {"gmail-drafts", "payhoa-mailroom-send"} <= kinds
    assert "gmail-drafts/proposal-request" in cases and "gmail-drafts/acknowledgment" not in cases
    unmet = {n for r in wanted.report().values() for n in r["plans"]}
    assert not unmet & (kinds | cases)


def test_the_docs_list_of_jobs_and_kinds_still_wanted_matches_the_diff():
    checks.load_all()
    text = wanted.current()
    assert text, "docs/workflows-engine.md has no generated block between the wanted markers"
    assert text.strip() == wanted.markdown().strip(), (
        "the list in docs/workflows-engine.md has drifted from the families' WANTED and the registries; run "
        "python -m jason.workflows.jobs.wanted --write")


def test_the_generated_block_names_the_unmet_and_no_unit_owner_or_address():
    block = wanted.markdown()
    assert "gmail-drafts/acknowledgment" in block and "No approvals kind is added here" in block
    assert "`parcel-gap-lookup` -- no command yet" in block
    assert "CHECKS" not in block and len(CHECKS) > 0
