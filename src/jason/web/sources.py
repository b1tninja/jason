"""The JSON sources the UI reads, and the one thing it writes.

Each loader wraps a read-only tool from ``jason.mcp`` and reads disk only. ``leads`` gathers the places where the
stores show something a person has not yet pinned: a lead is evidence, not a pin, and the UI repeats that.
The one write is the board's own columns on a board item (status, owner, meeting, notes), the same fields
``jason board --set`` changes; jason's columns stay jason's.
"""

from __future__ import annotations

from typing import Any

Args = dict[str, str]


def _flag(args: Args, key: str) -> bool:
    return args.get(key, "").lower() in ("1", "true", "yes")


def board_digest(args: Args) -> dict[str, Any]:
    from jason.mcp.county import board_digest as tool

    return tool(since=args.get("since", ""), days=int(args.get("days", "30") or 30))


def board_items(args: Args) -> dict[str, Any]:
    from jason.mcp.county import board_items as tool

    return tool(include_closed=_flag(args, "closed"))


def association_records(args: Args) -> dict[str, Any]:
    from jason.mcp.county import association_records as tool

    return tool()


def records_inventory(args: Args) -> dict[str, Any]:
    from jason.mcp.county import records_inventory as tool

    return tool()


def library_status(args: Args) -> dict[str, Any]:
    from jason.mcp.county import library_status as tool

    return tool()


def document_readings(args: Args) -> dict[str, Any]:
    from jason.mcp.county import document_readings as tool

    return tool()


def jobs_status(args: Args) -> dict[str, Any]:
    from jason.mcp.county import jobs_status as tool

    return tool(job=int(args.get("job", "0") or 0), every=_flag(args, "all"))


def leads(args: Args) -> dict[str, Any]:
    """Everything the stores show that no person has pinned yet, in one shape: ``source`` names the tool, ``kind``
    the sort of lead, ``title`` the thing, ``detail`` why it is a lead, and ``next`` what a person would do."""
    rows: list[dict[str, Any]] = []
    notes: list[str] = []

    def attempt(source: str, fn) -> None:
        try:
            fn()
        except Exception as exc:  # a missing store is a note, not a crash
            notes.append(f"{source}: {type(exc).__name__}: {exc}")

    def _library() -> None:
        status = library_status({})
        for path in status.get("unclassified", []):
            rows.append({"source": "library_status", "kind": "unclassified file", "title": path,
                         "detail": "no name rule, phrase rule, or model placed it", "next": "classify it, or add a rule row"})

    def _inventory() -> None:
        for rec in records_inventory({}).get("records", []):
            if rec.get("gap"):
                rows.append({"source": "records_inventory", "kind": "records gap", "title": rec["record"],
                             "detail": rec["gap"], "next": "pin where the record is kept, or gather it",
                             "authority": rec.get("citation", "")})

    def _readings() -> None:
        for p in document_readings({}).get("supersessions", []):
            if not p.get("pinned"):
                rows.append({"source": "document_readings", "kind": "supersession not pinned",
                             "title": f"{p['number']} superseded by {p['supersededBy']}",
                             "detail": f"the text of {p['source']} says so (phase {p.get('phase') or '?'})",
                             "next": "read both instruments, then pin it in the profile"})

    def _association() -> None:
        rec = association_records({})
        for d in rec.get("deliveries", []):
            for missing in d.get("missing", []):
                rows.append({"source": "association_records", "kind": "delivery missing", "title": d["delivery"],
                             "detail": missing, "next": "order the copy, or find it in the files"})
        for r in rec.get("unplaced", []):
            rows.append({"source": "association_records", "kind": "unplaced instrument", "title": r["number"],
                         "detail": f"{r['filing']} recorded {r['recorded'] or '?'} by {r['recordedBy'] or '?'}; tied to no delivery or phase",
                         "next": "read it and place it, or mark it as not the association's"})

    attempt("library_status", _library)
    attempt("records_inventory", _inventory)
    attempt("document_readings", _readings)
    attempt("association_records", _association)
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["kind"]] = counts.get(r["kind"], 0) + 1
    return {"count": len(rows), "counts": counts, "rows": rows, "notes": notes,
            "caveats": ["A lead is evidence, not a pin: a reading, a match, or a gap is something to read, never a finding."]}


def default_loaders() -> dict[str, Any]:
    return {
        "board-digest": board_digest,
        "board-items": board_items,
        "association-records": association_records,
        "records-inventory": records_inventory,
        "library-status": library_status,
        "document-readings": document_readings,
        "jobs": jobs_status,
        "leads": leads,
    }


BOARD_FIELDS = ("status", "owner", "meeting", "notes")


def set_board_item(item_id: str, changes: dict[str, Any]) -> dict[str, Any]:
    """Change a board item's board-owned fields. Anything else is refused (``ValueError``), as ``jason board --set`` refuses it."""
    from jason.mcp.county import _data_dir
    from jason.tasks.board_items import _encode, set_fields

    unknown = sorted(set(changes) - set(BOARD_FIELDS))
    if unknown:
        raise ValueError(f"{', '.join(unknown)}: jason's; the board sets {', '.join(BOARD_FIELDS)}")
    clean = {k: str(v) for k, v in changes.items() if v is not None}
    if not clean:
        raise ValueError("nothing to change")
    return _encode(set_fields(_data_dir(None), item_id, **clean))
