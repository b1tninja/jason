"""The Work screens' loaders and writer (docs/console/screens/work.md): the open runs, one run, the catalog of definitions, and
the small acts, over ``jason.workflows``.

- ``GET /api/work[?definition=&role=&due=&state=&mine=1&q=]``: the runs, each once, in the group of its most pressing open
  step (``yours``, ``others``, ``clock``, ``board``), legal dates first. ``mine=1`` keeps the ``yours`` group (the Today band).
- ``GET /api/work-run?definition=&id=``: one run. The loader never appends: it folds the stored events, then folds again with
  what opening the run *would* append (a dry resume: the checks, the approvals and jobs the stores now show, the evidence that
  moved), and says so in ``pending``. Writing those events is ``jason workflow --open`` or the ``open`` act.
- ``GET /api/work-definitions[?family=&key=&role=&mine=1]``: the workflows jason has, with drift from their procedures; with
  ``key`` one definition read whole (its steps, clocks, and the statute words a law clock cites).
- ``POST /api/write/work/<definition>/<run id>`` with ``{act, step?, record?, reason?, text?, ...}``: ``attest``, ``arrived``,
  ``skip``, ``na`` (a step recorded as not applicable, with a reason and a record), ``set-date`` (a late or optional date slot
  given a day, with a record), ``reopen``, ``pause``, ``resume``, ``note``, ``cancel``, ``open``, each one ``jason.workflows.api`` function with
  the signed-in person's own name as ``by`` and the roles their offices hold. ``POST /api/write/work/start`` (or
  ``.../<definition>/start``) with ``{definition, subject, label, dates, items?, yes?, dryRun?}`` starts a draft run.

**Who.** A signed-in person whose offices open P2 (the manager and every board office), or an administrator (who then reads
the ``Visibility.ADMIN`` definitions alone): 401 signed out, 403 with ``access.may_see``'s sentence otherwise. The owner view
never reads them (``OWNER_SOURCES`` does not list them). A write is the signer's own: refused while an admin views as someone
else, and a ``by`` in the body naming another person is a 403. The engine decides what a role may do; its sentence is the answer
(403 for a role, 400 for a rule, 409 for a run that moved on).

**What is held back.** A list row carries the run's own label, the step, the role, the date and its basis; never a subject
(it can be a unit), an item, a name, or an answer. A run's page shows the step's own evidence addresses and the history
(``by`` is the signed-in account that acted; text a person typed has any email or phone masked).

**Held and administrator runs** (``jason.workflows.types.Visibility``; ``work_scope`` decides). A ``HELD`` definition (a
hearing, a delinquent account, a records request: CIV 4935(e)) shows a run outside the private view as its ``held_title``, its
state, its group, and the basis word of its date, with the run id as an opaque handle (``held`` is true, the page ``held_page``);
inside the private view (``access.private_window()`` open for an office that opens P3 in it) the whole run, and each opening is a
line in ``access/served.jsonl`` under the run id. Outside it an act on a held run is the 404 a missing run gets, and starting one
is a 403. An ``ADMIN`` definition is listed, read, and started by an administrator only; for anyone else it is not listed, its
runs are not listed or counted, a read is the 404 a missing run gets, and a start is the refusal an unknown definition gets. A
definition with ``console_start`` false (a terminal procedure) is listed, never started here. ``notComposed`` says plainly what
each route could not build. Disk only: nothing here calls PayHOA, Google, or a model.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from jason.web.extra.work_scope import STEP_WORDS

Args = dict[str, str]

ACTS = ("attest", "arrived", "skip", "na", "set-date", "reopen", "pause", "resume", "note", "cancel", "open")
GROUPS = (("yours", "Yours"), ("others", "Waiting on others"), ("clock", "Waiting on a clock"), ("board", "The board"))
DUE_FILTERS = ("soon", "week", "overdue", "legal", "past")
WEEK = 7
BASIS_WORDS = {"law": "LEGAL", "documents": "DOCUMENTS", "counterparty": "COUNTERPARTY", "provider": "PROVIDER",
               "proposed policy": "PROPOSED", "person": "PERSON"}
READING_LABEL = "jason's reading, not the provision"
ACTING_REFUSED = "Viewing as {who} (admin view): go back to yourself first. A step is recorded in a person's own name."
DECISION_ELSEWHERE = ("A decision is recorded in Decisions by the secretary; this screen does not record it, and the step "
                      "reads done once the decision is on record.")
PLAN_ELSEWHERE = "A plan is decided and applied in Approvals; the run reads the result."
NO_RUN = "no run {rid} of {definition}"
ROLE_REFUSALS = (" role that ", "may not skip", "may not record", "may not set date", "may not cancel",
                 "engine's own name", " allows only ",
                 "made the first, so a different person")
KEPT = ("what", "reason", "record", "outcome", "motion", "choice", "item", "ok", "message", "text", "status", "job", "approval",
        "child", "definition", "until", "found", "activated", "legal_clock", "draft", "subject", "label", "dates", "slot", "day",
        "was")
TEXTS = frozenset({"what", "reason", "record", "outcome", "motion", "message", "text", "label", "subject"})
CAVEATS = (
    "Read from the stores on disk. jason decides nothing: a date is the law's, the documents', a counterparty's, jason's "
    "proposal, or a person's, and says which; an act on a plan, a job, or a decision happens on the screen that owns it.",
    "The run page shows the run as opening it now would find it (a dry resume, written nowhere); the list shows each run as "
    "of its last write.",
)


# -- the data folder, the day, the viewer --------------------------------------------------------------------------------------


def _root() -> Path:
    from jason.mcp.county import _data_dir

    return Path(_data_dir(None))


def _today() -> date:
    return date.today()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _gate() -> Any:
    """The request's viewer, or None (sign-in not set up, or no request). 401 signed out and 403 where the viewer's offices do
    not open P2 and the viewer is not an administrator (``work_scope.gate``; an administrator with no office reads only the
    ``Visibility.ADMIN`` definitions)."""
    from jason.web.extra import work_scope

    return work_scope.gate()


def _viewer(*, writing: bool = False) -> Any:
    """The signed-in viewer whose offices open P2 (or an administrator), or abort: 401 signed out, 403 where the offices do
    not open P2 and the viewer is no administrator (and, for a write, while an admin views as someone else). None outside a
    request (a script, or the Python API)."""
    from flask import abort, has_request_context

    from jason.web import access

    if not has_request_context():
        return None
    viewer = access.signed_in()
    if writing and viewer.acting:
        abort(access.refusal(403, ACTING_REFUSED.format(who=viewer.label)))
    if not viewer.admin:
        access.allow(viewer, access.Level.P2)
    return viewer


@dataclass(frozen=True)
class Who:
    """The person looking: their account name (what a write is recorded under) and the roles their offices hold."""

    account: str = ""
    roles: frozenset[str] = frozenset()

    def holds(self, role: Any) -> bool:
        """Whether the viewer's offices hold a step's role (``anyone``: any named person; the engine's own names: nobody)."""
        word = role.value if hasattr(role, "value") else str(role)
        if word in ("jason", "scheduler"):
            return False
        return bool(self.account) and (word == "anyone" or word in self.roles)

    def holds_step(self, sd: Any) -> bool:
        """Whether the viewer holds any role that may act on the step (its primary role or one of the others)."""
        return any(self.holds(r) for r in sd.acting_roles)

    def roles_of(self, name: str) -> tuple[str, ...]:
        """The engine's ``roles_of``: the signer's roles, and no one else's."""
        same = self.account.casefold() == (name or "").strip().casefold()
        return tuple(sorted(self.roles)) if same and self.account else ()


def who_is(viewer: Any) -> Who:
    if viewer is None:
        return Who()
    roles = set(getattr(viewer, "offices", ()) or ())
    if getattr(viewer, "admin", False):
        roles.add("administrator")
    return Who(str(viewer.account or ""), frozenset(roles))


def _abort(status: int, sentence: str, **more: Any) -> None:
    """Refuse a request with ``sentence`` (in a request); outside one, the same words as a ``ValueError``."""
    from flask import abort, has_request_context, jsonify, make_response

    if not has_request_context():
        raise ValueError(sentence)
    resp = make_response(jsonify(error=sentence, **more), status)
    resp.headers["Cache-Control"] = "no-store"
    abort(resp)


# -- the definitions -------------------------------------------------------------------------------------------------------------


def _register(root: Path, problems: list[dict[str, str]]) -> None:
    """The general definitions, registered the first time they are missing (idempotent, never at import). One that fails its
    checks is left out and listed, never guessed."""
    from jason.workflows import definitions
    from jason.workflows.definitions_general import GENERAL, register_general
    from jason.workflows.types import InvalidWorkflow

    if all(definitions.find(build().key) is not None for build in GENERAL):
        return
    try:
        register_general(root)
    except InvalidWorkflow as exc:
        problems.append({"what": "A general definition", "why": f"left out because it failed its checks: {exc}"})
    except Exception as exc:  # noqa: BLE001 - a registry that cannot be read is said, not guessed
        problems.append({"what": "The general definitions", "why": f"could not be registered: {type(exc).__name__}: {exc}"})


def _readers(root: Path, day: date) -> Any:
    from jason.workflows.readers import StoreReaders

    return StoreReaders(root, today=day)


# -- small helpers -----------------------------------------------------------------------------------------------------------------


def _mask(text: Any) -> str:
    from jason.approvals.evidence import mask_text

    return mask_text(str(text or ""))[0]


def _day_of(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value or "")[:10])
    except ValueError:
        return None


