"""The platform family's workflow definitions (src/jason/workflows/defs/platform.py), against the family page
(docs/workflows/mail-and-platform.md) and the disconnect screen (docs/console/screens/integration-disconnect.md): each one is
valid against the real registries, its steps match the table kept below, its procedure addresses exist, and a few runs show
the branches and the per-letter steps work in a temporary data folder. Everything is made up ("J. Manager", "A. Admin", opaque
ids); no real store, no network, no profile.

The tables record what was built: where the page names a ``check`` that a registered read backs
(``jason.workflows.checks.platform``), the step is a ``check`` step with role ``jason``; where it names a ``check`` or a ``job``
that no registered read or job backs, the step is a ``person`` step (its ``why`` says what it becomes), so the kinds below
differ from the page's on purpose.
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

import jason.workflows.defs.platform as platform
from jason.workflows import api, checks, definitions
from jason.workflows import definitions_general as general
from jason.workflows.readers import CHECKS, JOBS, NamedCheck, StoreReaders
from jason.workflows.types import ClockBasis, Role, StepKind, StepRefused, Visibility, parse_sop
from test_workflows_support import data  # noqa: F401 - the `data` fixture

MANAGER, SECRETARY, ADMIN = "J. Manager", "S. Secretary", "A. Admin"
PEOPLE = {MANAGER: {"manager"}, SECRETARY: {"secretary", "director"}, ADMIN: {"administrator"}}

REPO = Path(__file__).resolve().parents[1]
SOURCE = Path(platform.__file__)

P, B, D, W, PL, C = "person", "branch", "decision", "wait", "plan", "check"
M, A, S, J = "manager", "administrator", "secretary", "jason"


def table(rows: str) -> dict[str, tuple[str, str]]:
    """'1 P M; 2 B M' as {id: (kind, role)}; the letters are the kinds above."""
    kinds = {"P": P, "B": B, "D": D, "W": W, "L": PL, "C": C}
    roles = {"M": M, "A": A, "S": S, "J": J}
    out = {}
    for row in rows.split(";"):
        step, kind, role = row.split()
        out[step] = (kinds[kind], roles[role])
    return out


EXPECTED = {
    "mail-triage": table("1 C J; 2 P M; 3 P M; 4 C J; 5 P M; 6 B M; 7 P M; 8 P M; 9 W M; 10 P M; 11 D S; 12 C J"),
    "email-conversation": table("1 C J; 2 P M; 3 C J; 4 P M; 5 B M; 6 P M; 7 P M; 8 B M; 9 P M; 10 P M; 11 P M; 12 W M; "
                                "13 P M; 14 P M; 15 P M"),
    "gmail-draft": table("1 P M; 2 P M; 3 B M; 4 D S; 5 P M; 6 P M; 7 L M; 8 P M; 9 W M; 10 P M"),
    "response-inbox": table("1 P M; 2 C J; 3 P M; 4 B M; 5 P M; 6 P M; 7 P M; 8 P M; 9 P M; 10 C J; 11 P M"),
    "integration-connect": table("1 C J; 2 P A; 3 P A; 4 P A; 5 P A; 6 P A; 7 P A; 8 P A; 9 P A; 10 P A; 11 W A; 12 W A; "
                                 "13 B A; 13.1 P A; 13.2 P A; 13.3 P A; 13.4 P A"),
    "service-run": table("1 C J; 2 C J; 3 P A; 4 B A; 5 P A; 6 P A; 7 P A; 8 D S; 9 B A; 10 C J; 11 P A; 12 P A"),
    "check-in": table("1 P A; 2 P A; 3 P A; 4 P A; 5 P A; 6 P A; 7 P A"),
}
"""{definition: {step number: (kind, role)}}: the page's tables, with a read or a job no registry backs built as a person's step
and a read that is registered built as a check (a wait that a read ends keeps its kind: ``mail-triage.9``)."""

CHECKS_USED = {
    "mail-triage.1": "mail-fresh", "mail-triage.4": "mail-lanes", "mail-triage.9": "mail-scanned", "mail-triage.12": "mail-period-chosen",
    "email-conversation.1": "gmail-fresh", "email-conversation.3": "thread-status",
    "response-inbox.2": "responses-channels", "response-inbox.10": "responses-outstanding",
    "integration-connect.1": "instance-which", "service-run.1": "instance-which", "service-run.2": "service-heartbeat",
    "service-run.10": "service-queue",
}
"""{step id: the registered read it names}: the twelve steps a read of ``jason.workflows.checks.platform`` answers."""

SUBJECTS = {"mail-triage": "period", "email-conversation": "thread", "gmail-draft": "draft", "response-inbox": "request",
            "integration-connect": "integration", "service-run": "service", "check-in": "change"}

SOPS = {  # step id -> the procedure step it addresses, by what the step says
    "mail-triage": {}, "gmail-draft": {},
    "email-conversation": {"email-conversation.9": "respond#3"},
    "response-inbox": {"response-inbox.1": "owner-info-cycle#14", "response-inbox.5": "owner-info-cycle#14",
                       "response-inbox.6": "owner-info-cycle#14", "response-inbox.7": "owner-info-cycle#14",
                       "response-inbox.10": "owner-info-cycle#15", "response-inbox.11": "owner-info-cycle#17"},
    "integration-connect": {"integration-connect.1": "onboard#1", "integration-connect.3": "onboard#13",
                            "integration-connect.5": "onboard#6", "integration-connect.6": "onboard#6",
                            "integration-connect.7": "onboard#6", "integration-connect.8": "onboard#13",
                            "integration-connect.10": "onboard#14"},
    "service-run": {"service-run.1": "onboard#1", "service-run.3": "onboard#14", "service-run.7": "onboard#14"},
    "check-in": {f"check-in.{i}": f"check-in#{i}" for i in range(1, 6)},
}

BUILT = {b().key: b for b in platform.BUILDERS}


@pytest.fixture(autouse=True)
def fresh():
    definitions.reset()
    yield
    definitions.reset()


def roles_of(by):
    return PEOPLE.get(by, ())


def shelf():
    return general.shelf_resolver(REPO / "data")


# --- the definitions ------------------------------------------------------------------------------------------------------

def test_the_family_builds_seven_definitions_and_registers_the_managers_four_and_the_administrators_three():
    assert set(BUILT) == set(EXPECTED) == set(platform.KEYS) | set(platform.ADMIN_KEYS)
    assert [b().key for b in platform.BOARD_BUILDERS] == list(platform.KEYS)
    assert [b().key for b in platform.ADMIN_BUILDERS] == list(platform.ADMIN_KEYS)
    assert [b().key for b in platform.BUILDERS] == [*platform.KEYS, *platform.ADMIN_KEYS]
    assert not set(platform.KEYS) & set(platform.ADMIN_KEYS)
    assert all(isinstance(w, str) and w for w in platform.WANTED) and len(set(platform.WANTED)) == len(platform.WANTED)


@pytest.mark.parametrize("key", sorted(EXPECTED))
def test_each_definition_validates_against_the_real_registries(key):
    wf = BUILT[key]()
    problems = definitions.validate(wf, jobs=set(JOBS), workflows=set(BUILT) | {w.key for w in definitions.all_definitions()},
                                    resolve_law=shelf())
    assert problems == [], [str(p) for p in problems]
    assert definitions.drift([wf]) == []
    assert wf.family == "platform" and wf.subject == SUBJECTS[key] and wf.dates == () and wf.clocks == ()


@pytest.mark.parametrize("key", sorted(EXPECTED))
def test_each_definitions_steps_match_the_table(key):
    wf = BUILT[key]()
    want = EXPECTED[key]
    assert [s.id for s in wf.steps] == [f"{key}.{n}" for n in want]                 # the page's order, ids <key>.<n>
    assert {s.id: (s.kind.value, s.role.value) for s in wf.steps} == {f"{key}.{n}": v for n, v in want.items()}
    assert all(s.title and s.why for s in wf.steps)
    assert {x for p in wf.phases for x in p.steps} == {s.id for s in wf.steps}      # every step is on the rail once
    assert sum(len(p.steps) for p in wf.phases) == len(wf.steps)
    assert all(isinstance(s.role, Role) for s in wf.steps)


def test_step_counts_are_the_pages_tables():
    assert {k: len(v) for k, v in EXPECTED.items()} == {
        "mail-triage": 12, "email-conversation": 15, "gmail-draft": 10, "response-inbox": 11, "integration-connect": 17,
        "service-run": 12, "check-in": 7}


@pytest.mark.parametrize("key", sorted(EXPECTED))
def test_sop_addresses_exist_and_only_where_mapped(key):
    from jason.community import procedures

    wf = BUILT[key]()
    got = {s.id: s.sop for s in wf.steps if s.sop}
    assert got == SOPS[key]
    for address in got.values():
        proc, index = parse_sop(address)
        found = procedures.find(proc)
        assert found is not None and 1 <= index <= len(found.steps), address
    assert wf.procedure == ("check-in" if key == "check-in" else "")


def test_the_check_steps_name_the_registered_reads_and_no_step_is_a_job_and_the_one_plan_is_the_registered_gmail_drafts_kind():
    checks.load_all()
    plans, named = {}, {}
    for key in BUILT:
        for s in BUILT[key]().steps:
            assert s.kind is not StepKind.JOB and not s.job and not s.spawns, s.id             # no registered job backs them
            if s.check is not None:
                assert isinstance(s.check, NamedCheck) and s.check.name in CHECKS, s.id        # a name, and a read that exists
                assert s.kind in (StepKind.CHECK, StepKind.WAIT), s.id
                named[s.id] = s.check.name
            if s.kind is StepKind.CHECK:
                assert s.check is not None and s.role is Role.JASON and not s.record and s.skip is None, s.id
            if s.kind is StepKind.PLAN:
                plans[s.id] = s.plan_kind
    assert named == CHECKS_USED
    assert plans == {"gmail-draft.7": "gmail-drafts"}
    assert {"mail-findings", "thread-leads", "thread-closed", "vault-answers"}.isdisjoint(CHECKS)      # the wanted reads are not smuggled in


def test_the_wanted_list_names_every_read_job_and_kind_the_person_steps_say_they_become():
    checks.load_all()
    text = "\n".join(platform.WANTED)
    named = 0
    for key in BUILT:
        for s in BUILT[key]().steps:
            for word in ("check", "job"):
                if f"Becomes a {word} (" in s.why:
                    name = s.why.split(f"Becomes a {word} (", 1)[1].split(")", 1)[0]
                    assert f"{word} {name} (" in text, (s.id, name)
                    assert name not in (CHECKS if word == "check" else JOBS), name       # wanted, not yet registered
                    assert s.kind is StepKind.PERSON, s.id
                    named += 1
    assert named >= 12
    assert "plan payhoa-requests-from-email (email-conversation.6)" in text and "plan gmail-thread-reply" in text


def test_a_wanted_read_is_one_not_yet_built_and_a_built_read_is_no_longer_wanted():
    checks.load_all()
    wanted = {line.split()[1] for line in platform.WANTED if line.startswith("check ")}
    assert wanted == {"mail-findings", "thread-leads", "thread-closed", "draft-source", "draft-preview", "responses-recognized",
                      "integration-state", "vault-answers", "service-limits", "service-verify"}
    assert not wanted & set(CHECKS)
    assert set(CHECKS_USED.values()) <= set(CHECKS) and not set(CHECKS_USED.values()) & wanted


def test_every_clock_has_a_basis_a_label_and_the_two_statutes_are_the_only_law_clocks():
    law = {}
    for key in BUILT:
        wf = BUILT[key]()
        for s in wf.steps:
            if s.clock is None:
                continue
            assert isinstance(s.clock.basis, ClockBasis) and s.clock.label, s.id
            if s.clock.basis is ClockBasis.PROPOSED_POLICY:
                assert s.clock.label.lower().find("proposed") >= 0, s.id        # a proposed number is labeled, never a stamp
            if s.clock.basis is ClockBasis.LAW:
                law[s.id] = s.clock.cite
                assert s.skip is None and s.is_legal                            # a legal step cannot be skipped
    assert law == {"mail-triage.3": "CIV 4530(a)(1)", "email-conversation.6": "CIV 5210(b)"}


def test_the_statutes_cited_resolve_on_the_authorities_shelf_when_it_is_here():
    resolve = shelf()
    if resolve is None or resolve("CIV 4530(a)(1)") is None:
        pytest.skip("the authorities shelf is not on this checkout")
    assert resolve("CIV 4530(a)(1)") is True and resolve("CIV 5210(b)") is True


def test_a_general_email_reply_time_is_proposed_policy_with_no_date():
    clock = BUILT["email-conversation"]().step("email-conversation.4").clock
    assert clock.basis is ClockBasis.PROPOSED_POLICY and not clock.slot and "response-standards" in clock.label
    assert "not adopted" in clock.label


def test_the_registered_runs_use_no_clock_basis_the_work_backend_does_not_compose():
    for key in platform.KEYS:
        for s in BUILT[key]().steps:
            assert s.clock is None or s.clock.basis is not ClockBasis.COUNTERPARTY, s.id


# --- the boundaries: no sending, no association, no secret -----------------------------------------------------------------

VERBS = {"send", "--send", "forward", "--forward", "shred", "--shred", "discard", "--discard", "scan", "--scan", "--approve",
         "--decide", "revoke", "--revoke", "--cancel"}


def test_no_command_sends_mails_forwards_shreds_discards_scans_or_approves():
    for key in BUILT:
        for s in BUILT[key]().steps:
            words = set(s.command.replace(";", " ").replace("(", " ").replace(")", " ").split())
            assert not words & VERBS, (s.id, s.command)
            assert "--approve" not in s.command


def test_the_module_is_pure_data_and_names_no_association_or_profile():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    allowed = {"__future__", "typing", "jason.workflows.types", "jason.workflows.readers", "jason.workflows.definitions_general"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert {a.name.split(".")[0] for a in node.names} <= set(sys.stdlib_module_names), node.names
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0 and node.module in allowed, node.module
    text = SOURCE.read_text(encoding="utf-8").lower()
    for word in ("mystique", "jason_mystique", "123 main", "@example"):
        assert word not in text
    code = (
        "import sys, json\n"
        "import jason\n"
        "before = set(sys.modules)\n"
        "import jason.workflows.defs.platform as p\n"
        "[b() for b in p.BUILDERS + p.ADMIN_BUILDERS]\n"
        "new = sorted(m for m in set(sys.modules) - before if m.split('.')[0] in "
        "('jason', 'mystique', 'jason_mystique', 'payhoa', 'google'))\n"
        "print(json.dumps(new))\n"
    )
    out = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    loaded = json.loads(out.stdout.strip().splitlines()[-1])                    # only the engine's own modules, and no profile
    assert {"jason.workflows", "jason.workflows.defs", "jason.workflows.defs.platform", "jason.workflows.types",
            "jason.workflows.readers"} <= set(loaded)
    assert all(m in ("jason.workflows", "jason.locks") or m.startswith("jason.workflows.") for m in loaded), loaded   # the stores' lock


def test_the_triage_read_step_holds_a_letter_that_carries_a_credential():
    read = BUILT["mail-triage"]().step("mail-triage.5")
    assert read.repeat.value == "per item"
    assert "read at a terminal" in read.record and "read at a terminal" in read.why
    assert "credential" in read.why and "opens in no screen" in read.why
    assert "no word of the letter" in BUILT["mail-triage"]().step("mail-triage.7").record               # the choice carries no word of the letter


def test_a_gmail_draft_never_records_an_address_and_never_sends():
    wf = BUILT["gmail-draft"]()
    assert "no address" in wf.step("gmail-draft.5").record
    assert "never sends" in wf.step("gmail-draft.8").why
    assert wf.step("gmail-draft.7").plan_kind == "gmail-drafts" and wf.step("gmail-draft.7").role is Role.MANAGER
    assert all(c in "proposal-request hearing meeting-notice" for c in platform.CASES)
    assert platform.CASES == ("proposal-request", "hearing", "meeting-notice")


def test_the_connect_run_does_not_assume_the_vault_and_holds_no_secret():
    wf = BUILT["integration-connect"]()
    for n in ("3", "4"):
        step = wf.step(f"integration-connect.{n}")
        assert step.skip is not None and step.skip.roles == (Role.ADMINISTRATOR,)
    assert "development" in wf.step("integration-connect.3").why and "hosted" in wf.step("integration-connect.3").why
    assert "hosted" in wf.step("integration-connect.6").why
    for s in wf.steps:
        assert s.role in (Role.ADMINISTRATOR, Role.JASON) and (s.role is Role.JASON) == (s.kind is StepKind.CHECK)
        assert "password" not in s.record.lower() and "token" not in s.record.lower().replace("token name", "")
    assert wf.step("integration-connect.8").command == "jason integrations check KEY --live --by NAME"
    assert wf.step("integration-connect.6").record.endswith("(never its value)")


def test_the_disconnect_is_a_branch_of_four_ordered_person_steps_and_jason_revokes_nothing():
    wf = BUILT["integration-connect"]()
    branch = wf.step("integration-connect.13")
    paths = {c.key: c.steps for c in branch.choices}
    ic = "integration-connect."
    assert paths == {"keep": (), "pause-instead": (ic + "13.1",),
                     "disconnect": tuple(ic + n for n in ("13.1", "13.2", "13.3", "13.4"))}
    chain = [wf.step(ic + n) for n in ("13.1", "13.2", "13.3", "13.4")]
    assert [s.needs for s in chain] == [(ic + "13",), (ic + "13.1",), (ic + "13.2",), (ic + "13.3",)]
    assert all(s.kind is StepKind.PERSON and s.role is Role.ADMINISTRATOR for s in chain)
    assert "jason cannot revoke" in chain[1].why and chain[1].command == ""             # the revoke is the provider's, by hand
    assert chain[0].command.startswith("jason cadence --pause")                        # the one part that is built
    assert "not built" in branch.why


def test_the_administrators_runs_are_registered_as_admin_definitions_and_check_in_is_not_started_from_the_console():
    vis = {key: BUILT[key]().visibility for key in BUILT}
    assert {k for k, v in vis.items() if v is Visibility.ADMIN} == set(platform.ADMIN_KEYS)
    assert {k for k, v in vis.items() if v is Visibility.BOARD} == set(platform.KEYS)
    assert [k for k in BUILT if not BUILT[k]().console_start] == ["check-in"]
    assert all(s.role is Role.ADMINISTRATOR or s.kind in (StepKind.DECISION, StepKind.CHECK)
               for key in platform.ADMIN_KEYS for s in BUILT[key]().steps)


# --- registration ---------------------------------------------------------------------------------------------------------

def test_register_general_registers_the_seven_beside_the_existing_two_the_administrators_three_as_admin_definitions():
    keys = [w.key for w in general.register_general(REPO / "data")]
    assert {"owner-info-cycle", "control-adoption", *platform.KEYS, *platform.ADMIN_KEYS} <= set(keys)
    assert all(definitions.find(k) is not None for k in (*platform.KEYS, *platform.ADMIN_KEYS))
    assert all(definitions.find(k).visibility is Visibility.ADMIN for k in platform.ADMIN_KEYS)
    assert len(keys) == len(set(keys))                                                  # no key is taken twice


# --- runs: the branches and the per-letter steps ----------------------------------------------------------------------------

def readers_for(data):
    """The engine's world over the temporary folder: the checks of this family read the stores put there."""
    return StoreReaders(data, community=None)


