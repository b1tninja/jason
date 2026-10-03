"""Permanent section ids on disk: build each document's table, find a cited section again, and migrate the records.

- ``build`` makes a document's ``IdTable`` (``jason.community.permanent_ids``): a document kept as amended from its
  versions (``section_refs.build_versions``), with its outline on disk (the working copy as read) named as the
  ``outline`` reading; any other document from its outline alone. The table is kept in
  ``data/section-refs/ids-<document>.json``; a rebuild carries the stored ids, so a section numbered differently by a
  new reading keeps its id and gains a name. A table another history source wrote (``source`` other than
  ``versions`` or ``outline``: a revision detector's lineages) is read, never rebuilt here.
- ``locate`` finds the section a record cites (a document, the number as written, the words it quotes, the day it was
  written): its permanent id, the version in force that day, the reading that numbers it so, and its number now.
- ``migrate`` adds the permanent id and the version cited to the records that cite sections, keeping each one's number
  as written. Data records get new fields in place (the stored document duties, the transcriptions, and the records
  of ``{QUOTE:}`` renderings), each file backed up once beside itself; the specification's rows (Conflict rows,
  notice provisions, the profile's corrections) are Python, so their ids go in a register,
  ``data/section-refs/cited.json``. Nothing is removed or renamed; a dry run is the default.

Reading only, except ``migrate --apply`` and the cached tables: nothing here reaches Drive, PayHOA, or the mail.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from dataclasses import dataclass, replace
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable

from jason.community.living import provisions_of
from jason.community.outlines import normalize_number
from jason.community.permanent_ids import IdTable, add_reading, base_number, carry, from_versions

OUTLINE = "outline"            # the reading of the outline on disk (for a living document: the working copy as read)
OWN_SOURCES = frozenset({"versions", "outline"})
REGISTER = "cited.json"


def ids_path(data_dir: Path, document: str) -> Path:
    from jason.tasks.section_refs import store_dir

    return store_dir(data_dir) / f"ids-{document}.json"


def load(data_dir: Path, document: str) -> IdTable | None:
    path = ids_path(data_dir, document)
    if not path.is_file():
        return None
    try:
        return IdTable.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, KeyError):
        return None


def save(table: IdTable, data_dir: Path) -> Path:
    path = ids_path(data_dir, table.document)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(table.to_dict(), indent=1), encoding="utf-8")
    return path


def _stat(path: Path) -> str:
    if not path.is_file():
        return f"{path.name}:-"
    st = path.stat()
    return f"{path.name}:{st.st_size}:{int(st.st_mtime)}"


def _fingerprint(resolver: Any, document: str, key: str) -> str:
    from jason.tasks.section_refs import _fingerprint as versions_fingerprint

    import jason.community.permanent_ids as ids_mod

    h = hashlib.sha256(key.encode("utf-8"))
    living = resolver.living(document)
    if living is not None:
        h.update(versions_fingerprint(living, resolver.data_dir).encode())
    h.update(_stat(Path(resolver.data_dir) / "outlines" / f"{document}.json").encode())
    h.update(hashlib.sha256(Path(ids_mod.__file__).read_bytes()).digest())
    return h.hexdigest()[:24]


def effective_dates(versions: Any) -> list[date | None]:
    """The day each version of a living document took effect, oldest first (None for the base)."""
    snaps = versions.snapshots
    return [None] + [snaps[k - 1].until + timedelta(days=1) for k in range(1, len(snaps))]


def build(resolver: Any, document: str, *, key: str = "", refresh: bool = False) -> IdTable | None:
    """The document's table, rebuilt when its sources changed and carried from the stored one. None when the document
    has neither versions nor an outline on disk and no other source wrote a table."""
    from jason.tasks.living_docs import chosen_reading

    key = key or document
    stored = load(resolver.data_dir, document)
    if stored is not None and stored.source and stored.source not in OWN_SOURCES:
        return stored                                    # another history source's table: read, never rebuilt
    fingerprint = _fingerprint(resolver, document, key)
    if stored is not None and stored.fingerprint == fingerprint and stored.key == key and not refresh:
        return stored
    today = date.today().isoformat()
    living = resolver.living(document)
    outline = resolver.outline(document)
    if living is not None:
        versions = resolver.versions(document)
        days = effective_dates(versions)
        fresh = from_versions(key, [(d, s.provisions) for d, s in zip(days, versions.snapshots)], document=document,
                              basis=chosen_reading(resolver.data_dir, document) or "original", built=today)
        fresh.source = "versions"
        if outline is not None:
            working = bool(living.working_doc) and outline.source == living.working_doc
            add_reading(fresh, OUTLINE, provisions_of(outline), versions.now.provisions,
                        describe=f"data/outlines/{document}.json" + (" (the working copy kept by hand)" if working
                                                                     else ""))
    elif outline is not None:
        fresh = from_versions(key, [(None, provisions_of(outline))], document=document,
                              basis=f"outline revision {outline.revision}" if outline.revision else "outline",
                              built=today)
        fresh.source = "outline"
    else:
        return stored
    fresh.fingerprint = fingerprint
    if stored is not None and stored.key == key:
        fresh = carry(stored, fresh, reading_was=stored.basis or "earlier")
    save(fresh, resolver.data_dir)
    return fresh


# --- Finding a cited section again ---------------------------------------------------------------------------------------

def _letters(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


@dataclass(frozen=True)
class Located:
    pid: str
    number: str                  # the number now, in the text as amended ("" when gone)
    written: str                 # the number as the record wrote it
    reading: str = ""            # the reading that numbers it as written ("" the text as amended)
    version: str = ""            # the version in force when it was written ("@base", "@2099-01-01")
    within: bool = False         # the record's section runs inside ``number`` in the text as amended
    quoted: bool | None = None   # whether the record's quote is in the section's words (None: no quote)
    ambiguous: bool = False      # more than one section answers to the number (another reading, a number printed
                                 # twice) and no quote tells them apart
    removed: bool = False
    twice: bool = False          # the document prints its number more than once
    others: tuple[str, ...] = ()  # the other ids the number may name, when nothing told them apart

    def note(self) -> str:
        where = (f"under the {self.reading} reading" if self.reading else "in the text as amended")
        if self.removed:
            return f"{self.written} {where} is {self.pid}, since removed"
        if self.within:
            return (f"{self.written} {where} runs inside {self.number} in the text as amended, which does not split it "
                    f"({self.pid})")
        head, n = base_number(self.number or self.pid.rsplit("/", 1)[-1])
        if self.twice:
            return f"the document numbers more than one section {head}; this is number {n} in order ({self.pid})"
        if self.number == self.written:
            return f"{self.pid}"
        return f"renumbered: {self.written} {where} is {self.number} in the text as amended ({self.pid})"

    def as_dict(self) -> dict[str, Any]:
        out = {"written": self.written, "pid": self.pid, "number": self.number, "version": self.version}
        if self.reading:
            out["reading"] = self.reading
        if self.within:
            out["within"] = True
        if self.ambiguous:
            out["ambiguous"] = True
            out["candidates"] = [self.pid, *self.others]
            del out["pid"]                       # never stored: a person picks
        return out


class Locator:
    """Finds cited sections by permanent id, over the documents a ``DiskResolver`` reads."""

    def __init__(self, resolver: Any, books: Any = None):
        self.resolver = resolver
        self.books = books
        self._tables: dict[str, IdTable | None] = {}
        self._docs: dict[tuple[str, date | None], Any] = {}
        self.errors: list[str] = []          # tables that could not be built, and why

    def table(self, document: str) -> IdTable | None:
        if document not in self._tables:
            key = self.books.key(document) if self.books is not None else document
            try:
                self._tables[document] = build(self.resolver, document, key=key)
            except Exception as exc:     # a document that cannot be read is a miss for its ids, never a traceback
                self._tables[document] = None
                self.errors.append(f"permanent ids of {document}: {exc}")
        return self._tables[document]

    def version_label(self, document: str, day: date | None) -> str:
        """The version in force on ``day`` (now when None): ``@base`` or the day it took effect."""
        if self.resolver.living(document) is None:
            return "@base"
        try:
            v = self.resolver.versions(document)
        except Exception:
            return ""
        days = effective_dates(v)
        current = "@base"
        for d in days[1:]:
            if day is None or d <= day:
                current = f"@{d.isoformat()}"
        return current

    def _doc(self, document: str, day: date | None = None) -> Any:
        if (document, day) not in self._docs:
            try:
                self._docs[(document, day)] = self.resolver.document(document, day)[0]
            except Exception:
                self._docs[(document, day)] = None
        return self._docs[(document, day)]

    def words(self, document: str, number: str, day: date | None = None) -> str:
        """A section's words with its subsections', the n-th of a number printed twice (``B-1~2``)."""
        doc = self._doc(document, day)
        if doc is None or not number:
            return ""
        head, n = base_number(number)
        at = [k for k, p in enumerate(doc.provisions) if p.number == head]
        if len(at) < n:
            return ""
        k = at[n - 1]
        out = [doc.provisions[k]]
        for p in doc.provisions[k + 1:]:
            if p.number and (p.number.startswith(head + "(") or p.number.startswith(head + ".")):
                out.append(p)
            else:
                break
        return "\n".join("\n".join(x for x in (p.caption, p.body) if x) for p in out if not p.removed)

    def locate(self, document: str, number: str, *, quote: str = "", day: date | None = None, pid: str = "",
               reading: str = "") -> Located | None:
        """The section a record cites. ``pid`` (stored by the migration) is used as it is; otherwise each reading is
        tried (the one named, the text as amended on ``day``, then the others) and a quote picks among them."""
        table = self.table(document)
        if table is None:
            return None
        number = normalize_number(number) if "~" not in number else number
        version = self.version_label(document, day)
        wanted = _letters(quote)
        tried: list[tuple[str, str]] = []
        if pid:
            tried = [(reading, pid)]
        else:
            order = [r for r in dict.fromkeys([reading, "", *table.readings]) if r == "" or r in table.readings]
            for r in order:
                for p in table.candidates(number, r, day if not r else None):
                    if (r, p) not in tried and all(p != q for _, q in tried):
                        tried.append((r, p))
        if not tried:
            return None
        found = []
        for r, p in tried:
            s = table.get(p)
            if s is None:
                continue
            now = table.name_of(p)
            here = now.number if now is not None else ""
            mine = [n for n in s.names if n.reading == r and n.number == number] if r else []
            within = any(n.within for n in mine)
            quoted = None
            if wanted:
                quoted = wanted in _letters(self.words(document, here))
            twice = any(base_number(q)[0] == base_number(here)[0] and q != here
                        for q in (table.number_of(x) or "" for _, x in tried if x != p)) or "~" in here
            found.append(Located(p, here, number, r, version, within, quoted, False, s.removed is not None, twice))
        if wanted:
            hits = [x for x in found if x.quoted]
            if hits:
                return hits[0]
        first = found[0] if found else None
        if first is None:
            return None
        others = tuple(dict.fromkeys(x.pid for x in found if x.pid != first.pid))
        if others and not wanted:
            first = replace(first, ambiguous=True, others=others)
        return first


# --- The migration ---------------------------------------------------------------------------------------------------------

def _backup(path: Path) -> Path | None:
    """A copy of ``path`` before its first migration (``NAME.pre-ids.bak``), never overwritten."""
    if not path.is_file():
        return None
    bak = path.with_name(path.name + ".pre-ids.bak")
    if not bak.exists():
        shutil.copy2(path, bak)
    return bak


def _fields(loc: Located) -> dict[str, Any]:
    if loc.ambiguous:
        return {}                            # more than one section answers: a person picks, nothing is stored
    out = {"pid": loc.pid, "version": loc.version}
    if loc.reading:
        out["reading"] = loc.reading
    if loc.within:
        out["within"] = True
    return out


def _numbers(field: str) -> list[str]:
    from jason.tasks.cite import _numbers_in

    return _numbers_in(field)


def migrate(shelf: Any, *, apply: bool = False, log=None) -> dict[str, Any]:
    """Add each citing record's permanent id and the version it cites. Returns counts by record kind and the records
    that could not be placed or are ambiguous across readings; with ``apply``, writes them (backups first)."""
    from jason.locks import Resource, hold

    data_dir = Path(shelf.data_dir)
    loc = shelf.locator
    report: dict[str, Any] = {"applied": apply, "kinds": {}, "unplaced": [], "ambiguous": [], "written": [],
                              "backups": []}

    def count(kind: str, ok: bool) -> None:
        row = report["kinds"].setdefault(kind, {"placed": 0, "unplaced": 0})
        row["placed" if ok else "unplaced"] += 1

    def note(kind: str, key: str, document: str, number: str, got: Located | None) -> None:
        count(kind, got is not None)
        if got is None:
            report["unplaced"].append({"record": key, "document": document, "written": number})
        elif got.ambiguous:
            report["ambiguous"].append({"record": key, "document": document, "written": number,
                                        "candidates": [got.pid, *got.others]})

    # Stored document duties: the number as written stays in "section".
    folder = data_dir / "duties"
    for path in sorted(folder.glob("*.json")) if folder.is_dir() else ():
        with hold(Resource.STORE, f"duties-{path.stem}", timeout=60, purpose="jason cite --migrate-ids"):
            raw = json.loads(path.read_text(encoding="utf-8"))
            read_day = None
            if raw.get("read"):
                try:
                    read_day = date.fromisoformat(str(raw["read"])[:10])
                except ValueError:
                    read_day = None
            changed = False
            for item in raw.get("duties") or ():
                section = normalize_number(item.get("section") or "")
                if not section or not re.match(r"^(?:[A-Z]{1,2}-)?\d", section):
                    continue
                document = item.get("source") or path.stem
                got = loc.locate(document, section, quote=item.get("quote", ""), day=read_day, reading=OUTLINE)
                note("duty", item.get("id", ""), document, section, got)
                if got is not None:
                    new = _fields(got)
                    if any(item.get(k) != v for k, v in new.items()):
                        item.update(new)
                        changed = True
            if changed and apply:
                report["backups"].append(str(_backup(path)))
                path.write_text(json.dumps(raw, indent=1), encoding="utf-8")
                report["written"].append(str(path))
    # Transcriptions: corrections to a living document's words, read against its base.
    for living in getattr(shelf.community, "living_documents", lambda: ())():
        from jason.tasks.living_docs import transcriptions_path

        path = transcriptions_path(data_dir, living.key)
        if not path.is_file():
            continue
        rows = json.loads(path.read_text(encoding="utf-8"))
        base_day = None
        try:
            v = shelf.resolver.versions(living.key)
            base_day = v.snapshots[0].until if len(v.snapshots) > 1 else None
        except Exception:
            pass
        changed = False
        for r in rows:
            section = normalize_number(r.get("section") or "")
            got = loc.locate(living.key, section, quote=r.get("right", ""), day=base_day) \
                or loc.locate(living.key, section, quote=r.get("right", ""))
            note("transcription", f"{living.key}:{section}:{r.get('wrong', '')}", living.key, section, got)
            if got is not None:
                new = _fields(got)
                if any(r.get(k) != v for k, v in new.items()):
                    r.update(new)
                    changed = True
        if changed and apply:
            report["backups"].append(str(_backup(path)))
            path.write_text(json.dumps(rows, indent=1), encoding="utf-8")
            report["written"].append(str(path))
    # The records of {QUOTE:}/{CITE:} renderings.
    for path in sorted(data_dir.rglob("*.refs.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        changed = False
        for r in raw.get("references") or ():
            day = date.fromisoformat(r["as_of"]) if r.get("as_of") else None
            got = loc.locate(r.get("key", ""), r.get("section", ""), day=day)
            note("rendering", f"{path.name}:{r.get('token', '')}", r.get("key", ""), r.get("section", ""), got)
            if got is not None:
                new = _fields(got)
                if any(r.get(k) != v for k, v in new.items()):
                    r.update(new)
                    changed = True
        if changed and apply:
            report["backups"].append(str(_backup(path)))
            path.write_text(json.dumps(raw, indent=1), encoding="utf-8")
            report["written"].append(str(path))
    # The specification's rows: a register, since jason does not rewrite Python.
    register: dict[str, list[dict[str, Any]]] = {}
    c = shelf.community
    for p in getattr(c, "notice_provisions", lambda: ())():
        for number in _numbers(p.section or ""):
            got = loc.locate(p.document, number)
            note("notice provision", f"notice:{p.key}", p.document, number, got)
            if got is not None:
                register.setdefault(f"notice:{p.key}", []).append({"document": p.document, **got.as_dict()})
    from jason.community.cite import Unit, targets_in

    names = shelf.names()
    for r in getattr(c, "conflicts", lambda: ())():
        for t in targets_in(r.provision, names):
            if t.unit is not Unit.SECTION or not re.match(r"^(?:[A-Z]{1,2}-)?\d", t.number):
                continue
            got = loc.locate(t.key, t.number)
            note("conflict row", f"conflict:{r.key}", t.key, t.number, got)
            if got is not None:
                register.setdefault(f"conflict:{r.key}", []).append({"document": t.key, **got.as_dict()})
    for living in getattr(c, "living_documents", lambda: ())():
        for k, corr in enumerate(living.corrections):
            section = normalize_number(corr.section)
            got = loc.locate(living.key, section, quote=corr.right)
            note("correction", f"correction:{living.key}:{k}", living.key, section, got)
            if got is not None:
                register.setdefault(f"correction:{living.key}:{k}", []).append({"document": living.key,
                                                                                **got.as_dict()})
    report["register"] = len(register)
    if apply:
        from jason.tasks.section_refs import store_dir

        path = store_dir(data_dir) / REGISTER
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_file():
            report["backups"].append(str(_backup(path)))
        path.write_text(json.dumps({"format": 1, "built": date.today().isoformat(), "records": register}, indent=1),
                        encoding="utf-8")
        report["written"].append(str(path))
    if log:
        for kind, row in report["kinds"].items():
            log(f"{kind}: {row['placed']} placed, {row['unplaced']} not")
    return report


def load_register(data_dir: Path) -> dict[str, list[dict[str, Any]]]:
    """The register of the specification's rows (``migrate --apply`` writes it): record key -> its cited sections."""
    from jason.tasks.section_refs import store_dir

    path = store_dir(Path(data_dir)) / REGISTER
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("records") or {}
    except (OSError, ValueError):
        return {}


