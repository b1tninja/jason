"""The recorded governing instruments: the declaration (CC&Rs), its amendments, and each phase's declaration of annexation.

Each record wraps what ``jason.community.readings`` reads (the recorder's stamp, the title, the citations with their
verb, the annexed units and common areas, the declarant, the amended sections) and adds what those mixins leave out:
the execution block (the "IN WITNESS WHEREOF" clause, blank date and signature lines, the notary's acknowledgment),
who approved an amendment and under which authority, the rental cap, and the pages the extract reaches.

The law shapes these instruments. A declaration recorded after 1985 contains a legal description, states that the
development is a condominium project (or other type), names the association, and sets out the restrictions meant to
be enforceable equitable servitudes (CIV 4250(a)). An amendment is effective once the members approve it by the
declaration's percentage, an officer certifies that approval in an acknowledged writing, and it is recorded
(CIV 4270(a)(1)-(3)); the board alone may amend to delete a discriminatory covenant (4225(b)), developer provisions
after build-out (4230), repealed cross-references (4235), or a rental restriction the law voids (4741(f), by July 1,
2022, after 28 days' general notice). A declaration may not cap rentals below 25 percent of the separate interests
(4741(b)). An extension of the declaration's term may not exceed its initial term or 20 years (4265(c)).

A reading is evidence. A supersession or an instrument number the text states is pinned in the specification
(``mystique/annexations.py``, ``mystique/ccrs.py``) only after a person reads it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from enum import Enum

from jason.community.document_models import DocumentModel, Finding, ModelContext, Severity, register, squash
from jason.community.readings import Citation, DocumentKindGuess, Relation
from jason.community.symbols import DocumentKind

from .governing_deeds import copy_findings, copy_recording
from .governing_shared import (
    READER,
    Execution,
    Recording,
    annexed_property,
    citations,
    coverage_finding,
    execution,
    map_reference,
    number_date,
    ordinal,
    page_coverage,
    cites_repealed,
    repealed_sections,
    spec_amendment_numbers,
    spec_ccrs_number,
    spec_reports,
    spec_supersessions,
)

RENTAL_FLOOR_PERCENT = 25                  # CIV 4741(b)
RENTAL_AMENDMENT_DEADLINE = date(2022, 7, 1)  # CIV 4741(f)


class Approval(Enum):
    """Who approved an amendment, and the authority that lets them."""

    MEMBERS = "members"                      # CIV 4270(a)(1)
    DECLARANT = "declarant"                  # the declaration's own amendment article, before or after first conveyance
    BOARD_RENTAL = "board-rental"            # CIV 4741(f)
    BOARD_COVENANT = "board-covenant"        # CIV 4225(b)
    BOARD_DEVELOPER = "board-developer"      # CIV 4230
    BOARD_CROSS_REFERENCE = "board-cross-reference"  # CIV 4235
    COURT = "court"                          # CIV 4275


_APPROVAL_AUTHORITY = {
    Approval.MEMBERS: "CIV 4270(a)(1)", Approval.BOARD_RENTAL: "CIV 4741(f)", Approval.BOARD_COVENANT: "CIV 4225(b)",
    Approval.BOARD_DEVELOPER: "CIV 4230", Approval.BOARD_CROSS_REFERENCE: "CIV 4235", Approval.COURT: "CIV 4275",
}


@dataclass(frozen=True)
class CitedInstrument:
    """An earlier instrument the text cites, with the verb that ties them."""

    number: str
    recorded: date | None
    title: str
    relation: str

    @classmethod
    def of(cls, c: Citation) -> "CitedInstrument":
        return cls(c.number, c.recorded, c.title, c.relation.value)


@dataclass
class DeclarationRecord:
    title: str = ""
    restated: bool = False
    recording: Recording = field(default_factory=Recording)
    certification_differs: str = ""      # a title company's certification that disagrees with the file name
    number: str = ""
    recorded: date | None = None
    declarant: str = ""
    project: str = ""
    phase_one_units: int | None = None
    total_units: int | None = None
    buildings: int | None = None
    prior_declaration: str = ""            # the instrument this one rescinds ("the Prior Declaration"), by number
    prior_declaration_recorded: date | None = None
    citations: tuple[CitedInstrument, ...] = ()
    map_reference: str = ""
    rental_cap_percent: int | None = None
    states_project_type: bool = False      # CIV 4250(a)
    names_association: bool = False        # CIV 4250(a)
    legal_description: bool = False        # CIV 4250(a)
    equitable_servitudes: bool = False     # CIV 4250(a)
    repealed_sections: tuple[str, ...] = ()
    toc_last_page: int | None = None
    last_page_seen: int | None = None
    execution: Execution = field(default_factory=Execution)
    aca_owned_in_fee: bool = False             # 1.10(a): the Association Common Area is the association's in fee
    aca_includes_structure: bool = False       # 1.10(a): it includes the entire dwelling structure, not the Units or the C.C.A.
    lot_a_is_aca: bool = False                 # 1.10(a): Lot A of the Subdivision Map is Association Common Area
    cca_elevations: tuple[int, int] | None = None  # 1.10(b): the "Cloud" Common Area, the air space between these elevations (feet)
    cca_share_text: str = ""                   # 1.10(b): the sentence giving each owner's undivided share of the C.C.A., as printed


@dataclass
class AmendmentRecord:
    title: str = ""
    ordinal: int | None = None             # First = 1, Second = 2
    recording: Recording = field(default_factory=Recording)
    certification_differs: str = ""      # a title company's certification that disagrees with the file name
    number: str = ""
    recorded: date | None = None
    maker: str = ""                        # "is made by ..." (the declarant, or the association)
    approval: Approval | None = None
    authorities: tuple[str, ...] = ()      # the statute or declaration section the text relies on ("CIV 4741(f)", "15.2(d)")
    declaration_number: str = ""           # the declaration it amends, as cited
    prior_amendments: tuple[str, ...] = ()
    annexations_cited: tuple[str, ...] = ()
    sections: tuple[str, ...] = ()         # "4.15"
    subsections: tuple[str, ...] = ()      # "4.15(a)", "4.15(m)"
    effective_on_recording: bool = False
    certified: bool = False                # an officer's certificate of the members' approval, CIV 4270(a)(2)
    extends_term: bool = False             # CIV 4265
    witness_ordinal: int | None = None     # the ordinal the IN WITNESS clause names
    draft_year: int | None = None          # "DATED: ______, 2023"
    citations: tuple[CitedInstrument, ...] = ()
    execution: Execution = field(default_factory=Execution)


@dataclass
class AnnexationRecord:
    title: str = ""
    amended_restated: bool = False
    phase: int | None = None
    recording: Recording = field(default_factory=Recording)
    certification_differs: str = ""      # a title company's certification that disagrees with the file name
    number: str = ""
    recorded: date | None = None
    declarant: str = ""
    first_unit: int | None = None
    last_unit: int | None = None
    association_common_areas: tuple[int, ...] = ()
    condominium_common_areas: tuple[int, ...] = ()
    units: int | None = None
    declaration_number: str = ""
    plan_number: str = ""
    map_reference: str = ""
    rescinds: tuple[str, ...] = ()
    citations: tuple[CitedInstrument, ...] = ()
    execution: Execution = field(default_factory=Execution)
    undivided_interest: str = ""                  # each owner's share of the phase's Condominium Common Area ("1/10th")
    assessments_commence: str = ""                # when Regular Assessments start for the annexed property
    cost_centers: bool = False                    # the instrument sets cost centers (its assessment components or 1.3(d))
    cost_center_clause: bool = False              # section 1.3(d), the cost center allocation itself, is in the text
    assessment_components: tuple[str, ...] = ()   # "general", "phases 1 and 2 property cost center", "annexed property cost center"
    phases_1_2_acas: tuple[int, ...] = ()         # the Association Common Areas the clause names as the Phases 1 and 2 Property
    annexed_center_expenses: str = ""             # what the Annexed Property Cost Center carries (1.3(d)(iii))
    phases_1_2_center_text: bool = False          # 1.3(d)(ii), the Phases 1 and 2 Property Cost Center's expenses, is in the text
    phases_1_2_clause_skipped: bool = False       # 1.3(d) runs from (i) to (iii) in the recorded text, though 1.3(a)(ii) cites (d)(ii)
    allocated_equally: bool = False               # each cost center's component "allocated and assessed equally among the Units"
    defect_period_expired: bool = False           # the clause states the WL Homes buildings' defect period has expired


_BORDER_NOISE = re.compile(r"(?<=\s)(?:[|:!;\]\[{}]+|i)(?=\s)")
_PHASE_TAIL = re.compile(r"(PHASE\s+\d{1,2})\b.*$")


def instrument_title(text: str) -> str:
    """``TitleReader`` over a head with the scan's border marks removed, cut after the phase number."""
    head = _BORDER_NOISE.sub(" ", text[:6000])
    title = READER.read_title(head) or READER.read_title(text)
    title = _PHASE_TAIL.sub(r"\1", title)
    title = re.sub(r"(?:\s+[A-Z])+$", "", title)  # a stray capital from the line after the title ("P" of "Page")
    flat = " ".join(head.split()).upper()
    if "DECLARATION OF ANNEXATION" in title and not title.startswith("AMENDED") and \
            re.search(r"AMENDED\s+AND\s+RESTATED\W{0,6}DECLARATION\s+OF\s+ANNEXATION", flat):
        title = "AMENDED AND RESTATED " + title
    return title.strip(" ,-")


