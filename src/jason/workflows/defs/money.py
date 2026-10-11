"""The money family of general workflow definitions (docs/workflows/money.md, section 2; the three screen pages
docs/console/screens/monthly-review.md, county-tax-cycle.md, and delinquency-process.md).

Pure data: this module imports only the engine's types (no step names a read, see below), and the definitions are rows,
like a rule row. It names no association. A run's dates are slots asked at
start, a statute is cited by key (``CIV 5500(a)``) and is checked against the authorities shelf when the row registers.

**Ids.** The page's tables name a step with a short word (``snap``, ``lienvote``, ``R1``). Here a step's id is
``<key>.<n>``, n counting the table's rows from 1 in the page's order. ``step_id(key, "snap")`` answers the id for a table
word, and ``table_ids(key)`` is the whole map, for a test or a doc.

**What is a person's step now.** The engine registers a ``check`` only by a name in ``jason.workflows.readers.CHECKS`` and a
``job`` only by a name in ``readers.JOBS``; neither holds a money read yet, and this family adds none. A page's ``check`` or
``job`` row is therefore a ``person`` step whose ``why`` says what it becomes and names it ``(wanted: check NAME)`` or
``(wanted: job NAME)``; ``WANTED`` lists each, with what it would read. The same is true of a ``plan`` the approvals
registry has no kind for. Plans used: ``payhoa-attach-bills`` (the bill, once matched, is attached after a person decides)
and ``payhoa-mailroom-send`` (a mailed notice, charged to the association, two people).

**Not here.** ``delinquency_account`` is built and validates but is left out of ``BUILDERS``: a run about one parcel and one
owner's balance is an executive-session matter (CIV 4935), and the Work backend (src/jason/web/extra/work.py) cannot yet hold
such a run ("executive handling not composed"). A run's id is opaque and never a parcel; until a step can be marked
executive, the definition is not offered. Add it to ``BUILDERS`` when the backend can.

**Clocks.** A ``law`` clock is on the shelf (data/authorities) or it is not a law clock. The Revenue and Taxation Code
installment sections are not on the shelf, so the ``county-tax-cycle`` clocks are ``documents`` clocks, "from the county's
bill". A date jason computes from a statute's day-count says so (``COMPUTED``).
"""

from __future__ import annotations

from typing import Any, Callable, NamedTuple

from jason.workflows.types import (
    Choice, ClockBasis, ClockDef, DateSlot, Elapsed, Phase, Repeat, Role, SkipRule, StepDef, StepKind, Workflow,
)

COMPUTED = "computed by jason from the statute's day-count, the earliest day"
"""Said on every clock jason reckons by adding a statute's days to a date a person recorded. How a period that ends on a
weekend or a holiday is counted is for counsel."""

P, C, J, PL, D, W, B = (StepKind.PERSON, StepKind.CHECK, StepKind.JOB, StepKind.PLAN, StepKind.DECISION, StepKind.WAIT,
                        StepKind.BRANCH)
M, TR, SE, PR, DI, AN = (Role.MANAGER, Role.TREASURER, Role.SECRETARY, Role.PRESIDENT, Role.DIRECTOR, Role.ANYONE)

SKIP_M, SKIP_TR, SKIP_SE = SkipRule((M,)), SkipRule((TR,)), SkipRule((SE,))
SKIP_ANY_OFFICER = SkipRule((M, TR, SE))

ATTACH = "payhoa-attach-bills"
MAILROOM = "payhoa-mailroom-send"


# --- what a step says it becomes ------------------------------------------------------------------------------------

def _check(name: str) -> str:
    return (f" A person's step now; it becomes a check step when the read {name} is registered (docs/workflows/money.md, "
            f"section 7) (wanted: check {name}).")


def _job(name: str) -> str:
    return (f" A person's step now (the command is the terminal's); it becomes a job step when {name} is registered "
            f"(wanted: job {name}).")


def _arrives(name: str) -> str:
    return f" A person notes the arrival now; a read of {name} will end it (wanted: check {name})."


def _plan(name: str) -> str:
    return f" A person's step now; it becomes a plan step when an approvals kind for it is registered (wanted: plan {name})."


WANTED: tuple[str, ...] = (
    # --- checks (readers.CHECKS): read-only, from the stores on disk
    "check bill-snapshot-fresh: bill-attach.snapshot {syncedAt, ageDays, stale} against the integration's 2-day stale-after",
    "check bill-queue-read: bill-attach.counts and rows[].status (matched, ambiguous, no match, unrouted, no source yet, "
    "not checked, already attached, no bill expected)",
    "check bill-handed: the bill-attach run for the month is done or handed (a wait step's arrival)",
    "check payee-class-read: bill-investigation.routing {payeeClass, source, byRule} for the transaction",
    "check stores-tried-read: bill-investigation tried[] with each store's age, and candidates[]",
    "check bill-mail-arrived: a mail item or portal file arrives that matches the transaction's amount",
    "check review-reconciliations: reconciliations per account, covered through the month, open items (CIV 5500(a), (b))",
    "check review-statements: the library holds a bank statement for each account for the month (not built: no check pairs "
    "a statement to a month)",
    "check review-budget: budget variance by category for the month (CIV 5500(c))",
    "check review-income-expense: books pl for the month, operating and reserve (CIV 5500(e))",
    "check review-registers: check register, general ledger, delinquent assessment receivable report runs (CIV 5500(f))",
    "check review-transfers: reserve_transfers against the board's prior written approval (CIV 5502(a); not built: no run "
    "check pairs a transfer to an approval)",
    "check delinquency-ledger-read: delinquency.rows[] {standing, pastDueCents, ledgerSynced} for the account",
    "check delinquency-charges: the ledger's late charge and interest against CIV 5650(b)(2), (3) and the declaration (not built)",
    "check delinquency-order: the ledger's order of application against CIV 5655(a) (not built)",
    "check delinquency-policy-notice: the annual policy statement carries the CIV 5730 notice",
    "check delinquency-floor: assessments alone against the CIV 5720(b) floor (the ledger's past due may include late charges)",
    "check delinquency-closed: balance zero and no lien of record",
    "check delinquency-plan-request: a payment plan request arrives within the notice's window (CIV 5665(b))",
    "check fiscal-window: the CIV 5300(a) and 5310(a) window from the notice catalog; 'date not on record' is a state",
    "check reserve-study-due: reserves latest study date, next visit and review due (CIV 5550(a); applies only when the "
    "components' value reaches the statute's threshold)",
    "check reserve-plan-match: the budget's reserve contribution against the adopted funding plan",
    "check budget-limits: the CIV 5605 limits (20 percent of the preceding year's regular assessment; 5 percent of budgeted "
    "gross expenses for special assessments) (not built)",
    "check disclosure-insurance-summary: packets.insurance_rows, each policy's term in force (CIV 5300(b)(9))",
    "check disclosure-reserve-summary: the figures from the latest study, cash and cash equivalents only (CIV 5300(b)(2), 5565, 5570)",
    "check disclosure-send-plan: counts, billed pages, and estimate for the send (payhoa.pricing)",
    "check disclosure-delivery-read: bounces and returns read from the notice ledger",
    "check fiscal-owner-info-cycle: the owner information cycle's answers are entered (CIV 4041(b)(1))",
    "check reserve-notice: borrowings[].documents.notice, the agenda 'Notice of Intent to Borrow' (CIV 5515(a), 4920)",
    "check reserve-two-signatures: the bank's record of two signatures (not read by jason)",
    "check reserve-restored: a repayment found by amount, a lead (CIV 5515(d))",
    "check insurance-due: insurance-renewals.policies[].daysToTermEnd, renewalWindow, standing",
    "check insurance-limits: insurance_policies.findings against the CIV 5800, 5805, 5806 limits",
    "check insurance-changed: memberNoticeNeeded and the term against the term before (ChangeKind)",
    "check insurance-summary: insurance_rows for the fiscal year (CIV 5300(b)(9))",
    "check tax-standing: tax_standing per parcel (unpaid newest year, delinquent older years, years with no bill)",
    "check tax-bill-files: each bill row has a file under tax-bills/",
    "check tax-mailed-bill: tax_bill_checks, a mailed bill's amounts against the stored bill",
    "check tax-years-closed: balances zero per parcel",
    # --- jobs (readers.JOBS): a command a worker runs, found in the queue by its arguments
    "job bill-snapshot-fetch: jason invoices --fetch (a PayHOA read, no write)",
    "job bill-sources-read: jason fetch-bills; jason sync-tax; jason vendors --sync, per source",
    "job bill-dry-run: jason sync-bills --dry-run (reads PayHOA, uploads nothing); then --source SRC after a bill is kept",
    "job invoice-review-read: jason invoices after the plan",
    "job tax-documents-keep: jason county-tax --import-receipts / --import-bill (signed, append only)",
    "job books-sync: jason books --sync; jason budget; jason reconcile --fetch; jason ledger --fetch, per source",
    "job packet-plan: jason packet annual-disclosures --year Y (plan and gaps), then --values",
    "job packet-build: --build --yes; jason segments; jason preflight; jason review annual-disclosures",
    "job tax-catalog-sync: jason sync-tax, per parcel",
    # --- plans (the approvals registry)
    "plan annual-packet-docs: --make-templates --yes and --build --draft --yes (Docs and a draft PDF)",
)
"""What the page's ``check``, ``job``, and ``plan`` rows would register to become engine steps, each with what it reads.
Every ``(wanted: KIND NAME)`` in a step's ``why`` is an entry here (a test keeps the two in step). Nothing here is
registered: this family adds nothing to ``readers.CHECKS`` or ``readers.JOBS``."""


