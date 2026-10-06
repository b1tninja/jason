"""``jason responses``: has anyone answered? (docs/responses-design.md).

One place to ask over every way an owner can answer a request: a signed-in PayHOA form, a Google Form, a reply email
carrying the filled form, a mailed return that was scanned. The records, the checks, and the acts are
``jason.tasks.response_inbox``; this module is the command line over them.

- No option: the inbox from disk. What is new, grouped by request, then for each channel when it last succeeded, how
  the last try ended, and how old that is ("never checked" says so), and the line naming ``--check``.
- ``--check [--channel C ...] [--from ADDRESS] [--since DATE] [--by NAME] [--json]``: a live, read-only look at each
  channel. Gmail and PayHOA are asked only when a channel needs them, and only a person at a console or the scheduler
  (``--by scheduler``) runs it. A channel that cannot sign in says why and the others are checked; the exit is 1 when
  any channel failed or needs a sign-in. It writes jason's own inbox on disk and nothing to Gmail or PayHOA.
- ``--list`` (``--state``, ``--request``, ``--unit``, ``--channel``, ``--new``, ``--days``) and ``--show ID``: from disk;
  what is printed is masked (no email address, phone number, or street address).
- ``--read ID [--model NAME] --by NAME``: download the attachments and read the form from them. The reading is evidence
  for a person, never an answer.
- ``--confirm ID --by NAME [--set FIELD=VALUE ...] [--why TEXT]``: a person says "this is what it says". It makes
  keyed answers, the same ones a PayHOA submission becomes. Nothing is written to PayHOA: ``jason owner-info --apply``
  plans what it would do, and only its ``--yes`` writes.
- ``--seen ID ...`` / ``--seen-all``, ``--dismiss ID --by NAME --why TEXT``: a person's act, logged.
- ``--add-manual --request K --how TEXT --who NAME [--unit U] [--file PATH ...] --by NAME``: a return that came another way
  (a form handed in at the office, an answer taken by phone), keyed as an arrival of channel ``manual``, state new. Any scan
  is copied to the private files folder; ``--read`` and ``--confirm`` then take it like any other. Sends nothing.
- ``--outstanding [--request K] [--json]``: from disk, who was sent a copy of a request and has not responded (the
  sent-copy catalog ``data/forms/references.json`` less the answers kept), with when each copy was sent and by which
  channel, and a short separate list of owners never sent a copy; names and units only. It says how old the catalog, the
  owner list, and the last check are.

A refusal prints ``jason responses: <reason>`` and exits 2.
"""

from __future__ import annotations

import argparse
import sys
from contextlib import ExitStack
from typing import Any, Callable

from jason.commands.integrations import at_terminal

SCHEDULER = "scheduler"
LIVE_LINE = ("This reads what the last check kept; `jason responses --check` is the live read (Gmail and PayHOA, "
             "read-only).")
ACTIONS = ("check", "list", "show", "read", "confirm", "seen", "seen_all", "dismiss", "outstanding", "add_manual")
# An option and the actions it goes with (None: the inbox view). A stray one is refused rather than ignored.
MODIFIERS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("channel", "--channel", ("check", "list")), ("from_address", "--from", ("check",)), ("since", "--since", ("check",)),
    ("state", "--state", ("list",)), ("unit", "--unit", ("list", "add_manual")), ("new", "--new", ("list",)),
    ("days", "--days", ("list",)), ("request", "--request", ("list", "seen_all", "outstanding", "add_manual")),
    ("how", "--how", ("add_manual",)), ("who", "--who", ("add_manual",)), ("file", "--file", ("add_manual",)),
    ("model", "--model", ("read",)),
    ("set", "--set", ("confirm",)), ("why", "--why", ("confirm", "dismiss")))


def _refuse(reason: str) -> int:
    print(f"jason responses: {reason}", file=sys.stderr)
    return 2


def _ri() -> Any:
    from jason.tasks import response_inbox

    return response_inbox


def _mask(value: Any, *, addresses: bool = True) -> Any:
    """``value`` with each email address and phone number replaced (and, unless ``addresses`` is False, each street
    address): nothing printed here is a contact detail."""
    from jason.approvals.audit import mask

    return mask(value, addresses=addresses)


def _hide(name: str, value: Any) -> Any:
    """An answer's value as it may leave: an email or a phone number masked wherever it is, and a field named for contact
    details (an email, a phone, a mailing address) masked whole when the pattern missed it. A unit's own address is the
    unit's, so it stays (the same rule as the MCP tool ``response``)."""
    from jason.approvals.evidence import _CONTACT_NAME

    if isinstance(value, (list, tuple)):
        return [_hide(name, v) for v in value]
    if isinstance(value, dict):
        return {k: _hide(k, v) for k, v in value.items()}
    if not isinstance(value, str):
        return value
    private = bool(_CONTACT_NAME.search(name or ""))
    text = _mask(value, addresses=private)
    return "[masked]" if private and text.strip() and text == value else text


