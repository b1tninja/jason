"""Onboarding a community: the request list a manager sends, and what came back.

``CATALOG`` is the general list of records, documents, reports, ledgers, and information a manager asks for when
taking on a California common interest development, written once for any association from jason's own record
models: the Civil Code 5200 records (``AssociationRecord``), the subdivider's deliveries (``DeveloperDelivery``,
10 CCR 2792.23), and the document kinds. A profile marks an item not applicable; it never edits the list.

The checklist store (``data/onboarding/requests.json``) keeps, per item, what a person did: asked (of whom, when),
received (when, where filed), pinned, gap, or not applicable (why). Where a store already answers (the 5200
inventory, the developer file, the library), the loader overlays that reading; the person's entry is the record.
jason's own store; it sends no request and files nothing.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

STORE = Path("onboarding") / "requests.json"


class Holder(Enum):
    BOARD = "the board"
    PRIOR_MANAGER = "the prior manager"
    DEVELOPER = "the developer"
    COUNTY = "the county"
    AGENT = "an agent or vendor"
    COUNSEL = "counsel"
    TREASURER = "the treasurer or CPA"


class Group(Enum):
    GOVERNING = "governing documents and the developer file"
    FINANCIAL = "financial"
    INSURANCE = "insurance"
    CONTRACTS = "contracts, vendors, and utilities"
    MEMBERSHIP = "membership and owners"
    MEETINGS = "meetings and elections"
    LEGAL = "legal"
    PROPERTY = "property"
    ACCOUNTS = "accounts and access"
    TRANSITION = "the transition from the prior manager"


class RequestStatus(Enum):
    NOT_ASKED = "not asked"
    ASKED = "asked"
    RECEIVED = "received"
    PINNED = "pinned"
    GAP = "gap"
    NOT_APPLICABLE = "not applicable"


@dataclass(frozen=True)
class CatalogItem:
    key: str
    group: Group
    title: str                       # plain words, as a board member knows it
    authority: str = ""              # the statute or regulation, beside the title
    holders: tuple[Holder, ...] = (Holder.BOARD,)
    record: str = ""                 # AssociationRecord value it satisfies, when one
    delivery: str = ""               # DeveloperDelivery value, when one
    kinds: tuple[str, ...] = ()      # DocumentKind values it is filed as
    why: str = ""                    # one line on what it is for


def _i(key, group, title, authority="", holders=(Holder.BOARD,), record="", delivery="", kinds=(), why=""):
    return CatalogItem(key, group, title, authority, tuple(holders), record, delivery, tuple(kinds), why)


B, P, D, C, A, L, T = Holder.BOARD, Holder.PRIOR_MANAGER, Holder.DEVELOPER, Holder.COUNTY, Holder.AGENT, Holder.COUNSEL, Holder.TREASURER
G = Group

CATALOG: tuple[CatalogItem, ...] = (
    # governing documents and the developer file
    _i("declaration", G.GOVERNING, "The recorded declaration (CC&Rs) and every amendment", "CIV 4135, 5200(a)(11)", (B, P, C), "governing_documents", "declaration", ("declaration", "amendment"), "which instrument controls"),
    _i("annexations", G.GOVERNING, "Each annexation or supplemental declaration", "CIV 5200(a)(11)", (B, P, C), "governing_documents", "", ("annexation",), "which units and common areas each phase added"),
    _i("articles", G.GOVERNING, "Articles of incorporation and the Secretary of State record", "CIV 4150; Corp. Code", (B, P), "governing_documents", "articles", ("articles",)),
    _i("bylaws", G.GOVERNING, "Bylaws and their amendments", "CIV 4150", (B, P), "governing_documents", "bylaws", ("bylaws",)),
    _i("rules", G.GOVERNING, "Operating rules, the fine schedule, and the architectural standards", "CIV 4340-4370", (B, P), "governing_documents", "use_rules", ("operating_rules",)),
    _i("election-rules", G.GOVERNING, "Election rules", "CIV 5105", (B, P), "governing_documents", "", ("election_rules",)),
    _i("policies-resolutions", G.GOVERNING, "Board policies and resolutions in force", "", (B, P), "", "", ("policy", "resolution"), "collection policy, hearing procedure, records policy, meeting schedule resolution"),
    _i("map-plan", G.GOVERNING, "The subdivision map and the condominium plan", "10 CCR 2792.23; CIV 4120, 4285", (D, C, B), "", "condominium_plan", ("map", "condominium_plan"), "the units and common areas as recorded"),
    _i("common-area-deed", G.GOVERNING, "The deed of the common area to the association", "10 CCR 2792.23", (D, C), "", "common_area_deed", ("grant_deed",)),
    _i("public-report", G.GOVERNING, "The public report (DRE) for each phase", "BPC 11018.2; 10 CCR 2792.23", (D, B), "", "public_report", ("dre_report",), "the budget and the reserves the subdivider promised"),
    _i("plans-manuals", G.GOVERNING, "Building plans and the maintenance manuals or plans delivered", "10 CCR 2792.23", (D, B, P), "", "maintenance_plans", ("plan_set",)),
    _i("bonds-warranties", G.GOVERNING, "The subdivider's bonds, securities, and warranties, and their releases", "10 CCR 2792.4, 2792.9, 2792.10", (D, B), "", "bond", ("surety_bond", "security_agreement", "subsidy_agreement", "bond_release"), "a bond with no release on file is open on the record"),
    # financial
    _i("budget", G.FINANCIAL, "The current and prior year's budgets", "CIV 5300(b)(1)", (T, P), "financial_disclosure", "", ("budget",)),
    _i("reserve-study", G.FINANCIAL, "The reserve study and its last update", "CIV 5550, 5300(b)(3)", (T, P, A), "financial_disclosure", "", ("reserve_study",), "the site visit is due every three years"),
    _i("reviewed-statement", G.FINANCIAL, "The reviewed financial statement (CPA) for each year", "CIV 5305", (T, P), "financial_disclosure", "", ("financial_review",)),
    _i("interim-financials", G.FINANCIAL, "Monthly or quarterly financial statements and treasurer's reports", "CIV 5500, 5200(a)(3)", (P, T), "interim_financial", "", ("financial_statement", "treasurer_report")),
    _i("check-register", G.FINANCIAL, "The check register and general ledger", "CIV 5200(a)(10)", (P, T), "check_register", "", (), "the ledger before the current platform was adopted"),
    _i("bank-statements", G.FINANCIAL, "Bank statements for the operating and reserve accounts, and which account is the reserve", "CIV 5200(b), 5500", (T, P), "enhanced", "", ("bank_statement",)),
    _i("reserve-accounts", G.FINANCIAL, "Reserve account statements and investments (CDs), and any reserve borrowing", "CIV 5200(a)(7), 5515", (T, P), "reserve_account", "", (), "a borrowing needs its notice, finding, and restoration within a year"),
    _i("tax-returns", G.FINANCIAL, "Federal and state tax returns and the exempt status", "CIV 5200(a)(6)", (T, P), "tax_return", "", ("tax_return",)),
    _i("vendor-approvals", G.FINANCIAL, "Contracts awarded and the approvals behind them", "CIV 5200(a)(5)", (B, P), "vendor_approval", "", (), "paid against approved"),
    _i("assessment-roll", G.FINANCIAL, "The assessment roll, delinquencies, and any payment plans", "CIV 5600-5740", (P, T), "", "", ("owner_statement", "delinquency_notice"), "what each unit owes and where collection stands"),
    _i("annual-disclosures", G.FINANCIAL, "The annual budget report and policy statement last sent, and when", "CIV 5300, 5310, 5320", (P, B), "financial_disclosure", "", ("annual_disclosure",)),
    _i("reserve-litigation", G.FINANCIAL, "Any accounting of reserve funds used for litigation", "CIV 5520, 5200(a)(12)", (T, L), "reserve_litigation_accounting", "", ()),
    # insurance
    _i("policies", G.INSURANCE, "Every policy in force: master, umbrella, fidelity, directors and officers, workers' compensation, flood", "CIV 5800-5810, 5300(b)(9)", (A, P), "executed_contract", "insurance", ("insurance_policy",)),
    _i("evidence-loss-runs", G.INSURANCE, "Evidence of insurance, loss runs, and open claims", "", (A, P), "", "", ("evidence_of_insurance", "loss_run", "claim_letter")),
    _i("agent", G.INSURANCE, "The agent or broker of record and the renewal dates", "", (A, B), "", "", (), "the renewal is a board decision; a 5810 notice when limits change"),
    # contracts, vendors, utilities
    _i("contracts", G.CONTRACTS, "Executed contracts and leases in force, with their terms and renewals", "CIV 5200(a)(4)", (P, B), "executed_contract", "contract", ("contract", "lease")),
    _i("vendors", G.CONTRACTS, "The vendor list with contacts, portals, and how each is paid", "", (P, B), "", "", (), "landscape, pool, elevator, pest, fire, backflow, janitorial, security"),
    _i("utilities", G.CONTRACTS, "Utility accounts by building and who pays each", "", (P, A), "", "", ("utility_bill",)),
    _i("permits", G.CONTRACTS, "Open permits and the permit portal account", "", (C, P), "", "", (), "the city's records of the association's own work"),
    # membership and owners
    _i("membership-list", G.MEMBERSHIP, "The membership list: each unit's owner, mailing address, and contact", "CIV 5200(a)(9), 5220", (P, B), "membership_list", "membership_register", ("membership_list",)),
    _i("owner-information", G.MEMBERSHIP, "Each owner's delivery preference, secondary address, occupancy, and representative", "CIV 4040, 4041, 5260", (P, B), "", "", ("form",), "the annual owner-information request"),
    _i("rentals", G.MEMBERSHIP, "Which units are rented and the rental rules in force", "CIV 4740, 4741", (P, B), "", "", (), "existing rentals against any cap"),
    _i("resale-history", G.MEMBERSHIP, "Resale disclosures and escrow requests answered", "CIV 4525-4545, 5200(a)(2)", (P,), "transfer_financial", "", ("resale_disclosure", "escrow_request")),
    # meetings and elections
    _i("minutes", G.MEETINGS, "Board and member meeting minutes, open and executive, for the years kept", "CIV 4950, 5200(a)(8)", (B, P), "minutes", "minutes", ("minutes", "executive_session")),
    _i("agendas-notices", G.MEETINGS, "Agendas and meeting notices, and how notice is given", "CIV 4920, 4930", (B, P), "minutes", "", ("agenda", "notice")),
    _i("elections", G.MEETINGS, "Election materials: ballots, results, the inspector's report, for the retention period", "CIV 5125, 5200(c)", (B, P), "election_materials", "", ("ballot", "election_results")),
    _i("board-roster", G.MEETINGS, "The board roster, officers, terms, and the meeting schedule", "CIV 4085, 4920", (B,), "", "", (), "who signs, who is noticed"),
    # legal
    _i("cases", G.LEGAL, "Pending or threatened claims and lawsuits, and counsel's contact", "CIV 4935, 5200(a)(4)", (L, B), "", "", ("legal_correspondence", "legal_brief", "settlement")),
    _i("liens", G.LEGAL, "Liens the association recorded and their releases", "CIV 5675, 5685", (P, C), "", "", ("recorded_lien",), "a lien paid needs its release within 21 days"),
    _i("holds", G.LEGAL, "Any litigation hold in force and what it covers", "", (L,), "", "", ()),
    # property
    _i("parcels", G.PROPERTY, "The parcel numbers, units, buildings, and common areas", "", (C, D, P), "", "", (), "the index the records are read against"),
    _i("inspections", G.PROPERTY, "Inspection reports: balcony (elevated elements), fire alarm and sprinklers, backflow, elevator", "CIV 5551, 5200(a)(15)", (P, A), "elevated_element_report", "", ("inspection_report", "elevated_element_inspection")),
    _i("reserve-components", G.PROPERTY, "The reserve components and their last replacement dates", "CIV 5550", (A, P), "", "", (), "whether work reset a component's life"),
    _i("photos", G.PROPERTY, "Photos of the common areas and any incident", "", (B, P), "", "", ("image",)),
    # accounts and access
    _i("payhoa", G.ACCOUNTS, "The accounting and owner platform: organization, admin access, folders", "", (B, P), "", "", (), "the ledger, the library, the owners"),
    _i("google", G.ACCOUNTS, "The association's Google account: Drive home, groups, calendar, consent", "", (B, P), "", "", ()),
    _i("mail", G.ACCOUNTS, "The mailing address of record and the mail service, with forwarding from the prior address", "CIV 4035", (B, P), "", "", ()),
    _i("zoom", G.ACCOUNTS, "The meeting platform account and its recordings", "", (B, P), "", "", ("audio",)),
    _i("portals", G.ACCOUNTS, "County, utility, and vendor portal accounts", "", (P, A), "", "", ()),
    _i("website-groups", G.ACCOUNTS, "The website, email groups, and who administers them", "CIV 4045", (B, P), "", "", ()),
    # the transition
    _i("final-accounting", G.TRANSITION, "The prior manager's final accounting and transfer of funds", "BPC 11500; CIV 5380", (P, T), "", "", (), "reserve accounts before adoption show as other assets"),
    _i("archive", G.TRANSITION, "The prior manager's document archive, in its folders", "CIV 5200", (P,), "", "", (), "classified by folder on arrival"),
    _i("disclosure", G.TRANSITION, "The manager's own disclosure and the acknowledgment that the records belong to the association", "CIV 5375; BPC 11504", (B,), "", "", ()),
    _i("open-matters", G.TRANSITION, "Open matters the prior manager was handling: requests, violations, claims, projects", "", (P, B), "", "", (), "what is awaiting an answer"),
)

CATALOG_KEYS = {c.key for c in CATALOG}


@dataclass
class Request:
    key: str
    status: str = RequestStatus.NOT_ASKED.value
    asked_of: str = ""               # a Holder value or a person's role; never a private fact the page must hide
    asked_on: str = ""
    chased_on: str = ""
    received_on: str = ""
    filed: str = ""                  # where it was filed: a PayHOA folder, a Drive path, a library id
    reason: str = ""                 # for not applicable
    note: str = ""
    updated: str = ""
    history: list[str] = field(default_factory=list)


EDITABLE = ("status", "asked_of", "asked_on", "chased_on", "received_on", "filed", "reason", "note")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def catalog_dicts() -> list[dict[str, Any]]:
    return [{"key": c.key, "group": c.group.value, "title": c.title, "authority": c.authority, "holders": [h.value for h in c.holders],
             "record": c.record, "delivery": c.delivery, "kinds": list(c.kinds), "why": c.why} for c in CATALOG]


def load(data_dir: Path) -> dict[str, Request]:
    path = Path(data_dir) / STORE
    if not path.is_file():
        return {}
    known = set(Request.__dataclass_fields__)
    rows = [Request(**{k: v for k, v in raw.items() if k in known}) for raw in json.loads(path.read_text(encoding="utf-8")).get("requests", [])]
    return {r.key: r for r in rows}


def save(data_dir: Path, rows: dict[str, Request]) -> Path:
    path = Path(data_dir) / STORE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"savedAt": _now(), "requests": [asdict(r) for r in rows.values()]}, indent=1), encoding="utf-8")
    return path


def _store_lock(fn):
    import functools

    from jason.locks import Resource, hold

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        with hold(Resource.STORE, "onboarding", timeout=60, purpose=f"onboarding: {fn.__name__}"):
            return fn(*args, **kwargs)
    return wrapper


@_store_lock
def update(data_dir: Path, key: str, **changes: Any) -> Request:
    """Record what a person did about one item. ``status`` is a RequestStatus value; not applicable needs a reason."""
    if key not in CATALOG_KEYS:
        raise KeyError(key)
    unknown = sorted(set(changes) - set(EDITABLE))
    if unknown:
        raise ValueError(f"{', '.join(unknown)}: not a request field")
    if "status" in changes and changes["status"] not in {s.value for s in RequestStatus}:
        raise ValueError(f"status is one of {', '.join(s.value for s in RequestStatus)}")
    rows = load(data_dir)
    r = rows.get(key) or Request(key=key)
    now = _now()
    if changes.get("status") == RequestStatus.NOT_APPLICABLE.value and not (changes.get("reason") or r.reason):
        raise ValueError("not applicable needs a reason; it is the record of why")
    for k, v in changes.items():
        v = str(v)
        if getattr(r, k) != v:
            if k == "status":
                r.history.append(f"{now[:10]}: {r.status} -> {v}")
            setattr(r, k, v)
    r.updated = now
    rows[key] = r
    save(data_dir, rows)
    return r


def request_letter(items: list[dict[str, Any]], *, association: str = "the association", to: str = "the board") -> str:
    """The request list as a letter in plain words, grouped, with the statute beside each item. Sent by a person."""
    out = [f"# Records and information requested for {association}", "", f"To {to}: as the new manager, I am gathering the association's records. "
           "Please send what you have of the items below, or tell me who holds each. Where an item does not exist or does not "
           "apply, a line saying so is as useful as the document.", ""]
    by: dict[str, list[dict[str, Any]]] = {}
    for it in items:
        by.setdefault(it["group"], []).append(it)
    for group, rows in by.items():
        out += [f"## {group[0].upper() + group[1:]}", ""]
        for it in rows:
            cite = f" ({it['authority']})" if it.get("authority") else ""
            who = f" Usually held by {', '.join(it['holders'])}." if it.get("holders") else ""
            out.append(f"- **{it['title']}**{cite}.{who}{(' ' + it['why'] + '.') if it.get('why') else ''}")
        out.append("")
    out.append("Thank you. Nothing here is a demand; it is the list of what the association's records should hold.")
    return "\n".join(out)
