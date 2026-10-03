"""``jason rule-change``: carry a proposed operating rule change through Civil Code 4360.

Writes ``data/board/rule-change-<slug>.md``: the member notice of the proposed change (28 days before the board
decides), the agenda item for the decision meeting, and the notice of adoption (15 days after). The decision meeting
defaults to the first meeting on the schedule at least 28 days after the notice date. Each section's current words are
read through the shared reader (the living document or the outline, by address), and the proposed text is cited as its
own stage version (``KEY@proposed-DATE``).

``--from-manual`` drafts the board's 4360 course for publishing the official rules extracted from the owner's manual:
the text of the proposed rule change is the official rules document with its concordance, the passages changed with no
adoption found are proposed with their earlier words, and the Doc's pending suggestions are left out. It writes
``data/drafts/rule-change-official-rules-<notice date>.md`` and nothing else.

``--draft-email`` previews the member notice as a Gmail draft with no recipients; ``--draft-email --yes`` saves it and
keeps its text, subject, and the sections it recites in ``data/notices/KEY/`` (``jason.tasks.notice_text``; KEY is
``rule-change-proposed-CHANGE-NOTICEDATE`` unless ``--notice`` names it). jason never sends email: a person addresses
the draft and sends it from Gmail.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path
from typing import Any, Callable


def _data_dir(args: argparse.Namespace) -> Path:
    from jason.config import Settings

    return Settings.load(args.env).payhoa_catalog.parent


def _timeline(args: argparse.Namespace, schedule: Any):
    from jason.tasks import rule_change as rc

    notice_date = date.fromisoformat(args.notice_date) if args.notice_date else date.today()
    decision = date.fromisoformat(args.decision) if args.decision else None
    comment = date.fromisoformat(args.comment_deadline) if args.comment_deadline else None
    return rc.timeline(schedule, notice_date=notice_date, decision=decision, monthly=not args.regular_months_only,
                       comment_deadline=comment, fiscal_year_end=date((decision or notice_date).year, 12, 31))


def cmd_from_manual(args: argparse.Namespace) -> int:
    from jason.community import community as active
    from jason.community.manual import ManualError
    from jason.tasks import manual as manual_task
    from jason.tasks import manual_rule_change as mrc
    from jason.tasks import rule_change as rc

    community = active()
    schedule = community.meeting_schedule()
    try:
        when = _timeline(args, schedule)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    data_dir = _data_dir(args)
    try:
        part = mrc.partition(data_dir, community)
        spec = manual_task.spec_of(community)
    except ManualError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    shelf = rc.open_shelf(data_dir, community)
    law = rc.recite_law(shelf)
    book = shelf.books.key("rules")
    markdown = mrc.render(part, when, community.name, schedule, law=law, book_titles=spec.book_titles, book=book)
    path = mrc.write(data_dir, when.notice_date, markdown)
    carried = [s for s in part.suggestions if s.in_draft]
    print(f"Saved {path} (a draft; nothing is sent)")
    print(f"(b) changed with no adoption found: {len(part.official)} in the official rules, {len(part.other_rules)} in "
          f"the policies bound in the manual; (c) pending suggestions: {len(part.suggestions)}, {len(carried)} carried "
          f"by the official rules draft; {len(part.unplaced)} changes not placed (listed for a person).")
    print(f"Notice by {when.notice_by}; decision {when.decision}; adoption notice by {when.adoption_notice_by}.")
    return 0


def cmd_rule_change(args: argparse.Namespace, agent_factory: Callable[[Any], Any]) -> int:
    from jason.community import community as active
    from jason.tasks import rule_change as rc

    if getattr(args, "from_manual", False):
        return cmd_from_manual(args)
    community = active()
    changes = tuple(community.rule_changes())
    if args.list or not args.change:
        for change in changes:
            print(f"{change.key}  {change.title}")
        return 0
    try:
        change = rc.find_change(changes, args.change)
    except LookupError as exc:
        print(exc, file=sys.stderr)
        return 2
    schedule = community.meeting_schedule()
    try:
        when = _timeline(args, schedule)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    data_dir = _data_dir(args)
    shelf = rc.open_shelf(data_dir, community)
    recitals = rc.recite_sections(change, shelf=shelf, data_dir=data_dir)
    current = rc.words_of(recitals)
    if not current:
        print(f"note: no current text for {change.document} on the shelf or in data/outlines (run jason outlines)",
              file=sys.stderr)
    misses = [r.number for r in recitals.values() if r.source == "outline"]
    if misses:
        print(f"note: read from the outline directly, the shelf could not place: {', '.join(misses)}", file=sys.stderr)
    law = rc.recite_law(shelf)
    book = shelf.books.key(change.document)
    version = rc.proposed_version(change, when, book=book)
    authorities = rc.authority_status(data_dir, change)
    markdown = rc.render_markdown(change, when, current, community.name, schedule, authorities, recitals=recitals,
                                  version=version, law=law)
    path = rc.write(data_dir, change, markdown)
    print(f"Saved {path}")
    print(f"Notice by {when.notice_by}; decision {when.decision} ({when.lead_days} days after a notice on "
          f"{when.notice_date}); comments by {when.comment_deadline}; adoption notice by {when.adoption_notice_by}.")
    print(f"Proposed text cited as {rc.version_address(version)} (not in force).")
    missing = [row["citation"] for row in authorities if not row["found"]]
    if missing:
        print(f"unverified citations (not in data/authorities): {', '.join(missing)}", file=sys.stderr)
    if not args.draft_email:
        return 0
    notice = rc.member_notice(change, when, current, community.name, schedule, law=law)
    draft = rc.email_draft(notice)
    from jason.tasks.notice_text import NoticeKeyError, check_key

    try:
        key = check_key(args.notice or rc.notice_key(change, when))
    except NoticeKeyError as exc:
        print(exc, file=sys.stderr)
        return 2
    print(f"\nGmail draft preview (no recipients; a person addresses and sends it):\nSubject: {draft.subject}\n")
    print(draft.text)
    if not args.yes:
        print("\nDry run: add --yes to save this as a Gmail draft (it is never sent); its text is then kept in "
              f"{data_dir / 'notices' / key} (jason://notice/{key}).")
        return 0
    from jason.google.gmail_drafts import GmailDrafts

    with agent_factory(args) as agent:
        created = rc.save_draft(GmailDrafts.on(agent.drive()), draft)
    print(f"\nGmail draft {created.get('id')} created with no recipients; review, address, and send it from Gmail.")
    entry = rc.keep_notice(data_dir, key, notice, change, recitals=recitals, version=version, by=args.by or "",
                           state=f"saved as Gmail draft {created.get('id')} with no recipients, for a person to "
                                 "address and send; not a record that it was sent")
    print(f"Kept its text in {data_dir / 'notices' / key} (sha256 {entry['files'][0]['sha256'][:16]}); "
          f"jason cite jason://notice/{key}")
    return 0


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("rule-change", help="Member notice, agenda item, and adoption notice for a proposed rule change "
                                           "(Civil Code 4360); never sends")
    add_common(p)
    p.add_argument("change", nargs="?", help="the proposed change's key (see --list)")
    p.add_argument("--list", action="store_true", help="list the proposed rule changes in the specification")
    p.add_argument("--from-manual", action="store_true",
                   help="draft the 4360 notice publishing the official rules extracted from the owner's manual "
                        "(jason manual --render, jason revisions); writes data/drafts only")
    p.add_argument("--notice-date", metavar="DATE", help="the day the member notice goes out (default: today)")
    p.add_argument("--decision", metavar="DATE", help="the decision meeting (default: first meeting 28+ days out)")
    p.add_argument("--comment-deadline", metavar="DATE", help="members' written comments due (default: the day before)")
    p.add_argument("--regular-months-only", action="store_true",
                   help="count only the resolution's regular months, not the monthly practice")
    p.add_argument("--draft-email", action="store_true", help="preview the member notice as a Gmail draft")
    p.add_argument("--yes", action="store_true", help="with --draft-email: save the draft (never sent) and keep its "
                                                      "text in data/notices/KEY/")
    p.add_argument("--notice", metavar="KEY", help="with --draft-email: the notice's ledger key (default "
                                                   "rule-change-proposed-CHANGE-NOTICEDATE)")
    p.add_argument("--by", metavar="NAME", help="with --draft-email --yes: who saved the draft")
    p.set_defaults(func=lambda a: cmd_rule_change(a, agent_factory))