def _safe_address(address: Any) -> str:
    """An evidence or link address with no path outside the data folder: ``file:forms/campaigns.json`` stays, a drive-lettered or
    rooted or ``..`` path does not."""
    text = str(address or "")
    kind, sep, rest = text.partition(":")
    body = rest if sep and len(kind) > 1 else text
    if re.match(r"^(?:[A-Za-z]:)?[\\/]", body) or re.search(r"(?:^|[\\/])\.\.(?:[\\/]|$)", body):
        return "(a path outside the data folder)"
    return text


def _basis(clock: Any) -> dict[str, Any]:
    word = clock.basis.value
    return {"basis": word, "basisLabel": BASIS_WORDS.get(word, word.upper()), "legal": word == "law",
            "proposed": word == "proposed policy"}


def _clock_row(c: Any) -> dict[str, Any]:
    return {"key": c.key, "step": c.step, "label": c.label, "due": c.due or None, "status": c.status, "days": c.days,
            "cite": c.cite, **_basis(c)}


def _due(view: Any, step_id: str = "") -> dict[str, Any] | None:
    """The date to show for a run: the step's own clock when it has a date and is not satisfied, else the nearest date on the
    run. ``{date, basis, basisLabel, legal, proposed, label, cite, status, days, step}``."""
    dated = [c for c in view.clocks if c.due and c.status != "satisfied"]
    own = [c for c in dated if step_id and c.step == step_id]
    pool = own or sorted(dated, key=lambda c: (c.due, 0 if c.basis.value == "law" else 1, c.key))
    if not pool:
        return None
    c = pool[0]
    return {"date": c.due, "label": c.label, "cite": c.cite, "status": c.status, "days": c.days, "step": c.step, **_basis(c)}


def _age(view: Any, day: date) -> dict[str, Any]:
    opened, updated = _day_of(view.opened_at), _day_of(view.updated)
    return {"days": (day - opened).days if opened else None, "opened": opened.isoformat() if opened else None,
            "idleDays": (day - updated).days if updated else None, "updated": view.updated}


def _words(role: Any) -> str:
    word = role.value if hasattr(role, "value") else str(role)
    return word if word in ("jason", "scheduler", "anyone") else f"the {word}"


def _step_words(sd: Any) -> str:
    """Who may act on a step in words: the one role, or each of its roles joined by "or"."""
    return " or ".join(_words(r) for r in sd.acting_roles)


# -- the pressing step, whose move it is, the group ------------------------------------------------------------------------


def _ranks() -> dict[Any, int]:
    from jason.workflows.types import StepState as S

    return {S.FAILED: 0, S.NEEDS_PERSON: 1, S.READY: 2, S.RUNNING: 3, S.WAITING: 4}


def _pressing(wf: Any, view: Any) -> Any:
    """The open step a run is about: one a person or jason must act on before one that only waits; among those, a legal date
    first, the nearest date, then the definition's order."""
    rank, found = _ranks(), []
    for i, sv in enumerate(view.steps):
        if sv.state not in rank:
            continue
        due = _due(view, sv.id) if any(c.step == sv.id and c.due and c.status != "satisfied" for c in view.clocks) else None
        found.append(((rank[sv.state], 0 if due and due["legal"] else 1, due["date"] if due else "9999", i), sv))
    return min(found, key=lambda f: f[0])[1] if found else None


def _waiting_on(wf: Any, view: Any, sv: Any) -> dict[str, Any]:
    """Whose move it is, in words: ``{kind, word, role?, detail?}`` with kind one of open, paused, nothing, system, office,
    board, clock, arrival, approval, run."""
    from jason.workflows.fold import clock_due
    from jason.workflows.types import RunState, StepKind, StepState

    if view.state is RunState.DRAFT:
        return {"kind": "open", "word": "someone to open the run", "detail": "a draft: no clock runs until it is opened"}
    if view.state is RunState.PAUSED:
        return {"kind": "paused", "word": "a resume", "detail": _mask(view.paused_reason)}
    if sv is None:
        return {"kind": "nothing", "word": "nothing open", "detail": ""}
    sd = wf.step(sv.id)
    if sv.state is StepState.WAITING:
        if sd.kind is StepKind.PLAN:
            return {"kind": "approval", "word": "the approvals engine", "detail": _mask(sv.reason)}
        if sd.spawns and "child run" in sv.reason:
            return {"kind": "run", "word": "a child run", "detail": _mask(sv.reason)}
        if sd.kind is StepKind.WAIT and sd.clock is not None and clock_due(sd.clock, view.dates) is not None:
            return {"kind": "clock", "word": "a clock", "role": sd.role.value,
                    "detail": sd.clock.label or sd.clock.basis.value}
        return {"kind": "arrival", "word": "an arrival", "role": sd.role.value, "detail": _mask(sv.reason)}
    if sd.role.value in ("jason", "scheduler"):
        return {"kind": "system", "word": "jason", "role": sd.role.value,
                "detail": "the next time the run is opened" if sv.state is StepState.READY else _mask(sv.reason)}
    if sd.kind is StepKind.DECISION:
        return {"kind": "board", "word": f"the board; the {sd.role.value} records", "role": sd.role.value, "detail": ""}
    return {"kind": "office", "word": _step_words(sd), "role": sd.role.value, "detail": ""}


def _group(wf: Any, view: Any, sv: Any, who: Who) -> str:
    from jason.workflows.fold import clock_due
    from jason.workflows.types import RunState, StepKind, StepState

    if view.state in (RunState.DONE, RunState.CANCELLED):
        return "closed"
    if view.state is RunState.DRAFT:
        return "yours" if who.account and who.account.casefold() == view.owner.casefold() else "others"
    if view.state is RunState.PAUSED or sv is None:
        return "others"
    sd = wf.step(sv.id)
    if sv.state is StepState.WAITING:
        dated = sd.kind is StepKind.WAIT and sd.clock is not None and clock_due(sd.clock, view.dates) is not None
        return "clock" if dated and not sd.spawns else "others"
    if sd.kind is StepKind.DECISION:
        return "board"
    if sv.state in (StepState.NEEDS_PERSON, StepState.FAILED, StepState.READY) and who.holds_step(sd):
        return "yours"
    return "others"


def _position(wf: Any, step_id: str) -> int:
    return next((i for i, s in enumerate(wf.steps, 1) if s.id == step_id), 0)


def _row(wf: Any, run: Any, view: Any, who: Who, day: date) -> dict[str, Any]:
    """One list row. No subject, no item, no name: the run's own label, the step, the role, the date and its basis."""
    sv = _pressing(wf, view)
    sd = wf.step(sv.id) if sv is not None else None
    group = _group(wf, view, sv, who)
    open_run = group != "closed"
    due = _due(view, sv.id if sv else "") if open_run else None
    return {
        "id": run.id, "definition": wf.key, "definitionTitle": wf.title, "family": wf.family, "subjectKind": wf.subject,
        "label": _mask(view.label), "state": view.state.value, "group": group,
        "current": ({"id": sv.id, "title": sv.title, "n": _position(wf, sv.id), "of": len(wf.steps), "kind": sv.kind.value,
                     "state": sv.state.value, "role": sv.role.value} if sv is not None
                    else {"id": "", "title": "", "n": 0, "of": len(wf.steps), "kind": "", "state": "", "role": ""}),
        "owner": sd.role.value if sd is not None else "",
        "waitingOn": _waiting_on(wf, view, sv) if open_run else None,
        "mine": bool(sd is not None and who.holds_step(sd) and open_run and view.state.value != "paused"),
        "due": due, "pastLaw": bool(view.past_law), "age": _age(view, day), "paused": view.state.value == "paused",
        "pausedReason": _mask(view.paused_reason), "visibility": wf.visibility.value, "held": False,
    }


def _public_title(wf: Any, step_id: str) -> str:
    """A held run's current step outside the private view: its own title where the definition marks it ``public_title``
    (it names no matter), else "a step"; empty where there is no open step."""
    if not step_id:
        return ""
    sd = wf.step(step_id)
    return sd.title if sd is not None and sd.public_title else STEP_WORDS


def _held_due(due: dict[str, Any] | None) -> dict[str, Any] | None:
    """The date of a held run outside the private view: the day and its basis word, not the clock's label, the statute it
    cites, or the step it belongs to (each can name the matter)."""
    if not due:
        return None
    return {"date": due["date"], "label": "", "cite": "", "status": due["status"], "days": due["days"], "step": "",
            "basis": due["basis"], "basisLabel": due["basisLabel"], "legal": due["legal"], "proposed": due["proposed"]}


