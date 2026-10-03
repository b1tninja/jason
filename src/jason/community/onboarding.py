"""What a new association's profile needs: the onboarding checklist, as data.

Bringing an association into jason is the same work a management company does when it takes one over: gather the
association's records and information, then set up the systems that use them. This module is that request list,
written once for any California common interest development. Each ``OnboardingItem`` says what the item is, why it is
needed (the statute, or what jason uses it for), where it usually comes from, which ``Community`` method, record, or
book it fills, and how jason checks that it is present.

An item's ``origins`` say where it came from:

- ``Origin.LAW``: a statute requires the association to keep or give it (the text is in ``data/authorities``);
- ``Origin.PROFILE``: jason's own design needs it (a ``Community`` method, a book, a store);
- ``Origin.REQUEST``: an incoming manager's transition request list asked for it;
- ``Origin.FOLLOW_UP``: the incoming manager asked for it during the transition, after the list;
- ``Origin.HANDOFF``: the board's own knowledge-transfer document for a new manager carried it.

``check(ctx)`` runs every item's checks against a ``Context`` the caller loads (the profile, the classified library,
the Civil Code 5200 records inventory, file counts on disk, the private facts, the settings). An item is present when
every check passes, partial when some do, and missing when none does or when nothing in jason holds it yet. An item
with no ``fetch`` command is one a person must supply: jason has no source it can read for it.

An item a person supplies may carry a ``FactAsk``: the question jason asks while it is missing or partial, and where the
answer goes (``FactRecord``): the private facts (``data/spec/<profile>.json``), a proposed change to the profile for a
person to apply, or a note that the secret is kept in Keeper, never its value. ``Fact`` checks the private facts.

The stages (``Stage``, ``GATES``) group the items into the order a takeover opens: start, ingest, establish, operate,
adopt. A gate is open when its items are present and its own checks pass (``Settled``: no open question of some kinds;
``Verified``: the governing instruments' copies matched in the county index).

Pure records: nothing here reads disk; the task (``jason.tasks.onboarding``) loads the context.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Iterable

from jason.community.books import Book, entries_of
from jason.community.symbols import AssociationRecord, DocumentKind

K = DocumentKind
R = AssociationRecord


class Group(Enum):
    """The checklist's sections, in the order a takeover usually needs them."""

    GOVERNING = "governing"
    RECORDED = "recorded"
    CORPORATE = "corporate"
    BOARD = "board"
    MEMBERS = "members"
    FINANCE = "finance"
    INSURANCE = "insurance"
    VENDORS = "vendors"
    MAINTENANCE = "maintenance"
    MEETINGS = "meetings"
    ELECTIONS = "elections"
    ENFORCEMENT = "enforcement"
    ARCHITECTURAL = "architectural"
    RECORDS = "records"
    ACCESS = "access"

    @property
    def title(self) -> str:
        return GROUP_TITLES[self]


GROUP_TITLES: dict[Group, str] = {
    Group.GOVERNING: "Governing documents and amendments",
    Group.RECORDED: "Recorded instruments: maps, plans, deeds, and the developer's file",
    Group.CORPORATE: "Corporate and tax filings",
    Group.BOARD: "The board, officers, committees, and manager",
    Group.MEMBERS: "Members, units, and occupants",
    Group.FINANCE: "Finances: accounts, budget, reserves, ledgers, and collections",
    Group.INSURANCE: "Insurance",
    Group.VENDORS: "Contracts and vendors",
    Group.MAINTENANCE: "Maintenance, utilities, and life safety",
    Group.MEETINGS: "Meetings: minutes, agendas, and the schedule",
    Group.ELECTIONS: "Elections",
    Group.ENFORCEMENT: "Enforcement",
    Group.ARCHITECTURAL: "Architectural review",
    Group.RECORDS: "Records, retention, and pending matters",
    Group.ACCESS: "System access",
}


class Source(Enum):
    """Where an item usually comes from."""

    PRIOR_MANAGER = "prior manager"
    BOARD = "board"
    COUNTY_RECORDER = "county recorder"
    COUNTY_ASSESSOR = "county assessor and tax collector"
    SECRETARY_OF_STATE = "Secretary of State"
    DEVELOPER = "developer or the Department of Real Estate"
    CITY = "city or county building department"
    BANK = "bank"
    ACCOUNTANT = "accountant"
    RESERVE_SPECIALIST = "reserve specialist"
    INSURER = "insurance agent"
    UTILITY = "utility"
    VENDOR = "vendor"
    COUNSEL = "counsel"
    OWNERS = "owners"
    PLATFORM = "management software"


class Origin(Enum):
    """Where an item on the checklist came from (the module docstring says what each means)."""

    LAW = "law"
    PROFILE = "profile"
    REQUEST = "request"
    FOLLOW_UP = "follow-up"
    HANDOFF = "handoff"


class Status(Enum):
    PRESENT = "present"
    PARTIAL = "partial"
    MISSING = "missing"


@dataclass
class Context:
    """What the checks read. The task loads it; a test builds one by hand.

    ``count(path, table)`` is the number of rows, files, or entries at a store under the data folder (0 when there is
    none); ``private(name)`` is a private fact file's content (empty when there is none)."""

    community: Any
    library: tuple[dict[str, Any], ...] = ()
    holdings: tuple[Any, ...] = ()
    count: Callable[[str, str], int] = lambda path, table="": 0
    private: Callable[[str], Any] = lambda name: {}
    settings: Any = None
    profile: str = ""                        # the active profile's name: its private facts file (``Fact``)
    asks: tuple[Any, ...] = ()               # the intake questions (``Settled``)


@dataclass(frozen=True)
class Finding:
    passed: bool
    evidence: str


@dataclass(frozen=True)
class Method:
    """A ``Community`` method or property answers: a non-empty result (at least ``minimum`` rows; with ``contains``,
    rows whose name holds those words; with ``field``, that attribute of the result set)."""

    name: str
    minimum: int = 1
    contains: str = ""
    field: str = ""

    def run(self, ctx: Context) -> Finding:
        label = f"Community.{self.name}"
        try:
            value = getattr(ctx.community, self.name)
            if callable(value):
                value = value()
                label += "()"
        except Exception as exc:  # noqa: BLE001 - a profile that cannot answer is a miss, not a crash
            return Finding(False, f"{label} failed: {type(exc).__name__}")
        if self.field:
            value = getattr(value, self.field, None)
            label = f"{label}.{self.field}"
        count = _size(value, self.contains)
        if self.contains:
            label = f"{label} rows naming {self.contains!r}"
        if self.field and not isinstance(value, (tuple, list, dict)):
            return Finding(count >= self.minimum, f"{label}: {'set' if count else 'not set'}")
        return Finding(count >= self.minimum, f"{label}: {count}")


@dataclass(frozen=True)
class Kinds:
    """The classified library holds at least ``minimum`` files of these kinds."""

    kinds: tuple[DocumentKind, ...]
    minimum: int = 1

    def run(self, ctx: Context) -> Finding:
        values = {k.value for k in self.kinds}
        count = sum(1 for row in ctx.library if str(row.get("kind") or "") in values)
        names = "/".join(k.value for k in self.kinds)
        return Finding(count >= self.minimum, f"library: {count} {names} file{'' if count == 1 else 's'}")


@dataclass(frozen=True)
class Record:
    """The Civil Code 5200 records inventory pins a holder for this record and finds files in it."""

    kind: AssociationRecord

    def run(self, ctx: Context) -> Finding:
        holding = next((h for h in ctx.holdings if getattr(h, "kind", None) is self.kind), None)
        label = f"5200 record {self.kind.value}"
        if holding is None:
            return Finding(False, f"{label}: the records inventory was not read")
        if holding.pinned and holding.documents:
            return Finding(True, f"{label}: pinned, {holding.documents} files")
        return Finding(False, f"{label}: {holding.gap or 'no files'}")


@dataclass(frozen=True)
class InBook:
    """The profile maps a document into this book (``Community.book_entries()``)."""

    book: Book

    def run(self, ctx: Context) -> Finding:
        documents = sorted({e.document for e in entries_of(ctx.community) if e.book is self.book})
        if documents:
            more = f" and {len(documents) - 3} more" if len(documents) > 3 else ""
            return Finding(True, f"book {self.book.value}: {', '.join(documents[:3])}{more}")
        return Finding(False, f"book {self.book.value}: no document mapped")


