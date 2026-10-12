"""The money family's reads (docs/workflows/money.md, sections 2 and 7): the ``check`` names a money definition may use.

Twelve came first (the bill-attach, payment-investigation, monthly-review, reserve, insurance-due, and tax reads); round two
added fourteen: ``review-statements``, ``review-income-expense``, ``review-registers`` (the library and the stored
ledger), ``fiscal-window`` (the notice catalog), ``reserve-plan-match`` and ``disclosure-reserve-summary`` (the reserve
study, the budget), ``disclosure-insurance-summary``, ``insurance-limits``, ``insurance-changed`` (a suggestion for a
person's answer, never the answer) and ``insurance-summary`` (the policy report and the renewals store),
``disclosure-delivery-read`` (the notice ledger), ``reserve-notice`` and ``reserve-restored`` (the reserve transfers), and
``tax-years-closed`` (the tax catalog). ``insurance-answer`` came after: it says in the run whether the person's answer to the
suggestion agrees with it.

Each read is read-only. It looks at stores already on disk (the PayHOA snapshot, the dry run, the reconciliations, the
finance snapshot, the stored ledger, the library, the reserve studies, the insurance sheet and policy report, the notice
ledger, the tax catalog, the run store) and writes nothing, reaches no network, and calls no PayHOA, Google, county portal,
or Keeper. The tax catalog and the notice ledger are opened read only (``mode=ro``), never through ``TaxStore`` or the ledger
module's own opener, whose constructors create tables. A store that is missing or cannot be read gives ``ok=False`` with
the reason; a read never raises and is never ``ok`` by default. Amounts are integer cents.

**Not built here, and why.** ``review-transfers`` (no store holds the board's prior written approval of a transfer),
``delinquency-ledger-read``, ``delinquency-charges``, ``delinquency-order``, ``delinquency-policy-notice``,
``delinquency-floor``, ``delinquency-plan-request`` and ``delinquency-closed`` (a delinquent account's run is held and its
subject is an opaque id, never a parcel, so a read cannot tell which account the run is about; the association-wide counts
and ages stay with ``jason who-owes`` and ``association_collections``), ``budget-limits`` (the figures are a person's
until counsel reads CIV 5605), ``reserve-two-signatures`` (the bank's record, which jason does not read),
``disclosure-send-plan`` (the page counts come from payhoa's pricing, which a read may not import),
``fiscal-owner-info-cycle`` (the members family reads the cycle), and ``tax-mailed-bill`` (its reader opens ``TaxStore``).

**What ``ok`` means.** For a read a step is *about* (a snapshot is fresh, a policy's term end is near, a reconciliation
covers the month) ``ok`` says the claim holds and ``message`` says what was found. For a read that only reports (the
queue's counts, the stores searched, the payee class) ``ok`` says the read was made. None of them decides anything a
person decides: a candidate is a lead, a standing is a reading, and the reviewer's judgment stays the reviewer's.

**Privacy.** The messages carry counts, dates, categories, and ids, never an owner's name or balance. A parcel is shown by
its last four characters; a candidate in mail or Gmail is not described beyond its kind.

**Subjects.** A run's subject reads ``month:2099-09``, ``transaction:12345``, ``policy:NUMBER``, or a year; a read takes
what it needs from the subject, then the run's dates, and says so when the run names none.

Registered by importing this module (``jason.workflows.checks.load_all`` does); importing it loads no profile.
"""

from __future__ import annotations

import functools
import re
import sqlite3
from datetime import date, datetime, time, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Iterable

from jason.workflows.checks import check
from jason.workflows.readers import StoreReaders
from jason.workflows.types import CheckResult, RunView

RENEWAL_WINDOW_DAYS = 90
"""The window an insurance term end is called near: a proposed policy, not the law's (the definition's own clock says the same)."""

_MONTH = re.compile(r"(?<!\d)(\d{4})-(\d{2})(?!\d)")
_YEAR = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")
_LAST = 5
"""How many ids a message lists before it says 'and N more'."""


class _Unreadable(Exception):
    """A store that is missing or cannot be read: the message is the reason, said as it is."""


