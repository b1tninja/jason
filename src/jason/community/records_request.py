"""Which recorded instruments the association's records still lack, and what a copy order costs.

Civil Code section 5200 makes the governing documents association records,
and the association's own liens, the notices against it, and the
construction-period claims are the rest of its recorded story. A recorded
copy on disk is one whose stamp names the instrument (``readings``), or
whose file name prints the number, or that a Drive pin names. Everything
else the record names is a candidate for a copy order from the county
clerk/recorder, priced by the county's schedule: a plain copy is one fee
for the first page and one for each further page, a certified copy a
little more. The page count comes from the stamp when a copy is on disk,
else from the index detail when it was fetched into the cache, else it is
estimated and the row says so.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from jason.community.filings import Process

# Sacramento County Clerk/Recorder copy fees, from the county's page, read 2026-09-28.
PLAIN_FIRST_PAGE_CENTS = 800
PLAIN_EXTRA_PAGE_CENTS = 100
CERTIFIED_FIRST_PAGE_CENTS = 900
CERTIFIED_EXTRA_PAGE_CENTS = 100
# A page count the index has not given yet, for a first estimate; the row says it is an estimate.
ESTIMATED_PAGES = {"annexation": 7, "declaration": 60, "restatement or amendment": 8, "amendment": 8, "condominium plan": 20, "common area deed": 6}
DEFAULT_ESTIMATED_PAGES = 4

ORDER_FORM = "https://ccr.saccounty.gov/content/dam/ccr/documents/ORCopyOrderForm.pdf"
ORDER_PAGE = "https://ccr.saccounty.gov/us/en/recorded-document-copies.html"
MAIL_TO = "Sacramento County Clerk/Recorder, 3636 American River Drive, Suite 110, Sacramento, CA 95864"
FAX = "(916) 874-0947"
PHONE = "(916) 874-6334"


@dataclass(frozen=True)
class RequestRow:
    """One instrument to order: what to write on the form, why it is wanted, and what it costs."""

    number: str
    recorded: date | None
    title: str
    role: str
    why: str
    priority: int
    pages: int | None
    pages_estimated: bool
    certified: bool = False
    model_read: str = ""
    """The copy on disk a model read this instrument's stamp from; verify the stamp before dropping the order."""

    @property
    def book(self) -> str:
        """The county's book for a modern number: the recording date as eight digits."""
        return self.number[:8] if len(self.number) == 12 else ""

    @property
    def page(self) -> str:
        return self.number[8:] if len(self.number) == 12 else ""

    @property
    def page_count(self) -> int:
        return self.pages or ESTIMATED_PAGES.get(self.role, DEFAULT_ESTIMATED_PAGES)

    @property
    def cost_cents(self) -> int:
        first = CERTIFIED_FIRST_PAGE_CENTS if self.certified else PLAIN_FIRST_PAGE_CENTS
        extra = CERTIFIED_EXTRA_PAGE_CENTS if self.certified else PLAIN_EXTRA_PAGE_CENTS
        return first + extra * max(0, self.page_count - 1)


_WHY = {
    "declaration": ("the recorded declaration itself, the instrument every deed recites; the association's copy must be the recorded one", 1),
    "restatement or amendment": ("a recorded amendment or restatement of the declaration; the operative text of the sections it changes", 1),
    "amendment": ("a recorded amendment of the declaration; the operative text of the sections it changes", 1),
    "annexation": ("the annexation that brought a phase under the declaration; it names the units and common areas annexed and the easements reserved", 2),
    "condominium plan": ("the plan that draws the units and common areas the deeds convey", 2),
    "common area deed": ("the deed that gave the association a common-area parcel; title to what the association maintains", 2),
    "notice of completion": ("the developer's notice of completion; fixes the mechanic's lien deadlines for that building", 4),
}


