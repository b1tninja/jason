"""Helpers the financial models share: signed amounts as printed, the file's own period, and the specification's bank
accounts. Nothing here registers a model."""

from __future__ import annotations

import calendar
import json
import re
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

from jason.community.document_models import ModelContext
from jason.community.invoices import parse_date

# "$1,234.56", "-$758.27", "$-19,851.29", "(5,476.60)", "-1,076.13", "1,234"
_SIGNED = re.compile(r"(\()?\s*(-)?\s*\$?\s*(-)?\s*(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d\d))?\s*(\))?")
MONEY_LINE = r"\(?-?\$?\s?-?(?:\d{1,3}(?:,\d{3})+|\d+)\.\d\d\)?"
WHOLE_LINE = r"\(?-?\$?\s?-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d\d)?\)?"
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November",
          "December")


def signed_cents(text: str | None) -> int | None:
    """An amount as printed, with its sign: a leading minus or parentheses make it negative."""
    if not text:
        return None
    m = _SIGNED.search(text)
    if not m:
        return None
    value = int(m.group(4).replace(",", "")) * 100 + int(m.group(5) or 0)
    negative = bool(m.group(2) or m.group(3) or (m.group(1) and m.group(6)))
    return -value if negative else value


def line_amount(label: str, text: str, *, whole: bool = False, start: int = 0, end: int | None = None) -> int | None:
    """The amount on the line right after a line that is ``label`` (a regex), as signed cents."""
    pattern = re.compile(r"(?:^|\n)[ \t]*" + label + r"[ \t]*\n[ \t]*(" + (WHOLE_LINE if whole else MONEY_LINE) + r")[ \t]*(?:\n|$)", re.I)
    m = pattern.search(text or "", start, len(text or "") if end is None else end)
    return signed_cents(m.group(1)) if m else None


def month_end(year: int, month: int) -> date:
    return date(year, month, calendar.monthrange(year, month)[1])


def long_date(text: str) -> date | None:
    """"November 30, 2025", "Nov 30, 2025", "Nov 1, 2025"."""
    return parse_date(re.sub(r"\s+", " ", text or "").strip())


def file_period(context: ModelContext) -> str:
    """The period the library gave the file ("2025-06"), else the one its name carries."""
    if context.period:
        return context.period
    m = re.search(r"(20\d\d)[-_ .](\d\d)\b", context.name or "")
    return f"{m.group(1)}-{m.group(2)}" if m else ""


def spec_bank_accounts(context: ModelContext) -> tuple[Any, ...]:
    accounts = getattr(context.community, "bank_accounts", None)
    if accounts is None:
        return ()
    try:
        return tuple(accounts() if callable(accounts) else accounts)
    except Exception:
        return ()


def spec_units(context: ModelContext) -> int | None:
    units = getattr(context.community, "units", None)
    if units is None:
        return None
    try:
        return len(units() if callable(units) else units)
    except Exception:
        return None


@lru_cache(maxsize=16)
def _json(path: str, mtime: float) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def data_json(context: ModelContext, relative: str) -> Any:
    """A JSON file under the data directory, read once per change; None when absent."""
    if context.data_dir is None:
        return None
    path = Path(context.data_dir) / relative
    if not path.is_file():
        return None
    try:
        return _json(str(path), path.stat().st_mtime)
    except (OSError, ValueError):
        return None


@lru_cache(maxsize=4)
def _studies(data_dir: str) -> tuple[Any, ...]:
    from jason.tasks.reserves import load_studies

    try:
        return tuple(load_studies(Path(data_dir)))
    except Exception:
        return ()


def disk_studies(context: ModelContext) -> tuple[Any, ...]:
    """Every reserve study on disk (``jason.tasks.reserves.load_studies``), oldest fiscal year first; read once per run."""
    return _studies(str(context.data_dir)) if context.data_dir is not None else ()


def dollars(cents: int | None) -> str:
    if cents is None:
        return "-"
    return f"-${abs(cents) / 100:,.2f}" if cents < 0 else f"${cents / 100:,.2f}"


__all__ = ["signed_cents", "line_amount", "month_end", "long_date", "file_period", "spec_bank_accounts", "spec_units", "data_json",
           "disk_studies", "dollars", "MONEY_LINE", "WHOLE_LINE", "MONTHS"]
