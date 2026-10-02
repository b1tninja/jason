"""``jason rule-change``: carry a proposed operating rule change through Civil Code 4360.

Writes ``data/board/rule-change-<slug>.md``: the member notice of the proposed change (28 days before the board
decides), the agenda item for the decision meeting, and the notice of adoption (15 days after). The decision meeting
defaults to the first meeting on the schedule at least 28 days after the notice date.

``--draft-email`` previews the member notice as a Gmail draft with no recipients; ``--draft-email --yes`` saves it.
jason never sends email: a person addresses the draft and sends it from Gmail.
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


def cmd_rule_change(args: argparse.Namespace, agent_factory: Callable[[Any], Any]) -> int:
    from jason.community import mystique
    from jason.tasks import rule_change as rc

    community = mystique()
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
    notice_date = date.fromisoformat(args.notice_date) if args.notice_date else date.today()
    decision = date.fromisoformat(args.decision) if args.decision else None
    comment = date.fromisoformat(args.comment_deadline) if args.comment_deadline else None
    try:
        when = rc.timeline(schedule, notice_date=notice_date, decision=decision, monthly=not args.regular_months_only,
                           comment_deadline=comment, fiscal_year_end=date((decision or notice_date).year, 12, 31))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    data_dir = _data_dir(args)
    current = rc.current_sections(data_dir, change.document)
    if not current:
        print(f"note: data/outlines/{change.document}.json not on disk; current text is left out (run jason outlines)",
              file=sys.stderr)
    authorities = rc.authority_status(data_dir, change)
    markdown = rc.render_markdown(change, when, current, community.name, schedule, authorities)
    path = rc.write(data_dir, change, markdown)
    print(f"Saved {path}")
    print(f"Notice by {when.notice_by}; decision {when.decision} ({when.lead_days} days after a notice on "
          f"{when.notice_date}); comments by {when.comment_deadline}; adoption notice by {when.adoption_notice_by}.")
    missing = [row["citation"] for row in authorities if not row["found"]]
    if missing:
        print(f"unverified citations (not in data/authorities): {', '.join(missing)}", file=sys.stderr)
    if not args.draft_email:
        return 0
    notice = rc.member_notice(change, when, current, community.name, schedule)
    draft = rc.email_draft(notice)
    print(f"\nGmail draft preview (no recipients; a person addresses and sends it):\nSubject: {draft.subject}\n")
    print(draft.text)
    if not args.yes:
        print("\nDry run: add --yes to save this as a Gmail draft (it is never sent).")
        return 0
    from jason.google.gmail_drafts import GmailDrafts

    with agent_factory(args) as agent:
        created = rc.save_draft(GmailDrafts.on(agent.drive()), draft)
    print(f"\nGmail draft {created.get('id')} created with no recipients; review, address, and send it from Gmail.")
    return 0


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("rule-change", help="Member notice, agenda item, and adoption notice for a proposed rule change "
                                           "(Civil Code 4360); never sends")
    add_common(p)
    p.add_argument("change", nargs="?", help="the proposed change's key (see --list)")
    p.add_argument("--list", action="store_true", help="list the proposed rule changes in the specification")
    p.add_argument("--notice-date", metavar="DATE", help="the day the member notice goes out (default: today)")
    p.add_argument("--decision", metavar="DATE", help="the decision meeting (default: first meeting 28+ days out)")
    p.add_argument("--comment-deadline", metavar="DATE", help="members' written comments due (default: the day before)")
    p.add_argument("--regular-months-only", action="store_true",
                   help="count only the resolution's regular months, not the monthly practice")
    p.add_argument("--draft-email", action="store_true", help="preview the member notice as a Gmail draft")
    p.add_argument("--yes", action="store_true", help="with --draft-email: save the draft (never sent)")
    p.set_defaults(func=lambda a: cmd_rule_change(a, agent_factory))
