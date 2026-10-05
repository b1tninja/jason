"""Full policy packets: the master package, the crime policy, and the umbrella's evidence of insurance.

A carrier's packet buries its declarations among notices and forms (the Arden master package runs to 400,000
characters). These models find the declarations inside the packet and read them; they sort before the general
``policy-declarations`` reader, which reads a stray "Policy" label in a packet as the policy number.

- ``package-declarations``: Accelerant's "POLICY DECLARATIONS - Condominium Assoc." through Arden (the master policy):
  the policy and renewed numbers, the period, the premium by coverage part, the named insured's mailing address, the
  covered premises, the building limit, valuation, and deductible, business income, equipment breakdown, the protective
  safeguards the property coverage depends on, the liability limits, the units, and the schedule of forms.
- ``crime-declarations``: PMA's Commercial Crime Policy Declarations (the fidelity policy): the period, the premium, and
  each insuring agreement's limit and deductible.
- ``umbrella-evidence``: McGowan's umbrella Evidence of Insurance and Purchasing Group Membership (Federal Insurance):
  the period, the limits, the retained limit, and the premium.

The law these are checked against is in ``contracts_insurance`` (CIV 5300(b)(9), 5800, 5805, 5806, 5810); the
specification's master policy (``Mystique.insurance().master()``) carries the deductible and the number in force.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from jason.community.document_models import DocumentModel, Finding, ModelContext, Severity, cents, register
from jason.community.symbols import DocumentKind


def _mdy(text: str) -> date | None:
    m = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", text or "")
    try:
        return date(int(m.group(3)), int(m.group(1)), int(m.group(2))) if m else None
    except ValueError:
        return None


def _amount(text: str) -> int | None:
    m = re.search(r"\$?\s*([\d,]{3,}(?:\.\d\d)?)", text or "")
    return cents("$" + m.group(1)) if m else None


def _money(value: int | None) -> str:
    return f"${value / 100:,.0f}" if value is not None else "-"


def _spec_master(context: ModelContext):
    try:
        return context.community.insurance().master() if context.community is not None else None
    except Exception:
        return None


def _named_insured(decl: str, context: ModelContext) -> str:
    """The association's name (``Community.name``) where the declarations print it, in the capitals the page uses. The
    page wraps the name and the text layer can give its second line first, so the name's leading words alone name it
    ("OAK RIDGE COMMUNITY" for Oak Ridge Community Association). Empty when the specification gives no name or the page
    names another insured."""
    own = str(getattr(context.community, "name", "") or "")
    words = own.split()
    if len(words) > 1 and words[-1].casefold() == "association":
        words = words[:-1]
    found = re.search(r"\s+".join(re.escape(w) for w in words), decl, re.I) if words else None
    return own.upper() if found else ""


def _mailing(text: str, context: ModelContext) -> str:
    """The named insured's mailing address among the page's addresses (``contracts_insurance.mailing_address``)."""
    from jason.community.models.contracts_insurance import association_mail_words, mailing_address

    return mailing_address(text, association_mail_words(context))


def _mailing_findings(address: str, context: ModelContext, what: str) -> list[Finding]:
    """The address against the association's current one: street, box, and ZIP (CIV 5810)."""
    from jason.community.models.contracts_insurance import mailing_findings

    return mailing_findings(address, context, what)


def _current_mail_words(context: ModelContext) -> tuple[str, ...]:
    try:
        rows = context.community.mail_addresses() if context.community is not None else ()
    except Exception:
        return ()
    return tuple(w for a in rows if getattr(a.kind, "name", "") == "CURRENT" for w in a.words)


# -- the master package ----------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Form:
    number: str
    title: str


@dataclass
class PackagePolicy:
    carrier: str = ""
    program: str = ""
    policy_number: str = ""
    renewal_of: str = ""
    term_start: date | None = None
    term_end: date | None = None
    premium: int | None = None
    premium_parts: dict[str, int] = field(default_factory=dict)   # coverage part -> cents
    named_insured: str = ""
    mailing_address: str = ""
    premises: str = ""
    building_limit: int | None = None
    valuation: str = ""
    property_deductible: int | None = None
    business_income: str = ""
    equipment_breakdown_limit: int | None = None
    equipment_breakdown_deductible: int | None = None
    protective_safeguards: tuple[str, ...] = ()
    units: int | None = None
    each_occurrence: int | None = None
    general_aggregate: int | None = None
    products_aggregate: int | None = None
    personal_injury: int | None = None
    hired_non_owned_auto: int | None = None
    forms: tuple[Form, ...] = ()
    terrorism_excluded: bool = False
    unit_interior: str = ""        # "single entity" when the unit interior form is on the schedule


