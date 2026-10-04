"""The owner-information apply, planned once and performed by one set of functions.

``jason owner-info --apply --payhoa`` and the approvals kind ``owner-info-tags`` (``jason.approvals.kinds.owner_info``)
both go through here, so the two doors plan and write the same things:

- ``plan_apply`` reads PayHOA live once (``ReadOnce``: the planner, the response policy, and the fingerprint share one
  read) and gives the ledger, the tag writes (a test membership's dropped), the unit writes the response policy holds for
  the board, and each owner's request with its status and findings;
- ``execute_each`` performs writes and says what became of each one (``owner_info.execute`` counts them);
- ``requests_left`` gives each open request with what still stands in its way, given the writes not made, and
  ``owner_info.complete`` marks one complete. Only a request with nothing left is completed: the board's stated
  exception in AGENTS.md, and nothing else of a member's request is approved, denied, or assigned.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Callable

from jason.tasks.owner_info import ToComplete, Write

# What a plan may call: PayHOA reads. A planning client refuses anything that writes.
READS = ("list_units", "iter_people", "list_form_submissions", "get_form_submission")
WRITE_PREFIXES = ("add_", "update_", "remove_", "set_", "create_", "delete_", "send_", "upload_", "cancel_", "submit_",
                  "approve_", "deny_", "assign_", "patch_", "post_", "put_")


class WriteRefused(RuntimeError):
    """A planning client was asked to write."""


class ReadOnce:
    """A PayHOA client for planning: each read is made once and the same call answers from it after, so one plan is one
    live read; anything that writes is refused (a plan is read-only)."""

    def __init__(self, client: Any) -> None:
        self._client = client
        self._memo: dict[tuple, Any] = {}

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._client, name)
        if name.startswith(WRITE_PREFIXES):
            raise WriteRefused(f"a plan only reads PayHOA: {name} refused")
        if name not in READS:
            return attr

        def read(*args: Any, **kwargs: Any) -> Any:
            key = (name, args, tuple(sorted(kwargs.items())))
            if key not in self._memo:
                value = attr(*args, **kwargs)
                self._memo[key] = list(value) if name.startswith("iter_") else value
            value = self._memo[key]
            return iter(value) if name.startswith("iter_") else value

        return read


def live_read(client: Any, org: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Every unit (all pages) and every person, read live."""
    units, page = [], 1
    while True:
        body = client.list_units(org, page=page)
        units.extend(body.get("data") or [])
        meta = body.get("meta") or {}
        if page >= int(meta.get("lastPage") or meta.get("last_page") or 1):
            break
        page += 1
    return units, list(client.iter_people(org))


def owner_information(community: Any) -> Any:
    """The profile's owner-information forms (``Community.owner_information``), or None."""
    method = getattr(community, "owner_information", None)
    return method() if method is not None else None


GATHER_VIA = "owner_info_apply.gather_answers"


def gather_answers(data_dir: Path, forms: Any, client: Any = None,
                   org_id: int | None = None, *, via: str = GATHER_VIA) -> tuple[list[Any], dict[str, str]]:
    """Every answer jason holds, from each channel, and each source's title. Each PayHOA submission read live is kept
    as that request's latest full read (``submission_cache``: ``payhoa-files/requests/<id>/submission.json``), with
    ``via`` naming what read it."""
    from jason.tasks.forms import forms_dir, import_responses

    answers, titles = [], {"payhoa": "PayHOA owner information form"}
    for rules in forms.FORM_IMPORTS:
        saved = forms_dir(data_dir) / rules.source / "responses.json"
        if saved.is_file():
            answers += import_responses(json.loads(saved.read_text(encoding="utf-8")), rules)
            titles["google"] = rules.title
    if client is not None:
        from jason.tasks import submission_cache
        from jason.tasks.payhoa_forms import fetch_submissions, record_for

        record = record_for(data_dir, forms.OWNER_INFO.key.value)
        if record:
            from jason.config import test_memberships

            tests = test_memberships()      # a test account's answers are never an owner's
            keep = submission_cache.keeper(submission_cache.files_dir(data_dir), via=via,
                                           form_id=int(record["formId"]),
                                           form_name=str(record.get("title") or forms.OWNER_INFO.title))
            answers += [a for a in fetch_submissions(client, org_id, record, forms.OWNER_INFO, keep=keep)
                        if a.membership_id is None or int(a.membership_id) not in tests]
    return answers, titles


