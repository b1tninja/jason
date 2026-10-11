"""The ``payhoa-attach-bills`` kind: ``jason sync-bills --yes`` as an approval, attaching only.

The planner runs the attach engine's dry run (``jason.sources.attach.attach_bills(dry_run=True)``: one read of PayHOA's
unapproved transactions, each routed to a bill source and matched to one bill by exact amount and date) and makes one
approvable item for each ``matched`` result: the transaction, the bill, and the PDF that would be attached. A result
that is ambiguous, has no match, already has an attachment, or errors is no item, because nothing may be attached for
it; each is counted in the summary and listed in the plan's notes. A transaction no source owns is not listed here
(``jason sync-bills`` prints it).

The applier performs only the approved items. For each one it reads the transaction again (one that gained an
attachment since the plan is skipped), resolves the item's bill again and checks it is the same bill for the same
amount, then uploads the PDF with ``client.upload_attachment``. It never approves the PayHOA transaction, never
deletes, and a failure on one item does not stop the next.

Scope: ``sources`` (optional list of bill-source names; empty is every source) and ``date_window_days``.
"""

from __future__ import annotations

import re
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterator

from jason.approvals.engine import Live, Planned
from jason.approvals.model import Change, ChangeOp, Evidence, PlanItem, Result, digest, item_id

KEY = "payhoa-attach-bills"
OP = "attach bill"
# The rule the kind recites. The review of the association's accounts is the board's duty under Civil Code 5500(a);
# that the bill attached is what the reviewer needs is the plan's reading (each item says so), not the statute's words.
RULE = "CIV 5500(a)"
NOTES_LIMIT = 50                         # lines of what is not an item that the plan lists; the rest are counted


@dataclass
class Context:
    """The planner's own, in memory, for the applier: the matched result behind each item, and the plan's window."""
    results: dict[str, Any] = field(default_factory=dict)       # item id -> attach.MatchResult (status matched)
    window_days: int = 7


@contextmanager
def open_registry(live: Live, names: set[str] | None) -> Iterator[Any]:
    """The bill sources the engine routes with (SMUD, the City's portal, each vendor portal with a credential, the county
    tax collector), narrowed to ``names``. Planning reads their caches; a source signs in to its portal only when the
    applier asks it to resolve a bill. Closed when the block ends."""
    from jason.agent import Jason

    with Jason(interactive=False) as agent:
        yield agent.bill_source_registry().filter(names or None)


def _org(live: Live) -> int:
    from jason.sources.types import profile_org_id

    return profile_org_id(live.org_id or None)


def cents(value: int) -> str:
    sign = "-" if value < 0 else ""
    return f"{sign}${abs(value) // 100:,}.{abs(value) % 100:02d}"


def _line(text: str, limit: int = 70) -> str:
    return re.sub(r"\s+", " ", text or "").strip()[:limit]


def _scope(scope: dict[str, Any]) -> tuple[list[str], int]:
    from jason.sources.types import DEFAULT_DATE_WINDOW_DAYS

    names = sorted({str(n) for n in scope.get("sources") or () if str(n).strip()})
    window = int(scope.get("date_window_days") or DEFAULT_DATE_WINDOW_DAYS)
    return names, window


def plan(live: Live, scope: dict[str, Any]) -> Planned:
    """Read PayHOA once and plan, writing and uploading nothing."""
    from jason.sources.attach import attach_bills

    names, window = _scope(scope)
    read_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with open_registry(live, set(names) or None) as registry:
        report = attach_bills(live.client, registry, org_id=_org(live), date_window_days=window, dry_run=True,
                              approve=False)
    return build(report, names=names, window=window, read_at=read_at)


def _item(m: Any, window: int) -> PlanItem:
    bill = m.bill
    pdf = "on disk" if bill.has_pdf else "fetched from the source when applied"
    return PlanItem(
        item_id(KEY, OP, f"transaction:{m.transaction_id}", f"{bill.source}|{bill.bill_id}|{m.amount_cents}"), OP,
        f"transaction:{m.transaction_id}",
        f"{m.transaction_date.isoformat()} {cents(m.amount_cents)} {_line(m.description)}", f"{bill.source} bill dated "
        f"{bill.bill_date.isoformat()}, {cents(bill.amount_cents)}",
        f"{bill.source} bill {bill.bill_id} dated {bill.bill_date.isoformat()} is for exactly the transaction's "
        f"{cents(m.amount_cents)}, within {window} days of {m.transaction_date.isoformat()}, and is the only bill that "
        f"fits. Its PDF is {pdf}. The reading that the attachment is what the reviewer needs is the plan's. Attaching "
        "approves nothing in PayHOA.",
        group=f"{bill.source}", change=Change(ChangeOp.ADD, "transaction attachments", "bill PDF", "none",
                                              "1 attachment"),
        rule=RULE, evidence=(Evidence("The same dry run", "jason sync-bills --dry-run"),),
        basis=digest({"transaction": m.transaction_id, "amount": m.amount_cents, "date": m.transaction_date.isoformat(),
                      "description": m.description, "attachments": 0,
                      "bill": [bill.source, bill.bill_id, bill.bill_date.isoformat(), bill.amount_cents]}))