# --- a table of rows, assembled into a definition ---------------------------------------------------------------------

class _Row(NamedTuple):
    tid: str                               # the page's word for the step
    title: str
    kind: StepKind
    role: Role
    needs: tuple[str, ...]                 # table words
    more: dict[str, Any]


def _row(tid: str, title: str, kind: StepKind, role: Role, needs: str = "", **more: Any) -> _Row:
    if "why" in more:
        more["why"] = more["why"].strip()
    return _Row(tid, title, kind, role, tuple(needs.split()), more)


def _ids(key: str, rows: tuple[_Row, ...]) -> dict[str, str]:
    ids = {r.tid: f"{key}.{i}" for i, r in enumerate(rows, 1)}
    assert len(ids) == len(rows), f"{key}: a table word repeats"
    return ids


def _assemble(key: str, title: str, subject: str, rows: tuple[_Row, ...], *, dates: tuple[DateSlot, ...] = (),
              phases: tuple[tuple[str, str, str], ...] = (), clocks: tuple[ClockDef, ...] = ()) -> Workflow:
    ids = _ids(key, rows)
    steps = []
    for r in rows:
        more = dict(r.more)
        if "choices" in more:      # (key, "table words") pairs, turned into the ids
            more["choices"] = tuple(Choice(k, tuple(ids[t] for t in words.split())) for k, words in more["choices"])
        steps.append(StepDef(ids[r.tid], r.title, r.kind, role=r.role, needs=tuple(ids[n] for n in r.needs), **more))
    built = tuple(Phase(k, t, tuple(ids[x] for x in words.split())) for k, t, words in phases)
    return Workflow(key=key, title=title, family="money", subject=subject, steps=tuple(steps), dates=dates, phases=built,
                    procedure="", clocks=clocks)


def _law(cite: str, slot: str = "", days: int = 0, label: str = "") -> ClockDef:
    """A law clock. With a slot and a day-count it is a date jason computes, and says so."""
    text = label or cite
    if slot and days:
        text = f"{text} ({COMPUTED})"
    return ClockDef(ClockBasis.LAW, slot, days, cite=cite, label=text)


def _policy(label: str, slot: str = "", days: int = 0) -> ClockDef:
    return ClockDef(ClockBasis.PROPOSED_POLICY, slot, days, label=f"{label} (proposed policy, not adopted by the board)")


def _documents(label: str, slot: str = "", days: int = 0, cite: str = "") -> ClockDef:
    return ClockDef(ClockBasis.DOCUMENTS, slot, days, cite=cite, label=label)


# --- 2.1 bill-attach ------------------------------------------------------------------------------------------------

BA = "bill-attach"


def _bill_attach_rows() -> tuple[_Row, ...]:
    return (
        _row("snap", "Is the PayHOA snapshot fresh", P, M, command="jason invoices --fetch",
             record="the snapshot's syncedAt and its age in days", clock=_policy("stale after 2 days: the integration's default, payhoa-transactions"),
             why="The queue never reports a count from nothing: a snapshot older than its stale-after is said first. Skip never."
                 + _check("bill-snapshot-fresh")),
        _row("fetch", "Refresh the snapshot", P, M, "snap", command="jason invoices --fetch", skip=SKIP_M,
             record="the new syncedAt", why="A PayHOA read that fetches no write. Skipped, with the reason, when the snapshot is fresh."
                                           + _job("bill-snapshot-fetch")),
        _row("queue", "Read the queue by status", P, M, "snap", record="the counts by status",
             why="Matched, ambiguous, no match, unrouted, no source yet, not checked, already attached, no bill expected; a loader, no command."
                 + _check("bill-queue-read")),
        _row("srcs", "Read each source that has a pending payment", P, M, "queue", repeat=Repeat.PER_ITEM, skip=SKIP_M,
             command="jason fetch-bills; jason sync-tax; jason vendors --sync", record="the source and its new stamp",
             clock=_policy("each source's stale-after in jason cadence"),
             why="One item a source (a sign-in at a terminal is a person's). Skipped when the source is current." + _job("bill-sources-read")),
        _row("dry", "Dry-run the attach", P, M, "srcs", command="jason sync-bills --dry-run", evidence=("file:bills/last-dry-run.json",),
             record="the dry run is current with the snapshot", clock=_policy("a plan expires after 6 hours: the kind's max_age_hours"),
             why="Reads PayHOA and uploads nothing; each row is matched, ambiguous, or no match, with which date matched. A same-amount "
                 "match is a lead until a person attaches it." + _job("bill-dry-run")),
        _row("plan", "Plan the attaches", PL, TR, "dry", plan_kind=ATTACH, command="jason approvals plan payhoa-attach-bills --by NAME",
             clock=_policy("a plan's max age is 6 hours: the kind's max_age_hours"),
             why="One item a matched row; the applier re-reads each transaction and bill. A rejected or held item is recorded, not "
                 "retried. A payment-signer control may govern this step later."),
        _row("work", "Open an investigation for each row that needs one", P, M, "queue", repeat=Repeat.PER_ITEM, skip=SKIP_M,
             record="the payment-investigation run opened, by transaction id",
             why="One item a transaction in ambiguous, no match, unrouted, or no source yet; skipped for a row that is attached or expects "
                 "no bill. A link to the child run; whether a step may open another run is the board's open question (the page's "
                 "section 11)."),
        _row("inv", "Re-read the invoice review", P, M, "plan", command="jason invoices --fetch; jason invoices",
             record="the invoice summary is newer than the plan", why="The findings a payment already approved still raise." + _job("invoice-review-read")),
        _row("hand", "Hand the pass to the treasurer", P, M, "plan work", record="the counts left open and why",
             clock=ClockDef(ClockBasis.PERSON, "review_on", 0, label="before the treasurer's monthly review"),
             why="The manager attests what is left; skip never."),
    )


