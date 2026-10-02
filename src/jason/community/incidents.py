"""The maintenance history and the insurance claims, read from the association's repair paperwork and placed on units
and buildings.

A document is evidence: a proposal, estimate, quote, contract, change order, invoice, inspection report, claim letter,
or notice. ``read_evidence`` reads one document's own words (its scope and problem lines, not its terms and conditions)
into the cause, the building element, the work, whether a claim is tied to it, the places, the stage, the date, and the
amount. The rule rows below decide each; the first matching row wins where one answer is wanted, and every matching row
counts where several are (a roof leak can also be water damage to the drywall). A document the rules do not read stays
unread.

Two answers, kept apart. The work (repair, maintenance, improvement, inspection) makes every event part of the
maintenance history; a maintenance vendor's calls are maintenance by rule (``VendorWork``). Whether an event was more
than upkeep is not guessed from words: it is claimed when its paperwork ties it to an insurance claim (a claim number,
a claim letter, an adjuster, a statement or date of loss). The cause (a roof leak, a burst pipe, a collision) says what
happened; an event with a sudden cause and no claim is one a claim could have been asked for, and whether the peril was
covered is the insurer's answer.

``group_events`` joins the evidence that is one event: the same unit or building, a shared cause or element, and dates
within ``EVENT_WINDOW_DAYS`` of each other (a proposal, then the contract, then the invoice), or the same claim number.

The places come from the text. A unit is its street address on one of the development's streets; its building is the
specification's building table. The association's site address (3000 Macon Dr) means the whole community. An address
labeled as the bill-to or the customer is the payer's mailing address (often a board member's home), not the job site,
and places the event only when the document names no other.

Nothing here reads a person's name into the record. A snippet is cut from the scope lines with email addresses and
phone numbers removed; a confidential source's snippets are held back by the task unless asked for.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from enum import Enum
from typing import Any, Iterable, Mapping

from jason.community.base import BuildingRange, assign_building
from jason.community.symbols import Building, Street

EVENT_WINDOW_DAYS = 150
SAME_UNIT_DAYS = 45


class Work(Enum):
    """What the association had done. Every event is part of the maintenance history by its work."""

    REPAIR = "repair"              # a fix: a leak stopped, a part replaced, damage restored
    MAINTENANCE = "maintenance"    # upkeep: recurring service, or a maintenance vendor's call
    IMPROVEMENT = "improvement"    # something added or upgraded
    INSPECTION = "inspection"      # a report or a test
    NONE = "none"                  # paperwork with no work in it (a claim letter)


class ClaimStanding(Enum):
    """An event against the master policy's deductible, the least loss worth a claim."""

    CLAIMED = "claimed"
    CANDIDATE = "claim candidate"           # a sudden cause, and the paperwork's cost reaches the deductible
    UNDER_DEDUCTIBLE = "under deductible"   # a sudden cause, and the cost stays under it: the carrier would pay nothing
    COST_UNKNOWN = "sudden, cost unknown"   # a sudden cause, and no amount on the paperwork
    NONE = "none"                           # upkeep, an improvement, or an inspection with no sudden cause


class Cause(Enum):
    ROOF_LEAK = "roof leak"
    PLUMBING = "plumbing leak or overflow"
    WATER_INTRUSION = "water intrusion"
    DRAINAGE = "drainage or flooding"
    SEWER = "sewer backup"
    IRRIGATION_BREAK = "irrigation break"
    FIRE = "fire or smoke"
    VANDALISM = "vandalism"
    THEFT = "theft or break-in"
    VEHICLE = "vehicle collision"
    TREE = "tree failure"
    STORM = "storm or wind"
    BIRDS = "birds"
    RODENTS = "rodents"
    INSECTS = "insects or termites"
    ANIMAL = "animal attack"
    MOLD = "mold"
    DETERIORATION = "deterioration"
    ELECTRICAL = "electrical failure"
    EQUIPMENT = "equipment failure"


# Causes that are sudden events: a document naming one is an incident even when it names no emergency.
SUDDEN = frozenset({Cause.ROOF_LEAK, Cause.PLUMBING, Cause.WATER_INTRUSION, Cause.DRAINAGE, Cause.SEWER, Cause.IRRIGATION_BREAK,
                    Cause.FIRE, Cause.VANDALISM, Cause.THEFT, Cause.VEHICLE, Cause.TREE, Cause.STORM, Cause.ANIMAL})


# The perils a service contract's scope lists ("storm damaged plants, vandalism, fallen limbs"): named there, they are
# what the service covers, not an event. A roof leak, a burst pipe, or a collision named in a contract is still one.
# Causes too common to join two documents by themselves: every pest invoice names rodents, every repair deterioration.
WEAK_CAUSES = frozenset({Cause.DETERIORATION, Cause.WATER_INTRUSION, Cause.RODENTS, Cause.INSECTS, Cause.BIRDS})
LISTED_PERILS = frozenset({Cause.STORM, Cause.VANDALISM, Cause.TREE, Cause.DRAINAGE, Cause.WATER_INTRUSION, Cause.IRRIGATION_BREAK})


class Element(Enum):
    """The part of the property the document is about."""

    ROOF = "roof"
    GUTTER = "gutters and downspouts"
    BALCONY = "balcony or deck"
    EXTERIOR_WALL = "stucco, siding, or paint"
    INTERIOR = "unit interior"
    ATTIC = "attic"
    PLUMBING = "plumbing"
    GARAGE_DOOR = "garage door"
    DOOR = "door"
    WINDOW = "window"
    FENCE = "fence or wall"
    GATE = "gate"
    IRRIGATION = "irrigation"
    LANDSCAPE = "landscaping"
    TREE = "tree"
    LIGHTING = "lighting"
    ELECTRICAL = "electrical"
    STORM_DRAIN = "storm drain"
    PAVING = "paving and striping"
    MAILBOX = "mailboxes"
    FIRE_SYSTEM = "fire alarm or sprinklers"
    BACKFLOW = "backflow"
    SOLAR = "solar panels"
    HVAC = "HVAC"
    SIGNAGE = "signs"
    PEST = "pest control"


class Stage(Enum):
    """Where a document sits in an event's paper trail."""

    CLAIM = "claim"
    REPORT = "report"
    PROPOSAL = "proposal"
    CONTRACT = "contract"
    CHANGE_ORDER = "change order"
    INVOICE = "invoice"
    NOTICE = "notice"
    PHOTOS = "photos"
    OTHER = "other"