def start(data, key, subject, label, items=()):
    general.register_general()
    out = api.start(data, key, subject, label, {}, MANAGER, items=items, yes=True)
    rid = out["run"]["id"]
    refresh(data, rid)
    return rid


def refresh(data, rid):
    """Open the run again: the resume runs the checks that are ready now and appends only what changed."""
    return api.open_run(data, rid, MANAGER, roles_of=roles_of, yes=True, readers=readers_for(data))


def put_stores(data, *, threads=(), letters=(), scanned=("m-0001",), stale=False):
    """Made-up, fresh stores: the Gmail headers of each thread (one inbound message from a vendor) and the mail store."""
    now = datetime.now(timezone.utc)
    stamp = "2000-01-01T00:00:00+00:00" if stale else now.isoformat(timespec="seconds")
    mails = [{"mailId": m, "received": now.date().isoformat(), "sender": "Vendor Example", "kind": "advertising",
              "urgency": "file", "scanned": m in scanned, "deadlines": [], "aiSummary": []} for m in letters]
    messages = [{"messageId": f"{t}-1", "threadId": t, "at": now.isoformat(timespec="seconds"), "direction": "in",
                 "domains": ["vendor.example"], "parties": ["vendor.example"], "subject": "A question",
                 "people": [["Vendor Example", "v@vendor.example", "from"]], "attachments": []} for t in threads]
    for relative, body in (("gmail/correspondence.json", {"syncedAt": stamp, "messages": messages}),
                           ("mail/items.json", {"syncedAt": stamp, "items": mails})):
        path = data / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(body), encoding="utf-8")


