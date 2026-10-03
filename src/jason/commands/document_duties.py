"""``jason duties --documents KEY``: the duties, prohibitions, permissions, rights, and conditions a governing document
states, as the phrase grammar reads them, for a person to review (``jason.tasks.document_duties``).

    jason duties --documents bylaws                    # read (or reread) the bylaws and list their norms
    jason duties --documents all --timed --untracked   # duties with a deadline or recurrence nothing tracks
    jason duties --documents ccrs --notices            # duties to give notice: leads for the notice catalog
    jason duties --documents ccrs --bearer owner --kind prohibition
    jason duties --documents bylaws --review ID --status confirmed --note "read 2026-10-02"

A reading is evidence, not a rule row. ``cmd_duties`` in ``jason.cli`` hands over here when ``--documents`` is given.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _data_dir(args: argparse.Namespace) -> Path:
    from jason.config import data_dir

    return data_dir(getattr(args, "env", None))


def cmd_document_duties(args: argparse.Namespace) -> int:
    from jason.community import community
    from jason.community.deontic import Bearer, DutyKind, NORMS, ReviewStatus
    from jason.tasks import document_duties as dd
    from jason.tasks.outlines import load

    data_dir = _data_dir(args)
    active = community()
    known = {o.key: o for o in load(data_dir)}
    wanted = args.documents
    keys = [k for k, o in known.items() if o.kind != "annexation"] if wanted in ("all", "") else [wanted]
    unknown = [k for k in keys if k not in known]
    if unknown:
        print(f"no outline {', '.join(unknown)} in {data_dir / 'outlines'} (jason outlines); one of: "
              f"{', '.join(sorted(k for k, o in known.items() if o.kind != 'annexation'))}", file=sys.stderr)
        return 2

    if args.review:
        if len(keys) != 1:
            print("--review needs one document: --documents KEY", file=sys.stderr)
            return 2
        try:
            status = ReviewStatus(args.status)
            entry = dd.review(data_dir, keys[0], args.review, status, note=args.note or "",
                              kind=DutyKind(args.set_kind) if args.set_kind else None,
                              bearer=Bearer(args.set_bearer) if args.set_bearer else None,
                              tracked_by=args.tracked_by or "")
        except (KeyError, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            return 2
        print(json.dumps(entry) if args.json else f"{args.review}: {entry['status']}")
        return 0

    reread = [k for k in keys if args.read or not dd.store_path(data_dir, k).is_file()]
    if reread:
        dd.run(data_dir, reread, community=active)
    if args.fill_bearers:
        from jason.community.content import ModelUnavailable
        from jason.community.duty_model import DutyModel

        reader = DutyModel(model=args.model or "", keep_alive="2m", num_ctx=args.num_ctx or 0)
        try:
            for k in keys:
                result = dd.fill_bearers(data_dir, k, reader=reader, log=lambda line: None)
                print(f"{k}: {result['filled']} of {result['unstated']} unstated bearers filled by {reader.model} "
                      f"({result['asked']} passages asked)", file=sys.stderr)
        except ModelUnavailable as exc:
            print(f"the local model is not available: {exc}", file=sys.stderr)
            return 1
    duties = [d for k in keys for d in dd.stored(data_dir, k)]
    if not args.all_kinds:
        duties = [d for d in duties if d.kind in NORMS]
    if args.kind:
        duties = [d for d in duties if d.kind.value == args.kind]
    if args.bearer:
        duties = [d for d in duties if d.bearer.value == args.bearer]
    if args.unreviewed:
        duties = [d for d in duties if d.review is ReviewStatus.UNREVIEWED]
    if args.notices:
        duties = [d for d in duties if d.notice and d.kind in (DutyKind.DUTY, DutyKind.CONDITION)]
    tracked: dict[str, str] = {}
    if args.timed or args.untracked or args.notices:
        trackers = (active.obligations(), active.notice_rules(), getattr(active, "notice_provisions", lambda: ())())
        rows = dd.untracked(duties, *trackers) if not args.notices else [(d, dd.tracking(d, *trackers)) for d in duties]
        tracked = {d.id: by for d, by in rows}
        duties = [d for d, by in rows if not (args.untracked and by)]
    if args.json:
        print(json.dumps([{**d.to_dict(), "trackedBy": tracked.get(d.id, "")} for d in duties], indent=1))
        return 0
    from collections import Counter

    counts = Counter(d.kind.value for d in duties)
    print(f"{len(duties)} readings in {', '.join(keys) if len(keys) <= 4 else f'{len(keys)} documents'}: "
          + ", ".join(f"{n} {k}" for k, n in counts.most_common()))
    for d in duties[: args.limit or None]:
        line = dd.describe(d)
        if tracked:
            line += f"  | tracked by: {tracked[d.id] or 'nothing'}"
        print(f"  {d.id}  {line}")
    if args.limit and len(duties) > args.limit:
        print(f"  ... {len(duties) - args.limit} more (--limit 0 for all)")
    if args.notices:
        print("\nA duty to give notice that no notice provision or rule carries is a lead for the notice catalog "
              "(docs/notices.md: Community.notice_provisions(), notice_catalog); this list does not add to it.")
    print("\nA reading is evidence for a person to review (--review ID --status confirmed|corrected|rejected), not a rule row.")
    return 0


def add_arguments(parser: argparse.ArgumentParser) -> None:
    from jason.community.deontic import Bearer, DutyKind, ReviewStatus

    parser.add_argument("--documents", nargs="?", const="all", default=None, metavar="KEY",
                        help="List the norms a governing document states (an outline key, or all): duties, prohibitions, "
                             "permissions, rights, and conditions, as the phrase grammar reads them")
    parser.add_argument("--read", action="store_true", help="With --documents: reread the outlines (reviews are kept)")
    parser.add_argument("--kind", choices=[k.value for k in DutyKind], help="With --documents: one kind")
    parser.add_argument("--bearer", choices=[b.value for b in Bearer], help="With --documents: one bearer")
    parser.add_argument("--timed", action="store_true", help="With --documents: duties with a deadline or recurrence, "
                                                              "and what tracks each")
    parser.add_argument("--untracked", action="store_true", help="With --documents: timed duties that no recurring "
                                                                  "deadline, calendar event, notice provision, or notice "
                                                                  "rule carries")
    parser.add_argument("--notices", action="store_true", help="With --documents: duties to give notice, and the notice "
                                                                "provision or rule that covers each (leads for the notice "
                                                                "catalog)")
    parser.add_argument("--unreviewed", action="store_true", help="With --documents: only readings no one has reviewed")
    parser.add_argument("--fill-bearers", action="store_true",
                        help="With --documents: ask the local model who bears each norm the words leave unstated (the "
                             "hybrid; preflight and the GPU lock first; answers cached)")
    parser.add_argument("--model", default="", help="With --fill-bearers: the Ollama model (default: jason's shared model)")
    parser.add_argument("--num-ctx", type=int, default=0, help="With --fill-bearers: the context window")
    parser.add_argument("--all-kinds", action="store_true", help="With --documents: include definitions and statements "
                                                                  "of status")
    parser.add_argument("--limit", type=int, default=60, help="With --documents: lines to print (0 for all)")
    parser.add_argument("--review", metavar="ID", help="With --documents KEY: record a person's review of one reading")
    parser.add_argument("--status", choices=[s.value for s in ReviewStatus], default="confirmed",
                        help="With --review: the review's status")
    parser.add_argument("--note", default="", help="With --review: the reviewer's note")
    parser.add_argument("--set-kind", choices=[k.value for k in DutyKind], help="With --review: the corrected kind")
    parser.add_argument("--set-bearer", choices=[b.value for b in Bearer], help="With --review: the corrected bearer")
    parser.add_argument("--tracked-by", default="", help="With --review: what carries this timed duty (a recurring "
                                                         "deadline's name, a calendar event, a notice rule, a command)")


__all__ = ["cmd_document_duties", "add_arguments"]