_DECL = re.compile(r"POLICY DECLARATIONS - Condominium Assoc\.", re.I)
_FORM_LINE = re.compile(r"^((?:[A-Z]{1,4} ){1,3}\d{2,5}(?: [A-Z]{2})?(?: \d{2}){2})\s*$", re.M)


def _limit_after(label: str, text: str) -> int | None:
    m = re.search(re.escape(label) + r"\s*\n\s*\$?([\d,]{4,})", text)
    return cents("$" + m.group(1)) if m else None


# A form number ends in its edition, month and year ("IL 09 53 01 15", "N CP 12301 10 20", "CP 00 17 10 12").
_FORM_NUMBER = re.compile(r"^(?:[A-Z]{1,4} ){1,3}(?:[A-Z]{1,4} )?\d[\dA-Z ]{1,14} \d{2} \d{2}$")


def schedule_of_forms(text: str) -> tuple[Form, ...]:
    """The forms and endorsements the schedule lists: each form number with the title on the lines after it."""
    forms: list[Form] = []
    # Every page of the schedule repeats its heading; each page's lines run a few thousand characters past it.
    for heading in re.finditer(r"SCHEDULE OF FORMS AND ENDORSEMENTS", text or ""):
        lines = [ln.strip() for ln in text[heading.end(): heading.end() + 5000].splitlines() if ln.strip()]
        i = 0
        while i < len(lines):
            if _FORM_NUMBER.match(lines[i]) and i + 1 < len(lines) and not _FORM_NUMBER.match(lines[i + 1]):
                title = lines[i + 1]
                if i + 2 < len(lines) and not _FORM_NUMBER.match(lines[i + 2]) and lines[i + 2].isupper() and len(title) > 60:
                    title = f"{title} {lines[i + 2]}"
                forms.append(Form(lines[i], title))
                i += 2
                continue
            i += 1
    return tuple(dict.fromkeys(forms))


