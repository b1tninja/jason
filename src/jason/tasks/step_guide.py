"""The step panel's three objects, composed for a person: ``enable`` (can this person do it now), ``nudge`` (when is it due and who else
sees it), and ``guide`` (what to do, look at, and know), docs/workflows/person-steps.md sections 5 to 7.

One composer for both doors: ``jason.web.extra.work`` hands its three objects to the step panel, and ``jason workflow --guide`` and
``--due`` print the same words at a terminal. It reads the run (already folded by the caller), the roster, the stores a guide read asks,
the authorities shelf (the words of a cite, with the read-through to the outside held off: ``statute_fetch.disabled``), and the
integrations' last recorded state. It writes nothing, sends nothing, and calls no outside system: the page and the loaders it feeds make
no call to PayHOA, Google, Zoom, or a mail service.

Held and administrator runs are the caller's to withhold: nothing here is asked for a held run outside the private view.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from jason.workflows import guide as guide_mod, guide_reads, nudge as nudge_mod
from jason.workflows.nudge import PROPOSED_NOTE, Nudge, Prefs
from jason.workflows.nudge import BOARD
from jason.workflows.types import Role, RunState, RunView, StepDef, StepState, StepView, Visibility, Workflow, role_words

BOARD_OFFICES = frozenset({"president", "vice president", "secretary", "treasurer", "director"})
READING_LABEL = "jason's reading"
VIEWING_AS = "Viewing as {who} (admin view): go back to yourself first."
BACKUPS = {"manager": "president", "president": "vice president"}
"""A proposed default for who stands in for an office (section 5.5), used only when the profile names no backup. A proposal, labeled so."""

DONE_STATES = (StepState.DONE, StepState.SKIPPED, StepState.SUPERSEDED)


# --- who holds which office -----------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Holders:
    """The roster by office: (office, name) rows from the community's officers and its administrators. An empty roster is *unknown*, not
    vacant: a profile that names no officers has not said every office is empty."""

    rows: tuple[tuple[str, str], ...] = ()

    @classmethod
    def from_officers(cls, officers: Iterable[Any] = (), admins: Iterable[Any] = ()) -> "Holders":
        rows = [(o.role.value, o.name) for o in officers if getattr(o, "name", "")]
        rows += [("administrator", a.name) for a in admins if getattr(a, "name", "")]
        return cls(tuple(dict.fromkeys(rows)))

    @property
    def known(self) -> bool:
        """Whether the community names any officer. A roster of administrators alone says nothing about the board's offices."""
        return any(o != "administrator" for o, _ in self.rows)

    def known_for(self, office: str) -> bool:
        return any(o == "administrator" for o, _ in self.rows) if office == "administrator" else self.known

    def names(self, office: str) -> tuple[str, ...]:
        return tuple(dict.fromkeys(n for o, n in self.rows if o == office))

    def roles_of(self, name: str) -> frozenset[str]:
        key = (name or "").strip().casefold()
        return frozenset(o for o, n in self.rows if n.strip().casefold() == key) if key else frozenset()

    def vacant(self, offices: Iterable[str]) -> frozenset[str]:
        return frozenset(o for o in offices if self.known_for(o) and not self.names(o))


@dataclass(frozen=True)
class Person:
    """A signed-in person as the composer needs them: their name and the offices they hold (the same API the web's ``Who`` has)."""

    account: str = ""
    roles: frozenset[str] = frozenset()

    def holds(self, role: Any) -> bool:
        word = role.value if hasattr(role, "value") else str(role)
        if word in ("jason", "scheduler"):
            return False
        return bool(self.account) and (word == "anyone" or word in self.roles)

    def holds_step(self, sd: StepDef) -> bool:
        return any(self.holds(r) for r in sd.acting_roles)


def words_of(role: Any) -> str:
    return role_words(role)


