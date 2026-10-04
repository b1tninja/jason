"""Insurance policies (declarations pages) and evidence of insurance (ACORD certificates).

The law shapes what the association does with these. The annual budget report summarizes the property, general
liability, earthquake, flood, and fidelity policies: for each the insurer, the type, the limit, and the deductible, and
a copy of the declarations page may stand in for the summary (CIV 5300(b)(9)). Members get individual notice when one of
those policies lapses, is canceled and not replaced, or changes significantly, such as a lower limit or a higher
deductible (CIV 5810). A volunteer director's immunity needs general liability and D&O coverage of at least $500,000
for 100 or fewer separate interests (CIV 5800(a)(4)); owners' tenant-in-common tort protection needs general liability
of at least $2,000,000 for 100 or fewer (CIV 5805(b)); crime or fidelity coverage must at least equal the reserves plus
three months' assessments, cover computer and funds transfer fraud, and cover a managing agent (CIV 5806).

Layouts recognized:

- ``nfip-flood-declarations``: the NFIP Residential Condominium Building Association Policy declarations Philadelphia
  Indemnity issues through manageflood (new, renewal, and revised declarations). The page's text comes out with the
  labels and values apart; the reader keys on the values' shapes. The page prints the RCBAP's co-insurance test: at a
  loss the building must be insured to the lesser of 80% of its replacement cost or the maximum available, which is
  $250,000 a unit (44 CFR 61.6).
- ``policy-declarations``: any other declarations page that prints "Policy Number", "Policy Period", and "Named
  Insured" labels with their values.
- ``acord-certificate``: ACORD 25 (liability), 24 (property), 27 and 28 (evidence of property) certificates, with the
  ACORD 101 additional remarks. The reader drops the form's printed labels and reads the values in order.

The policy sheet is the specification (``Mystique.insurance().policies``); a reading's number and dates are checked
against it and against the other policy files in the library, never pinned by it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Any

from jason.community.document_models import (
    DocumentModel,
    Finding,
    ModelContext,
    Severity,
    cents,
    dates_in,
    first,
    register,
    squash,
)
from jason.community.invoices import parse_date
from jason.community.reviews import AS_OF
from jason.community.symbols import Building, DocumentKind, PolicyKind

SOON_DAYS = 60


class Coverage(Enum):
    """A line of coverage as a policy or certificate names it."""

    PROPERTY = "property"
    GENERAL_LIABILITY = "general_liability"
    AUTO = "auto"
    UMBRELLA = "umbrella"
    WORKERS_COMP = "workers_comp"
    CRIME = "crime"
    DIRECTORS_AND_OFFICERS = "directors_and_officers"
    FLOOD = "flood"
    EARTHQUAKE = "earthquake"
    OTHER = "other"


# The policy sheet's line each coverage belongs to. The master policy carries property, general liability, and auto.
POLICY_KIND = {
    Coverage.PROPERTY: PolicyKind.MASTER,
    Coverage.GENERAL_LIABILITY: PolicyKind.MASTER,
    Coverage.AUTO: PolicyKind.MASTER,
    Coverage.UMBRELLA: PolicyKind.UMBRELLA,
    Coverage.WORKERS_COMP: PolicyKind.WORKERS_COMP,
    Coverage.CRIME: PolicyKind.FIDELITY,
    Coverage.DIRECTORS_AND_OFFICERS: PolicyKind.DIRECTORS_AND_OFFICERS,
    Coverage.FLOOD: PolicyKind.FLOOD,
}
# The lines CIV 5300(b)(9) asks the annual budget report to summarize.
SUMMARY_LINES = (Coverage.PROPERTY, Coverage.GENERAL_LIABILITY, Coverage.EARTHQUAKE, Coverage.FLOOD, Coverage.CRIME)

# A coverage named in words, first match wins.
COVERAGE_WORDS: tuple[tuple[str, Coverage], ...] = (
    (r"director|D\s*&\s*O\b", Coverage.DIRECTORS_AND_OFFICERS),
    (r"crime|fidelity|dishonesty|bond", Coverage.CRIME),
    (r"flood", Coverage.FLOOD),
    (r"earthquake|\bDIC\b", Coverage.EARTHQUAKE),
    (r"umbrella|excess", Coverage.UMBRELLA),
    (r"workers", Coverage.WORKERS_COMP),
    (r"general liab|\bCGL\b", Coverage.GENERAL_LIABILITY),
    (r"auto", Coverage.AUTO),
    (r"property|building|special form", Coverage.PROPERTY),
)


def coverage_of(words: str) -> Coverage | None:
    for pattern, coverage in COVERAGE_WORDS:
        if re.search(pattern, words or "", re.I):
            return coverage
    return None


class Declaration(Enum):
    NEW = "new"
    RENEWAL = "renewal"
    REVISED = "revised"


@dataclass(frozen=True)
class Charge:
    name: str
    amount: int  # cents


@dataclass
class InsurancePolicy:
    carrier: str = ""
    naic: str = ""
    policy_number: str = ""
    coverage: Coverage | None = None
    program: str = ""                 # "National Flood Insurance Program"
    form: str = ""                    # "RCBAP"
    declaration: Declaration | None = None
    named_insured: str = ""
    property_location: str = ""
    building: Building | None = None
    term_start: date | None = None
    term_end: date | None = None
    endorsement_effective: date | None = None
    limit: int | None = None          # cents; the building coverage for a flood policy
    contents_limit: int | None = None
    deductible: int | None = None
    replacement_cost: int | None = None
    units: int | None = None
    flood_zone: str = ""
    premium: int | None = None        # the total the term costs
    charges: tuple[Charge, ...] = ()  # the parts of the premium the page itemizes
    producer: str = ""                # the agency
    agent: str = ""
    printed: date | None = None
    mailing_address: str = ""         # where the insurer sends the named insured's notices (CIV 5810)


def mailing_findings(address: str, context: ModelContext, what: str) -> list[Finding]:
    """A policy that mails its notices somewhere other than the association's current mailing address (the spec's
    ``mail_addresses``), which renewal, cancellation, and claim notices then miss."""
    try:
        rows = context.community.mail_addresses() if context.community is not None else ()
    except Exception:
        rows = ()
    current = [a for a in rows if getattr(a.kind, "name", "") == "CURRENT"]
    if not address or not current:
        return []
    squashed = _squash(address)
    row = current[0]
    boxes = list(getattr(row, "requires", ()) or [w for w in row.words if re.match(r"PMB|SUITE|STE|#", w, re.I)])
    streets = [w for w in row.words if w not in boxes and not re.match(r"PMB", w, re.I)]
    zips = re.findall(r"\b(\d{5})(?:-\d{4})?\b", address)
    if not any(_squash(w) in squashed for w in streets):
        problem = "not its current address"
    elif boxes and not any(_squash(w) in squashed for w in boxes):
        problem = f"the current street without its box ({boxes[0]})"
    elif getattr(row, "zip", "") and zips and zips[-1] != row.zip:
        problem = f"the current street and box with ZIP {zips[-1]}, not {row.zip}"
    else:
        return []
    return [Finding("mailing-address-not-current", f"{what} mails the association at {address}, {problem}: renewal, cancellation, "
                    "and claim notices go there. Ask the agent to change it", Severity.PROBLEM, "CIV 5810")]


def _squash(s: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())


def mailing_address(text: str, known: tuple[str, ...] = ()) -> str:
    """The named insured's mailing address on a declarations page whose labels print apart from their values. The page
    also prints the insurer's, the agency's, and the property's addresses, so only a street line (with its city and ZIP)
    that carries one of the association's own addresses, current or former (``known``, spaces ignored), is taken."""
    marks = [_squash(w) for w in known if len(_squash(w)) >= 4]
    # A box line ("PMB 188") may sit between the street and the city.
    for street, box, city in re.findall(r"\n\s*(\d[^\n]{3,48})\n(?:\s*((?:PMB|STE|SUITE|#)[^\n]{1,20})\n)?\s*"
                                        r"([A-Z][A-Za-z .]+,\s*CA,?\s+\d{5}(?:-\d{4})?)", text or ""):
        if any(m in _squash(street) for m in marks):
            return ", ".join(p.strip() for p in (street, box, city) if p.strip())
    return ""


