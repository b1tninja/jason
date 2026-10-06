"""Who may make rules: the provisions of the governing documents that give the association, the board, a committee, or the
members the power to adopt, amend, or repeal rules, read from the words.

An operating rule is valid only if it is within the authority the law or the governing documents confer (Civil Code
4350(b)), so a rule is only as good as the grant behind it. This module finds the grants. For each one it records who
holds the power, the subjects it reaches, its limits and conditions, the procedure it names, and the recited words; then
it sets the grants beside the rules actually on file, subject by subject, so the board sees where authority exists and no
rule has been adopted, and where a rule exists and no authority was found. Both are findings for the board, never an
accusation.

Where it sits. ``docs/programs.md`` is the adoption catalog: an instrument adopted under authority. This module reads
the *authority* side for operating rules (the ``OPERATING_RULE`` instrument), and leaves the adoption act to that
catalog's ``AdoptionEvidence``. ``jason.community.deontic`` supplies the duty readings (modality, bearer, verb, object)
that find candidates, and ``jason.community.manual`` supplies the parts of an owner's manual that are rules.

Two readers, kept apart.

- **The rules** (``rule_reading``): the phrase grammar's duty readings and a few sentence patterns. It reads a candidate
  as a grant, a limit on a grant, or a reference to rules, names the holder from the bearer, the subjects from a word
  list, the conditions and the procedure from phrases. It is the default, and it needs no model.
- **The local model** (``RuleModel``, an option): shown a candidate's section with the sentence marked, it chooses among
  closed lists (grant, holder, subject, condition) and quotes the words that decide each. Free generation over-corrects
  (docs/ocr-correction.md), so it never writes a label it was not given, and a quote that is not in the section is
  dropped (``reference_model.find_quote``). Its answer is sampled again at a higher temperature for self-consistency.

**Agreement sets the tier.** Both readers read a grant with the same holder: ``LIKELY``. One reader alone: ``SUGGESTED``.
The readers disagree on whether it is a grant: ``CONFLICT``. Every row is a lead for a person (``ReviewStatus``).

Whether a subject needs the notice Civil Code 4360 requires is 4355(a)'s division. ``reach`` says which of its listed
subjects a subject falls under, as a labeled reading; for subjects that turn on where a rule applies it names both
readings and leaves the question for counsel. jason proposes; the board adopts.

Parts. A document may hold others (the rules inside an owner's manual). ``RulePart`` is one such part, built today from
the manual's classification (``parts_from_manual``). A grant found outside a rules part (in the manual's guidance) is a
finding. Where a document-segmentation reader exists, its parts replace ``parts_from_manual``; nothing else changes.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Callable, Iterable, Sequence
from urllib.parse import urlparse

from jason.community.deontic import (
    Bearer, DocumentDuty, DutyKind, _descends, find_bearer, read_outline, sentences,
)
from jason.community.document_segments import place_parts
from jason.community.outlines import DocumentOutline
from jason.community.reference_model import LOCAL_HOSTS, find_quote, passages


# ---------------------------------------------------------------------------------------------------------------------
# Closed lists


class Answer(Enum):
    """Whether a candidate sentence gives the power to make rules."""

    GRANT = "yes"             # the words give someone the power (or the duty) to adopt, amend, or repeal rules
    NO = "no"                 # the words mention rules but give no such power
    LIMITS = "limits"         # the words limit or condition how rules are made, without giving the power
    REFERS = "refers"         # the words refer to rules adopted elsewhere, or define the word Rules


class Holder(Enum):
    BOARD = "board"
    ASSOCIATION = "association"
    COMMITTEE = "committee"
    MEMBERS = "members"
    OFFICER = "officer"
    MANAGER = "manager"
    OTHER = "other"
    UNSTATED = "unstated"


class Subject(Enum):
    """What a rule may be about. Closed, so two readers can agree; a subject the list lacks is ``other: WORD``."""

    GENERAL = "general"                    # the use, occupancy, management, and operation of the development at large
    COMMON_AREA = "common_area"
    SEPARATE_INTEREST = "separate_interest"    # use of a unit, its porch, patio, or garage
    PARKING = "parking"
    VEHICLES = "vehicles"
    PETS = "pets"
    REGISTRATION = "registration"          # of vehicles, pets, or occupants
    LEASING = "leasing"
    ARCHITECTURE = "architecture"          # alterations, appearance, design review
    NOISE = "noise"
    TRASH = "trash"
    SIGNS = "signs"
    FINES = "fines"                        # monetary penalties
    DISCIPLINE = "discipline"              # hearings, sanctions, suspension of privileges
    ASSESSMENTS = "assessments"            # amounts, payment, collection, payment plans
    DISPUTES = "disputes"
    ELECTIONS = "elections"
    MEETINGS = "meetings"
    RECORDS = "records"
    INSURANCE = "insurance"                # coverage, deductibles, the owners' own insurance
    MAINTENANCE = "maintenance"            # of the common area or a unit
    OTHER = "other"


class Condition(Enum):
    """A limit or condition on the power, as the words state it."""

    CONSISTENT_WITH_DOCUMENTS = "consistent_with_documents"   # not in conflict with the declaration, bylaws, or articles
    CONSISTENT_WITH_LAW = "consistent_with_law"
    REASONABLE = "reasonable"
    NOTICE = "notice"                      # notice to the members before or after adopting
    MEMBER_VOTE = "member_vote"            # a member vote approves or reverses it
    BOARD_VOTE = "board_vote"              # a board vote, at a meeting
    IN_WRITING = "in_writing"
    UNIFORM = "uniform"                    # applies alike to all, or generally
    NECESSARY = "necessary"                # tied to a purpose or a need ("as the Board deems necessary")
    EMERGENCY = "emergency"                # an emergency rule change
    BOARD_APPROVAL = "board_approval"      # a committee's rules take effect only on the board's approval
    SUPPLEMENTS = "supplements"            # in addition to, not in place of, the document's own provisions
    DISCRETION = "discretion"              # the holder's own discretion


SUBJECT_WORDS = [s.value for s in Subject]
CONDITION_WORDS = [c.value for c in Condition]
HOLDER_WORDS = [h.value for h in Holder]
ANSWER_WORDS = [a.value for a in Answer]


class Tier(Enum):
    LIKELY = "likely"          # both readers read a grant, with the same holder
    SUGGESTED = "suggested"    # one reader alone
    CONFLICT = "conflict"      # the readers disagree on whether it is a grant


class Review(Enum):
    UNREVIEWED = "unreviewed"
    CONFIRMED = "confirmed"
    CORRECTED = "corrected"
    REJECTED = "rejected"


_BEARER_HOLDER = {
    Bearer.BOARD: Holder.BOARD, Bearer.ASSOCIATION: Holder.ASSOCIATION, Bearer.COMMITTEE: Holder.COMMITTEE,
    Bearer.MEMBER: Holder.MEMBERS, Bearer.OWNER: Holder.MEMBERS, Bearer.OFFICER: Holder.OFFICER,
    Bearer.MANAGER: Holder.MANAGER, Bearer.UNSTATED: Holder.UNSTATED,
}


def holder_of(bearer: Bearer) -> Holder:
    return _BEARER_HOLDER.get(bearer, Holder.OTHER)


# ---------------------------------------------------------------------------------------------------------------------
# Civil Code 4355(a): which subjects take notice under 4360


class Reach(Enum):
    LISTED = "listed"          # the subject falls under a subject 4355(a) lists
    DEPENDS = "depends"        # it turns on what the rule does: two readings remain, and counsel reads them
    NOT_LISTED = "not listed"  # none listed; 4355(b) may take the change out of 4360 and 4365 as well


@dataclass(frozen=True)
class Reading4355:
    reach: Reach
    cites: tuple[str, ...]
    note: str


_USE = "use of the common area or of an exclusive use common area (4355(a)(1))"
_SEP = "use of a separate interest (4355(a)(2))"

REACH: dict[Subject, Reading4355] = {
    Subject.COMMON_AREA: Reading4355(Reach.LISTED, ("4355(a)(1)",), "use of the common area"),
    Subject.SEPARATE_INTEREST: Reading4355(Reach.LISTED, ("4355(a)(2)",), "use of a separate interest"),
    Subject.ARCHITECTURE: Reading4355(Reach.LISTED, ("4355(a)(2)", "4355(a)(6)"),
                                      "aesthetic or architectural standards (a)(2), and the procedure for reviewing a physical change (a)(6)"),
    Subject.FINES: Reading4355(Reach.LISTED, ("4355(a)(3)",), "a schedule of monetary penalties"),
    Subject.DISCIPLINE: Reading4355(Reach.LISTED, ("4355(a)(3)",), "member discipline, and any procedure for the imposition of penalties"),
    Subject.DISPUTES: Reading4355(Reach.LISTED, ("4355(a)(5)",), "procedures adopted for resolution of disputes"),
    Subject.ELECTIONS: Reading4355(Reach.LISTED, ("4355(a)(7)",), "procedures for elections"),
    Subject.ASSESSMENTS: Reading4355(Reach.DEPENDS, ("4355(a)(4)", "4355(b)(3)"),
                                     "standards for delinquent assessment payment plans are listed (a)(4); a decision setting the amount of an "
                                     "assessment is not (b)(3)"),
    Subject.PARKING: Reading4355(Reach.DEPENDS, ("4355(a)(1)", "4355(a)(2)"),
                                 "listed if the rule governs the common area or an exclusive use common area (a)(1) or a separate interest "
                                 "(a)(2); a rule that does neither has no listed subject"),
    Subject.VEHICLES: Reading4355(Reach.DEPENDS, ("4355(a)(1)", "4355(a)(2)"),
                                  "listed if the rule governs the common area (a)(1) or a separate interest (a)(2)"),
    Subject.PETS: Reading4355(Reach.DEPENDS, ("4355(a)(1)", "4355(a)(2)"),
                              "listed as use of the common area (a)(1), or of a unit (a)(2), by the place the rule reaches"),
    Subject.NOISE: Reading4355(Reach.DEPENDS, ("4355(a)(1)", "4355(a)(2)"),
                               "listed as use of the common area or of a unit, by the place the rule reaches"),
    Subject.TRASH: Reading4355(Reach.DEPENDS, ("4355(a)(1)", "4355(a)(2)", "4355(b)(1)"),
                               "use of the common area or a unit is listed; a decision on maintenance of the common area is not (b)(1)"),
    Subject.SIGNS: Reading4355(Reach.DEPENDS, ("4355(a)(1)", "4355(a)(2)"),
                               "listed as use of the common area or of a unit (display from a unit), by the place the rule reaches"),
    Subject.REGISTRATION: Reading4355(Reach.DEPENDS, ("4355(a)(1)", "4355(a)(2)"),
                                      "listed when the registration is a condition of using the common area or a unit"),
    Subject.LEASING: Reading4355(Reach.DEPENDS, ("4355(a)(2)",),
                                 "one reading: leasing is use of a separate interest (a)(2); the other: a limit on leasing is a restraint on "
                                 "transfer, not a use, and no listed subject; counsel reads it"),
    Subject.INSURANCE: Reading4355(Reach.NOT_LISTED, (), "none of the listed subjects"),
    Subject.MAINTENANCE: Reading4355(Reach.NOT_LISTED, ("4355(b)(1)",), "a decision regarding maintenance of the common area is out of 4360 and 4365 (b)(1); a rule on how owners maintain a unit may be use of a separate interest"),
    Subject.MEETINGS: Reading4355(Reach.NOT_LISTED, (), "none of the listed subjects"),
    Subject.RECORDS: Reading4355(Reach.NOT_LISTED, (), "none of the listed subjects"),
    Subject.GENERAL: Reading4355(Reach.DEPENDS, ("4355(a)",), "a general power reaches listed subjects and others; each rule is read by its subject"),
    Subject.OTHER: Reading4355(Reach.DEPENDS, ("4355(a)",), "a subject the list lacks: read by what the rule does"),
}


def reach(subject: Subject) -> Reading4355:
    return REACH[subject]


# ---------------------------------------------------------------------------------------------------------------------
# Words: subjects, verbs, objects

_SUBJECT_PATTERNS: tuple[tuple[Subject, str], ...] = (
    (Subject.PARKING, r"\bpark(?:ing|ed|s)?\b|\bgarage\s+(?:door|space)s?\b|\bparking\s+(?:space|permit|spot)s?\b"),
    (Subject.VEHICLES, r"\bvehicles?\b|\btrucks?\b|\bmotorcycles?\b|\brecreational\s+vehicles?\b|\bbicycles?\b|\bboats?\b|\btrailers?\b|\bcars?\b"),
    (Subject.PETS, r"\bpets?\b|\banimals?\b|\bdogs?\b|\bcats?\b|\bleash"),
    (Subject.REGISTRATION, r"\bregist(?:er|ration|ered)\b"),
    (Subject.LEASING, r"\bleas(?:e|es|ed|ing)\b|\brent(?:al|als|ed|ing)?\b"),
    (Subject.ARCHITECTURE, r"\barchitect\w*|\balterations?\b|\bimprovements?\b|\baesthetic\w*|\bdesign\s+review\b|\bexterior\s+(?:paint|color|appearance)|"
                           r"\bdesign\s+(?:guidelines?|committee|standards|review)\b|\bpaint(?:ing)?\b|\bcolors?\b|\bapproval\s+of\s+(?:plans|improvements)|\bhome\s+improvement\b"),
    (Subject.NOISE, r"\bnois(?:e|es|y)\b|\bnuisances?\b|\bquiet\b|\bannoy\w*"),
    (Subject.TRASH, r"\btrash\b|\bgarbage\b|\brefuse\b|\brecycl\w+|\bwaste\s+(?:container|collection)|\bcontainers?\b"),
    (Subject.SIGNS, r"\bsigns?\b|\bsignage\b|\bflags?\b|\bbanners?\b|\bdisplay\s+of\b"),
    (Subject.FINES, r"\bfines?\b|\bmonetary\s+penalt\w+|\bschedule\s+of\s+(?:fines|penalt\w+)|\bpenalt(?:y|ies)\b"),
    (Subject.DISCIPLINE, r"\bdisciplin\w+|\bsanctions?\b|\bhearings?\b|\bsuspen(?:d|sion)\b|\bpenalt(?:y|ies)\b|\benforcement\s+(?:procedure|process|action)"),
    (Subject.ASSESSMENTS, r"\bassessments?\b|\bpayment\s+plans?\b|\bdelinquen\w+|\bcollection\s+of\b|\bdues\b"),
    (Subject.DISPUTES, r"\bdisputes?\b|\balternative\s+dispute\b|\binternal\s+dispute\b|\bmeet\s+and\s+confer\b"),
    (Subject.ELECTIONS, r"\belections?\b|\bballots?\b|\bnominat\w+|\bvoting\b|\bcandidates?\b|\binspectors?\s+of\s+election"),
    (Subject.MEETINGS, r"\bmeetings?\s+of\b|\bproxy\b|\bproxies\b|\bquorum\b"),
    (Subject.RECORDS, r"\binspection\s+of\s+(?:books|records)|\bmembership\s+list\b|\bassociation\s+records\b"),
    (Subject.INSURANCE, r"\binsurance\b|\bdeductibles?\b|\bcoverage\b"),
    (Subject.MAINTENANCE, r"\bmaintenance\b|\bmaintain(?:ed|ing)?\b|\brepairs?\b|\blandscap\w+"),
    (Subject.COMMON_AREA, r"\bcommon\s+(?:area|areas|property|elements)\b|\brecreational\s+facilit\w+|\bpools?\b|\bspa\b|\bclubhouse\b|\bfacilit(?:y|ies)\b"),
    (Subject.SEPARATE_INTEREST, r"\bunits?\b|\bseparate\s+interests?\b|\bporch(?:es)?\b|\bpatios?\b|\bbalcon(?:y|ies)\b|\bdecks?\b|\bwindows?\b|\bgarages?\b"),
    (Subject.GENERAL, r"\buse,\s+occupancy\b|\bmanagement\s+and\s+operation\b|\badministration,\s+management\b|\bmanagement,\s+(?:operation|administration)"),
)
_USE_COMMON = re.compile(r"\b(?:use|uses)\s+of\s+(?:the\s+|any\s+)?(?:common\s+(?:area|areas|property)|recreational\s+facilit\w+)", re.I)
_USE_UNIT = re.compile(r"\b(?:use|uses)\s+of\s+(?:a\s+|the\s+|any\s+|his\s+or\s+her\s+)?(?:unit|units|separate\s+interests?)\b", re.I)
_SUBJECT_RE = tuple((s, re.compile(p, re.I)) for s, p in _SUBJECT_PATTERNS)

# A subject word that only locates ("in the Common Area", "within a Unit") names the place a rule applies, not a subject of
# its own: it counts when no other subject is found.
_PLACE = {Subject.COMMON_AREA, Subject.SEPARATE_INTEREST}


def subjects_of(text: str) -> tuple[Subject, ...]:
    """The subjects a passage's words reach, in ``Subject`` order; a place (common area, a unit) alone only when no other
    subject is found. Empty when none."""
    found = [s for s, rx in _SUBJECT_RE if rx.search(text)]
    # "the use of the Common Area" and "the use of a Unit" are subjects 4355(a) names, not only places.
    for place, rx in ((Subject.COMMON_AREA, _USE_COMMON), (Subject.SEPARATE_INTEREST, _USE_UNIT)):
        if rx.search(text) and place not in found:
            found.append(place)
    topics = [s for s in found if s not in _PLACE]
    if topics:
        named = [s for s in found if s in _PLACE and ((s is Subject.COMMON_AREA and _USE_COMMON.search(text))
                                                      or (s is Subject.SEPARATE_INTEREST and _USE_UNIT.search(text)))]
        return tuple(topics + named)
    return tuple(found)


_VERB = re.compile(r"\b(?:(?:re)?adopt|(?:re)?adopts|(?:re)?adopted|(?:re)?adopting|make|makes|made|making|establish\w*|promulgat\w*|amend\w*|repeal\w*|"
                   r"modif\w*|publish\w*|enact\w*|prescrib\w*|formulat\w*|issu\w*|revis\w*|institut\w*|creat\w*|form|draft\w*|develop\w*|revers\w*|rescind\w*)\b", re.I)
_HEAD_VERB = re.compile(r"^(?:(?:re)?adopt|make|establish|promulgate|amend|repeal|modify|publish|enact|prescribe|formulate|issue|revise|"
                        r"institute|set\s+forth|create|form|draft|develop)\b", re.I)
_OBJECT = re.compile(r"\b(?P<obj>(?:(?:further|reasonable|such|additional|operating|association|written|new|any|all|the)\s+){0,3}"
                     r"(?:rules?(?:\s+and\s+regulations?)?|regulations?|polic(?:y|ies)|procedures?|guidelines?|standards?|"
                     r"schedules?\s+of\s+(?:\w+\s+)?(?:fines|penalties|fees)|(?:limitations?|restrictions?)(?=\s+(?:on|regarding|governing|upon)\b)))\b", re.I)
_STOPS = re.compile(r"insurance\s+polic(?:y|ies)|polic(?:y|ies)\s+of\s+(?:\w+\s+){0,4}insurance|"
                    r"parliamentary\s+procedures?|robert['’]?s\s+rules(?:\s+of\s+order)?|rules\s+of\s+order|"
                    r"policy\s+statement|rules\s+of\s+(?:evidence|court|procedure)", re.I)
_SELF = re.compile(r"\b(?:this|these|the\s+foregoing|the\s+following|those|such)\s+(?:rules?(?:\s+and\s+regulations?)?|polic(?:y|ies)|"
                   r"procedures?|regulations?)\b", re.I)
_REFER = (
    ("subject to the rules", re.compile(r"\bsubject\s+to\s+(?:any\s+|the\s+|such\s+|all\s+|applicable\s+)?(?:reasonable\s+|association\s+)?"
                                        r"(?:rules|regulations|guidelines)\b", re.I)),
    ("pursuant to rules", re.compile(r"\bpursuant\s+to\s+(?:any\s+|the\s+|such\s+|all\s+)?(?:\w+\s+)?(?:rules|regulations|policies|guidelines)\b", re.I)),
    ("as the board may adopt", re.compile(r"\bas\s+(?:the\s+)?(?:board|association)(?:\s+of\s+directors)?\s+may\s+(?:adopt|establish|promulgate|"
                                         r"prescribe|determine|provide|designate)\b", re.I)),
    ("in accordance with the rules", re.compile(r"\bin\s+accordance\s+with\s+(?:the\s+|any\s+|such\s+)?(?:\w+\s+)?(?:rules|regulations|policies|guidelines)\b", re.I)),
    ("authority for rules", re.compile(r"\bauthority\s+(?:for|to)\s+[^.]{0,80}\b(?:rules|regulations|policies|guidelines)\b", re.I)),
    ("adopted rules", re.compile(r"\b(?:duly\s+|properly\s+)?adopted\s+(?:\w+\s+)?(?:rules|regulations|policies|guidelines)\b|"
                                 r"\b(?:rules|regulations|policies|guidelines|schedule\s+of\s+(?:fines|penalties))\s+(?:duly\s+)?(?:adopted|established|"
                                 r"promulgated|issued)\s+by\b", re.I)),
)
_APPLIES = re.compile(r"\b(?:only\s+)?apply\s+to\s+(?:a|an|any|the)\s+(?:\w+\s+){0,2}rules?\b|\bnot\s+apply\s+to\s+(?:a|an|any|the)\s+"
                      r"(?:\w+\s+){0,2}rules?\b|\bnot\s+apply\s+to\s+(?:a|an|any|the)\s+(?:\w+\s+){0,2}rule\s+changes?\b", re.I)
# A standard left to the board without the word "rule": "a reasonable number, as determined by the Board", "a time limit
# shall be established by the Board". Collected only when the sentence is about a standard, so "an excuse approved by the
# Board" is not.
_DELEGATE = re.compile(r"\b(?:determined|established|prescribed|specified|designated|fixed|set)\s+by\s+(?:the\s+)?(?:board|association)\b|"
                       r"\bas\s+the\s+board(?:\s+of\s+directors)?\s+(?:may\s+)?(?:deem|determine|prescribe|establish|specify|require)\w*\b|"
                       r"\bsuch\s+(?:\w+\s+)?(?:conditions|terms|requirements|limits?)\s+as\s+the\s+board\b", re.I)
_STANDARD = re.compile(r"\b(?:limits?|numbers?|standards?|requirements?|conditions|schedules?|methods?|hours|periods?|sizes?|amounts?|"
                       r"maximum|minimum)\b", re.I)
_SCOPE = re.compile(r"\b(?:the\s+)?rules?\s+(?:may|shall)\s+(?:concern|include|cover|address|relate\s+to|pertain\s+to)\b", re.I)
_DEFINITION = re.compile(r"[“\"](?P<term>[^”\"]{0,60}\b(?:rules?|regulations|guidelines|standards|polic(?:y|ies))\b[^”\"]{0,40})[”\"]\s*"
                         r"(?:shall\s+)?(?:mean|means|refer|refers|include|includes)\b", re.I)
_MODAL_GRANT = re.compile(r"\b(?:may|shall\s+have\s+(?:the\s+)?(?:\w+\s+)?(?:power|authority|right)|has\s+the\s+(?:power|authority|right)|"
                          r"have\s+the\s+(?:power|authority|right)|is\s+(?:hereby\s+)?(?:authorized|empowered)|are\s+(?:hereby\s+)?(?:authorized|empowered)|"
                          r"shall\s+(?:adopt|establish|promulgate|make|publish)|shall\s+be\s+(?:authorized|empowered)|can)\b", re.I)
_LIMIT = (
    ("reverse", re.compile(r"\brevers(?:e|ed|al)\b|\brescind\w*", re.I)),
    ("notice before", re.compile(r"\bnotice\b[^.;]{0,100}\b(?:before|prior\s+to)\s+(?:adopt|the\s+adoption|the\s+effective)", re.I)),
    ("conflict", re.compile(r"\bnot\s+(?:be\s+)?(?:in\s+)?(?:conflict|inconsistent)\b|\bshall\s+not\s+conflict\b|\bmay\s+not\s+(?:conflict|contradict)\b", re.I)),
    ("rule change", re.compile(r"\brule\s+changes?\b", re.I)),
    ("procedure", re.compile(r"\bprocedures?\s+for\s+(?:the\s+)?(?:adoption|modification|amendment)", re.I)),
)

_CONDITION_PATTERNS: tuple[tuple[Condition, str], ...] = (
    (Condition.CONSISTENT_WITH_DOCUMENTS, r"\b(?:not\s+(?:be\s+)?(?:in\s+)?conflict(?:ing)?\s+with|consistent\s+with|in\s+conformity\s+with|"
                                          r"in\s+accordance\s+with)\s+(?:the\s+|this\s+|any\s+|these\s+)?(?:\w+\s+){0,2}(?:declaration|bylaws|articles|"
                                          r"governing\s+documents|section|article)\b[^,;.]{0,30}"),
    (Condition.CONSISTENT_WITH_LAW, r"\b(?:consistent\s+with|in\s+accordance\s+with|not\s+(?:in\s+)?conflict\s+with|in\s+compliance\s+with|"
                                    r"subject\s+to)\s+(?:applicable\s+|all\s+)?(?:laws?|statutes?|law)\b[^,;.]{0,30}"),
    (Condition.REASONABLE, r"\breasonabl[ey]\b(?:\s+\w+){0,4}"),
    (Condition.NOTICE, r"\b(?:written\s+)?notice\b[^.;]{0,120}\b(?:members?|owners?)\b[^.;]{0,60}|\bnotice\b[^.;]{0,100}\b(?:at\s+least|not\s+less\s+than)\s+\w+\s*(?:\(\d+\)\s*)?days\b[^.;]{0,50}|\b(?:at\s+least|not\s+less\s+than)\s+(?:\w+\s*)?"
                       r"(?:\(\d+\)\s*)?days['’]?\s+(?:prior\s+|written\s+)?notice\b[^.;]{0,60}|\bdelivered\s+to\s+the\s+members[^.;]{0,60}"),
    (Condition.MEMBER_VOTE, r"\b(?:affirmative\s+)?vote\s+of\s+(?:at\s+least\s+|a\s+majority\s+of\s+|two[- ]thirds\s+of\s+)?(?:the\s+)?"
                            r"(?:members|total\s+voting\s+power|owners)[^.;]{0,50}|\bapproved\s+by\s+(?:the\s+)?(?:vote\s+of\s+the\s+)?members[^.;]{0,50}"),
    (Condition.BOARD_VOTE, r"\b(?:vote\s+of\s+(?:the\s+)?(?:board|directors)|at\s+a\s+(?:duly\s+(?:called|held)\s+)?(?:regular\s+or\s+special\s+)?"
                           r"(?:meeting\s+of\s+the\s+)?board\s+meeting|majority\s+of\s+the\s+(?:board|directors)|open\s+(?:board\s+)?meeting)[^.;]{0,50}"),
    (Condition.IN_WRITING, r"\bin\s+writing\b[^.;]{0,30}|\bwritten\s+(?:rules|policy|policies)\b"),
    (Condition.UNIFORM, r"\bapplies?\s+(?:generally|uniformly|equally|alike)\b[^.;]{0,40}|\buniform(?:ly)?\b[^.;]{0,40}|\bnondiscriminat\w+[^.;]{0,30}"),
    (Condition.NECESSARY, r"\bas\s+the\s+(?:board|association)(?:\s+of\s+directors)?\s+(?:deems|determines|shall\s+deem)\s+(?:\w+\s+){0,3}"
                          r"(?:necessary|appropriate|advisable|proper|desirable)\b[^,;.]{0,60}|\b(?:necessary|appropriate)\s+(?:for|to)\s+the\s+"
                          r"(?:management|operation|administration|enforcement)[^,;.]{0,60}"),
    (Condition.EMERGENCY, r"\bemergency\b[^.;]{0,80}"),
    (Condition.BOARD_APPROVAL, r"\b(?:when|if|once|upon)\s+(?:approved|adopted)(?:\s+and\s+adopted)?\s+by\s+the\s+board\b[^,;.]{0,40}|"
                               r"\bsubject\s+to\s+(?:the\s+)?(?:approval|ratification)\s+of\s+the\s+board\b"),
    (Condition.SUPPLEMENTS, r"\bin\s+addition\s+to\s+(?:the\s+)?(?:provisions|restrictions|requirements)[^,;.]{0,60}|\bfurther\s+(?:define|elaborate|refine)\b[^,;.]{0,60}"),
    (Condition.DISCRETION, r"\bin\s+its\s+(?:sole\s+|absolute\s+|complete\s+)?discretion\b|\bsole\s+discretion\b|\bcomplete\s+discretion\b|\bhas\s+the\s+discretion\b"),
)
_CONDITION_RE = tuple((c, re.compile(p, re.I)) for c, p in _CONDITION_PATTERNS)

_PROCEDURE = re.compile(
    r"\b(?:in\s+accordance\s+with|pursuant\s+to|as\s+provided\s+in|as\s+set\s+forth\s+in|under)\s+(?:the\s+)?(?:procedures?|section|article)\s+[^,;.]{0,70}|"
    r"\bprocedures?\s+for\s+the\s+(?:adoption|modification|amendment)\s+[^,;.]{0,90}|"
    r"\b(?:at\s+least|not\s+less\s+than)\s+(?:\w+\s*)?(?:\(\d+\)\s*)?days\s+(?:before|prior\s+to|after)\s+[^,;.]{0,60}|"
    r"\bwithin\s+(?:\w+\s*)?(?:\(\d+\)\s*)?days\s+after\s+[^,;.]{0,60}|"
    r"\bdeliver\w*\s+(?:to\s+the\s+)?members[^,;.]{0,70}", re.I)
_CITES = re.compile(r"\bSection\s+\d+(?:\.\d+)*(?:\([a-z0-9]{1,4}\))*", re.I)


# ---------------------------------------------------------------------------------------------------------------------
# Records


def _cond_dict(c: Any) -> dict[str, Any]:
    return {"kind": c.kind.value, "quote": c.quote, **({"elsewhere": True} if c.elsewhere else {})}


def _clean(text: str) -> str:
    return " ".join(text.split())


@dataclass(frozen=True)
class Candidate:
    """A sentence that may grant rule-making power, with why it was collected and the section it sits in."""

    source: str
    section: str
    title: str
    start: int                       # offsets of the sentence in the outline's text
    end: int
    text: str                        # the sentence
    context: str                     # the section's words, for the model
    reasons: tuple[str, ...]
    duties: tuple[str, ...] = ()     # ids of the duty readings in the sentence
    part: str = ""                   # the part of the document it sits in ("rules", "guidance", ...), when parts are known
    items: tuple[str, ...] = ()      # the list a lead-in opens ("the following subjects:"), item by item
    part_source: str = ""            # where the part comes from: "segments" or "classification" ("" when no parts are known)
    part_contested: str = ""         # the other reading's kind for the part, where the two disagree it is a rule

    @property
    def id(self) -> str:
        digest = hashlib.sha1(f"{self.source}|{self.section}|{_clean(self.text).lower()}".encode("utf-8")).hexdigest()[:10]
        return f"{self.source}#{self.section}:{digest}"


@dataclass(frozen=True)
class QuotedCondition:
    kind: Condition
    quote: str
    elsewhere: bool = False          # the words are in the section, not in the sentence the row recites


@dataclass(frozen=True)
class Reading:
    """One reader's answer for one candidate. Every quote in it is words of the candidate's section."""

    reader: str                      # "rules" or "model"
    answer: Answer
    holder: Holder = Holder.UNSTATED
    subjects: tuple[Subject, ...] = ()
    other_subjects: tuple[str, ...] = ()
    conditions: tuple[QuotedCondition, ...] = ()
    procedure: str = ""
    words: str = ""                  # the operative words, verbatim
    consistency: float | None = None  # the share of extra samples that agree on the answer and holder (the model)
    dropped: tuple[str, ...] = ()    # quotes dropped because they are not verbatim

    def to_dict(self) -> dict[str, Any]:
        return {"reader": self.reader, "answer": self.answer.value, "holder": self.holder.value,
                "subjects": [s.value for s in self.subjects], "otherSubjects": list(self.other_subjects),
                "conditions": [_cond_dict(c) for c in self.conditions],
                "procedure": self.procedure, "words": self.words, "consistency": self.consistency,
                "dropped": list(self.dropped)}

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Reading:
        return cls(reader=raw["reader"], answer=Answer(raw["answer"]), holder=Holder(raw.get("holder", "unstated")),
                   subjects=tuple(Subject(s) for s in raw.get("subjects") or ()),
                   other_subjects=tuple(raw.get("otherSubjects") or ()),
                   conditions=tuple(QuotedCondition(Condition(c["kind"]), c["quote"], bool(c.get("elsewhere"))) for c in raw.get("conditions") or ()),
                   procedure=raw.get("procedure", ""), words=raw.get("words", ""), consistency=raw.get("consistency"),
                   dropped=tuple(raw.get("dropped") or ()))


@dataclass(frozen=True)
class RuleAuthority:
    """A provision that may give the power to make rules, as the readers read it: for a person to review."""

    id: str
    source: str
    section: str
    title: str
    answer: Answer
    holder: Holder
    subjects: tuple[Subject, ...]
    other_subjects: tuple[str, ...]
    conditions: tuple[QuotedCondition, ...]
    procedure: str
    words: str                       # recited: the operative words when verbatim, else the sentence
    sentence: str
    tier: Tier
    readers: tuple[str, ...]
    consistency: float | None = None
    related: tuple[str, ...] = ()    # ids of the limits and references that bear on it
    part: str = ""
    review: Review = Review.UNREVIEWED
    note: str = ""
    part_source: str = ""            # where the part came from: "segments" (a stored segmentation) or "classification"
    part_contested: str = ""         # the other reading's kind for the part, where the two disagree it is a rule

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "source": self.source, "section": self.section, "title": self.title,
                "answer": self.answer.value, "holder": self.holder.value, "subjects": [s.value for s in self.subjects],
                "otherSubjects": list(self.other_subjects),
                "conditions": [_cond_dict(c) for c in self.conditions],
                "procedure": self.procedure, "words": self.words, "sentence": self.sentence, "tier": self.tier.value,
                "readers": list(self.readers), "consistency": self.consistency, "related": list(self.related),
                "part": self.part, "partSource": self.part_source, "partContested": self.part_contested, "review": self.review.value, "note": self.note}

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> RuleAuthority:
        return cls(id=raw["id"], source=raw["source"], section=raw["section"], title=raw.get("title", ""),
                   answer=Answer(raw["answer"]), holder=Holder(raw["holder"]),
                   subjects=tuple(Subject(s) for s in raw.get("subjects") or ()),
                   other_subjects=tuple(raw.get("otherSubjects") or ()),
                   conditions=tuple(QuotedCondition(Condition(c["kind"]), c["quote"], bool(c.get("elsewhere"))) for c in raw.get("conditions") or ()),
                   procedure=raw.get("procedure", ""), words=raw.get("words", ""), sentence=raw.get("sentence", ""),
                   tier=Tier(raw["tier"]), readers=tuple(raw.get("readers") or ()), consistency=raw.get("consistency"),
                   related=tuple(raw.get("related") or ()), part=raw.get("part", ""),
                   review=Review(raw.get("review", "unreviewed")), note=raw.get("note", ""),
                   part_source=raw.get("partSource", ""), part_contested=raw.get("partContested", ""))


# ---------------------------------------------------------------------------------------------------------------------
# Parts


@dataclass(frozen=True)
class RulePart:
    """A part of a document with its own standing: the rules in an owner's manual, its guidance, a policy bound in.
    ``kind`` is "rule", "policy", "copy", or "guidance"; offsets are into the outline's text."""

    source: str
    start: int
    end: int
    kind: str
    book: str = ""
    label: str = ""
    origin: str = "classification"   # where the part comes from: "classification" (the manual's rows) or "segments"
    contested: str = ""              # the other reading's kind, where the two disagree whether it is a rule (``merge_parts``)


