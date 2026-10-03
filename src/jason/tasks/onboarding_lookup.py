"""Leads for a new association from public sources jason reads without credentials: the questions a lookup prefills.

``jason onboard --new KEY --lookup`` (or ``jason onboard --lookup`` for the active profile) searches the county
recorder's public index for the association's name, read-only, through the county's existing reader
(``jason.community.recorder`` and the other counties' readers; this module adds no scraping). What it finds becomes
**leads**: each a question with the found value as jason's suggestion, kept under ``leads`` in the profile's private
facts file (``data/spec/<profile>.json``). The session (``jason.tasks.onboarding_session.lead_asks``) asks each one as
a ``FACT`` question while its checklist item is not present. A lead is never written into the profile: a person
answers, a second person confirms where it is high stakes, and ``jason onboard --apply`` turns the answer into a
proposed change for a person to apply.

A recorder hit is not a pin. The index lists what was recorded under a name; whether a document is the association's
declaration is read from the recorded copy.

The Secretary of State's business search has no reader in jason, so no lead comes from it: the corporate filings stay
questions for a person (the checklist's corporate group).
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from jason.community.onboarding import LEADS

SEARCH_LIMIT = 300                 # index rows read for one name, at most
CHOICES = 6                        # instruments offered as choices, at most


def _sacramento() -> Any:
    from jason.community.recorder import Sacramento

    return Sacramento.county_recorder


def _placer() -> Any:
    from jason.community.placer.recorder import Placer

    return Placer.county_recorder


# The counties with a public index reader in jason, by the county's name in lowercase with words joined by "-".
READERS: dict[str, Callable[[], Any]] = {"sacramento": _sacramento, "placer": _placer}


def county_key(county: str) -> str:
    """``"Sacramento County"`` -> ``"sacramento"``; ``"San Luis Obispo"`` -> ``"san-luis-obispo"``."""
    words = [w for w in re.split(r"[^a-z0-9]+", county.lower()) if w and w != "county"]
    return "-".join(words)


def region_for(county: str) -> str:
    """The profile's ``region`` for a California county (``"ca/sacramento"``), or "" when none is given."""
    key = county_key(county)
    return f"ca/{key}" if key else ""


def reader_for(county: str) -> Any | None:
    """The county recorder's public index reader, or None when jason has none for that county (or it cannot load)."""
    make = READERS.get(county_key(county))
    if make is None:
        return None
    try:
        return make()
    except Exception:  # noqa: BLE001 - a reader that cannot load is no reader: the lookup says so
        return None


# --- What the index rows say -------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Shelf:
    """One kind of recorded instrument a lead asks about: the checklist item it serves, the words its filing name
    carries, and what the answer fills."""

    key: str
    item: str
    words: tuple[str, ...]
    method: str
    stakes: bool
    question: str
    all_choice: bool                 # a series: "all N listed" is a choice


# In match order: an annexation's filing name may also say declaration, an amendment's may say restriction.
SHELVES: tuple[Shelf, ...] = (
    Shelf("annexations", "annexations", ("ANNEX",), "pins", False,
          "The county recorder's index lists these annexation instruments under the association's name. Which are "
          "the association's supplementary declarations?", True),
    Shelf("amendments", "amendments", ("AMEND",), "ccrs", True,
          "The county recorder's index lists these amendments under the association's name. Which are amendments to "
          "the association's declaration that were recorded and are in force?", True),
    Shelf("condominium-plans", "condominium-plans", ("CONDOMINIUM PLAN", "CONDO PLAN"), "pins", False,
          "The county recorder's index lists these condominium plans under the association's name. Which define the "
          "association's units?", True),
    Shelf("bylaws", "bylaws", ("BYLAW",), "pins", False,
          "The county recorder's index lists bylaws recorded under the association's name. Is one of these the "
          "association's bylaws?", False),
    Shelf("declaration", "declaration", ("DECLARATION", "RESTRICTION", "COVENANT"), "ccrs", True,
          "The county recorder's index lists these declarations under the association's name. Which is the "
          "association's declaration (the one later amendments amend)?", False),
)


def shelf_of(filing_name: str) -> Shelf | None:
    upper = filing_name.upper()
    return next((s for s in SHELVES if any(w in upper for w in s.words)), None)


def _row_choice(row: Any) -> str:
    day = row.recorded.isoformat() if getattr(row, "recorded", None) else "undated"
    return f"{row.number} ({day}, {str(row.filing_name).strip() or row.filing_code})"