def association_mail_words(context: ModelContext) -> tuple[str, ...]:
    """The words of every mailing address the association has used (current and former managers'), not the property's."""
    try:
        rows = context.community.mail_addresses() if context.community is not None else ()
    except Exception:
        return ()
    return tuple(w for a in rows if getattr(a.kind, "name", "") != "PROPERTY" for w in a.words)


# NFIP declarations -----------------------------------------------------------------------------------------------

_NFIP = re.compile(r"NATIONAL FLOOD INSURANCE PROGRAM|NFIP Policy Number", re.I)
_TERM_DATE = re.compile(r"(\d{1,2}/\d{1,2}/\d{4}) 12:01 AM")
_WHOLE = re.compile(r"^\$([\d,]+)$", re.M)
_WITH_CENTS = re.compile(r"^\(?\$([\d,]+\.\d\d)\)?$", re.M)
_ADDRESS = re.compile(r"\b(\d{3,5})(?:-\d{3,5})?\s+([A-Z][A-Za-z]+(?: [A-Z][A-Za-z]+)*?)\s+(DR|DRIVE|WALK|LN|LANE|WAY|ST|STREET|AVE|AVENUE|CT|CIR)\b\.?"
                      r"(?:\s+BLDG\s*(\d))?", re.I)
_SUFFIX = {"DRIVE": "DR", "LANE": "LN", "STREET": "ST", "AVENUE": "AVE"}


def _amount_line_after(label: str, text: str, pattern: re.Pattern = _WITH_CENTS, window: int = 200) -> int | None:
    m = re.search(label, text, re.I)
    if not m:
        return None
    hit = pattern.search(text[m.end(): m.end() + window])
    return cents(hit.group(0)) if hit else None


def _whole_after(label: str, text: str, low: int, high: int, window: int = 400) -> int | None:
    """The first whole-dollar amount ("$2,000", no cents) after ``label`` within [low, high] dollars, as cents."""
    m = re.search(label, text, re.I)
    if not m:
        return None
    for hit in _WHOLE.finditer(text[m.end(): m.end() + window]):
        value = int(hit.group(1).replace(",", ""))
        if low <= value <= high:
            return value * 100
    return None


def _contents_after_building(text: str, building: int | None) -> int | None:
    """The contents coverage, which the page prints on the line after the building coverage: "N/A" or "$0" is none (0),
    as on a condominium building policy that insures no association contents."""
    if not building:
        return None
    m = re.search(r"\nCOVERAGE\s*\n", text)
    if not m:
        return None
    amount = f"${building // 100:,}"
    hit = re.search(r"^" + re.escape(amount) + r"\s*\n\s*([^\n]+)", text[m.end(): m.end() + 400], re.M)
    if not hit:
        return None
    value = hit.group(1).strip()
    if re.fullmatch(r"N/A|\$0(?:\.00)?", value):
        return 0
    whole = re.fullmatch(r"\$([\d,]+)", value)
    dollars = int(whole.group(1).replace(",", "")) if whole else 0
    return dollars * 100 if dollars >= 10_000 else None   # a smaller amount there is the deductible, not a limit


def building_at(text: str, context: ModelContext) -> tuple[Building | None, str]:
    """The flood building an address in the text falls in (the specification's street ranges), and that address."""
    from jason.community.base import assign_building

    ranges = ()
    community = context.community
    if community is not None and hasattr(community, "buildings"):
        try:
            ranges = tuple(community.buildings())
        except Exception:  # a partial specification in a test
            ranges = ()
    for m in _ADDRESS.finditer(text or ""):
        printed = m.group(4)
        street = f"{m.group(2).upper()} {_SUFFIX.get(m.group(3).upper(), m.group(3).upper())}"
        if printed and printed.isdigit():
            try:
                return Building(int(printed)), squash(m.group(0))
            except ValueError:
                pass
        hit = assign_building(f"{m.group(1)} {street}", ranges) if ranges else None
        if hit is not None:
            return hit.number, squash(m.group(0))
    return None, ""


