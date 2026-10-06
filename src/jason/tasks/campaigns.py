"""The campaign record: the handler is chosen when a form is made (docs/arrivals-design.md, "The handler is chosen when
the form is made"; build step 1a).

A **campaign** is one form, one cycle, one channel: ``NP27E`` is the owner-information form's emailed copies for the 2027
cycle (``form_refs.campaign``). A person opens it, once, before any copy is made, and the record keeps what was chosen:

- the form (the library's key), the library's version and the day of the law it recites (``as_of``) at that time;
- the form's **authority** (a tuple of canonical citations; empty for a form tied to no law);
- the **handler** and its options, and the procedure (``jason sop``). A form with an authority takes the process handler
  its authority names; a form with none takes a general handler a person chooses from the short fixed list
  (``form_library.handlers``). A profile cannot add one by data;
- the cycle (opened, return-by), the channel, who chose it and when, and whether it is open or closed.

``data/forms/campaigns.json`` holds one row per campaign code, written atomically under the store lock
``form-campaigns-<profile>``. It holds no address, no email, and no owner.

**The invariant: a reference exists only if a handler does.** ``require`` is the one gate every place that makes a
reference or a marker for a form goes through first (the emailed copies, the mailed letter, a stamped fillable PDF): it
refuses, with the reason, a form that is not offered, has no registered handler or procedure, takes the wrong handler for
its authority, or has no open campaign. Each copy's entry in ``data/forms/references.json`` then carries its campaign
(``stamp``), so an arrival with a reference is routed to its handler by one lookup.

A cycle that was running before this record existed keeps working: ``adopt_existing`` reads the profile's response
requests (``Community.response_requests``) and the library's definition of their form, and writes a row for each marker
campaign they name. No other data is rewritten; an entry in ``references.json`` with no ``campaign`` is read as belonging
to the campaign its marker's prefix names (``campaign_of``).
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from jason.community.form_refs import Channel, campaign as campaign_code, parse

STORE = Path("forms") / "campaigns.json"
WORDS = {Channel.EMAIL: "email", Channel.MAIL: "mail", Channel.PAYHOA: "payhoa"}
WHO_ADOPTED = "the profile (its response requests)"


class CampaignRefusal(ValueError):
    """A campaign cannot be opened, or a reference made: ``str(exc)`` is the reason, in plain words, naming what is
    missing."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class CampaignStatus(Enum):
    OPEN = "open"
    CLOSED = "closed"


@dataclass(frozen=True)
class Campaign:
    code: str                                   # "NP27E": the form's code, the cycle's year, the channel
    form: str                                   # the library's key for the form
    form_key: str = ""                          # the form's own key (``FormKey``): what ``references.json`` calls it
    version: str = ""                           # the library's version of the form when the campaign was opened
    as_of: str = ""                             # the day of the law that version recites
    authority: tuple[str, ...] = ()             # canonical citations; empty for a general form
    handler: str = ""                           # a key of ``form_library.handlers.HANDLERS``
    options: Mapping[str, str] = field(default_factory=dict)
    procedure: str = ""
    channel: str = ""                           # "email", "mail", or "payhoa"
    year: int = 0
    opened: str = ""
    return_by: str = ""
    by: str = ""                                # who chose it
    chosen_at: str = ""
    status: CampaignStatus = CampaignStatus.OPEN
    closed_by: str = ""
    closed_at: str = ""
    adopted: bool = False                       # read from the profile's response requests, not chosen in this record
    stored: bool = True                         # False: planned from the profile, not yet written to the store

    @property
    def is_open(self) -> bool:
        return self.status is CampaignStatus.OPEN

    @property
    def kind(self) -> str:
        return "process" if self.authority else "general"

    def to_json(self) -> dict[str, Any]:
        return {"code": self.code, "form": self.form, "formKey": self.form_key, "version": self.version, "asOf": self.as_of,
                "authority": list(self.authority), "handler": self.handler, "options": dict(self.options),
                "procedure": self.procedure, "channel": self.channel, "year": self.year,
                "cycle": {"opened": self.opened, "returnBy": self.return_by}, "by": self.by, "chosenAt": self.chosen_at,
                "status": self.status.value, "closedBy": self.closed_by, "closedAt": self.closed_at, "adopted": self.adopted}

    @classmethod
    def from_json(cls, code: str, raw: Mapping[str, Any]) -> Campaign:
        cycle = raw.get("cycle") or {}
        return cls(str(raw.get("code") or code), str(raw.get("form") or ""), str(raw.get("formKey") or ""),
                   str(raw.get("version") or ""), str(raw.get("asOf") or ""), tuple(raw.get("authority") or ()),
                   str(raw.get("handler") or ""), {str(k): str(v) for k, v in (raw.get("options") or {}).items()},
                   str(raw.get("procedure") or ""), str(raw.get("channel") or ""), int(raw.get("year") or 0),
                   str(cycle.get("opened") or ""), str(cycle.get("returnBy") or ""), str(raw.get("by") or ""),
                   str(raw.get("chosenAt") or ""), CampaignStatus(raw.get("status") or "open"), str(raw.get("closedBy") or ""),
                   str(raw.get("closedAt") or ""), bool(raw.get("adopted")))