def build(report: Any, *, names: list[str], window: int, read_at: str = "") -> Planned:
    """The items, from an ``UploadReport`` of a dry run. Pure: reads nothing."""
    ctx = Context(window_days=window)
    items: list[PlanItem] = []
    others: list[Any] = []
    counts: dict[str, int] = {}
    for m in report.results:
        counts[m.status] = counts.get(m.status, 0) + 1
        if m.status == "matched" and m.bill is not None:
            item = _item(m, window)
            items.append(item)
            ctx.results[item.id] = m
        else:
            others.append(m)
    notes = [f"transaction {m.transaction_id} ({cents(m.amount_cents)}, {m.transaction_date.isoformat()}): "
             f"{m.status}: {_line(m.detail, 120)} (no item: nothing is attached for it)"
             for m in others[:NOTES_LIMIT]]
    if len(others) > NOTES_LIMIT:
        notes.append(f"{len(others) - NOTES_LIMIT} more transactions with no item")
    notes.append("The plan matches bills already on disk. A bill a portal has not been synced for is not in it: "
                 "jason sync-bills syncs the portals, and a new plan then finds it. A transaction no source owns "
                 "is not listed here.")
    summary = {"matched": len(items), "ambiguous": counts.get("ambiguous", 0), "noMatch": counts.get("no_match", 0),
               "skipped": counts.get("skipped", 0), "errors": counts.get("error", 0),
               "matchedCents": sum(m.amount_cents for m in ctx.results.values()),
               "withPdf": sum(1 for m in ctx.results.values() if m.bill.has_pdf), "dateWindowDays": window,
               "cost": "No charge: a PDF attached to a PayHOA transaction; nothing is approved"}
    return Planned(items, scope={"sources": names, "date_window_days": window},
                   title="Bills: attach matched PDFs to PayHOA transactions", summary=summary,
                   evidence=(Evidence("The same plan as a dry run", "jason sync-bills --dry-run"),
                             Evidence("Civil Code 5500(a)", RULE)),
                   notes=notes, context=ctx, read_at=read_at)


# --- apply --------------------------------------------------------------------------------------------------------------

def _uncertain(exc: BaseException) -> bool:
    """An upload that went out with no answer back (a timeout, a dropped connection): PayHOA may have taken it."""
    from jason.approvals.kinds.owner_info import _uncertain as uncertain

    return uncertain(exc)


def apply(live: Live, planned: Planned, items: list[PlanItem], recorder: Any) -> None:
    """Attach the PDF for each approved item, and nothing else."""
    from jason.sources.types import BillNeed, active_attachments

    ctx: Context = planned.context
    org = _org(live)
    names = {m.bill.source for i in items if (m := ctx.results.get(i.id)) is not None}
    with open_registry(live, names or None) as registry:
        for item in items:
            m = ctx.results.get(item.id)
            if m is None:
                recorder.done(item.id, Result.FAILED, "not a matched bill in the plan read just now")
                continue
            uploading = False
            try:
                if active_attachments(live.client.get_transaction(org, m.transaction_id)):
                    recorder.done(item.id, Result.NOT_APPLIED, "skipped: the transaction has an attachment now")
                    continue
                source = registry.get(m.bill.source)
                if source is None:
                    recorder.done(item.id, Result.FAILED, f"no bill source {m.bill.source}")
                    continue
                need = BillNeed(amount_cents=m.amount_cents, around=m.transaction_date, window_days=ctx.window_days,
                                transaction_id=m.transaction_id, description=m.description)
                bill = source.resolve([need], ensure_pdfs=True).get(need.key)
                if bill is None:
                    recorder.done(item.id, Result.FAILED, f"{m.bill.source} bill {m.bill.bill_id} no longer resolves")
                    continue
                if bill.bill_id != m.bill.bill_id or bill.amount_cents != m.bill.amount_cents:
                    recorder.done(item.id, Result.FAILED,
                                  f"the bill changed: planned {m.bill.bill_id} ({cents(m.bill.amount_cents)}), now "
                                  f"{bill.bill_id} ({cents(bill.amount_cents)}); nothing uploaded")
                    continue
                pdf = bill.pdf_path if bill.has_pdf and bill.pdf_path is not None else source.ensure_pdf(bill)
                recorder.applying([item.id])
                uploading = True
                live.client.upload_attachment(org, m.transaction_id, pdf)
            except Exception as exc:  # noqa: BLE001 - recorded on the item; the next item goes on
                result = Result.UNCERTAIN if uploading and _uncertain(exc) else Result.FAILED
                recorder.done(item.id, result, f"{type(exc).__name__}: {exc}")
                continue
            recorder.done(item.id, Result.APPLIED, f"uploaded {pdf.name}; the transaction is not approved")


__all__ = ["Context", "KEY", "OP", "RULE", "apply", "build", "cents", "open_registry", "plan"]
