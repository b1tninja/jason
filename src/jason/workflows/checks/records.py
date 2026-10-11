"""The reads of the records family (src/jason/workflows/defs/records.py): the ones an existing read function or store answers.

Each is registered into ``jason.workflows.readers.CHECKS`` when this module is imported (``checks.load_all``). Each reads
stores on disk through the functions that already read them, writes nothing, calls no outside system, and loads no profile
by name: the community is the readers' own lazy one, and the chosen profile's name is read with ``resolve_community``, which
loads nothing. A store that cannot be read, or that holds nothing to read, returns ``ok=False`` with the reason; no read is
ok by default.

- ``active-community``: the profile this process serves is the one the run is about.
- ``onboard-gates-read``, ``onboard-gate-start`` / ``-ingest`` / ``-establish`` / ``-operate`` / ``-adopt``,
  ``onboard-checklist``: the onboarding checklist and its five gates (``jason.community.onboarding``), as ``jason onboard``
  reads them. A gate read is jason's reading of the checklist; the board decides what is done.
- ``record-slots-read``: the record checklist's counts by state (``jason.tasks.record_slots``).
- ``key-document-status``: one key document entry's status (``jason.tasks.key_documents``).
- ``ingest-gate``: the last ingest report (``jason.tasks.ingest.gate``).
- ``split-review``: one draft split's counts (``jason.tasks.split_session``), flags included when the page facts are measured.
- round two: ``scratch-room`` (``jason storage --check``, in whole gigabytes and a count of problems, never a path),
  ``profile-own-facts`` (each private-facts topic is in the profile's own folder, ``jason spec``), ``key-document-verified``
  (an entry has a recording number and a recorded copy on disk that carries it), ``request-kinds-mapped`` (each kind a
  records request asks for maps to a paragraph of CIV 5200(a) and a slot of the record checklist), and ``record-compare`` (each
  pin of a slot has a kept reading, with the verdicts counted).

Not here, and why: ``document-kind-read`` would fail a step that the next step needs done (a library file with no kind is
what document-intake step 3 answers, and a failed check blocks the steps after it); ``quotes-verified`` has no stored answer to
read (the answer is a file handed to ``jason verify-quotes``); ``designation-on-file`` has no store; ``parcel-strand-gaps``
needs the ownership chain, and the stores that read it (``OwnershipStore``, ``TaxStore``, ``IndexCache``) create their tables
when they are opened, which a read may not do.

Privacy: a message carries counts, checklist item keys, statuses, and states. It names no file, owner, or confidential kind.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jason.workflows.checks import check
from jason.workflows.readers import StoreReaders
from jason.workflows.types import CheckResult, RunView

STAGES = ("start", "ingest", "establish", "operate", "adopt")
SHOWN = 8
"""How many item keys a message lists before it says "and N more"."""


# --- small helpers --------------------------------------------------------------------------------------------------

def _handle(view: RunView, *kinds: str) -> str:
    """The run's subject handle: the part after ``kind:`` for one of ``kinds``, or the whole subject when it has no colon."""
    head, sep, rest = str(getattr(view, "subject", "") or "").partition(":")
    if sep:
        return rest.strip() if head.strip().lower() in kinds else ""
    return head.strip()


def _active() -> tuple[str, str]:
    """(the chosen profile's name, "") or ("", why not). Loads no profile."""
    try:
        from jason.community.profile import resolve_community

        return resolve_community().name, ""
    except Exception as exc:  # noqa: BLE001 - no community chosen: the reads that need one say so
        return "", f"no community is chosen ({type(exc).__name__}: {exc})"


def _mismatch(view: RunView) -> str:
    """Why the active community is not the run's, or "" when it is (or the run names none)."""
    want = _handle(view, "association", "profile", "community").lower()
    if not want:
        return ""
    have, why = _active()
    if why:
        return why
    if have != want:
        return f"the active community is {have}, not the run's {want}: choose it first (jason use KEY); nothing was read"
    return ""


def _keys(keys: list[str]) -> str:
    shown = ", ".join(keys[:SHOWN])
    return shown + (f" and {len(keys) - SHOWN} more" if len(keys) > SHOWN else "")


