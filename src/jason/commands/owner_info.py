"""``jason owner-info``: the owner information cycle (Civil Code 4040, 4041) for the board, in one place.

``jason owner-info`` shows the cycle's deadlines (the date owners are asked to answer by, the day the answers must be in
PayHOA, 30 days before the annual reports), every current owner's standing (answered this cycle, an election on file,
an earlier answer to confirm, or no election and so first-class mail), and how notices go today; ``--out FILE`` writes
the ledger, one row an owner (names; no addresses). Answers come from every channel jason reads: the outside forms in
``mystique/forms.py`` (their saved responses) and, with ``--payhoa``, the PayHOA form's signed-in submissions.

``--prefill UNIT --out DIR`` writes each owner's letter with a page of what PayHOA holds for them beside the blank form
(``tasks.owner_prefill``), for a person to look at.

``--apply`` reads PayHOA live and lists every write that would bring it up to date, each with its reason: the
default "Notices by Mail" tag for owners with no election, a this-cycle answer's tag changes, and each earlier answer
applied as tags (no custom fields), never over an election already in PayHOA. ``--yes`` writes them.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any, Callable


def _data_dir(args: argparse.Namespace) -> Path:
    from jason.config import Settings

    return Settings.load(args.env).payhoa_catalog.parent


def _answers(data_dir: Path, forms: Any, client: Any = None, org_id: int | None = None) -> tuple[list[Any], dict[str, str]]:
    """Every answer jason holds, from each channel, and each source's title."""
    from jason.tasks.forms import forms_dir, import_responses

    answers, titles = [], {"payhoa": "PayHOA owner information form"}
    for rules in forms.FORM_IMPORTS:
        saved = forms_dir(data_dir) / rules.source / "responses.json"
        if saved.is_file():
            answers += import_responses(json.loads(saved.read_text(encoding="utf-8")), rules)
            titles["google"] = rules.title
    if client is not None:
        from jason.tasks.payhoa_forms import fetch_submissions, record_for

        record = record_for(data_dir, forms.OWNER_INFO.key.value)
        if record:
            from jason.config import test_memberships

            tests = test_memberships()      # a test account's answers are never an owner's
            answers += [a for a in fetch_submissions(client, org_id, record, forms.OWNER_INFO)
                        if a.membership_id is None or int(a.membership_id) not in tests]
    return answers, titles


def _rows(units: list[dict[str, Any]], people: list[dict[str, Any]], answers: list[Any], data_dir: Path,
          community: Any, cycle: Any, today: date) -> tuple[Any, list[Any]]:
    from jason.tasks.member_preferences import match, unit_owners
    from jason.tasks.notice_delivery import plan
    from jason.tasks.owner_info import ledger
    from jason.tasks.parties import PartyResolver

    tags = community.payhoa_tags()
    deeds = PartyResolver(data_dir).latest_deed
    matched = match(answers, unit_owners(units, people, deeds, tags), tags, cycle=cycle, today=today)
    found = plan(units, people, tags)
    from jason.community.spec import spec_module

    return found, ledger(found, matched, tags, cycle, earlier=spec_module("forms").EARLIER_ELECTIONS, today=today)