def _guess(text: str) -> DocumentKindGuess:
    """The kind ``Reader`` infers from the head's title."""
    return READER.read(text[:6000]).kind


def _declaration_cited(cited: tuple[Citation, ...]) -> str:
    for c in cited:
        if re.search(r"DECLARATION\s+OF\s+COVENANTS", c.title, re.I) and not re.search(r"AMENDMENT", c.title, re.I):
            return c.number
    for c in cited:
        if re.search(r"Declaration", c.context[-160:]) and "Annexation" not in c.context[-160:] and "Amendment" not in c.title:
            return c.number
    return ""


def _flat_upper(text: str) -> str:
    return " ".join(text[:6000].split()).upper()


# The declaration.

_PRIOR = re.compile(r"(?:Book\s+(\d{8}),?\s+(?:at\s+)?Page\s+(\d{1,4})|(?:Document|Instrument)\s+No\.?\s*(\d{12}))[^()]{0,200}?\(\s*the\s+\W?Prior\s+Declaration",
                    re.I)
_DECLARANT_MEANS = re.compile(r"\W?Declarant\W?\s+(?:shall\s+)?means?\s+(.{3,160}?(?:company|corporation|partnership))(?=[,.\s])", re.I)
_RENTAL_CAP = re.compile(r"Not\s+more\s+than\s+[a-z -]*\((\d{1,3})\s?%\)[^.]{0,120}?\bUnits\b[^.]{0,120}?\b(?:leased|rented)", re.I)