def states(data, rid):
    return {s["id"]: s["state"] for s in api.show(data, rid)["steps"]}


def attest(data, rid, key, n, by=MANAGER, **more):
    return api.attest(data, rid, f"{key}.{n}", by, roles_of=roles_of, record=more.pop("record", "recorded"), **more)


def test_an_email_thread_that_is_a_notice_or_held_ends_at_the_route(data):
    for choice in ("notice", "held"):
        thread = f"{choice}0001"
        put_stores(data, threads=(thread,))
        rid = start(data, "email-conversation", f"thread:{thread}", "Thread " + choice)
        got = states(data, rid)
        assert got["email-conversation.1"] == "done"                                   # the Gmail store was read a moment ago
        api.skip(data, rid, "email-conversation.2", MANAGER, roles_of=roles_of, reason="fresh")
        refresh(data, rid)
        assert states(data, rid)["email-conversation.3"] == "done"                     # the thread is in the store: its status was read
        attest(data, rid, "email-conversation", "4")
        api.attest(data, rid, "email-conversation.5", MANAGER, roles_of=roles_of, choice=choice)
        got = states(data, rid)
        ec = "email-conversation."
        assert all(got[ec + str(n)] == "skipped" for n in range(6, 15)), got
        assert got[ec + "15"] == "needs a person"                                      # close is the only step left
        attest(data, rid, "email-conversation", "15")
        assert api.show(data, rid)["state"] == "done"