def parts_from_manual(source: str, classification: Any) -> list[RulePart]:
    """The parts of a manual-type document from ``jason.community.manual.classify``: each segment with its kind.
    A stored segmentation's parts are ``parts_from_segments``."""
    out = []
    for seg in getattr(classification, "segments", ()) or ():
        if seg.end <= seg.start:
            continue
        out.append(RulePart(source, seg.start, seg.end, seg.kind.value, seg.target.book, seg.old))
    return out


SEGMENT_KINDS = {"rules": "rule", "policy": "policy", "procedure": "policy"}
RULE_PART_KINDS = ("rule", "policy")
FRAME_KINDS = ("cover", "contents")      # a segment part that frames a document and never overrides a finer reading of the text


def parts_from_segments(source: str, parts: Iterable[Any], text: str, *, exhibits: Iterable[Any] = (),
                        page_count: int = 0) -> list[RulePart]:
    """The parts of a document from a stored segmentation (``document_segments``): each part is found in ``text`` (the
    outline's) by its heading (``place_parts``: in page order, each part ending where the next begins, a heading printed
    again later being a running header and not another part, a cover or contents part only its few pages: ``page_count``)
    and kept with its kind (a rules part is "rule", a policy or procedure
    "policy", anything else its own word: "guidance", "form", "cover"), and each exhibit, from its heading to the next
    exhibit or part, as "exhibit": a grant stated in an exhibit counts as the exhibit's and a rule there is not a rule on
    file. A part whose heading is not in ``text`` is left out, never placed by guess. Each part's ``origin`` is "segments".
    ``merge_parts`` sets them beside the manual classification's."""
    heads = [f"{e.label} {e.title}".strip() for e in exhibits if getattr(e, "label", "")]
    found: list[RulePart] = []
    roots = [p for p in parts if not (getattr(p, "segment", "") and p.segment.count(".") > 0)]   # a part in an exhibit is the exhibit's
    spans = place_parts(roots, text, heads, page_count)
    for part in roots:
        span = spans.get(part.key)
        if span is None or span[1] <= span[0]:
            continue
        found.append(RulePart(source, span[0], span[1], SEGMENT_KINDS.get(part.kind.value, part.kind.value), part.book,
                              part.title, "segments"))
    found.sort(key=lambda p: p.start)
    trimmed: list[RulePart] = []
    for k, p in enumerate(found):
        later = [q.start for q in found[k + 1:] if q.start > p.start]
        trimmed.append(replace(p, end=min([p.end, *later])))
    found = trimmed
    marks = []
    for e in exhibits:
        if not getattr(e, "label", ""):
            continue
        at = _find_heading(text, f"{e.label} {e.title}".strip())
        if at is not None:
            marks.append((at, e))
    marks.sort(key=lambda m: m[0])
    for k, (at, e) in enumerate(marks):
        later = [p.start for p in found if p.start > at] + [m[0] for m in marks[k + 1:]] + [len(text)]
        found.append(RulePart(source, at, min(later), "exhibit", "", e.label, "segments"))
    return sorted(found, key=lambda p: p.start)


