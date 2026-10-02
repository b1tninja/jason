"""Mystique Community Association, expressed as objects."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jason.community.base import (
    BuildingRange,
    Community,
    Developer,
    GoverningDocument,
    DriveRoot,
    InsuranceCatalog,
    DocumentPin,
    KnownAnchor,
    LibraryFolder,
    SitePageRef,
    SyncRule,
    TransactionRule,
)

from .anchors import FILES, LIBRARY, PAGES, ROOTS
from .developers import ASSOCIATION, DEVELOPERS, PROJECT
from .ccrs import CCRS
from .documents import EXCLUDED, KIND_RULES, RULES
from .parcels import ASSOCIATION_COMMON_AREAS, COMMON_AREAS, COST_CENTERS, UNITS
from .pins import PINS
from .plans import FLOOR_PLANS
from .annexations import SUPERSESSIONS
from .solar import SOLAR_PROGRAM
from .utilities import UTILITY_ACCOUNTS, UTILITY_BUDGET_LINES, UTILITY_ROLL
from .banking import BANK_ACCOUNTS, BOARD, BOARD_ITEMS_SHEET, MEETING_SCHEDULE, RESERVE_BUDGET_LINES
from .cases import LEGAL_CASES
from .vendors import VENDOR_PORTALS
from .reports import HELD_UNITS, PLAN_BLOCKS, UNIT_BLOCKS, REPORTS
from .insurance import CATALOG
from .reserves import COMPONENTS as RESERVE_COMPONENTS
from .transactions import RULES as TRANSACTION_RULES
from jason.community.symbols import DocumentKind, DocumentRule, KnownFile, PayhoaFolder


class Mystique(Community):
    """The association specification. Facts are attributes of this class, not a file."""

    def __init__(self) -> None:
        self._root = Path(__file__).resolve().parent
        self._files = {row.file: row for row in FILES}
        self._library = {row.folder: row for row in LIBRARY}

    @property
    def name(self) -> str:
        return "Mystique Community Association"

    @property
    def corporate_name(self) -> str:
        return "MYSTIQUE COMMUNITY ASSOCIATION"

    @property
    def slug(self) -> str:
        return "mystique"

    @property
    def org_id(self) -> int:
        return 27889

    @property
    def site(self) -> str:
        return "https://www.mystiquecommunity.com"

    def unit_city_state_zip(self) -> str:
        """Every unit's last address line (templates.UNIT_CITY_STATE_ZIP)."""
        from .templates import UNIT_CITY_STATE_ZIP

        return UNIT_CITY_STATE_ZIP

    @property
    def root(self) -> Path:
        return self._root

    @property
    def sync_rules(self) -> tuple[SyncRule, ...]:
        return RULES

    def document_sync_rules(self) -> dict[str, Any]:
        """Dict shape the document-sync tasks already consume."""
        return {
            "rules": [rule.as_dict(self.library_folder(rule.destination).path) for rule in RULES],
            "exclude": [row.as_dict() for row in EXCLUDED],
        }

    def buildings(self) -> tuple[BuildingRange, ...]:
        return CATALOG.buildings

    def insurance(self) -> InsuranceCatalog:
        return CATALOG

    @property
    def ccrs(self) -> GoverningDocument:
        return CCRS

    def pins(self) -> tuple[DocumentPin, ...]:
        return PINS

    def developers(self) -> tuple[Developer, ...]:
        return DEVELOPERS

    def public_reports(self):
        return REPORTS

    def plan_blocks(self):
        return PLAN_BLOCKS

    def unit_blocks(self):
        """Every building's unit numbering, the 2007 plan and Watt's, for reading a unit number."""
        return UNIT_BLOCKS

    def held_units(self):
        return HELD_UNITS

    def floor_plans(self):
        """The plans each developer offered, as the entitlement file and the brochure state them."""
        return FLOOR_PLANS

    def supersessions(self):
        """Governing instruments a later one rescinded, as that later instrument's body states."""
        return SUPERSESSIONS

    def solar_program(self):
        """The developer's shared solar: the buildings, the lease funds, and who services the leases."""
        return SOLAR_PROGRAM

    def vendor_portals(self):
        """Vendor customer portals (vendors.py)."""
        return VENDOR_PORTALS

    def copy_priority(self):
        """The channel order for choosing a document's copy (copies.py)."""
        from .copies import COPY_PRIORITY

        return COPY_PRIORITY

    def email_domains(self) -> tuple[str, ...]:
        """The association's own email domain (mail.py)."""
        from .mail import EMAIL_DOMAINS

        return EMAIL_DOMAINS

    def google_groups(self):
        """The association's Google Groups and what mail to each is for (groups.py)."""
        from .groups import GROUPS

        return GROUPS

    def packets(self):
        """The packets delivered as one PDF, with where each part is found (packets.py)."""
        from .packets import PACKETS

        return PACKETS

    def notice_rules(self):
        """The notices the association sends, with who receives each and how (notices.py)."""
        from .notices import NOTICE_RULES

        return NOTICE_RULES

    def notice_provisions(self):
        """The governing documents' notice clauses beside the statute (notices.py)."""
        from .notices import NOTICE_PROVISIONS

        return NOTICE_PROVISIONS

    def leasing_rules(self):
        """CC&Rs 4.15 as amended (leasing.py)."""
        from .leasing import LEASING

        return LEASING

    def help_articles(self):
        """PayHOA's help articles that letters and emails point owners to (help.py)."""
        from .help import HELP_ARTICLES

        return HELP_ARTICLES

    def payhoa_fields(self):
        """The PayHOA custom fields in use and proposed (tags.py)."""
        from .tags import PAYHOA_FIELDS

        return PAYHOA_FIELDS

    def payhoa_tags(self):
        """The PayHOA tags in use and proposed, with what each means (tags.py)."""
        from .tags import PAYHOA_TAGS

        return PAYHOA_TAGS

    def identity(self):
        """The association as its notices name it (templates.IDENTITY)."""
        from .templates import IDENTITY

        return IDENTITY

    def letterhead(self):
        """The Letterhead Doc, its footer, and its email frame (templates.LETTERHEAD)."""
        from .templates import LETTERHEAD

        return LETTERHEAD

    def coverages_not_carried(self):
        """The association carries no earthquake insurance (the insurance sheet and every notice since 2025)."""
        return ("earthquake",)

    def citations(self):
        """The bylaws, enforcement policy, and declaration sections the notices cite (templates.CITATIONS)."""
        from .templates import CITATIONS

        return CITATIONS

    def drive_home(self):
        """My Drive, Templates, Meetings, PayHOA Broadcasts, and Disciplinary (templates.DRIVE_HOME)."""
        from .templates import DRIVE_HOME

        return DRIVE_HOME

    def prompt_context(self):
        """Who the association is, for every task prompt: read from the specification (units, buildings, the board's
        group, the mailing address), plus how it is managed (prompts.py)."""
        from jason.community.groups import GroupPurpose

        from .prompts import MANAGEMENT
        from .templates import FOOTER

        board = next((g.address for g in self.google_groups() if g.purpose is GroupPurpose.BOARD), "")
        lines = [f"{self.name}: a condominium association of {len(self.units())} units in {len(self.buildings())} buildings.",
                 f"It is {MANAGEMENT}. Notices are signed \"Board of Directors, {self.name}\", never as a manager."]
        if board:
            lines.append(f"Members reach the board at {board}; its mailing address is {FOOTER}.")
        return tuple(lines)

    def task_prompts(self):
        """Each kind of task's prompt: law, questions, facts, and required elements (prompts.py)."""
        from .prompts import TASK_PROMPTS

        return TASK_PROMPTS

    def permit_portal(self):
        """The City's Citizen Access portal and the collection that holds the association's permits (permits.py)."""
        from .permits import ACCELA

        return ACCELA

    def closed_permit_statuses(self) -> tuple[str, ...]:
        """Permit statuses that need nothing more; other records are read in full on each sync (permits.py)."""
        from .permits import CLOSED_STATUSES

        return CLOSED_STATUSES

    def request_forms(self):
        """PayHOA's request forms with their question ids, and the topics each takes (requests.py)."""
        from .requests import REQUEST_FORMS

        return REQUEST_FORMS

    def request_topics(self):
        """The topics that are a request of the association when an owner raises them (requests.py)."""
        from .requests import REQUEST_TOPICS

        return REQUEST_TOPICS

    def intent_rules(self):
        """What a subject asks: complaint, maintenance, information, billing, question, enforcement (topics.py)."""
        from .topics import INTENT_RULES

        return INTENT_RULES

    def topic_sources(self):
        """Where each topic's answer is likely written: passages, library kinds, precedent violations (topics.py)."""
        from .topics import TOPIC_SOURCES

        return TOPIC_SOURCES

    def topic_rules(self):
        """The topics owners, vendors, and agencies write about, by subject words (topics.py)."""
        from .topics import TOPIC_RULES

        return TOPIC_RULES

    def obligations(self):
        """Recurring deadlines with their authority and the PayHOA evidence that shows them done (obligations.py)."""
        from .obligations import OBLIGATIONS

        return OBLIGATIONS

    def mail_addresses(self):
        """Where letters to the association are addressed, and which address is current (mail.py)."""
        from .mail import MAIL_ADDRESSES

        return MAIL_ADDRESSES

    def senders(self):
        """The association's counterparties: who writes to it and who it pays, by kind of source (senders.py)."""
        from .senders import SENDERS

        return SENDERS

    def premium_rules(self):
        """How an approval in the minutes is followed to the premiums it bought (insurance.py)."""
        from .insurance import PREMIUM_RULES

        return PREMIUM_RULES

    def evidence_plan(self):
        """The Drive folders and loose files that hold repair paperwork, and the names never read (incidents.py)."""
        from .incidents import EVIDENCE

        return EVIDENCE

    def bank_accounts(self):
        """The association's bank accounts; empty until a person confirms which is the reserve (see banking.py)."""
        return BANK_ACCOUNTS

    def utility_accounts(self):
        """Each SMUD and City account's purpose on the site, from the board's utility sheet."""
        return UTILITY_ACCOUNTS

    def utility_budget_lines(self):
        """The PayHOA budget line each utility service is budgeted under."""
        return UTILITY_BUDGET_LINES

    def legal_cases(self):
        """The construction defect claim, the pending lawsuit, and the other matters (mystique/cases.py)."""
        return LEGAL_CASES

    def meeting_schedule(self):
        """Third Tuesdays at 7:00 pm on Zoom (Administrative Resolution 20230130-1); monthly in practice."""
        return MEETING_SCHEDULE

    def rule_changes(self):
        """Proposed operating rule changes, drafts for the board and counsel (rule_changes.py)."""
        from .rule_changes import RULE_CHANGES

        return RULE_CHANGES

    def zoom_meeting_rules(self):
        """Hearing, executive session, annual meeting, committee, then board meeting, by the topic's words (zoom.py)."""
        from .zoom import ZOOM_MEETING_RULES

        return ZOOM_MEETING_RULES

    def executive_break_patterns(self):
        """The chair's adjournment to executive session, as the transcripts say it (zoom.py)."""
        from .zoom import EXECUTIVE_BREAK_PATTERNS

        return EXECUTIVE_BREAK_PATTERNS

    def zoom_history_since(self):
        """January 30, 2023: Administrative Resolution 20230130-1 put every meeting on Zoom (zoom.py)."""
        from .zoom import ZOOM_HISTORY_SINCE

        return ZOOM_HISTORY_SINCE

    def meeting_record_rules(self):
        """Agenda, minutes, transcript, chat, summary, and recording files by name (meetings.py)."""
        from .meetings import RECORD_RULES

        return RECORD_RULES

    def meeting_email_rules(self):
        """PayHOA's notice copies, Zoom's recording and summary emails, and replies about a meeting (meetings.py)."""
        from .meetings import EMAIL_RULES

        return EMAIL_RULES

    def privilege_parties(self):
        """Defense and association counsel, the carriers and adjusters, the broker, the plaintiff's counsel (privilege.py)."""
        from .privilege import PRIVILEGE_PARTIES

        return PRIVILEGE_PARTIES

    def privilege_name_rules(self):
        """Names marked privileged, defense requests, and the other side's papers (privilege.py)."""
        from .privilege import PRIVILEGE_NAME_RULES

        return PRIVILEGE_NAME_RULES

    def privilege_names(self):
        """What a communication is called, and the names of sensitive records (privilege.py)."""
        from .privilege import COMMUNICATION_NAMES, SENSITIVE_NAMES

        return COMMUNICATION_NAMES, SENSITIVE_NAMES

    def registers(self):
        """The board action items, and the registers to come (registers.py)."""
        from .registers import REGISTERS

        return REGISTERS

    def registers_folder(self):
        """New register Sheets go in the association's Drive folder "Registers" (registers.py)."""
        from .registers import REGISTERS_FOLDER

        return REGISTERS_FOLDER

    def legal_holds(self):
        """26CV016125, the dog attack: duty from the June 24, 2025 preservation letter (holds.py)."""
        from .holds import LEGAL_HOLDS

        return LEGAL_HOLDS

    def calendar_policy(self):
        """Board calendar titles; months outside the resolution are not called special (board_calendar.py)."""
        from .board_calendar import CALENDAR_POLICY

        return CALENDAR_POLICY

    def photo_album_rule(self):
        """"Mystique {date} {item}", with the likely incident's address and claims (photos.py)."""
        from .photos import ALBUM_NAME

        return ALBUM_NAME

    def photos_drive_folder(self):
        """Empty until the board picks a Drive folder for imported photos (photos.py)."""
        from .photos import PHOTOS_DRIVE_FOLDER

        return PHOTOS_DRIVE_FOLDER

    def app_properties(self):
        """The jason_* appProperties on Drive files, jason_hold reserved for a legal hold (labels.py)."""
        from .labels import APP_PROPERTIES

        return APP_PROPERTIES

    def agenda_item_rules(self):
        """What each agenda item brings: the treasurer's report its statements, a claim its letters and estimates (meetings.py)."""
        from .meetings import AGENDA_ITEM_RULES

        return AGENDA_ITEM_RULES

    def agenda_link_rules(self):
        """What an agenda's chips and links point at: Drive, Docs, Photos, Zoom, law, court (meetings.py)."""
        from .meetings import LINK_RULES

        return LINK_RULES

    def communication_search(self):
        """The words PayHOA's communications log is searched by for meeting notices (meetings.py)."""
        from .meetings import COMMUNICATION_SEARCH

        return COMMUNICATION_SEARCH

    def not_meeting_records(self):
        """The bylaws' audio book (meetings.py)."""
        from .meetings import NOT_MEETING_RECORDS

        return NOT_MEETING_RECORDS

    def citable_documents(self):
        """The governing documents, policies, and rules as Google Docs, with the names other documents cite them by."""
        from .outlines import CITABLE_DOCUMENTS

        return CITABLE_DOCUMENTS

    def resolutions_folder(self):
        """My Drive/Governing Documents/Resolutions (outlines.py)."""
        from .outlines import RESOLUTIONS_FOLDER

        return RESOLUTIONS_FOLDER

    def library_outlined_kinds(self):
        """The annexations, outlined from their text extracts, each supplementing the Declaration (outlines.py)."""
        from .outlines import LIBRARY_OUTLINED_KINDS

        return LIBRARY_OUTLINED_KINDS

    def document_templates(self):
        """Letter on letterhead, notice of hearing, notice of decision: Docs in My Drive/Templates (templates.py)."""
        from .templates import TEMPLATES

        return TEMPLATES

    def hearing_policy(self):
        """A hearing is its own Zoom meeting, 30 minutes, with a waiting room, not recorded (zoom.py)."""
        from .zoom import HEARING_POLICY

        return HEARING_POLICY

    def board(self):
        """Five seats (Bylaws 5.1, fixed by the board); a quorum is a majority of the directors in office, at least two (7.10)."""
        return BOARD

    def board_items_sheet(self):
        """The Google Sheet that holds the board's action items (banking.py)."""
        return BOARD_ITEMS_SHEET

    def lessons(self):
        """Mystique's own lessons (lessons.py), beside jason's general ones."""
        from .lessons import LESSONS

        return LESSONS

    def response_rules(self):
        """The documents' response clocks and the proposed policies (responses.py)."""
        from .responses import RESPONSE_RULES

        return RESPONSE_RULES

    def assignments(self):
        """Who does each duty and when (schedule.py): jason's proposals until the board adopts them."""
        from .schedule import ASSIGNMENTS

        return ASSIGNMENTS

    def fiscal_year_end(self):
        """The fiscal year is the calendar year."""
        return (12, 31)

    def living_documents(self):
        """Mystique's documents kept as amended (living.py)."""
        from .living import LIVING_DOCUMENTS

        return LIVING_DOCUMENTS

    def conflicts(self):
        """Mystique's provisions that yield to a higher authority (conflicts.py), each followed only that far."""
        from .conflicts import CONFLICTS

        return CONFLICTS

    def packet_reports(self):
        """Every board packet carries last month's Treasurer's Report, as PayHOA ran it (the treasurer runs the packet;
        jason includes the run, never builds one)."""
        return ("{REPORT:treasurers-report period=previous-month}",)

    def reserve_budget_lines(self):
        """The PayHOA budget lines for the reserve contribution and the repayment of borrowed reserve funds."""
        return RESERVE_BUDGET_LINES

    def utility_roll(self):
        """The city's and the sewer district's delinquent-utility charges on the tax bill, by claimant."""
        return UTILITY_ROLL

    def index_project(self) -> str:
        return PROJECT

    def index_association(self) -> str:
        return ASSOCIATION

    def units(self) -> tuple[str, ...]:
        return UNITS

    def common_areas(self) -> tuple[str, ...]:
        return COMMON_AREAS

    def cost_centers(self):
        """The Annexed Property and Phases 1 and 2 Property cost centers (each Watt annexation, section 1.3)."""
        return COST_CENTERS

    def association_common_areas(self):
        """A.C.A. 1 to 8: each building's association-owned parcel, its phase, and its units (the Condominium Plan)."""
        return ASSOCIATION_COMMON_AREAS

    def kind_rules(self):
        return KIND_RULES

    def document_rules(self) -> tuple[DocumentRule, ...]:
        return tuple(rule.id for rule in RULES)

    def transaction_rules(self) -> tuple[TransactionRule, ...]:
        return TRANSACTION_RULES

    def reserve_components(self):
        return RESERVE_COMPONENTS

    def insurance_workbook_id(self) -> str:
        return self.known_file(KnownFile.INSURANCE_WORKBOOK).drive_id

    def library_folders(self) -> tuple[LibraryFolder, ...]:
        return tuple(self._library.values())

    def known_files(self) -> tuple[KnownAnchor, ...]:
        return tuple(self._files.values())

    def known_file(self, file: KnownFile) -> KnownAnchor:
        try:
            return self._files[file]
        except KeyError:
            raise KeyError(file) from None

    def library_folder(self, folder: PayhoaFolder) -> LibraryFolder:
        try:
            return self._library[folder]
        except KeyError:
            raise KeyError(folder) from None

    def drive_roots(self) -> tuple[DriveRoot, ...]:
        return ROOTS

    def site_pages(self) -> tuple[SitePageRef, ...]:
        return PAGES
