"""Locate an association's recorded documents in the county recorder's public index, for onboarding.

A board taking over, or a manager onboarding, usually does not know the recording numbers of the declaration,
its amendments, the annexations that brought each phase in, the condominium plans, the maps, or the deeds that
gave the association its common area. The locator finds them, read-only, in three searches:

1. **By name.** Each spelling the county's association directory (asspy) holds for the association: every
   instrument a party of which is the association. Its own assessment liens are counted, not listed.
2. **Beside.** The numbers recorded the same day around each governing instrument found (a declaration, an
   annexation, a condominium plan): a community's formation is recorded together, so the map, the plan, the
   declaration, and the common-area deed sit beside one another. A neighbor counts when it shares a business party
   (the builder) with the instrument, or names the association.
3. **The builder.** The governing filings of the builders on those instruments. A builder records every phase's
   annexation, but also other communities'; these are asked about, never assumed.

Each located instrument serves an onboarding checklist item by its filing name (``jason.community.locator``) and
carries how it was tied (``Tie``). The result becomes leads, one per item (``leads``), which the onboarding
session asks as FACT questions; and a board's list (``markdown``): each document number, its date and type, why
it is thought the association's, and the question. A located instrument is a lead, not a pin: the recorded copy
is read before it is pinned. Every party is kept: the business and association parties in ``parties``, and the
private persons (an owner on a deed or a lien) in ``people`` with their index side (R grantor, E grantee). Owners'
names stay in jason's private data (``data/onboarding/``) and are never committed.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from jason.community.locator import HIGH_STAKES, QUESTIONS, Tie, rule_for
from jason.community.onboarding import item as checklist_item

# A business party: a builder, a lender, an agency, an association. Anything else is a private person (``people``).
_BUSINESS = re.compile(
    r"\b(?:LLC|L L C|INC|CORP|CORPORATION|COMPANY|CO|LP|L P|LTD|PTP|PRTN|PARTNERSHIP|HOMES|COMMUNITIES|BUILDERS|"
    r"DEVELOPMENT|DEVEL|DEVELOPERS|PROPERTIES|ASSOCIATION|ASSN|HOA|POA|COUNTY|CITY|DISTRICT|AGENCY|AUTHORITY|STATE|"
    r"BANK|TRUST COMPANY|GROUP|VENTURES|INVESTORS|HOLDINGS|PARTNERS)\b"
)
# A party that is not a builder: a public body or a lender. Its other filings are not the community's phases.
_NOT_BUILDER = re.compile(
    r"\b(?:COUNTY|CITY|STATE OF|AGENCY|AUTHORITY|DISTRICT|DEPARTMENT|UNITED STATES|BANK|MORTGAGE|SAVINGS|CREDIT UNION|"
    r"TITLE|ESCROW|TRUST COMPANY|NATIONAL ASSOCIATION|NATL|FINANCIAL|LENDING|ASSOCIATION|ASSN|HOA|POA)\b"
)

REACH = 6            # numbers read on each side of a governing instrument
ANCHORS = 15         # governing instruments whose neighbors are read, at most
BUILDERS = 3         # builders whose governing filings are read, at most
EARLIEST = 4         # the association's earliest named instruments whose neighbors are read too
CHOICES = 12         # instruments offered as choices in one question, at most

# The items a takeover needs whose absence is worth saying: listed under "Not located" with the ask.
CORE_ITEMS = ("declaration", "amendments", "annexations", "maps")
NOT_LOCATED_ASK = ("none in the index under the association's names or beside its documents. It may predate the "
                   "index's names, or be recorded under the builder alone; ask the board or the prior manager for the "
                   "recording number.")
CAVEATS = (
    "A located instrument is a lead, not a pin: the recorded copy is read before it is pinned.",
    "The builder's filings may be another community's; they are asked about, never suggested.",
    "Every party is kept: an owner on a deed or a lien is listed by name with its index side (R grantor, E grantee). "
    "Owners' names stay in jason's private data and are never committed.",
    "Read from the county recorder's public index when the locate ran (located_at); the index may hold more since.",
)


@dataclass(frozen=True)
class Located:
    """One recorded instrument the locator ties to the association."""

    number: str
    recorded: date | None
    filing: str
    item: str
    tie: Tie
    parties: tuple[str, ...] = ()        # business and association parties
    via: str = ""                        # the instrument it was found beside, or the builder whose filing it is
    people: tuple[tuple[str, str], ...] = ()   # private persons as indexed: (name, side), side R (grantor) or E (grantee)

    @property
    def label(self) -> str:
        day = self.recorded.isoformat() if self.recorded else "undated"
        how = self.tie.value + (f" ({self.via})" if self.via else "")
        return f"{self.number} ({day}, {self.filing}; {how})"


@dataclass
class Location:
    """What the locator found for one association, and what it could not read."""

    association: str
    county: str
    spellings: tuple[str, ...] = ()
    found: list[Located] = field(default_factory=list)
    liens: int = 0
    notes: list[str] = field(default_factory=list)
    searches: int = 0

    def by_item(self) -> dict[str, list[Located]]:
        out: dict[str, list[Located]] = {}
        for each in sorted(self.found, key=lambda x: (x.recorded or date.max, x.number)):
            out.setdefault(each.item, []).append(each)
        return out

    def leads(self, *, source: str, found: str) -> list[dict[str, Any]]:
        """One onboarding lead per checklist item located: the question, the instruments as choices, the strong ties
        as the suggestion. ``jason.tasks.onboarding_lookup.save_leads`` keeps them; the session asks each."""
        out: list[dict[str, Any]] = []
        for item_key, located in self.by_item().items():
            if item_key not in QUESTIONS:
                continue
            strong = [x for x in located if x.tie.strong]
            choices = [x.label for x in located[:CHOICES]]
            if len(located) > 1:
                choices.insert(0, f"all {len(located)} listed")
                if strong and len(strong) < len(located):
                    choices.insert(1, f"the {len(strong)} tied by name or recorded with its documents")
            choices.append("none of these: dismiss")
            if len(strong) == len(located) and len(located) > 1:
                suggestion = choices[0]
            elif len(strong) > 1:
                suggestion = choices[1]
            else:
                suggestion = strong[0].label if strong else ""
            ties = sorted({x.tie.value for x in located})
            entry = checklist_item(item_key)
            out.append({
                "key": f"located-{item_key}",
                "item": item_key,
                "method": "ccrs" if item_key in HIGH_STAKES else "pins",
                "stakes": item_key in HIGH_STAKES,
                "question": f"The county recorder's index shows {len(located)} "
                            f"{(entry.title if entry else item_key).lower()} for {self.association}. "
                            f"{QUESTIONS[item_key]}",
                "choices": choices,
                "suggestion": suggestion,
                "source": source,
                "found": found,
                "evidence": [f"{len(located)} located: " + "; ".join(ties),
                             *(x.label for x in located[CHOICES:CHOICES + 3]),
                             "A located instrument is a lead, not a pin: the recorded copy is read before it is pinned."],
            })
        return out

    def markdown(self) -> str:
        """The board's list: every located document by checklist item, why it is thought the association's, and what
        to answer."""
        lines = [f"# Recorded documents located for {self.association}", "",
                 f"Read from the {self.county} recorder's public index. Searched under: "
                 + ", ".join(self.spellings) + ".", ""]
        if self.liens:
            lines += [f"The association's own assessment liens and releases: {self.liens} (counted, not listed).", ""]
        for item_key, located in self.by_item().items():
            entry = checklist_item(item_key)
            lines += [f"## {entry.title if entry else item_key}", ""]
            if item_key in QUESTIONS:
                lines += [f"**Ask:** {QUESTIONS[item_key]} Do you hold a copy of each?", ""]
            lines += ["| Document | Recorded | Filing | Why | Parties | People |", "| --- | --- | --- | --- | --- | --- |"]
            for x in located:
                why = x.tie.value + (f" ({x.via})" if x.via else "")
                people = "; ".join(f"{name} ({side})" for name, side in x.people)
                lines.append(f"| {x.number} | {x.recorded or ''} | {x.filing} | {why} | {'; '.join(x.parties)} | {people} |")
            lines.append("")
        missing = [k for k in CORE_ITEMS if k not in self.by_item()]
        if missing:
            lines += ["## Not located", ""]
            for k in missing:
                entry = checklist_item(k)
                lines.append(f"- {entry.title if entry else k}: {NOT_LOCATED_ASK}")
            lines.append("")
        if self.notes:
            lines += ["## Notes", "", *(f"- {n}" for n in self.notes), ""]
        lines += ["A located instrument is a lead, not a pin: the recorded copy is read before it is pinned.", ""]
        return "\n".join(lines)

    def to_dict(self, *, located_at: str = "") -> dict[str, Any]:
        """The result as data (``data/onboarding/<profile>-documents-located.json``, the console's
        ``/api/documents-located``): each checklist item located with its instruments, the core items not located
        with their ask, the notes, and the caveats. Every party: the business and association ``parties``, and the
        private ``people`` with their index side. The file is jason's private data, never committed."""
        items = []
        for item_key, located in self.by_item().items():
            entry = checklist_item(item_key)
            items.append({
                "item": item_key,
                "title": entry.title if entry else item_key,
                "question": QUESTIONS.get(item_key, ""),
                "stakes": item_key in HIGH_STAKES,
                "located": [{
                    "number": x.number,
                    "recorded": x.recorded.isoformat() if x.recorded else "",
                    "filing": x.filing,
                    "tie": x.tie.name.lower(),
                    "tie_label": x.tie.value,
                    "strong": x.tie.strong,
                    "via": x.via,
                    "parties": list(x.parties),
                    "people": [{"name": name, "side": side} for name, side in x.people],
                } for x in located],
            })
        held = self.by_item()
        not_located = []
        for k in CORE_ITEMS:
            if k in held:
                continue
            entry = checklist_item(k)
            not_located.append({"item": k, "title": entry.title if entry else k, "ask": NOT_LOCATED_ASK})
        return {
            "association": self.association,
            "county": self.county,
            "located_at": located_at,
            "searches": self.searches,
            "liens": self.liens,
            "spellings": list(self.spellings),
            "items": items,
            "not_located": not_located,
            "notes": list(self.notes),
            "caveats": list(CAVEATS),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Location:
        """A result read back from ``to_dict``: the located instruments with their ties; the derived fields (items'
        titles and questions, not located, caveats) are computed again."""
        found = []
        for row in data.get("items") or ():
            for x in row.get("located") or ():
                recorded = x.get("recorded") or ""
                found.append(Located(
                    str(x.get("number", "")),
                    date.fromisoformat(recorded) if recorded else None,
                    str(x.get("filing", "")),
                    str(row.get("item", "")),
                    Tie[str(x.get("tie", "declarant")).upper()],
                    tuple(x.get("parties") or ()),
                    str(x.get("via", "")),
                    _people_from(x.get("people")),
                ))
        return cls(str(data.get("association", "")), str(data.get("county", "")), tuple(data.get("spellings") or ()),
                   found, int(data.get("liens") or 0), list(data.get("notes") or ()), int(data.get("searches") or 0))


class _Index:
    """The county recorder, read through its public methods: one session, renewed on a failure, every search counted."""

    def __init__(self, recorder, location: Location):
        self.recorder = recorder
        self.location = location
        self.session = None
        self.catalog: dict[str, str] = {}
        if hasattr(recorder, "document_types"):
            try:
                self.catalog = {t.name: t.id for t in recorder.document_types()}
            except Exception as exc:  # noqa: BLE001 - without the catalog the searches run without type filters
                location.notes.append(f"the index's document types could not be read ({type(exc).__name__}); searched without them")

    def _call(self, **kw) -> tuple[int, tuple]:
        self.location.searches += 1
        for attempt in (1, 2):
            if self.session is None or attempt == 2:
                self.session = self.recorder.open_session()
            try:
                if hasattr(self.recorder, "search_page"):
                    return self.recorder.search_page(session=self.session, rows=1000, **kw)
                kw.pop("types", None)
                rows = tuple(self.recorder.search(session=self.session, limit=1000, **kw))
                return len(rows), rows
            except Exception as exc:  # noqa: BLE001 - a second failure is a note; the other searches go on
                failure = exc
        self.location.notes.append(f"a search could not be read ({type(failure).__name__}: {failure}); "
                                   f"what it would have found is not listed")
        return 0, ()

    def types(self, wanted) -> tuple[str, ...]:
        return tuple(i for name, i in self.catalog.items() if wanted(name))

    def by_name(self, name: str, *, types: tuple[str, ...] = ()) -> tuple:
        extra = {"types": types} if types else {}
        total, rows = self._call(name=name, **extra)
        if total > len(rows):
            self.location.notes.append(f"{name!r}: the index counts {total}, one page holds {len(rows)}; the rest are not listed")
        return rows

    def numbers(self, low: str, high: str) -> tuple:
        return self._call(number=low, number_to=high)[1]


@dataclass(frozen=True)
class _Instrument:
    number: str
    recorded: date | None
    filing: str
    grantors: tuple[str, ...]
    grantees: tuple[str, ...]

    @property
    def parties(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys((*self.grantors, *self.grantees)))


def _instruments(rows) -> list[_Instrument]:
    """Index rows as one instrument per number; a number listed under two filings carries both."""
    grouped: dict[str, list] = {}
    for row in rows:
        grouped.setdefault(row.number, []).append(row)
    out = []
    for number, group in grouped.items():
        filings = list(dict.fromkeys(str(r.filing_name) for r in group if r.filing_name))
        out.append(_Instrument(
            number,
            next((r.recorded for r in group if r.recorded), None),
            "; ".join(filings),
            tuple(dict.fromkeys(n for r in group for n in r.grantors)),
            tuple(dict.fromkeys(n for r in group for n in r.grantees)),
        ))
    return out


def _is_business(name: str) -> bool:
    return bool(_BUSINESS.search(" ".join(name.upper().split())))


def _business(names) -> tuple[str, ...]:
    return tuple(n for n in names if _is_business(n))


def _people(instrument: _Instrument) -> tuple[tuple[str, str], ...]:
    """The private persons on an instrument as indexed: (name, side), R for a grantor and E for a grantee."""
    rows = [(n, "R") for n in instrument.grantors if n.strip() and not _is_business(n)]
    rows += [(n, "E") for n in instrument.grantees if n.strip() and not _is_business(n)]
    return tuple(dict.fromkeys(rows))


def _people_from(rows: Any) -> tuple[tuple[str, str], ...]:
    """``people`` read back from ``to_dict``: dicts with name and side, or ``[name, side]`` pairs."""
    out: list[tuple[str, str]] = []
    for row in rows or ():
        if isinstance(row, dict):
            name, side = str(row.get("name", "")), str(row.get("side", ""))
        elif isinstance(row, (list, tuple)) and row:
            name, side = str(row[0]), str(row[1]) if len(row) > 1 else ""
        else:
            name, side = str(row), ""
        if name.strip():
            out.append((name, side))
    return tuple(out)


def _rule(filing: str):
    # A number listed under two filings is read by its strongest (the reconveyance over its substitution).
    return next((r for part in filing.split("; ") for r in (rule_for(part),) if r is not None), None)


def locate(name: str, county: str, *, recorder: Any = None, known: dict[str, Any] | None = None,
           reach: int = REACH, anchors: int = ANCHORS, builders: int = BUILDERS) -> Location:
    """Locate the association's recorded documents. ``known`` is its directory entry (``onboarding_lookup.
    directory_match``): the spellings to search under; without one, ``name`` alone is searched. ``recorder``
    replaces the county's reader (tests)."""
    from asspy.associations import key as association_key

    from jason.tasks.onboarding_lookup import directory_match, reader_for

    known = known if known is not None else directory_match(name, county)
    spellings = tuple(known["spellings"][:4]) if known else (name,)
    title = known["name"] if known else name
    out = Location(title, county, spellings)
    reader = recorder if recorder is not None else reader_for(county)
    if reader is None:
        out.notes.append(f"jason has no reader for {county!r}; nothing was searched")
        return out
    if not known:
        out.notes.append("the association is not in the county's directory; searched under the name given only")
    index = _Index(reader, out)
    mine = {association_key(s) for s in spellings}
    is_ours = lambda party: association_key(party) in mine  # noqa: E731
    seen: dict[str, Located] = {}

    def keep(located: Located) -> None:
        held = seen.get(located.number)
        if held is None or list(Tie).index(located.tie) < list(Tie).index(held.tie):
            seen[located.number] = located

    # 1. By name: every instrument a party of which is the association; its own liens counted.
    # Every type but the association's own liens, which a busy association records by the thousand.
    others = index.types(lambda n: (r := rule_for(n)) is None or r.item != "recorded-liens")
    liens: set[str] = set()
    for spelling in spellings:
        for each in _instruments(index.by_name(spelling, types=others)):
            if not any(is_ours(p) for p in each.parties):
                continue
            rule = _rule(each.filing)
            if rule is None:
                continue
            if rule.item == "recorded-liens":
                liens.add(each.number)
                continue
            if rule.side == "E" and not any(is_ours(p) for p in each.grantees):
                continue
            keep(Located(each.number, each.recorded, each.filing, rule.item, Tie.NAMED, _business(each.parties),
                         people=_people(each)))
    # The liens are left out of the search by type; the directory counted them when it surveyed the county.
    out.liens = len(liens) or int((known or {}).get("evidence", {}).get("assessment lien", 0))

    # 2. Beside: the formation recorded with each governing instrument.
    governing = [x for x in seen.values() if (r := _rule(x.filing)) is not None and r.governing]
    # The association's earliest named instruments (its first common-area deeds) are recorded with the declaration:
    # read beside them too, so the original declaration is tied by its neighbor, not only as the builder's filing.
    earliest = sorted((x for x in seen.values() if x not in governing and x.recorded), key=lambda x: (x.recorded, x.number))
    governing += earliest[:EARLIEST]
    # The directory's governing instruments: those naming the association, and those a survey tied to it by a
    # same-day neighbor (``asspy.associations.link``), which are the builder's and so recorded beside, not named.
    for number in (known or {}).get("governing", ()):
        if number not in seen:
            governing.append(Located(number, None, "", "", Tie.NAMED))
    for number, via in (known or {}).get("links", ()):
        if number not in seen:
            governing.append(Located(number, None, "", "", Tie.BESIDE, via=via))
    builders_found: dict[str, int] = {}
    for anchor in sorted(governing, key=lambda x: x.number)[:anchors]:
        around = reader.nearby(anchor.number, before=reach, after=reach)
        if not around:
            continue
        rows = _instruments(index.numbers(min((anchor.number, *around)), max((anchor.number, *around))))
        here = next((x for x in rows if x.number == anchor.number), None)
        if here is None:
            continue
        theirs = {association_key(p) for p in _business(here.parties) if not is_ours(p)}
        for p in _business(here.parties):
            if not _NOT_BUILDER.search(p.upper()):
                builders_found[p] = builders_found.get(p, 0) + 1
        if anchor.number not in seen:
            rule = _rule(here.filing)
            if rule is not None and rule.item != "recorded-liens":
                tie = Tie.NAMED if any(is_ours(p) for p in here.parties) else anchor.tie
                keep(Located(here.number, here.recorded, here.filing, rule.item, tie, _business(here.parties), via=anchor.via,
                             people=_people(here)))
        for each in rows:
            if each.number == anchor.number or each.recorded != here.recorded:
                continue
            rule = _rule(each.filing)
            if rule is None or not rule.beside:
                continue
            shares = bool({association_key(p) for p in _business(each.parties)} & theirs)
            names_us = any(is_ours(p) for p in each.parties)
            if not (shares or names_us):
                continue
            if rule.side == "E" and not any(is_ours(p) for p in each.grantees):
                continue
            keep(Located(each.number, each.recorded, each.filing, rule.item,
                         Tie.NAMED if names_us else Tie.BESIDE, _business(each.parties), via=anchor.number,
                         people=_people(each)))

    # 3. The builders' own governing filings: other phases, or other communities.
    governing_types = index.types(lambda n: (r := rule_for(n)) is not None and r.governing)
    for builder, _ in sorted(builders_found.items(), key=lambda kv: -kv[1])[:builders]:
        rows = index.by_name(builder, types=governing_types)
        for each in _instruments(rows):
            rule = _rule(each.filing)
            if rule is None or not rule.governing or each.number in seen:
                continue
            keep(Located(each.number, each.recorded, each.filing, rule.item, Tie.DECLARANT,
                         _business(each.parties), via=builder, people=_people(each)))
    out.found = sorted(seen.values(), key=lambda x: (x.item, x.recorded or date.max, x.number))
    if builders_found:
        out.notes.append("builders on its governing instruments: " + ", ".join(sorted(builders_found))
                         + "; their other filings are listed as the builder's, to be confirmed")
    return out


# --- The result on disk, and the locate as a person's queued job ------------------------------------------------------
#
# ``jason onboard --locate`` writes the board's list (.md) and the result as data (.json) under data/onboarding/. The
# console and jason-mcp read the .json and never search the county: a fresh locate is a job a person queues
# (``enqueue``), which ``jason worker`` runs on the county lane (``jason.jobs``). Who asked is kept beside the queue
# in ``data/onboarding/locate-requests.jsonl``.

REQUESTS = "locate-requests.jsonl"
_ACTIVE_JOB = ("queued", "running")


def stem(profile: str, *, name: str = "", county: str = "", own: bool = True) -> str:
    """The files' stem: the profile's key for its own association; for another association (``--name``), the county
    and the directory key of the name, so a lookup of a neighbor never lands in the profile's files."""
    if own:
        return profile
    from asspy.associations import key as association_key

    from jason.tasks.onboarding_lookup import county_key

    slug = "-".join(association_key(name).lower().split()) or "association"
    return f"{county_key(county) or 'county'}-{slug}"


def paths(data_dir: Path, file_stem: str) -> tuple[Path, Path]:
    """``(json, md)`` under ``data/onboarding/``."""
    folder = Path(data_dir) / "onboarding"
    return folder / f"{file_stem}-documents-located.json", folder / f"{file_stem}-documents-located.md"


def _atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def save(location: Location, data_dir: Path, file_stem: str, *, located_at: str = "") -> tuple[Path, Path]:
    """Write the board's list and the result as data, each replaced whole (a reader never sees half a file)."""
    when = located_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    as_json, as_md = paths(data_dir, file_stem)
    _atomic(as_md, location.markdown())
    _atomic(as_json, json.dumps(location.to_dict(located_at=when), indent=1, ensure_ascii=False) + "\n")
    return as_json, as_md


def load(data_dir: Path, file_stem: str) -> dict[str, Any] | None:
    """The saved result, or None when no locate has run (or the file cannot be read)."""
    as_json, _ = paths(data_dir, file_stem)
    if not as_json.is_file():
        return None
    try:
        data = json.loads(as_json.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def is_own(name: str, own_name: str) -> bool:
    """True when ``name`` is the profile's own association: none given, or the same directory key."""
    if not name.strip():
        return True
    from asspy.associations import key as association_key

    return association_key(name) == association_key(own_name)


def active() -> tuple[str, str, str]:
    """The active profile's key, its association's name, and the county its ``region`` names ("" when unset)."""
    from jason.community import community
    from jason.community.profile import profile_name

    the = community()
    county = the.region.split("/", 1)[1] if "/" in the.region else ""
    return profile_name(), the.name, county


def argv_for(county: str, name: str = "") -> list[str]:
    """The jason command line that locates: the job's argv."""
    return ["onboard", "--locate", "--county", county] + (["--name", name] if name else [])


def command(argv: list[str]) -> str:
    return "jason " + " ".join(f'"{a}"' if (" " in a or not a) else a for a in argv)


def _target(argv: list[str]) -> tuple[str, str] | None:
    """``(county, name)`` of a queued ``onboard --locate`` command line, or None for any other command."""
    if not argv or argv[0] != "onboard" or "--locate" not in argv:
        return None

    def value(flag: str) -> str:
        return argv[argv.index(flag) + 1] if flag in argv[:-1] else ""

    return value("--county"), value("--name")


def _requests(data_dir: Path) -> dict[int, dict[str, Any]]:
    path = Path(data_dir) / "onboarding" / REQUESTS
    out: dict[int, dict[str, Any]] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
            out[int(row["job"])] = row
        except (ValueError, KeyError, TypeError):
            continue
    return out


def _job_dict(job: Any, requested: dict[int, dict[str, Any]]) -> dict[str, Any]:
    return {"id": job.id, "status": job.status.value, "resource": job.job_class.value, "command": job.command,
            "created": job.created, "started": job.started, "finished": job.finished, "exit_code": job.exit_code,
            "note": job.note, "requested_by": requested.get(job.id, {}).get("by", "")}


def _jobs_for(data_dir: Path, file_stem: str, own: tuple[str, str, str]) -> list[Any]:
    """The queue's locate jobs for these files, newest first (queued, running, or failed). Reading the queue never
    creates it: no ``jobs.db``, no jobs."""
    if not (Path(data_dir) / "jobs.db").is_file():
        return []
    from jason import jobs

    profile, own_name, own_county = own
    found = []
    for job in jobs.jobs(data_dir, limit=200):
        target = _target(job.argv)
        if target is None:
            continue
        county, name = target
        mine = is_own(name, own_name)
        if stem(profile, name=name, county=county or own_county, own=mine) == file_stem:
            found.append(job)
    return found


def view(data_dir: Path, *, county: str = "", name: str = "",
         own: tuple[str, str, str] | None = None) -> dict[str, Any]:
    """What the console and jason-mcp show: the saved result for the active profile (or ``name`` in ``county``), with
    the locate job when one is queued, running, or failed since; or, when none ran, ``missing`` with the command that
    fills it. Reads disk only."""
    profile, own_name, own_county = own or active()
    mine = is_own(name, own_name)
    county = county.strip() or own_county
    the_name = name.strip() or own_name
    file_stem = stem(profile, name=the_name, county=county, own=mine)
    argv = argv_for(county or "<county>", name.strip())
    data = load(data_dir, file_stem)
    if data is None:
        out: dict[str, Any] = {
            "missing": True, "association": the_name, "county": county, "command": command(argv),
            "note": ("No locate has run for this association. A locate reads the county recorder's public index; "
                     "it runs as a job a person queues, never on page load."
                     + ("" if county else " The profile names no county (region): give one.")),
            "caveats": list(CAVEATS),
        }
    else:
        out = dict(data)
        _, as_md = paths(data_dir, file_stem)
        if as_md.is_file():
            out["report"] = f"onboarding/{as_md.name}"
        out["command"] = command(argv)
    out["profile"] = profile if mine else ""
    requested = _requests(data_dir)
    for job in _jobs_for(data_dir, file_stem, (profile, own_name, own_county)):
        if job.status.value in _ACTIVE_JOB or (job.status.value == "failed" and job.finished > str(out.get("located_at", ""))):
            out["job"] = _job_dict(job, requested)
            break
    return out


def enqueue(data_dir: Path, *, county: str = "", name: str = "", by: str = "",
            own: tuple[str, str, str] | None = None) -> dict[str, Any]:
    """A person's request for a fresh locate: queued as ``onboard --locate --county X [--name N]`` on the county lane,
    with who asked kept in ``data/onboarding/locate-requests.jsonl``. A locate already queued or running for the same
    files is returned instead of a second one. Nothing here reads the county."""
    from jason import jobs
    from jason.tasks.onboarding_lookup import READERS, county_key

    if not by.strip():
        raise ValueError("a locate is a person's action: give by (who asked)")
    profile, own_name, own_county = own or active()
    county = county.strip() or own_county
    if not county:
        raise ValueError("give the county (the profile names no region)")
    if county_key(county) not in READERS:
        raise ValueError(f"jason has no reader for {county!r} (readers: {', '.join(sorted(READERS))})")
    mine = is_own(name, own_name)
    file_stem = stem(profile, name=name.strip() or own_name, county=county, own=mine)
    argv = argv_for(county, name.strip())
    requested = _requests(data_dir)
    for job in _jobs_for(data_dir, file_stem, (profile, own_name, own_county)):
        if job.status.value in _ACTIVE_JOB:
            return {"job": _job_dict(job, requested), "command": job.command, "existing": True,
                    "note": "a locate for this association is already queued or running"}
    job = jobs.add(data_dir, argv)
    row = {"job": job.id, "by": by.strip(), "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "county": county, "name": name.strip(), "profile": profile if mine else ""}
    log = Path(data_dir) / "onboarding" / REQUESTS
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {"job": _job_dict(job, {job.id: row}), "command": job.command, "existing": False,
            "note": "queued; jason worker runs it on the county lane (jason worker --once)"}
