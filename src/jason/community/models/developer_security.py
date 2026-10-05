"""The subdivider's securities to the association: DRE security agreements, subsidy agreements, surety bonds, releases.

When a phase is sold under a Department of Real Estate public report, the subdivider secures three obligations to the
association, each on a Commissioner's form held by an escrow holder:

- **Assessments on its unsold units** (10 CCR 2792.9): an Assessment Security Agreement (RE 643) and a surety bond
  (RE 643J), ordinarily six months of regular assessments, held until 80% of the phase's interests are conveyed.
- **A subsidy** (10 CCR 2792.10): when the subdivider pays part of the owners' share of costs (the gap between the
  budgeted assessment and the one it wants buyers to pay), a Subsidy Agreement, a Subsidy Security Agreement (RE 643E),
  and a bond (RE 643K); the subdivider delivers a monthly accounting.
- **Completion of common areas** (B&P 11018.5(a)(2); 10 CCR 2792.4): a Common Area Completion Security Agreement
  (RE 613) and a bond (RE 611), when common areas are not complete at the first sale; the board must consider
  enforcement if no notice of completion is recorded within 60 days of the completion date (2792.4; CC&R 3.7).

Release runs through the escrow holder: the subdivider demands return and certifies performance (paid, 80% conveyed,
completed lien-free); the association has 40 days to object in writing, or both sign joint instructions
(2792.9(b)(4), 2792.10). Every bond and security is a delivery the subdivider owed the association (2792.23(a)(10)).

``split_instruments`` cuts a compiled production (the developer's 2022 response to the association's 2792.23 demand)
into its instruments, so each reads with its own model.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from enum import Enum

from jason.community.base import NEVER, alternation, name_regex
from jason.community.document_models import (
    DocumentModel,
    Finding,
    ModelContext,
    Severity,
    dates_in,
    first,
    register,
    squash,
)
from jason.community.sources import SourceKind, first_sender_in
from jason.community.symbols import DocumentKind


class SecurityType(Enum):
    ASSESSMENT = "assessment"    # 10 CCR 2792.9: the subdivider's assessments on its units
    SUBSIDY = "subsidy"          # 10 CCR 2792.10: goods, services, or part of the owners' share of costs
    COMPLETION = "completion"    # B&P 11018.5(a)(2), 10 CCR 2792.4: completion of the common-area improvements


class ReleaseGround(Enum):
    PERFORMED = "performed"          # the subdivider performed (paid, delivered the subsidy)
    EIGHTY_PERCENT = "80% conveyed"  # 2792.9: 80% of the phase's interests conveyed
    COMPLETED = "completed"          # the improvements completed lien-free


REGULATION = {SecurityType.ASSESSMENT: "10 CCR 2792.9", SecurityType.SUBSIDY: "10 CCR 2792.10",
              SecurityType.COMPLETION: "B&P 11018.5(a)(2); 10 CCR 2792.4"}
FORMS = {"RE 643": SecurityType.ASSESSMENT, "RE 643J": SecurityType.ASSESSMENT, "RE 643E": SecurityType.SUBSIDY,
         "RE 643K": SecurityType.SUBSIDY, "RE 613": SecurityType.COMPLETION, "RE 611": SecurityType.COMPLETION}


@dataclass
class SecurityAgreement:
    form: str = ""                        # "RE 643", "RE 643E", "RE 613"
    security_type: SecurityType | None = None
    regulation: str = ""
    association: str = ""
    subdivider: str = ""
    subdivision: str = ""
    phase: int | None = None
    dre_file: str = ""
    escrow_holder: str = ""
    escrow_account: str = ""
    property: str = ""
    units: tuple[int, int] | None = None
    common_areas: tuple[int, ...] = ()    # "Association Common Area 8"
    made_on: date | None = None
    undated: bool = False                 # the "made this ___ day of ___" line is blank
    bond_amount_cents: int | None = None  # the security the agreement says the subdivider procured


@dataclass
class SubsidyAgreement:
    phase: int | None = None
    phases: tuple[int, ...] = ()
    association: str = ""
    declarant: str = ""
    made_on: date | None = None
    amended: bool = False
    units_in_phase: int | None = None
    target_assessment_cents: int | None = None   # the monthly assessment owners pay; the declarant pays the excess
    gap_cents: int | None = None                  # the budgeted assessment's excess over it
    maximum_total_cents: int | None = None
    term_start: str = ""
    term_end: str = ""
    due_day: int | None = None
    late_charge_percent: int | None = None
    monthly_statement: bool = False
    declaration_book_page: str = ""               # "20070920 0938"
    annexation_number: str = ""


@dataclass
class SuretyBond:
    bond_number: str = ""
    form: str = ""
    security_type: SecurityType | None = None
    regulation: str = ""
    principal: str = ""
    surety: str = ""
    obligee: str = ""
    penal_sum_cents: int | None = None
    premium_cents: int | None = None
    phase: int | None = None
    signed_on: date | None = None
    waives_2845: bool = False


@dataclass(frozen=True)
class ReleasedBond:
    number: str
    phase: int | None = None
    description: str = ""
    amount_cents: int | None = None


@dataclass
class BondRelease:
    dated: date | None = None
    sender: str = ""
    recipient: str = ""
    bonds: tuple[ReleasedBond, ...] = ()
    grounds: tuple[ReleaseGround, ...] = ()
    regulation: str = ""
    cites_resolution: bool = False
    by_association: bool = False       # the association's own letter or resolution, not the escrow holder's request


_ADDRESS = r"A\s*D\s*D\s*R\s*E\s*S\s*S"


def _clean(text: str) -> str:
    """OCR of a filled-in form: underscores between typed letters ("M_ys_t_iq_ue") and doubled spaces removed."""
    return squash(re.sub(r"_+", "", text or ""))


def _form(text: str) -> str:
    found = re.search(r"\bRE\s*(6\d\d)\s*\.?\s*([A-Z1]?)\b", text)
    if not found:
        return ""
    suffix = found.group(2).replace("1", "J") if found.group(1) == "643" else found.group(2)
    return f"RE {found.group(1)}{suffix}"


def _money(text: str) -> int | None:
    m = re.search(r"\$\s*([\d,]+)(?:\.(\d\d))?", text or "")
    return int(m.group(1).replace(",", "")) * 100 + int(m.group(2) or 0) if m else None


def _phase(text: str) -> int | None:
    m = re.search(r"\((?:DRE\s+)?Phase\s+(\d)\)|DRE Phase (\d)|PHASE\s+(\d)\b", text, re.I)
    return int(next(g for g in m.groups() if g)) if m else None


def _made_on(text: str) -> tuple[date | None, bool]:
    m = re.search(r"made (?:and entered into )?this\s+(.{0,70}?)\s*,?\s*(?:20\d\d|2\s*0\s*0\s*\w)?\s*,?\s*by and between", text, re.I)
    if not m:
        return None, False
    clause = m.group(0)
    day = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+day of\s+([A-Za-z~=._ -]{3,30}?)\s*,?\s*(20\d\d)", clause)
    if day:
        month = re.sub(r"[^A-Za-z]", "", day.group(2))
        from jason.community.invoices import parse_date

        parsed = parse_date(f"{month} {day.group(1)}, {day.group(3)}")
        if parsed:
            return parsed, False
    found = dates_in(clause)
    if found:
        return found[0], False
    return None, bool(re.search(r"this\s+_{2,}\s*day", clause))


def _dre_file(text: str) -> str:
    m = re.search(r"\b(\d{6}SA)(?:[-\s]*(F[O0]{2}|F00|A01|F00C00))?", text)
    return m.group(1) if m else ""


def _spec_report(context: ModelContext, file_number: str = "", phase: int | None = None):
    reports = getattr(context.community, "public_reports", lambda: ())() if context.community is not None else ()
    for report in reports or ():
        if file_number and report.file_number == file_number:
            return report
    for report in reports or ():
        if phase is not None and report.phase == phase:
            return report
    return None


def _own_name(context: ModelContext) -> str:
    """The association's name, as the specification gives it; empty without one."""
    return str(getattr(context.community, "name", "") or "")