def _community() -> Any:
    from jason.community import community

    return community()


def _titles(community: Any) -> dict[str, str]:
    try:
        return {r.key: r.title for r in community.response_requests()}
    except Exception:  # noqa: BLE001 - a profile that cannot say is a profile with no titles
        return {}


def _print_json(body: Any) -> None:
    from jason.commands._shared import to_json

    print(to_json(body))


class _Clients:
    """The live clients, made when a channel first asks for one (``Jason`` is built then, and closed at the end), so a
    check of the disk channels alone signs in to nothing. Gmail is never interactive here."""

    def __init__(self, args: argparse.Namespace, agent_factory: Callable[[Any], Any]) -> None:
        self.args, self.factory, self.stack, self._agent = args, agent_factory, ExitStack(), None

    def agent(self) -> Any:
        if self._agent is None:
            self._agent = self.stack.enter_context(self.factory(self.args))
        return self._agent

    def mapping(self) -> dict[Any, Callable[[], Any]]:
        from jason.community.response_inbox import Channel

        return {Channel.PAYHOA: lambda: self.agent().payhoa(),
                Channel.GMAIL: lambda: self.agent().gmail(interactive=False)}

    def __enter__(self) -> _Clients:
        return self

    def __exit__(self, *exc: Any) -> Any:
        return self.stack.__exit__(*exc)


# -- words --------------------------------------------------------------------------------------------------------------

def _age(hours: float | None) -> str:
    if hours is None:
        return ""
    if hours < 1:
        return f"{round(hours * 60)}m"
    return f"{hours:.0f}h" if hours < 48 else f"{hours / 24:.0f}d"


def _when(stamp: str) -> str:
    return stamp[:16].replace("T", " ") if stamp else "unknown time"


def _arrival_lines(a: Any, indent: str = "  ") -> list[str]:
    """An arrival in two lines: who, which unit, when, its state; then its subject and attachment names."""
    mark = f" (superseded by {a.superseded_by})" if a.superseded_by else ""
    head = f"{indent}{a.id}  {_when(a.at)}  {a.who or '-'}  {a.unit or 'unit not known'}  [{a.state.value}]{mark}"
    detail = (a.summary or "") + (f"  attachments: {', '.join(a.attachments)}" if a.attachments else "")
    return [_mask(head, addresses=False), _mask(f"{indent}    {detail.strip()}", addresses=False)]


def _channel_lines(data_dir: Any) -> list[str]:
    """Each channel: when it last succeeded and how old that is, how the last try ended, or that it was never checked."""
    from jason.community.response_inbox import Channel

    known = {row["channel"]: row for row in _ri().channel_status(data_dir)}
    reads_disk = {"mail": " (reads disk)", "forms": " (reads disk)"}
    out = []
    for channel in Channel:
        row = known.get(channel.value)
        label = f"  {channel.value:7}"
        if channel is Channel.MANUAL:                # a person adds these (--add-manual): there is nothing to check
            out.append(f"{label} keyed by a person from paper or a call (nothing to check)")
            continue
        if row is None:
            out.append(f"{label} never checked{reads_disk.get(channel.value, '')}")
            continue
        ended = row["ended"] or "unknown"
        why = f": {row['reason']}" if row["reason"] and row["ended"] != "ok" else ""
        if row["lastOk"]:
            out.append(_mask(f"{label} last succeeded {row['lastOk']} ({_age(row['ageHours'])} ago); last try "
                             f"{row['lastTried'] or '?'} ended {ended}{why}", addresses=False))
        else:
            out.append(_mask(f"{label} never succeeded; last try {row['lastTried'] or '?'} ended {ended}{why}",
                             addresses=False))
    return out


# -- no option: the inbox from disk -------------------------------------------------------------------------------------

def _inbox(args: argparse.Namespace, data_dir: Any) -> int:
    ri = _ri()
    community = _community()
    titles = _titles(community)
    arrivals = list(ri.load_inbox(data_dir).arrivals.values())
    new = ri.list_arrivals(data_dir, state="new")
    others: dict[str, int] = {}
    for a in arrivals:
        if a.state.value != "new":
            others[a.state.value] = others.get(a.state.value, 0) + 1
    if args.json:
        _print_json({"new": [_mask(a.to_json(), addresses=False) for a in new], "kept": len(arrivals), "otherStates": others,
                     "checked": ri.channel_status(data_dir), "note": LIVE_LINE})
        return 0
    print(f"Responses inbox: {len(new)} new, {len(arrivals)} kept.")
    if not titles and not arrivals:
        print("The profile watches no request (Community.response_requests is empty), so there is nothing to check.")
    print()
    if new:
        print("New, by request:")
        order = [k for k in titles if any(a.request == k for a in new)] + \
                sorted({a.request for a in new} - set(titles))
        for key in order:
            rows = [a for a in new if a.request == key]
            print(f"  {key}: {titles.get(key, 'a request the profile no longer lists')} ({len(rows)})")
            for a in rows:
                print("\n".join(_arrival_lines(a, "    ")))
        print()
    else:
        print("Nothing new.")
        print()
    if others:
        print("Kept, in other states: " + ", ".join(f"{k} {v}" for k, v in sorted(others.items()))
              + "  (jason responses --list --state STATE)")
        print()
    print("Channels:")
    print("\n".join(_channel_lines(data_dir)))
    print()
    print(LIVE_LINE)
    return 0


