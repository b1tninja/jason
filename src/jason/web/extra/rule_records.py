"""The rule records the console reads (docs/console/handoff-rule-records.md, phase 1): ``rule-records``, ``rule-record``,
``rule-record-history``, ``rule-record-compare``, ``rule-uses`` and ``rule-events``. Disk only, read only: each is
``jason.tasks.rule_records``' view of the stored or derived records, so the console, the command and the MCP tools agree.

The status, the comparison word, the version in force on a day and the diff are worked out here, on the server; the client
derives nothing. The board's screens only (the drafts and the uses name no owner, but the grounds are a board working
paper); nothing here is in the owner view's sources. Nothing is written.
"""

from __future__ import annotations

from typing import Any

Args = dict[str, str]


def _root() -> Any:
    from jason.mcp.county import _data_dir

    return _data_dir(None)


def _records(args: Args) -> str:
    mode = args.get("records", "auto") or "auto"
    return mode if mode in ("auto", "derived", "stored") else "auto"


def rule_records(args: Args) -> dict[str, Any]:
    """The book: every record with its status, version in force, subjects, grounds standing and Doc comparison, and counts."""
    from jason.tasks import rule_records as task

    return task.list_view(_root(), as_of=args.get("as_of", ""), status=args.get("status", ""), subject=args.get("subject", ""),
                          records=_records(args))


def rule_record(args: Args) -> dict[str, Any]:
    from jason.tasks import rule_records as task

    return task.record_detail(args.get("id", ""), _root(), as_of=args.get("as_of", ""), records=_records(args))


def rule_record_history(args: Args) -> dict[str, Any]:
    from jason.tasks import rule_records as task

    return task.history_detail(args.get("id", ""), _root(), as_of=args.get("as_of", ""), records=_records(args))


def rule_record_compare(args: Args) -> dict[str, Any]:
    from jason.tasks import rule_records as task

    return task.compare_detail(args.get("id", ""), _root(), as_of=args.get("as_of", ""), records=_records(args))


def rule_uses(args: Args) -> dict[str, Any]:
    from jason.tasks import rule_records as task

    return task.uses_detail(args.get("id", ""), _root(), as_of=args.get("as_of", ""), records=_records(args))


def rule_events(args: Args) -> dict[str, Any]:
    from jason.tasks import rule_records as task

    return task.events_detail(args.get("id", ""), args.get("key", ""), _root(), records=_records(args))
