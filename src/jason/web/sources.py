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


def duties(args: Args) -> dict[str, Any]:
    """The manager's duty anchors (docs/community-manager.md): each with what it keeps straight, its sections, artifact,
    cadence, the CIV 5200 records it rests on, what jason produces, and its limit. ``anchor`` gives one duty's full
    brief with the passages retrieval found; without it, the list (no retrieval)."""
    from jason.community.duties import DUTIES

    anchor = args.get("anchor", "").strip()
    if anchor:
        from jason.mcp.county import duty_brief

        return duty_brief(anchor)
    return {"found": True, "count": len(DUTIES), "duties": [
        {"anchor": d.anchor, "keepsStraight": d.keeps_straight, "sections": d.sections, "artifact": d.artifact,
         "cadence": d.cadence.value, "when": d.when, "records": [r.value for r in d.records], "produce": d.produce, "limit": d.limit}
        for d in DUTIES]}


def calendar(args: Args) -> dict[str, Any]:
    from jason.mcp.county import association_calendar as tool

    return tool()


def meetings(args: Args) -> dict[str, Any]:
    from jason.mcp.county import meeting_records as tool

    return tool(date=args.get("date", ""))


def insurance(args: Args) -> dict[str, Any]:
    from jason.mcp.county import insurance_review as tool

    return tool()


def budget(args: Args) -> dict[str, Any]:
    from jason.mcp.county import budget_status as tool

    return tool(year=int(args.get("year", "0") or 0))


def reconciliations(args: Args) -> dict[str, Any]:
    from jason.mcp.county import bank_reconciliations as tool

    return tool()


def invoices(args: Args) -> dict[str, Any]:
    from jason.mcp.county import invoice_review as tool

    return tool(payee=args.get("payee", ""), problems_only=not _flag(args, "all"), since=args.get("since", ""),
                limit=int(args.get("limit", "80") or 80))


def collections(args: Args) -> dict[str, Any]:
    from jason.mcp.county import association_collections as tool

    return tool()


def reserves(args: Args) -> dict[str, Any]:
    from jason.mcp.county import reserve_transfers as tool

    return tool()


def hearings(args: Args) -> dict[str, Any]:
    from jason.mcp.county import hearings as tool

    return tool()


def title_watch(args: Args) -> dict[str, Any]:
    from jason.mcp.county import title_watch as tool

    return tool(apn=args.get("apn", ""), standing=args.get("standing", ""), attention=_flag(args, "attention"))


def open_items(args: Args) -> dict[str, Any]:
    from jason.mcp.county import open_items as tool

    return tool(days=int(args.get("days", "30") or 30))


def utility_payments(args: Args) -> dict[str, Any]:
    from jason.mcp.county import utility_payments as tool

    return tool(problems_only=not _flag(args, "all"), since=args.get("since", ""), limit=int(args.get("limit", "80") or 80))


def ledger_validation(args: Args) -> dict[str, Any]:
    from jason.mcp.county import ledger_validation as tool

    return tool()


def legal_cases(args: Args) -> dict[str, Any]:
    from jason.mcp.county import legal_cases as tool

    return tool()


def audit_chains(args: Args) -> dict[str, Any]:
    from jason.mcp.county import audit_chains as tool

    return tool(apn=args.get("apn", ""))


def request_links(args: Args) -> dict[str, Any]:
    from jason.mcp.county import request_links as tool

    return tool(unit=args.get("unit", ""), drafts_only=_flag(args, "drafts"), limit=int(args.get("limit", "40") or 40))


def canvases(args: Args) -> dict[str, Any]:
    """The canvases on disk; ``key`` gives one in full."""
    from jason.mcp.county import _data_dir
    from jason.tasks import canvases as store

    key = args.get("key", "").strip()
    if key:
        try:
            return {"found": True, "canvas": store.encode(store.load(_data_dir(None), key))}
        except KeyError:
            return {"found": False, "note": f"no canvas {key}"}
    items = store.load_all(_data_dir(None))
    return {"found": True, "count": len(items), "statuses": [s.value for s in store.CanvasStatus],
            "canvases": [{**store.encode(c), "clips": len(c.clips), "notes": ""} for c in items]}


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
        "duties": duties,
        "calendar": calendar,
        "meetings": meetings,
        "insurance": insurance,
        "budget": budget,
        "reconciliations": reconciliations,
        "invoices": invoices,
        "collections": collections,
        "reserves": reserves,
        "hearings": hearings,
        "title-watch": title_watch,
        "open-items": open_items,
        "utility-payments": utility_payments,
        "ledger-validation": ledger_validation,
        "legal-cases": legal_cases,
        "audit-chains": audit_chains,
        "request-links": request_links,
        "canvases": canvases,
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


def write_canvas(key: str, body: dict[str, Any]) -> dict[str, Any]:
    """The canvas writes: ``key`` empty creates one from ``body.title``; a body with ``clip`` adds a clip; otherwise the
    editable fields change in place. A person's scratchpad, jason's own store; nothing outward."""
    from jason.mcp.county import _data_dir
    from jason.tasks import canvases as store

    root = _data_dir(None)
    if not key:
        return store.encode(store.create(root, str(body.get("title", "")), question=str(body.get("question", "")),
                                         duty=str(body.get("duty", "")), matter=str(body.get("matter", ""))))
    clip = body.get("clip")
    if clip is not None:
        if not isinstance(clip, dict):
            raise ValueError("clip is an object with source and text")
        return store.encode(store.add_clip(root, key, source=str(clip.get("source", "")), text=str(clip.get("text", "")),
                                           label=str(clip.get("label", "")), args=clip.get("args") if isinstance(clip.get("args"), dict) else None))
    changes = {k: v for k, v in body.items() if v is not None}
    if not changes:
        raise ValueError("nothing to change")
    return store.encode(store.update(root, key, **changes))