def test_a_stale_gmail_store_holds_the_thread_run_at_its_first_step_until_it_is_read(data):
    put_stores(data, threads=("stale0001",), stale=True)
    rid = start(data, "email-conversation", "thread:stale0001", "Thread stale")
    one = next(s for s in api.show(data, rid)["steps"] if s["id"] == "email-conversation.1")
    assert one["state"] == "failed" and "more than 1 hour ago" in one["reason"] and "jason gmail --sync" in one["reason"]
    with pytest.raises(StepRefused, match="check step"):
        api.attest(data, rid, "email-conversation.1", MANAGER, roles_of=roles_of, record="read")      # no person's word stands in
    put_stores(data, threads=("stale0001",))                                                              # a person ran `jason gmail --sync`
    refresh(data, rid)
    assert states(data, rid)["email-conversation.1"] == "done"
    events = json.dumps(api.show(data, rid, events=True)["events"])
    assert not re.search(r"[\w.+-]+@[\w-]+\.[A-Za-z]{2,}", events) and "A question" not in events and "Vendor Example" not in events


def test_a_thread_missing_from_the_gmail_store_fails_its_status_read_and_a_wait_for_the_other_side_is_still_a_persons(data):
    put_stores(data, threads=("other0001",))
    rid = start(data, "email-conversation", "thread:absent0001", "Thread absent")
    api.skip(data, rid, "email-conversation.2", MANAGER, roles_of=roles_of, reason="fresh")
    refresh(data, rid)
    three = next(s for s in api.show(data, rid)["steps"] if s["id"] == "email-conversation.3")
    assert three["state"] == "failed" and "not in the Gmail store" in three["reason"]
    assert states(data, rid)["email-conversation.4"] == "blocked" or states(data, rid)["email-conversation.4"] == "not started"