# -- --check ------------------------------------------------------------------------------------------------------------

def _check(args: argparse.Namespace, agent_factory: Callable[[Any], Any], data_dir: Any) -> int:
    from jason.commands._shared import day
    from jason.community.response_inbox import Channel

    ri = _ri()
    by = (args.by or "").strip()
    if not (at_terminal() or by == SCHEDULER):
        return _refuse("a live check calls Gmail and PayHOA, so a person runs it at a terminal (stdin is not one); the "
                       f"scheduler passes --by {SCHEDULER}")
    try:
        since = day(args.since)
    except ValueError:
        return _refuse("--since takes a day as YYYY-MM-DD")
    if not by:
        from jason.approvals.audit import os_actor

        by = os_actor()
    channels = [Channel(c) for c in args.channel or []] or None
    with _Clients(args, agent_factory) as live:
        report = ri.check(data_dir, _community(), clients=live.mapping(), by=by, channels=channels, since=since,
                          sender=args.from_address or "")
    kept_ids = {a.id for a in report.kept}
    if args.json:
        _print_json({
            "at": report.at, "by": report.by,
            "channels": [{"channel": c.channel.value, "ended": c.ended.value, "reason": _mask(c.reason, addresses=False),
                          "looked": c.looked, "kept": c.kept} for c in report.channels],
            "kept": [_mask(a.to_json(), addresses=False) for a in report.kept],
            "listed": [_mask({"id": f"gmail:{m.id}", "at": m.at, "who": m.who, "subject": m.subject,
                              "attachments": list(m.attachments), "candidate": m.candidate, "reason": m.reason,
                              "kept": f"gmail:{m.id}" in kept_ids}, addresses=False) for m in report.listed]})
        return 1 if report.failed else 0
    print(f"Checked {report.at} by {report.by}. Read-only: nothing was written to Gmail or PayHOA; only jason's own "
          f"inbox on disk.")
    if not report.channels:
        print("Nothing was checked: no channel applies (--from searches Gmail only).")
    for c in report.channels:
        line = f"  {c.channel.value:7} {c.ended.value:8} looked {c.looked}, kept {c.kept}"
        if c.ended.value == "sign-in":
            line += f"; needs a sign-in: {c.reason}"
        elif c.reason:
            line += f"; {c.reason}"
        print(_mask(line, addresses=False))
    print()
    if report.kept:
        print(f"Kept {len(report.kept)} new:")
        for a in report.kept:
            print("\n".join(_arrival_lines(a)))
    else:
        print("Nothing new was kept.")
    if args.from_address:
        print()
        now_kept = sum(1 for m in report.listed if f"gmail:{m.id}" in kept_ids)
        print(f"Messages from that address in the window: {len(report.listed)} found, {now_kept} kept now "
              f"(the address is not printed).")
        for m in report.listed:
            if f"gmail:{m.id}" in kept_ids:
                verdict = "kept"
            elif m.candidate:
                verdict = "already kept"
            else:
                verdict = f"listed only, not kept: {m.reason}"
            files = f"  attachments: {', '.join(m.attachments)}" if m.attachments else ""
            print(_mask(f"  gmail:{m.id}  {_when(m.at)}  {m.who}  {m.subject}{files}  [{verdict}]", addresses=False))
    if report.failed:
        print()
        print("Failed: " + ", ".join(c.channel.value for c in report.failed) + ". A channel that needs a sign-in is "
              "the scheduler's pause, not a retry: sign in (`jason login`, or the Google sign-in), then check again.")
    return 1 if report.failed else 0


# -- --list and --show --------------------------------------------------------------------------------------------------

def _list(args: argparse.Namespace, data_dir: Any) -> int:
    ri = _ri()
    if args.new and args.state and args.state != "new":
        return _refuse("--new is the state new; it does not go with another --state")
    rows = ri.list_arrivals(data_dir, state=args.state or "", request=args.request or "", unit=args.unit or "",
                            new=bool(args.new), days=int(args.days or 0))
    if args.channel:
        rows = [a for a in rows if a.channel.value in set(args.channel)]
    if args.json:
        _print_json({"arrivals": [_mask(a.to_json(), addresses=False) for a in rows],
                     "checked": ri.channel_status(data_dir), "note": LIVE_LINE})
        return 0
    if not rows:
        print("No arrival matches.")
    else:
        print(f"{len(rows)} arrival(s), newest first:")
        for a in rows:
            print("\n".join(_arrival_lines(a)))
    print()
    print(LIVE_LINE)
    return 0


