"""The property family's reads (docs/workflows/property-safety-vendors.md): the life-safety record, the deficiency register,
the loss packet, a contract's notice windows, the backflow tester and the assemblies, the paint catalog, the elevated-elements
due day, what a contract's counterparty owes, the managing agent's statement, an improvement request's entry, and a
maintenance program's standing.

Each is a ``check`` (``jason.workflows.checks``): it reads stores that are already on disk through the task modules' own read
functions, writes nothing, reaches no network, and calls no vendor, insurer, PayHOA, or Google. A read that cannot be made
(a missing or damaged store, a profile with no such fact) is ``ok=False`` with the reason, never ``ok`` by default and never an
exception. The profile is asked only through ``readers.community``, and only when a read needs a fact of it.

**What ok means.** A check passes when the thing it reads is *there*: the act is on the register, the packet assembles, the
lists were fetched. What the read *found* (a color renamed, a tester listed under another business, an obligation overdue) is in
the message for a person, because a difference is the input to the next step and never a reason to hide it.

**Privacy.** A deficiency's impairment answer and the insurer correspondence may bear on a claim (P2). A check on the register
names the row's id, the day an act was recorded, and a library reference; it never says what a person answered, never quotes the
deficiency's words, and never names who acted. The loss packet reports counts and never a unit, an owner, or a name. The
tester's name, the inspector's, and a counterparty's are never in a message. Amounts are integer cents; none is read here.
"""

from __future__ import annotations

import functools
import json
import re
from datetime import date, timedelta
from typing import Any, Callable

from jason.workflows.checks import check
from jason.workflows.types import CheckResult, RunView

TESTER_LIST_DAYS = 365
"""A tester list older than this is flagged (the page's proposed number, not a law's)."""

_SHORT = 200


def _no(why: str) -> CheckResult:
    return CheckResult(False, (), why)


def _guard(what: str) -> Callable[[Callable], Callable]:
    """A read that raises is a read that failed: ``ok=False`` naming what could not be read, never an exception and never ok."""

    def wrap(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def run(readers: Any, view: RunView, item: str = "") -> CheckResult:
            try:
                return fn(readers, view, item)
            except Exception as exc:  # noqa: BLE001 - an unreadable store fails the check with the reason
                text = " ".join(str(exc).split())[:_SHORT]
                return _no(f"{what} cannot be read: {type(exc).__name__}" + (f": {text}" if text else ""))

        return run

    return wrap


def _community(readers: Any) -> tuple[Any, str]:
    """(the profile, "") or (None, why not). A profile is asked for only by the reads that need a fact of it."""
    try:
        found = readers.community
    except Exception as exc:  # noqa: BLE001 - no community chosen
        return None, f"no community is chosen ({type(exc).__name__})"
    if found is None:
        return None, "no community is chosen"
    return found, ""


def _evidence(readers: Any, *addresses: str) -> tuple[str, ...]:
    return readers.evidence_entries(addresses)


def _tally(words: list[str]) -> str:
    counts: dict[str, int] = {}
    for w in words:
        counts[w] = counts.get(w, 0) + 1
    return ", ".join(f"{n} {w}" for w, n in sorted(counts.items())) or "none"


def _day(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value or "")[:10])
    except ValueError:
        return None


# --- the life-safety record -----------------------------------------------------------------------------------------

LIFE_SAFETY_FILES = ("file:documents/readings.json", "file:schedule/done.jsonl", "file:drive/vendor-files.jsonl")


def _life_safety(readers: Any, item: str) -> tuple[Any, str]:
    """(the records, "") or (None, why not). ``item`` narrows the read to one system when it is a listed system's key; an item
    that is not one (a period, a report) leaves the whole record in view."""
    community, why = _community(readers)
    if community is None:
        return None, why
    from jason.tasks import inspections

    records = inspections.review(readers.data_dir, community, as_of=readers.today)
    if not records.listed or not records.systems:
        return None, "the profile lists no life-safety system, so no obligation's record can be read"
    return (records.of(item) if item and records.of(item) is not None else records), ""