def _settings() -> Any:
    try:
        from jason.config import Settings

        return Settings.load()
    except Exception:  # noqa: BLE001 - no .env: the settings-based checklist items read as not set
        return None


def _fail(message: str) -> CheckResult:
    return CheckResult(False, (), message)


# --- the active community -------------------------------------------------------------------------------------------------

@check("active-community")
def active_community(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """The profile this process serves is the profile the run is about (the subject, ``association:KEY``). A mismatch
    fails the check: no job may run for the wrong association."""
    want = _handle(view, "association", "profile", "community").lower()
    if not want:
        return _fail("the run's subject names no profile (association:KEY), so the active community cannot be compared")
    have, why = _active()
    if why:
        return _fail(why)
    if have != want:
        return _fail(f"the active community is {have}, but the run is about {want}: jason use {want}, then open the run again")
    return CheckResult(True, (), f"the active community is {have}, the run's subject")


# --- the onboarding checklist and its gates -------------------------------------------------------------------------------

def _checklist(readers: StoreReaders, view: RunView) -> tuple[Any, str]:
    """((the checklist's results, the gates' results), "") or (None, why not). Read-only: the same reading ``jason onboard``
    and the ``onboarding_status`` tool take, without ranking the questions."""
    problem = _mismatch(view)
    if problem:
        return None, problem
    try:
        from jason.community import intake
        from jason.community.onboarding import check as run_checklist, gates
        from jason.tasks.onboarding import load_context

        community = readers.community
        if community is None:
            return None, "no community is chosen, so the checklist cannot be read"
        ctx = load_context(community, Path(readers.data_dir), settings=_settings(), asks=tuple(intake.load(Path(readers.data_dir))))
        results = run_checklist(ctx)
        return (results, gates(results, ctx)), ""
    except Exception as exc:  # noqa: BLE001 - a store that cannot be read fails the check with the reason
        return None, f"the checklist cannot be read ({type(exc).__name__}: {exc})"


def _evidence(readers: StoreReaders) -> tuple[str, ...]:
    return readers.evidence_entries(("file:intake/asks.json", "glob:onboarding/ingest-*.json"))


@check("onboard-gates-read")
def onboard_gates_read(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """The checklist and the five gates can be read: the counts by status, and which gates are open. It passes when it reads;
    the counts are information for a person, never a verdict."""
    read, why = _checklist(readers, view)
    if read is None:
        return _fail(why)
    from jason.community.onboarding import counts

    results, gate_results = read
    tally = counts(results)
    states = ", ".join(f"{g.gate.stage.value} {'open' if g.open else 'closed'}" for g in gate_results)
    return CheckResult(True, _evidence(readers), f"{len(results)} checklist items: {tally['present']} present, "
                       f"{tally['partial']} partial, {tally['missing']} missing; gates: {states}")


def _gate(stage: str):
    def read(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
        got, why = _checklist(readers, view)
        if got is None:
            return _fail(why)
        _, gate_results = got
        found = next((g for g in gate_results if g.gate.stage.value == stage), None)
        if found is None:
            return _fail(f"the {stage} gate is not among the checklist's gates")
        if found.open:
            return CheckResult(True, _evidence(readers), f"the {stage} gate reads open: {found.gate.opens}")
        parts = [f"{r.item.key} {r.status.value}" for r in found.waiting]
        failed = sum(1 for f in found.findings if not f.passed)
        waiting = f"{len(found.waiting)} checklist item(s) not present: {_keys(parts)}" if found.waiting else ""
        own = f"{failed} of the gate's own check(s) not passed" if failed else ""
        return _fail(f"the {stage} gate reads closed ({'; '.join(x for x in (waiting, own) if x)}); the board decides "
                     "what is done, and this reading only says what is missing")

    read.__name__ = f"onboard_gate_{stage}"
    read.__doc__ = (f"The {stage} gate reads open: its checklist items are present and its own checks pass. A closed gate "
                    "fails the check and lists the item keys and statuses it waits on, never a value.")
    return read


for _stage in STAGES:
    check(f"onboard-gate-{_stage}")(_gate(_stage))


@check("onboard-checklist")
def onboard_checklist(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """Only what a person supplies is missing: every item not present is one no jason command can read. An item jason could
    fill and has not fails the check and is listed. Who owns each missing item (the schedule) is not read here."""
    read, why = _checklist(readers, view)
    if read is None:
        return _fail(why)
    from jason.community.onboarding import Status

    results, _ = read
    short = [r for r in results if r.status is not Status.PRESENT]
    mine = [r.item.key for r in short if not r.item.by_person]
    theirs = len(short) - len(mine)
    message = (f"{len(results) - len(short)} of {len(results)} items present; {theirs} missing or partial are a person's to "
               "supply; the schedule's owners are not read here")
    if mine:
        return _fail(f"{len(mine)} item(s) jason could fill are not present: {_keys(mine)}; {message}")
    return CheckResult(True, _evidence(readers), message)


# --- the record checklist ----------------------------------------------------------------------------------------------------

@check("record-slots-read")
def record_slots_read(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """The record checklist can be read, and how many slots are in each state. It passes when it reads at least one slot; a
    slot's state is computed from the stores and never set by a step."""
    problem = _mismatch(view)
    if problem:
        return _fail(problem)
    name, why = _active()
    if why:
        return _fail(why)
    try:
        from jason.community import private
        from jason.tasks import library, record_slots

        library.load(Path(readers.data_dir))                      # the record checklist reads a damaged library as an empty one
        pins = private.path_of("records", name)
        if pins.is_file() and not isinstance(json.loads(pins.read_text(encoding="utf-8")), dict):
            raise ValueError("the pins and answers file is not a record")
        community = readers.community
        shown = record_slots.view(community, Path(readers.data_dir), name)
    except Exception as exc:  # noqa: BLE001 - a checklist that cannot be read fails the check with the reason
        return _fail(f"the record checklist cannot be read ({type(exc).__name__}: {exc})")
    tally = shown.get("counts") or {}
    total = int(tally.get("total") or 0)
    if not total:
        return _fail("the record checklist holds no slot")
    states = ", ".join(f"{n} {k}" for k, n in sorted((tally.get("byState") or {}).items()) if n)
    message = (f"{total} slots ({int(tally.get('hidden') or 0)} hidden): {states}; "
               + ("every slot has a file or a person's answer" if shown.get("allInHand") else "some slots hold nothing yet"))
    return CheckResult(True, readers.evidence_entries(("file:library/library.db", "file:records/history.jsonl")), message)


# --- one key document ---------------------------------------------------------------------------------------------------------

@check("key-document-status")
def key_document_status(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """The entry the run is about (the subject, ``entry:KEY``) is on the key documents list, and its status. 'Missing' is only
    ever a person's word; this reads whatever the stores say. A file is counted, never named."""
    key = _handle(view, "entry", "key-document")
    if not key:
        return _fail("the run's subject names no key document entry (entry:KEY)")
    name, why = _active()
    if why:
        return _fail(why)
    try:
        from jason.tasks import key_documents

        listing = key_documents.checklist(readers.community, Path(readers.data_dir), name)
    except Exception as exc:  # noqa: BLE001 - a list that cannot be read fails the check with the reason
        return _fail(f"the key documents list cannot be read ({type(exc).__name__}: {exc})")
    rows = [e for g in listing.get("groups") or () for e in g.get("entries") or ()]
    found = next((e for e in rows if e.get("key") == key), None)
    if found is None:
        return _fail(f"entry {key} is not on the key documents list ({len(rows)} entries read)")
    pins = (found.get("slot") or {}).get("pins", 0)
    message = (f"entry {key} is {found['status']}: {len(found.get('copies') or ())} recorded copy(ies) on disk, "
               f"{len(found.get('links') or ())} link(s), {pins} pin(s) in the record checklist")
    return CheckResult(True, readers.evidence_entries((f"file:key-documents/{name}.json",)), message)


# --- the last ingest ----------------------------------------------------------------------------------------------------------

@check("ingest-gate")
def ingest_gate(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """The last ingest report was applied (files were filed, not only read in a dry run) and none of its parked questions is
    still open. Held files and found versions are information: they are reported, never failed."""
    try:
        from jason.tasks import ingest

        got = ingest.gate(Path(readers.data_dir))
    except Exception as exc:  # noqa: BLE001 - a report that cannot be read fails the check with the reason
        return _fail(f"the last ingest report cannot be read ({type(exc).__name__}: {exc})")
    if got is None:
        return _fail("nothing was ever ingested, or the last report cannot be read (jason ingest SOURCE)")
    evidence = readers.evidence_entries(("glob:onboarding/ingest-*.json", "file:intake/asks.json"))
    message = (f"the last ingest ({got['day']}, {got['mode']}): {got['files']} files, {got['new']} new, {got['filed']} filed, "
               f"{got['held']} held, {got['versions']} version(s) found, {got['questions']} question(s)")
    if got["mode"] != "applied":
        return CheckResult(False, evidence, message + "; it was a dry run, so nothing was filed")
    if got["questions"] and not got["parked"]:
        return CheckResult(False, evidence, message + "; its questions are not parked (jason ingest SOURCE --park)")
    if got["stillOpen"]:
        return CheckResult(False, evidence, message + f"; {got['stillOpen']} of its questions are still open")
    return CheckResult(True, evidence, message)


# --- a draft split ------------------------------------------------------------------------------------------------------------

@check("split-review")
def split_review(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """The draft the run is about (the subject, ``draft:ID``) can be read and has at least one part to write. Counts only; the
    flags are readings, not decisions, so they are listed and never fail the check."""
    sid = _handle(view, "draft", "split")
    if not sid:
        return _fail("the run's subject names no draft split (draft:ID)")
    try:
        from jason.tasks import split_session

        session = split_session.load(Path(readers.data_dir), sid)
    except Exception as exc:  # noqa: BLE001 - a draft that cannot be read fails the check with the reason
        return _fail(f"draft {sid} cannot be read ({type(exc).__name__}): it is not in the split store")
    if session.status in ("declined", "stale"):
        return _fail(f"draft {sid} is {session.status}, so there is nothing to review")
    parts = [s for s in session.segments() if s.level == 0]
    if not parts:
        return _fail(f"draft {sid} has no part to write")
    message = f"draft {sid} is {session.status}: {session.pages} pages, {len(parts)} part(s), version {session.version}"
    flagged = ""
    try:
        from jason.tasks import split_flags

        name, _ = _active()
        got = split_flags.flags(sid, community=readers.community, root=Path(readers.data_dir), profile=name or None)["counts"]
        flagged = "; flags: " + (", ".join(f"{n} {k}" for k, n in got.items() if n) or "none")
    except Exception:  # noqa: BLE001 - the pages' facts are not measured yet: the counts above stand
        flagged = "; the page flags could not be read (the page facts may not be measured yet)"
    return CheckResult(True, (), message + flagged)


# === round two: the reads the page's remaining check rows wanted ===========================================================

# --- where scratch and caches go --------------------------------------------------------------------------------------------

GB = 1024 ** 3


@check("scratch-room")
def scratch_room(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """The temp folder and the county cache are on a drive with room (``jason storage --check``): no drive jason writes to is
    under the free-space floor, and scratch is not on the small system drive. It says the drives and the free space in whole
    gigabytes and counts the problems; a path is never in the message (``jason storage --check`` prints them)."""
    try:
        from jason.storage import report

        rep = report(Path(readers.data_dir), sizes=False)
    except Exception as exc:  # noqa: BLE001 - a report that cannot be made fails the check with the reason
        return _fail(f"the storage report cannot be made ({type(exc).__name__}: {str(exc)[:160]})")

    def where(prefix: str) -> str:
        place = next((p for p in rep.get("places") or [] if str(p.get("name", "")).startswith(prefix)), None)
        if place is None:
            return "none set"
        free = place.get("free")
        return f"{place.get('drive') or 'an unknown drive'} with " + (f"{int(free // GB)} GB free" if free is not None else "free space unknown")

    problems = list(rep.get("problems") or [])
    said = (f"scratch is on {where('temp')}; the county cache is on {where('ASSPY_HOME')}; the data folder is on {where('data directory')} "
            f"(the floor is {rep.get('minFreeGb'):g} GB)")
    if problems:
        return _fail(said + f"; {len(problems)} problem(s): jason storage --check says which")
    return CheckResult(True, (), said + "; no drive is short of room")


# --- the profile's own facts ------------------------------------------------------------------------------------------------------

@check("profile-own-facts")
def profile_own_facts(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """Only the chosen profile's private facts are read: each topic file it has is in its own folder, none is read from the
    old shared layout that is kept for the default profile (``jason spec --migrate`` copies it). It names no file and reads no
    value: counts only."""
    if not _handle(view, "association", "profile", "community"):
        return _fail("the run's subject names no profile (association:KEY), so the facts read cannot be compared with one")
    problem = _mismatch(view)
    if problem:
        return _fail(problem)
    try:
        from jason.community import private
        from jason.tasks import spec_layout

        who = private.profile_of()
        root = private.spec_dir()
        found = spec_layout.where(who, root)
        has_own = (root / f"{who}.json").is_file()
    except Exception as exc:  # noqa: BLE001 - a folder that cannot be listed fails the check with the reason
        return _fail(f"the private facts cannot be listed ({type(exc).__name__}: {str(exc)[:160]})")
    old = [name for name, path in found if path.parent == root]
    own = len(found) - len(old)
    said = (f"{len(found)} topic file(s) for the profile: {own} in its own folder, {len(old)} in the old shared layout; "
            f"its own facts file is {'there' if has_own else 'not there yet'}")
    if old:
        return _fail(said + "; the old layout is the default profile's until jason spec --migrate copies it")
    return CheckResult(True, (), said)


# --- one key document, verified ---------------------------------------------------------------------------------------------------

@check("key-document-verified")
def key_document_verified(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """The entry the run is about (the subject, ``entry:KEY``) carries a recording number from the county index (or the
    specification), and a recorded copy on disk carries that number by its stamp or its name. An entry with no number is noted
    as not recorded (CIV 4270(a)(3) for an amendment). The number is counted, never said, and a file is never named."""
    key = _handle(view, "entry", "key-document")
    if not key:
        return _fail("the run's subject names no key document entry (entry:KEY)")
    name, why = _active()
    if why:
        return _fail(why)
    try:
        from jason.tasks import key_documents

        listing = key_documents.checklist(readers.community, Path(readers.data_dir), name)
    except Exception as exc:  # noqa: BLE001 - a list that cannot be read fails the check with the reason
        return _fail(f"the key documents list cannot be read ({type(exc).__name__}: {exc})")
    rows = [e for g in listing.get("groups") or () for e in g.get("entries") or ()]
    found = next((e for e in rows if e.get("key") == key), None)
    if found is None:
        return _fail(f"entry {key} is not on the key documents list ({len(rows)} entries read)")
    evidence = readers.evidence_entries((f"file:key-documents/{name}.json",))
    disk = [c for c in found.get("copies") or () if c.get("kind") == "disk"]
    if not found.get("number"):
        return CheckResult(False, evidence, f"entry {key} has no recording number: it is noted as not recorded, "
                                            f"and {len(disk)} recorded copy(ies) on disk carry one")
    said = (f"entry {key} has a recording number from the county index or the specification; {len(disk)} recorded copy(ies) on disk "
            f"carry it by stamp or name, {len(found.get('copies') or ()) - len(disk)} other copy(ies) are pinned")
    if not disk:
        return CheckResult(False, evidence, said + ": no recorded copy has been matched to the number yet")
    return CheckResult(True, evidence, said + " (whether it is the complete recorded copy is for a person to read)")


# --- a request's kinds ----------------------------------------------------------------------------------------------------------------

@check("request-kinds-mapped")
def request_kinds_mapped(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """Each kind of record the request asks for (the subject, ``request:ID``; or the one kind ``item`` names) maps to a
    paragraph of CIV 5200(a) and to at least one slot of the record checklist, and the slots' states are counted. A kind is
    never named: the request is a held run's, and the kinds are the member's. Whether a slot holds the record is its state."""
    handle = _handle(view, "request")
    if not handle:
        return _fail("the run's subject names no request (request:ID)")
    name, why = _active()
    if why:
        return _fail(why)
    try:
        from jason.community.records import CITATION
        from jason.community.symbols import AssociationRecord
        from jason.tasks import record_slots, records_requests

        request = records_requests.get(Path(readers.data_dir), handle)
        kinds = [k for k in request.records if not item.strip() or k == item.strip()]
        if not kinds:
            return _fail("the request asks for no kind of record" if not item.strip() else "the request does not ask for that kind")
        shown = record_slots.view(readers.community, Path(readers.data_dir), name)
    except KeyError:
        return _fail("no such request is in the request store")
    except Exception as exc:  # noqa: BLE001 - a store that cannot be read fails the check with the reason
        return _fail(f"the request cannot be mapped ({type(exc).__name__}: {str(exc)[:160]})")
    slots = [s for g in shown.get("groups") or () for s in g.get("slots") or ()]
    known = {a.value: a for a in AssociationRecord}
    unmapped, states = 0, {}
    for kind in kinds:
        record = known.get(kind)
        mine = [s for s in slots if record is not None and any(str(r).startswith(CITATION[record]) for r in s.get("requires") or ())]
        if not mine:
            unmapped += 1
        for s in mine:
            states[s["state"]] = states.get(s["state"], 0) + 1
    said = (f"{len(kinds) - unmapped} of {len(kinds)} kind(s) asked map to a paragraph of CIV 5200(a) and a slot of the record "
            "checklist; the slots' states: " + (", ".join(f"{n} {k}" for k, n in sorted(states.items())) or "none"))
    if unmapped:
        return _fail(said + f"; {unmapped} kind(s) have no slot: a miss stays a miss, and a person says where the record is held")
    return CheckResult(True, readers.evidence_entries(("file:records-requests/requests.json",)), said)


# --- a pick, compared with its slot ------------------------------------------------------------------------------------------------------

@check("record-compare")
def record_compare(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """The slot the step names (the item) holds a pinned file whose reading was kept, and each reading says whether the file's
    kind agrees with the slot's, differs (a wrong-slot pick), or is unclassified. It passes when every pin has a reading, whatever
    the verdicts: a difference is what the next step resolves, and it sets the slot to a problem on its own. Counts only."""
    slot = item.strip()
    if not slot:
        return _fail("the step is read one slot at a time: the item names the slot")
    problem = _mismatch(view)
    if problem:
        return _fail(problem)
    name, why = _active()
    if why:
        return _fail(why)
    try:
        from jason.tasks import record_readback, record_slots

        shown = record_slots.slot_view(slot, readers.community, Path(readers.data_dir), name, private=False, history=False)
        if not shown.get("found"):
            return _fail(f"{slot} is not a slot of the record checklist")
        pins = [h["pin"] for h in shown.get("holders") or () if h.get("kind") != "folder"]
        verdicts = {"agrees": 0, "differs": 0, "unclassified": 0}
        unread = 0
        for pin in pins:
            kept = record_readback.load(Path(readers.data_dir), name, pin)
            said = str(((kept or {}).get("compare") or {}).get("verdict") or "")
            if said in verdicts:
                verdicts[said] += 1
            else:
                unread += 1
    except Exception as exc:  # noqa: BLE001 - a store that cannot be read fails the check with the reason
        return _fail(f"the slot cannot be compared ({type(exc).__name__}: {str(exc)[:160]})")
    if not pins:
        return _fail(f"no file is pinned to {slot}, so there is nothing to compare")
    said = (f"{len(pins)} pinned file(s) in {slot}: {verdicts['agrees']} agree with the slot, {verdicts['differs']} differ, "
            f"{verdicts['unclassified']} are unclassified, {unread} not read yet")
    if unread:
        return _fail(said + "; jason records --read KEY reads them")
    return CheckResult(True, (), said + ("; a difference sets the slot to problem and is resolved in the next step" if verdicts["differs"] else ""))