def _answer_text(value: Any) -> str:
    return "; ".join(str(v) for v in value) if isinstance(value, (list, tuple)) else str(value)


def _mask_reading(reading: dict[str, Any] | None) -> dict[str, Any] | None:
    """A reading with every value masked, except the unit it names (a unit's label is not a contact detail). The answers
    and each field's value are masked by the field's name (``_hide``)."""
    if reading is None:
        return None
    kept = ("owner", "answers", "fields", "notes", "copy", "recognition")
    masked = _mask({k: v for k, v in reading.items() if k not in kept})
    masked["owner"] = _mask(reading.get("owner") or {}, addresses=False)
    # the notes, the copy sent, and how it was recognized name units (a unit's label is not a contact detail): an email
    # address or phone number in them is still masked
    for name in ("notes", "copy", "recognition"):
        if name in reading:
            masked[name] = _mask(reading[name], addresses=False)
    masked["answers"] = _hide("", reading.get("answers") or {})
    masked["fields"] = {name: {**{k: v for k, v in _mask(f).items() if k != "value"}, "value": _hide(name, f.get("value"))}
                        for name, f in (reading.get("fields") or {}).items()}
    return masked


def _mask_keyed(keyed: dict[str, Any] | None) -> dict[str, Any] | None:
    """The keyed answers' file masked: its answers and contacts by field name, the rest by pattern."""
    if keyed is None:
        return None
    masked = _mask({k: v for k, v in keyed.items() if k not in ("answers", "contacts")}, addresses=False)
    masked["answers"] = _hide("", keyed.get("answers") or {})
    masked["contacts"] = _hide("", keyed.get("contacts") or [])
    masked["problems"] = _mask(keyed.get("problems") or [])
    return masked


def _copy_sent(data_dir: Any, community: Any, reading: dict[str, Any]) -> dict[str, Any]:
    """The copy the reading names (``tasks.response_inbox.copy_of``): the one the reading recorded when it was made, else the
    one the sent-copy catalog holds under the printed reference, with whether it was sent to the owner and unit the sender's
    address matched and to the unit the form names. ``None`` for a comparison that cannot be made."""
    return _ri().copy_of(data_dir, reading, community=community)


def _rung_number(name: str) -> int:
    from jason.tasks.recognize import Rung

    try:
        return Rung(name).number
    except ValueError:
        return 0


def _yes(value: bool | None, unknown: str = "not known") -> str:
    return unknown if value is None else ("yes" if value else "NO")


def _reading_lines(reading: dict[str, Any], copy: dict[str, Any]) -> list[str]:
    """A reading as a person checks it: how it was read, the form's reference and whether it matches the copy's owner
    and unit, each field with its confidence, and the reader's notes. Masked."""
    r = _mask_reading(reading) or {}
    how = r.get("how") or "not the form"
    out = [f"Reading ({how}; read {r.get('readAt', '?')} by {r.get('by', '?')}"
           + (f", model {r['model']}" if r.get("model") else ", no model") + "). It is evidence for a person to "
           "check against the scan, never an answer."]
    if not r.get("form"):
        out.append("  No form was found in the files: dismiss the arrival, or read it again (--model reads handwriting).")
    for f in r.get("files") or []:
        out.append(f"  file {f.get('name')}: {f.get('how')}"
                   + (f" ({f['linesMatched']} printed lines matched)" if f.get("linesMatched") else ""))
    owner = r.get("owner") or {}
    out.append("  sender matched to: " + (f"{owner.get('name')}, {owner.get('unit')} ({owner.get('matchedBy')})"
                                          if owner else "no owner (the address is not one PayHOA holds, or a mailed scan)"))
    if r.get("reference"):
        out.append(f"  reference: {r['reference']} (read from {r.get('referenceHow') or 'the page'}); the campaign "
                   f"{r.get('campaign') or '?'} {'names this request' if r.get('campaignMatches') else 'is not this request'}")
        if not copy.get("found"):
            out.append("  the copy sent under it: " + (
                "a reference we did not send (no copy on file carries it)" if copy.get("unsent") else
                "none on file (data/forms/references.json), so unit and owner cannot be compared"))
    else:
        out.append("  reference: none read from the page")
    if copy.get("found"):
        sent = f"sent to {copy.get('owner') or 'an owner'} at {copy.get('unit') or 'a unit'}" \
               + (" (the reference was put right by one character)" if copy.get("putRight") else "")
        written = copy.get("matchesWritten")
        out.append(f"  the copy sent under it: {sent}; matches the sender's unit: {_yes(copy.get('matchesUnit'))}; "
                   f"owner: {_yes(copy.get('matchesOwner'))}"
                   + (f"; the unit written on the form: {_yes(written)}" if written is not None else ""))
        if copy.get("rung"):
            out.append(f"  recognized by rung {_rung_number(copy['rung'])}, {copy['rung']} ({copy.get('sure', '?')}): "
                       "a hint checked against what was sent, not a reading")
    elif not r.get("reference") and copy.get("unsent"):
        out.append("  a reference we did not send was found in the subject or an attachment's text")
    fields = r.get("fields") or {}
    if fields:
        out.append("  fields (value, how it was read, confidence):")
        for name, f in fields.items():
            out.append(f"    {name:28} {_answer_text(f.get('value'))[:60]:60} {f.get('how', ''):10} {float(f.get('confidence', 0)):.2f}")
    if r.get("answers"):
        out.append("  answers read (what --confirm keeps, unless --set corrects them; values masked):")
        out += [f"    {k}: {_answer_text(v)}" for k, v in r["answers"].items()]
    if r.get("signature") or r.get("signed"):
        out.append(f"  signature: {r.get('signature') or 'none read'}; dated {r.get('signed') or 'none read'}")
    for note in r.get("notes") or []:
        out.append(f"  note: {note}")
    return out