def ledger_rows(units: list[dict[str, Any]], people: list[dict[str, Any]], answers: list[Any], data_dir: Path,
                community: Any, cycle: Any, today: date, *, earlier: Any = None) -> tuple[Any, list[Any]]:
    """The delivery plan (``notice_delivery.plan``) and the ledger, one row an owner. ``earlier`` is the profile's
    ``EarlierElections`` (default: its owner-information forms, ``Community.owner_information``)."""
    from jason.tasks.member_preferences import match, unit_owners
    from jason.tasks.notice_delivery import plan
    from jason.tasks.owner_info import ledger
    from jason.tasks.parties import PartyResolver

    if earlier is None:
        earlier = getattr(owner_information(community), "EARLIER_ELECTIONS", None)
    tags = community.payhoa_tags()
    deeds = PartyResolver(data_dir).latest_deed
    matched = match(answers, unit_owners(units, people, deeds, tags), tags, cycle=cycle, today=today)
    found = plan(units, people, tags)
    return found, ledger(found, matched, tags, cycle, earlier=earlier, today=today)


@dataclass
class HeldWrite:
    """A write the response policy holds: never written, with the finding that holds it."""
    write: Write
    rule: str
    board_item: str
    text: str


@dataclass
class ApplyPlan:
    """One live read and everything planned from it."""
    client: ReadOnce
    org: int
    units: list[dict[str, Any]]
    people: list[dict[str, Any]]
    rows: list[Any]
    found: Any
    writes: list[Write]                                  # to write: test memberships dropped, held writes out
    held: list[HeldWrite] = field(default_factory=list)
    statuses: dict[int, Any] = field(default_factory=dict)          # submission id -> PayHOA status
    findings: dict[int, list[Any]] = field(default_factory=dict)    # submission id -> owner_responses findings
    contexts: list[Any] = field(default_factory=list)
    comment: str = ""
    payhoa: bool = True
    left_out: int = 0                                    # writes dropped because they were on a test membership

    @property
    def member_tag_rows(self) -> dict[int, list[dict[str, Any]]]:
        """Each member's tag rows as read, for a removal by row id."""
        return {int(p["id"]): list(p.get("tags") or []) for p in self.people if p.get("id") is not None}


def plan_apply(client: Any, org: int, *, community: Any, forms: Any, cycle: Any, data_dir: Path, today: date,
               payhoa: bool = True, env: Any = None, via: str = GATHER_VIA) -> ApplyPlan:
    """Read PayHOA once and plan every write that would bring it up to date, as ``jason owner-info --apply`` lists them.
    With ``payhoa`` the PayHOA form's submissions are read too: the response policy then holds a unit's occupancy tag
    for the board where an owner's answer and the tag differ, and each owner's request is read with its findings; each
    submission read is kept as its request's latest full read, ``via`` naming the command (``gather_answers``)."""
    from jason.config import test_memberships
    from jason.tasks.owner_info import plan_writes

    reader = client if isinstance(client, ReadOnce) else ReadOnce(client)
    units, people = live_read(reader, org)
    answers, _ = gather_answers(data_dir, forms, reader if payhoa else None, org, via=via)
    found, rows = ledger_rows(units, people, answers, data_dir, community, cycle, today, earlier=forms.EARLIER_ELECTIONS)
    writes = plan_writes(rows, found, community.payhoa_tags(), earlier=forms.EARLIER_ELECTIONS, today=today)
    # a test account is never an owner of record: no delivery or other tag goes on it
    test = test_memberships(env)
    kept = [w for w in writes if not (w.kind.startswith("member") and w.target in test)]
    plan = ApplyPlan(reader, org, units, people, rows, found, kept, payhoa=payhoa, left_out=len(writes) - len(kept),
                     comment=getattr(forms, "OWNER_INFO_COMPLETED_COMMENT", ""))
    writes = kept
    if not payhoa:
        return plan
    # the response policy holds an occupancy the unit's tag does not show for the board: its tag writes wait
    from jason.community.tags import TagPurpose, TagScope
    from jason.tasks.owner_responses import Outcome, contexts, triage
    from jason.tasks.payhoa_forms import record_for

    plan.contexts = contexts(reader, org, data_dir, community, forms, live=(units, people))
    plan.findings = {c.submission: triage(c) for c in plan.contexts}
    held_by: dict[int, Any] = {}
    for c in plan.contexts:
        for f in plan.findings[c.submission]:
            if f.outcome is Outcome.BOARD and f.rule == "occupancy-vs-tag":
                held_by.setdefault(c.unit_id, f)
    occupancy = {t.name for t in community.payhoa_tags() if t.purpose is TagPurpose.OCCUPANCY and t.scope is TagScope.UNIT}
    for w in writes:
        if w.kind.startswith("unit") and w.target in held_by and w.value in occupancy:
            f = held_by[w.target]
            plan.held.append(HeldWrite(w, f.rule, f.board_item, f.text))
    held = [h.write for h in plan.held]
    plan.writes = [w for w in writes if w not in held]
    record = record_for(data_dir, forms.OWNER_INFO.key.value)
    if record is not None:
        plan.statuses = {int(r["id"]): r.get("status") for r in reader.list_form_submissions(int(record["formId"]))}
    return plan