class PackageDeclarationsModel(DocumentModel):
    kind = DocumentKind.INSURANCE_POLICY
    name = "package-declarations"
    required = ("policy_number", "term_start", "term_end", "premium", "building_limit", "property_deductible", "each_occurrence")

    def parse(self, text: str, context: ModelContext) -> PackagePolicy | None:
        start = _DECL.search(text or "")
        if not start:
            return None
        decl = text[start.start(): start.start() + 9000]
        r = PackagePolicy(carrier="Accelerant National Insurance Company" if re.search(r"Accelerant", text or "", re.I) else "",
                          program="Arden Insurance Services" if re.search(r"Arden", text or "", re.I) else "")
        number = re.search(r"\b(N\d{3}[A-Z]{2}\d{4}-\d{2})\b", decl)
        r.policy_number = number.group(1) if number else ""
        renewed = re.search(r"(N\d{3}[A-Z]{2}\d{4}-\d{2})\s*\n\s*RENEWAL OF NUMBER", decl)
        r.renewal_of = renewed.group(1) if renewed else ""
        period = re.search(r"POLICY PERIOD:.*?\n\s*(\d{2}/\d{2}/\d{4})\s*\n\s*(\d{2}/\d{2}/\d{4})", decl, re.S)
        if period:
            r.term_start, r.term_end = _mdy(period.group(1)), _mdy(period.group(2))
        for part in ("COMMERCIAL PROPERTY", "COMMERCIAL GENERAL LIABILITY", "COMMERCIAL INLAND MARINE"):
            m = re.search(r"([\d,]+\.\d\d)\s*\n\s*" + part + r" COVERAGE PART", decl)
            if m:
                r.premium_parts[part.title().replace("Commercial ", "")] = cents("$" + m.group(1))
        total = re.search(r"([\d,]+\.\d\d)\s*\n\s*TOTAL:", decl) or re.search(r"TOTAL:\s*\n\s*([\d,]+\.\d\d)", decl)
        r.premium = cents("$" + total.group(1)) if total else (sum(r.premium_parts.values()) or None)
        named = re.search(r"\n([^\n]*(?:Association|Community)[^\n]*)\n([^\n]+)\n([^\n]+\d{5})\s*\nAGENCY AND MAILING", decl)
        if named:
            r.named_insured, r.mailing_address = named.group(1).strip(), f"{named.group(2).strip()}, {named.group(3).strip()}"
        premises = re.search(r"Mortgagee Name And Address\s*\n\s*\d+\s*\n\s*[\d-]+\s*\n\s*([^\n]+)\n\s*([^\n]+)", decl)
        r.premises = f"{premises.group(1).strip()}, {premises.group(2).strip()}" if premises else ""
        building = re.search(r"Limit of Insurance\s*\n\s*([\d,]{6,})\s*\n\s*loc# ?\d+ - Building\s*\n\s*(\w+)\s*\n\s*(\w+)\s*\n\s*([\d,]+)", decl)
        if building:
            r.building_limit = cents("$" + building.group(1))
            r.valuation = {"GRC": "guaranteed replacement cost", "RC": "replacement cost", "ACV": "actual cash value",
                           "AV": "agreed value", "IRC": "increased replacement cost"}.get(building.group(3), building.group(3))
            r.property_deductible = cents("$" + building.group(4))
        income = re.search(r"(\d+)-? ?Months\s*\n\s*loc# ?\d+ - Business Income", decl)
        r.business_income = f"{income.group(1)} months" if income else ""
        eb = re.search(r"Equipment Breakdown\s*\n\s*\$([\d,]+)\s*\n\s*\$([\d,]+)", decl)
        if eb:
            r.equipment_breakdown_limit, r.equipment_breakdown_deductible = cents("$" + eb.group(1)), cents("$" + eb.group(2))
        r.protective_safeguards = tuple(m.group(1).strip() for m in re.finditer(r"Protective Safeguards - ([^\n]+)", decl))
        units = re.search(r"\n(\d+)\s*\n\s*units", decl)
        r.units = int(units.group(1)) if units else None
        r.each_occurrence = _limit_after("Each Occurrence Limit", decl)
        r.general_aggregate = _limit_after("General Aggregate Limit", decl)
        r.products_aggregate = _limit_after("Products/Completed Operations Aggregate Limit", decl)
        r.personal_injury = _limit_after("Personal and Advertising Injury Limit", decl)
        r.hired_non_owned_auto = _limit_after("Hired and Non-owned Auto Liability", decl)
        r.forms = schedule_of_forms(text)
        titles = " ".join(f.title for f in r.forms)
        r.terrorism_excluded = bool(re.search(r"EXCLUSION OF CERTIFIED ACTS OF TERRORISM", titles))
        r.unit_interior = "single entity" if re.search(r"UNIT INTERIOR\s*[–-]?\s*SINGLE ENTITY", titles) else ""
        return r

    def check(self, r: PackagePolicy, context: ModelContext) -> list[Finding]:
        found: list[Finding] = []
        master = _spec_master(context)
        if master is not None and r.policy_number and r.policy_number not in master.numbers:
            found.append(Finding("number-not-in-specification", f"the master policy's number {r.policy_number} is neither the "
                                 f"specification's {master.number} nor an earlier one", Severity.CHECK))
        if master is not None and master.deductible_cents and r.property_deductible and r.property_deductible != master.deductible_cents:
            found.append(Finding("deductible-differs", f"the declarations' property deductible is {_money(r.property_deductible)}; the "
                                 f"specification has {_money(master.deductible_cents)}", Severity.CHECK))
        current = _current_mail_words(context)
        if r.mailing_address and current and not any(w.upper() in r.mailing_address.upper() for w in current):
            found.append(Finding("mailing-address-not-current", f"the policy mails the named insured at {r.mailing_address}, not the "
                                 "association's current address: renewal, cancellation, and claim notices go there. Ask the agent to "
                                 "change it", Severity.PROBLEM, "CIV 5810"))
        for guard in r.protective_safeguards:
            found.append(Finding("protective-safeguard", f"property coverage carries a protective safeguards condition ({guard}): the "
                                 "system must be kept in service and the carrier told of an impairment, or a loss can go unpaid",
                                 Severity.CHECK))
        if r.each_occurrence and r.each_occurrence < 50_000_000:
            found.append(Finding("gl-under-immunity-minimum", f"general liability {_money(r.each_occurrence)} per occurrence is under the "
                                 "$500,000 volunteer-director immunity minimum", Severity.PROBLEM, "CIV 5800(a)(4)"))
        if r.terrorism_excluded:
            found.append(Finding("terrorism-excluded", "certified acts of terrorism are excluded (the TRIA offer was not taken); fire "
                                 "following terrorism stays covered in California", Severity.INFO))
        if r.valuation:
            found.append(Finding("valuation", f"buildings {_money(r.building_limit)} on {r.valuation}, deductible "
                                 f"{_money(r.property_deductible)}; unit interiors {r.unit_interior or 'as the unit definition form says'}",
                                 Severity.INFO, "CIV 5300(b)(9)"))
        return found