def _office_row(office: str, roster: Holders, who: Any, backup_for: Callable[[str], str] | None) -> dict[str, Any]:
    names = list(roster.names(office))
    if who is not None and getattr(who, "account", "") and who.holds(Role.parse(office) or office) and who.account not in names \
            and office != "anyone":
        names.append(who.account)
    stand = ""
    basis = ""
    if backup_for is not None:
        try:
            stand = str(backup_for(office) or "")
        except Exception:  # noqa: BLE001 - a profile that cannot say has no backup
            stand = ""
    if stand:
        basis = "the profile's"
    elif office in BACKUPS:
        stand, basis = BACKUPS[office], PROPOSED_NOTE
    row: dict[str, Any] = {"office": office, "names": names, "vacant": roster.known_for(office) and not names}
    if stand:
        row["backup"] = {"office": stand, "names": list(roster.names(stand)), "basis": basis}
    return row


def holders_of(sd: StepDef, view: RunView, roster: Holders, who: Any, backup_for: Callable[[str], str] | None = None) -> list[dict[str, Any]]:
    """Who the person is, by office, for every office that may act on the step: its holders, whether it is vacant, and a backup. An
    ``anyone`` step is the run's owner's to see to (section 5.1)."""
    out = []
    for role in sd.acting_roles:
        if role in (Role.JASON, Role.SCHEDULER):
            continue
        if role is Role.ANYONE:
            out.append({"office": "anyone", "names": [view.owner] if view.owner else [], "vacant": False, "owner": True})
        else:
            out.append(_office_row(role.value, roster, who, backup_for))
    return out


# --- enable ---------------------------------------------------------------------------------------------------------------------

def _pos(wf: Workflow, step_id: str) -> int:
    return next((i for i, s in enumerate(wf.steps, 1) if s.id == step_id), 0)


def _day(value: Any) -> str:
    return str(value or "")[:10]


