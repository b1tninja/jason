"""Drive-bound documents. A governing document keeps its amendments beside it."""

from __future__ import annotations

import fnmatch
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from typing import Any, Sequence

from jason.community.symbols import (
    AssociationRecord,
    DeveloperDelivery,
    DocumentCategory,
    DocumentKind,
    FileKind,
    PayhoaFolder,
)


@dataclass(frozen=True)
class DocumentProfile:
    """Category, the Civil Code 5200 record when there is one, and the developer delivery."""

    category: DocumentCategory
    record: AssociationRecord | None = None
    delivery: DeveloperDelivery | None = None


PROFILE: dict[DocumentKind, DocumentProfile] = {
    DocumentKind.DECLARATION: DocumentProfile(DocumentCategory.GOVERNING, AssociationRecord.GOVERNING_DOCUMENTS, DeveloperDelivery.DECLARATION),
    DocumentKind.AMENDMENT: DocumentProfile(DocumentCategory.GOVERNING, AssociationRecord.GOVERNING_DOCUMENTS, DeveloperDelivery.DECLARATION),
    DocumentKind.BYLAWS: DocumentProfile(DocumentCategory.GOVERNING, AssociationRecord.GOVERNING_DOCUMENTS, DeveloperDelivery.BYLAWS),
    DocumentKind.ARTICLES: DocumentProfile(DocumentCategory.GOVERNING, AssociationRecord.GOVERNING_DOCUMENTS, DeveloperDelivery.ARTICLES),
    DocumentKind.POLICY: DocumentProfile(DocumentCategory.GOVERNING, AssociationRecord.GOVERNING_DOCUMENTS),
    DocumentKind.ELECTION_RULES: DocumentProfile(DocumentCategory.GOVERNING, AssociationRecord.GOVERNING_DOCUMENTS),
    DocumentKind.ANNEXATION: DocumentProfile(DocumentCategory.GOVERNING, AssociationRecord.GOVERNING_DOCUMENTS, DeveloperDelivery.DECLARATION),
    DocumentKind.RESOLUTION: DocumentProfile(DocumentCategory.GOVERNING),
    DocumentKind.MINUTES: DocumentProfile(DocumentCategory.MEETING, AssociationRecord.MINUTES),
    DocumentKind.TREASURER_REPORT: DocumentProfile(DocumentCategory.FINANCIAL, AssociationRecord.INTERIM_FINANCIAL),
    DocumentKind.MEMBERSHIP_LIST: DocumentProfile(DocumentCategory.MEMBERSHIP, AssociationRecord.MEMBERSHIP_LIST, DeveloperDelivery.MEMBERSHIP_REGISTER),
    DocumentKind.INSURANCE_POLICY: DocumentProfile(DocumentCategory.INSURANCE, AssociationRecord.EXECUTED_CONTRACT, DeveloperDelivery.INSURANCE),
    DocumentKind.CONTRACT: DocumentProfile(DocumentCategory.CONTRACT, AssociationRecord.EXECUTED_CONTRACT),
    DocumentKind.LEASE: DocumentProfile(DocumentCategory.CONTRACT, AssociationRecord.EXECUTED_CONTRACT),
    DocumentKind.CONDOMINIUM_PLAN: DocumentProfile(DocumentCategory.PROPERTY, None, DeveloperDelivery.CONDOMINIUM_PLAN),
    DocumentKind.MAP: DocumentProfile(DocumentCategory.PROPERTY),
    DocumentKind.GRANT_DEED: DocumentProfile(DocumentCategory.PROPERTY),
    DocumentKind.DRE_REPORT: DocumentProfile(DocumentCategory.PROPERTY, None, DeveloperDelivery.PUBLIC_REPORT),
    DocumentKind.PLAN_SET: DocumentProfile(DocumentCategory.PROPERTY, None, DeveloperDelivery.MAINTENANCE_PLANS),
    # The record each kind satisfies follows Civil Code 5200 as the 2025 publication words it (data/authorities).
    DocumentKind.OPERATING_RULES: DocumentProfile(DocumentCategory.GOVERNING, AssociationRecord.GOVERNING_DOCUMENTS),
    DocumentKind.AGENDA: DocumentProfile(DocumentCategory.MEETING, AssociationRecord.MINUTES),
    DocumentKind.EXECUTIVE_SESSION: DocumentProfile(DocumentCategory.MEETING),
    DocumentKind.NOTICE: DocumentProfile(DocumentCategory.MEETING),
    DocumentKind.COMMITTEE_REPORT: DocumentProfile(DocumentCategory.MEETING),
    DocumentKind.BALLOT: DocumentProfile(DocumentCategory.ELECTION, AssociationRecord.ELECTION_MATERIALS),
    DocumentKind.ELECTION_RESULTS: DocumentProfile(DocumentCategory.ELECTION, AssociationRecord.ELECTION_MATERIALS),
    DocumentKind.FINANCIAL_STATEMENT: DocumentProfile(DocumentCategory.FINANCIAL, AssociationRecord.INTERIM_FINANCIAL),
    DocumentKind.BANK_STATEMENT: DocumentProfile(DocumentCategory.FINANCIAL, AssociationRecord.ENHANCED),
    DocumentKind.BUDGET: DocumentProfile(DocumentCategory.FINANCIAL, AssociationRecord.FINANCIAL_DISCLOSURE),
    DocumentKind.RESERVE_STUDY: DocumentProfile(DocumentCategory.FINANCIAL, AssociationRecord.FINANCIAL_DISCLOSURE),
    DocumentKind.FINANCIAL_REVIEW: DocumentProfile(DocumentCategory.FINANCIAL, AssociationRecord.FINANCIAL_DISCLOSURE),
    DocumentKind.TAX_RETURN: DocumentProfile(DocumentCategory.FINANCIAL, AssociationRecord.TAX_RETURN),
    DocumentKind.ANNUAL_DISCLOSURE: DocumentProfile(DocumentCategory.FINANCIAL, AssociationRecord.FINANCIAL_DISCLOSURE),
    DocumentKind.INVOICE: DocumentProfile(DocumentCategory.FINANCIAL, AssociationRecord.ENHANCED),
    DocumentKind.UTILITY_BILL: DocumentProfile(DocumentCategory.FINANCIAL, AssociationRecord.ENHANCED),
    DocumentKind.TAX_BILL: DocumentProfile(DocumentCategory.FINANCIAL),
    DocumentKind.PROPOSAL: DocumentProfile(DocumentCategory.CONTRACT),
    DocumentKind.INSPECTION_REPORT: DocumentProfile(DocumentCategory.PROPERTY),
    DocumentKind.ELEVATED_ELEMENT_INSPECTION: DocumentProfile(DocumentCategory.PROPERTY, AssociationRecord.ELEVATED_ELEMENT_REPORT),
    DocumentKind.EVIDENCE_OF_INSURANCE: DocumentProfile(DocumentCategory.INSURANCE),
    DocumentKind.LOSS_RUN: DocumentProfile(DocumentCategory.INSURANCE),
    DocumentKind.CLAIM_LETTER: DocumentProfile(DocumentCategory.INSURANCE),
    DocumentKind.CLAIM_PAYMENT: DocumentProfile(DocumentCategory.INSURANCE, AssociationRecord.ENHANCED),
    DocumentKind.CLAIM_AUTHORIZATION: DocumentProfile(DocumentCategory.INSURANCE, AssociationRecord.EXECUTED_CONTRACT),
    DocumentKind.CLAIM_ESTIMATE: DocumentProfile(DocumentCategory.INSURANCE),
    DocumentKind.POLICE_REPORT: DocumentProfile(DocumentCategory.LEGAL),
    DocumentKind.MANAGER_CASE_REPORT: DocumentProfile(DocumentCategory.REFERENCE),
    DocumentKind.IMAGE: DocumentProfile(DocumentCategory.PROPERTY),
    DocumentKind.SETTLEMENT: DocumentProfile(DocumentCategory.LEGAL, AssociationRecord.EXECUTED_CONTRACT),
    DocumentKind.LEGAL_CORRESPONDENCE: DocumentProfile(DocumentCategory.LEGAL),
    DocumentKind.LEGAL_BRIEF: DocumentProfile(DocumentCategory.LEGAL),
    DocumentKind.RECORDED_LIEN: DocumentProfile(DocumentCategory.LEGAL),
    DocumentKind.DELINQUENCY_NOTICE: DocumentProfile(DocumentCategory.LEGAL),
    DocumentKind.OWNER_HISTORY: DocumentProfile(DocumentCategory.MEMBERSHIP),
    DocumentKind.OWNER_STATEMENT: DocumentProfile(DocumentCategory.MEMBERSHIP),
    DocumentKind.ESCROW_REQUEST: DocumentProfile(DocumentCategory.MEMBERSHIP),
    DocumentKind.FORM: DocumentProfile(DocumentCategory.MEMBERSHIP),
    DocumentKind.TEMPLATE: DocumentProfile(DocumentCategory.REFERENCE),
    DocumentKind.CORRESPONDENCE: DocumentProfile(DocumentCategory.REFERENCE),
    DocumentKind.VIOLATION_NOTICE: DocumentProfile(DocumentCategory.LEGAL),
    # The documents given to a buyer on a sale (CIV 4525): the resale certificate and the lender's questionnaire.
    DocumentKind.RESALE_DISCLOSURE: DocumentProfile(DocumentCategory.MEMBERSHIP, AssociationRecord.TRANSFER_FINANCIAL),
    DocumentKind.SECURITY_REPORT: DocumentProfile(DocumentCategory.PROPERTY),
    DocumentKind.AUDIO: DocumentProfile(DocumentCategory.REFERENCE),
    # Each is a 2792.23(a)(10) delivery ("any bond or other security device" naming the association) and an executed contract.
    DocumentKind.SECURITY_AGREEMENT: DocumentProfile(DocumentCategory.CONTRACT, AssociationRecord.EXECUTED_CONTRACT, DeveloperDelivery.BOND),
    DocumentKind.SUBSIDY_AGREEMENT: DocumentProfile(DocumentCategory.CONTRACT, AssociationRecord.EXECUTED_CONTRACT, DeveloperDelivery.BOND),
    DocumentKind.SURETY_BOND: DocumentProfile(DocumentCategory.CONTRACT, AssociationRecord.EXECUTED_CONTRACT, DeveloperDelivery.BOND),
    DocumentKind.BOND_RELEASE: DocumentProfile(DocumentCategory.CONTRACT, None, DeveloperDelivery.BOND),
}


