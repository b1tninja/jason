"""``jason draft`` and ``jason forms``: Gmail drafts for a person to send, and the association's request forms.

Both are dry runs by default: they print what would be created. ``--yes`` creates the Gmail draft or the Google Form.
jason never sends email; a draft waits in Gmail for a person.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any, Callable


def _data_dir(args: argparse.Namespace) -> Path:
    from jason.config import Settings

    return Settings.load(args.env).payhoa_catalog.parent


def cmd_draft(args: argparse.Namespace, agent_factory: Callable[[Any], Any]) -> int:
    from jason.community import mystique
    from jason.google.gmail_drafts import GmailDrafts
    from jason.tasks.drafts import find_hearing, hearing_draft, meeting_notice_draft, save

    data_dir = _data_dir(args)
    association = mystique().name
    if args.list:
        with agent_factory(args) as agent:
            gmail = GmailDrafts.on(agent.drive())
            for row in gmail.list():
                saved = gmail.get(row["id"])
                print(f"{saved.id}  to: {', '.join(saved.to) or '(none)'}  {saved.subject}")
        return 0
    if args.show or args.edit:
        return _show_or_edit(args, agent_factory)
    if not args.to:
        print("--to is required: the recipient's address, given by the person", file=sys.stderr)
        return 2
    if args.hearing:
        try:
            hearing = find_hearing(data_dir, args.hearing)
        except (FileNotFoundError, LookupError) as exc:
            print(exc, file=sys.stderr)
            return 1
        pdf = None
        if args.pdf:
            doc = hearing.get("noticeDoc") or {}
            if not doc.get("id"):
                print("the hearing has no notice Doc to export; run `jason hearing --doc` first", file=sys.stderr)
                return 1
            pdf = data_dir / "zoom" / "hearings" / f"Notice of Hearing {hearing['start'][:10]}.pdf"
            with agent_factory(args) as agent:
                agent.drive().docs().export_pdf(doc["id"], pdf)
        plan = hearing_draft(hearing, args.to, association, pdf=pdf)
    elif args.meeting_notice:
        try:
            plan = meeting_notice_draft(data_dir, date.fromisoformat(args.meeting_notice), args.to, association)
        except FileNotFoundError as exc:
            print(exc, file=sys.stderr)
            return 1
    else:
        print("give --hearing ADDRESS or --meeting-notice DATE", file=sys.stderr)
        return 2
    for line in plan.lines():
        print(line)
    if not args.yes:
        print("Dry run: add --yes to save this as a Gmail draft (it is not sent).")
        return 0
    with agent_factory(args) as agent:
        created = save(plan, GmailDrafts.on(agent.drive()))
    print(f"Gmail draft {created.get('id')} created; review and send it from Gmail.")
    return 0


def cmd_forms(args: argparse.Namespace, agent_factory: Callable[[Any], Any]) -> int:
    from jason.google.forms import GoogleForms
    from jason.tasks.forms import create, fetch_responses, load_rows, plan_lines, template

    data_dir = _data_dir(args)
    if args.create:
        tpl = template(args.create)
        for line in plan_lines(tpl):
            print(line)
        from jason.community.spec import spec_module

        channel = getattr(spec_module("forms"), "GOOGLE_FORMS", {}).get(tpl.key)
        if channel:
            print(f"  + {channel.reference} (optional; an owner's personal link fills it)")
            print(f"  respondent email: {channel.email.value}; created unpublished (publish with --publish ID --yes)")
        if not args.yes:
            print("Dry run: add --yes to create this form in Google Forms.")
            return 0
        with agent_factory(args) as agent:
            values = {}
            cycle = getattr(spec_module("forms"), "OWNER_INFO_CYCLE", None)
            if cycle is not None and cycle.return_by:          # the preamble's answer-by date
                values["RETURN_BY"] = f"{cycle.return_by:%A, %B} {cycle.return_by.day}, {cycle.return_by.year}"
            record = create(GoogleForms.on(agent.drive()), tpl, data_dir, channel=channel, values=values)
        print(f"Form {record['formId']} created, unpublished: {record.get('responderUri')}")
        if channel:
            print("record form_id and responder_uri in GOOGLE_FORMS in mystique/forms.py")
        return 0
    if args.publish:
        state = "unpublish" if args.unpublish else "publish"
        if not args.yes:
            print(f"Dry run: --yes would {state} form {args.publish}; published, anyone with the link can answer.")
            return 0
        with agent_factory(args) as agent:
            GoogleForms.on(agent.drive()).publish(args.publish, published=not args.unpublish)
        print(f"form {args.publish}: {state}ed")
        return 0
    if args.responses:
        if not args.offline:
            with agent_factory(args) as agent:
                path = fetch_responses(GoogleForms.on(agent.drive()), args.responses, data_dir)
            print(f"Saved {path}", file=sys.stderr)
        rows = load_rows(data_dir, args.responses)
        if args.json:
            print(json.dumps(rows, indent=1))
        else:
            for row in rows:
                print(" | ".join(f"{k}: {v}" for k, v in row.items() if k != "responseId"))
            print(f"{len(rows)} response(s)")
        return 0
    if args.pdf:
        return _form_pdf(args, data_dir)
    if args.read:
        return _read_pdfs(args)
    if args.match:
        return _match(args, agent_factory, data_dir)
    if args.payhoa:
        return _payhoa_form(args, agent_factory, data_dir)
    if args.payhoa_submissions:
        return _payhoa_submissions(args, agent_factory, data_dir)
    if args.payhoa_test:
        return _payhoa_test(args, agent_factory, data_dir)
    print("give --create, --responses, --pdf, or --read", file=sys.stderr)
    return 2


def _form_pdf(args: argparse.Namespace, data_dir: Path) -> int:
    """A fillable PDF of a form, from its definition, on the letterhead; nothing is sent or uploaded."""
    from jason.community import mystique
    from jason.tasks.forms import form_pdf, template

    tpl = template(args.pdf)
    prefill = dict(p.split("=", 1) for p in args.prefill)
    out = Path(args.out) if args.out else data_dir / "forms" / f"{tpl.key.value}.pdf"
    names = form_pdf(tpl, out, association=mystique().name, logo=data_dir / "brand" / "letterhead-logo.png",
                     prefill=prefill or None)
    print(f"{out}: {len(names)} fields: {', '.join(names)}")
    return 0


def _payhoa_form(args: argparse.Namespace, agent_factory: Callable[[Any], Any], data_dir: Path) -> int:
    """Make a definition's form in PayHOA's builder. Without --yes it prints the questions and changes nothing."""
    from jason.tasks.forms import template
    from jason.tasks.payhoa_forms import questions_for, record_for

    tpl = template(args.payhoa)
    print(f"PayHOA form: {tpl.title} (requires a unit; the unit's address is not asked)")
    for n, q in enumerate(questions_for(tpl), 1):
        extra = f" [{' / '.join(q.options)}]" if q.options else ""
        print(f"  {n:2}. {q.kind:8} {q.label}{' (required)' if q.required else ''}{extra}")
    existing = record_for(data_dir, tpl.key.value)
    if args.update:
        # edit the recorded form in place, as PayHOA's editor saves: kept questions keep their ids and answers
        from jason.community.spec import spec_module
        from jason.tasks.payhoa_forms import form_values, update

        if existing is None:
            print("no PayHOA form recorded for this definition: create it first", file=sys.stderr)
            return 1
        with agent_factory(args) as agent:
            try:
                changes = update(agent.payhoa(), agent.org_id, tpl, data_dir, dry_run=not args.yes,
                                 values=form_values(spec_module("forms").OWNER_INFO_CYCLE))
            except RuntimeError as exc:
                print(exc, file=sys.stderr)
                return 1
        print(f"form {existing['formId']}: {changes['kept']} questions kept (their answers stay tied to them), "
              f"{len(changes['added'])} added" + (f": {', '.join(changes['added'])}" if changes["added"] else "")
              + (f"; reworded: {'; '.join(changes['reworded'])}" if changes.get("reworded") else "")
              + (f"; help changed: {'; '.join(changes['help changed'])}" if changes.get("help changed") else "")
              + ("; saved and read back" if args.yes else "; dry run: add --yes to save the edit in PayHOA"))
        return 0
    if existing and existing.get("locked"):
        print(f"form {existing['formId']} is live and locked ({existing['locked']}): it is never deleted or made "
              f"again; change it with --update")
        if args.replace or args.yes:
            return 1
    elif existing:
        print(f"already made: form {existing['formId']} on {existing['created'][:10]}; "
              + ("--replace deletes it (if it has no submissions) and makes it again" if args.replace
                 else "another would be a second form (--replace to make it again)"))
    if not args.yes:
        print("Dry run: add --yes to create it in PayHOA (switched off until a person turns it on, or --enable).")
        return 0
    from jason.community.spec import spec_module
    from jason.tasks.payhoa_forms import create, form_values, replace

    values = form_values(spec_module("forms").OWNER_INFO_CYCLE)
    with agent_factory(args) as agent:
        make = replace if args.replace else create
        try:
            record = make(agent.payhoa(), agent.org_id, tpl, data_dir, enable=args.enable, values=values)
        except RuntimeError as exc:
            print(exc, file=sys.stderr)
            return 1
    print(f"made PayHOA form {record['formId']} ({'on' if record['enabled'] else 'off'}); recorded in data/payhoa/forms.json")
    return 0


def _payhoa_test(args: argparse.Namespace, agent_factory: Callable[[Any], Any], data_dir: Path) -> int:
    """Submit made-up answers to every question as the test owner, read them back as the admin, and compare: the
    whole path an owner's answer takes. The submission stays in PayHOA as the test account's (never an owner's)."""
    from jason.community.spec import spec_module
    from jason.tasks.forms import template
    from jason.tasks.payhoa_forms import record_for, round_trip, sample_values

    tpl = template(args.payhoa_test)
    record = record_for(data_dir, tpl.key.value)
    if record is None:
        print("no PayHOA form recorded for this definition", file=sys.stderr)
        return 1
    from jason.config import test_memberships

    tests = test_memberships(getattr(args, "env", None))
    values = sample_values(tpl)
    print(f"form {record['formId']}: {len(values)} made-up answers from the test owner")
    if not args.yes:
        print("dry run: add --yes to submit them as the test owner and read them back")
        return 0
    with agent_factory(args) as agent:
        admin, owner, org = agent.payhoa(), agent.payhoa_test(), agent.org_id
        member = int(owner.token_claims.get("memberId") or 0)
        if member not in tests:
            print(f"the test login is membership {member}, which payhoa_test_membership_ids in .env does not name: stopped", file=sys.stderr)
            return 1
        unit = int(owner.token_claims.get("unitId") or 0)
        submission, wrong = round_trip(admin, owner, org, tpl, record, unit, values)
    print(f"submission {submission}: " + ("every answer read back as sent" if not wrong else f"{len(wrong)} differ"))
    for w in wrong:
        print(f"  {w}")
    return 0 if not wrong else 1


def _payhoa_submissions(args: argparse.Namespace, agent_factory: Callable[[Any], Any], data_dir: Path) -> int:
    """The PayHOA form's submissions read by field, checked, and matched to the current owners (signed in: by member)."""
    import csv

    from jason.community import mystique
    from jason.community.forms import answer_rows
    from jason.community.spec import spec_module
    from jason.config import Settings
    from jason.tasks.forms import template
    from jason.tasks.member_preferences import REVIEW_HEADER, match, payhoa_owners, review_rows, summary
    from jason.tasks.parties import PartyResolver
    from jason.tasks.payhoa_forms import fetch_submissions, record_for

    tpl = template(args.payhoa_submissions)
    record = record_for(data_dir, tpl.key.value)
    if record is None:
        print(f"no PayHOA form made from {tpl.key.value} yet (jason forms --payhoa {tpl.key.value} --yes)", file=sys.stderr)
        return 2
    with agent_factory(args) as agent:
        answers = fetch_submissions(agent.payhoa(), agent.org_id, record, tpl)
    header, rows = answer_rows(tpl, answers)
    out = Path(args.out) if args.out else data_dir / "payhoa" / f"form-{record['formId']}-answers.csv"
    with open(out, "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows([header, *rows])
    matched = match(answers, payhoa_owners(Settings.load(args.env).payhoa_catalog, PartyResolver(data_dir).latest_deed),
                    mystique().payhoa_tags(), cycle=spec_module("forms").OWNER_INFO_CYCLE)
    review = out.with_name(out.stem + "-review.csv")
    with open(review, "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows([REVIEW_HEADER, *review_rows(matched)])
    print(f"{len(answers)} submission(s): answers {out}; review {review}")
    print(json.dumps(summary(matched), indent=1))
    return 0


def _match(args: argparse.Namespace, agent_factory: Callable[[Any], Any], data_dir: Path) -> int:
    """A Google Form's responses read into the association's definition (``FORM_IMPORTS``) and set beside PayHOA's
    current owners: a summary here, the review row by row in data/forms/<id>/payhoa-review.csv (local only). Nothing is
    written to PayHOA."""
    import csv

    from jason.community.spec import spec_module
    from jason.config import Settings
    from jason.google.forms import GoogleForms
    from jason.tasks.forms import fetch_responses, forms_dir, import_responses
    from jason.tasks.member_preferences import REVIEW_HEADER, match, payhoa_owners, review_rows, summary

    rules = next((r for r in spec_module("forms").FORM_IMPORTS if r.source == args.match), None)
    if rules is None:
        print(f"no import rules for form {args.match} in mystique/forms.py FORM_IMPORTS", file=sys.stderr)
        return 2
    if not args.offline:
        with agent_factory(args) as agent:
            fetch_responses(GoogleForms.on(agent.drive()), args.match, data_dir)
    saved = json.loads((forms_dir(data_dir) / args.match / "responses.json").read_text(encoding="utf-8"))
    from jason.community import mystique
    from jason.tasks.parties import PartyResolver

    forms = spec_module("forms")
    deeds = PartyResolver(data_dir).latest_deed               # when each unit last changed hands, from the county
    matched = match(import_responses(saved, rules), payhoa_owners(Settings.load(args.env).payhoa_catalog, deeds),
                    mystique().payhoa_tags(), cycle=forms.OWNER_INFO_CYCLE)
    out = Path(args.out) if args.out else forms_dir(data_dir) / args.match / "payhoa-review.csv"
    with open(out, "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows([REVIEW_HEADER, *review_rows(matched)])
    print(f"{rules.title}: {rules.note}")
    print(json.dumps(summary(matched), indent=1))
    print(f"review (local; names and emails, no addresses): {out}")
    return 0


def _read_pdfs(args: argparse.Namespace) -> int:
    """Read returned fillable PDFs by question and check each against the form; print the rows, or write a CSV."""
    import csv

    from jason.tasks.forms import read_pdfs, template

    if not args.form:
        print("--read needs --form (the form the PDFs are)", file=sys.stderr)
        return 2
    header, rows = read_pdfs(template(args.form), [Path(p) for p in args.read])
    if args.out:
        with open(args.out, "w", newline="", encoding="utf-8") as fh:
            csv.writer(fh).writerows([header, *rows])
        print(f"{len(rows)} response(s) written to {args.out}")
    elif args.json:
        print(json.dumps([dict(zip(header, row)) for row in rows], indent=1))
    else:
        for row in rows:
            print(" | ".join(f"{h}: {v}" for h, v in zip(header, row) if v))
    problems = sum(1 for row in rows if row[-1])
    if problems:
        print(f"{problems} response(s) with problems to review", file=sys.stderr)
    return 0


def _show_or_edit(args: argparse.Namespace, agent_factory: Callable[[Any], Any]) -> int:
    """Show a saved draft, or refine it in place: --replace OLD NEW (repeatable), --subject, --body-file, --to.
    Without --yes the diff is printed and nothing changes."""
    from jason.google.errors import GoogleError
    from jason.google.gmail_drafts import GmailDrafts

    with agent_factory(args) as agent:
        gmail = GmailDrafts.on(agent.drive())
        if args.show:
            d = gmail.get(args.show)
            print(f"To: {', '.join(d.to) or '(none)'}\nCc: {', '.join(d.cc) or '(none)'}\nSubject: {d.subject}")
            if d.attachments:
                print(f"Attachments: {', '.join(d.attachments)}")
            print("\n" + d.text)
            return 0
        body = Path(args.body_file).read_text(encoding="utf-8") if args.body_file else None
        try:
            edit = gmail.edit(args.edit, replace=tuple(tuple(r) for r in args.replace or ()), subject=args.subject,
                              text=body, to=tuple(args.to.split(",")) if args.to else (), yes=args.yes)
        except GoogleError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        if not edit.changed:
            print("no change")
            return 0
        print(edit.diff())
        print("\nupdated in place (not sent)" if args.yes else "\ndry run: add --yes to update the draft in place (never sent)")
    return 0


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    draft = sub.add_parser("draft", help="Save a hearing or meeting notice as a Gmail draft (never sends)")
    add_common(draft)
    which = draft.add_mutually_exclusive_group()
    which.add_argument("--hearing", metavar="ADDRESS", help="the saved hearing for this unit address")
    which.add_argument("--meeting-notice", metavar="DATE", help="the agenda data/board/agenda-DATE.md")
    which.add_argument("--list", action="store_true", help="list the mailbox's drafts")
    which.add_argument("--show", metavar="DRAFT_ID", help="print a saved draft")
    which.add_argument("--edit", metavar="DRAFT_ID", help="refine a saved draft in place (diff first; --yes updates)")
    draft.add_argument("--replace", nargs=2, action="append", metavar=("OLD", "NEW"),
                       help="with --edit: replace text (repeatable; each OLD must be found)")
    draft.add_argument("--subject", help="with --edit: a new subject")
    draft.add_argument("--body-file", help="with --edit: the new text from a file")
    draft.add_argument("--to", metavar="EMAIL", help="recipient, given by the person")
    draft.add_argument("--pdf", action="store_true", help="attach the notice Doc as PDF instead of linking it")
    draft.add_argument("--yes", action="store_true", help="create the draft (default: dry run)")
    draft.set_defaults(func=lambda a: cmd_draft(a, agent_factory))

    forms = sub.add_parser("forms", help="Create the association's request forms and read their responses")
    add_common(forms)
    act = forms.add_mutually_exclusive_group()
    act.add_argument("--create", choices=("idr", "records", "owner-info"), help="create a form from its template")
    act.add_argument("--responses", metavar="FORM_ID", help="fetch and list a form's responses")
    act.add_argument("--publish", metavar="FORM_ID", help="publish a Google Form (with --yes): anyone with the link can answer")
    forms.add_argument("--unpublish", action="store_true", help="with --publish: take the form down instead")
    act.add_argument("--pdf", choices=("idr", "records", "owner-info"),
                     help="make a fillable PDF of a form from its definition (no Doc; printed by Chrome or Edge)")
    act.add_argument("--read", nargs="+", metavar="PDF", help="read returned fillable PDFs (with --form) and check them")
    act.add_argument("--payhoa", choices=("idr", "records", "owner-info"),
                     help="make a form in PayHOA's form builder from its definition (dry run; --yes creates it, switched off)")
    act.add_argument("--payhoa-test", choices=("idr", "records", "owner-info"),
                     help="submit made-up answers to every question as the test owner (payhoa_test_record_uid), "
                          "read them back as the admin, and compare (with --yes)")
    act.add_argument("--payhoa-submissions", choices=("idr", "records", "owner-info"),
                     help="read the PayHOA form's submissions by field, check them, and match them to PayHOA's owners")
    forms.add_argument("--enable", action="store_true", help="with --payhoa --yes: leave the new form on for owners")
    forms.add_argument("--replace", action="store_true",
                       help="with --payhoa --yes: delete the form made before (only if it has no submissions) and make it again")
    forms.add_argument("--update", action="store_true",
                       help="with --payhoa: edit the recorded form in place to match the definition, keeping each "
                            "question's id and answers (dry run without --yes; refuses to drop a question)")
    act.add_argument("--match", metavar="FORM_ID",
                     help="read a Google Form's responses by its import rules and match them to PayHOA's current owners")
    forms.add_argument("--form", choices=("idr", "records", "owner-info"), help="with --read: the form the PDFs are")
    forms.add_argument("--out", help="with --pdf: where to write it (default data/forms/<form>.pdf); with --read: a CSV")
    forms.add_argument("--prefill", action="append", default=[], metavar="FIELD=VALUE",
                       help="with --pdf: set a field for one recipient (repeatable), e.g. unit-address=\"<the unit's address>\"")
    forms.add_argument("--offline", action="store_true", help="read the saved responses without fetching")
    forms.add_argument("--json", action="store_true")
    forms.add_argument("--yes", action="store_true", help="create the form (default: dry run)")
    forms.set_defaults(func=lambda a: cmd_forms(a, agent_factory))