class PlaceRole(Enum):
    JOB = "job site"          # labeled as the job, project, location, or loss address, or written "@ address"
    MENTION = "mentioned"     # in the text with no label
    BILLING = "bill to"       # the payer's mailing address
    SITE = "community"        # the association's site address: the whole community


@dataclass(frozen=True)
class Rule:
    """One row: the value it gives and the words that give it."""

    value: Any
    pattern: str


CAUSE_RULES: tuple[Rule, ...] = (
    Rule(Cause.VEHICLE, r"vehicle collision|vehicle (?:hit|struck|drove|crashed)|(?:car|truck|driver) (?:hit|struck|drove into|crashed)|hit by a (?:car|vehicle|truck)|police report|collision"),
    Rule(Cause.FIRE, r"fire damage|smoke damage|\bburn(?:ed|t) (?:down|out)|caught (?:on )?fire|fire restoration(?! of)|\bscorch"),
    Rule(Cause.VANDALISM, r"vandal|graffiti|tagging|malicious mischief"),
    Rule(Cause.THEFT, r"stolen|\btheft|broke into|break[- ]in|burglary|burglarized|pried open"),
    Rule(Cause.TREE, r"fallen tree|tree (?:fell|fall|down|failure|uprooted)|(?:limb|branch) (?:fell|broke|failure)|uproot"),
    Rule(Cause.STORM, r"storm damage|wind damage|windstorm|blown off"),
    Rule(Cause.ANIMAL, r"dog attack|dog bite|attacked by"),
    Rule(Cause.ROOF_LEAK, r"roof leak|leak(?:ing|s)? (?:from|through|at|in) the roof|roof(?:ing)? .{0,40}water intrusion|water intrusion .{0,60}(?:roof|vent flashing|exhaust vent)"),
    Rule(Cause.SEWER, r"sewer (?:back|line (?:clog|break|repair|stoppage)|clog)|sewage (?:backup|spill|overflow)|back(?:ed)?[- ]?up (?:of|in|into)|"
                      r"drain line clog|main ?line (?:clog|stoppage)"),
    Rule(Cause.PLUMBING, r"overflow|supply line|burst|pipe (?:leak|broke|burst)|broken pipe|water heater|toilet|slab leak|plumbing leak|leak .{0,30}(?:pipe|valve|faucet)"),
    Rule(Cause.IRRIGATION_BREAK, r"(?:irrigation|main ?line|lateral|sprinkler) (?:line )?break|line break|broken (?:irrigation|sprinkler|lateral)|valve (?:stuck|leak)"),
    Rule(Cause.DRAINAGE, r"storm drain (?:clog|block|back|repair|line)|clogged (?:storm )?drain|standing water|ponding|pooling|"
                         r"flood(?:ed|ing)\b(?! (?:zone|insurance|policy|map))|drainage (?:problem|issue|failure)|poor drainage|hydro ?jet"),
    Rule(Cause.WATER_INTRUSION, r"water (?:damage|damaged|intrusion|stain)|\bleak(?:s|ing|ed)?\b|moisture|wet (?:drywall|ceiling)"),
    Rule(Cause.MOLD, r"\bmold(?:y)?\b(?! (?:issues related|related))"),
    Rule(Cause.BIRDS, r"pigeon|bird (?:debris|dropping|nest|screen|exclusion)|birds? nest"),
    Rule(Cause.RODENTS, r"rodent|\brats?\b|\bmice\b|rodent[- ]proof"),
    Rule(Cause.INSECTS, r"termite|wood[- ]destroying|\bbees?\b|wasps?|hornet|\bants\b"),
    Rule(Cause.DETERIORATION, r"dry ?rot|rott(?:ed|ing)|deteriorat|\brust(?:ed|ing|y)?\b|\bcrack(?:ed|ing|s)?\b|delaminat|\bfailed\b|\bworn\b|peeling"),
    Rule(Cause.ELECTRICAL, r"(?:lights?|circuit|breaker|power) (?:out|not working|tripp)|not working|outage|ballast|short(?:ed)? circuit"),
    Rule(Cause.EQUIPMENT, r"motor (?:failed|burned)|broken (?:spring|cable|opener)|won'?t (?:open|close)|off (?:its )?track"),
)

ELEMENT_RULES: tuple[Rule, ...] = (
    Rule(Element.ROOF, r"\broof|shingle|\btiles?\b|flashing|underlayment|ridge|valley|batten"),
    Rule(Element.GUTTER, r"gutter|downspout"),
    Rule(Element.BALCONY, r"balcon|\bdeck\b|elevated element|waterproofing membrane|SB ?721|SB ?326"),
    Rule(Element.EXTERIOR_WALL, r"stucco|siding|exterior (?:wall|paint)|paint(?:ing)? (?:the )?(?:building|exterior)|soffit|fascia|trim board|pressure wash"),
    Rule(Element.INTERIOR, r"drywall|ceiling|interior|bathroom|kitchen|bedroom|flooring|baseboard|cabinet"),
    Rule(Element.ATTIC, r"\battic"),
    Rule(Element.PLUMBING, r"plumbing|pipe|water heater|toilet|drain line|sewer|shut[- ]?off valve"),
    Rule(Element.GARAGE_DOOR, r"garage door"),
    Rule(Element.DOOR, r"\bdoor(?:s|way| frame| opening)?\b(?! bell)"),
    Rule(Element.WINDOW, r"\bwindows?\b"),
    Rule(Element.FENCE, r"\bfenc(?:e|ing)|block wall|retaining wall|masonry wall"),
    Rule(Element.GATE, r"\bgates?\b"),
    Rule(Element.IRRIGATION, r"irrigation|sprinkler (?:head|line|valve)|drip line|controller|lateral line"),
    Rule(Element.TREE, r"\btrees?\b|arborist|cypress|stump"),
    Rule(Element.LANDSCAPE, r"landscap|shrub|mulch|turf|lawn|planter|hedge"),
    Rule(Element.LIGHTING, r"light(?:s|ing)?\b|lamp|fixture|ballast|street ?light|porch light"),
    Rule(Element.ELECTRICAL, r"electric|breaker|wiring|outlet|panel"),
    Rule(Element.STORM_DRAIN, r"storm drain|catch basin|drain inlet"),
    Rule(Element.PAVING, r"paving|asphalt|slurry|seal ?coat|crack seal|striping|curb|concrete|sidewalk"),
    Rule(Element.MAILBOX, r"mail ?box|cluster box|CBU|mail kiosk"),
    Rule(Element.FIRE_SYSTEM, r"fire (?:alarm|sprinkler)|smoke detector|FACP|riser|fire extinguisher"),
    Rule(Element.BACKFLOW, r"backflow"),
    Rule(Element.SOLAR, r"solar"),
    Rule(Element.HVAC, r"\bHVAC\b|air condition|furnace|condenser|exhaust vent|dryer vent"),
    Rule(Element.SIGNAGE, r"\bsigns?\b|signage|sign post"),
    Rule(Element.PEST, r"pest control|rodent|termite|pigeon|bait station"),
)