def bill_attach() -> Workflow:
    """The monthly pass that attaches bills to PayHOA payments (docs/workflows/money.md, section 2.1). Subject: a month."""
    return _assemble(
        BA, "Attach bills to PayHOA payments", "period", _bill_attach_rows(),
        dates=(DateSlot("review_on", "The treasurer's monthly review", required=False),),
        phases=(("read", "Read", "snap fetch queue srcs"), ("plan", "Dry-run and plan", "dry plan"),
                ("hand", "Work what is left and hand over", "work inv hand")))


# --- 2.2 payment-investigation --------------------------------------------------------------------------------------

PI = "payment-investigation"


def _payment_investigation_rows() -> tuple[_Row, ...]:
    return (
        _row("class", "Name the payee class and the rule that chose it", P, M, record="the class, the source, and the rule",
             why="routing {payeeClass, source, byRule}. A miss stays a miss." + _check("payee-class-read")),
        _row("tried", "Search every store on disk by amount", P, M, "class", repeat=Repeat.PER_ITEM,
             record="the stores tried, each with its age, and the candidates (a document or a payment proof)",
             why="A store not read says 'not read' with its command; the others still show. A candidate is a lead, not the bill."
                 + _check("stores-tried-read")),
        _row("rule", "Propose a payee row when none selected it", P, M, "class", skip=SKIP_M, record="the board item (a finding)",
             command="jason board --set", why="Skipped when a row selected it."),
        _row("proof", "Fetch the bill or the receipt from the payee's own site", P, TR, "tried", skip=SKIP_TR,
             record="the saved bill or receipt a person holds",
             why="A sign-in jason does not do. Skipped when a candidate is exact."),
        _row("keep", "Keep what was saved", P, TR, "proof", repeat=Repeat.PER_ITEM, skip=SKIP_TR,
             command="jason county-tax --import-receipts FILE --by NAME; jason county-tax --import-bill FILE --apn A --year Y --by NAME",
             evidence=("file:tax/receipts.json",), record="the file kept and its row",
             why="One item a file. Signed, append only." + _job("tax-documents-keep")),
        _row("redry", "Dry-run the source again", P, M, "keep", skip=SKIP_M, command="jason sync-bills --dry-run --source SRC",
             record="the row is now matched", why="Skipped if no source owns the payee." + _job("bill-dry-run")),
        _row("attach", "Attach the matched bill", PL, TR, "redry", plan_kind=ATTACH, skip=SKIP_TR,
             command="jason approvals plan payhoa-attach-bills --by NAME",
             clock=_policy("a plan's max age is 6 hours: the kind's max_age_hours"),
             why="Skipped when the outcome is not an attached bill. A person decides and applies the approval."),
        _row("policy", "May a payment's receipt stand in for its bill", D, SE, "out", record="the board's decision, date, vote, and instrument",
             why="The law is silent, so the board decides a written policy once for the association, not for each payment; its "
                 "wording is a proposal until adopted (Civil Code 4350). On the receipt-only path only."),
        _row("mail", "Wait for a scan or a vendor invoice", W, M, "out", command="jason mail; jason vendors --sync",
             clock=_policy("re-check at each monthly pass; no number is the law's"),
             why="Ends when a mail item or portal file matches the amount; a later sync that finds the bill reopens the run. On the "
                 "waiting-for-mail path only." + _arrives("bill-mail-arrived")),
        _row("out", "Record the outcome", B, M, "tried", evidence=("file:bills/investigations.json",),
             command="POST /api/write/bill-investigation/<tx>", record="the outcome row: outcome, by, at, document, note",
             choices=(("attached-bill", ""), ("attached-receipt-only", "policy"), ("not-our-bill", ""),
                      ("waiting-for-mail", "mail"), ("escalated", "esc")),
             why="The outcome words are the code's. Append only; a later outcome supersedes. The treasurer or the manager records it. "
                 "No step here attaches or approves."),
        _row("esc", "Take it to the treasurer or the board", P, TR, "out", command="jason board --set", record="the board item",
             why="On the escalated path only."),
    )


def payment_investigation() -> Workflow:
    """One PayHOA transaction with no bill the sources can match (money.md, section 2.2). Subject: a transaction id."""
    return _assemble(
        PI, "Investigate a payment with no bill", "transaction", _payment_investigation_rows(),
        phases=(("find", "Find", "class tried rule"), ("fetch", "Get the bill and attach it", "proof keep redry attach"),
                ("outcome", "Record the outcome", "out policy mail esc")))


# --- 2.3 monthly-review ---------------------------------------------------------------------------------------------

MR = "monthly-review"

_BY_MONTH = "month_end"


def _duty(cite: str, label: str) -> ClockDef:
    return _law(cite, _BY_MONTH, 0, label)