def profile(kind: DocumentKind) -> DocumentProfile:
    return PROFILE[kind]


@dataclass(frozen=True)
class DocumentPin:
    """One Drive file pinned to a document kind. The record comes from the kind.

    ``pattern`` names the segments of ``title``. ``group("building")`` reads one.
    """

    title: str
    drive_id: str
    kind: DocumentKind
    pattern: PathPattern | None = None
    delivery: DeveloperDelivery | None = None

    @property
    def category(self) -> DocumentCategory:
        return profile(self.kind).category

    @property
    def record(self) -> AssociationRecord | None:
        return profile(self.kind).record

    def group(self, name: str) -> str:
        if self.pattern is None:
            raise KeyError(name)
        hit = self.pattern.match(self.title)
        if hit is None:
            raise KeyError(name)
        return hit.group(name)


def pin(
    title: str,
    drive_id: str,
    kind: DocumentKind,
    pattern: PathPattern | None = None,
    delivery: DeveloperDelivery | None = None,
) -> DocumentPin:
    """Pin a file that Civil Code 5200 counts as an association record."""
    if profile(kind).record is None:
        raise ValueError(f"{kind.value} is not an association record")
    chosen = _delivery(kind, delivery)
    if pattern is not None and pattern.match(title) is None:
        raise ValueError(f"{title!r} does not match {pattern.expression!r}")
    return DocumentPin(title, drive_id, kind, pattern, chosen)