@dataclass(frozen=True)
class Store:
    """A store under the data folder holds at least ``minimum`` rows, files, or entries (``table`` for a database)."""

    path: str
    table: str = ""
    minimum: int = 1

    def run(self, ctx: Context) -> Finding:
        count = ctx.count(self.path, self.table)
        where = f"data/{self.path}" + (f" {self.table}" if self.table else "")
        return Finding(count >= self.minimum, f"{where}: {count}")


@dataclass(frozen=True)
class Private:
    """A private fact file (``data/spec/<name>.json``) has entries. Only the count is reported, never a value."""

    name: str

    def run(self, ctx: Context) -> Finding:
        value = ctx.private(self.name)
        count = _size(value, "")
        return Finding(count > 0, f"private facts {self.name}: {count}")


@dataclass(frozen=True)
class Setting:
    """A setting is set (a Keeper record UID or a token file). Only whether it is set is reported."""

    name: str

    def run(self, ctx: Context) -> Finding:
        settings = ctx.settings
        value: Any = ""
        if settings is not None:
            value = getattr(settings, self.name, "") or ""
            if not value and self.name.endswith("_record_uid") and hasattr(settings, "record_uid"):
                value = settings.record_uid(self.name[: -len("_record_uid")])
        return Finding(bool(str(value).strip()), f"setting {self.name}: {'set' if value else 'not set'}")


FACTS = "facts"                              # the key in ``data/spec/<profile>.json`` that holds answered facts


@dataclass(frozen=True)
class Fact:
    """A person's answer for this item is in the profile's private facts (``data/spec/<profile>.json``, under
    ``facts``), or the record that it is kept in Keeper. Only whether it is recorded is reported, never a value."""

    key: str

    def run(self, ctx: Context) -> Finding:
        found = ctx.private(ctx.profile) if ctx.profile else {}
        entry = (found.get(FACTS) or {}).get(self.key) if isinstance(found, dict) else None
        if not entry:
            return Finding(False, f"private fact {self.key}: not answered")
        if isinstance(entry, dict) and entry.get("kept_in"):
            return Finding(True, f"private fact {self.key}: kept in {entry['kept_in']}")
        return Finding(True, f"private fact {self.key}: recorded")


@dataclass(frozen=True)
class Settled:
    """No open intake question of these kinds (values of ``AskKind``); with ``governing``, only questions about a
    document in a governing book (CIV 4150) count."""

    kinds: tuple[str, ...]
    governing: bool = False

    def counts(self, ask: Any, books: Any = None) -> bool:
        """Whether this open question holds the check closed."""
        if getattr(ask.status, "value", ask.status) != "open" or getattr(ask.kind, "value", ask.kind) not in self.kinds:
            return False
        if not self.governing:
            return True
        document = ask.subject.split("#", 1)[0].split("@", 1)[0]
        book = books.book(document) if books is not None else None
        return bool(book is not None and book.governing)

    def run(self, ctx: Context) -> Finding:
        from jason.community.books import Books

        books = Books.of(ctx.community) if self.governing else None
        found = sum(1 for a in ctx.asks if self.counts(a, books))
        where = " on the governing documents" if self.governing else ""
        return Finding(found == 0, f"intake: {found} open {'/'.join(self.kinds)} question{'' if found == 1 else 's'}{where}")


@dataclass(frozen=True)
class Verified:
    """Each governing instrument's copy (the declaration, its amendments and annexations) read with a recording stamp is
    matched in the county index, and none is read without a stamp. The records inventory's governing notes say which;
    an unrecorded copy is not counted against it (the recorded instrument is the record)."""

    def run(self, ctx: Context) -> Finding:
        holding = next((h for h in ctx.holdings if getattr(getattr(h, "kind", None), "value", "") == "governing_documents"), None)
        notes = list(getattr(holding, "notes", ()) or ())
        if holding is None or not notes:
            return Finding(False, "county: the governing instruments' copies were not read")
        recorded = [n for n in notes if ": recorded as " in n]
        matched = [n for n in recorded if "," in n.split(": recorded as ", 1)[1]]
        unstamped = [n for n in notes if "no stamp read" in n]
        passed = bool(recorded) and len(matched) == len(recorded) and not unstamped
        return Finding(passed, f"county: {len(matched)} of {len(recorded)} recorded copies matched in the index, "
                               f"{len(unstamped)} read without a stamp")


Check = Method | Kinds | Record | InBook | Store | Private | Setting | Fact | Settled | Verified


class FactRecord(Enum):
    """Where a person's answer to a fact goes."""

    PRIVATE = "private facts"                # data/spec/<profile>.json: people, account numbers, the tax ID
    PROFILE = "profile change"               # a proposed patch to the profile, for a person to review and apply
    KEEPER = "kept in Keeper"                # a record that the secret is in Keeper, under a named record; no value


@dataclass(frozen=True)
class FactAsk:
    """The question jason asks a person while the item is missing or partial.

    ``lead_kinds`` are library document kinds that may hold the answer (their files are the question's evidence);
    ``lead_pattern`` a regular expression whose most common match in those files' text is jason's suggestion.
    ``clock`` names the legal clock the answer sets, when it sets one. ``stakes`` marks an answer a second person
    confirms before it is applied."""

    question: str
    record: FactRecord = FactRecord.PRIVATE
    stakes: bool = False
    clock: str = ""
    choices: tuple[str, ...] = ()
    lead_kinds: tuple[DocumentKind, ...] = ()
    lead_pattern: str = ""
    method: str = ""                         # for a profile change: the ``Community`` method the answer fills


@dataclass(frozen=True)
class OnboardingItem:
    key: str
    group: Group
    title: str
    why: str                                 # the statute, or what jason uses it for
    sources: tuple[Source, ...]
    fills: str                               # the jason record, Community method, or book it fills
    checks: tuple[Check, ...] = ()
    origins: tuple[Origin, ...] = ()
    fetch: str = ""                          # the jason command that reads it once access is set up
    private: bool = False                    # it names people or accounts: private facts or notes, not the spec
    note: str = ""
    ask: FactAsk | None = None               # the question a person answers while it is missing or partial

    @property
    def by_person(self) -> bool:
        """No jason command can read it: a person supplies it."""
        return not self.fetch


@dataclass(frozen=True)
class ItemResult:
    item: OnboardingItem
    status: Status
    findings: tuple[Finding, ...] = ()

    @property
    def evidence(self) -> str:
        if not self.findings:
            return "nothing in jason holds this yet"
        return "; ".join(("ok " if f.passed else "no ") + f.evidence for f in self.findings)


L, P, Q, F, H = Origin.LAW, Origin.PROFILE, Origin.REQUEST, Origin.FOLLOW_UP, Origin.HANDOFF
S = Source
A = FactAsk
PROFILE_CHANGE, KEEPER = FactRecord.PROFILE, FactRecord.KEEPER
FACTS_FILE = "private facts (data/spec/<profile>.json)"

