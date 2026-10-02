"""Every cached index document read against the known processes, and what is left.

A document is explained when a process holds it: a chain step or an
instrument beside one, the land chain, a lien lifecycle, an owner event,
a governing record, the association's own filings, a solar lease notice.
What is left over is sorted by the party it names and the pattern it fits:
a re-recording of a chain step, a companion transfer at a closing, an
owner's other property, the developer's other projects, the developer's
insolvency, or nothing yet. The last group is the list to model next. A
document naming no community party at all is noise a wide-name search
swept in, and is counted, not sorted.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any

from jason.community.filings import Family, instrument_class, same_party
from jason.community.index_cache import skip_lender
from jason.community.processes import COMPANION, RERECORDING, SAME_DAY_TWIN, beside_step
from jason.community.recorder import FiledInstrument, developer_for

INSOLVENCY_CODES = ("385", "223", "651", "291", "576")
SOLAR_WORDS = ("SOLAR", "SUNNOVA", "SUNRUN", "SUNSTREET", "SUNPOWER", "TESLA", "SOLARCITY", "ULTRALIGHT", "DORADO", "SUNRISE")


class Bucket(Enum):
    CHAIN = "chain step"
    RELATED = "instrument beside a chain step"
    LAND_CHAIN = "land chain"
    LIEN = "lien lifecycle"
    OWNER_EVENT = "owner event"
    GOVERNING = "governing record"
    ASSOCIATION = "the association's own filing"
    CANDIDATE = "candidate placed on a parcel"
    SOLAR_NOTICE = "solar lease notice"
    RERECORDING = "re-recording of a chain step"
    SAME_DAY_TWIN = "same-day deed with a chain step's parties"
    COMPANION = "companion transfer at a closing"
    OWNER_OTHER = "an owner's other property"
    DEVELOPER_OTHER = "the developer's other project"
    DEVELOPER_INSOLVENCY = "the developer's insolvency"
    UNRESOLVED = "no process yet"
    NOISE = "names no community party"


@dataclass(frozen=True)
class Placement:
    bucket: Bucket
    why: str
    apn: str = ""


@dataclass
class Coverage:
    total: int = 0
    placed: dict[str, Placement] = field(default_factory=dict)
    examples: dict[Bucket, list[dict[str, Any]]] = field(default_factory=dict)

    @property
    def counts(self) -> dict[str, int]:
        found = Counter(p.bucket.value for p in self.placed.values())
        return dict(sorted(found.items(), key=lambda kv: -kv[1]))

    def as_dict(self) -> dict[str, Any]:
        return {
            "documents": self.total,
            "counts": self.counts,
            "examples": {bucket.value: rows for bucket, rows in self.examples.items()},
        }


def coverage(
    histories: tuple,
    record,
    docs: tuple[FiledInstrument, ...] | list[FiledInstrument],
    *,
    developers: tuple,
    association: str,
    project: str,
    land_chain: tuple[str, ...] = (),
    examples: int = 4,
) -> Coverage:
    result = Coverage(total=len(docs))
    placed = result.placed

    def mark(number: str, bucket: Bucket, why: str, apn: str = "") -> None:
        if number and number not in placed:
            placed[number] = Placement(bucket, why, apn)

    assn = association.upper()
    project_word = project.upper()
    owners: dict[str, list[tuple[str, date | None, date | None]]] = {}
    chain_steps: list[tuple[str, FiledInstrument | None, Any]] = []
    for item in histories:
        steps = item.steps
        for index, step in enumerate(steps):
            mark(step.number, Bucket.CHAIN, step.process or "deed", item.apn)
            for rel in step.related:
                mark(rel.number, Bucket.RELATED, rel.role, item.apn)
            if not item.association:
                until = steps[index + 1].recorded if index + 1 < len(steps) else None
                for name in step.grantees:
                    if name.strip() and not skip_lender(name) and not developer_for(name, developers) and assn not in name.upper():
                        owners.setdefault(name, []).append((item.apn, step.recorded, until))
                chain_steps.append((item.apn, None, step))
        for lien in item.liens:
            for s in lien.encumbrance.steps:
                mark(s.number, Bucket.LIEN, f"{lien.encumbrance.process.value} ({lien.where})", item.apn)
        for event in item.owner_events:
            mark(event.number, Bucket.OWNER_EVENT, event.kind, item.apn)
        for c in item.candidates:
            mark(c.number, Bucket.CANDIDATE, "placed by a pass", item.apn)
        if item.solar is not None:
            for notice in getattr(item.solar, "notices", ()):
                mark(notice.number, Bucket.SOLAR_NOTICE, "notice of a solar contract", item.apn)
    for number in land_chain:
        mark(number, Bucket.LAND_CHAIN, "the community deeds back through the land")
    if record is not None:
        for g in (*record.governing, *record.unplaced):
            mark(g.number, Bucket.GOVERNING, g.role)
        for label, items in (("placed by the association", record.placed), ("against the association", record.against), ("construction claim", record.construction)):
            for e in items:
                for s in e.steps:
                    mark(s.number, Bucket.ASSOCIATION, label)
        for n in record.notices:
            mark(n.number, Bucket.ASSOCIATION, "notice")

    by_number = {d.number: d for d in docs}
    step_docs = [(apn, by_number.get(step.number), step) for apn, _, step in chain_steps]

    for d in docs:
        if d.number in placed:
            continue
        klass = instrument_class(d.filing_code, d.filing_name, d.kind)
        parties = (*d.grantors, *d.grantees)
        dev = any(developer_for(name, developers) for name in parties)
        ours = any(assn in name.upper() or name.upper().startswith(project_word + " ") for name in parties)
        owner_hits = [(name, span) for name in parties for owner, spans in owners.items() if same_party(name, owner) for span in spans]
        if not dev and not ours and not owner_hits:
            mark(d.number, Bucket.NOISE, klass.name or d.kind)
            continue
        during = [(name, apn) for name, (apn, start, until) in owner_hits if d.recorded and start and d.recorded >= start and (until is None or d.recorded <= until)]
        # A re-recording or a companion of a chain step, by citation, same parties, or a family transfer within days.
        twin = _twin_of(d, step_docs)
        if twin is not None:
            mark(d.number, twin[0], twin[1], twin[2])
            continue
        if klass.code in INSOLVENCY_CODES and dev or (klass.code == "542" and dev):
            mark(d.number, Bucket.DEVELOPER_INSOLVENCY, f"{klass.code} {klass.name}".strip())
            continue
        if klass.code == "549" and any(any(word in name.upper() for word in SOLAR_WORDS) for name in d.grantees):
            mark(d.number, Bucket.SOLAR_NOTICE if during else Bucket.OWNER_OTHER, "notice of a solar contract" + ("" if during else ", another property"), during[0][1] if during else "")
            continue
        if dev and not during and not ours:
            mark(d.number, Bucket.DEVELOPER_OTHER, f"{klass.code} {klass.name}".strip() or d.kind)
            continue
        if owner_hits and not during:
            mark(d.number, Bucket.OWNER_OTHER, f"{klass.code} {klass.name}".strip() + ", outside tenure")
            continue
        if during and klass.family in (Family.CONVEYANCE, Family.NOTICE, Family.LOAN, Family.RELEASE, Family.OTHER, Family.DEFAULT, Family.SALE, Family.AUTHORITY):
            mark(d.number, Bucket.OWNER_OTHER, f"{klass.code} {klass.name}".strip() + ", during tenure", during[0][1])
            continue
        why = f"{klass.code} {klass.name}".strip() or d.kind
        if during:
            why += f", names an owner during tenure but no parcel process holds it"
        mark(d.number, Bucket.UNRESOLVED, why, during[0][1] if during else "")

    for d in docs:
        p = placed.get(d.number)
        if p is None or p.bucket in (Bucket.CHAIN, Bucket.LIEN, Bucket.NOISE, Bucket.RELATED):
            continue
        rows = result.examples.setdefault(p.bucket, [])
        if len(rows) < examples:
            rows.append({"number": d.number, "recorded": d.recorded.isoformat() if d.recorded else "", "filing": f"{d.filing_code} {d.filing_name}".strip() or d.kind,
                         "from": list(d.grantors)[:3], "to": list(d.grantees)[:3], "why": p.why, "apn": p.apn})
    return result


def _twin_of(d: FiledInstrument, step_docs) -> tuple[Bucket, str, str] | None:
    """A re-recording of a chain step, or a companion transfer at its closing, by ``processes.beside_step``."""
    for apn, step_doc, step in step_docs:
        found = beside_step(d, step.number, step_doc, step.grantees)
        if found is not None:
            role, why = found
            bucket = {RERECORDING: Bucket.RERECORDING, COMPANION: Bucket.COMPANION, SAME_DAY_TWIN: Bucket.SAME_DAY_TWIN}[role]
            return bucket, why, apn
    return None


# The buckets a known process holds, then the patterns beside them, then what is left.
EXPLAINED = (
    Bucket.CHAIN, Bucket.RELATED, Bucket.LAND_CHAIN, Bucket.LIEN, Bucket.OWNER_EVENT, Bucket.GOVERNING,
    Bucket.ASSOCIATION, Bucket.CANDIDATE, Bucket.SOLAR_NOTICE,
)
PATTERNS = (
    Bucket.RERECORDING, Bucket.SAME_DAY_TWIN, Bucket.COMPANION, Bucket.OWNER_OTHER, Bucket.DEVELOPER_OTHER, Bucket.DEVELOPER_INSOLVENCY,
)


def coverage_markdown(result: dict, *, title: str, today=None) -> str:
    """The coverage page from ``Coverage.as_dict()``: what each process explains, the patterns, and what is left to model."""
    counts: dict[str, int] = result.get("counts") or {}
    examples: dict[str, list] = result.get("examples") or {}
    total = int(result.get("documents") or 0)
    lines = [f"# {title}", ""]
    lines.append(
        "Every document in the cached recorder index, read against the processes Jason models. A document is explained when a "
        "process holds it; the rest is sorted by the pattern it fits, and \"no process yet\" is the list to model next. "
        "A document naming no community party is noise a wide-name search swept in."
        + (f" Read {today.isoformat()}." if today else "")
    )
    lines.append("")
    for heading, group in (("Explained by a process", EXPLAINED), ("Beside the processes", PATTERNS), ("Left over", (Bucket.UNRESOLVED, Bucket.NOISE))):
        lines.append(f"## {heading}")
        lines.append("")
        lines.append("| Bucket | Documents | Share |")
        lines.append("| --- | ---: | ---: |")
        for bucket in group:
            count = counts.get(bucket.value, 0)
            if count:
                lines.append(f"| {bucket.value} | {count} | {count / total:.1%} |" if total else f"| {bucket.value} | {count} | |")
        lines.append("")
        for bucket in group:
            rows = examples.get(bucket.value) or []
            if not rows or bucket in (Bucket.CHAIN, Bucket.LIEN):
                continue
            lines.append(f"**{bucket.value}**")
            lines.append("")
            for row in rows:
                grantors, grantees = "; ".join(row.get("from") or []), "; ".join(row.get("to") or [])
                parties = f"{grantors} to {grantees}" if grantors and grantees else (grantors or grantees)
                where = f" ({row['apn']})" if row.get("apn") else ""
                lines.append(f"- {row['number']}, {row['recorded']}, {row['filing']}: {parties}{where}. {row['why']}")
            lines.append("")
    return "\n".join(lines)