def _left(a: Any) -> str:
    """What is left to do for an arrival, as the command that does it."""
    state = a.state.value
    if state in ("new", "seen"):
        if a.structured:
            return (f"it came structured ({a.channel.value}): no reading is needed; `jason owner-info --apply` plans from it")
        return f"read it (`jason responses --read {a.id} --by NAME`), then confirm it"
    return {"read": f"confirm the reading (`jason responses --confirm {a.id} --by NAME [--set FIELD=VALUE]`) or dismiss it",
            "keyed": "record it: `jason owner-info --apply --payhoa` plans the writes; a person's --yes writes PayHOA",
            "recorded": "nothing: PayHOA holds what it called for", "dismissed": "nothing: it was set aside"}[state]


def _show(args: argparse.Namespace, data_dir: Any) -> int:
    ri = _ri()
    body = ri.show(data_dir, args.show)
    a = ri.get(data_dir, args.show)
    copy = _copy_sent(data_dir, _community(), body["reading"]) if body["reading"] else {}
    masked = {"arrival": _mask(body["arrival"], addresses=False), "reading": _mask_reading(body["reading"]),
              "copy": copy, "keyed": _mask_keyed(body["keyed"]), "files": body["files"],
              "acts": _mask(body["acts"], addresses=False), "left": _left(a)}
    if args.json:
        _print_json(masked)
        return 0
    print("\n".join(_arrival_lines(a, "")[:1]))
    print(f"  request {a.request}; arrived {a.at or '?'}; kept {a.kept_at or '?'}")
    print(_mask(f"  {a.summary}", addresses=False))
    print(f"  attachments: {', '.join(a.attachments) or 'none'}; downloaded: {', '.join(body['files']) or 'none'}")
    if a.note:
        print(_mask(f"  note: {a.note}", addresses=False))
    if body["reading"]:
        print()
        print("\n".join(_reading_lines(body["reading"], copy)))
    if masked["keyed"]:
        k = masked["keyed"]
        print()
        print(f"Keyed answers (confirmed by {k.get('by')} {k.get('at')}; values masked):")
        for name, value in (k.get("answers") or {}).items():
            print(f"  {name}: {_answer_text(value)}")
        print(f"  corrected: {', '.join(k.get('corrected') or []) or 'none'}; problems: {'; '.join(k.get('problems') or []) or 'none'}")
    print()
    print("Acts:")
    for act in masked["acts"]:
        why = f": {act['why']}" if act.get("why") else ""
        print(f"  {act['at']}  {act['by']}  {act['act']}{why}")
    print()
    print(f"Left: {_left(a)}")
    return 0


# -- --outstanding ------------------------------------------------------------------------------------------------------

def _ago(hours: float | None) -> str:
    return f"{_age(hours)} ago" if hours is not None else "age not known"