def _developer(text: str, context: ModelContext) -> str:
    """A subdivider the specification pins, as the text prints it with its company form ("Oak Ridge Homes, LLC"); empty
    when it pins none or the text names none."""
    developers = getattr(context.community, "developers", tuple)() if context.community is not None else ()
    names = [name for developer in developers or () for name in (developer.name, *developer.names)]
    return first(rf"((?:{alternation(names)}),? (?:LLC|Inc\.?|L\.?P\.?))", text) if names else ""


def _named(text: str, context: ModelContext, *kinds: SourceKind, skip: str = "") -> str:
    """The counterparty of one of ``kinds`` the text names first, by its name in the specification's sender directory;
    one the directory does not list is not named: a miss."""
    senders = getattr(context.community, "senders", tuple)() if context.community is not None else ()
    found = first_sender_in(text, senders or (), *kinds, skip=(skip,) if skip else ())
    return found.name if found else ""


def _names_association(name: str, community) -> bool | None:
    """Whether ``name`` is the association's: it carries the name word as letters print it (``Community.name_pattern``)
    or the full name (``Community.name``). None when the specification gives neither: it cannot be told."""
    word = getattr(community, "name_pattern", str)() if community is not None else ""
    own = str(getattr(community, "name", "") or "")
    if not word and not own:
        return None
    patterns = [p for p in (word, name_regex(own) if own else "") if p]
    return any(re.search(p, name, re.I) for p in patterns)