declaration_repealed = cites_repealed("declaration-repealed-sections", DeclarationRecord)


class DeclarationModel(DocumentModel):
    kind = DocumentKind.DECLARATION
    name = "declaration"
    required = ("title", "declarant", "number", "recorded")
    lens_checks = (declaration_repealed,)

    def parse(self, text: str, context: ModelContext) -> DeclarationRecord | None:
        title = instrument_title(text)
        upper = title.upper()
        if "DECLARATION OF COVENANTS" not in upper or "AMENDMENT" in upper or "ANNEXATION" in upper:
            if _guess(text) is not DocumentKindGuess.DECLARATION:
                return None
        flat = squash(text)
        r = DeclarationRecord(title=title)
        r.restated = "RESTATED" in upper or bool(re.search(r"\bRestated\s+Declaration\b", flat[:6000]))
        r.recording, r.certification_differs = copy_recording(text, context.name)
        r.number, r.recorded = r.recording.number, r.recording.recorded
        r.declarant = READER.read_declarant(text) or _first(_DECLARANT_MEANS, flat)
        hit = re.search(r"\bFOR\s+([A-Z][A-Z' ]{2,40}?)(?:\s+(?:PHASE|TABLE|RECITALS)\b|$)", title)
        r.project = hit.group(1).strip() if hit else ""
        hit = re.search(r"Phase\s+(?:I|1)\s+consists\s+of\s+(\d{1,3})\s+Condominium\s+Units", flat, re.I)
        r.phase_one_units = int(hit.group(1)) if hit else None
        hit = re.search(r"consist\s+of\s*(\d{1,3})\s*Condominium\s+Units\s+located\s+within\s+(\d{1,2})\s+buildings", flat, re.I)
        if hit:
            r.total_units, r.buildings = int(hit.group(1)), int(hit.group(2))
        prior = _PRIOR.search(flat)
        if prior:
            r.prior_declaration = f"{prior.group(1)}{int(prior.group(2)):04d}" if prior.group(1) else prior.group(3)
            r.prior_declaration_recorded = number_date(r.prior_declaration)
        cited = citations(text, own=r.number)
        r.citations = tuple(CitedInstrument.of(c) for c in cited)
        r.map_reference = map_reference(text)
        cap = _RENTAL_CAP.search(flat)
        r.rental_cap_percent = int(cap.group(1)) if cap else None
        r.states_project_type = bool(re.search(r"condominium\s+project|planned\s+development|community\s+apartment|stock\s+cooperative",
                                               flat, re.I))
        r.names_association = bool(re.search(r"\W?Association\W?\s+(?:shall\s+)?means?\b", flat, re.I))
        r.legal_description = bool(re.search(r"(?:more\s+particularly\s+described|legal\s+description)", flat, re.I))
        r.equitable_servitudes = bool(re.search(r"equitable\s+servitudes?", flat, re.I))
        r.repealed_sections = repealed_sections(flat)
        r.toc_last_page, r.last_page_seen = page_coverage(text)
        r.execution = execution(text)
        common = re.search(r"two\s*\(2\)\s*types of Common Area(.{0,1800}?)Condominium\W{0,3}\s+shall mean", flat, re.I)
        if common:
            body = common.group(1)
            r.aca_owned_in_fee = bool(re.search(r"Association Common Area[^.]{0,80}owned in fee by the Association", body, re.I))
            r.aca_includes_structure = bool(re.search(r"includes the entire dwelling structure", body, re.I))
            r.lot_a_is_aca = bool(re.search(r"Lot A[^.]{0,60}is Association Co\w+ Area", body, re.I))
            heights = re.search(r"between elevations (\d+) feet and (\d+) feet", body, re.I)
            r.cca_elevations = (int(heights.group(1)), int(heights.group(2))) if heights else None
            share = re.search(r"(Each Owner shall have, as appurtenant to the Owner's Unit, an equal undivided interest.{0,400}?above the "
                              r"Owner's Unit\.)(?:.{0,400}?above the Owner's Unit\.)?", body, re.I)
            r.cca_share_text = share.group(0) if share else ""
        return r

    def check(self, r: DeclarationRecord, context: ModelContext) -> list[Finding]:
        found = copy_findings(r.recording, r.certification_differs, context.name)
        pinned = spec_ccrs_number(context.community)
        if pinned and r.prior_declaration and pinned == r.prior_declaration:
            found.append(Finding("spec-pins-rescinded-declaration", f"the specification's CC&Rs number {pinned} is the prior declaration this "
                                 "restated declaration rescinds; the declaration in force is this one (later instruments cite it by its "
                                 "own number)", Severity.CHECK))
        elif pinned and r.number and pinned != r.number:
            found.append(Finding("spec-number-differs", f"the stamp reads {r.number}; the specification pins the CC&Rs as {pinned}",
                                 Severity.CHECK))
        if r.rental_cap_percent is not None and r.rental_cap_percent < RENTAL_FLOOR_PERCENT:
            found.append(Finding("rental-cap-below-floor", f"the declaration caps rentals at {r.rental_cap_percent}% of the units; the "
                                 f"association may not enforce a cap below {RENTAL_FLOOR_PERCENT}% (check a later amendment restates it)",
                                 Severity.CHECK, "CIV 4741(b), (f)"))
        for flag, code, what in ((r.states_project_type, "no-project-type", "a statement of the development's type (condominium project)"),
                                 (r.names_association, "no-association-name", "the association's name (an \"Association\" definition)"),
                                 (r.legal_description, "no-legal-description", "a legal description of the development"),
                                 (r.equitable_servitudes, "no-equitable-servitudes", "restrictions stated as enforceable equitable servitudes")):
            if not flag:
                found.append(Finding(code, f"the text does not show {what}", Severity.CHECK, "CIV 4250(a)"))
        found.append(declaration_repealed)   # the records lens's place: the former sections cited, and where the law history puts each
        found += coverage_finding(r.toc_last_page, r.last_page_seen)
        return found