def leads_from_rows(name: str, query: str, rows: Iterable[Any], *, source: str, found: str) -> list[dict[str, Any]]:
    """The leads one name search gives: one per kind of governing instrument found, and the name the index spells
    the association by. Counts, document numbers, dates, and the association's own spellings only: no other party's
    name is kept (a lien names an owner)."""
    rows = [r for r in rows if getattr(r, "number", "")]
    seen: set[str] = set()
    unique = []
    for r in sorted(rows, key=lambda r: (getattr(r, "recorded", None) or date.max, r.number)):
        if r.number not in seen:
            seen.add(r.number)
            unique.append(r)
    filings = Counter(str(r.filing_name).strip() or str(r.filing_code) for r in unique)
    summary = (f"the index lists {len(unique)} instrument{'' if len(unique) == 1 else 's'} under {query!r}"
               + (": " + ", ".join(f"{n} {f}" for f, n in filings.most_common(6)) if filings else ""))
    caveat = "A hit is not a pin: the recorded copy is read before it is pinned."
    out: list[dict[str, Any]] = []
    for shelf in SHELVES:
        hits = [r for r in unique if shelf_of(str(r.filing_name)) is shelf]
        if not hits:
            continue
        choices = [_row_choice(r) for r in hits[:CHOICES]]
        if shelf.all_choice and len(hits) > 1:
            choices.insert(0, f"all {len(hits)} listed")
        choices.append("none of these: dismiss")
        suggestion = choices[0]
        out.append({"key": shelf.key, "item": shelf.item, "method": shelf.method, "stakes": shelf.stakes,
                    "question": shelf.question, "choices": choices, "suggestion": suggestion, "source": source,
                    "found": found, "evidence": [summary, f"{len(hits)} filed as {shelf.key.replace('-', ' ')}"
                                                 + (f"; the first {CHOICES} by date are listed" if len(hits) > CHOICES
                                                    else ""), caveat]})
    spellings: Counter = Counter()
    for r in unique:
        for party in getattr(r, "names", ()) or ():
            text = " ".join(str(party).upper().split())
            if text.startswith(query.upper()):
                spellings[text] += 1
    if spellings:
        ranked = [s for s, _ in spellings.most_common(CHOICES)]
        out.append({"key": "indexed-name", "item": "recorded-liens", "method": "index_association",
                    "stakes": False,
                    "question": (f"The county recorder's index spells {name!r} these ways. Which spelling is the "
                                 f"association's, so the title watch finds the liens it records and the instruments "
                                 f"recorded under its name?"),
                    "choices": ranked + ["none of these: dismiss"], "suggestion": ranked[0], "source": source,
                    "found": found,
                    "evidence": [summary, "spellings: " + "; ".join(f"{s} ({n})" for s, n in spellings.most_common(4)),
                                 caveat]})
    return out


@dataclass
class Lookup:
    """What one lookup found, and what it could not read."""

    leads: list[dict[str, Any]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def lookup(name: str, county: str, *, recorder: Any = None, today: date | None = None,
           limit: int = SEARCH_LIMIT) -> Lookup:
    """Search the county recorder's public index for the association's name, read-only. ``recorder`` replaces the
    county's reader (tests). A county with no reader, or an index that cannot be read, is a note, not a failure."""
    from jason.community.recorder import index_name

    out = Lookup()
    out.notes.append("Secretary of State: jason has no reader for the business search; the corporate filings are "
                     "asked of a person.")
    if not county.strip():
        out.notes.append("county recorder: no county given (--county), so the index was not searched.")
        return out
    reader = recorder if recorder is not None else reader_for(county)
    label = f"{county_key(county).replace('-', ' ').title()} County recorder's public index"
    if reader is None:
        out.notes.append(f"county recorder: jason has no reader for {county!r} "
                         f"(readers: {', '.join(sorted(READERS))}); nothing was searched.")
        return out
    query = index_name(name)
    if not query:
        out.notes.append(f"county recorder: {name!r} gives no index query.")
        return out
    try:
        rows = tuple(reader.search(name=query, limit=limit))
    except Exception as exc:  # noqa: BLE001 - a public source that fails is a note; the questions stay a person's
        out.notes.append(f"county recorder: the search for {query!r} failed ({type(exc).__name__}); nothing was "
                         f"found.")
        return out
    day = (today or date.today()).isoformat()
    out.leads = leads_from_rows(name, query, rows, source=label, found=day)
    out.notes.append(f"county recorder: searched {query!r}: {len(rows)} rows"
                     + (f" (stopped at {limit})" if len(rows) >= limit else "") + f", {len(out.leads)} leads.")
    return out


# --- Where leads are kept ------------------------------------------------------------------------------------------------

def save_leads(profile: str, leads: list[dict[str, Any]], *, spec_dir: Path | None = None) -> Path:
    """Merge leads into ``<spec dir>/<profile>.json`` under ``leads``: a new lookup's lead replaces the one with the
    same key, the others stay, and the answered facts are not touched. The file is copied to ``backups/`` first when
    it changes."""
    from jason.community.private import spec_dir as default_spec_dir
    from jason.locks import Resource, hold

    folder = Path(spec_dir) if spec_dir is not None else default_spec_dir()
    path = folder / f"{profile}.json"
    with hold(Resource.STORE, f"spec-{profile}", timeout=120, purpose="onboarding leads"):
        before = path.read_text(encoding="utf-8") if path.is_file() else ""
        data = json.loads(before) if before.strip() else {}
        if not isinstance(data, dict):
            raise ValueError(f"{path.name} is not a JSON object; fix it by hand")
        fresh = {lead["key"]: lead for lead in leads}
        kept = [lead for lead in data.get(LEADS) or () if isinstance(lead, dict) and lead.get("key") not in fresh]
        data[LEADS] = kept + list(fresh.values())
        after = json.dumps(data, indent=1, ensure_ascii=False) + "\n"
        if after == before:
            return path
        if before.strip():
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            backup = folder / "backups" / f"{profile}-{stamp}.json"
            backup.parent.mkdir(parents=True, exist_ok=True)
            backup.write_text(before, encoding="utf-8")
        folder.mkdir(parents=True, exist_ok=True)
        path.write_text(after, encoding="utf-8")
    return path


__all__ = ["CHOICES", "Lookup", "READERS", "SEARCH_LIMIT", "SHELVES", "Shelf", "county_key", "leads_from_rows",
           "lookup", "reader_for", "region_for", "save_leads", "shelf_of"]
