"""The ``payhoa-mailroom-send`` kind: a saved Mailroom preview as a two-person plan, mailed only by a person at a terminal.

``jason mailroom --pdf FILE --units UNITS`` saves a preview record (``tasks.mailroom``): the letter's sha256, the
options, the units, the owners PayHOA names, the cost, and a fingerprint over all of them. This kind turns that record
into one plan item (the letter is one thing, not item by item): its fingerprint is the item's basis, the recipient count
and the cost are shown, and a second, distinct person signs before anything is mailed. A mailing cannot be recalled, so
the plan is read again live at every step that matters; a preview that no longer matches PayHOA (the file changed, a
unit or an owner moved, an address changed, the cost differs, or it is older than the limit) is an item nobody can
approve, and an approved plan whose letter changed is superseded (``engine.apply``), never mailed.

**Apply is terminal only.** The engine refuses this kind unless the caller is ``jason mailroom --send --yes --approval ID``
(``ActionKind.terminal_only``, ``Live.terminal``), so jason-web and ``jason approvals apply`` cannot mail it. The
applier checks again, and also that two distinct people signed this plan's fingerprint, before it calls
``tasks.mailroom.send`` with the fingerprint as ``expect``. The mailing is recorded through the engine's recorder and
logged in ``data/mailroom/sent.jsonl`` with the approval's id. Cancel is not a kind: it is a command with a logged line.

Scope: ``{"preview": ID}`` (a saved preview's id, a unique prefix, or the first characters of its fingerprint).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jason.approvals.engine import Live, Planned
from jason.approvals.model import Change, ChangeOp, Evidence, ItemClass, PlanItem, Result, item_id, same_person

KEY = "payhoa-mailroom-send"
OP = "mail letter"
# The delivery methods Civil Code 4040(a)(2) lists. The plan shows the mail class beside it; whether a given mailing is
# an individual delivery is the board's and counsel's to say (docs/console/screens/mailroom.md).
RULE = "CIV 4040(a)(2)"


@dataclass
class Context:
    """The planner's own, in memory, for the applier: the letter as it would go now, and the saved preview behind it."""
    prepared: Any
    facts: dict[str, Any]
    record: dict[str, Any]
    options: Any


def cents(value: int) -> str:
    return f"${int(value) // 100:,}.{int(value) % 100:02d}"


def _scope_preview(scope: dict[str, Any]) -> str:
    ref = str(scope.get("preview") or "").strip()
    if not ref:
        raise ValueError('scope names the saved preview: {"preview": ID} (jason mailroom --pdf FILE --units UNITS saves one)')
    return ref


def _describe_options(o: dict[str, Any]) -> str:
    return (f"{o.get('mailClass')}{', ' + o['tracking'] if o.get('tracking') else ''}, "
            f"{'color' if o.get('color') != 'bw' else 'black and white'}, "
            f"{'two-sided' if o.get('doubleSided') else 'one-sided'}")


def plan(live: Live, scope: dict[str, Any]) -> Planned:
    """Read the saved preview and PayHOA's recipients for it, and plan one item. Mails nothing, draws no proof."""
    from jason.tasks import mailroom

    ref = _scope_preview(scope)
    data_dir = Path(live.data_dir)
    record = mailroom.load_preview(data_dir, ref)
    read_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    facts, prepared = mailroom.live_facts(live.client, live.org_id, data_dir, record)
    stale = mailroom.stale_reasons(record, facts)
    return build(record, facts, prepared, stale, read_at=read_at)


