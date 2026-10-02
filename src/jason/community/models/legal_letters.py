"""Legal correspondence and briefs: counsel's letters to the members, the board's offers of dispute resolution, and the
association's mediation brief.

Two letters the law shapes. After a construction-defect settlement the association tells the members, as soon as
reasonably practicable, a general description of the defects that will be corrected, a good-faith estimate of when,
and the status of the other claims (CIV 6100(a)(1)-(3)). An offer of alternative dispute resolution served as a Request
for Resolution describes the dispute, asks for ADR, says the recipient has 30 days to respond or the request is deemed
rejected, and, served on a member, includes a copy of the ADR article (CIV 5935(a)); the association may not refuse a
member's request to meet and confer (5915(b)(2)); discipline or a charge for common-area damage takes a written
decision within 14 days of the board's action (5855(f)).

``LegalLetter`` reads Berding & Weil's membership letters (the 2023 settlement notice and the window-warranty reminder)
and the board's "Offer to Participate in Dispute Resolution (IDR & ADR)". ``LegalBrief`` reads the association's
mediation brief. Neither keeps an owner's name, and a letter that prints a portal login keeps only the fact that it does.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
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
    building_of,
    civil_code_citations,
    days_between,
    former_sections,
    former_sections_finding,
    site_address,
    unit_count,
)
from jason.community.symbols import Building, DocumentKind

ADR_RESPONSE_DAYS = 30        # CIV 5935(a)(3)
DECISION_NOTICE_DAYS = 14     # CIV 5855(f)


class LetterType(Enum):
    SETTLEMENT_DISCLOSURE = "settlement disclosure (CIV 6100)"
    DISPUTE_RESOLUTION_OFFER = "offer of IDR and ADR"
    MEMBERSHIP_UPDATE = "counsel's membership update"
    LIEN_RESOLUTION = "counsel's lien resolution for the board"
    TRUST_DISBURSEMENT = "counsel's trust account disbursement"
    OTHER = "other"


class Recipient(Enum):
    MEMBERSHIP = "the membership"
    OWNER = "one owner"
    BOARD = "the board"
    OTHER = "other"


_FIRMS = (("Berding & Weil LLP", r"BERDING\s*&\s*WEIL"), ("Severaid & Glahn, PC", r"SEVERAID\s*&\s*GLAHN"),
          ("Downey Brand LLP", r"DOWNEY BRAND"))


def _firm(text: str) -> str:
    return next((name for name, pattern in _FIRMS if re.search(pattern, text, re.I)), "")


@dataclass
class LegalLetter:
    letter_type: LetterType = LetterType.OTHER
    letter_date: date | None = None
    sender: str = ""                     # the firm, or "Board of Directors"
    sender_is_counsel: bool = False
    recipient: Recipient = Recipient.OTHER
    names_owner: bool = False
    property_address: str = ""
    building: Building | None = None
    subject: str = ""
    draft: bool = False
    privileged: bool = False
    delivery: str = ""                   # "U.S. Mail", "Electronic Mail"
    parties: tuple[str, ...] = ()        # the entities the matter is against (builders, vendors)
    buildings_named: tuple[Building, ...] = ()
    settlement_amount: int | None = None
    amounts: tuple[int, ...] = ()
    civil_code: tuple[str, ...] = ()
    former_sections: tuple[str, ...] = ()
    ccr_sections: tuple[str, ...] = ()
    response_days: int | None = None     # "contact the Association in writing within ten (10) days"
    board_decision: date | None = None   # the board action the letter follows
    decision_notice: date | None = None  # the "Notice of Board Decision" it refers to
    adr_article_attached: bool = False
    prints_credentials: bool = False
    # CIV 6100(a) disclosures, for a settlement letter
    defects_described: bool = False
    repair_estimate: bool = False
    other_claims_status: bool = False


def _days(phrase: str) -> int | None:
    m = re.search(r"within (\w+(?:-\w+)?) \((\d+)\) days|within (\d+) days", phrase, re.I)
    if not m:
        return None
    return int(m.group(2) or m.group(3))


class LegalLetterModel(DocumentModel):
    kind = DocumentKind.LEGAL_CORRESPONDENCE
    name = "legal-letter"
    required = ("letter_date", "sender", "subject")

    def parse(self, text: str, context: ModelContext) -> LegalLetter | None:
        if not re.search(r"\bDear\b|Very truly yours|Sincerely|RE:|Subject:", text or "", re.I):
            return None
        flat = squash(text)
        r = LegalLetter()
        firm = _firm(text)
        if re.search(r"DISPUTE RESOLUTION \(IDR\s*&\s*ADR\)|meet and confer", text, re.I) and re.search(r"offer|invitation", flat, re.I):
            r.letter_type = LetterType.DISPUTE_RESOLUTION_OFFER
        elif re.search(r"section 6100|Notice of Settlement", flat, re.I):
            r.letter_type = LetterType.SETTLEMENT_DISCLOSURE
        elif re.search(r"Lien Resolution|NOD Resolution", flat, re.I):
            r.letter_type = LetterType.LIEN_RESOLUTION
        elif re.search(r"Trust Account Disbursement", flat, re.I):
            r.letter_type = LetterType.TRUST_DISBURSEMENT
        elif firm and re.search(r"Dear Member", flat, re.I):
            r.letter_type = LetterType.MEMBERSHIP_UPDATE
        r.sender = firm or ("Board of Directors" if re.search(r"Board of Directors\s*\n?\s*Mystique", text) else "")
        r.sender_is_counsel = bool(firm)
        r.recipient = Recipient.MEMBERSHIP if re.search(r"Dear Member|\nMembership\s*\n", text) else \
            Recipient.OWNER if re.search(r"Dear Homeowner|Property Address:", text) else \
            Recipient.BOARD if re.search(r"SENT TO:\s*Board of Directors", text) else Recipient.OTHER
        r.names_owner = r.recipient is Recipient.OWNER and bool(re.search(r"\nTo:\s*[A-Z][a-z]+", text))
        r.property_address = site_address(first(r"Property Address:\s*([^\n]+)", text)) if re.search(r"Property Address:", text) else ""
        r.building = building_of(context, r.property_address)
        r.letter_date = date_after(r"\bDate:\s*", text, window=40) or (dates_in(text[:600]) or [None])[0]
        subject = first(r"Subject:\s*([^\n]+(?:\n(?!Dear|To:)[^\n]+)?)", text) or \
            first(r"RE:\s*(?:\n\s*)*(?:MYSTIQUE COMMUNITY ASSOCIATION\s*\n\s*)?(?:\n\s*)*([^\n]+)", text)
        r.subject = subject[:200]
        r.draft = bool(re.search(r"^\s*DRAFT\s*$", text, re.M))
        r.privileged = bool(re.search(r"PRIVILEGED|CONFIDENTIAL", text))
        r.delivery = "U.S. Mail" if re.search(r"VIA U\.S\. MAIL", text, re.I) else "Electronic Mail" if re.search(r"VIA ELECTRONIC MAIL", text, re.I) else ""
        parties = re.findall(r"(Watt Communities at Mystique,? LLC|WC Development Services,? Inc\.?|Milgard)", flat)
        r.parties = tuple(dict.fromkeys(p.replace(",", "") for p in parties))
        named = re.search(r"Buildings? ((?:\d, )*\d,? (?:and|&) \d)", flat)
        r.buildings_named = tuple(Building(int(n)) for n in re.findall(r"\d", named.group(1))) if named else ()
        amount = first(r"total settlement amount is (\$[\d,]+(?:\.\d\d)?)", flat)
        r.settlement_amount = cents(amount) if amount else None
        r.amounts = tuple(v for v in (cents(a) for a in re.findall(r"\$[\d,]+\.\d\d", flat)) if v)
        r.civil_code = civil_code_citations(flat)
        r.former_sections = former_sections(flat)
        r.ccr_sections = tuple(dict.fromkeys(re.findall(r"CC&Rs? (?:section|§)\s*([\d.]+(?:\([a-z]\))*(?:\([ivx]+\))?)", flat, re.I)))
        r.response_days = _days(first(r"(contact the Association in writing within [^.]+)", flat, 0) or first(r"(respond within [^.]+)", flat, 0))
        r.board_decision = date_after(r"its decision on", flat, window=30)
        r.decision_notice = date_after(r"Notice of Board Decision dated", flat, window=30)
        r.adr_article_attached = bool(re.search(r"5925\.\s*\(", text)) or bool(re.search(r"Article 3\. Alternative Dispute Resolution", text))
        r.prints_credentials = bool(re.search(r"\bPassword:\s*\n?\s*\S+", text)) and bool(re.search(r"\bUsername:", text))
        if r.letter_type is LetterType.SETTLEMENT_DISCLOSURE:
            r.defects_described = bool(re.search(r"claims included|defects?,? damages,? and issues identified|will be corrected|will be repaired",
                                                 flat, re.I))
            r.repair_estimate = bool(re.search(r"(?:expects?|estimate[sd]?|anticipate[sd]?) [^.]{0,80}(?:repairs?|correct\w*) [^.]{0,60}"
                                               r"(?:by|in|during|within) (?:\w+ )?(?:19|20)\d\d", flat, re.I))
            r.other_claims_status = bool(re.search(r"does not include the following claims|not include any other|excluded from the release",
                                                   flat, re.I))
        return r

    def check(self, r: LegalLetter, context: ModelContext) -> list[Finding]:
        found: list[Finding] = []
        if r.letter_type is LetterType.SETTLEMENT_DISCLOSURE:
            if not r.defects_described:
                found.append(Finding("no-defect-description", "the notice gives no general description of the defects to be corrected",
                                     Severity.PROBLEM, "CIV 6100(a)(1)"))
            if not r.repair_estimate:
                found.append(Finding("no-repair-estimate", "the notice gives no estimate of when the defects will be corrected (it may defer "
                                     "to a later disclosure, which 6100(b) allows)", Severity.CHECK, "CIV 6100(a)(2), (b)"))
            if not r.other_claims_status:
                found.append(Finding("no-other-claims-status", "the notice does not give the status of the claims the settlement leaves out",
                                     Severity.PROBLEM, "CIV 6100(a)(3)"))
            found.append(Finding("members-of-record", "the disclosure goes only to the members on the association's records",
                                 Severity.INFO, "CIV 6100(a)"))
        if r.letter_type is LetterType.DISPUTE_RESOLUTION_OFFER:
            if r.response_days is not None and r.response_days < ADR_RESPONSE_DAYS:
                found.append(Finding("adr-response-window", f"the letter asks for an answer within {r.response_days} days; a Request for "
                                     f"Resolution must give the recipient {ADR_RESPONSE_DAYS} days before it is deemed rejected",
                                     Severity.CHECK, "CIV 5935(a)(3)"))
            if not r.adr_article_attached:
                found.append(Finding("adr-article-not-attached", "the text does not include a copy of the ADR article (Civil Code 5925 and "
                                     "following), which a Request for Resolution served on a member must carry", Severity.CHECK,
                                     "CIV 5935(a)(4)"))
            lag = days_between(r.board_decision, r.decision_notice)
            if lag is not None:
                # The deadline in force when the board acted: 15 days before Stats. 2025, Ch. 22, 14 since.
                from jason.community.statutory_terms import in_force

                allowed = in_force("written decision after a hearing", r.board_decision)
                severity = Severity.PROBLEM if lag > allowed else Severity.INFO
                found.append(Finding("decision-notice-days", f"the board's written decision is dated {lag} days after its action; "
                                     f"the statute then allowed {allowed}", severity, "CIV 5855(f)"))
        found += former_sections_finding(r.former_sections, context.data_dir)
        if r.draft:
            found.append(Finding("draft", "the file is a draft; the letter sent may differ", Severity.INFO))
        if r.prints_credentials:
            found.append(Finding("prints-credentials", "the letter prints a portal username and password; keep the file out of shared "
                                 "folders and ask counsel whether the login is still live", Severity.CHECK))
        if r.privileged:
            found.append(Finding("privileged", "marked privileged or confidential; the association may withhold privileged records from "
                                 "inspection, and should share this only as counsel directs", Severity.INFO, "CIV 5215(a)(3)"))
        return found


@dataclass
class LegalBrief:
    brief_date: date | None = None
    privileged: bool = False
    privilege_basis: tuple[str, ...] = ()     # the Evidence Code sections it cites for confidentiality
    caption: str = ""                         # "Mystique Community Association v. Watt Communities at Mystique, LLC"
    forum: str = ""                           # "mediation", "arbitration", "court"
    event_date: date | None = None            # the mediation or hearing it is for
    addressed_to: str = ""                    # the neutral's firm ("Burke ADR")
    author_firm: str = ""
    units_stated: int | None = None
    buildings_stated: int | None = None
    claims_basis: str = ""                    # "SB800"
    cost_of_repair: int | None = None         # cents, the expert's total
    cost_of_repair_date: date | None = None
    exhibits: int = 0


_NUMBERS = {"six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}


class LegalBriefModel(DocumentModel):
    kind = DocumentKind.LEGAL_BRIEF
    name = "mediation-brief"
    required = ("brief_date", "caption", "author_firm")

    def parse(self, text: str, context: ModelContext) -> LegalBrief | None:
        if not re.search(r"\bbrief\b", (text or "")[:3000], re.I) or not re.search(r"\bv\.\s", (text or "")[:3000]):
            return None
        flat = squash(text)
        r = LegalBrief()
        r.brief_date = (dates_in(text[:600]) or [None])[0]
        r.privileged = bool(re.search(r"PRIVILEGED|Protected from disclosure|CONFIDENTIAL", text[:1500], re.I))
        r.privilege_basis = tuple(dict.fromkeys(re.findall(r"Evidence Code\s*(?:§+\s*)?(\d{4})", flat)))
        r.caption = first(r"Re:\s*([A-Z][^\n]+? v\. [^\n]+)", text) or first(r"([A-Z][\w ]+ Association v\. [A-Z][\w ,.]+?(?:LLC|Inc\.?))", flat)
        r.forum = "mediation" if re.search(r"mediation", flat[:3000], re.I) else "arbitration" if re.search(r"arbitration", flat[:3000], re.I) else ""
        r.event_date = date_after(r"in advance of the", flat, window=40) or date_after(r"(?:mediation|hearing) (?:on|set for)", flat, window=40)
        if r.event_date is None:
            m = re.search(r"in advance of the (\w+ \d{1,2})(?:st|nd|rd|th)?,? (\d{4})", flat)
            if m:
                r.event_date = (dates_in(f"{m.group(1)}, {m.group(2)}") or [None])[0]
        r.addressed_to = first(r"\n([A-Z][A-Za-z ]+ ADR)\s*\n", text) or first(r"\n([A-Z][A-Za-z &]+ (?:Mediation|Arbitration)[A-Za-z ]*)\n", text)
        r.author_firm = _firm(text)
        units = re.search(r"\((\d+)\) townhouse|(\d+) (?:condominium |townhouse[- ]style )?units", flat)
        r.units_stated = int(units.group(1) or units.group(2)) if units else None
        buildings = first(r"featuring (\w+) buildings", flat).lower()
        r.buildings_stated = _NUMBERS.get(buildings) or (int(buildings) if buildings.isdigit() else None)
        r.claims_basis = "SB800" if re.search(r"SB\s?800", flat) else ""
        cost = first(r"TOTAL COST TO REPAIR\s*(\$[\d,]+)", flat)
        r.cost_of_repair = cents(cost) if cost else None
        r.cost_of_repair_date = date_after(r"PRELIMINARY COST OF REPAIR\s*Date:", flat, window=20)
        r.exhibits = len(set(re.findall(r"EXHIBIT\s+[\"“]?([A-Z0-9]+)", text)))
        return r

    def check(self, r: LegalBrief, context: ModelContext) -> list[Finding]:
        found: list[Finding] = []
        units = unit_count(context)
        if r.units_stated and units and r.units_stated != units:
            found.append(Finding("unit-count", f"the brief counts {r.units_stated} units; the specification has {units}", Severity.CHECK))
        if r.privileged:
            found.append(Finding("mediation-privileged", "a mediation brief is privileged"
                                 + (f" (Evidence Code {', '.join(r.privilege_basis)})" if r.privilege_basis else "")
                                 + "; the association may withhold it from a records request", Severity.INFO, "CIV 5215(a)(3)"))
        return found


register(LegalLetterModel())
register(LegalBriefModel())

__all__ = ["LetterType", "Recipient", "LegalLetter", "LegalLetterModel", "LegalBrief", "LegalBriefModel"]
