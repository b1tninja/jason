"""The profile's rows for community facts, the unit record, and the loss packet.

See ``mystique/docs/unit-records-profile.md`` for why each row exists. Provisions are ``cite_document`` expressions, never the
words. A reading here is a lead: it points, and the carrier, the board, and counsel decide.
"""

from jason.community.facts import Fact, FactScope, FactStatus, ScopeKind
from jason.community.loss_packet import LadderStep, OpenQuestion
from jason.community.unit_record import ComponentKind as K
from jason.community.unit_record import UnitCoverage

UNIT_FINISHES = "unit-finishes-and-equipment"
BUILDER_OPTIONS = "builder-options"
CONSEQUENTIAL_DAMAGE = "consequential-damage-7-11"
DEDUCTIBLE_GUIDELINES = "deductible-guidelines"

UNIT_COVERAGE = UnitCoverage(
    # Declaration 8.1(a)(i)(B): "utility fixtures" are both the plumbing and the electrical.
    declaration_kinds=(
        K.WALL_FINISH,
        K.CEILING_FINISH,
        K.FLOORING,
        K.DOORS,
        K.PLUMBING_FIXTURE,
        K.ELECTRICAL_FIXTURE,
        K.CABINETS,
        K.BUILT_IN_APPLIANCE,
        K.HVAC,
        K.WATER_HEATER,
    ),
    # Endorsement N CP 12301: fixtures (built-in cabinets and appliances, electrical and plumbing) and appliances.
    policy_kinds=(K.CABINETS, K.BUILT_IN_APPLIANCE, K.ELECTRICAL_FIXTURE, K.PLUMBING_FIXTURE, K.APPLIANCE),
    declaration_cite=("decl#8.1(a)(i)(B)", "decl#8.4"),
    policy_cite=(),  # the endorsement's library address, once the policy's declarations are on file
    differs_question=UNIT_FINISHES,
    builder_question=BUILDER_OPTIONS,
)

LOSS_LADDER = (
    LadderStep(1, "What is the item?", ("decl#8.1(a)(i)(B)", "decl#8.4"), (UNIT_FINISHES, BUILDER_OPTIONS)),
    LadderStep(2, "Where did the cause originate?", ("decl#7.6", "decl#7.11", "decl#7.9"), (CONSEQUENTIAL_DAMAGE,)),
    LadderStep(
        3,
        "Is it an insured casualty above the deductible?",
        ("decl#11.1", "decl#11.2", "decl#8.1(a)(iv)", "decl#8.1(a)(vi)"),
        (UNIT_FINISHES,),
    ),
    LadderStep(
        4,
        "Whose negligence, and of what degree?",
        ("decl#7.6", "decl#7.9", "decl#7.11"),
        (CONSEQUENTIAL_DAMAGE,),
    ),
    LadderStep(5, "Who pays the deductible?", ("decl#8.1(a)(vii)",), (DEDUCTIBLE_GUIDELINES,)),
)

OPEN_QUESTIONS = (
    OpenQuestion(
        UNIT_FINISHES,
        "Does the master policy extend to unit finishes, heating and cooling, and water heaters?",
        with_whom="the insurance agent",
        status="draft not sent",
        source="data/drafts/insurance-agent-unit-coverage.md",
    ),
    OpenQuestion(
        BUILDER_OPTIONS,
        "Does a developer option installed at closing count as original?",
        with_whom="the insurance agent",
    ),
    OpenQuestion(
        CONSEQUENTIAL_DAMAGE,
        "Is 7.11 lawful and fair as applied to a roof leak?",
        with_whom="counsel",
        status="sent",
        asked="2026-03-19",
    ),
    OpenQuestion(
        DEDUCTIBLE_GUIDELINES,
        "The board has not adopted the guidelines 8.1(a)(vii) calls for; the April 30, 2026 write-up is a draft to adopt.",
        with_whom="the board",
        status="draft",
        source="mystique/docs/unit-records-findings.md",
    ),
)

_COMMUNITY = FactScope(ScopeKind.COMMUNITY)

FACTS = (
    Fact(
        "touch-up-paint",
        "Touch-up paint is addressed in the Owner's Manual.",
        ("paint",),
        _COMMUNITY,
        FactStatus.DOCUMENTED,
        sources=("Owner's Manual",),
    ),
    Fact(
        "interior-paint-colors",
        "No interior color is on file; interior paint is read as the owner's discretion.",
        ("paint", "interior"),
        _COMMUNITY,
        FactStatus.ASSUMED,
        provisions=("decl#7.5",),
    ),
    Fact(
        "original-finishes-by-plan",
        "The original flooring and appliances for each plan are not on file.",
        ("interior", "unit record"),
        _COMMUNITY,
        FactStatus.ASSUMED,
    ),
    Fact(
        "interior-water-damage",
        "Who repairs interior water damage is a question the declaration speaks to.",
        ("insurance", "repairs"),
        _COMMUNITY,
        FactStatus.DOCUMENTED,
        provisions=("decl#7.11",),
        answers=(CONSEQUENTIAL_DAMAGE,),
    ),
    Fact(
        "master-policy-unit-components",
        "The declaration's list and the policy's endorsement name different components.",
        ("insurance", "unit record"),
        _COMMUNITY,
        FactStatus.DOCUMENTED,
        provisions=("decl#8.1(a)(i)(B)",),
        answers=(UNIT_FINISHES,),
    ),
)