def _monthly_review_rows() -> tuple[_Row, ...]:
    return (
        _row("sync", "Refresh the books", P, M, repeat=Repeat.PER_ITEM, skip=SKIP_M,
             command="jason books --sync; jason budget; jason reconcile --fetch; jason ledger --fetch",
             record="each source's stamp against its stale-after",
             why="Ledger, budget, reconciliations, and reports are stale after 9 days (the integration defaults; proposed policy, not the "
                 "law's). One item a source; skipped when current." + _job("books-sync")),
        _row("attach", "Bills attached for the month", W, M, skip=SKIP_M,
             why="Links to the bill-attach run for the month; skipped, with the reason, when the board reviews without it."
                 + _arrives("bill-handed")),
        _row("recon", "Reconciliations current: operating, reserve", P, TR, "sync", repeat=Repeat.PER_ITEM,
             command="jason reconcile", record="each account, covered through which month, and its open items",
             clock=_duty("CIV 5500(a)", "review a current reconciliation on a monthly basis, operating and reserve (CIV 5500(a), (b))"),
             why="Whether it is 'current' is the reviewer's judgment, not jason's." + _check("review-reconciliations")),
        _row("stmt", "Latest bank statements on file", P, TR, repeat=Repeat.PER_ITEM, command="jason library",
             record="the statement filed for each account for the month, or none filed",
             clock=_duty("CIV 5500(d)", "review the latest account statements from the financial institutions"),
             why="One item an account." + _check("review-statements")),
        _row("bva", "Actual against budget", P, TR, "sync", command="jason budget", record="the variance by category and the snapshot's age",
             clock=_duty("CIV 5500(c)", "review actual operating revenues and expenses against the budget"), why="" + _check("review-budget")),
        _row("ie", "Income and expense statement, operating and reserve", P, TR, "sync",
             command="jason books pl; jason report treasurers-report period=previous-month --doc --yes",
             record="the statement read for the month", clock=_duty("CIV 5500(e)", "review an income and expense statement"),
             why="" + _check("review-income-expense")),
        _row("regs", "Check register, general ledger, delinquent receivable report", P, TR, "sync", command="jason books check; jason who-owes",
             record="the three reports read for the month (totals and counts only, no names)",
             clock=_duty("CIV 5500(f)", "review the check register, monthly general ledger, and delinquent assessment receivable reports"),
             why="" + _check("review-registers")),
        _row("inv", "Invoice findings worked", P, TR, "attach", repeat=Repeat.PER_ITEM, skip=SKIP_TR, command="jason invoices",
             record="per finding: re-attached, re-categorized, or recovered",
             why="One item a payment; skipped with a reason ('not a problem'). A worked list, not a statutory item."),
        _row("xfer", "Reserve and operating transfers over the limit have prior written approval", P, TR, "sync", repeat=Repeat.PER_ITEM,
             command="jason reserves --transfers", record="each transfer and the board's prior written approval on file",
             clock=_law("CIV 5502(a)", label="no transfer without the board's prior written approval, unless under the limit"),
             why="Beside the six duties of CIV 5500, not a seventh." + _check("review-transfers")),
        _row("path", "Review at a meeting, or independently", B, TR, "recon bva ie regs", record="the path, and for a subcommittee its members",
             choices=(("meeting", ""), ("every-director", "rat"), ("subcommittee", "rat")),
             why="CIV 5500 does not say the board reviews at a meeting; the meeting path is the board's review as the board. CIV 5501 "
                 "names two groups of reviewers, every individual member of the board, or a subcommittee of the treasurer and at least one "
                 "other board member, and one condition, ratification at the next meeting. Three paths, not two."),
        _row("rev", "Review the reports", P, DI, "path", repeat=Repeat.PER_ITEM,
             record="each reviewer's name, the date, and the parts read", command="jason monthly-review --month M --review --parts a,b,c --by NAME",
             clock=_duty("CIV 5500", "the board reviews each month; the day is the board's"),
             why="One item a reviewer: the board at the meeting, each director, or the subcommittee. Each reviewer signs their own, "
                 "and says which parts they read. No store holds this yet (the page's section 8): the attestation's record is it."),
        _row("rat", "Ratify at the next meeting", D, SE, "rev", record="the minutes line that ratifies the review",
             command="jason schedule-evidence --watch",
             clock=_law("CIV 5501", "next_meeting", 0, "ratified at the board meeting subsequent to the review, and reflected in the minutes"),
             why="The independent paths only; the meeting path skips it. A review not ratified is a finding for the board; whether a later "
                 "meeting still counts is for counsel."),
        _row("rec", "The record is filed", P, SE, "rev rat", record="the minutes link", why="The secretary files the minutes line that records the review."),
    )


def monthly_review() -> Workflow:
    """One month's financial review: the six duties of CIV 5500, three review paths, and the ratification CIV 5501 asks of
    the independent ones (money.md, section 2.3; docs/console/screens/monthly-review.md). Subject: a month."""
    return _assemble(
        MR, "The monthly financial review", "period", _monthly_review_rows(),
        dates=(DateSlot("month_end", "The month under review ends"),
               DateSlot("next_meeting", "The board meeting after the review", required=False, after="month_end")),
        phases=(("gather", "Gather", "sync attach"), ("read", "Read the six parts", "recon stmt bva ie regs inv xfer"),
                ("review", "Review and ratify", "path rev rat rec")))


# --- 2.4 delinquency-account (built, left out of BUILDERS) -------------------------------------------------------------

DA = "delinquency-account"


