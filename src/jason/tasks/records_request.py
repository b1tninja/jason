"""Build the copy-order list: the recorded instruments the association's records lack, priced.

Reads the governing extracts on disk for their stamps, the Drive pins for
their numbers, and the association's record for what it names. Page
counts come from the stamps, from the index cache when a detail was
fetched, and, with ``fetch_pages``, from the county index now.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path

from jason.community.index_cache import IndexCache
from jason.community.readings import numbers_on_disk, read_folder
from jason.community.records_request import RequestRow, request_dicts, request_markdown, request_rows
from jason.tasks.read_scans import model_read_numbers

_NUMBER = re.compile(r"\b((?:19|20)\d{10})\b")


@dataclass
class RecordsRequestReport:
    rows: tuple[RequestRow, ...] = ()
    written: tuple[Path, ...] = ()
    fetched_pages: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def cost_cents(self) -> int:
        return sum(row.cost_cents for row in self.rows)

    def summary(self) -> str:
        return f"records request rows={len(self.rows)} cost=${self.cost_cents / 100:,.2f} pagesFetched={self.fetched_pages} files={len(self.written)} errors={len(self.errors)}"


def copies_on_disk(community, root: Path) -> set[str]:
    """Every instrument number a recorded copy on disk or a Drive pin carries."""
    found: set[str] = set()
    folders = (
        root / "artifacts" / "site-docs" / "governing_documents",
        root / "artifacts" / "site-docs" / "governing_documents_Annexations",
        root / "artifacts" / "site-docs" / "deeds",
        root / "payhoa-files" / "documents",
        root / "governing",
    )
    found.update(numbers_on_disk(read_folder(*folders)))
    for folder in (root / "artifacts" / "site-docs", root / "payhoa-files", root / "governing"):
        if folder.is_dir():
            for path in folder.rglob("*"):
                if path.is_file():
                    found.update(_NUMBER.findall(path.name))
    for pin in community.pins():
        found.update(_NUMBER.findall(pin.title))
    return found


def page_counts(root: Path, numbers: tuple[str, ...], *, fetch_live: bool = False, recorder=None) -> tuple[dict[str, int], int, list[str]]:
    """Page counts from the stamps on disk, the cache, and, when asked, the index detail."""
    pages: dict[str, int] = {}
    for reading in read_folder(root / "artifacts" / "site-docs" / "governing_documents", root / "artifacts" / "site-docs" / "governing_documents_Annexations", root / "governing"):
        if reading.number and reading.stamp.pages:
            pages[reading.number] = reading.stamp.pages
    fetched = 0
    errors: list[str] = []
    with IndexCache(root / "index-cache.db") as cache:
        for number in numbers:
            if number in pages:
                continue
            cached = cache.pages_of(number)
            if cached:
                pages[number] = cached
                continue
            if not fetch_live or recorder is None:
                continue
            try:
                rows = recorder.search(number=number, limit=3)
                row = next((r for r in rows if r.number == number), None)
                detail = recorder.detail(row.internal_id) if row is not None and row.internal_id else None
            except Exception as exc:
                errors.append(f"{number}: {exc}")
                continue
            if detail is not None and detail.pages:
                pages[number] = detail.pages
                cache.set_pages(number, detail.pages)
                fetched += 1
    return pages, fetched, errors


def build_records_request(community, root: Path, record, *, out_dir: Path | None = None, fetch_pages: bool = False, recorder=None, include_liens: bool = True) -> RecordsRequestReport:
    on_disk = copies_on_disk(community, root)
    draft = request_rows(record, on_disk=on_disk, include_liens=include_liens)
    pages, fetched, errors = page_counts(root, tuple(row.number for row in draft), fetch_live=fetch_pages, recorder=recorder)
    rows = request_rows(record, on_disk=on_disk, pages=pages, include_liens=include_liens, model_read=model_read_numbers(root))
    written: list[Path] = []
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        page = out_dir / "records-request.md"
        page.write_text(request_markdown(rows, title=f"{community.name}: recorded copies to order"), encoding="utf-8")
        written.append(page)
        table = out_dir / "records-request.csv"
        with table.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["priority", "number", "book", "page", "recorded", "title", "role", "why", "pages", "pagesEstimated", "certified", "costCents", "modelRead"])
            writer.writeheader()
            for row in request_dicts(rows):
                writer.writerow(row)
        written.append(table)
    return RecordsRequestReport(rows, tuple(written), fetched, errors)
