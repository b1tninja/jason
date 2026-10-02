"""A register's Sheet: adopted or created, shaped once, and synced by key without overwriting the board's columns."""

from __future__ import annotations

import re

import pytest

from jason.community.registers import Column, Kind, Owner, Register
from jason.tasks import registers as task

REG = Register("items", "Items Register", "Items", (
    Column("id"), Column("title"), Column("status", Owner.BOARD, Kind.CHOICE, ("open", "closed")),
    Column("due", Owner.JASON, Kind.DATE), Column("notes", Owner.BOARD)))


class FakeSheets:
    """Holds one spreadsheet's tabs as lists of rows and records every write."""

    def __init__(self, tabs=None):
        self.tabs = tabs or {}
        self.writes, self.batches, self.created = [], [], []

    def create(self, title, sheet_titles=()):
        self.created.append(title)
        self.tabs = {t: [] for t in sheet_titles}
        return {"spreadsheetId": "S1"}

    def sheet_titles(self, sid):
        return list(self.tabs)

    def get(self, sid, fields=""):
        return {"sheets": [{"properties": {"title": t, "sheetId": i}} for i, t in enumerate(self.tabs)]}

    def batch_update(self, sid, requests):
        self.batches.append(requests)
        for r in requests:
            if "addSheet" in r:
                self.tabs[r["addSheet"]["properties"]["title"]] = []

    def values_get(self, sid, a1):
        tab = a1.split("!")[0]
        return {"values": [list(r) for r in self.tabs.get(tab, [])]}

    def _set(self, tab, row, col, value):
        rows = self.tabs.setdefault(tab, [])
        while len(rows) <= row:
            rows.append([])
        while len(rows[row]) <= col:
            rows[row].append("")
        rows[row][col] = value

    def values_update(self, sid, a1, rows):
        tab, cell = a1.split("!")
        r0 = int(re.sub(r"\D", "", cell) or 1) - 1
        for i, row in enumerate(rows):
            for j, v in enumerate(row):
                self._set(tab, r0 + i, j, v)

    def values_batch_update(self, sid, data):
        self.writes += data
        for d in data:
            tab, cell = d["range"].split("!")
            col = ord(re.sub(r"\d", "", cell)) - 65
            self._set(tab, int(re.sub(r"\D", "", cell)) - 1, col, d["values"][0][0])

    def values_append(self, sid, a1, rows):
        tab = a1.split("!")[0]
        self.tabs.setdefault(tab, []).extend([list(r) for r in rows])


def test_a_register_is_created_with_its_tabs_and_shaped_once(tmp_path) -> None:
    class Drive:
        def child_folder(self, parent, name):
            return ""

        def create_folder(self, name, parent):
            return "F1"

        def move(self, fid, folder):
            self.moved = (fid, folder)

    sheets, drive = FakeSheets(), Drive()
    entry = task.ensure(sheets, drive, REG, tmp_path, folder="Registers")
    assert entry["spreadsheetId"] == "S1" and drive.moved == ("S1", "F1")
    assert sheets.tabs["Items"][0] == ["id", "title", "status", "due", "notes"] and sheets.tabs["Log"][0][0] == "seen"
    assert task.shape(sheets, REG, tmp_path) > 0 and task.shape(sheets, REG, tmp_path) == 0
    rules = [r for r in sheets.batches[-1] if "setDataValidation" in r]
    assert rules[0]["setDataValidation"]["rule"]["condition"]["values"] == [{"userEnteredValue": "open"}, {"userEnteredValue": "closed"}]
    protected = [r["addProtectedRange"]["protectedRange"]["description"] for r in sheets.batches[-1] if "addProtectedRange" in r]
    assert "jason keeps title" in protected and not any("status" in p or "notes" in p for p in protected)


def test_sync_reads_the_boards_edits_writes_only_jasons_cells_and_appends_new_rows(tmp_path) -> None:
    sheets = FakeSheets({"Items": [["id", "title", "status", "due", "notes"],
                                   ["a", "Old title", "closed", "2026-10-01", "done by Pat"],
                                   ["b", "Roof", "", "", ""],
                                   ["x", "a row the board added", "", "", ""]], "Log": [list(task.LOG_COLUMNS)], "About": []})
    task.ensure(sheets, None, REG, tmp_path, adopt="S1")
    store = {"a": {"id": "a", "title": "New title", "status": "open", "due": "2026-10-01", "notes": ""},
             "b": {"id": "b", "title": "Roof", "status": "open", "due": "", "notes": ""},
             "c": {"id": "c", "title": "Pool", "status": "open", "due": "2026-11-01", "notes": ""}}

    def apply(edits):
        for k, changes in edits.items():
            store[k].update(changes)

    result = task.sync(sheets, REG, tmp_path, lambda: [dict(v) for v in store.values()], apply)
    assert store["a"]["status"] == "closed" and store["a"]["notes"] == "done by Pat"        # the board's edits came back
    assert result["boardEdits"] == 2 and result["logged"] == 2 and result["unknownRows"] == ["x"]
    assert [w["range"] for w in sheets.writes] == ["Items!B2"]                               # only jason's changed cell
    assert sheets.tabs["Items"][1] == ["a", "New title", "closed", "2026-10-01", "done by Pat"]
    assert sheets.tabs["Items"][-1][0] == "c" and result["appended"] == 1
    assert [r[2:5] for r in sheets.tabs["Log"][1:]] == [["status", "open", "closed"], ["notes", "", "done by Pat"]]


def test_a_moved_or_renamed_column_stops_the_sync(tmp_path) -> None:
    sheets = FakeSheets({"Items": [["id", "status", "title", "due", "notes"]], "Log": [], "About": []})
    with pytest.raises(ValueError):
        task.ensure(sheets, None, REG, tmp_path, adopt="S1")


def test_column_letters() -> None:
    assert [task.letter(i) for i in (0, 25, 26, 27)] == ["A", "Z", "AA", "AB"]