# -- the store -----------------------------------------------------------------------------------------------------------

def _now(now: datetime | None) -> str:
    return (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")


def _day(value: Any) -> str:
    return value.isoformat() if isinstance(value, (date, datetime)) else str(value or "")


def load_raw(data_dir: Path) -> dict[str, dict[str, Any]]:
    """The rows as stored, by campaign code ({} when there is no file or it cannot be read)."""
    path = Path(data_dir) / STORE
    try:
        raw = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    except (OSError, ValueError):
        return {}
    return {str(k): v for k, v in raw.items() if isinstance(v, dict)} if isinstance(raw, dict) else {}


def load(data_dir: Path) -> dict[str, Campaign]:
    return {code: Campaign.from_json(code, row) for code, row in load_raw(data_dir).items()}


def _lock_key() -> str:
    from jason.community.profile import profile_name

    return f"form-campaigns-{profile_name()}"


def _update(data_dir: Path, change: Any, purpose: str) -> Any:
    """Read the store under its lock, let ``change(rows)`` edit the rows (and return a result), and write it back
    atomically."""
    from jason.locks import Resource, hold

    path = Path(data_dir) / STORE
    with hold(Resource.STORE, _lock_key(), purpose=purpose):
        rows = load(data_dir)
        result = change(rows)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps({c: r.to_json() for c, r in sorted(rows.items())}, indent=1, sort_keys=True), encoding="utf-8")
        tmp.replace(path)
    return result


def channel_of(value: Any) -> Channel:
    """A channel from its word (``email``, ``mail``, ``payhoa``) or its marker letter (``E``, ``M``, ``P``)."""
    if isinstance(value, Channel):
        return value
    text = str(value or "").strip().casefold()
    for channel, word in WORDS.items():
        if text in (word, channel.value.casefold(), channel.name.casefold()):
            return channel
    raise CampaignRefusal(f"channel {value!r} is not one of email, mail, payhoa (marker letters E, M, P)")


# -- judging a form ------------------------------------------------------------------------------------------------------

def _resolved(community: Any, form_key: str) -> Any:
    """The community's form by its library key or its template's, offered or refused with the reason."""
    from jason.community.form_library.resolve import resolve
    from jason.community.form_library.tiers import Status

    resolved = resolve(community)
    form = resolved.get(str(form_key or ""))
    if form is None:
        known = ", ".join(f.key for f in resolved.forms) or "none"
        raise CampaignRefusal(f"there is no form {form_key!r} in this community's forms (the forms: {known})")
    if form.status is Status.NOT_OFFERED:
        raise CampaignRefusal(f"form {form.key!r} is not offered: " + ("; ".join(form.missing) or "a slot or binding is missing")
                              + " (jason form-library --show " + form.key + ")")
    return form


