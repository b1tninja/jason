"""``StoreReaders``: the engine's world, read from jason's own stores (docs/workflows-engine.md, sections 4, 5, and 10).

A resume (``jason.workflows.resume``) asks a ``Readers`` object five questions; this answers them from disk and writes
nothing, reaches no network, and never calls PayHOA, Google, or Keeper:

- **a check**: a ``check`` step names a read (``named_check("dates-room")``); ``StoreReaders.check`` finds it in ``CHECKS``
  and calls the existing read functions behind it (the follow-ups, the response inbox, the campaigns, the notice ledger,
  the approvals store). A step with a plain callable is called as before. A check that cannot read returns ``ok=False`` with
  the reason, never ``ok``.
- **an approval** (a ``plan`` step): found by the step's idempotence key, in the approvals store by ``Approval.scope``
  (``{"workflow": key}``) or by the ``plan-made`` event that recorded the key; a superseded plan is followed to the plan
  that replaced it. ``make_plan`` never makes a plan (that reads the live system, which is a person's command); it *adopts*
  the newest plan of the step's kind a person made since the run opened, if no other run holds it, and records it under the key.
- **a job** (a ``job`` step): found by the key in the run store's ``job-queued`` events, then read from ``data/jobs.db``. The
  queue holds no key, so ``queue_job`` does not queue: it adopts the newest queued job whose command matches the step's
  ``JobSpec`` and was added since the run opened.
- **evidence**: an address is ``file:<path under the data folder>`` or ``glob:<pattern under it>``; its hash is the first 12
  hex of the sha256 of the file (or, for a glob, of the matches' names and bytes). A missing file has no hash.
- **an arrival** (a ``wait`` step): the step's named check, run now; it has arrived when the check passes.

Importing this module loads no profile and no client. The community is asked for only when a check needs it, and a test
passes its own. ``today`` is an argument so a check is reproducible.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from jason.workflows import definitions, fold, store
from jason.workflows.resume import ApprovalState, JobState, Readers
from jason.workflows.types import CheckResult, EventKind, RunView, StepDef


# --- named checks ---------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class NamedCheck:
    """What a definition's ``check`` holds: the name of a read, not the read. Called on its own (by a ``Readers`` that does
    not know the name) it says so rather than guessing; ``StoreReaders`` looks the name up in ``CHECKS``."""

    name: str

    def __call__(self, view: RunView, *rest: Any) -> CheckResult:
        return CheckResult(False, (), f"the read {self.name!r} needs the stores; open the run through jason workflow")


def named_check(name: str) -> NamedCheck:
    return NamedCheck(name)


# --- jobs a definition may name -------------------------------------------------------------------------------------

@dataclass(frozen=True)
class JobSpec:
    """How a job step's command is recognized in the queue: every ``require`` word is among the job's arguments, none of
    ``forbid`` is, and (with ``prefix``) some argument starts with it. The queue keeps the command and not a key."""

    name: str
    require: tuple[str, ...]
    forbid: tuple[str, ...] = ()
    prefix: str = ""

    def matches(self, argv: Iterable[str]) -> bool:
        words = list(argv)
        return (all(w in words for w in self.require) and not any(w in words for w in self.forbid)
                and (not self.prefix or any(w.startswith(self.prefix) for w in words)))


JOBS: dict[str, JobSpec] = {j.name: j for j in (
    JobSpec("payhoa-form-test", ("forms", "--payhoa-test")),
    JobSpec("owner-info-send-plan", ("owner-info", "--send-plan")),
    JobSpec("owner-info-email-test", ("owner-info", "--email-batch", "--only", "me")),
    JobSpec("notices-sync", ("notices", "--sync"), prefix="owner-info-"),
)}
"""The job names a definition may use (``definitions.validate`` takes ``JOBS`` as its registry of jobs)."""


# --- small helpers --------------------------------------------------------------------------------------------------

def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:12]


def when(value: Any) -> datetime | None:
    """An ISO time as an aware datetime, ``None`` when it cannot be read."""
    text = str(value or "").strip().replace("Z", "+00:00")
    if not text:
        return None
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def day_of(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value or ""))
    except ValueError:
        return None


# --- the readers ----------------------------------------------------------------------------------------------------

class StoreReaders(Readers):
    """Reads from ``data_dir``; writes nothing. ``community`` is the profile a check may ask (the active one when none is
    given, loaded only when a check asks); ``today`` fixes the day for a check."""

    def __init__(self, data_dir: Path | str, *, community: Any = None, today: date | None = None) -> None:
        self.data_dir = Path(data_dir)
        self._community = community
        self.today = today or date.today()

    @property
    def community(self) -> Any:
        if self._community is None:
            from jason.community import community as active

            self._community = active()
        return self._community

    # -- a check ------------------------------------------------------------------------------------------------------

    def check(self, step: StepDef, view: RunView, item: str = "") -> CheckResult | None:
        name = getattr(step.check, "name", "")
        if name and name in CHECKS:
            return CHECKS[name](self, view, item)
        return super().check(step, view, item)

    def arrival(self, step: StepDef, view: RunView, item: str = "") -> str | None:
        name = getattr(step.check, "name", "")
        if not name or name not in CHECKS:
            return None
        try:
            res = CHECKS[name](self, view, item)
        except Exception:  # noqa: BLE001 - an unreadable store is no arrival
            return None
        return (res.message or "arrived") if res.ok else None

    # -- evidence -----------------------------------------------------------------------------------------------------

    def _inside(self, relative: str) -> Path | None:
        """A path under the data folder, ``None`` when it would leave it."""
        base = self.data_dir.resolve()
        path = (base / relative).resolve()
        try:
            path.relative_to(base)
        except ValueError:
            return None
        return path

    def evidence(self, address: str) -> str | None:
        kind, _, rest = address.partition(":")
        if kind == "file":
            path = self._inside(rest)
            return digest(path.read_bytes()) if path is not None and path.is_file() else None
        if kind == "glob":
            base = self.data_dir.resolve()
            files = sorted(p for p in base.glob(rest) if p.is_file()) if rest and not Path(rest).is_absolute() and ".." not in Path(rest).parts else []
            if not files:
                return None
            h = hashlib.sha256()
            for p in files:
                h.update(p.relative_to(base).as_posix().encode("utf-8") + b"\0" + p.read_bytes() + b"\0")
            return h.hexdigest()[:12]
        return None

    def evidence_entries(self, addresses: Iterable[str]) -> tuple[str, ...]:
        return tuple(f"{a}@{h}" for a in addresses if (h := self.evidence(a)))

    # -- what other runs hold -----------------------------------------------------------------------------------------

    def _events(self, kind: EventKind) -> Iterable[Any]:
        for definition, rid in store.list_runs(self.data_dir):
            try:
                run = store.read(self.data_dir, definition, rid)
            except Exception:  # noqa: BLE001 - a run that cannot be read holds nothing
                continue
            for e in run.events:
                if e.kind is kind:
                    yield e

    def _recorded(self, kind: EventKind, field_name: str) -> dict[str, str]:
        """{idempotence key: approval or job id} from the ``plan-made`` or ``job-queued`` events of every run."""
        return {str(e.detail["key"]): str(e.detail[field_name]) for e in self._events(kind)
                if e.detail.get("key") and e.detail.get(field_name)}

    def _held(self, kind: EventKind, field_name: str, *, but: str = "") -> set[str]:
        return {str(e.detail[field_name]) for e in self._events(kind)
                if e.detail.get(field_name) and str(e.detail.get("key", "")) != but}

    # -- an approval --------------------------------------------------------------------------------------------------

    def _approvals(self) -> dict[str, Any]:
        from jason.approvals import store as approvals

        out = {}
        for ident in approvals.ids(self.data_dir):
            try:
                out[ident] = approvals.load(ident, self.data_dir)
            except Exception:  # noqa: BLE001 - one unreadable approval hides no other
                continue
        return out

    @staticmethod
    def _head(found: Any, by_id: dict[str, Any]) -> Any:
        """The plan a superseded plan was replaced by, and so on to the newest."""
        seen = set()
        while found.superseded_by and found.superseded_by in by_id and found.id not in seen:
            seen.add(found.id)
            found = by_id[found.superseded_by]
        return found

    def approval(self, key: str) -> ApprovalState | None:
        by_id = self._approvals()
        ident = self._recorded(EventKind.PLAN_MADE, "approval").get(key, "")
        found = by_id.get(ident) if ident else None
        if found is None:
            found = next((a for a in by_id.values() if a.scope.get("workflow") == key), None)
        if found is None:
            return None
        head = self._head(found, by_id)
        reason = "; ".join(str(n) for n in head.notes[-1:]) if head.status.value in ("failed", "withdrawn") else ""
        return ApprovalState(head.id, head.status.value, reason)

    def make_plan(self, kind: str, key: str, step: StepDef, view: RunView, item: str = "") -> str | None:
        """Adopts, never makes: the newest plan of this kind that a person made since the run opened, if no other run
        holds it. Making one reads the live system, which is the person's command (the step shows it)."""
        from jason.approvals import model, registry

        try:
            wanted = registry.get(kind).key
        except KeyError:
            return None
        opened = when(view.opened_at)
        if opened is None:
            return None
        by_id = self._approvals()
        taken = self._held(EventKind.PLAN_MADE, "approval", but=key)
        usable = {model.ApprovalStatus.PLANNED, model.ApprovalStatus.IN_REVIEW, model.ApprovalStatus.APPROVED,
                  model.ApprovalStatus.PARTIALLY_APPROVED, model.ApprovalStatus.APPLYING, model.ApprovalStatus.APPLIED,
                  model.ApprovalStatus.FAILED}
        mine = [a for a in by_id.values()
                if a.kind == wanted and (when(a.requested_at) or opened) >= opened and a.id not in taken]
        for a in sorted(mine, key=lambda a: (a.requested_at, a.id), reverse=True):
            head = self._head(a, by_id)
            if head.status in usable and head.id not in taken:
                return head.id
        return None

    # -- a job --------------------------------------------------------------------------------------------------------

    def _jobs(self) -> list[Any]:
        if not (self.data_dir / "jobs.db").is_file():
            return []
        from jason import jobs

        return jobs.jobs(self.data_dir, every=True, limit=500)

    def job(self, key: str) -> JobState | None:
        ident = self._recorded(EventKind.JOB_QUEUED, "job").get(key, "")
        if not ident:
            return None
        found = next((j for j in self._jobs() if str(j.id) == ident), None)
        if found is None:
            return None
        state = {"queued": "queued", "running": "running", "done": "finished", "failed": "failed",
                 "cancelled": "failed"}.get(found.status.value, "queued")
        return JobState(str(found.id), state, found.summary or found.note or "")

    def queue_job(self, name: str, key: str, step: StepDef, view: RunView, item: str = "") -> str | None:
        """Adopts, never queues: the newest job in the queue that the step's ``JobSpec`` recognizes, added since the run
        opened and held by no other step."""
        spec = JOBS.get(name)
        opened = when(view.opened_at)
        if spec is None or opened is None:
            return None
        taken = self._held(EventKind.JOB_QUEUED, "job", but=key)
        for j in sorted(self._jobs(), key=lambda j: j.id, reverse=True):
            if str(j.id) in taken or (when(j.created) or opened) < opened:
                continue
            if j.status.value != "cancelled" and spec.matches(j.argv):
                return str(j.id)
        return None

    # -- a child run --------------------------------------------------------------------------------------------------

    def child_state(self, run_id: str) -> str | None:
        try:
            definition = store.locate(self.data_dir, run_id)
            wf = definitions.find(definition)
            if wf is None:
                return None
            run = store.read(self.data_dir, definition, run_id)
            return fold.state(list(run.events), wf, self.today, run_id=run_id).state.value
        except Exception:  # noqa: BLE001 - a child that cannot be read is not finished
            return None

    # -- what the cycle's checks share --------------------------------------------------------------------------------

    def campaigns_of(self, view: RunView) -> list[Any]:
        """The campaigns whose return-by date is the run's."""
        from jason.tasks import campaigns

        want = view.dates.get("return_by", "")
        return [c for c in campaigns.load(self.data_dir).values() if want and c.return_by == want]

    def requests_of(self, view: RunView) -> list[Any]:
        """The profile's response requests whose return-by date is the run's."""
        want = day_of(view.dates.get("return_by", ""))
        if want is None:
            return []
        found = self.community.response_requests() if self.community is not None else ()
        return [r for r in found or () if getattr(getattr(r, "cycle", None), "return_by", None) == want]