def test_an_emailed_request_carries_the_law_clock_and_a_vendor_thread_does_not(data):
    put_stores(data, threads=("request0001", "vendor0001"))
    rid = start(data, "email-conversation", "thread:request0001", "Thread request")
    api.skip(data, rid, "email-conversation.2", MANAGER, roles_of=roles_of, reason="fresh")
    refresh(data, rid)
    attest(data, rid, "email-conversation", "4")
    api.attest(data, rid, "email-conversation.5", MANAGER, roles_of=roles_of, choice="request")
    assert states(data, rid)["email-conversation.6"] == "needs a person"
    clocks = {c["key"]: c for c in api.show(data, rid)["clocks"]}
    assert clocks["email-conversation.6"]["basis"] == "law" and clocks["email-conversation.6"]["cite"] == "CIV 5210(b)"
    with pytest.raises(StepRefused, match="cannot be skipped"):
        api.skip(data, rid, "email-conversation.6", MANAGER, roles_of=roles_of, reason="no")
    other = start(data, "email-conversation", "thread:vendor0001", "Thread vendor")
    api.skip(data, other, "email-conversation.2", MANAGER, roles_of=roles_of, reason="fresh")
    refresh(data, other)
    attest(data, other, "email-conversation", "4")
    api.attest(data, other, "email-conversation.5", MANAGER, roles_of=roles_of, choice="vendor")
    assert states(data, other)["email-conversation.6"] == "skipped"


