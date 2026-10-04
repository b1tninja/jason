"""`jason hold`: a legal hold's register, its Vault matter and holds, its Drive labels, and its custody checks."""

from __future__ import annotations

import argparse
import json
from typing import Any, Callable


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    parser = sub.add_parser("hold", help="Legal hold: scope and register; --vault / --label need --yes; --watch checks custody")
    add_common(parser)
    parser.add_argument("--key", default="", help="The hold (default: the first in the specification)")
    parser.add_argument("--vault", action="store_true", help="Create the Vault matter and its Drive and Mail holds (needs --yes)")
    parser.add_argument("--label", action="store_true", help="Set jason_hold on the held Drive files (needs --yes)")
    parser.add_argument("--watch", action="store_true", help="Which held Drive files were deleted, moved, or re-shared since the duty arose")
    parser.add_argument("--since", default="", help="With --watch, from this date instead")
    parser.add_argument("--notices", action="store_true",
                        help="Draft the hold notices and the note to counsel in Gmail (never sent; --yes saves the drafts)")
    parser.add_argument("--yes", action="store_true", help="Confirm a write to Vault, Drive, or Gmail drafts")
    parser.add_argument("--json", action="store_true", help="Print JSON")
    parser.set_defaults(func=lambda args: run(args, agent_factory))


def run(args: argparse.Namespace, agent_factory: Callable[[Any], Any]) -> int:
    from jason.community import community as active
    from jason.config import Settings
    from jason.tasks import legal_hold as task

    data_dir = Settings.load(args.env).payhoa_catalog.parent
    community = active()
    try:
        spec = task.hold_spec(community, args.key)
    except ValueError as exc:
        print(f"error: {exc}")
        return 2
    reg = task.build_register(data_dir, community, spec)
    out: dict[str, Any] = {}
    if args.vault:
        if args.yes:
            with agent_factory(args) as agent, agent.google_vault() as vault:
                out["vault"] = task.vault_apply(vault, data_dir, spec, yes=True)
        else:
            out["vault"] = task.vault_apply(None, data_dir, spec, yes=False)
            print("Vault plan (add --yes to create it):")
            print(json.dumps(out["vault"]["plan"], indent=2))
    if args.label:
        if args.yes:
            with agent_factory(args) as agent:
                out["label"] = task.label(agent.drive(), data_dir, spec, yes=True, community=community)
        else:
            out["label"] = task.label(None, data_dir, spec, yes=False, community=community)
    if args.notices:
        if args.yes:
            from jason.google.gmail_drafts import GmailDrafts

            with agent_factory(args) as agent:
                out["notices"] = task.draft_notices(GmailDrafts.on(agent.drive()), data_dir, spec, yes=True)
        else:
            out["notices"] = task.draft_notices(None, data_dir, spec, yes=False)
            for n in out["notices"]["drafts"]:
                print(f"--- draft for {n['for']} (to: {', '.join(n['to']) or 'left for you to fill'})")
                print(f"Subject: {n['subject']}", end="\n\n")
                print(n["text"], end="\n\n")
    if args.watch:
        from jason.google.drive_activity import DriveActivityClient

        with agent_factory(args) as agent:
            out["watch"] = task.watch(DriveActivityClient.from_drive(agent.drive()), data_dir, spec, since=args.since)
    reg = task.load_register(data_dir, spec.key)
    if args.json:
        print(json.dumps({"register": reg, **out}, indent=2, default=str))
    else:
        print("\n".join(task.lines(reg)))
        for k in ("vault", "label", "notices"):
            if k in out and not out[k].get("dryRun"):
                print(f"{k}: {json.dumps(out[k], default=str)[:400]}")
        if out.get("label", {}).get("dryRun"):
            print(f"label: would set jason_hold on {out['label']['wouldLabel']} Drive files (add --yes)")
    return 0
