"""Recorded liens: the association's notice of delinquent assessment, a contractor's mechanics lien and its release, and
the bond that releases a mechanics lien.

The law shapes each. The notice of delinquent assessment states the amount, a legal description of the separate
interest, and the record owner's name (CIV 5675(a)); the itemized statement is recorded with it (5675(b)); it names the
trustee and the trustee's address for a nonjudicial foreclosure (5675(c)); the person the declaration or the association
designates signs it, or the president (5675(d)); and a copy goes by certified mail to the owners within 10 days of
recording (5675(e)). Only the board decides to record it, by majority vote in an open meeting, in the minutes (5673);
the pre-lien notice comes at least 30 days before (5660). Paid, the association records a release within 21 days
(5685(a)). Under $1,800 of assessments, and not over 12 months delinquent, the lien cannot be foreclosed (5720(b)).

A mechanics lien is signed and verified by the claimant and states the demand, the owner or reputed owner, the kind of
work, who hired the claimant, the site, the claimant's address, a proof of service, and the statutory notice (CIV
8416(a)); the claimant must sue within 90 days of recording or the lien expires (8460(a)). A release bond is 125 percent
of the claim, by an admitted surety (8424(b)); the claimant then has six months after notice to sue on the bond (8424(d)).

``AssessmentLien`` reads a collections firm's "Notice of Claim of Lien for Delinquent Assessments". ``MechanicsLien``
reads a claimant's counsel's "Notice and Claim of Mechanic's Lien" (and a release filed in the same file).
``LienReleaseBond`` reads a surety's "Bond for Release of Mechanic's Lien". No record keeps an owner's name.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum

from jason.community.document_models import (
    DocumentModel,
    Finding,
    ModelContext,
    Severity,
    cents,
    date_after,
    dates_in,
    first,
    register,
    squash,
)
from jason.community.models.legal_shared import (
    FORECLOSURE_FLOOR,
    INTEREST_CAP_PERCENT,
    LATE_CHARGE_PERCENT,
    LIEN_MAIL_DAYS,
    PRE_LIEN_DAYS,
    RELEASE_DAYS,
    ChargeKind,
    apns_in,
    building_number,
    building_of,
    charge_kind,
    days_between,
    known_parcels,
    site_address,
    site_addresses,
    words_to_cents,
)
from jason.community.reviews import AS_OF
from jason.community.sources import SourceKind, sender_name
from jason.community.symbols import Building, DocumentKind

MECHANICS_ACTION_DAYS = 90       # CIV 8460(a)
BOND_PERCENT = 125               # CIV 8424(b)


class LienInstrument(Enum):
    ASSESSMENT_LIEN = "notice of delinquent assessment"
    MECHANICS_LIEN = "claim of mechanics lien"
    MECHANICS_RELEASE = "release of mechanics lien"
    RELEASE_BOND = "mechanics lien release bond"


@dataclass(frozen=True)
class LienItem:
    description: str
    kind: ChargeKind
    amount: int                  # cents
    months: int | None = None    # installments the line covers ("5 @ $320.00/month")
    rate: int | None = None      # cents per installment


_RECORDED = re.compile(r"(?:Doc(?:ument)?\s*#?\s*:?|a~,)\s*(\d{12})\b")


def _recording(text: str, name: str) -> tuple[str, date | None, bool]:
    """The recorder's document number and date from the stamp; the file name's number when the stamp did not OCR."""
    head = text[:1500]
    number = first(_RECORDED, head) or first(r"\b(20\d{10})\b", head)
    from_name = False
    if not number:
        number, from_name = first(r"\b((?:19|20)\d{10})\b", name), True
    recorded = None
    if number:
        m = re.search(number, head)
        window = head[m.end(): m.end() + 80] if m else ""
        found = dates_in(window) or dates_in(head[max(0, (m.start() if m else 0) - 80): (m.start() if m else 0)])
        recorded = found[0] if found else None
        if recorded is None and len(number) == 12:
            try:
                recorded = date(int(number[:4]), int(number[4:6]), int(number[6:8]))
            except ValueError:
                recorded = None
    return number, recorded, from_name and bool(number)


def _name_number(number: str, context: ModelContext) -> list[Finding]:
    """A file named for one recording number that carries another (a release filed with the lien it followed)."""
    named = first(r"\b((?:19|20)\d{10})\b", context.name)
    if named and number and named != number:
        return [Finding("file-name-number-differs", f"the file name carries document {named}; the recorder's stamp in the text reads "
                        f"{number}", Severity.CHECK)]
    return []


@dataclass
class AssessmentLien:
    instrument: LienInstrument = LienInstrument.ASSESSMENT_LIEN
    title: str = ""
    document_number: str = ""
    document_number_from_name: bool = False
    recorded: date | None = None
    recording_fee: int | None = None
    requested_by: str = ""                   # who asked for recording: a listed law firm by its directory name, else as printed
    association: str = ""
    association_address: str = ""
    declaration: str = ""                    # the declaration it relies on, as recorded ("Book 20070920, Page 937")
    property_address: str = ""
    building: Building | None = None         # from the legal description
    unit: str = ""
    apn: str = ""
    legal_description: bool = False
    names_owner: bool = False
    amount: int | None = None                # cents
    as_of: date | None = None
    items: tuple[LienItem, ...] = ()
    items_total: int | None = None
    itemized_statement: bool = False
    delinquent_assessments: int | None = None
    months_delinquent: int | None = None
    interest_rate_percent: float | None = None
    late_charge_percent: float | None = None
    trustee: str = ""
    trustee_address: str = ""
    elects_to_sell: bool = False
    signer_capacity: str = ""                # "Attorney and Authorized Agent", "President"
    signed_by_agent: bool = False
    dated: date | None = None
    mailing_statement: bool = False          # the 5675(e) statement that a copy will be mailed within ten days
    notarized: bool = False


# An item starts with one of these words (never the matter line above the items, which names the owner).
_ITEM = re.compile(r"(\b(?:Unpaid|Association(?:'s)?|Interest|Late|Collection|Attorney(?:'s)?|Admin\w*|Recording|Pre-?lien|Costs?)\b"
                   r"[^$]{3,400}?)\$\s*'?\s*\n?\s*([\d,]+\s?\.\s?\d\d)")


def _items(statement: str) -> tuple[LienItem, ...]:
    items = []
    statement = statement[statement.find("Unpaid"):] if "Unpaid" in statement else statement
    for m in _ITEM.finditer(statement):
        desc = squash(re.sub(r"[.\s]{4,}", " ", m.group(1)))
        if re.match(r"total", desc, re.I) or re.search(r"Total Now Due", desc, re.I):
            continue
        amount = cents(m.group(2).replace(" ", "")) or 0
        kind = charge_kind(desc)
        if re.search(r"unpaid and delinquent (?:balance of )?regular assessment|special assessment", desc, re.I):
            kind = ChargeKind.ASSESSMENT
        months = re.search(r"\(\s*(\d+)\s*@\s*\$?([\d,]+\.\d\d)\s*/\s*month", desc)
        items.append(LienItem(re.split(r"\s\(\s*\d+\s*@", desc)[0][:160], kind, amount,
                              int(months.group(1)) if months else None, cents(months.group(2)) if months else None))
    return tuple(items)


class AssessmentLienModel(DocumentModel):
    kind = DocumentKind.RECORDED_LIEN
    name = "notice-of-delinquent-assessment"
    required = ("document_number", "recorded", "amount", "property_address", "trustee", "signer_capacity")

    def parse(self, text: str, context: ModelContext) -> AssessmentLien | None:
        if not re.search(r"(?:claim of )?lien for delinquent assessments?|notice of delinquent assessment", text or "", re.I) or \
                re.search(r"mechanic'?s lien", text or "", re.I):
            return None
        flat = squash(text)
        r = AssessmentLien()
        r.title = first(r"(NOTICE OF (?:CLAIM OF )?(?:LIEN FOR )?DELINQUENT ASSESSMENTS?)", text, flags=0) or "Notice of Delinquent Assessment"
        r.document_number, r.recorded, r.document_number_from_name = _recording(text, context.name)
        fee = first(r"Fees\s*\n?\s*(\$[\d,]+\.\d\d)", text[:800])
        r.recording_fee = cents(fee) if fee else None
        # A law firm the sender directory lists, by its name there; any other requester as the recorder's block prints it.
        r.requested_by = sender_name(text[:1200], context.community, SourceKind.LAW_FIRM) or \
            first(r"Recording Requested by[^\n]*\n(?:[^\n]*\n){0,3}?\s*([A-Z][A-Z&,. ]{5,})\n", text)
        r.association = first(r"that (MYSTIQUE COMMUNITY ASSOCIATION)", flat) or ("Mystique Community Association" if "MYSTIQUE" in text.upper() else "")
        r.association_address = first(r"whose address for the purpose of all matters addressed herein is ((?:[^,]+,){2,3}[^,]+?\d{5})", flat)
        r.declaration = first(r"Declaration[^.]{0,200}?recorded on [^,]+, \d{4}, in (Book \d+, at Page \d+)", flat)
        exhibit_a = text[text.find('EXHIBIT "A"'):] if 'EXHIBIT "A"' in text else text
        r.legal_description = bool(re.search(r"PARCEL ONE|Condominium Plan|as depicted, described and defined", flat, re.I))
        unit = re.search(r"Unit\s+(\d+),?\s+in\s+Building\s+(\d+)", exhibit_a, re.I)
        if unit:
            r.unit, r.building = unit.group(1), building_number(unit.group(2))
        apns = apns_in(text)
        r.apn = apns[0] if apns else ""
        statement = text[text.find('EXHIBIT "B"'):] if 'EXHIBIT "B"' in text else ""
        r.property_address = site_address(statement) or site_address(text)
        if r.building is None:
            r.building = building_of(context, r.property_address)
        r.names_owner = bool(re.search(r"amounts due to the Association from [A-Z]", flat)) or bool(re.search(r"Liens\s*-\s*[A-Z][a-z]+", statement))
        r.amount = cents(first(r"aggregate total amount of (\$[\d,]+\.\d\d)", flat)) if re.search(r"aggregate total amount of \$", flat) else None
        r.as_of = date_after(r"AMOUNT DUE\s*AS OF", statement, window=40) or date_after(r"as of", first(r"aggregate total amount of[^.]{0,80}", flat, 0))
        r.itemized_statement = bool(re.search(r"ITEMIZED STATEMENT", statement))
        if statement:
            r.items = _items(re.sub(r"@\s*\$", "@ ", squash(statement)))
            r.items_total = sum(i.amount for i in r.items) if r.items else None
            total_now = first(r"Total Now Due[ .]*\$?\s*'?\s*([\d,]+\.\d\d)", squash(statement))
            if r.amount is None and total_now:
                r.amount = cents(total_now)
            assessments = [i for i in r.items if i.kind is ChargeKind.ASSESSMENT]
            r.delinquent_assessments = sum(i.amount for i in assessments) if assessments else None
            months = [i.months for i in assessments if i.months]
            r.months_delinquent = sum(months) + sum(1 for i in assessments if not i.months) if assessments else None
        rate = first(r"Interest\s*\(?@\s*(\d+(?:\.\d+)?)\s*%", flat)
        r.interest_rate_percent = float(rate) if rate else None
        late = first(r"late charges?, at (\d+(?:\.\d+)?)\s*%", flat)
        r.late_charge_percent = float(late) if late else None
        r.trustee = first(r"designates ([A-Z][A-Z0-9 &,.'-]+?)(?:, a [A-Za-z ]+?(?:corporation|company|partnership))?, whose address", flat)
        r.trustee_address = first(r"designates [^.]+?, whose address is ((?:[^,]+,){2,3}[^,]+?\d{5})", flat)
        r.elects_to_sell = bool(re.search(r"hereby elects to sell", flat, re.I))
        r.signer_capacity = first(r"\n\s*(Attorney and Authorized Agent|Authorized Agent|President|Secretary|Managing Agent)\s*\n", text)
        r.signed_by_agent = bool(r.signer_capacity) and r.signer_capacity != "President"
        r.dated = date_after(r"Dated:", text, window=30)
        if r.dated is None:
            month = first(r"Dated:\s*([A-Z][a-z]+)[_\s]", text)
            if month and r.as_of and month.lower().startswith(r.as_of.strftime("%B").lower()[:3]):
                r.dated = r.as_of
        r.mailing_statement = bool(re.search(r"5675\s*\(e\)", flat)) or bool(re.search(r"within ten days of recording", flat, re.I))
        r.notarized = bool(re.search(r"NOTARIAL ACKNOWLEDGMENT|Notary Public", text))
        return r

    def check(self, r: AssessmentLien, context: ModelContext) -> list[Finding]:
        found: list[Finding] = []
        if not r.legal_description:
            found.append(Finding("no-legal-description", "the text carries no legal description of the separate interest", Severity.PROBLEM, "CIV 5675(a)"))
        if not r.names_owner:
            found.append(Finding("record-owner-not-named", "the text does not name the record owner", Severity.CHECK, "CIV 5675(a)"))
        if not r.itemized_statement:
            found.append(Finding("no-itemized-statement", "the itemized statement of charges is not recorded with the notice in this text",
                                 Severity.PROBLEM, "CIV 5675(b)"))
        if not r.trustee:
            found.append(Finding("no-trustee", "the notice names no trustee; without one the lien cannot be enforced by nonjudicial "
                                 "foreclosure", Severity.CHECK, "CIV 5675(c)"))
        elif not r.trustee_address:
            found.append(Finding("no-trustee-address", f"the notice names {r.trustee} as trustee without an address", Severity.CHECK, "CIV 5675(c)"))
        if r.signed_by_agent:
            found.append(Finding("signed-by-agent", f"signed by the association's {r.signer_capacity.lower()}; confirm the declaration or "
                                 "the board designated that person to sign", Severity.CHECK, "CIV 5675(d)"))
        if r.recorded:
            found.append(Finding("mail-copy", f"a copy of the recorded notice must go by certified mail to every owner of record by "
                                 f"{r.recorded + timedelta(days=LIEN_MAIL_DAYS)}; keep the receipts", Severity.CHECK, "CIV 5675(e)"))
            found.append(Finding("pre-lien-notice", f"the pre-lien notice must have gone by certified mail by "
                                 f"{r.recorded - timedelta(days=PRE_LIEN_DAYS)} ({PRE_LIEN_DAYS} days before recording)", Severity.CHECK, "CIV 5660"))
        found.append(Finding("board-vote", "only the board may decide to record the lien, by majority vote in an open meeting, with the "
                             "vote in the minutes; confirm the minutes", Severity.CHECK, "CIV 5673"))
        if r.amount is not None and r.items_total is not None and r.items_total != r.amount:
            found.append(Finding("items-disagree", f"the itemized lines add to ${r.items_total / 100:,.2f}; the notice claims "
                                 f"${r.amount / 100:,.2f}", Severity.PROBLEM, "CIV 5675(a), (b)"))
        if r.interest_rate_percent and r.interest_rate_percent > INTEREST_CAP_PERCENT:
            found.append(Finding("interest-rate-over-cap", f"interest at {r.interest_rate_percent:g}% a year", Severity.PROBLEM, "CIV 5650(b)(3)"))
        if r.late_charge_percent and r.late_charge_percent > LATE_CHARGE_PERCENT:
            found.append(Finding("late-charge-rate-over-cap", f"late charges at {r.late_charge_percent:g}%", Severity.PROBLEM, "CIV 5650(b)(2)"))
        if r.delinquent_assessments is not None:
            if r.delinquent_assessments < FORECLOSURE_FLOOR and not (r.months_delinquent and r.months_delinquent > 12):
                found.append(Finding("not-foreclosable", f"${r.delinquent_assessments / 100:,.2f} of assessments, under $1,800 and not over 12 "
                                     "months delinquent: the lien may not be foreclosed", Severity.INFO, "CIV 5720(b)"))
            else:
                found.append(Finding("foreclosable", f"${r.delinquent_assessments / 100:,.2f} of assessments secured"
                                     + (f" over {r.months_delinquent} months" if r.months_delinquent else "")
                                     + "; the $1,800 or 12-month floor for foreclosure is met", Severity.INFO, "CIV 5720(b)"))
        if r.apn:
            parcels = known_parcels(context)
            if parcels and r.apn not in parcels:
                found.append(Finding("parcel-not-in-spec", f"APN {r.apn} is not one of the association's parcels in the specification", Severity.CHECK))
        spec_building = building_of(context, r.property_address)
        if spec_building and r.building and spec_building != r.building:
            found.append(Finding("building-disagrees", f"the legal description places the unit in building {r.building.value}; the "
                                 f"specification places {r.property_address} in building {spec_building.value}", Severity.CHECK))
        found += _name_number(r.document_number, context)
        if r.document_number_from_name:
            found.append(Finding("document-number-from-name", "the recorder's stamp did not read; the document number comes from the file name",
                                 Severity.CHECK))
        lag = days_between(r.dated, r.recorded)
        if lag is not None and lag > 30:
            found.append(Finding("recorded-late", f"recorded {lag} days after it was signed", Severity.INFO))
        found.append(Finding("release-on-payment", f"when the sums in the notice are paid, record a release within {RELEASE_DAYS} days and "
                             "give the owner a copy", Severity.INFO, "CIV 5685(a)"))
        return found


@dataclass(frozen=True)
class LienRelease:
    released_number: str
    released_recorded: date | None
    dated: date | None
    served: bool


@dataclass
class MechanicsLien:
    instrument: LienInstrument = LienInstrument.MECHANICS_LIEN
    document_number: str = ""
    document_number_from_name: bool = False
    recorded: date | None = None
    claimant: str = ""
    claimant_address: str = ""
    attorney_firm: str = ""
    amount: int | None = None
    work: str = ""                       # "lumber and building materials"
    hired_by: str = ""
    prime_contractor: str = ""
    reputed_owner: str = ""              # as the lien names it (an entity here; a person's name is not kept)
    reputed_owner_is_person: bool = False
    properties: tuple[str, ...] = ()
    apns: tuple[str, ...] = ()
    buildings: tuple[Building, ...] = ()
    statutory_notice: bool = False
    verified: bool = False
    proof_of_service: bool = False
    service_method: str = ""
    dated: date | None = None
    releases: tuple[LienRelease, ...] = ()


_ENTITY = re.compile(r"\b(?:Inc\.?|LLC|L\.L\.C\.|Corporation|Company|Co\.|LP|LLP|Association|Trust)\b", re.I)


@AS_OF.check("lien-action-deadline", MechanicsLien, fields=("recorded",))
def lien_action_deadline(r, as_of: date, _facts=None) -> list[Finding]:
    """As of a date: whether the claimant's time to sue on the lien has run."""
    if not r.recorded:
        return []
    deadline = r.recorded + timedelta(days=MECHANICS_ACTION_DAYS)
    if as_of > deadline:
        return [Finding("action-deadline-passed", f"the claimant had to sue by {deadline}; without a recorded lis pendens or "
                        "credit extension the lien has expired and is unenforceable (it stays of record)", Severity.INFO,
                        "CIV 8460(a), 8461")]
    return [Finding("action-deadline", f"the claimant must sue to enforce by {deadline}", Severity.CHECK, "CIV 8460(a)")]