def _held_row(wf: Any, row: dict[str, Any]) -> dict[str, Any]:
    """A held run's list row outside the private view: the definition's general title, the state, the group, the date and its
    basis word, whose move it is by office, and an opaque handle (the run id, which is random). No label, subject, step
    title (unless marked public), reason, clock label, or citation."""
    cur, wait = row["current"], row["waitingOn"]
    public = bool(cur["id"]) and _public_title(wf, cur["id"]) != STEP_WORDS
    return {
        "id": row["id"], "handle": row["id"], "definition": wf.key, "definitionTitle": wf.held_title, "family": wf.family,
        "subjectKind": "", "label": wf.held_title, "state": row["state"], "group": row["group"],
        "current": {"id": "", "title": _public_title(wf, cur["id"]), "n": cur["n"] if public else 0, "of": cur["of"] if public else 0,
                    "kind": "", "state": cur["state"], "role": cur["role"]},
        "owner": row["owner"],
        "waitingOn": ({"kind": wait["kind"], "word": wait["word"], "role": wait.get("role", ""), "detail": ""} if wait else None),
        "mine": row["mine"], "due": _held_due(row["due"]), "pastLaw": row["pastLaw"],
        "age": {"days": row["age"]["days"], "opened": None, "idleDays": row["age"]["idleDays"], "updated": ""},
        "paused": row["paused"], "pausedReason": "", "visibility": row["visibility"], "held": True,
    }


def _order(row: dict[str, Any]) -> tuple[int, str, str]:
    """Within a group: a legal date, then any other date by day, then a run with no date; the run id last, for a stable order."""
    due = row["due"]
    return (0 if due and due["legal"] else 1 if due else 2, due["date"] if due else "", row["id"])


def _rows(root: Path, who: Who, day: date, readers: Any, problems: list[dict[str, str]], scope: Any = None) -> list[dict[str, Any]]:
    """Every run the viewer's scope reads, each once. A run of a definition the scope does not read is not here at all (not
    listed, not counted, not a problem); a held run outside the private view is its reduced row (``_held_row``)."""
    from jason.workflows import definitions, fold, resume, store

    out = []
    for definition, rid in store.list_runs(root):
        wf = definitions.find(definition)
        if wf is not None and scope is not None and not scope.reads(wf):
            continue
        # a held run outside the private view says only that it could not be read: an error's words can carry the matter
        quiet = wf is not None and scope is not None and scope.holds_back(wf)
        try:
            run = store.read(root, definition, rid)
        except Exception as exc:  # noqa: BLE001 - one unreadable run hides no other
            problems.append({"what": f"Run {rid}", "why": "could not be read" if quiet else f"could not be read: {exc}"})
            continue
        if wf is None:
            problems.append({"what": f"Run {rid}", "why": f"its definition {definition} is not registered, so it is not listed"})
            continue
        try:
            events = list(run.events)
            view = fold.state(events, wf, day, resume.children_of(events, readers), run_id=rid)
        except Exception as exc:  # noqa: BLE001
            problems.append({"what": f"Run {rid}", "why": "could not be read" if quiet else f"could not be read: {exc}"})
            continue
        row = _row(wf, run, view, who, day)
        if scope is not None and scope.holds_back(wf):
            row = _held_row(wf, row)
        row["torn"], row["corrupt"] = bool(run.torn), run.corrupt
        out.append(row)
    return out


def _due_filter(rows: list[dict[str, Any]], word: str) -> list[dict[str, Any]]:
    def days(r: dict[str, Any]) -> int | None:
        return r["due"]["days"] if r["due"] else None

    if word in ("soon",):
        return [r for r in rows if days(r) is not None and days(r) <= WEEK]
    if word == "week":
        return [r for r in rows if days(r) is not None and 0 <= days(r) <= WEEK]
    if word == "overdue":
        return [r for r in rows if days(r) is not None and days(r) < 0]
    if word == "legal":
        return [r for r in rows if r["due"] and r["due"]["legal"]]
    return [r for r in rows if r["pastLaw"]]


# -- GET /api/work -----------------------------------------------------------------------------------------------------------------


def not_composed(extra: Iterable[dict[str, str]] = ()) -> list[dict[str, str]]:
    base = [
        {"what": "Executive-session runs (CIV 4935(e))",
         "why": "Held by definition, not by step: a hearing, a delinquent account, and a records request show a general title "
                "and a state only outside the private view, and each opening in the private view is logged. No step of any "
                "other definition is marked executive, so those runs show in full at this level."},
        {"what": "Waiting on the member, a vendor, or an authority",
         "why": "A wait names the clock or the arrival it waits for, not a counterparty, so it reads 'a clock' or 'an arrival', "
                "with the clock's own label."},
        {"what": "The follow-up a past legal date opens",
         "why": "The engine reports a past law clock and opens no follow-up; the run says so and links none."},
    ]
    return base + list(extra)


def _flag(args: Args, key: str) -> bool:
    return str(args.get(key) or "").strip().lower() in ("1", "true", "yes", "on")


def work(args: Args) -> dict[str, Any]:
    """``GET /api/work?definition=&role=&due=&state=&mine=1&q=``: the runs, each once, in the group of its most pressing open
    step. ``counts`` are the signed-in person's whole picture (open runs, per group, due this week, past a legal date) before
    the filters; ``shown`` is after them. A run's own page is where its steps are."""
    from jason.workflows import api, definitions
    from jason.workflows.types import Role, RunState

    from jason.web.extra import work_scope

    viewer = _gate()
    who = who_is(viewer)
    scope = work_scope.scope_of(viewer)
    root, day = _root(), _today()
    problems: list[dict[str, str]] = []
    _register(root, problems)

    state = (args.get("state") or "open").strip().lower()
    if state not in ("open", "all") and state not in {s.value for s in RunState}:
        raise ValueError(f"state is open, all, or one of {', '.join(s.value for s in RunState)}")
    role = (args.get("role") or "").strip().lower()
    if role and Role.parse(role) is None:
        raise ValueError(f"role is one of {', '.join(r.value for r in Role)}")
    due = (args.get("due") or "").strip().lower()
    if due and due not in DUE_FILTERS:
        raise ValueError(f"due is one of {', '.join(DUE_FILTERS)}")
    definition = (args.get("definition") or "").strip()
    text = " ".join((args.get("q") or "").lower().split())

    every = _rows(root, who, day, _readers(root, day), problems, scope)
    opened = [r for r in every if r["state"] in api.OPEN_STATES]
    counts = {"open": len(opened), "dueThisWeek": sum(1 for r in opened if r["due"] and r["due"]["days"] is not None
                                                      and 0 <= r["due"]["days"] <= WEEK),
              "overdue": sum(1 for r in opened if r["due"] and r["due"]["days"] is not None and r["due"]["days"] < 0),
              "pastLegal": sum(1 for r in opened if r["pastLaw"]),
              **{key: sum(1 for r in opened if r["group"] == key) for key, _ in GROUPS}}

    rows = opened if state == "open" else every if state == "all" else [r for r in every if r["state"] == state]
    if definition:
        rows = [r for r in rows if r["definition"] == definition]
    if role:
        rows = [r for r in rows if r["owner"] == role]
    if text:
        rows = [r for r in rows if text in f"{r['label']} {r['definitionTitle']} {r['current']['title']}".lower()]
    if due:
        rows = _due_filter(rows, due)
    if _flag(args, "mine"):
        rows = [r for r in rows if r["group"] == "yours"]
    order = {key: i for i, (key, _) in enumerate(GROUPS)}
    rows.sort(key=lambda r: (order.get(r["group"], len(order)), _order(r)))
    opened_held = sum(1 for r in rows if r["visibility"] == "held" and not r["held"])
    if opened_held:                          # held runs listed in full (the private view): the reading is logged
        work_scope.log_opening(scope, "api/work", runs=opened_held)
    return {
        "found": True, "asOf": day.isoformat(), "state": state, "counts": counts, "shown": len(rows), "runs": rows,
        "groups": [{"key": key, "title": title, "count": sum(1 for r in rows if r["group"] == key)} for key, title in GROUPS],
        "definitions": [{"key": w.key, "title": w.title, "family": w.family}
                        for w in sorted(definitions.all_definitions(), key=lambda w: (w.family, w.key)) if scope.reads(w)],
        "roles": [r.value for r in Role], "viewer": {"roles": sorted(who.roles)},
        "empty": "No runs are open. Start one from Start a run." if not counts["open"] and not problems else "",
        "caveats": list(CAVEATS), "problems": problems, "notComposed": not_composed(problems),
    }


# -- one run ---------------------------------------------------------------------------------------------------------------------


def dry_resume(run: Any, wf: Any, day: date, readers: Any) -> tuple[list[Any], list[Any]]:
    """The run's events with what opening it now would append, and just those: a read of the stores, written nowhere. The same
    passes ``jason.workflows.resume.resume`` makes, over a list in memory."""
    from jason.workflows import fold, resume
    from jason.workflows.types import Event

    events, virtual = list(run.events), []
    for _ in range(len(wf.steps) * 3 + 5):
        view = fold.state(events, wf, day, resume.children_of(events, readers), run_id=run.id)
        acts = resume.pending(view, events, wf, readers)
        if not acts:
            break
        for act in acts:
            event = Event(n=events[-1].n + 1, kind=act.kind, by="jason", at=_now(), step=act.step, detail=act.detail)
            events.append(event)
            virtual.append(event)
    return events, virtual


