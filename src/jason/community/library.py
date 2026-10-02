"""The association's document library, classified: what each file is, which Civil Code 5200 record it is, and how we know.

The PayHOA catalog lists every file with its folder path. Classification
runs as a chain, and each stage records its method so a reader can weigh it:

1. the name and folder rules in the Mystique specification (``KIND_RULES``);
2. phrase rules over the document's own text (``content.py``), for names the
   rules miss and to confirm or refine what they said;
3. the agenda items that used the file, when their kinds and the file's text agree, or two or more uses agree
   (``Method.AGENDA``, from ``jason.tasks.agenda_kinds``);
4. a local model over the text, for what all three leave (``Method.MODEL``);
5. nothing, which is a miss and is reported as one.

A kind maps to its 5200 record through ``documents.PROFILE``; context can
add one (a financial copy in the resale packet is also a 4525 transfer
document, 5200(a)(2)). Confidential files (bank statements, owner
histories, delinquency files, the member list) are classified like any
other and flagged, so an ingestion step can keep them out of a shared
catalog. Nothing here calls PayHOA; the catalog is read from disk.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Any

from jason.community.documents import profile
from jason.community.symbols import AssociationRecord, DocumentCategory, DocumentKind


class Method(Enum):
    NAME = "name or folder rule"
    CONTENT = "phrase rule over the text"
    AGENDA = "agenda item that used the file"
    MODEL = "local model over the text"
    PERSON = "a person's answer (jason intake)"
    NONE = "unclassified"


@dataclass(frozen=True)
class LibraryDocument:
    source: str
    id: str
    path: str
    name: str
    folder: str
    size: int | None = None
    public: bool | None = None


# Kinds whose content is private to the board or an owner, wherever they are filed.
CONFIDENTIAL_KINDS = frozenset({
    DocumentKind.BANK_STATEMENT, DocumentKind.OWNER_HISTORY, DocumentKind.OWNER_STATEMENT, DocumentKind.ESCROW_REQUEST,
    DocumentKind.MEMBERSHIP_LIST, DocumentKind.DELINQUENCY_NOTICE,
    DocumentKind.EXECUTIVE_SESSION, DocumentKind.LEGAL_BRIEF, DocumentKind.VIOLATION_NOTICE, DocumentKind.RESALE_DISCLOSURE,
    # A claim's papers name the owners, the policyholders, and what was damaged in a unit; a police report names drivers.
    DocumentKind.CLAIM_LETTER, DocumentKind.CLAIM_PAYMENT, DocumentKind.CLAIM_AUTHORIZATION, DocumentKind.CLAIM_ESTIMATE,
    DocumentKind.POLICE_REPORT,
})
# A completed resident registration form carries the residents' names, phones, and vehicles.
CONFIDENTIAL_FOLDERS = ("confidential/", "resident registration forms/")
# Financial kinds the resale packet delivers under Civil Code 4525, which 5200(a)(2) makes a record of its own.
TRANSFER_FOLDERS = ("resale documents/",)


@dataclass(frozen=True)
class Classified:
    document: LibraryDocument
    kind: DocumentKind | None
    method: Method
    period: str = ""
    evidence: str = ""
    confidence: float | None = None
    extra_records: tuple[AssociationRecord, ...] = ()
    private: str = ""          # why the text makes it confidential (``content.private_content``), else ""

    @property
    def category(self) -> DocumentCategory | None:
        return profile(self.kind).category if self.kind else None

    @property
    def records(self) -> tuple[AssociationRecord, ...]:
        found: list[AssociationRecord] = []
        if self.kind is not None and profile(self.kind).record is not None:
            found.append(profile(self.kind).record)
        folder = self.document.path.casefold()
        if self.kind is not None and profile(self.kind).category is DocumentCategory.FINANCIAL and folder.startswith(TRANSFER_FOLDERS):
            found.append(AssociationRecord.TRANSFER_FINANCIAL)
        for record in self.extra_records:
            if record not in found:
                found.append(record)
        return tuple(found)

    @property
    def confidential(self) -> bool:
        return (self.kind in CONFIDENTIAL_KINDS or self.document.path.casefold().startswith(CONFIDENTIAL_FOLDERS)
                or bool(self.private))

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.document.id, "source": self.document.source, "path": self.document.path, "name": self.document.name,
            "kind": self.kind.value if self.kind else "", "category": self.category.value if self.category else "",
            "records": [r.value for r in self.records], "method": self.method.name, "period": self.period,
            "confidential": self.confidential, "evidence": self.evidence, "confidence": self.confidence,
        }


def payhoa_documents(db: Path) -> tuple[LibraryDocument, ...]:
    """Every file (not folder) in the PayHOA catalog, read-only."""
    if not Path(db).is_file():
        return ()
    conn = sqlite3.connect(f"file:{Path(db).as_posix()}?mode=ro", uri=True)
    try:
        rows = conn.execute("SELECT id, path, file_name, directory, public, file_size FROM documents").fetchall()
    finally:
        conn.close()
    found: list[LibraryDocument] = []
    # A folder row sometimes comes without its directory flag; one that other files sit under is a folder.
    parents = {str(path or "").rsplit("/", 1)[0].casefold() for _, path, _, _, _, _ in rows if "/" in str(path or "")}
    for doc_id, path, name, directory, public, size in rows:
        if directory or str(path or name or "").casefold() in parents:
            continue
        full = str(path or name or "")
        folder = full.rsplit("/", 1)[0] + "/" if "/" in full else ""
        found.append(LibraryDocument("payhoa", str(doc_id), full, str(name or full.rsplit("/", 1)[-1]), folder,
                                     int(size) if size is not None else None, bool(public) if public is not None else None))
    found.sort(key=lambda d: d.path.casefold())
    return tuple(found)


def folder_of(community, path: str):
    """The PayHOA folder whose library path is the longest prefix of ``path``, or None."""
    best = None
    folded = path.casefold()
    for folder in community.library_folders():
        prefix = folder.path.casefold()
        if folded.startswith(prefix) and (best is None or len(prefix) > len(best.path)):
            best = folder
    return best.folder if best is not None else None


_MONTHS = {m: i for i, m in enumerate(("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"), start=1)}
_PERIODS = (
    (re.compile(r"(?<!\d)(20\d\d)(\d\d)(\d\d)-(?:statements|noticesandletters)"), lambda m: f"{m[1]}-{m[2]}-{m[3]}"),
    (re.compile(r"(?:Minutes|Agenda)[^\d]*(\d{1,2})_(\d{1,2})_(\d\d)(?!\d)", re.I), lambda m: f"20{m[3]}-{int(m[1]):02d}-{int(m[2]):02d}"),
    (re.compile(r"(?<!\d)(\d{1,2})_(\d{1,2})_(\d\d)(?!\d)"), lambda m: f"20{m[3]}-{int(m[1]):02d}-{int(m[2]):02d}"),
    (re.compile(r"Report\s*-?\s*(20\d\d)-(\d\d)", re.I), lambda m: f"{m[1]}-{m[2]}"),
    (re.compile(r"(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)(20\d\d)", re.I), lambda m: f"{m[2]}-{_MONTHS[m[1].upper()]:02d}"),
    (re.compile(r"(?<![\d-])(20\d\d)-(\d\d)(?![\d])"), lambda m: f"{m[1]}-{m[2]}"),
    (re.compile(r"(?<!\d)(20[0-3]\d)(?!\d)"), lambda m: m[1]),
)


def period_of(name: str) -> str:
    """The date or month or year a file's name gives for its contents, or "" (a recorder number is not a year)."""
    stem = name.rsplit(".", 1)[0]
    if re.search(r"(?<!\d)(19|20)\d{10}(?!\d)", stem):
        return ""
    for pattern, render in _PERIODS:
        match = pattern.search(stem)
        if match:
            return render(match)
    return ""