def _obligee_check(name: str, context: ModelContext, what: str) -> list[Finding]:
    if name and _names_association(name, context.community) is False:
        return [Finding("not-the-association", f"the {what} names {name!r}, not the association", Severity.PROBLEM, "10 CCR 2792.23(a)(10)")]
    return []


class SecurityAgreementModel(DocumentModel):
    kind = DocumentKind.SECURITY_AGREEMENT
    name = "dre-security-agreement"
    required = ("form", "security_type", "subdivider", "dre_file", "escrow_holder")

    def parse(self, text: str, context: ModelContext) -> SecurityAgreement | None:
        flat = _clean(text)
        title = re.search(r"(ASSESSMENT|SUBSIDY|COMPLETION) SECURITY\s*AGREEMENT", flat, re.I)
        if not title:
            return None
        r = SecurityAgreement()
        r.form = _form(flat)
        r.security_type = {"ASSESSMENT": SecurityType.ASSESSMENT, "SUBSIDY": SecurityType.SUBSIDY,
                           "COMPLETION": SecurityType.COMPLETION}[title.group(1).upper()]
        reg = re.search(r"(?:Reg\.?|Regulation|Section)\s*(2792\.\s*\d+)", flat, re.I)
        r.regulation = f"10 CCR {reg.group(1).replace(' ', '')}" if reg else REGULATION[r.security_type]
        r.association = first(r"AME OF O\S*\s*ASSOC\S*\s+(.+?)\s+" + _ADDRESS, flat)
        r.subdivider = first(r"AME OF SUBDIVIDER\s+(.+?)\s+" + _ADDRESS, flat)
        r.subdivision = first(r"AME OF SUBDIVISION\s+(.+?)\s+(?:COUNTY|ESCROW\W*HOLDER|NAME OF ESCROW|SUBDIVISIONS)", flat)
        r.phase = _phase(r.subdivision) or _phase(flat[:600])
        r.dre_file = _dre_file(flat)
        r.escrow_holder = first(r"AME OF ESCROW\W*\s*HOLDER\s+(.+?)\s+(?:" + _ADDRESS + "|TYPE OF)", flat)
        r.escrow_account = first(r"\b(P-\d{6}-\d)\b", flat)
        r.property = first(r"real property described as:?\s+(.+?)\s*\(herein", flat)[:300]
        units = re.search(r"Units? (\d+) throu\w+ (\d+)", r.property or flat)
        r.units = (int(units.group(1)), int(units.group(2))) if units else None
        r.common_areas = tuple(int(n) for n in dict.fromkeys(re.findall(r"Association Common Area (\d+)", r.property or "")))
        r.made_on, r.undated = _made_on(flat)
        bond = re.search(r"surety bond in the sum of[^($]{0,120}\(\s*\$\s*([\d,]+(?:\.\d\d)?)", flat, re.I)
        r.bond_amount_cents = _money("$" + bond.group(1)) if bond else None
        return r

    def check(self, r: SecurityAgreement, context: ModelContext) -> list[Finding]:
        found = _obligee_check(r.association, context, "agreement")
        if r.undated:
            found.append(Finding("agreement-undated", "the date line is blank: this copy may be unsigned; the executed copy is the record",
                                 Severity.CHECK, "10 CCR 2792.23(a)(10)"))
        report = _spec_report(context, r.dre_file, r.phase)
        if report is not None and r.phase is not None and report.phase != r.phase:
            found.append(Finding("phase-file-mismatch", f"DRE file {r.dre_file} is phase {report.phase} in the specification, not phase {r.phase}",
                                 Severity.CHECK))
        if r.security_type is SecurityType.ASSESSMENT:
            found.append(Finding("assessment-release-rule", "held until 80% of the phase's interests are conveyed and the subdivider certifies it "
                                 "paid its assessments; the association has 40 days to object to a demand for release",
                                 Severity.INFO, "10 CCR 2792.9(b)(4)"))
        elif r.security_type is SecurityType.SUBSIDY:
            found.append(Finding("subsidy-accounting", "the subdivider owes the association a monthly accounting of the subsidy while it runs",
                                 Severity.INFO, "10 CCR 2792.10"))
        elif r.security_type is SecurityType.COMPLETION:
            found.append(Finding("completion-vote", "if no notice of completion is recorded within 60 days of the completion date, the board "
                                 "must consider enforcing the security, and 5% of the members may call a meeting on it",
                                 Severity.INFO, "10 CCR 2792.4; CC&R 3.7"))
        return found