def deliver(
    title: str,
    drive_id: str,
    kind: DocumentKind,
    delivery: DeveloperDelivery,
    pattern: PathPattern | None = None,
) -> DocumentPin:
    """Pin a document the subdivider was required to provide.

    The file need not be a Civil Code 5200 record. A map, a condominium plan,
    a common-area deed, a public report, and a plan set use this.
    """
    chosen = _delivery(kind, delivery)
    if chosen is None:
        raise ValueError(f"{kind.value} has no developer delivery")
    if pattern is not None and pattern.match(title) is None:
        raise ValueError(f"{title!r} does not match {pattern.expression!r}")
    return DocumentPin(title, drive_id, kind, pattern, chosen)


def _delivery(kind: DocumentKind, delivery: DeveloperDelivery | None) -> DeveloperDelivery | None:
    expected = profile(kind).delivery
    if delivery is None:
        return expected
    if expected is not None and expected is not delivery:
        raise ValueError(f"{kind.value} delivers {expected.value}")
    return delivery


def developer_file(
    pins: Sequence[DocumentPin],
) -> dict[DeveloperDelivery, tuple[DocumentPin, ...]]:
    """Each Title 10 delivery, and the pins that locate it. An empty tuple is a gap."""
    found: dict[DeveloperDelivery, list[DocumentPin]] = {item: [] for item in DeveloperDelivery}
    for row in pins:
        if row.delivery is not None:
            found[row.delivery].append(row)
    return {item: tuple(rows) for item, rows in found.items()}