def merge_parts(segmented: Sequence[RulePart], classified: Sequence[RulePart], text: str) -> list[RulePart]:
    """One document's parts from both readings, the stored segmentation's and the manual classification's.

    - Text only one of them covers keeps that reading's part.
    - Where both cover it and agree on the kind (a rule part, a policy part), or both read it as something that is not
      a rule or a policy (guidance, a copy, an exhibit, a form), the segmentation's part is kept: it is the preferred
      reading, so the part says "segments".
    - Where they **disagree** (one reads a rule where the other reads a policy, or reads a rule where the other reads
      guidance), the classification's part is kept and the segmentation's kind is written on it
      (``RulePart.contested``). A reading that would count a stretch as rules the other does not is a question for a
      person, never a way to enlarge the rules on file; the counts of a document the classification covers do not change.
    A stretch with no letter or digit (the line break between two parts) goes with the part before it."""
    cuts = sorted({0, len(text), *(p.start for p in [*segmented, *classified]), *(p.end for p in [*segmented, *classified])})
    pieces: list[RulePart] = []
    made: list[tuple[int, str]] = []       # which parts each piece was cut from: only a part's own pieces rejoin
    for a, b in zip(cuts, cuts[1:]):
        if b <= a:
            continue
        s = next((p for p in segmented if p.start <= a and b <= p.end), None)
        c = next((p for p in classified if p.start <= a and b <= p.end), None)
        if s is None and c is None:
            continue
        if s is not None and c is not None:
            both_rule, neither = s.kind in RULE_PART_KINDS and c.kind in RULE_PART_KINDS, \
                s.kind not in RULE_PART_KINDS and c.kind not in RULE_PART_KINDS
            if s.kind == c.kind:
                chosen = s
            elif s.kind in FRAME_KINDS or both_rule:
                chosen = c             # a cover or contents page is no finer than the classification; a rule and a policy differ in kind only
            elif neither:
                chosen = s
            else:
                chosen = replace(c, contested=s.kind)
        else:
            chosen = s or c
        token = (id(s) if chosen is s else id(c), chosen.contested)
        if pieces and pieces[-1].end == a and made[-1] == token:
            pieces[-1] = replace(pieces[-1], end=b)
        elif pieces and pieces[-1].end == a and not any(ch.isalnum() for ch in text[a:b]):
            pieces[-1] = replace(pieces[-1], end=b)
        else:
            pieces.append(replace(chosen, start=a, end=b))
            made.append(token)
    return pieces