ITEMS: tuple[OnboardingItem, ...] = (
    # Governing documents and amendments
    OnboardingItem(
        "declaration", Group.GOVERNING, "The declaration (CC&Rs), the recorded copy",
        "CIV 4135, 4150; every buyer gets it (4525(a)(1)); jason's decl book, outlines, and living text read it",
        (S.COUNTY_RECORDER, S.PRIOR_MANAGER), "book decl; Community.ccrs(), book_entries(), governing_set()",
        (InBook(Book.DECL), Kinds((K.DECLARATION,))), (L, P, Q, H), "jason sync-catalog; jason outlines --fetch"),
    OnboardingItem(
        "amendments", Group.GOVERNING, "Every amendment to the declaration, with its recording number, and any in progress",
        "an amendment takes effect when recorded (CIV 4270(a)(3)); jason keeps the declaration as amended",
        (S.COUNTY_RECORDER, S.BOARD, S.COUNSEL), "book decl versions; Community.revision_series(), supersessions()",
        (Kinds((K.AMENDMENT,)), Method("revision_series")), (L, P, Q, H), "jason records-request; jason revisions",
        note="An amendment approved but not yet recorded is not in force; list it as pending."),
    OnboardingItem(
        "annexations", Group.GOVERNING, "Annexations (supplementary declarations), one per phase, and any phase never annexed",
        "a supplementary declaration is part of the declaration (CIV 4135); jason's phases, pins, and buildings",
        (S.COUNTY_RECORDER, S.DEVELOPER), "book decl parts; Community.pins(), buildings()",
        (Kinds((K.ANNEXATION,)), Method("pins")), (P, Q, H), "jason records-request"),
    OnboardingItem(
        "articles", Group.GOVERNING, "Articles of incorporation",
        "a governing document (CIV 4150); filed with the Secretary of State", (S.SECRETARY_OF_STATE, S.PRIOR_MANAGER),
        "book arts", (InBook(Book.ARTS), Kinds((K.ARTICLES,))), (L, P, Q, H), "jason sync-catalog"),
    OnboardingItem(
        "bylaws", Group.GOVERNING, "Bylaws and their amendments",
        "a governing document (CIV 4150); seats, terms, officers, quorum", (S.PRIOR_MANAGER, S.BOARD),
        "book bylaws; Community.board()", (InBook(Book.BYLAWS), Kinds((K.BYLAWS,))), (L, P, Q, H), "jason sync-catalog"),
    OnboardingItem(
        "operating-rules", Group.GOVERNING, "Operating rules, each separately adopted rule document, and the notices of each change",
        "CIV 4340, 4355, 4360; the rules and policies an incoming manager enforces",
        (S.PRIOR_MANAGER, S.BOARD), "book rules; Community.rule_changes(), rule_change_records()",
        (InBook(Book.RULES), Kinds((K.OPERATING_RULES,)), Method("rule_change_records")), (L, P, Q, H),
        "jason sync-catalog; jason rule-change"),
    OnboardingItem(
        "election-rules", Group.GOVERNING, "Election rules",
        "the association must adopt them (CIV 5105(a))", (S.PRIOR_MANAGER, S.BOARD), "book elec",
        (InBook(Book.ELEC), Kinds((K.ELECTION_RULES,))), (L, P, Q, H), "jason sync-catalog"),
    OnboardingItem(
        "policies-resolutions", Group.GOVERNING, "Board policies and resolutions in force (collection, enforcement, records, reserves, ethics)",
        "the annual policy statement draws on them (CIV 5310(a)); resolutions are records (5200(a)(8))",
        (S.PRIOR_MANAGER, S.BOARD), "book res; the policies library folder",
        (InBook(Book.RES), Kinds((K.POLICY, K.RESOLUTION))), (L, P, Q, H), "jason sync-catalog"),
    OnboardingItem(
        "governing-set", Group.GOVERNING, "The documents' own definition of the governing documents, and their defined terms",
        "jason reports where the documents' list differs from CIV 4150 and reads each defined term",
        (S.BOARD,), "Community.governing_set(), defined_terms()",
        (Method("governing_set"), Method("defined_terms")), (P,), "jason outlines"),
    OnboardingItem(
        "conflicts", Group.GOVERNING, "Provisions a later statute displaces, read with counsel where unclear",
        "a provision yields only to the extent of a conflict (CIV 4205); jason lists them for the board",
        (S.COUNSEL, S.BOARD), "Community.conflicts()", (Method("conflicts"),), (L, P), "jason conflicts --leads"),
    OnboardingItem(
        "owners-manual", Group.GOVERNING, "The owner's manual or handbook that reprints the rules for owners",
        "a guide, not a governing document; jason keeps it in step with the rules", (S.BOARD, S.PRIOR_MANAGER),
        "book manual; Community.owners_manual()", (Method("owners_manual"), InBook(Book.MANUAL)), (P, H), "jason manual"),
    # Recorded instruments
    OnboardingItem(
        "maps", Group.RECORDED, "Subdivision and parcel maps",
        "the description of the development (CIV 4285); jason's plan book", (S.COUNTY_RECORDER, S.CITY),
        "book plan", (Kinds((K.MAP,)),), (L, P, H), "jason records-request"),
    OnboardingItem(
        "condominium-plans", Group.RECORDED, "Condominium plans and their amendments, by phase",
        "the plan defines each unit's boundaries (CIV 4120, 4285)", (S.COUNTY_RECORDER, S.DEVELOPER),
        "book plan; Community.plan_blocks(), unit_blocks(), floor_plans()",
        (Kinds((K.CONDOMINIUM_PLAN,)), Method("plan_blocks"), Method("unit_blocks")), (L, P, H), "jason records-request"),
    OnboardingItem(
        "common-area-deeds", Group.RECORDED, "Deeds conveying the common area to the association",
        "proves what the association owns and is taxed on", (S.COUNTY_RECORDER, S.DEVELOPER),
        "Community.deed_numbers(), association_common_areas(), common_areas()",
        (Method("deed_numbers"), Method("association_common_areas"), Kinds((K.GRANT_DEED,))), (P,),
        "jason records-request; jason county-report"),
    OnboardingItem(
        "public-reports", Group.RECORDED, "The developer's public reports, budgets, and completion bonds by phase",
        "the developer's promises and securities (Business and Professions Code 11018); jason's developer file",
        (S.DEVELOPER,), "Community.public_reports(), developers(), developer_file()",
        (Method("public_reports"), Method("developers"), Kinds((K.DRE_REPORT,))), (P,), "jason securities"),
    OnboardingItem(
        "developer-file", Group.RECORDED, "What the developer delivered at turnover: maintenance manual, warranties, as-built plans",
        "jason's developer file: an empty delivery group is a missing document", (S.DEVELOPER, S.PRIOR_MANAGER),
        "Community.developer_file()", (Method("developer_file"),), (P, H)),
    OnboardingItem(
        "building-plans", Group.RECORDED, "Building plan sets and the permits they were built under",
        "repairs, claims, and inspections need them", (S.CITY, S.DEVELOPER), "Community.floor_plans()",
        (Kinds((K.PLAN_SET,)), Method("floor_plans")), (P, H), "jason permits"),
    OnboardingItem(
        "parcels", Group.RECORDED, "Every parcel number, units and common areas",
        "jason's tax, assessor, and title stores are keyed by parcel", (S.COUNTY_ASSESSOR, S.COUNTY_RECORDER),
        "Community.parcels(), units(), common_areas()",
        (Method("parcels"), Store("ownership.db", "ownership")), (P,), "jason sync-secured; jason sync-tax"),
    OnboardingItem(
        "recorded-liens", Group.RECORDED, "Recorded assessment liens, releases, and notices against units",
        "the association's liens (CIV 5675-5720) and what stands against title", (S.COUNTY_RECORDER, S.PRIOR_MANAGER),
        "the index cache; jason title-watch", (Kinds((K.RECORDED_LIEN,)),), (L, P, Q), "jason sync-liens; jason title-watch"),
    # Corporate and tax filings
    OnboardingItem(
        "tax-id", Group.CORPORATE, "Federal employer identification number and the state entity number",
        "tax returns, bank accounts, and 1099s use them", (S.PRIOR_MANAGER, S.SECRETARY_OF_STATE), FACTS_FILE,
        (Fact("tax-id"),), (Q, H),
        note="The answer is a private fact; add a Community field, with an empty default, when a task needs it.",
        ask=A("What are the association's federal employer identification number (EIN) and its state entity number?",
              lead_kinds=(K.TAX_RETURN, K.FINANCIAL_REVIEW), lead_pattern=r"\b\d{2}-\d{7}\b")),
    OnboardingItem(
        "statement-of-information", Group.CORPORATE, "The statement of information and the common interest development statement (SI-CID), current",
        "every two years (Corporations Code 8210; CIV 5405)", (S.SECRETARY_OF_STATE,), "Community.obligations()",
        (Method("obligations", contains="statement of information"),), (L, P),
        ask=A("When was the statement of information (with the SI-CID) last filed, and when is the next one due?",
              PROFILE_CHANGE, clock="the statement of information every two years (CIV 5405)", method="obligations")),
    OnboardingItem(
        "official-address", Group.CORPORATE, "The designated recipient and address for official notices, the posting location, and the overnight payment address",
        "CIV 4035, 4045, 5655; each goes in the annual policy statement (5310(a))", (S.BOARD, S.PRIOR_MANAGER),
        "Community.identity(), mail_addresses()",
        (Method("identity", field="designated_recipient"), Method("identity", field="posting_location"),
         Method("mail_addresses")), (L, P),
        ask=A("Who is the designated recipient of official notices, and at what address? Where are general notices "
              "posted, and what is the overnight payment address?", PROFILE_CHANGE, method="identity")),
    OnboardingItem(
        "tax-returns", Group.CORPORATE, "Federal and state tax returns for prior years",
        "an association record (CIV 5200(a)(6)); the next return's preparer needs them", (S.ACCOUNTANT, S.PRIOR_MANAGER),
        "book tax", (Record(R.TAX_RETURN), Kinds((K.TAX_RETURN,))), (L, Q, H), "jason sync-catalog"),
    OnboardingItem(
        "property-tax", Group.CORPORATE, "Property tax on the common-area parcels: bills, installments, and who pays",
        "jason's deadlines and tax store", (S.COUNTY_ASSESSOR,), "Community.obligations()",
        (Method("obligations", contains="property tax"), Store("tax.db")), (P,), "jason sync-tax; jason deadlines"),
    OnboardingItem(
        "1099s-w9s", Group.CORPORATE, "1099 reports and vendors' W-9s",
        "the year's information returns", (S.PRIOR_MANAGER, S.VENDOR), FACTS_FILE, (Fact("1099s-w9s"),), (Q, H),
        note="jason keeps no W-9 record; the accounting system holds them.",
        ask=A("Who keeps the 1099 reports and the vendors' W-9s, and where?")),
    # The board, officers, committees, and manager
    OnboardingItem(
        "board-rule", Group.BOARD, "The number of seats, their terms, and the quorum, from the bylaws",
        "quorum counts in minutes and the election cycle", (S.BOARD,), "Community.board()", (Method("board"),), (P,),
        ask=A("How many seats does the board have, how long is a term, and what is the quorum?", PROFILE_CHANGE,
              lead_kinds=(K.BYLAWS,), method="board")),
    OnboardingItem(
        "board-roster", Group.BOARD, "Directors and officers, with their offices, term dates, and contact",
        "who may act, sign, and be noticed; the incoming manager's first request", (S.BOARD, S.PRIOR_MANAGER),
        "PayHOA's Board Member tag; data/payhoa/board-members.json", (Store("payhoa/board-members.json"),), (P, Q, H),
        "jason board", private=True),
    OnboardingItem(
        "signers", Group.BOARD, "Bank signers, their order, and the board's approval limits for transfers",
        "transfers over the limit need the board's written approval (CIV 5380(b)(6), 5502)", (S.BOARD, S.BANK),
        FACTS_FILE, (Fact("signers"),), (L, F), private=True,
        note="Asked during the transition (the new signature card), not on the request list.",
        ask=A("Who are the bank signers, in what order, and above what amount does a transfer need the board's "
              "written approval?", stakes=True, lead_kinds=(K.RESOLUTION, K.MINUTES))),
    OnboardingItem(
        "committees", Group.BOARD, "Committees, their members, and their contact information",
        "committee agendas and minutes are records (CIV 5200(a)(8)); who reviews architecture and events", (S.BOARD,),
        "Community.assignments()", (Method("assignments", contains="committee"),), (L, P, Q, H), private=True),
    OnboardingItem(
        "assignments", Group.BOARD, "Who does each duty and when",
        "jason's schedule: what falls due and the duties nobody owns", (S.BOARD,), "Community.assignments()",
        (Method("assignments"),), (P,), "jason schedule"),
    OnboardingItem(
        "manager", Group.BOARD, "The management agreement, the manager's written disclosures, and how it holds the association's funds",
        "CIV 5375, 5375.5, 5380, 5806 (the manager's fidelity coverage)", (S.PRIOR_MANAGER, S.BOARD),
        "Community.assignments()", (Method("assignments", contains="manager"),), (L, P)),
    OnboardingItem(
        "people-tasks", Group.BOARD, "Who answers which kind of request or message",
        "jason routes requests and mail by these rules", (S.BOARD,), "Community.people_task_rules()",
        (Method("people_task_rules"),), (P,)),
    # Members, units, and occupants
    OnboardingItem(
        "units", Group.MEMBERS, "Every unit: address, building, phase, and plan",
        "the frame for owners, assessments, insurance by building, and parcels", (S.PRIOR_MANAGER, S.COUNTY_ASSESSOR),
        "Community.units(), buildings(); the PayHOA units",
        (Method("units"), Method("buildings"), Store("payhoa.db", "units")), (P, Q), "jason sync-catalog"),
    OnboardingItem(
        "owner-roster", Group.MEMBERS, "Owners and tenants, with mailing addresses, email, and phone",
        "the membership list (CIV 5200(a)(9)); notices go where members ask (4040, 4041)", (S.PRIOR_MANAGER, S.OWNERS),
        "the PayHOA people; the 5200 membership list", (Store("payhoa.db", "people"), Record(R.MEMBERSHIP_LIST)),
        (L, P, Q, H), "jason sync-catalog", private=True),
    OnboardingItem(
        "account-numbers", Group.MEMBERS, "Each owner's account number at the prior manager",
        "for the inquiries that follow a move", (S.PRIOR_MANAGER,), FACTS_FILE, (Fact("account-numbers"),), (Q,),
        private=True,
        ask=A("Where is the list of each owner's account number at the prior manager kept, or is there none?",
              choices=("none: the prior manager kept no account numbers",))),
    OnboardingItem(
        "owner-information", Group.MEMBERS, "Each owner's annual delivery preferences, legal representative, and occupancy",
        "CIV 4041, entered 30 days before the annual reports", (S.OWNERS,), "PayHOA tags; Community.payhoa_tags()",
        (Method("payhoa_tags"), Store("owner-info")), (L, P), "jason owner-info", private=True),
    OnboardingItem(
        "ownership-chain", Group.MEMBERS, "Each unit's deed history from the county",
        "who owned when; new owners and transfers", (S.COUNTY_RECORDER, S.COUNTY_ASSESSOR), "data/ownership.db",
        (Store("ownership.db", "chain"),), (P,), "jason county-report", private=True),
    OnboardingItem(
        "leasing", Group.MEMBERS, "Leasing rules, the rental cap, and the units now rented",
        "CIV 4740, 4741; 4525(a)(9)", (S.BOARD, S.OWNERS), "Community.leasing_rules()",
        (Method("leasing_rules"), Kinds((K.LEASE,))), (L, P), "jason rentals", private=True),
    OnboardingItem(
        "resale-package", Group.MEMBERS, "The escrow package given on a sale, and its fees",
        "CIV 4525, 4528, 4530", (S.PRIOR_MANAGER,), "Community.packets()",
        (Method("packets"), Kinds((K.RESALE_DISCLOSURE, K.ESCROW_REQUEST))), (L, P, Q), "jason new-owners"),
    OnboardingItem(
        "other-charges", Group.MEMBERS, "Other items billed to owners: special assessments, utilities, permits, rentals of common area",
        "a buyer's statement lists every charge (CIV 4525(a)(4), (8))", (S.PRIOR_MANAGER, S.BOARD), FACTS_FILE,
        (Fact("other-charges"),), (L, Q, H),
        ask=A("What is billed to owners besides the regular assessment (special assessments, utilities, permits, "
              "rentals of common area), and how much?", choices=("none: only the regular assessment",),
              lead_kinds=(K.BUDGET, K.RESALE_DISCLOSURE))),
    # Finances
    OnboardingItem(
        "bank-accounts", Group.FINANCE, "Operating and reserve accounts: bank, type, last digits, and a contact at the bank",
        "the board reviews each account's statements monthly (CIV 5500(d))", (S.BANK, S.PRIOR_MANAGER),
        "Community.bank_accounts(); account numbers in private facts",
        (Method("bank_accounts"), Private("bank_accounts")), (L, P, Q, H), "jason accounts", private=True),
    OnboardingItem(
        "bank-statements", Group.FINANCE, "Bank statements and reconciliations",
        "CIV 5500(a), (b), (d)", (S.BANK, S.PLATFORM), "the reconciliations store",
        (Kinds((K.BANK_STATEMENT,)), Store("payhoa/reconciliations.json")), (L, P), "jason reconcile"),
    OnboardingItem(
        "prefund", Group.FINANCE, "Start-up funds for the new operating account, and how money moves from the old accounts",
        "the new manager pays bills before the first assessments clear", (S.PRIOR_MANAGER, S.BOARD, S.BANK),
        FACTS_FILE, (Fact("prefund"),), (Q, F),
        note="The outgoing manager may wire rather than write a check; send account details apart from their label.",
        ask=A("How much start-up money goes into the new operating account, and how does money move from the old "
              "accounts (a wire or a check)?")),
    OnboardingItem(
        "assessments", Group.FINANCE, "Current regular assessments by year, the billing frequency, and the billing method",
        "CIV 4525(a)(4), 5300(b)(1), 5600-5625", (S.PRIOR_MANAGER, S.BOARD), "the PayHOA budgets",
        (Store("payhoa/budgets"), Kinds((K.BUDGET,))), (L, Q, H), "jason budget"),
    OnboardingItem(
        "budget-reports", Group.FINANCE, "Annual budget reports and policy statements, current and prior years",
        "CIV 5300, 5310; every buyer gets the latest (4525(a)(3))", (S.PRIOR_MANAGER,), "book budget, book aps",
        (Record(R.FINANCIAL_DISCLOSURE), Kinds((K.BUDGET, K.ANNUAL_DISCLOSURE))), (L, P, Q, H), "jason sync-catalog"),
    OnboardingItem(
        "financial-statements", Group.FINANCE, "The latest monthly financial statements, the prior year-end, and the final ones at the handover",
        "CIV 5200(a)(3), 5500(c), (e)", (S.PRIOR_MANAGER,), "book fin",
        (Record(R.INTERIM_FINANCIAL), Kinds((K.FINANCIAL_STATEMENT, K.TREASURER_REPORT))), (L, P, Q, H),
        "jason sync-catalog; jason ledger"),
    OnboardingItem(
        "general-ledger", Group.FINANCE, "The general ledger for the current and prior years, the check register, and the vendor ledger",
        "CIV 5200(a)(10), 5500(f)", (S.PRIOR_MANAGER, S.PLATFORM), "data/payhoa/ledger.db",
        (Store("payhoa/ledger.db", "entries"), Record(R.CHECK_REGISTER)), (L, P, Q), "jason books"),
    OnboardingItem(
        "owner-ledgers", Group.FINANCE, "Owner ledgers with ending balances, and the receivable and prepaid reports",
        "the board reviews delinquencies monthly (CIV 5500(f)); each balance carried over needs its detail",
        (S.PRIOR_MANAGER,), "PayHOA charges and payments", (Kinds((K.OWNER_STATEMENT, K.OWNER_HISTORY)),),
        (L, Q), "jason who-owes", private=True,
        note="Ask again after each month's late fees post until the handover."),
    OnboardingItem(
        "financial-review", Group.FINANCE, "The accountant's review of the prior year's financial statements",
        "CIV 5305", (S.ACCOUNTANT, S.PRIOR_MANAGER), "Community.obligations()",
        (Kinds((K.FINANCIAL_REVIEW,)), Method("obligations", contains="financial")), (L, Q, H), "jason sync-catalog"),
    OnboardingItem(
        "reserve-study", Group.FINANCE, "The reserve study and its updates, with the component list",
        "CIV 5550, 5560, 5565; the budget report summarizes it", (S.RESERVE_SPECIALIST, S.PRIOR_MANAGER),
        "book rsv; Community.reserve_components()",
        (Kinds((K.RESERVE_STUDY,)), Method("reserve_components"), Store("reserve-studies")), (L, P), "jason reserves",
        note="Not on a typical takeover request list; ask for it."),
    OnboardingItem(
        "reserve-accounts", Group.FINANCE, "Reserve balances, certificates of deposit and their maturities, and any transfers or borrowing",
        "CIV 5200(a)(7), 5510, 5515, 5565", (S.BANK, S.PRIOR_MANAGER), "Community.reserve_budget_lines()",
        (Record(R.RESERVE_ACCOUNT), Method("reserve_budget_lines")), (L, P, H), "jason reserves"),
    OnboardingItem(
        "cost-centers", Group.FINANCE, "How expenses are shared: cost centers by building or phase, as the declaration requires",
        "assessments follow the declaration's allocation", (S.BOARD,), "Community.cost_centers(), association_common_areas()",
        (Method("cost_centers"), Method("association_common_areas")), (P, H), "jason cost-centers"),
    OnboardingItem(
        "fiscal-year", Group.FINANCE, "The fiscal year's end", "sets the annual reports' window (CIV 5300(a), 5310(a))",
        (S.BOARD, S.PRIOR_MANAGER), "Community.fiscal_year_end()", (Method("fiscal_year_end"),), (L, P),
        ask=A("On what day does the fiscal year end?", PROFILE_CHANGE,
              clock="the annual budget report and policy statement windows (CIV 5300(a), 5310(a))",
              lead_kinds=(K.BUDGET, K.FINANCIAL_REVIEW), method="fiscal_year_end")),
    OnboardingItem(
        "transaction-rules", Group.FINANCE, "How bank transactions are categorized, and the budget lines for utilities and reserves",
        "jason matches bills and expenses to budget lines", (S.PLATFORM, S.BOARD),
        "Community.transaction_rules(), utility_budget_lines()",
        (Method("transaction_rules"), Method("utility_budget_lines")), (P,)),
    OnboardingItem(
        "collection-policy", Group.FINANCE, "The assessment collection and delinquency policy",
        "CIV 5310(a)(6), (7), 5730", (S.PRIOR_MANAGER, S.BOARD), "book coll",
        (InBook(Book.COLL), Method("assignments", contains="collection")), (L, P, Q, H), "jason sync-catalog"),
    OnboardingItem(
        "delinquencies", Group.FINANCE, "Owners in collections or foreclosure, the collection agent, and each account's status",
        "CIV 5650-5740; a lien amount must be current before foreclosure", (S.PRIOR_MANAGER, S.COUNSEL),
        "PayHOA charges; recorded liens", (Kinds((K.DELINQUENCY_NOTICE, K.RECORDED_LIEN)),), (L, Q, H),
        "jason who-owes", private=True),
    OnboardingItem(
        "loans", Group.FINANCE, "Loans with a term over one year: payee, rate, balance, payment, and payoff",
        "the budget report states them (CIV 5300(b)(8))", (S.PRIOR_MANAGER, S.BANK), FACTS_FILE, (Fact("loans"),),
        (L,),
        ask=A("Does the association have a loan with a term over one year? If so: the payee, rate, balance, payment, "
              "and payoff.", choices=("none: no loan over one year",),
              lead_kinds=(K.BUDGET, K.FINANCIAL_STATEMENT, K.FINANCIAL_REVIEW))),
    # Insurance
    OnboardingItem(
        "policies", Group.INSURANCE, "Each policy: carrier, agent, number, term, limits, and deductible (property, liability, directors and officers, fidelity, flood, earthquake, umbrella, workers' compensation)",
        "CIV 5300(b)(9), 5800-5806", (S.INSURER, S.PRIOR_MANAGER), "Community.insurance()",
        (Method("insurance", field="policies"), Kinds((K.INSURANCE_POLICY,))), (L, P, Q, H), "jason policies"),
    OnboardingItem(
        "certificates", Group.INSURANCE, "Certificates and evidence of insurance, for lenders and owners",
        "a lender's or buyer's request", (S.INSURER,), "the insurance library folder",
        (Kinds((K.EVIDENCE_OF_INSURANCE,)),), (Q, H), "jason sync-catalog"),
    OnboardingItem(
        "renewals", Group.INSURANCE, "Renewal dates and premium payments by term",
        "jason watches renewals and premiums", (S.INSURER, S.PLATFORM), "Community.premium_rules(); the insurance sheet",
        (Method("premium_rules"), Store("insurance/sheet.json")), (P, H), "jason insurance"),
    OnboardingItem(
        "claims", Group.INSURANCE, "Claims open or closed in the last five years, and the loss runs",
        "renewals and the incident history", (S.INSURER, S.PRIOR_MANAGER), "the incident history",
        (Kinds((K.LOSS_RUN, K.CLAIM_LETTER, K.CLAIM_PAYMENT)),), (P,), "jason incidents"),
    OnboardingItem(
        "not-carried", Group.INSURANCE, "Coverages the association does not carry, and the notice owners get",
        "CIV 5300(b)(9), 5810", (S.INSURER, S.BOARD), "Community.coverages_not_carried()",
        (Method("coverages_not_carried"),), (L, P),
        ask=A("Which coverages does the association not carry (earthquake, flood), for the notice owners get?",
              PROFILE_CHANGE, lead_kinds=(K.INSURANCE_POLICY, K.ANNUAL_DISCLOSURE), method="coverages_not_carried")),
    # Contracts and vendors
    OnboardingItem(
        "contracts", Group.VENDORS, "Executed contracts in force, with their terms and renewals",
        "an association record (CIV 5200(a)(4))", (S.PRIOR_MANAGER, S.VENDOR), "book contract",
        (Record(R.EXECUTED_CONTRACT), Kinds((K.CONTRACT,))), (L, P, Q), "jason sync-catalog"),
    OnboardingItem(
        "vendor-directory", Group.VENDORS, "Every vendor, its account number, and its contact",
        "who to tell about the new manager; who writes from each vendor", (S.PRIOR_MANAGER,),
        "PayHOA's vendor directory; Community.senders()",
        (Store("payhoa/vendor-info.json"), Method("senders")), (P, Q, H), "jason contacts"),
    OnboardingItem(
        "vendor-licenses", Group.VENDORS, "Vendors' licenses, insurance certificates, and W-9s",
        "a licensed contractor; insurance before work starts", (S.VENDOR,),
        f"VendorLicense rows on vendor portals; {FACTS_FILE}", (Fact("vendor-licenses"),), (P, H),
        note="jason records a license only for a portal vendor; the rest are kept outside jason.",
        ask=A("Where are the vendors' licenses, insurance certificates, and W-9s kept, and who checks them before "
              "work starts?", lead_kinds=(K.EVIDENCE_OF_INSURANCE, K.CONTRACT))),
    OnboardingItem(
        "vendor-portals", Group.VENDORS, "Vendor customer portals the association signs in to",
        "jason reads visits, invoices, and files from them", (S.VENDOR,), "Community.vendor_portals()",
        (Method("vendor_portals"),), (P,), "jason vendors"),
    OnboardingItem(
        "vendor-approvals", Group.VENDORS, "The board's written approvals of vendors and contractors",
        "an association record (CIV 5200(a)(5))", (S.BOARD, S.PRIOR_MANAGER), "5200 vendor approvals",
        (Record(R.VENDOR_APPROVAL),), (L,)),
    # Maintenance, utilities, and life safety
    OnboardingItem(
        "utility-accounts", Group.MAINTENANCE, "Every utility account and meter, with a recent bill for each",
        "who serves what; jason matches each bill to its account", (S.UTILITY, S.PRIOR_MANAGER),
        "Community.utility_accounts(); account numbers in private facts",
        (Method("utility_accounts"), Private("utility_accounts"), Kinds((K.UTILITY_BILL,))), (P, Q, H),
        "jason utilities; jason sync-bills", private=True),
    OnboardingItem(
        "utility-allocation", Group.MAINTENANCE, "How utilities are charged: submeters or shared in the budget, as the declaration says",
        "the declaration may require individual billing", (S.BOARD,), "Community.utility_roll(), utility_budget_lines()",
        (Method("utility_roll"), Method("utility_budget_lines")), (P, F),
        ask=A("How are utilities charged: submeters billed to owners, or shared in the budget? What does the "
              "declaration require?", PROFILE_CHANGE, lead_kinds=(K.UTILITY_BILL, K.BUDGET), method="utility_roll")),
    OnboardingItem(
        "life-safety", Group.MAINTENANCE, "Fire alarm, sprinkler, and backflow inspections: schedule and last reports",
        "the fire code and the water purveyor's annual test", (S.VENDOR, S.CITY), "Community.obligations()",
        (Method("obligations", contains="fire"), Kinds((K.INSPECTION_REPORT,))), (P,), "jason deadlines"),
    OnboardingItem(
        "elevated-elements", Group.MAINTENANCE, "The inspection report on balconies and other exterior elevated elements",
        "CIV 5551; every buyer gets it (4525(a)(11))", (S.VENDOR, S.PRIOR_MANAGER), "book insp",
        (Record(R.ELEVATED_ELEMENT_REPORT), Kinds((K.ELEVATED_ELEMENT_INSPECTION,))), (L, P), "jason sync-catalog"),
    OnboardingItem(
        "maintenance-manual", Group.MAINTENANCE, "The maintenance manual, the responsibility split, equipment manuals, paint and fixture schedules",
        "who maintains what, and the parts to match", (S.DEVELOPER, S.PRIOR_MANAGER, S.BOARD),
        "Community.assignments()", (Method("assignments", contains="maintenance"),), (P, H)),
    OnboardingItem(
        "maintenance-programs", Group.MAINTENANCE, "Standing inspection programs and their worksheets",
        "a program applied the same way every time", (S.BOARD,), FACTS_FILE, (Fact("maintenance-programs"),), (H,),
        ask=A("Which standing inspection programs are there (what, how often, and who), and where are their "
              "worksheets?", choices=("none yet",), lead_kinds=(K.INSPECTION_REPORT,))),
    OnboardingItem(
        "permits", Group.MAINTENANCE, "Building permits, open and closed", "repairs and claims", (S.CITY,),
        "Community.permit_portal()", (Method("permit_portal"),), (P,), "jason permit-status"),
    OnboardingItem(
        "shared-systems", Group.MAINTENANCE, "Systems under their own agreements: shared solar, cameras, telecom",
        "jason tracks a shared program's terms and payments", (S.VENDOR, S.BOARD), "Community.solar_program()",
        (Method("solar_program"),), (P, H)),
    OnboardingItem(
        "keys-and-codes", Group.MAINTENANCE, "Keys, lock boxes, panel and controller codes, and stored materials and where they are",
        "access for repairs and emergencies", (S.PRIOR_MANAGER, S.BOARD),
        "the password vault, not a document; the private facts record only the Keeper record's name",
        (Fact("keys-and-codes"),), (Q, H), private=True,
        note="Codes and passwords go in the vault (Keeper), never in a document or an email.",
        ask=A("Which Keeper record holds the keys, lock boxes, and panel and controller codes, and where are the "
              "stored materials? Answer with the record's name, never a code.", KEEPER)),
    # Meetings
    OnboardingItem(
        "minutes", Group.MEETINGS, "Minutes of board and member meetings, at least the last twelve months",
        "CIV 4950, 5200(a)(8); a buyer may ask for a year's (4525(a)(10))", (S.PRIOR_MANAGER, S.BOARD), "book min",
        (Record(R.MINUTES), Kinds((K.MINUTES,))), (L, P, Q, H), "jason meetings"),
    OnboardingItem(
        "agendas", Group.MEETINGS, "Agendas and meeting notices", "CIV 4920", (S.BOARD, S.PRIOR_MANAGER), "book agenda",
        (Kinds((K.AGENDA,)),), (L, P, H), "jason meetings"),
    OnboardingItem(
        "meeting-schedule", Group.MEETINGS, "The regular meeting schedule, place or platform, and the annual meeting's month",
        "notice periods count from it (CIV 4920)", (S.BOARD,), "Community.meeting_schedule(), calendar_policy()",
        (Method("meeting_schedule"), Method("calendar_policy")), (L, P, H), "jason calendar"),
    OnboardingItem(
        "executive-sessions", Group.MEETINGS, "Executive-session minutes", "CIV 4935", (S.BOARD,), "book exec",
        (Kinds((K.EXECUTIVE_SESSION,)),), (L, P)),
    OnboardingItem(
        "recordings", Group.MEETINGS, "Meeting recordings and the meeting platform", "jason drafts minutes from them",
        (S.BOARD,), "Community.zoom_meeting_rules()", (Method("zoom_meeting_rules"),), (P, H), "jason zoom"),
    OnboardingItem(
        "notice-rules", Group.MEETINGS, "How notices are delivered and posted", "CIV 4040, 4045, 4920",
        (S.BOARD,), "Community.notice_rules()", (Method("notice_rules"),), (L, P), "jason notices"),
    # Elections
    OnboardingItem(
        "election-status", Group.ELECTIONS, "The election in progress or last held: results, seats and terms filled, next cycle",
        "CIV 5100-5145", (S.PRIOR_MANAGER, S.BOARD), "Community.assignments()",
        (Kinds((K.ELECTION_RESULTS,)), Method("assignments", contains="election")), (L, Q, H)),
    OnboardingItem(
        "election-materials", Group.ELECTIONS, "Ballots and election materials, kept a year",
        "CIV 5125, 5200(c)", (S.PRIOR_MANAGER,), "book ballots",
        (Record(R.ELECTION_MATERIALS), Kinds((K.BALLOT,))), (L,)),
    # Enforcement
    OnboardingItem(
        "discipline-policy", Group.ENFORCEMENT, "The enforcement policy, the fine schedule, and the hearing procedure",
        "CIV 5850, 5855; in the policy statement (5310(a)(8))", (S.PRIOR_MANAGER, S.BOARD),
        "book disc; Community.hearing_policy()", (InBook(Book.DISC), Method("hearing_policy")), (L, P, H),
        "jason sync-catalog"),
    OnboardingItem(
        "open-violations", Group.ENFORCEMENT, "Open violations, notices sent, and hearings pending",
        "a buyer gets unresolved notices (CIV 4525(a)(5))", (S.PRIOR_MANAGER,), "PayHOA violations",
        (Store("payhoa.db", "violations"), Kinds((K.VIOLATION_NOTICE,))), (L, P, F), "jason violations", private=True),
    OnboardingItem(
        "parking", Group.ENFORCEMENT, "Parking permits issued, towing authorizations, and the towing company",
        "Vehicle Code 22658; the rules' parking part", (S.PRIOR_MANAGER, S.BOARD), FACTS_FILE, (Fact("parking"),),
        (H, F), private=True,
        ask=A("Who is the towing company, where is the towing authorization, and where is the list of parking "
              "permits issued?", lead_kinds=(K.CONTRACT,))),
    OnboardingItem(
        "dispute-resolution", Group.ENFORCEMENT, "Internal and alternative dispute resolution procedures",
        "CIV 5905-5920, 5925-5965; summarized in the policy statement", (S.BOARD,), "Community.assignments()",
        (Method("assignments", contains="dispute"),), (L, P)),
    # Architectural review
    OnboardingItem(
        "architectural-procedure", Group.ARCHITECTURAL, "The architectural review procedure and its request form",
        "CIV 4765; summarized in the policy statement (5310(a)(10))", (S.BOARD, S.PRIOR_MANAGER),
        "book arch; Community.request_forms()", (InBook(Book.ARCH), Method("request_forms")), (L, P, H),
        "jason sync-catalog; jason forms"),
    OnboardingItem(
        "architectural-decisions", Group.ARCHITECTURAL, "Past architectural approvals and denials by unit, and pending requests",
        "a decision binds the next request on that unit", (S.PRIOR_MANAGER, S.BOARD), "PayHOA requests",
        (Store("payhoa.db", "requests"),), (P,), "jason sync-catalog"),
    # Records, retention, and pending matters
    OnboardingItem(
        "records-map", Group.RECORDS, "Where each kind of record lives: library folders, Drive folders, and sync rules",
        "CIV 5200, 5210: producible on request", (S.BOARD, S.PLATFORM),
        "Community.library_folders(), drive_roots(), sync_rules",
        (Method("library_folders"), Method("drive_roots"), Method("sync_rules")), (L, P), "jason duties"),
    OnboardingItem(
        "paper-records", Group.RECORDS, "Paper records in storage: boxes, a contents list for each, and where to collect them",
        "the association's records follow the association", (S.PRIOR_MANAGER,), FACTS_FILE, (Fact("paper-records"),),
        (Q, H),
        ask=A("Where are the paper records (how many boxes, with a contents list for each), and how are they "
              "collected?", choices=("none: there are no paper records",))),
    OnboardingItem(
        "litigation", Group.RECORDS, "Pending litigation and claims, with counsel and the matter's status",
        "the incoming manager's disclosure; holds and privilege", (S.COUNSEL, S.PRIOR_MANAGER),
        "Community.legal_cases(); private case facts", (Method("legal_cases"), Private("cases")), (P, Q, H),
        "jason cases", private=True),
    OnboardingItem(
        "construction-defects", Group.RECORDS, "Construction defect claims, settlements, and the notice to members",
        "CIV 6000, 6100; a buyer gets the list and the notice (4525(a)(6), (7))", (S.COUNSEL, S.BOARD),
        "Community.legal_cases()", (Kinds((K.SETTLEMENT,)), Method("legal_cases")), (L, P, H), "jason cases",
        private=True),
    OnboardingItem(
        "legal-holds", Group.RECORDS, "Legal holds in force", "what may not be deleted", (S.COUNSEL,),
        "Community.legal_holds()", (Method("legal_holds"), Private("holds")), (P,), "jason hold", private=True),
    OnboardingItem(
        "privilege", Group.RECORDS, "Counsel and the other parties whose communications are privileged",
        "jason holds privileged records back", (S.COUNSEL, S.BOARD), "Community.privilege_parties()",
        (Method("privilege_parties"),), (P,)),
    OnboardingItem(
        "open-requests", Group.RECORDS, "Open owner requests and the correspondence behind them",
        "nothing open is lost in the move", (S.PRIOR_MANAGER, S.PLATFORM), "PayHOA requests; the Gmail store",
        (Store("payhoa.db", "requests"), Store("gmail/correspondence.json")), (P,), "jason sync-catalog; jason gmail",
        private=True),
    OnboardingItem(
        "templates", Group.RECORDS, "Letter templates, the letterhead, and the owner forms (records inspection, special meeting petition)",
        "notices and letters go out on the association's own forms (CIV 5205)", (S.BOARD, S.PRIOR_MANAGER),
        "Community.document_templates(), letterhead(), request_forms()",
        (Method("document_templates"), Method("letterhead"), Method("request_forms")), (P, H), "jason templates"),
    OnboardingItem(
        "orientation", Group.RECORDS, "Board orientation: training material, recorded walkthroughs, and the law references the board uses",
        "how one board's knowledge reaches the next", (S.BOARD,), FACTS_FILE, (Fact("orientation"),), (H,),
        ask=A("What board orientation material is there (training, recorded walkthroughs, the law references the "
              "board uses), and where?", choices=("none yet",))),
    # System access
    OnboardingItem(
        "management-software", Group.ACCESS, "The association's organization in the management software, and the board's access",
        "jason reads and writes through it", (S.PLATFORM,), "Community.org_id; setting payhoa_record_uid",
        (Method("org_id"), Setting("payhoa_record_uid")), (P,), "jason sync-catalog"),
    OnboardingItem(
        "prior-portal", Group.ACCESS, "The board's access to the prior manager's portal until the handover ends",
        "the records are there until they are delivered", (S.PRIOR_MANAGER,),
        "the password vault; the private facts record only the Keeper record's name", (Fact("prior-portal"),), (F,),
        note="Asked during the transition: access ended before the records were delivered.",
        ask=A("Which Keeper record holds the board's sign-in to the prior manager's portal, and until what day does "
              "access last? Answer with the record's name, never a password.", KEEPER,
              choices=("none: the handover is complete",))),
    OnboardingItem(
        "email-groups", Group.ACCESS, "The association's email domain and groups, and what each is for",
        "jason reads which group a message came through", (S.BOARD,), "Community.google_groups(), email_domains()",
        (Method("google_groups"), Method("email_domains")), (P, H), "jason gmail"),
    OnboardingItem(
        "drive", Group.ACCESS, "The shared Drive and its folder map", "jason's sync rules and library read it",
        (S.BOARD,), "Community.drive_home(), drive_roots()",
        (Method("drive_home"), Method("drive_roots")), (P, H), "jason drive"),
    OnboardingItem(
        "website", Group.ACCESS, "The owners' website and its pages", "where members find documents (CIV 4045)",
        (S.BOARD,), "Community.site_pages()", (Method("site_pages"),), (P,)),
    OnboardingItem(
        "payment-portal", Group.ACCESS, "How owners pay: the payment portal, the lockbox, and the welcome letter",
        "owners need it before the first assessment after the move", (S.BANK, S.PRIOR_MANAGER), FACTS_FILE,
        (Fact("payment-portal"),), (H, F),
        ask=A("How do owners pay: the payment portal, the lockbox address, and where is the welcome letter?",
              lead_kinds=(K.NOTICE, K.CORRESPONDENCE))),
    OnboardingItem(
        "vault", Group.ACCESS, "The password vault and the Google sign-in jason uses", "jason never stores a password",
        (S.BOARD,), "settings: Keeper record UIDs", (Setting("google_oauth_record_uid"),), (P,), "jason login"),
    OnboardingItem(
        "calendar", Group.ACCESS, "The association calendar for meetings, deadlines, and renewals",
        "jason posts meetings and deadlines to it", (S.BOARD,), "Community.calendar_policy()",
        (Method("calendar_policy"),), (P, H), "jason calendar"),
)
del L, P, Q, F, H, S, A, PROFILE_CHANGE, KEEPER


