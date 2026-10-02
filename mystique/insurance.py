"""Insurance coverage. Files are found by walking Insurance, not by listing each PDF."""

from datetime import date

from jason.community.base import PremiumRules
from jason.community.register import InsuranceRegistry
from jason.community.sources import Sender, SourceKind
from jason.community.symbols import Building, PolicyKind

from .buildings import BUILDINGS

catalog = InsuranceRegistry()

# The flood zone every building's declarations print (CURRENT FLOOD ZONE: A99), as the flood notices explain it.
FLOOD_ZONE = ("A99: a high-risk Special Flood Hazard Area protected by levees still being completed. Most mortgage "
              "lenders require flood insurance there.")


# The board's policy sheet (September 29, 2026) lists N030PK2940-00, G74805796, and 4124011561232Y. The carriers'
# own letters show the number each term carried; the sheet's are earlier terms and stay as prior numbers.


# Accelerant-Arden Community Association National: the claim acknowledgment of June 22, 2026 (loss of June 4, 2026)
# and the notice of conditional renewal of July 24, 2026 name NO30PK2940-01, expiring September 28, 2026. The 2025-26
# premium was financed through Arden: $7,821.30 down on September 30, 2025, then monthly installments to May 2026.
@catalog.policy
# 2026-27 (LaBarre/Oksnee's certificate of September 30, 2026): N030PK2940-02, September 28, 2026 to September 28, 2027;
# the signed proposal adds a $5,000 general liability deductible ("due to claims history"). The sheet was updated October 1.
class Master:
    kind = PolicyKind.MASTER
    number = "N030PK2940-02"
    prior_numbers = ("N030PK2940-01", "N030PK2940-00")
    renewal = date(2027, 9, 28)
    carrier = "Accelerant National Insurance Company"
    program = "Arden Insurance Services"
    agent = "LaBarre/Oksnee Insurance Agency"
    premium_categories = ("Master",)
    # $10,000 per occurrence: the board's threshold for a claim (September 29, 2026), and what Accelerant's statement of
    # loss on claim AZ260311 (the 3031 Enchanted garage, May 2026) subtracts.
    deductible_cents = 1_000_000


# Federal Insurance Company through McGowan Program Administrators: the notice of conditional renewal of July 13, 2026
# names G75199788, expiring September 28, 2026 (the sheet's April 5 is not this policy's date). The umbrella premium
# was paid with the D&O premium on September 29, 2024 and September 30, 2025.
@catalog.policy
# 2026-27 (the certificate of September 30, 2026): G75734232, September 28, 2026 to September 28, 2027.
class Umbrella:
    kind = PolicyKind.UMBRELLA
    number = "G75734232"
    prior_numbers = ("G75199788", "G74805796")
    renewal = date(2027, 9, 28)
    carrier = "Federal Insurance Company"
    program = "McGowan Program Administrators"
    agent = "LaBarre/Oksnee Insurance Agency"
    premium_categories = ("Umbrella",)


# The crime (fidelity) policy is Manufacturers Alliance's through LaBarre/Oksnee, and its number carries the term's year:
# 4124... (2024), 4125... (invoice of Aug 14, 2025), 4126... (invoice of Aug 14, 2026, effective Sep 28, 2026; the $318
# premium cleared to CAIS Insurance on Aug 26, 2026).
@catalog.policy
class Fidelity:
    kind = PolicyKind.FIDELITY
    number = "4126011561232Y"
    prior_numbers = ("4125011561232Y", "4124011561232Y")
    renewal = date(2027, 9, 28)
    carrier = "Manufacturers Alliance Insurance Company"
    agent = "LaBarre/Oksnee Insurance Agency"
    premium_categories = ("Fidelity",)


# MG Skinner's D&O/Crime binder of July 25, 2025 names 1-SKN-CA-01524174-01 for 2025-26 with Accredited Surety and
# Casualty ($1,000,000 aggregate, $1,000 retention, $1,292.95); the sheet's -00 is the 2024-25 term.
@catalog.policy
# 2026-27 (the certificate of September 30, 2026): 1-SKN-CA-01524174-02, September 28, 2026 to September 28, 2027.
class DirectorsAndOfficers:
    kind = PolicyKind.DIRECTORS_AND_OFFICERS
    number = "1-SKN-CA-01524174-02"
    prior_numbers = ("1-SKN-CA-01524174-01", "1-SKN-CA-01524174-00")
    renewal = date(2027, 9, 28)
    carrier = "Accredited Surety and Casualty Company"
    program = "MG Skinner & Associates"
    agent = "LaBarre/Oksnee Insurance Agency"
    premium_categories = ("D&O",)


# PMA's workers' compensation, a new policy effective September 28, 2026: CAIS, LLC's invoice 7734669 of September 24,
# 2026 ($355 premium and $18 tax, $373.00 due October 18, 2026), sent by LaBarre/Oksnee on September 30, 2026. CAIS bills
# it and the crime policy on one account; the prefix tells them apart (20... workers' comp, 41... crime). The budget has
# no workers' comp line, so no PayHOA category is named until the treasurer chooses one.
@catalog.policy
class WorkersComp:
    kind = PolicyKind.WORKERS_COMP
    number = "2026011561232Y"
    renewal = date(2027, 9, 28)
    carrier = "Pennsylvania Manufacturers' Association Insurance Company"
    program = "CAIS, LLC"
    agent = "LaBarre/Oksnee Insurance Agency"


class _Flood:
    """NFIP flood through Philadelphia Insurance Companies, one policy per building, since 2025.

    ``renewal`` is the end of the term in force, as the carrier's renewal bill states it ("Your flood insurance policy
    will expire 12/03/2026"); a renewal already paid does not move it.
    """

    kind = PolicyKind.FLOOD
    carrier = "Philadelphia Indemnity Insurance Company (NFIP)"
    premium_categories = ("Flood",)