def _find_heading(text: str, heading: str) -> int | None:
    """Where a heading begins a line of ``text`` (an exhibit's label and title): a mention in a sentence is not it."""
    folded = re.sub(r"[^a-z0-9]+", "", heading.lower())
    if len(folded) < 4:
        return None
    found = re.search(r"(?m)^[ \t#*]*" + r"[\W_]*".join(re.escape(c) for c in folded), text, re.I)
    return found.start() if found else None


def part_at(parts: Sequence[RulePart], source: str, start: int) -> RulePart | None:
    inside = [p for p in parts if p.source == source and p.start <= start < p.end]
    return min(inside, key=lambda p: p.end - p.start) if inside else None


# ---------------------------------------------------------------------------------------------------------------------
# Candidates


def _object_spans(text: str) -> list[tuple[int, int]]:
    """Where the rule-type nouns are in ``text``, with insurance policies, parliamentary procedure, and the like left out."""
    blocked = [(m.start(), m.end()) for m in _STOPS.finditer(text)]
    return [(m.start(), m.end()) for m in _OBJECT.finditer(text) if not any(a <= m.start() < b for a, b in blocked)]


def _verb_object(text: str) -> tuple[bool, bool]:
    """(an adoption verb sits within 90 characters of a rule-type noun, and that noun is not only a self-reference)."""
    objects = _object_spans(text)
    verbs = [(m.start(), m.end()) for m in _VERB.finditer(text)]
    pairs = [(v, o) for v in verbs for o in objects if -90 <= o[0] - v[1] <= 90 or -90 <= v[0] - o[1] <= 90]
    if not pairs:
        return False, False
    selfish = [_SELF.search(text[max(0, o[0] - 20):o[1]]) is not None for _, o in pairs]
    return True, not all(selfish)