LOSS_PATTERN = re.compile(r"statement of loss|proof of loss|claim (?:no\.?|number|#)\s*:?\s*[A-Z]{0,3}\d|claim outcome|\badjuster\b|date of loss|"
                          r"loss location|water mitigation|mitigation (?:estimate|services|company|invoice)|dry[- ]?out|water extraction|"
                          r"subrogation|re:? claim\b", re.I)
INCIDENT_PATTERN = re.compile(r"emergency (?:call|service|repair|response|visit|meeting|work)|emergency repairs|after[- ]hours|"
                              r"same[- ]day service|reported by", re.I)
DEFECT_PATTERN = re.compile(r"dry ?rot|rott(?:ed|ing)|deteriorat|\bcrack|(?<!passed )\bfailed\b(?!\s+\d)|failing|damaged|broken|missing|\bloose\b|slipped|"
                            r"improperly installed|defect|\brust(?:ed|ing|y)?\b", re.I)
INSPECTION_PATTERN = re.compile(r"inspection report|test report|annual inspection|report of inspection|observations and defect", re.I)
MAINTENANCE_PATTERN = re.compile(r"monthly|quarterly|bi-?weekly|weekly service|service agreement|maintenance (?:service|agreement|contract)|"
                                 r"routine|annual (?:service|test)|clean(?:ing|ed)? (?:all|the)? ?(?:gutters|debris)|flush all", re.I)
IMPROVEMENT_PATTERN = re.compile(r"install(?:ation)? of (?:new|additional)|new installation|upgrade|add(?:ing)? (?:new|additional)|improvement", re.I)
REPAIR_PATTERN = re.compile(r"repair|replace|fix|reset|reseal|patch|restor|\binstall(?:ed)?\b|\bremov(?:e|ed)\b|cleaned out", re.I)

STAGE_RULES: tuple[Rule, ...] = (
    Rule(Stage.CLAIM, r"statement of loss|claim outcome|claim info|re:? claim|primacy letter|echeque|police report|proof of loss"),
    Rule(Stage.CHANGE_ORDER, r"change order"),
    Rule(Stage.REPORT, r"inspection report|test report|service report|report of|observations and defect|inspection worksheet"),
    Rule(Stage.CONTRACT, r"contract|agreement|work authorization|signed|docusign"),
    # "Estimate" or "estimates", not "estimated" (an IRS estimated tax payment is not a bid).
    Rule(Stage.PROPOSAL, r"proposal|estimates?(?![a-z])|quote|quotation|\bbid\b|scope of work"),
    Rule(Stage.INVOICE, r"invoice|receipt|statement|\binv[_ #]|(?<![a-z])inv[-_ #]?\d|payment|paid"),
    Rule(Stage.NOTICE, r"notice"),
    Rule(Stage.PHOTOS, r"pics|photos|pictures"),
)

# Lines that are terms, disclaimers, and form text, not what was found or done.
BOILERPLATE = re.compile(
    r"warrant|not responsible|not be (?:held )?liable|liabilit|mechanic'?s'? lien|preliminary notice|arbitrat|mediation|jury|"
    r"terms (?:and|&) conditions|payment terms|late (?:fee|charge)|interest (?:rate|at)|per (?:month|annum)|service charge at|"
    r"subject to change|if a leak should appear|must be monitored|neglected|mold[- ]related|we are not qualified|"
    r"contractors'? state license board|registrar|right to cancel|cancellation|three business days|"
    r"insurance does not cover|hold harmless|indemnif|attorney'?s'? fees|governing law|entire agreement|"
    r"credit card|convenience fee|finance charge|remit|thank you for your business|www\.|https?://|"
    r"page \d+ of \d+|please (?:pay|remit)|if you have any questions|excluding|exclusions?\b|acts? of god", re.I)
# Documents that are never repair paperwork, by their name or first page: lender and escrow forms, budgets and
# disclosures, insurance policies and proposals, violation notices, demand requests, and brochures.
NOT_REPAIR = re.compile(
    r"questionnaire|form[- ]1076|instructions (?:to escrow|for buyer)|demand request|hoa request|payoff|resale|"
    r"annual (?:budget|disclosure|policy statement)|budget (?:summary|\(revised\)|report)|\bbudget\b|reserve study|"
    r"insurance (?:summary|disclosure|proposal)|policy (?:period|number)|named insured|declarations page|premium|"
    r"notice of violation|courtesy (?:notice|reminder)|hearing notice|UCC lien|solar (?:lease|agreement)|"
    r"treasurer'?s report|profit (?:and|&) loss|balance sheet|bank statement|tax (?:return|bill)|minutes of|agenda for|"
    r"overview\.pdf|brochure|newsletter|single entity|coverage (?:summary|limits?)|limits of (?:insurance|liability)|"
    r"cover letter|references\.pdf|overview _ references|management (?:proposal|agreement|contract|services)|final map|"
    r"insurance (?:agency|services)\b|underwrit|renewal (?:proposal|quote)|program administrator|"
    r"settlement agreement|homeowners? (?:hoa )?warranty|owner hoa warranty|warranty detail", re.I)
_TERMS_START = re.compile(r"\n\s*(?:terms (?:and|&) conditions|contract terms|general conditions|conditions of (?:sale|service)|"
                          r"notice to (?:owner|customer)|limited warranty)\b", re.I)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE = re.compile(r"\(?\b\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b|\+1\d{10}\b")


def scope_text(text: str, *, limit: int = 6000) -> str:
    """A document's own words: the lines before its terms, less the disclaimers and form lines."""
    body = text or ""
    stop = _TERMS_START.search(body)
    if stop and stop.start() > 200:
        body = body[: stop.start()]
    lines = [ln.strip() for ln in body.splitlines()]
    kept = [ln for ln in lines if ln and not BOILERPLATE.search(ln)]
    return "\n".join(kept)[:limit]


