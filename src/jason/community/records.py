"""Association records, Civil Code 5200, from the 2025 session publication.

Paragraphs (a)(13) and (a)(14) do not add a sixteenth kind. They pull enhanced
records and election materials into the definition. Executive-session minutes
are outside ``MINUTES`` (section 5200(a)(8)).
"""

from jason.community.symbols import AssociationRecord

CITATION: dict[AssociationRecord, str] = {
    AssociationRecord.FINANCIAL_DISCLOSURE: "CIV 5200(a)(1)",
    AssociationRecord.TRANSFER_FINANCIAL: "CIV 5200(a)(2)",
    AssociationRecord.INTERIM_FINANCIAL: "CIV 5200(a)(3)",
    AssociationRecord.EXECUTED_CONTRACT: "CIV 5200(a)(4)",
    AssociationRecord.VENDOR_APPROVAL: "CIV 5200(a)(5)",
    AssociationRecord.TAX_RETURN: "CIV 5200(a)(6)",
    AssociationRecord.RESERVE_ACCOUNT: "CIV 5200(a)(7)",
    AssociationRecord.MINUTES: "CIV 5200(a)(8)",
    AssociationRecord.MEMBERSHIP_LIST: "CIV 5200(a)(9)",
    AssociationRecord.CHECK_REGISTER: "CIV 5200(a)(10)",
    AssociationRecord.GOVERNING_DOCUMENTS: "CIV 5200(a)(11)",
    AssociationRecord.RESERVE_LITIGATION_ACCOUNTING: "CIV 5200(a)(12)",
    AssociationRecord.ENHANCED: "CIV 5200(b)",
    AssociationRecord.ELECTION_MATERIALS: "CIV 5200(c)",
    AssociationRecord.ELEVATED_ELEMENT_REPORT: "CIV 5200(a)(15)",
}


def citation(kind: AssociationRecord) -> str:
    return CITATION[kind]
