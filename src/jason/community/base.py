"""Abstract community: the specification a task can ask, not the APIs it calls."""

from __future__ import annotations

import fnmatch
import re
from abc import ABC, abstractmethod
from enum import Enum
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable

from jason.community.documents import DocumentPin, GoverningDocument
from jason.community.symbols import (
    AssociationRecord,
    Building,
    DocumentKind,
    DocumentRule,
    FileKind,
    KnownFile,
    Parity,
    InsuranceVisit,
    DeveloperDelivery,
    PayhoaFolder,
    PolicyKind,
    PublicDrive,
    SitePage,
    Street,
    Utility,
)


@dataclass(frozen=True)
class Developer:
    """One subdivider. ``names`` are the forms the county index uses.

    One developer can appear under more than one index name. A later builder
    who resumed the project is a separate developer, not another spelling.
    """

    name: str
    names: tuple[str, ...]


@dataclass(frozen=True)
class BuildingRange:
    """One flood building: a street range and which side of the street."""

    number: Building
    street: Street
    low: int
    high: int
    parity: Parity
    policy_number: str = ""
    location_prints_building: bool = False

    def contains(self, street_number: int, street: Street) -> bool:
        if street is not self.street:
            return False
        if not self.low <= street_number <= self.high:
            return False
        if self.parity is Parity.ODD:
            return street_number % 2 == 1
        if self.parity is Parity.EVEN:
            return street_number % 2 == 0
        return self.parity is Parity.ANY


@dataclass(frozen=True)
class TransactionRule:
    """One utility identity. Listed order is the match order."""

    utility: Utility
    category_id: int | None
    rule_names: tuple[str, ...] = ()
    description_contains: tuple[str, ...] = ()
    description_contains_all: tuple[str, ...] = ()
    description_requires: str = ""
    description_any: tuple[str, ...] = ()
    blocked_by: tuple[Utility, ...] = ()

    def matches(self, tx: dict[str, Any], *, category_id: int | None = None) -> bool:
        rule = tx.get("transactionRule") or {}
        rule_name = str(rule.get("name") or "").upper() if isinstance(rule, dict) else ""
        description = str(tx.get("description") or "").upper()
        if any(name in rule_name for name in self.rule_names):
            return True
        if any(token in description for token in self.description_contains):
            return True
        if self.description_contains_all and all(token in description for token in self.description_contains_all):
            return True
        if self.description_requires and self.description_requires in description:
            if any(token in description for token in self.description_any):
                return True
        active_category = self.category_id if category_id is None else category_id
        return active_category is not None and tx.get("categoryId") == active_category


@dataclass(frozen=True)
class KnownAnchor:
    """One well-known Drive file, Doc, Sheet, or Site."""

    file: KnownFile
    kind: FileKind
    name: str
    drive_id: str
    payhoa_folder: PayhoaFolder | None = None
    publish_name: str = ""
    tab: str = ""
    records: tuple[AssociationRecord, ...] = ()
    document_kind: DocumentKind | None = None


class AccountPurpose(Enum):
    OPERATING = "operating"
    RESERVE = "reserve"


class ReserveLine(Enum):
    """What a budget line moves into the reserve: the regular contribution, or the repayment of reserve funds borrowed
    for operating (Civil Code 5515)."""

    CONTRIBUTION = "contribution"
    REPAYMENT = "repayment"


class CostCenter(Enum):
    """The assessment cost center a building's Association Common Area belongs to (each Watt annexation, section 1.3)."""

    PHASES_1_AND_2 = "phases 1 and 2 property"   # ACA 3 and ACA 8, built by WL Homes in 2008
    ANNEXED = "annexed property"                 # Watt's annexed buildings


@dataclass(frozen=True)
class CostCenterRule:
    """How a cost center shares its expenses: ``expenses`` are the costs it carries, allocated equally among the units of
    its Association Common Areas, on top of the General Assessment Component every unit shares under the declaration."""

    center: CostCenter
    expenses: str
    allocation: str
    source: str


@dataclass(frozen=True)
class AssociationCommonArea:
    """One Association Common Area (A.C.A.) of the Condominium Plan: the parcel the association owns in fee, which holds a
    building's structure, everything but its units and its Condominium Common Area (C.C.A.). ``number`` is the plan's
    designation ("A.C.A. 3"); it is the building's number. ``phase`` is the DRE phase that annexed it, and ``units`` the
    plan's unit numbers in it (the 2007 plan for buildings 3 and 8, Watt's numbering for the rest)."""

    number: int
    apn: str
    building: Building
    phase: int
    units: tuple[int, int]
    builder: str = ""
    cost_center: CostCenter | None = None

    @property
    def label(self) -> str:
        return f"ACA {self.number}"

    @property
    def unit_count(self) -> int:
        return self.units[1] - self.units[0] + 1


@dataclass(frozen=True)
class MeetingSchedule:
    """When the board meets: the ``nth`` ``weekday`` (0 = Monday) of each month in ``regular_months`` (every month when
    empty) at ``time`` in ``place``; the annual meeting of members the same weekday of ``annual_month``. ``resolution`` is
    the one that fixes it; ``practice`` notes a practice that differs from it."""

    weekday: int
    nth: int
    time: str
    place: str
    regular_months: tuple[int, ...] = ()
    annual_month: int | None = None
    resolution: str = ""
    practice: str = ""

    def day_in(self, year: int, month: int) -> date:
        first = date(year, month, 1)
        offset = (self.weekday - first.weekday()) % 7
        return first + timedelta(days=offset + 7 * (self.nth - 1))

    def next_meeting(self, after: date, *, monthly: bool = False) -> date:
        """The next regular meeting after ``after``: in a regular month, or any month when ``monthly`` (the practice)."""
        year, month = after.year, after.month
        for _ in range(24):
            day = self.day_in(year, month)
            if day > after and (monthly or not self.regular_months or month in self.regular_months):
                return day
            year, month = (year, month + 1) if month < 12 else (year + 1, 1)
        raise ValueError("no meeting within two years")


class VoteBasis(Enum):
    """What carries a board motion, as the bylaws or counsel's reading of them set it."""

    MAJORITY_PRESENT = "a majority of the directors present at a meeting at which a quorum is present"
    MAJORITY_IN_OFFICE = "a majority of the directors in office"


@dataclass(frozen=True)
class RuleSource:
    """Where a board rule comes from: the provision jason recites from disk (``cite``, as ``jason cite`` reads it:
    "Bylaws 1.2"), or counsel's reading (``counsel`` names whose and when; ``reading`` is its words), shown labeled
    as a reading, never as the provision's words."""

    cite: str = ""
    counsel: str = ""
    reading: str = ""

    @property
    def label(self) -> str:
        if self.counsel:
            return f"{self.counsel}'s reading" + (f" of {self.cite}" if self.cite else "")
        return self.cite