# --- the reads a definition names -----------------------------------------------------------------------------------

SYNC_DAYS = 1
"""The day after a send that the delivery sync falls (the procedure's practice; the board has not adopted a number)."""


def _slot(view: RunView, name: str) -> date | None:
    return day_of(view.dates.get(name, ""))


def dates_room(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """The cycle's dates leave room for one correction before the return-by date, and the day the answers must be entered
    does not come before it."""
    from datetime import timedelta

    from jason.tasks.followups import PROPOSED_DAYS

    opens, return_by, mailed = _slot(view, "opens_on"), _slot(view, "return_by"), _slot(view, "reports_mailed")
    if opens is None or return_by is None:
        return CheckResult(False, (), "the run has no opens_on and return_by dates")
    resend = PROPOSED_DAYS["resend"]
    room = (return_by - opens).days
    needed = SYNC_DAYS + resend
    message = (f"return-by is {room} days after the cycle opens; the first delivery sync falls on day {SYNC_DAYS} and a "
               f"resend on day {needed} (proposed policy: no minimum is adopted)")
    if room <= needed:
        return CheckResult(False, (), "the dates leave no room for one correction: " + message)
    if mailed is not None:
        entry = mailed - timedelta(days=30)
        if entry < return_by:
            return CheckResult(False, (), f"the day to enter the answers ({entry.isoformat()}, 30 days before the reports are "
                                          f"mailed) comes before the return-by date {return_by.isoformat()}")
        message += f"; the entry day {entry.isoformat()} is {(entry - return_by).days} days after return-by"
    return CheckResult(True, (), message)


def outstanding_read(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """The follow-ups and the funnel can be read: how many are open and how many owners are outstanding. It passes when it
    reads; the count is information for a person, never a verdict."""
    if readers.community is None:
        return CheckResult(False, (), "no community is chosen, so the follow-ups cannot be derived")
    from jason.tasks import followups

    codes = {c.code for c in readers.campaigns_of(view)}
    found = [i for i in followups.items(readers.data_dir, readers.community, today=readers.today)
             if i.open and (not i.campaign or i.campaign in codes)]
    counts = [i.outstanding for i in found if i.campaign in codes and i.outstanding is not None]
    outstanding = max(counts) if counts else None
    message = (f"{len(found)} follow-up item(s) open" +
               (f"; {outstanding} owner(s) outstanding" if outstanding is not None else "; the outstanding count could not be read"))
    return CheckResult(True, readers.evidence_entries(("file:followups/acts.jsonl", "file:responses/inbox.json")), message)


def entry_day_gap(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """Nothing is read and left unconfirmed, nothing is confirmed and left unrecorded, no plan is open. A gap fails the
    check and is listed; the run never writes the answers itself (Civil Code 4041(b)(1))."""
    from jason.approvals.model import OPEN, ApprovalStatus
    from jason.community.response_inbox import State
    from jason.tasks import response_inbox as inbox

    requests = readers.requests_of(view)
    if not requests:
        return CheckResult(False, (), f"no response request in the profile has the return-by date {view.dates.get('return_by', '?')}")
    keys = {r.key for r in requests}
    unread = unrecorded = 0
    for a in inbox.load_inbox(readers.data_dir).arrivals.values():
        if a.request not in keys or a.superseded_by or a.state in (State.DISMISSED, State.RECORDED):
            continue
        if a.structured:
            if a.state in (State.NEW, State.SEEN) and "status: complete" not in a.note:
                unrecorded += 1
        elif a.state in (State.NEW, State.SEEN, State.READ):
            unread += 1
        elif a.state is State.KEYED:
            unrecorded += 1
    plans = sum(1 for a in readers._approvals().values()
                if a.kind == "owner-info-tags" and (a.status in OPEN or a.status is ApprovalStatus.APPLYING))
    message = f"{unread} arrival(s) unread or unconfirmed; {unrecorded} confirmed and not recorded; {plans} plan(s) open"
    evidence = readers.evidence_entries(("file:responses/inbox.json",))
    return CheckResult(not (unread or unrecorded or plans), evidence, message)


def delivery_read(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """Every emailed copy has an outcome in the notice ledger (the ledger's own words: delivered, bounced, unknown after 24
    hours, and so on), so the delivery can be acted on. The notice's key is the campaign's cycle year."""
    from jason.tasks import notice_ledger

    mine = [c for c in readers.campaigns_of(view) if c.channel == "email" and c.year]
    if not mine:
        return CheckResult(False, (), "no email campaign with this run's return-by date, so the notice key is unknown")
    if not (readers.data_dir / "notices" / "deliveries.db").is_file():
        return CheckResult(False, (), "the notice ledger has not been synced yet")
    attempts = []
    for c in mine:
        attempts += [a for a in notice_ledger.load(readers.data_dir, f"owner-info-{c.year}") if a.channel == "email"]
    if not attempts:
        return CheckResult(False, (), "the ledger holds no emailed copy yet")
    waiting = sum(1 for a in attempts if a.status is notice_ledger.Delivery.PENDING)
    tally: dict[str, int] = {}
    for a in attempts:
        tally[a.status.value] = tally.get(a.status.value, 0) + 1
    message = f"{len(attempts)} emailed copies: " + ", ".join(f"{n} {w}" for w, n in sorted(tally.items()))
    if waiting:
        return CheckResult(False, (), f"{waiting} of {message} have no outcome yet")
    return CheckResult(True, (), message)


CHECKS: dict[str, Callable[[StoreReaders, RunView, str], CheckResult]] = {
    "dates-room": dates_room, "outstanding-read": outstanding_read, "entry-day-gap": entry_day_gap, "delivery-read": delivery_read,
}
"""The reads a definition may name with ``named_check``: each takes the readers, the run's view, and the item."""


__all__ = ["CHECKS", "JOBS", "JobSpec", "NamedCheck", "StoreReaders", "digest", "named_check"]
