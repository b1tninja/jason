"""The reserve study as a document: its funding plan, its components, and its thirty-year cash flow.

A reserve study is prepared each year (Civil Code 5550: a full study with a site visit
at least every three years, an update in between). It drives two budget lines: the
reserve contribution (the transfer to reserves), and the reserve analyst's own fee. It
also carries the Assessment and Reserve Funding Disclosure Summary (Civil Code 5570)
that must go to members with the budget.

Every preparer prints that disclosure in the statute's words, so ``read_disclosure``
reads it from any study. Everything else is laid out the preparer's own way, so each
preparer is a ``StudyReader``: ``CaliforniaBuilderServices`` reads the funding summary,
the projection, the component funding summary, and the annual expenditure detail. A
study no reader recognises still yields its disclosure.

Amounts are integer cents. A percent is a fraction (0.43).
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace
from datetime import date
from enum import Enum
from pathlib import Path


class StudyLevel(Enum):
    """The three kinds of study the industry standard names (Level I, II, III)."""

    FULL = "full study with site visit"
    UPDATE_WITH_SITE_VISIT = "update with site visit"
    UPDATE_WITHOUT_SITE_VISIT = "update without site visit"


@dataclass(frozen=True)
class DisclosureYear:
    year: int
    required_cents: int | None = None
    projected_cents: int | None = None
    percent_funded: float | None = None


@dataclass(frozen=True)
class ReserveDisclosure:
    """The Assessment and Reserve Funding Disclosure Summary (Civil Code 5570), as the study states it."""

    fiscal_year: int | None = None
    assessment_per_month_cents: int | None = None
    sufficient_for_30_years: bool | None = None
    required_end_of_year_cents: int | None = None
    projected_end_of_year_cents: int | None = None
    current_balance_cents: int | None = None
    percent_funded: float | None = None
    interest_rate: float | None = None
    inflation_rate: float | None = None
    next_years: tuple[DisclosureYear, ...] = ()


@dataclass(frozen=True)
class ProjectionYear:
    """One year of the study's funding plan: what goes in, what is spent, and where the fund ends."""

    year: int
    current_cost_cents: int
    contribution_cents: int
    interest_cents: int
    expenditures_cents: int
    ending_balance_cents: int
    fully_funded_cents: int
    percent_funded: float


@dataclass(frozen=True)
class StudyComponent:
    """One component line of the study's component funding summary."""

    category: str
    description: str
    future_cost_cents: int | None
    useful_life_years: int | None
    remaining_life_years: int | None
    distribution_cents: int = 0
    contribution_cents: int = 0
    liability_cents: int = 0
    fully_funded_cents: int = 0
    unfunded: bool = False
    # Today's replacement cost, when the study prints it beside (or instead of) the inflated future cost.
    current_cost_cents: int | None = None
    quantity: str = ""


@dataclass(frozen=True)
class PlannedExpenditure:
    """A component's replacement or repair the study schedules in a year, at that year's inflated cost."""

    year: int
    category: str
    description: str
    cost_cents: int


@dataclass(frozen=True)
class ReserveStudy:
    preparer: str
    prepared: date | None
    fiscal_year: int | None
    level: StudyLevel | None
    units: int | None
    source: str
    disclosure: ReserveDisclosure
    beginning_balance_cents: int | None = None
    monthly_contribution_cents: int | None = None
    contribution_increase: float | None = None
    projection: tuple[ProjectionYear, ...] = ()
    components: tuple[StudyComponent, ...] = ()
    expenditures: tuple[PlannedExpenditure, ...] = ()
    notes: tuple[str, ...] = ()

    @property
    def annual_contribution_cents(self) -> int | None:
        row = self.year(self.fiscal_year) if self.fiscal_year else None
        if row:
            return row.contribution_cents
        return self.monthly_contribution_cents * 12 if self.monthly_contribution_cents is not None else None

    @property
    def percent_funded(self) -> float | None:
        """Beginning balance against the fully funded balance, from the component table; else the disclosure's figure."""
        funded = sum(c.fully_funded_cents for c in self.components)
        if funded and self.beginning_balance_cents is not None:
            return round(self.beginning_balance_cents / funded, 3)
        return self.disclosure.percent_funded

    def year(self, year: int | None) -> ProjectionYear | None:
        return next((row for row in self.projection if row.year == year), None)

    def expenditures_in(self, year: int) -> list[PlannedExpenditure]:
        return [item for item in self.expenditures if item.year == year]

    def per_unit_month_cents(self, cents: int | None) -> int | None:
        if cents is None or not self.units:
            return None
        return round(cents / self.units / 12)