def _outstanding_lines(body: dict[str, Any]) -> list[str]:
    cat, check, owners = body["catalog"], body["lastCheck"], body["ownerList"]
    out = [f"Who was sent a copy and has not responded, as of {_when(body['at'])} UTC. Disk only: nothing was asked of PayHOA "
           "or Gmail."]
    if cat["exists"]:
        out.append(f"  sent-copy catalog: {cat['path']}, written {_when(cat['writtenAt'])} ({_ago(cat['ageHours'])}); "
                   f"{cat['copies']} copies on record" + (f", {cat['mailings']} mailing(s)" if cat["mailings"] else "")
                   + (f"; the newest was sent {_when(cat['newestSent'])} ({_ago(cat['newestSentAgeHours'])})"
                      if cat["newestSent"] else ""))
    else:
        out.append(f"  sent-copy catalog: none on disk ({cat['path']}): no copy has been recorded as sent")
    out.append(f"  last check that succeeded: {_when(check['at'])} ({_ago(check['ageHours'])}); `jason responses --check` "
               "looks for newer answers" if check["at"] else "  last check: none has succeeded yet, so answers that "
               "arrived are not counted (`jason responses --check`)")
    out.append("  owner list: " + (f"data/payhoa.db, written {_when(owners['writtenAt'])} ({_ago(owners['ageHours'])})"
                                   if owners["exists"] else "none on disk (data/payhoa.db)"))
    if not body["requests"]:
        out += ["", "The profile watches no request (Community.response_requests is empty)."]
    for req in body["requests"]:
        out += ["", f"{req['request']}: {req['title']} (return by {req['returnBy'] or 'no date'})",
                f"  {req['sent']} copies sent, {req['answered']} answered, {req['notResponded']} not responded"]
        if req.get("handler"):                 # chosen when the form was made (jason campaigns)
            out.append(f"  handler: {req['handler']} (campaigns {', '.join(c['code'] for c in req['campaigns'])})")
        if req["outstanding"]:
            out.append("  Sent a copy and not responded:")
            for row in req["outstanding"]:
                days = f" ({row['daysSinceSent']}d)" if row["daysSinceSent"] is not None else ""
                out.append(f"    {row['unit'] or 'unit not known':28} {row['owner'] or 'owner not known':26} "
                           f"{row['channel'] or '?':6} sent {_when(row['sentAt'])[:10]}{days}")
        elif req["sent"]:
            out.append("  Everyone who was sent a copy has an answer on disk.")
        else:
            out.append("  No emailed copy is on record for this request.")
        if req["neverAsked"] is None:
            out.append(f"  Never asked: {req['neverAskedNote']}")
        elif req["neverAsked"]:
            out.append(f"  Never sent a copy (no copy recorded; {req['neverAskedAnswered']} more answered anyway):")
            for row in req["neverAsked"]:
                out.append(f"    {row['unit'] or 'unit not known':28} {row['owner'] or 'owner not known'}"
                           + ("  (another owner of the unit was sent one)" if row["unitHasASentCopy"] else ""))
        else:
            out.append("  Never asked: every current owner was sent a copy or has answered.")
        if req["note"]:
            out.append(f"  {req['note']}")
    out += ["", body["note"].capitalize() + "."]
    return out


def _outstanding(args: argparse.Namespace, data_dir: Any) -> int:
    from jason.tasks.response_outstanding import outstanding

    body = _mask(outstanding(data_dir, _community(), request=args.request or ""), addresses=False)
    if args.json:
        _print_json(body)
        return 0
    print("\n".join(_outstanding_lines(body)))
    return 0


# -- --read, --confirm, --seen, --dismiss -------------------------------------------------------------------------------

def _read(args: argparse.Namespace, agent_factory: Callable[[Any], Any], data_dir: Any) -> int:
    ri = _ri()
    by = (args.by or "").strip()
    if not (at_terminal() or by == SCHEDULER):
        return _refuse("reading an arrival downloads its attachments (Gmail) and may run a local model, so a person runs "
                       f"it at a terminal (stdin is not one); the scheduler passes --by {SCHEDULER}")
    community = _community()
    with _Clients(args, agent_factory) as live:
        reading = ri.read(data_dir, community, args.read, by=by, clients=live.mapping(), model=args.model or "")
    copy = _copy_sent(data_dir, community, reading)
    if args.json:
        _print_json({"reading": _mask_reading(reading), "copy": copy})
        return 0
    a = ri.get(data_dir, args.read)
    print(f"Read {a.id} by {by}: {len(reading['files'])} file(s) in data/responses/files/{a.stem}/. Nothing was written "
          f"to Gmail or PayHOA, and no answer was made.")
    print("\n".join(_reading_lines(reading, copy)))
    print()
    if reading.get("form"):
        print(f"Next: check it against the scan, then `jason responses --confirm {a.id} --by NAME [--set FIELD=VALUE ...]`.")
    else:
        print(f"Next: `jason responses --dismiss {a.id} --by NAME --why TEXT`, or read it again with --model.")
    return 0