def _recite(root: Path, cite: str, day: date, cache: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """The statute's words as the authorities shelf holds them, with jason's note on which version, or why there are none. The
    words are quoted whole, as stored; jason's reading is a separate field, labeled."""
    if cite in cache:
        return cache[cite]
    from jason.community import law_text

    out: dict[str, Any] = {"citation": cite, "section": "", "words": "", "digest": "", "source": "", "note": "", "caveats": [],
                           "versions": [], "undecided": False, "missing": "", "readingLabel": READING_LABEL,
                           "restatement": law_text.NOT_RESTATEMENT}
    try:
        q = law_text.quoted(cite, root, day)
    except Exception as exc:  # noqa: BLE001 - a shelf that cannot be read is said
        out["missing"] = f"The authorities shelf could not be read: {type(exc).__name__}: {exc}"
        cache[cite] = out
        return out
    out["section"] = q.citation
    if q.text is not None:
        out.update(words=q.text.words, digest=q.text.digest, source=q.text.source)
    elif not q.held:
        out["missing"] = f"The authorities shelf does not hold {cite}; its words are not recited here (jason export-authorities)."
    out.update(note=q.note, caveats=list(q.caveats), undecided=q.undecided)
    if q.several:
        out["versions"] = [{"digest": v.digest, "words": v.words, "label": q.label(v.digest)} for v in q.held]
    cache[cite] = out
    return out


def _step_group(wf: Any, step_id: str) -> str:
    """A step group (the response intake's 17, 17.6, 17.7) shows under its own prefix: the definition's ``group``, else the
    prefix its id shares with a sibling's."""
    sd = wf.step(step_id)
    if sd.group:
        return sd.group
    head = step_id.removeprefix(f"{wf.key}.").split(".", 1)[0]
    shared = [s for s in wf.steps if s.id.removeprefix(f"{wf.key}.").split(".", 1)[0] == head]
    return head if len(shared) > 1 else ""


def _phase_of(wf: Any) -> dict[str, tuple[str, str]]:
    return {sid: (p.key, p.title) for p in wf.phases for sid in p.steps}


def _link_state(root: Path, link: Any, readers: Any) -> dict[str, Any]:
    """A link as the run shows it: its kind, its id, and the state its own store gives now (or that it is not read here)."""
    out: dict[str, Any] = {"kind": link.kind, "id": _safe_address(link.address), "step": link.step, "label": _mask(link.label),
                           "state": "", "read": False}
    try:
        if link.kind == "approval":
            from jason.approvals import store as approvals

            out.update(state=approvals.load(link.address, root).status.value, read=True, screen="approvals")
        elif link.kind == "job":
            if (root / "jobs.db").is_file():
                from jason import jobs

                found = next((j for j in jobs.jobs(root, every=True, limit=500) if str(j.id) == str(link.address)), None)
                if found is not None:
                    out.update(state=found.status.value, read=True)
        elif link.kind == "run":
            state = readers.child_state(link.address)
            if state:
                out.update(state=state, read=True, screen="work")
    except Exception as exc:  # noqa: BLE001 - a store that cannot be read is said, never guessed
        out["problem"] = f"could not read: {type(exc).__name__}: {exc}"
    return out


def _evidence_rows(wf: Any, sv: Any, sd: Any, readers: Any) -> list[dict[str, Any]]:
    """What to look at: the addresses the step names, with the hash kept when it was done and the hash now."""
    from jason.workflows import fold

    kept = fold.parse_evidence(sv.evidence)
    moved = {str(c.get("address")): c for c in sv.changed}
    out = []
    for address in dict.fromkeys(list(sd.evidence) + list(kept)):
        try:
            now = readers.evidence(address)
        except Exception:  # noqa: BLE001 - a store that cannot be read has no hash now
            now = None
        was = moved[address].get("was") if address in moved else kept.get(address)
        out.append({"address": _safe_address(address), "kept": was or None, "now": now,
                    "changed": address in moved or bool(was and now and was != now), "present": now is not None})
    return out


def _notice(sd: Any, ctx: Who, view: Any) -> dict[str, Any]:
    """What the viewer may do with one step, from the engine's own rules, and the sentence for each act not offered. Nothing is
    written; the engine decides again when a person acts."""
    from jason.workflows.steps import ACTING
    from jason.workflows.types import RunState, StepKind, StepState

    sv = view.step(sd.id)
    acting = view.state in ACTING
    holds = ctx.holds_step(sd)
    offered, refused = [], {}

    def refuse(act: str, why: str) -> None:
        refused[act] = why

    if sd.kind is StepKind.PERSON or (sd.kind is StepKind.BRANCH and sd.check is None):
        if not acting:
            refuse("attest", f"The run is {view.state.value}; steps are acted on when it is active.")
        elif sv.state is not StepState.NEEDS_PERSON:
            refuse("attest", f"This step is {sv.state.value}, not waiting on a person.")
        elif not holds:
            refuse("attest", f"Waiting on {_step_words(sd)}.")
        else:
            offered.append("attest")
    elif sd.kind is StepKind.DECISION:
        refuse("attest", DECISION_ELSEWHERE)
    elif sd.kind is StepKind.PLAN:
        refuse("attest", PLAN_ELSEWHERE)
    if sd.kind is StepKind.WAIT:
        if acting and sv.state is StepState.WAITING and holds:
            offered.append("arrived")
        elif not holds:
            refuse("arrived", f"Waiting on {_step_words(sd)}.")
    if sd.skip is None or sd.is_legal:
        refuse("skip", "Skip is not offered: this step is required by the law." if sd.is_legal
               else "Skip is not offered: the definition gives this step no skip rule.")
    else:
        allowed = sd.skip.roles or sd.acting_roles
        if not acting or sv.state in (StepState.DONE, StepState.SKIPPED, StepState.SUPERSEDED):
            refuse("skip", f"This step is {sv.state.value}.")
        elif not any(ctx.holds(r) for r in allowed):
            refuse("skip", f"Only {', '.join(_words(r) for r in allowed)} may skip this step.")
        else:
            offered.append("skip")
    if sd.na is not None:        # a step with the not-applicable outcome (a legal step may carry it; it is not a skip)
        allowed = sd.na.roles or sd.acting_roles
        if not acting or sv.state in (StepState.DONE, StepState.SKIPPED, StepState.SUPERSEDED):
            refuse("na", f"This step is {sv.state.value}.")
        elif not any(ctx.holds(r) for r in allowed):
            refuse("na", f"Only {', '.join(_words(r) for r in allowed)} may record this step as not applicable.")
        else:
            offered.append("na")
    if sv.state in (StepState.DONE, StepState.SKIPPED, StepState.FAILED) and view.state not in (RunState.CANCELLED, RunState.DRAFT):
        if holds:
            offered.append("reopen")
        else:
            refuse("reopen", f"Only {_step_words(sd)} may reopen this step.")
    return {"acts": offered, "notOffered": refused}


def _run_acts(wf: Any, view: Any, ctx: Who, acting_as: str) -> dict[str, Any]:
    from jason.workflows.steps import ACTING, CANCEL_ROLES
    from jason.workflows.types import RunState, StepState

    def one(offered: bool, why: str = "", **more: Any) -> dict[str, Any]:
        return {"offered": offered and not acting_as, "why": ACTING_REFUSED.format(who=acting_as) if acting_as else why, **more}

    state = view.state
    legal = (any(c.basis.value == "law" and c.status != "satisfied" for c in view.clocks)
             or any(wf.step(s.id) is not None and wf.step(s.id).is_legal and s.state not in (StepState.DONE, StepState.SKIPPED)
                    for s in view.steps))
    cancel_ok = not legal or any(ctx.holds(r) for r in CANCEL_ROLES)
    settable = [d for d in view.date_slots if d.settable]
    may_set = [d.name for d in settable if (wf.slot(d.name).roles == () or any(ctx.holds(r) for r in wf.slot(d.name).roles))]
    return {
        "open": one(state is RunState.DRAFT, "" if state is RunState.DRAFT else f"The run is {state.value}, not a draft.",
                    needsYes=wf.has_legal_clock()),
        "pause": one(state in ACTING, "" if state in ACTING else f"The run is {state.value}; only a running run is paused."),
        "resume": one(state is RunState.PAUSED, "" if state is RunState.PAUSED else f"The run is {state.value}, not paused."),
        "note": one(True),
        "setDate": one(bool(may_set), ("" if may_set else ("No date is left to set on this run." if not settable
                                                           else "Only the roles the definition names may set these dates.")),
                       slots=may_set),
        "cancel": one(state not in (RunState.CANCELLED, RunState.DONE) and cancel_ok,
                      "" if state not in (RunState.CANCELLED, RunState.DONE) and cancel_ok
                      else (f"The run is already {state.value}." if state in (RunState.CANCELLED, RunState.DONE)
                            else "Only the secretary or the manager may cancel a run with a legal clock."),
                      needsYes=legal, legal=legal),
    }


def _sentence(e: Any, titles: dict[str, str], order: dict[str, int]) -> str:
    """A history line in words: who did what to which step. Text a person typed has any email or phone masked."""
    who = e.by or "?"
    d = e.detail
    step = f"step {order[e.step]}, {titles[e.step]}" if e.step in titles else (f"step {e.step}" if e.step else "the run")
    note = lambda *keys: next((_mask(d[k]) for k in keys if d.get(k)), "")  # noqa: E731
    k = e.kind.value
    if k == "opened":
        return f"{who} started the run as a draft" if d.get("draft") else f"{who} opened the run"
    if k == "resumed":
        return f"{who} opened the run and started its clocks" if d.get("activated") else f"{who} lifted the pause"
    if k == "paused":
        return f"{who} paused the run" + (f": {note('reason')}" if note("reason") else "")
    if k == "cancelled":
        return f"{who} cancelled the run" + (f": {note('reason')}" if note("reason") else "")
    if k == "note":
        return f"{who} noted on {step}: {note('text')}"
    if k == "attested":
        return (f"{who} attested {step}" + (f" ({note('record')})" if note("record") else "")
                + (f", confirming {d['confirms']}" if d.get("confirms") else ""))
    if k == "decided":
        return f"{who} recorded the decision on {step}: {note('outcome')}" + (f" ({note('record')})" if note("record") else "")
    if k == "arrived":
        return f"{who} noted that what {step} waits for has come"
    if k == "skipped":
        return f"{who} skipped {step}" + (f": {note('reason')}" if note("reason") else "")
    if k == "not-applicable":
        return (f"{step[:1].upper()}{step[1:]} recorded as not applicable by {who}" + (f": {note('reason')}" if note("reason") else "")
                + (f" ({note('record')})" if note("record") else ""))
    if k == "date-set":
        return (f"{who} set date {d.get('slot', '?')} to {d.get('day', '?')}"
                + (f", correcting {d['was']}" if d.get("was") else "") + (f": {note('reason')}" if note("reason") else "")
                + (f" ({note('record')})" if note("record") else ""))
    if k == "reopened":
        return f"{who} reopened {step}" + (f": {note('reason')}" if note("reason") else "")
    if k == "check-ran":
        return f"{who} read {step}: " + ("passed" if d.get("ok") else "did not pass") + (f" ({note('message')})" if note("message") else "")
    if k == "job-queued":
        return f"{who} found the job for {step}"
    if k == "job-finished":
        return f"{who} read the job for {step}: " + ("finished" if d.get("ok") else "failed")
    if k == "plan-made":
        return f"{who} linked the approval for {step}"
    if k == "approval-decided":
        return f"{who} read the approval for {step}: {note('status')}"
    if k == "applied":
        return f"{who} read the approval for {step} as applied"
    if k == "waited":
        return f"{who} began the wait at {step}"
    if k == "changed":
        return f"{who} found that what {step} was done on has changed"
    if k == "spawned":
        return f"{who} started a child run from {step}"
    return f"{who} {k} {step}"


def _event(e: Any, titles: dict[str, str], order: dict[str, int], *, virtual: bool = False) -> dict[str, Any]:
    """One history row. ``detail`` is a short list of the event's own words, with contact details masked; evidence is its
    addresses. Never an owner's answer: an event holds addresses and counts."""
    from jason.workflows import fold

    detail: dict[str, Any] = {}
    for key in KEPT:
        value = e.detail.get(key)
        if value in (None, "", [], {}):
            continue
        if key == "dates" and isinstance(value, dict):
            detail[key] = {str(k): str(v) for k, v in value.items()}
        elif key in TEXTS:
            detail[key] = _mask(value)
        elif isinstance(value, (str, int, float, bool)):
            detail[key] = value
    if e.detail.get("items"):
        detail["itemCount"] = len(e.detail["items"])
    if e.detail.get("differences"):
        detail["differences"] = [{"address": _safe_address(x.get("address")), "was": x.get("was"), "now": x.get("now")}
                                 for x in e.detail["differences"] if isinstance(x, dict)]
    if e.detail.get("evidence"):
        detail["evidence"] = [{"address": _safe_address(a), "hash": h or None} for a, h in fold.parse_evidence(e.detail["evidence"]).items()]
    return {"n": e.n, "kind": e.kind.value, "step": e.step, "stepTitle": titles.get(e.step, ""), "by": e.by, "at": e.at,
            "text": _sentence(e, titles, order), "detail": detail, "pending": virtual}


def _changed_rows(view: Any, events: list[Any], titles: dict[str, str], order: dict[str, int], virtual: set[int]) -> list[dict[str, Any]]:
    """Each step that reads 'changed since': the difference and when it was seen. ``pending`` when the difference was found by
    this read and no event holds it yet."""
    last = {}
    for e in events:
        if e.kind.value == "changed" and e.step:
            last[e.step] = e
    out = []
    for sv in view.steps:
        for diff in sv.changed:
            e = last.get(sv.id)
            out.append({"step": sv.id, "stepTitle": titles.get(sv.id, ""), "n": order.get(sv.id, 0), "address": _safe_address(diff.get("address")),
                        "was": diff.get("was"), "now": diff.get("now"), "at": e.at if e else None,
                        "pending": bool(e and e.n in virtual)})
    return out


def _na_outcome(sd: Any) -> dict[str, Any] | None:
    """The not-applicable outcome a step declares: who may record it and what it asks for (a legal step may carry one)."""
    if sd.na is None:
        return None
    return {"roles": [r.value for r in (sd.na.roles or sd.acting_roles)], "reasonRequired": sd.na.reason_required,
            "recordRequired": sd.na.record_required}


def _slot_rows(view: Any, wf: Any) -> list[dict[str, Any]]:
    """Each date slot of the run: its day, who set it after the start, and whether a person may set it now."""
    out = []
    for d in view.date_slots:
        slot = wf.slot(d.name)
        out.append({"name": d.name, "label": d.label, "value": d.value or None, "required": d.required, "late": d.late,
                    "settable": d.settable, "correction": d.correction, "timing": d.timing, "sets": d.sets,
                    "setBy": d.set_by or None, "setAt": d.set_at or None, "record": _mask(d.record) or None,
                    "after": slot.after if slot is not None else "", "roles": [r.value for r in (slot.roles if slot else ())]})
    return out


def _step_controls(root: Path, wf: Any, steps: list[dict[str, Any]], events: list[Any], day: date) -> list[dict[str, str]]:
    """Put ``controls`` on each step an adopted control bites on (docs/console/screens/controls.md, "The required-by-a-control
    line"): one row for each gate, with the sentence the engine refuses with. Nothing is added when no controls source is
    configured, so a run page with no controls is as it was. A control store that cannot be read is a problem on the page, not
    a reason to hide the run (the writer refuses the act in that case)."""
    from jason.workflows import api
    from jason.workflows.types import StepKind

    try:
        from jason.controls import store, view

        if not store.configured(root):
            return []
        attestable = []
        for sd in wf.steps:
            if sd.kind in (StepKind.PERSON, StepKind.DECISION) or (sd.kind is StepKind.BRANCH and sd.check is None) or (
                    sd.skip is not None and not sd.is_legal) or sd.na is not None:
                attestable.append((sd.id, sd.role.value, tuple(r.value for r in sd.acting_roles)))
        pending = {sid: (api.pending_first(events, sid, "attest") or api.pending_first(events, sid, "skip")
                         or api.pending_first(events, sid, "na"))
                   for sid, *_ in attestable}
        rows = view.step_controls(root, wf.key, wf.family, attestable, today=day, pending=pending, community=_community())
    except Exception as exc:  # noqa: BLE001 - the page says what it could not read
        return [{"what": "The controls the board adopted", "why": f"could not be read here ({type(exc).__name__}); the server still refuses an act a control forbids"}]
    for step in steps:
        if step["id"] in rows:
            step["controls"] = rows[step["id"]]
    return []


def compose_run(root: Path, definition: str, rid: str, who: Who, day: date, *, acting_as: str = "",
                readers: Any = None) -> dict[str, Any]:
    """One run, read now: the stored events folded with what opening the run would append (``pending``), each step with whose
    move it is and what the viewer may do, the clocks with their basis (a law clock with the statute's words), the links in
    their current state, the history newest first, and the steps that read 'changed since'."""
    from jason.workflows import definitions, fold, resume, store
    from jason.workflows.types import StepKind

    readers = readers or _readers(root, day)
    wf = definitions.find(definition)
    if wf is None:
        raise ValueError(f"no workflow definition {definition} is registered, so run {rid} cannot be read")
    try:
        run = store.read(root, definition, rid)
    except store.NoSuchRun:
        raise KeyError(f"{definition}/{rid}") from None
    events, virtual = dry_resume(run, wf, day, readers)
    view = fold.state(events, wf, day, resume.children_of(events, readers), run_id=rid)
    titles = {s.id: s.title for s in wf.steps}
    order = {s.id: i for i, s in enumerate(wf.steps, 1)}
    phases = _phase_of(wf)
    links = [_link_state(root, link, readers) for link in view.links]
    by_step: dict[str, list[dict[str, Any]]] = {}
    for link in links:
        by_step.setdefault(link["step"], []).append(link)
    pressing = _pressing(wf, view)
    steps = []
    for i, sd in enumerate(wf.steps, 1):
        sv = view.step(sd.id)
        phase = phases.get(sd.id, ("", ""))
        mine = by_step.get(sd.id, [])
        step: dict[str, Any] = {
            "id": sd.id, "n": i, "of": len(wf.steps), "title": sd.title, "kind": sd.kind.value, "role": sd.role.value,
            "roles": [r.value for r in sd.acting_roles], "na": sv.na, "naOutcome": _na_outcome(sd),
            "waitsOnChild": sd.waits_on_child, "children": list(sv.children),
            "state": sv.state.value, "reason": _mask(sv.reason), "phase": phase[0], "phaseTitle": phase[1],
            "group": _step_group(wf, sd.id), "why": sd.why, "command": sd.command, "sop": sd.sop, "legal": sd.is_legal,
            "needsRecord": sd.record, "record": _mask(sv.record), "by": sv.by, "at": sv.at, "current": bool(pressing and pressing.id == sd.id),
            "blockedBy": list(sv.blocked_by), "items": [{"item": it, "state": st.value} for it, st in sv.items],
            "choice": sv.choice, "choices": [c.key for c in sd.choices], "spawns": sd.spawns,
            "skip": ({"roles": [r.value for r in (sd.skip.roles or sd.acting_roles)], "reasonRequired": sd.skip.reason_required}
                     if sd.skip is not None and not sd.is_legal else None),
            "clock": ({"slot": sd.clock.slot, "days": sd.clock.days, "label": sd.clock.label, "cite": sd.clock.cite,
                       **_basis(sd.clock)} if sd.clock is not None else None),
            "evidence": _evidence_rows(wf, sv, sd, readers), "links": mine, "changed": [
                {"address": _safe_address(c.get("address")), "was": c.get("was"), "now": c.get("now")} for c in sv.changed],
            "waitingOn": (_waiting_on(wf, view, sv) if sv.state.value in ("ready", "running", "waiting", "needs a person", "failed")
                          else None),
            "yours": bool(who.holds_step(sd) and sv.state.value in ("needs a person", "failed", "ready")),
            **_notice(sd, who, view),
        }
        if acting_as:
            step["acts"], step["notOffered"] = [], {a: ACTING_REFUSED.format(who=acting_as) for a in ACTS}
        if sd.kind is StepKind.DECISION:
            d = dict(sv.detail)
            step["decision"] = {"recorded": bool(d.get("outcome")), "motion": _mask(d.get("motion") or sd.title),
                                "outcome": _mask(d.get("outcome")), "record": _mask(d.get("record")), "by": sv.by, "at": sv.at,
                                "final": sv.state.value == "done", "screen": "decisions"}
        elif sd.kind is StepKind.PLAN:
            made = next((l for l in mine if l["kind"] == "approval"), None)
            step["plan"] = {"approval": made["id"] if made else None, "status": made["state"] if made else "",
                            "kind": sd.plan_kind, "screen": "approvals"}
        elif sd.kind is StepKind.JOB:
            made = next((l for l in mine if l["kind"] == "job"), None)
            step["job"] = {"job": made["id"] if made else None, "state": made["state"] if made else "", "name": sd.job}
        steps.append(step)
    control_problems = _step_controls(root, wf, steps, events, day)
    cache: dict[str, dict[str, Any]] = {}
    clocks = []
    for c in view.clocks:
        row = _clock_row(c)
        row["past"] = c.status == "overdue"
        row["stepTitle"] = titles.get(c.step, "")
        row["scope"] = "step" if c.step else "run"
        if c.basis.value == "law" and c.cite:
            row["law"] = {**_recite(root, c.cite, day, cache), "reading": c.label}
        clocks.append(row)
    virtual_n = {e.n for e in virtual}
    history = [_event(e, titles, order, virtual=e.n in virtual_n) for e in reversed(events)]
    problems = list(control_problems)
    for row in clocks:
        if row.get("law", {}).get("missing"):
            problems.append({"what": f"The words of {row['cite']}", "why": row["law"]["missing"]})
    for step in steps:
        for link in step["links"]:
            if not link["read"]:
                problems.append({"what": f"The {link['kind']} {link['id']}",
                                 "why": link.get("problem") or "its state is not read here; open it on its own screen"})
    if run.torn:
        problems.append({"what": "The run's last line", "why": "is torn (a partial write was dropped); the next write cuts it off and keeps its text"})
    if run.corrupt:
        problems.append({"what": f"Line {run.corrupt} of the run", "why": "is not an event; nothing more is appended until a person looks at it"})
    if view.orphans:
        problems.append({"what": "Steps in the events", "why": f"the definition no longer has {', '.join(view.orphans)}"})
    closing = [s["id"] for s in steps if s["state"] in ("ready", "running", "waiting", "needs a person", "failed")]
    return {
        "found": True, "asOf": day.isoformat(), "caveats": list(CAVEATS),
        "run": {
            "id": rid, "definition": wf.key, "definitionTitle": wf.title, "family": wf.family, "label": _mask(view.label),
            "subject": _mask(view.subject), "subjectKind": wf.subject, "state": view.state.value, "n": run.n, "updated": view.updated,
            "opened": view.opened_at, "openedBy": view.owner, "dates": dict(view.dates), "itemCount": len(view.items),
            "dateSlots": _slot_rows(view, wf), "openSlots": [d.name for d in view.date_slots if d.settable],
            "parent": view.parent, "children": list(view.children), "pausedReason": _mask(view.paused_reason),
            "cancelledReason": _mask(view.cancelled_reason), "torn": bool(run.torn), "corrupt": run.corrupt,
            "orphans": list(view.orphans), "pastLaw": list(view.past_law), "age": _age(view, day),
            "current": ({"id": pressing.id, "title": pressing.title, "n": order[pressing.id], "of": len(wf.steps)}
                        if pressing else None),
            "acts": _run_acts(wf, view, who, acting_as), "cancelWill": {"openSteps": closing, "childRuns": list(view.children)},
        },
        "phases": [{"key": p.key, "title": p.title, "steps": list(p.steps)} for p in wf.phases],
        "steps": steps, "clocks": clocks, "links": links, "history": history,
        "changed": _changed_rows(view, events, titles, order, virtual_n),
        "pending": [{"kind": e.kind.value, "step": e.step, "stepTitle": titles.get(e.step, "")} for e in virtual],
        "viewer": {"roles": sorted(who.roles)}, "problems": problems,
        "notComposed": not_composed(problems) + [
            {"what": "The decision's mover, second, and vote",
             "why": "The run keeps the secretary's record reference and outcome; the decisions store is not linked by id, so "
                    "the votes are read on Decisions."},
            {"what": "The step's embedded view (a funnel, a follow-ups band, an arrivals lane)",
             "why": "This route gives the step's evidence addresses and links; the owning screen's own loader feeds the embed."},
        ],
    }


def held_page(root: Path, wf: Any, rid: str, who: Who, day: date, *, readers: Any = None) -> dict[str, Any]:
    """A held run outside the private view, in the shape of ``compose_run`` with nothing in it: the definition's general title,
    the state, the step's title only where the definition marks it public (else "a step"), the date and its basis word. No
    label, subject, dates, steps, evidence address, link, clock, or history sentence (a name, a unit, or a parcel can be in
    any of them); every act reads "not offered" with the sentence that says where the run opens. ``KeyError`` for a run not
    on disk."""
    from jason.web.extra.work_scope import HELD_NOTE
    from jason.workflows import fold, resume, store

    readers = readers or _readers(root, day)
    try:
        run = store.read(root, wf.key, rid)
    except store.NoSuchRun:
        raise KeyError(f"{wf.key}/{rid}") from None
    events = list(run.events)
    view = fold.state(events, wf, day, resume.children_of(events, readers), run_id=rid)
    row = _held_row(wf, _row(wf, run, view, who, day))
    cur = row["current"]
    none = {"offered": False, "why": HELD_NOTE}
    return {
        "found": True, "held": True, "heldTitle": wf.held_title, "heldWhy": HELD_NOTE, "asOf": day.isoformat(),
        "caveats": list(CAVEATS),
        "run": {
            "id": rid, "handle": rid, "definition": wf.key, "definitionTitle": wf.held_title, "family": wf.family,
            "label": wf.held_title, "subject": "", "subjectKind": "", "state": row["state"], "n": 0, "updated": "",
            "opened": "", "openedBy": "", "dates": {}, "itemCount": 0, "dateSlots": [], "openSlots": [], "parent": "",
            "children": [], "pausedReason": "", "cancelledReason": "", "torn": False, "corrupt": 0, "orphans": [],
            "pastLaw": ["law"] if row["pastLaw"] else [], "age": row["age"], "due": row["due"],
            "current": {"id": "", "title": cur["title"], "n": cur["n"], "of": cur["of"]} if cur["title"] else None,
            "acts": {"open": none, "pause": none, "resume": none, "note": none, "cancel": {**none, "legal": False},
                     "setDate": {**none, "slots": []}},
            "cancelWill": {"openSteps": [], "childRuns": []},
        },
        "phases": [], "steps": [], "clocks": [], "links": [], "history": [], "changed": [], "pending": [],
        "viewer": {"roles": sorted(who.roles)}, "problems": [], "notComposed": [],
    }


def work_run(args: Args) -> dict[str, Any]:
    """``GET /api/work-run?definition=&id=``: one run (see ``compose_run``). 404 for a run that is not on disk, and the same
    404 for a run of a definition the viewer may not know of (``Visibility.ADMIN`` for a non-administrator). A held run outside
    the private view answers ``held_page``; inside it, the whole run, and the opening is logged under the run's id."""
    from jason.web.extra import work_scope

    viewer = _gate()
    definition, rid = (args.get("definition") or "").strip(), (args.get("id") or "").strip()
    if not definition or not rid:
        raise ValueError("work-run needs definition= and id=")
    scope = work_scope.scope_of(viewer)
    root, day = _root(), _today()
    problems: list[dict[str, str]] = []
    _register(root, problems)
    from jason.workflows import definitions, store

    try:
        located = store.locate(root, rid)
    except store.NoSuchRun:
        _abort(404, NO_RUN.format(rid=rid, definition=definition))
    wf = definitions.find(located)
    if located != definition or (wf is not None and not scope.reads(wf)):
        _abort(404, NO_RUN.format(rid=rid, definition=definition))
    try:
        if wf is not None and scope.holds_back(wf):
            return held_page(root, wf, rid, who_is(viewer), day)
        if wf is not None and scope.opens_held(wf):
            work_scope.log_opening(scope, f"api/work-run/{rid}")
        return compose_run(root, definition, rid, who_is(viewer), day, acting_as=viewer.label if getattr(viewer, "acting", False) else "")
    except KeyError:
        _abort(404, NO_RUN.format(rid=rid, definition=definition))


# -- the definitions -------------------------------------------------------------------------------------------------------------


def _community() -> Any:
    try:
        from jason.community import community

        return community()
    except Exception:  # noqa: BLE001 - no community chosen: the general procedures only
        return None


def _startable(wf: Any, scope: Any) -> tuple[bool, str]:
    """Whether the console starts a run of this definition for the viewer, and the sentence when it does not: a terminal
    procedure (``console_start`` False), or a held definition outside the private view."""
    from jason.web.extra.work_scope import HELD_START, NOT_FROM_CONSOLE

    if not wf.console_start:
        return False, NOT_FROM_CONSOLE.format(title=wf.title)
    if scope is not None and scope.holds_back(wf):
        return False, HELD_START
    return True, ""


def _definition_row(wf: Any, who: Who, find: Any, drifted: dict[str, list[str]], scope: Any = None) -> dict[str, Any]:
    from jason.community import lessons as lessons_mod

    proc = find(wf.procedure) if wf.procedure else None
    named = sorted({k for s in (proc.steps if proc is not None else ()) for k in s.lessons})
    found = [lessons_mod.lesson(k) for k in named]
    why = drifted.get(wf.key, [])
    startable, startable_why = _startable(wf, scope)
    return {
        "visibility": wf.visibility.value, "held": wf.visibility.value == "held", "heldTitle": wf.held_title,
        "startableWhy": startable_why,
        "key": wf.key, "title": wf.title, "family": wf.family, "subjectKind": wf.subject, "steps": len(wf.steps),
        "phases": [{"key": p.key, "title": p.title, "steps": len(p.steps)} for p in wf.phases],
        "dates": [{"name": d.name, "label": d.label, "required": d.required, "after": d.after,
                   "rule": f"may not come before {d.after}" if d.after else "", "late": d.late, "settable": d.settable,
                   "timing": d.timing.value} for d in wf.dates],
        "legalClock": wf.has_legal_clock(), "procedure": wf.procedure,
        "procedureSteps": len(proc.steps) if proc is not None else None,
        "drift": {"ok": not why, "why": why}, "cadence": "", "startable": startable, "startedBy": [], "needsYes": wf.has_legal_clock(),
        "roles": sorted({r.value for s in wf.steps for r in s.acting_roles}), "mySteps": any(who.holds_step(s) for s in wf.steps),
        "lessons": [{"key": l.key, "status": l.status.value} for l in found if l is not None],
    }


def _definition_page(wf: Any, root: Path, day: date) -> dict[str, Any]:
    """One definition read whole: every step with its kind, role, clock and basis, what it needs and produces, and the sentence
    it shows a person; a law clock's statute words recited from the shelf."""
    cache: dict[str, dict[str, Any]] = {}
    phases = _phase_of(wf)

    def clock(c: Any) -> dict[str, Any]:
        out = {"slot": c.slot, "days": c.days, "label": c.label, "cite": c.cite, **_basis(c)}
        if c.basis.value == "law" and c.cite:
            out["law"] = {**_recite(root, c.cite, day, cache), "reading": c.label}
        return out

    return {
        "key": wf.key, "title": wf.title, "family": wf.family, "subjectKind": wf.subject, "procedure": wf.procedure,
        "dates": [{"name": d.name, "label": d.label, "required": d.required, "after": d.after, "late": d.late,
                   "settable": d.settable, "timing": d.timing.value} for d in wf.dates],
        "clocks": [clock(c) for c in wf.clocks],
        "steps": [{"id": s.id, "n": i, "title": s.title, "kind": s.kind.value, "role": s.role.value,
                   "roles": [r.value for r in s.acting_roles], "naOutcome": _na_outcome(s), "waitsOnChild": s.waits_on_child,
                   "needs": list(s.needs),
                   "why": s.why, "command": s.command, "plan": s.plan_kind, "job": s.job, "evidence": [_safe_address(e) for e in s.evidence],
                   "record": s.record, "legal": s.is_legal, "repeat": s.repeat.value, "spawns": s.spawns, "sop": s.sop,
                   "skip": ({"roles": [r.value for r in (s.skip.roles or s.acting_roles)], "reasonRequired": s.skip.reason_required}
                            if s.skip is not None and not s.is_legal else None),
                   "clock": clock(s.clock) if s.clock is not None else None, "phase": phases.get(s.id, ("", ""))[0],
                   "group": _step_group(wf, s.id)} for i, s in enumerate(wf.steps, 1)],
    }


def work_definitions(args: Args) -> dict[str, Any]:
    """``GET /api/work-definitions[?family=&key=&role=&mine=1]``: the registered workflows, by family, with their step count,
    procedure, drift, and the lessons their procedure names; with ``key`` the one definition read whole. Read only: no control
    edits a definition."""
    from jason.web.extra import work_scope
    from jason.workflows import definitions
    from jason.workflows.types import Role

    viewer = _gate()
    who = who_is(viewer)
    scope = work_scope.scope_of(viewer)
    root, day = _root(), _today()
    problems: list[dict[str, str]] = []
    _register(root, problems)
    role = (args.get("role") or "").strip().lower()
    if role and Role.parse(role) is None:
        raise ValueError(f"role is one of {', '.join(r.value for r in Role)}")
    family = (args.get("family") or "").strip()
    key = (args.get("key") or "").strip()
    text = " ".join((args.get("q") or "").lower().split())
    home = _community()
    from jason.community.procedures import find as find_procedure

    def find(k: str) -> Any:
        return find_procedure(k, home)

    every = sorted((w for w in definitions.all_definitions() if scope.reads(w)), key=lambda w: (w.family, w.key))
    drifted: dict[str, list[str]] = {}
    for p in definitions.drift(every, find):
        owner = next((w.key for w in every if p.row == w.key or any(s.id == p.row for s in w.steps)), p.row)
        drifted.setdefault(owner, []).append(str(p))
    for p in definitions.rejected():
        problems.append({"what": f"Definition {p.row}", "why": f"is left out: {p.message}"})
    rows = [_definition_row(w, who, find, drifted, scope) for w in every]
    by_key = {w.key: w for w in every}

    def matches(r: dict[str, Any]) -> bool:
        wf = by_key[r["key"]]
        return not text or text in f"{r['title']} {r['key']}".lower() or any(text in s.title.lower() for s in wf.steps)

    shown = [r for r in rows if (not family or r["family"] == family) and (not role or role in r["roles"])
             and (not _flag(args, "mine") or r["mySteps"]) and matches(r)]
    families = sorted({r["family"] for r in shown})
    out: dict[str, Any] = {
        "found": True, "asOf": day.isoformat(),
        "counts": {"definitions": len(rows), "shown": len(shown), "families": len({r["family"] for r in rows}),
                   "drifted": sum(1 for r in rows if not r["drift"]["ok"])},
        "families": [{"family": f, "definitions": [r for r in shown if r["family"] == f]} for f in families],
        "definitions": shown,
        "empty": "No workflows are registered." if not rows else "",
        "viewer": {"roles": sorted(who.roles)}, "roles": [r.value for r in Role], "caveats": list(CAVEATS), "problems": problems,
        "notComposed": not_composed(problems) + [
            {"what": "How often a workflow runs", "why": "A definition holds no cadence, so 'cadence' is empty."},
            {"what": "Who may start a workflow",
             "why": "A definition holds no start rule: every office that opens this page may start one, and 'startedBy' is empty. "
                    "The exceptions are the definition's own: a held one starts only in the private view, and a terminal "
                    "procedure (console_start false) is never started here."},
        ],
    }
    if key:
        wf = definitions.find(key)
        if wf is None or not scope.reads(wf):
            _abort(404, f"no workflow definition {key}")
        out["definition"] = {**next(r for r in rows if r["key"] == key), **_definition_page(wf, root, day)}
    return out


# -- the writer ------------------------------------------------------------------------------------------------------------------


def _need(body: dict[str, Any], key: str) -> str:
    value = str(body.get(key) or "").strip()
    if not value:
        raise ValueError(f"{key} is required for this act")
    return value


def _expect(body: dict[str, Any]) -> int | None:
    raw = body.get("expect", body.get("n"))
    if raw in (None, ""):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        raise ValueError(f"expect is the n you last saw, a whole number, not {raw!r}") from None


def _signer(viewer: Any, body: dict[str, Any]) -> tuple[str, Who]:
    """Who is acting and what they hold. In a request: the signed-in account and the roles of its offices, and a ``by`` naming
    another person is a 403. Outside one (the Python API): ``by`` from the body and the roles the community's roster gives."""
    if viewer is not None:
        given = str(body.get("by") or "").strip()
        if given and given.casefold() != viewer.account.casefold():
            _abort(403, f"signed in as {viewer.account}: a step goes on the record under the signed-in name, not {given}")
        return viewer.account, who_is(viewer)
    from jason.commands.workflow import Roster

    roster = Roster()
    by = roster.canonical(str(body.get("by") or "").strip())
    if not by:
        raise ValueError("by is required when no one is signed in")
    return by, Who(by, frozenset(roster.roles_of(by)))


def _refused(exc: Exception) -> None:
    """The engine's refusal as the answer: 403 where it is about a role, 409 for a run that moved on or is held, else 400 (a
    rule); its sentence is the message."""
    from jason.locks import ResourceBusy
    from jason.workflows.types import RunChanged, StepRefused, WorkflowError

    text = str(exc.args[0] if exc.args else exc)
    if isinstance(exc, RunChanged):
        _abort(409, text, expected=exc.expected, actual=exc.actual)
    if isinstance(exc, ResourceBusy):
        _abort(409, text)
    if isinstance(exc, StepRefused) and any(w in text for w in ROLE_REFUSALS):
        _abort(403, text)
    if isinstance(exc, WorkflowError):
        raise ValueError(text) from None
    raise exc


def write(key: str, body: dict[str, Any]) -> dict[str, Any]:
    """``POST /api/write/work/<definition>/<run id>`` with ``{act, step?, record?, reason?, text?, item?, expect?, yes?}``, or
    ``.../start`` (see ``start``). The act is one of ``ACTS``; ``by`` is always the signed-in person. 404 for a run that is not
    on disk; 400 for a rule the engine states; 403 for a role it states or a body ``by`` naming someone else; 409 for a run that
    moved on since ``expect``. Returns the event, what an ``open`` appended, and the run as ``work-run`` gives it."""
    from jason.workflows import api, definitions, store
    from jason.workflows.types import StepKind, WorkflowError

    viewer = _viewer(writing=True)
    parts = [p for p in str(key).strip("/").split("/") if p]
    if parts == ["start"] or (len(parts) == 2 and parts[1] == "start"):
        return start(parts[0] if len(parts) == 2 else "", body, viewer)
    if len(parts) != 2:
        raise KeyError(key)
    definition, rid = parts
    act = str(body.get("act") or "").strip()
    if act not in ACTS:
        raise ValueError(f"act is one of {', '.join(ACTS)}")
    by, who = _signer(viewer, body)
    root, day = _root(), _today()
    _register(root, [])
    try:
        located = store.locate(root, rid)
    except store.NoSuchRun:
        raise KeyError(f"{definition}/{rid}") from None
    if located != definition:
        raise KeyError(f"{definition}/{rid}")
    wf = definitions.find(definition)
    from jason.web.extra import work_scope

    scope = work_scope.scope_of(viewer)
    if wf is not None and (not scope.reads(wf) or scope.holds_back(wf)):
        raise KeyError(f"{definition}/{rid}")        # the 404 a missing run gets: a held run outside the private view, or an ADMIN run
    if wf is not None and scope.opens_held(wf):
        work_scope.log_opening(scope, f"api/write/work/{rid}", act=act)
    expect = _expect(body)
    step = str(body.get("step") or "").strip()
    sd = wf.step(step) if wf is not None and step else None
    if act == "attest" and sd is not None:
        if sd.kind is StepKind.DECISION:
            raise ValueError(DECISION_ELSEWHERE)
        if sd.kind is StepKind.PLAN:
            raise ValueError(PLAN_ELSEWHERE)
    readers = _readers(root, day)
    common = {"readers": readers, "expect": expect, "today": day}
    text = lambda name: str(body.get(name) or "").strip()  # noqa: E731
    yes = bool(body.get("yes") or body.get("confirm"))
    try:
        if act == "attest":
            out = api.attest(root, rid, _need(body, "step"), by, roles_of=who.roles_of, record=text("record"), what=text("what"),
                             item=text("item"), choice=text("choice"), **common)
        elif act == "arrived":
            out = api.arrived(root, rid, _need(body, "step"), by, roles_of=who.roles_of, what=text("what"), item=text("item"), **common)
        elif act == "skip":
            out = api.skip(root, rid, _need(body, "step"), by, roles_of=who.roles_of, reason=text("reason"), item=text("item"), **common)
        elif act == "na":
            out = api.not_applicable(root, rid, _need(body, "step"), by, roles_of=who.roles_of, reason=text("reason"),
                                     record=text("record"), item=text("item"), **common)
        elif act == "set-date":
            out = api.set_date(root, rid, _need(body, "slot"), _need(body, "day"), by, roles_of=who.roles_of,
                               record=text("record"), reason=text("reason"), **common)
        elif act == "reopen":
            out = api.reopen(root, rid, _need(body, "step"), by, roles_of=who.roles_of, reason=text("reason"), item=text("item"), **common)
        elif act == "pause":
            out = api.pause(root, rid, by, reason=text("reason"), **common)
        elif act == "resume":
            out = api.resume_run(root, rid, by, **common)
        elif act == "note":
            out = api.note(root, rid, by, text=text("text"), step=step, **common)
        elif act == "cancel":
            out = api.cancel(root, rid, by, roles_of=who.roles_of, reason=text("reason"), yes=yes, **common)
        else:
            out = api.open_run(root, rid, by, readers=readers, yes=yes, roles_of=who.roles_of, expect=expect, today=day)
    except (WorkflowError, RuntimeError) as exc:
        _refused(exc)
    titles = {s.id: s.title for s in wf.steps}
    order = {s.id: i for i, s in enumerate(wf.steps, 1)}
    from jason.workflows.types import Event

    made = [Event.from_dict(e) for e in (out.get("appended") or ([out["event"]] if out.get("event") else []))]
    rows = [_event(e, titles, order) for e in made]
    return {"ok": True, "act": act, "by": by, "event": rows[-1] if rows else None, "appended": rows,
            "run": compose_run(root, definition, rid, who, day, readers=readers)}


def start(definition: str, body: dict[str, Any], viewer: Any = None) -> dict[str, Any]:
    """``POST /api/write/work/<definition>/start`` or ``/start`` with ``{definition, subject, label, dates, items?, yes?,
    dryRun?}``: a draft run (no clock runs until it is opened). A definition with a legal clock needs ``yes``. ``dryRun`` checks
    the dates and says what would be refused, and writes nothing. The dates are checked against the definition's own rule
    (``Workflow.check_dates``), whose sentences are the answer."""
    from jason.workflows import api, definitions
    from jason.workflows.types import WorkflowError

    named = str(body.get("definition") or "").strip()
    if definition and named and definition != named:
        raise ValueError(f"the path names {definition} and the body names {named}")
    definition = definition or named
    if not definition:
        raise ValueError("definition is required to start a run")
    by, _ = _signer(viewer, body)
    root, day = _root(), _today()
    _register(root, [])
    from jason.web.extra import work_scope

    scope = work_scope.scope_of(viewer)
    wf = definitions.find(definition)
    if wf is None or not scope.reads(wf):               # an ADMIN definition is, to anyone else, a definition that is not there
        raise ValueError("no workflow definition " + definition + ": " + (", ".join(w.key for w in definitions.all_definitions()
                                                                                    if scope.reads(w))
                                                                          or "No workflows are registered."))
    startable, why = _startable(wf, scope)
    if not startable:
        _abort(403, why)
    if scope.opens_held(wf):
        work_scope.log_opening(scope, f"api/write/work/{wf.key}/start")
    raw = body.get("dates") or {}
    if not isinstance(raw, dict):
        raise ValueError("dates is an object of NAME: YYYY-MM-DD")
    dates = {str(k).strip(): str(v).strip() for k, v in raw.items() if str(v or "").strip()}
    subject, label = str(body.get("subject") or "").strip(), str(body.get("label") or "").strip()
    items = [str(i) for i in (body.get("items") or ())]
    yes = bool(body.get("yes") or body.get("confirm"))
    if body.get("dryRun") in (True, "1", "true", "yes"):
        problems = wf.check_dates(dates)
        if not subject:
            problems.append("a run is about a subject")
        if wf.has_legal_clock() and not yes:
            problems.append(f"{wf.key} has a legal clock: starting it needs yes")
        return {"ok": not problems, "dryRun": True, "definition": wf.key, "problems": problems}
    try:
        made = api.start(root, definition, subject, label, dates, by, items=items, parent=str(body.get("parent") or "").strip(),
                         yes=yes, today=day)
    except (WorkflowError, RuntimeError) as exc:
        _refused(exc)
    rid = made["run"]["id"]
    return {"ok": True, "act": "start", "by": by, "id": rid, "definition": wf.key,
            "run": compose_run(root, definition, rid, who_is(viewer) if viewer is not None else Who(by), day)}


__all__ = ["ACTS", "ACTING_REFUSED", "CAVEATS", "DECISION_ELSEWHERE", "GROUPS", "Who", "compose_run", "dry_resume", "held_page",
           "not_composed", "start", "who_is", "work", "work_definitions", "work_run", "write"]