def build(record: dict[str, Any], facts: dict[str, Any], prepared: Any, stale: list[str], *, read_at: str = "") -> Planned:
    """The plan, from the saved preview, the letter as it would go now, and why they differ (empty when they do not).
    Pure: reads nothing."""
    from jason.tasks import mailroom

    fp, saved_fp = facts["fingerprint"], record["fingerprint"]
    pdf, options = facts["pdf"], facts["options"]
    n, total, each = facts["lettersExpected"], facts["totalCents"], facts["printed"]["centsEach"]
    owners = len({r["ownerId"] for r in facts["recipients"] if r["isIncluded"] and r["ownerId"]})
    left_out = sum(1 for r in facts["recipients"] if not r["isIncluded"])
    klass = ItemClass.INFORMATIONAL if stale else ItemClass.APPROVABLE
    how = _describe_options(options)
    label = f"{pdf['name']}: {n} letters, {how}"
    why = (f"The saved preview {record['id']} no longer matches what would go ({'; '.join(stale)}). Nothing here can be "
           f"approved: read it again with jason mailroom --pdf FILE --units UNITS and plan from the new preview."
           if stale else
           f"{n} letters, {how}; {cents(each)} a letter, {cents(total)} in all by PayHOA's pricing guide, charged to the "
           f"association. The letter is {pdf['pages']} pages (PayHOA adds an address page); PayHOA names {owners} owners "
           f"for {len(facts['units'])} units. This mails real letters and a letter cannot be recalled. Fingerprint "
           f"{mailroom.shown(fp)}.")
    item = PlanItem(
        item_id(KEY, OP, f"preview:{record['id']}", pdf["name"]), OP, f"preview:{record['id']}", label,
        f"{n} letters, {cents(total)}", why, group=pdf["name"],
        change=Change(ChangeOp.SET, "mailing", "", "not mailed", f"{n} letters mailed, {cents(total)} charged"),
        rule=RULE, evidence=(Evidence("The saved preview", f"jason mailroom --preview {record['id']}"),),
        basis=fp, klass=klass, high_stakes=True, cost_cents=total)
    notes = ["A mailing cannot be recalled: PayHOA's cancel works only while a letter is still processing, a window of "
             "minutes. This plan is applied only by a person at a terminal: jason mailroom --send --yes --expect "
             f"{mailroom.shown(fp)} --approval ID.",
             "Billing is by printed page with PayHOA's address page counted; a sixth billed page adds $2.25 of postage "
             "a letter."]
    if options.get("mailClass") == "standard":
        notes.append(mailroom.STANDARD_NOTE)
    if record.get("notice"):
        notes.append(f"the letter is kept as the notice {record['notice']} when it is mailed")
    if left_out:
        notes.append(f"PayHOA leaves {left_out} recipient row(s) out of the mailing; jason mailed none of them and "
                     "cannot leave an included one out")
    notes += [f"no PayHOA unit matched '{m}'" for m in record.get("missing") or ()]
    notes += [f"stale: {s}" for s in stale]
    summary = {"preview": record["id"], "fingerprint": mailroom.shown(fp), "savedFingerprint": mailroom.shown(saved_fp),
               "pdf": pdf["name"], "pages": pdf["pages"], "billedPages": facts["printed"]["pages"],
               "sheets": facts["printed"]["sheets"], "heavy": facts["printed"]["heavy"], "units": len(facts["units"]),
               "recipients": n, "owners": owners, "leftOut": left_out, "mailClass": options["mailClass"],
               "tracking": options["tracking"], "color": options["color"], "doubleSided": options["doubleSided"],
               "sendTo": options["sendTo"], "withInvoices": options["withInvoices"], "centsEach": each,
               "totalCents": total, "notice": record.get("notice") or "", "stale": stale,
               "cost": f"{cents(total)}: {n} letters at {cents(each)} by the pricing guide; PayHOA charges the account"}
    return Planned([item], scope={"preview": record["id"]}, title=f"Mail {pdf['name']} to {n} recipients ({cents(total)})",
                   summary=summary,
                   evidence=(Evidence("The saved preview", f"jason mailroom --preview {record['id']}"),
                             Evidence("Civil Code 4040(a)(2)", RULE)),
                   cost_cents=total, notes=notes, context=Context(prepared, facts, record, options), read_at=read_at)


# --- apply --------------------------------------------------------------------------------------------------------------

def signed_by_two(a: Any) -> str:
    """Why this approval is not signed by two distinct people on its fingerprint ("" when it is)."""
    first, second = a.first, a.second
    if first is None or second is None:
        return "two signatures are needed and one is missing"
    if same_person(first.name, second.name):
        return f"{first.name} signed twice: a second, distinct person signs"
    if first.fingerprint != a.fingerprint or second.fingerprint != a.fingerprint:
        return "a signature is on a different plan than this one"
    return ""