# -- the crime policy ------------------------------------------------------------------------------------------------


_AGREEMENTS = ("Employee Theft", "Forgery Or Alteration", "Inside The Premises - Theft Of Money And Securities",
               "Inside The Premises - Robbery Or Safe Burglary Of Other Property", "Outside The Premises",
               "Computer And Funds Transfer Fraud", "Money Orders And Counterfeit Money")


@dataclass(frozen=True)
class Agreement:
    name: str
    limit: int | None
    deductible: int | None


@dataclass
class CrimePolicy:
    carrier: str = ""
    policy_number: str = ""
    term_start: date | None = None
    term_end: date | None = None
    premium: int | None = None
    named_insured: str = ""
    agreements: tuple[Agreement, ...] = ()
    mailing_address: str = ""   # where the insurer mails the named insured (CIV 5810)
    order_read: bool = True       # the limits print in a run after the agreements; they are read in the form's order


class CrimeDeclarationsModel(DocumentModel):
    kind = DocumentKind.INSURANCE_POLICY
    name = "crime-declarations"
    required = ("policy_number", "term_start", "term_end", "premium", "agreements")

    def parse(self, text: str, context: ModelContext) -> CrimePolicy | None:
        # The declarations page itself, not the schedule of forms that names it.
        start = next((m for m in re.finditer(r"COMMERCIAL\s+CRIME\s+POLICY\s+DECLARATIONS", text or "")
                      if re.search(r"In\s+return\s+for\s+the\s+payment|Coverage\s+Is\s+Written", text[m.end(): m.end() + 600])), None)
        if not start:
            return None
        decl = text[start.start(): start.start() + 5000]
        r = CrimePolicy(carrier="Manufacturers Alliance Insurance Company" if re.search(r"MANUFACTURERS ALLIANCE", decl) else "")
        number = re.search(r"\b(\d{6}-\d{2}-\d{2}-\d{2}-\d[A-Z])\b", decl)
        r.policy_number = number.group(1).replace("-", "") if number else ""
        dates = re.findall(r"\b(\d{2}-\d{2}-\d{4})\b", decl)
        if len(dates) >= 2:
            r.term_start, r.term_end = _mdy(dates[0]), _mdy(dates[1])
        premium = re.search(r"Premium\s+From:\s*[\d-]+\s+To:\s*[\d-]+\s+\$\s*([\d,]+\.\d\d)", " ".join((text or "").split()))
        r.premium = cents("$" + premium.group(1)) if premium else None
        run = re.search(r"deleted\.\s*((?:\$\s*[\d,]+\s*){2,14})", " ".join(decl.split()))
        amounts = [cents("$" + a) for a in re.findall(r"\$\s*([\d,]+)", run.group(1))] if run else []
        pairs = list(zip(amounts[0::2], amounts[1::2]))
        r.agreements = tuple(Agreement(name, limit, deductible) for name, (limit, deductible) in zip(_AGREEMENTS, pairs))
        r.named_insured = _named_insured(decl, context)
        r.mailing_address = _mailing(text, context)
        return r

    def check(self, r: CrimePolicy, context: ModelContext) -> list[Finding]:
        found: list[Finding] = []
        theft = next((a for a in r.agreements if a.name == "Employee Theft"), None)
        fraud = next((a for a in r.agreements if a.name == "Computer And Funds Transfer Fraud"), None)
        need = required_crime_limit(context)
        if theft and theft.limit and need:
            reserves, three_months, total = need
            severity = Severity.PROBLEM if theft.limit < total else Severity.INFO
            found.append(Finding("crime-limit-vs-5806", f"employee theft {_money(theft.limit)} against reserves {_money(reserves)} plus three "
                                 f"months' assessments {_money(three_months)} = {_money(total)}", severity, "CIV 5806(a)"))
        if fraud is None or not fraud.limit:
            found.append(Finding("no-funds-transfer-fraud", "no computer and funds transfer fraud limit was read", Severity.CHECK, "CIV 5806(b)"))
        elif need and fraud.limit < need[2]:
            found.append(Finding("funds-transfer-fraud-limit", f"computer and funds transfer fraud reads {_money(fraud.limit)} (in the form's "
                                 "order); CIV 5806 asks the coverage to include it: confirm its limit with the agent", Severity.CHECK, "CIV 5806(b)"))
        found += _mailing_findings(r.mailing_address, context, "the crime policy")
        return found


