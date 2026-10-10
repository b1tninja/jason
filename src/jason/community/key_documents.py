"""The key documents checklist: the declaration, each amendment and annexation, and the other documents an
association must be able to put its hands on, with each one's recording number, where a copy is, and its status.

Three layers, as everywhere in jason:

- **The list** (``KEY_DOCUMENTS``) is data: one row per kind of key document, named by its onboarding checklist item
  (``jason.community.onboarding``) where one exists, with the document kinds (``DocumentKind``), the governing-record
  roles (``jason.community.governing``), and the 2792.23 delivery (``DeveloperDelivery``) that fill it. A row that
  ``repeats`` expands to one entry per instrument (each amendment, each phase's annexation, each plan).
- **The expansion** (``expected_entries``) is pure: given what the specification pins (the governing document and its
  amendments, the supersessions, the Drive pins, the public reports), what the index holds (the governing records),
  what the locator found (leads), and the recorded copies on disk, it lists each entry with its number and copies.
- **The store** (``KeyDocumentStore``) is ``data/key-documents/<profile>.json``: what people did. A **link** attaches a
  copy (a file under data/, a Drive file, a PayHOA library document, or an upload), **unlink** marks a link removed
  (the file stays; who and when are kept), and **status** records a person's word (missing, held on paper). Every
  write names its person (``by``), holds the store's lock (``jason.locks``), and replaces the file whole.

A status is computed, never guessed: ``linked`` when a person linked a copy here; else the person's own status when
one is recorded; else ``held`` when the specification pins a copy or a recorded copy on disk carries the number; else
``located`` when a recording number is known (from the specification, the index, or a locator lead); else
``expected``. ``missing`` is only ever a person's word: none on record is not none given. A located number is a lead,
not a pin: the recorded copy is read before it is pinned in the specification.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping

from jason.community.symbols import DeveloperDelivery, DocumentKind

K = DocumentKind
D = DeveloperDelivery


class KeyStatus(Enum):
    EXPECTED = "expected"
    LOCATED = "located"
    HELD = "held"
    LINKED = "linked"
    MISSING = "missing"


STATUS_MEANING: dict[KeyStatus, str] = {
    KeyStatus.EXPECTED: "on the list; nothing on record yet",
    KeyStatus.LOCATED: "a recording number is known (a lead until the copy is read); no copy is held",
    KeyStatus.HELD: "a copy is held: a Drive pin in the specification, or a recorded copy on disk",
    KeyStatus.LINKED: "a person linked a copy here",
    KeyStatus.MISSING: "a person recorded that the association does not hold it",
}

# The statuses a person may record with ``status``; linked comes only from a link.
PERSON_STATUSES = (KeyStatus.EXPECTED, KeyStatus.LOCATED, KeyStatus.HELD, KeyStatus.MISSING)


class LinkKind(Enum):
    FILE = "file"          # a file under data/
    DRIVE = "drive"        # a Drive file, by id
    PAYHOA = "payhoa"      # a PayHOA library document, by id
    UPLOAD = "upload"      # a file a person chose, copied into data/key-documents/<profile>/files/


@dataclass(frozen=True)
class KeyDocument:
    """One kind of key document. ``key`` is the onboarding item it serves where there is one."""

    key: str
    title: str
    kinds: tuple[DocumentKind, ...] = ()
    roles: tuple[str, ...] = ()          # the governing-record roles (``GoverningRecord.role``) that fill it
    delivery: DeveloperDelivery | None = None
    repeats: bool = False                # one entry per instrument
    recorded: bool = False               # a recorded instrument the county index holds
    why: str = ""                        # filled from the onboarding item when empty
    source: str = ""


KEY_DOCUMENTS: tuple[KeyDocument, ...] = (
    KeyDocument("declaration", "The declaration (CC&Rs), the recorded copy", (K.DECLARATION,),
                ("declaration", "restated declaration"), D.DECLARATION, False, True, source="county recorder"),
    KeyDocument("amendments", "Each amendment to the declaration", (K.AMENDMENT,),
                ("amendment", "restatement or amendment", "covenant modification"), D.DECLARATION, True, True,
                source="county recorder"),
    KeyDocument("annexations", "Each annexation (supplementary declaration), one per phase", (K.ANNEXATION,),
                ("annexation",), D.DECLARATION, True, True, source="county recorder"),
    KeyDocument("articles", "Articles of incorporation", (K.ARTICLES,), ("articles",), D.ARTICLES,
                source="Secretary of State"),
    KeyDocument("bylaws", "Bylaws and their amendments", (K.BYLAWS,), ("bylaws",), D.BYLAWS, source="the association"),
    KeyDocument("operating-rules", "Operating rules", (K.OPERATING_RULES,), (), D.USE_RULES, source="the association"),
    KeyDocument("election-rules", "Election rules", (K.ELECTION_RULES,), (), None, source="the association"),
    KeyDocument("condominium-plans", "Each condominium plan and plan amendment", (K.CONDOMINIUM_PLAN,),
                ("condominium plan", "condominium plan amendment"), D.CONDOMINIUM_PLAN, True, True,
                source="county recorder"),
    KeyDocument("maps", "Subdivision and parcel maps", (K.MAP,), ("subdivision map", "parcel map"), D.SUBDIVISION_MAP,
                True, True, source="county recorder (map books)"),
    KeyDocument("common-area-deeds", "Each deed conveying common area to the association", (K.GRANT_DEED,),
                ("common area deed", "easement", "easement deed"), D.COMMON_AREA_DEED, True, True,
                source="county recorder"),
    KeyDocument("notices-of-completion", "Notices of completion", (), ("notice of completion",), D.NOTICE_OF_COMPLETION,
                True, True, why="starts the lien clocks on the work (CIV 8412, 8414); a 2792.23 delivery",
                source="county recorder"),
    KeyDocument("public-reports", "The developer's public reports, by phase", (K.DRE_REPORT,), (), D.PUBLIC_REPORT,
                source="Department of Real Estate"),
    KeyDocument("building-plans", "Building plan sets", (K.PLAN_SET,), (), D.MAINTENANCE_PLANS, source="city or developer"),
    KeyDocument("other-recorded", "Other recorded governing instruments (covenants, cancellations, agreements)", (),
                ("covenant", "cancellation of restrictions", "covenant and agreement"), D.RECIPROCAL_INSTRUMENT, True, True,
                why="an instrument recorded under the project's or the association's name that changes what binds it",
                source="county recorder"),
)

OTHER = "other"            # a person's own entry: other/<slug>, titled when it is first linked


def key_document(key: str) -> KeyDocument | None:
    return next((row for row in KEY_DOCUMENTS if row.key == key), None)


def why_of(row: KeyDocument) -> str:
    if row.why:
        return row.why
    from jason.community.onboarding import item

    found = item(row.key)
    return found.why if found is not None else ""


def item_of(entry_key: str) -> str:
    return entry_key.split("/", 1)[0]


_KEY = re.compile(r"^[a-z][a-z0-9-]*(?:/[A-Za-z0-9][A-Za-z0-9._-]{0,80})?$")


def valid_key(entry_key: str) -> bool:
    """An entry key: a list row's key, or ``<row>/<number or slug>``, or ``other/<slug>``."""
    if not _KEY.match(entry_key or ""):
        return False
    item = item_of(entry_key)
    return item == OTHER and "/" in entry_key or key_document(item) is not None