@check("life-safety-standing")
@_guard("the life-safety records")
def life_safety_standing(readers: Any, view: RunView, item: str = "") -> CheckResult:
    """Each obligation's standing for its system, from the calendar row the life-safety loader carries, and how many periods
    stand covered, partly on file, not on file, or not yet due. It passes when the record can be read; an overdue obligation or
    a period with nothing on file is the message, because it is what the step goes on to ask the servicer about."""
    records, why = _life_safety(readers, item)
    if records is None:
        return _no(why)
    standings: list[str] = []
    periods: dict[str, int] = {}
    for s in records.systems:
        for o in s.obligations:
            standings.append(str((o.calendar or {}).get("standing") or "none on record"))
            for word, n in o.counts().items():
                periods[word] = periods.get(word, 0) + n
    if not standings:
        return _no(f"{len(records.systems)} system(s) are listed but no obligation applies to them in the record")
    message = (f"{len(standings)} obligation(s) for {len(records.systems)} system(s): {_tally(standings)}; periods: "
               + ", ".join(f"{n} {w}" for w, n in sorted(periods.items())) + f"; {len(records.unplaced)} report(s) unplaced")
    return CheckResult(True, _evidence(readers, *LIFE_SAFETY_FILES), message)


@check("life-safety-reports-read")
@_guard("the life-safety records")
def life_safety_reports_read(readers: Any, view: RunView, item: str = "") -> CheckResult:
    """Every report the filing log shows filed has been read into the record (a filing with no reading is the model pass not
    run, or run and unable to read it), and at least one report is on file to read. A report no period could hold is for the
    placing step and does not fail this one."""
    records, why = _life_safety(readers, item)
    if records is None:
        return _no(why)
    unread = sum(len(s.not_read) for s in records.systems)
    placed = sum(len(p.reports) for s in records.systems for o in s.obligations for p in o.periods)
    placed += sum(len(o.earlier) for s in records.systems for o in s.obligations) + sum(len(s.unassigned) for s in records.systems)
    held = len(records.unplaced)
    message = f"{placed} report(s) placed, {held} not placed, {unread} filed and not read"
    evidence = _evidence(readers, *LIFE_SAFETY_FILES)
    if unread:
        return CheckResult(False, evidence, message + ": the filed pass (jason models --filed) has not read every report")
    if not (placed or held):
        return CheckResult(False, evidence, "no report is on file to read for the record")
    return CheckResult(True, evidence, message)


# --- the deficiency register ----------------------------------------------------------------------------------------

def _register(readers: Any, view: RunView, item: str) -> tuple[dict[str, Any] | None, dict[str, Any], str]:
    """(the row, its state, "") or (None, {}, why not). The run's subject is the register row's id."""
    from jason.tasks import deficiencies

    if not (readers.data_dir / deficiencies.STORE).is_file():
        return None, {}, "the deficiency register is not on disk"
    rows = deficiencies.load(readers.data_dir)
    ident = str(view.subject or "").strip()
    row = next((r for r in rows if r.get("id") == ident), None) or next((r for r in rows if item and r.get("id") == item), None)
    if row is None:
        return None, {}, f"no deficiency {ident or '(no id)'} is in the register"
    return row, deficiencies.state_of(row), ""


def _register_evidence(readers: Any) -> tuple[str, ...]:
    from jason.tasks import deficiencies

    return _evidence(readers, f"file:{deficiencies.STORE.as_posix()}")


def _at(act: Any) -> str:
    return str((act or {}).get("at") or "")[:10] or "an unrecorded day"


