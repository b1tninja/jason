"""The association's records under Civil Code 5200: what each kind is, where the specification keeps it, and what is on hand.

Each record kind has a citation and a retention rule. The specification
pins where it lives: a PayHOA library folder, a Drive sync rule, a known
file. The local catalog says how many files those folders hold, and the
readings of the governing copies say which instruments are recorded, in
force, or unsigned drafts. A kind nothing pins is a gap the inventory
names; a kind with a holder but no files is a gap too.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from jason.community.records import CITATION
from jason.community.symbols import AssociationRecord

RETENTION: dict[AssociationRecord, str] = {
    AssociationRecord.MINUTES: "kept permanently; available within thirty days of the meeting (CIV 4950, 5210)",
    AssociationRecord.MEMBERSHIP_LIST: "kept current; opt-outs honored (CIV 5220, 5260)",
    AssociationRecord.GOVERNING_DOCUMENTS: "kept as long as they govern; the recorded copy is the record",
    AssociationRecord.ELECTION_MATERIALS: "kept one year after the election (CIV 5125)",
    AssociationRecord.ELEVATED_ELEMENT_REPORT: "kept for two inspection cycles (CIV 5551)",
}
DEFAULT_RETENTION = "the current fiscal year and the two prior fiscal years, producible within ten business days or thirty calendar days (CIV 5210)"

MEANING: dict[AssociationRecord, str] = {
    AssociationRecord.FINANCIAL_DISCLOSURE: "the annual budget report and policy statement and what backs them",
    AssociationRecord.TRANSFER_FINANCIAL: "the financial documents given on a sale under CIV 4525",
    AssociationRecord.INTERIM_FINANCIAL: "interim balance sheets, income statements, budget comparisons, and reserve statements",
    AssociationRecord.EXECUTED_CONTRACT: "executed contracts, except privileged ones, including insurance policies and leases",
    AssociationRecord.VENDOR_APPROVAL: "written board approvals of vendors or contractors",
    AssociationRecord.TAX_RETURN: "state and federal tax returns",
    AssociationRecord.RESERVE_ACCOUNT: "reserve account balances and the record of payments from them",
    AssociationRecord.MINUTES: "minutes of member, board, and committee meetings, not executive session",
    AssociationRecord.MEMBERSHIP_LIST: "the membership list under CIV 5200(a)(9) and Corporations Code 8330",
    AssociationRecord.CHECK_REGISTER: "the check register",
    AssociationRecord.GOVERNING_DOCUMENTS: "the declaration, articles, bylaws, rules, and their amendments and annexations",
    AssociationRecord.RESERVE_LITIGATION_ACCOUNTING: "the accounting for reserves used for litigation",
    AssociationRecord.ENHANCED: "invoices, receipts, canceled checks, statements, and reimbursement requests, with the redactions CIV 5215 allows",
    AssociationRecord.ELECTION_MATERIALS: "ballots, envelopes, sign-in sheets, and the tally, sealed after the count",
    AssociationRecord.ELEVATED_ELEMENT_REPORT: "the balcony and elevated-element inspection report under CIV 5551",
}


@dataclass
class Holding:
    kind: AssociationRecord
    citation: str
    meaning: str
    retention: str
    folders: list[dict[str, Any]] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    rules: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    # From the classified library: how many files are this record, and the newest by the period each gives.
    classified: int = 0
    newest: str = ""
    newest_period: str = ""

    @property
    def pinned(self) -> bool:
        return bool(self.folders or self.files or self.rules)

    @property
    def documents(self) -> int:
        return max(sum(int(folder.get("documents") or 0) for folder in self.folders), self.classified)

    @property
    def gap(self) -> str:
        if not self.pinned and not self.classified:
            return "nothing pinned and no classified file: no folder, file, or sync rule holds this kind, and the library shows none"
        if not self.pinned:
            return f"held in {self.classified} classified files with no pinned folder; pin the folder that should hold it"
        if self.folders and not self.documents and not self.files:
            return "a folder is pinned but the catalog holds no file in it"
        return ""


def inventory(community, catalog_paths: tuple[str, ...] = (), *, readings: tuple = (), governing=None, library: tuple = ()) -> tuple[Holding, ...]:
    """One holding per record kind, from the specification, the catalog's file paths, and the readings."""
    found: dict[AssociationRecord, Holding] = {
        kind: Holding(kind, CITATION[kind], MEANING.get(kind, ""), RETENTION.get(kind, DEFAULT_RETENTION)) for kind in AssociationRecord
    }
    for folder in _library(community):
        for kind in folder.records or ():
            count = sum(1 for path in catalog_paths if path.startswith(folder.path))
            found[kind].folders.append({"folder": folder.path, "payhoaId": folder.payhoa_id, "documents": count})
    for anchor in _files(community):
        for kind in anchor.records or ():
            found[kind].files.append(anchor.name)
    for rule in community.sync_rules:
        for kind in getattr(rule, "records", ()) or ():
            found[kind].rules.append(f"{rule.id.value}: Drive {rule.drive_folder} to PayHOA {rule.destination.value}")
    for row in library:
        for value in row.get("records") or ():
            try:
                holding = found[AssociationRecord(value)]
            except (ValueError, KeyError):
                continue
            holding.classified += 1
            period = str(row.get("period") or "")
            if not holding.newest or period > holding.newest_period:
                holding.newest_period = period
                holding.newest = f"{row.get('name', '')} ({period})" if period else str(row.get("name", ""))
    governing_notes = _governing_notes(readings, governing)
    if governing_notes:
        found[AssociationRecord.GOVERNING_DOCUMENTS].notes.extend(governing_notes)
    return tuple(found.values())


