"""``jason mailroom --preview ID`` and ``--approval ID``: a saved preview read again, and a two-person plan applied.

Both are called from ``cli.cmd_mailroom`` after PayHOA is signed in. ``--preview ID`` shows a saved preview (the record
``tasks.mailroom.save_preview`` keeps beside PayHOA's proof) and whether it is stale: the PDF changed, the units or the
owners PayHOA names moved, the cost differs, or it is older than the limit. With ``--send --yes`` it sends exactly that
preview: the letter is read again and refused unless its fingerprint is the saved one. ``--approval ID`` checks a
``payhoa-mailroom-send`` approval (nothing mailed), and with ``--send --yes`` applies it: the one place that kind is
applied (``Live.terminal``). Neither mails anything on jason's own initiative.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _mail_class_word(value: str) -> str:
    return "first-class" if value == "first class" else "standard"


def _lines(record: dict[str, Any], stale: list[str] | None) -> list[str]:
    from jason.tasks import mailroom

    o, p, pr = record["options"], record["pdf"], record["printed"]
    where = "owners' mailing" if o["sendTo"] == "mailing" else "unit"
    out = [f"preview {record['id']} (fingerprint {mailroom.shown(record['fingerprint'])}), read {record['read']}"
           + (f" by {record['by']}" if record.get("by") else ""),
           f"  {p['name']}: {p['pages']} pages, sha256 {p['sha256'][:16]}"
           + (f"; kept as the notice {record['notice']}" if record.get("notice") else ""),
           f"  {len(record['units'])} units, {record['lettersExpected']} letters expected; prints as {pr['pages']} pages on "
           f"{pr['sheets']} sheets; ${pr['centsEach'] / 100:.2f} a letter, ${record['totalCents'] / 100:.2f} in all "
           f"({'heavy: $2.25 more postage a letter' if pr['heavy'] else 'no heavy postage'})",
           f"  {o['mailClass']}{', ' + o['tracking'] if o['tracking'] else ''}, "
           f"{'black and white' if o['color'] == 'bw' else 'color'}, {'two' if o['doubleSided'] else 'one'}-sided"
           + (", with invoices" if o["withInvoices"] else "") + f"; to the {where} address"]
    out += [f"  no PayHOA unit matched '{m}'" for m in record.get("missing") or ()]
    if stale is None:
        return out
    if stale:
        out.append("  STALE, read it again (jason mailroom --pdf FILE --units UNITS): " + "; ".join(stale))
    else:
        out.append("  current: the letter, the units, the owners, the addresses, and the cost match PayHOA as read just now")
    out.append("  A preview is a read of PayHOA at a time, not a promise. Nothing is mailed by this command.")
    return out


def show_preview(args: argparse.Namespace, client: Any, org_id: int, data_dir: Path) -> int | None:
    """Show a saved preview and whether it is stale. With ``--send --yes`` and a current preview, set up the arguments
    to send exactly it and return None (``cmd_mailroom`` then goes through its ``--pdf`` path, expecting the saved
    fingerprint); otherwise return the exit code (0 current, 1 stale, 2 not found)."""
    from jason.tasks import mailroom

    try:
        record = mailroom.load_preview(data_dir, args.preview)
        facts, _ = mailroom.live_facts(client, org_id, data_dir, record)
    except (KeyError, ValueError) as exc:
        print(f"refused: {exc.args[0] if exc.args else exc}", file=sys.stderr)
        return 2
    stale = mailroom.stale_reasons(record, facts)
    replaying = bool(args.send and args.yes and not stale)         # the --pdf path then prints the one document
    if not replaying and args.json:
        print(json.dumps({"preview": record, "current": facts["fingerprint"], "stale": stale,
                          "maxAgeHours": mailroom.PREVIEW_MAX_AGE_HOURS}, indent=2, default=str))
    elif not replaying:
        print("\n".join(_lines(record, stale)))
    if not (args.send and args.yes):
        return 1 if stale else 0
    if stale:
        print("refused, nothing mailed: the preview is stale; read it again and send that one", file=sys.stderr)
        return 2
    o = record["options"]
    args.pdf, args.units = record["pdf"]["path"], ",".join(str(u["id"]) for u in record["units"])
    args.send_to, args.with_invoices, args.double_sided = o["sendTo"], o["withInvoices"], o["doubleSided"]
    args.mail_class, args.tracking, args.color = _mail_class_word(o["mailClass"]), o["tracking"], o["color"] != "bw"
    args.expect = args.expect or record["fingerprint"]
    args.notice = args.notice or record.get("notice") or ""
    return None


def _recheck_lines(r: Any) -> list[str]:
    from jason.approvals.model import short

    out = [f"{r.approval.id}: {r.approval.status.value}"]
    out += [f"  refused: {p}" for p in r.problems]
    if r.planned is not None:
        out.append(f"  the plan's fingerprint at review {short(r.then)}, read live now {short(r.now)}: "
                   + ("unchanged" if not r.changed else f"{len(r.changed)} changed since review"))
        out += [f"    {c.op} {c.label}: {c.why}" for c in r.changed]
    return out


def apply_approval(args: argparse.Namespace, client: Any, org_id: int, data_dir: Path) -> int:
    """Check a ``payhoa-mailroom-send`` approval, or with ``--send --yes`` mail it. The engine refuses unless the plan is
    approved and confirmed by a second, distinct person, is not too old, and the letter's fingerprint (read just now) is
    the one reviewed; a letter that changed supersedes the plan and mails nothing."""
    from jason.approvals import engine, store
    from jason.approvals.audit import os_actor
    from jason.approvals.kinds.mailroom_send import KEY
    from jason.tasks import mailroom

    try:
        ident = store.resolve(args.approval, data_dir)
        a = store.load(ident, data_dir)
        if a.kind != KEY:
            raise engine.Refused(f"{a.id} is a {a.kind} approval, not {KEY}")
        if args.expect:
            basis = next((i.basis for i in a.items if i.approvable), "")
            typed = args.expect.strip().lower()
            if len(typed) < mailroom.MIN_EXPECT or not basis.startswith(typed):
                raise mailroom.FingerprintMismatch(
                    f"--expect {typed[:mailroom.FINGERPRINT_SHOWN]} is not the plan's fingerprint "
                    f"({mailroom.shown(basis) or 'none'})")
        live = engine.Live(client, org_id, data_dir, getattr(args, "env", None), terminal=True)
        if not (args.send and args.yes):
            r = engine.check(a.id, live, data_dir=data_dir)
            print("\n".join(_recheck_lines(r)))
            print("Nothing mailed. With --send --yes (and --expect FINGERPRINT) this mails the approved letter."
                  if r.ok else "Nothing mailed: this plan would not be applied as it stands.")
            return 0 if r.ok else 1
        done = engine.apply(a.id, live, by=args.by or os_actor(), data_dir=data_dir)
    except (engine.Refused, KeyError, ValueError) as exc:             # a FingerprintMismatch is a ValueError
        print(f"refused, nothing mailed: {exc.args[0] if exc.args else exc}", file=sys.stderr)
        return 2
    if done.superseded_by is not None:
        print(f"the letter changed since review: nothing mailed. {done.approval.id} is superseded by "
              f"{done.superseded_by.id} (jason approvals show {done.superseded_by.id})")
        for c in done.changed:
            print(f"  {c.op} {c.label}: {c.why}")
        return 1
    result = done.approval
    print(f"{result.id}: {result.status.value}")
    for i in result.approved:
        print(f"  {i.label[:60]}: {i.result.value}" + (f" ({i.result_detail})" if i.result_detail else ""))
    return 0 if result.status.value == "applied" else 1