def _delinquency_rows() -> tuple[_Row, ...]:
    return (
        _row("det", "The ledger shows a past-due balance", P, TR, command="jason sync-catalog; jason who-owes",
             record="the standing, the past due in cents, and the ledger's sync day",
             clock=_law("CIV 5650(b)", label="delinquent 15 days after they become due unless the declaration provides longer"),
             why="Standing words are CollectionStanding: OWED_NO_LIEN, LIEN_SECURES_DEBT, RELEASE_DUE, CREDIT."
                 + _check("delinquency-ledger-read")),
        _row("chg", "Late charge and interest within the caps", P, TR, "det", record="the charges against the caps and the declaration",
             clock=_law("CIV 5650(b)", label="late charge and interest within the statute's caps"),
             why="Not built as a check." + _check("delinquency-charges")),
        _row("app", "Payments applied assessments first", P, TR, "det", record="the ledger's order of application",
             clock=_law("CIV 5655(a)", label="payments first to the assessments owed"), why="Not built as a check." + _check("delinquency-order")),
        _row("pol", "The collection policy and the 5730 notice are in force", P, M, repeat=Repeat.PER_PERIOD,
             command="jason packet annual-disclosures --year Y", record="the annual policy statement that carries it",
             clock=_law("CIV 5310(a)", label="the annual policy statement carries the notice"),
             why="Links to the fiscal-year run. Once a year." + _check("delinquency-policy-notice")),
        _row("notice", "Prepare and send the pre-lien notice by certified mail", PL, M, "det chg app pol", plan_kind=MAILROOM,
             command="jason notices; jason mailroom --pdf (preview), then a person sends with --send --yes",
             clock=_law("CIV 5660", label="notify the owner of record in writing by certified mail at least 30 days before recording"),
             why="No base template exists for this notice yet. Mailroom mail is charged to the association and cannot be recalled: "
                 "two people, and jason never sends. The notice ledger row, the Mailroom letter ids, and the certified receipt are the "
                 "record. Skip never."),
        _row("plan", "Payment plan request arrives", W, M, "notice", elapsed=Elapsed.ENDS, command="jason responses --check; jason followups",
             clock=_law("CIV 5665(b)", "notice_mailed", 15, "a request mailed within 15 days of the notice's postmark"),
             why="Ends when the window passes; a request that arrives is logged by the manager." + _arrives("delinquency-plan-request")),
        _row("meet", "Meet the owner in executive session on a payment plan", D, SE, "plan", skip=SKIP_ANY_OFFICER,
             command="POST /api/write/delinquency/<apn>", record="the step 'payment plan offered': decided on, vote, by",
             why="CIV 5665(b) (the board meets the owner in executive session within 45 days of the request's postmark) and 4935(c); the "
                 "45-day clock is on the run (request_postmarked). Skipped when no request arrived."),
        _row("mc", "Offer meet and confer before recording", P, M, "notice", record="the date of the offer and the owner's reply",
             clock=_law("CIV 5670", label="offer dispute resolution before recording a lien"),
             why="Skip never. No store holds the offer yet."),
        _row("wait30", "Wait the 30 days", W, M, "notice", elapsed=Elapsed.ENDS, command="jason followups",
             clock=_law("CIV 5660", "notice_mailed", 30, "at least 30 days prior to recording a lien"),
             why="The notice's certified mail date plus 30 days; how the days are counted is counsel's. If the notice is not proved "
                 "delivered the clock does not start, and a notice cured late starts it again (CIV 5690)."),
        _row("floor", "Foreclosure floor question", P, TR, "det", record="assessments alone against $1,800, or 12 months delinquent",
             clock=_law("CIV 5720(b)", label="the foreclosure floor, assessments alone"),
             why="The ledger's past due may include late charges the floor leaves out; a person separates them." + _check("delinquency-floor")),
        _row("lienvote", "Decide whether to record a lien", D, SE, "wait30 mc", command="POST /api/write/delinquency/<apn>",
             record="the vote, the meeting, and the minutes line (the roll call)",
             clock=_law("CIV 5673", label="by a majority vote of the directors in an open meeting; not delegable"),
             why="Skip never. The board declines or defers as a recorded decision; the run waits here. The vote and the recording are two "
                 "steps."),
        _row("rec", "Record the notice of delinquent assessment", P, PR, "lienvote", evidence=("file:board/collection-steps.json",),
             record="the county index shows the filing", command="jason sync-liens",
             clock=_law("CIV 5675", label="the notice states the amount, a legal description, the owner's name, and the trustee"),
             why="Signed by the president or the person the association designates. jason records no lien."),
        _row("copy", "Mail the recorded notice by certified mail", P, M, "rec", command="jason notices",
             record="the ledger row lien-copy",
             clock=_law("CIV 5675(e)", "recorded_on", 10, "mailed no later than 10 calendar days after recordation"),
             why="Skip never."),
        _row("pay", "Payment received; lien paid", B, M, "rec", choices=(("paid", "rel"), ("unpaid", "enf adr fclose alt hand off")),
             command="jason sync-catalog", record="the ledger balance at or below zero while a lien stands",
             why="Decided by the ledger's fact (the standing RELEASE_DUE). Choose paid to go to the release, unpaid to go on to "
                 "enforcement." + _check("delinquency-closed")),
        _row("rel", "Record the release and give the owner a copy", P, M, "pay", record="the county index shows the release",
             clock=_law("CIV 5685(a)", "paid_on", 21, "within 21 days of the payment, record a lien release or notice of rescission"),
             why="Skip never. A lien still of record past the day is a finding, not an error to hide."),
        _row("enf", "Wait 30 days after recording", W, M, "rec", elapsed=Elapsed.ENDS,
             clock=_law("CIV 5700(a)", "recorded_on", 30, "the lien may be enforced after 30 days following the recording"),
             why="Ends on the day."),
        _row("adr", "Offer meet and confer or ADR before foreclosure", P, M, "enf", record="the offer and the owner's choice",
             clock=_law("CIV 5705(b)", label="offer dispute resolution before initiating foreclosure"), why="Skip never. No store holds the offer yet."),
        _row("fclose", "Decide whether to initiate foreclosure", D, SE, "adr floor", command="POST /api/write/delinquency/<apn>",
             record="the vote in executive session; the next open meeting's minutes name the parcel",
             clock=_law("CIV 5705(c)", label="by a majority vote of the directors in an executive session; not delegable; at least 30 days before any public sale (CIV 4935(d))"),
             why="Skip never. The open minutes name the parcel number, not the owner."),
        _row("alt", "Small claims or another remedy", D, SE, "floor", skip=SKIP_SE, record="the board's recorded step",
             why="CIV 5720(b)(1), (3): for a debt under the floor, small claims or another manner except foreclosure. Skipped when not taken."),
        _row("hand", "Hand the account to an agency", P, M, "pay", skip=SKIP_M, command="jason who-owes-sheet",
             record="the agency step as the board recorded it",
             why="jason writes a sheet for review only and submits nothing to an agency."),
        _row("off", "Write off", D, SE, "pay", skip=SKIP_SE, record="the recorded step 'written off'",
             why="Skipped when the account is not written off."),
        _row("close", "Close the account", P, M, "pay rel off", command="jason who-owes",
             record="balance zero and no lien of record", why="" + _check("delinquency-closed")),
    )


def delinquency_account() -> Workflow:
    """One unit's assessment account under Civil Code 5650 to 5720 (money.md, section 2.4;
    docs/console/screens/delinquency-process.md). **Built but left out of ``BUILDERS``**: see the module docstring. Subject: an
    account, named by an opaque run id and never by a parcel. The lien and foreclosure decisions are the board's and not
    delegated; jason records what the board did, and submits to no agency, records no lien, and forecloses on nothing."""
    return _assemble(
        DA, "A delinquent account", "account", _delinquency_rows(),
        dates=(DateSlot("notice_mailed", "The pre-lien notice was mailed (certified)", required=False),
               DateSlot("request_postmarked", "A payment plan request was postmarked", required=False, after="notice_mailed"),
               DateSlot("recorded_on", "The notice of delinquent assessment was recorded", required=False, after="notice_mailed"),
               DateSlot("paid_on", "The lien was paid", required=False)),
        clocks=(_law("CIV 5665(b)", "request_postmarked", 45, "the board meets the owner in executive session within 45 days of the request's postmark"),),
        phases=(("account", "The account", "det chg app pol"), ("notice", "Notice", "notice plan meet mc wait30 floor"),
                ("lien", "Lien", "lienvote rec copy"), ("release", "Release", "pay rel"),
                ("foreclosure", "Foreclosure and the routes not taken", "enf adr fclose alt hand off close")))


# --- 2.5 fiscal-year ------------------------------------------------------------------------------------------------

FY = "fiscal-year"