def _hits(rules: tuple[Rule, ...], text: str) -> list[tuple[Any, re.Match]]:
    out = []
    for rule in rules:
        m = re.search(rule.pattern, text, re.I)
        if m:
            out.append((rule.value, m))
    return out


def causes_in(text: str) -> tuple[Cause, ...]:
    """Every cause the text names, in rule order; a roof leak is not also a generic water intrusion."""
    found = [c for c, _ in _hits(CAUSE_RULES, text)]
    if Cause.ROOF_LEAK in found and Cause.WATER_INTRUSION in found:
        found.remove(Cause.WATER_INTRUSION)
    if Cause.PLUMBING in found and Cause.WATER_INTRUSION in found:
        found.remove(Cause.WATER_INTRUSION)
    return tuple(found)


def elements_in(text: str) -> tuple[Element, ...]:
    return tuple(e for e, _ in _hits(ELEMENT_RULES, text))


def stage_of(title: str, text: str) -> Stage:
    """The stage by the file's name first, then by the text's first lines."""
    for where in (title or "", (text or "")[:800]):
        for rule in STAGE_RULES:
            if re.search(rule.pattern, where, re.I):
                return rule.value
    return Stage.OTHER


def claimed_in(text: str, stage: Stage) -> bool:
    """Whether the paperwork ties the work to an insurance claim: a claim document, a claim number, an adjuster, a date or
    statement of loss. Whether a peril was covered is the insurer's answer; a claim on file is the record that one was
    asked."""
    return stage is Stage.CLAIM or bool(LOSS_PATTERN.search(text))


def work_of(text: str, causes: tuple[Cause, ...], stage: Stage) -> Work:
    """The work the words show: an inspection or test, recurring upkeep, an improvement, or a repair. A claim document
    (an adjuster's letter, a statement of loss, a police report) is no work of its own."""
    if stage is Stage.CLAIM:
        return Work.NONE
    if stage is Stage.REPORT or INSPECTION_PATTERN.search(text):
        return Work.INSPECTION
    # A service contract or proposal lists the perils its scope covers ("storm damaged plants, vandalism"): it is upkeep,
    # unless it names an emergency or a specific failure (a roof leak, a burst pipe, a collision).
    specific = (set(causes) & SUDDEN) - LISTED_PERILS
    if MAINTENANCE_PATTERN.search(text) and not INCIDENT_PATTERN.search(text) and not specific:
        return Work.MAINTENANCE
    if IMPROVEMENT_PATTERN.search(text) and not specific:
        return Work.IMPROVEMENT
    if REPAIR_PATTERN.search(text) or DEFECT_PATTERN.search(text) or causes or INCIDENT_PATTERN.search(text):
        return Work.REPAIR
    return Work.NONE


# -- where the paperwork is ------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class EvidenceFolder:
    """A Drive folder (its path under My Drive) that holds repair paperwork, and whether what it holds is confidential."""

    path: str
    holds: str
    confidential: bool = False
    skip: tuple[str, ...] = ()        # file-name globs in it that are not evidence


@dataclass(frozen=True)
class VendorWork:
    """A vendor whose calls on these elements are one kind of work, whatever its paperwork says: the association's
    roofer's leak calls are the roofs' upkeep. ``vendor`` is the counterparty's name in the sender directory; empty
    ``elements`` means any. It sets the work only; a claim on the same event is still a claim."""

    vendor: str
    work: Work
    elements: tuple[Element, ...] = ()
    why: str = ""


@dataclass(frozen=True)
class EvidencePlan:
    """What the incident history reads from Drive: its folders, the loose files at My Drive's root by name, the names that
    are never downloaded (medical and veterinary records), and the largest file worth fetching (photo sets are larger);
    and the vendors whose calls are one kind of work by rule."""

    folders: tuple[EvidenceFolder, ...]
    root_names: tuple[str, ...] = ()
    private_names: tuple[str, ...] = ()
    max_bytes: int = 25_000_000
    site_words: tuple[str, ...] = ()  # other addresses that mean the whole community (a premises address no parcel has)
    vendor_work: tuple[VendorWork, ...] = ()


def apply_vendor_work(evidence: Iterable["Evidence"], rules: Iterable[VendorWork], names: Mapping[str, str]) -> None:
    """Set each document's work by the first vendor rule that names its vendor and one of its elements. ``names`` maps
    a vendor as a document or payment prints it (upper case) to its name in the sender directory."""
    rules = tuple(rules)
    for ev in evidence:
        vendor = names.get((ev.vendor or "").upper(), ev.vendor)
        for rule in rules:
            if vendor == rule.vendor and (not rule.elements or set(ev.elements) & set(rule.elements)):
                if ev.work is not rule.work:
                    ev.hint = f"{ev.work.value} -> {rule.work.value}: {rule.why or rule.vendor}"
                    ev.work = rule.work
                break


# -- places ----------------------------------------------------------------------------------------------------------

_STREET_WORDS = {"MACON": Street.MACON_DR, "ENCHANTED": Street.ENCHANTED_WALK, "MAGICAL": Street.MAGICAL_WALK,
                 "MESMERIZING": Street.MESMERIZING_WALK, "WHIMSICAL": Street.WHIMSICAL_LN}
_ADDRESS = re.compile(r"(?<![\d$.,])(\d{4})(?:\s*(?:-|&|and|/|to)\s*(\d{4}))?\s*,?\s+(Macon|Enchanted|Magical|Mesmerizing|Whimsical)\b"
                      r"(?:\s+(?:Dr(?:ive)?|Walk|La?ne?|Wy|Way)\b\.?)?(?:\s*(?:#|Unit|Apt\.?)\s*(\d{1,3})\b)?", re.I)
# "Whimsical Lane, 5627": the street before the number, as an adjuster's file names it.
_ADDRESS_BACKWARDS = re.compile(r"\b(Macon|Enchanted|Magical|Mesmerizing|Whimsical)\s+(?:Dr(?:ive)?|Walk|La?ne?)\s*,\s*(\d{4})\b", re.I)
_BUILDING = re.compile(r"\b(?:Building|Bldg\.?)\s*#?\s*([1-8])\b(?!\s*(?:units?|condo|buildings))", re.I)
_JOB_LABEL = re.compile(r"\b(?:job ?site|job (?:address|location|name)|project|location|service (?:address|location)|property(?: address)?|"
                        r"site address|loss location|work (?:site|address)|risk address|address of loss|above units?|units?|over units?)\b", re.I)