def classify_by_name(community, doc: LibraryDocument) -> Classified:
    kind = community.classify_document(doc.name, folder_of(community, doc.path), doc.path)
    period = period_of(doc.name)
    if kind is None:
        return Classified(doc, None, Method.NONE, period)
    extra: tuple[AssociationRecord, ...] = ()
    evidence = "name and folder rules in the specification"
    account = _account_of(community, doc.name) if kind in (DocumentKind.BANK_STATEMENT, DocumentKind.CORRESPONDENCE) else None
    if account is not None:
        label = account.label or account.purpose.value
        evidence += f"; account ending {account.suffix} is the {label} account in the specification"
        if account.purpose.value == "reserve":
            # A reserve account's statements, and the bank's letters on a reserve CD, record reserve balances (5200(a)(7)).
            extra = (AssociationRecord.RESERVE_ACCOUNT,)
            if kind is DocumentKind.CORRESPONDENCE:
                extra += (AssociationRecord.ENHANCED,)
    return Classified(doc, kind, Method.NAME, period, evidence=evidence, extra_records=extra)


def _account_of(community, name: str):
    """The specification's bank account whose suffix the statement file name carries, or None."""
    accounts = getattr(community, "bank_accounts", lambda: ())() or ()
    for account in accounts:
        if re.search(rf"(?<!\d){re.escape(account.suffix)}(?!\d)", name):
            return account
    return None