@check("deficiency-confirmed")
@_guard("the deficiency register")
def deficiency_confirmed(readers: Any, view: RunView, item: str = "") -> CheckResult:
    """The row has been confirmed against the report: a person's act is on the register. A proposed row is not yet a finding."""
    row, state, why = _register(readers, view, item)
    if row is None:
        return _no(why)
    if not state["confirmed"]:
        return CheckResult(False, _register_evidence(readers), f"{row['id']} is only proposed: no confirmation is on the register")
    return CheckResult(True, _register_evidence(readers), f"{row['id']}: the confirmation is on the register, dated {_at(state['confirmed'])}")


@check("deficiency-impairs-recorded")
@_guard("the deficiency register")
def deficiency_impairs_recorded(readers: Any, view: RunView, item: str = "") -> CheckResult:
    """A person has recorded an answer to whether the deficiency impairs a scheduled safeguard. The answer is P2 and is not in
    the message: only that one is recorded, and its day."""
    row, state, why = _register(readers, view, item)
    if row is None:
        return _no(why)
    if state["impairs"] is None:
        return CheckResult(False, _register_evidence(readers), f"{row['id']}: no answer on impairment is recorded; jason never infers one")
    return CheckResult(True, _register_evidence(readers),
                       f"{row['id']}: an answer on impairment is recorded, dated {_at(state['impairsBy'])}")


@check("deficiency-insurer-told")
@_guard("the deficiency register")
def deficiency_insurer_told(readers: Any, view: RunView, item: str = "") -> CheckResult:
    """The act 'insurer told' is on the register with the day and the record of what was sent (a reference, not its words).
    jason tells no insurer; this reads what a person recorded."""
    row, state, why = _register(readers, view, item)
    if row is None:
        return _no(why)
    told = state["insurerTold"]
    if told is None:
        return CheckResult(False, _register_evidence(readers), f"{row['id']}: no record shows the insurer was told")
    return CheckResult(True, _register_evidence(readers),
                       f"{row['id']}: told on {told.get('on') or _at(told)}, record {told.get('record') or 'not named'}"
                       f"{'' if told.get('inLibrary') else ' (not in the library)'}")


@check("deficiency-cleared")
@_guard("the deficiency register")
def deficiency_cleared(readers: Any, view: RunView, item: str = "") -> CheckResult:
    """A record that cleared the deficiency is linked: its kind, its library reference, and its day. A subject line or free text
    cannot clear a row, and the register refuses a clearing record dated before the finding."""
    row, state, why = _register(readers, view, item)
    if row is None:
        return _no(why)
    cleared = state["cleared"]
    if cleared is None:
        return CheckResult(False, _register_evidence(readers), f"{row['id']} is {state['standing']}: no clearing record is linked")
    return CheckResult(True, _register_evidence(readers),
                       f"{row['id']}: cleared on {cleared.get('on') or _at(cleared)} by {cleared.get('kind') or 'a record'} "
                       f"{cleared.get('record') or '(no reference)'}")


@check("deficiency-board-item")
@_guard("the board items")
def deficiency_board_item(readers: Any, view: RunView, item: str = "") -> CheckResult:
    """A confirmed deficiency has its board item (the register writes one after each act). The priority is not in the message:
    jason's proposal rises with an impairment, which is P2. The board closes the item, never a clear."""
    from jason.tasks import board_items, deficiencies

    row, state, why = _register(readers, view, item)
    if row is None:
        return _no(why)
    evidence = _evidence(readers, f"file:{deficiencies.STORE.as_posix()}", f"file:{board_items.STORE.as_posix()}")
    if not state["confirmed"]:
        return CheckResult(False, evidence, f"{row['id']} is only proposed: a board item exists once a person confirms it")
    wanted = deficiencies.item_id(row["id"])
    found = next((i for i in board_items.load(readers.data_dir) if i.id == wanted), None)
    if found is None:
        return CheckResult(False, evidence, f"{row['id']} is confirmed but board item {wanted} is not on the board's list")
    return CheckResult(True, evidence, f"board item {found.id} is on the board's list, {found.status.value}")


# --- the loss packet ------------------------------------------------------------------------------------------------