def timeline(locator: Locator, document: str, number: str, *, day: date | None = None) -> dict[str, Any] | None:
    """A section's history by its permanent id: each version of the document with the number it went by and whether
    its words changed, then the names other readings give it."""
    table = locator.table(document)
    if table is None:
        return None
    pid = table.permanent_id(number, day) or (table.candidates(number, OUTLINE) or [None])[0]
    if pid is None:
        return None
    s = table.get(pid)
    rows: list[dict[str, Any]] = []
    resolver = locator.resolver
    if resolver.living(document) is not None:
        v = resolver.versions(document)
        last = None
        for eff, snap in zip(effective_dates(v), v.snapshots):
            here = eff or (None if len(v.snapshots) == 1 else v.snapshots[0].until)
            n = table.number_of(pid, here)
            words = locator.words(document, n, here) if n else ""
            rows.append({"version": f"@{eff.isoformat()}" if eff else "@base", "through": snap.through or "the base",
                         "number": n, "changed": last is not None and words != last, "present": bool(words),
                         "inForce": True})
            last = words
        now = table.number_of(pid)
        for op in v.pending:                              # a draft that would set it: a stage, never in force
            if now and normalize_number(op.get("section", "")) == now:
                info = v.instruments.get(op["instrument"]) or {}
                stamp = info.get("dated") or "undated"
                rows.append({"version": f"@{info.get('standing', 'draft')}-{stamp}", "through": info.get("describe")
                             or op["instrument"], "number": now, "changed": True, "present": True, "inForce": False})
    names = [n.to_dict() | {"says": n.describe()} for n in s.names
             if n.reading and (n.within or n.number != (table.number_of(pid) or ""))]
    return {"pid": pid, "born": s.born.isoformat() if s.born else "base",
            "removed": s.removed.isoformat() if s.removed else None, "versions": rows, "readings": names}


__all__ = ["Located", "Locator", "OUTLINE", "build", "effective_dates", "ids_path", "load", "load_register", "migrate",
           "save", "timeline"]