class SubsidyAgreementModel(DocumentModel):
    kind = DocumentKind.SUBSIDY_AGREEMENT
    name = "subsidy-agreement"
    required = ("declarant", "term_start", "term_end")

    def parse(self, text: str, context: ModelContext) -> SubsidyAgreement | None:
        flat = _clean(text)
        if not re.search(r"SUBSIDY AGREEMENT", flat, re.I) or re.search(r"SUBSIDY SECURITY AGREEMENT AND", flat[:400], re.I):
            return None
        r = SubsidyAgreement()
        head = flat[:500]
        r.phases = tuple(int(n) for n in dict.fromkeys(re.findall(r"PHASES?\s+(\d)", head, re.I) + re.findall(r"\band (\d)\b", head[:200])))
        r.phase = r.phases[0] if len(r.phases) == 1 else None
        r.amended = bool(re.search(r"AMENDED", head, re.I))
        own = _own_name(context)
        r.association = own if own and re.search(name_regex(own), flat, re.I) else ""
        r.declarant = first(r"and\s+(.{5,80}?),\s+an?\s+(?:California|Delaware)\s+limited liability company\s*\(\"?(?:Declarant|Subdivider)", flat) or \
            _developer(flat, context)
        r.made_on, _ = _made_on(flat)
        units = re.search(r"consists of [a-z-]+ \((\d+)\) residential Units", flat, re.I)
        r.units_in_phase = int(units.group(1)) if units else None
        target = re.search(r"levied against the Unit exceeds \$\s?([\d,]+\.\d\d)", flat, re.I)
        r.target_assessment_cents = _money(target.group(0)) if target else None
        gap = re.search(r"\$\s?([\d,]+\.\d\d) greater than", flat)
        r.gap_cents = _money(gap.group(0)) if gap else None
        maximum = re.search(r"Maximum Total Subsidy[^$]{0,200}?(\$\s?[\d,]+(?:\.\d\d)?)", flat[flat.find("Term") if "Term" in flat else 0:], re.I)
        r.maximum_total_cents = _money(maximum.group(1)) if maximum else None
        r.term_start = first(r"shall commence (.{10,160}?),?\s*and shall continue", flat)
        r.term_end = first(r"shall continue until the (.{10,400}?)(?:\s+5\.|\s+Extension)", flat)
        due = re.search(r"on or before the (\d+)(?:st|nd|rd|th) calendar day of the month", flat)
        r.due_day = int(due.group(1)) if due else None
        late = re.search(r"late charge of (\d+)%", flat)
        r.late_charge_percent = int(late.group(1)) if late else None
        r.monthly_statement = bool(re.search(r"monthly (?:statement|accounting)|statement[^.]{0,80}each (?:calendar )?month", flat, re.I))
        book = re.search(r"Book\s+(\d{8}),?\s+at\s+Page\s+(\d{3,4})", flat)
        r.declaration_book_page = f"{book.group(1)} {book.group(2).zfill(4)}" if book else ""
        annex = re.search(r"Document No\.?\s*([0-9A-Za-z']{10,14})", flat)
        r.annexation_number = re.sub(r"\D", "", annex.group(1)) if annex else ""
        return r

    def check(self, r: SubsidyAgreement, context: ModelContext) -> list[Finding]:
        found = []
        ccrs = getattr(getattr(context.community, "ccrs", None), "recorder_number", "") if context.community is not None else ""
        if r.declaration_book_page and ccrs:
            book, page = r.declaration_book_page.split()
            if book + page != ccrs:
                found.append(Finding("declaration-citation", f"cites the declaration at Book {book} Page {page}; the specification pins {ccrs}",
                                     Severity.CHECK))
        if r.phase is not None and r.units_in_phase:
            reports = sorted(getattr(context.community, "public_reports", lambda: ())() or (), key=lambda p: p.phase) if context.community else []
            report = next((p for p in reports if p.phase == r.phase), None)
            # Watt's agreements count the units of every phase it had annexed so far (phase 4: 7 + 10 = 17).
            running = {start: sum(p.units for p in reports if start <= p.phase <= r.phase) for start in range(1, r.phase + 1)}
            if report is not None and report.units != r.units_in_phase:
                since = next((s for s, total in running.items() if total == r.units_in_phase), None)
                if since is not None:
                    found.append(Finding("phase-units-cumulative", f"the agreement's {r.units_in_phase} units are phases {since} through {r.phase} "
                                         "together, not this phase alone", Severity.INFO))
                else:
                    found.append(Finding("phase-units", f"the agreement counts {r.units_in_phase} units in phase {r.phase}; the specification's "
                                         f"public report has {report.units}", Severity.CHECK))
        if r.target_assessment_cents and r.phase is not None:
            report = _spec_report(context, phase=r.phase)
            if report is not None and report.assessment_cents and report.assessment_cents != r.target_assessment_cents:
                found.append(Finding("target-assessment", f"owners were to pay ${r.target_assessment_cents / 100:,.2f} a month; the public "
                                     f"report's assessment is ${report.assessment_cents / 100:,.2f}", Severity.INFO))
        found.append(Finding("subsidy-security", "a subsidy is secured by a Subsidy Security Agreement (RE 643E) and bond (RE 643K) held in "
                             "escrow, and the declarant owes a monthly accounting", Severity.INFO, "10 CCR 2792.10"))
        return found