@check("loss-packet")
@_guard("the loss packet")
def loss_packet(readers: Any, view: RunView, item: str = "") -> CheckResult:
    """The five-question loss packet assembles over the profile's ladder, the master policy, and a person's confirmations. The
    item is the unit's id (a record is asked for by its id, never by what it says); the run's subject is the incident's id.
    Counts only: no unit, owner, or name is in the message."""
    unit = str(item or "").strip()
    if not unit:
        return _no("the packet is for one unit: name the unit's id as the item")
    community, why = _community(readers)
    if community is None:
        return _no(why)
    from jason.tasks import unit_records_view

    incident = str(view.subject or "").partition(":")[2] or str(view.subject or "")
    packet = unit_records_view.loss_packet_view(readers.data_dir, community, unit, incident.strip())
    if not packet.get("found"):
        return _no(str(packet.get("note") or "no loss packet could be assembled"))
    steps = packet.get("steps") or []
    confirmed = sum(1 for s in steps if s.get("state") == "confirmed")
    held = sum(1 for s in steps if s.get("held"))
    policy = "a master policy is on file" if packet.get("policy") else "no master policy is on file"
    message = f"{len(steps)} step(s) assembled: {confirmed} confirmed by a person, {held} with a held note; {policy}"
    if not steps:
        return _no("the ladder has no steps")
    return CheckResult(True, (), message)


# --- a contract's notice windows ------------------------------------------------------------------------------------

def _window_unit(quote: str) -> str:
    """'days' or 'months' as the clause's own words give it; '' when neither or both appear (a person reads it)."""
    days, months = bool(re.search(r"\bdays?\b", quote, re.I)), bool(re.search(r"\bmonths?\b", quote, re.I))
    return "days" if days and not months else "months" if months and not days else ""


def _before(end: date, amount: int, unit: str) -> date:
    if unit == "months":
        from jason.tasks.deadlines import add_months

        return add_months(end, -amount)
    return end - timedelta(days=amount)


def _terms_reading(readers: Any, view: RunView) -> tuple[dict[str, Any] | None, tuple[str, ...], str]:
    """(the run's contract's terms reading, its evidence, "") or (None, (), why not). The run's subject is the reading's key,
    bare or after a ``kind:`` prefix."""
    from jason.tasks import contract_terms

    store = readers.data_dir / contract_terms.STORE
    if not store.is_dir():
        return None, (), "no contract terms have been read yet (jason contract-terms)"
    subject = str(view.subject or "").strip()
    wanted = {subject, subject.partition(":")[2].strip()} - {""}
    reading = next((r for r in contract_terms.load(readers.data_dir) if str(r.get("key")) in wanted), None)
    if reading is None:
        return None, (), "no terms reading has the run's contract as its key"
    evidence = _evidence(readers, *(f"file:{p.relative_to(readers.data_dir).as_posix()}" for p in sorted(store.glob("*.json"))
                                    if json.loads(p.read_text(encoding="utf-8")).get("key") == reading.get("key")))
    return reading, evidence, ""


@check("contract-window")
@_guard("the contract terms")
def contract_window(readers: Any, view: RunView, item: str = "") -> CheckResult:
    """Both edges of each notice window read from the contract, counted back from the term's end: it opens at the longest lead
    (no earlier) and closes at the shortest (no later). A notice outside either edge may not count. The delivery the clause names
    is part of the window. The item, when given, is a clause's id or section."""
    end = _day(view.dates.get("term_ends", ""))
    if end is None:
        return _no("the run has no term_ends date to count the windows back from")
    reading, evidence, why = _terms_reading(readers, view)
    if reading is None:
        return _no(why)
    clauses = [t for t in reading.get("terms") or [] if t.get("window_days")
               and (not item or item in (str(t.get("id")), str(t.get("section"))))]
    if not clauses:
        return CheckResult(False, evidence, "the reading has no notice window with two edges" + (f" for {item}" if item else ""))
    counted: list[str] = []
    unclear: list[str] = []
    for t in clauses:
        lo, hi = sorted(int(n) for n in t["window_days"])
        unit = _window_unit(str(t.get("quote") or ""))
        where = f"section {t.get('section') or '-'}"
        if not unit:
            unclear.append(where)
            continue
        opens, closes = _before(end, hi, unit), _before(end, lo, unit)
        today = readers.today
        where_now = "not yet open" if today < opens else "open" if today <= closes else "closed"
        delivery = ", ".join(t.get("delivery") or ()) or "delivery not named"
        counted.append(f"{where}: opens {opens.isoformat()} (earliest), closes {closes.isoformat()} (latest), "
                       f"{delivery}; today it is {where_now}")
    if not counted:
        return CheckResult(False, evidence, f"{len(unclear)} window(s) have an unclear unit of time; a person reads the clause")
    tail = f"; {len(unclear)} more with an unclear unit of time" if unclear else ""
    return CheckResult(True, evidence, f"term ends {end.isoformat()}; " + "; ".join(counted) + tail)