@dataclass(frozen=True)
class KindRule:
    """One filename pattern. Listed order is the match order."""

    kind: DocumentKind
    globs: tuple[str, ...]
    folder: PayhoaFolder | None = None
    # Globs over the library path ("Confidential/Complete Financial Statements/2025/x.pdf"); empty matches any path.
    paths: tuple[str, ...] = ()


_BRACE_RE = re.compile(r"\{([^{}]+)\}")
_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


@dataclass(frozen=True)
class PathMatch:
    """Named segments taken from one path. ``group("year")`` is the ``{year}`` segment."""

    groups: tuple[tuple[str, str], ...]

    def group(self, name: str) -> str:
        for key, value in self.groups:
            if key == name:
                return value
        raise KeyError(name)


@dataclass(frozen=True)
class PathPattern:
    """A path expression.

    ``{year}`` captures one segment under that name. ``{a,b}`` stays alternation,
    the same brace form the sync globs already use. A trailing slash matches that
    directory and anything filed under it. ``*`` matches inside one segment.
    """

    expression: str

    def match(self, path: str) -> PathMatch | None:
        """Return the named groups, or ``None`` when the path misses."""
        normalized = path.replace("\\", "/").strip("/")
        for alternative in _expand_braces(self.expression):
            found = _compile_pattern(alternative).fullmatch(normalized)
            if found is not None:
                return PathMatch(tuple(found.groupdict().items()))
        return None


def _expand_braces(pattern: str) -> list[str]:
    match = _BRACE_RE.search(pattern)
    if match is None or "," not in match.group(1) or _NAME_RE.fullmatch(match.group(1)):
        return [pattern]
    before = pattern[: match.start()]
    after = pattern[match.end() :]
    out: list[str] = []
    for option in match.group(1).split(","):
        out.extend(_expand_braces(before + option + after))
    return out