def required_crime_limit(context: ModelContext) -> tuple[int, int, int] | None:
    """Reserves (the stored ledger's reserve accounts) plus three months' assessments (the latest annual disclosure's monthly
    assessment times the units), in cents; None when either is not on disk."""
    if not context.data_dir:
        return None
    ledger = Path(context.data_dir) / "payhoa" / "ledger.db"
    if not ledger.is_file():
        return None
    with sqlite3.connect(ledger) as db:
        rows = db.execute("select account, balance from entries where account like '%Reserve%' and balance is not null "
                          "order by month desc, seq desc").fetchall()
    latest: dict[str, int] = {}
    for account, balance in rows:
        latest.setdefault(account, balance)
    reserves = sum(v for v in latest.values() if v and v > 0)
    units = None
    try:
        units = len(context.community.units()) if context.community is not None else None
    except Exception:
        units = None
    monthly = None
    readings = Path(context.data_dir) / "documents" / "readings.json"
    if readings.is_file():
        try:
            rows = json.loads(readings.read_text(encoding="utf-8"))
            items = rows.get("readings") if isinstance(rows, dict) else rows
            for row in items or []:
                fields = (row.get("reading") or row).get("fields") or {}
                if fields.get("monthly_assessment_cents"):
                    monthly = fields["monthly_assessment_cents"]
        except Exception:
            monthly = None
    if not reserves or not units or not monthly:
        return None
    three = monthly * units * 3
    return reserves, three, reserves + three


# -- the umbrella's evidence -----------------------------------------------------------------------------------------


@dataclass
class UmbrellaEvidence:
    carrier: str = ""
    program: str = ""
    evidence_number: str = ""
    term_start: date | None = None
    term_end: date | None = None
    each_occurrence: int | None = None
    aggregate: int | None = None
    retained_limit: int | None = None
    premium: int | None = None
    mailing_address: str = ""         # where the insurer mails the named insured (CIV 5810)