def cmd_owner_info(args: argparse.Namespace, agent_factory: Callable[[Any], Any]) -> int:
    from jason.community import mystique
    from jason.community.spec import spec_module
    from jason.config import Settings
    from jason.tasks.broadcast import catalog_rows
    from jason.tasks.owner_info import summary

    community, forms, today = mystique(), spec_module("forms"), date.today()
    cycle, data_dir = forms.OWNER_INFO_CYCLE, _data_dir(args)
    if args.apply:
        return _apply(args, agent_factory, community, forms, cycle, data_dir, today)
    if args.prefill:
        return _prefill(args, agent_factory, community, forms, data_dir)
    if args.send_plan:
        return _send_plan(args, agent_factory, community, forms, data_dir)
    if args.email_batch:
        return _email_batch(args, agent_factory, community, forms, data_dir)
    if args.mail_batch:
        return _mail_batch(args, agent_factory, community, forms, data_dir)
    units, people, synced = catalog_rows(Settings.load(args.env).payhoa_catalog)
    units = [{**u, "label": u.get("title")} for u in units]
    if args.payhoa:
        with agent_factory(args) as agent:
            answers, _ = _answers(data_dir, forms, agent.payhoa(), agent.org_id)
    else:
        answers, _ = _answers(data_dir, forms)
    found, rows = _rows(units, people, answers, data_dir, community, cycle, today)
    report = summary(rows, cycle, today)
    report["catalogSynced"] = synced
    # The plan this read computed, saved for the web UI to show and a person to confirm (owner_info_plan).
    from jason.tasks.owner_info import plan_writes, to_complete
    from jason.tasks.owner_info_plan import save_plan

    planned = plan_writes(rows, found, community.payhoa_tags(), earlier=forms.EARLIER_ELECTIONS, today=today)
    save_plan(data_dir, summary=report, writes=planned, to_complete=to_complete(rows, planned), owners=rows)
    print(json.dumps(report, indent=1))
    print("next actions:")
    for action, count in Counter(a for r in rows for a in r.actions[:1]).most_common():
        print(f"  {count:3}  {action}")
    if args.out:
        with open(args.out, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["unit", "owner", "status", "notices go by", "latest answer", "answered", "age", "next action"])
            for r in rows:
                a = r.answer
                writer.writerow([r.unit, r.name, r.status.value, r.delivery, a.source if a else "",
                                 a.submitted[:10] if a else "", a.age if a else "", "; ".join(r.actions)])
        print(f"ledger: {args.out}")
    return 0


def _apply(args: argparse.Namespace, agent_factory: Callable[[Any], Any], community: Any, forms: Any, cycle: Any,
           data_dir: Path, today: date) -> int:
    """Read PayHOA live, plan the writes, and with --yes perform them."""
    from jason.tasks.owner_info import execute, plan_writes

    with agent_factory(args) as agent:
        client, org = agent.payhoa(), agent.org_id
        units, page = [], 1
        while True:
            body = client.list_units(org, page=page)
            units.extend(body.get("data") or [])
            meta = body.get("meta") or {}
            if page >= int(meta.get("lastPage") or meta.get("last_page") or 1):
                break
            page += 1
        people = list(client.iter_people(org))
        answers, _ = _answers(data_dir, forms, client if args.payhoa else None, org)
        found, rows = _rows(units, people, answers, data_dir, community, cycle, today)
        writes = plan_writes(rows, found, community.payhoa_tags(), earlier=forms.EARLIER_ELECTIONS, today=today)
        # a test account is never an owner of record: no delivery or other tag goes on it
        from jason.config import test_memberships

        test = test_memberships(getattr(args, "env", None))
        writes = [w for w in writes if not (w.kind.startswith("member") and w.target in test)]
        from jason.tasks.owner_info import to_complete as _to_complete
        from jason.tasks.owner_info_plan import save_plan as _save_plan

        _save_plan(data_dir, summary=summary(rows, cycle, today), writes=writes, to_complete=_to_complete(rows, writes), owners=rows)
        for kind, count in Counter(w.kind for w in writes).items():
            print(f"  {kind:14} {count}")
        for w in writes[: args.show]:
            print(f"    {w.kind:14} {w.label[:40]:40} {w.value[:70]}  ({w.why})")
        if not writes:
            print("PayHOA is up to date for this cycle.")
        elif not args.yes:
            print(f"Dry run ({len(writes)} writes, read live just now): add --yes to write them in PayHOA.")
        else:
            tag_rows = {int(p["id"]): list(p.get("tags") or []) for p in people if p.get("id") is not None}
            done = execute(client, org, writes, member_tag_rows=tag_rows)
            print("written: " + ", ".join(f"{k} {v}" for k, v in done.items()))
            writes = []                                  # written: nothing pending stands in a request's way
            _save_plan(data_dir, summary=summary(rows, cycle, today), writes=[], to_complete=_to_complete(rows, []), owners=rows, written=True)
        if args.payhoa:
            _complete_requests(args, client, org, forms, data_dir, rows, writes)
    return 0