def _nfip(text: str, context: ModelContext) -> InsurancePolicy | None:
    if not _NFIP.search(text or "") or not re.search(r"FLOOD INSURANCE POLICY DECLARATIONS", text, re.I):
        return None
    r = InsurancePolicy(coverage=Coverage.FLOOD, program="National Flood Insurance Program")
    r.policy_number = first(r"NFIP Policy Number:\s*(\d{8,})", text) or first(r"Company Policy Number:\s*(\d{8,})", text)
    r.carrier = first(r"^([A-Z][A-Z &.,]+(?:INDEMNITY|INSURANCE|ASSURANCE|CASUALTY) COMPANY)\s*$", text, flags=re.M)
    naic = re.search(r"NAIC[^\n]*\n", text)
    hit = re.search(r"^(\d{5})$", text[naic.end():], re.M) if naic else None
    r.naic = hit.group(1) if hit else ""
    r.form = "RCBAP" if re.search(r"\bRCBAP\b|Residential Condominium Building Association Policy", text, re.I) else \
        first(r"Policy Form:\s*([A-Z]+)", text)
    kind = first(r"(NEW|RENEWAL|REVISED) FLOOD INSURANCE POLICY DECLARATIONS", text)
    r.declaration = Declaration(kind.lower()) if kind else None
    r.named_insured = first(r"\n([^\n]+)\n\s*INSURED NAME\(S\)", text) or first(r"\n([^\n]+)\n\s*Insured\(s\):", text)
    term = re.search(r"Policy Term:", text)
    days = [parse_date(d) for d in _TERM_DATE.findall(text[term.end(): term.end() + 700])] if term else []
    days = [d for d in days if d]
    if len(days) >= 2:
        r.term_start, r.term_end = days[0], days[1]
    r.endorsement_effective = (dates_in(first(r"\n([^\n]*)\n\s*Endorsement Effective Date:", text)) or [None])[0]
    r.building, r.property_location = building_at(text, context)
    r.limit = _whole_after(r"\nCOVERAGE\s*\n", text, 10_000, 100_000_000)
    r.contents_limit = _contents_after_building(text, r.limit)
    r.deductible = _whole_after(r"\nDEDUCTIBLE\s*\n", text, 500, 100_000)
    r.replacement_cost = _amount_line_after(r"REPLACEMENT COST VALUE:", text)
    units = first(r"NUMBER OF UNITS:\s*(\d+)\s*UNITS?", text)
    r.units = int(units) if units else None
    r.flood_zone = first(r"CURRENT FLOOD ZONE:\s*\n\s*([A-Z]{1,2} ?\d{0,2})\s*\n", text)
    r.agent = first(r"Agency Phone:\s*\n\s*([A-Z][A-Z .'-]+)\n", text)
    r.producer = first(r"\n([A-Z][A-Z/&.,' ]*AGENCY[A-Z,. ]*)\n", text)
    r.printed = (dates_in(first(r"\n([^\n]*)\n\s*Printed\b", text)) or [None])[0]
    r.mailing_address = mailing_address(text, association_mail_words(context))
    # The page prints the labels apart from their values; each value sits in a fixed place relative to a label.
    r.premium = _amount_line_after(r"ANNUAL SUBTOTAL:", text) or _amount_line_after(r"FEDERAL POLICY (?:SERVICE )?FEE:", text)
    parts = [("discounted premium", _amount_line_after(r"DISCOUNTED PREMIUM:", text)),
             ("reserve fund assessment", _amount_line_after(r"PROBATION SURCHARGE:", text)),
             ("federal policy fee", None),
             ("HFIAA surcharge", _amount_line_after(r"HFIAA SURCHARGE:", text))]
    discounted = re.search(r"DISCOUNTED PREMIUM:\s*\n\s*\(?\$[\d,]+\.\d\d\)?\s*\n\s*(\(?\$[\d,]+\.\d\d\)?)", text)
    if discounted:
        parts[2] = ("federal policy fee", cents(discounted.group(1)))
    r.charges = tuple(Charge(name, amount) for name, amount in parts if amount is not None)
    return r


# Other declarations pages --------------------------------------------------------------------------------------------

def _declarations(text: str, context: ModelContext) -> InsurancePolicy | None:
    if not re.search(r"declarations", text or "", re.I) or not re.search(r"Policy (?:Number|No\.?)", text, re.I) \
            or not re.search(r"Named Insured", text, re.I):
        return None
    r = InsurancePolicy()
    r.policy_number = first(r"Policy (?:Number|No\.?)\s*:?\s*([A-Z0-9][A-Z0-9-]{5,})", text)
    r.named_insured = first(r"Named Insured\s*:?\s*\n?\s*([^\n]+)", text)
    r.carrier = first(r"^([A-Z][A-Za-z &.,]+(?:Insurance|Indemnity|Assurance|Casualty|Surety)(?: Company| Exchange)?)\s*$", text, flags=re.M)
    period = re.search(r"Policy (?:Period|Term)\s*:?", text, re.I)
    days = dates_in(text[period.end(): period.end() + 200]) if period else []
    if len(days) >= 2:
        r.term_start, r.term_end = days[0], days[1]
    r.coverage = coverage_of(first(r"([^\n]*(?:Coverage Part|Policy)[^\n]*Declarations[^\n]*)", text) or text[:600])
    r.limit = cents(first(r"(?:Limit of (?:Insurance|Liability)|Each Occurrence|Policy Limit)\s*:?\s*(\$?[\d,]+)", text)) \
        if re.search(r"Limit of (?:Insurance|Liability)|Each Occurrence|Policy Limit", text, re.I) else None
    deductible = first(r"Deductible\s*:?\s*(\$?[\d,]+)", text)
    r.deductible = cents(deductible) if deductible else None
    premium = first(r"Total (?:Annual |Policy )?Premium\s*:?\s*(\$?[\d,]+\.\d\d)", text)
    r.premium = cents(premium) if premium else None
    r.producer = first(r"(?:Producer|Agent)\s*:?\s*\n?\s*([^\n]+)", text)
    return r


# Checks shared by the policy models ---------------------------------------------------------------------------------

def fold(number: str) -> str:
    from jason.tasks.insurance import fold_number

    return fold_number(number or "")


def sheet_policies(context: ModelContext) -> tuple[Any, ...]:
    community = context.community
    if community is None or not hasattr(community, "insurance"):
        return ()
    try:
        return tuple(community.insurance().policies)
    except Exception:
        return ()


def sheet_policy(number: str, context: ModelContext) -> Any | None:
    folded = fold(number)
    for policy in sheet_policies(context):
        if folded and folded in {fold(n) for n in policy.numbers}:
            return policy
    return None


def community_word(context: ModelContext) -> str:
    """The association's distinctive first word ("Mystique"), to tell its name on a page."""
    name = str(getattr(context.community, "name", "") or "")
    return name.split()[0].lower() if name else ""


def is_association(name: str, context: ModelContext) -> bool:
    word = community_word(context)
    low = (name or "").lower()
    return bool(word and word in low) or (not word and bool(re.search(r"association|\bHOA\b", name or "", re.I)))


def unit_count(context: ModelContext) -> int | None:
    units = getattr(context.community, "units", None)
    if units is None:
        return None
    try:
        return len(units() if callable(units) else units)
    except TypeError:
        return None


_LIBRARY_CACHE: dict[tuple[str, str], list[tuple[dict[str, Any], Any]]] = {}


def library_records(context: ModelContext, kind: DocumentKind, parse) -> list[tuple[dict[str, Any], Any]]:
    """Every library file of ``kind`` parsed with ``parse`` (no checks), once per data directory: the other files a check
    compares a reading with."""
    if context.data_dir is None:
        return []
    key = (str(Path(context.data_dir).resolve()), kind.value)
    if key not in _LIBRARY_CACHE:
        from jason.tasks.library import distinct, load, text_for

        out = []
        for row in distinct(load(Path(context.data_dir))):
            if row.get("kind") != kind.value:
                continue
            text = text_for(Path(context.data_dir), row["id"])
            # No date goes to the parse: a record is what the file says, on any day.
            record = parse(text, ModelContext(context.community, context.data_dir, name=row.get("name") or "")) if text.strip() else None
            if record is not None:
                out.append((row, record))
        _LIBRARY_CACHE[key] = out
    return _LIBRARY_CACHE[key]


def _money(value: int | None) -> str:
    return "?" if value is None else f"${value / 100:,.0f}" if value % 100 == 0 else f"${value / 100:,.2f}"


def sheet_renewal(r, community: Any) -> date | None:
    """What the policy-term check reads from the specification: the renewal date of the policy sheet's term in force for
    this policy (for a flood number the sheet does not carry, the sheet's flood policy on the same building)."""
    context = ModelContext(community)
    policy = sheet_policy(r.policy_number, context)
    if policy is None and r.building is not None:
        policy = next((p for p in sheet_policies(context) if p.kind is PolicyKind.FLOOD and p.building == r.building), None)
    return getattr(policy, "renewal", None)