class UmbrellaEvidenceModel(DocumentModel):
    kind = DocumentKind.INSURANCE_POLICY
    name = "umbrella-evidence"
    required = ("carrier", "evidence_number", "term_start", "term_end", "each_occurrence")

    def parse(self, text: str, context: ModelContext) -> UmbrellaEvidence | None:
        if not re.search(r"Umbrella Program\s*\n\s*Evidence of Insurance|Evidence of Insurance and Purchasing Group", text or "", re.I):
            return None
        r = UmbrellaEvidence(carrier=(re.search(r"INSURER:\s*\n?\s*([A-Z][A-Za-z ]+Company)", text) or [None, ""])[1] if
                             re.search(r"INSURER:\s*\n?\s*([A-Z][A-Za-z ]+Company)", text) else
                             ("Federal Insurance Company" if "Federal Insurance" in text else ""),
                             program="McGowan Program Administrators" if "McGowan" in text else "")
        number = re.search(r"EVIDENCE NUMBER:\s*\n?\s*([\w-]+)", text)
        r.evidence_number = number.group(1) if number else ""
        period = re.search(r"(\d{2}/\d{2}/\d{4})\s+to\s+(\d{2}/\d{2}/\d{4})", text)
        if period:
            r.term_start, r.term_end = _mdy(period.group(1)), _mdy(period.group(2))
        limits = re.search(r"LIMIT:\s*\n?\s*\$([\d,]+)\s*/\s*\$([\d,]+)", text)
        if limits:
            r.each_occurrence, r.aggregate = cents("$" + limits.group(1)), cents("$" + limits.group(2))
        retained = re.search(r"Insured.s Retained Limit.*?\$([\d,]+)\s*\n\s*\$([\d,]+)\s*\n\s*\$([\d,]+)\s*\n\s*\$([\d,]+)", text, re.S)
        r.retained_limit = cents("$" + retained.group(3)) if retained else None
        premium = re.search(r"\$([\d,]+\.\d\d)\s*\n\s*Total Premium", text)
        r.premium = cents("$" + premium.group(1)) if premium else None
        r.mailing_address = _mailing(text, context)
        return r

    def check(self, r: UmbrellaEvidence, context: ModelContext) -> list[Finding]:
        found: list[Finding] = []
        if r.each_occurrence:
            found.append(Finding("umbrella-limit", f"umbrella {_money(r.each_occurrence)} per occurrence over the general liability: with "
                                 "$1,000,000 primary the association reaches $2,000,000 per occurrence", Severity.INFO, "CIV 5805(b)"))
        found += _mailing_findings(r.mailing_address, context, "the umbrella policy")
        return found


# -- the D&O policy --------------------------------------------------------------------------------------------------


def _form_values(text: str) -> dict[str, Any]:
    """A filled form's values read apart from its labels: the policy number (a hyphenated token with letters and digits
    printed at least twice), the limit (the largest whole-dollar amount of $100,000 or more), and the retention (the next
    whole-dollar amount after the limit, below it)."""
    out: dict[str, Any] = {}
    tokens = re.findall(r"\b(?=[A-Z0-9-]*\d)(?=[A-Z0-9-]*[A-Z])[A-Z0-9]+(?:-[A-Z0-9]+){2,}\b", text or "")
    repeated = [t for t in dict.fromkeys(tokens) if tokens.count(t) >= 2]
    if repeated:
        out["number"] = repeated[0]
    whole = [(m.start(), cents(m.group(0))) for m in re.finditer(r"\$[\d,]{4,}(?!\.\d)(?:\.00)?\b", text or "")]
    big = [v for _, v in whole if v is not None and v >= 10_000_000]
    if big:
        out["limit"] = max(big)
        at = next(i for i, (_, v) in enumerate(whole) if v == out["limit"])
        after = [v for _, v in whole[at + 1:] if v is not None and v < out["limit"]]
        if after:
            out["retention"] = after[0]
    return out


@dataclass
class DirectorsAndOfficersPolicy:
    carrier: str = ""
    program: str = ""
    policy_number: str = ""
    term_start: date | None = None
    term_end: date | None = None
    limit: int | None = None             # in the aggregate for the policy year
    retention: int | None = None
    premium: int | None = None
    prior_litigation: date | None = None
    claims_made: bool = False
    mailing_address: str = ""


