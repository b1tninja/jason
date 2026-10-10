"""The record checklist for the active profile, read from disk, and the writes a person makes to it (docs/record-intake.md).

``assemble`` builds the slot list from jason's own catalog, never typed here: the Civil Code 5200 records, the developer
deliveries, the key documents, the onboarding items that are documents, and a few document kinds with no shelf of their
own; then the profile's additions and hidden slots (``Community.record_slots()``). ``view`` and ``slot_view`` compute each
slot's state from the records on disk: a person's pins and answers (``data/spec/<profile>/records.json`` through
``jason.community.private``), the key documents' store (a pick on a recorded instrument is its link: one writer), the
specification's own pins, and what the classified library shows of each pinned file. Nothing here calls Drive, PayHOA,
Google, or the county.

The writes are a person's: ``pick`` (a Drive link or id, or a library id, to a slot), ``answer`` (not applicable, none
exists, or waiting, each with the person's words), and ``unpin``. Each names its person (``by``), is a dry run unless
told otherwise, holds the store's lock, replaces ``records.json`` whole after a backup, and appends to
``data/records/history.jsonl``; nothing is deleted, and the file picked is never touched. jason never writes in its own
name. Resolving a pasted link in Drive (read-only) is optional and goes through a client the caller opens.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

from jason.community.key_documents import KEY_DOCUMENTS, KeyDocumentStore, item_of, key_document, why_of
from jason.community.record_slots import (
    STATE_MEANING,
    Answer,
    AnswerKind,
    Cardinality,
    Origin,
    Pin,
    PinKind,
    PinStatus,
    Reading,
    Slot,
    SlotRule,
    SlotSource,
    SlotState,
    apply_rules,
    citations_in,
    counts,
    latest_answer,
    merge_holders,
    parse_drive_ref,
    pin_status,
    slot_state,
)
from jason.community.records import CITATION
from jason.community.symbols import AssociationRecord, DeveloperDelivery, DocumentCategory, DocumentKind

CAVEATS = (
    "A slot's state is jason's reading of records. A person's answer is theirs. Missing is not none: the association may "
    "hold it outside jason.",
    "A pick names a file and copies nothing; a reading by jason is a suggestion until a person confirms it, and is never "
    "verified against the law.",
    "A confidential file is held back: its name is masked outside the private view.",
)

STORE = "records.json"
HISTORY = ("records", "history.jsonl")
PERIOD_FORMS = "a year (2099), a month (2099-06), or a quarter (2099-Q2)"

# Where each Civil Code 5200 record sits among the onboarding groups (the group values of jason.community.onboarding), so the
# two checklists never disagree about a section. The governing documents record is carried by the key documents' slots.
RECORD_GROUPS: dict[AssociationRecord, str] = {
    AssociationRecord.FINANCIAL_DISCLOSURE: "finance",
    AssociationRecord.TRANSFER_FINANCIAL: "members",
    AssociationRecord.INTERIM_FINANCIAL: "finance",
    AssociationRecord.EXECUTED_CONTRACT: "vendors",
    AssociationRecord.VENDOR_APPROVAL: "vendors",
    AssociationRecord.TAX_RETURN: "corporate",
    AssociationRecord.RESERVE_ACCOUNT: "finance",
    AssociationRecord.MINUTES: "meetings",
    AssociationRecord.MEMBERSHIP_LIST: "members",
    AssociationRecord.CHECK_REGISTER: "finance",
    AssociationRecord.RESERVE_LITIGATION_ACCOUNTING: "finance",
    AssociationRecord.ENHANCED: "finance",
    AssociationRecord.ELECTION_MATERIALS: "elections",
    AssociationRecord.ELEVATED_ELEMENT_REPORT: "maintenance",
}
RECORD_SERIES = frozenset({
    AssociationRecord.FINANCIAL_DISCLOSURE, AssociationRecord.INTERIM_FINANCIAL, AssociationRecord.TAX_RETURN,
    AssociationRecord.RESERVE_ACCOUNT, AssociationRecord.MINUTES, AssociationRecord.CHECK_REGISTER,
    AssociationRecord.ELECTION_MATERIALS, AssociationRecord.ELEVATED_ELEMENT_REPORT,
})
RECORD_SEVERAL = frozenset({AssociationRecord.EXECUTED_CONTRACT, AssociationRecord.VENDOR_APPROVAL, AssociationRecord.ENHANCED})
RECORD_TITLES: dict[AssociationRecord, str] = {
    AssociationRecord.FINANCIAL_DISCLOSURE: "The annual budget report and policy statement, with what backs them",
    AssociationRecord.TRANSFER_FINANCIAL: "The financial documents given to a buyer on a sale",
    AssociationRecord.INTERIM_FINANCIAL: "Interim financial statements and budget comparisons",
    AssociationRecord.EXECUTED_CONTRACT: "Executed contracts, including insurance policies and leases",
    AssociationRecord.VENDOR_APPROVAL: "The board's written approvals of vendors and contractors",
    AssociationRecord.TAX_RETURN: "State and federal tax returns",
    AssociationRecord.RESERVE_ACCOUNT: "Reserve account balances and the record of payments from them",
    AssociationRecord.MINUTES: "Minutes of member, board, and committee meetings",
    AssociationRecord.MEMBERSHIP_LIST: "The membership list",
    AssociationRecord.CHECK_REGISTER: "The check register",
    AssociationRecord.RESERVE_LITIGATION_ACCOUNTING: "The accounting for reserves used for litigation",
    AssociationRecord.ENHANCED: "Invoices, receipts, canceled checks, and statements",
    AssociationRecord.ELECTION_MATERIALS: "Election materials: ballots, envelopes, sign-in sheets, and the tally",
    AssociationRecord.ELEVATED_ELEMENT_REPORT: "The elevated-element inspection report",
}
DELIVERY_TITLES: dict[DeveloperDelivery, str] = {
    DeveloperDelivery.BOND: "Each bond or other security the developer gave the association",
    DeveloperDelivery.WARRANTY: "Warranties the developer delivered",
    DeveloperDelivery.INSURANCE: "Insurance the developer delivered",
    DeveloperDelivery.CONTRACT: "Contracts the developer delivered",
    DeveloperDelivery.MEMBERSHIP_REGISTER: "The membership register the developer delivered",
    DeveloperDelivery.BOOKS: "The books the developer delivered",
    DeveloperDelivery.MINUTES: "The minutes the developer delivered",
}
DELIVERY_SEVERAL = frozenset({DeveloperDelivery.BOND, DeveloperDelivery.WARRANTY, DeveloperDelivery.INSURANCE,
                              DeveloperDelivery.CONTRACT, DeveloperDelivery.MINUTES})
DELIVERY_CITATIONS = {DeveloperDelivery.PUBLIC_REPORT: ("BPC 11018.5",)}
DELIVERY_RULE = "10 CCR 2792.23"
# Kinds with no shelf of their own among the above: a series or a set for each (the budget and the reserve study are a
# series, the policies and contracts a set that grows).
KIND_SLOTS: tuple[tuple[tuple[DocumentKind, ...], Cardinality, str, str], ...] = (
    ((DocumentKind.INSURANCE_POLICY, DocumentKind.EVIDENCE_OF_INSURANCE), Cardinality.SEVERAL, "Insurance policies and certificates", "insurance"),
    ((DocumentKind.CONTRACT,), Cardinality.SEVERAL, "Contracts with vendors", "vendors"),
    ((DocumentKind.RESERVE_STUDY,), Cardinality.SERIES, "Reserve studies", "finance"),
    ((DocumentKind.BUDGET,), Cardinality.SERIES, "Budgets", "finance"),
    ((DocumentKind.FINANCIAL_STATEMENT,), Cardinality.SERIES, "Financial statements", "finance"),
)
# The slots whose record the key documents' instruments are read after: an amendment waits on the declaration it amends.
AFTER_DECLARATION = ("amendments", "annexations")
GATE_ORDER = ("start", "ingest", "establish", "operate", "adopt")


@dataclass(frozen=True)
class Assembly:
    slots: tuple[Slot, ...]
    hidden: dict[str, str] = field(default_factory=dict)
    notes: tuple[str, ...] = ()


def _confidential(kinds: tuple[DocumentKind, ...]) -> bool:
    from jason.community.library import CONFIDENTIAL_KINDS

    return bool(kinds) and all(k in CONFIDENTIAL_KINDS for k in kinds)


def _kinds_for(**by: Any) -> tuple[DocumentKind, ...]:
    from jason.community.documents import PROFILE

    record, delivery = by.get("record"), by.get("delivery")
    return tuple(k for k, p in PROFILE.items() if (record is not None and p.record is record) or (delivery is not None and p.delivery is delivery))


def _gate(*item_keys: str) -> str:
    from jason.community.onboarding import stages_of

    stages = sorted({s.value for key in item_keys for s in stages_of(key)}, key=lambda v: GATE_ORDER.index(v))
    return stages[0] if stages else ""


def _record_gate(kind: AssociationRecord) -> str:
    from jason.community.onboarding import ITEMS, Record

    return _gate(*(i.key for i in ITEMS if any(isinstance(c, Record) and c.kind is kind for c in i.checks)))


def assemble(community: Any = None) -> Assembly:
    """The slot list from jason's catalog, with the profile's additions and hidden slots applied."""
    from jason.community.documents import PROFILE
    from jason.community.onboarding import ITEMS, Group, Kinds, item

    notes: list[str] = []
    slots: list[Slot] = []
    # 1. Civil Code 5200: one for each record kind. The governing documents are the key documents' slots.
    for kind in AssociationRecord:
        if kind is AssociationRecord.GOVERNING_DOCUMENTS:
            continue
        kinds = _kinds_for(record=kind)
        slots.append(Slot(
            f"records/5200/{kind.value}", RECORD_TITLES[kind], RECORD_GROUPS[kind], (CITATION[kind],),
            Cardinality.SERIES if kind in RECORD_SERIES else Cardinality.SEVERAL if kind in RECORD_SEVERAL else Cardinality.ONE,
            kinds, _confidential(kinds), source=SlotSource.RECORD_5200, gate=_record_gate(kind), record=kind.value))
    # 2. The key documents: the instruments, each row a slot, a recorded one read after the declaration.
    for row in KEY_DOCUMENTS:
        found = item(row.key)
        group = found.group.value if found is not None else Group.RECORDED.value
        profile = PROFILE[row.kinds[0]] if row.kinds else None
        slots.append(Slot(
            f"{group}/{row.key}", row.title, group, citations_in(why_of(row)),
            Cardinality.SEVERAL if row.repeats else Cardinality.ONE, row.kinds, _confidential(row.kinds),
            source=SlotSource.KEY_DOCUMENT, why=why_of(row),
            waits_on=(f"{Group.GOVERNING.value}/declaration",) if row.key in AFTER_DECLARATION else (),
            gate=_gate(row.key), key_document=row.key,
            record=profile.record.value if profile is not None and profile.record is not None else "",
            delivery=row.delivery.value if row.delivery is not None else ""))
    # 3. The developer's deliveries no key document carries (10 CCR 2792.23).
    carried = {row.delivery for row in KEY_DOCUMENTS if row.delivery is not None}
    for delivery in DeveloperDelivery:
        if delivery in carried or delivery not in DELIVERY_TITLES:
            continue
        kinds = _kinds_for(delivery=delivery)
        slots.append(Slot(
            f"delivery/{delivery.value}", DELIVERY_TITLES[delivery], "recorded", (DELIVERY_RULE, *DELIVERY_CITATIONS.get(delivery, ())),
            Cardinality.SEVERAL if delivery in DELIVERY_SEVERAL else Cardinality.ONE, kinds, _confidential(kinds),
            source=SlotSource.DELIVERY, delivery=delivery.value, gate=_gate("developer-file")))
    # 4. Kinds with no shelf of their own (before the onboarding items, so an item they cover is not a second slot).
    for kinds, cardinality, title, group in KIND_SLOTS:
        slots.append(Slot(f"kind/{kinds[0].value}", title, group, (), cardinality, kinds, _confidential(kinds),
                          source=SlotSource.KIND, why="jason reads these as a kind (the document kinds' shelf)"))
    # 5. The onboarding items that are documents and are not already a slot above.
    have = {k for s in slots for k in s.kinds}
    row_keys = {row.key for row in KEY_DOCUMENTS}
    for it in ITEMS:
        kinds = tuple(dict.fromkeys(k for c in it.checks if isinstance(c, Kinds) for k in c.kinds))
        if not kinds or it.key in row_keys or set(kinds) <= have:
            continue
        slots.append(Slot(
            f"{it.group.value}/{it.key}", it.title, it.group.value, citations_in(it.why), Cardinality.SEVERAL, kinds,
            _confidential(kinds), source=SlotSource.ONBOARDING, why=it.why, gate=_gate(it.key)))
    # The programs the documents mandate are slots when the adoption catalog exists (docs/programs.md): not built yet.
    try:
        import importlib

        importlib.import_module("jason.community.program_catalog")
        notes.append("the program catalog exists but its slots are not yet read here")
    except ImportError:
        notes.append("no program slots yet: the program catalog (docs/programs.md) is not built")
    rules: tuple[SlotRule, ...] = ()
    if community is not None:
        try:
            rules = tuple(community.record_slots() or ())
        except Exception as exc:  # noqa: BLE001 - a profile that cannot answer adds and hides nothing
            notes.append(f"the profile's slot rules could not be read ({type(exc).__name__})")
    found, hidden = apply_rules(slots, rules)
    return Assembly(found, hidden, tuple(notes))


# The records on disk ------------------------------------------------------------------------------------------------------

def _root(root: Path | None) -> Path:
    if root is not None:
        return Path(root)
    from jason.mcp.county import _data_dir

    return _data_dir(None)


def _profile(profile: str | None, community: Any = None) -> str:
    if profile:
        return profile
    from jason.community.profile import profile_name

    return profile_name()


def store_path(profile: str, *, spec: Path | None = None) -> Path:
    """``<spec>/<profile>/records.json``: where this profile's pins and answers are kept (a private fact, never checked in)."""
    from jason.community import private

    return Path(spec if spec is not None else private.spec_dir()) / profile / STORE