_BILL_LABEL = re.compile(r"\b(?:bill(?:ed)? ?to|sold ?to|ship(?:ping)? ?(?:to|address)|deliver(?:y|ed)? to|customer(?: name| address)?|remit|"
                         r"mail(?:ing)? address|prepared for|owner address|insured|client|attn|c/o)\b", re.I)
_JUST_BEFORE = re.compile(r"(?:@|\bat|\bfor|\bin)\s*$", re.I)


def _role_near(before: str) -> PlaceRole:
    """The role the nearest label gives: the words just before the number on its line, then that line, then up to two
    lines above it."""
    lines = before.split("\n")[-3:]
    if _JUST_BEFORE.search(lines[-1]):
        return PlaceRole.JOB
    for line in reversed(lines):
        bill, job = _BILL_LABEL.search(line), _JOB_LABEL.search(line)
        if bill and job:
            return PlaceRole.JOB if job.start() > bill.start() else PlaceRole.BILLING
        if bill:
            return PlaceRole.BILLING
        if job:
            return PlaceRole.JOB
    return PlaceRole.MENTION


@dataclass(frozen=True)
class Place:
    address: str                  # "5615 WHIMSICAL LN", or "" for a building named alone
    building: Building | None
    role: PlaceRole
    unit_label: str = ""          # "#90" when the text prints one
    parcel: bool = True           # False: the number is on a development street but is no parcel (a typo, a project number)

    @property
    def key(self) -> str:
        return self.address or (f"building {int(self.building)}" if self.building else "community")


def places_in(text: str, buildings: Iterable[BuildingRange], site_words: Iterable[str] = (),
              known: Mapping[str, Building] | None = None, parcels: frozenset[str] | set[str] | None = None) -> tuple[Place, ...]:
    """The development's addresses and buildings the text names, each with its role. ``known`` places the addresses
    the building table does not cover (an end unit addressed on the cross street), by its parcel. ``parcels`` is every
    real street address; a number that is neither in it nor in a building's range is kept but marked as no parcel."""
    ranges = tuple(buildings)
    site = tuple(w.upper() for w in site_words)
    known = known or {}
    found: dict[str, Place] = {}

    def add(number: int, street: Street, start: int, unit: str = "") -> None:
        address = f"{number} {street.value}"
        if any(address.startswith(w) or w.startswith(address) for w in site):
            role = PlaceRole.SITE
        else:
            role = _role_near(text[max(0, start - 160): start])
        hit = assign_building(address, ranges)
        real = role is PlaceRole.SITE or hit is not None or address in known or parcels is None or address in parcels
        place = Place(address, hit.number if hit else known.get(address), role, f"#{unit}" if unit else "", real)
        old = found.get(address)
        # A job label anywhere wins over a bill-to elsewhere in the same document.
        if old is None or _rank(place.role) < _rank(old.role):
            found[address] = place

    for m in _ADDRESS.finditer(text or ""):
        street = _STREET_WORDS[m.group(3).upper()]
        low = int(m.group(1))
        high = int(m.group(2)) if m.group(2) else None
        if high is not None and not 0 < high - low <= 60:
            both_real = parcels is not None and {f"{low} {street.value}", f"{high} {street.value}"} <= set(parcels)
            if both_real and low < high:
                # "5607-5693 Whimsical Ln": the whole street, not its two end units.
                continue
            # "4119 - 3022 Enchanted": a project number, then the address.
            add(high, street, m.start(2), m.group(4) or "")
            continue
        add(low, street, m.start(), m.group(4) or "")
        if high is not None:
            add(high, street, m.start())
    for m in _ADDRESS_BACKWARDS.finditer(text or ""):
        add(int(m.group(2)), _STREET_WORDS[m.group(1).upper()], m.start())
    named = {p.building for p in found.values() if p.building}
    for m in _BUILDING.finditer(text or ""):
        b = Building(int(m.group(1)))
        if b not in named:
            found.setdefault(f"building {int(b)}", Place("", b, PlaceRole.MENTION))
    return tuple(found.values())


def _rank(role: PlaceRole) -> int:
    return (PlaceRole.JOB, PlaceRole.MENTION, PlaceRole.SITE, PlaceRole.BILLING).index(role)


def located(places: tuple[Place, ...]) -> tuple[Place, ...]:
    """The places that locate the work: the job sites and mentions (a named building among them), else the site. A
    bill-to or ship-to address never does: it is where the payer lives or the parts went, often a board member's home."""
    places = tuple(p for p in places if p.parcel)
    units = [p for p in places if p.role in (PlaceRole.JOB, PlaceRole.MENTION)]
    if units:
        return tuple(units)
    return tuple(p for p in places if p.role is PlaceRole.SITE)


# -- evidence --------------------------------------------------------------------------------------------------------


@dataclass
class Evidence:
    """One document read for events."""

    ref: str                                  # where it is: a path under data/, or "payhoa attachment 123"
    channel: str                              # "payhoa", "email", "drive", "library"
    title: str
    day: date | None
    vendor: str = ""
    amount_cents: int | None = None
    stage: Stage = Stage.OTHER
    work: Work = Work.NONE
    claimed: bool = False                     # the paperwork ties it to an insurance claim
    causes: tuple[Cause, ...] = ()
    elements: tuple[Element, ...] = ()
    places: tuple[Place, ...] = ()
    snippet: str = ""
    sha256: str = ""
    payment: dict | None = None               # {"key", "day", "amountCents", "payee", "memo"} when PayHOA paid it
    claim: str = ""                           # a claim number the text prints
    confidential: bool = False
    also: tuple[str, ...] = ()                # the same file's other copies
    excluded: str = ""                        # why the document is not repair paperwork, when its name or first page says so
    hint: str = ""                            # the vendor rule that set its work, when one did
    claim_status: str = ""                    # the carrier's status, from a loss run ("Closed With Pay")
    claim_paid_cents: int | None = None       # what the carrier paid on the claim, from a loss run

    @property
    def where(self) -> tuple[Place, ...]:
        return located(self.places)

    @property
    def unplaced(self) -> tuple[str, ...]:
        """Development-street numbers the text prints that are no parcel."""
        return tuple(p.address for p in self.places if not p.parcel)


_CLAIM = re.compile(r"claim\s*(?:no\.?|number|#)?\s*:?\s*([A-Z]{0,3}\d[\dA-Z]*(?:[-–]\d+)*)\b", re.I)