def _complete_requests(args: argparse.Namespace, client: Any, org: int, forms: Any, data_dir: Path, rows: list[Any],
                       writes: list[Any]) -> None:
    """Each owner's open PayHOA request: marked complete, with the thank-you comment, once jason has recorded all of
    it (the board's rule of October 1, 2026, AGENTS.md); otherwise left open with what is left for a person. Only with
    --yes; a test account's request is never an owner's and is left alone."""
    from jason.tasks.owner_info import complete, to_complete
    from jason.tasks.payhoa_forms import record_for

    record = record_for(data_dir, forms.OWNER_INFO.key.value)
    if record is None:
        return
    status = {int(r["id"]): r.get("status") for r in client.list_form_submissions(int(record["formId"]))}
    comment = getattr(forms, "OWNER_INFO_COMPLETED_COMMENT", "")
    for item in to_complete(rows, writes):
        if status.get(item.submission_id) != "pending":
            continue
        if item.left:
            print(f"  request {item.submission_id} ({item.unit}: {item.name}) stays open: {'; '.join(item.left)}")
        elif args.yes:
            complete(client, org, item, comment)
            print(f"  request {item.submission_id} ({item.unit}: {item.name}) marked complete; the owner is thanked")
        else:
            print(f"  request {item.submission_id} ({item.unit}: {item.name}) would be marked complete (--yes)")