def reasons_for(sentence: str) -> tuple[str, ...]:
    """Why a sentence is a candidate: the patterns it matches. Empty when it is none."""
    found: list[str] = []
    if _object_spans(sentence):
        has_pair, _ = _verb_object(sentence)
        if has_pair:
            found.append("verb+object")
        for name, rx in _REFER:
            if rx.search(sentence):
                found.append("refers: " + name)
    if _DEFINITION.search(sentence):
        found.append("definition")
    if _DELEGATE.search(sentence) and _STANDARD.search(sentence):
        found.append("delegation")
    if _SCOPE.search(sentence):
        found.append("scope")
    if _APPLIES.search(sentence):
        found.append("applicability")
    return tuple(dict.fromkeys(found))


def candidates(outline: DocumentOutline, duties: Iterable[DocumentDuty] | None = None, *, parts: Sequence[RulePart] = (),
               window: int = 1600) -> list[Candidate]:
    """Every sentence of ``outline`` that may grant, limit, or refer to rule-making power, found by rule: the duty
    readings (modality, bearer, verb, object) and the sentence patterns. ``duties`` default to the grammar's readings."""
    readings = list(duties) if duties is not None else read_outline(outline)
    by_sentence: dict[tuple[str, int], list[DocumentDuty]] = {}
    for d in readings:
        by_sentence.setdefault((d.section, d.start), []).append(d)
    out: list[Candidate] = []
    rows = passages(outline, max_chars=1_000_000, min_chars=1)
    for k, p in enumerate(rows):
        for s, e in sentences(p.text):
            sent = p.text[s:e]
            if p.title and _clean(sent) == _clean(p.title) and len(p.text) > e + 1:
                continue                                  # the section's own heading, with words after it
            why = list(reasons_for(sent))
            mine = by_sentence.get((p.section, p.start + s), [])
            for d in mine:
                if d.kind in (DutyKind.PERMISSION, DutyKind.RIGHT, DutyKind.DUTY) and _is_adoption(d):
                    why.append(f"duty: {d.kind.value} of {d.bearer.value}")
            if not why:
                continue
            at = p.text.find(sent)
            lo = max(0, at - window // 2)
            context = p.text[lo:at] + "[[" + sent + "]]" + p.text[at + len(sent):at + len(sent) + window // 2]
            part = part_at(parts, outline.key, p.start + s)
            items: tuple[str, ...] = ()
            if p.section and (sent.rstrip().endswith(":") or not re.search(r"[.!?\"”)]$", sent.rstrip())):
                items = tuple(_clean(q.text) for q in rows[k + 1:] if _descends(q.section, p.section))[:12]
                if items:
                    context += "\nThe list that follows:\n" + "\n".join("- " + i[:200] for i in items)
            out.append(Candidate(outline.key, p.section, p.title, p.start + s, p.start + e, sent, context,
                                 tuple(dict.fromkeys(why)), tuple(d.id for d in mine), part.kind if part else "", items,
                                 part.origin if part else "", part.contested if part else ""))
    return out


def _head(action: str) -> str:
    """The first verb of a duty's action, after a leading "have the power to" or "be authorized to"."""
    a = _clean(action)
    a = re.sub(r"^(?:have|has)\s+(?:the\s+)?(?:\w+\s+){0,2}?(?:power|authority|right|discretion)(?:\s+and\s+(?:the\s+)?(?:power|authority))?\s+to\s+", "", a, flags=re.I)
    a = re.sub(r"^be\s+(?:hereby\s+)?(?:authorized|empowered|permitted)\s+to\s+", "", a, flags=re.I)
    a = re.sub(r"^(?:decide|elect|choose|determine|resolve)\s+to\s+", "", a, flags=re.I)
    a = re.sub(r"^(?:also|further|then|hereafter|from\s+time\s+to\s+time)\s+", "", a, flags=re.I)
    return a


def _is_adoption(d: DocumentDuty) -> bool:
    head = _head(d.action)
    if not _HEAD_VERB.match(head):
        return False
    objects = _object_spans(head[:200])
    return bool(objects)


# ---------------------------------------------------------------------------------------------------------------------
# The rules' reading


def _conditions(text: str) -> tuple[QuotedCondition, ...]:
    out = []
    for kind, rx in _CONDITION_RE:
        m = rx.search(text)
        if m:
            out.append(QuotedCondition(kind, _clean(m.group(0)).strip(" ,;.")))
    return tuple(out)


def _procedure(text: str) -> str:
    m = _PROCEDURE.search(text)
    return _clean(m.group(0)).strip(" ,;.") if m else ""


def rule_reading(c: Candidate, duties: Sequence[DocumentDuty] = ()) -> Reading:
    """The rules' reading of one candidate: a grant when a power or a duty whose head verb is adopt, make, establish,
    promulgate, amend, or the like has a rule-type noun for its object; a limit when the sentence conditions how rules
    are made without giving the power; a reference when it only names rules adopted elsewhere, defines the word, or lists
    what the Rules may concern."""
    text = c.text
    mine = [d for d in duties if d.id in c.duties] if duties and c.duties else []
    grants = [d for d in mine if d.kind in (DutyKind.PERMISSION, DutyKind.RIGHT, DutyKind.DUTY) and _is_adoption(d)]
    has_pair, not_self = _verb_object(text)
    holder = Holder.UNSTATED
    answer = Answer.NO
    if grants:
        g = grants[0]
        answer, holder = Answer.GRANT, holder_of(g.bearer)
        if holder is Holder.UNSTATED:
            holder = holder_of(find_bearer(text[:max(0, g.marker_at - g.start)])[0])
    else:
        modal = _MODAL_GRANT.search(text) if has_pair else None
        subj = find_bearer(text[:modal.start()]) if modal else (Bearer.UNSTATED, "")
        head = _head(text[modal.end():]) if modal else ""
        if modal and subj[0] is not Bearer.UNSTATED and _HEAD_VERB.match(head) and _object_spans(head[:200]) \
                and not re.search(r"\bnot\s*$", text[:modal.start()], re.I):
            answer, holder = Answer.GRANT, holder_of(subj[0])
        elif "applicability" in c.reasons or (has_pair and not_self and any(rx.search(text) for _, rx in _LIMIT)):
            answer = Answer.LIMITS
        elif any(r in ("definition", "scope", "delegation") or r.startswith("refers") for r in c.reasons) or (has_pair and not_self and _adopted_by(text)):
            answer = Answer.REFERS
            by = _adopted_by(text)
            holder = holder_of(find_bearer(by)[0]) if by else Holder.UNSTATED
        elif _object_spans(text) and not _SELF.search(text) and any(rx.search(text) for _, rx in _LIMIT):
            answer = Answer.LIMITS
    live = answer is not Answer.NO
    return Reading("rules", answer, holder, subjects_of(text + " " + " ".join(c.items)) if live else (), (), _conditions(text) if live else (),
                   _procedure(text) if live else "", _clean(text) if answer is Answer.GRANT else "")


def _adopted_by(text: str) -> str:
    m = re.search(r"\b(?:adopted|established|promulgated|published|approved|made)\s+(?:and\s+(?:published|adopted|enforced)\s+)?by\s+(?:the\s+)?([^,;.]{2,50})", text, re.I)
    return m.group(1) if m else ""


# ---------------------------------------------------------------------------------------------------------------------
# The local model


PROMPT_VERSION = "2"        # in the key of a saved answer: a changed prompt asks again

METHOD = """You read one passage of a California common interest development's governing document (a declaration of \
covenants, conditions and restrictions, bylaws, election rules, operating rules, or a board policy) and decide what one \
marked sentence does about the power to make rules. The sentence is marked [[ like this ]] inside its section.

The question: does the marked sentence itself give someone the power (or impose the duty) to adopt, make, establish, \
amend, or repeal rules, regulations, policies, procedures, or guidelines? Answer only about the marked sentence; the \
rest of the passage is context, and a power given in another sentence is not this sentence's.

grant, one of:
- yes: the sentence gives that power or imposes that duty ("The Board may adopt rules governing ...", "The Association \
shall have the power to establish regulations ...").
- limits: the sentence limits or conditions how rules are made without giving the power itself: the notice to the \
members before a rule takes effect, the meeting where a rule is decided, a vote that may reverse a rule, when a rule \
may be adopted again, how long an emergency rule lasts, which rules the procedure applies to, a requirement that a \
rule be reasonable or not conflict with another document.
- refers: the sentence only refers to rules adopted somewhere else ("subject to the Rules", "as the Board may adopt", \
"in accordance with rules adopted by the Board"), or defines the word Rules.
- no: the words name rules but give no power and set no limit: a rule or policy speaking of itself ("these rules are \
effective on ..."), an insurance policy, parliamentary procedure, a duty to obey the rules, a penalty for breaking them.

holder: who holds the power, as the words state it, one of: board (the board of directors or a director); association; \
committee; members (the members or owners, by vote); officer; manager (the managing agent); other; unstated. A power \
given in the passive ("Rules may be adopted") has the holder the section names; otherwise unstated.

subjects: what the rules may be about, as the words state them, from this list only: general (use, occupancy, \
management, and operation at large); common_area; separate_interest (a unit, porch, patio, or garage); parking; \
vehicles; pets; registration; leasing; architecture (alterations and appearance); noise; trash; signs; fines; \
discipline (hearings and sanctions); assessments; disputes; elections; meetings; records; other. A subject not on the \
list is "other", with the word in other_subjects. Leave subjects empty when grant is no.

conditions: each limit or condition on the power that the sentence or its section states, with its kind and the words \
copied exactly. Kinds: consistent_with_documents (not in conflict with, or consistent with, the declaration, bylaws, or \
articles); consistent_with_law; reasonable; notice (notice to the members); member_vote (a member vote approves or \
reverses it); board_vote (a board vote at a meeting); in_writing; uniform (applies generally or alike); necessary (as \
the holder deems necessary, or for a stated purpose); emergency; board_approval (a committee's rules take effect on \
the board's approval); supplements (in addition to the document's own provisions); discretion (the holder's own \
discretion). List only what the words say.

procedure: the words that name how the power is exercised or how a rule is adopted (a notice period, a vote, a cross-\
reference to another section's procedure), copied exactly, or "".

words: the operative words that decide your answer, copied exactly from the marked sentence, four to thirty words.

Every quote is copied character for character from the passage; never paraphrase, and leave a quote "" when no words \
say it. When in doubt, answer no or refers, not yes."""

EXAMPLES = """Examples (invented text):
Passage: "The Board may adopt reasonable rules governing the use of the swimming pool, provided that the rules do not \
conflict with this Declaration."
Answer: {"grant": "yes", "holder": "board", "subjects": ["common_area"], "other_subjects": [], "conditions": [{"kind": \
"reasonable", "quote": "reasonable rules"}, {"kind": "consistent_with_documents", "quote": "do not conflict with this \
Declaration"}], "procedure": "", "words": "The Board may adopt reasonable rules governing the use of the swimming pool"}
Passage: "Owners shall comply with the Rules adopted by the Board. A policy of title insurance shall be delivered at closing."
Answer for the first sentence: {"grant": "refers", "holder": "board", "subjects": [], "other_subjects": [], \
"conditions": [], "procedure": "", "words": "the Rules adopted by the Board"}
Answer for the second sentence: {"grant": "no", "holder": "unstated", "subjects": [], "other_subjects": [], \
"conditions": [], "procedure": "", "words": ""}
Passage: "The Board shall give each Member written notice of a proposed rule at least 30 days before adopting it. Members \
holding five percent of the votes may call a meeting to vote on reversing the rule."
Answer for the first sentence: {"grant": "limits", "holder": "board", "subjects": [], "other_subjects": [], \
"conditions": [{"kind": "notice", "quote": "written notice of a proposed rule at least 30 days before adopting it"}], \
"procedure": "written notice of a proposed rule at least 30 days before adopting it", "words": "shall give each Member \
written notice of a proposed rule"}
Passage: "A decision on a proposed rule shall be made at a meeting of the Board. A rule reversed by the Members may not be \
adopted again for one year."
Answer for the second sentence: {"grant": "limits", "holder": "board", "subjects": [], "other_subjects": [], \
"conditions": [], "procedure": "may not be adopted again for one year", "words": "A rule reversed by the Members may not \
be adopted again for one year"}"""

ANSWER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "grant": {"type": "string", "enum": ANSWER_WORDS},
        "holder": {"type": "string", "enum": HOLDER_WORDS},
        "subjects": {"type": "array", "items": {"type": "string", "enum": SUBJECT_WORDS}},
        "other_subjects": {"type": "array", "items": {"type": "string"}},
        "conditions": {"type": "array", "items": {
            "type": "object",
            "properties": {"kind": {"type": "string", "enum": CONDITION_WORDS}, "quote": {"type": "string"}},
            "required": ["kind", "quote"]}},
        "procedure": {"type": "string"},
        "words": {"type": "string"},
    },
    "required": ["grant", "holder", "subjects", "other_subjects", "conditions", "procedure", "words"],
}