def enable_dict(wf: Workflow, sd: StepDef, sv: StepView, view: RunView, who: Any, roster: Holders, *, acting_as: str = "",
                controls: Iterable[Mapping[str, Any]] = (), integrations: Mapping[str, str] | None = None,
                first_by: str = "", backup_for: Callable[[str], str] | None = None, procedure: Any = None,
                integration_names: Mapping[str, str] | None = None) -> dict[str, Any]:
    """The step's enable state: the first of the ten that applies (section 5.2), with the words, who holds the step, and what is missing.
    ``controls`` are the rows the run page already carries for the step; ``integrations`` maps a key to ``ok``, ``unknown``, or the
    recorded state when it is not signed in."""
    spec = guide_mod.spec(sd, procedure)
    holders = holders_of(sd, view, roster, who, backup_for)
    second_gate = any(c.get("gate") == "second" and c.get("state") == "in force" for c in controls)
    first = first_by or next((str(c.get("firstBy")) for c in controls if c.get("firstBy")), "")
    out: dict[str, Any] = {"state": "ready", "word": "", "holders": holders, "missing": [], "secondPerson": bool(spec.second_person or second_gate),
                           "terminalOnly": bool(spec.terminal), "youHold": sorted(getattr(who, "roles", ())),
                           "owner": view.owner, "inHand": list(spec.in_hand), "accessNote": spec.access_note}

    def set_(state: str, word: str, **more: Any) -> dict[str, Any]:
        out.update(state=state, word=word, **more)
        return out

    if sv.state in DONE_STATES:
        who_did = sv.by or "?"
        if sv.state is StepState.SUPERSEDED:
            return set_("superseded", "Replaced by a later step.")
        if sv.na:
            return set_("not applicable", f"Recorded as not applicable by {who_did} on {_day(sv.at)}.", record=sv.record)
        if sv.state is StepState.SKIPPED:
            return set_("skipped", f"Skipped by {who_did} on {_day(sv.at)}.", record=sv.record)
        return set_("done", f"Done by {who_did} on {_day(sv.at)}.", record=sv.record)
    if acting_as:
        return set_("viewing as", VIEWING_AS.format(who=acting_as))
    if view.state is RunState.DRAFT:
        return set_("draft", "The run has not been opened.")
    if view.state is RunState.PAUSED:
        return set_("paused", f"The run is paused{': ' + view.paused_reason if view.paused_reason else ''}.")
    if view.state in (RunState.DONE, RunState.CANCELLED):
        return set_("closed", f"The run is {view.state.value}.")
    if not who.holds_step(sd):
        offices = " or ".join(words_of(r) for r in sd.acting_roles)
        mine = sorted(r for r in getattr(who, "roles", ()))
        more = f" You are {', '.join('the ' + r for r in mine)}." if mine else ""
        return set_("not yours", f"Waiting on {offices}.", detail=f"Only {offices} can do this.{more}")
    if sv.state in (StepState.NOT_STARTED, StepState.BLOCKED):
        wait = sv.blocked_by[0] if sv.blocked_by else next((n for n in sd.needs if (view.step(n) is not None and view.step(n).state not in DONE_STATES)), "")
        step = view.step(wait)
        return set_("not ready", f"Waits on step {_pos(wf, wait)}: {step.title if step else wait}.",
                    waitsOn={"id": wait, "n": _pos(wf, wait), "title": step.title if step else wait})
    absent = []
    states = integrations or {}
    for key in spec.integrations:
        got = states.get(key, "unknown")
        if got not in ("ok", "unknown"):
            name = (integration_names or {}).get(key, key)
            absent.append({"what": name, "why": f"{name} is {got}", "fix": f"jason integrations check {key} --live"})
    if absent:
        return set_("needs an integration", f"Needs {absent[0]['what']} signed in." if len(absent) == 1
                    else "Needs " + ", ".join(a["what"] for a in absent) + " signed in.", missing=absent)
    if out["secondPerson"]:
        primary = words_of(sd.role)
        word = f"Needs a second person: {primary} or another director."
        if first and who.account and first.casefold() == who.account.casefold():
            more = f"You made the first; a different person confirms."
        elif first:
            more = f"{first} made the first; you are the different person who confirms."
        elif second_gate:
            more = "The first act is recorded as a note and the step stays open."
        else:
            more = "The record names the second person who confirmed it."
        return set_("needs a second person", word, firstBy=first, detail=more)
    if out["terminalOnly"]:
        return set_("terminal only", "A person does this at a terminal.")
    me = next((r for r in sd.acting_roles if r is not Role.ANYONE and who.holds(r)), None)
    word = (f"Yours: you hold the {me.value} office. Nothing is missing." if me is not None
            else "Yours: any signed-in person may do this. Nothing is missing.")
    return set_("ready", word)


# --- nudge ----------------------------------------------------------------------------------------------------------------------

def nudge_dict(n: Nudge, *, who_account: str = "", prefs: Prefs = nudge_mod.DEFAULTS) -> dict[str, Any]:
    """A nudge as the page and the terminal read it: the band and its word, the date and whose it is, how far off, who else sees it, and a
    claim. The three numbers are labeled as proposals until the board adopts them."""
    out: dict[str, Any] = {
        "band": n.band.value, "word": n.word, "due": n.due or None, "days": n.days, "basis": n.basis, "basisLabel": n.basis_label,
        "legal": n.legal, "proposed": n.proposed, "label": n.label, "cite": n.cite, "openDays": n.open_days,
        "escalatedTo": n.escalated_to or None, "escalatedWhy": n.escalated_why, "snoozable": n.snoozable, "items": dict(n.items) if n.items else None,
        "numbers": {"leadDays": n.lead_days, "afterHours": n.after_hours, "escalateAfterHours": prefs.escalate_after_hours,
                    "adopted": prefs.adopted, "note": "" if prefs.adopted else PROPOSED_NOTE},
        "claim": None,
    }
    if n.claim is not None:
        out["claim"] = {"by": n.claim.by, "at": n.claim.at, "stale": n.claim_stale,
                        "mine": bool(who_account) and n.claim.by.casefold() == who_account.casefold()}
    return out