def judge(community: Any, form_key: str, handler: str | None = None) -> tuple[Any, str]:
    """The form, and the handler it will take, or a ``CampaignRefusal``: the form is offered; its handler and procedure
    are registered; a form with an authority takes the handler its authority names; a form with none takes a general
    handler a person chose."""
    from jason.community.form_library import handlers as table

    form = _resolved(community, form_key)
    d = form.definition
    given = (handler or "").strip()
    if d.authority:
        if given and given != d.handler:
            raise CampaignRefusal(f"form {d.key!r} serves {', '.join(d.authority)}: its handler is "
                                  f"{d.handler or 'not set'}, the one its authority names; it cannot take {given!r}")
        chosen = d.handler
    else:
        chosen = given or d.handler
        if not chosen:
            general = sorted(k for k, h in table.HANDLERS.items() if h.kind is table.HandlerKind.GENERAL)
            raise CampaignRefusal(f"form {d.key!r} has no authority, so a person chooses its handler from the general handlers "
                                  f"when it is made (--handler KEY): {', '.join(general)}")
    issues = table.problems(replace(d, handler=chosen), community)
    if issues:
        raise CampaignRefusal(f"form {d.key!r} cannot be made: " + "; ".join(issues))
    return form, chosen


def _code(form: Any, year: int, channel: Channel) -> str:
    try:
        return campaign_code(form.template.code, year, channel)
    except ValueError as exc:
        raise CampaignRefusal(f"form {form.key!r} has no usable marker code ({exc}); a form that carries a reference needs "
                              "one") from exc


def open_campaign(community: Any, form_key: str, *, channel: Any, cycle: Any, by: str, data_dir: Path,
                  handler: str | None = None, options: Mapping[str, str] | None = None,
                  now: datetime | None = None) -> Campaign:
    """A person's act: open the campaign for a form, one cycle, one channel, and keep what was chosen. It writes the row
    and makes no copy. ``cycle`` is an ``AnswerCycle`` (year, opened, return_by). Raises ``CampaignRefusal`` with the
    reason when the form cannot be made, has no handler, has the wrong one, or ``by`` is empty."""
    if not (by or "").strip():
        raise CampaignRefusal("who chose the handler is required (--by NAME): a person opens a campaign")
    through = channel_of(channel)
    form, chosen = judge(community, form_key, handler)
    for key in (options or {}):
        if not str(key).strip():
            raise CampaignRefusal("a handler option needs a name (--option NAME=VALUE)")
    d = form.definition
    year = int(cycle.year)
    code = _code(form, year, through)
    row = Campaign(code, d.key, d.template.key.value, d.version, _day(d.as_of), tuple(d.authority), chosen,
                   {str(k): str(v) for k, v in (options or {}).items()}, d.procedure, WORDS[through], year,
                   _day(getattr(cycle, "opened", "")), _day(getattr(cycle, "return_by", "")), by.strip(), _now(now))

    def add(rows: dict[str, Campaign]) -> None:
        held = rows.get(code)
        if held is not None:
            raise CampaignRefusal(f"campaign {code} already exists ({held.status.value}, form {held.form}, handler "
                                  f"{held.handler}); a code names one form, one cycle, and one channel"
                                  + ("" if not held.is_open else f": close it first (jason campaigns --close {code} --by NAME)"))
        rows[code] = row

    _update(data_dir, add, f"open campaign {code}")
    return row


def close_campaign(data_dir: Path, code: str, *, by: str, now: datetime | None = None) -> Campaign:
    if not (by or "").strip():
        raise CampaignRefusal("who closes it is required (--by NAME)")
    name = (code or "").strip().upper()

    def close(rows: dict[str, Campaign]) -> Campaign:
        held = rows.get(name)
        if held is None:
            raise CampaignRefusal(f"there is no campaign {code!r} (jason campaigns lists them)")
        if not held.is_open:
            raise CampaignRefusal(f"campaign {name} is already closed")
        rows[name] = replace(held, status=CampaignStatus.CLOSED, closed_by=by.strip(), closed_at=_now(now))
        return rows[name]

    return _update(data_dir, close, f"close campaign {name}")


# -- the cycle that was running before this record ------------------------------------------------------------------------