def _live(client: Any, org: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    units, page = [], 1
    while True:
        body = client.list_units(org, page=page)
        units.extend(body.get("data") or [])
        meta = body.get("meta") or {}
        if page >= int(meta.get("lastPage") or meta.get("last_page") or 1):
            break
        page += 1
    return units, list(client.iter_people(org))


def _prefill(args: argparse.Namespace, agent_factory: Callable[[Any], Any], community: Any, forms: Any,
             data_dir: Path) -> int:
    """Each named unit's owners' letters, with the page of what is on file read live from PayHOA, written to --out (a
    preview to look at and delete: the letters hold the owners' addresses)."""
    from jason.tasks.owner_prefill import letter_pdf, prefills
    from jason.tasks.parties import PartyResolver

    packet = data_dir / "packets" / f"owner-information-{forms.OWNER_INFO_CYCLE.year}" / "packet.pdf"
    if not packet.is_file():
        print(f"no packet at {packet}: run jason packet owner-information --build --yes first", file=sys.stderr)
        return 2
    if not args.out:
        print("--out DIR is required with --prefill (the letters hold owners' addresses; delete them after)", file=sys.stderr)
        return 2
    activity = {}
    with agent_factory(args) as agent:
        units, people = _live(agent.payhoa(), agent.org_id)
        if args.emailed:
            from jason.tasks.owner_prefill import read_activity

            activity = read_activity(agent.payhoa(), agent.org_id, {int(p["id"]): p for p in people}, today=date.today(),
                                     days=forms.SUGGESTED_CHOICES.active_days)
    found = prefills(units, people, community.payhoa_tags(), forms.OWNER_INFO,
                     deeds=PartyResolver(data_dir).latest_deed, only=args.prefill)
    out_dir = Path(args.out)
    for p in found:
        stem = f"{p.unit.replace(' ', '-').lower()}-{p.membership_id}"
        if args.emailed:                       # the form alone, filled, with the association's suggestions
            from jason.tasks.owner_prefill import fill_pdf, suggested

            extra = suggested(p, activity.get(p.membership_id), forms.SUGGESTED_CHOICES, today=date.today())
            path = fill_pdf(packet.with_name("owner-info-fillable.pdf"), p, out_dir / f"{stem}-emailed.pdf",
                            forms.OWNER_INFO, extra=extra)
            from jason.community.fillable import stamp_reference
            from jason.community.form_refs import Channel, make

            stamp_reference(path, make(forms.OWNER_INFO.code, forms.OWNER_INFO_CYCLE.year, Channel.EMAIL,
                                       membership_id=p.membership_id, unit_id=p.unit_id).text)
        else:
            path = letter_pdf(packet, p, out_dir / f"{stem}.pdf", forms.OWNER_INFO, as_of=date.today())
        filled = ", ".join(k for k, v in p.values.items() if v not in ("", None, False))
        print(f"{p.unit}: {path.name}  filled: {filled}" + (f"  ({'; '.join(p.notes)})" if p.notes else ""))
    if not found:
        print("no owners matched " + ", ".join(args.prefill))
    return 0


def _send_plan(args: argparse.Namespace, agent_factory: Callable[[Any], Any], community: Any, forms: Any,
               data_dir: Path) -> int:
    """What each owner will be sent and what each copy carries, read live; written as Markdown (no addresses)."""
    from datetime import datetime

    from jason.tasks.owner_prefill import read_activity
    from jason.tasks.owner_send import live_signals, markdown, summary

    today = date.today()
    with agent_factory(args) as agent:
        _, people = _live(agent.payhoa(), agent.org_id)
        activity = read_activity(agent.payhoa(), agent.org_id, {int(p["id"]): p for p in people}, today=today,
                                 days=forms.SUGGESTED_CHOICES.active_days)
        rows, signals, _ = live_signals(agent.payhoa(), agent.org_id, community, forms, data_dir, activity=activity,
                                        today=today)
    out = Path(args.out or data_dir / "owner-info" / f"send-plan-{today.isoformat()}.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(markdown(rows, today=today, source=f"PayHOA, live, {datetime.now():%Y-%m-%d %H:%M}", signals=signals),
                   encoding="utf-8")
    print(json.dumps(summary(rows), indent=1))
    for x in (x for x in signals if x.finding):
        print(f"  {x.unit}: {x.finding}")
    print(f"plan: {out}")
    return 0


def _only(row: Any, args: argparse.Namespace) -> bool:
    """Whether a send-plan row is one ``--only`` names: a unit whose address starts so, or ``me``, the operator's own
    unit (``payhoa_my_unit_id`` in .env), so a test to oneself never writes one's address on a command line or in docs."""
    for wanted in args.only:
        if wanted.lower() == "me":
            from jason.config import Settings

            mine = Settings.load(getattr(args, "env", None)).payhoa_my_unit_id
            if mine is None:
                raise SystemExit("--only me needs payhoa_my_unit_id in .env")
            if int(row.unit_id) == mine:
                return True
        elif row.unit.upper().startswith(wanted.upper()):
            return True
    return False


def _test_suffix(args: argparse.Namespace) -> str:
    """A test run's own batch: each test is new (the date and minute it began), so a test repeated after a change is
    sent again rather than skipped as already sent; ``--test-batch NAME`` resumes or names one."""
    from datetime import datetime

    return "-test-" + (args.test_batch or datetime.now().strftime("%Y%m%d-%H%M"))


def _form_not_live(client: Any, data_dir: Path, forms: Any, args: argparse.Namespace, message: str = "") -> bool:
    """Whether the form the letter and emails link to can't take answers (deleted, off, or another form than the link
    names). A send that points owners to a broken link stops; a dry run says so too."""
    import json as _json

    from jason.tasks.payhoa_forms import live_problem, record_for

    record = record_for(data_dir, forms.OWNER_INFO.key.value)
    values = data_dir / "packets" / f"owner-information-{forms.OWNER_INFO_CYCLE.year}" / "values.json"
    # the letter's link (the same on every copy) is checked for a letter; an email's links get each copy's unit
    link = "" if message else (
        _json.loads(values.read_text(encoding="utf-8")).get("OWNER_FORM_LINK", "") if values.is_file() else "")
    problem = "no PayHOA form is recorded for the owner information form" if record is None else         live_problem(client, record, link)
    if not problem and record is not None and message and "/app/forms/" in message             and f"/app/forms/{record['formId']}" not in message:
        problem = f"the email message links to another form than {record['formId']}: update the draft's links"
    if problem:
        print(f"stopped: {problem}", file=sys.stderr)
        return True
    return False


def _compose(message_text: str, community: Any, year: int, base_dir: Path, picture_link: Callable[[Path], str]) -> str:
    """The message every copy starts from: help filled, citations and addresses linked, the pictures put where
    ``picture_link`` says (PayHOA's upload link when sending), then the letterhead. Each copy then gets its own unit,
    links, and reference (``EmailHandler.message_for``)."""
    from jason.community.email_html import host_images, local_images, with_letterhead
    from jason.community.links import fill_help_tokens, linkify
    from jason.tasks.broadcast import body_of

    message, _ = fill_help_tokens(body_of(message_text), community.help_articles())
    message = linkify(message, subject=f"Owner Information Form {year}")
    if local_images(message):        # before the letterhead's tidy, which keeps only web links
        message = host_images(message, base_dir, picture_link)
    letterhead = community.email_letterhead()
    return with_letterhead(message, letterhead) if letterhead else message


def _write_preview(out: Path, message_text: str, community: Any, year: int, base_dir: Path, row: Any, forms: Any,
                   subject: str, data_dir: Path) -> None:
    """The email as one owner receives it, sending nothing: the first copy in the plan (or of --only), pictures shown
    from the files on disk, PayHOA's {first name} left for PayHOA."""
    import base64
    import html as _html

    from jason.tasks.owner_send import EmailHandler

    shown: dict[str, Path] = {}

    def stand_in(path: Path) -> str:                   # a web-style link the letterhead tidy keeps, swapped below
        link = f"https://preview.invalid/{len(shown)}/{path.name}"
        shown[link] = path
        return link

    handler = EmailHandler.__new__(EmailHandler)
    handler.message, handler.google_form, handler.subject = _compose(message_text, community, year, base_dir,
                                                                     stand_in), None, subject
    handler.data_dir, handler.form, handler.year = data_dir, forms.OWNER_INFO, year
    reference = handler.reference(row.membership_id, row.unit_id)
    body = handler.message_for(reference, row.unit, row.unit_id)
    for link, path in shown.items():
        body = body.replace(link, "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode())
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(f"<!doctype html><meta charset='utf-8'><title>{_html.escape(handler.subject_for(reference, row.unit))}"
                   f"</title><p style='color:#666'>Subject: {_html.escape(handler.subject_for(reference, row.unit))}</p>"
                   f"{body}", encoding="utf-8")
    print(f"preview: {out} (as {row.unit} receives it; nothing sent)")


def _email_batch(args: argparse.Namespace, agent_factory: Callable[[Any], Any], community: Any, forms: Any,
                 data_dir: Path) -> int:
    """Each owner's own emailed copy, as a batch: planned from PayHOA read live, recorded in the ledger, then sent one
    at a time, slowly, resuming where the last run stopped (``jason.batches``). Without --yes it says what it would do."""
    from datetime import datetime, timezone

    from jason import batches
    from jason.community.email_html import with_letterhead
    from jason.tasks.broadcast import body_of
    from jason.community.form_refs import Channel
    from jason.tasks.delivery_engines import ENGINES
    from jason.tasks.owner_prefill import read_activity
    from jason.tasks.owner_send import send_plan
    from jason.tasks.parties import PartyResolver

    engine = ENGINES[Channel.EMAIL]
    year, today = forms.OWNER_INFO_CYCLE.year, date.today()
    batch_id = engine.batch_id(forms.OWNER_INFO, year)
    sent_to: set[tuple[int, int]] | None = None
    if args.follow_up:
        # a follow-up goes to the owners the first batch reached, in its own batch: their filled form again, or
        # (--attach) one file for everyone
        if not args.message:
            print("--follow-up needs --message HTML (and --attach PDF to attach that instead of the filled form)",
                  file=sys.stderr)
            return 2
        sent_to = {(int(i.payload["membershipId"]), int(i.payload["unitId"])) for i in batches.items(data_dir, batch_id)
                   if i.status is batches.ItemStatus.SENT}
        if not sent_to:
            print(f"no sent items in {batch_id} to follow up", file=sys.stderr)
            return 2
        batch_id += f"-{args.follow_up}"
    if args.only:
        batch_id += _test_suffix(args)  # a test for a few units keeps out of the real batch's ledger
    form_pdf = Path(args.attach) if args.attach else data_dir / "packets" / f"owner-information-{year}" / "owner-info-fillable.pdf"
    message_file = Path(args.message or data_dir / "drafts" / "owner-information-email-prefilled.html")
    if not form_pdf.is_file() or not message_file.is_file():
        print(f"need {form_pdf} and {message_file}", file=sys.stderr)
        return 2
    from jason.community.markdown_html import message_html

    message_text = message_html(message_file.read_text(encoding="utf-8"), message_file.suffix)   # Markdown or HTML
    with agent_factory(args) as agent:
        client, org = agent.payhoa(), agent.org_id
        if _form_not_live(client, data_dir, forms, args, message_text):
            return 2
        units, people = _live(client, org)
        activity = read_activity(client, org, {int(p["id"]): p for p in people}, today=today,
                                 days=forms.SUGGESTED_CHOICES.active_days)
        rows = send_plan(units, people, community.payhoa_tags(), forms.OWNER_INFO,
                         community.notice_rule("owner-info-solicitation"), forms.SUGGESTED_CHOICES, activity,
                         deeds=PartyResolver(data_dir).latest_deed, today=today)
        if args.only:
            rows = [r for r in rows if _only(r, args)]
        else:                          # a test account gets the real send only when a test asks for its unit
            from jason.config import test_memberships

            tests = test_memberships(getattr(args, "env", None))
            rows = [r for r in rows if r.membership_id not in tests]
        if sent_to is not None and not args.only:
            rows = [r for r in rows if (r.membership_id, r.unit_id) in sent_to]
        items = engine.items(rows, units, community.payhoa_tags())
        pace = engine.pace()
        minutes = len(items) * (pace.interval + pace.jitter / 2 + pace.step) / 60
        print(f"{len(items)} emailed copies; one at a time, about {minutes:.0f} minutes; batch {batch_id}")
        if not args.yes:
            from jason.community.email_html import local_images

            for name in local_images(message_text):
                found = (message_file.parent / name).is_file()
                print(f"  picture {name}: {'uploaded when sent' if found else 'MISSING'}")
            for key, label, _ in items[:args.show]:
                print(f"  {label}")
            if args.preview and rows:
                _write_preview(Path(args.preview), message_text, community, year, message_file.parent, rows[0],
                               forms, args.subject, data_dir)
            print("Dry run: add --yes --confirmed-by NAME to record and send them (--limit N sends the first N).")
            return 0
        if not args.confirmed_by:
            print("--confirmed-by NAME is required to send", file=sys.stderr)
            return 2
        batches.create(data_dir, batch_id, "owner-info-email",
                       f"Owner information request {year}: " + (f"follow-up ({args.follow_up})" if args.follow_up
                                                                 else "emailed copies"),
                       items, confirmed_by=args.confirmed_by, params={"subject": args.subject})
        message = _compose(message_text, community, year, message_file.parent, lambda path: client.upload_file(
            path, filename=path.name, content_type="image/png", context="communication")["viewUrl"])
        google_form, channel = None, getattr(forms, "GOOGLE_FORMS", {}).get(forms.OWNER_INFO.key)
        if channel and channel.form_id and "{GOOGLE_FORM_LINK}" in message:   # each owner's personal link
            from jason.google.forms import GoogleForms

            google_form = GoogleForms.on(agent.drive()).get(channel.form_id)
        handler = engine.handler(client, org, rows, form=forms.OWNER_INFO, form_pdf=form_pdf, subject=args.subject,
                               message=message, sender=args.sender or client.reply_email(org),
                               since=batches.batch(data_dir, batch_id)["created"], filename=f"Owner Information Form {year}.pdf",
                               choices=forms.SUGGESTED_CHOICES, activity=activity, people=people, today=today,
                               data_dir=data_dir, year=year, google_form=google_form,
                               google_reference=channel.reference if channel else "",
                               attachment=Path(args.attach) if args.attach else None)
        counts = batches.run(data_dir, batch_id, handler, pace=pace, limit=args.limit,
                             remaining=lambda: getattr(client, "rate_remaining", None))
    print("now: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())) + f"  (jason batches --show {batch_id})")
    return 0


def _mail_batch(args: argparse.Namespace, agent_factory: Callable[[Any], Any], community: Any, forms: Any,
                data_dir: Path) -> int:
    """The letters, as a batch: the same letter (cover and blank form) to every owner the law sends mail, one Mailroom
    send per building, slowly, resuming where the last run stopped. The Mailroom prints, mails, and charges the
    association; without --yes this says what it would do."""
    from jason import batches
    from jason.community.form_refs import Channel
    from jason.tasks import form_references
    from jason.tasks.delivery_engines import ENGINES
    from jason.tasks.owner_send import send_plan

    engine = ENGINES[Channel.MAIL]
    year, today = forms.OWNER_INFO_CYCLE.year, date.today()
    batch_id = engine.batch_id(forms.OWNER_INFO, year)
    if args.only:
        # a letter is one Mailroom send per building, keyed by the building: a run for a few units (a test) gets its
        # own batch, or the real batch would count those buildings as mailed and skip their other owners
        batch_id += _test_suffix(args)
    packet = data_dir / "packets" / f"owner-information-{year}" / "packet.pdf"
    if not packet.is_file():
        print(f"no letter at {packet}: run jason packet owner-information --build --yes first", file=sys.stderr)
        return 2
    # The letter as mailed: the packet with the campaign's marker (every copy the same, so one marker for all).
    marker = engine.marker(forms.OWNER_INFO, year).text
    pdf = engine.letter(packet, forms.OWNER_INFO, year, packet.with_name("packet-mailed.pdf"))
    with agent_factory(args) as agent:
        client, org = agent.payhoa(), agent.org_id
        if _form_not_live(client, data_dir, forms, args):
            return 2
        units, people = _live(client, org)
        rows = send_plan(units, people, community.payhoa_tags(), forms.OWNER_INFO,
                         community.notice_rule("owner-info-solicitation"), forms.SUGGESTED_CHOICES, {}, today=today)
        if args.only:
            keep = {r.unit_id for r in rows if _only(r, args)}
            units = [u for u in units if int(u["id"]) in keep]
        items = engine.items(rows, units, community.payhoa_tags())
        handler = engine.handler(client, org, data_dir, pdf=pdf, double_sided=args.double_sided)
        print(f"{len(items)} Mailroom sends of the same {handler.pages}-page letter, marked {marker}; batch {batch_id}")
        if not args.yes:
            letters = 0
            for key, label, payload in items:
                who = handler.recipients(batches.Item(batch_id, key, label, payload))
                letters += len(who)
                print(f"  {label}: {len(who)} letter(s) to {len(payload['ownerIds'])} owner(s)")
            print(f"{letters} letters. Dry run (PayHOA was asked whom each reaches; nothing mailed): add --yes "
                  "--confirmed-by NAME to mail them (--limit N sends the first N buildings).")
            return 0
        if not args.confirmed_by:
            print("--confirmed-by NAME is required to mail", file=sys.stderr)
            return 2
        batches.create(data_dir, batch_id, "owner-info-mail", f"Owner information request {year}: letters",
                       items, confirmed_by=args.confirmed_by,
                       params={"pdf": str(pdf), "pages": handler.pages, "marker": marker})
        form_references.record(data_dir, marker, form=forms.OWNER_INFO.key.value, year=year, channel=engine.channel.name,
                               identity=engine.identity.value, batch=batch_id)
        counts = batches.run(data_dir, batch_id, handler, pace=engine.pace(), limit=args.limit,
                             remaining=lambda: getattr(client, "rate_remaining", None))
    print("now: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())) + f"  (jason batches --show {batch_id})")
    return 0


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("owner-info", help="The owner information cycle (CIV 4040, 4041): standing, deadlines, and PayHOA updates")
    add_common(p)
    p.add_argument("--payhoa", action="store_true", help="also read the PayHOA form's signed-in submissions (live)")
    p.add_argument("--out", help="write the ledger, one row an owner (names; no addresses); with --prefill, the folder")
    p.add_argument("--mail-batch", action="store_true",
                   help="mail the same letter to every owner the law sends mail, one Mailroom send per building, as a "
                        "resumable batch (dry run without --yes)")
    p.add_argument("--double-sided", action="store_true", help="with --mail-batch: print on both sides")
    p.add_argument("--email-batch", action="store_true",
                   help="email each owner their own filled copy, slowly, as a resumable batch (dry run without --yes)")
    p.add_argument("--only", action="append", default=[], metavar="UNIT", help="with --email-batch or --mail-batch: only these units (an address's start, or me: payhoa_my_unit_id in .env)")
    p.add_argument("--limit", type=int, help="with a batch: stop after sending this many items")
    p.add_argument("--confirmed-by", help="with a batch and --yes: the person who confirmed the send")
    p.add_argument("--subject", default="Owner information request: how would you like to receive Association notices?",
                   help="with --email-batch: the subject")
    p.add_argument("--test-batch", metavar="NAME", default="",
                   help="with --only: the test batch to resume (default: a new one, named by the time it began)")
    p.add_argument("--message", help="with --email-batch: the message, Markdown (.md) or HTML (default data/drafts/owner-information-email-prefilled.html)")
    p.add_argument("--sender", help="with --email-batch: the From address (default PayHOA's reply-to)")
    p.add_argument("--follow-up", metavar="NAME", default="",
                   help="with --email-batch: a follow-up (an updated copy, a correction) to the owners the email batch "
                        "reached, in its own batch; needs --message")
    p.add_argument("--preview", metavar="HTML",
                   help="with --email-batch (dry run): write the email as the first owner (or --only's) receives it")
    p.add_argument("--attach", metavar="PDF", help="with --follow-up: one file attached instead of each owner's filled form")
    p.add_argument("--send-plan", action="store_true",
                   help="write what each owner will be sent and what each copy carries (read live; no addresses)")
    p.add_argument("--emailed", action="store_true",
                   help="with --prefill: the emailed copy (the form filled, with the suggested choices) instead of the letter")
    p.add_argument("--prefill", action="append", default=[], metavar="UNIT",
                   help="write the pre-filled letter for each owner of the unit(s) whose address starts so (read live)")
    p.add_argument("--apply", action="store_true", help="read PayHOA live and list the writes that bring it up to date")
    p.add_argument("--show", type=int, default=15, help="with --apply: how many writes to list (default 15)")
    p.add_argument("--yes", action="store_true", help="with --apply: write them in PayHOA")
    p.set_defaults(func=lambda a: cmd_owner_info(a, agent_factory))