# Amendments.

_MAKER = re.compile(r"\bis\s+made\b.{0,80}?\bby\s+(.{3,140}?)\s*\(", re.I)
_SECTION = re.compile(r"\bSections?\s+(\d+(?:\.\d+)+)(?:\s*\(\s*([a-z0-9]{1,4})\s*\))?", re.I)
_CHANGED = re.compile(r"\b(?:is|are|shall\s+be)\s+(?:hereby\s+)?(?:amended|restated|removed|deleted|added|replaced|rescinded)", re.I)
_SUBSECTION = re.compile(r"subsection\s*\(\s*([a-z0-9]{1,4})\s*\)", re.I)
_TITLE_ORDINAL = re.compile(r"\b(FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|EIGHTH|NINTH|TENTH)\s+AMENDMENT\b", re.I)


def amended_sections(flat: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """The sections (``4.15``) and subsections (``4.15(a)``) the operative part says it changes. ``SectionReader`` reads
    ``Section 4.2 is amended``; this also reads ``Article 4, Sections 4.15 ... is hereby amended`` and a subsection named
    between the section and the verb."""
    start = flat.upper().find("NOW, THEREFORE")
    body = flat[start:] if start >= 0 else flat
    sections = list(READER.read_sections(body))
    subsections: list[str] = []
    for m in _SECTION.finditer(body):
        window = body[m.end(): m.end() + 260]
        verb = _CHANGED.search(window)
        if not verb:
            continue
        if m.group(1) not in sections:
            sections.append(m.group(1))
        between = window[: verb.start()]
        sub = m.group(2) or (_SUBSECTION.search(between).group(1) if _SUBSECTION.search(between) else "")
        if sub and f"{m.group(1)}({sub})" not in subsections:
            subsections.append(f"{m.group(1)}({sub})")
    return tuple(sections), tuple(subsections)


def approval_of(flat: str, maker: str) -> tuple[Approval | None, tuple[str, ...]]:
    authorities: list[str] = []
    for m in re.finditer(r"Civil\s+Code\s+(?:section\s+|§\s*)?(4\d{3}|5\d{3})(?:\s*\(\s*([a-z])\s*\))?", flat, re.I):
        cite = f"CIV {m.group(1)}" + (f"({m.group(2)})" if m.group(2) else "")
        if cite not in authorities:
            authorities.append(cite)
    for m in re.finditer(r"(?:Subsection|Section)\s+(\d+\.\d+(?:\s*\(\s*[a-z]\s*\))?)\s+of\s+the\s+(?:Prior\s+)?Declaration\s+(?:permits|provides|allows)",
                         flat, re.I):
        authorities.append(re.sub(r"\s+", "", m.group(1)))
    lower = flat.lower()
    if re.search(r"civil\s+code\s+section\s+4741|§\s*4741", lower):
        return Approval.BOARD_RENTAL, tuple(authorities)
    if re.search(r"civil\s+code\s+section\s+4225|restrictive\s+covenant\s+in\s+violation", lower):
        return Approval.BOARD_COVENANT, tuple(authorities)
    if re.search(r"civil\s+code\s+section\s+4235|correct\s+the\s+cross-reference", lower):
        return Approval.BOARD_CROSS_REFERENCE, tuple(authorities)
    if re.search(r"civil\s+code\s+section\s+4230", lower):
        return Approval.BOARD_DEVELOPER, tuple(authorities)
    if re.search(r"superior\s+court|court\s+order|civil\s+code\s+section\s+4275", lower):
        return Approval.COURT, tuple(authorities)
    if "declarant" in maker.lower() or re.search(r"permits\s+the\s+declarant\s+to\s+amend|\(\W?declarant\W?\)", lower[:4000]):
        return Approval.DECLARANT, tuple(authorities)
    if re.search(r"(?:approved|affirmative\s+vote|written\s+ballot|consent)[^.]{0,120}(?:members|voting\s+power|owners)", lower):
        return Approval.MEMBERS, tuple(authorities)
    return None, tuple(authorities)


class AmendmentModel(DocumentModel):
    kind = DocumentKind.AMENDMENT
    name = "declaration-amendment"
    required = ("title", "number", "recorded", "declaration_number", "sections", "approval")

    def parse(self, text: str, context: ModelContext) -> AmendmentRecord | None:
        title = instrument_title(text)
        upper = title.upper()
        if "ANNEXATION" in upper or ("AMENDMENT" not in upper and _guess(text) is not DocumentKindGuess.AMENDMENT):
            return None
        flat = squash(text)
        r = AmendmentRecord(title=title)
        hit = _TITLE_ORDINAL.search(title)
        r.ordinal = ordinal(hit.group(1)) if hit else None
        r.recording, r.certification_differs = copy_recording(text, context.name)
        r.number, r.recorded = r.recording.number, r.recording.recorded
        r.maker = _first(_MAKER, flat)
        r.approval, r.authorities = approval_of(flat, r.maker)
        cited = citations(text, own=r.number)
        r.citations = tuple(CitedInstrument.of(c) for c in cited)
        r.declaration_number = _declaration_cited(cited)
        r.prior_amendments = tuple(c.number for c in cited if c.number != r.declaration_number and re.search(r"Amendment", c.title, re.I))
        r.annexations_cited = tuple(c.number for c in cited if c.relation in (Relation.ANNEXES_UNDER, Relation.RESCINDS))
        r.sections, r.subsections = amended_sections(flat)
        r.effective_on_recording = bool(re.search(r"effective\s+upon\s+(?:its\s+)?Record", flat, re.I))
        r.certified = bool(re.search(r"\bcertif(?:y|ies)\b[^.]{0,200}(?:approv|vote|ballot)", flat, re.I))
        r.extends_term = bool(re.search(r"extend\w*\s+the\s+term", flat, re.I))
        witness = flat[flat.upper().rfind("WITNESS WHEREOF"):] if "WITNESS WHEREOF" in flat.upper() else ""
        hit = _TITLE_ORDINAL.search(witness[:600])
        r.witness_ordinal = ordinal(hit.group(1)) if hit else None
        hit = re.search(r"DATED:?\s*_{3,},?\s*(\d{4})", flat)
        r.draft_year = int(hit.group(1)) if hit else None
        r.execution = execution(text)
        return r

    def check(self, r: AmendmentRecord, context: ModelContext) -> list[Finding]:
        # An amendment is effective only once recorded (CIV 4270(a)(3)): a copy with no stamp is not the effective instrument.
        found = copy_findings(r.recording, r.certification_differs, context.name, authority="CIV 4270(a)(3)")
        if r.execution.date_blank or r.execution.signature_blank:
            found.append(Finding("unsigned-draft", "the date or signature lines are blank: an unsigned draft", Severity.CHECK))
        if r.ordinal and r.witness_ordinal and r.ordinal != r.witness_ordinal:
            found.append(Finding("ordinal-mismatch", f"the title calls this amendment number {r.ordinal}, but the signature clause adopts "
                                 f"amendment number {r.witness_ordinal}", Severity.PROBLEM))
        if r.approval is None:
            found.append(Finding("approval-not-stated", "the text does not say who approved the amendment or under what authority",
                                 Severity.CHECK, "CIV 4270(a)(1)"))
        elif r.approval is Approval.MEMBERS and not r.certified:
            found.append(Finding("no-approval-certificate", "no officer's certificate that the members approved it; the certificate must "
                                 "be executed and acknowledged", Severity.CHECK, "CIV 4270(a)(2)"))
        elif r.approval is Approval.BOARD_RENTAL:
            when = r.recorded or r.execution.dated or (date(r.draft_year, 1, 1) if r.draft_year else None)
            if when and when > RENTAL_AMENDMENT_DEADLINE:
                found.append(Finding("after-rental-amendment-deadline", f"the board's rental amendment is dated {when.year}; the statute "
                                     f"required it by {RENTAL_AMENDMENT_DEADLINE}", Severity.CHECK, "CIV 4741(f)"))
            found.append(Finding("rental-amendment-notice", "the board must give 28 days' general notice with the text, purpose, and effect "
                                 "before approving, and decide at a board meeting; the text cannot show that it did", Severity.CHECK,
                                 "CIV 4741(f)"))
        elif r.approval is Approval.BOARD_DEVELOPER:
            found.append(Finding("developer-amendment-vote", "a board amendment deleting developer provisions needs 30 days' notice and a "
                                 "majority of a quorum of the members", Severity.CHECK, "CIV 4230(c), (d)"))
        elif r.approval is Approval.BOARD_CROSS_REFERENCE and r.number:
            found.append(Finding("record-board-resolution", "a restated declaration corrected under 4235 is recorded with the board's "
                                 "resolution", Severity.INFO, "CIV 4235(b)"))
        if r.extends_term:
            found.append(Finding("term-extension", "the amendment extends the declaration's term; no single extension may exceed the "
                                 "initial term or 20 years", Severity.INFO, "CIV 4265(b), (c)"))
        pinned = spec_ccrs_number(context.community)
        if pinned and r.declaration_number and pinned != r.declaration_number:
            found.append(Finding("amends-unpinned-declaration", f"amends the declaration recorded as {r.declaration_number}; the "
                                 f"specification pins the CC&Rs as {pinned}", Severity.CHECK))
        if r.number and context.community is not None and r.number not in spec_amendment_numbers(context.community):
            found.append(Finding("amendment-not-pinned", f"the specification's CC&Rs list no amendment recorded as {r.number}",
                                 Severity.INFO))
        return found


# Annexations.

class AnnexationModel(DocumentModel):
    kind = DocumentKind.ANNEXATION
    name = "declaration-of-annexation"
    required = ("title", "phase", "number", "recorded", "first_unit", "last_unit", "declaration_number")

    def parse(self, text: str, context: ModelContext) -> AnnexationRecord | None:
        title = instrument_title(text)
        if "ANNEXATION" not in title.upper() and "DECLARATION OF ANNEXATION" not in _flat_upper(text):
            return None
        flat = squash(text)
        r = AnnexationRecord(title=title)
        r.amended_restated = title.upper().startswith("AMENDED") or bool(
            re.search(r"AMENDED\s+AND\s+RESTATED\W{0,6}DECLARATION\s+OF\s+ANNEXATION", _flat_upper(text)))
        r.phase = READER.read_phase(text)
        if r.phase is None:
            hit = re.search(r"PHASE\s+(\d{1,2})\b", title, re.I)
            r.phase = int(hit.group(1)) if hit else None
        r.recording, r.certification_differs = copy_recording(text, context.name)
        r.number, r.recorded = r.recording.number, r.recording.recorded
        r.declarant = READER.read_declarant(text)
        annexed = annexed_property(text)
        r.first_unit, r.last_unit = annexed.first_unit, annexed.last_unit
        r.association_common_areas, r.condominium_common_areas = annexed.association_common_areas, annexed.condominium_common_areas
        if r.first_unit is not None and r.last_unit is not None:
            r.units = r.last_unit - r.first_unit + 1
        cited = citations(text, own=r.number)
        r.citations = tuple(CitedInstrument.of(c) for c in cited)
        r.declaration_number = _declaration_cited(cited)
        plans = [c.number for c in cited if c.relation is Relation.PLAN or "Plan" in c.title]
        r.plan_number = plans[0] if plans else ""
        r.map_reference = map_reference(text)
        r.rescinds = tuple(c.number for c in cited if c.relation is Relation.RESCINDS)
        r.execution = execution(text)
        # "a 1/10th undivided interest"; OCR prints the slash as a 1 ("1110th").
        share = re.search(r"\b1\s*(?:/|1)\s*(\d{1,2})\s*(?:\s*(?:th|st|nd|rd))?\s+undivided\s+interest", flat, re.I)
        r.undivided_interest = f"1/{share.group(1)}" if share else ""
        commence = re.search(r"Regular Assessments shall commence with respect to the Annexed Property (on .{10,120}?Declarant)\.", flat, re.I)
        r.assessments_commence = commence.group(1) if commence else ""
        r.cost_center_clause = bool(re.search(r"Cost Center Allocation", flat, re.I))
        components = []
        if re.search(r"General Assessment Component", flat, re.I):
            components.append("general")
        if re.search(r"Phases 1 and 2 Property Cost Center", flat, re.I):
            components.append("phases 1 and 2 property cost center")
        if re.search(r"Annexed Property Cost Center", flat, re.I):
            components.append("annexed property cost center")
        r.assessment_components = tuple(components)
        r.cost_centers = r.cost_center_clause or len(components) > 1
        clause = re.search(r"Segregation of Expenses for Buildings\.(.{0,600}?)(?:were originally constructed|as such areas)", flat, re.I)
        if clause:
            r.phases_1_2_acas = tuple(int(n) for n in dict.fromkeys(re.findall(r"Association Common Area\s+(\d)", clause.group(1))))
        expenses = re.search(r"Cost Center For Expenses Attributable to Annexed Property\.\s*The expenses associated with (.{10,200}?) shall be included",
                             flat, re.I)
        r.annexed_center_expenses = expenses.group(1) if expenses else ""
        # Phase 3 heads it "Cost Center For Expenses the Phases 1 and 2 Property", without "Attributable to"; OCR prints 1 as I.
        r.phases_1_2_center_text = bool(re.search(r"Cost Center For Expenses (?:Attributable to )?(?:the )?Phases [1Il] and 2", flat, re.I))
        # Phases 6 and 7 go from (i), which ends "... Annexed Property Owners only.", straight to (iii).
        r.phases_1_2_clause_skipped = not r.phases_1_2_center_text and bool(re.search(
            r"Annexed Property Owners only\.\s*\(\w{1,4}\)\s*Cost Center For Expenses Attributable to Annexed Property", flat, re.I))
        r.allocated_equally = bool(re.search(r"Cost Center Assessment Component[^.]{0,200}allocated and assessed equally", flat, re.I))
        r.defect_period_expired = bool(re.search(r"statutory period for asserting construction defects[^.]{0,160}has expired", flat, re.I))
        return r

    def check(self, r: AnnexationRecord, context: ModelContext) -> list[Finding]:
        found = copy_findings(r.recording, r.certification_differs, context.name)
        named_amended = "AMENDED" in (context.name or "").upper() or "RESTATED" in (context.name or "").upper()
        if context.name and r.amended_restated and not named_amended:
            found.append(Finding("name-omits-amended", f"the file name reads as the original phase {r.phase} annexation; the text is the "
                                 "amended and restated instrument", Severity.CHECK))
        elif context.name and named_amended and not r.amended_restated:
            found.append(Finding("name-says-amended", "the file name says amended; the text is not the amended and restated instrument",
                                 Severity.CHECK))
        report = next((p for p in spec_reports(context.community) if getattr(p, "phase", None) == r.phase), None) if r.phase else None
        if report is not None:
            if r.recorded and report.annexation and r.recorded != report.annexation:
                found.append(Finding("annexation-date-differs", f"recorded {r.recorded}; the specification has phase {r.phase} annexed on "
                                     f"{report.annexation}", Severity.CHECK))
            if r.units and report.units and r.units != report.units:
                found.append(Finding("unit-count-differs", f"annexes {r.units} units ({r.first_unit}-{r.last_unit}); the specification's "
                                     f"phase {r.phase} has {report.units}", Severity.CHECK))
        facts = spec_supersessions(context.community)
        pinned = {(f.number, f.superseded_by) for f in facts}
        for old in r.rescinds:
            if r.number and (old, r.number) not in pinned:
                found.append(Finding("supersession-not-pinned", f"rescinds and supersedes {old}; the specification does not pin that yet",
                                     Severity.CHECK))
        for fact in facts:
            if r.number and fact.number == r.number:
                found.append(Finding("rescinded", f"the specification records this instrument as rescinded by {fact.superseded_by}",
                                     Severity.INFO))
        ccrs = spec_ccrs_number(context.community)
        if ccrs and r.declaration_number and ccrs != r.declaration_number:
            found.append(Finding("annexes-under-unpinned-declaration", f"annexes under the declaration recorded as {r.declaration_number}; "
                                 f"the specification pins the CC&Rs as {ccrs}", Severity.CHECK))
        if not r.execution.acknowledged:
            found.append(Finding("no-acknowledgment-in-text", "no notary's acknowledgment in the text (it may be an image)", Severity.CHECK))
        found.extend(_cost_center_findings(r, context))
        return found


def _cost_center_findings(r: AnnexationRecord, context: ModelContext) -> list[Finding]:
    """The annexation's cost centers and Condominium Common Area share, against the specification's Association Common Areas."""
    from jason.community.base import CostCenter

    found: list[Finding] = []
    areas = {a.number: a for a in getattr(context.community, "association_common_areas", lambda: ())() or ()} if context.community else {}
    for number in r.association_common_areas:
        area = areas.get(number)
        if area is None:
            continue
        if r.phase is not None and area.phase != r.phase:
            found.append(Finding("aca-phase-differs", f"annexes A.C.A. {number}; the specification has it in phase {area.phase}", Severity.CHECK))
        if r.first_unit is not None and (r.first_unit, r.last_unit) != area.units:
            found.append(Finding("aca-units-differ", f"annexes units {r.first_unit}-{r.last_unit} with A.C.A. {number}; the specification has "
                                 f"{area.units[0]}-{area.units[1]}", Severity.CHECK))
        if r.cost_centers and area.cost_center is not CostCenter.ANNEXED:
            found.append(Finding("aca-cost-center", f"the instrument puts A.C.A. {number} in the Annexed Property Cost Center; the specification "
                                 f"has {area.cost_center.value if area.cost_center else 'none'}", Severity.CHECK))
    if r.cost_centers and areas:
        pinned = tuple(sorted(n for n, a in areas.items() if a.cost_center is CostCenter.PHASES_1_AND_2))
        if r.phases_1_2_acas and tuple(sorted(r.phases_1_2_acas)) != pinned:
            found.append(Finding("phases-1-2-acas-differ", f"names A.C.A. {', '.join(map(str, r.phases_1_2_acas))} as the Phases 1 and 2 Property; "
                                 f"the specification has {', '.join(map(str, pinned))}", Severity.CHECK))
    if r.cost_centers:
        found.append(Finding("cost-centers", "Regular Assessments are a General Assessment Component shared by every unit plus the unit's cost "
                             "center component, shared equally within the Phases 1 and 2 Property (A.C.A. 3 and 8) or the Annexed Property; "
                             "the budget must keep the cost centers apart", Severity.INFO, "Declaration of Annexation 1.3(a), (b), (d)"))
        if not r.cost_center_clause:
            found.append(Finding("cost-center-clause-missing", "the assessment components name the cost centers, but section 1.3(d), which "
                                 "allocates their expenses, is not in the text; the extract is missing pages", Severity.CHECK))
        elif r.phases_1_2_clause_skipped:
            found.append(Finding("phases-1-2-clause-skipped", "1.3(a)(ii) says the Phases 1 and 2 Property Cost Center component consists "
                                 "of the expenses \"described in subsection 1.3(d)(ii), below\", but this instrument's 1.3(d) goes from (i) "
                                 "to (iii): the text has no (ii). The Phase 3 annexation's 1.3(d)(ii) defines those expenses; whether it "
                                 "governs this phase is for counsel", Severity.CHECK, "Declaration of Annexation 1.3(a)(ii), (d)"))
        elif not r.phases_1_2_center_text:
            found.append(Finding("phases-1-2-clause-missing", "subsection 1.3(d)(ii), which lists the Phases 1 and 2 Property Cost Center's "
                                 "expenses, is not in the text; read it from the recorded copy", Severity.CHECK))
    if r.undivided_interest and r.units:
        denominator = re.search(r"/(\d+)", r.undivided_interest)
        if denominator and int(denominator.group(1)) != r.units:
            found.append(Finding("cca-share-differs", f"gives each owner a {r.undivided_interest} share of C.C.A. "
                                 f"{', '.join(map(str, r.condominium_common_areas)) or '?'}, but annexes {r.units} units", Severity.CHECK))
    return found


def _first(pattern: re.Pattern, flat: str) -> str:
    hit = pattern.search(flat)
    return " ".join(hit.group(1).split()).strip(" ,") if hit else ""


register(DeclarationModel())
register(AmendmentModel())
register(AnnexationModel())

__all__ = ["Approval", "CitedInstrument", "DeclarationRecord", "AmendmentRecord", "AnnexationRecord", "DeclarationModel", "AmendmentModel",
           "AnnexationModel", "instrument_title", "amended_sections", "approval_of"]