@AS_OF.check("policy-term", InsurancePolicy, fields=("coverage", "policy_number", "building", "term_end"), facts=sheet_renewal)
def policy_term(r, as_of: date, renewal: date | None = None) -> list[Finding]:
    """As of a date: a term that ended or ends soon, read against the policy sheet's term in force (``sheet_renewal``)."""
    end = r.term_end
    if end is None:
        return []
    what = f"{r.coverage.value.replace('_', ' ') if r.coverage else 'policy'} {r.policy_number or ''}".strip()
    if r.building is not None:
        what += f" (building {int(r.building)})"
    left = (end - as_of).days
    if left < 0:
        if renewal and renewal > end:
            return [Finding("term-superseded", f"{what} ended {end}; the policy sheet carries a later term, to {renewal}", Severity.INFO)]
        return [Finding("term-ended", f"{what} ended {end} and the policy sheet shows no later term; confirm it renewed. If it lapsed "
                        "and was not replaced, members get individual notice", Severity.CHECK, "CIV 5810")]
    if left <= SOON_DAYS:
        return [Finding("term-ending", f"{what} ends {end} ({left} days); if the carrier will not renew and no replacement is in "
                        "place by then, members must be told at once", Severity.CHECK, "CIV 5810")]
    if renewal and end > renewal:
        return [Finding("next-term-issued", f"{what} runs to {end}, past the policy sheet's term in force (to {renewal}): the next "
                        "term is issued", Severity.INFO)]
    return []


def summary_finding(rows: list[tuple[Coverage | None, str, int | None, int | None]], authority: str = "CIV 5300(b)(9)") -> list[Finding]:
    """Which of the annual summary's items (insurer, type, limit, and the deductible if any) the page gives for each line
    it shows. A line without a deductible may have none, so only a missing insurer or limit is a gap."""
    out = []
    for coverage, insurer, limit, _deductible in rows:
        if coverage not in SUMMARY_LINES:
            continue
        gaps = [label for label, value in (("insurer", insurer), ("limit", limit)) if not value]
        name = coverage.value.replace("_", " ")
        if gaps:
            out.append(Finding("summary-item-missing", f"the {name} line gives no {', '.join(gaps)}; the annual budget report's insurance "
                               "summary needs the insurer, type, limit, and deductible (if any)", Severity.CHECK, authority))
    if rows and not out:
        names = sorted({c.value.replace("_", " ") for c, *_ in rows if c in SUMMARY_LINES})
        if names:
            out.append(Finding("summary-items-present", f"the page gives the insurer, type, limit, and deductible for {', '.join(names)}; a "
                               "declarations page can be distributed in place of that part of the summary", Severity.INFO, authority))
    return out


class NfipFloodDeclarationsModel(DocumentModel):
    kind = DocumentKind.INSURANCE_POLICY
    name = "nfip-flood-declarations"
    required = ("carrier", "policy_number", "named_insured", "term_start", "term_end", "limit", "deductible", "premium", "building")
    lens_checks = (policy_term,)

    def parse(self, text: str, context: ModelContext) -> InsurancePolicy | None:
        return _nfip(text, context)

    def check(self, r: InsurancePolicy, context: ModelContext) -> list[Finding]:
        found = policy_findings(r, context)
        parts = {c.name: c.amount for c in r.charges}
        if r.premium and len(parts) == 4:
            total = sum(parts.values())
            if total != r.premium:
                found.append(Finding("premium-parts", f"the premium's parts add to {_money(total)}, not the total {_money(r.premium)} (a "
                                     "probation surcharge or a misread value)", Severity.CHECK))
        if r.limit and r.replacement_cost:
            found += coinsurance_findings(r)
        found += mailing_findings(r.mailing_address, context, "the flood policy")
        policy = sheet_policy(r.policy_number, context)
        if policy is not None and policy.building is not None and r.building is not None and policy.building != r.building:
            found.append(Finding("building-mismatch", f"the policy sheet puts {r.policy_number} on building {int(policy.building)}; the "
                                 f"page's location is building {int(r.building)}", Severity.CHECK))
        if policy is None and r.building is not None:
            on_sheet = [p for p in sheet_policies(context) if p.kind is PolicyKind.FLOOD and p.building == r.building]
            if on_sheet:
                found.append(Finding("number-not-on-sheet", f"flood policy {r.policy_number} for building {int(r.building)} is not on the "
                                     f"policy sheet, which lists {on_sheet[0].number} for that building", Severity.CHECK))
        if r.building is not None and r.term_start and r.term_end:
            overlap = sorted({rec.policy_number for _row, rec in library_records(context, DocumentKind.INSURANCE_POLICY, _nfip)
                              if rec.building == r.building and rec.policy_number and fold(rec.policy_number) != fold(r.policy_number)
                              and rec.term_start and rec.term_end and rec.term_start < r.term_end and r.term_start < rec.term_end})
            if overlap:
                found.append(Finding("overlapping-flood-policy", f"another flood policy in the library covers building {int(r.building)} for "
                                     f"an overlapping term ({', '.join(overlap)}); confirm only one is in force and any duplicate premium "
                                     "was refunded", Severity.CHECK))
        found += change_findings(r, context)
        return found


NFIP_UNIT_MAXIMUM = 25_000_000   # cents: the NFIP's building coverage for a condominium building is at most $250,000 a unit
COINSURANCE_SHARE = 0.80         # the RCBAP's co-insurance test: the lesser of 80% of replacement cost or the maximum available


def coinsurance_findings(r: InsurancePolicy) -> list[Finding]:
    """Building coverage against the RCBAP's co-insurance test, which the page prints: at a loss the building must be insured
    to the lesser of 80% of its replacement cost or the maximum available, $250,000 times the units."""
    share = r.limit / r.replacement_cost
    if not r.units:
        return [Finding("coverage-to-value", f"building coverage {_money(r.limit)} is {share:.0%} of the {_money(r.replacement_cost)} "
                        "replacement cost; the page prints no unit count, so the NFIP maximum for the co-insurance test cannot be "
                        "figured", Severity.INFO)]
    maximum = NFIP_UNIT_MAXIMUM * r.units
    needed = min(int(r.replacement_cost * COINSURANCE_SHARE), maximum)
    units = f" for {r.units} units"
    if r.limit >= maximum:
        return [Finding("coverage-to-value", f"building coverage {_money(r.limit)} is the NFIP maximum{units} ($250,000 a unit), "
                        f"{share:.0%} of the {_money(r.replacement_cost)} replacement cost; that meets the co-insurance test the page "
                        "prints (the lesser of 80% of replacement cost or the maximum)", Severity.INFO, "44 CFR 61.6")]
    if r.limit < needed:
        return [Finding("coverage-below-coinsurance", f"building coverage {_money(r.limit)} is under {_money(needed)}, the lesser of 80% of "
                        f"the {_money(r.replacement_cost)} replacement cost and the NFIP maximum{units}; the page warns a loss would be paid "
                        "with a co-insurance penalty", Severity.CHECK, "44 CFR 61.6")]
    return [Finding("coverage-to-value", f"building coverage {_money(r.limit)} is {share:.0%} of the {_money(r.replacement_cost)} "
                    f"replacement cost{units}, at or above the co-insurance test's 80%", Severity.INFO)]