# --- the backflow tester --------------------------------------------------------------------------------------------

@check("backflow-tester")
@_guard("the tester lists")
def backflow_tester(readers: Any, view: RunView, item: str = "") -> CheckResult:
    """The tester the reports print, against the published lists' dated snapshot. Passes when every list was fetched, the snapshot
    is within a year, and no list lacks the tester; 'listed under another business' passes and is said. Matching is on the name:
    'listed' is never certified. The tester's name is not in the message."""
    community, why = _community(readers)
    if community is None:
        return _no(why)
    from jason.tasks import backflow

    program = community.backflow_program()
    if program is None:
        return _no("the specification sets no backflow program")
    path = readers.data_dir / backflow.SNAPSHOT
    snapshot = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
    found = backflow.check_tester(program, snapshot)
    if not found:
        return _no("the program names no tester to check")
    evidence = _evidence(readers, f"file:{backflow.SNAPSHOT.as_posix()}")
    rows = found.get("lists") or []
    if snapshot is None or not rows:
        return CheckResult(False, evidence, "the tester lists have not been fetched (jason backflow --fetch-testers)")
    words = [str(r.get("found")) for r in rows]
    message = f"{len(rows)} list(s): {_tally(words)}"
    fetched = _day(snapshot.get("fetched"))
    if fetched is None or (readers.today - fetched).days > TESTER_LIST_DAYS:
        return CheckResult(False, evidence, message + f"; the snapshot is older than {TESTER_LIST_DAYS} days or undated (proposed)")
    if "not fetched" in words:
        return CheckResult(False, evidence, message + ": a list was not fetched")
    if "not listed" in words:
        return CheckResult(False, evidence, message + ": the tester is not on every list")
    return CheckResult(True, evidence, message)


# --- the paint catalog ----------------------------------------------------------------------------------------------

@check("paint-catalog")
@_guard("the paint schedule")
def paint_catalog(readers: Any, view: RunView, item: str = "") -> CheckResult:
    """Each scheduled color against the maker's catalog copy on disk (never fetched here): ok, renamed, discontinued, not found, or
    not checked (another maker's). Passes when the schedule and the copy can be read; a difference is the message, and is what the
    board's substitute step is for. The item, when given, is a schedule row's label or a color's code."""
    community, why = _community(readers)
    if community is None:
        return _no(why)
    from jason.tasks import paint_view

    schedules = tuple(community.paint_schedules())
    if not schedules:
        return _no("the association has no color schedule")
    evidence = _evidence(readers, f"file:{paint_view.CATALOG_FILE.as_posix()}")
    catalog = paint_view.open_catalog(readers.data_dir)
    if catalog is None:
        return CheckResult(False, evidence, f"no catalog copy is on disk, so no color is checked ({paint_view.REFRESH_COMMAND})")
    try:
        counts: dict[str, int] = {}
        needs = 0
        for schedule in schedules:
            shown = paint_view.schedule_view(schedule, catalog)
            for row in shown["rows"]:
                for color in row["colors"]:
                    if item and item not in (row["label"], color["code"]):
                        continue
                    counts[color["status"]] = counts.get(color["status"], 0) + 1
            needs += int(shown["needsAPerson"])
    finally:
        catalog.close()
    if not counts:
        return CheckResult(False, evidence, "no scheduled color matches" if item else "the schedule lists no color")
    return CheckResult(True, evidence, f"{sum(counts.values())} color(s): " + ", ".join(f"{n} {w}" for w, n in sorted(counts.items()))
                       + f"; {needs} need a person")


