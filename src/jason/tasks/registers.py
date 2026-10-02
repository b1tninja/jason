"""Keep a register's Google Sheet: create or adopt it, shape it, and sync it by key without overwriting the board.

``ensure`` gives a register its spreadsheet: an existing one the specification names (adopted), or a new one in the
registers folder (``Community.registers_folder``), with the records tab, the log tab, and an About tab. ``shape`` sets the
header (bold, frozen, with each column's note), column widths, a dropdown or date or checkbox rule per typed column,
dates shown as yyyy-mm-dd, and a warning-only protection on jason's columns and the header row, so a person editing in
Sheets is warned before overwriting what jason keeps. Shaping runs once per spreadsheet (recorded in the state).

``sync`` reads the tab, finds each row by its key (the first column), and:

1. **reads the board's columns back**: a non-empty board cell that differs from jason's record is the board's edit,
   returned to the caller to apply to its own store, and logged as a row in the log tab;
2. **writes only jason's columns** that changed, cell by cell in one atomic ``values:batchUpdate``; a board column of an
   existing row is never written;
3. **appends** a record with no row yet, whole;
4. **reports** a row whose key jason does not know (a row the board added by hand); it is left as it is.

Nothing is cleared, reordered, or deleted. The state (spreadsheet ids, shaping) is ``data/registers/registers.json``.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from jason.community.registers import LOG_COLUMNS, LOG_TAB, Kind, Owner, Register

STATE = Path("registers") / "registers.json"
ABOUT_TAB = "About"
ROWS = 2000                      # validation and protection reach this far down


def _state(data_dir: Path) -> dict[str, Any]:
    path = Path(data_dir) / STATE
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def _save(data_dir: Path, state: dict[str, Any]) -> None:
    path = Path(data_dir) / STATE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=1), encoding="utf-8")


def letter(index: int) -> str:
    """0 -> A, 25 -> Z, 26 -> AA."""
    out = ""
    index += 1
    while index:
        index, rem = divmod(index - 1, 26)
        out = chr(65 + rem) + out
    return out


def spreadsheet_id(data_dir: Path, reg: Register) -> str:
    return (_state(data_dir).get(reg.key) or {}).get("spreadsheetId", "")


def ensure(sheets: Any, drive: Any, reg: Register, data_dir: Path, *, folder: str = "", adopt: str = "") -> dict[str, Any]:
    """The register's spreadsheet: the one already recorded, an existing one to adopt (``adopt``), or a new one in
    ``folder`` (a folder of that name in My Drive, created when missing)."""
    state = _state(data_dir)
    entry = state.get(reg.key) or {}
    if entry.get("spreadsheetId"):
        return entry
    sibling = next((v for k, v in state.items() if reg.book and v.get("book") == reg.book and v.get("spreadsheetId")), None)
    if sibling is not None and not adopt:
        # A register in the same book: its own tab in the book's spreadsheet.
        sid = sibling["spreadsheetId"]
        if reg.tab not in sheets.sheet_titles(sid):
            sheets.batch_update(sid, [{"addSheet": {"properties": {"title": reg.tab}}}])
        sheets.values_update(sid, f"{reg.tab}!A1", [list(reg.names)])
        entry = {"spreadsheetId": sid, "adopted": False, "book": reg.book,
                 "created": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        state[reg.key] = entry
        _save(data_dir, state)
        return entry
    if adopt:
        titles = sheets.sheet_titles(adopt)
        if reg.tab not in titles:
            raise ValueError(f"{reg.title} ({adopt}) has no tab {reg.tab!r}; it has {titles}")
        header = (sheets.values_get(adopt, f"{reg.tab}!1:1").get("values") or [[]])[0]
        if header and tuple(header[: len(reg.names)]) != reg.names:
            raise ValueError(f"{reg.title}'s header {header} is not the register's columns {list(reg.names)}")
        missing = [t for t in (LOG_TAB, ABOUT_TAB) if t not in titles]
        if missing:
            sheets.batch_update(adopt, [{"addSheet": {"properties": {"title": t}}} for t in missing])
        if not header:
            sheets.values_update(adopt, f"{reg.tab}!A1", [list(reg.names)])
        entry = {"spreadsheetId": adopt, "adopted": True}
    else:
        made = sheets.create(reg.book or reg.title, sheet_titles=(reg.tab, LOG_TAB, ABOUT_TAB))
        sid = made["spreadsheetId"]
        sheets.values_update(sid, f"{reg.tab}!A1", [list(reg.names)])
        if folder:
            parent = drive.child_folder("root", folder) or drive.create_folder(folder, "root")
            drive.move(sid, parent)
            entry["folderId"] = parent
        entry.update({"spreadsheetId": sid, "adopted": False})
    sid = entry["spreadsheetId"]
    sheets.values_update(sid, f"{LOG_TAB}!A1", [list(LOG_COLUMNS)])
    sheets.values_update(sid, f"{ABOUT_TAB}!A1", [["register", reg.key], ["about", reg.about],
                                                  ["kept by", "jason and the board: jason writes its columns, the board its own"],
                                                  ["confidential", "yes: directors only" if reg.confidential else "no"],
                                                  ["columns", "; ".join(f"{c.name} ({c.owner.value})" for c in reg.columns)]])
    entry["created"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if reg.book:
        entry["book"] = reg.book
    state[reg.key] = entry
    _save(data_dir, state)
    return entry


def _sheet_ids(sheets: Any, sid: str) -> dict[str, int]:
    body = sheets.get(sid, fields="sheets.properties(sheetId,title)")
    return {s["properties"]["title"]: s["properties"]["sheetId"] for s in body.get("sheets", [])}


def shape(sheets: Any, reg: Register, data_dir: Path, *, force: bool = False) -> int:
    """Header, widths, validation, date format, and warning-only protection; once per spreadsheet unless ``force``."""
    state = _state(data_dir)
    entry = state.get(reg.key) or {}
    sid = entry.get("spreadsheetId")
    if not sid:
        raise ValueError(f"{reg.key} has no spreadsheet yet (ensure first)")
    if entry.get("shaped") and not force:
        return 0
    tab = _sheet_ids(sheets, sid)[reg.tab]
    n = len(reg.columns)
    requests: list[dict[str, Any]] = [
        {"updateSheetProperties": {"properties": {"sheetId": tab, "gridProperties": {"frozenRowCount": 1}},
                                   "fields": "gridProperties.frozenRowCount"}},
        {"repeatCell": {"range": {"sheetId": tab, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": n},
                        "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}}, "fields": "userEnteredFormat.textFormat.bold"}},
    ]
    for i, c in enumerate(reg.columns):
        col = {"sheetId": tab, "startColumnIndex": i, "endColumnIndex": i + 1}
        requests.append({"updateDimensionProperties": {"range": {"sheetId": tab, "dimension": "COLUMNS", "startIndex": i, "endIndex": i + 1},
                                                       "properties": {"pixelSize": c.width}, "fields": "pixelSize"}})
        note = f"{c.owner.value}'s column" + (f": {c.note}" if c.note else "")
        requests.append({"updateCells": {"range": {**col, "startRowIndex": 0, "endRowIndex": 1}, "rows": [{"values": [{"note": note}]}],
                                         "fields": "note"}})
        body = {**col, "startRowIndex": 1, "endRowIndex": ROWS}
        rule = None
        if c.kind is Kind.CHOICE and c.choices:
            rule = {"condition": {"type": "ONE_OF_LIST", "values": [{"userEnteredValue": v} for v in c.choices]}, "showCustomUi": True,
                    "strict": c.owner is Owner.BOARD}
        elif c.kind is Kind.DATE:
            rule = {"condition": {"type": "DATE_IS_VALID"}, "strict": False}
            requests.append({"repeatCell": {"range": body, "cell": {"userEnteredFormat": {"numberFormat": {"type": "DATE", "pattern": "yyyy-mm-dd"}}},
                                            "fields": "userEnteredFormat.numberFormat"}})
        elif c.kind is Kind.CHECKBOX:
            rule = {"condition": {"type": "BOOLEAN"}}
        elif c.kind is Kind.MONEY:
            requests.append({"repeatCell": {"range": body, "cell": {"userEnteredFormat": {"numberFormat": {"type": "CURRENCY", "pattern": "$#,##0.00"}}},
                                            "fields": "userEnteredFormat.numberFormat"}})
        if rule:
            requests.append({"setDataValidation": {"range": body, "rule": rule}})
        if c.owner is Owner.JASON:
            requests.append({"addProtectedRange": {"protectedRange": {"range": {**col, "startRowIndex": 1, "endRowIndex": ROWS},
                                                                      "description": f"jason keeps {c.name}", "warningOnly": True}}})
    requests.append({"addProtectedRange": {"protectedRange": {"range": {"sheetId": tab, "startRowIndex": 0, "endRowIndex": 1},
                                                              "description": "the register's columns: never rename or move", "warningOnly": True}}})
    sheets.batch_update(sid, requests)
    entry["shaped"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    state[reg.key] = entry
    _save(data_dir, state)
    return len(requests)


def _cell(value: Any) -> str:
    return "" if value is None else str(value)


def sync(sheets: Any, reg: Register, data_dir: Path, records: Callable[[], list[dict[str, Any]]],
         apply: Callable[[dict[str, dict[str, str]]], Any] | None = None) -> dict[str, Any]:
    """Read the board's edits, let the caller apply them (``apply``), then write jason's columns and new rows."""
    sid = spreadsheet_id(data_dir, reg)
    if not sid:
        raise ValueError(f"{reg.key} has no spreadsheet yet (jason registers --create {reg.key} --yes)")
    values = sheets.values_get(sid, f"{reg.tab}!A1:{letter(len(reg.columns) + 10)}{ROWS}").get("values") or []
    header = values[0] if values else []
    if tuple(header[: len(reg.names)]) != reg.names:
        raise ValueError(f"{reg.title}'s header changed: {header}; the register needs {list(reg.names)} in that order")
    key = reg.names[0]
    board = [c.name for c in reg.owned(Owner.BOARD)]
    rows: dict[str, tuple[int, list[str]]] = {}
    for n, row in enumerate(values[1:], start=2):
        if row and row[0].strip():
            rows[row[0].strip()] = (n, row + [""] * (len(reg.names) - len(row)))
    before = {str(r[key]): r for r in records()}
    edits: dict[str, dict[str, str]] = {}
    log: list[list[str]] = []
    seen = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for k, (n, row) in rows.items():
        record = before.get(k)
        if record is None:
            continue
        for name in board:
            value = row[reg.names.index(name)].strip()
            if value and value != _cell(record.get(name)).strip():
                edits.setdefault(k, {})[name] = value
                log.append([seen, k, name, _cell(record.get(name)), value, "the board, in the Sheet"])
    if edits and apply is not None:
        apply(edits)
    after = records()
    data: list[dict[str, Any]] = []
    append: list[list[str]] = []
    for record in after:
        k = str(record[key])
        if k not in rows:
            append.append([_cell(record.get(name)) for name in reg.names])
            continue
        n, row = rows[k]
        for i, c in enumerate(reg.columns):
            if c.owner is Owner.JASON and _cell(record.get(c.name)) != row[i]:
                data.append({"range": f"{reg.tab}!{letter(i)}{n}", "values": [[_cell(record.get(c.name))]]})
    if data:
        sheets.values_batch_update(sid, data)
    if append:
        sheets.values_append(sid, f"{reg.tab}!A1", append)
    if log:
        sheets.values_append(sid, f"{LOG_TAB}!A1", log)
    known = {str(r[key]) for r in after}
    return {"boardEdits": sum(len(v) for v in edits.values()), "cellsWritten": len(data), "appended": len(append),
            "logged": len(log), "unknownRows": sorted(k for k in rows if k not in known)}


def registers(community: Any) -> tuple[Register, ...]:
    hook = getattr(community, "registers", None)
    return tuple(hook()) if callable(hook) else ()


def register(community: Any, key: str) -> Register:
    found = next((r for r in registers(community) if r.key == key), None)
    if found is None:
        raise ValueError(f"no register {key!r}; the specification has {', '.join(r.key for r in registers(community)) or 'none'}")
    return found


__all__ = ["ensure", "letter", "register", "registers", "shape", "spreadsheet_id", "sync"]