def policy_findings(r: InsurancePolicy, context: ModelContext) -> list[Finding]:
    found: list[Finding] = [policy_term]   # the as-of lens's place: the term ended, ends soon, or the next one is issued
    if r.named_insured and context.community is not None and not is_association(r.named_insured, context):
        found.append(Finding("insured-not-association", f"the named insured is {r.named_insured!r}, not the association", Severity.PROBLEM))
    if r.policy_number and sheet_policies(context) and sheet_policy(r.policy_number, context) is None and r.coverage is not Coverage.FLOOD:
        found.append(Finding("number-not-on-sheet", f"policy {r.policy_number} is not on the policy sheet (neither a current nor a prior "
                             "number)", Severity.CHECK))
    found += summary_finding([(r.coverage, r.carrier, r.limit, r.deductible)])
    return found


def change_findings(r: InsurancePolicy, context: ModelContext) -> list[Finding]:
    """A lower limit or a higher deductible than the same building's previous term in the library (CIV 5810)."""
    if r.building is None or r.term_start is None:
        return []
    earlier = [rec for _row, rec in library_records(context, DocumentKind.INSURANCE_POLICY, _nfip)
               if rec.building == r.building and rec.term_end and abs((rec.term_end - r.term_start).days) <= 3]
    found = []
    for prior in earlier[:1]:
        if prior.limit and r.limit and r.limit < prior.limit:
            found.append(Finding("limit-reduced", f"building coverage fell from {_money(prior.limit)} to {_money(r.limit)} at this term; a "
                                 "reduction in limits needs individual notice to members", Severity.CHECK, "CIV 5810"))
        if prior.deductible and r.deductible and r.deductible > prior.deductible:
            found.append(Finding("deductible-raised", f"the deductible rose from {_money(prior.deductible)} to {_money(r.deductible)} at this "
                                 "term; an increase in the deductible needs individual notice to members", Severity.CHECK, "CIV 5810"))
        if prior.premium and r.premium:
            found.append(Finding("premium-change", f"the premium went from {_money(prior.premium)} to {_money(r.premium)} "
                                 f"({(r.premium - prior.premium) / prior.premium:+.0%}) over the previous term", Severity.INFO))
    return found


class PolicyDeclarationsModel(DocumentModel):
    kind = DocumentKind.INSURANCE_POLICY
    name = "policy-declarations"
    required = ("carrier", "policy_number", "named_insured", "term_start", "term_end", "limit")
    lens_checks = (policy_term,)

    def parse(self, text: str, context: ModelContext) -> InsurancePolicy | None:
        return _declarations(text, context)

    def check(self, r: InsurancePolicy, context: ModelContext) -> list[Finding]:
        return policy_findings(r, context)


# ACORD certificates ------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class CoverageLine:
    insurer: str = ""                 # the insurer's letter on the certificate (A, B, ...)
    coverage: Coverage | None = None
    named: str = ""                   # the coverage as the certificate words it ("Crime/Fidelity Bond")
    policy_number: str = ""
    effective: date | None = None
    expiration: date | None = None
    limit: int | None = None          # cents: each occurrence, combined single limit, or the stated limit
    aggregate: int | None = None
    deductible: int | None = None
    building: Building | None = None  # a flood line in the remarks
    limits: tuple[int, ...] = ()


@dataclass(frozen=True)
class Insurer:
    letter: str
    name: str
    naic: str = ""


@dataclass
class EvidenceOfInsurance:
    forms: tuple[str, ...] = ()       # "ACORD 25", "ACORD 101"
    issued: date | None = None
    producer: str = ""
    insurers: tuple[Insurer, ...] = ()
    insured: str = ""
    certificate_number: str = ""
    lines: tuple[CoverageLine, ...] = ()
    description: tuple[str, ...] = ()
    remarks: tuple[str, ...] = ()
    holder: str = ""
    units: int | None = None          # "consists of 81 units"


# The ACORD forms' printed labels, as the text layer gives them one per line.
ACORD_LABELS = frozenset("""
SHOULD ANY OF THE ABOVE DESCRIBED POLICIES BE CANCELLED BEFORE|THE EXPIRATION DATE THEREOF, NOTICE WILL BE DELIVERED IN|
ACCORDANCE WITH THE POLICY PROVISIONS.|INSURER(S) AFFORDING COVERAGE|INSURER A :|INSURER B :|INSURER C :|INSURER D :|INSURER E :|
INSURER F :|NAIC #|NAME:|CONTACT|(A/C, No):|FAX|E-MAIL|ADDRESS:|PRODUCER|(A/C, No, Ext):|PHONE|INSURED|REVISION NUMBER:|
CERTIFICATE NUMBER:|COVERAGES|OTHER:|(Per accident)|(Ea accident)|$|N / A|SUBR|WVD|ADDL|INSD|ADDL SUBR|PROPERTY DAMAGE|
BODILY INJURY (Per accident)|BODILY INJURY (Per person)|COMBINED SINGLE LIMIT|AUTOS ONLY|AUTOS|NON-OWNED|SCHEDULED|OWNED|ANY AUTO|
AUTOMOBILE LIABILITY|Y / N|WORKERS COMPENSATION|AND EMPLOYERS' LIABILITY|OFFICER/MEMBER EXCLUDED?|(Mandatory in NH)|
DESCRIPTION OF OPERATIONS below|If yes, describe under|ANY PROPRIETOR/PARTNER/EXECUTIVE|E.L. DISEASE - POLICY LIMIT|
E.L. DISEASE - EA EMPLOYEE|E.L. EACH ACCIDENT|ER|OTH-|STATUTE|PER|LIMITS|(MM/DD/YYYY)|POLICY EXP|POLICY EFF|POLICY NUMBER|
TYPE OF INSURANCE|LTR|INSR|EXCESS LIAB|UMBRELLA LIAB|EACH OCCURRENCE|AGGREGATE|OCCUR|CLAIMS-MADE|DED|RETENTION $|RETENTION|
PRODUCTS - COMP/OP AGG|GENERAL AGGREGATE|PERSONAL & ADV INJURY|MED EXP (Any one person)|DAMAGE TO RENTED|PREMISES (Ea occurrence)|
COMMERCIAL GENERAL LIABILITY|GEN'L AGGREGATE LIMIT APPLIES PER:|POLICY|PRO-|JECT|LOC|CERTIFICATE OF LIABILITY INSURANCE|
DATE (MM/DD/YYYY)|CANCELLATION|AUTHORIZED REPRESENTATIVE|CERTIFICATE HOLDER|HIRED|FORM NUMBER:|FORM TITLE:|ADDITIONAL REMARKS|
ADDITIONAL REMARKS SCHEDULE|Page of|AGENCY CUSTOMER ID:|LOC #:|AGENCY|CARRIER|NAIC CODE|NAMED INSURED|EFFECTIVE DATE:|
CERTIFICATE OF PROPERTY INSURANCE|COVERED PROPERTY|POLICY EFFECTIVE|POLICY EXPIRATION|PROPERTY|CAUSES OF LOSS|BASIC|BROAD|SPECIAL|
EARTHQUAKE|FLOOD|BUILDING|PERSONAL PROPERTY|BUSINESS INCOME|EXTRA EXPENSE|BLANKET BUILDING|BLANKET PERS PROP|BLANKET BLDG & PP|WIND|
DEDUCTIBLES|CONTENTS|RENTAL VALUE|INLAND MARINE|TYPE OF POLICY|NAMED PERILS|CRIME|EQUIPMENT BREAKDOWN|BOILER & MACHINERY /|
CUSTOMER ID:|PRODUCER CUSTOMER ID:|EVIDENCE OF PROPERTY INSURANCE|EVIDENCE OF COMMERCIAL PROPERTY INSURANCE|LOAN NUMBER|
ADDITIONAL INTEREST|MORTGAGEE|LENDER'S LOSS PAYABLE|LOSS PAYEE|LENDER SERVICING AGENT NAME AND ADDRESS|AMOUNT OF INSURANCE|
CONTINUED UNTIL TERMINATED IF CHECKED|THIS REPLACES PRIOR EVIDENCE DATED:|PROPERTY INFORMATION|LOCATION/DESCRIPTION|
COVERAGE INFORMATION|PERILS INSURED|COMMERCIAL PROPERTY COVERAGE AMOUNT OF INSURANCE:|YES|NO|N/A|
""".replace("\n", "").split("|")) - {""}
_LABEL_PREFIXES = ("IMPORTANT:", "If SUBROGATION", "this certificate does not", "THIS CERTIFICATE IS ISSUED", "CERTIFICATE DOES NOT",
                   "BELOW.", "REPRESENTATIVE OR PRODUCER", "THIS IS TO CERTIFY", "INDICATED.", "CERTIFICATE MAY BE ISSUED",
                   "EXCLUSIONS AND CONDITIONS", "A statement on", "DESCRIPTION OF OPERATIONS /", "LOCATION OF PREMISES", "SPECIAL CONDITIONS",
                   "THIS ADDITIONAL REMARKS FORM", "©", "The ACORD name", "ACORD ", "Page ")