def claim_key(number: str) -> str:
    """One claim however its paperwork prints it: Farmers adds feature suffixes (5021000019-1, 5021000019-1-1) and USAA
    a line (030200001-002), so a long first group is the claim; a short one (1006-00-0001) is part of the number."""
    flat = re.sub(r"\s+", "", (number or "").upper()).replace("–", "-")
    head = flat.split("-", 1)[0]
    return head if len(head) >= 7 else flat


def _claim_in(words: str) -> str:
    for m in _CLAIM.finditer(words):
        number = re.sub(r"\s+", "", m.group(1)).replace("–", "-")
        if sum(ch.isdigit() for ch in number) >= 6:
            return number
    return ""


def snippet_of(text: str, patterns: Iterable[str], *, width: int = 180) -> str:
    """The scope line around the first match, without email addresses or phone numbers."""
    for pattern in patterns:
        m = re.search(pattern, text, re.I)
        if m:
            start = max(0, m.start() - width // 3)
            piece = " ".join(text[start: start + width].split())
            piece = _PHONE.sub("[phone]", _EMAIL.sub("[email]", piece))
            return piece
    first = " ".join(text[:width].split())
    return _PHONE.sub("[phone]", _EMAIL.sub("[email]", first))


def read_evidence(text: str, *, title: str, ref: str, channel: str, day: date | None, buildings: Iterable[BuildingRange],
                  site_words: Iterable[str] = (), vendor: str = "", amount_cents: int | None = None, extra: str = "",
                  sha256: str = "", payment: dict | None = None, confidential: bool = False,
                  known: Mapping[str, Building] | None = None, parcels: frozenset[str] | set[str] | None = None) -> Evidence:
    """One document's evidence. ``extra`` is text beside the document that describes it (an email subject, a payment memo)."""
    scope = scope_text(text)
    words = "\n".join(w for w in (title, extra, scope) if w)
    causes = causes_in(words)
    elements = elements_in(words)
    stage = stage_of(title, scope)
    places = places_in("\n".join(w for w in (extra, text or "") if w), buildings, site_words, known, parcels)
    patterns = [r.pattern for r in CAUSE_RULES if r.value in causes] + [r.pattern for r in ELEMENT_RULES if r.value in elements]
    # A claim file's name often carries the number alone ("ESTIMATE FOR REPAIRS 5021000019-1.pdf").
    named = re.search(r"\b(\d{9,10}(?:-\d{1,3})+)\b", title or "")
    # The document's own number first; an email subject can name another claim in the same thread.
    claim = _claim_in(scope) or _claim_in(title or "") or (named.group(1) if named else "") or _claim_in(extra or "")
    not_repair = NOT_REPAIR.search(f"{title}\n{(text or '')[:1500]}")
    return Evidence(ref, channel, title, day, vendor, amount_cents, stage, work_of(words, causes, stage),
                    claimed_in(words, stage) or bool(claim), causes, elements, places,
                    snippet_of(scope or words, patterns), sha256, payment, claim, confidential,
                    excluded=not_repair.group(0) if not_repair else "")


# -- loss runs -------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class LossRunClaim:
    """One claim on a carrier's loss run: the insurer's own record of a claim on the policy."""

    carrier: str
    policy: str
    number: str
    date_of_loss: date | None
    status: str                    # "Closed With Pay", "Closed Without Pay", "Open"
    claim_type: str                # "Commercial Property"
    cause: str                     # "Water Damage (Not Frozen Pipes)"
    location: str
    paid_cents: int | None
    expenses_cents: int | None
    net_cents: int | None
    valued: date | None            # the loss run's valuation date


LOSS_RUN = re.compile(r"Claim (?:Summary|Detail) Report|\bloss runs?\b", re.I)
_DETAIL = re.compile(r"Claim Number Date of Loss\s*\n\s*Claim Status\s*\n\s*Claim Type\s*\n\s*Loss Information\s*\n(.*?)(?=Loss Details|Page \d+ of \d+|\Z)", re.S)


def _money_after(label: str, text: str) -> int | None:
    m = re.search(label + r"\s*:?\s*\n?\s*\$?\s*([\d,]+\.\d\d)", text, re.I)
    return round(float(m.group(1).replace(",", "")) * 100) if m else None


def _us_date(value: str) -> date | None:
    m = re.match(r"\s*(\d{1,2})/(\d{1,2})/(\d{4})", value or "")
    try:
        return date(int(m.group(3)), int(m.group(1)), int(m.group(2))) if m else None
    except ValueError:
        return None


def read_loss_run(text: str) -> tuple[LossRunClaim, ...]:
    """Every claim a carrier's loss run details; empty when the text is not one or it lists no claim."""
    if not LOSS_RUN.search((text or "")[:600]):
        return ()
    carrier = _first_line_after(r"Company:", text)
    policy = _first_line_after(r"Policy #:", text)
    valued = _us_date(_first_line_after(r"Valuation Date:", text))
    out = []
    for m in _DETAIL.finditer(text):
        block = m.group(1)
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        if len(lines) < 4:
            continue
        number, dol, status, kind = lines[:4]
        location = re.search(r"Location of Loss:\s*\n\s*([^\n]+)", block)
        cause = re.search(r"Cause of Loss Description:\s*\n\s*([^\n]+)", block)
        out.append(LossRunClaim(carrier, policy, number, _us_date(dol), status, kind, cause.group(1).strip() if cause else "",
                                location.group(1).strip() if location else "", _money_after("Losses Paid", block),
                                _money_after("Expenses", block), _money_after("Net Incurred", block), valued))
    return tuple(out)


def _first_line_after(label: str, text: str) -> str:
    m = re.search(label + r"[ \t]*([^\n]*)\n?\s*([^\n]*)", text or "")
    if not m:
        return ""
    return (m.group(1).strip() or m.group(2).strip())


def loss_run_text(claim: LossRunClaim) -> str:
    """The claim as the words the evidence reader reads."""
    return (f"Loss run claim {claim.number}\nClaim Number: {claim.number}\nDate of Loss: {claim.date_of_loss}\n"
            f"Cause of loss: {claim.cause}\nLoss location: {claim.location}\nStatus: {claim.status}\nCarrier: {claim.carrier}")


# Counterparties whose paperwork is repair work: a vendor, and the city or a utility doing work. An insurer's, bank's,
# lawyer's, accountant's, title company's, or manager's document is evidence only as a claim.
TRADE_KINDS = frozenset({"vendor", "government agency", "utility"})


def is_repair_paperwork(ev: Evidence, *, trade: bool | None = None) -> bool:
    """Whether a read document is evidence of work or an event: it names a cause or an element; it is a proposal,
    contract, change order, invoice, report, claim, notice, or photo set, or it names a sudden cause; and a known
    counterparty that is not a trade counts only through a claim. ``trade`` is None when the counterparty is not known."""
    if ev.claimed and (ev.claim or ev.stage is Stage.CLAIM):
        return True
    if ev.work is Work.NONE or not (ev.causes or ev.elements):
        return False
    if trade is False or ev.excluded:
        return False
    return ev.stage is not Stage.OTHER or bool(set(ev.causes) & SUDDEN)


# -- events ----------------------------------------------------------------------------------------------------------


@dataclass
class Event:
    first: date | None
    last: date | None
    works: tuple[Work, ...]
    causes: tuple[Cause, ...]
    elements: tuple[Element, ...]
    places: tuple[Place, ...]
    evidence: list[Evidence] = field(default_factory=list)
    # The first document's places. Later documents join by these, so one invoice listing five addresses does not chain
    # five units' events into one.
    anchor: tuple[Place, ...] = ()

    @property
    def buildings(self) -> tuple[Building, ...]:
        return tuple(sorted({p.building for p in self.places if p.building}))

    @property
    def addresses(self) -> tuple[str, ...]:
        return tuple(sorted({p.address for p in self.places if p.address and p.role is not PlaceRole.SITE}))

    @property
    def community_wide(self) -> bool:
        return not self.addresses and not self.buildings

    @property
    def estimated_cents(self) -> int | None:
        quoted = [e.amount_cents for e in self.evidence if e.stage in (Stage.PROPOSAL, Stage.CONTRACT, Stage.CHANGE_ORDER) and e.amount_cents]
        return max(quoted) if quoted else None

    @property
    def paid_cents(self) -> int | None:
        paid = {e.payment["key"]: e.payment["amountCents"] for e in self.evidence if e.payment}
        return sum(paid.values()) if paid else None

    @property
    def invoiced_cents(self) -> int | None:
        billed = {(e.vendor, e.amount_cents) for e in self.evidence if e.stage is Stage.INVOICE and e.amount_cents and not e.payment}
        return sum(a for _, a in billed) if billed else None

    @property
    def claims(self) -> tuple[str, ...]:
        """The claims tied to the event, one per claim however its papers print the number."""
        return tuple(sorted({claim_key(e.claim) for e in self.evidence if e.claim}))

    @property
    def claim_outcomes(self) -> dict[str, dict]:
        """Each claim the carrier's loss run records: its status and what it paid."""
        return {e.claim: {"status": e.claim_status, "paidCents": e.claim_paid_cents, "carrier": e.vendor}
                for e in self.evidence if e.claim and e.claim_status}

    @property
    def claimed(self) -> bool:
        """An insurance claim is on file for the event: the line between upkeep and a covered loss is the insurer's."""
        return any(e.claimed for e in self.evidence)

    @property
    def sudden(self) -> bool:
        """The paperwork names a sudden cause (a leak, a break, a collision): a peril a claim could have been asked for."""
        found = set(self.causes) & SUDDEN
        # A pest vendor checking "for any possible water leaks" is not a water event.
        if found == {Cause.WATER_INTRUSION} and set(self.causes) & {Cause.RODENTS, Cause.INSECTS}:
            return False
        return bool(found)

    @property
    def cost_cents(self) -> int | None:
        """The most the paperwork puts on the event: the largest quote, the invoices, the payments, or a carrier's figure."""
        # The largest single figure, not a sum: a month of small repairs is not one loss. A claim's own estimates are parts
        # of one loss (the repair and the water mitigation), so their distinct amounts add.
        figures = [e.amount_cents for e in self.evidence if e.amount_cents]
        figures += [e.payment["amountCents"] for e in self.evidence if e.payment and e.payment.get("amountCents", 0) > 0]
        estimates = {e.amount_cents for e in self.evidence if e.claimed and e.claim and e.amount_cents and not e.claim_status
                     and e.stage in (Stage.PROPOSAL, Stage.CLAIM)}
        settled = [e.claim_paid_cents for e in self.evidence if e.claim_paid_cents]
        if len(estimates) > 1 and not settled:
            figures.append(sum(estimates))
        return max(figures) if figures else None

    def standing(self, deductible_cents: int | None) -> "ClaimStanding":
        """Where the event stands against the master policy: claimed, or a sudden cause whose cost reaches the deductible
        (a claim candidate), stays under it, or is unknown; else no claim question."""
        if self.claimed:
            return ClaimStanding.CLAIMED
        if not self.sudden:
            return ClaimStanding.NONE
        cost = self.cost_cents
        if cost is None or deductible_cents is None:
            return ClaimStanding.COST_UNKNOWN
        return ClaimStanding.CANDIDATE if cost >= deductible_cents else ClaimStanding.UNDER_DEDUCTIBLE

    @property
    def routine(self) -> bool:
        """Upkeep and inspections only, with no claim and no sudden cause."""
        return not self.claimed and not self.sudden and set(self.works) <= {Work.MAINTENANCE, Work.INSPECTION, Work.NONE}

    @property
    def vendors(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(e.vendor for e in self.evidence if e.vendor))


def _related(event: Event, ev: Evidence) -> bool:
    if ev.day and event.last and (ev.day - event.last).days > EVENT_WINDOW_DAYS:
        return False
    if ev.day and event.first and (event.first - ev.day).days > EVENT_WINDOW_DAYS:
        return False
    if any(e.sha256 and e.sha256 == ev.sha256 for e in event.evidence):
        return True
    if ev.payment and any(e.payment and e.payment["key"] == ev.payment["key"] for e in event.evidence):
        return True
    if ev.claim and claim_key(ev.claim) in event.claims:
        return True
    anchor = event.anchor or event.places
    mine = {p.address for p in ev.where if p.address and p.role is not PlaceRole.SITE}
    theirs = {p.address for p in anchor if p.address and p.role is not PlaceRole.SITE}
    # Two different claims are two events, unless they are the owner's and the association's claims on one loss: the
    # same unit and the same day of loss.
    if ev.claim and event.claims and claim_key(ev.claim) not in event.claims:
        if not (mine & theirs and ev.day and event.first and abs((ev.day - event.first).days) <= 3):
            return False
    # Routine upkeep joins a claim only through the claim's own unit: a year of pest invoices is not a liability claim.
    if event.claimed and not ev.claimed and ev.work is Work.MAINTENANCE and not (mine & theirs):
        return False
    if mine and theirs:
        if not mine & theirs:
            return False
        # One unit's paperwork within weeks of its event is that event: the police report, the contractor's proposal,
        # and the reimbursement notice share an address and dates, not always a word.
        if ev.day and event.last and abs((ev.day - event.last).days) <= SAME_UNIT_DAYS and (event.claimed or event.sudden):
            return True
        if ev.vendor and ev.vendor in event.vendors:
            return True
    else:
        mb = {p.building for p in ev.where if p.building}
        tb = {p.building for p in anchor if p.building}
        if not (bool(mb and tb and mb & tb) or (not mine and not theirs and not mb and not tb)):
            return False
    shared_cause = bool(set(ev.causes) & set(event.causes) - WEAK_CAUSES)
    shared_element = bool(set(ev.elements[:2]) & set(event.elements[:3]))
    if not (shared_cause or shared_element):
        return False
    # Another copy of a document already in the event (a signed copy, an emailed copy): the same amount, the same element.
    if ev.amount_cents and any(e.amount_cents == ev.amount_cents and e.stage is ev.stage for e in event.evidence):
        return True
    # Without a unit on both sides (a building named alone, or the whole community) documents join by cause or by the
    # same vendor, not by element alone: every tile job is on a roof. The event spans one window from its first document,
    # so a year of a vendor's line items is not one event.
    if not (mine and theirs):
        if ev.day and event.first and (ev.day - event.first).days > EVENT_WINDOW_DAYS:
            return False
        return shared_cause or bool(ev.vendor and ev.vendor in event.vendors and shared_element)
    return True


MULTI_SITE = 3


def split_sites(ev: Evidence) -> list[Evidence]:
    """A document naming more than ``MULTI_SITE`` units (a monthly invoice listing each repair's address) as one row per
    unit, so each unit's event stands alone; a document naming a few (two sides of one wall) stays whole."""
    units = [p for p in ev.where if p.address and p.role is not PlaceRole.SITE]
    if len(units) <= MULTI_SITE:
        return [ev]
    return [replace(ev, places=(p,)) for p in units]


def _add(target: Event, ev: Evidence) -> None:
    target.evidence.append(ev)
    target.first = min(d for d in (target.first, ev.day) if d)
    target.last = max(d for d in (target.last, ev.day) if d)
    target.works = tuple(w for w in Work if w in set(target.works) | {ev.work})
    target.causes = tuple(dict.fromkeys(target.causes + ev.causes))
    target.elements = tuple(dict.fromkeys(target.elements + ev.elements))
    have = {p.key for p in target.places}
    target.places = target.places + tuple(p for p in ev.where if p.key not in have)


def _units(rows: Iterable[Evidence]) -> set[str]:
    return {p.address for e in rows for p in e.where if p.address and p.role is not PlaceRole.SITE}


def claim_seeds(rows: list[Evidence]) -> list[list[Evidence]]:
    """The claim papers grouped before anything else: one group per claim number, and the groups for one loss merged
    (the same day of loss, within three days, at the same unit or at no unit): the owner's and the association's claims,
    and a loss run's number beside the carrier's letter number for the same claim."""
    groups: dict[str, list[Evidence]] = {}
    for ev in rows:
        if ev.claim:
            groups.setdefault(claim_key(ev.claim), []).append(ev)
    merged: list[list[Evidence]] = []
    for group in sorted(groups.values(), key=lambda g: min(e.day for e in g)):
        day = min(e.day for e in group)
        units = _units(group)
        # The same loss at the same unit, or a claim with no unit (a loss run's street-wide location) beside one with a unit.
        home = next((m for m in merged if abs((min(e.day for e in m) - day).days) <= 3
                     and ((units & _units(m)) or not units or not _units(m))), None)
        if home is None:
            merged.append(list(group))
        else:
            home.extend(group)
    return merged


def group_events(evidence: Iterable[Evidence]) -> list[Event]:
    """The evidence that is one event, oldest first. Evidence with no work and no claim, or no date, stays out. Claim
    papers are grouped first (``claim_seeds``), so a claim's estimate joins its claim though it arrives before its letter."""
    rows = sorted((part for e in evidence if (e.work is not Work.NONE or e.claimed) and e.day for part in split_sites(e)),
                  key=lambda e: (e.day, e.ref))
    events: list[Event] = []
    seeded: set[int] = set()
    for group in claim_seeds(rows):
        group.sort(key=lambda e: (e.day, e.ref))
        head = group[0]
        places = tuple({p.key: p for e in group for p in e.where}.values())
        event = Event(head.day, head.day, (head.work,), head.causes, head.elements, places, [head], places)
        for ev in group[1:]:
            _add(event, ev)
        events.append(event)
        seeded.update(id(e) for e in group)
    events.sort(key=lambda e: e.first)
    for ev in rows:
        if id(ev) in seeded:
            continue
        target = next((ev_ for ev_ in sorted(events, key=lambda e: e.last, reverse=True) if _related(ev_, ev)), None)
        if target is None:
            events.append(Event(ev.day, ev.day, (ev.work,), ev.causes, ev.elements, ev.where, [ev], ev.where))
            continue
        _add(target, ev)
    events.sort(key=lambda e: (e.first, e.last))
    return events


def cause_counts(events: Iterable[Event]) -> Counter:
    return Counter(c for e in events for c in e.causes[:1])


def within(event: Event, since: date | None) -> bool:
    return since is None or (event.last is not None and event.last >= since - timedelta(days=0))


__all__ = ["EVENT_WINDOW_DAYS", "Work", "ClaimStanding", "Cause", "Element", "Stage", "PlaceRole", "Rule", "CAUSE_RULES", "ELEMENT_RULES",
           "STAGE_RULES", "Place", "Evidence", "Event", "scope_text", "causes_in", "elements_in", "stage_of", "work_of",
           "claimed_in", "claim_key", "LossRunClaim", "read_loss_run", "loss_run_text", "places_in", "located", "read_evidence", "is_repair_paperwork", "TRADE_KINDS", "VendorWork",
           "apply_vendor_work", "group_events", "snippet_of", "cause_counts", "within", "SUDDEN"]