class DirectorsAndOfficersModel(DocumentModel):
    """MG Skinner's D&O/Crime binder with Accredited Surety and Casualty's Community Association Select declarations."""

    kind = DocumentKind.INSURANCE_POLICY
    name = "dno-declarations"
    required = ("policy_number", "term_start", "term_end", "limit", "retention", "premium")

    def parse(self, text: str, context: ModelContext) -> DirectorsAndOfficersPolicy | None:
        if not re.search(r"DECLARATIONS\s*-\s*D&O|D&O/Crime Binder", text or ""):
            return None
        r = DirectorsAndOfficersPolicy(carrier=(re.search(r"Carrier:\s*([^\n]+)", text) or [None, ""])[1].strip()
                                       if re.search(r"Carrier:\s*([^\n]+)", text) else "",
                                       program="MG Skinner & Associates" if re.search(r"MG Skinner", text) else "")
        if not r.carrier and re.search(r"Accredited Surety and Casualty", text):
            r.carrier = "Accredited Surety and Casualty Company"
        number = re.search(r"POLICY NUMBER:\s*([\w-]*\d[\w-]*)", text) or re.search(r"Binder #:\s*([\w-]*\d[\w-]*)", text)
        r.policy_number = number.group(1) if number else ""
        # The declarations are a filled form: its text layer prints the labels in one block and the values in another,
        # so "POLICY NUMBER:" is followed by the next label ("PRODUCER:"). The number is then the hyphenated token with
        # digits that the page prints more than once (the header and the footer), and the limit the largest round amount.
        values = _form_values(text)
        if not r.policy_number:
            r.policy_number = values.get("number", "")
        period = re.search(r"Inception Date:\s*([\d/]+).*?Expiration Date:[_\s]*([\d/]+)", text, re.S) or \
            re.search(r"Effective from\s+([\d/]+)\s+to\s+([\d/]+)", text)
        if period:
            r.term_start, r.term_end = _mdy(period.group(1)), _mdy(period.group(2))
        limit = re.search(r"LIMIT OF LIABILITY:\s*\n?\s*\$([\d,]+)", text)
        r.limit = cents("$" + limit.group(1)) if limit else values.get("limit")
        retention = re.search(r"RETENTION:\s*\n?\s*\$([\d,]+)", text)
        r.retention = cents("$" + retention.group(1)) if retention else values.get("retention")
        premium = re.search(r"PREMIUM:\s*\n?\s*\$([\d,]+\.\d\d)", text) or re.search(r"Total Premium:\s*\$([\d,]+\.\d\d)", text)
        r.premium = cents("$" + premium.group(1)) if premium else None
        prior = re.search(r"PRIOR LITIGATION DATE:\s*\n?\s*([\d/]+)", text)
        r.prior_litigation = _mdy(prior.group(1)) if prior else None
        r.claims_made = bool(re.search(r"CLAIMS-MADE POLICY", text))
        mailing = re.search(r"Mailing\s*\n[^\n]*\n\s*([^\n]+)\n[^\n]*\n\s*([^\n]+\d{5})", text)
        r.mailing_address = f"{mailing.group(1).strip()}, {mailing.group(2).strip()}" if mailing else ""
        return r

    def check(self, r: DirectorsAndOfficersPolicy, context: ModelContext) -> list[Finding]:
        found: list[Finding] = []
        if r.limit is not None and r.limit < 50_000_000:
            found.append(Finding("dno-under-immunity-minimum", f"D&O {_money(r.limit)} is under the $500,000 volunteer-director immunity "
                                 "minimum", Severity.PROBLEM, "CIV 5800(a)(4)"))
        elif r.limit:
            found.append(Finding("dno-limit", f"D&O {_money(r.limit)} in the aggregate for the policy year meets the $500,000 minimum for "
                                 "volunteer-director immunity", Severity.INFO, "CIV 5800(a)(4)"))
        if r.claims_made:
            found.append(Finding("claims-made", "claims-made: a claim is covered only if made during the policy period and reported within "
                                 "90 days after it ends; a renewal must keep the prior litigation date"
                                 + (f" ({r.prior_litigation})" if r.prior_litigation else ""), Severity.CHECK))
        current = _current_mail_words(context)
        if r.mailing_address and current and not any(w.upper() in r.mailing_address.upper() for w in current):
            found.append(Finding("mailing-address-not-current", f"the D&O policy mails the association at {r.mailing_address}, not its "
                                 "current address", Severity.PROBLEM, "CIV 5810"))
        return found


for _model in (UmbrellaEvidenceModel(), CrimeDeclarationsModel(), DirectorsAndOfficersModel(), PackageDeclarationsModel()):
    register(_model, first=True)


__all__ = ["PackagePolicy", "PackageDeclarationsModel", "CrimePolicy", "CrimeDeclarationsModel", "Agreement", "UmbrellaEvidence",
           "UmbrellaEvidenceModel", "required_crime_limit", "Form"]