def items(group: Group | None = None) -> tuple[OnboardingItem, ...]:
    return tuple(i for i in ITEMS if group is None or i.group is group)


def item(key: str) -> OnboardingItem | None:
    return next((i for i in ITEMS if i.key == key), None)


# --- Stages ------------------------------------------------------------------------------------------------------------

class Stage(Enum):
    """The order a takeover opens in. Each stage's gate is open when its items are present and its checks pass."""

    START = "start"
    INGEST = "ingest"
    ESTABLISH = "establish"
    OPERATE = "operate"
    ADOPT = "adopt"


@dataclass(frozen=True)
class Gate:
    stage: Stage
    title: str
    opens: str                               # the sentence that says when it opens
    items: tuple[str, ...]                   # checklist item keys that must be present
    checks: tuple[Check, ...] = ()           # and the gate's own checks


# Which text is in force, and whether an instrument took effect: open questions of these kinds hold "establish" closed.
IN_FORCE_KINDS = ("standing", "readings differ", "before differs", "drift")

GATES: tuple[Gate, ...] = (
    Gate(Stage.START, "The profile is set up and jason reaches the association's systems",
         "open once the units, the management software, the Drive, and the vault are present",
         ("units", "management-software", "drive", "vault")),
    Gate(Stage.INGEST, "The records are taken in, classified, and mapped",
         "open once the records map, minutes, budget reports, financial statements, contracts, and insurance policies "
         "are present, and no library file waits for a kind",
         ("records-map", "minutes", "budget-reports", "financial-statements", "contracts", "policies"),
         (Settled(("classify",)),)),
    Gate(Stage.ESTABLISH, "The governing documents are established",
         "open once the declaration with its amendments and annexations, the bylaws, and the articles are present; "
         "each recorded copy is matched in the county index; and no question is open about which text is in force",
         ("declaration", "amendments", "annexations", "bylaws", "articles"),
         (Verified(), Settled(IN_FORCE_KINDS, governing=True))),
    Gate(Stage.OPERATE, "jason can run the association's business",
         "open once the board, the signers, the accounts, the assessments, the fiscal year, the meetings, the notices, "
         "the schedule, and the utilities are present",
         ("board-rule", "board-roster", "signers", "bank-accounts", "assessments", "fiscal-year", "meeting-schedule",
          "notice-rules", "assignments", "utility-accounts")),
    Gate(Stage.ADOPT, "The board has the rules and policies jason applies",
         "open once the operating rules, the election rules, the policies and resolutions, the collection and "
         "enforcement policies, the architectural procedure, the governing set, and the conflicts are present",
         ("operating-rules", "election-rules", "policies-resolutions", "collection-policy", "discipline-policy",
          "architectural-procedure", "governing-set", "conflicts")),
)