def requests_left(plan: ApplyPlan, pending: list[Write]) -> list[ToComplete]:
    """Each owner's open (pending) PayHOA request, with what is left before it is fully recorded: a write in
    ``pending`` (not yet made), something a person enters, and every finding of the response policy but "record" (a
    question for the board, something to confirm with the owner, a person's entry). Empty ``left``: it may be completed."""
    from jason.tasks.owner_info import to_complete
    from jason.tasks.owner_responses import Outcome

    held = {sid: [f"{f.outcome.value}: {f.rule}" for f in fs if f.outcome is not Outcome.RECORD]
            for sid, fs in plan.findings.items()}
    out = []
    for item in to_complete(plan.rows, pending):
        if plan.statuses.get(item.submission_id) != "pending":
            continue
        item.left += [h for h in held.get(item.submission_id, []) if h not in item.left]
        out.append(item)
    return out


@dataclass
class WriteResult:
    """What became of one write: ``done`` (PayHOA answered it), ``already`` (nothing to do: a removal whose tag row is
    gone, as the plan wanted), or neither, with ``error`` when the call failed or ``detail`` when it was not tried."""
    write: Write
    done: bool
    detail: str = ""
    error: BaseException | None = None
    already: bool = False

    @property
    def satisfied(self) -> bool:
        """PayHOA now holds what the write asked for: no request waits on it."""
        return self.done or self.already


def execute_each(client: Any, org_id: int, writes: list[Write], *,
                 member_tag_rows: dict[int, list[dict[str, Any]]] | None = None, batch: int = 25,
                 before: Callable[[list[Write]], None] | None = None) -> list[WriteResult]:
    """Perform the writes in ``owner_info.execute``'s order (member tags added in batches by tag, then removals by the
    member's tag row, and unit tags) and say what became of each. ``before`` hears each request's writes just before it
    is made (an audit's intent line). The first failure stops the run: its writes are failed, and the rest are not
    attempted."""
    from collections import defaultdict

    out: list[WriteResult] = []
    stopped: BaseException | None = None

    def call(group: list[Write], fn: Any, detail: str = "") -> None:
        nonlocal stopped
        if stopped is not None:
            out.extend(WriteResult(w, False, "not attempted: an earlier write failed") for w in group)
            return
        if before is not None:
            before(group)
        try:
            fn()
        except Exception as exc:  # noqa: BLE001 - recorded per write; the caller decides whether to raise
            stopped = exc
            out.extend(WriteResult(w, False, f"failed: {type(exc).__name__}: {exc}", exc) for w in group)
            return
        out.extend(WriteResult(w, True, detail) for w in group)

    adds: dict[str, list[Write]] = defaultdict(list)
    for w in writes:
        if w.kind == "member tag +":
            adds[w.value].append(w)
    for tag, group in adds.items():
        for i in range(0, len(group), batch):
            part = group[i:i + batch]
            call(part, lambda part=part, tag=tag: client.update_member_tags(org_id, [w.target for w in part], add=[tag]))
    for w in writes:
        if w.kind == "member tag -":
            rows = [t for t in (member_tag_rows or {}).get(w.target, []) if t.get("tag") == w.value]
            if rows:
                call([w], lambda w=w, rows=rows: client.update_member_tags(org_id, [w.target], remove=[int(rows[0]["id"])]))
            else:
                out.append(WriteResult(w, False, "nothing to remove: the member has no such tag row", already=True))
        elif w.kind == "unit tag +":
            call([w], lambda w=w: client.add_unit_tag(org_id, [w.target], w.value))
        elif w.kind == "unit tag -":
            call([w], lambda w=w: client.remove_unit_tag(org_id, [w.target], w.value))
    return out


__all__ = ["ApplyPlan", "HeldWrite", "READS", "ReadOnce", "WriteRefused", "WriteResult", "execute_each",
           "gather_answers", "ledger_rows", "live_read", "owner_information", "plan_apply", "requests_left"]