def _guarded(name: str) -> Callable[[Callable[..., CheckResult]], Callable[..., CheckResult]]:
    """Register ``fn`` as the read ``name``. An exception becomes ``ok=False`` with its reason; a read never raises."""

    def wrap(fn: Callable[..., CheckResult]) -> Callable[..., CheckResult]:
        @functools.wraps(fn)
        def run(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
            try:
                return fn(readers, view, item)
            except _Unreadable as exc:
                return CheckResult(False, (), str(exc))
            except Exception as exc:  # noqa: BLE001 - a store that cannot be read fails the check with the reason
                return CheckResult(False, (), f"cannot read: {type(exc).__name__}: {str(exc)[:200]}")

        return check(name)(run)

    return wrap


# --- small helpers --------------------------------------------------------------------------------------------------

def _address(relative: Path | str) -> str:
    return "file:" + Path(relative).as_posix()


def _noon(readers: StoreReaders) -> datetime:
    """The reader's day as a moment, so an age in days is reproducible."""
    return datetime.combine(readers.today, time(12, 0), tzinfo=timezone.utc)


def _dates(view: RunView) -> dict[str, str]:
    return dict(getattr(view, "dates", None) or {})


def _month_of(view: RunView) -> str:
    """``YYYY-MM`` from the run's subject, else its month_end date; empty when the run names none."""
    for text in (getattr(view, "subject", ""), _dates(view).get("month_end", "")):
        found = _MONTH.search(str(text or ""))
        if found and 1 <= int(found.group(2)) <= 12:
            return f"{found.group(1)}-{found.group(2)}"
    return ""


def _year_of(view: RunView, readers: StoreReaders | None = None, *, default: bool = True) -> int | None:
    """A year from the run's subject, label, or fiscal-year end; the reader's year when ``default`` and none is named."""
    for text in (getattr(view, "subject", ""), getattr(view, "label", ""), _dates(view).get("fiscal_year_end", "")):
        found = _YEAR.search(str(text or ""))
        if found:
            return int(found.group(1))
    return readers.today.year if default and readers is not None else None


def _transaction_of(view: RunView, item: str) -> int | None:
    """The PayHOA transaction id the item or the run's subject names (``transaction:12345`` or a bare number)."""
    for text in (item, str(getattr(view, "subject", "") or "")):
        found = re.search(r"(\d+)\s*$", text.strip())
        if found:
            return int(found.group(1))
    return None


def _settings() -> Any:
    try:
        from jason.config import Settings

        return Settings.load()
    except Exception:  # noqa: BLE001 - no .env: no category overrides, the profile's own rules
        return None


def _registry(readers: StoreReaders) -> Any:
    from jason.sources.offline import routing_registry

    return routing_registry(readers.community, _settings(), readers.data_dir)


def _more(items: Iterable[str]) -> str:
    listed = list(items)
    shown = ", ".join(listed[:_LAST])
    return shown + (f" and {len(listed) - _LAST} more" if len(listed) > _LAST else "")


def _last4(value: Any) -> str:
    return str(value or "")[-4:]


def _digits(value: Any) -> str:
    return re.sub(r"\D", "", str(value or ""))


class _NoRoute:
    """A registry that routes nothing: the snapshot's age does not depend on whose bill a payment is."""

    @staticmethod
    def route(_tx: dict[str, Any]) -> None:
        return None


_NOBODY = SimpleNamespace(payee_rules=lambda: ())


# --- bill-attach ----------------------------------------------------------------------------------------------------

@_guarded("bill-snapshot-fresh")
def snapshot_fresh(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """The stored PayHOA snapshot is no older than the integration's stale-after (``payhoa-transactions``, 2 days)."""
    from jason.tasks import bill_dry_run, bill_queue

    out = bill_queue.build(readers.data_dir, _NOBODY, _NoRoute(), now=_noon(readers))
    if not out.get("found"):
        return CheckResult(False, (), f"{out.get('reason', 'No PayHOA snapshot on disk.')} {out.get('command', '')} fetches it".strip())
    snap = out["snapshot"]
    evidence = readers.evidence_entries((_address(bill_dry_run.SNAPSHOT),))
    stamp, age, limit = str(snap.get("syncedAt") or ""), snap.get("ageDays"), snap.get("staleAfterDays")
    if age is None:
        return CheckResult(False, evidence, f"the snapshot's syncedAt ({stamp or 'none'}) cannot be read as a time; {snap.get('command', '')} fetches it")
    if snap.get("stale"):
        return CheckResult(False, evidence, f"the snapshot of {stamp[:10]} is {age} days old, past its stale-after of {limit} days "
                                            f"(proposed policy: the integration's default); {snap.get('command', '')} refreshes it")
    bound = f"within its stale-after of {limit} days" if limit is not None else "and no stale-after is set for its source"
    return CheckResult(True, evidence, f"the snapshot of {stamp[:10]} is {age} days old, {bound}")


@_guarded("bill-queue-read")
def queue_read(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """The queue can be read from the snapshot, routed offline with the profile's rules: how many rows wait, by status."""
    from jason.tasks import bill_dry_run, bill_queue

    out = bill_queue.build(readers.data_dir, readers.community, _registry(readers), now=_noon(readers))
    if not out.get("found"):
        return CheckResult(False, (), f"{out.get('reason', 'No PayHOA snapshot on disk.')} {out.get('command', '')} fetches it".strip())
    counts = out.get("counts") or {}
    rows = sum(counts.values())
    by = ", ".join(f"{n} {status}" for status, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))
    stale = " The snapshot is stale." if (out.get("snapshot") or {}).get("stale") else ""
    sources = out.get("sourcesNeeded") or []
    need = f" Sources with a payment waiting: {', '.join(sources)}." if sources else ""
    evidence = readers.evidence_entries((_address(bill_dry_run.SNAPSHOT), _address(bill_dry_run.STORE)))
    return CheckResult(True, evidence, f"{rows} payment(s) wait on a bill" + (f": {by}" if by else "")
                       + f"; {out.get('withoutPdf', 0)} without a PDF.{need}{stale}")


@_guarded("bill-handed")
def bill_handed(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """A bill-attach run for the month has handed the pass to the treasurer (or is done)."""
    from jason.workflows import definitions, fold, store
    from jason.workflows.defs import money
    from jason.workflows.types import RunState, StepState

    month = _month_of(view)
    if not month:
        return CheckResult(False, (), "the run names no month, so the bill-attach run to look for is unknown")
    wf = definitions.find(money.BA)
    if wf is None:
        return CheckResult(False, (), f"the definition {money.BA} is not registered here")
    hand = money.step_id(money.BA, "hand")
    found = []
    for definition, rid in store.list_runs(readers.data_dir):
        if definition != money.BA:
            continue
        run = store.read(readers.data_dir, definition, rid)
        if not run.events:
            continue
        first = _MONTH.search(str(run.events[0].detail.get("subject", "")))
        if not first or f"{first.group(1)}-{first.group(2)}" != month:
            continue
        seen = fold.state(list(run.events), wf, readers.today, run_id=rid)
        if seen.state is RunState.CANCELLED:
            continue
        found.append((rid, seen))
    if not found:
        return CheckResult(False, (), f"no {money.BA} run for {month} is on record")
    for rid, seen in found:
        if seen.state is RunState.DONE:
            return CheckResult(True, (), f"the {money.BA} run for {month} is done ({rid})")
        if seen.state_of(hand) is StepState.DONE:
            return CheckResult(True, (), f"the {money.BA} run for {month} has handed the pass to the treasurer ({rid})")
    states = ", ".join(f"{rid} is {seen.state.value}" for rid, seen in found)
    return CheckResult(False, (), f"the pass for {month} is not handed yet: {states}")


# --- payment-investigation ------------------------------------------------------------------------------------------

def _snapshot_transaction(readers: StoreReaders, ident: int) -> tuple[dict[str, Any], str]:
    """(the transaction of the stored snapshot, its syncedAt); a snapshot that is missing or lacks it is unreadable."""
    import json

    from jason.tasks import bill_dry_run

    path = readers.data_dir / bill_dry_run.SNAPSHOT
    if not path.is_file():
        raise _Unreadable("No PayHOA snapshot on disk; jason invoices --fetch fetches it")
    snap = json.loads(path.read_text(encoding="utf-8"))
    tx = next((t for t in snap.get("transactions") or [] if int(t.get("id") or 0) == ident), None)
    if tx is None:
        raise _Unreadable(f"transaction {ident} is not in the snapshot of {str(snap.get('syncedAt') or '')[:10] or 'no date'}")
    return tx, str(snap.get("syncedAt") or "")


def _tx_id(view: RunView, item: str) -> int:
    ident = _transaction_of(view, item)
    if ident is None:
        raise _Unreadable("the run's subject names no PayHOA transaction")
    return ident


@_guarded("payee-class-read")
def payee_class_read(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """The payee class of the transaction, the source that owns it, and the profile row that chose the class. A miss stays a miss."""
    from jason.community.payees import payee_of, rule_of
    from jason.tasks import bill_dry_run

    tx, _stamp = _snapshot_transaction(readers, _tx_id(view, item))
    rules = tuple(readers.community.payee_rules())
    row, payee, source = rule_of(tx, rules), payee_of(tx, rules), _registry(readers).route(tx)
    where = f"owned by the {source.name} source" if source is not None else "owned by no bill source"
    chosen = (f"selected by the profile's payee row: {row.note or 'a row without a note'}" if row is not None
              else "no payee row selects it (a miss stays a miss; a row can be proposed)")
    return CheckResult(True, readers.evidence_entries((_address(bill_dry_run.SNAPSHOT),)),
                       f"payee class {payee.value}, {where}; {chosen}")


def _card(readers: StoreReaders, view: RunView, item: str) -> dict[str, Any]:
    """The investigation card for the run's transaction, without the P2 detail of mail or Gmail."""
    from jason.tasks.bill_investigation import investigate

    card = investigate(readers.data_dir, readers.community, _registry(readers), _tx_id(view, item), now=_noon(readers), private=False)
    if not card.get("found"):
        raise _Unreadable(f"{card.get('reason', 'the transaction is not in the snapshot')} {card.get('command', '')} fetches it".strip())
    return card


@_guarded("stores-tried-read")
def stores_tried_read(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """Every store on disk was searched by the transaction's amount: each store's result, and the candidates (leads). It passes
    when the search ran; a store that could not be read is named as not read, and the others still show."""
    from jason.tasks import bill_dry_run

    card = _card(readers, view, item)
    stores = [t for t in card.get("tried") or [] if t.get("source") not in ("the profile's payee rows", "the county's or a vendor's own site")]
    unread = [t["source"] for t in stores if t.get("result") == "not read"]
    candidates = card.get("candidates") or []
    exact = sum(1 for c in candidates if c.get("confidence") == "exact")
    said = (f"{len(stores) - len(unread)} of {len(stores)} stores read"
            + (f"; not read: {', '.join(unread)}" if unread else "")
            + f"; {len(candidates)} candidate(s), {exact} exact (a lead until a person attaches it)")
    return CheckResult(True, readers.evidence_entries((_address(bill_dry_run.SNAPSHOT),)), said)


@_guarded("bill-mail-arrived")
def bill_mail_arrived(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """A scanned letter or a vendor portal's record now names the transaction's amount (a lead; the bill is a person's to confirm)."""
    card = _card(readers, view, item)
    found = [c for c in card.get("candidates") or [] if c.get("kind") in ("mail-scan", "portal-invoice") and c.get("evidence") == "document"]
    if not found:
        return CheckResult(False, (), "no scanned letter or vendor portal record names this amount yet")
    exact = sum(1 for c in found if c.get("confidence") == "exact")
    kinds = sorted({"a scanned letter" if c["kind"] == "mail-scan" else "a vendor portal record" for c in found})
    return CheckResult(True, (), f"{len(found)} candidate(s) name this amount ({' and '.join(kinds)}), {exact} with a date in the window; "
                                 "a lead until a person attaches it")


# --- monthly-review -------------------------------------------------------------------------------------------------

@_guarded("review-reconciliations")
def reconciliations_read(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """Each bank account has a completed reconciliation through the month, with no month skipped. Open items are counted."""
    from jason.tasks import reconciliations

    month = _month_of(view)
    if not month:
        return CheckResult(False, (), "the run names no month, so the reconciliations cannot be read against one")
    result = reconciliations.review(readers.data_dir, today=readers.today)
    if not result.get("found"):
        return CheckResult(False, (), str(result.get("note") or "no reconciliations on disk; jason reconcile --fetch reads them"))
    accounts = result.get("accounts") or []
    if item.strip():
        accounts = [a for a in accounts if str(a.get("account", "")).casefold() == item.strip().casefold()]
        if not accounts:
            return CheckResult(False, (), f"no reconciliation is on file for the account {item.strip()}")
    if not accounts:
        return CheckResult(False, (), "the reconciliations store holds no account")
    short = [a["account"] for a in accounts if str(a.get("latest") or "")[:7] < month]
    gaps = [f"{a['account']} ({', '.join(a['gaps'])})" for a in accounts if a.get("gaps")]
    items = sum(len(a.get("openItems") or []) for a in accounts)
    stale = sum(len(a.get("staleOpenItems") or []) for a in accounts)
    payments = sum(int(a.get("openPaymentsCents") or 0) for a in accounts)
    deposits = sum(int(a.get("openDepositsCents") or 0) for a in accounts)
    tail = (f"; {items} open item(s) ({stale} past {reconciliations.STALE_DAYS} days): {payments} cents of payments, {deposits} cents of "
            "deposits (whether it is current is the reviewer's judgment)")
    evidence = readers.evidence_entries((_address(Path("payhoa") / reconciliations.FILE),))
    if short or gaps:
        why = []
        if short:
            why.append(f"not reconciled through {month}: {_more(short)}")
        if gaps:
            why.append(f"a month skipped: {_more(gaps)}")
        return CheckResult(False, evidence, "; ".join(why) + tail)
    return CheckResult(True, evidence, f"{len(accounts)} account(s) reconciled through {month}, no month skipped" + tail)


@_guarded("review-budget")
def budget_read(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """The finance snapshot covers the month's year through the month, and says how many categories are off budget year to date."""
    from jason.tasks import finance

    month = _month_of(view)
    if not month:
        return CheckResult(False, (), "the run names no month, so the budget snapshot cannot be read against one")
    year, number = int(month[:4]), int(month[5:])
    snap = finance.load(readers.data_dir, year)
    if snap is None:
        return CheckResult(False, (), f"no finance snapshot for {year}; jason budget reads it")
    evidence = readers.evidence_entries((_address(Path(finance.FINANCE_DIR) / f"finance-{year}.json"),))
    through = snap.get("throughMonth")
    expense = finance.variances(snap, "expense", top=10_000)
    revenue = finance.variances(snap, "revenue", top=10_000)
    over = [r for r in expense if r["gap"] > 0]
    under = [r for r in revenue if r["gap"] < 0]
    biggest = max(over, key=lambda r: r["gap"], default=None)
    said = (f"{len(expense)} expense and {len(revenue)} revenue categories year to date through month {through}: "
            f"{len(over)} expense categories over budget" + (f" (the furthest, {biggest['category']}, by {biggest['gap']} cents)" if biggest else "")
            + f", {len(under)} revenue categories under budget (CIV 5500(c); the reading is the reviewer's)")
    if not isinstance(through, int) or through < number:
        return CheckResult(False, evidence, f"the {year} snapshot ({str(snap.get('syncedAt') or '')[:10] or 'no date'}) runs through month "
                                            f"{through}, not {number}; jason budget refreshes it. " + said)
    return CheckResult(True, evidence, said)


# --- fiscal-year ----------------------------------------------------------------------------------------------------

@_guarded("reserve-study-due")
def reserve_study_due(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """The latest study's date, and whether a site visit or the annual review falls due by the run's fiscal year (CIV 5550(a))."""
    from jason.tasks import reserves

    studies = reserves.load_studies(readers.data_dir)
    if not studies:
        return CheckResult(False, (), "no reserve study on disk; jason library --fetch, or a PDF under data/reserve-studies")
    schedule = reserves.site_visit_due(studies)
    year = _year_of(view, readers)
    visit, review = schedule.get("nextSiteVisitForFiscalYear"), schedule.get("nextReviewForFiscalYear")
    last = schedule.get("lastSiteVisitStudy")
    parts = [f"the last study with a site visit is dated {last}" if last else "no study with a site visit is on file, so the visit's date cannot be computed",
             f"the next site visit is for fiscal year {visit}" if visit else "", f"the next review is for fiscal year {review}" if review else ""]
    said = "; ".join(p for p in parts if p) + (" (applies only when the components' value reaches the statute's threshold; a person answers that)")
    visit_due = visit is not None and visit <= year
    review_due = review is not None and review <= year
    if not visit_due and not review_due:
        return CheckResult(False, (), f"nothing falls due by fiscal year {year}: " + said)
    due = " and ".join(w for w, on in (("the site visit", visit_due), ("the annual review", review_due)) if on)
    return CheckResult(True, (), f"{due} {'fall' if visit_due and review_due else 'falls'} due by fiscal year {year}: " + said)


# --- insurance-renewal ----------------------------------------------------------------------------------------------

@_guarded("insurance-due")
def insurance_due(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """A policy's term end, the days left, whether that is inside the renewal window, and the review's standing. It passes
    when a term end is read: a renewal run may start earlier than the window, so the window is said and never a gate."""
    from jason.tasks import insurance

    review = insurance.review(readers.data_dir, readers.community, today=readers.today)
    policies = [p for p in review.get("policies") or []]
    if not policies:
        return CheckResult(False, (), "the profile's policy sheet lists no policy")
    key = item.strip() or str(getattr(view, "subject", "") or "").split(":", 1)[-1].strip()
    named = [p for p in policies if key and insurance.fold_number(str(p.get("number") or "")) == insurance.fold_number(key)]
    rows = []
    for p in named or policies:
        try:
            days = (date.fromisoformat(str(p.get("termEnd"))[:10]) - readers.today).days
        except ValueError:
            continue
        rows.append((days, p))
    if not rows:
        return CheckResult(False, (), "no policy on the sheet has a term end")
    rows.sort(key=lambda r: r[0])
    days, soonest = rows[0]
    scope = "the named policy" if named else f"{len(rows)} policies"
    where = ("inside" if days <= RENEWAL_WINDOW_DAYS else "outside") + f" the {RENEWAL_WINDOW_DAYS}-day renewal window (proposed policy)"
    when_ = f"in {days} days" if days >= 0 else f"{-days} days ago"
    return CheckResult(True, (), f"{scope}: the soonest term ends {when_}, {where}; {soonest.get('kind', 'a policy')}: {soonest.get('standing', '')}")


# --- county-tax-cycle -----------------------------------------------------------------------------------------------

def _tax_bills(readers: StoreReaders, columns: str) -> list[sqlite3.Row]:
    path = readers.data_dir / "tax.db"
    if not path.is_file():
        raise _Unreadable("no tax catalog on disk; jason sync-tax reads it")
    conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(f"SELECT {columns} FROM bills ORDER BY apn, year, number").fetchall()
    except sqlite3.OperationalError as exc:
        raise _Unreadable(f"the tax catalog has no readable bills table ({exc}); jason sync-tax fills it") from exc
    finally:
        conn.close()


@_guarded("tax-standing")
def tax_standing_read(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """Each parcel's tax standing from its stored bills: unpaid newest year, delinquent older years, years with no bill. It passes
    when the bills are read and says what it found: an older year unpaid must not block the step that pays it."""
    from jason.community.standing import tax_standing
    from jason.community.tax import TaxBill

    rows = _tax_bills(readers, "apn, number, year, total_cents, balance_cents")
    wanted = _digits(item)
    by_parcel: dict[str, list[TaxBill]] = {}
    for r in rows:
        if wanted and _digits(r["apn"]) != wanted:
            continue
        by_parcel.setdefault(str(r["apn"]), []).append(TaxBill(number=str(r["number"]), name="", year=r["year"],
                                                              total_cents=r["total_cents"], balance_cents=r["balance_cents"]))
    if not by_parcel:
        return CheckResult(False, (), f"no stored bill for the parcel ending {_last4(item)}" if wanted else "the tax catalog holds no bill; jason sync-tax reads it")
    standings = {apn: tax_standing(bills) for apn, bills in by_parcel.items()}
    tally: dict[str, int] = {}
    for s in standings.values():
        tally[s.status] = tally.get(s.status, 0) + 1
    bad = [f"ending {_last4(apn)} ({s.oldest_delinquent})" for apn, s in standings.items() if s.delinquent]
    said = f"{len(standings)} parcel(s) read: " + ", ".join(f"{n} {status}" for status, n in sorted(tally.items()))
    gap = [f"ending {_last4(apn)}" for apn, s in standings.items() if s.missing_years]
    if gap:
        said += f"; years with no bill on file: {_more(gap)}"
    said += "; the newest year unpaid is due, never delinquent, until a bill date is entered"
    if bad:
        said = f"older years are still unpaid on {_more(bad)} (the oldest year in parentheses); " + said
    return CheckResult(True, (), said)


@_guarded("tax-bill-files")
def tax_bill_files(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """Every stored bill of the run's tax year (else the newest year in the catalog) has its PDF under the data folder."""
    rows = _tax_bills(readers, "apn, number, year, pdf_path")
    wanted = _digits(item)
    rows = [r for r in rows if not wanted or _digits(r["apn"]) == wanted or str(r["number"]) == item.strip()]
    if not rows:
        return CheckResult(False, (), f"no stored bill matches {_last4(item)}" if wanted else "the tax catalog holds no bill; jason sync-tax reads it")
    year = _year_of(view, readers, default=False)
    if year is None:
        year = max((r["year"] for r in rows if r["year"] is not None), default=None)
    mine = [r for r in rows if r["year"] == year]
    if not mine:
        return CheckResult(False, (), f"the catalog holds no bill for tax year {year}")
    have, missing = [], []
    for r in mine:
        address = _address(r["pdf_path"]) if r["pdf_path"] else ""
        (have if address and readers.evidence(address) else missing).append((r, address))
    evidence = readers.evidence_entries(a for _r, a in have)
    said = f"{len(have)} of {len(mine)} bill(s) of tax year {year} have a file under the data folder"
    if missing:
        names = [f"ending {_last4(r['apn'])} bill {r['number']}" for r, _a in missing]
        return CheckResult(False, evidence, said + f"; no file for {_more(names)}; jason county-tax --import-bill saves one")
    return CheckResult(True, evidence, said)


# === round two: the reads the page's remaining check rows wanted ===========================================================

def _day(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value or "")[:10])
    except ValueError:
        return None


def _month_bounds(month: str) -> tuple[date, date]:
    import calendar

    year, number = int(month[:4]), int(month[5:])
    return date(year, number, 1), date(year, number, calendar.monthrange(year, number)[1])


def _ledger_month(readers: StoreReaders, view: RunView) -> tuple[str, date, date, list[Any], dict[str, Any]]:
    """(the month, its first and last day, the stored ledger's entries, the month's row in the store): the ledger read for a
    month that is over, else the reason it cannot be read."""
    from jason.tasks import books

    month = _month_of(view)
    if not month:
        raise _Unreadable("the run names no month, so the ledger cannot be read for one")
    items = books.load(readers.data_dir)
    if not items:
        raise _Unreadable("no ledger on disk; jason books --sync reads it")
    stored = {m["month"]: dict(m) for m in books.stored_months(readers.data_dir)}
    if month not in stored:
        raise _Unreadable(f"the stored ledger holds no rows of {month}; jason books --sync reads it")
    first, last = _month_bounds(month)
    fetched = _day(stored[month].get("fetched_at"))
    if fetched is None or fetched <= last:
        raise _Unreadable(f"the ledger's rows of {month} were read {fetched or 'at no recorded time'}, before the month ended; "
                          "jason books --sync reads it again")
    if not int(stored[month].get("rows") or 0):
        raise _Unreadable(f"the stored ledger holds no row of {month}")
    return month, first, last, items, stored[month]


def _ledger_evidence(readers: StoreReaders) -> tuple[str, ...]:
    from jason.tasks import books

    return readers.evidence_entries((_address(Path("payhoa") / books.STORE),))


# --- monthly-review: statements, income and expense, registers -----------------------------------------------------------

@_guarded("review-statements")
def statements_read(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """The library holds a bank statement of the month for each bank account the profile names (CIV 5500(d)). An account is
    matched by the last four digits its statement files carry; a message names an account by its label and never by a number.
    The statement is counted, never described: a bank statement is a confidential file."""
    from jason.tasks import library

    month = _month_of(view)
    if not month:
        return CheckResult(False, (), "the run names no month, so the statements cannot be looked for")
    accounts = list(readers.community.bank_accounts())
    if not accounts:
        return CheckResult(False, (), "the profile names no bank account, so no statement can be paired with one")
    if item.strip():
        wanted = item.strip().casefold()
        accounts = [a for a in accounts if wanted in {str(a.label).casefold(), a.purpose.value.casefold(), str(a.suffix)}]
        if not accounts:
            return CheckResult(False, (), "the profile names no bank account for that item")
    stored = library.load(readers.data_dir)
    if not stored:
        return CheckResult(False, (), "no library on disk; jason library reads it")
    rows = [r for r in library.distinct(stored) if r.get("kind") == "bank_statement" and str(r.get("period") or "").startswith(month)]
    have, missing = [], []
    for account in accounts:
        suffix = str(account.suffix or "")
        found = [r for r in rows if suffix and suffix in f"{r.get('name', '')} {r.get('path', '')}"]
        (have if found else missing).append(account.label or account.purpose.value)
    evidence = readers.evidence_entries((_address(library.STORE),))
    said = (f"{len(have)} of {len(accounts)} bank account(s) have a statement of {month} in the library "
            f"({len(rows)} statement file(s) of the month in all)")
    if missing:
        return CheckResult(False, evidence, said + f"; none filed for {_more(missing)} (a person files it, jason library reads it)")
    return CheckResult(True, evidence, said)


@_guarded("review-income-expense")
def income_expense_read(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """The stored ledger can state the month's income and expense (CIV 5500(e)): the category counts and the totals, in cents,
    from the ledger read after the month ended. Whether the statement is right is the reviewer's."""
    from jason.community import ledger

    month, first, last, items, _row = _ledger_month(readers, view)
    pl = ledger.profit_and_loss(items, first, last)
    if not pl["income"] and not pl["expense"]:
        return CheckResult(False, _ledger_evidence(readers), f"the ledger has no income or expense entry in {month}")
    moved = ledger.cash_flow(items, first, last)
    return CheckResult(True, _ledger_evidence(readers),
                       f"the ledger states {month}: {len(pl['income'])} income categories, {pl['incomeCents']} cents; "
                       f"{len(pl['expense'])} expense categories, {pl['expenseCents']} cents; net {pl['netCents']} cents; "
                       f"{len(moved)} bank account(s) moved money (the statement is the books' reading; whether it is right "
                       "is the reviewer's judgment)")


@_guarded("review-registers")
def registers_read(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """The three reports CIV 5500(f) names can be drawn from the stored ledger for the month: the general ledger (its rows), the
    check register (the money out of the bank accounts), and the delinquent assessment receivable report (units owing and the
    total, without names). Counts and cents only."""
    from jason.community import ledger

    month, first, last, items, row = _ledger_month(readers, view)
    paid = [e for e in items if e.type == ledger.BANK and not e.starting and first <= e.day <= last and e.credit]
    owed = ledger.receivables(items, last)
    return CheckResult(True, _ledger_evidence(readers),
                       f"{month}: the general ledger holds {int(row.get('rows') or 0)} row(s); the register shows {len(paid)} "
                       f"payment(s) out, {sum(e.credit for e in paid)} cents; {owed['unitsOwing']} unit(s) owe {owed['owedCents']} "
                       "cents at the month's end (whether they are right is the reviewer's)")


# --- fiscal-year: the window, the reserve, the budget, the disclosures ------------------------------------------------------

@_guarded("fiscal-window")
def fiscal_window(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """The window for the annual budget report and the annual policy statement (CIV 5300(a), 5310(a)), from the notice catalog
    and the fiscal year's end; and, when the dated day is on record, that it falls inside. A date that is not on record is a
    state, said as it is, never a guess."""
    from jason.community import notice_catalog
    from jason.community.notices import Anchor

    end = _day(_dates(view).get("fiscal_year_end"))
    if end is None:
        return CheckResult(False, (), "the fiscal year's end is not on record: a date not on record is a question for the manager, never a guess")
    windows = {}
    for key in ("annual-budget-report", "annual-policy-statement"):
        row = notice_catalog.requirement(key)
        found = [t.window(end) for t in row.timing if t.anchor is Anchor.FISCAL_YEAR_END]
        if not found:
            return CheckResult(False, (), f"the notice catalog gives {row.statute} no window from the fiscal year's end")
        windows[key] = found[0]
    first, last = windows["annual-budget-report"]
    other = windows["annual-policy-statement"]
    said = (f"the window for the fiscal year ending {end.isoformat()} runs {first} to {last} (CIV 5300"
            + (", 5310 the same)" if other == (first, last) else f"; the policy statement's differs: {other[0]} to {other[1]})"))
    dated = _day(_dates(view).get("dated_day"))
    if dated is None:
        return CheckResult(False, (), said + "; the dated day is not on record yet (date not on record)")
    if (first is not None and dated < first) or (last is not None and dated > last):
        return CheckResult(False, (), said + f"; the dated day {dated.isoformat()} is outside it")
    return CheckResult(True, (), said + f"; the dated day {dated.isoformat()} is inside it")


def _plan_row(readers: StoreReaders, year: int) -> tuple[Any, Any]:
    from jason.tasks import reserves

    studies = reserves.load_studies(readers.data_dir)
    if not studies:
        raise _Unreadable("no reserve study on disk; jason library --fetch, or a PDF under data/reserve-studies")
    latest = reserves.latest_study(studies)
    row = latest.year(year)
    if row is None:
        raise _Unreadable(f"the latest study (fiscal year {latest.fiscal_year}) has no plan row for {year}")
    return latest, row


@_guarded("reserve-plan-match")
def reserve_plan_match(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """The budget's transfer to reserves for the fiscal year against the latest study's contribution for the year (within one
    dollar, as the reserve brief reads it). The study's plan is a reading; the board adopts the funding plan."""
    from jason.tasks import finance, reserves

    year = _year_of(view, readers)
    latest, row = _plan_row(readers, year)
    snap = finance.load(readers.data_dir, year)
    if snap is None:
        return CheckResult(False, (), f"no finance snapshot for {year}; jason budget reads it")
    evidence = readers.evidence_entries((_address(Path(finance.FINANCE_DIR) / f"finance-{year}.json"),))
    line = next((i for i in (snap.get("expense") or {}).get("items", []) if str(i.get("name")) == reserves.TRANSFER_LINE), None)
    if line is None or line.get("expected") is None:
        return CheckResult(False, evidence, f"the {year} budget has no '{reserves.TRANSFER_LINE}' line")
    budget, plan = int(line["expected"]), int(row.contribution_cents)
    gap = budget - plan
    said = (f"the {year} budget transfers {budget} cents to reserves; the study of fiscal year {latest.fiscal_year} plans {plan} cents "
            "(the plan the board adopted is the board's to name)")
    if abs(gap) > 100:
        return CheckResult(False, evidence, said + f"; they differ by {gap} cents")
    return CheckResult(True, evidence, said + ("; they agree" if not gap else f"; they differ by {gap} cents, inside a dollar"))


@_guarded("disclosure-reserve-summary")
def reserve_summary(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """The latest study carries the figures the reserve summary needs for the fiscal year (CIV 5300(b)(2), 5565, 5570): the
    contribution, the projected and the fully funded balances, and the percent funded. The summary counts cash and cash
    equivalents only; the treasurer confirms that against the bank."""
    year = _year_of(view, readers)
    latest, row = _plan_row(readers, year)
    current = getattr(getattr(latest, "disclosure", None), "current_balance_cents", None)
    said = (f"the study of fiscal year {latest.fiscal_year} gives {year}: contribution {row.contribution_cents} cents, projected end "
            f"{row.ending_balance_cents} cents, fully funded {row.fully_funded_cents} cents, {row.percent_funded} percent funded"
            + (f"; its disclosure summary's current balance is {current} cents" if current is not None else "")
            + " (cash and cash equivalents only is the treasurer's to confirm against the bank)")
    return CheckResult(True, (), said)


def _policy_report(readers: StoreReaders) -> tuple[dict[str, Any], tuple[str, ...]]:
    from jason.tasks import policies

    report = policies.load(readers.data_dir)
    if not report.get("found"):
        raise _Unreadable("no policy report on disk; jason policies --fetch builds it")
    return report, readers.evidence_entries((_address(Path("reports") / policies.REPORT),))


def _numbers(policy: dict[str, Any]) -> set[str]:
    from jason.tasks import insurance

    return {insurance.fold_number(str(n)) for n in (policy.get("number"), *(policy.get("priorNumbers") or ())) if n}


def _policy_key(view: RunView, item: str) -> str:
    from jason.tasks import insurance

    key = item.strip() or str(getattr(view, "subject", "") or "").split(":", 1)[-1].strip()
    return insurance.fold_number(key) if key else ""


def _scoped(report: dict[str, Any], view: RunView, item: str) -> tuple[list[dict[str, Any]], bool]:
    """(the report's policies the run is about, whether it named one): the policy the item or the subject names, else all."""
    fold = _policy_key(view, item)
    named = [p for p in report.get("policies") or [] if fold and fold in _numbers(p)]
    return (named, True) if named else (list(report.get("policies") or []), False)


def _summary(readers: StoreReaders, rows: list[dict[str, Any]], year: int, scope: str, evidence: tuple[str, ...]) -> CheckResult:
    from jason.tasks import packets

    if not rows:
        return CheckResult(False, evidence, "the policy report lists no policy")
    not_carried = tuple(getattr(readers.community, "coverages_not_carried", lambda: ())() or ())
    table, gaps = packets.insurance_rows(rows, year, not_carried=not_carried)
    said = f"{scope}: {len(table)} summary row(s) for fiscal year {year} from {len(rows)} policy(ies)"
    if gaps or not table:
        return CheckResult(False, evidence, said + f"; {len(gaps)} gap(s): "
                           + (_more(gaps) if gaps else "no policy has a term in force on the first day of the year"))
    return CheckResult(True, evidence, said + ", each with a term in force on the first day of the year (CIV 5300(b)(9))")


@_guarded("disclosure-insurance-summary")
def insurance_summary_for_disclosures(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """The insurance summary of the annual budget report: every policy has a term in force on the first day of the fiscal year,
    so ``insurance_rows`` has no gap (CIV 5300(b)(9))."""
    report, evidence = _policy_report(readers)
    return _summary(readers, list(report.get("policies") or []), _year_of(view, readers), "all policies", evidence)


@_guarded("insurance-summary")
def insurance_summary_for_policy(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """The run's policy has its row in the insurance summary for the fiscal year of the new term (CIV 5300(b)(9)): the year of
    the term's end date when the run has one, else the reader's year."""
    report, evidence = _policy_report(readers)
    rows, named = _scoped(report, view, item)
    day = _day(_dates(view).get("term_end"))
    return _summary(readers, rows, day.year if day else readers.today.year, "the named policy" if named else "all policies", evidence)


@_guarded("insurance-limits")
def insurance_limits(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """The policy report's findings against the required coverages and limits (CIV 5800, 5805, 5806), counted by severity. It
    passes when every policy in scope has its declarations read, so the limits could be weighed; a finding is information for
    the board's decision and never blocks it (a shortfall is what the board decides on). A finding is a reading of the
    declarations; the declarations govern."""
    report, evidence = _policy_report(readers)
    rows, named = _scoped(report, view, item)
    if not rows:
        return CheckResult(False, evidence, "the policy report lists no policy")
    tally = {"problem": 0, "check": 0, "info": 0}
    undeclared = 0
    for p in rows:
        for f in p.get("findings") or []:
            if any(str(f.get("authority") or "").startswith(c) for c in ("CIV 5800", "CIV 5805", "CIV 5806")):
                severity = str(f.get("severity") or "check")
                tally[severity if severity in tally else "check"] += 1
            if f.get("code") == "no-declarations":
                undeclared += 1
    scope = "the named policy" if named else f"{len(rows)} policy(ies)"
    said = (f"{scope}: {sum(tally.values())} finding(s) against the CIV 5800, 5805 and 5806 limits ({tally['problem']} problem, "
            f"{tally['check']} to look at, {tally['info']} for information); {undeclared} without declarations read "
            "(a finding is a reading of the declarations, which govern; the board weighs it before it decides)")
    return CheckResult(not undeclared, evidence, said)


def _insurance_read(readers: StoreReaders, view: RunView, item: str) -> tuple[str, str, tuple[str, ...]]:
    """(the suggested path, what was found, the evidence): ``changed`` when the board's recorded decision says a member notice
    is needed (a lapse, or a change in limits) or the declarations show a change the statute names (CIV 5810: a lapse not
    replaced, a reduced limit, a higher deductible); ``unchanged`` otherwise. The path is "" (no suggestion) when no decision
    is on record for the policy or the stores cannot be read: the read never raises and never guesses."""
    from jason.tasks import insurance_notice, insurance_renewals
    from jason.tasks.insurance import fold_number

    try:
        fold = _policy_key(view, item)
        stored = next((d for n, d in insurance_renewals.load(readers.data_dir).items() if fold and fold_number(str(n)) == fold), None)
        evidence = readers.evidence_entries((_address(insurance_renewals.STORE),))
        if stored is None:
            return "", "no renewal decision is recorded for the policy: the board's decision comes first", evidence
        significant, seen = 0, "the declarations were not read"
        try:
            report, more = _policy_report(readers)
            evidence += more
            mine = [p for p in report.get("policies") or [] if fold in _numbers(p)]
            if mine:
                changes, gaps = insurance_notice.policy_changes(mine, _day(_dates(view).get("term_end")) or readers.today)
                significant = sum(1 for c in changes if c.kind.significant)
                seen = (f"the declarations show {len(changes)} change(s), {significant} the statute names"
                        + (f", {len(gaps)} gap(s)" if gaps else ""))
        except _Unreadable:
            pass
        notice = bool(stored.get("memberNoticeNeeded"))
        changed = notice or significant > 0
        said = (f"the board's decision is recorded ({stored.get('decision', '')}); memberNoticeNeeded is {'yes' if notice else 'no'}; "
                f"{seen} (CIV 5810): coverage {'changed' if changed else 'is unchanged'}")
        return ("changed" if changed else "unchanged"), said, evidence
    except Exception as exc:  # noqa: BLE001 - a store that cannot be read leaves the person without a suggestion, never with a guess
        return "", f"the renewal decision cannot be read ({type(exc).__name__})", ()


@_guarded("insurance-changed")
def insurance_changed(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """A suggestion for the person who answers 'did coverage change or lapse' (CIV 5810). It does not decide the branch: the
    answer is the manager's (the board's matter), and the read's ``choice`` is the default shown beside the question. It passes
    when the read was made; with no decision on record, or no store it can read, it passes with no ``choice`` and says why, so
    the manager answers by hand. A person who answers differently is recorded as having answered over this read
    (``insurance-answer``)."""
    path, said, evidence = _insurance_read(readers, view, item)
    if not path:
        return CheckResult(True, evidence, f"no suggestion: {said}; the manager answers by hand")
    return CheckResult(True, evidence, f"suggested {path}: {said}. A suggestion only: the manager answers, and may answer differently.",
                       choice=path)


@_guarded("insurance-answer")
def insurance_answer(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """Whether the manager's answer to 'did coverage change or lapse' agrees with the read's suggestion, said plainly in the
    run's record: it agrees; it was given with no suggestion to compare; or the person answered over the read, with the
    suggestion and whether a record or reason came with the answer. It passes once an answer is on record and never judges
    it: the answer is the person's."""
    from jason.workflows.defs import money

    step = getattr(view, "step", None)
    asked = step(money.step_id(money.IR, "chg")) if callable(step) else None
    read = step(money.step_id(money.IR, "read")) if callable(step) else None
    if asked is None or read is None:
        return CheckResult(False, (), "this run is not an insurance renewal: it has no step for the answer and the read")
    answer = asked.choice
    if not answer:
        return CheckResult(False, (), "no answer to 'did coverage change or lapse' is recorded yet")
    suggested = read.choice
    if not suggested:
        why = str(read.detail.get("message") or "the read made no suggestion")
        return CheckResult(True, (), f"the answer {answer} was given by hand; the read made no suggestion to compare ({why})")
    if suggested == answer:
        return CheckResult(True, (), f"the answer {answer} agrees with the read's suggestion")
    reason = ("a record came with it" if str(asked.record or "").strip() else "no record or reason came with it")
    return CheckResult(True, (), f"the person overrode the read: answered {answer} where the read suggested {suggested} ({reason}); "
                       "the answer stands as the person's")


# --- the disclosures' delivery -----------------------------------------------------------------------------------------------

@_guarded("disclosure-delivery-read")
def disclosure_delivery_read(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """The notice ledger holds the send of the annual budget report (``annual-budget-report-YEAR``) and no attempt is still
    pending: the bounces, returns, and failures are counted. It passes when the delivery was read; a bounce is a follow-up for
    a person (CIV 4041(e)), not a failure of the read. Counts only: no member, unit, or address."""
    year = _year_of(view, readers)
    notice = item.strip() or f"annual-budget-report-{year}"
    path = readers.data_dir / "notices" / "deliveries.db"
    if not path.is_file():
        return CheckResult(False, (), "none on record: the notice ledger is not on disk; jason notices KEY --sync reads the delivery")
    conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        rows = conn.execute("SELECT status, COUNT(*) FROM attempts WHERE notice = ? GROUP BY status", (notice,)).fetchall()
    except sqlite3.OperationalError as exc:
        raise _Unreadable(f"the notice ledger has no readable attempts table ({exc})") from exc
    finally:
        conn.close()
    evidence = readers.evidence_entries((_address(Path("notices") / "deliveries.db"),))
    if not rows:
        return CheckResult(False, evidence, f"none on record: the ledger holds no attempt for {notice}; jason notices {notice} --sync reads the delivery")
    by = {str(status): int(n) for status, n in rows}
    said = (f"{sum(by.values())} attempt(s) for {notice}: "
            + ", ".join(f"{n} {status}" for status, n in sorted(by.items(), key=lambda kv: (-kv[1], kv[0]))))
    if by.get("pending"):
        return CheckResult(False, evidence, said + f"; {by['pending']} still pending: the delivery is read again after 24 hours")
    follow = sum(by.get(s, 0) for s in ("bounced", "returned", "failed", "unknown", "skipped"))
    return CheckResult(True, evidence, said + f"; {follow} need a follow-up (a bounce, a return, a failure, or no email on file)")


# --- reserve-borrowing ---------------------------------------------------------------------------------------------------------

def _loan(readers: StoreReaders, view: RunView, item: str) -> dict[str, Any]:
    """The borrowing the run is about, from the reserve transfers' review: the day of the initial transfer (the run's date, else
    the day in its subject) and, when several share it, the ledger number the subject ends with."""
    from jason.tasks import reserve_transfers

    text = f"{item} {getattr(view, 'subject', '')}".strip()
    found = _day(_dates(view).get("transfer_on")) or _day(next(iter(re.findall(r"\d{4}-\d{2}-\d{2}", text)), ""))
    if found is None:
        raise _Unreadable("the run names no day for the initial transfer")
    review = reserve_transfers.review(readers.data_dir, readers.community, today=readers.today)
    if not review.get("found"):
        raise _Unreadable(str(review.get("note") or "the reserve transfers cannot be read"))
    mine = [r for r in review.get("borrowings") or [] if r.get("day") == found.isoformat()]
    number = re.search(r"\d{4}-\d{2}-\d{2}\D*(\d+)\s*$", text)
    if len(mine) > 1 and number:
        mine = [r for r in mine if str(r.get("number")) == number.group(1)] or mine
    if not mine:
        raise _Unreadable(f"no borrowing of {found.isoformat()} among the {len(review.get('borrowings') or [])} the ledger shows")
    return mine[0]


@_guarded("reserve-notice")
def reserve_notice(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """An agenda in the library, within 60 days before the transfer, carries a 'Notice of Intent to Borrow' item (CIV 5515(a),
    4920). A document missing from the library may be in the board's files; the read says only what the library holds."""
    loan = _loan(readers, view, item)
    documents = loan.get("documents") or {}
    notice, minutes = documents.get("notice"), documents.get("minutes")
    if not notice:
        return CheckResult(False, (), "no agenda in the library gives notice of intent to borrow within 60 days before the transfer "
                                      "(the board's files may hold one that is not in PayHOA's library yet)")
    more = (("; minutes of that meeting are in the library" + (" (a draft only)" if minutes.get("draft") else ""))
            if minutes else "; no minutes of that meeting are in the library yet")
    return CheckResult(True, (), f"the agenda of the meeting of {notice.get('meeting')} carries the notice of intent to borrow{more}")


@_guarded("reserve-restored")
def reserve_restored(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """A transfer back to the reserve restores the borrowing, found by amount: a lead, because the board's resolution says which
    loan a payment restored (CIV 5515(d)). It says whether the restoration came inside the year."""
    loan = _loan(readers, view, item)
    cents, back = int(loan.get("cents") or 0), int(loan.get("repaidCents") or 0)
    if int(loan.get("outstandingCents") or 0) > 0:
        return CheckResult(False, (), f"{back} of {cents} cents are restored; {loan['outstandingCents']} cents are not, "
                                      f"and the year ends {loan.get('deadline')}")
    when = "inside" if str(loan.get("repaidOn") or "") <= str(loan.get("deadline") or "") else "after"
    return CheckResult(True, (), f"{back} cents were restored by {loan.get('repaidOn')}, {when} the year that ended {loan.get('deadline')} "
                                 "(found by amount: a lead until the resolution confirms which loan it restored)")


# --- county-tax-cycle -------------------------------------------------------------------------------------------------------------

@_guarded("tax-years-closed")
def tax_years_closed(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """Every stored bill of the tax year (the run's, else the newest in the catalog) has a balance of zero. It passes only when
    each parcel's bills are paid; a parcel is named by its last four characters and a balance is in cents."""
    rows = _tax_bills(readers, "apn, number, year, balance_cents")
    wanted = _digits(item)
    rows = [r for r in rows if not wanted or _digits(r["apn"]) == wanted]
    if not rows:
        return CheckResult(False, (), "the tax catalog holds no bill for that parcel" if wanted
                           else "the tax catalog holds no bill; jason sync-tax reads it")
    year = _year_of(view, readers, default=False)
    if year is None:
        year = max((r["year"] for r in rows if r["year"] is not None), default=None)
    mine = [r for r in rows if r["year"] == year]
    if not mine:
        return CheckResult(False, (), f"the catalog holds no bill for tax year {year}")
    unpaid = [r for r in mine if r["balance_cents"] is None or int(r["balance_cents"]) != 0]
    parcels, owing = {str(r["apn"]) for r in mine}, {str(r["apn"]) for r in unpaid}
    said = f"{len(parcels) - len(owing)} of {len(parcels)} parcel(s) have every bill of tax year {year} at a zero balance"
    if unpaid:
        cents = sum(int(r["balance_cents"] or 0) for r in unpaid)
        return CheckResult(False, (), said + f"; {len(unpaid)} bill(s) on {_more(f'ending {_last4(a)}' for a in sorted(owing))} "
                                             f"still show a balance, {cents} cents in all")
    return CheckResult(True, (), said)
