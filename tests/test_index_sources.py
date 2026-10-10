"""The index sources for the library, the mail, the reports, and the documentation: each file's flags, decided strictly."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from jason.community import passage_index as pi
from jason.tasks import index_sources as sources
from jason.tasks import library


def _library(data: Path, rows: list[tuple]) -> None:
    """A library store with (id, path, kind, sha256, period, records, confidential) rows and a text file for each id."""
    (data / "library" / "text").mkdir(parents=True)
    with sqlite3.connect(data / library.STORE) as conn:
        conn.execute(library.SCHEMA)
        for doc_id, path, kind, sha, period, records, confidential in rows:
            conn.execute("INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                         (doc_id, "payhoa", path, path.rsplit("/", 1)[-1], kind, "", records, "NAME", period,
                          int(confidential), "", 1.0, "2026-01-01T00:00:00+00:00", sha))
    conn.close()


def _text(data: Path, doc_id: str, words: str) -> None:
    (data / "library" / "text" / f"{doc_id}.txt").write_text(words, encoding="utf-8")


@pytest.fixture()
def data(tmp_path: Path) -> Path:
    _library(tmp_path, [
        ("1", "Meetings/Minutes of January.pdf", "minutes", "aa", "2026-01", "minutes", False),
        # The same bytes filed twice. The open copy sorts first; the copy under Confidential/ makes the document confidential.
        ("2", "Attachments/Budget memo.pdf", "budget", "bb", "2026", "financial_disclosure", False),
        ("3", "Confidential/Budget memo.pdf", "budget", "bb", "2026", "financial_disclosure", True),
        ("4", "Scans/scan0001.pdf", "", "cc", "", "", False),                       # unclassified
        ("5", "Financials/Statement.pdf", "bank_statement", "dd", "2026-02", "reserve_account", True),
        ("6", "Financials/Treasurer's Report.pdf", "treasurer_report", "ee", "2026-02", "interim_financial", False),
        ("7", "Templates/Blank form.docx", "template", "ff", "", "", False),
        ("8", "Meetings/Agenda.pdf", "agenda", "gg", "2026-03", "", False),         # no text on disk
        # An unclassified copy of the minutes: the document is still the minutes, by its classified copy.
        ("9", "Scans/scan0002.pdf", "", "aa", "", "", False),
    ])
    _text(tmp_path, "1", "The board approved the garage door contract by a vote of three to none.\n")
    _text(tmp_path, "2", "The budget memo: the garage door reserve is short.\n")
    _text(tmp_path, "3", "The budget memo: the garage door reserve is short.\n")
    _text(tmp_path, "4", "A scan nobody classified, about a garage door.\n")
    _text(tmp_path, "5", "Statement of account for the reserve fund.\n")
    _text(tmp_path, "6", "Treasurer's report: garage door expenses and the aging summary.\n")
    _text(tmp_path, "7", "Blank form.\n")
    _text(tmp_path, "8", "   \n")

    mail = tmp_path / "mail"
    rows = []

    def letter(mail_id: str, kind: str, text: str, *, source: dict | None = None, credential: bool = False, page: bool = True) -> None:
        folder = mail / mail_id
        folder.mkdir(parents=True)
        (folder / "text.txt").write_text(text, encoding="utf-8")
        if page:
            (folder / "letter.md").write_text(f"# 2026-03-01 A sender ({kind}) [mail {mail_id}]\n\n## Scanned text\n\n{text}", encoding="utf-8")
        rows.append({"mailId": mail_id, "received": "2026-03-01T10:00:00", "sender": "A sender", "from": "A sender", "kind": kind,
                     "text": True, "credential": credential,
                     "source": {"kind": "utility", "misdirected": False} if source is None else source})

    letter("100", "utility bill", "Your water bill for the garage door wash station is due.\n")
    letter("101", "legal notice", "Counsel's letter about the garage door claim.\n", page=False)
    letter("102", "government or tax notice", "Your access code: 4411. Use it to verify ownership of the garage door.\n")
    letter("103", "other", "A letter nobody could sort, about a garage door.\n")
    letter("104", "utility bill", "Statement for another association's garage door.\n",
           source={"kind": "another community association", "misdirected": True})
    letter("105", "vendor invoice or statement", "An owner's statement about a garage door.\n",
           source={"kind": "owner or resident", "misdirected": False})
    # A page on disk the sort does not list, and one whose stored flag is stale: the text itself is read.
    (mail / "106").mkdir()
    (mail / "106" / "letter.md").write_text("# A letter with no row\n\nGarage door estimate.\n", encoding="utf-8")
    letter("107", "utility bill", "Your temporary password for the garage door portal is hunter2.\n")
    (mail / "items.json").write_text(json.dumps({"items": rows}), encoding="utf-8")

    reports = tmp_path / "reports"
    (reports / "property-history").mkdir(parents=True)
    (reports / "property-history" / "unit-1.md").write_text("# 123 Main St\n\nWho held the unit with the garage door.\n", encoding="utf-8")
    (reports / "duties.md").write_text("# The manager's duties\n\nThe garage door maintenance duty and its statute.\n", encoding="utf-8")
    (reports / "new-report.md").write_text("# A report no rule places\n\nGarage door counts.\n", encoding="utf-8")
    return tmp_path


def _by_name(plan: sources.Plan) -> dict[str, pi.IndexFile]:
    return {f"{entry.path.parent.name}/{entry.path.name}": entry for entry in plan.entries}


def test_a_confidential_copy_makes_the_document_confidential_and_an_unclassified_row_is_left_out(data):
    plan = sources.LibrarySource().plan(data)
    found = _by_name(plan)
    assert set(found) == {"text/1.txt", "text/2.txt", "text/5.txt", "text/6.txt"}           # one entry for the two copies
    assert not found["text/1.txt"].confidential
    assert found["text/2.txt"].confidential                                              # by its other copy, under Confidential/
    assert found["text/5.txt"].confidential and found["text/6.txt"].confidential         # a confidential kind; a held kind
    assert plan.left_out == {sources.UNCLASSIFIED: 1, sources.NOT_A_RECORD: 1, sources.NO_TEXT: 1}
    assert plan.held == {"a copy in a confidential folder": 1, "a confidential kind": 1, "a held kind": 1}
    entry = found["text/1.txt"]
    assert (entry.catalog, entry.standing, entry.kind, entry.generated) == ("library", pi.Standing.RECORD, "minutes", False)
    assert entry.context == "Minutes of January.pdf: minutes; period 2026-01; Civil Code 5200 record: minutes"


def test_a_copy_whose_stored_flag_is_stale_is_still_held_by_its_folder_and_kind(data):
    source = sources.LibrarySource()
    assert source.copy_held({"kind": "budget", "path": "confidential/x.pdf", "confidential": False}) == "a copy in a confidential folder"
    assert source.copy_held({"kind": "membership_list", "path": "x.csv", "confidential": False}) == "a confidential kind"
    assert source.copy_held({"kind": "a_kind_since_removed", "path": "x.pdf", "confidential": False}) == "a kind the code does not know"
    assert source.copy_held({"kind": "minutes", "path": "Meetings/x.pdf", "confidential": False}) == ""


def test_a_vision_reading_of_every_page_is_the_text_file_and_a_partial_one_is_not(data):
    folder = data / "library" / "text"
    (folder / "1.vision.txt").write_text("The vision model's reading.\n", encoding="utf-8")
    (folder / "1.vision.json").write_text(json.dumps({"pages": 4, "pagesRead": 2}), encoding="utf-8")
    assert library.text_path(data, "1") == folder / "1.txt"
    (folder / "1.vision.json").write_text(json.dumps({"pages": 4, "pagesRead": 4}), encoding="utf-8")
    assert library.text_path(data, "1") == folder / "1.vision.txt"
    assert library.text_path(data, "8") is None and library.text_path(data, "missing") is None
    before = sorted(p.name for p in folder.iterdir())
    sources.LibrarySource().plan(data)
    assert sorted(p.name for p in folder.iterdir()) == before                             # the source writes nothing


def test_a_letter_with_an_access_code_is_never_indexed_and_an_unsorted_one_is_confidential(data):
    plan = sources.MailSource().plan(data)
    found = _by_name(plan)
    assert set(found) == {"100/letter.md", "101/text.txt", "103/letter.md", "106/letter.md"}
    assert not found["100/letter.md"].confidential
    assert found["101/text.txt"].confidential                  # an attorney's letter: no page was written, its text is read
    assert found["103/letter.md"].confidential                 # the sort left it unknown
    assert found["106/letter.md"].confidential                 # no stored row at all
    assert plan.left_out == {"carries a PIN, a passcode, a password, or an access code": 2,
                             "another association's mail: not the association's record": 1,
                             "an owner's or resident's own account": 1}
    entry = found["100/letter.md"]
    assert (entry.catalog, entry.standing, entry.kind) == ("mail", pi.Standing.RECORD, "")
    assert entry.context == "A letter the association received 2026-03-01 from A sender (mail 100); sorted as utility bill"


def test_a_credential_is_read_from_the_text_whatever_the_stored_row_says(data):
    assert sources.mail_call({"kind": "utility bill", "credential": False, "source": {"kind": "utility"}},
                             "Your PIN: 1234") == (sources.Call.NEVER, sources.MAIL_RULES[0].name)
    assert sources.mail_call({"kind": "utility bill", "credential": True, "source": {"kind": "utility"}}, "A bill.")[0] is sources.Call.NEVER
    assert sources.mail_call({"kind": "utility bill", "source": {"kind": "utility"}}, "A bill.") == (sources.Call.OPEN, "")
    # A row sorted without the profile never asked whose mail it is: unknown, so confidential.
    assert sources.mail_call({"kind": "utility bill", "source": {}}, "A bill.")[0] is sources.Call.CONFIDENTIAL
    assert sources.mail_call({"kind": "a kind since removed", "source": {"kind": "utility"}}, "A bill.")[0] is sources.Call.CONFIDENTIAL


def test_a_sort_that_cannot_be_read_makes_every_letter_confidential(data):
    (data / "mail" / "items.json").write_text("{not json", encoding="utf-8")
    plan = sources.MailSource().plan(data)
    assert plan.entries and all(entry.confidential for entry in plan.entries)
    assert "102" not in {entry.path.parent.name for entry in plan.entries}                # the access code is still read


def test_a_report_no_rule_places_is_confidential(data):
    plan = sources.ReportsSource().plan(data)
    found = _by_name(plan)
    assert found["property-history/unit-1.md"].confidential and found["reports/new-report.md"].confidential
    duties = found["reports/duties.md"]
    assert not duties.confidential and duties.generated and duties.standing is pi.Standing.PAGE
    assert duties.context == "jason's report: The manager's duties"
    assert plan.held == {sources.REPORT_RULES[0].why: 1, sources.UNPLACED: 1}
    assert sources.report_call("Property-History/x.md")[0] and sources.report_call("deep/duties.md") == (True, sources.UNPLACED)


def test_a_letter_or_an_open_report_that_names_a_member_is_confidential(data, monkeypatch):
    import re

    monkeypatch.setattr(sources, "member_pattern", lambda data_dir: re.compile(r"\bPat\s+Example\b", re.IGNORECASE))
    (data / "reports" / "duties.md").write_text("# The manager's duties\n\nPat  Example asked about the garage door.\n", encoding="utf-8")
    (data / "mail" / "100" / "text.txt").write_text("A bill for the unit of pat example.\n", encoding="utf-8")
    assert _by_name(sources.ReportsSource().plan(data))["reports/duties.md"].confidential
    assert _by_name(sources.MailSource().plan(data))["100/letter.md"].confidential


def test_members_names_come_from_the_roster_and_no_roster_is_no_pattern(tmp_path):
    assert sources.member_pattern(tmp_path) is None
    with sqlite3.connect(tmp_path / "payhoa.db") as conn:
        conn.execute("CREATE TABLE people (name TEXT)")
        conn.execute("INSERT INTO people VALUES ('Pat Q. Example')")
    conn.close()
    pattern = sources.member_pattern(tmp_path)
    assert pattern.search("a letter to Example Pat") and pattern.search("PAT EXAMPLE") and not pattern.search("Pat Sample")


def test_the_documentation_is_indexed_from_outside_the_data_directory(data, tmp_path_factory):
    checkout = tmp_path_factory.mktemp("checkout")
    (checkout / "docs").mkdir()
    (checkout / "AGENTS.md").write_text("# jason\n\nHow jason decides who maintains a garage door.\n", encoding="utf-8")
    (checkout / "docs" / "mail.md").write_text("# The mail\n\nHow the mail is sorted.\n", encoding="utf-8")
    (checkout / "docs" / "console").mkdir()
    (checkout / "docs" / "console" / "screens.md").write_text("# Screens\n", encoding="utf-8")
    source = sources.DocsSource(root=checkout)
    entries = list(source.entries(data))
    assert [e.path.name for e in entries] == ["AGENTS.md", "mail.md"]                    # docs/*.md, not its subfolders
    assert all(e.generated and not e.confidential and e.standing is pi.Standing.PAGE for e in entries)
    governing = data / "governing"
    governing.mkdir()
    (governing / "ccrs.md").write_text("# Declaration\n\nEach Owner shall maintain the garage door.\n", encoding="utf-8")
    inside = pi.IndexSource("records", "governing", pi.Standing.RECORD)
    report = pi.build(data, sources=(inside, source), kind_of=lambda name: "")
    assert report.files == 3
    loaded = pi.load(data, vectors=False)
    paths = {p.path for p in loaded.passages}
    assert (checkout / "AGENTS.md").resolve() in paths and (data / "governing" / "ccrs.md") in paths
    assert {p.path.name for p in pi.load(data, pi.Scope(folders=("governing",)), vectors=False).passages} == {"ccrs.md"}
    hits = pi.search("who maintains a garage door", data_dir=data, scope=pi.Scope(catalogs=("docs",)), mode="keyword")
    assert hits and hits[0].hit.passage.path == (checkout / "AGENTS.md").resolve() and hits[0].row.generated
    # A second build cuts nothing, and a file gone from the checkout leaves the index.
    assert pi.build(data, sources=(inside, source), kind_of=lambda name: "").cut == 0
    (checkout / "docs" / "mail.md").unlink()
    assert pi.build(data, sources=(inside, source), kind_of=lambda name: "").removed == 1
    assert sources.DocsSource(root=checkout / "nowhere").plan(data).entries == []


def _build(data: Path) -> None:
    pi.build(data, sources=(sources.LibrarySource(), sources.MailSource(), sources.ReportsSource()), kind_of=lambda name: "")


def test_a_board_search_sees_the_confidential_rows_and_the_default_scope_does_not(data):
    _build(data)
    default = pi.search("garage door", data_dir=data, k=30, mode="keyword")
    assert default and not any(h.row.confidential for h in default)
    assert {h.hit.passage.path.parent.name + "/" + h.hit.passage.path.name for h in default} == {
        "text/1.txt", "100/letter.md", "reports/duties.md"}
    board = pi.search("garage door", data_dir=data, scope=pi.Scope(confidential=True), k=30, mode="keyword")
    seen = {h.hit.passage.path.parent.name + "/" + h.hit.passage.path.name: h.row for h in board}
    assert {"text/2.txt", "text/6.txt", "101/text.txt", "103/letter.md", "106/letter.md", "property-history/unit-1.md",
            "reports/new-report.md"} <= set(seen)
    assert seen["text/2.txt"].confidential and seen["text/2.txt"].kind == "budget" and seen["text/2.txt"].catalog == "library"
    # Never in the index, whatever the scope: the letters with a credential, the unclassified scan, the other association's.
    everything = {p.path.parent.name + "/" + p.path.name for p in pi.load(data, pi.Scope(confidential=True), vectors=False).passages}
    assert not everything & {"102/letter.md", "102/text.txt", "107/letter.md", "107/text.txt", "text/4.txt", "104/letter.md",
                             "105/letter.md", "text/3.txt", "text/7.txt"}


def test_document_search_holds_confidential_files_back_unless_asked_and_a_case_only_when_named(data):
    from jason.mcp.county import document_search

    case = data / "cases" / "example" / "files"
    case.mkdir(parents=True)
    (case / "transcript.txt").write_text("Counsel on the garage door claim.\n", encoding="utf-8")
    pi.build(data, kind_of=lambda name: "", sources=(
        sources.LibrarySource(), sources.MailSource(), sources.ReportsSource(),
        pi.IndexSource("case-example", "cases/example/files", pi.Standing.EVIDENCE, confidential=True)))
    shared = document_search("garage door", data_dir=data, mode="keyword", k=30)
    assert shared["hits"] and not any(h["confidential"] for h in shared["hits"])
    assert next(h for h in shared["hits"] if h["catalog"] == "library")["context"].startswith("Minutes of January.pdf: minutes")
    asked = document_search("garage door", data_dir=data, mode="keyword", k=30, include_confidential=True)
    catalogs = {h["catalog"] for h in asked["hits"] if h["confidential"]}
    assert catalogs == {"library", "mail", "reports"}                                     # the case is not named
    named = document_search("garage door", data_dir=data, mode="keyword", k=30, catalog="case-example,library")
    held = {h["catalog"] for h in named["hits"] if h["confidential"]}
    assert held == {"case-example"} and {h["catalog"] for h in named["hits"]} == {"case-example", "library"}
    assert any("never in the index" in c for c in asked["caveats"])


def test_a_file_another_source_gives_openly_is_held_when_the_library_holds_its_bytes_as_confidential(data):
    import hashlib

    from jason.commands import index

    mirror = data / "governing"
    mirror.mkdir()
    (mirror / "Budget memo.pdf").write_bytes(b"%PDF the budget memo")
    (mirror / "Budget memo.pdf.md").write_text("# Budget memo\n\nThe garage door reserve is short.\n", encoding="utf-8")
    (mirror / "rules.md").write_text("# Rules\n\nKeep the garage door closed.\n", encoding="utf-8")
    sha = hashlib.sha256(b"%PDF the budget memo").hexdigest()
    with sqlite3.connect(data / library.STORE) as conn:
        conn.execute("UPDATE documents SET sha256 = ? WHERE id IN ('2', '3')", (sha,))
    conn.close()
    folder = pi.IndexSource("records", "governing", pi.Standing.RECORD)
    held = sources.library_holds(data)
    assert held(mirror / "Budget memo.pdf.md") and held(mirror / "Budget memo.pdf") and not held(mirror / "rules.md")
    pi.build(data, sources=(folder,), kind_of=lambda name: "", held=held)
    assert {p.path.name for p in pi.load(data, vectors=False).passages} == {"rules.md"}
    assert {p.path.name for p in pi.load(data, pi.Scope(confidential=True), vectors=False).passages} == {"rules.md", "Budget memo.pdf.md"}
    (row,) = index.plan(data, (folder,))
    assert (row["files"], row["confidential"], row["confidentialBy"]) == (2, 1, {index.LIBRARY_HOLDS: 1})
    # Without the test the copy is open: this is the leak the test closes.
    pi.build(data, sources=(folder,), kind_of=lambda name: "")
    assert "Budget memo.pdf.md" in {p.path.name for p in pi.load(data, vectors=False).passages}


def test_a_build_refuses_a_search_scope_instead_of_ignoring_it(monkeypatch, capsys):
    """`--catalog` on a build used to be ignored: the whole index was re-cut and re-embedded. A build drops the files that are
    gone, so honoring it would delete the other catalogs' passages; it is refused, and nothing is built."""
    from argparse import Namespace

    from jason.commands import index

    monkeypatch.setattr(pi, "build", lambda *a, **k: (_ for _ in ()).throw(AssertionError("built")))
    for flag in ("catalog", "standing", "kind", "folder"):
        scope = {"catalog": [], "standing": [], "kind": [], "folder": [], "confidential": False, flag: ["x"]}
        assert index.cmd_index(Namespace(build=True, plan=False, no_embed=True, search=None, json=False, **scope)) == 2
        assert f"--{flag} scope a search" in capsys.readouterr().err
    assert index.cmd_index(Namespace(build=True, plan=False, no_embed=True, search=None, json=False, catalog=[], standing=[],
                                     kind=[], folder=[], confidential=True)) == 2


def test_the_build_takes_the_new_sources_and_the_plan_counts_them(data, monkeypatch):
    from jason.commands import index

    monkeypatch.setattr(sources, "checkout", lambda: None)
    assert {"library", "mail", "reports", "docs"} <= {name for source in index.sources() for name in source.catalogs}
    rows = {row["catalog"]: row for row in index.plan(data, sources.sources())}
    assert rows["library"]["files"] == 4 and rows["library"]["confidential"] == 3
    assert rows["library"]["leftOut"][sources.UNCLASSIFIED] == 1
    assert rows["mail"]["files"] == 4 and rows["mail"]["confidential"] == 3
    assert rows["reports"] == {"catalog": "reports", "files": 3, "confidential": 2, "leftOut": {},
                               "confidentialBy": {sources.REPORT_RULES[0].why: 1, sources.UNPLACED: 1}}
    assert rows["docs"]["files"] == 0