@dataclass(frozen=True)
class GateResult:
    gate: Gate
    waiting: tuple[ItemResult, ...]          # its items not yet present
    findings: tuple[Finding, ...]            # its own checks

    @property
    def open(self) -> bool:
        return not self.waiting and all(f.passed for f in self.findings)

    @property
    def evidence(self) -> str:
        parts = [f"{r.item.key} {r.status.value}" for r in self.waiting]
        parts += [f.evidence for f in self.findings if not f.passed]
        return "; ".join(parts)


def gates(results: Iterable[ItemResult], ctx: Context) -> tuple[GateResult, ...]:
    """Each stage's gate against the checklist's results and the context."""
    found = {r.item.key: r for r in results}
    out = []
    for g in GATES:
        waiting = tuple(found[k] for k in g.items if k in found and found[k].status is not Status.PRESENT)
        out.append(GateResult(g, waiting, tuple(c.run(ctx) for c in g.checks)))
    return tuple(out)


def stages_of(key: str) -> tuple[Stage, ...]:
    """The stages whose gate waits on this checklist item."""
    return tuple(g.stage for g in GATES if key in g.items)


def check_item(item: OnboardingItem, ctx: Context) -> ItemResult:
    findings = tuple(c.run(ctx) for c in item.checks)
    passed = sum(1 for f in findings if f.passed)
    if findings and passed == len(findings):
        status = Status.PRESENT
    elif passed:
        status = Status.PARTIAL
    else:
        status = Status.MISSING
    return ItemResult(item, status, findings)