@dataclass(frozen=True)
class BoardRule:
    """The board's size and quorum as the bylaws set them. ``seats`` is the number the board fixed within
    ``minimum``..``maximum``; a quorum is a majority of the directors then in office, never fewer than ``quorum_floor``.

    ``vote_basis`` is what carries a motion, from ``vote_source``. ``interested_in_quorum`` says whether a director who
    disclosed an interest and does not vote still counts toward the quorum and among the directors present, from
    ``interested_source``. Either is None when neither the bylaws' words nor counsel's reading is on file: the meeting
    room then says "not on file; ask counsel" and never fills it in."""

    seats: int
    minimum: int
    maximum: int
    quorum_floor: int = 2
    source: str = ""
    vote_basis: VoteBasis | None = None
    vote_source: RuleSource | None = None
    interested_in_quorum: bool | None = None
    interested_source: RuleSource | None = None
    quorum_source: str = ""        # the provision that sets the quorum ("Bylaws 1.2"), cited where a quorum is counted

    def quorum(self, in_office: int | None = None) -> int:
        """Directors needed for a quorum when ``in_office`` directors hold office (default: every seat filled)."""
        serving = self.seats if in_office is None else in_office
        return max(serving // 2 + 1, self.quorum_floor)


@dataclass(frozen=True)
class NoticePeriod:
    """The notice of a board meeting the governing documents require (CIV 4920(b)(3)): ``days`` before the meeting, from
    ``source`` (the provision, "Bylaws 1.2"). ``executive_days`` is set only where the provision says it applies to a
    meeting held solely in executive session; otherwise that meeting takes the statute's period."""

    days: int
    source: str
    executive_days: int | None = None


@dataclass(frozen=True)
class SpeakingLimit:
    """The time limit the board established for members to speak (CIV 4925(b)): ``minutes`` for each member, from the
    board's adopted ``source`` (a resolution or policy)."""

    minutes: int
    source: str


@dataclass(frozen=True)
class BankAccount:
    """One association bank account, known by the last four digits its statement files carry."""

    suffix: str
    purpose: AccountPurpose
    bank: str = ""
    label: str = ""


@dataclass(frozen=True)
class LicensedPerson:
    """A person on a company's license: a qualified manager, an operator, or a field representative."""

    name: str
    role: str
    number: str = ""
    status: str = ""

    def is_named(self, other: str) -> bool:
        """"TURNER, KYLE T" and "Kyle Turner (NORTH)" name the same person: the surname and first name both appear."""
        words = lambda text: {w for w in re.findall(r"[a-z]+", text.lower()) if len(w) > 1 and w not in {"north", "south", "central", "com", "specialt", "jr"}}  # noqa: E731
        mine, theirs = words(self.name), words(other)
        return len(mine & theirs) >= 2


@dataclass(frozen=True)
class VendorLicense:
    """A vendor's state license as a person read it at the licensing board, and on what date.

    ``relationships_seen`` against ``relationships_total`` says how much of the license's roster was read;
    a person not in ``people`` may still be on the part not read.
    """

    board: str
    number: str
    kind: str
    classes: tuple[str, ...]
    status: str
    issued: Any
    verified: Any
    people: tuple[LicensedPerson, ...] = ()
    relationships_seen: int = 0
    relationships_total: int = 0
    lookup: str = ""

    def person(self, name: str) -> LicensedPerson | None:
        """The roster entry for a name, a license (Operator, then Field Representative) before an office held."""
        rank = {"Operator": 0, "Field Representative": 1}
        found = [p for p in self.people if p.is_named(name)]
        return min(found, key=lambda p: rank.get(p.role, 2)) if found else None


@dataclass(frozen=True)
class VendorPortal:
    """A vendor's customer portal jason signs in to: the vendor, its platform and account, and where its bills go.

    ``key`` names the Keeper record's setting (``<key>_record_uid`` in .env). ``payhoa_words`` are the words a
    PayHOA bank description carries for this vendor; ``budget_line`` is the expense category its invoices belong to.
    """

    key: str
    vendor: str
    platform: Any
    account: str
    budget_line: str
    payhoa_words: tuple[str, ...] = ()
    service: str = ""
    license: Any = None


@dataclass(frozen=True)
class FilingRule:
    """One row of the filing table: which documents it takes, and the folder they go to.

    ``kind`` is a ``DocumentKind``, or None for any kind (an unclassified document too). ``senders`` names sender
    directory rows and ``source_kinds`` kinds of source (``SourceKind``); empty means any. ``path`` is the folder's
    names from the filing root, one name a level (a name may hold "/"), with ``{vendor}`` (the sender row's name) and
    ``{year}`` (the fiscal year the message came in) filled in.

    The row's test is an applicability condition (``condition``): the document's kind, the sender by name, and the
    sender's kind of source. ``verdict`` asks it of one document, so a filing explains itself as every other rule row
    does (``Verdict.explain()``), and ``takes`` is whether it applies. An unclassified document has no kind fact, so
    a rule that names a kind is undetermined for it and does not take it: a miss stays a miss."""

    kind: Any
    path: tuple[str, ...]
    senders: tuple[str, ...] = ()
    source_kinds: tuple[Any, ...] = ()

    def condition(self) -> Any:
        """What the rule takes, as a ``jason.community.applicability`` condition; ``ALWAYS`` for a rule with no test."""
        from jason.community.applicability import ALWAYS, AllOf, Fact, In, Is

        parts: list[Any] = []
        if self.kind is not None:
            parts.append(Is(Fact.DOCUMENT_KIND, self.kind))
        for fact, values in ((Fact.SENDER, self.senders), (Fact.SOURCE_KIND, self.source_kinds)):
            if values:
                parts.append(Is(fact, values[0]) if len(values) == 1 else In(fact, frozenset(values)))
        return ALWAYS if not parts else parts[0] if len(parts) == 1 else AllOf(*parts)

    def verdict(self, sender: Any, kind: Any) -> Any:
        """The rule asked of one document: its ``Verdict``, with the facts that decided it and where each is from."""
        from jason.community.applicability import evaluate, filing_facts

        return evaluate(self.condition(), filing_facts(sender, kind))

    def takes(self, sender: Any, kind: Any) -> bool:
        return self.verdict(sender, kind).applies


@dataclass(frozen=True)
class EmailFiling:
    """Where a counterparty's email attachments are filed in Drive (``jason.tasks.vendor_files``): the rules in match
    order, from the folder ``root`` (a Drive folder id; "root" is My Drive). The first rule that takes the document
    wins; a document no rule takes goes to ``fallback``. A miss stays in the vendor's own folder, never a guess."""

    root: str
    rules: tuple[FilingRule, ...]
    fallback: tuple[str, ...] = ("Vendors", "{vendor}", "{year}")

    def path_for(self, sender: Any, kind: Any, year: int | str) -> tuple[tuple[str, ...], FilingRule | None]:
        """The folder path for a document, and the rule that placed it (None for the fallback)."""
        rule = next((r for r in self.rules if r.takes(sender, kind)), None)
        path = rule.path if rule else self.fallback
        return tuple(part.format(vendor=sender.name, year=year) for part in path), rule

    def explain(self, sender: Any, kind: Any) -> str:
        """Why a document goes where it does: the verdict of the rule that takes it, or, for the fallback, that no
        rule applies. The same words ``Verdict.explain()`` gives for any other rule row."""
        rule = next((r for r in self.rules if r.takes(sender, kind)), None)
        if rule is not None:
            return rule.verdict(sender, kind).explain()
        from jason.community.applicability import filing_facts

        known = "; ".join(v.describe() for v in filing_facts(sender, kind).values)
        return (f"no rule applies ({len(self.rules)} asked, in order): the fallback folder\n  known: {known}"
                + ("" if kind is not None else "\n  missing: the document's kind (the classifier gave none)"))


@dataclass(frozen=True)
class LibraryFolder:
    """A PayHOA folder and, when the public site embeds one, its Drive id."""

    folder: PayhoaFolder
    payhoa_id: int
    path: str
    document_rule: DocumentRule | None = None
    drive: PublicDrive | None = None
    records: tuple[AssociationRecord, ...] = ()


@dataclass(frozen=True)
class DriveRoot:
    """Signed-in Drive root folder that corresponds to a PayHOA library path."""

    drive_folder: str
    payhoa_folder: PayhoaFolder
    drive: PublicDrive | None = None
    document_rule: DocumentRule | None = None


@dataclass(frozen=True)
class SyncRule:
    """One Drive folder glob and the PayHOA path it publishes to."""

    id: DocumentRule
    drive_folder: str
    drive: PublicDrive
    glob: str
    destination: PayhoaFolder
    exclude_globs: tuple[str, ...] = ()
    also_seen_in: str = ""
    records: tuple[AssociationRecord, ...] = ()

    def as_dict(self, payhoa_path: str) -> dict[str, Any]:
        row: dict[str, Any] = {
            "id": self.id.value,
            "drive_folder": self.drive_folder,
            "drive_id": self.drive.value,
            "glob": self.glob,
            "payhoa": payhoa_path,
            "mode": "name-match",
        }
        if self.exclude_globs:
            row["exclude"] = list(self.exclude_globs)
        if self.also_seen_in:
            row["also_seen_in"] = self.also_seen_in
        return row


@dataclass(frozen=True)
class ExcludedFolder:
    drive_folder: str
    drive_id: str
    reason: str

    def as_dict(self) -> dict[str, str]:
        return {
            "drive_folder": self.drive_folder,
            "drive_id": self.drive_id,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class InsuranceYear:
    """One archived Drive folder under Insurance, named by the policy year."""

    year: int
    drive_id: str

    def excluded_folder(self) -> ExcludedFolder:
        return ExcludedFolder(
            f"Insurance/{self.year}",
            self.drive_id,
            "archived insurance year, not the current library",
        )


@dataclass(frozen=True)
class Policy:
    """One line of coverage. Flood policies name the building; the others do not."""

    kind: PolicyKind
    number: str = ""
    renewal: date | None = None
    building: Building | None = None
    declaration_name: str = ""
    location_prints_building: bool = False
    # The term's carrier, the program or wholesaler that issues and bills it, and the agent of record.
    carrier: str = ""
    program: str = ""
    agent: str = ""
    # Numbers the same coverage carried in earlier terms (a number can roll each term: -00, -01; 4125..., 4126...).
    prior_numbers: tuple[str, ...] = ()
    # The PayHOA categories its premium is booked to.
    premium_categories: tuple[str, ...] = ()
    # The per-occurrence deductible, integer cents: below it the carrier pays nothing, so it is the least loss worth a claim.
    deductible_cents: int | None = None

    @property
    def numbers(self) -> tuple[str, ...]:
        return tuple(n for n in (self.number, *self.prior_numbers) if n)


@dataclass(frozen=True)
class PremiumRules:
    """How an approval in the minutes is followed to the premiums it bought.

    ``words`` mark an approval about insurance; ``weak_words`` ("renewal", "policy", "package") count only when no other
    rule links the approval. ``coverage_words`` say which coverage an approval names, in order; an approval that names
    none means the ``package`` kinds (the flood policies renew on their own dates). ``payees`` are who a premium is paid
    to beyond the policies' carriers, programs, and agents and the insurer senders: an NFIP premium debit, a premium
    finance company (``jason.community.sources.Sender``). ``categories`` are PayHOA categories of insurance spending that
    are no one policy's premium (a policy fee, an old catch-all). ``lead_days`` and ``follow_days`` bound the payments
    from the meeting: a premium is paid ahead, then in installments.
    """

    words: str
    weak_words: str
    coverage_words: tuple[tuple[PolicyKind, str], ...]
    package: tuple[PolicyKind, ...]
    payees: tuple[Any, ...] = ()
    categories: tuple[str, ...] = ()
    lead_days: int = 60
    follow_days: int = 300


@dataclass(frozen=True)
class InsuranceCatalog:
    """Coverage facts, plus how to walk Insurance without listing every file.

    Root files are selected by ``file_globs``. A child folder whose name is a
    four-digit year is a year folder: the walk stops there and does not take
    ``*.pdf``. Policy numbers and renewals stay on ``Policy`` because a file
    name does not carry them.
    """

    years: tuple[InsuranceYear, ...]
    policies: tuple[Policy, ...]
    buildings: tuple[BuildingRange, ...]
    file_globs: tuple[str, ...] = (
        "FLOOD POLICY *",
        "Certificate of Insurance*",
        "Personal Insurance Checklist*",
        "RCBAP Lender rules.pdf",
        "Custom evidence of insurance*",
    )

    def year(self, year: int) -> InsuranceYear:
        for row in self.years:
            if row.year == year:
                return row
        raise KeyError(year)

    def match(self, path: str) -> int | None:
        """Return the calendar year when ``path`` is ``Insurance/<year>/...``.

        The shape is the glob ``Insurance/[0-9][0-9][0-9][0-9]``. A year that
        matches is not automatically archived; only years in this catalog are.
        """
        parts = path.replace("\\", "/").strip("/").split("/")
        match parts:
            case ["Insurance", year, *_] if year.isdigit() and len(year) == 4:
                return int(year)
            case _:
                return None

    def visit(self, path: str) -> InsuranceVisit:
        """Classify one Insurance path. Year folders are not a file catalog."""
        parts = path.replace("\\", "/").strip("/").split("/")
        match parts:
            case ["Insurance", year] if _is_year(year):
                return InsuranceVisit.YEAR_FOLDER
            case ["Insurance", year, *_] if _is_year(year):
                return InsuranceVisit.YEAR_FOLDER
            case ["Insurance", name] if self._root_file(name):
                return InsuranceVisit.ROOT_FILE
            case _:
                return InsuranceVisit.SKIP

    def _root_file(self, name: str) -> bool:
        return any(fnmatch.fnmatch(name, pattern) for pattern in self.file_globs)

    def master(self) -> Policy | None:
        """The master (building) policy, or None when the catalog has none."""
        return next((row for row in self.policies if row.kind is PolicyKind.MASTER), None)

    def flood_policy(self, building: Building) -> Policy:
        for row in self.policies:
            if row.kind is PolicyKind.FLOOD and row.building is building:
                return row
        raise KeyError(building)

    def excluded_folders(self) -> tuple[ExcludedFolder, ...]:
        return tuple(row.excluded_folder() for row in self.years)


@dataclass(frozen=True)
class Theme:
    """A community's brand tokens: the accent and what sits on it, the brand font, and the hero surface the public page
    and the meeting stage use. Light values first; ``dark`` carries the dark-scheme overrides by the same keys. The
    console applies them on ``[data-community=<slug>]``; its data views take the brand only, the public page the full
    surface (``surface``) when ``data-reach="full"``. ``font_url`` is a stylesheet link the page may load (Google Fonts)."""

    wordmark: str                               # the short name shown as the brand ("Mystique")
    accent: str                                 # "#5b3f8f"
    on_accent: str = "#fff"
    accent_2: str = ""
    on_accent_2: str = ""
    brand_font: str = "system-ui"
    brand_weight: int = 700
    brand_case: str = "none"                    # "uppercase" | "none"
    brand_tracking: str = "0"
    hero: str = ""
    hero_ink: str = ""
    hero_muted: str = ""
    hero_line: str = ""
    font_url: str = ""
    dark: dict[str, str] | None = None          # same keys, dark-scheme values
    surface: dict[str, str] | None = None       # bg/panel/ink/muted/line for the public page
    surface_dark: dict[str, str] | None = None

    def tokens(self, scheme: str = "light") -> dict[str, str]:
        """The CSS custom properties for one scheme, by name without the ``--``."""
        base = {"accent": self.accent, "on-accent": self.on_accent, "accent-2": self.accent_2, "on-accent-2": self.on_accent_2,
                "brand-font": self.brand_font, "brand-weight": str(self.brand_weight), "brand-case": self.brand_case,
                "brand-tracking": self.brand_tracking, "hero": self.hero, "hero-ink": self.hero_ink, "hero-muted": self.hero_muted,
                "hero-line": self.hero_line}
        if scheme == "dark":
            base.update({k.replace("_", "-"): v for k, v in (self.dark or {}).items()})
        return {k: v for k, v in base.items() if v}


class OfficerRole(Enum):
    PRESIDENT = "president"
    VICE_PRESIDENT = "vice president"
    SECRETARY = "secretary"
    TREASURER = "treasurer"
    DIRECTOR = "director"
    MANAGER = "manager"


@dataclass(frozen=True)
class Officer:
    """One person in a board or management role. ``approves`` names what the role may approve on its own
    (``"the treasurer"``, ``"a fluent reviewer"``); ``"the board"`` is never a person's: it is a vote at a meeting
    (CIV 4910) that the president or the secretary records. ``email`` is the Google account the person signs in to
    jason-web with (``jason.web.signin``); a private fact, empty when the person does not sign in."""

    role: OfficerRole
    name: str
    approves: tuple[str, ...] = ()
    email: str = ""

    def can_approve(self, approver: str) -> bool:
        if approver == "the board":
            return self.role in (OfficerRole.PRESIDENT, OfficerRole.SECRETARY)
        return approver in self.approves


def offices_of(officers: Iterable[Officer], name: str) -> tuple[Officer, ...]:
    """Every row a person holds: one person may hold more than one office where the bylaws allow (a secretary who is
    also the treasurer is two rows with the same name)."""
    return tuple(o for o in officers if o.name == name)


@dataclass(frozen=True)
class VacancyProvision:
    """How the governing documents fill a vacant office: the provision (``source``, "Bylaws 1.2") and its words as
    stored (``words``, recited whole; empty: cited, not quoted). jason never fills a vacancy or routes an office's work
    to another: who acts meanwhile is only what these words say."""

    source: str
    words: str = ""


class SeatKind(Enum):
    """Which seat a term is for: a director's seat the members elect, or an office the board fills."""

    DIRECTOR = "director"
    OFFICER = "officer"


@dataclass(frozen=True)
class Term:
    """One person's term in a seat, as the record that filled it says: a private fact (``jason.community.roster``).

    ``office`` is the office of an officer's term (None for a director's). ``end`` None: no end date on record, as
    for an officer who serves at the pleasure of the board. ``source`` is the election record (the minutes of the
    meeting that elected or appointed, or the inspector of elections' report); ``provision`` the governing documents'
    provision that sets the term, as given (cited, not quoted). jason sets no term and invents no end: a term has ended
    only when its recorded end is past (``ended``)."""

    person: str
    seat: SeatKind
    start: date
    end: date | None = None
    office: OfficerRole | None = None
    source: str = ""
    provision: str = ""

    def ended(self, today: date) -> bool:
        return self.end is not None and self.end < today


class IdentityProvider(Enum):
    """Who vouches for a person signing in to the console. Google (a Workspace account) is the one built; another
    is a new member here and a new flow in ``jason.web.signin``."""

    GOOGLE = "google"


@dataclass(frozen=True)
class SignInProvider:
    """One way to sign in to the console for this community: the identity provider, the Keeper record holding its
    OAuth client (``client_id``, ``client_secret``), and the email domains whose accounts it accepts (empty: the
    community's ``email_domains``). ``key`` names it when there is more than one; ``label`` is the button's words."""

    key: str
    record_uid: str
    provider: IdentityProvider = IdentityProvider.GOOGLE
    domains: tuple[str, ...] = ()
    label: str = ""


@dataclass(frozen=True)
class SitePageRef:
    page: SitePage
    path: str
    payhoa_folders: tuple[PayhoaFolder, ...] = ()


class Community(ABC):
    """Community-specific facts. Subclasses load a specification; they do not perform tasks."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    def corporate_name(self) -> str:
        """Name on recorded instruments. Empty until the specification sets it."""
        return ""

    @property
    def region(self) -> str:
        """Where the association's public records are kept, as ``"<state>/<county>"`` (``"ca/<county>"``): which county
        recorder, assessor, and tax collector jason reads (phase 6 of docs/profiles.md). Empty until set."""
        return ""

    @property
    @abstractmethod
    def slug(self) -> str: ...

    @property
    @abstractmethod
    def org_id(self) -> int: ...

    @property
    @abstractmethod
    def root(self) -> Path: ...

    @abstractmethod
    def document_sync_rules(self) -> dict[str, Any]: ...

    @property
    def sync_rules(self) -> tuple[SyncRule, ...]:
        """The Drive sync rules as records. Empty until the specification sets them."""
        return ()

    def kind_rules(self) -> tuple[Any, ...]:
        """The document kind rules (`documents.KindRule`), in match order. Empty until the specification sets them."""
        return ()

    def classify_document(self, name: str, folder: Any = None, path: str = "") -> Any:
        """The `DocumentKind` the kind rules give a file by name, PayHOA folder, and library path; a miss is None."""
        from jason.community.documents import classify_document

        return classify_document(name, self.kind_rules(), folder=folder, path=path)

    @abstractmethod
    def buildings(self) -> tuple[BuildingRange, ...]: ...

    @abstractmethod
    def document_rules(self) -> tuple[DocumentRule, ...]: ...

    @abstractmethod
    def transaction_rules(self) -> tuple[TransactionRule, ...]: ...

    @abstractmethod
    def insurance_workbook_id(self) -> str: ...

    @abstractmethod
    def known_file(self, file: KnownFile) -> KnownAnchor: ...

    @abstractmethod
    def library_folder(self, folder: PayhoaFolder) -> LibraryFolder: ...

    @abstractmethod
    def drive_roots(self) -> tuple[DriveRoot, ...]: ...

    @abstractmethod
    def site_pages(self) -> tuple[SitePageRef, ...]: ...

    @abstractmethod
    def insurance(self) -> InsuranceCatalog: ...

    @property
    @abstractmethod
    def ccrs(self) -> GoverningDocument: ...

    @abstractmethod
    def pins(self) -> tuple[DocumentPin, ...]: ...

    def developers(self) -> tuple[Developer, ...]:
        """Subdividers pinned for this community. Empty until the specification sets them."""
        return ()

    def public_reports(self):
        """Bureau files and the phase each one covers. Empty until the specification sets them."""
        return ()

    def plan_blocks(self):
        """Assessor blocks that still use the original plan's unit numbers."""
        return ()

    def unit_blocks(self):
        """Every building's unit numbering, for reading a unit number. Defaults to the plan blocks."""
        return self.plan_blocks()

    def held_units(self):
        """Bulk deeds that name the units of a building still held on that day."""
        return ()

    def floor_plans(self):
        """The plans each developer offered. Empty until the specification sets them."""
        return ()

    def library_folders(self) -> tuple[LibraryFolder, ...]:
        """Every PayHOA library folder the specification pins. Empty until it sets them."""
        return ()

    def known_files(self) -> tuple[KnownAnchor, ...]:
        """Every well-known Drive file the specification pins. Empty until it sets them."""
        return ()

    def solar_program(self):
        """The developer's shared solar program, or None when the community has none."""
        return None

    def paint_schedules(self) -> tuple:
        """The association's paint schedules (``jason.community.paint.PaintSchedule``). Empty until the specification sets them."""
        return ()

    def vendor_portals(self) -> tuple[VendorPortal, ...]:
        """Vendor customer portals jason reads bills and service records from. Empty until the specification sets them."""
        return ()

    def facts(self) -> tuple:
        """What the association knows about itself (``jason.community.facts.Fact``). Empty until the specification sets them."""
        return ()

    def original_specs(self) -> tuple:
        """Each plan's original finishes and equipment (``jason.community.unit_record.OriginalSpec``). Empty until set."""
        return ()

    def unit_coverage(self):
        """The two lists the documents draw for a unit's components (``unit_record.UnitCoverage``), or None."""
        return None

    def loss_ladder(self) -> tuple:
        """The five questions of a loss and their provisions (``loss_packet.LadderStep``). Empty until set."""
        return ()

    def open_questions(self) -> tuple:
        """Questions the association has put to an agent, counsel, or the board (``loss_packet.OpenQuestion``). Empty until set."""
        return ()

    def deductible_policy(self):
        """The board's adopted deductible guideline as a rule row, or None until adopted."""
        return None

    def interior_reports(self) -> tuple:
        """Owner-reported interior colors by plan. Empty until a register supplies them."""
        return ()

    def mail_addresses(self):
        """Addresses a letter to the association can be sent to, each with what it is (``MailAddress``). Empty until set."""
        return ()

    def streets(self) -> tuple[Street, ...]:
        """The streets the association's units and site are on: a reader finds "123 Main St" in a bill or letter only
        on one of them. Empty until set, and then no street address is read as the association's."""
        return ()

    def name_pattern(self) -> str:
        """A regular expression for the association's distinctive name word as letters print it, OCR misreadings
        included (``oak\\s*r[il1]dge``). Empty until set, and then no text is taken to name the association."""
        return ""

    def evidence_plan(self):
        """Where the repair paperwork is in Drive (``jason.community.incidents.EvidencePlan``), or None until the
        specification sets it."""
        return None

    def senders(self):
        """The association's named counterparties (``jason.community.sources.Sender``). Empty until the specification sets them."""
        return ()

    def email_filing(self) -> EmailFiling | None:
        """Where vendors' email attachments are filed in Drive (``EmailFiling``), or None until the specification sets it."""
        return None

    def premium_rules(self) -> PremiumRules | None:
        """How approvals in the minutes are followed to insurance premiums (``PremiumRules``), or None until set."""
        return None

    def site(self) -> str:
        """The association's public website URL, or "" when it has none."""
        return ""

    def theme(self) -> Theme | None:
        """The association's brand for the console and its public owner page (``Theme``), or None for jason's neutral look."""
        return None

    def officers(self) -> tuple[Officer, ...]:
        """The board's officers and the manager by role (``Officer``), names from the private facts; empty until set.
        A person who holds two offices is two rows (``offices_of``)."""
        return ()

    def vacancy_provision(self, office: OfficerRole) -> VacancyProvision | None:
        """The provision that governs a vacancy in ``office`` (``VacancyProvision``), recited where no one holds it.
        None until the specification sets it: the console then says no one holds the office, and nothing more."""
        return None

    def terms(self) -> tuple[Term, ...]:
        """Each director's and officer's term (``Term``) with the election record that set it, from the private facts
        (``data/spec/<profile>/terms.json``, read by ``jason.community.roster.terms_of``); empty until recorded."""
        return ()

    def sign_in(self) -> tuple[SignInProvider, ...]:
        """How people sign in to the console for this community (``SignInProvider``): its own Google Workspace
        client or clients; a private fact. Empty: the installation's (``jason.access``)."""
        return ()

    def copy_priority(self):
        """Which channel's copy of a document to read first (``jason.community.copies.Channel``), best first."""
        from jason.community.copies import Channel

        return tuple(Channel)

    def email_domains(self) -> tuple[str, ...]:
        """The association's own email domains. Empty until set."""
        return ()

    def google_groups(self) -> tuple:
        """The association's Google Groups (``GoogleGroup``): address, name, and what mail to it is for. Empty until set."""
        return ()

    def task_prompts(self) -> tuple:
        """Each kind of task's prompt (``jason.community.prompts.TaskPrompt``): purpose, controlling law, what to look for,
        the records that hold the facts, and the required elements. Empty until set."""
        return ()

    def packets(self) -> tuple:
        """The packets the association delivers as one PDF (``jason.community.packets.Packet``). Empty until set."""
        return ()

    def packet(self, key: str):
        """One packet by key; KeyError when the specification has none."""
        for packet in self.packets():
            if packet.key == key:
                return packet
        raise KeyError(key)

    def notice_rules(self) -> tuple:
        """The notices the association sends, with who receives each and how
        (``jason.community.notices.NoticeRule``). Empty until set."""
        return ()

    def notice_rule(self, key: str):
        for rule in self.notice_rules():
            if rule.key == key:
                return rule
        raise KeyError(key)

    def notice_provisions(self) -> tuple:
        """What the governing documents say about notice beside the statute (``jason.community.notices.
        NoticeProvision``): a clause that asks more, the same, less, or differently than a catalog requirement
        (``jason.community.notice_catalog``), or a notice only the documents require. Empty until set."""
        return ()

    def leasing_rules(self):
        """The declaration's leasing cap and minimum term (``jason.community.leasing.LeasingRules``); None until set."""
        return None

    def unit_city_state_zip(self) -> str:
        """Every unit's last address line ("City, ST 00000"), so a street line at one of the community's own
        units can be completed (``postal.read_mailing_address``). Empty until set."""
        return ""

    def help_articles(self) -> tuple:
        """The software vendor's help articles that letters and emails point owners to (``key``, ``title``, ``url``,
        ``steps``), for ``{HELP:key}`` in a template. Empty until set."""
        return ()

    def payhoa_fields(self) -> tuple:
        """The PayHOA custom fields the association uses or proposes (``jason.community.tags.PayhoaField``). Empty
        until set."""
        return ()

    def payhoa_tags(self) -> tuple:
        """The PayHOA tags the association uses or proposes, with what each means
        (``jason.community.tags.PayhoaTag``). Empty until set."""
        return ()

    def identity(self):
        """Who the association is, as its notices name it (`identity.Identity`). The default knows only the name,
        corporate name, and units' city line; a profile sets the rest."""
        from jason.community.identity import Identity

        return Identity(self.name, corporate_name=self.corporate_name, unit_city_state_zip=self.unit_city_state_zip())

    def letterhead(self):
        """The letterhead every rendering puts around a document (`identity.LetterheadSpec`). The default is the
        name alone, with no Doc to copy and no logo."""
        from jason.community.identity import LetterheadSpec

        identity = self.identity()
        return LetterheadSpec(identity.name.upper(), footer=identity.official_address)

    def citations(self) -> dict[Any, str]:
        """The association's own governing-document section for each `template_values.CitationPurpose` a notice
        cites ("Bylaws Section 4.2"). Empty until set: a template then prints the purpose's general wording."""
        return {}

    def coverages_not_carried(self) -> tuple[str, ...]:
        """Kinds of insurance the association does not carry and says so in its notices ("earthquake"). Empty until
        set: a notice then says nothing about coverage the records do not list."""
        return ()

    def drive_home(self):
        """The Drive folders generated documents are filed in (`identity.DriveHome`); empty until set."""
        from jason.community.identity import DriveHome

        return DriveHome()

    def email_letterhead(self):
        """The letterhead as an email frame (``jason.community.email_html.Letterhead``)."""
        return self.letterhead().email()

    def prompt_context(self) -> tuple[str, ...]:
        """Facts about the association every task prompt carries: its name, how it is managed, who signs, how members
        reach it. Empty until set."""
        return ()

    def task_prompt(self, kind):
        """The prompt for one ``TaskKind``; KeyError when the specification has none."""
        for task in self.task_prompts():
            if task.kind is kind:
                return task
        raise KeyError(kind)

    def task_for_subject(self, subject: str):
        """The task whose ``subjects`` patterns match a template's subject or a Doc's title, first row first; None on a miss."""
        import re

        for task in self.task_prompts():
            if any(re.search(pattern, subject or "") for pattern in task.subjects):
                return task
        return None

    def permit_portal(self):
        """The permit portal and the collection holding the association's records. None until set."""
        return None

    def closed_permit_statuses(self) -> tuple[str, ...]:
        """Permit statuses that need nothing more. Empty until set."""
        return ()

    def request_forms(self):
        """The association's request forms (form id, title/message/attachment question ids, topics). Empty until set."""
        return ()

    def owner_information(self):
        """The owner-information cycle's forms (Civil Code 4040, 4041): an object carrying ``OWNER_INFO`` (the form),
        ``OWNER_INFO_CYCLE``, ``EARLIER_ELECTIONS``, ``FORM_IMPORTS``, and ``OWNER_INFO_COMPLETED_COMMENT`` (the
        board's comment when a request is completed). None until set."""
        return None

    def request_topics(self):
        """The topics that make an owner's email a request of the association. Empty until set."""
        return ()

    def intent_rules(self):
        """The patterns that name what a subject asks (``jason.community.topics.IntentRule``). Empty until set."""
        return ()

    def topic_sources(self):
        """Where each topic's answer is likely written (``jason.community.topics.TopicSources``). Empty until set."""
        return ()

    def topic_rules(self):
        """The words that name each topic in a subject line (``jason.community.topics.TopicRule``). Empty until set."""
        return ()

    def obligations(self):
        """The association's recurring deadlines (``jason.community.obligations.Obligation``). Empty until set."""
        return ()

    def applicability_facts(self) -> tuple:
        """The association's own facts that decide what applies to it (``jason.community.applicability.FactValue``,
        source PROFILE): its kind of development, occupancy class, unit count, city, water purveyor. Empty until set,
        so a condition on them is undetermined, never a crash (docs/applicability.md)."""
        return ()

    def life_safety_systems(self) -> tuple:
        """The association's life safety systems (``jason.community.life_safety.LifeSafetySystem``): each one's kind,
        the standard it was installed under where a record says, what it serves, and who services it. Empty until
        set, so a rule that turns on a system is undetermined, with the question of which systems there are."""
        return ()

    def bank_accounts(self) -> tuple[BankAccount, ...]:
        """The association's bank accounts by statement suffix. Empty until the specification sets them."""
        return ()

    def association_common_areas(self) -> tuple[AssociationCommonArea, ...]:
        """The Condominium Plan's Association Common Areas, one per building. Empty until the specification sets them."""
        return ()

    def cost_centers(self) -> tuple[CostCenterRule, ...]:
        """The assessment cost centers and how each shares its expenses. Empty until the specification sets them."""
        return ()

    def legal_cases(self) -> tuple:
        """The association's legal matters (``jason.community.legal_cases.LegalCase``). Empty until the specification sets them."""
        return ()

    def meeting_schedule(self) -> MeetingSchedule | None:
        """When the board and the members meet. None until the specification sets it."""
        return None

    def rule_changes(self) -> tuple:
        """Proposed operating rule changes (``jason.community.rule_changes.RuleChange``). Empty until the specification sets them."""
        return ()

    def rule_change_records(self) -> tuple:
        """The association's own rule changes, made or proposed, whose stages jason reads from disk
        (``jason.community.record_stages.RuleChangeRecord``). Empty until the specification sets them."""
        return ()

    def zoom_meeting_rules(self) -> tuple:
        """Topic words that name a Zoom meeting's kind (``jason.zoom.models.MeetingRule``), in order. Empty until set."""
        return ()

    def executive_break_patterns(self) -> tuple[str, ...]:
        """Regexes for the line where the open meeting adjourns to executive session on the same call. Empty until set."""
        return ()

    def zoom_history_since(self) -> date | None:
        """The first day the association met on Zoom; the sync reads its history from there. None until set."""
        return None

    def meeting_record_rules(self) -> tuple:
        """What meeting files are called (``jason.community.meeting_records.RecordRule``), in order. Empty until set."""
        return ()

    def meeting_email_rules(self) -> tuple:
        """Emails about a meeting (``jason.community.meeting_records.EmailRule``), in order. Empty until set."""
        return ()

    def privilege_parties(self) -> tuple:
        """Counsel, insurers, the other side, by email domain (``jason.community.privilege.PrivilegeParty``). Empty until set."""
        return ()

    def privilege_name_rules(self) -> tuple:
        """Names that tell a document's privilege (``jason.community.privilege.PrivilegeNameRule``), in order. Empty until set."""
        return ()

    def privilege_names(self) -> tuple:
        """(a regex for what a communication is called, (regex, sensitivity) rows). Empty until set."""
        return ("", ())

    def registers(self) -> tuple:
        """The registers jason and the board keep as Google Sheets (``jason.community.registers.Register``). Empty until set."""
        return ()

    def registers_folder(self) -> str:
        """The Drive folder new register Sheets are created in. Empty until set."""
        return ""

    def legal_holds(self) -> tuple:
        """The legal holds in force (``jason.community.holds.LegalHoldSpec``). Empty until set."""
        return ()

    def calendar_policy(self):
        """The board calendar's event titles (``jason.community.board_calendar.CalendarPolicy``). None until set."""
        return None

    def calendar_id(self) -> str:
        """The id of the Google calendar ``jason calendar`` writes to, which the UI embeds. Empty means none."""
        return ""

    def photo_album_rule(self):
        """How jason names the Photos albums it keeps (``jason.community.photos.AlbumNameRule``). None until set."""
        return None

    def photos_drive_folder(self) -> str:
        """The Drive folder imported photos are copied into. Empty until the board picks one."""
        return ""

    def app_properties(self) -> tuple:
        """The appProperties jason writes on Drive files (``jason.community.drive_labels``). Empty until set."""
        return ()

    def agenda_item_rules(self) -> tuple:
        """The document kinds an agenda item brings, by its title (``jason.community.agenda_items.ItemRule``). Empty until set."""
        return ()

    def agenda_link_rules(self) -> tuple:
        """What an agenda link points at (``jason.community.agenda_links.LinkRule``), in order. Empty until set."""
        return ()

    def communication_search(self) -> tuple[str, ...]:
        """Words to search PayHOA's communications log by for meeting notices. Empty until set."""
        return ()

    def not_meeting_records(self) -> tuple[str, ...]:
        """Path prefixes whose files are never meeting records. Empty until set."""
        return ()

    def citable_documents(self) -> tuple:
        """The Google Docs other documents cite, with their aliases (``jason.community.outlines.CitableDocument``)."""
        return ()

    def revision_series(self) -> tuple:
        """Documents whose versions ``jason revisions`` compares, with file names that hold an older version beyond
        the document's title and aliases (``jason.community.revision_detection.RevisionSeries``). Empty: each citable
        document, found by its title and aliases only."""
        return ()

    def book_entries(self) -> tuple:
        """Which of the association's documents fills which book (``jason.community.books.BookEntry``): the
        declaration's document in ``decl``, a separately adopted set of rules as a part of ``rules``. A record
        address (``jason://decl/6.2(a)``) reads through it; a document no row maps is addressed by its own key. Empty
        until set."""
        return ()

    def defined_terms(self) -> tuple:
        """The terms the association's documents define, each with the section that defines it
        (``jason.community.definitions.DefinedTerm``): reciting a section that uses one carries its definition beside
        it. Empty until set."""
        return ()

    def governing_set(self):
        """What the association's own documents say "the Governing Documents" are
        (``jason.community.definitions.GoverningSet``), kept apart from the Act's list (CIV 4150). None until set."""
        return None

    def resolutions_folder(self) -> str:
        """The Drive folder whose Google Docs are the board's resolutions. Empty until set."""
        return ""

    def library_outlined_kinds(self) -> dict:
        """Document kinds outlined from the library's text extracts (recorded PDFs with no Doc), each with the key of
        the document it supplements."""
        return {}

    def document_templates(self) -> tuple:
        """The letter templates in Drive (``jason.community.templates.DocumentTemplate``). Empty until set."""
        return ()

    def document_template(self, kind):
        """The template of ``kind``, or None."""
        return next((t for t in self.document_templates() if t.kind is kind), None)

    def hearing_policy(self):
        """How a disciplinary hearing is held on Zoom (``jason.zoom.models.HearingPolicy``). None until set."""
        return None

    def board_meeting_policy(self):
        """How a board meeting is held on Zoom (``jason.zoom.models.BoardMeetingPolicy``). None until set."""
        return None

    def board(self) -> BoardRule | None:
        """The board's size and quorum rule. None until the specification sets it. Who holds the seats is PayHOA's
        "Board Member" tag, read live, not a fact here."""
        return None

    def board_notice_period(self) -> NoticePeriod | None:
        """The notice of a board meeting the governing documents require, with its provision. None until the
        specification sets it: the statute's period then applies (CIV 4920(a), (b))."""
        return None

    def open_forum_limit(self) -> SpeakingLimit | None:
        """The time limit the board established for members to speak (CIV 4925(b)). None until the board adopts one:
        the meeting room then says no limit is on record, never a default."""
        return None

    def board_items_sheet(self) -> str:
        """The Google Sheet id of the board's action items. Empty until the specification sets it."""
        return ""

    def board_items_title(self) -> str:
        """The title of the board's action items Sheet and Google Tasks list, as the association named them. Empty until
        the specification sets it: jason then names them from the association's name (``board_items.sheet_title``)."""
        return ""

    def procedures(self) -> tuple:
        """The community's own procedures (``jason.community.procedures.Procedure``), beside jason's general ones.
        Empty until the specification keeps some."""
        return ()

    def lessons(self) -> tuple:
        """The community's own lessons (``jason.community.lessons.Lesson``): what went wrong here, beside jason's
        general ones. Empty until the specification keeps some."""
        return ()

    def response_rules(self) -> tuple:
        """The profile's response clocks (``jason.community.responses.ResponseRule``): the governing documents' own,
        and proposed policies where the law is silent; they replace jason's for the same kind. Empty until set."""
        return ()

    def request_kind_rules(self) -> tuple:
        """The profile's own classification rows (``responses.KindRule``), tried before jason's. Empty until set."""
        return ()

    def assignments(self) -> tuple:
        """Who does each duty and when (``jason.community.schedule.Assignment``): the roles and schedules jason
        proposes and the board adopts. Empty until the specification keeps some."""
        return ()

    def people_task_rules(self) -> tuple:
        """How people's own Google Tasks and calendar events match what jason tracks
        (``jason.community.people_tasks.PeopleTaskRule``), tried in order before the general matches. Empty until set."""
        return ()

    def evidence_rules(self) -> tuple:
        """The profile's own evidence rules (``jason.community.schedule_evidence.EvidenceRule``): what shows a duty
        done that it covers by its own documents' sections, or the words its minutes use. Tried before jason's.
        Empty until set."""
        return ()

    def fiscal_year_end(self) -> tuple[int, int] | None:
        """The fiscal year's last day as (month, day), the anchor for the annual reports. None until set."""
        return None

    def living_documents(self) -> tuple:
        """The documents kept as amended (``jason.community.living.LivingDocument``): each one's base text, its
        amendments, corrections, and the rule rows that copy its terms. Empty until the specification keeps some."""
        return ()

    def conflicts(self) -> tuple:
        """The community's written provisions a higher authority displaces, wholly or in part
        (``jason.community.authority_order.Conflict``): a governing document or rule followed only as far as the law
        allows. Empty until the specification records some."""
        return ()

    def law_readings(self) -> tuple:
        """The board's and counsel's readings of the law and of the governing documents
        (``jason.community.law_readings.LawReading``), each tied to the digest of the words it reads. Empty until
        the specification records some."""
        return ()

    def owners_manual(self):
        """The owner's manual taken apart (``jason.community.manual.ManualSpec``): which of its sections are the
        operating rules, copies, policies, and guidance, and where each goes. None until the specification sets it."""
        return None

    def packet_reports(self) -> tuple[str, ...]:
        """The reports every board packet carries, as references (``{REPORT:treasurers-report period=previous-month}``),
        shown as already built (``live_reports``). Empty until the specification sets them."""
        return ()

    def utility_accounts(self):
        """Each utility account's purpose on the site (``UtilityAccount``). Empty until the specification sets them."""
        return ()

    def utility_budget_lines(self):
        """The budget line name for each utility ``Service``. Empty until the specification sets them."""
        return {}

    def reserve_budget_lines(self) -> dict[ReserveLine, str]:
        """The PayHOA budget line for each ``ReserveLine``. Empty until the specification sets them."""
        return {}

    def utility_roll(self):
        """How the utility agencies move a delinquent account onto the tax bill. Empty until the specification sets them."""
        return ()

    def supersessions(self):
        """Governing instruments a later one rescinded or replaced. Empty until the specification sets them."""
        return ()

    def index_project(self) -> str:
        """Leading name of the declaration. Empty until the specification sets it."""
        return ""

    def index_association(self) -> str:
        """Leading name shared by the association's index spellings."""
        return ""

    def developer_file(self) -> dict[DeveloperDelivery, tuple[DocumentPin, ...]]:
        """Title 10 deliveries located by a pin. An empty tuple is still missing."""
        from jason.community.documents import developer_file

        return developer_file(self.pins())

    def deed_numbers(self) -> tuple[str, ...]:
        """Document numbers on pinned grant deeds.

        These are the facts an ownership analysis starts from. A recorder
        search hit is not one of them until its file is pinned. Two files for
        the same stamp count once.
        """
        from jason.community.recorder import document_numbers
        from jason.community.symbols import DocumentKind

        titles = tuple(row.title for row in self.pins() if row.kind is DocumentKind.GRANT_DEED)
        return document_numbers(*titles)

    @abstractmethod
    def units(self) -> tuple[str, ...]: ...

    @abstractmethod
    def common_areas(self) -> tuple[str, ...]: ...

    def reserve_components(self):
        """Reserve components with life, cost center, and classification.

        The default is empty. An association specification fills it in.
        """
        return ()

    def parcels(self) -> tuple[str, ...]:
        """Residential units, then the common-area parcels the association is taxed on."""
        return self.units() + self.common_areas()

    def building_for_address(self, address: str) -> BuildingRange | None:
        """Return the flood building for a unit street address, or None."""
        number, street = split_address(address)
        if number is None or street is None:
            return None
        hits = [row for row in self.buildings() if row.contains(number, street)]
        if len(hits) == 1:
            return hits[0]
        return None


def _is_year(name: str) -> bool:
    return name.isdigit() and len(name) == 4


def split_address(address: str) -> tuple[int | None, Street | None]:
    """Split ``3007 ENCHANTED WALK`` into a street number and a `Street` member."""
    parts = address.strip().split()
    if len(parts) < 2 or not parts[0].isdigit():
        return None, None
    token = " ".join(parts[1:]).upper()
    street = next((item for item in Street if item.value == token), None)
    if street is None:
        return None, None
    return int(parts[0]), street


# A pattern that matches nothing: what a reader searches for when the profile names no street or name.
NEVER = r"(?!)"


def street_words(streets: Iterable[Street]) -> dict[str, Street]:
    """Each street by the first word of its name, as a letter abbreviates it: ``MAIN`` for MAIN ST."""
    return {street.value.split()[0]: street for street in streets}


def alternation(words: Iterable[str]) -> str:
    """``words`` as one regular-expression alternation, longest first; `NEVER` when there are none."""
    ordered = sorted({w for w in words if w}, key=len, reverse=True)
    return "|".join(re.escape(w) for w in ordered) or NEVER


def name_regex(name: str) -> str:
    """The association's full name as a pattern: its words apart by any spacing, "Association" abbreviated or not."""
    words = [r"assoc(?:iation)?" if w.casefold() == "association" else re.escape(w) for w in (name or "").split()]
    return r"\s+".join(words) or NEVER


def read_unit_address(text: str) -> tuple[int | None, Street | None]:
    """A street number and a `Street` from an address as a person typed it ("3007 Enchanted Wk., Sacramento CA",
    "5655 whimsical lane #2"): the first number, then the street whose name's first word follows it, a typo allowed.
    A miss is (None, None); it never guesses between two streets."""
    import difflib

    m = re.search(r"\b(\d{3,5})\s+([A-Za-z]+)", text or "")
    if not m:
        return None, None
    word = m.group(2).upper()
    heads = {street.value.split()[0]: street for street in Street}
    hit = difflib.get_close_matches(word, list(heads), n=2, cutoff=0.8)
    if len(hit) != 1:
        return None, None
    return int(m.group(1)), heads[hit[0]]


def assign_building(address: str, ranges: tuple[BuildingRange, ...] | list[BuildingRange]) -> BuildingRange | None:
    """Match one address against a building table. Overlaps and misses return None."""
    number, street = split_address(address)
    if number is None:
        return None
    hits = [row for row in ranges if street is not None and row.contains(number, street)]
    if len(hits) == 1:
        return hits[0]
    return None
