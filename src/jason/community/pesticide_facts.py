"""What each active ingredient is, what it harms, and which California rules reach it; and the label limits jason can test.

Reference data, not Mystique facts: the rows are the same for any association. Each row cites the
source it was checked against (September 29, 2026). ``INGREDIENTS`` describes; ``LABEL_LIMITS`` and
``SITE_RULES`` are tested against the vendor's application record by ``check_applications``. A test
that needs a fact the record lacks (which building, what "landscape areas" means) asks rather than finds.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from enum import Enum


class Concern(Enum):
    HIGHEST = "highest"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Ingredient:
    name: str
    chemical_class: str
    action: str
    people_and_pets: str
    bees: Concern
    aquatic: Concern
    california: str
    sources: tuple[str, ...]
    names: tuple[str, ...] = ()

    def matches(self, label: str) -> bool:
        folded = label.casefold()
        return any(n.casefold() in folded for n in (self.name, *self.names))


PYRETHROID_RULE = ("Pyrethroid surface-water rule (3 CCR 6970): outdoors, only spot, crack-and-crevice, or a 1-inch pin stream on "
                   "pavement, doors and windows; a band up to 2 ft on walls and 3 ft on soil; never in rain, on standing water, "
                   "or into drains and gutters (baits in stations and eaves exempt, 3 CCR 6972)")
NEONIC_RULE = ("Neonicotinoid rule (FAC 12838(c)(2), since Jan 1, 2025): on outdoor ornamental plants, trees, or turf only a "
               "certified commercial applicator may apply it (for a structural company, an Operator or Field Representative); "
               "building and crack-and-crevice uses are not the restricted site; DPR's reevaluation is due by Q3 2027")

INGREDIENTS: tuple[Ingredient, ...] = (
    Ingredient("dinotefuran", "neonicotinoid", "systemic; attacks the insect nervous system",
               "moderate acute toxicity; the label keeps children and pets off treated surfaces until dry; a potential "
               "groundwater contaminant (DPR)", Concern.HIGHEST, Concern.LOW, NEONIC_RULE,
               ("https://ipm.ucanr.edu/home-and-landscape/pesticide-active-ingredients-database/active-ingredient-details/?uaiKey=140",
                "https://www.cdpr.ca.gov/active-ingredient/dinotefuran/")),
    Ingredient("imidacloprid", "neonicotinoid", "systemic; attacks the insect nervous system",
               "DPR's 2024 non-agricultural assessment found a risk to children after turf use; pets show vomiting, drooling, "
               "tremors; persists months to years in soil", Concern.HIGHEST, Concern.HIGH,
               NEONIC_RULE + "; DPR modeled building-perimeter use as the largest source of neonicotinoid runoff, and Sacramento "
               "creek samples exceeded the aquatic benchmark in every detection (2022-23)",
               ("http://npic.orst.edu/factsheets/imidagen.html",
                "https://www.cdpr.ca.gov/wp-content/uploads/2024/12/study_329_monitoring_report_2024.pdf")),
    Ingredient("bifenthrin", "pyrethroid", "contact nerve poison",
               "EPA: possible human carcinogen; pets show drooling, tremors; binds to soil and reaches creeks on sediment",
               Concern.HIGHEST, Concern.HIGHEST,
               PYRETHROID_RULE + "; DPR calls it the leading cause of pyrethroid toxicity in urban water, and it was in every "
               "Sacramento-area sediment sample (2022-23)",
               ("https://npic.orst.edu/factsheets/bifgen.html", "https://www.law.cornell.edu/regulations/california/3-CCR-6970")),
    Ingredient("lambda-cyhalothrin", "pyrethroid", "contact nerve poison", "soil half-life about 30 days",
               Concern.HIGHEST, Concern.HIGHEST, PYRETHROID_RULE,
               ("http://npic.orst.edu/factsheets/l_cyhalogen.pdf",), ("lambda cyhalothrin",)),
    Ingredient("deltamethrin", "pyrethroid", "contact nerve poison",
               "EPA: not likely a human carcinogen; toxic to dogs and cats if eaten; soil half-life 6 to 209 days",
               Concern.HIGHEST, Concern.HIGH, PYRETHROID_RULE + "; every Sacramento creek detection exceeded the benchmark (2022-23)",
               ("http://npic.orst.edu/factsheets/DeltaGen.html",)),
    Ingredient("alpha-cypermethrin", "pyrethroid", "contact nerve poison", "label signal word Caution",
               Concern.HIGH, Concern.HIGHEST,
               "3 CCR 6970 lists cypermethrin; whether it reaches alpha-cypermethrin (a separate DPR chemical code) is not settled; "
               "the federal label allows a 7-ft soil band where 6970 caps pyrethroid bands at 3 ft",
               ("https://apps.cdpr.ca.gov/cgi-bin/label/pir.pl?prodno=74136",), ("alpha cypermethrin", "cypermethrin")),
    Ingredient("esfenvalerate", "pyrethroid", "contact nerve poison (with prallethrin for knockdown)",
               "EPA's 2020 review added residential post-application mitigation to prallethrin labels",
               Concern.HIGH, Concern.HIGH, PYRETHROID_RULE,
               ("https://www3.epa.gov/pesticides/chem_search/ppls/001021-02574-20260305.pdf",), ("prallethrin",)),
    Ingredient("fipronil", "phenylpyrazole", "blocks insect nerve signaling",
               "EPA: possible human carcinogen (thyroid); DPR 2023 found a risk of concern to professional handlers of the "
               "concentrate, not to residents after application; breakdown products are more toxic to aquatic life than fipronil",
               Concern.HIGH, Concern.HIGHEST,
               "California label terms for Termidor SC: 0.03% dilution only, 4 applications a calendar year, 60 days apart, none "
               "Nov 1 to Feb 28, a band 6 in up and 6 in out; DPR's 2025-26 actions target pet flea products, not structural use",
               ("https://www3.epa.gov/pesticides/chem_search/ppls/007969-00210-20230815.pdf",
                "https://www.cdpr.ca.gov/active-ingredient/fipronil/")),
    Ingredient("cholecalciferol", "vitamin D3 rodenticide (not an anticoagulant)", "raises blood calcium to kidney failure",
               "high acute toxicity; a pet that eats bait shows vomiting and thirst, then kidney failure in 1 to 2 days, with "
               "no specific antidote; NPIC rates secondary poisoning low, but the label warns dogs and scavengers may be poisoned "
               "by eating poisoned rodents; tamper-resistant stations are required where children or pets can reach",
               Concern.LOW, Concern.HIGH,
               "not reached by California's anticoagulant bans (FAC 12978.7: AB 1788, AB 1322, AB 2552)",
               ("http://npic.orst.edu/factsheets/rodenticides.html",
                "https://www3.epa.gov/pesticides/chem_search/ppls/007969-00382-20170310.pdf")),
    Ingredient("sodium lauryl sulfate", "FIFRA 25(b) minimum-risk (botanical oils and a surfactant)", "contact",
               "EPA does not review exempt products; independent bee and aquatic data were not found",
               Concern.LOW, Concern.UNKNOWN,
               "exempt from California registration if it meets 3 CCR 6147, and exempt from pesticide use reporting, so it will "
               "not appear in the county's use records",
               ("https://www.cdpr.ca.gov/wp-content/uploads/2024/08/section25b.pdf",), ("geraniol", "clove oil", "cornmint")),
)


def ingredients_of(label: str, product: str = "") -> tuple[Ingredient, ...]:
    """The ingredients a vendor's active-ingredient label names ("Dinotefuran 40%"); the product name as a fallback."""
    found = tuple(i for i in INGREDIENTS if i.matches(label))
    if found or not product:
        return found
    return tuple(i for i in INGREDIENTS if i.name in PRODUCT_INGREDIENTS.get(product.upper(), ()))