class SuretyBondModel(DocumentModel):
    kind = DocumentKind.SURETY_BOND
    name = "dre-surety-bond"
    required = ("bond_number", "principal", "surety", "obligee", "penal_sum_cents")

    def parse(self, text: str, context: ModelContext) -> SuretyBond | None:
        flat = _clean(text)
        if not re.search(r"penal sum|SURETY BOND", flat, re.I) or not re.search(r"Obligee|firmly held and bound", flat, re.I):
            return None
        r = SuretyBond()
        own = flat.upper().find("SURETY BOND")
        if own > 0:
            flat = flat[own:]
        number = re.search(r"[B8J][O0I]N[DO0]\s*N(?:UMBER|[O0]\.?)\s*#?\s*(?:PREMI\w*\s*)?(\d{6,10})", flat, re.I) or re.search(r"\bBOND\s*#\s*(\d{6,10})", flat, re.I) \
            or re.search(r"Bond\s*#\s*(\d{6,10})", context.name)
        r.bond_number = number.group(1) if number else ""
        if number and number.string is flat and number.start() > 600:
            # A garbled copy of another bond can come first; this bond's facts follow its own number.
            flat = flat[number.start() - 400:]
        title_at = max(flat.upper().find("SURETY BOND"), 0)
        r.form = _form(flat[title_at: title_at + 300]) or _form(flat)
        reg = re.search(r"(?:Regulation|Section)\s*(2792\.\s*(?:\d+|I[O0]|\][O0]))", flat, re.I)
        regulation = re.sub(r"[I\]][O0]", "10", reg.group(1).replace(" ", "")) if reg else ""
        r.regulation = f"10 CCR {regulation}" if regulation else ""
        r.security_type = FORMS.get(r.form) or {"2792.9": SecurityType.ASSESSMENT, "2792.10": SecurityType.SUBSIDY,
                                                 "2792.4": SecurityType.COMPLETION}.get(regulation)
        r.principal = first(r"That we,?\s+(.+?)\s*(?:\(Name of Subdivider\)\s*)?,?\s*as Principal", flat)
        r.principal = re.sub(r"\s*\(Name of Subdivider\)", "", r.principal)
        r.surety = first(r"as Principal,?\s+and\s+(.+?)\s*(?:BOND NUMBER|\(Name ?of ?Surety\)|,\s*a corporation)", flat)
        r.surety = re.sub(r"\s*(?:BOND NUMBER.*|SUBDIVISIONS.*|\(Name of.*)$", "", r.surety)
        r.obligee = first(r"bound unto\s+(.+?)\s*\(Name ?of ?Association", flat)
        at = flat.find("penal sum of")
        near = flat[at: at + 320] if at >= 0 else ""
        penal = re.search(r"[DP]ollars\s*\(\s*[$\u00a7S]\s*([\d,]+\.\d\d)", near)
        r.penal_sum_cents = _money("$" + penal.group(1)) if penal else None
        # The sum is written in words and figures; a figure OCR broke ("$ 949.00" for nineteen thousand) is not the sum.
        words = re.sub(r"[^a-z]", "", first(r"penal sum of\s+(.{0,90}?)[DP]ollars", flat).lower())
        if r.penal_sum_cents is not None and re.search(r"t\w?ous|housand", words) and r.penal_sum_cents < 100000:
            r.penal_sum_cents = None
        premium = re.search(r"PREMIUM\s*(?:\d{6,10}\s*)?\$\s?([\d,]+\.\d\d)", flat)
        r.premium_cents = _money("$" + premium.group(1)) if premium else None
        # The bond's own heading names its phase; text before the title may be the previous instrument's.
        r.phase = _phase(flat[title_at: title_at + 400])
        signed = re.search(r"this\s+(\d{1,2})(?:st|nd|rd|th)?\s+day of\s+([A-Za-z]+)\s*,?\s*(\d{4})", flat)
        if signed:
            from jason.community.invoices import parse_date

            r.signed_on = parse_date(f"{signed.group(2)} {signed.group(1)}, {signed.group(3)}")
        r.waives_2845 = "2845" in flat
        return r

    def check(self, r: SuretyBond, context: ModelContext) -> list[Finding]:
        found = _obligee_check(r.obligee, context, "bond")
        if r.security_type is SecurityType.ASSESSMENT and r.penal_sum_cents and r.phase is not None:
            report = _spec_report(context, phase=r.phase)
            if report is not None and report.assessment_cents:
                six_months = report.units * report.assessment_cents * 6
                if r.penal_sum_cents < six_months:
                    found.append(Finding("below-six-months", f"the bond's ${r.penal_sum_cents / 100:,.2f} is less than six months of assessments on the "
                                         f"phase's {report.units} units (${six_months / 100:,.2f}); the regulation ordinarily asks six months",
                                         Severity.CHECK, "10 CCR 2792.9"))
        if not r.waives_2845:
            found.append(Finding("no-2845-waiver", "the text does not show the surety's waiver under Civil Code 2845", Severity.CHECK))
        found.append(Finding("keep-until-released", "keep the bond with its agreement until a release is on file", Severity.INFO,
                             "10 CCR 2792.23(a)(10)"))
        return found