def prompt_for(c: Candidate) -> str:
    where = f"The document: {c.source}" + (f", section {c.section}" if c.section else ", a part with no section number")
    if c.title and c.title != c.section:
        where += f" ({c.title[:90]})"
    return f"{METHOD}\n\n{EXAMPLES}\n\n{where}.\nPassage:\n{c.context}"


def model_reading(raw: str, c: Candidate, *, consistency: float | None = None) -> Reading | None:
    """The model's answer as a reading, with each quote kept only when it is verbatim in the candidate's section. None when
    the answer is not JSON in the schema's shape."""
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    try:
        answer = Answer(str(data.get("grant") or "").strip().lower())
        holder = Holder(str(data.get("holder") or "unstated").strip().lower())
    except ValueError:
        return None
    dropped: list[str] = []
    section_words = c.context.replace("[[", "").replace("]]", "")

    def verbatim(quote: Any) -> str:
        words = _clean(str(quote or ""))
        if not words:
            return ""
        span = find_quote(section_words, words)
        if span is None:
            dropped.append(words[:120])
            return ""
        return _clean(section_words[span[0]:span[1]])

    subjects = []
    grounded = set(subjects_of(section_words))
    for s in data.get("subjects") or ():
        try:
            subject = Subject(str(s).strip().lower())
        except ValueError:
            continue
        # A subject is kept only when the section's words reach it: a model asked what a general power covers will list them all.
        if subject in (Subject.GENERAL, Subject.OTHER) or subject in grounded:
            if subject not in subjects:
                subjects.append(subject)
        else:
            dropped.append(f"subject {subject.value}: no word of the section reaches it")
    others = tuple(_clean(str(w)) for w in data.get("other_subjects") or () if _clean(str(w)))
    conditions = []
    for item in data.get("conditions") or ():
        if not isinstance(item, dict):
            continue
        try:
            kind = Condition(str(item.get("kind") or "").strip().lower())
        except ValueError:
            continue
        quote = verbatim(item.get("quote"))
        if quote:
            conditions.append(QuotedCondition(kind, quote, find_quote(c.text, quote) is None))
    procedure = verbatim(data.get("procedure"))
    words = verbatim(data.get("words"))
    # The model answers for the marked sentence. Words from another sentence of the passage mean it answered for that one
    # (which is its own candidate): this answer is no.
    if answer in (Answer.GRANT, Answer.LIMITS) and words and find_quote(c.text, words) is None:
        dropped.append("words not in the marked sentence: " + words[:100])
        answer, words = Answer.NO, ""
    if answer is Answer.NO:
        subjects, others, conditions, procedure = [], (), [], ""
    return Reading("model", answer, holder, tuple(subjects), others, tuple(conditions), procedure, words, consistency, tuple(dropped))


class RuleModel:
    """The local text model over one candidate, answering to ``ANSWER_SCHEMA``. ``fetch(url, payload)`` replaces HTTP in
    tests. Only an Ollama on this machine is asked; a request holds the GPU lock, and waits for it up to ``lock_wait``
    seconds (another job may hold it)."""

    def __init__(self, *, model: str = "", base_url: str = "", fetch: Callable[[str, dict], dict] | None = None,
                 timeout: int = 300, lock_wait: int = 3600, keep_alive: str = "5m", num_ctx: int = 16384) -> None:
        from jason.community.ocr_models import DEFAULT_TEXT_MODEL
        from jason.community.ollama_extractor import OLLAMA_URL

        self.model = model or DEFAULT_TEXT_MODEL
        self.base_url = (base_url or OLLAMA_URL).rstrip("/")
        if (urlparse(self.base_url).hostname or "") not in LOCAL_HOSTS:
            raise ValueError(f"the rule reader asks only an Ollama on this machine, not {self.base_url}")
        self._fetch = fetch
        self.timeout, self.lock_wait, self.keep_alive, self.num_ctx = timeout, lock_wait, keep_alive, num_ctx
        self._checked = False

    def preflight(self) -> None:
        """``local_ai.preflight``: refuse, before sending, a model that would run on the CPU or short of commit."""
        if self._fetch is not None or self._checked:
            return
        from jason.community.content import ModelUnavailable
        from jason.local_ai import LocalAIUnavailable, preflight

        try:
            preflight(self.model, ollama_url=self.base_url)
        except LocalAIUnavailable as exc:
            raise ModelUnavailable(str(exc)) from exc
        self._checked = True

    def release(self) -> None:
        """Unload the model (``keep_alive`` 0): a model left loaded crashes other jobs short of commit."""
        if self._fetch is not None:
            return
        try:
            from jason.local_ai import unload

            unload(self.model, ollama_url=self.base_url)
        except Exception:  # noqa: BLE001 - releasing is a courtesy; a failure leaves the model to its keep_alive
            pass

    def ask(self, c: Candidate, *, temperature: float = 0.0, seed: int | None = None) -> str:
        self.preflight()
        options: dict[str, Any] = {"temperature": temperature, "num_ctx": self.num_ctx, "num_predict": 1024}
        if seed is not None:
            options["seed"] = seed
        payload = {"model": self.model, "messages": [{"role": "user", "content": prompt_for(c)}], "format": ANSWER_SCHEMA,
                   "stream": False, "think": False, "keep_alive": self.keep_alive, "options": options}
        data = self._post("/api/chat", payload)
        return str((data.get("message") or {}).get("content") or data.get("response") or "")

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        if self._fetch is not None:
            return self._fetch(f"{self.base_url}{path}", payload)
        from urllib.error import URLError
        from urllib.request import Request, urlopen

        from jason.community.content import ModelUnavailable
        from jason.locks import Resource, ResourceBusy, hold

        request = Request(f"{self.base_url}{path}", data=json.dumps(payload).encode("utf-8"),
                          headers={"Content-Type": "application/json"}, method="POST")
        try:
            with hold(Resource.GPU, timeout=self.lock_wait, purpose=f"{self.model} rule authority"), \
                    urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except ResourceBusy as exc:
            raise ModelUnavailable(f"the model server stayed busy with another jason process: {exc}") from exc
        except (URLError, OSError) as exc:
            raise ModelUnavailable(f"Ollama at {self.base_url} did not answer: {exc}") from exc

    def read_raw(self, c: Candidate, *, samples: int = 3, temperature: float = 0.3) -> tuple[str, float | None]:
        """The greedy answer as the model wrote it, and its self-consistency: the share of ``samples`` more answers (at
        ``temperature``) that agree with it on the answer and the holder."""
        raw = self.ask(c)
        first = model_reading(raw, c)
        if first is None or samples <= 0:
            return raw, None
        agree = 0
        for k in range(samples):
            other = model_reading(self.ask(c, temperature=temperature, seed=k + 1), c)
            if other is not None and (other.answer, other.holder) == (first.answer, first.holder):
                agree += 1
        return raw, agree / samples

    def read(self, c: Candidate, *, samples: int = 3, temperature: float = 0.3) -> Reading | None:
        raw, consistency = self.read_raw(c, samples=samples, temperature=temperature)
        return model_reading(raw, c, consistency=consistency)