def slug(text: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", str(text).lower())).strip("-")[:60] or "document"


# The expansion ------------------------------------------------------------------------------------------------------

@dataclass
class Copy:
    """A copy jason can see without a person's link: a Drive pin in the specification or a recorded copy on disk."""

    kind: str                 # "drive" | "disk"
    ref: str                  # the Drive id, or the path under data/
    name: str
    source: str               # "specification pin" | "recorded copy on disk"

    def as_dict(self) -> dict[str, Any]:
        url = drive_url(self.ref) if self.kind == "drive" else ""
        return {"kind": self.kind, "ref": self.ref, "name": self.name, "source": self.source, "url": url}


@dataclass
class Entry:
    """One expected key document."""

    key: str
    item: str
    title: str
    number: str = ""
    recorded: str = ""
    phase: int | None = None
    role: str = ""
    filing: str = ""
    superseded_by: str = ""
    sections: tuple[str, ...] = ()
    copies: list[Copy] = field(default_factory=list)
    leads: list[dict[str, Any]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)

    def source(self, name: str) -> None:
        if name and name not in self.sources:
            self.sources.append(name)


_NUMBERS = re.compile(r"(?<![0-9])((?:19|20)\d{10}|(?:19|20)\d{2}-\d{7})(?![0-9])")
_PHASE = re.compile(r"\bphase\s*(\d+)\b", re.IGNORECASE)


def numbers_in(text: str) -> tuple[str, ...]:
    """Recording numbers a title or a path prints: Sacramento's twelve digits, or a year and a sequence (Placer)."""
    return tuple(dict.fromkeys(_NUMBERS.findall(str(text or ""))))


def drive_url(drive_id: str) -> str:
    return f"https://drive.google.com/open?id={drive_id}" if drive_id else ""


def expected_entries(
    *,
    governing_document: Any = None,
    governing: Iterable[Any] = (),
    unplaced: Iterable[Any] = (),
    supersessions: Iterable[Any] = (),
    pins: Iterable[Any] = (),
    public_reports: Iterable[Any] = (),
    located: Iterable[Mapping[str, Any]] = (),
    on_disk: Mapping[str, str] | None = None,
) -> list[Entry]:
    """Every expected key document, in list order, each with what is known of it.

    ``governing_document`` is the specification's declaration (``GoverningDocument``, with ``amendments``);
    ``governing`` and ``unplaced`` are the index's governing records (``GoverningRecord``); ``supersessions`` the
    specification's ``Supersession`` facts; ``pins`` its ``DocumentPin`` rows; ``public_reports`` its phases (``phase``,
    ``annexation``); ``located`` the locator's rows (number, recorded, filing, item, tie, via); ``on_disk`` each
    recording number a copy on disk carries, with its path under data/.
    """
    on_disk = dict(on_disk or {})
    entries: dict[str, Entry] = {}
    order: list[str] = []
    by_number: dict[str, str] = {}

    def add(entry: Entry) -> Entry:
        if entry.key in entries:
            return entries[entry.key]
        entries[entry.key] = entry
        order.append(entry.key)
        if entry.number:
            by_number.setdefault(entry.number, entry.key)
        return entry

    role_item = {role: row.key for row in KEY_DOCUMENTS for role in row.roles}
    for row in KEY_DOCUMENTS:
        if not row.repeats:
            add(Entry(row.key, row.key, row.title))

    # The specification's declaration and its amendments: firm numbers.
    declaration = entries["declaration"]
    doc = governing_document
    if doc is not None:
        if getattr(doc, "recorder_number", ""):
            declaration.number = doc.recorder_number
            declaration.recorded = _iso(getattr(doc, "recorded", None))
            by_number[declaration.number] = "declaration"
        declaration.source("specification")
        for amendment in getattr(doc, "amendments", ()) or ():
            number = getattr(amendment, "recorder_number", "") or ""
            title = getattr(amendment, "title", "") or "Amendment"
            entry = add(Entry(f"amendments/{number or slug(title)}", "amendments", title, number,
                              _iso(getattr(amendment, "recorded", None)), role="amendment",
                              sections=tuple(getattr(amendment, "sections", ()) or ())))
            entry.source("specification")
            if not number:
                entry.notes.append("no recording number in the specification: not recorded, or not yet read; an "
                                   "amendment takes effect when recorded (CIV 4270(a)(3))")

    # The index's governing records.
    governing, unplaced = list(governing), list(unplaced)
    unplaced_numbers = {r.number for r in unplaced}
    for record in governing + unplaced:
        item = role_item.get(record.role, "other-recorded")
        row = key_document(item)
        if row is not None and not row.repeats:
            target = entries[item]
            if record.superseded_by:
                entry = add(Entry(f"{item}/{record.number}", item, f"{_title_case(record.role)} (rescinded)", record.number))
            elif target.number and target.number != record.number:
                entry = add(Entry(f"{item}/{record.number}", item, _title_case(record.role), record.number))
            else:
                entry = target
                entry.number = entry.number or record.number
                by_number.setdefault(record.number, entry.key)
        else:
            key = by_number.get(record.number) or f"{item}/{record.number}"
            entry = add(Entry(key, item, _record_title(record), record.number))
        entry.recorded = entry.recorded or _iso(record.recorded)
        entry.phase = entry.phase if entry.phase is not None else record.phase
        entry.role = entry.role or record.role
        entry.filing = entry.filing or record.filing
        entry.superseded_by = entry.superseded_by or (record.superseded_by or "")
        entry.source("county index")
        if record.number in unplaced_numbers and not any("tied to no phase" in n for n in entry.notes):
            entry.notes.append("a developer's filing tied to no phase: may be another community's; read it before relying on it")

    # The specification's supersessions: the earlier instrument is rescinded.
    for fact in supersessions:
        key = by_number.get(fact.number)
        if key is None:
            item = "declaration" if getattr(fact, "role", "") == "declaration" else "annexations"
            entry = add(Entry(f"{item}/{fact.number}", item, f"{_title_case(getattr(fact, 'role', 'instrument'))} (rescinded)",
                              fact.number, phase=getattr(fact, "phase", None)))
        else:
            entry = entries[key]
        entry.superseded_by = fact.superseded_by
        entry.source("specification")
        reason = getattr(fact, "reason", "")
        if reason and reason not in entry.notes:
            entry.notes.append(reason)

    # Phases the public reports say were annexed with no annexation in force on the list.
    annexed = {e.phase for e in entries.values() if e.item == "annexations" and e.phase is not None and not e.superseded_by}
    for report in public_reports:
        phase = getattr(report, "phase", None)
        if phase is None or not getattr(report, "annexation", None) or phase in annexed:
            continue
        annexed.add(phase)
        entry = add(Entry(f"annexations/phase-{phase}", "annexations", f"Annexation of phase {phase}", phase=phase,
                          recorded=_iso(report.annexation)))
        entry.source("public reports")
        entry.notes.append(f"the public reports give phase {phase} an annexation date; no instrument for it is on the list")

    # Locator leads.
    for row in located:
        number = str(row.get("number", "") or "").strip()
        item = str(row.get("item", "") or "")
        if item == "recorded-liens" or (not number and not item):
            continue
        lead = {k: (str(v) if isinstance(v, date) else v) for k, v in row.items() if k in ("number", "recorded", "filing", "tie", "via", "item", "source")}
        key = by_number.get(number)
        if key is None:
            doc_row = key_document(item)
            if doc_row is None:
                continue
            if doc_row.repeats and number:
                filing = str(row.get("filing", "") or "")
                entry = add(Entry(f"{item}/{number}", item, _title_case(filing.lower()) or "Recorded instrument", number,
                                  _iso(row.get("recorded")), filing=filing))
            elif doc_row.repeats:
                continue
            else:
                entry = entries[item]
        else:
            entry = entries[key]
        if lead not in entry.leads:
            entry.leads.append(lead)
        entry.source("locator")

    # Copies: the Drive pins and the recorded copies on disk.
    primary = {row.key: row.key for row in KEY_DOCUMENTS if not row.repeats}
    # A pin is the specification's document when it is the same Drive file, or carries the same title with or without
    # its extension (a Doc and its PDF export).
    titles: dict[str, str] = {}
    if doc is not None:
        named = [(doc, "declaration")] + [
            (a, f"amendments/{getattr(a, 'recorder_number', '') or slug(getattr(a, 'title', ''))}")
            for a in getattr(doc, "amendments", ()) or ()
        ]
        for document, key in named:
            for mark in (getattr(document, "drive_id", ""), _stem(getattr(document, "title", ""))):
                if mark:
                    titles.setdefault(mark, key)
    for pin in pins:
        copy = Copy("drive", pin.drive_id, pin.title, "specification pin")
        numbers = numbers_in(pin.title)
        key = (next((by_number[n] for n in numbers if n in by_number), None) or titles.get(pin.drive_id)
               or titles.get(_stem(pin.title)))
        if key is None:
            row = _row_for_pin(pin)
            if row is None:
                continue
            phase = _PHASE.search(pin.title)
            if row.repeats and phase:
                key = next((k for k in order if entries[k].item == row.key and entries[k].phase == int(phase.group(1))
                            and not entries[k].superseded_by), None)
            if key is None and row.repeats and numbers:
                entry = add(Entry(f"{row.key}/{numbers[0]}", row.key, _stem(pin.title, fold=False), numbers[0]))
                entry.notes.append("named by a pinned copy only: the index cache holds no record of it")
                entry.source("specification")
                key = entry.key
            key = key or primary.get(row.key) or _group_key(row, entries, order, add)
        entry = entries[key]
        if all(c.ref != copy.ref for c in entry.copies):
            entry.copies.append(copy)
        entry.source("specification")
    for number, path in on_disk.items():
        key = by_number.get(number)
        if key is None:
            continue
        entry = entries[key]
        if all(c.ref != path for c in entry.copies):
            entry.copies.append(Copy("disk", path, Path(path).name, "recorded copy on disk"))
    return [entries[k] for k in _ordered(order, entries)]


def _group_key(row: KeyDocument, entries: dict[str, Entry], order: list[str], add) -> str:
    """Where a pin with no number goes on a repeating row: the row's files entry."""
    entry = add(Entry(f"{row.key}/files", row.key, f"{row.title.split(',')[0]}: copies not tied to one instrument"))
    entry.notes.append("pinned copies whose names carry no recording number; read each to tie it to its instrument")
    return entry.key


def _row_for_pin(pin: Any) -> KeyDocument | None:
    kind = getattr(pin, "kind", None)
    delivery = getattr(pin, "delivery", None)
    for row in KEY_DOCUMENTS:
        if kind in row.kinds:
            return row
    for row in KEY_DOCUMENTS:
        if delivery is not None and delivery is row.delivery and row.kinds:
            return row
    return None


def _ordered(order: list[str], entries: dict[str, Entry]) -> list[str]:
    rank = {row.key: i for i, row in enumerate(KEY_DOCUMENTS)}

    def key(entry_key: str):
        entry = entries[entry_key]
        return (rank.get(entry.item, len(rank)), "/" in entry_key and entry_key.endswith("/files"),
                entry.recorded or "9999", entry.number, entry_key)

    return sorted(order, key=key)


def _record_title(record: Any) -> str:
    role = _title_case(record.role)
    if record.phase is not None and record.role == "annexation":
        role = f"Annexation of phase {record.phase}"
    return role + (" (rescinded)" if record.superseded_by else "")


def _stem(title: str, *, fold: bool = True) -> str:
    """A title without a file extension, folded for matching: "CCRs - 2nd Amendment.pdf" is "ccrs - 2nd amendment"."""
    text = re.sub(r"\.(pdf|docx?|md|txt)$", "", " ".join(str(title or "").split()), flags=re.IGNORECASE)
    return text.casefold() if fold else text


def _title_case(text: str) -> str:
    text = str(text or "").strip()
    return text[:1].upper() + text[1:] if text else ""


def _iso(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()[:10]
    return str(value or "")


# Status -------------------------------------------------------------------------------------------------------------

def active_links(stored: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    return [link for link in (stored or {}).get("links", []) if not link.get("unlinked")]


def status_of(entry: Entry | None, stored: Mapping[str, Any] | None) -> tuple[KeyStatus, str]:
    """The entry's status and why, by the rule in the module's docstring."""
    if active_links(stored):
        n = len(active_links(stored))
        return KeyStatus.LINKED, f"{n} copy linked by a person" if n == 1 else f"{n} copies linked by a person"
    said = (stored or {}).get("status")
    if isinstance(said, Mapping) and said.get("value"):
        return KeyStatus(said["value"]), f"recorded by {said.get('by', '?')} on {str(said.get('at', ''))[:10]}" + (f": {said['note']}" if said.get("note") else "")
    if entry is not None and entry.copies:
        return KeyStatus.HELD, entry.copies[0].source
    if entry is not None and (entry.number or entry.leads):
        return KeyStatus.LOCATED, ("recording number from the " + ", ".join(entry.sources)) if entry.number else "a locator lead"
    return KeyStatus.EXPECTED, "none on record yet; none on record is not none given"


# The store ----------------------------------------------------------------------------------------------------------

def max_upload_bytes() -> int:
    """The largest upload, from the `upload.max_bytes` limit (jason.limits; 100 MB unless a person set it)."""
    from jason import limits

    return int(limits.value("upload.max_bytes"))


UPLOAD_SUFFIXES = frozenset({".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".tif", ".tiff", ".txt", ".md", ".doc", ".docx"})
_DRIVE_ID = re.compile(r"^[A-Za-z0-9_-]{10,}$")
_DRIVE_URL = re.compile(r"(?:/d/|[?&]id=|/folders/)([A-Za-z0-9_-]{10,})")


def drive_id(ref: str) -> str:
    """A Drive file id from an id or any Drive or Docs URL; ValueError when it holds none."""
    text = str(ref or "").strip()
    hit = _DRIVE_URL.search(text)
    if hit:
        return hit.group(1)
    if _DRIVE_ID.match(text):
        return text
    raise ValueError("give a Drive file id or its link (https://drive.google.com/file/d/ID/...)")


def payhoa_id(ref: str) -> str:
    text = str(ref or "").strip()
    if not text.isdigit():
        raise ValueError("a PayHOA library document is named by its number (the id in the library's link)")
    return text


def safe_name(name: str) -> str:
    """The original file name, without any folder, and without characters a file name cannot hold."""
    base = re.split(r"[\\/]", str(name or ""))[-1]
    base = "".join(ch for ch in base if ch >= " " and ch not in '<>:"|?*').strip(" .")
    if not base:
        raise ValueError("the file needs a name")
    return base[:180]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _who(by: str) -> str:
    name = " ".join(str(by or "").split())
    if not name:
        raise ValueError("say who is doing this: a write records its person (by)")
    if name.casefold() == "jason":
        raise ValueError("a person links and unlinks a copy; jason never writes in its own name")
    return name


class KeyDocumentStore:
    """``<data>/key-documents/<profile>.json`` and the uploads beside it in ``<profile>/files/``."""

    def __init__(self, root: Path | str, profile: str) -> None:
        self.root = Path(root)
        self.profile = profile
        self.folder = self.root / "key-documents"
        self.path = self.folder / f"{profile}.json"
        self.files = self.folder / profile / "files"

    def load(self) -> dict[str, Any]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {"version": 1, "profile": self.profile, "entries": {}}
        if not isinstance(data, dict) or not isinstance(data.get("entries"), dict):
            raise ValueError(f"{self.path.name} is not a key-documents store; fix it by hand")
        return data

    def entry(self, key: str) -> dict[str, Any]:
        return self.load()["entries"].get(key, {})

    def _write(self, data: dict[str, Any]) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(tmp, self.path)

    def _change(self, key: str, change, *, purpose: str) -> dict[str, Any]:
        from jason.locks import Resource, hold

        if not valid_key(key):
            raise KeyError(key)
        with hold(Resource.STORE, f"key-documents-{self.profile}", timeout=120, purpose=purpose):
            data = self.load()
            entry = data["entries"].setdefault(key, {"links": [], "status": None, "log": []})
            entry.setdefault("links", [])
            entry.setdefault("log", [])
            result = change(entry)
            self._write(data)
        return result

    def link(self, key: str, kind: LinkKind, ref: str, *, by: str, name: str = "", sha256: str = "", size: int | None = None,
             note: str = "", title: str = "") -> dict[str, Any]:
        """Attach a copy. The same copy linked again is the one link, not two."""
        who = _who(by)

        def change(entry: dict[str, Any]) -> dict[str, Any]:
            if title and not entry.get("title"):
                entry["title"] = " ".join(title.split())[:200]
            for held in entry["links"]:
                if held["kind"] == kind.value and held["ref"] == ref and not held.get("unlinked"):
                    return held
            link = {"id": "l-" + secrets.token_hex(4), "kind": kind.value, "ref": ref, "name": name or ref, "sha256": sha256,
                    "size": size, "by": who, "at": _now(), "note": note, "unlinked": None}
            entry["links"].append(link)
            entry["log"].append({"at": link["at"], "by": who, "action": "link", "link": link["id"], "note": note})
            return link

        return self._change(key, change, purpose="key documents: link")

    def unlink(self, key: str, link_id: str, *, by: str, note: str = "") -> dict[str, Any]:
        """Mark a link removed. Nothing is deleted: the file stays where it is, and the link keeps who removed it."""
        who = _who(by)

        def change(entry: dict[str, Any]) -> dict[str, Any]:
            for held in entry["links"]:
                if held["id"] == link_id:
                    if held.get("unlinked"):
                        return held
                    held["unlinked"] = {"by": who, "at": _now(), "note": note}
                    entry["log"].append({"at": held["unlinked"]["at"], "by": who, "action": "unlink", "link": link_id, "note": note})
                    return held
            raise KeyError(link_id)

        return self._change(key, change, purpose="key documents: unlink")

    def set_status(self, key: str, value: KeyStatus | str, *, by: str, note: str = "") -> dict[str, Any]:
        """A person's word on an entry: missing, held (on paper, say where), located, or back to expected."""
        who = _who(by)
        status = KeyStatus(value) if not isinstance(value, KeyStatus) else value
        if status not in PERSON_STATUSES:
            raise ValueError("linked comes from a link; record missing, held, located, or expected")
        if status is KeyStatus.MISSING and not note.strip():
            raise ValueError("say what was looked for and where, in a few words: missing is a person's finding")

        def change(entry: dict[str, Any]) -> dict[str, Any]:
            entry["status"] = {"value": status.value, "by": who, "at": _now(), "note": note}
            entry["log"].append({"at": entry["status"]["at"], "by": who, "action": "status", "status": status.value, "note": note})
            return entry["status"]

        return self._change(key, change, purpose="key documents: status")

    def save_upload(self, name: str, data: bytes) -> tuple[str, str, int]:
        """Keep a chosen file under ``files/<first 16 of its sha256>/<its original name>``: the same file twice is one
        copy, and nothing is ever overwritten. Returns the path under data/, the sha256, and the size."""
        original = safe_name(name)
        if Path(original).suffix.lower() not in UPLOAD_SUFFIXES:
            raise ValueError(f"{original}: jason keeps documents and scans ({', '.join(sorted(UPLOAD_SUFFIXES))})")
        if not data:
            raise ValueError(f"{original} is empty")
        cap = max_upload_bytes()
        if len(data) > cap:
            from jason import limits

            raise limits.refusal("upload.max_bytes", len(data), cap)
        digest = hashlib.sha256(data).hexdigest()
        target = self.files / digest[:16] / original
        if target.exists():
            if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                raise ValueError(f"{target} holds another file; nothing was written")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_name(target.name + ".part")
            tmp.write_bytes(data)
            os.replace(tmp, target)
        return target.relative_to(self.root).as_posix(), digest, len(data)


def file_digest(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


__all__ = [
    "Copy", "Entry", "KEY_DOCUMENTS", "KeyDocument", "KeyDocumentStore", "KeyStatus", "LinkKind", "max_upload_bytes",
    "OTHER", "PERSON_STATUSES", "STATUS_MEANING", "UPLOAD_SUFFIXES", "active_links", "drive_id", "drive_url",
    "expected_entries", "file_digest", "item_of", "key_document", "numbers_in", "payhoa_id", "safe_name", "slug",
    "status_of", "valid_key", "why_of",
]