# Products whose portal record leaves the active ingredient blank.
PRODUCT_INGREDIENTS = {"FENDONA CS": ("alpha-cypermethrin",)}


@dataclass(frozen=True)
class LabelLimit:
    """A label's limits on how often, when, and how strong, for one product in California."""

    epa_registration: str
    product: str
    per_year: int
    min_interval_days: int
    closed_from: tuple[int, int]
    closed_to: tuple[int, int]
    max_fl_oz_per_gallon: float
    dilution: str
    source: str


LABEL_LIMITS: tuple[LabelLimit, ...] = (
    LabelLimit("7969-210", "TERMIDOR SC", 4, 60, (11, 1), (2, 28), 0.4, "0.03% (0.4 fl oz per gallon)",
               "Termidor SC label, EPA-stamped Aug 15, 2023, Additional California Specific Use Restrictions: "
               "https://www3.epa.gov/pesticides/chem_search/ppls/007969-00210-20230815.pdf"),
)


@dataclass(frozen=True)
class SiteRule:
    """A restricted site for an ingredient: an application record naming the site is a question for the vendor."""

    ingredients: tuple[str, ...]
    site_words: tuple[str, ...]
    since: date
    question: str
    citation: str


SITE_RULES: tuple[SiteRule, ...] = (
    SiteRule(("dinotefuran", "imidacloprid"), ("landscape", "turf", "lawn", "shrub", "tree", "ornamental", "plant", "yard"),
             date(2025, 1, 1),
             "The record lists landscape or yard areas. Were ornamental plants, trees, or turf treated, and by a technician "
             "with an Operator or Field Representative license?",
             "FAC 12838(c)(2); DPR Q&A, Oct 1, 2024"),
)


def _in_closed_season(day: date, limit: LabelLimit) -> bool:
    start = date(day.year, *limit.closed_from)
    end = date(day.year, *limit.closed_to)
    return day >= start or day <= end if start > end else start <= day <= end


