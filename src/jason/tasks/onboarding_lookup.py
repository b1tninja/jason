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


# --- The county's associations (asspy's directory) ----------------------------------------------------------------------

def directory_for(county: str) -> Any | None:
    """The county's association directory as ``python -m asspy.associations_cli <county> --survey`` built it, or None
    when the county has not been surveyed (no directory is created by asking)."""
    try:
        from asspy import County

        from jason.asspy_home import apply

        apply()                                   # ASSPY_HOME from the environment or jason's .env, before asspy reads it
        place = County(county_key(county).replace("-", "_"))
    except Exception:  # noqa: BLE001 - a county asspy does not know has no directory
        return None
    path = place.db_path.with_name("associations.db")
    return place.associations(path) if path.is_file() else None


def _association(item: Any) -> dict[str, Any]:
    return {
        "name": item.name,
        "kind": item.kind.value,
        "standing": item.standing.value,
        "first": item.first.isoformat() if item.first else "",
        "last": item.last.isoformat() if item.last else "",
        "spellings": [name for name, _ in item.names.most_common(6)],
        "evidence": dict(item.evidence),
    }


def known_associations(county: str, words: str = "") -> list[dict[str, Any]]:
    """The owners', commercial, and maintenance associations the county's index shows, for a person to choose from:
    name, kind, standing (confirmed: it records assessment liens or its declaration), the years it recorded, its
    spellings, and the evidence. ``words`` narrows to names holding every word. A row is a lead, not a pin."""
    directory = directory_for(county)
    if directory is None:
        return []
    with directory:
        chosen = {item.key for item in directory.all()}
        rows = directory.find(words) if words.strip() else directory.all()
        return [_association(item) for item in rows if item.key in chosen]


SEARCH_RESULTS = 25                # directory rows a search returns by default
DIRECTORY_CAVEATS = (
    "A row is a lead, not a pin: the directory reads names on the county recorder's public index, not the "
    "association's own records.",
    "Standing is the index's evidence: confirmed means it records assessment liens or a declaration; likely means "
    "other association business; neither says the association is active today.",
    "The directory holds only the months its survey read; an association that recorded nothing in them is not listed.",
)