_FORM = re.compile(r"ACORD (\d{2,3}) \((\d{4})/\d{2}\)")
CERTIFICATE_FORMS = frozenset({"24", "25", "27", "28"})
_POLNUM = re.compile(r"^(?=[A-Z0-9-]*\d)(?=[A-Z0-9-]*[A-Z-])?[A-Z0-9][A-Z0-9-]{5,}$")
_DATE = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")
_AMOUNT = re.compile(r"^\$?\s?(\d{1,3}(?:,\d{3})+|\d{3,})(?:\.\d\d)?$")
_INSURER_WORDS = re.compile(r"\b(Insurance|Indemnity|Casualty|Surety|Exchange|Assurance|Underwriters|Lloyd'?s|Mutual|Reciprocal)\b", re.I)
_FLOOD_REMARK = re.compile(r"(\d{1,2}/\d{1,2}/\d{4})\s*-\s*(\d{1,2}/\d{1,2}/\d{4})\s+([A-Z0-9-]{6,})\s+Bldg\s*(\d)\s*-\s*\$([\d,]+)\s*/\s*Ded\s*\$([\d,]+)",
                           re.I)


def _is_label(line: str) -> bool:
    return line in ACORD_LABELS or line.startswith(_LABEL_PREFIXES)


def _values(page: str) -> list[str]:
    return [line for line in (squash(raw) for raw in page.split("\n")) if line and not _is_label(line)]


def _amount(line: str) -> int | None:
    m = _AMOUNT.match(line)
    return cents(line) if m else None


def _is_polnum(line: str) -> bool:
    return bool(_POLNUM.match(line)) and not _DATE.match(line) and not _AMOUNT.match(line) and not re.fullmatch(r"\d{5}", line)


def _rows(values: list[str], start: int) -> tuple[list[CoverageLine], int]:
    """The coverage rows from ``start``: each begins at its insurer letter; a run of letters is a block of rows whose
    numbers, dates, deductibles, and limits then follow column by column. Returns the rows and where they end."""
    segments: list[list[str]] = []
    i = start
    while i < len(values):
        if re.fullmatch(r"[A-F]", values[i]) and (not segments or not re.fullmatch(r"[A-F]", values[i - 1])):
            segments.append([])
        if segments:
            segments[-1].append(values[i])
        i += 1
    rows: list[CoverageLine] = []
    end = start
    consumed = start
    for seg in segments:
        letters = []
        while seg and re.fullmatch(r"[A-F]", seg[0]):
            letters.append(seg.pop(0))
        consumed += len(letters)
        numbers = [j for j, v in enumerate(seg) if _is_polnum(v)]
        dates = [j for j, v in enumerate(seg) if _DATE.match(v)]
        if not numbers or len(dates) < 2:
            consumed += len(seg)
            continue
        k = len(numbers)
        names = [v for v in seg[:numbers[0]] if re.search(r"[A-Za-z]{3}", v) and not _DATE.match(v) and not re.fullmatch(r"[XYN]", v)
                 and not re.search(r"^(Limit|Deductible)\s*:?$|^Included$", v, re.I)]
        after = seg[dates[-1] + 1:]
        last = dates[-1]
        if k > 1:
            eff = [parse_date(seg[j]) for j in dates[:k]]
            exp = [parse_date(seg[j]) for j in dates[k: 2 * k]]
            deds = [cents(v) for v in after if re.search(r"deductible", v, re.I)][:k]
            amounts = [(n, _amount(v)) for n, v in enumerate(after) if _amount(v) is not None][:k]
            last += 1 + max([n for n, _a in amounts] + [len(deds) - 1, -1])
            for r in range(k):
                named = names[r] if r < len(names) else ""
                rows.append(CoverageLine(letters[r] if r < len(letters) else "", coverage_of(named), named, seg[numbers[r]],
                                         eff[r] if r < len(eff) else None, exp[r] if r < len(exp) else None,
                                         amounts[r][1] if r < len(amounts) else None, None, deds[r] if r < len(deds) else None))
        else:
            eff, exp = parse_date(seg[dates[-2]]), parse_date(seg[dates[-1]])
            deductible = None
            limit = None
            amounts = []
            included = 0
            for n, v in enumerate(seg):
                if n in dates:
                    continue
                labeled = n > 0 and re.fullmatch(r"(?:Deductible|Limit)\s*:?", seg[n - 1], re.I)
                if re.fullmatch(r"Deductible\s*:?", v, re.I) and n + 1 < len(seg):
                    deductible = _amount(seg[n + 1])
                    last = max(last, n + 1)
                    continue
                if re.fullmatch(r"Limit\s*:?", v, re.I) and n + 1 < len(seg):
                    limit = _amount(seg[n + 1])
                    last = max(last, n + 1)
                    continue
                if v == "Included":  # a limit the master policy includes (hired and non-owned auto)
                    included += 1
                    continue
                value = _amount(v)
                if value is not None and not labeled:
                    amounts.append(value)
                    last = max(last, n)
                elif re.search(r"deductible", v, re.I):
                    deductible = cents(v)
            named = next((n for n in names if coverage_of(n)), names[0] if names else "")
            coverage = coverage_of(named) if named else None
            if coverage is None:
                big = [a for a in amounts if a >= 10_000_000]
                small = [a for a in amounts if a < 10_000_000]
                coverage = Coverage.GENERAL_LIABILITY if len(amounts) >= 4 else Coverage.AUTO if len(amounts) + included == 1 else \
                    Coverage.UMBRELLA if big and small else Coverage.WORKERS_COMP if len(big) == 3 else Coverage.OTHER
            aggregate = None
            if coverage is Coverage.GENERAL_LIABILITY and len(amounts) >= 5:
                aggregate = amounts[4]
            elif coverage is Coverage.UMBRELLA and len(amounts) >= 2:
                aggregate = amounts[1]
            if limit is None and amounts:
                limit = max(amounts) if coverage is Coverage.PROPERTY else amounts[0]
            if coverage is Coverage.UMBRELLA and deductible is None:
                small = [a for a in amounts if a < 10_000_000]
                deductible = small[0] if small else None
            rows.append(CoverageLine(letters[0] if letters else "", coverage, named, seg[numbers[0]], eff, exp, limit, aggregate, deductible,
                                     None, tuple(amounts)))
        end = consumed + last + 1
        consumed += len(seg)
    return rows, end