# --- the elevated-elements due day ----------------------------------------------------------------------------------

@check("elevated-due")
@_guard("the elevated-elements records")
def elevated_due(readers: Any, view: RunView, item: str = "") -> CheckResult:
    """Each building the section reaches has a next due day counted from its record (nine years from the last inspection; six
    from the certificate of occupancy where the section's (k) reaches it). A building with no date on record is a question, never
    a guess, and fails the check until a person enters the fact. The item, when given, names a building's label."""
    community, why = _community(readers)
    if community is None:
        return _no(why)
    from jason.community import elevated_inspections

    rows = elevated_inspections.calendar_rows(community, readers.today)
    if item:
        rows = [r for r in rows if item.lower() in str(r.get("name", "")).lower()]
    if not rows:
        return _no("no building the section reaches has a record" + (" matching the item" if item else ""))
    dated = sorted(str(r["next"]) for r in rows if r.get("next"))
    unknown = len(rows) - len(dated)
    past = sum(1 for d in dated if d < readers.today.isoformat())
    message = (f"{len(rows)} building(s) reached: {len(dated)} with a due day"
               + (f", the earliest {dated[0]}" if dated else "") + (f", {past} past" if past else ""))
    if unknown:
        return _no(message + f"; {unknown} with no date on record (a question for a person)")
    return CheckResult(True, (), message)


# --- the backflow assemblies, side by side --------------------------------------------------------------------------------

@check("backflow-assemblies")
@_guard("the backflow program")
def backflow_assemblies(readers: Any, view: RunView, item: str = "") -> CheckResult:
    """The program's assemblies set beside what the water account and the test reports say: how many there are for each
    service, how many have a passed test on record, how many last failed, and how many counts a source gives that differ from
    the assemblies' (none is picked; a person reconciles). Counts only: no serial, location, account, meter, or tag is in the
    message. It passes when the program lists at least one assembly; a difference is the message and the input to the next
    step, never a reason to hide it."""
    community, why = _community(readers)
    if community is None:
        return _no(why)
    from jason.tasks import backflow

    shown = backflow.view(readers.data_dir, community, today=readers.today)
    if not shown.get("found"):
        return _no(str(shown.get("note") or "the specification sets no backflow program"))
    rows = shown.get("assemblies") or []
    if not rows:
        return _no("the program lists no assembly")
    passed = sum(1 for a in rows if a.get("lastPassed"))
    failed = sum(1 for a in rows if a.get("lastFailed") and a["lastFailed"] >= (a.get("lastPassed") or ""))
    none = sum(1 for a in rows if not a.get("lastPassed") and not a.get("lastFailed"))
    differing = len(shown.get("discrepancies") or [])
    message = (f"{len(rows)} assembly(ies): {_tally([str(a.get('service')) for a in rows])}; {passed} with a passed test on record, "
               f"{failed} whose last recorded test failed, {none} with no test on record; {differing} count(s) from another source "
               f"differ from the assemblies' (none picked); {len(shown.get('notices') or [])} notice(s)")
    return CheckResult(True, (), message)


# --- what a contract's counterparty owes ----------------------------------------------------------------------------------