def plan_adoption(community: Any, data_dir: Path, *, now: datetime | None = None) -> tuple[list[Campaign], list[str]]:
    """The rows the profile's response requests call for that the store lacks, and, for each it cannot make, why. Reads
    only; ``adopt_existing`` writes them."""
    from jason.community.form_library import handlers as table
    from jason.community.form_library.resolve import resolve
    from jason.community.form_library.tiers import Status

    held = load(data_dir)
    requests = getattr(community, "response_requests", lambda: ())() or ()
    if not requests:
        return [], []
    resolved = resolve(community)
    stamp = _now(now)
    rows: list[Campaign] = []
    skipped: list[str] = []
    for req in requests:
        form = resolved.get(req.form.key.value)
        for name in req.marker_campaigns:
            code = name.upper()
            if code in held or any(r.code == code for r in rows):
                continue
            if form is None or form.status is Status.NOT_OFFERED:
                skipped.append(f"{code}: the form {req.form.key.value!r} is not offered, so no campaign is adopted")
                continue
            issues = table.problems(form.definition, community)
            if issues:
                skipped.append(f"{code}: " + "; ".join(issues))
                continue
            try:
                through = channel_of(code[-1])
            except CampaignRefusal:
                skipped.append(f"{code}: its last letter is not a channel")
                continue
            d = form.definition
            rows.append(Campaign(code, d.key, d.template.key.value, d.version, _day(d.as_of), tuple(d.authority), d.handler, {},
                                 d.procedure, WORDS[through], int(req.cycle.year), _day(req.cycle.opened),
                                 _day(req.cycle.return_by), WHO_ADOPTED, stamp, adopted=True, stored=False))
    return rows, skipped


def adopt_existing(community: Any, data_dir: Path, *, now: datetime | None = None) -> list[Campaign]:
    """Write the rows ``plan_adoption`` names (the campaigns of requests already running), keeping every row already
    there. Returns the rows written."""
    planned, _ = plan_adoption(community, data_dir, now=now)
    if not planned:
        return []

    def add(rows: dict[str, Campaign]) -> list[Campaign]:
        added = []
        for row in planned:
            if row.code not in rows:
                rows[row.code] = replace(row, stored=True)
                added.append(rows[row.code])
        return added

    return _update(data_dir, add, "adopt the profile's running campaigns")


def view(data_dir: Path, community: Any = None) -> dict[str, Campaign]:
    """The stored rows, and (read-only) the rows the profile's running requests would adopt, marked ``stored=False``."""
    rows = load(data_dir)
    if community is not None:
        try:
            planned = plan_adoption(community, data_dir)[0]
        except Exception:  # noqa: BLE001 - a library that cannot resolve shows the stored rows, not a traceback
            planned = []
        for row in planned:
            rows.setdefault(row.code, row)
    return rows


# -- reading a campaign --------------------------------------------------------------------------------------------------

def campaign_of(data_dir: Path, reference_or_code: str, rows: Mapping[str, Campaign] | None = None) -> Campaign | None:
    """The campaign a reference or a code belongs to. A copy's entry in ``references.json`` that names its ``campaign`` is
    read by it; an older entry with none is read as belonging to the campaign its marker's prefix names."""
    held = dict(rows) if rows is not None else load(data_dir)
    text = (reference_or_code or "").strip()
    if text.upper() in held:
        return held[text.upper()]
    from jason.tasks import form_references

    entry = form_references.load(Path(data_dir)).get(text)
    named = str((entry or {}).get("campaign") or "").upper()
    if named in held:
        return held[named]
    for marker in parse(text):
        if marker.campaign in held:
            return held[marker.campaign]
    return None


def stamp(data_dir: Path, reference: str) -> dict[str, str]:
    """What a sent copy's entry in ``references.json`` carries to point at its campaign (``campaign``, ``formVersion``);
    empty when the reference has no campaign row, so a copy made without one is recorded as it always was."""
    row = campaign_of(data_dir, reference)
    return {"campaign": row.code, "formVersion": row.version} if row is not None else {}


def for_request(rows: Mapping[str, Campaign], request: Any) -> list[Campaign]:
    """The campaigns a ``ResponseRequest`` names by its marker campaigns, in the order it names them."""
    return [rows[c.upper()] for c in getattr(request, "marker_campaigns", ()) if c.upper() in rows]


# -- the gate ------------------------------------------------------------------------------------------------------------

