"""The registers for the UI: the specification's list, each register's local snapshot, and the board's edits into it.

``registers(args)`` lists the profile's registers (``Community.registers()``) with whether a snapshot is on disk and when
it was saved; ``?key=`` gives one register's columns, rows, and log from its snapshot. ``write(key, body)`` records one
board edit in the snapshot (``jason.tasks.register_snapshots.edit``): the key is ``"<register>|<row key>"``, the body
``{column, value, by}``. A jason-owned column is refused. The Sheet is behind the snapshot until the next sync pushes
the edit; the page says so. Reads disk only; calls neither Google nor PayHOA.
"""

from __future__ import annotations

from typing import Any

Args = dict[str, str]

CAVEATS = (
    "The board's columns are edited here in jason's local snapshot and logged; the Sheet catches up at the next sync (jason registers --sync, or the register's own sync). Until then the Sheet is behind.",
    "jason's columns are jason's: its own run writes them, and the page shows them as they were last synced.",
)


def _registers(community: Any) -> tuple:
    hook = getattr(community, "registers", None)
    try:
        return tuple(hook()) if callable(hook) else ()
    except Exception:
        return ()


def _data_dir():
    from jason.mcp.county import _data_dir

    return _data_dir(None)


def registers(args: Args) -> dict[str, Any]:
    """The list, or with ``key`` one register: its columns (name, owner, kind, choices), rows (by the first column, the
    key; ``pendingSync`` on a row edited here since the last sync), and log."""
    from jason.community.registers import Owner
    from jason.tasks import register_snapshots as store
    from jason.web.sources import _community

    root = _data_dir()
    specs = {r.key: r for r in _registers(_community())}
    snapshots = store.load_all(root)
    key = args.get("key", "").strip()
    if key:
        reg = specs.get(key)
        snap = snapshots.get(key)
        if reg is None and snap is None:
            return {"found": False, "note": f"no register {key}"}
        columns = store.encode_columns(reg) if reg is not None else snap.get("columns", [])
        rows = list(snap.get("rows", [])) if snap else []
        log = list(snap.get("log", [])) if snap else []
        log.sort(key=lambda e: str(e.get("seen", "")), reverse=True)
        return {"found": True, "key": key, "title": reg.title if reg is not None else snap.get("title", key),
                "confidential": bool(reg.confidential if reg is not None else snap.get("confidential")),
                "about": reg.about if reg is not None else "", "savedAt": snap.get("savedAt") if snap else None,
                "columns": columns, "keyColumn": columns[0]["name"] if columns else "", "rows": rows, "log": log,
                "pending": sum(1 for r in rows if r.get("pendingSync")), "inSpecification": reg is not None,
                "syncCommand": f"jason registers --sync {key}", "caveats": list(CAVEATS),
                "note": "" if snap else "no snapshot yet; the rows appear after the first sync"}
    out = []
    for k, reg in specs.items():
        snap = snapshots.get(k)
        out.append({"key": k, "title": reg.title, "tab": reg.tab, "confidential": reg.confidential, "about": reg.about,
                    "columns": store.encode_columns(reg), "boardColumns": [c.name for c in reg.owned(Owner.BOARD)],
                    "snapshot": snap is not None, "savedAt": snap.get("savedAt") if snap else None,
                    "rows": len(snap.get("rows", [])) if snap else 0, "pending": sum(1 for r in snap.get("rows", []) if r.get("pendingSync")) if snap else 0})
    for k, snap in snapshots.items():  # a snapshot of a register the specification no longer lists
        if k not in specs:
            out.append({"key": k, "title": snap.get("title", k), "tab": "", "confidential": bool(snap.get("confidential")), "about": "",
                        "columns": snap.get("columns", []), "boardColumns": [c["name"] for c in snap.get("columns", []) if c.get("owner") == "board"],
                        "snapshot": True, "savedAt": snap.get("savedAt"), "rows": len(snap.get("rows", [])),
                        "pending": sum(1 for r in snap.get("rows", []) if r.get("pendingSync")), "notInSpecification": True})
    return {"found": True, "count": len(out), "registers": out, "caveats": list(CAVEATS),
            "note": "" if out else "the specification lists no registers"}


def write(key: str, body: dict[str, Any]) -> dict[str, Any]:
    """One board edit: ``key`` is ``<register>|<row key>``; ``body`` has ``column``, ``value``, and ``by``."""
    from jason.tasks import register_snapshots as store

    register_key, sep, row_key = key.partition("|")
    if not sep or not register_key.strip() or not row_key.strip():
        raise ValueError("the key is <register>|<row key>")
    column = str(body.get("column", "")).strip()
    if not column:
        raise ValueError("column is required")
    row = store.edit(_data_dir(), register_key.strip(), row_key.strip(), column, body.get("value"), by=str(body.get("by", "")))
    return {"key": register_key.strip(), "rowKey": row_key.strip(), "column": column, "row": row,
            "note": "saved in the snapshot and logged; the Sheet catches up at the next sync"}