_MONEY = r"\$?\s?([\d,]+(?:\.\d\d)?)"
_RATE = r"(\d{1,2}(?:\.\d+)?)\s*(?:%|percent)"


def cents_of(text: str | None) -> int | None:
    """"$195,572" or "7,364.67" as cents."""
    if text is None:
        return None
    raw = text.replace("$", "").replace(",", "").strip()
    if not raw:
        return None
    whole, _, frac = raw.partition(".")
    return int(whole or "0") * 100 + int((frac + "00")[:2])


def flat(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def read_disclosure(text: str) -> ReserveDisclosure:
    """The statutory disclosure summary's figures, from any preparer's wording of Civil Code 5570."""
    t = flat(text)
    fiscal = re.search(r"Fiscal Year Ending:?\s*(?:\d{1,2}/\d{1,2}/)?(20\d\d)", t, re.I)
    assessment = re.search(r"regular assessment per ownership interest is:?\s*" + _MONEY + r"\s*per Month", t, re.I)
    required = re.search(r"estimated amount required in the reserve fund at the end of the current fiscal year is\s*" + _MONEY, t, re.I)
    projected = re.search(r"projected reserve fund cash balance at the end of the current fiscal year is\s*" + _MONEY, t, re.I)
    current = re.search(r"current fund balance of\s*" + _MONEY, t, re.I)
    percent = re.search(r"reserves being\s*([\d.]+)%\s*funded", t, re.I) or re.search(r"percentage funding of\s*([\d.]+)%", t, re.I)
    # The statute's wording, or the note some preparers print instead ("2.00% per year was the assumed long-term interest rate").
    interest = (re.search(r"interest rate earned on reserve funds (?:was|is)\s*" + _RATE, t, re.I)
                or re.search(_RATE + r" per year was the assumed long-term (?:before[- ]tax )?interest rate", t, re.I))
    inflation = (re.search(r"inflation rate to be applied to major component[^.]{0,80}? (?:was|is)\s*" + _RATE, t, re.I)
                 or re.search(_RATE + r" per year was the assumed long-term inflation rate", t, re.I))
    sufficient = None
    answer = re.search(r"next 30 years\?\s*(Yes\s*[_\sX]*No\s*[_\sX]*)", t, re.I)
    if answer:
        chunk = answer.group(1)
        yes, no = re.search(r"Yes\s*([_\s]*X)", chunk), re.search(r"No\s*([_\s]*X)", chunk)
        sufficient = True if yes and not no else False if no and not yes else None
    else:
        # Helsing prints the answer in words: "... during the next 30 years? Answer: Yes".
        worded = re.search(r"(?:during|over) the next 30 years\?\s*(?:Answer:?\s*)?(Yes|No)\b", t, re.I)
        sufficient = worded.group(1).lower() == "yes" if worded else None
    years: dict[int, dict] = {}
    required_block = re.search(r"Estimated Reserve Amount Required(.*?)(?:If the reserve funding plan|$)", t, re.I)
    if required_block:
        for year, amount in re.findall(r"\b(20\d\d)\s+\$([\d,]+)", required_block.group(1)):
            years.setdefault(int(year), {})["required_cents"] = cents_of(amount)
    projected_block = re.search(r"Projected Reserve Fund Balance Percent Funded(.*?)(?:Note:|$)", t, re.I)
    if projected_block:
        for year, amount, pct in re.findall(r"\b(20\d\d)\s+\$([\d,]+)\s+([\d.]+)%", projected_block.group(1)):
            entry = years.setdefault(int(year), {})
            entry["projected_cents"] = cents_of(amount)
            entry["percent_funded"] = round(float(pct) / 100, 3)
    return ReserveDisclosure(
        fiscal_year=int(fiscal.group(1)) if fiscal else None,
        assessment_per_month_cents=cents_of(assessment.group(1)) if assessment else None,
        sufficient_for_30_years=sufficient,
        required_end_of_year_cents=cents_of(required.group(1)) if required else None,
        projected_end_of_year_cents=cents_of(projected.group(1)) if projected else None,
        current_balance_cents=cents_of(current.group(1)) if current else None,
        percent_funded=round(float(percent.group(1)) / 100, 3) if percent else None,
        interest_rate=round(float(interest.group(1)) / 100, 5) if interest else None,
        inflation_rate=round(float(inflation.group(1)) / 100, 5) if inflation else None,
        next_years=tuple(DisclosureYear(y, **v) for y, v in sorted(years.items())),
    )


class StudyReader(ABC):
    """One preparer's layout."""

    preparer: str

    @abstractmethod
    def matches(self, pages: list[str]) -> bool: ...

    @abstractmethod
    def read(self, pages: list[str], source: str) -> ReserveStudy: ...

    def read_layout(self, words: list[list[tuple]], study: ReserveStudy) -> ReserveStudy:
        """What only the words' positions show (a table whose text comes out in the wrong order); ``words`` is each page's
        PyMuPDF ``get_text("words")``. The study as read by default."""
        return study


_NUMBER = re.compile(r"^\$?-?[\d,]+(?:\.\d+)?%?$")


def _lines(pages: list[str], heading: str) -> list[str]:
    """The non-empty lines of every page whose text carries ``heading``, trailing numbers split off their text."""
    out: list[str] = []
    for page in pages:
        if heading not in page:
            continue
        for raw in page.splitlines():
            line = raw.strip()
            if not line:
                continue
            # "Paving - Asphalt; Overlay & Replacement 218,050" -> text, number; ".. 69,777" and "Replace..2,554,168" too.
            match = re.match(r"^(.*?[A-Za-z)\].])\s*((?:\$?[\d,]+(?:\.\d+)?%?\s*)+)$", line)
            if match and re.search(r"[A-Za-z]", match.group(1)) and not re.fullmatch(r"20\d\d", match.group(2).strip()):
                out.append(match.group(1).strip())
                out.extend(match.group(2).split())
            else:
                out.append(line)
    return out


class CaliforniaBuilderServices(StudyReader):
    """California Builder Services (Clovis): "Reserve Analysis Report", full studies and updates since FY25."""

    preparer = "California Builder Services"

    def matches(self, pages: list[str]) -> bool:
        return any("CALIFORNIA BUILDER SERVICES" in p for p in pages[:6]) and any("RESERVE ANALYSIS REPORT" in p for p in pages[:2])

    def read(self, pages: list[str], source: str) -> ReserveStudy:
        text = "\n".join(pages)
        head = flat("\n".join(pages[:1]))
        kind = re.search(r"(Full Study|Update)\s*(?:\|)?\s*FY(\d\d)\s*(?:\|)?\s*([A-Z][a-z]+ \d{1,2}, \d{4})", head)
        prepared = _long_date(kind.group(3)) if kind else None
        level = None
        if kind:
            level = StudyLevel.FULL if kind.group(1) == "Full Study" else (
                StudyLevel.UPDATE_WITH_SITE_VISIT if re.search(r"with site visit", text, re.I) and not re.search(r"without site visit", text, re.I)
                else StudyLevel.UPDATE_WITHOUT_SITE_VISIT)
        summary = flat(next((p for p in pages if "Funding Model Summary" in p and "Report Parameters" in p), ""))
        units = re.search(r"Total Units\s+(\d+)", summary)
        begin = re.search(r"(20\d\d) Beginning Balance\s*" + _MONEY, summary)
        monthly = re.search(r"Required Monthly Contribution\s*" + _MONEY, summary)
        increase = re.search(r"Annual Assessment Increase\s*([\d.]+)%", summary)
        budget_year = re.search(r"Budget Year Beginning\s+[A-Z][a-z]+ \d{1,2}, (20\d\d)", summary)
        fiscal = int(budget_year.group(1)) if budget_year else (2000 + int(kind.group(2)) if kind else None)
        disclosure = read_disclosure("\n".join(p for p in pages if "Disclosure Summary" in p or "PAGE 1-2" in p))
        return ReserveStudy(
            preparer=self.preparer,
            prepared=prepared,
            fiscal_year=fiscal,
            level=level,
            units=int(units.group(1)) if units else None,
            source=source,
            disclosure=disclosure,
            beginning_balance_cents=cents_of(begin.group(2)) if begin else None,
            monthly_contribution_cents=cents_of(monthly.group(1)) if monthly else None,
            contribution_increase=round(float(increase.group(1)) / 100, 4) if increase else None,
            projection=tuple(self._projection(pages)),
            components=tuple(self._components(pages)),
            expenditures=tuple(self._expenditures(pages)),
        )

    @staticmethod
    def _projection(pages: list[str]) -> list[ProjectionYear]:
        page = flat(next((p for p in pages if "Funding Model Projection" in p and "Percent" in p), ""))
        rows = re.findall(
            r"\b(20\d\d)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+(?:([\d,]+)\s+)?([\d,]+)\s+([\d,]+)\s+(\d+)%", page)
        found = []
        for year, cost, contribution, interest, spent, ending, funded, pct in rows:
            found.append(ProjectionYear(int(year), cents_of(cost), cents_of(contribution), cents_of(interest),
                                        cents_of(spent) or 0, cents_of(ending), cents_of(funded), round(int(pct) / 100, 3)))
        return found

    @staticmethod
    def _components(pages: list[str]) -> list[StudyComponent]:
        lines = _lines(pages, "Component Funding Summary")
        found: list[StudyComponent] = []
        category = ""
        text: str | None = None
        numbers: list[str] = []
        started = False

        def close() -> None:
            nonlocal text, numbers, category
            if text is None:
                return
            if text.endswith("unfunded"):
                found.append(StudyComponent(category, text[: -len("unfunded")].strip(), None, None, None, unfunded=True))
            elif len(numbers) in (6, 7):
                values = [cents_of(n) for n in numbers]
                cost, life, remaining = values[0], int(numbers[1].replace(",", "")), int(numbers[2].replace(",", ""))
                rest = values[3:] if len(numbers) == 7 else [0] + values[3:]
                found.append(StudyComponent(category, text, cost, life, remaining, rest[0], rest[1], rest[2], rest[3]))
            elif not numbers and not text.startswith(("Grand Total", "Percent Fully", "Current Average")):
                category = text.replace(" continued...", "")
            text, numbers = None, []

        for line in lines:
            if line == "Description":
                started = True
                continue
            if not started or line.startswith(("Mystique", "CALIFORNIA BUILDER", "PAGE ", "Component Funding Summary")):
                if line.startswith("Component Funding Summary"):
                    close()
                    started = False
                continue
            if _NUMBER.match(line):
                if text is not None:
                    numbers.append(line)
                continue
            close()
            if " - Total" in line or line.startswith(("Grand Total", "Percent Fully", "Current Average")):
                text, numbers = None, []
                # The totals' numbers follow; swallow them by leaving no open row.
                continue
            text = line
        close()
        return [c for c in found if c.description]

    @staticmethod
    def _expenditures(pages: list[str]) -> list[PlannedExpenditure]:
        lines = _lines(pages, "Annual Expenditure Detail")
        found: list[PlannedExpenditure] = []
        year = None
        category = ""
        pending: str | None = None
        for line in lines:
            match = re.match(r"Replacement Year\s+(20\d\d)", line)
            if match:
                year, pending = int(match.group(1)), None
                continue
            if year is None or line.startswith(("Mystique", "CALIFORNIA BUILDER", "PAGE ", "Annual Expenditure Detail", "Description", "Total for")):
                pending = None
                continue
            if _NUMBER.match(line):
                if pending is not None:
                    found.append(PlannedExpenditure(year, category, pending, cents_of(line)))
                    pending = None
                continue
            if pending is not None:
                # A text line after a text line: the first was a category heading.
                category = pending
            pending = line
            if " - " not in line:
                category, pending = line, None
        return found


def _long_date(text: str) -> date | None:
    months = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")
    m = re.fullmatch(r"([A-Z][a-z]+) (\d{1,2}), (\d{4})", text.strip())
    if m and m.group(1) in months:
        return date(int(m.group(3)), months.index(m.group(1)) + 1, int(m.group(2)))
    return None


class DisclosureOnly(StudyReader):
    """Any other preparer: the statutory disclosure, the preparer's name, and the study's date and level when stated."""

    preparer = ""

    def matches(self, pages: list[str]) -> bool:
        return True

    def read(self, pages: list[str], source: str) -> ReserveStudy:
        text = flat("\n".join(pages))
        head = flat("\n".join(pages[:2]))
        preparer = ""
        for name in ("The Helsing Group", "Browning Reserve Group", "California Builder Services", "Association Reserves", "Reserve Studies Inc"):
            if name.lower() in head.lower() or name.lower() in text[:20000].lower():
                preparer = name
                break
        level = None
        if re.search(r"w/o site visit|without site[- ]visit", head, re.I):
            level = StudyLevel.UPDATE_WITHOUT_SITE_VISIT
        elif re.search(r"with site visit", head, re.I):
            level = StudyLevel.UPDATE_WITH_SITE_VISIT
        elif re.search(r"full (reserve )?study|level i\b", head, re.I):
            level = StudyLevel.FULL
        units = re.search(r"total of (\d+) Units", text, re.I) or re.search(r"Total Units:?\s+(\d+)", text, re.I)
        dates = [d for d in (_long_date(x) for x in re.findall(r"([A-Z][a-z]+ \d{1,2}, 20\d\d)", head)) if d]
        disclosure = read_disclosure(text)
        fiscal = disclosure.fiscal_year
        prepared_for = re.search(r"Prepared for (?:the )?(?:FY )?(20\d\d) Fiscal Year|for use in future budgeting beginning:?\s*(?:\d{1,2}/\d{1,2}/)?(20\d\d)|Prepared for FY (20\d\d)", head, re.I)
        if fiscal is None and prepared_for:
            fiscal = int(next(g for g in prepared_for.groups() if g))
        # A cover page also prints the period the study serves; the study was prepared before that period began.
        before = [d for d in dates if fiscal is None or d < date(fiscal, 1, 1)]
        prepared = max(before) if before else (dates[0] if dates else None)
        contribution = re.search(r"Reserve Contribution for (20\d\d) is:?\s*" + _MONEY, text, re.I)
        return ReserveStudy(
            preparer=preparer or "unknown preparer",
            prepared=prepared,
            fiscal_year=fiscal,
            level=level,
            units=int(units.group(1)) if units else None,
            source=source,
            disclosure=disclosure,
            monthly_contribution_cents=round(cents_of(contribution.group(2)) / 12) if contribution else None,
            notes=("only the statutory disclosure is read; no reader knows this preparer's tables",),
        )


class HelsingGroup(DisclosureOnly):
    """The Helsing Group: "Level III Funding Update"; the plan is the disclosure notes' 30-year projection summary.

    Each row prints ending balance, fully funded balance, percent funded, contribution, special assessments,
    interest, and expenses (negative), then the fiscal year.
    """

    preparer = "The Helsing Group"

    def matches(self, pages: list[str]) -> bool:
        head = flat("\n".join(pages[:2]))
        return "Helsing" in head and "Funding Update" in head

    def read(self, pages: list[str], source: str) -> ReserveStudy:
        base = super().read(pages, source)
        page = flat(next((p for p in pages if "Reserve Fund Projections (Summary)" in p), ""))
        rows = re.findall(r"\$([\d,]+)\s+\$([\d,]+)\s+([\d.]+)%\s+\$([\d,.]+)\s+\$([\d,.]+)\s+\$([\d,]+)\s+\$(-?[\d,]+)\s+(20\d\d)", page)
        projection = tuple(
            ProjectionYear(int(year), 0, cents_of(contribution), cents_of(interest), abs(cents_of(spent.lstrip("-")) or 0),
                           cents_of(ending), cents_of(funded), round(float(pct) / 100, 3))
            for ending, funded, pct, contribution, _special, interest, spent, year in rows)
        begin = base.disclosure.current_balance_cents
        return replace(base, preparer=self.preparer, projection=projection, beginning_balance_cents=begin,
                       components=tuple(self._components(pages)),
                       notes=("the plan is the disclosure's 30-year projection; components are the Detailed Component List",))

    @staticmethod
    def _components(pages: list[str]) -> list[StudyComponent]:
        """The Detailed Component List: a category line, then rows of name, unit cost, useful life, remaining life,
        expected life, current cost, future cost, and quantity."""
        found: list[StudyComponent] = []
        for page in pages:
            if "Detailed Component List" not in page:
                continue
            lines = [line.strip() for line in page.splitlines() if line.strip()]
            texts: list[str] = []
            category = ""
            i = 0
            while i < len(lines):
                row = lines[i:i + 8]
                if (len(row) >= 7 and row[0].startswith("$") and all(re.fullmatch(r"\d+", x) for x in row[1:4])
                        and row[4].startswith("$") and row[5].startswith("$")):
                    if len(texts) >= 2 and not texts[-2].startswith("Subtotal"):
                        category = texts[-2]
                    name = texts[-1] if texts else ""
                    # The quantity is one line ("1 Lot", "49,575 S.F.") or two (the number, then the unit).
                    one_line = bool(re.search(r"[A-Za-z]", row[6])) or len(row) == 7
                    quantity = row[6] if one_line else f"{row[6]} {row[7]}"
                    found.append(StudyComponent(
                        category, f"{category}: {name}" if category else name, cents_of(row[5].replace("$", "").strip()),
                        int(row[1]), int(row[2]), current_cost_cents=cents_of(row[4].replace("$", "").strip()), quantity=quantity))
                    texts = []
                    i += 7 if one_line else 8
                    continue
                if not lines[i].startswith(("$", "Subtotal")) and not re.fullmatch(r"[\d,.\s]+", lines[i]):
                    texts.append(lines[i])
                elif lines[i].startswith("Subtotal"):
                    texts = ["Subtotal"]
                i += 1
        return found

    def read_layout(self, words: list[list[tuple]], study: ReserveStudy) -> ReserveStudy:
        if study.expenditures:
            return study
        found = schedule_expenditures(words)
        return replace(study, expenditures=found, notes=study.notes + (
            "expenditures are the \"Estimated Expenditure Schedule\" pages, read by the words' positions (the text layer "
            "prints the columns out of order), kept for each year whose items add to the page's Grand Total",)) if found else study


_AMOUNT = re.compile(r"\$[\d,]+")


def schedule_expenditures(words: list[list[tuple]]) -> tuple[PlannedExpenditure, ...]:
    """Helsing's "Estimated Expenditure Schedule from 2024 to 2033": a header of ten years, then per component a name
    at the left margin and ten amounts (on the name's line, or split onto the line under it), then "Grand Total:".

    Words are grouped into lines by their vertical middle; an amount goes to the year whose header starts nearest its
    left edge. A year is kept only when its components add to the Grand Total printed under it, within the whole-dollar
    rounding of its items."""
    found: list[PlannedExpenditure] = []
    for page in words:
        if not any(w[4] == "Expenditure" for w in page) or not any(w[4] == "Schedule" for w in page):
            continue
        # A line is the words whose middles lie within two points of the line's first word (a header's years can sit
        # a point apart).
        ys: list[float] = []
        ordered: list[list[tuple]] = []
        for mid, x0, word in sorted(((y0 + y1) / 2, x0, word) for x0, y0, _x1, y1, word, *_rest in page):
            if ys and mid - ys[-1] <= 2:
                ordered[-1].append((x0, word))
            else:
                ys.append(mid)
                ordered.append([(x0, word)])
        ordered = [sorted(row) for row in ordered]
        header = next((row for row in ordered if sum(bool(re.fullmatch(r"20\d\d", w)) for _x, w in row) >= 3
                       and not any(w == "from" for _x, w in row)), None)
        if header is None:
            continue
        columns = [(x, int(w)) for x, w in header if re.fullmatch(r"20\d\d", w)]
        left = min(x for x, _y in columns)

        def year_at(x: float) -> int:
            return min(columns, key=lambda c: abs(c[0] - x))[1]

        rows: list[tuple[str, dict[int, int]]] = []
        totals: dict[int, int] = {}
        last_y = -100
        for y, row in zip(ys, ordered):
            label = " ".join(w for x, w in row if x < left - 20 and not _AMOUNT.fullmatch(w))
            amounts = [(x, cents_of(w)) for x, w in row if _AMOUNT.fullmatch(w)]
            if label.endswith("Total:"):
                totals = {year_at(x): c for x, c in amounts}
                continue
            if label and amounts is not None and not re.fullmatch(r"[\d\s]+", label):
                if not amounts and not rows:
                    continue
                rows.append((label, {}))
            elif not (rows and amounts and y - last_y <= 6):
                continue
            if rows:
                for x, c in amounts:
                    rows[-1][1][year_at(x)] = c
            last_y = y
        rows = [(name, costs) for name, costs in rows if costs]
        for year, total in totals.items():
            # Each amount prints in whole dollars and the total rounds the unrounded sum: half a dollar per item.
            items = sum(1 for _n, costs in rows if costs.get(year))
            if abs(sum(costs.get(year, 0) for _n, costs in rows) - total) > max(100, 50 * items):
                continue
            for name, costs in rows:
                if costs.get(year):
                    category = name.split(",")[0].split("/")[0].strip()
                    found.append(PlannedExpenditure(year, category, name, costs[year]))
    return tuple(sorted(found, key=lambda e: (e.year, e.description)))


class BrowningReserveGroup(DisclosureOnly):
    """Browning Reserve Group: Section IV, "30 Year Reserve Funding Plan Including Fully Funded Balance and % Funded".

    Each row prints the year, beginning balance, fully funded balance, percent funded, inflated expenditures,
    contribution, special assessments and other contributions, interest, and ending balance.
    """

    preparer = "Browning Reserve Group"

    def matches(self, pages: list[str]) -> bool:
        return "Browning Reserve Group" in flat("\n".join(pages[:6]))

    def read(self, pages: list[str], source: str) -> ReserveStudy:
        base = super().read(pages, source)
        pattern = r"\b(20\d\d)\s+([\d,]+)\s+([\d,]+)\s+([\d.]+)%\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)"
        # The table of contents names the section too; the plan is the page with the most rows.
        rows = max((re.findall(pattern, flat(p)) for p in pages if "Including Fully Funded Balance" in p), key=len, default=[])
        projection = tuple(
            ProjectionYear(int(year), 0, cents_of(contribution), cents_of(interest), cents_of(spent), cents_of(ending),
                           cents_of(funded), round(float(pct) / 100, 3))
            for year, _begin, funded, pct, spent, contribution, _special, interest, ending in rows)
        begin = next((cents_of(b) for year, b, *_rest in rows if base.fiscal_year and int(year) == base.fiscal_year), None)
        return replace(base, preparer=self.preparer, projection=projection, beginning_balance_cents=begin,
                       components=tuple(self._components(pages)), expenditures=by_year_expenditures("\n".join(pages)),
                       notes=("the plan is Section IV's 30-year funding plan; components are Section VII's tabular listing; "
                              "expenditures are the \"Expenditures by Year\" schedule, kept for each year whose items add to its total",))

    @staticmethod
    def _components(pages: list[str]) -> list[StudyComponent]:
        """Section VII, Component Tabular Listing: a group line ("Paving" over "01000 -"), then per component
        "NNN - Name", quantity, unit cost ("$.22/SqFt"), useful life, current cost, remaining life, an optional
        share ("(50%)"), and the location."""
        found: list[StudyComponent] = []
        for page in pages:
            if "Component Tabular Listing" not in page:
                continue
            lines = [line.strip() for line in page.splitlines() if line.strip()]
            group = ""
            for i, line in enumerate(lines):
                if re.fullmatch(r"\d{5} -", line) and i > 0:
                    group = lines[i - 1]
                    continue
                named = re.fullmatch(r"(\d{3}) - (.+)", line)
                row = lines[i + 1:i + 7]
                if not named or len(row) < 5:
                    continue
                quantity, unit, life, current, remaining = row[:5]
                if not (re.fullmatch(r"[\d,.]+", quantity) and unit.startswith("$") and re.fullmatch(r"\d+", life)
                        and current.startswith("$") and re.fullmatch(r"\d+", remaining)):
                    continue
                share = row[5] if len(row) > 5 and re.fullmatch(r"\(\d+(?:\.\d+)?%\)", row[5]) else ""
                found.append(StudyComponent(
                    group, f"{group}: {named.group(2)}" + (f" {share}" if share else ""), None, int(life), int(remaining),
                    current_cost_cents=cents_of(current), quantity=f"{quantity} at {unit}"))
        return found


def _whole(text: str) -> int:
    return int(text.replace(",", "")) * 100


def by_year_expenditures(text: str) -> tuple[PlannedExpenditure, ...]:
    """Browning Reserve Group's "Expenditures by Year - Next 6 Years": under each year, a group ("Paving" over "01000 -"),
    then per component "NNN - Name", its description, current cost, useful life, and (after the first year) the inflated
    cost; each year ends in its current-cost total and "Total  2023:". A year is kept only when its components' current
    costs add to that total; each keeps its inflated cost, as the other readers do."""
    start = text.find("Expenditures by Year - Next")
    if start < 0:
        return ()
    stop = re.search(r"\nSection (?:VIII|IX|X)\b", text[start:])
    lines = [line.strip() for line in text[start: start + stop.start() if stop else len(text)].splitlines()]
    found: list[PlannedExpenditure] = []
    year: int | None = None
    group = ""
    current: list[tuple[int, PlannedExpenditure]] = []
    number = re.compile(r"[\d,]+")
    for i, line in enumerate(lines):
        total = re.fullmatch(r"Total\s+(20\d\d):", line)
        if total and year == int(total.group(1)):
            printed = _whole(lines[i - 1]) if i and number.fullmatch(lines[i - 1]) else None
            if printed is not None and sum(cost for cost, _e in current) == printed:
                found += [e for _cost, e in current]
            current = []
        elif re.fullmatch(r"20\d\d", line):
            if int(line) != year:
                year, current = int(line), []
        elif re.fullmatch(r"\d{5} -", line) and i:
            group = lines[i - 1]
        elif (named := re.fullmatch(r"\d{3} - (.+)", line)) and year and i + 3 < len(lines):
            cost, life = lines[i + 2], lines[i + 3]
            if number.fullmatch(cost) and re.fullmatch(r"\d+", life):
                # In the study's first year the inflated cost is the current cost and is not printed; a number followed by
                # a "Total" line is the group's total.
                after = lines[i + 4] if i + 4 < len(lines) else ""
                following = lines[i + 5] if i + 5 < len(lines) else ""
                inflated = _whole(after) if number.fullmatch(after) and not following.startswith("Total") else _whole(cost)
                current.append((_whole(cost), PlannedExpenditure(year, group, f"{named.group(1)}: {lines[i + 1]}", inflated)))
    return tuple(found)


READERS: tuple[StudyReader, ...] = (CaliforniaBuilderServices(), HelsingGroup(), BrowningReserveGroup(), DisclosureOnly())


def read_pages(pages: list[str], source: str = "") -> ReserveStudy:
    reader = next(r for r in READERS if r.matches(pages))
    return reader.read(pages, source)


def read_study(path: str | Path) -> ReserveStudy:
    """Read a study PDF with the first reader that knows its preparer."""
    import pymupdf

    with pymupdf.open(str(path)) as doc:
        pages = [page.get_text() for page in doc]
        words = [page.get_text("words") for page in doc]
    reader = next(r for r in READERS if r.matches(pages))
    return reader.read_layout(words, reader.read(pages, str(path)))


__all__ = [
    "StudyLevel", "DisclosureYear", "ReserveDisclosure", "ProjectionYear", "StudyComponent", "PlannedExpenditure",
    "ReserveStudy", "StudyReader", "CaliforniaBuilderServices", "DisclosureOnly", "READERS", "read_disclosure",
    "read_pages", "read_study", "cents_of", "field",
]