@check("contract-owed")
@_guard("the contract terms")
def contract_owed(readers: Any, view: RunView, item: str = "") -> CheckResult:
    """The deliverables the contract names (logs, reports, records at the end), by who owes each and whether it carries a time.
    It passes when the terms reading exists. Whether a deliverable is *on file* is not read: no store links a deliverable to a
    document, so the message says so and a person reads the list. The item, when given, is a clause's id or section."""
    reading, evidence, why = _terms_reading(readers, view)
    if reading is None:
        return _no(why)
    terms = [t for t in reading.get("terms") or [] if not item or item in (str(t.get("id")), str(t.get("section")))]
    if not terms:
        return CheckResult(False, evidence, "the reading holds no term" + (f" for {item}" if item else ""))
    owed = [t for t in terms if t.get("deliverable")]
    by_party = _tally([str(t.get("party") or "unstated") for t in owed])
    timed = sum(1 for t in owed if t.get("deadline") or t.get("recurrence_months"))
    return CheckResult(True, evidence, f"{len(owed)} deliverable(s) among {len(terms)} term(s): {by_party}; {timed} with a stated time; "
                       "whether each is on file is not read here (no store links a deliverable to a document)")


# --- the managing agent's written statement ------------------------------------------------------------------------------

STATEMENT_ITEMS = 5
"""CIV 5375(a) to (e): the items a managing agent's written statement gives the board."""

READINGS = "documents/readings.json"


@check("contract-statement")
@_guard("the document readings")
def contract_statement(readers: Any, view: RunView, item: str = "") -> CheckResult:
    """Whether the document reading of the run's contract found the managing agent's written statement (CIV 5375) in the
    agreement's own text, and how many of its five items it gives. The statement may be a separate paper: a reading that finds
    none in the agreement is not a finding that none exists, so it fails with that said. The statement's day against the
    90-day window is a person's to read (``agreement_on``). The run's subject is the terms reading's key (``library-ID``)."""
    path = readers.data_dir / READINGS
    if not path.is_file():
        return _no("no document readings are on disk (jason models)")
    subject = str(view.subject or "").strip()
    key = (subject.partition(":")[2].strip() or subject)
    wanted = {key, key.removeprefix("library-")} - {""}
    if not wanted:
        return _no("the run has no contract key as its subject")
    rows = json.loads(path.read_text(encoding="utf-8")).get("readings") or []
    row = next((r for r in rows if str(r.get("id")) in wanted), None)
    evidence = _evidence(readers, f"file:{READINGS}")
    if row is None:
        return CheckResult(False, evidence, "no document reading is stored for the run's contract (jason models)")
    codes = {str(f.get("code")) for f in row.get("findings") or []}
    if "manager-statement" in codes:
        given = (row.get("fields") or {}).get("manager_statement")
        n = len(given) if isinstance(given, list) else None
        words = f"{n} of {STATEMENT_ITEMS} item(s) stated" if n is not None else "its items not counted"
        more = "; the statute asks for each item, even when the answer is none" if "manager-statement-incomplete" in codes else ""
        return CheckResult(True, evidence, f"the agreement carries a managing agent's statement ({words}){more}; "
                           "its date against the 90 days before the agreement is a person's to read")
    if "manager-disclosure" in codes:
        return CheckResult(False, evidence, "the agreement is read as a management agreement and carries no statement; a separate "
                           "statement is not read here, so a person confirms one is on file (CIV 5375)")
    return CheckResult(False, evidence, "the reading does not take the document for a management agreement, so no statement is read; "
                       "a person records that none is needed")


# --- an improvement request's entry in the unit's manual -----------------------------------------------------------------