def _holder_and_description(tail: list[str]) -> tuple[str, tuple[str, ...]]:
    holder: list[str] = []
    for line in reversed(tail):
        if len(holder) >= 4 or line.endswith((".", "...", "*", ")")) or len(line.split()) >= 8:
            break
        holder.insert(0, line)
    description = tuple(tail[: len(tail) - len(holder)])
    return ", ".join(holder), description


def _acord(text: str, context: ModelContext) -> EvidenceOfInsurance | None:
    if not re.search(r"CERTIFICATE OF (?:LIABILITY|PROPERTY) INSURANCE|EVIDENCE OF (?:COMMERCIAL )?PROPERTY INSURANCE", text or "") \
            or not _FORM.search(text):
        return None
    r = EvidenceOfInsurance()
    pages = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    certificate_pages = [p for p in pages if any(m.group(1) in CERTIFICATE_FORMS for m in _FORM.finditer(p))]
    remark_pages = [p for p in pages if any(m.group(1) == "101" for m in _FORM.finditer(p)) and p not in certificate_pages]
    r.forms = tuple(dict.fromkeys(f"ACORD {m.group(1)}" for p in certificate_pages + remark_pages for m in _FORM.finditer(p)))
    lines: list[CoverageLine] = []
    descriptions: list[str] = []
    for page in certificate_pages:
        values = _values(page)
        issued = next((i for i, v in enumerate(values) if _DATE.match(v)), None)
        if issued is None:
            continue
        r.issued = r.issued or parse_date(values[issued])
        r.producer = r.producer or (values[issued + 1] if issued + 1 < len(values) else "")
        email = next((i for i in range(issued, min(issued + 12, len(values))) if "@" in values[i]), issued + 1)
        start = next((i for i in range(email + 1, len(values)) if re.fullmatch(r"[A-F]", values[i])), len(values))
        insurers: list[Insurer] = []
        insured_block: list[str] = []
        j = email + 1
        while j < start:
            v = values[j]
            if j + 1 < start and re.fullmatch(r"\d{5}", values[j + 1]) and re.search(r"[A-Za-z]{3}", v):
                insurers.append(Insurer(chr(ord("A") + len(insurers)), v, values[j + 1]))
                j += 2
                continue
            if _INSURER_WORDS.search(v) and not re.search(r"agency|agent|broker", v, re.I):
                insurers.append(Insurer(chr(ord("A") + len(insurers)), v))  # an insurer the certificate gives no NAIC number
                j += 1
                continue
            if re.fullmatch(r"\d{7,}", v):
                r.certificate_number = r.certificate_number or v
            elif not (re.fullmatch(r"[A-Z0-9-]+", v) and re.search(r"\d", v)) and not re.fullmatch(r"[\d() .-]{10,}", v):
                insured_block.append(v)
            j += 1
        if not r.insurers:
            r.insurers = tuple(insurers)
        if not r.insured and insured_block:
            named = [v for v in insured_block if is_association(v, context)] if context.community is not None else []
            r.insured = named[0] if named else insured_block[0]
        rows, end = _rows(values, start)
        lines += rows
        holder, description = _holder_and_description(values[end:])
        r.holder = r.holder or holder
        descriptions += list(description)
    remarks: list[str] = []
    for page in remark_pages:
        values = _values(page)
        title = next((i for i, v in enumerate(values) if v.startswith("CERTIFICATE OF")), None)
        remarks += values[title + 1:] if title is not None else [v for v in values if len(v.split()) >= 3]
    for m in _FLOOD_REMARK.finditer("\n".join(remarks + descriptions)):
        try:
            building = Building(int(m.group(4)))
        except ValueError:
            building = None
        lines.append(CoverageLine("", Coverage.FLOOD, "Commercial Flood", m.group(3), parse_date(m.group(1)), parse_date(m.group(2)),
                                  int(m.group(5).replace(",", "")) * 100, None, int(m.group(6).replace(",", "")) * 100, building))
    r.lines = tuple(lines)
    r.description = tuple(descriptions)
    r.remarks = tuple(remarks)
    units = re.search(r"(?:consists of|consisting of)\s+(\d+)\s+units", " ".join(descriptions + remarks), re.I) or \
        re.search(r"\b(\d+)\s+Units\b", " ".join(descriptions), re.I)
    r.units = int(units.group(1)) if units else None
    return r


def _limit(lines: list[CoverageLine], coverage: Coverage) -> int | None:
    values = [l.limit for l in lines if l.coverage is coverage and l.limit]
    return max(values) if values else None


@AS_OF.check("certificate-lines", EvidenceOfInsurance, fields=("lines",))
def certificate_lines(r, as_of: date, _facts=None) -> list[Finding]:
    """As of a date: which of a certificate's policies have expired, and which expire soon."""
    found: list[Finding] = []
    ends = [l.expiration for l in r.lines if l.expiration]
    if ends:
        latest = max(ends)
        expired = [l for l in r.lines if l.expiration and l.expiration < as_of]
        soon = [l for l in r.lines if l.expiration and 0 <= (l.expiration - as_of).days <= SOON_DAYS]
        if latest < as_of:
            found.append(Finding("certificate-expired", f"every policy on the certificate has expired (the last on {latest}); anyone "
                                 "relying on it needs the renewal certificate", Severity.CHECK))
        elif expired:
            found.append(Finding("lines-expired", f"{len(expired)} of {len(r.lines)} policies on the certificate have expired: "
                                 + ", ".join(f"{l.policy_number} ({l.expiration})" for l in expired), Severity.CHECK))
        if soon:
            found.append(Finding("lines-expiring", f"{len(soon)} policies expire within {SOON_DAYS} days: "
                                 + ", ".join(f"{l.policy_number} ({l.expiration})" for l in soon), Severity.INFO, "CIV 5810"))
    return found


