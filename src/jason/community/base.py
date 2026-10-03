"""Abstract community: the specification a task can ask, not the APIs it calls."""

from __future__ import annotations

import fnmatch
import re
from abc import ABC, abstractmethod
from enum import Enum
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

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


@dataclass(frozen=True)
class BoardRule:
    """The board's size and quorum as the bylaws set them. ``seats`` is the number the board fixed within
    ``minimum``..``maximum``; a quorum is a majority of the directors then in office, never fewer than ``quorum_floor``."""

    seats: int
    minimum: int
    maximum: int
    quorum_floor: int = 2
    source: str = ""

    def quorum(self, in_office: int | None = None) -> int:
        """Directors needed for a quorum when ``in_office`` directors hold office (default: every seat filled)."""
        serving = self.seats if in_office is None else in_office
        return max(serving // 2 + 1, self.quorum_floor)


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

    def vendor_portals(self) -> tuple[VendorPortal, ...]:
        """Vendor customer portals jason reads bills and service records from. Empty until the specification sets them."""
        return ()

    def mail_addresses(self):
        """Addresses a letter to the association can be sent to, each with what it is (``MailAddress``). Empty until set."""
        return ()

    def evidence_plan(self):
        """Where the repair paperwork is in Drive (``jason.community.incidents.EvidencePlan``), or None until the
        specification sets it."""
        return None

    def senders(self):
        """The association's named counterparties (``jason.community.sources.Sender``). Empty until the specification sets them."""
        return ()

    def premium_rules(self) -> PremiumRules | None:
        """How approvals in the minutes are followed to insurance premiums (``PremiumRules``), or None until set."""
        return None

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

    def board(self) -> BoardRule | None:
        """The board's size and quorum rule. None until the specification sets it. Who holds the seats is PayHOA's
        "Board Member" tag, read live, not a fact here."""
        return None

    def board_items_sheet(self) -> str:
        """The Google Sheet id of the board's action items. Empty until the specification sets it."""
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