def request_rows(
    record,
    *,
    on_disk: set[str] | frozenset[str],
    pages: dict[str, int] | None = None,
    include_liens: bool = True,
    certified_roles: tuple[str, ...] = ("declaration", "restatement or amendment", "amendment"),
    model_read: dict[str, dict[str, str]] | None = None,
) -> tuple[RequestRow, ...]:
    """The instruments the association's record names that have no recorded copy on disk, priced.

    ``model_read`` maps a number to the copy a model read it from; such a
    row stays on the list at the lowest priority, marked for a person to
    verify the stamp before it is dropped.
    """
    pages = pages or {}
    model_read = model_read or {}
    rows: list[RequestRow] = []
    seen: set[str] = set()
    for g in record.governing:
        if g.number in on_disk or g.number in seen:
            continue
        seen.add(g.number)
        why, priority = _WHY.get(g.role, (f"a recorded {g.role} naming the project", 3))
        if g.superseded_by:
            why = f"{why}; rescinded and superseded by {g.superseded_by}, wanted for the file, not for force"
            priority = max(priority, 3)
        read = model_read.get(g.number, {})
        if read:
            why = f"a copy on disk, {read.get('file')}, reads as this instrument to {read.get('model')} on {read.get('read')}; verify its stamp, then drop this row. {why}"
            priority = 4
        rows.append(RequestRow(g.number, g.recorded, g.filing, g.role, why, priority, pages.get(g.number), g.number not in pages, g.role in certified_roles, read.get("file", "")))
    if include_liens:
        for label, items, priority in (
            ("the association's own lien", record.placed, 2),
            ("a lien or notice against the association", record.against, 2),
            ("a construction-period claim against the developer", record.construction, 3),
        ):
            for e in items:
                for step in e.steps:
                    if step.number in on_disk or step.number in seen:
                        continue
                    seen.add(step.number)
                    why = f"{label}: {e.process.value}, {e.status}; the recorded instrument is the association's record of it"
                    if e.process is Process.ASSESSMENT_LIEN:
                        why += " and the collections file needs the recorded notice and release"
                    rows.append(RequestRow(step.number, step.recorded, step.filing, e.process.value, why, priority, pages.get(step.number), step.number not in pages))
        for item in record.notices:
            if item.number in on_disk or item.number in seen:
                continue
            seen.add(item.number)
            rows.append(RequestRow(item.number, item.recorded, f"{item.filing_code} {item.filing_name}".strip(), "notice", "a notice the association recorded", 3, pages.get(item.number), item.number not in pages))
    rows.sort(key=lambda row: (row.priority, row.recorded or date.min, row.number))
    return tuple(rows)


def request_markdown(rows: tuple[RequestRow, ...], *, title: str) -> str:
    total = sum(row.cost_cents for row in rows)
    estimated = sum(1 for row in rows if row.pages_estimated)
    lines = [f"# {title}", ""]
    lines.append(
        f"{len(rows)} recorded instruments the association's record names and no recorded copy on disk carries. "
        f"Ordered from the Sacramento County Clerk/Recorder at the county's fees, the set costs about ${total / 100:,.2f}"
        + (f"; {estimated} page counts are estimates and the total moves with them." if estimated else ".")
    )
    lines.append("")
    lines.append(f"Fees: a plain copy is ${PLAIN_FIRST_PAGE_CENTS / 100:.2f} for the first page and ${PLAIN_EXTRA_PAGE_CENTS / 100:.2f} for each further page; a certified copy is ${CERTIFIED_FIRST_PAGE_CENTS / 100:.2f} and ${CERTIFIED_EXTRA_PAGE_CENTS / 100:.2f}. The form asks for the book and page from the online index; for a twelve-digit number the book is the first eight digits and the page the last four. Order form: {ORDER_FORM}. Mail to {MAIL_TO}, fax {FAX}, or call {PHONE}. Fees and the form are as the county's page read on 2026-09-28; confirm before sending.")
    lines.append("")
    lines.append("| Priority | Document | Book | Page | Recorded | Title on the index | What it is | Why | Pages | Copy | Cost |")
    lines.append("| ---: | --- | --- | --- | --- | --- | --- | --- | ---: | --- | ---: |")
    for row in rows:
        pages = f"{row.page_count}{'*' if row.pages_estimated else ''}"
        lines.append(
            f"| {row.priority} | {row.number} | {row.book} | {row.page} | {row.recorded.isoformat() if row.recorded else ''} | {row.title} | {row.role} | {row.why} | {pages} | {'certified' if row.certified else 'plain'} | ${row.cost_cents / 100:,.2f} |"
        )
    lines.append("")
    lines.append("An asterisk marks an estimated page count. Priority 1 is the declaration and its amendments, 2 the annexations, plans, deeds, and the association's own liens, 3 the rest, and 4 an instrument a copy on disk may already be, by a model's reading of its stamp: verify that copy before ordering.")
    lines.append("")
    return "\n".join(lines)


def request_dicts(rows: tuple[RequestRow, ...]) -> list[dict[str, Any]]:
    return [
        {
            "number": row.number, "book": row.book, "page": row.page, "recorded": row.recorded.isoformat() if row.recorded else "",
            "title": row.title, "role": row.role, "why": row.why, "priority": row.priority,
            "pages": row.page_count, "pagesEstimated": row.pages_estimated, "certified": row.certified, "costCents": row.cost_cents,
            "modelRead": row.model_read,
        }
        for row in rows
    ]