def _applied(row: dict) -> bool:
    """The row records a volume applied ("4.000 gals"), not "0.000 gals"."""
    match = re.match(r"\s*([\d.]+)", row.get("diluted") or "")
    return match is None or float(match.group(1)) > 0


def _fl_oz_per_gallon(dilution: str) -> float | None:
    """"0.3 flozs / 1 gals" as fluid ounces per gallon."""
    match = re.match(r"\s*([\d.]+)\s*(fl ?ozs?|flozs?|gals?)\s*/\s*([\d.]+)\s*gals?", dilution or "", re.I)
    if not match:
        return None
    amount = float(match.group(1)) * (128.0 if match.group(2).lower().startswith("gal") else 1.0)
    return amount / float(match.group(3))


def check_applications(applications: list[dict], buildings_by_day: dict[str, tuple[int, ...]] | None = None,
                       labels: dict[str, str] | None = None) -> list[dict]:
    """Findings for one property's applications: label limits the record shows exceeded, and site-rule questions.

    Intervals and yearly counts are per building where the visit note names the buildings, else per property.
    ``applications`` are the portal's chemical usage rows (day, product, epa_number, dilution, areas); ``labels`` maps a
    product to the active-ingredient label its visit records carry ("Imidacloprid 21.4%").
    """
    findings: list[dict] = []
    buildings_by_day = buildings_by_day or {}
    labels = labels or {}
    for limit in LABEL_LIMITS:
        # A row recording no volume applied is a placeholder, not an application.
        rows = sorted((a for a in applications if a["product"].upper() == limit.product and a.get("day") and _applied(a)),
                      key=lambda a: a["day"])
        days = sorted({a["day"] for a in rows})
        for a in rows:
            if re.match(r"\s*[\d.]+\s*gals?\s*/", a.get("dilution", ""), re.I):
                findings.append({"kind": "question", "product": limit.product, "date": a["day"],
                                 "finding": f"the record's dilution reads \"{a['dilution']}\", gallons of product per gallon; "
                                            f"ask for the actual mix (the California label allows only {limit.dilution})",
                                 "source": limit.source})
                continue
            strength = _fl_oz_per_gallon(a.get("dilution", ""))
            if strength is not None and strength > limit.max_fl_oz_per_gallon + 1e-9:
                findings.append({"kind": "label", "product": limit.product, "date": a["day"],
                                 "finding": f"mixed at {strength:g} fl oz per gallon; the California label allows only {limit.dilution}",
                                 "areas": a.get("areas", ""), "source": limit.source})
        for d in days:
            if _in_closed_season(date.fromisoformat(d), limit):
                findings.append({"kind": "label", "product": limit.product, "date": d,
                                 "finding": "applied between November 1 and February 28, which the California label prohibits",
                                 "source": limit.source})
        groups: dict[str, list[date]] = {}
        for d in days:
            names = buildings_by_day.get(d)
            for key in ([f"building {b}" for b in names] if names else ["the property"]):
                groups.setdefault(key, []).append(date.fromisoformat(d))
        # A day with no building named is compared with the property's other days only; without the buildings the
        # record cannot show the same structure was treated twice, so a short gap there is a question.
        for key, dates in groups.items():
            for earlier, later in zip(dates, dates[1:]):
                gap = (later - earlier).days
                if gap < limit.min_interval_days:
                    known = key != "the property"
                    findings.append({"kind": "label" if known else "question", "product": limit.product, "date": later.isoformat(),
                                     "where": key if known else "buildings not recorded",
                                     "finding": f"{gap} days after the {earlier.isoformat()} application; the California label "
                                                f"requires {limit.min_interval_days}" + ("" if known else
                                                " between applications to the same structure; which buildings were treated?"),
                                     "source": limit.source})
            per_year: dict[int, int] = {}
            for d in dates:
                per_year[d.year] = per_year.get(d.year, 0) + 1
            for year, count in per_year.items():
                if count > limit.per_year:
                    findings.append({"kind": "label", "product": limit.product, "date": str(year), "where": key,
                                     "finding": f"{count} applications in {year}; the California label allows {limit.per_year}",
                                     "source": limit.source})
    for rule in SITE_RULES:
        for a in applications:
            if not a.get("day") or date.fromisoformat(a["day"]) < rule.since:
                continue
            names = {i.name for i in ingredients_of(labels.get(a["product"], ""), a["product"])}
            areas = (a.get("areas") or "").lower()
            if names & set(rule.ingredients) and any(w in areas for w in rule.site_words):
                findings.append({"kind": "question", "product": a["product"], "date": a["day"], "finding": rule.question,
                                 "areas": a.get("areas", ""), "source": rule.citation})
    return sorted(findings, key=lambda f: (f["kind"], f["product"], f["date"]))


__all__ = ["Concern", "Ingredient", "INGREDIENTS", "ingredients_of", "LabelLimit", "LABEL_LIMITS", "SiteRule", "SITE_RULES",
           "check_applications", "PYRETHROID_RULE", "NEONIC_RULE"]