def test_a_reply_goes_through_a_draft_and_a_send_and_a_forward_skips_them(data):
    put_stores(data, threads=("reply0001",))
    rid = start(data, "email-conversation", "thread:reply0001", "Thread reply")
    ec = "email-conversation"
    api.skip(data, rid, f"{ec}.2", MANAGER, roles_of=roles_of, reason="fresh")
    refresh(data, rid)
    attest(data, rid, ec, "4")
    api.attest(data, rid, f"{ec}.5", MANAGER, roles_of=roles_of, choice="vendor")
    attest(data, rid, ec, "7")
    api.attest(data, rid, f"{ec}.8", MANAGER, roles_of=roles_of, choice="forward")
    got = states(data, rid)
    assert got[f"{ec}.9"] == got[f"{ec}.11"] == "skipped" and got[f"{ec}.10"] == "needs a person"
    with pytest.raises(StepRefused, match="record"):
        api.attest(data, rid, f"{ec}.10", MANAGER, roles_of=roles_of)                  # the assignee and date are the record


def test_a_purpose_that_commits_the_association_ends_the_draft_at_the_boards_decision(data):
    rid = start(data, "gmail-draft", "hearing:unit-0001", "Draft for a hearing")
    gd = "gmail-draft"
    attest(data, rid, gd, "1")
    attest(data, rid, gd, "2")
    api.attest(data, rid, f"{gd}.3", MANAGER, roles_of=roles_of, choice="yes")
    got = states(data, rid)
    assert all(got[f"{gd}.{n}"] == "skipped" for n in range(5, 11)), got
    assert got[f"{gd}.4"] == "needs a person"
    with pytest.raises(StepRefused, match="secretary"):
        api.attest(data, rid, f"{gd}.4", MANAGER, roles_of=roles_of, outcome="approved", record="minutes")