def check(ctx: Context, chosen: Iterable[OnboardingItem] | None = None) -> tuple[ItemResult, ...]:
    return tuple(check_item(item, ctx) for item in (ITEMS if chosen is None else chosen))


def counts(results: Iterable[ItemResult]) -> dict[str, int]:
    found = {s.value: 0 for s in Status}
    for r in results:
        found[r.status.value] += 1
    return found


def by_group(results: Iterable[ItemResult]) -> dict[Group, list[ItemResult]]:
    grouped: dict[Group, list[ItemResult]] = {g: [] for g in Group}
    for r in results:
        grouped[r.item.group].append(r)
    return {g: rows for g, rows in grouped.items() if rows}


def report_markdown(results: tuple[ItemResult, ...], *, title: str) -> str:
    total = counts(results)
    lines = [f"# {title}", ""]
    lines.append(f"{len(results)} items: {total['present']} present, {total['partial']} partial, {total['missing']} missing. "
                 f"{sum(1 for r in results if r.item.by_person)} have no jason command to read them: a person supplies them.")
    lines += ["", "| Group | Items | Present | Partial | Missing |", "| --- | ---: | ---: | ---: | ---: |"]
    for group, rows in by_group(results).items():
        c = counts(rows)
        lines.append(f"| {group.title} | {len(rows)} | {c['present']} | {c['partial']} | {c['missing']} |")
    for group, rows in by_group(results).items():
        lines += ["", f"## {group.title}", "", "| Item | Status | Evidence | Supplied by | From |", "| --- | --- | --- | --- | --- |"]
        for r in rows:
            who = "a person" if r.item.by_person else r.item.fetch
            lines.append(f"| {r.item.title} (`{r.item.key}`) | {r.status.value} | {_cell(r.evidence)} | {_cell(who)} | "
                         f"{', '.join(o.value for o in r.item.origins)} |")
    lines += ["", "A missing item is a place to look, not a finding that the record does not exist: the association may "
              "hold it outside jason. Evidence gives counts only, never a private value.", ""]
    return "\n".join(lines)