def _library(community):
    return tuple(community.library_folders())


def _files(community):
    return tuple(community.known_files())


def _governing_notes(readings: tuple, governing) -> list[str]:
    notes: list[str] = []
    for reading in readings:
        if reading.kind.value not in ("declaration", "amendment", "annexation"):
            continue
        name = reading.path.name.replace(".pdf.md", ".pdf").replace(".md", "")
        if reading.stamp.unrecorded_copy or getattr(reading, "unsigned", False):
            notes.append(f"{name}: an unrecorded copy" + (", unsigned" if getattr(reading, "unsigned", False) else "") + "; the recorded instrument is the record")
        elif reading.number:
            status = ""
            if governing is not None:
                match = next((g for g in governing if g.number == reading.number), None)
                if match is not None:
                    status = f", {match.status}"
            notes.append(f"{name}: recorded as {reading.number}{status}")
        else:
            notes.append(f"{name}: no stamp read; verify the copy")
    return notes


def inventory_markdown(holdings: tuple[Holding, ...], *, title: str) -> str:
    lines = [f"# {title}", ""]
    gaps = [h for h in holdings if h.gap]
    lines.append(f"{len(holdings)} kinds of record under Civil Code 5200. {len(holdings) - len(gaps)} have a pinned holder; {len(gaps)} do not, or hold no file yet.")
    lines.append("")
    lines.append("| Record | Citation | What it is | Where it lives | Files | Newest | Retention | Gap |")
    lines.append("| --- | --- | --- | --- | ---: | --- | --- | --- |")
    for h in holdings:
        where = "; ".join([f["folder"] for f in h.folders] + h.files + h.rules)
        lines.append(f"| {h.kind.value.replace('_', ' ')} | {h.citation} | {h.meaning} | {where} | {h.documents} | {h.newest} | {h.retention} | {h.gap} |")
    lines.append("")
    governing = next((h for h in holdings if h.kind is AssociationRecord.GOVERNING_DOCUMENTS), None)
    if governing is not None and governing.notes:
        lines.append("## The governing copies")
        lines.append("")
        lines.extend(f"- {note}" for note in governing.notes)
        lines.append("")
    lines.append("A gap is a place to look, not a finding that the record does not exist: the association may hold it outside PayHOA and Drive. The membership list is the Membership workbook, which Jason reads and does not write.")
    lines.append("")
    return "\n".join(lines)


def inventory_dicts(holdings: tuple[Holding, ...]) -> list[dict[str, Any]]:
    return [
        {"record": h.kind.value, "citation": h.citation, "meaning": h.meaning, "retention": h.retention, "folders": h.folders, "files": h.files, "rules": h.rules, "documents": h.documents, "classified": h.classified, "newest": h.newest, "notes": h.notes, "gap": h.gap}
        for h in holdings
    ]