def test_a_case_that_commits_nothing_reaches_the_plan_and_waits_for_an_approval(data):
    rid = start(data, "gmail-draft", "proposal-request:system-0001", "Draft for a proposal request")
    gd = "gmail-draft"
    for n in ("1", "2"):
        attest(data, rid, gd, n)
    api.attest(data, rid, f"{gd}.3", MANAGER, roles_of=roles_of, choice="no")
    assert states(data, rid)[f"{gd}.4"] == "skipped"
    attest(data, rid, gd, "5", record="2 addresses")
    attest(data, rid, gd, "6")
    assert states(data, rid)[f"{gd}.7"] == "ready"                                      # a plan is adopted, never attested
    with pytest.raises(StepRefused, match="plan step"):
        api.attest(data, rid, f"{gd}.7", MANAGER, roles_of=roles_of, record="x")


def test_each_letter_of_a_period_is_read_by_its_opaque_id_and_a_held_one_is_read_at_a_terminal(data):
    put_stores(data, letters=("m-0001", "m-0002"))
    rid = start(data, "mail-triage", "period:2099-10-05", "Mail since 2099-10-05", items=("m-0001", "m-0002"))
    mt = "mail-triage"
    assert states(data, rid)[f"{mt}.1"] == "done"                                       # the mail store was read a moment ago
    api.skip(data, rid, f"{mt}.2", MANAGER, roles_of=roles_of, reason="the mailbox is fresh")
    refresh(data, rid)
    attest(data, rid, mt, "3")
    got = states(data, rid)
    assert got[f"{mt}.4"] == "done"                                                     # the lanes were counted
    api.attest(data, rid, f"{mt}.5", MANAGER, roles_of=roles_of, record="read", item="m-0001")
    mid = next(s for s in api.show(data, rid)["steps"] if s["id"] == f"{mt}.5")
    assert mid["state"] == "needs a person" and [i["state"] for i in mid["items"]] == ["done", "needs a person"]
    api.attest(data, rid, f"{mt}.5", MANAGER, roles_of=roles_of, record="read at a terminal", item="m-0002")
    assert states(data, rid)[f"{mt}.5"] == "done"
    with pytest.raises(StepRefused, match="item"):
        api.attest(data, rid, f"{mt}.7", MANAGER, roles_of=roles_of, record="keep")     # a per-letter step names its letter
    api.attest(data, rid, f"{mt}.7", MANAGER, roles_of=roles_of, record="keep", item="m-0001")
    events = json.dumps(api.show(data, rid, events=True)["events"])
    assert "m-0001" in events and not re.search(r"[\w.+-]+@[\w-]+\.[A-Za-z]{2,}", events)       # ids only; no address
    assert "Vendor Example" not in events