def request_markdown(source: Source, *, title: str) -> str:
    """The items to ask one source for, grouped: the list a board or a new manager sends."""
    lines = [f"# {title}", ""]
    for group in Group:
        rows = [i for i in items(group) if source in i.sources]
        if not rows:
            continue
        lines += [f"## {group.title}", ""]
        for i in rows:
            lines.append(f"- [ ] {i.title}")
        lines.append("")
    return "\n".join(lines)


def report_dicts(results: tuple[ItemResult, ...]) -> list[dict[str, Any]]:
    return [
        {"key": r.item.key, "group": r.item.group.value, "title": r.item.title, "status": r.status.value,
         "why": r.item.why, "sources": [s.value for s in r.item.sources], "fills": r.item.fills,
         "origins": [o.value for o in r.item.origins], "fetch": r.item.fetch, "byPerson": r.item.by_person,
         "private": r.item.private, "note": r.item.note,
         "ask": ({"question": r.item.ask.question, "record": r.item.ask.record.value, "stakes": r.item.ask.stakes}
                 if r.item.ask else None),
         "findings": [{"passed": f.passed, "evidence": f.evidence} for f in r.findings]}
        for r in results
    ]


def _cell(text: str) -> str:
    return text.replace("|", "\\|")


def _row_text(row: Any) -> str:
    """A row's naming words: its name, key, title, kind, and purpose, whichever it has; else the row itself."""
    words = [getattr(row, attr, None) for attr in ("name", "key", "title", "kind", "purpose")]
    found = [str(getattr(w, "value", w)) for w in words if w]
    return " ".join(found) if found else str(row)


def _size(value: Any, contains: str) -> int:
    if value is None:
        return 0
    if isinstance(value, (str, bytes)):
        return 1 if value.strip() else 0
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return 1 if value else 0
    if isinstance(value, dict):
        rows: list[Any] = list(value.values()) if contains else list(value)
    elif isinstance(value, (tuple, list, set, frozenset)):
        rows = list(value)
    else:
        return 1
    if contains:
        needle = contains.casefold()
        rows = [r for r in rows if needle in _row_text(r).casefold()]
    return len(rows)


__all__ = [
    "Check", "Context", "FACTS", "Fact", "FactAsk", "FactRecord", "Finding", "GATES", "Gate", "GateResult", "Group",
    "IN_FORCE_KINDS", "InBook", "ItemResult", "ITEMS", "Kinds", "Method", "OnboardingItem", "Origin", "Private",
    "Record", "Setting", "Settled", "Source", "Stage", "Status", "Store", "Verified", "by_group", "check", "check_item",
    "counts", "gates", "item", "items", "report_dicts", "report_markdown", "request_markdown", "stages_of",
]