def apply(live: Live, planned: Planned, items: list[PlanItem], recorder: Any) -> None:
    """Mail the approved letter, only for a person at a terminal, only when two distinct people signed this plan and the
    letter would go as the plan's basis says. Anything else is recorded as blocked and nothing is mailed."""
    from jason.tasks import mailroom

    ctx: Context = planned.context
    a = recorder.approval
    for item in items:
        if not live.terminal:
            recorder.done(item.id, Result.BLOCKED,
                          f"mailing is done by a person at a terminal: jason mailroom --send --yes --expect "
                          f"{mailroom.shown(item.basis)} --approval {a.id}")
            continue
        unsigned = signed_by_two(a)
        if unsigned:
            recorder.done(item.id, Result.BLOCKED, unsigned)
            continue
        approved = a.item(item.id)
        if approved.basis != item.basis or ctx.facts["fingerprint"] != approved.basis:
            recorder.done(item.id, Result.BLOCKED, "the letter would go differently than the plan the signers saw")
            continue
        o = ctx.options
        try:
            opts = mailroom.Options.from_dict(o)
            mailroom.check_options("first-class" if opts.first_class else "standard", tracking=opts.tracking,
                                   with_invoices=opts.with_invoices, double_sided=opts.double_sided)
            if not ctx.prepared.owner_ids:
                raise ValueError("PayHOA named no recipient for these units")
        except ValueError as exc:
            recorder.done(item.id, Result.BLOCKED, f"{exc}; nothing mailed")
            continue
        recorder.applying([item.id])
        try:
            sent = mailroom.send(live.client, live.org_id, Path(live.data_dir), ctx.prepared,
                                 double_sided=opts.double_sided, with_invoices=opts.with_invoices, color=opts.color,
                                 mail_class="first-class" if opts.first_class else "standard", tracking=opts.tracking,
                                 by=recorder.actor, expect=approved.basis, approval=a.id, preview_id=ctx.record["id"])
        except mailroom.FingerprintMismatch as exc:
            recorder.done(item.id, Result.BLOCKED, f"{exc}; nothing mailed")
            continue
        except Exception as exc:  # noqa: BLE001 - recorded on the item
            from payhoa.exceptions import PayhoaError

            # PayHOA answered with a refusal: nothing was mailed. Anything else may have gone out: look before sending again.
            if isinstance(exc, PayhoaError):
                recorder.done(item.id, Result.FAILED, f"PayHOA refused the send: {exc}")
            else:
                recorder.done(item.id, Result.UNCERTAIN,
                              f"{type(exc).__name__}: {exc}; the letters may have been mailed: look in PayHOA's "
                              "Mailroom (jason mailroom) before sending again")
            continue
        batches = ", ".join(str(b["id"]) for b in sent["batches"]) or "(not listed yet: look in PayHOA's Mailroom)"
        charged = sum(int(b["costCents"] or 0) for b in sent["batches"])
        detail = (f"mailed: batch {batches}{', ' + cents(charged) if charged else ''}; fingerprint "
                  f"{mailroom.shown(item.basis)}; logged in data/mailroom/sent.jsonl")
        if sent.get("readBackError"):
            detail += f"; the batch could not be read back ({sent['readBackError']}): look in PayHOA's Mailroom"
        notice = ctx.record.get("notice") or ""
        if notice:
            try:
                entry = mailroom.keep_notice(Path(live.data_dir), notice, ctx.prepared, sent, by=recorder.actor)
                detail += f"; kept as the notice {notice} (sha256 {entry['files'][0]['sha256'][:16]})"
            except Exception as exc:  # noqa: BLE001 - the mailing is done; the keeping is said, not hidden
                detail += f"; the letter was mailed but could not be kept as the notice {notice}: {type(exc).__name__}: {exc}"
        recorder.done(item.id, Result.APPLIED, detail)


__all__ = ["Context", "KEY", "OP", "RULE", "apply", "build", "cents", "plan", "signed_by_two"]
