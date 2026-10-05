"""The subdivider's securities to the association, phase by phase: agreements, bonds, and what released them.

Reads the developer-security documents saved from Drive (``data/developer-security``: each PDF with its text beside it,
listed in ``index.json``) and any library files of the same kinds. A compiled production (the developer's 2022
response to the association's 10 CCR 2792.23 demand) is cut into its instruments. Each instrument reads with its model
(``jason.community.models.developer_security``), and the register joins them:

- per phase (the specification's public reports: DRE file, building, units): the security agreements by type
  (assessment 2792.9, subsidy 2792.10, completion 2792.4 / B&P 11018.5), the subsidy agreement, and the bonds;
- per bond: its surety, penal sum, form, and the release evidence (an escrow holder's release request, the association's
  letter, or a board resolution naming the bond number); a bond with none is open on the record.

A bond open on the record may have been released without a copy reaching Drive; the escrow holder can say. Nothing here
calls a service or changes a record.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from jason.community.document_models import ModelContext, read, to_plain
from jason.community.symbols import DocumentKind

FOLDER = Path("developer-security")
_BOND_NUMBER = re.compile(r"\b(10\d{5}|100\d{7}|20\d{5})\b")


@dataclass
class BondEntry:
    number: str
    phase: int | None = None
    security_type: str = ""
    form: str = ""
    surety: str = ""
    penal_sum_cents: int | None = None
    signed_on: str = ""
    sources: list[str] = field(default_factory=list)
    releases: list[dict[str, Any]] = field(default_factory=list)
    phase_inferred: bool = False   # the phase whose agreement states the bond's sum, not one the bond prints
    readings: list[dict[str, Any]] = field(default_factory=list)   # every copy's reading, to show where copies disagree


def _instruments(data_dir: Path, community: Any) -> list[tuple[str, DocumentKind, str]]:
    """(source name, kind, text) for every instrument on disk: each saved file, and each piece of a compiled production."""
    from jason.community.models.developer_security import split_instruments

    root = Path(data_dir) / FOLDER
    index = json.loads((root / "index.json").read_text(encoding="utf-8")) if (root / "index.json").is_file() else []
    seen: set[str] = set()
    found = []
    for entry in index:
        text_path = (root / entry["file"]).with_suffix(".txt")
        if not text_path.is_file():
            continue
        text = text_path.read_text(encoding="utf-8")
        key = re.sub(r"\s+", " ", text[:4000])
        if key in seen:  # the same PDF saved twice in Drive
            continue
        seen.add(key)
        kind = community.classify_document(entry["name"], None, "")
        pieces = split_instruments(text, community) if kind is None or len(text) > 60000 else []
        if len(pieces) > 1:
            found.extend((f"{entry['name']} #{n + 1}", k, body) for n, (k, body) in enumerate(pieces))
        elif kind is not None:
            found.append((entry["name"], kind, text))
    try:
        from jason.tasks.library import load, text_for

        for row in load(Path(data_dir)):
            if row.get("kind") in ("security_agreement", "subsidy_agreement", "surety_bond", "bond_release"):
                found.append((row["name"], DocumentKind(row["kind"]), text_for(Path(data_dir), row["id"])))
    except Exception:  # the library is optional here
        pass
    return found


def register(data_dir: Path, community: Any, *, today: date | None = None) -> dict[str, Any]:
    day = today or date.today()
    instruments = _instruments(Path(data_dir), community)
    if not instruments:
        return {"found": False, "note": "no developer-security documents on disk; save them from Drive into data/developer-security"}
    reports = {r.phase: r for r in community.public_reports()}
    by_file = {r.file_number: r.phase for r in reports.values()}
    phases: dict[int, dict[str, Any]] = {p: {"phase": p, "dreFile": r.file_number, "building": getattr(r.building, "value", str(r.building)),
                                            "units": r.units, "assessmentCents": r.assessment_cents, "agreements": [],
                                            "subsidyAgreements": [], "bonds": []} for p, r in sorted(reports.items())}
    bonds: dict[str, BondEntry] = {}
    releases, readings, misses = [], [], []
    resolutions = []
    for source, kind, text in instruments:
        context = ModelContext(community, Path(data_dir), day, source)
        if kind is DocumentKind.RESOLUTION or re.search(r"SPECIAL RESOLUTION", text[:400], re.I):
            resolutions.append((source, text))
            continue
        reading = read(kind, text, context)
        if reading is None:
            misses.append({"source": source, "kind": kind.value})
            continue
        fields = to_plain(reading.record)
        row = {"source": source, "kind": kind.value, "model": reading.model, "complete": reading.complete, "missing": list(reading.missing),
               "findings": [f.as_dict() for f in reading.findings if f.severity.value != "info"], "fields": fields}
        readings.append(row)
        if kind is DocumentKind.SURETY_BOND and fields.get("bond_number"):
            entry = bonds.setdefault(fields["bond_number"], BondEntry(fields["bond_number"]))
            entry.phase = entry.phase or fields.get("phase")
            entry.security_type = entry.security_type or (fields.get("security_type") or "")
            entry.form = entry.form or fields.get("form") or ""
            entry.surety = entry.surety or re.sub(r"\s+", " ", fields.get("surety") or "")[:60]
            entry.penal_sum_cents = entry.penal_sum_cents or fields.get("penal_sum_cents")
            entry.signed_on = entry.signed_on or (fields.get("signed_on") or "")
            entry.sources.append(source)
            entry.readings.append({"phase": fields.get("phase"), "type": fields.get("security_type"), "form": fields.get("form"),
                                   "penalSumCents": fields.get("penal_sum_cents"), "signedOn": fields.get("signed_on"), "source": source})
        elif kind is DocumentKind.SECURITY_AGREEMENT:
            phase = fields.get("phase") or by_file.get(fields.get("dre_file") or "")
            if phase in phases:
                phases[phase]["agreements"].append({"type": fields.get("security_type"), "form": fields.get("form"), "madeOn": fields.get("made_on"),
                                                    "escrowAccount": fields.get("escrow_account"), "units": fields.get("units"),
                                                    "commonAreas": fields.get("common_areas"), "bondCents": fields.get("bond_amount_cents"),
                                                    "source": source})
        elif kind is DocumentKind.SUBSIDY_AGREEMENT:
            for phase in fields.get("phases") or ([fields["phase"]] if fields.get("phase") else []):
                if phase in phases:
                    phases[phase]["subsidyAgreements"].append({"targetAssessmentCents": fields.get("target_assessment_cents"),
                                                               "gapCents": fields.get("gap_cents"), "termEnd": fields.get("term_end"),
                                                               "source": source})
        elif kind is DocumentKind.BOND_RELEASE:
            releases.append((source, fields))
    for source, fields in releases:
        for bond in fields.get("bonds") or []:
            entry = bonds.setdefault(bond["number"], BondEntry(bond["number"], bond.get("phase")))
            entry.phase = entry.phase or bond.get("phase")
            entry.penal_sum_cents = entry.penal_sum_cents or bond.get("amount_cents")
            entry.releases.append({"dated": fields.get("dated"), "by": fields.get("sender"), "grounds": fields.get("grounds"), "source": source})
    for source, text in resolutions:
        for number in dict.fromkeys(_BOND_NUMBER.findall(text)):
            if number in bonds and re.search(r"release", text, re.I):
                bonds[number].releases.append({"dated": None, "by": "board resolution", "grounds": [], "source": source})
    stated = {}
    for p in phases.values():
        for a in p["agreements"]:
            if a.get("bondCents"):
                stated.setdefault(a["bondCents"], set()).add(p["phase"])
    for entry in bonds.values():
        if entry.phase is None and entry.penal_sum_cents and len(stated.get(entry.penal_sum_cents, ())) == 1:
            entry.phase, entry.phase_inferred = next(iter(stated[entry.penal_sum_cents])), True
    for entry in bonds.values():
        if entry.phase in phases:
            phases[entry.phase]["bonds"].append(entry.number)
    rows = []
    for entry in sorted(bonds.values(), key=lambda b: (b.phase or 99, b.number)):
        status = "released" if entry.releases else "no release on file"
        disagree = [name for name, key in (("sum", "penalSumCents"), ("phase", "phase"), ("type", "type"), ("signed", "signedOn"))
                    if len({r[key] for r in entry.readings if r[key] not in (None, "")}) > 1]
        rows.append({"number": entry.number, "phase": entry.phase, "phaseInferred": entry.phase_inferred, "type": entry.security_type, "form": entry.form, "surety": entry.surety,
                     "penalSumCents": entry.penal_sum_cents, "signedOn": entry.signed_on, "status": status, "releases": entry.releases,
                     "copiesDisagree": disagree, "readings": entry.readings,
                     "sources": entry.sources})
    gaps = []
    for p in phases.values():
        types = {a["type"] for a in p["agreements"]}
        if "assessment" not in types:
            gaps.append(f"phase {p['phase']} ({p['dreFile']}): no assessment security agreement (10 CCR 2792.9) on file")
        if p["subsidyAgreements"] and "subsidy" not in types and not any(b["type"] == "subsidy" and b["phase"] == p["phase"] for b in rows):
            gaps.append(f"phase {p['phase']}: a subsidy agreement but no subsidy security (RE 643E or RE 643K bond) on file (10 CCR 2792.10)")
        if not p["bonds"]:
            gaps.append(f"phase {p['phase']}: no bond on file")
    return {
        "found": True, "phases": list(phases.values()), "bonds": rows, "gaps": gaps, "readings": readings, "unread": misses,
        "openBonds": [r["number"] for r in rows if r["status"] != "released"],
        "caveats": [
            "A bond with no release on file may have been released without a copy reaching Drive; the escrow holder can confirm.",
            "A phase marked * is inferred: that phase's security agreement states the bond's exact sum.",
            "Phases 1 and 2 (WL Homes, 2007-08) were secured before the current forms; their bonds' releases are letters to First American Title.",
            "Read from OCR of scanned forms: numbers and amounts are the scans' as read; the originals are the record.",
        ],
    }


def dollars(cents: int | None) -> str:
    return "-" if cents is None else f"${cents / 100:,.2f}"


def register_lines(result: dict[str, Any]) -> list[str]:
    if not result.get("found"):
        return [result.get("note", "nothing on disk")]
    out = ["Developer securities by phase", ""]
    for p in result["phases"]:
        agreements = ", ".join(f"{a['type']} ({a['form'] or '?'})" for a in p["agreements"]) or "none on file"
        subsidy = "; subsidy agreement" if p["subsidyAgreements"] else ""
        out.append(f"Phase {p['phase']}  DRE {p['dreFile']}  building {p['building']}  {p['units']} units: agreements: {agreements}{subsidy}; "
                   f"bonds: {', '.join(p['bonds']) or 'none on file'}")
    out.append("")
    out.append("Bonds")
    for b in result["bonds"]:
        released = "; ".join(f"{r['dated'] or '?'} by {r['by']}" for r in b["releases"]) or "-"
        out.append(f"  {b['number']:<11} phase {(str(b['phase']) + ('*' if b['phaseInferred'] else '')) if b['phase'] else '?'}  {b['type'] or '?':<10} {b['form'] or '?':<8} {dollars(b['penalSumCents']):>11}  "
                   f"{b['surety'][:30]:<30} {b['status']}  (released: {released})")
        if b["copiesDisagree"]:
            values = "; ".join(f"{r['source'][-6:]}: {dollars(r['penalSumCents'])} phase {r['phase'] or '?'} {r['type'] or '?'}" for r in b["readings"])
            out.append(f"      ! copies read differently ({', '.join(b['copiesDisagree'])}): {values}")
    if result["gaps"]:
        out.append("")
        out.append("Gaps")
        out.extend(f"  ! {g}" for g in result["gaps"])
    out.append("")
    out.extend(f"* {c}" for c in result["caveats"])
    return out


__all__ = ["register", "register_lines"]