def survey_command(county: str) -> str:
    """The asspy command that builds the county's directory (``--quick`` where asspy's CLI has it)."""
    place = county_key(county).replace("-", "_") or "<county>"
    try:
        from importlib.util import find_spec

        spec = find_spec("asspy.associations_cli")
        quick = bool(spec and spec.origin and "--quick" in Path(spec.origin).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - without the source, the long survey's command is given
        quick = False
    if quick:
        return f"python -m asspy.associations_cli {place} --quick"
    return f"python -m asspy.associations_cli {place} --survey 2001-01 YYYY-MM"


def _plain(value: Any) -> Any:
    """A summary as JSON: dataclasses, enums, dates, and counters made plain."""
    import dataclasses
    from enum import Enum

    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _plain(dataclasses.asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(_plain(k)): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_plain(v) for v in value]
    return value


def _summary(directory: Any) -> dict[str, Any]:
    """``Directory.summary()`` where asspy has it; else the counts read here."""
    if hasattr(directory, "summary"):
        made = _plain(directory.summary())
        if isinstance(made, dict):
            return made
    every = directory.associations()
    governing = directory.governing()
    return {
        "associations": len(every),
        "by_kind": dict(Counter(item.kind.value for item in every)),
        "by_standing": dict(Counter(item.standing.value for item in every)),
        "governing": len(governing),
        "unassociated_governing": len(directory.governing(unassociated=True)),
        "links": len(directory.links()),
        "failures": len(directory.failures()),
    }


def directory_search(county: str, q: str = "", limit: int = SEARCH_RESULTS) -> dict[str, Any]:
    """The county's association directory, searched, as data for the console and jason-mcp: ``surveyed``, the
    directory's ``summary``, the ``results`` (owners', commercial, and maintenance associations with evidence, each
    with its spellings, evidence, the governing instruments that name it or were linked to it, and the search score),
    the caveats, and, when the county is not surveyed, the asspy ``command`` that surveys it. Reads disk only; asking
    never creates a directory."""
    limit = max(1, min(int(limit or SEARCH_RESULTS), 200))
    out: dict[str, Any] = {"county": county, "surveyed": False, "query": q, "summary": {}, "results": [],
                           "caveats": list(DIRECTORY_CAVEATS)}
    if not county.strip():
        out["note"] = "no county: give one (the profile names no region)"
        return out
    directory = directory_for(county)
    if directory is None:
        out["command"] = survey_command(county)
        out["note"] = (f"{county}: no association directory yet. The survey reads the county recorder's public index "
                       "for months; a person runs it.")
        return out
    from asspy.associations import key

    out["surveyed"] = True
    with directory:
        chosen = {item.key for item in directory.all()}
        if q.strip() and hasattr(directory, "search"):
            hits = [(item, score) for item, score in directory.search(q, limit=max(limit * 4, limit))]
        elif q.strip():
            wanted = set(key(q).split())
            hits = [(item, round(len(wanted) / max(1, len(item.key.split())), 3)) for item in directory.find(q)]
            hits.sort(key=lambda pair: (-pair[1], pair[0].name))
        else:
            hits = [(item, None) for item in directory.all()]
        hits = [(item, score) for item, score in hits if item.key in chosen][:limit]
        governing = directory.governing()
        links = directory.links()
        for item, score in hits:
            keys = {key(spelling) for spelling in item.names} | {item.key}
            row = _association(item)
            row = {"key": item.key, **row,
                   "governing": sum(1 for g in governing if keys & set(g.associations)),
                   "links": sum(1 for link in links if link.association in keys),
                   "score": score}
            out["results"].append(row)
        out["summary"] = _summary(directory)
    out["count"] = len(out["results"])
    return out


def directory_match(name: str, county: str) -> dict[str, Any] | None:
    """The directory's association for this name: the same key, or the one association whose name holds every word."""
    directory = directory_for(county)
    if directory is None:
        return None
    from asspy.associations import key

    with directory:
        held = directory.get(key(name))
        if held is None:
            found = directory.find(name)
            held = found[0] if len(found) == 1 else None
        if held is None:
            return None
        out = _association(held)
        keys = {key(spelling) for spelling in held.names}
        # The governing instruments the survey saw naming it, and those its link pass tied to it by a neighbor.
        out["governing"] = [g.number for g in directory.governing() if keys & set(g.associations)]
        out["links"] = [(link.number, link.via) for link in directory.links() if link.association in keys]
        return out


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


def leads_from_rows(name: str, query: str, rows: Iterable[Any], *, source: str, found: str,
                    known: list[str] | None = None) -> list[dict[str, Any]]:
    """The leads one name search gives: one per kind of governing instrument found, and the name the index spells
    the association by. Counts, document numbers, dates, and the association's own spellings only: no other party's
    name is kept (a lien names an owner). ``known`` are the spellings the county's association directory holds for
    it (an older "... HOA" among them); they lead the spelling question."""
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
    for rank, spelling in enumerate(known or ()):
        # The directory counted every recording; keep its order ahead of this search's prefix matches.
        spellings[" ".join(spelling.upper().split())] += len(unique) + len(known or ()) - rank
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
           limit: int = SEARCH_LIMIT, directory: bool | None = None) -> Lookup:
    """Search the county recorder's public index for the association's name, read-only. ``recorder`` replaces the
    county's reader (tests). A county with no reader, or an index that cannot be read, is a note, not a failure.

    When the county's association directory (asspy) knows the name, its other spellings are searched too, up to
    three in all, and lead the spelling question. ``directory`` forces that on or off; by default it is consulted
    only with the county's own reader."""
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
    consult = recorder is None if directory is None else directory
    known = directory_match(name, county) if consult else None
    queries = [query]
    if known:
        out.notes.append(f"county association directory: {known['name']} ({known['kind']}, {known['standing']}; "
                         f"recorded {known['first']}..{known['last']}); its spellings are searched too.")
        for spelling in known["spellings"]:
            if spelling not in queries and len(queries) < 3:
                queries.append(spelling)
    rows: list[Any] = []
    failed = 0
    for each in queries:
        try:
            rows.extend(reader.search(name=each, limit=limit))
        except Exception as exc:  # noqa: BLE001 - a public source that fails is a note; the questions stay a person's
            failed += 1
            out.notes.append(f"county recorder: the search for {each!r} failed ({type(exc).__name__}); nothing was "
                             f"found under it.")
    if failed == len(queries):
        return out
    day = (today or date.today()).isoformat()
    out.leads = leads_from_rows(name, query, rows, source=label, found=day, known=known["spellings"] if known else None)
    out.notes.append(f"county recorder: searched {', '.join(repr(q) for q in queries)}: {len(rows)} rows"
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


__all__ = ["CHOICES", "Lookup", "READERS", "SEARCH_LIMIT", "SHELVES", "Shelf", "county_key", "directory_search",
           "leads_from_rows", "lookup", "reader_for", "region_for", "save_leads", "shelf_of", "survey_command"]