@check("improvement-findings")
@_guard("the unit's entries")
def improvement_findings(readers: Any, view: RunView, item: str = "") -> CheckResult:
    """The one of the five findings the stores can answer today: *approval, no entry*. It passes when an entry shared with the
    association links to this request (its ``approval`` is ``improvement:<request id>``). A private entry is counted and never
    read, so the finding can say only "no entry shared", never "no entry". The other four (an entry with no approval, records
    that show work with none, an entry that differs from the approval, a condition open) need the request store and the change
    rules, which are not built; the message says so. The item is the unit's id; the run's subject is the request's id. Counts
    only: no unit, owner, or entry text is in the message or the evidence."""
    unit = str(item or "").strip()
    if not unit:
        return _no("the findings are read for one unit: name the unit's id as the item")
    subject = str(view.subject or "").strip()
    request = (subject.partition(":")[2] or subject).strip()
    if not request:
        return _no("the run has no request id as its subject")
    from jason.tasks import unit_records_view

    if not (unit_records_view._unit_dir(readers.data_dir, unit) / "entries.json").is_file():
        return _no("no entries are on file for the unit")
    entries, held = unit_records_view._entries(readers.data_dir, unit, owner=False)
    linked = sum(1 for e in entries if e.approval.strip() in {f"improvement:{request}", request})
    unlinked = sum(1 for e in entries if not e.approval.strip())
    rest = "the other four findings need the request store and the change rules (not built)"
    count = f"{len(entries)} entr(ies) shared with the association, {linked} linking to this request, {unlinked} with no approval reference"
    if not linked:
        return _no(f"no entry shared with the association links to this request ({count}; {held} private, counted and not read); {rest}")
    return CheckResult(True, (), f"{count}; {held} private, counted and not read; {rest}")


# --- a maintenance program's standing -------------------------------------------------------------------------------------

PROGRAM_VISIT_DAYS = 120
"""A program whose latest recorded visit is older than this reads 'not current' (the page's proposed number, not a law's)."""


@check("program-standing")
@_guard("the vendor portal")
def program_standing(readers: Any, view: RunView, item: str = "") -> CheckResult:
    """A maintenance program's standing in three words, each its own: *document*, *adoption*, and *implementation*. Only
    implementation is read today, from the visits on disk for the program's vendor portal (the run's subject, or the item, is the
    portal's key). Document and adoption are 'not read': the program catalog (docs/programs.md) is not built, and a vendor's
    approval is implementation evidence, never an adoption. 'No act on record' is not 'not adopted', and the message never
    says so. It passes when the visits can be read; the count and the latest day are the message, no customer or address."""
    community, why = _community(readers)
    if community is None:
        return _no(why)
    subject = str(view.subject or "").strip()
    key = (item or subject.partition(":")[2] or subject).strip()
    portal = next((p for p in community.vendor_portals() if p.key == key), None)
    if portal is None:
        return _no("the specification declares no vendor portal for this program; its document, adoption, and implementation are not read here")
    from jason.tasks import vendor_portals

    accounts = vendor_portals.load_accounts(readers.data_dir, portal.key)
    unread = "document: not read (no program catalog); adoption: no act read (a vendor's approval is not one)"
    if not accounts:
        return _no(f"implementation: no portal data on disk (jason vendors --sync); {unread}")
    days = sorted(str(s.get("day"))[:10] for a in accounts for s in a.get("services") or [] if _day(s.get("day")) is not None)
    evidence = _evidence(readers, *(f"glob:{vendor_portals.VENDORS_DIR}/{portal.key}/*/{vendor_portals.ACCOUNT}",))
    if not days:
        return CheckResult(False, evidence, f"implementation: {len(accounts)} account(s) on disk and no visit on record; {unread}")
    age = (readers.today - _day(days[-1])).days
    state = "current" if age <= PROGRAM_VISIT_DAYS else f"not current (the latest visit is over {PROGRAM_VISIT_DAYS} days old; proposed)"
    return CheckResult(True, evidence, f"implementation: {len(days)} visit(s) on record, the latest {days[-1]}, {state}; {unread}")


__all__ = ["backflow_assemblies", "backflow_tester", "contract_owed", "contract_statement", "contract_window",
           "deficiency_board_item", "deficiency_cleared", "deficiency_confirmed", "deficiency_impairs_recorded",
           "deficiency_insurer_told", "elevated_due", "improvement_findings", "life_safety_reports_read", "life_safety_standing",
           "loss_packet", "paint_catalog", "program_standing"]