def load_store(profile: str) -> dict[str, Any]:
    """The profile's records file read through the private facts' own path rules; absent is empty, never an error."""
    from jason.community import private

    path = private.path_of("records", profile)
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    except (OSError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    return {"version": 1, "profile": profile, "pins": list(data.get("pins") or []), "answers": list(data.get("answers") or [])}


def _pin_of(row: dict[str, Any]) -> Pin | None:
    try:
        unpinned = row.get("unpinned") or {}
        return Pin(str(row["id"]), str(row["slot"]), PinKind(row["kind"]), str(row["ref"]), str(row.get("name") or ""),
                   str(row.get("period") or ""), str(row.get("by") or ""), str(row.get("at") or ""), str(row.get("note") or ""),
                   Origin.DATA, STORE, str(unpinned.get("by") or ""), str(unpinned.get("at") or ""))
    except (KeyError, ValueError, AttributeError):
        return None


def _answer_of(row: dict[str, Any]) -> Answer | None:
    try:
        return Answer(str(row["id"]), str(row["slot"]), AnswerKind(row["answer"]), str(row.get("reason") or ""),
                      str(row.get("by") or ""), str(row.get("at") or ""), str(row.get("who") or ""))
    except (KeyError, ValueError):
        return None


def _key_document_records(root: Path, profile: str, slot: Slot) -> tuple[list[Pin], list[Answer]]:
    """The key documents' store as this slot's pins and answer: each active link is a pin, a person's "missing" is a
    "none exists" answer. One writer: the store the key-documents screen and command write."""
    if not slot.key_document:
        return [], []
    pins: list[Pin] = []
    answers: list[Answer] = []
    entries = KeyDocumentStore(root, profile).load()["entries"]
    for key, held in entries.items():
        if item_of(key) != slot.key_document:
            continue
        for link in held.get("links", []):
            kind = {"drive": PinKind.DRIVE, "payhoa": PinKind.LIBRARY}.get(link.get("kind"), PinKind.FILE)
            gone = link.get("unlinked") or {}
            pins.append(Pin("k-" + str(link.get("id")), slot.key, kind, str(link.get("ref") or ""), str(link.get("name") or ""),
                            "", str(link.get("by") or ""), str(link.get("at") or ""), str(link.get("note") or ""), Origin.DATA,
                            "key-documents", str(gone.get("by") or ""), str(gone.get("at") or ""), store_id=key))
        said = held.get("status") if isinstance(held.get("status"), dict) else {}
        if said.get("value") == "missing":
            answers.append(Answer("ks-" + key, slot.key, AnswerKind.NONE, str(said.get("note") or ""), str(said.get("by") or ""),
                                  str(said.get("at") or ""), source="key-documents"))
    return pins, answers


def _code_id(slot: str, kind: str, ref: str) -> str:
    return "c-" + hashlib.sha1(f"{slot}|{kind}|{ref}".encode()).hexdigest()[:8]


def code_pins(community: Any, slots: tuple[Slot, ...]) -> dict[str, list[Pin]]:
    """What the specification itself pins for each slot: the Drive files of its governing document and pins by kind and
    developer delivery, its known files and library folders and sync rules for a 5200 record. Read through the
    ``Community`` interface; a profile that cannot answer one method gives none of it."""
    out: dict[str, list[Pin]] = {s.key: [] for s in slots}
    if community is None:
        return out

    def add(slot: Slot, kind: PinKind, ref: str, name: str, source: str) -> None:
        if ref and not any(p.kind == kind and p.ref == ref for p in out[slot.key]):
            out[slot.key].append(Pin(_code_id(slot.key, kind.value, ref), slot.key, kind, ref, name, origin=Origin.CODE, source=source))

    def call(name: str) -> Any:
        try:
            value = getattr(community, name)
            return value() if callable(value) else value
        except Exception:  # noqa: BLE001 - a profile with nothing to say gives nothing
            return None

    declaration = call("ccrs")
    if declaration is not None:
        for slot in slots:
            if slot.key_document == "declaration":
                add(slot, PinKind.DRIVE, getattr(declaration, "drive_id", ""), getattr(declaration, "title", ""), "specification: governing document")
            if slot.key_document == "amendments":
                for amendment in getattr(declaration, "amendments", ()) or ():
                    add(slot, PinKind.DRIVE, getattr(amendment, "drive_id", ""), getattr(amendment, "title", ""), "specification: amendment")
    for pin in call("pins") or ():
        for slot in slots:
            if pin.kind in slot.kinds:
                add(slot, PinKind.DRIVE, pin.drive_id, pin.title, "specification: pinned document")
    for delivery, pinned in (call("developer_file") or {}).items():
        for slot in slots:
            if slot.source is SlotSource.DELIVERY and slot.delivery == getattr(delivery, "value", delivery):
                for pin in pinned:
                    add(slot, PinKind.DRIVE, pin.drive_id, pin.title, "specification: developer delivery")
    by_record = {s.record: s for s in slots if s.source is SlotSource.RECORD_5200}
    for anchor in call("known_files") or ():
        for record in getattr(anchor, "records", ()) or ():
            if record.value in by_record:
                add(by_record[record.value], PinKind.DRIVE, getattr(anchor, "drive_id", ""), getattr(anchor, "name", ""), "specification: known file")
    for folder in call("library_folders") or ():
        for record in getattr(folder, "records", ()) or ():
            if record.value in by_record:
                add(by_record[record.value], PinKind.FOLDER, folder.path, folder.path, "specification: library folder")
    for rule in call("sync_rules") or ():
        for record in getattr(rule, "records", ()) or ():
            if record.value in by_record:
                add(by_record[record.value], PinKind.FOLDER, rule.drive_folder, rule.drive_folder, "specification: Drive sync rule")
    return out


class Library:
    """The classified library on disk (``library/library.db``) and the Drive catalog (``drive/files.json``), indexed so a
    pinned file is found by its library id, its Drive id, or its upload's hash. Disk only; absent is empty."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        rows: tuple[dict[str, Any], ...] = ()
        try:
            from jason.tasks.library import load

            rows = load(self.root)
        except Exception:  # noqa: BLE001 - no library yet: every pin is only picked
            rows = ()
        self.rows = rows
        self.by_id = {str(r["id"]): r for r in rows}
        self.by_name: dict[str, list[dict[str, Any]]] = {}
        for r in rows:
            self.by_name.setdefault(str(r.get("name") or "").casefold(), []).append(r)
        self.drive: dict[str, dict[str, Any]] = {}
        self.drive_synced = ""
        try:
            raw = json.loads((self.root / "drive" / "files.json").read_text(encoding="utf-8"))
            self.drive = {str(f.get("id")): f for f in raw.get("files", []) if isinstance(f, dict)}
            self.drive_synced = str(raw.get("syncedAt") or "")
        except (OSError, ValueError):
            pass

    def _row_for(self, pin: Pin) -> tuple[dict[str, Any] | None, str]:
        """The library row for a pin and the name known for it."""
        if pin.kind is PinKind.LIBRARY:
            row = self.by_id.get(pin.ref)
            return row, str((row or {}).get("name") or pin.name)
        if pin.kind is PinKind.DRIVE:
            known = self.drive.get(pin.ref)
            name = str((known or {}).get("name") or pin.name)
            matches = self.by_name.get(name.casefold(), []) if name else []
            kinds = {m.get("kind") for m in matches}
            return (matches[0] if matches and len(kinds) == 1 else None), name
        if pin.kind is PinKind.FILE:
            name = pin.name or Path(pin.ref).name
            parts = Path(pin.ref).parts
            digest = parts[-2] if "files" in parts and len(parts) >= 2 else ""
            if digest:
                for r in self.rows:
                    if str(r.get("sha256") or "").startswith(digest):
                        return r, name
            matches = self.by_name.get(name.casefold(), [])
            return (matches[0] if len(matches) == 1 else None), name
        return None, pin.name

    def reading(self, pin: Pin) -> Reading:
        row, name = self._row_for(pin)
        if row is None:
            return Reading(found=False, name=name)
        from jason.tasks.library import text_path

        try:
            read = text_path(self.root, str(row["id"])) is not None
        except OSError:
            read = False
        person = str(row.get("method") or "") == "PERSON"
        evidence = str(row.get("evidence") or "")
        by, _, day = evidence.removeprefix("chosen by ").partition(" on ") if person and evidence.startswith("chosen by ") else ("", "", "")
        return Reading(True, name or str(row.get("name") or ""), str(row.get("kind") or "") or None, bool(row.get("confidential")), read,
                       (by.split(":")[0].strip() or "a person") if person else "", day.split(":")[0].strip() if person else "",
                       str(row["id"]), str(row.get("method") or ""))


# The checklist -------------------------------------------------------------------------------------------------------------

def _mask_name(reading: Reading, pin: Pin, private: bool) -> str:
    if reading.confidential and not private:
        return f"a confidential file (kind: {(reading.kind or 'unclassified').replace('_', ' ')})"
    return reading.name or pin.name


def _ref_shown(pin: Pin, reading: Reading, private: bool) -> str:
    """A file's id is not shown whole outside the private view (it is P2; docs/console/security-and-privacy.md)."""
    if pin.kind is PinKind.FOLDER or private:
        return pin.ref
    return (pin.ref[:6] + "…") if len(pin.ref) > 8 else pin.ref


@dataclass
class Computed:
    slot: Slot
    hidden: str
    holders: list[Pin]
    statuses: list[PinStatus]
    collisions: list[dict[str, Any]]
    answer: Answer | None
    answers: list[Answer]
    state: SlotState
    holding: str
    candidates: list[dict[str, Any]]
    folders: list[Pin]

    @property
    def held(self) -> int:
        return sum(1 for s in self.statuses if s.held)


def compute(community: Any = None, root: Path | None = None, profile: str | None = None) -> list[Computed]:
    """Every slot with its holders, collisions, answer, and state, from what is on disk. Disk only."""
    root = _root(root)
    profile = _profile(profile, community)
    assembly = assemble(community)
    slots = assembly.slots
    library = Library(root)
    stored = load_store(profile)
    data_pins = [p for p in (_pin_of(r) for r in stored["pins"]) if p]
    data_answers = [a for a in (_answer_of(r) for r in stored["answers"]) if a]
    code = code_pins(community, slots)
    holdings = _holdings(community, root, library)
    pinned_library = {p.ref for p in data_pins if p.kind is PinKind.LIBRARY and p.active}
    by_kind: dict[str, list[dict[str, Any]]] = {}
    for r in library.rows:
        by_kind.setdefault(str(r.get("kind") or ""), []).append(r)
    out: list[Computed] = []
    for slot in slots:
        kd_pins, kd_answers = _key_document_records(root, profile, slot)
        mine = [p for p in data_pins if p.slot == slot.key] + kd_pins
        holders, collisions = merge_holders(slot, code.get(slot.key, []), mine)
        files = [h for h in holders if h.kind is not PinKind.FOLDER]
        folders = [h for h in holders if h.kind is PinKind.FOLDER]
        statuses = [pin_status(slot, h, library.reading(h)) for h in files]
        answers = [a for a in data_answers if a.slot == slot.key] + kd_answers
        answer = latest_answer(answers)
        holding, why = None, ""
        if not files:
            # The specification's own holder (a folder it pins) is a holder; files the library classified that nobody
            # pinned are candidates, not a holder: nobody has spoken for the slot.
            held_record = holdings.get(slot.record) if slot.record and slot.source is SlotSource.RECORD_5200 else None
            if folders and held_record is not None and (held_record.classified or held_record.documents):
                holding, why = SlotState.CLASSIFIED, f"a folder the specification pins; {held_record.documents or held_record.classified} files in it"
            elif folders:
                holding, why = SlotState.PICKED, "a folder the specification pins; the catalog holds no file there"
        candidates = [
            {"ref": f"library:{r['id']}", "name": r.get("name", ""), "kind": r.get("kind", ""), "confidential": bool(r.get("confidential"))}
            for k in slot.kinds for r in by_kind.get(k.value, []) if str(r["id"]) not in pinned_library
        ]
        out.append(Computed(slot, assembly.hidden.get(slot.key, ""), holders, statuses, collisions, answer, answers,
                            slot_state(slot, statuses, answer, holding=holding), why, candidates, folders))
    return out


def _holdings(community: Any, root: Path, library: Library) -> dict[str, Any]:
    """The Civil Code 5200 inventory's holdings by record value (specification pins and classified files), or none."""
    if community is None:
        return {}
    try:
        from jason.community.records_inventory import inventory
        from jason.tasks.association_pages import catalog_paths
        from jason.tasks.library import distinct

        paths = catalog_paths(root, community.org_id)
        return {h.kind.value: h for h in inventory(community, paths, library=tuple(distinct(library.rows)))}
    except Exception:  # noqa: BLE001 - the inventory needs the catalog; without it the slots read from pins and answers alone
        return {}


def _row(c: Computed, *, private: bool) -> dict[str, Any]:
    s = c.slot
    periods = []
    if s.cardinality is Cardinality.SERIES:
        seen: dict[str, SlotState] = {}
        for st in c.statuses:
            seen[st.pin.period or "unplaced"] = min((seen.get(st.pin.period or "unplaced", st.state), st.state), key=lambda x: x.value)
        periods = [{"period": p, "state": v.value} for p, v in sorted(seen.items(), reverse=True)]
    return {
        "key": s.key, "title": s.title, "group": s.group, "requires": list(s.requires), "cardinality": s.cardinality.value,
        "state": c.state.value, "stateWord": c.state.word, "held": c.held, "cells": len(periods), "periods": periods,
        "confidential": s.confidential, "hidden": c.hidden, "source": s.source.value, "gate": s.gate,
        "kinds": [k.value for k in s.kinds], "pins": len(c.holders), "candidates": len(c.candidates), "collision": bool(c.collisions),
        "problem": next((p.problem for p in c.statuses if p.problem), ""), "waitsOn": list(s.waits_on),
        "route": "#/onboarding/records/" + quote(s.key, safe=""),
    }


def view(community: Any = None, root: Path | None = None, profile: str | None = None, *, group: str = "", state: str = "",
         private: bool = False) -> dict[str, Any]:
    """The checklist: groups of slots with their states, the counts, and the biggest unknowns. ``group`` and ``state`` narrow
    the listing (the counts stay whole). No file name is in it, so nothing here needs masking; ``slot_view`` names files."""
    from jason.community.onboarding import GROUP_TITLES, Group
    from jason.community.record_slots import STATE_WORDS

    root = _root(root)
    profile = _profile(profile, community)
    computed = compute(community, root, profile)
    rows = [_row(c, private=private) for c in computed]
    wanted = [r for r in rows if (not group or r["group"] == group) and (not state or r["state"] == state)]
    by_group: dict[str, list[dict[str, Any]]] = {}
    for r in wanted:
        by_group.setdefault(r["group"], []).append(r)
    order = [g.value for g in Group]
    groups = []
    for key in sorted(by_group, key=lambda k: order.index(k) if k in order else len(order)):
        mine = [r for r in rows if r["group"] == key]
        laws = sorted({c for r in by_group[key] for c in r["requires"]})
        groups.append({
            "key": key, "title": GROUP_TITLES[Group(key)] if key in order else key, "law": ", ".join(laws[:3]),
            "opensGate": next((r["gate"] for r in by_group[key] if r["gate"]), ""),
            "counts": {"total": len(mine), "held": sum(r["held"] for r in mine),
                       "answered": sum(1 for r in mine if r["state"] in ("notApplicable", "doesNotExist", "waiting"))},
            "slots": by_group[key],
        })
    five = [r for r in rows if r["key"].startswith("records/5200/")]
    drive = _drive_catalog(root)
    unknowns = sorted((r for r in rows if r["state"] == "empty" and not r["hidden"]),
                      key=lambda r: (GATE_ORDER.index(r["gate"]) if r["gate"] else len(GATE_ORDER), 0 if r["requires"] else 1, r["key"]))
    waits = {r["key"]: [x["key"] for x in rows if r["key"] in x["waitsOn"]] for r in rows}
    return {
        "found": True, "asOf": datetime.now(timezone.utc).date().isoformat(), "profile": profile,
        "driveConnected": None, "driveCatalog": drive,
        "counts": counts(rows), "law": {"civil code 5200": {"slots": len(five), "answered_or_held": sum(1 for r in five if r["state"] != "empty")}},
        "states": [{"value": s.value, "word": STATE_WORDS[s], "meaning": STATE_MEANING[s]} for s in SlotState],
        "groups": groups,
        "biggestUnknowns": [{"key": r["key"], "title": r["title"],
                             "why": (f"the {r['gate']} gate waits on it" if r["gate"] else "a statute names it: " + ", ".join(r["requires"][:2])),
                             "blocks": waits.get(r["key"], [])} for r in unknowns[:10]],
        "notes": list(assemble(community).notes), "caveats": list(CAVEATS),
    }


def _drive_catalog(root: Path) -> dict[str, Any]:
    lib = Library(root)
    return {"syncedAt": lib.drive_synced, "files": len(lib.drive)}


def _holder_dict(st: PinStatus, slot: Slot, others: dict[str, list[tuple[str, str]]], *, private: bool) -> dict[str, Any]:
    pin, reading = st.pin, st.reading
    shown = _mask_name(reading, pin, private) if reading.found or reading.confidential else (pin.name or "a file not in the library")
    if reading.confidential and not private:
        shown = _mask_name(reading, pin, private)
    return {
        "pin": pin.id, "origin": pin.origin.value, "source": pin.source, "kind": pin.kind.value,
        "name": shown, "ref": _ref_shown(pin, reading, private), "period": pin.period, "by": pin.by, "at": pin.at[:10],
        "note": "" if (reading.confidential and not private) else pin.note,
        "state": st.state.value, "stateWord": st.state.word, "held": st.held,
        "opens": "opens in the private view" if st.held and not private else "",
        "reading": {"found": reading.found, "readsAs": (st.reads_as or None), "readers": ([reading.method] if reading.method else []),
                    "tier": ("confirmed by a person" if reading.confirmed_by else "suggested" if reading.found and reading.kind else None),
                    "read": reading.read, "confirmedBy": reading.confirmed_by, "confirmedAt": reading.confirmed_at},
        "problem": st.problem,
        "wrongSlot": ({"readsAs": st.reads_as, "expects": [k.value for k in slot.kinds],
                       "fits": [{"key": k, "title": t} for k, t in others.get(st.reads_as, [])],
                       "acts": ["pin it to a slot it fits", "unpin"]} if st.wrong_slot else None),
    }


def slot_view(key: str, community: Any = None, root: Path | None = None, profile: str | None = None, *, private: bool = False,
              history: bool = True) -> dict[str, Any]:
    """One slot: what requires it, what is held, the candidates, collisions, the person's answer, what may be done, and
    the trail. ``private`` names a confidential file; without it the name and note are masked and the id is shortened."""
    root = _root(root)
    profile = _profile(profile, community)
    computed = compute(community, root, profile)
    found = next((c for c in computed if c.slot.key == key), None)
    if found is None:
        return {"found": False, "key": key, "reason": "no such slot", "caveats": list(CAVEATS)}
    s = found.slot
    fits: dict[str, list[tuple[str, str]]] = {}
    for c in computed:
        for k in c.slot.kinds:
            fits.setdefault(k.value, []).append((c.slot.key, c.slot.title))
    ans = found.answer
    mask_words = s.confidential and not private
    answer = None if ans is None else {
        "id": ans.id, "answer": ans.kind.value, "word": ans.kind.state.word, "by": ans.by, "at": ans.at[:10],
        "reason": "" if mask_words else ans.reason, "who": "" if mask_words else ans.who, "source": ans.source,
        "held": mask_words}
    log = [r for r in read_history(root) if r.get("slot") == key][-12:] if history else []
    row = _row(found, private=private)
    return {
        **row,
        "found": True, "why": s.why, "existence": {"possible": s.existence, "answer": answer},
        "shelf": sorted({_category(k) for k in s.kinds}), "record": s.record, "delivery": s.delivery,
        "holders": [_holder_dict(st, s, fits, private=private) for st in found.statuses],
        "specificationFolders": [{"pin": f.id, "folder": f.name, "source": f.source} for f in found.folders],
        "holding": found.holding, "collisions": found.collisions,
        "candidates": [{"ref": c["ref"], "name": ("a confidential file" if c["confidential"] and not private else c["name"]),
                        "kind": c["kind"], "why": f"classified as {c['kind'].replace('_', ' ')}; not pinned"} for c in found.candidates[:8]],
        "acts": {"pickFile": not found.hidden, "answer": s.existence and not found.hidden, "unpin": bool(found.holders), "pickFolder": False,
                 "upload": False, "replace": False,
                 "why": ("hidden by the profile: " + found.hidden) if found.hidden else
                        "choosing a folder, uploading, and replacing come with the chooser (phase 2 and 3)"},
        "log": [{k: v for k, v in r.items() if k not in ("detail",)} if not mask_words else {"at": r.get("at"), "by": r.get("by"), "act": r.get("act")}
                for r in log],
        "commands": {"slot": f"jason records --slot {key}", "pick": f"jason records --pick {key} --file LINK_OR_ID --by NAME",
                     "answer": f"jason records --answer {key} --not-applicable|--none|--waiting --reason TEXT --by NAME"},
        "caveats": list(CAVEATS),
    }


def _category(kind: DocumentKind) -> str:
    from jason.community.documents import PROFILE

    return PROFILE[kind].category.value


def pins_listing(community: Any = None, root: Path | None = None, profile: str | None = None) -> dict[str, Any]:
    """The specification's own pins, by slot (``jason records --pins``)."""
    assembly = assemble(community)
    pinned = code_pins(community, assembly.slots)
    return {"found": True, "pins": [{"slot": k, "pins": [{"kind": p.kind.value, "name": p.name, "source": p.source} for p in v]}
                                    for k, v in pinned.items() if v]}


# History ------------------------------------------------------------------------------------------------------------------

def history_path(root: Path) -> Path:
    return Path(root).joinpath(*HISTORY)


def read_history(root: Path) -> list[dict[str, Any]]:
    try:
        lines = history_path(root).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def _append_history(root: Path, row: dict[str, Any]) -> None:
    """One write of one line (a reader never sees half of one); nothing already there is changed."""
    path = history_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = (json.dumps(row, ensure_ascii=False) + "\n").encode("utf-8")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_BINARY", 0), 0o600)
    try:
        os.write(fd, line)
    finally:
        os.close(fd)


# The writes ---------------------------------------------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _who(by: str) -> str:
    name = " ".join(str(by or "").split())
    if not name:
        raise ValueError("A pick names who made it: say who is doing this (by).")
    if name.casefold() == "jason":
        raise ValueError("a person picks and answers; jason never writes in its own name")
    return name


def _words(text: str, what: str, *, required: bool = True) -> str:
    from jason.community.intake import secret_reason

    clean = " ".join(str(text or "").split())
    if required and not clean:
        raise ValueError(f"say {what}, in a few words: an answer is a person's finding")
    why = secret_reason(clean)
    if why:
        raise ValueError(f"the {what} {why}; nothing was written. Leave secrets out.")
    if len(clean) > 600:
        raise ValueError(f"the {what} is over 600 characters")
    return clean


def _slot(community: Any, key: str) -> tuple[Slot, str]:
    assembly = assemble(community)
    slot = next((s for s in assembly.slots if s.key == key), None)
    if slot is None:
        raise KeyError(key)
    return slot, assembly.hidden.get(key, "")


def _period(slot: Slot, period: str) -> str:
    import re

    clean = str(period or "").strip()
    if not clean:
        return ""
    if slot.cardinality is not Cardinality.SERIES:
        raise ValueError(f"{slot.key} holds {slot.cardinality.value}, not a series: a period belongs to a series slot")
    if not re.fullmatch(r"\d{4}(-\d{2}|-Q[1-4])?", clean):
        raise ValueError(f"a period is {PERIOD_FORMS}")
    return clean


def _write_store(profile: str, change, *, purpose: str) -> Path:
    """Read ``records.json`` fresh, apply ``change``, keep the old file as ``records.json.bak``, and replace it whole, under
    the store's lock."""
    from jason.locks import Resource, hold

    path = store_path(profile)
    with hold(Resource.STORE, f"record-slots-{profile}", timeout=120, purpose=purpose):
        try:
            data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        except ValueError as exc:
            raise ValueError(f"{path.name} is not valid JSON; fix it by hand before a write") from exc
        data = data if isinstance(data, dict) else {}
        data.setdefault("version", 1)
        data["profile"] = profile
        data.setdefault("pins", [])
        data.setdefault("answers", [])
        change(data)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_file():
            shutil.copyfile(path, path.with_name(path.name + ".bak"))
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(tmp, path)
    return path


def parse_file_ref(text: str) -> tuple[PinKind, str]:
    """What a person gave for a pick: ``library:ID`` (a file in jason's classified library) or a Drive link or id."""
    raw = str(text or "").strip()
    if raw.lower().startswith("library:"):
        ident = raw.split(":", 1)[1].strip()
        if not ident:
            raise ValueError("library: needs the library file's id")
        return PinKind.LIBRARY, ident
    ref = parse_drive_ref(raw)
    if ref.folder:
        raise ValueError("That is a folder. Picking a folder (a binding) comes with the chooser; paste the file's link, "
                         "or open the file in Drive and copy its link.")
    return PinKind.DRIVE, ref.id


def resolve(text: str, drive: Any) -> dict[str, Any]:
    """A pasted link resolved in Drive, read-only (``drive.get_file``): the name, type, size, and modified day, so the person
    sees what they pasted before the pick. ``drive`` is a ``GoogleDrive`` the caller opened (never a browser unless the
    caller asked); a file jason's account cannot see is a ValueError with the one line that says what to do."""
    kind, ref = parse_file_ref(text)
    if kind is not PinKind.DRIVE:
        raise ValueError("only a Drive link or id is resolved in Drive")
    try:
        meta = drive.get_file(ref)
    except Exception as exc:  # noqa: BLE001 - Google's refusal is the answer, in jason's words
        raise ValueError("jason's Drive account cannot open that file (not found, or not shared with it). Share it with the "
                         f"account jason signs in as, or upload it. ({type(exc).__name__})") from exc
    return {"id": ref, "name": str(meta.get("name") or ""), "type": str(meta.get("mimeType") or ""), "size": meta.get("size"),
            "modified": str(meta.get("modifiedTime") or "")[:10], "folder": meta.get("mimeType") == "application/vnd.google-apps.folder"}


def pick(slot_key: str, file: str, *, by: str, period: str = "", note: str = "", entry: str = "", drive: Any = None,
         dry_run: bool = True, community: Any = None, root: Path | None = None, profile: str | None = None) -> dict[str, Any]:
    """Pin a Drive file (link or id) or a library file (``library:ID``) to a slot, as ``by``. Copies, moves, shares, and
    writes nothing to the file. For a key-documents slot the pick is that store's link (one writer); a repeating row needs
    the instrument's recording number (``entry``). ``drive``, when given, resolves the link read-only first (a file jason's
    account cannot open writes nothing). A dry run (the default) says what it would write and writes nothing."""
    root = _root(root)
    profile = _profile(profile, community)
    who = _who(by)
    slot, hidden = _slot(community, slot_key)
    if hidden:
        raise ValueError(f"{slot_key} is hidden by the profile: {hidden}. Nothing was written.")
    kind, ref = parse_file_ref(file)
    note = _words(note, "note", required=False)
    period = _period(slot, period)
    name = ""
    if drive is not None and kind is PinKind.DRIVE:
        name = resolve(ref, drive)["name"]
    elif kind is PinKind.DRIVE:
        name = str(Library(root).drive.get(ref, {}).get("name") or "")
    elif kind is PinKind.LIBRARY:
        row = Library(root).by_id.get(ref)
        if row is None:
            raise ValueError(f"library file {ref} is not in the classified library (jason library lists them). Nothing was written.")
        name = str(row.get("name") or "")
    target = "key-documents/" + profile + ".json" if slot.key_document else f"spec/{profile}/{STORE}"
    entry_key = ""
    if slot.key_document:
        row_def = key_document(slot.key_document)
        assert row_def is not None
        if row_def.repeats:
            if not entry.strip():
                raise ValueError(f"{slot_key} holds recorded instruments, each by its recording number: pass the instrument "
                                 f"(--entry NUMBER) so the link goes to {row_def.key}/NUMBER, or use jason key-documents --link")
            entry_key = f"{row_def.key}/{entry.strip()}"
        else:
            entry_key = row_def.key
        if kind is PinKind.LIBRARY and not ref.isdigit():
            raise ValueError("a recorded instrument links a Drive file or a PayHOA library document (a numeric library id)")
    would = {"act": "pick", "slot": slot_key, "kind": kind.value, "ref": ref, "name": name, "period": period, "by": who,
             "writes": target, "entry": entry_key}
    if dry_run:
        return {"dryRun": True, "would": would, "note": "A dry run: nothing was written. Add --yes to record this pick. It names "
                "the file for the slot and copies, moves, shares, and renames nothing."}
    # Already pinned by the same file: the one pin.
    for existing in (_active_pins(root, profile, slot_key)):
        if existing.kind is kind and existing.ref == ref and existing.period == period:
            return {"dryRun": False, "ok": True, "pin": existing.id, "written": target, "already": True, "slot": slot_key}
    if slot.key_document:
        from jason.tasks import key_documents as kd

        if kind is PinKind.DRIVE:
            link = kd.link(entry_key, by=who, drive=ref, note=note, root=root, profile=profile)
        else:
            link = kd.link(entry_key, by=who, payhoa=ref, note=note, root=root, profile=profile)
        pin_id = "k-" + str(link["id"])
    else:
        pin_id = "p-" + secrets.token_hex(4)
        row = {"id": pin_id, "slot": slot_key, "kind": kind.value, "ref": ref, "name": name, "period": period, "by": who,
               "at": _now(), "note": note, "unpinned": None}
        _write_store(profile, lambda data: data["pins"].append(row), purpose="record slots: pick")
    _append_history(root, {"at": _now(), "profile": profile, "act": "pick", "slot": slot_key, "pin": pin_id, "by": who,
                           "kind": kind.value, "period": period, "note": note, "store": target})
    return {"dryRun": False, "ok": True, "pin": pin_id, "written": target, "slot": slot_key, "reading": "none queued (phase 2 reads a pick)"}


def _active_pins(root: Path, profile: str, slot_key: str) -> list[Pin]:
    slot = next((s for s in assemble(None).slots if s.key == slot_key), None)
    found = [p for p in (_pin_of(r) for r in load_store(profile)["pins"]) if p and p.slot == slot_key and p.active]
    if slot is not None:
        found += [p for p in _key_document_records(root, profile, slot)[0] if p.active]
    return found


def answer(slot_key: str, kind: AnswerKind | str, *, by: str, reason: str, who: str = "", dry_run: bool = True, community: Any = None,
           root: Path | None = None, profile: str | None = None) -> dict[str, Any]:
    """Record a person's word that a slot has no record to pick: not applicable (why it does not apply), none exists (what
    was looked for and where), or waiting (who has it, with ``who``). It hides nothing: the slot stays on the list. For a
    non-repeating key document, "none exists" is that store's "missing"."""
    root = _root(root)
    profile = _profile(profile, community)
    person = _who(by)
    slot, hidden = _slot(community, slot_key)
    if hidden:
        raise ValueError(f"{slot_key} is hidden by the profile: {hidden}. Nothing was written.")
    try:
        said = kind if isinstance(kind, AnswerKind) else AnswerKind(str(kind))
    except ValueError as exc:
        raise ValueError("an answer is notApplicable, none, or waiting") from exc
    if said is AnswerKind.NONE and not slot.existence:
        raise ValueError(f"{slot_key} cannot honestly be answered 'none exists'")
    what = {AnswerKind.NOT_APPLICABLE: "reason it does not apply", AnswerKind.NONE: "place you looked and what you looked for",
            AnswerKind.WAITING: "reason, and who has it"}[said]
    text = _words(reason, what)
    holder = _words(who, "name of who has it", required=False)
    key_row = key_document(slot.key_document) if slot.key_document else None
    through_key_documents = said is AnswerKind.NONE and key_row is not None and not key_row.repeats
    target = f"key-documents/{profile}.json" if through_key_documents else f"spec/{profile}/{STORE}"
    would = {"act": "answer", "slot": slot_key, "answer": said.value, "word": said.state.word, "reason": text, "who": holder,
             "by": person, "writes": target}
    if dry_run:
        return {"dryRun": True, "would": would, "note": "A dry run: nothing was written. Add --yes to record this answer. It "
                "is yours: it hides nothing, and says nothing about what the law requires."}
    if through_key_documents:
        from jason.tasks import key_documents as kd

        kd.set_status(key_row.key, "missing", by=person, note=text, root=root, profile=profile)
        ident = "ks-" + key_row.key
    else:
        ident = "a-" + secrets.token_hex(4)
        row = {"id": ident, "slot": slot_key, "answer": said.value, "reason": text, "who": holder, "by": person, "at": _now()}
        _write_store(profile, lambda data: data["answers"].append(row), purpose="record slots: answer")
    _append_history(root, {"at": _now(), "profile": profile, "act": "answer", "slot": slot_key, "answer": said.value,
                           "answerId": ident, "by": person, "store": target})
    return {"dryRun": False, "ok": True, "answer": ident, "written": target, "slot": slot_key}


def unpin(slot_key: str, *, by: str, pin: str = "", note: str = "", dry_run: bool = True, community: Any = None,
          root: Path | None = None, profile: str | None = None) -> dict[str, Any]:
    """Mark a person's pin removed (who and when are kept; the file stays where it is). With one active pin, ``pin`` may be
    left out. A pin the specification holds is not removed here: that is a change to the profile."""
    root = _root(root)
    profile = _profile(profile, community)
    person = _who(by)
    _slot(community, slot_key)
    note = _words(note, "note", required=False)
    active = _active_pins(root, profile, slot_key)
    if not pin:
        if len(active) != 1:
            raise ValueError(f"{slot_key} holds {len(active)} pins; name one with --pin (" + ", ".join(p.id for p in active) + ")"
                             if active else f"{slot_key} holds no pin of a person's to unpin")
        pin = active[0].id
    target = next((p for p in active if p.id == pin), None)
    if target is None:
        coded = any(p.id == pin for p in code_pins(community, assemble(community).slots).get(slot_key, []))
        raise ValueError("that pin is the specification's, not a person's: removing it is a change to the profile (a patch for a "
                         "person to apply)" if coded else f"{slot_key} has no active pin {pin}")
    store = f"key-documents/{profile}.json" if target.source == "key-documents" else f"spec/{profile}/{STORE}"
    would = {"act": "unpin", "slot": slot_key, "pin": pin, "by": person, "writes": store, "keeps": "the file where it is"}
    if dry_run:
        return {"dryRun": True, "would": would, "note": "A dry run: nothing was written. Add --yes to unpin. The file is not touched."}
    if target.source == "key-documents":
        from jason.tasks import key_documents as kd

        kd.unlink(target.store_id, pin.removeprefix("k-"), by=person, note=note, root=root, profile=profile)
    else:
        def change(data: dict[str, Any]) -> None:
            for row in data["pins"]:
                if row.get("id") == pin and not row.get("unpinned"):
                    row["unpinned"] = {"by": person, "at": _now(), "note": note}

        _write_store(profile, change, purpose="record slots: unpin")
    _append_history(root, {"at": _now(), "profile": profile, "act": "unpin", "slot": slot_key, "pin": pin, "by": person, "note": note, "store": store})
    return {"dryRun": False, "ok": True, "pin": pin, "written": store, "slot": slot_key}


__all__ = ["Assembly", "CAVEATS", "Computed", "Library", "RECORD_GROUPS", "answer", "assemble", "code_pins", "compute", "history_path",
           "load_store", "parse_file_ref", "pick", "pins_listing", "read_history", "resolve", "slot_view", "store_path", "unpin", "view"]