def classify_library(community, docs: tuple[LibraryDocument, ...]) -> tuple[Classified, ...]:
    return tuple(classify_by_name(community, doc) for doc in docs)


@dataclass
class Coverage:
    total: int = 0
    by_method: dict[str, int] = field(default_factory=dict)
    by_kind: dict[str, int] = field(default_factory=dict)
    by_record: dict[str, int] = field(default_factory=dict)
    unclassified: list[str] = field(default_factory=list)
    confidential: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {"total": self.total, "byMethod": self.by_method, "byKind": self.by_kind, "byRecord": self.by_record,
                "unclassified": self.unclassified, "confidential": self.confidential}


def coverage(rows: tuple[Classified, ...]) -> Coverage:
    found = Coverage(total=len(rows))
    for row in rows:
        found.by_method[row.method.name] = found.by_method.get(row.method.name, 0) + 1
        key = row.kind.value if row.kind else "(none)"
        found.by_kind[key] = found.by_kind.get(key, 0) + 1
        for record in row.records:
            found.by_record[record.value] = found.by_record.get(record.value, 0) + 1
        if row.kind is None:
            found.unclassified.append(row.document.path)
        if row.confidential:
            found.confidential += 1
    found.by_kind = dict(sorted(found.by_kind.items(), key=lambda kv: -kv[1]))
    return found


def latest_by_record(rows: tuple[Classified, ...]) -> dict[AssociationRecord, Classified]:
    """The newest dated document of each 5200 record kind, by the period its name gives."""
    best: dict[AssociationRecord, Classified] = {}
    for row in rows:
        for record in row.records:
            current = best.get(record)
            if current is None or (row.period or "") > (current.period or ""):
                best[record] = row
    return best


def library_markdown(rows: tuple[Classified, ...], *, title: str, today: date | None = None, distinct_files: int | None = None) -> str:
    """The library page: coverage by method, by 5200 record, and by kind, then what no stage classified."""
    from jason.community.records import CITATION

    cov = coverage(rows)
    lines = [f"# {title}", ""]
    lines.append(
        f"{cov.total} files in the PayHOA library, classified by the chain: the specification's name and folder rules, "
        "then phrase rules over each file's text, then a local model. Each row keeps its method. A blank template or a "
        "photo is classified so it can be set aside; it is not an association record."
        + (f" Read {today.isoformat()}." if today else "")
        + (f" {distinct_files} are distinct: the rest are the same file filed twice (a meeting's minutes and its copy in Email "
           "Attachments), counted here per filing and once in the records inventory." if distinct_files else "")
    )
    lines.append("")
    lines.append("| Method | Files |")
    lines.append("| --- | ---: |")
    for method in Method:
        if cov.by_method.get(method.name):
            lines.append(f"| {method.value} | {cov.by_method[method.name]} |")
    lines.append("")
    latest = latest_by_record(rows)
    lines.append("## Civil Code 5200 records held")
    lines.append("")
    lines.append("| Record | Citation | Files | Newest by name |")
    lines.append("| --- | --- | ---: | --- |")
    for record in AssociationRecord:
        count = cov.by_record.get(record.value, 0)
        newest = latest.get(record)
        shown = f"{newest.document.name} ({newest.period})" if newest and newest.period else (newest.document.name if newest else "")
        lines.append(f"| {record.value.replace('_', ' ')} | {CITATION[record]} | {count} | {_cell(shown)} |")
    lines.append("")
    lines.append(f"{cov.confidential} files are confidential (bank statements, owner histories, delinquency files, the member list, "
                 "executive sessions, and the Confidential folder); they stay out of the shared catalogs.")
    lines.append("")
    lines.append("## By kind")
    lines.append("")
    lines.append("| Kind | Shelf | Files |")
    lines.append("| --- | --- | ---: |")
    for key, count in cov.by_kind.items():
        shelf = profile(DocumentKind(key)).category.value if key != "(none)" else ""
        lines.append(f"| {key.replace('_', ' ')} | {shelf} | {count} |")
    lines.append("")
    if cov.unclassified:
        lines.append("## Unclassified")
        lines.append("")
        lines.append("No stage placed these. Each is a new rule row in `mystique/documents.py`, a phrase rule, or a file for a person to name.")
        lines.append("")
        lines.extend(f"- {path}" for path in cov.unclassified)
        lines.append("")
    return "\n".join(lines)


def _cell(text: str) -> str:
    return " ".join(str(text).split()).replace("|", "/")