def _fiscal_year_rows() -> tuple[_Row, ...]:
    window_open = _law("CIV 5300(a)", "fiscal_year_end", -90, "the window opens: the annual budget report is distributed 30 to 90 days before the end of the fiscal year (CIV 5300(a), 5310(a))")
    return (
        _row("open", "Start the run; set the dates", P, M, record="the fiscal year end and the dated day set",
             why="The window comes from the notice catalog, not from a typed number. Leave room for one correction."),
        _row("win", "The window is computed and fits", P, M, "open", clock=window_open, command="jason notices --catalog",
             record="the window's first and last day, and the dated day inside it",
             why="'Date not on record' is a state, a question for the manager, never a guess." + _check("fiscal-window")),
        # --- R: the reserve
        _row("R1", "The study is due", P, TR, "open", skip=SKIP_M, repeat=Repeat.PER_PERIOD, command="jason reserves --year Y",
             record="the latest study date and the next visit and review due",
             why="CIV 5550(a): at least once every three years. It applies only if the components' value reaches the statute's "
                 "threshold; skipped, with the reason, when 'does not apply' is answered." + _check("reserve-study-due")),
        _row("R2", "Commission or update the study", D, SE, "R1", skip=SKIP_SE, record="the decision record",
             why="Skipped when the study is not due."),
        _row("R3", "File the study", P, M, "R2", command="jason library", record="the library file of the study",
             why="A study file in the library, and the reserves loader's study reference changed."),
        _row("R4", "Annual review of the study", D, SE, "R3", repeat=Repeat.PER_PERIOD, record="the minutes line that records the annual review",
             clock=_law("CIV 5550(a)", label="the board reviews the study, or causes it to be reviewed, annually"), why="Skip never."),
        _row("R5", "Adopt the reserve funding plan, with its schedule of changes", D, SE, "R4", repeat=Repeat.PER_ITEM,
             record="the decision record, the meeting, and the vote",
             clock=_law("CIV 5560", label="the plan is adopted by the board at an open meeting before the membership"),
             why="One item a plan."),
        # --- B: the budget
        _row("B1", "Draft the pro forma operating budget", P, TR, "R5", command="jason budget; jason reserves --year Y",
             clock=ClockDef(ClockBasis.PERSON, "budget_meeting", 0, label="the board's date; no number is the law's"),
             record="next year's draft in PayHOA"),
        _row("B2", "Reserve contribution matches the plan", P, TR, "B1 R5", command="jason reserves --year Y",
             record="the budget's reserve line against the adopted plan", why="" + _check("reserve-plan-match")),
        _row("B3", "Does the budget raise regular assessments", B, TR, "B1", choices=(("increase", "B4 B5 B7"), ("no-increase", "")),
             record="the prior year's regular assessment against the new one, in cents",
             why="Not computed anywhere yet; a person answers until a read is registered."),
        _row("B4", "Test the increase against CIV 5605", B, TR, "B3", choices=(("within-limit", ""), ("over-limit", "B5")),
             clock=_law("CIV 5605", label="more than 20 percent greater than the preceding year's regular assessment, or special assessments above 5 percent of budgeted gross expenses, needs the members' approval"),
             record="the limits and the figures, in cents",
             why="A finding, not a verdict; no step says 'complies'." + _check("budget-limits")),
        _row("B5", "Members approve an over-limit increase", D, SE, "B4", record="the election or meeting result",
             clock=_law("CIV 5605", label="the approval of a majority of a quorum of members"),
             why="On the over-limit path only."),
        _row("B6", "Adopt the budget", D, SE, "B2 B4", record="the decision record and the minutes",
             clock=_policy("adopt before the collect stage closes"),
             why="The law is silent on the day the board adopts the budget: a held question for the board. Skip never."),
        _row("B7", "Notice of the increase", P, M, "B6", command="jason notices", record="the ledger row assessment-increase",
             clock=_law("CIV 5615", "increase_due", -30, "individual notice not less than 30 nor more than 60 days before the increased assessment becomes due"),
             why="On the increase path only."),
        # --- D: the annual disclosures packet
        _row("D1", "Plan the packet; read gaps", P, M, "win B6", command="jason packet annual-disclosures --year Y",
             record="the parts found or missing and the tokens open", why="" + _job("packet-plan")),
        _row("D2", "Write the values file", P, M, "D1", command="jason packet annual-disclosures --year Y --values",
             record="the open tokens listed", why="" + _job("packet-plan")),
        _row("D3", "Collect figures and files", P, TR, "D2", repeat=Repeat.PER_ITEM, skip=SKIP_ANY_OFFICER,
             record="each item: who, asked on, due by, state, and the value or file",
             clock=_policy("the latest day an item can arrive and leave the days the next stage needs", "dated_day", 0),
             why="One item a figure or file; waive with a reason, never 'present'. The collect list is not built."),
        _row("D4", "The insurance summary is complete", P, TR, "D3", command="jason policies --fetch",
             record="each policy's term in force, and the gaps",
             clock=_law("CIV 5300(b)(9)", label="a summary of the association's insurance policies"),
             why="Links to the insurance-renewal run." + _check("disclosure-insurance-summary")),
        _row("D5", "The reserve summary and the 5570 form", P, TR, "R5", command="jason reserves --year Y",
             record="the figures from the latest study, based only on cash and cash equivalents",
             clock=_law("CIV 5300(b)(2)", label="the reserve summary (CIV 5565, 5570)"), why="" + _check("disclosure-reserve-summary")),
        _row("D6", "The board's statements", D, SE, "B6 R5", repeat=Repeat.PER_ITEM, record="each statement entered by NAME: 'not yet adopted' or the meeting where adopted",
             clock=_law("CIV 5300(b)", label="the board's statements"),
             why="jason never writes the board's statement; a statement not yet adopted prints as such and a final build refuses."),
        _row("D7", "Link the owner information cycle", W, M, clock=_law("CIV 4041(b)(1)", "mailing_day", -30, "the answers are entered at least 30 days before the 5300 and 5310 disclosures"),
             why="Links to the owner-info-cycle run; ends when its answers are entered." + _arrives("fiscal-owner-info-cycle")),
        _row("D8", "Make the templates; build a draft", P, M, "D3 D4 D5 D6",
             command="jason packet annual-disclosures --year Y --make-templates --yes; then --build --draft --yes",
             record="the Docs and the draft PDF, with the gap pages named", why="No approvals kind is registered for it." + _plan("annual-packet-docs")),
        _row("D9", "Freeze, build, check", P, M, "D8", repeat=Repeat.PER_ITEM, command="jason packet annual-disclosures --year Y --build --yes; jason segments; jason preflight; jason review annual-disclosures",
             record="the revision built and its checks", why="One item a revision. The freeze is not built." + _job("packet-build")),
        _row("D10", "Read the packet", P, AN, "D9", repeat=Repeat.PER_ITEM, record="read by NAME, revision N",
             why="Adopts nothing."),
        _row("D11", "Plan the send", P, M, "D10", repeat=Repeat.PER_ITEM,
             command="jason mailroom --pdf --units U --notice annual-budget-report-YEAR",
             record="the counts, billed pages, and estimate in cents",
             clock=_law("CIV 5300(a)", "fiscal_year_end", -30, "the window's last day (CIV 5300(a), 5310(a))"),
             why="One item a variant. Billing is by printed page with PayHOA's address page counted." + _check("disclosure-send-plan")),
        _row("D12", "Send: email first, mail after", P, M, "D11", repeat=Repeat.PER_ITEM,
             command="jason mailroom --send --yes; jason owner-info --email-batch style batches",
             record="the batch key and the channel; for mail, the treasurer as the second person",
             clock=_law("CIV 5320(a)", "dated_day", 0, "individual delivery of the full report or a summary, by the dated day"),
             why="One item a channel; skip never. A send after the window closed says so in the law's words."),
        _row("D13", "Delivery read; follow-ups", W, M, "D12", command="jason notices KEY --sync; jason followups",
             clock=_policy("read delivery again after 24 hours"),
             why="Ends when the window closes or a person notes the arrival; 'none on record' until read." + _arrives("disclosure-delivery-read")),
        _row("D14", "Archive with proof", P, M, "D13", record="the sent packet, the map, the hashes, and the proof link"),
        # --- F: the reviewed financial statement
        _row("F1", "Does 5305 apply", B, TR, "open", choices=(("applies", "F2 F3 F4"), ("does-not-apply", "")),
             command="jason books pl", record="the year's gross income, in cents, against $75,000",
             clock=_law("CIV 5305", label="a review of the financial statement for a year of gross income above $75,000"),
             why="A fact jason will read; a person answers until a read is registered."),
        _row("F2", "Engage a licensee", D, SE, "F1", record="the recorded decision and the contract's address"),
        _row("F3", "Receive the review", P, TR, "F2", record="the library file of the review",
             clock=_documents("the engagement's date"), why="The year must be closed."),
        _row("F4", "Distribute within 120 days", P, M, "F3", command="jason notices financial-review",
             record="the ledger row financial-review",
             clock=_law("CIV 5305", "fiscal_year_end", 120, "distributed to the members within 120 days after the close of each fiscal year, by individual delivery"),
             why="Skip never when 5305 applies."),
        # --- C: close
        _row("C1", "Close the run; write the lessons", P, M, "D14 F4", command="jason lessons --area money",
             record="the lessons added, with their status",
             why="The money lesson area does not exist yet (the page's section 8)."),
    )