class BondReleaseModel(DocumentModel):
    kind = DocumentKind.BOND_RELEASE
    name = "bond-release"
    required = ("dated", "bonds")

    def parse(self, text: str, context: ModelContext) -> BondRelease | None:
        flat = _clean(text)
        if not re.search(r"releas", flat, re.I) or not re.search(r"\bbond", flat, re.I):
            return None
        r = BondRelease()
        found = dates_in(flat[:400])
        r.dated = found[0] if found else None
        own = _own_name(context)
        r.by_association = bool(own and re.search(rf"^\s*{name_regex(own)}", text or "", re.I)) or bool(re.search(r"SPECIAL RESOLUTION", flat[:200]))
        # The escrow holder that asks for the release, and the surety or escrow holder it writes to, are the title
        # companies and insurers the sender directory lists, each by its name there.
        r.sender = own if r.by_association else _named(flat, context, SourceKind.TITLE_ESCROW)
        r.recipient = _named(flat[40:], context, SourceKind.INSURER, SourceKind.TITLE_ESCROW, skip=r.sender)
        bonds: dict[str, ReleasedBond] = {}
        for m in re.finditer(r"(?:Phase\s*(\d)\s+)?(\d{7,10})\s+([\w ]{3,40}?Bond)\s+\$\s?([\d,]+)", flat):
            bonds[m.group(2)] = ReleasedBond(m.group(2), int(m.group(1)) if m.group(1) else _phase(flat), squash(m.group(3)), _money("$" + m.group(4)))
        for m in re.finditer(r"Bond\s*(?:No\.?|#|Number)?\s*\(?(?:No\.\s*)?(\d{7,10})", flat, re.I):
            bonds.setdefault(m.group(1), ReleasedBond(m.group(1), _phase(flat)))
        r.bonds = tuple(bonds.values())
        grounds = []
        if re.search(r"80\s*(?:percent|%)", flat, re.I):
            grounds.append(ReleaseGround.EIGHTY_PERCENT)
        if re.search(r"(?:faithfully|satisfactorily) perform|fulfilled its obligations|paid all", flat, re.I):
            grounds.append(ReleaseGround.PERFORMED)
        if re.search(r"completed? (?:free of|lien-free)|notice of completion", flat, re.I):
            grounds.append(ReleaseGround.COMPLETED)
        r.grounds = tuple(grounds)
        reg = re.findall(r"(?:Regulation|Section)\s*(2792\.\d+)", flat)
        r.regulation = ", ".join(f"10 CCR {x}" for x in dict.fromkeys(reg))
        r.cites_resolution = bool(re.search(r"Resolution", flat, re.I))
        return r

    def check(self, r: BondRelease, context: ModelContext) -> list[Finding]:
        found = []
        if not r.cites_resolution and not r.by_association:
            found.append(Finding("no-resolution", "the release does not cite a board resolution; a release is a board action at an open meeting "
                                 "recorded in the minutes", Severity.CHECK, "CIV 4930, 5200(a)(8)"))
        if not r.grounds:
            found.append(Finding("no-grounds", "the release states no ground (performance, 80% conveyed, completion)", Severity.CHECK,
                                 "10 CCR 2792.9(b)(4), 2792.10"))
        found.append(Finding("keep-release", "keep the release with the bond and the resolution that authorized it", Severity.INFO,
                             "10 CCR 2792.23(a)(10)"))
        return found