@catalog.policy
class FloodBuilding1(_Flood):
    kind = PolicyKind.FLOOD
    number = "5010015467"
    renewal = date(2027, 4, 5)
    building = Building.BLDG_1


@catalog.policy
class FloodBuilding2(_Flood):
    kind = PolicyKind.FLOOD
    number = "5010017011"
    # 5010012496 was Building 2's earlier NFIP policy; its 2024-25 term overlaps the current number's (confirmed by the
    # board 2026-09-29).
    prior_numbers = ("5010012496",)
    renewal = date(2027, 2, 27)
    building = Building.BLDG_2


@catalog.policy
class FloodBuilding3(_Flood):
    kind = PolicyKind.FLOOD
    number = "5010022692"
    renewal = date(2026, 12, 3)
    building = Building.BLDG_3
    location_prints_building = True


@catalog.policy
class FloodBuilding4(_Flood):
    kind = PolicyKind.FLOOD
    number = "5010022694"
    renewal = date(2026, 12, 19)
    building = Building.BLDG_4
    location_prints_building = True


@catalog.policy
class FloodBuilding5(_Flood):
    kind = PolicyKind.FLOOD
    number = "5010022209"
    renewal = date(2026, 11, 20)
    building = Building.BLDG_5


@catalog.policy
class FloodBuilding6(_Flood):
    kind = PolicyKind.FLOOD
    number = "5010022695"
    renewal = date(2026, 12, 3)
    building = Building.BLDG_6
    location_prints_building = True


@catalog.policy
class FloodBuilding7(_Flood):
    kind = PolicyKind.FLOOD
    number = "5010015472"
    renewal = date(2027, 4, 19)
    building = Building.BLDG_7


@catalog.policy
class FloodBuilding8(_Flood):
    kind = PolicyKind.FLOOD
    number = "5010022696"
    renewal = date(2026, 12, 3)
    building = Building.BLDG_8
    location_prints_building = True


CATALOG = catalog.catalog(BUILDINGS, ())


# Following an approval in the minutes to the premiums it bought (jason paid-vs-approved). The September 23, 2025 minutes
# approve "a $29,137 insurance renewal": the package proposal's $29,137.95 is the master ($26,421 through Arden, a down
# payment and seven installments), the umbrella and D&O ($2,398.95 to LaBarre/Oksnee), and the crime policy ($318 to CAIS).
_I = SourceKind.INSURER
PREMIUM_RULES = PremiumRules(
    words=r"\binsur|\bpremium|\bumbrella\b|\bD\s?&\s?O\b|directors and officers|\bcrime\b|\bfidelity\b|\bflood\b|\bcoverage\b|"
          r"\bNFIP\b|workers'? comp",
    weak_words=r"\brenewal\b|\bpolicy\b|\bpackage\b",
    coverage_words=(
        (PolicyKind.FLOOD, r"\bflood\b|\bNFIP\b"),
        (PolicyKind.UMBRELLA, r"\bumbrella\b|excess liability"),
        (PolicyKind.DIRECTORS_AND_OFFICERS, r"\bD\s?&\s?O\b|directors and officers"),
        (PolicyKind.FIDELITY, r"\bcrime\b|\bfidelity\b"),
        (PolicyKind.WORKERS_COMP, r"workers'? comp"),
        (PolicyKind.MASTER, r"\bmaster\b|\bpackage policy\b|\bproperty and (?:general )?liability\b"),
    ),
    package=(PolicyKind.MASTER, PolicyKind.UMBRELLA, PolicyKind.DIRECTORS_AND_OFFICERS, PolicyKind.FIDELITY),
    payees=(
        # The NFIP premium is an ACH debit from the Write Your Own carrier: "ORIG CO NAME:FLOOD INSURANCE ... PREMIUM",
        # booked to the payee "Flood Insurance" (Philadelphia since 2025; Fire Insurance Exchange before). FEMA's own
        # NFIP Direct is the same program without a carrier.
        Sender("Flood Insurance (NFIP premium debit)", _I, ("FLOOD INSURANCE",), role="NFIP flood premium debit from the WYO carrier"),
        Sender("NFIP Direct", _I, ("NFIP DIRECT", "NFIPDIRECT", "FEMA NFIP", "NATIONAL FLOOD INSURANCE PROGRAM"), role="FEMA's NFIP Direct (NFIP premium paid to FEMA: \"FEMA NFIP FLOOD INSUR\", October 28, 2024)"),
        # Premium finance companies: a financed premium is paid to them in installments, not to the carrier. Arden finances
        # the master itself; none of these has been paid yet.
        Sender("Imperial PFS", _I, ("IMPERIAL PFS", "IPFS"), role="premium finance company"),
        Sender("First Insurance Funding", _I, ("FIRST INSURANCE FUNDING", "FIRST INS FUNDING"), role="premium finance company"),
        Sender("AFCO Premium Finance", _I, ("AFCO",), role="premium finance company"),
        Sender("BankDirect Capital Finance", _I, ("BANKDIRECT",), role="premium finance company"),
        Sender("US Premium Finance", _I, ("US PREMIUM FINANCE", "USPF"), role="premium finance company"),
    ),
    # "Insurance" carried the Farmers master installments of 2024; "Policy Fee" is a program's or purchasing group's fee
    # billed with a premium; "Workers Comp" has no policy's premium_categories until the treasurer books the PMA premium.
    categories=("Insurance", "Policy Fee", "Workers Comp"),
)