# --- the words of a cite --------------------------------------------------------------------------------------------------------

def _read_only():
    from jason.tasks.statute_fetch import disabled

    return disabled()


def recite_cite(root: Path, cite: Any, day: date, *, community: Any = None, cache: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """One cite recited from what is stored: a statute's words from the authorities shelf (the version in force on ``day`` where the disk
    decides it), or a governing document's section by ``key#section``. The words are whole, as stored; jason's reading follows, labeled.
    A cite the disk cannot resolve says so and recites nothing. The read-through to the outside is held off (``statute_fetch.disabled``)."""
    key = cite.key
    cache = cache if cache is not None else {}
    if key in cache:
        return {**cache[key], "reading": cite.reading}
    kind = guide_mod.kind_of_cite(key)
    out: dict[str, Any] = {"key": key, "kind": "statute" if kind == "shelf" else "document", "words": "", "version": "", "source": "",
                           "reading": cite.reading, "readingLabel": READING_LABEL, "missing": "", "caveats": [], "restatement": "",
                           "command": "", "versions": []}
    try:
        with _read_only():
            if kind == "shelf":
                from jason.community import law_text

                q = law_text.quoted(key, root, day)
                out["restatement"] = law_text.NOT_RESTATEMENT
                if q.text is not None:
                    out.update(words=q.text.words, source=q.text.source, version=f"the words in force on {day.isoformat()}",
                               digest=q.text.digest)
                elif not q.held:
                    out.update(missing=f"The words of {key} are not on the shelf here.", command="jason export-authorities")
                out["caveats"] = [*q.caveats, *([q.note] if q.note else [])]
                if q.several:
                    out["versions"] = [{"digest": v.digest, "words": v.words, "label": q.label(v.digest)} for v in q.held]
                    if q.text is None and q.held:
                        out["version"] = "the shelf holds several versions and the disk does not show which is in force"
            else:
                from jason.tasks.cite import resolve

                got = resolve(key, as_of=day.isoformat(), text=True, community=community, data_dir=root)
                words = got.get("text") if isinstance(got, dict) else ""
                if isinstance(got, dict) and got.get("found") and isinstance(words, str) and words.strip():
                    out.update(words=words, source=str(got.get("citation") or key), version=str(got.get("inForce") or ""),
                               restatement=str(got.get("caveat") or ""))
                else:
                    out.update(missing=f"The words of {key} are not on the shelf here.", command=f"jason cite {key}")
    except Exception as exc:  # noqa: BLE001 - a shelf that cannot be read is said, never guessed
        out.update(words="", missing=f"The words of {key} are not on the shelf here ({type(exc).__name__}).")
    cache[key] = {k: v for k, v in out.items() if k != "reading"}
    return out


# --- guide ----------------------------------------------------------------------------------------------------------------------

_UNSAFE = re.compile(r"^(?:[A-Za-z]:)?[\\/]|(?:^|[\\/])\.\.(?:[\\/]|$)")


def safe_address(address: Any) -> str:
    text = str(address or "")
    kind, sep, rest = text.partition(":")
    body = rest if sep and len(kind) > 1 else text
    return "(a path outside the data folder)" if _UNSAFE.search(body) else text


def _look(item: Any, looked: guide_reads.Looked) -> dict[str, Any]:
    row: dict[str, Any] = {"label": item.label, "kind": "read", "read": item.read, "count": looked.count, "rows": list(looked.rows),
                           "refs": list(looked.refs), "asOf": looked.as_of, "unavailable": looked.unavailable}
    if looked.screen:
        row["screen"] = {"key": looked.screen, "name": looked.screen_name or looked.screen, "href": f"#/{looked.screen}"}
    return row


def look_at(spec: guide_mod.GuideSpec, readers: Any, view: RunView, sd: StepDef, day: date) -> list[dict[str, Any]]:
    """The step's look-at reads (each read, never raising) and, when it names store addresses, one counted row for them: how many are on
    disk now. Counts and handles only."""
    out = [_look(item, guide_reads.run_read(item.read, readers, view, sd, item.args, today=day)) for item in spec.look_at]
    if spec.evidence:
        present, rows = 0, []
        for address in spec.evidence:
            try:
                got = readers.evidence(address) if readers is not None else None
            except Exception:  # noqa: BLE001 - a store that cannot be read has no hash now
                got = None
            present += 1 if got else 0
            rows.append(safe_address(address))
        out.append({"label": "What the step reads", "kind": "evidence", "read": "", "count": present, "of": len(spec.evidence),
                    "rows": rows[:guide_reads.MAX_ROWS], "refs": rows, "asOf": day.isoformat(), "unavailable": ""})
    return out


def _lesson_row(key: str, community: Any) -> dict[str, Any]:
    from jason.community import lessons as lessons_mod

    found = next((l for l in lessons_mod.lessons(community) if l.key == key), None)
    return {"key": key, "status": found.status.value if found is not None else "unknown"}


def guide_dict(root: Path, wf: Workflow, sd: StepDef, view: RunView | None, sv: StepView | None, *, day: date, readers: Any = None,
               roster: Holders = Holders(), who: Any = None, name: str = "", run_id: str = "", community: Any = None,
               procedure: Any = None, backup_for: Callable[[str], str] | None = None,
               cache: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """The step's guide: every section the panel draws, in its order, each derived where the definition wrote nothing. ``view`` is
    ``None`` for a guide read from the definition alone (no run: no counts, no filled placeholders)."""
    spec = guide_mod.spec(sd, procedure)
    commands = []
    for c in spec.commands:
        filled, left = guide_mod.fill_command(c.text, name=name, run=run_id)
        commands.append({"text": filled, "raw": c.text, "note": c.note, "terminalOnly": c.terminal_only, "fillIn": left})
    asks = []
    for role in spec.ask:
        row = _office_row(role.value, roster, None, None)             # the roster alone: every reader is told the same names
        asks.append({"office": role.value, "names": row["names"], "vacant": row["vacant"]})
    sop = {"address": spec.sop, "key": spec.sop_key, "index": spec.sop_index,
           "command": f"jason sop {spec.sop_key}" if spec.sop_key else ""} if spec.sop else None
    return {
        "authored": list(spec.authored), "instruction": spec.instruction, "why": spec.why,
        "lookAt": look_at(spec, readers, view, sd, day) if view is not None else [],
        "rule": [recite_cite(root, c, day, community=community, cache=cache) for c in spec.cites],
        "checklist": [{"text": c.text, "required": c.required} for c in spec.checklist], "requiredChecks": spec.required_checks,
        "commands": commands, "doneWhen": spec.done_when, "record": spec.record, "blocked": spec.blocked,
        "notApplicable": spec.not_applicable, "naOffered": spec.na_declared, "skippable": spec.skippable, "ask": asks,
        "lessons": [_lesson_row(k, community) for k in spec.lessons], "sop": sop,
        "inHand": list(spec.in_hand), "accessNote": spec.access_note, "integrations": list(spec.integrations),
        "secondPerson": spec.second_person, "terminalOnly": spec.terminal,
    }


# --- what is due for a person ---------------------------------------------------------------------------------------------------

def folded(root: Path, wf: Workflow, rid: str, day: date, readers: Any = None, run: Any = None) -> tuple[list[Any], RunView]:
    """A run's events with what opening it now would append (a dry resume: the checks, the approvals and jobs the stores now show), and
    the view of those. Reads only: nothing is written, so a ``--due`` or a ``--guide`` never opens a run. This is the one fold every
    surface reads a run through (the Work list and its run page, the Today bands, the due report, the digest), so the step, the holder,
    and the day agree on all of them. ``run`` is the run already read from the store, when the caller has it."""
    from jason.workflows import fold, resume, store
    from jason.workflows.resume import Readers
    from jason.workflows.types import Event

    readers = readers or Readers()
    run = run if run is not None else store.read(root, wf.key, rid)
    events = list(run.events)
    for _ in range(len(wf.steps) * 3 + 5):
        view = fold.state(events, wf, day, resume.children_of(events, readers), run_id=rid)
        acts = resume.pending(view, events, wf, readers)
        if not acts:
            break
        for act in acts:
            # noon UTC: the same calendar day in every zone from Honolulu to Sydney, so the day basis of "today" holds after a local conversion
            events.append(Event(n=events[-1].n + 1, kind=act.kind, by="jason", at=day.isoformat() + "T12:00:00Z", step=act.step,
                                detail=act.detail))
    return events, fold.state(events, wf, day, resume.children_of(events, readers), run_id=rid)


def step_rows(root: Path, day: date, *, holders: Holders, readers: Any = None, prefs: Prefs = nudge_mod.DEFAULTS,
              reads: Callable[[Workflow], bool] | None = None, everything: bool = False,
              person: str = "") -> list[tuple[StepDef, Nudge, dict[str, Any], str]]:
    """Every person step of every open run that has a nudge (or, with ``everything``, is open), as ``(step, nudge, row, owner)``:
    the board-wide reading both ``due_report`` (one person's) and the digest and the Today band (everyone's) draw on. ``reads``
    says which definitions the caller may know of (default: every one but an administrator's); a held run is its general title and
    nothing else. ``row`` carries no label for a held run; ``owner`` is the run's owner (an ``anyone`` step is theirs to see to).
    Reads the stores; writes nothing."""
    from jason.workflows import definitions, store

    can_read = reads or (lambda wf: wf.visibility is not Visibility.ADMIN)
    out: list[tuple[StepDef, Nudge, dict[str, Any], str]] = []
    for definition, rid in store.list_runs(root):
        wf = definitions.find(definition)
        if wf is None or not can_read(wf):
            continue
        try:
            events, view = folded(root, wf, rid, day, readers)
        except Exception:  # noqa: BLE001 - one unreadable run hides no other
            continue
        held = wf.visibility is Visibility.HELD
        claims = nudge_mod.claims_of(events)
        offices = {r.value for sd in wf.steps for r in sd.acting_roles if r.value not in ("anyone", "jason", "scheduler")}
        for sd, n in nudge_mod.run_nudges(wf, view, day, prefs=prefs, vacant=holders.vacant(offices), claims=claims, quiet=everything):
            title = sd.title if (not held or sd.public_title) else "a step"
            row = {"run": rid, "definition": wf.key, "runLabel": wf.held_title if held else (view.label or wf.title), "held": held,
                   "step": sd.id, "n": _pos(wf, sd.id), "title": title, "holder": " or ".join(words_of(r) for r in sd.acting_roles),
                   "command": f"jason workflow --show {rid}", **nudge_dict(n, who_account=person, prefs=prefs)}
            if held:                          # the general title, the state, the office, the date and its basis word: nothing that names the matter
                row.update(label="", cite="", claim=None)
            out.append((sd, n, row, view.owner))
    return out


def due_report(root: Path, day: date, *, person: str, holders: Holders, readers: Any = None, prefs: Prefs = nudge_mod.DEFAULTS,
               within: int | None = None, everything: bool = False, roles: Iterable[str] | None = None,
               reads: Callable[[Workflow], bool] | None = None) -> dict[str, Any]:
    """The person steps due, late, or open a while for ``person`` (the offices the roster gives them, or ``roles`` where the caller
    knows them, as the console does; an ``anyone`` step is the run's owner's), and the steps escalated to one of their offices
    (visibility, never a message). A held run is its general title and nothing else; an administrator's run is shown to an
    administrator only (or to what ``reads`` allows). Reads the stores; writes nothing. ``within`` keeps a "due soon" or "open" line
    only if its date is within that many days; ``everything`` adds the person's open steps that are quiet."""
    held_roles = frozenset(roles) if roles is not None else holders.roles_of(person)
    admin = "administrator" in held_roles
    mine: list[tuple[Any, dict[str, Any]]] = []
    escalated: list[tuple[Any, dict[str, Any]]] = []
    allowed = reads or (lambda wf: wf.visibility is not Visibility.ADMIN or admin)
    for sd, n, row, owner_name in step_rows(root, day, holders=holders, readers=readers, prefs=prefs, reads=allowed,
                                            everything=everything, person=person):
        owner = Role.ANYONE in sd.acting_roles and owner_name.casefold() == person.casefold()
        holds = owner or any(r.value in held_roles for r in sd.acting_roles if r is not Role.ANYONE)
        sees = bool(n.escalated_to) and not holds and (n.escalated_to in held_roles
                                                       or (n.escalated_to == BOARD and bool(held_roles & BOARD_OFFICES)))
        if not (holds or sees):
            continue
        if within is not None and n.band in (nudge_mod.Band.SOON, nudge_mod.Band.STALE) and not sees and (n.days is None or n.days > within):
            continue
        (mine if holds else escalated).append((nudge_mod.order_key(n), row))

    def key(pair: tuple[Any, dict[str, Any]]) -> tuple[Any, str, int]:
        return pair[0], pair[1]["run"], pair[1]["n"]

    return {"person": person, "roles": sorted(held_roles), "asOf": day.isoformat(), "mine": [r for _, r in sorted(mine, key=key)],
            "escalated": [r for _, r in sorted(escalated, key=key)]}


def due_lines(report: Mapping[str, Any]) -> list[str]:
    """``jason workflow --due``: the lines for a person, most urgent first, each with the command that shows its run."""
    mine, esc = report["mine"], report["escalated"]
    legal = sum(1 for r in mine if r["band"] == "legal")
    offices = ", ".join(f"the {r}" for r in report["roles"]) or "no office on the roster"
    out = [f"Due for {report['person']} ({offices}), as of {report['asOf']} ({len(mine)} step{'s' if len(mine) != 1 else ''}; "
           f"{legal} on a legal clock)"]
    if not mine:
        out.append("  Nothing is due, late, or open a while.")

    def row(r: Mapping[str, Any]) -> list[str]:
        word = (r["word"] or "open").ljust(9)
        if r["held"]:
            what = f"{r['runLabel']}: a step is due" if r["band"] != "quiet" else f"{r['runLabel']}: a step is open"
            tail = f"due {r['due']} [{r['basisLabel']}]" if r["due"] else ""
        else:
            what = f"{r['runLabel']} · step {r['n']}  {r['title']}"
            tail = _due_phrase(r).replace("Due ", "due ", 1)
            if r["legal"] and r.get("cite"):
                tail += f" ({r['cite']})"
        return [f"  {word} {what}   {tail}".rstrip(), f"  {'':9} {r['command']}"]

    for r in mine:
        out += row(r)
    if esc:
        out.append(f"Escalated to you ({len(esc)}): shown here so you can see it; nothing was sent to anyone")
        for r in esc:
            out += row({**r, "title": f"{r['title']} ({r['holder']})"})
    return out


# --- the terminal's words --------------------------------------------------------------------------------------------------------

def _due_phrase(nd: Mapping[str, Any]) -> str:
    if not nd.get("due"):
        return ("needs a date" if nd.get("band") == "date" else "no date")
    days = nd.get("days")
    when = "" if days is None else (" today" if days == 0 else f", {abs(days)} day{'s' if abs(days) != 1 else ''} {'late' if days < 0 else 'to go'}")
    basis = f" [{nd['basisLabel']}]" if nd.get("basisLabel") else ""
    return f"Due {nd['due']}{basis}{when}"


def text_lines(title: str, n: int, of: int, guide: Mapping[str, Any], enable: Mapping[str, Any] | None = None,
               nudge: Mapping[str, Any] | None = None) -> list[str]:
    """The guide as plain text, in the panel's order, with the commands on their own lines (section 7.4)."""
    out = [f"{n}. {title}" if n else title]
    if enable:
        out.append(f"  {enable['word']}" + (f"  {enable['detail']}" if enable.get("detail") else ""))
        for m in enable.get("missing") or ():
            out.append(f"    missing: {m['why']} ({m['fix']})")
    if nudge:
        line = _due_phrase(nudge)
        if nudge.get("word"):
            line = f"{nudge['word']}  {line}"
        out.append(f"  {line}")
        if nudge.get("escalatedTo"):
            out.append(f"  Also seen by {nudge['escalatedTo']}: {nudge.get('escalatedWhy', '')}.")
        if nudge.get("claim"):
            c = nudge["claim"]
            out.append(f"  {c['by']} is on it since {_day(c['at'])}" + (" (still open)" if c.get("stale") else "") + ".")
        if nudge.get("band") in ("soon", "stale") or nudge.get("escalatedTo"):
            nums = nudge["numbers"]
            if nums.get("note"):
                out.append(f"  The lead, the open-a-while threshold, and the escalation delay are {nums['note']}.")

    def section(name: str, body: list[str]) -> None:
        if body:
            out.extend(["", name, *[f"  {b}" if b else "" for b in body]])

    section("Do this", [guide["instruction"]] + ([f"Why: {guide['why']}"] if guide.get("why") else []))
    looks = []
    for l in guide.get("lookAt", ()):
        if l.get("unavailable"):
            looks.append(f"{l['label']}: could not read: {l['unavailable']}")
        else:
            looks.append(f"{l['label']}: {l['count']}" + (f" of {l['of']}" if l.get("of") else "") + f" (as of {l['asOf']})")
            looks.extend(f"  {r}" for r in l.get("rows", ()))
    section("Look at", looks)
    rule: list[str] = []
    for r in guide.get("rule", ()):
        if r["missing"]:
            rule += [r["missing"]] + ([f"  Bring them down with: {r['command']}"] if r.get("command") else [])
            continue
        rule += [f"{r['key']}  ({r['version']})" if r.get("version") else r["key"], *[f"  | {line}" for line in r["words"].splitlines() if line.strip()]]
        if r.get("source"):
            rule.append(f"  Source: {r['source']}")
        if r.get("restatement"):
            rule.append(f"  Caveat: {r['restatement']}")
        if r.get("reading"):
            rule.append(f"  {r['readingLabel']}: {r['reading']}")
    section("The rule", rule)
    section("Check before you go on", [f"[ ] {c['text']}" + ("  (required)" if c["required"] else "") for c in guide.get("checklist", ())])
    cmds = []
    for i, c in enumerate(guide.get("commands", ()), 1):
        cmds.append(f"{i}. {c['text']}" + (f"   ({c['note']})" if c.get("note") else ""))
        if c.get("fillIn"):
            cmds.append(f"   fill in: {', '.join(c['fillIn'])}")
        if c.get("terminalOnly"):
            cmds.append("   A person applies this at a terminal.")
    section("The command", cmds)
    section("Done when", [guide["doneWhen"]] if guide.get("doneWhen") else [])
    section("If you are blocked", [guide["blocked"]])
    section("If it does not apply", [guide["notApplicable"]])
    asks = [f"{words_of(a['office'])}" + (f" ({', '.join(a['names'])})" if a["names"] else " (vacant)" if a["vacant"] else "") for a in guide.get("ask", ())]
    section("Ask", [", ".join(asks)] if asks else ["No one is named for this. Tell the president."])
    more = []
    if guide.get("sop"):
        more.append(f"{guide['sop']['command']} (step {guide['sop']['index']})")
    more += [f"Lesson: {l['key']} ({l['status']})" for l in guide.get("lessons", ())]
    section("Learn more", more)
    return out


__all__ = ["BACKUPS", "BOARD_OFFICES", "DONE_STATES", "Holders", "Person", "READING_LABEL", "VIEWING_AS", "enable_dict", "guide_dict",
           "holders_of", "look_at", "nudge_dict", "recite_cite", "safe_address", "text_lines", "words_of"]
