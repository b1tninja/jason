"""The money family's reads (docs/workflows/money.md, sections 2 and 7): twelve ``check`` names a money definition may use.

Each read is read-only. It looks at stores already on disk (the PayHOA snapshot, the dry run, the reconciliations, the
finance snapshot, the reserve studies, the insurance sheet, the tax catalog, the run store) and writes nothing, reaches no
network, and calls no PayHOA, Google, county portal, or Keeper. The tax catalog is opened read only (``mode=ro``), never
through ``TaxStore``, whose constructor creates tables. A store that is missing or cannot be read gives ``ok=False`` with
the reason; a read never raises and is never ``ok`` by default. Amounts are integer cents.

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