def fiscal_year() -> Workflow:
    """The fiscal year's spine: reserve, budget, annual disclosures, the reviewed statement, and the close (money.md, section 2.5).
    Subject: a fiscal year. The long-lived run: it opens in budget season and closes after the 120 days."""
    return _assemble(
        FY, "The fiscal year", "period", _fiscal_year_rows(),
        dates=(DateSlot("fiscal_year_end", "The fiscal year ends"),
               DateSlot("budget_meeting", "The board meeting that takes up the budget", required=False),
               DateSlot("dated_day", "The dated day of the reports", required=False),
               DateSlot("mailing_day", "The reports are mailed", required=False),
               DateSlot("increase_due", "An increased assessment becomes due", required=False)),
        phases=(("open", "Open", "open win"), ("reserve", "Reserve", "R1 R2 R3 R4 R5"),
                ("budget", "Budget", "B1 B2 B3 B4 B5 B6 B7"),
                ("disclosures", "Annual disclosures", "D1 D2 D3 D4 D5 D6 D7 D8 D9 D10 D11 D12 D13 D14"),
                ("statement", "Reviewed statement", "F1 F2 F3 F4"), ("close", "Close", "C1")))


# --- 2.6 reserve-borrowing ------------------------------------------------------------------------------------------

RB = "reserve-borrowing"


def _reserve_borrowing_rows() -> tuple[_Row, ...]:
    return (
        _row("spend", "Is it spending for a major component, not a loan", B, TR, command="jason reserves --transfers",
             choices=(("spending", ""), ("borrowing", "note fnd rst late sa")), record="the memo and the board's resolution",
             why="CIV 5510(b): spending for a major component is not a loan. A borrowing takes the path below."),
        _row("sig", "Two signatures for the withdrawal", P, TR, record="the bank's record, not read by jason",
             clock=_law("CIV 5510(a)", label="the signatures of at least two persons, directors or officers as the statute names them"),
             why="Skip never." + _check("reserve-two-signatures")),
        _row("appr", "Prior written approval over the limit", D, SE, skip=SKIP_SE, record="the written approval on file",
             why="CIV 5502(a): no transfer over the limit without the board's prior written approval. Skipped under the limit "
                 "(the engine cannot say 'a legal step unless it does not apply', so the law clock is cited here, not set)."),
        _row("note", "Notice of intent in a meeting notice", P, M, "spend", command="jason reserves --transfers",
             record="the agenda 'Notice of Intent to Borrow' and the meeting notice",
             clock=_law("CIV 5515(a)", label="notice of the intent to consider the transfer in a board meeting notice (CIV 4920)"),
             why="" + _check("reserve-notice")),
        _row("fnd", "The board's written finding in the minutes", D, SE, "note", evidence=("file:payhoa/reserve-findings.json",),
             command="POST /api/write/reserve-findings/<key>", record="the finding, recorded in the minutes",
             clock=_law("CIV 5515(c)", label="a written finding recorded in the board's minutes"), why="Skip never."),
        _row("rst", "Restore the money", W, TR, "fnd", command="jason reserves --transfers --fetch",
             clock=_law("CIV 5515(d)", "transfer_on", 365, "restored within one year of the date of the initial transfer"),
             why="Keeps waiting past the day and says so; the repayment is a lead found by amount, and the resolution says which loan."
                 + _arrives("reserve-restored")),
        _row("late", "A delayed restoration", D, SE, "fnd", skip=SKIP_SE, record="the finding for a late restoration, supported by documentation",
             why="Only when late; the same notice as a transfer (CIV 5515(d)). Needs the finding, not the restoration, because the restoration "
                 "is what is late."),
        _row("sa", "Special assessment if needed", D, SE, "fnd", skip=SKIP_SE, record="the decision record",
             why="Only when the restoration is at risk (CIV 5515(e), 5605)."),
        _row("lit", "Litigation use: general notice, quarterly accounting", P, M, skip=SKIP_M, command="jason notices",
             record="the notice record and the accounting", why="CIV 5520; only for litigation."),
    )


def reserve_borrowing() -> Workflow:
    """One borrowing from a reserve account (money.md, section 2.6). Subject: a borrowing, keyed by day and transaction."""
    return _assemble(
        RB, "A reserve borrowing", "borrowing", _reserve_borrowing_rows(),
        dates=(DateSlot("transfer_on", "The date of the initial transfer"),),
        phases=(("transfer", "The transfer", "spend sig appr"), ("borrow", "Borrow and restore", "note fnd rst late sa"),
                ("litigation", "Litigation use", "lit")))


# --- 2.7 insurance-renewal ------------------------------------------------------------------------------------------

IR = "insurance-renewal"


def _insurance_renewal_rows() -> tuple[_Row, ...]:
    return (
        _row("due", "The term end is near", P, M, command="jason insurance", record="the policy, the days to its term end, and its standing",
             clock=_policy("90 days before the term end: WINDOW_DAYS; the profile's schedule may set its own", "term_end", -90),
             why="" + _check("insurance-due")),
        _row("quote", "Gather the agent's proposals", P, M, "due", command="jason gmail --sync; jason mail",
             record="the proposals in the library or mail", why="Gmail headers are leads."),
        _row("min", "Required limits and coverages", P, M, "quote", command="jason policies",
             record="the findings against the required limits",
             clock=_law("CIV 5800", label="the required coverages and limits (CIV 5800, 5805, 5806)"), why="" + _check("insurance-limits")),
        _row("dec", "Decide the renewal", D, SE, "quote min", command="POST /api/write/insurance-renewals/<number>",
             record="the decision (renew as quoted, renew with changes, re-bid, change carrier, let lapse), decidedOn, by, premium, limitsChanged",
             why="Once per term; skip never. The board decides; jason buys nothing."),
        _row("bind", "Confirm the new term is bound", P, M, "dec", command="jason policies --fetch; jason insurance",
             record="the declarations, the premium paid or financed, and the policy sheet updated", why="standing: next term paid."),
        _row("chg", "Did coverage change or lapse", B, M, "dec bind", choices=(("changed", "mem"), ("unchanged", "")),
             record="memberNoticeNeeded, and the term against the term before",
             why="A fact jason will read; a person answers until a read is registered." + _check("insurance-changed")),
        _row("mem", "Notice to members", P, M, "chg", command="jason notices", record="the ledger row insurance-change",
             clock=_law("CIV 5810", label="individual notice as soon as reasonably practicable (no number: a held question); for a nonrenewal where replacement will not be in effect, immediately"),
             why="Only when coverage changed or lapsed."),
        _row("sum", "Feed the summary", P, M, "bind", repeat=Repeat.PER_PERIOD, command="jason packet annual-disclosures --year Y",
             record="insurance_rows for the fiscal year",
             clock=_law("CIV 5300(b)(9)", label="the insurance summary in the annual budget report"),
             why="Links into the fiscal-year run (D4)." + _check("insurance-summary")),
    )


