"""The reserve study, read by the existing preparer readers in ``jason.community.reserve_study``.

Civil Code 5550(a) has the board cause a visual inspection of the major components at least once every three years as part
of a reserve study, and review the study every year. The study identifies the major components with a remaining life
under 30 years, their remaining life, and their cost (5550(b)(1)-(3)), estimates the annual contribution needed
(5550(b)(4)), and sets a reserve funding plan (5550(b)(5)) with the schedule of assessment changes it needs (5560(a)).
Every study prints the Assessment and Reserve Funding Disclosure Summary in the words of 5570(a). The exterior elevated
elements report (5551) must be incorporated into the study (5551(f)), and the next such inspection coordinates with the
reserve study's (5551(i)).

``ReserveStudyModel`` splits the library's text back into pages at the preparers' page footers and hands them to
``read_pages``: California Builder Services, The Helsing Group, and Browning Reserve Group have their own readers, and any
other preparer yields at least the 5570 disclosure (its rates and 30-year answer in any preparer's wording). The record is
the reader's ``ReserveStudy`` with what the checks add; Browning's "Expenditures by Year" schedule
(``reserve_study.by_year_expenditures``) is tried on any study whose reader found no itemized expenditures.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import date

from jason.community.document_models import DocumentModel, Finding, ModelContext, Severity, register, squash
from jason.community.models.financial_common import disk_studies, long_date, spec_units
from jason.community.reserve_study import ReserveStudy, StudyLevel, by_year_expenditures, read_pages
from jason.community.symbols import DocumentKind

SITE_VISIT_YEARS = 3   # CIV 5550(a)

_PAGE_END = re.compile(r"^\s*(?:PAGE \d+-\d+|Page \d+(?: of \d+)?)\s*$")
_ELEVATED = re.compile(r"\b5551\b|SB\s*-?\s*326|elevated elements?|balcon(?:y|ies)|\bdecks?\b|landings?|walkways?", re.I)
_ELEVATED_REPORT = re.compile(r"(?:elevated elements?|SB\s*-?\s*326|5551|balcony|deck)[^.]{0,80}(?:inspection )?report\b|"
                              r"California Deck Inspection|report[^.]{0,60}(?:elevated elements?|SB\s*-?\s*326|5551)", re.I)


@dataclass
class ReserveStudyRecord:
    study: ReserveStudy
    preparer: str = ""
    fiscal_year: int | None = None
    prepared: date | None = None
    level: StudyLevel | None = None
    units: int | None = None
    components: int = 0
    components_with_life_and_cost: int = 0
    projection_years: int = 0
    planned_expenditures: int = 0
    last_site_visit: date | None = None        # when the study states its field inspection's date
    elevated_elements: tuple[str, ...] = ()    # the study's lines on balconies, decks, stairs, SB 326
    elevated_report_cited: bool = False        # the study names the 5551 inspection report
    # The 5570 form's answers where the preparer's reader missed them, read from the form's own words.
    interest_rate: float | None = None
    inflation_rate: float | None = None
    sufficient_for_30_years: bool | None = None
    not_inspected: tuple[str, ...] = ()        # components the study says were not visually inspected


_NOT_INSPECTED = re.compile(r"[^.]*\bnot (?:been )?visually inspected\b[^.]*\.", re.I)


def split_pages(text: str) -> list[str]:
    """The text back into pages. The library joins each page's text (which ends in a newline) with a newline, so an empty
    line is a page break; a text without one is cut after the preparers' page footers ("PAGE 2-3", " Page 4 ")."""
    text = text or ""
    if "\n\n" in text:
        return [page for page in text.split("\n\n") if page.strip()] or [text]
    pages: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        current.append(line)
        if _PAGE_END.match(line):
            pages.append("\n".join(current))
            current = []
    if current:
        pages.append("\n".join(current))
    return pages or [text]