class MechanicsLienModel(DocumentModel):
    kind = DocumentKind.RECORDED_LIEN
    name = "mechanics-lien"
    required = ("document_number", "recorded", "claimant", "amount", "reputed_owner", "properties")
    lens_checks = (lien_action_deadline,)

    def parse(self, text: str, context: ModelContext) -> MechanicsLien | None:
        if not re.search(r"CLAIM OF MECHANIC'?S LIEN", text or "", re.I) or re.search(r"as Surety", text or "", re.I):
            return None
        head = re.split(r"RELEASE OF (?:CLAIM OF )?(?:MECHANIC'?S )?LIEN", text, maxsplit=1, flags=re.I)[0] if \
            re.search(r"hereby releases", text, re.I) else text
        flat = squash(head)
        r = MechanicsLien()
        r.document_number, r.recorded, r.document_number_from_name = _recording(head, context.name)
        r.claimant = first(r"The undersigned ([A-Z][\w&.,' ]+?) \(\"?[“\"]?Claimant", flat)
        r.claimant_address = first(r"Claimant[”\"]?\), whose address is ([^,]+,[^,]+,[^,]+?\d{5})", flat)
        r.attorney_firm = first(r"\n([A-Z][A-Z ]+ LLP)\s*\n", head)
        r.amount = cents(first(r"The sum of (\$[\d,]+\.\d\d)", flat)) if re.search(r"The sum of \$", flat) else None
        r.work = first(r"offsets, for ([^.]+?) that were furnished", flat)
        r.hired_by = first(r"under contract with, ([A-Z][\w&.,' ]+?) whose address", flat)
        r.prime_contractor = first(r"reputed prime contractor is ([A-Z][\w&.,' ]+?) whose address", flat)
        owner = first(r"reputed owner of the Properties is ([A-Z][\w&.,' ]+?) whose address", flat)
        r.reputed_owner_is_person = bool(owner) and not _ENTITY.search(owner)
        r.reputed_owner = owner if owner and not r.reputed_owner_is_person else ""
        r.properties = site_addresses(first(r"located at:(.*?)Together", head, flags=re.I | re.S))
        r.apns = apns_in(first(r"located at:(.*?)Together", head, flags=re.I | re.S))
        buildings = [building_of(context, a) for a in r.properties]
        r.buildings = tuple(sorted({b for b in buildings if b is not None}, key=lambda b: b.value))
        r.statutory_notice = bool(re.search(r"NOTICE OF MECHANIC'?S LIEN\s*ATTENTION", flat, re.I)) and bool(re.search(r"cslb\.ca\.gov", flat, re.I))
        r.verified = bool(re.search(r"\bVERIFICATION\b", head)) and bool(re.search(r"penalty of perjury", flat, re.I))
        r.proof_of_service = bool(re.search(r"PROOF OF SERVICE AFFIDAVIT", head))
        r.service_method = "certified mail" if re.search(r"Certified Mail, Return Receipt Requested", head) else ""
        r.dated = date_after(r"Signed on", head, window=40) or date_after(r"\nDate:", head, window=30)
        releases = []
        for m in re.finditer(r"hereby releases in its entirety that certain Mechanic'?s Lien", text, re.I):
            tail = re.sub(r"(?<=[\d\s-])I(?=[\s\d,])", "1", squash(text[m.end(): m.end() + 400]))
            number = re.sub(r"[\s-]", "", first(r"document number ([\d\s-]{10,16}\d)", tail).replace("I", "1"))
            released = dates_in(first(r"Sacramento on ([^,]+, \d{4})", tail).replace(" I,", " 1,"))
            after = text[m.end():]
            dated = date_after(r"DA\s?TED:", after, window=40)
            releases.append(LienRelease(number, released[0] if released else None, dated, bool(re.search(r"PROOF OF SERVICE", after))))
        r.releases = tuple(releases)
        return r

    def check(self, r: MechanicsLien, context: ModelContext) -> list[Finding]:
        found: list[Finding] = []
        parts = {"a statement of the demand": r.amount, "the owner or reputed owner": r.reputed_owner or r.reputed_owner_is_person,
                 "the kind of work": r.work, "who hired the claimant": r.hired_by, "the site": r.properties, "the claimant's address": r.claimant_address,
                 "a proof of service affidavit": r.proof_of_service, "the statutory Notice of Mechanics Lien": r.statutory_notice}
        for label, value in parts.items():
            if not value:
                found.append(Finding("lien-part-not-in-text", f"the text does not show {label}", Severity.CHECK, "CIV 8416(a)"))
        if not r.verified:
            found.append(Finding("not-verified", "the text carries no verification of the claim", Severity.CHECK, "CIV 8416(a)"))
        found.append(lien_action_deadline)   # the as-of lens's place: the claimant's time to sue, running or run
        for release in r.releases:
            found.append(Finding("release-in-file", f"the file also releases lien {release.released_number or '(number not read)'}"
                                 + (f" recorded {release.released_recorded}" if release.released_recorded else ""), Severity.INFO))
        if r.reputed_owner and "association" not in r.reputed_owner.lower():
            found.append(Finding("owner-is-builder", f"the lien names {r.reputed_owner} as owner; the units it lists were the builder's "
                                 "when the lien recorded", Severity.INFO))
        parcels = known_parcels(context)
        if parcels and r.apns:
            outside = [a for a in r.apns if a not in parcels]
            if outside:
                found.append(Finding("parcels-not-in-spec", f"{len(outside)} of {len(r.apns)} APNs are not the association's parcels in the "
                                     "specification (OCR may have garbled them)", Severity.CHECK))
        found += _name_number(r.document_number, context)
        if r.document_number_from_name:
            found.append(Finding("document-number-from-name", "the recorder's stamp did not read; the document number comes from the file name",
                                 Severity.CHECK))
        return found


