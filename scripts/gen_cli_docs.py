"""Write docs/cli.md from the jason argument parser.

Run from the repository root with the project's venv:

    .venv/Scripts/python scripts/gen_cli_docs.py

The parser is the source. This script only lays it out: commands grouped by
area (GROUPS below), each with its help line and its options. A command not in
GROUPS lands in "Other"; add it to a group when that happens.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from jason.cli import build_parser

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "cli.md"

# The order of this list is the order of the sections in docs/cli.md.
GROUP_ORDER = [
    "PayHOA & finance",
    "Utility bills",
    "Documents & library",
    "Meetings, board & minutes",
    "Owners, requests, notices & forms",
    "Law, legal, insurance & claims",
    "Google Workspace",
    "Mail, email, Zoom & vendors",
    "Property records & county",
    "Local AI & search",
    "Setup & maintenance",
]

GROUPS: dict[str, str] = {
    # PayHOA & finance
    "dump-transactions": "PayHOA & finance",
    "probe-transactions": "PayHOA & finance",
    "sync-catalog": "PayHOA & finance",
    "reports": "PayHOA & finance",
    "who-owes": "PayHOA & finance",
    "who-owes-sheet": "PayHOA & finance",
    "budget": "PayHOA & finance",
    "accounts": "PayHOA & finance",
    "invoices": "PayHOA & finance",
    "books": "PayHOA & finance",
    "reconcile": "PayHOA & finance",
    "ledger": "PayHOA & finance",
    "reserves": "PayHOA & finance",
    "cost-centers": "PayHOA & finance",
    "vendor-matches": "PayHOA & finance",
    "paid-vs-approved": "PayHOA & finance",
    "mailroom": "PayHOA & finance",
    "batches": "PayHOA & finance",
    "approvals": "PayHOA & finance",
    # Utility bills
    "sync-bills": "Utility bills",
    "upload-smud-bills": "Utility bills",
    "upload-idoxs-bills": "Utility bills",
    "attach-bills": "Utility bills",
    "fetch-bills": "Utility bills",
    "sync-smud": "Utility bills",
    "sync-idoxs": "Utility bills",
    "utilities": "Utility bills",
    # Documents & library
    "export-documents": "Documents & library",
    "document-sync": "Documents & library",
    "publish-document": "Documents & library",
    "library": "Documents & library",
    "models": "Documents & library",
    "outlines": "Documents & library",
    "manual": "Documents & library",
    "revisions": "Documents & library",
    "copies": "Documents & library",
    "packet": "Documents & library",
    "report": "Documents & library",
    "templates": "Documents & library",
    "letter": "Documents & library",
    "qr": "Documents & library",
    # Meetings, board & minutes
    "digest": "Meetings, board & minutes",
    "board": "Meetings, board & minutes",
    "meetings": "Meetings, board & minutes",
    "hearing": "Meetings, board & minutes",
    "cross-checks": "Meetings, board & minutes",
    "minutes-privacy": "Meetings, board & minutes",
    "calendar": "Meetings, board & minutes",
    "rule-change": "Meetings, board & minutes",
    "record-stages": "Meetings, board & minutes",
    "schedule": "Meetings, board & minutes",
    "schedule-evidence": "Meetings, board & minutes",
    "attention": "Meetings, board & minutes",
    # Owners, requests, notices & forms
    "notices": "Owners, requests, notices & forms",
    "respond": "Owners, requests, notices & forms",
    # Documents & library
    "living": "Documents & library",
    "section-refs": "Documents & library",
    "cite": "Documents & library",
    "intake": "Documents & library",
    "ingest": "Documents & library",
    # Law, legal, insurance & claims
    "conflicts": "Law, legal, insurance & claims",
    # Setup & maintenance
    "lessons": "Setup & maintenance",
    "sop": "Setup & maintenance",
    "request-sheet": "Owners, requests, notices & forms",
    "notice-check": "Owners, requests, notices & forms",
    "export-requests": "Owners, requests, notices & forms",
    "review-requests": "Owners, requests, notices & forms",
    "request-comment": "Owners, requests, notices & forms",
    "request-note": "Owners, requests, notices & forms",
    "request-attach": "Owners, requests, notices & forms",
    "sync-request-files": "Owners, requests, notices & forms",
    "request-links": "Owners, requests, notices & forms",
    "violations": "Owners, requests, notices & forms",
    "notes": "Owners, requests, notices & forms",
    "communications": "Owners, requests, notices & forms",
    "owner-info": "Owners, requests, notices & forms",
    "delivery": "Owners, requests, notices & forms",
    "broadcast": "Owners, requests, notices & forms",
    "forms": "Owners, requests, notices & forms",
    "form-fuzz": "Owners, requests, notices & forms",
    "form-lab": "Owners, requests, notices & forms",
    "new-owners": "Owners, requests, notices & forms",
    "rentals": "Owners, requests, notices & forms",
    "leases": "Owners, requests, notices & forms",
    "party": "Owners, requests, notices & forms",
    # Law, legal, insurance & claims
    "export-authorities": "Law, legal, insurance & claims",
    "law-history": "Law, legal, insurance & claims",
    "statute-align": "Law, legal, insurance & claims",
    "duties": "Law, legal, insurance & claims",
    "review": "Law, legal, insurance & claims",
    "cases": "Law, legal, insurance & claims",
    "case": "Law, legal, insurance & claims",
    "hold": "Law, legal, insurance & claims",
    "vault": "Law, legal, insurance & claims",
    "insurance": "Law, legal, insurance & claims",
    "policies": "Law, legal, insurance & claims",
    "incidents": "Law, legal, insurance & claims",
    "deadlines": "Law, legal, insurance & claims",
    # Google Workspace
    "gmail": "Google Workspace",
    "drive": "Google Workspace",
    "drive-activity": "Google Workspace",
    "drive-labels": "Google Workspace",
    "draft": "Google Workspace",
    "photos": "Google Workspace",
    "registers": "Google Workspace",
    "google-features": "Google Workspace",
    # Mail, email, Zoom & vendors
    "mail": "Mail, email, Zoom & vendors",
    "zoom": "Mail, email, Zoom & vendors",
    "threads": "Mail, email, Zoom & vendors",
    "topics": "Mail, email, Zoom & vendors",
    "inbox": "Mail, email, Zoom & vendors",
    "replies": "Mail, email, Zoom & vendors",
    "open-items": "Mail, email, Zoom & vendors",
    "sources": "Mail, email, Zoom & vendors",
    "contacts": "Mail, email, Zoom & vendors",
    "signatures": "Mail, email, Zoom & vendors",
    "vendors": "Mail, email, Zoom & vendors",
    "pests": "Mail, email, Zoom & vendors",
    # Property records & county
    "permits": "Property records & county",
    "permit-status": "Property records & county",
    "ownership-sheet": "Property records & county",
    "property-history": "Property records & county",
    "unit-charts": "Property records & county",
    "sales-charts": "Property records & county",
    "equity-charts": "Property records & county",
    "county-report": "Property records & county",
    "sync-characteristics": "Property records & county",
    "sync-solar": "Property records & county",
    "sync-liens": "Property records & county",
    "sync-secured": "Property records & county",
    "sync-tax": "Property records & county",
    "brief": "Property records & county",
    "title-watch": "Property records & county",
    "recent-filings": "Property records & county",
    "records-request": "Property records & county",
    "index-coverage": "Property records & county",
    "securities": "Property records & county",
    # Local AI & search
    "local-ai": "Local AI & search",
    "anythingllm": "Local AI & search",
    "read-documents": "Local AI & search",
    "read-scans": "Local AI & search",
    "ocr-documents": "Local AI & search",
    # Setup & maintenance
    "login": "Setup & maintenance",
    "onboard": "Setup & maintenance",
    "spec": "Setup & maintenance",
    "jobs": "Setup & maintenance",
    "worker": "Setup & maintenance",
}

# Options most commands take; listed once in the intro instead of per command.
COMMON = {"--env", "--interactive"}


def _subparsers(parser: argparse.ArgumentParser) -> argparse._SubParsersAction | None:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action
    return None


def _cell(text: str) -> str:
    # Escape table pipes and Markdown link syntax that help text quotes.
    text = " ".join(text.split()).replace("|", "\\|")
    return text.replace("![", "!\\[").replace("](", "\\](")


def _help(parser: argparse.ArgumentParser, action: argparse.Action) -> str:
    if not action.help or action.help == argparse.SUPPRESS:
        return ""
    formatter = parser._get_formatter()
    try:
        return formatter._expand_help(action)
    except (KeyError, TypeError, ValueError):
        return action.help


def _flag(action: argparse.Action) -> str:
    if action.option_strings:
        return ", ".join(f"`{s}`" for s in action.option_strings)
    return f"`{action.metavar or action.dest}`"


def _metavar(action: argparse.Action) -> str:
    if action.nargs == 0:
        return ""
    if action.choices is not None and not isinstance(action, argparse._SubParsersAction):
        return "{" + ",".join(str(c) for c in action.choices) + "}"
    if action.option_strings:
        meta = action.metavar or action.dest.upper()
        return meta if isinstance(meta, str) else " ".join(meta)
    if action.nargs in ("*", "?", argparse.REMAINDER):
        return f"optional ({action.nargs})"
    if action.nargs == "+":
        return "one or more"
    return ""


def _options(parser: argparse.ArgumentParser) -> list[tuple[str, str, str]]:
    rows = []
    for action in parser._actions:
        if isinstance(action, (argparse._HelpAction, argparse._SubParsersAction)):
            continue
        if action.help == argparse.SUPPRESS:
            continue
        if COMMON.intersection(action.option_strings):
            continue
        rows.append((_flag(action), _cell(_metavar(action)), _cell(_help(parser, action))))
    return rows


def _write_command(lines: list[str], name: str, help_text: str, parser: argparse.ArgumentParser, level: int) -> None:
    lines.append(f"{'#' * level} `jason {name}`")
    lines.append("")
    if help_text:
        lines.append(_cell(help_text))
        lines.append("")
    rows = _options(parser)
    if rows:
        lines.append("| Option | Value | Help |")
        lines.append("|---|---|---|")
        for flag, meta, text in rows:
            lines.append(f"| {flag} | {meta} | {text} |")
        lines.append("")
    nested = _subparsers(parser)
    if nested is not None:
        helps = {c.dest: c.help or "" for c in nested._choices_actions}
        for sub_name, sub_parser in nested.choices.items():
            _write_command(lines, f"{name} {sub_name}", helps.get(sub_name, ""), sub_parser, min(level + 1, 6))


def main() -> int:
    parser = build_parser()
    top = _subparsers(parser)
    assert top is not None
    helps = {c.dest: c.help or "" for c in top._choices_actions}
    grouped: dict[str, list[str]] = {g: [] for g in GROUP_ORDER + ["Other"]}
    for name in top.choices:
        grouped[GROUPS.get(name, "Other")].append(name)

    lines = [
        "# Command line reference",
        "",
        "This page is generated by `scripts/gen_cli_docs.py` from the jason argument parser. Do not edit it by hand;",
        "regenerate it after a command changes. `jason <command> --help` is the source.",
        "",
        "Most commands also take `--env PATH` (the `.env` file; default `./.env` or `JASON_ENV`) and `--interactive`",
        "(allow Keeper password, MFA, and device approval prompts). They are left out of the tables below.",
        "",
        f"{len(top.choices)} commands, by area:",
        "",
    ]
    for group in GROUP_ORDER + ["Other"]:
        names = grouped[group]
        if names:
            anchor = "".join(c for c in group.lower().replace(" ", "-") if c.isalnum() or c == "-")
            lines.append(f"- [{group}](#{anchor}) ({len(names)})")
    lines.append("")
    for group in GROUP_ORDER + ["Other"]:
        names = grouped[group]
        if not names:
            continue
        lines.append(f"## {group}")
        lines.append("")
        for name in names:
            _write_command(lines, name, helps.get(name, ""), top.choices[name], 3)
    OUT.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    for group in GROUP_ORDER + ["Other"]:
        print(f"{group}: {len(grouped[group])}")
    if grouped["Other"]:
        print("Other:", ", ".join(grouped["Other"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