def _compile_pattern(expression: str) -> re.Pattern[str]:
    under = expression.endswith("/")
    body = expression[:-1] if under else expression
    parts: list[str] = []
    index = 0
    while index < len(body):
        if body.startswith("{", index):
            end = body.find("}", index)
            name = body[index + 1 : end]
            if end < 0 or _NAME_RE.fullmatch(name) is None:
                raise ValueError(f"{expression!r} has a brace that is not a name or an alternation")
            parts.append(f"(?P<{name}>[^/]+)")
            index = end + 1
            continue
        character = body[index]
        if character == "*":
            parts.append("[^/]*")
        elif character == "?":
            parts.append("[^/]")
        else:
            parts.append(re.escape(character))
        index += 1
    pattern = "".join(parts)
    if under:
        pattern += r"(?:/.*)?"
    return re.compile(pattern)


def classify_document(
    name: str,
    rules: tuple[KindRule, ...],
    *,
    folder: PayhoaFolder | None = None,
    path: str = "",
) -> DocumentKind | None:
    """First matching rule wins. A name that matches nothing stays unclassified.

    A rule with ``folder`` needs that PayHOA folder; one with ``paths`` needs
    the library path to match a glob. Matching ignores case.
    """
    folded_name = name.casefold()
    folded_path = path.replace("\\", "/").casefold()
    for rule in rules:
        if rule.folder is not None and rule.folder is not folder:
            continue
        if rule.paths and not any(fnmatch.fnmatchcase(folded_path, pattern.casefold()) for pattern in rule.paths):
            continue
        if any(fnmatch.fnmatchcase(folded_name, pattern.casefold()) for pattern in rule.globs):
            return rule.kind
    return None


class Document:
    """One document bound to a Drive file. The id is the binding; this class does not call Drive."""

    def __init__(
        self,
        *,
        title: str,
        drive_id: str,
        kind: FileKind = FileKind.GOOGLE_DOC,
        document_kind: DocumentKind | None = None,
        published: date | None = None,
        recorded: date | None = None,
        recorder_number: str = "",
    ) -> None:
        self.title = title
        self.drive_id = drive_id
        self.kind = kind
        self.document_kind = document_kind
        self.published = published
        self.recorded = recorded
        self.recorder_number = recorder_number

    @property
    def category(self) -> DocumentCategory | None:
        if self.document_kind is None:
            return None
        return profile(self.document_kind).category

    @property
    def record(self) -> AssociationRecord | None:
        if self.document_kind is None:
            return None
        return profile(self.document_kind).record


class Amendment:
    """Mixin. This instrument changes named sections of a governing document.

    ``sections`` are citations from the instrument (``"4.2"``). ``adopted`` is the
    date the membership or board adopted it. ``recorded`` is the date on the
    county stamp. ``recorder_number`` is the document number that stamp prints.
    ``published`` is the date that copy was issued. Leave each empty rather than
    guessing. A file name can repeat the number; the number is confirmed on the
    stamp, in a later instrument that recites it, or in the county index.
    """

    def __init__(
        self,
        *,
        sections: tuple[str, ...] = (),
        adopted: date | None = None,
        document_kind: DocumentKind = DocumentKind.AMENDMENT,
        **rest: Any,
    ) -> None:
        super().__init__(document_kind=document_kind, **rest)
        self.sections = sections
        self.adopted = adopted


class GoverningDocument(Document, ABC):
    """A governing document and the amendments that change its sections.

    Civil Code 5200(a)(11) names the governing documents as association records.
    The kind (declaration, bylaws, policy) says which governing document it is.
    """

    def __init__(self, *, amendments: tuple[Document, ...] = (), **rest: Any) -> None:
        super().__init__(**rest)
        self._amendments = amendments

    @property
    def amendments(self) -> tuple[Document, ...]:
        return self._amendments

    @property
    def instruments(self) -> tuple[Document, ...]:
        """The original, then each amendment, in the order they apply."""
        return (self, *self.amendments)

    @abstractmethod
    def cite(self) -> str:
        """Short name of this governing document, such as ``"CC&Rs"``."""