def require(community: Any, data_dir: Path, form_key: str, channel: Any, year: int | None = None, *,
            adopt: bool = False) -> Campaign:
    """The open campaign for this form and channel (and cycle year, when given), or a ``CampaignRefusal`` with the reason.
    Every place that makes a reference or a marker for a form calls this first. A cycle the profile's response requests
    already run counts as open; with ``adopt`` its rows are written (a real send), without it nothing is written (a dry
    run reports the same answer)."""
    from jason.community.form_library import handlers as table

    through = channel_of(channel)
    form = _resolved(community, form_key)
    rows = load(data_dir)
    planned = {r.code: r for r in plan_adoption(community, data_dir)[0]}

    def mine(source: Mapping[str, Campaign]) -> list[Campaign]:
        return [r for r in source.values() if r.form == form.key and r.channel == WORDS[through]
                and (year is None or r.year == int(year))]

    found = mine(rows) + [r for r in mine(planned) if r.code not in rows]
    if not found:
        raise CampaignRefusal(f"no campaign is open for form {form.key!r} by {WORDS[through]}"
                              + (f" for {int(year)}" if year else "")
                              + f": a person opens one first, choosing its handler (jason campaigns --open {form.key} "
                                f"--channel {WORDS[through]} --cycle-year YEAR --by NAME)")
    live = [r for r in found if r.is_open]
    if not live:
        raise CampaignRefusal(f"campaign {max(found, key=lambda r: r.year).code} is closed; open the next cycle's "
                              f"(jason campaigns --open {form.key} --channel {WORDS[through]} --cycle-year YEAR --by NAME)")
    row = max(live, key=lambda r: (r.year, r.code))
    issues = table.problems(replace(form.definition, handler=row.handler), community)
    if issues:
        raise CampaignRefusal(f"campaign {row.code}'s handler cannot stand: " + "; ".join(issues))
    if not row.stored and adopt:
        adopt_existing(community, data_dir)
        row = load(data_dir).get(row.code, row)
    return row


def gate(community: Any, data_dir: Path, form_key: str, channel: Any, year: int | None = None, *, adopt: bool = False) -> int:
    """``require`` for a command: 0 when a copy may be made, else the refusal printed as ``jason: <reason>`` and 2."""
    try:
        require(community, data_dir, form_key, channel, year, adopt=adopt)
    except CampaignRefusal as exc:
        print(f"jason: {exc.reason}", file=sys.stderr)
        return 2
    return 0


# -- what each campaign has done -----------------------------------------------------------------------------------------

def counts(data_dir: Path, community: Any, rows: Mapping[str, Campaign]) -> dict[str, dict[str, Any]]:
    """For each campaign: the copies and mailings recorded as sent (``references.json``), and, when the profile watches a
    request that names it, how many arrivals answer it and how many of those are recorded. ``returned`` is None for a
    campaign no request watches. Disk only."""
    from jason.community.response_inbox import State
    from jason.tasks import response_inbox as ri
    from jason.tasks.recognize import Catalog

    catalog = Catalog.load(Path(data_dir))
    copies = catalog.copies()
    requests = tuple(getattr(community, "response_requests", lambda: ())() or ()) if community is not None else ()
    arrivals = ri.load_inbox(Path(data_dir)).arrivals if requests else {}
    out: dict[str, dict[str, Any]] = {}
    for code in rows:
        mine = [c for c in copies if c.campaign == code]
        personal = [c for c in mine if c.identity == "copy"]
        watching = next((r for r in requests if r.names_campaign(code)), None)
        returned = recorded = None
        if watching is not None:
            answers = ri.answered_by(Path(data_dir), watching.key)
            ids = {i for c in mine for i in answers.of(c)}
            ids |= {i for reference, found in answers.references.items() if (_prefix(reference) == code) for i in found}
            returned = len(ids)
            recorded = sum(1 for i in ids if i in arrivals and arrivals[i].state is State.RECORDED)
        out[code] = {"copies": len(personal), "mailings": len(mine) - len(personal), "returned": returned, "recorded": recorded,
                     "request": watching.key if watching is not None else ""}
    return out


def _prefix(reference: str) -> str:
    markers = parse(reference)
    return markers[0].campaign if markers else ""


__all__ = ["Campaign", "CampaignRefusal", "CampaignStatus", "STORE", "WORDS", "adopt_existing", "campaign_of", "channel_of",
           "close_campaign", "counts", "for_request", "gate", "judge", "load", "load_raw", "open_campaign", "plan_adoption",
           "require", "stamp", "view"]