def insurance_renewal() -> Workflow:
    """One policy's next term (money.md, section 2.7). Subject: a policy term."""
    return _assemble(
        IR, "Renew an insurance policy", "policy", _insurance_renewal_rows(),
        dates=(DateSlot("term_end", "The policy's term ends"),),
        phases=(("prepare", "Prepare", "due quote min"), ("decide", "Decide and bind", "dec bind"),
                ("tell", "Tell the members and the summary", "chg mem sum")))


# --- 2.8 county-tax-cycle -------------------------------------------------------------------------------------------

CT = "county-tax-cycle"

_FROM_BILL = "from the county's bill"


def _county_tax_rows() -> tuple[_Row, ...]:
    return (
        _row("sync", "Read the county's tax catalog", P, M, repeat=Repeat.PER_ITEM, skip=SKIP_M, command="jason sync-tax",
             record="the catalog read, per parcel, and its stamp",
             clock=_policy("monthly on the 1st; stale after 35 days"),
             why="One item a parcel; skipped when current. Another county needs its own tax adapter." + _job("tax-catalog-sync")),
        _row("stand", "Read each parcel's standing", P, TR, "sync", repeat=Repeat.PER_ITEM, record="unpaid, delinquent, and years with no bill",
             why="Newest year unpaid reads 'due', never 'delinquent', until a bill date is entered." + _check("tax-standing")),
        _row("bill", "Every bill has its PDF", P, TR, "sync", repeat=Repeat.PER_ITEM, record="the bill row has a file under tax-bills/",
             why="One item a bill." + _check("tax-bill-files")),
        _row("pdf", "Save a missing bill", P, TR, "bill", repeat=Repeat.PER_ITEM, skip=SKIP_TR,
             command="jason county-tax --import-bill FILE --apn A --year Y --by NAME", record="the bill row", why="Skipped when present."),
        _row("mail", "The mailed bill matches the catalog", P, TR, "sync", repeat=Repeat.PER_ITEM, skip=SKIP_TR,
             record="the mailed bill's amounts against the stored bill",
             why="A supplemental or corrected bill matches neither." + _check("tax-mailed-bill")),
        _row("due", "Each installment's due and delinquent days", W, TR, "stand", repeat=Repeat.PER_ITEM, command="jason deadlines",
             clock=_documents(_FROM_BILL + "; the Revenue and Taxation Code sections are not on the authorities shelf, so nothing here is law"),
             why="One item an installment. A date not on record is a state: the county's bill states it."),
        _row("pay", "Pay the installment", P, TR, "stand", repeat=Repeat.PER_ITEM, record="the PayHOA transaction appears",
             clock=_documents("the delinquent day on the county's bill"),
             why="jason pays nothing and signs in to no collector's site. Skip never."),
        _row("rcpt", "Keep the receipt", P, TR, "pay", repeat=Repeat.PER_ITEM, command="jason county-tax --import-receipts FILE --by NAME",
             evidence=("file:tax/receipts.json",), record="the confirmation number, the items in cents, and the last four of the tender",
             why="A receipt is proof of payment, not the bill."),
        _row("att", "Attach the bill to the payment", PL, TR, "rcpt sync", plan_kind=ATTACH, repeat=Repeat.PER_ITEM,
             command="jason sync-bills --dry-run --source county-tax; jason approvals plan payhoa-attach-bills --by NAME",
             clock=_policy("a plan's max age is 6 hours: the kind's max_age_hours"),
             why="The county-tax source must match one receipt, one bill, and one PDF; a receipt that paid several bills is no match and a "
                 "person decides." + _job("bill-dry-run")),
        _row("cls", "Close the year's installments", P, TR, "att", record="balances zero per parcel", why="" + _check("tax-years-closed")),
    )


def county_tax_cycle() -> Workflow:
    """A tax year for the association's parcels (money.md, section 2.8; docs/console/screens/county-tax-cycle.md). The clocks
    are ``documents`` clocks, 'from the county's bill': the Revenue and Taxation Code installment sections are not on the
    authorities shelf, so no installment day is a law clock. Subject: a tax year."""
    return _assemble(
        CT, "The county property tax", "period", _county_tax_rows(),
        dates=(DateSlot("first_due", "First installment due, from the county's bill", required=False),
               DateSlot("first_delinquent", "First installment delinquent after, from the county's bill", required=False, after="first_due"),
               DateSlot("second_due", "Second installment due, from the county's bill", required=False, after="first_due"),
               DateSlot("second_delinquent", "Second installment delinquent after, from the county's bill", required=False, after="second_due")),
        clocks=(_documents("first installment " + _FROM_BILL, "first_due"), _documents("first installment delinquent after, " + _FROM_BILL, "first_delinquent"),
                _documents("second installment " + _FROM_BILL, "second_due"), _documents("second installment delinquent after, " + _FROM_BILL, "second_delinquent")),
        phases=(("read", "Read the county", "sync stand bill pdf mail"), ("pay", "Pay and keep the receipt", "due pay rcpt"),
                ("attach", "Attach and close", "att cls")))


# --- the registry ---------------------------------------------------------------------------------------------------

_ROWS: dict[str, Callable[[], tuple[_Row, ...]]] = {
    BA: _bill_attach_rows, PI: _payment_investigation_rows, MR: _monthly_review_rows, DA: _delinquency_rows,
    FY: _fiscal_year_rows, RB: _reserve_borrowing_rows, IR: _insurance_renewal_rows, CT: _county_tax_rows,
}


def step_id(key: str, tid: str) -> str:
    """The step id for the page's word: ``step_id("bill-attach", "snap")`` is ``bill-attach.1``."""
    ids = _ids(key, _ROWS[key]())
    if tid not in ids:
        raise KeyError(f"{key} has no table row {tid}")
    return ids[tid]


def table_ids(key: str) -> dict[str, str]:
    """{the page's word: step id} for one definition, in the page's order."""
    return _ids(key, _ROWS[key]())


KEYS: tuple[str, ...] = tuple(_ROWS)
"""The keys of the eight definitions this module builds, in the page's order of section 2."""


BUILDERS: tuple[Callable[[], Workflow], ...] = (
    bill_attach, payment_investigation, monthly_review, fiscal_year, reserve_borrowing, insurance_renewal, county_tax_cycle,
)
"""The definitions ``register_general`` registers. ``delinquency_account`` is built (``LEFT_OUT``) and not listed: an executive
matter about one parcel and one owner's balance, which the Work backend cannot hold yet ("executive handling not composed")."""

LEFT_OUT: tuple[Callable[[], Workflow], ...] = (delinquency_account,)


__all__ = ["BUILDERS", "COMPUTED", "KEYS", "LEFT_OUT", "WANTED", "bill_attach", "county_tax_cycle", "delinquency_account",
           "fiscal_year", "insurance_renewal", "monthly_review", "payment_investigation", "reserve_borrowing", "step_id", "table_ids"]