class ReserveStudyModel(DocumentModel):
    kind = DocumentKind.RESERVE_STUDY
    name = "reserve-study"
    required = ("preparer", "fiscal_year", "prepared", "level")

    def parse(self, text: str, context: ModelContext) -> ReserveStudyRecord | None:
        text = text or ""
        head = squash(text[:20000])
        if not re.search(r"reserve (?:study|analysis|funding)|funding update|replacement reserve", head, re.I):
            return None
        study = read_pages(split_pages(text), context.name)
        if not study.expenditures:
            study = replace(study, expenditures=by_year_expenditures(text))
        r = ReserveStudyRecord(study=study, preparer="" if study.preparer == "unknown preparer" else study.preparer,
                               fiscal_year=study.fiscal_year, prepared=study.prepared, level=study.level, units=study.units)
        r.components = len(study.components)
        r.components_with_life_and_cost = sum(1 for c in study.components if c.remaining_life_years is not None
                                              and (c.future_cost_cents or c.current_cost_cents))
        r.projection_years = len(study.projection)
        r.planned_expenditures = len(study.expenditures)
        flat = squash(text)
        visit = re.search(r"(?:field inspection|site (?:visit|inspection))[^.]{0,60}?(?:completed|conducted|performed)(?: on)? "
                          r"([A-Z][a-z]+ \d{1,2}, \d{4})", flat)
        r.last_site_visit = long_date(visit.group(1)) if visit else None
        if r.last_site_visit is None and study.level in (StudyLevel.FULL, StudyLevel.UPDATE_WITH_SITE_VISIT):
            r.last_site_visit = study.prepared
        r.elevated_elements = tuple(dict.fromkeys(line.strip()[:120] for line in text.splitlines() if _ELEVATED.search(line)))[:12]
        r.elevated_report_cited = bool(_ELEVATED_REPORT.search(flat))
        d = study.disclosure
        r.interest_rate, r.inflation_rate, r.sufficient_for_30_years = d.interest_rate, d.inflation_rate, d.sufficient_for_30_years
        r.not_inspected = tuple(dict.fromkeys(squash(m.group(0))[:200] for m in _NOT_INSPECTED.finditer(flat)))[:6]
        return r

    def check(self, r: ReserveStudyRecord, context: ModelContext) -> list[Finding]:
        found: list[Finding] = []
        s = r.study
        if r.level in (StudyLevel.FULL, StudyLevel.UPDATE_WITH_SITE_VISIT):
            found.append(Finding("site-visit-study", f"a {r.level.value}: the visual inspection 5550(a) requires at least every three years",
                                 Severity.INFO, "CIV 5550(a)"))
        elif r.level is StudyLevel.UPDATE_WITHOUT_SITE_VISIT:
            found.append(Finding("no-site-visit", "an update without a site visit; a visual inspection of the major components is due at "
                                 "least every three years", Severity.CHECK, "CIV 5550(a)"))
        if r.components == 0:
            found.append(Finding("no-components-read", "no component list was read (the reader may not know this layout); the study must "
                                 "identify the major components, their remaining life, and their cost", Severity.CHECK, "CIV 5550(b)(1)-(3)"))
        elif r.components_with_life_and_cost < r.components:
            found.append(Finding("components-without-life-or-cost", f"{r.components - r.components_with_life_and_cost} of {r.components} "
                                 "components read without a remaining life or cost", Severity.CHECK, "CIV 5550(b)(2), (3)"))
        if r.projection_years == 0 and s.monthly_contribution_cents is None:
            found.append(Finding("no-funding-plan-read", "no funding plan or contribution was read", Severity.CHECK, "CIV 5550(b)(4), (5)"))
        d = s.disclosure
        for label, value, item in (("fiscal year ending", d.fiscal_year, "5570(a)"),
                                   ("answer on 30-year sufficiency", r.sufficient_for_30_years, "5570(a)(3)"),
                                   ("amount required at year end", d.required_end_of_year_cents, "5570(a)(6)"),
                                   ("projected reserve balance at year end", d.projected_end_of_year_cents, "5570(a)(6)"),
                                   ("interest rate assumed", r.interest_rate, "5570(a)(7) note"),
                                   ("inflation rate assumed", r.inflation_rate, "5570(a)(7) note")):
            if value is None:
                found.append(Finding("disclosure-lacks-" + re.sub(r"[^a-z0-9]+", "-", label).strip("-"), f"the 5570 disclosure's {label} was not "
                                     "read from the text", Severity.CHECK, "CIV " + item))
        if r.sufficient_for_30_years is False:
            found.append(Finding("reserves-insufficient", "the disclosure answers No: projected reserves will not cover the next 30 years",
                                 Severity.INFO, "CIV 5570(a)(3), (4)"))
        funded = s.percent_funded
        if funded is not None:
            found.append(Finding("percent-funded", f"{funded:.0%} funded (the statute's formula; the preparer's figure)", Severity.INFO,
                                 "CIV 5570(a)(6), (b)(4)"))
        if r.interest_rate is not None:
            found.append(Finding("interest-assumption", f"the study assumes {r.interest_rate:.2%} interest on reserves; the reserve calculation may "
                                 "not assume more than 2 points over the Federal Reserve Bank of San Francisco's discount rate at the time",
                                 Severity.INFO, "CIV 5300(b)(7)"))
        if r.not_inspected:
            found.append(Finding("components-not-inspected", "the study says some components were not visually inspected: "
                                 + " ".join(r.not_inspected)[:300], Severity.CHECK, "CIV 5550(a)"))
        units = spec_units(context)
        if r.units and units and r.units != units:
            found.append(Finding("unit-count", f"the study counts {r.units} units; the specification has {units}, so its per-unit figures are "
                                 "off by that ratio", Severity.CHECK))
        if not r.preparer:
            found.append(Finding("unknown-preparer", "no reader knows this preparer; only the 5570 disclosure was read", Severity.CHECK))
        if not r.elevated_elements:
            found.append(Finding("no-elevated-elements", "the study does not mention balconies, decks, stairs, or the SB 326 inspection",
                                 Severity.CHECK, "CIV 5551(f)"))
        elif not r.elevated_report_cited:
            found.append(Finding("elevated-report-not-cited", "the study lists elevated elements but does not cite the 5551 inspection report "
                                 "it must incorporate", Severity.CHECK, "CIV 5551(f)"))
        else:
            found.append(Finding("elevated-report-cited", "the study cites the elevated-element inspection report", Severity.INFO, "CIV 5551(f)"))
        found += self._schedule(r, context)
        return found

    @staticmethod
    def _schedule(r: ReserveStudyRecord, context: ModelContext) -> list[Finding]:
        """Against the other studies on disk: whether this one is the latest, and when the next site visit falls due."""
        studies = disk_studies(context)
        if not studies or not r.fiscal_year:
            return []
        found: list[Finding] = []
        newer = [s for s in studies if (s.fiscal_year or 0) > r.fiscal_year]
        if newer:
            latest = max(newer, key=lambda s: (s.fiscal_year or 0, s.prepared or date.min))
            found.append(Finding("superseded", f"a later study is on disk (FY{latest.fiscal_year} by {latest.preparer})", Severity.INFO))
            return found
        visits = [s for s in studies if s.level in (StudyLevel.FULL, StudyLevel.UPDATE_WITH_SITE_VISIT) and s.fiscal_year]
        if visits:
            last = max(visits, key=lambda s: s.fiscal_year)
            due = last.fiscal_year + SITE_VISIT_YEARS
            severity = Severity.CHECK if due <= context.today.year + 1 else Severity.INFO
            found.append(Finding("next-site-visit", f"the last study with a site visit is FY{last.fiscal_year} ({last.preparer}); the next "
                                 f"is due for FY{due}", severity, "CIV 5550(a)"))
        if r.fiscal_year < context.today.year:
            found.append(Finding("no-current-study", f"no study on disk is newer than FY{r.fiscal_year}; the board reviews the study every year",
                                 Severity.CHECK, "CIV 5550(a)"))
        return found


register(ReserveStudyModel())

__all__ = ["ReserveStudyRecord", "ReserveStudyModel", "split_pages", "by_year_expenditures"]