# ---------------------------------------------------------------------------------------------------------------------
# Agreement


def combine(c: Candidate, rules: Reading, model: Reading | None) -> RuleAuthority | None:
    """The authority row for a candidate from the readings that read it, with its tier; None when no reader read it as a
    grant or a limit (a reference or no is not an authority)."""
    readings = [r for r in (rules, model) if r is not None]
    kept = [r for r in readings if r.answer in (Answer.GRANT, Answer.LIMITS)]
    if not kept:
        return None
    grants = [r for r in readings if r.answer is Answer.GRANT]
    if model is None:
        tier, answer = Tier.SUGGESTED, kept[0].answer
    elif rules.answer is model.answer and rules.answer in (Answer.GRANT, Answer.LIMITS):
        same = Holder.UNSTATED in (rules.holder, model.holder) or rules.holder is model.holder
        tier, answer = (Tier.LIKELY if same else Tier.SUGGESTED), rules.answer
    elif grants and any(r.answer in (Answer.NO, Answer.REFERS) for r in readings):
        tier, answer = Tier.CONFLICT, Answer.GRANT
    else:
        tier, answer = Tier.SUGGESTED, kept[0].answer
    chosen = [r for r in readings if r.answer is answer] or kept
    lead = next((r for r in chosen if r.reader == "model"), chosen[0])
    holder = next((r.holder for r in chosen if r.holder is not Holder.UNSTATED), Holder.UNSTATED)
    subjects: list[Subject] = []
    for r in chosen:
        subjects += [s for s in r.subjects if s not in subjects]
    others = tuple(dict.fromkeys(w for r in chosen for w in r.other_subjects))
    seen: dict[Condition, QuotedCondition] = {}
    for r in chosen:
        for cond in r.conditions:
            seen.setdefault(cond.kind, cond)
    words = lead.words or next((r.words for r in chosen if r.words), "") or _clean(c.text)
    procedure = lead.procedure or next((r.procedure for r in chosen if r.procedure), "")
    return RuleAuthority(c.id, c.source, c.section, c.title, answer, holder, tuple(subjects), others, tuple(seen.values()),
                         procedure, words, _clean(c.text), tier, tuple(r.reader for r in chosen),
                         model.consistency if model is not None else None, (), c.part, part_source=c.part_source,
                         part_contested=c.part_contested)


def link(rows: list[RuleAuthority]) -> list[RuleAuthority]:
    """Tie each grant to the limits that bear on it: those of the same document that name its section, are named by it, or
    speak of a rule change. A related provision is a lead, not a finding."""
    from dataclasses import replace

    limits = [r for r in rows if r.answer is Answer.LIMITS]
    out = []
    for r in rows:
        if r.answer is not Answer.GRANT:
            out.append(r)
            continue
        cited = {m.group(0).lower() for m in _CITES.finditer(r.sentence)}
        related = []
        for lim in limits:
            if lim.source != r.source:
                continue
            names = {m.group(0).lower() for m in _CITES.finditer(lim.sentence)}
            if (lim.section and f"section {lim.section}".lower() in cited) or (r.section and f"section {r.section}".lower() in names) \
                    or re.search(r"\brule\s+changes?\b", lim.sentence, re.I) and re.search(r"\brule\s+changes?\b|\bRules\b", r.sentence):
                related.append(lim.id)
        out.append(replace(r, related=tuple(related)))
    return out


def find(outlines: Iterable[DocumentOutline], *, model: RuleModel | None = None, duties: dict[str, list[DocumentDuty]] | None = None,
         parts: Sequence[RulePart] = (), samples: int = 3, cache: dict[str, Any] | None = None, cached_model: str = "",
         log: Callable[[str], None] = lambda s: None) -> dict[str, Any]:
    """Read every candidate of ``outlines``. Returns the candidates, each reader's readings by candidate id, and the
    authority rows. The model is asked only when given; ``cache`` (model and candidate id to the model's saved reading)
    saves a rerun and is filled as it goes. With no model, ``cached_model`` names a model whose saved answers are read."""
    cands: list[Candidate] = []
    rules: dict[str, Reading] = {}
    models: dict[str, Reading] = {}
    for outline in outlines:
        found = (duties or {}).get(outline.key)
        readings = found if found is not None else read_outline(outline)
        for c in candidates(outline, readings, parts=parts):
            cands.append(c)
            rules[c.id] = rule_reading(c, readings)
    name = model.model if model is not None else cached_model
    if name:
        for n, c in enumerate(cands, 1):
            key = f"{name}@{PROMPT_VERSION}|{c.id}"
            saved = (cache or {}).get(key)
            if saved is not None and "raw" not in saved:
                saved = None            # an answer saved before the raw text was kept
            if saved is None and model is not None:
                raw, consistency = model.read_raw(c, samples=samples)
                saved = {"raw": raw, "consistency": consistency}
                if cache is not None:
                    cache[key] = saved
            reading = model_reading(saved["raw"], c, consistency=saved.get("consistency")) if saved else None
            if reading is not None:
                models[c.id] = reading
            if model is not None and n % 10 == 0:
                log(f"  {n} of {len(cands)} candidates read")
    rows = [r for c in cands if (r := combine(c, rules[c.id], models.get(c.id))) is not None]
    return {"candidates": cands, "rules": rules, "model": models, "authorities": link(rows)}


# ---------------------------------------------------------------------------------------------------------------------
# Rules on file, and the subjects


@dataclass(frozen=True)
class RuleOnFile:
    """A section of a rules document (or a rules part of one) that states a norm, with the subjects its words reach."""

    source: str
    section: str
    title: str
    subjects: tuple[Subject, ...]
    words: str                       # the section's first norm sentence
    kind: str = "rule"               # "rule" or "policy" (a policy bound in, or a separate policy document)
    part_source: str = ""            # where the part came from, when the document has parts: "segments" or "classification"


RULE_KINDS = ("operating_rules", "election_rules", "policy")
RESTRICTION_KINDS = ("declaration", "bylaws", "amendment")


def _norm_sentences(p: Any, duties: Sequence[DocumentDuty]) -> list[DocumentDuty]:
    return [d for d in duties if d.section == p.section and p.start <= d.start < p.start + len(p.text)
            and d.kind in (DutyKind.PROHIBITION, DutyKind.DUTY, DutyKind.PERMISSION)]


def rules_on_file(outlines: Iterable[DocumentOutline], *, duties: dict[str, list[DocumentDuty]] | None = None,
                  parts: Sequence[RulePart] = (), kinds: Sequence[str] = RULE_KINDS) -> list[RuleOnFile]:
    """The norms the rules documents state, by section, with subjects. In a document with parts, only the rule and policy
    parts count (the manual's guidance is not a rule). A section is a rule on file on the strength of its words only: that
    the board adopted it is an act ``docs/programs.md``'s adoption evidence records, not this."""
    out: list[RuleOnFile] = []
    for outline in outlines:
        if outline.kind not in kinds:
            continue
        readings = (duties or {}).get(outline.key)
        if readings is None:
            readings = read_outline(outline)
        mine = [p for p in parts if p.source == outline.key]
        for p in passages(outline, max_chars=1_000_000, min_chars=1):
            part = part_at(mine, outline.key, p.start) if mine else None
            if mine and (part is None or part.kind not in ("rule", "policy")):
                continue
            norms = _norm_sentences(p, readings)
            if not norms:
                continue
            subs = subjects_of(f"{p.title} " + " ".join(d.quote for d in norms[:2]))
            out.append(RuleOnFile(outline.key, p.section, p.title, subs, _clean(norms[0].quote)[:300],
                                  part.kind if part else ("policy" if outline.kind == "policy" else "rule"),
                                  part.origin if part else ""))
    return out


def restrictions(outlines: Iterable[DocumentOutline], *, duties: dict[str, list[DocumentDuty]] | None = None) -> list[RuleOnFile]:
    """The prohibitions the declaration and bylaws state themselves, by section and subject: a restriction the documents
    set directly is not a rule, and needs no rule to stand."""
    out: list[RuleOnFile] = []
    for outline in outlines:
        if outline.kind not in RESTRICTION_KINDS:
            continue
        readings = (duties or {}).get(outline.key)
        if readings is None:
            readings = read_outline(outline)
        for p in passages(outline, max_chars=1_000_000, min_chars=1):
            norms = [d for d in _norm_sentences(p, readings) if d.kind is DutyKind.PROHIBITION]
            if norms:
                out.append(RuleOnFile(outline.key, p.section, p.title, subjects_of(f"{p.title} " + " ".join(d.quote for d in norms[:2])),
                                      _clean(norms[0].quote)[:300], "restriction"))
    return out