class AcordCertificateModel(DocumentModel):
    kind = DocumentKind.EVIDENCE_OF_INSURANCE
    name = "acord-certificate"
    required = ("issued", "producer", "insurers", "insured", "lines", "holder")
    lens_checks = (certificate_lines,)

    def parse(self, text: str, context: ModelContext) -> EvidenceOfInsurance | None:
        return _acord(text, context)

    def check(self, r: EvidenceOfInsurance, context: ModelContext) -> list[Finding]:
        found: list[Finding] = [certificate_lines]   # the as-of lens's place: the policies expired or expiring
        if r.holder and (is_association(r.holder, context) or re.search(r"board of directors", r.holder, re.I)):
            found.append(Finding("holder-is-association", f"the certificate holder is the association itself ({r.holder}); a certificate for "
                                 "a lender, vendor, or owner names that party", Severity.INFO))
        if r.insured and context.community is not None and not is_association(r.insured, context):
            found.append(Finding("insured-not-association", f"the insured is {r.insured!r}, not the association", Severity.PROBLEM))
        found += self._numbers(r, context)
        found += self._statutes(r, context)
        return found

    def _numbers(self, r: EvidenceOfInsurance, context: ModelContext) -> list[Finding]:
        found = []
        if sheet_policies(context):
            unknown = sorted({l.policy_number for l in r.lines if l.policy_number and sheet_policy(l.policy_number, context) is None})
            if unknown:
                found.append(Finding("number-not-on-sheet", f"policy numbers not on the policy sheet: {', '.join(unknown)}", Severity.CHECK))
            stale = sorted({(l.policy_number, p.number, l.expiration) for l in r.lines
                            if (p := sheet_policy(l.policy_number, context)) is not None and fold(l.policy_number) != fold(p.number)
                            and p.renewal and l.expiration and l.expiration >= p.renewal})
            for number, current, end in stale:
                found.append(Finding("prior-number-for-current-term", f"the certificate prints {number} for the term ending {end}; the policy "
                                     f"sheet lists {number} as an earlier term's number and {current} as the current one", Severity.CHECK))
            for l in r.lines:
                policy = sheet_policy(l.policy_number, context)
                expected = POLICY_KIND.get(l.coverage) if l.coverage else None
                if policy is not None and expected is not None and policy.kind is not expected:
                    found.append(Finding("line-kind-mismatch", f"{l.policy_number} is a {policy.kind.value} policy on the sheet; the certificate "
                                         f"shows it as {l.coverage.value.replace('_', ' ')}", Severity.CHECK))
        files = library_records(context, DocumentKind.INSURANCE_POLICY, _nfip)
        for l in r.lines:
            if l.coverage is not Coverage.FLOOD:
                continue
            same = [rec for _row, rec in files if fold(rec.policy_number) == fold(l.policy_number)]
            if not same:
                continue
            term = [rec for rec in same if rec.term_end == l.expiration]
            if not term:
                found.append(Finding("no-policy-file-for-term", f"the library holds flood policy {l.policy_number} but no declarations for the "
                                     f"term ending {l.expiration}", Severity.CHECK))
                continue
            rec = term[0]
            if (rec.limit and l.limit and rec.limit != l.limit) or (rec.deductible and l.deductible and rec.deductible != l.deductible):
                found.append(Finding("flood-line-differs", f"flood {l.policy_number}: the certificate shows {_money(l.limit)} / deductible "
                                     f"{_money(l.deductible)}; the declarations show {_money(rec.limit)} / {_money(rec.deductible)}", Severity.CHECK))
        return found

    def _statutes(self, r: EvidenceOfInsurance, context: ModelContext) -> list[Finding]:
        found: list[Finding] = []
        units = unit_count(context) or r.units
        if r.units and unit_count(context) and r.units != unit_count(context):
            found.append(Finding("unit-count", f"the certificate describes {r.units} units; the specification has {unit_count(context)}",
                                 Severity.CHECK))
        lines = list(r.lines)
        gl, dno = _limit(lines, Coverage.GENERAL_LIABILITY), _limit(lines, Coverage.DIRECTORS_AND_OFFICERS)
        if units and (gl or dno):
            floor = 50_000_000 if units <= 100 else 100_000_000
            short = [(name, value) for name, value in (("general liability", gl), ("D&O", dno)) if not value or value < floor]
            if short:
                found.append(Finding("volunteer-immunity-coverage", "for director immunity both general liability and D&O must be at least "
                                     f"{_money(floor)} ({units} separate interests); short: " + ", ".join(f"{n} {_money(v)}" for n, v in short),
                                     Severity.CHECK, "CIV 5800(a)(4)"))
            else:
                found.append(Finding("volunteer-immunity-coverage", f"general liability {_money(gl)} and D&O {_money(dno)} meet the "
                                     f"{_money(floor)} minimum for director immunity", Severity.INFO, "CIV 5800(a)(4)"))
        if units and gl:
            floor = 200_000_000 if units <= 100 else 300_000_000
            umbrella = _limit(lines, Coverage.UMBRELLA) or 0
            severity = Severity.INFO if gl + umbrella >= floor else Severity.CHECK
            found.append(Finding("owner-tort-coverage", f"general liability {_money(gl)} per occurrence"
                                 + (f" plus {_money(umbrella)} umbrella" if umbrella else "")
                                 + f" against the {_money(floor)} owners' tenant-in-common protection needs", severity, "CIV 5805(b)"))
        crime = _limit(lines, Coverage.CRIME)
        words = " ".join(r.description + r.remarks)
        if crime:
            fraud = bool(re.search(r"computer fraud", words, re.I) and re.search(r"(?:funds )?transfer fraud", words, re.I))
            agent = bool(re.search(r"management|managing agent", words, re.I) and re.search(r"fidelity|dishonesty|crime", words, re.I))
            found.append(Finding("crime-coverage", f"crime/fidelity limit {_money(crime)}: it must at least equal the reserves plus three "
                                 "months' assessments; computer and funds transfer fraud "
                                 + ("named" if fraud else "not named on the certificate") + "; a managing agent's coverage "
                                 + ("named" if agent else "not named"), Severity.CHECK, "CIV 5806"))
        found += summary_finding([(l.coverage, next((i.name for i in r.insurers if i.letter == l.insurer), "") or ("flood carrier" if
                                   l.coverage is Coverage.FLOOD else ""), l.limit, l.deductible) for l in lines])
        return found


register(NfipFloodDeclarationsModel())
register(PolicyDeclarationsModel())
register(AcordCertificateModel())

__all__ = ["Coverage", "Declaration", "Charge", "InsurancePolicy", "CoverageLine", "Insurer", "EvidenceOfInsurance",
           "NfipFloodDeclarationsModel", "PolicyDeclarationsModel", "AcordCertificateModel", "coverage_of", "building_at",
           "library_records", "sheet_policy", "is_association", "unit_count", "POLICY_KIND"]