@dataclass
class LienReleaseBond:
    instrument: LienInstrument = LienInstrument.RELEASE_BOND
    document_number: str = ""
    document_number_from_name: bool = False
    recorded: date | None = None         # the stamp's date, or the date the number carries
    principal: str = ""
    surety: str = ""
    surety_state: str = ""
    obligee: str = ""                    # the lien claimant
    bond_amount: int | None = None       # cents, from the written-out sum
    lien_amount: int | None = None
    lien_recorded: date | None = None
    statute: str = ""                    # the section the bond cites
    dated: date | None = None
    properties: tuple[str, ...] = ()
    attorney_in_fact: bool = False
    power_of_attorney: bool = False
    notarized: bool = False


class LienReleaseBondModel(DocumentModel):
    kind = DocumentKind.RECORDED_LIEN
    name = "mechanics-lien-release-bond"
    required = ("principal", "surety", "obligee", "bond_amount", "lien_amount")

    def parse(self, text: str, context: ModelContext) -> LienReleaseBond | None:
        if not re.search(r"as Surety", text or "", re.I) or not re.search(r"mechanic'?s lien", text or "", re.I):
            return None
        flat = re.sub(r",(\d{4})\b", r", \1", squash(text))
        r = LienReleaseBond()
        r.document_number, r.recorded, r.document_number_from_name = _recording(text, context.name)
        r.principal = first(r"That we,\s*([A-Z][\w&.,' ]+?)\s*_?\s*as Principal", flat)
        r.surety = first(r"as Principal and\s*(?:the\s*)?([A-Z][\w&.,' ]+?)\s*,?\s*[a4] corporation", flat, flags=0) or \
            first(r"as Principal and\s*([A-Z][\w&.' ]+?(?:Company|Corporation|Inc\.?))", flat)
        r.surety_state = first(r"laws of the State of ([A-Z][a-z]+(?: [A-Z][a-z]+)?)\s*,?\s*as Surety", flat)
        r.obligee = first(r"bound unto\s*([A-Z][\w&.,' ]+?)\s*,?\s*Obligee", flat)
        r.bond_amount = words_to_cents(first(r"Obligee, in the sum of\s*(.{10,160}?/100)", flat))
        lien = first(r"in the amount of.{0,160}?\(\s*\$\s*([\d,]+\.\d\d)\s*\)", flat) or first(r"\$\s*([\d,]+\.\d\d)\s*\)", flat)
        r.lien_amount = cents(lien) if lien else words_to_cents(first(r"in the amount of\s*(.{10,160}?/100)", flat))
        r.lien_recorded = date_after(r"State of California, on", flat, window=40)
        r.statute = "CIV " + first(r"Section (\d{4}) of the Civil Code", flat) if re.search(r"Section \d{4} of the Civil Code", flat) else ""
        witness = first(r"this\s*(\d{1,2})(?:st|nd|rd|th)?\s*day of\s*([A-Z][a-z]+)\s*,?\s*(\d{4})", flat, 0)
        m = re.search(r"this\s*(\d{1,2})(?:st|nd|rd|th)?\s*day of\s*([A-Z][a-z]+)\s*,?\s*(\d{4})", flat)
        if witness and m:
            found = dates_in(f"{m.group(2)} {m.group(1)}, {m.group(3)}")
            r.dated = found[0] if found else None
        r.properties = site_addresses(text)
        r.attorney_in_fact = bool(re.search(r"Attorney-in-Fact", text, re.I))
        r.power_of_attorney = bool(re.search(r"Power of Attorney", text, re.I))
        r.notarized = bool(re.search(r"Notary Public", text, re.I))
        return r

    def check(self, r: LienReleaseBond, context: ModelContext) -> list[Finding]:
        found: list[Finding] = []
        if r.bond_amount and r.lien_amount:
            needed = (r.lien_amount * BOND_PERCENT + 50) // 100
            if r.bond_amount < needed:
                found.append(Finding("bond-under-125-percent", f"the bond, ${r.bond_amount / 100:,.2f}, is under 125 percent of the "
                                     f"${r.lien_amount / 100:,.2f} claim (${needed / 100:,.2f})", Severity.PROBLEM, "CIV 8424(b)"))
            else:
                found.append(Finding("bond-covers-claim", f"the bond, ${r.bond_amount / 100:,.2f}, is at least 125 percent of the "
                                     f"${r.lien_amount / 100:,.2f} claim", Severity.INFO, "CIV 8424(b)"))
        if r.surety:
            found.append(Finding("admitted-surety", f"confirm {r.surety} is an admitted surety insurer", Severity.CHECK, "CIV 8424(b)"))
        found.append(Finding("claimant-notice", "the principal must give the claimant notice with a copy of the bond; the claimant then "
                             "has six months to sue on the bond", Severity.INFO, "CIV 8424(d)"))
        found += _name_number(r.document_number, context)
        if r.document_number_from_name:
            found.append(Finding("document-number-from-name", "the recorder's stamp did not read; the document number comes from the file name",
                                 Severity.CHECK))
        if not r.document_number:
            found.append(Finding("no-recording-number", "neither the text nor the file name gives the recording number", Severity.CHECK))
        return found


register(AssessmentLienModel())
register(LienReleaseBondModel())
register(MechanicsLienModel())

__all__ = ["LienInstrument", "LienItem", "AssessmentLien", "AssessmentLienModel", "LienRelease", "MechanicsLien", "MechanicsLienModel",
           "LienReleaseBond", "LienReleaseBondModel"]