class Standing(Enum):
    AUTHORITY_AND_RULES = "authority named, rules on file"   # a grant names the subject; rules on it are on file
    AUTHORITY_ONLY = "authority named, no rules on file"     # a grant names it; no rule on file states a norm on it
    GENERAL_AND_RULES = "general power only, rules on file"  # only a general power reaches it; rules on it are on file
    GENERAL_ONLY = "general power only, no rules on file"
    RULES_ONLY = "rules on file, no grant found"             # rules on it are on file; no grant found that reaches it
    NEITHER = "neither found"


@dataclass(frozen=True)
class SubjectRow:
    subject: Subject
    standing: Standing
    grants: tuple[str, ...]          # ids of the grants that name the subject
    general: tuple[str, ...]         # ids of the general grants ("use, occupancy, management ...") that reach every subject
    in_guidance: tuple[str, ...]     # ids of grants stated only in a guidance part (an owner's guide): not counted
    rules: tuple[RuleOnFile, ...]
    restrictions: tuple[RuleOnFile, ...]
    reading: Reading4355

    @property
    def general_only(self) -> bool:
        return bool(self.general) and not self.grants


def by_subject(authorities: Iterable[RuleAuthority], on_file: Iterable[RuleOnFile], stated: Iterable[RuleOnFile] = (),
               *, subjects: Iterable[Subject] | None = None) -> list[SubjectRow]:
    """Each subject's standing: the grants whose words name it, the general grants that reach every subject (kept apart,
    since a general power says nothing of this subject in particular), the rules on file on it, and the restrictions the
    documents state themselves. ``rules on file, no grant found`` is a finding for the board and no accusation: the
    authority may be in a document not read, or in the law itself."""
    held_grants = [a for a in authorities if a.answer is Answer.GRANT]
    grants = [a for a in held_grants if a.part in ("", "rule", "policy")]
    guide = [a for a in held_grants if a.part not in ("", "rule", "policy")]
    on_file, stated = list(on_file), list(stated)
    out = []
    for subject in subjects or [s for s in Subject if s is not Subject.OTHER]:
        said = tuple(a.id for a in guide if subject in a.subjects)
        named = tuple(a.id for a in grants if subject in a.subjects)
        general = tuple(a.id for a in grants if Subject.GENERAL in a.subjects and subject not in a.subjects)
        rules = tuple(r for r in on_file if subject in r.subjects)
        held = tuple(r for r in stated if subject in r.subjects)
        if named:
            standing = Standing.AUTHORITY_AND_RULES if rules else Standing.AUTHORITY_ONLY
        elif general:
            standing = Standing.GENERAL_AND_RULES if rules else Standing.GENERAL_ONLY
        else:
            standing = Standing.RULES_ONLY if rules else Standing.NEITHER
        out.append(SubjectRow(subject, standing, named, general, said, rules, held, reach(subject)))
    return out


# ---------------------------------------------------------------------------------------------------------------------
# The store


def store_path(data_dir: Any) -> Any:
    from pathlib import Path

    path = Path(data_dir) / "rules"
    path.mkdir(parents=True, exist_ok=True)
    return path / "authority.json"


def load_store(data_dir: Any) -> dict[str, Any]:
    path = store_path(data_dir)
    if not path.is_file():
        return {"authorities": [], "reviews": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def stored(data_dir: Any) -> list[RuleAuthority]:
    """The stored authorities with each one's review applied."""
    from dataclasses import replace

    raw = load_store(data_dir)
    reviews = raw.get("reviews") or {}
    out = []
    for item in raw.get("authorities") or ():
        row = RuleAuthority.from_dict(item)
        r = reviews.get(row.id)
        out.append(replace(row, review=Review(r["status"]), note=r.get("note", "")) if r else row)
    return out


def save(data_dir: Any, authorities: Sequence[RuleAuthority], *, reader: str, model: str = "", candidates_read: int = 0,
         references: int = 0) -> dict[str, Any]:
    """Write the authorities, keeping every review whose reading is still there; a review whose reading is gone is kept
    under ``orphaned`` for a person."""
    from datetime import datetime, timezone

    from jason.locks import Resource, hold

    with hold(Resource.STORE, "rule-authority", timeout=60, purpose="jason rules"):
        old = load_store(data_dir)
        reviews = dict(old.get("reviews") or {})
        ids = {a.id for a in authorities}
        orphaned = dict(old.get("orphaned") or {})
        for rid in list(reviews):
            if rid not in ids:
                orphaned[rid] = reviews.pop(rid)
        out = {"read": datetime.now(timezone.utc).isoformat(timespec="seconds"), "reader": reader, "model": model,
               "candidates": candidates_read, "references": references,
               "authorities": [a.to_dict() for a in authorities], "reviews": reviews, "orphaned": orphaned,
               "answers": old.get("answers") or {}}
        store_path(data_dir).write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


def load_answers(data_dir: Any) -> dict[str, Any]:
    return dict(load_store(data_dir).get("answers") or {})


def save_answers(data_dir: Any, answers: dict[str, Any]) -> None:
    from jason.locks import Resource, hold

    with hold(Resource.STORE, "rule-authority", timeout=60, purpose="jason rules"):
        raw = load_store(data_dir)
        raw["answers"] = answers
        store_path(data_dir).write_text(json.dumps(raw, indent=1), encoding="utf-8")


def review(data_dir: Any, authority_id: str, status: Review, *, note: str = "", reviewer: str = "") -> dict[str, Any]:
    from datetime import datetime, timezone

    from jason.locks import Resource, hold

    with hold(Resource.STORE, "rule-authority", timeout=60, purpose="jason rules --review"):
        raw = load_store(data_dir)
        if authority_id not in {a["id"] for a in raw.get("authorities") or ()}:
            raise KeyError(f"no authority {authority_id}")
        entry = {"status": status.value, "note": note, "reviewer": reviewer,
                 "when": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        raw.setdefault("reviews", {})[authority_id] = entry
        store_path(data_dir).write_text(json.dumps(raw, indent=1), encoding="utf-8")
    return entry


# ---------------------------------------------------------------------------------------------------------------------
# Measurement against a hand-labelled gold set


def gold_match(item: dict[str, Any], cands: Sequence[Candidate]) -> Candidate | None:
    """The candidate a gold item labels: the one whose sentence holds the item's ``quote`` (and, with ``source``, the one in
    that document)."""
    for c in cands:
        if item.get("source") and item["source"] != c.source:
            continue
        if find_quote(c.text, str(item.get("quote") or "")) is not None:
            return c
    return None


def _counts(pairs: Iterable[tuple[bool, bool]]) -> dict[str, float]:
    tp = fp = fn = tn = 0
    for want, got in pairs:
        tp += want and got
        fp += got and not want
        fn += want and not got
        tn += not want and not got
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": round(p, 3), "recall": round(r, 3),
            "f1": round(2 * p * r / (p + r), 3) if p + r else 0.0}


def measure(gold: Sequence[dict[str, Any]], cands: Sequence[Candidate], rules: dict[str, Reading],
            model: dict[str, Reading] | None = None) -> dict[str, Any]:
    """Precision and recall of "this is a grant" for the rules alone, the model alone, both (agreeing, the likely tier),
    and either, over the gold items; plus the collector's recall (the share of gold grants a candidate holds), and the
    holder and subject agreement on the grants each reader got right."""
    model = model or {}
    matched, missed = [], []
    for item in gold:
        c = gold_match(item, cands)
        (matched if c else missed).append((item, c))
    want = lambda item: item.get("label") == "yes"                                                    # noqa: E731
    out: dict[str, Any] = {"items": len(gold), "collected": len(matched),
                           "missedByCollector": [i.get("quote", "")[:80] for i, _ in missed],
                           "collectorRecall": round(sum(1 for i, _ in matched if want(i)) / max(1, sum(1 for i in gold if want(i))), 3)}
    rows = {"rules": [], "model": [], "both": [], "either": []}
    for item, c in matched:
        r = rules[c.id].answer is Answer.GRANT
        m = c.id in model and model[c.id].answer is Answer.GRANT
        rows["rules"].append((want(item), r))
        if model:
            rows["model"].append((want(item), m))
            same = r and m and Holder.UNSTATED in (rules[c.id].holder, model[c.id].holder) or (r and m and rules[c.id].holder is model[c.id].holder)
            rows["both"].append((want(item), bool(same)))
            rows["either"].append((want(item), r or m))
    # A gold grant the collector missed is a false negative for every reader.
    for item, _ in missed:
        if want(item):
            for name in rows:
                if rows[name] is not None and (name == "rules" or model):
                    rows[name].append((True, False))
    out["readers"] = {name: _counts(pairs) for name, pairs in rows.items() if pairs}
    labels = {"rules": rules, "model": model}
    detail: dict[str, Any] = {}
    for name, readings in labels.items():
        hits = [(item, readings[c.id]) for item, c in matched if want(item) and c.id in readings and readings[c.id].answer is Answer.GRANT]
        holder_ok = sum(1 for item, r in hits if item.get("holder") in (None, r.holder.value))
        subjects_ok = [len({s.value for s in r.subjects} & set(item.get("subjects") or ())) / max(1, len(set(item.get("subjects") or ())))
                       for item, r in hits if item.get("subjects")]
        if hits:
            detail[name] = {"grantsRead": len(hits), "holderRight": holder_ok,
                            "subjectRecall": round(sum(subjects_ok) / len(subjects_ok), 3) if subjects_ok else None}
    out["detail"] = detail
    # Four-way answers, for the confusion between no, limits, and refers.
    for name, readings in labels.items():
        if readings:
            right = sum(1 for item, c in matched if c.id in readings and readings[c.id].answer.value == item.get("label"))
            out.setdefault("answerRight", {})[name] = f"{right} of {len(matched)}"
    return out


__all__ = [
    "Answer", "Candidate", "Condition", "Holder", "Reach", "Reading", "Reading4355", "Review", "RuleAuthority", "RuleModel",
    "RuleOnFile", "RulePart", "Standing", "Subject", "SubjectRow", "Tier", "by_subject", "candidates", "combine", "find",
    "link", "load_store", "measure", "model_reading", "parts_from_manual", "part_at", "prompt_for", "reach", "restrictions",
    "rule_reading", "rules_on_file", "save", "stored", "subjects_of",
]