def test_the_period_closes_when_every_letter_has_a_recorded_choice_and_a_scan_ends_its_wait(data):
    from jason.tasks import mail_triage

    put_stores(data, letters=("m-0001", "m-0002"), scanned=("m-0001",))
    rid = start(data, "mail-triage", "period:2099-10-06", "Mail since 2099-10-06", items=("m-0001", "m-0002"))
    mt = "mail-triage"
    api.skip(data, rid, f"{mt}.2", MANAGER, roles_of=roles_of, reason="the mailbox is fresh")
    refresh(data, rid)
    attest(data, rid, mt, "3")
    for number, record in (("5", "read"), ("7", "scan"), ("8", "done at the service")):       # a step waits for every letter of the one before
        for item in ("m-0001", "m-0002"):
            api.attest(data, rid, f"{mt}.{number}", MANAGER, roles_of=roles_of, record=record, item=item)
    refresh(data, rid)
    wait = next(s for s in api.show(data, rid)["steps"] if s["id"] == f"{mt}.9")
    assert wait["state"] != "done"
    assert [i["state"] for i in wait["items"]].count("done") == 1                       # the scanned letter ended its wait; the other waits
    twelve = next(s for s in api.show(data, rid)["steps"] if s["id"] == f"{mt}.12")
    assert twelve["state"] == "failed" and "0 of 2 letter(s) have a recorded choice" in twelve["reason"]
    for item in ("m-0001", "m-0002"):
        mail_triage.choose(data, item, choice="scan", by=MANAGER)
    refresh(data, rid)
    twelve = next(s for s in api.show(data, rid)["steps"] if s["id"] == f"{mt}.12")
    assert twelve["state"] == "done"


def test_the_mail_triage_run_needs_yes_to_start_because_of_the_escrow_clock(data):
    general.register_general()
    with pytest.raises(StepRefused, match="legal clock"):
        api.start(data, "mail-triage", "period:2099-10-05", "Mail", {}, MANAGER)


# --- the simplest definition, start to done ---------------------------------------------------------------------------------

def test_check_in_runs_from_start_to_done_in_a_temporary_folder(data):
    definitions.register(platform.check_in(), jobs=set(JOBS))
    out = api.start(data, "check-in", "change:2099-10-12-a", "Check in a change", {}, ADMIN)
    rid = out["run"]["id"]
    assert out["run"]["state"] == "draft"
    api.open_run(data, rid, ADMIN, roles_of=roles_of)
    ci = "check-in"
    for n in ("1", "2", "3", "4"):
        api.attest(data, rid, f"{ci}.{n}", ADMIN, roles_of=roles_of, record="checked")
    with pytest.raises(StepRefused, match="role"):
        api.attest(data, rid, f"{ci}.5", MANAGER, roles_of=roles_of, record="commit abc")      # not the manager's
    api.attest(data, rid, f"{ci}.5", ADMIN, roles_of=roles_of, record="commit abc")
    for n in ("6", "7"):
        api.skip(data, rid, f"{ci}.{n}", ADMIN, roles_of=roles_of, reason="nothing went wrong")
    final = api.show(data, rid)
    assert final["state"] == "done" and all(s["state"] in ("done", "skipped") for s in final["steps"])
    assert api.verify(data, rid)["ok"]