# A compiled production ("Watt - Response to demand for production of documents 2792.23") holds many instruments.
def _starts(community=None) -> re.Pattern[str]:
    """Where an instrument's title begins. A subsidy agreement's title may lead with the project's name word as letters
    print it (``Community.name_pattern``, "OAK RIDGE SUBSIDY AGREEMENT - PHASE 3"); with none set, the title alone."""
    word = getattr(community, "name_pattern", str)() if community is not None else ""
    return re.compile(
        r"(?:STATE OF CALIFORNIA\s+)?(?:DEPARTMENT OF REAL ESTATE\s+)?SURETY BOND\s*\(\s*REG|"
        r"(?:ASSESSMENT|SUBSIDY|COMPLETION) SECURITY\s*AGREEMENT\s+AND|"
        rf"(?:FIRST AMENDED\s+)?(?:(?:{word or NEVER})\s+)?(?:OPERATING\s+)?SUBSIDY AGREEMENT\s*-?\s*PHASE", re.I)


def split_instruments(text: str, community=None) -> list[tuple[DocumentKind, str]]:
    """Each instrument in a compiled production, with the kind its heading names, in order. ``community`` lends the
    project's name word a subsidy agreement's title may lead with."""
    flat = _clean(text)
    starts_re = _starts(community)
    # A form's title repeats at the head of its later pages; an instrument starts where the title is followed by the parties'
    # block (an agreement) or by the bond's recital (a bond), or at a subsidy agreement's own title.
    starts = []
    titled = [m.start() for m in starts_re.finditer(flat)]
    for m in re.finditer(r"KNOW ALL MEN BY THESE PRESENTS", flat):
        # A bond whose title OCR lost; a power of attorney opens the same way but names no principal.
        if re.search(r"as\s+P\S*ipal", flat[m.start(): m.start() + 500]) and not any(0 <= m.start() - s <= 600 for s in titled):
            starts.append(m.start())
    for m in starts_re.finditer(flat):
        after = flat[m.start(): m.start() + 400]
        if re.search(r"SECURITY\s*AGREEMENT", m.group(0), re.I) and not re.search(r"AME OF O\S*\s*ASSOC|OWNERS\s*ASSOC", after, re.I):
            continue
        if re.search(r"SUBSIDY AGREEMENT\s*-?\s*PHASE", m.group(0), re.I) and not re.search(r"Parties to Agreement|Association and|ASSOCIATION AND", after, re.I):
            continue
        starts.append(m.start())
    starts.sort()
    pieces = []
    for n, start in enumerate(starts):
        end = starts[n + 1] if n + 1 < len(starts) else len(flat)
        body = flat[max(0, start - 200): end]   # a form's header fields can precede its title
        head = flat[start: start + 120].upper()
        kind = DocumentKind.SURETY_BOND if "SURETY BOND" in head or "KNOW ALL MEN" in head else \
            DocumentKind.SECURITY_AGREEMENT if "SECURITY" in head else DocumentKind.SUBSIDY_AGREEMENT
        pieces.append((kind, body))
    return pieces


register(SecurityAgreementModel())
register(SubsidyAgreementModel())
register(SuretyBondModel())
register(BondReleaseModel())

__all__ = ["SecurityType", "ReleaseGround", "SecurityAgreement", "SubsidyAgreement", "SuretyBond", "ReleasedBond", "BondRelease",
           "SecurityAgreementModel", "SubsidyAgreementModel", "SuretyBondModel", "BondReleaseModel", "split_instruments", "REGULATION"]