def _corrections(pairs: list[str] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for pair in pairs or []:
        name, sep, value = pair.partition("=")
        if not sep or not name.strip():
            raise _ri().ResponseError("--set takes FIELD=VALUE (an empty VALUE clears the answer)")
        out[name.strip()] = value
    return out


def _confirm(args: argparse.Namespace, data_dir: Any) -> int:
    ri = _ri()
    keyed = ri.confirm(data_dir, _community(), args.confirm, by=args.by or "", corrections=_corrections(args.set),
                       why=args.why or "")
    answers = _hide("", keyed.answers.answers)
    problems = [_mask(p) for p in keyed.problems]
    if args.json:
        _print_json({"id": args.confirm, "source": keyed.answers.source, "corrected": keyed.corrected,
                     "answers": answers, "problems": problems})
        return 0
    print(f"Confirmed {args.confirm} by {args.by.strip()}: keyed answers kept (source {keyed.answers.source}; values masked).")
    for name, value in answers.items():
        print(f"  {name}: {_answer_text(value)}")
    print(f"  corrected: {', '.join(keyed.corrected) or 'none'}")
    print("  problems: " + ("; ".join(problems) if problems else "none"))
    print("Nothing was written to PayHOA. `jason owner-info --apply` plans what it would write from every answer jason "
          "holds, this one included; only its --yes (a person's) writes PayHOA.")
    return 0


def _seen(args: argparse.Namespace, data_dir: Any) -> int:
    ri = _ri()
    if args.seen_all:
        moved = ri.seen_all(data_dir, by=args.by or "", request=args.request or "")
        ids = moved
    else:
        ids = list(args.seen)
        moved = ri.seen(data_dir, ids, by=args.by or "")
    if args.json:
        _print_json({"seen": moved, "unchanged": [i for i in ids if i not in moved]})
        return 0
    print(f"Marked seen: {', '.join(moved) or 'none'}." + (
        f" Left as they were (only a new arrival moves): {', '.join(i for i in ids if i not in moved)}."
        if len(moved) < len(ids) else ""))
    return 0


def _add_manual(args: argparse.Namespace, data_dir: Any) -> int:
    """A person keys a return that came another way (handed in at the office, taken by phone): one more arrival, channel
    manual, state new. Nothing is sent and nothing is written to PayHOA."""
    if not (args.request or "").strip():
        return _refuse("--request is required with --add-manual: the key of the request the return answers (jason responses --list)")
    if not (args.how or "").strip():
        return _refuse("--how is required with --add-manual: how it came in, e.g. 'handed in at the office' or 'by phone'")
    if not (args.who or "").strip():
        return _refuse("--who is required with --add-manual: the owner's name, as the person gave it")
    arrival = _ri().add_manual(data_dir, _community(), args.request.strip(), by=args.by or "", how=args.how, who=args.who,
                               unit=args.unit or "", files=args.file or ())
    if args.json:
        _print_json(_mask(arrival.to_json(), addresses=False))
        return 0
    print(f"Added {arrival.id} by {args.by.strip()}: {_mask(arrival.who, addresses=False)}, "
          f"{_mask(arrival.unit, addresses=False) or 'unit not named'}; {_mask(arrival.summary, addresses=False)}; "
          f"{len(arrival.attachments)} file(s) kept in data/responses/files/{arrival.stem}/.")
    print(f"Next: `jason responses --read {arrival.id} --by NAME` (a scan is read; with no scan a person keys each answer at "
          "--confirm), then --confirm. Nothing was sent, and nothing was written to PayHOA.")
    return 0


def _dismiss(args: argparse.Namespace, data_dir: Any) -> int:
    ri = _ri()
    before = ri.get(data_dir, args.dismiss)
    after = ri.dismiss(data_dir, args.dismiss, by=args.by or "", why=args.why or "")
    if args.json:
        _print_json(_mask(after.to_json(), addresses=False))
        return 0
    print(f"Dismissed {after.id} by {args.by.strip()}: {_mask(args.why.strip(), addresses=False)}")
    if before.state.value == "keyed":
        print("The keyed answers it had were set aside (data/responses/keyed/withdrawn/), not deleted, and no longer "
              "count as an answer.")
    return 0


# -- the command --------------------------------------------------------------------------------------------------------

def _action(args: argparse.Namespace) -> str | None:
    for name in ACTIONS:
        if getattr(args, name, None):
            return name
    return None


def _stray(args: argparse.Namespace, action: str | None) -> str:
    """The first option given that does not go with the action, else ''."""
    for dest, flag, goes in MODIFIERS:
        if getattr(args, dest, None) and action not in goes:
            return flag
    return ""


def cmd_responses(args: argparse.Namespace, agent_factory: Callable[[Any], Any]) -> int:
    from jason.commands._shared import data_dir as data_of

    action = _action(args)
    stray = _stray(args, action)
    if stray:
        return _refuse(f"{stray} does not go with " + (f"--{action.replace('_', '-')}" if action else "the inbox view; "
                                                          "it goes with an action (see jason responses --help)"))
    from jason.tasks.response_inbox import ResponseError

    refusals: tuple[type[BaseException], ...] = (ResponseError,)
    if action == "read" and args.model:
        from jason.local_ai import LocalAIUnavailable

        refusals += (LocalAIUnavailable,)
    data_dir = data_of(args)
    try:
        if action == "check":
            return _check(args, agent_factory, data_dir)
        if action == "list":
            return _list(args, data_dir)
        if action == "show":
            return _show(args, data_dir)
        if action == "read":
            return _read(args, agent_factory, data_dir)
        if action == "confirm":
            return _confirm(args, data_dir)
        if action in ("seen", "seen_all"):
            return _seen(args, data_dir)
        if action == "dismiss":
            return _dismiss(args, data_dir)
        if action == "outstanding":
            return _outstanding(args, data_dir)
        if action == "add_manual":
            return _add_manual(args, data_dir)
        return _inbox(args, data_dir)
    except refusals as exc:
        return _refuse(str(exc))


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    from jason.community.response_inbox import Channel, State

    p = sub.add_parser("responses", help="Has anyone answered? The inbox of responses to a request (PayHOA form, Google "
                                         "Form, reply email, mailed scan): check, read, confirm, dismiss")
    add_common(p)
    act = p.add_mutually_exclusive_group()
    act.add_argument("--check", action="store_true",
                     help="a live, read-only look at each channel (Gmail, PayHOA, the mail on disk, saved Google Form "
                          "responses); keeps new arrivals in jason's own inbox. A person at a console, or --by scheduler")
    act.add_argument("--list", action="store_true", help="the inbox from disk, newest first")
    act.add_argument("--show", metavar="ID", help="one arrival: its facts, files, reading, keyed answers, and acts (masked)")
    act.add_argument("--read", metavar="ID",
                     help="download its attachments and read the form from them (needs --by; a person at a console, or "
                          "--by scheduler); the reading is evidence, never an answer")
    act.add_argument("--confirm", metavar="ID",
                     help="a person says the reading is what the form says (needs --by); makes keyed answers; writes "
                          "nothing to PayHOA")
    act.add_argument("--seen", nargs="+", metavar="ID", help="mark arrivals looked at and left (needs --by)")
    act.add_argument("--seen-all", action="store_true", help="mark every new arrival seen (needs --by; --request narrows)")
    act.add_argument("--dismiss", metavar="ID", help="not an answer: a question, a duplicate, not the form (needs --by and --why)")
    act.add_argument("--outstanding", action="store_true",
                     help="who was sent a copy and has not responded, and owners never sent one, from the sent-copy catalog "
                          "less the answers kept (disk only; --request narrows; --json)")
    act.add_argument("--add-manual", action="store_true",
                     help="key a return that came another way (handed in at the office, taken by phone) as an arrival, channel "
                          "manual (needs --request, --how, --who, --by; --unit, --file optional); sends nothing")
    p.add_argument("--how", metavar="TEXT", help="with --add-manual: how it came in ('handed in at the office', 'by phone')")
    p.add_argument("--who", metavar="NAME", help="with --add-manual: the owner's name (no address)")
    p.add_argument("--file", action="append", metavar="PATH", help="with --add-manual: a scan or photo of the form (repeatable)")
    p.add_argument("--channel", action="append", choices=[c.value for c in Channel], metavar="C",
                   help="with --check or --list: only this channel (repeatable)")
    p.add_argument("--from", dest="from_address", metavar="ADDRESS",
                   help="with --check: every message from this address in the window, marking which were kept (Gmail; the "
                        "address is not printed or stored)")
    p.add_argument("--since", metavar="DATE", help="with --check: read from this day (YYYY-MM-DD), past a closed window")
    p.add_argument("--state", choices=[s.value for s in State], metavar="S",
                   help="with --list: only arrivals in this state")
    p.add_argument("--request", metavar="K", help="with --list, --seen-all, or --outstanding: only this request's key; with "
                                                  "--add-manual: the request the return answers")
    p.add_argument("--unit", metavar="U", help="with --list: only units whose label contains this; with --add-manual: the unit")
    p.add_argument("--new", action="store_true", help="with --list: only new arrivals")
    p.add_argument("--days", type=int, default=0, metavar="N", help="with --list: only arrivals from the last N days")
    p.add_argument("--model", metavar="NAME", help="with --read: also read handwriting with this local vision model (after the "
                                                   "local-AI preflight, holding the GPU lock)")
    p.add_argument("--set", action="append", metavar="FIELD=VALUE",
                   help="with --confirm: correct a field (repeatable; an empty VALUE clears it; a checkbox's options joined "
                        "with ';')")
    p.add_argument("--why", metavar="TEXT", help="with --confirm: a note; with --dismiss: the reason (required)")
    p.add_argument("--by", metavar="NAME",
                   help="who does it, for the log (--confirm, --read, --seen, --dismiss require it); a check run by the "
                        f"scheduler passes --by {SCHEDULER}")
    p.add_argument("--json", action="store_true", help="print JSON")
    p.set_defaults(func=lambda a: cmd_responses(a, agent_factory))
