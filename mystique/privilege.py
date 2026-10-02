"""Who Mystique's privileged communications are with, and the names that tell.

Read from the association's Gmail (September 29, 2026) and the legal cases (cases.py): Freeman Mathis & Gary defends
26CV016125 through the general liability carrier; Berding & Weil advises the association (the tender). Athens
Administrators handles the liability claim, ESIS the directors and officers claim, and DH Adjusting adjusts losses.
The broker's and the owner's own insurer's letters are not privileged. Ayala, Morgan & Buzzard represents the plaintiff.
A call here is a lead for counsel's review, never the determination.
"""

from __future__ import annotations

from jason.community.privilege import PrivilegeKind, PrivilegeNameRule, PrivilegeParty, Role

PRIVILEGE_PARTIES: tuple[PrivilegeParty, ...] = (
    PrivilegeParty("fmglaw.com", Role.COUNSEL, "Freeman Mathis & Gary (defense counsel)"),
    PrivilegeParty("berdingweil.com", Role.COUNSEL, "Berding & Weil (association counsel)"),
    PrivilegeParty("athensadmin.com", Role.INSURER, "Athens Administrators (liability claims)"),
    PrivilegeParty("esis.com", Role.INSURER, "ESIS (directors and officers claim)"),
    PrivilegeParty("dhadjusting.com", Role.INSURER, "DH Adjusting"),
    PrivilegeParty("ardenprograms.com", Role.INSURER, "Arden (insurance program)"),
    PrivilegeParty("hoa-insurance.com", Role.BROKER, "the insurance broker"),
    PrivilegeParty("amb.law", Role.ADVERSE, "the plaintiff's counsel"),
    PrivilegeParty("csaa.com", Role.THIRD_PARTY, "the owner's own insurer"),
)

# In order: a name that says it is counsel's analysis or marked privileged; a request to counsel or the carrier for a
# defense; the other side's papers (a summons, a complaint, a demand, a preservation letter), which are not privileged.
PRIVILEGE_NAME_RULES: tuple[PrivilegeNameRule, ...] = (
    PrivilegeNameRule(r"privileged|attorney[- ]client|work product|case analysis|litigation strategy", PrivilegeKind.WORK_PRODUCT,
                      "marked privileged or counsel's analysis"),
    PrivilegeNameRule(r"legal defense request|tender|defense request|request for defense|coverage position", PrivilegeKind.REVIEW,
                      "a request for defense or coverage; privileged if made for the defense"),
    PrivilegeNameRule(r"summons|\bROA \d|cover sheet|case summary|public portal|notice of lawsuit|\bcomplaint\b(?! ?re)",
                      PrivilegeKind.NOT_PRIVILEGED, "a court filing or the court's public record"),
    PrivilegeNameRule(r"\bdemand\b|preservation letter", PrivilegeKind.NOT_PRIVILEGED, "the other side's letter"),
    PrivilegeNameRule(r"transcript|recording", PrivilegeKind.REVIEW,
                      "a meeting or hearing record: confidential where it is an executive session (4935)"),
    PrivilegeNameRule(r"notice of (?:second |third )?violation|disciplinary hearing|courtesy notice|notice of decision",
                      PrivilegeKind.NOT_PRIVILEGED, "the association's letter to the owner"),
)

# A communication is a letter, memo, email, or analysis; anything else (records, invoices, photos, reports) already
# existed and is a document sent, not a communication made.
COMMUNICATION_NAMES = r"^Mystique Community (?:Association|Organization) Mail - |\bletter\b|\bmemo|\bemail\b|analysis|acknowledg|" \
                      r"correspondence|legal defense request|tender|\badvice\b"

# Names of sensitive records: kept, and never shared outside the matter.
SENSITIVE_NAMES: tuple[tuple[str, str], ...] = (
    (r"medical|urgent care|pediatric|health|\bMD\b|hospital|clinic|\bbill(?:ing)?\b.*(?:md|health|care)", "medical"),
)
