"""A collection's summary page: generated from the stores, indexed as a page, and carried by a pack once, labeled.
Everything here is made up."""

from __future__ import annotations

import json
import re
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from jason.community import passage_index as pi
from jason.community.context_pack import COLLECTION_SUMMARY_CHARS, assemble
from jason.community.document_collections import (SUMMARY_LABEL, Collection, collection, collections,
                                                  companion_summary)
from jason.community.legal_cases import CaseDuty, CaseEvent, CaseRole, CaseStatus, Forum, LegalCase
from jason.community.prompts import Audience, FactSource, TaskKind, TaskPrompt
from jason.community.symbols import DocumentKind
from jason.tasks import collection_pages as cp
from jason.tasks import review_store
from jason.tasks.case_files import FileState, catalog_name, index_sources, inventory

TODAY = date(2026, 10, 4)
KEY = "example-26cv000002"
CASE = LegalCase(
    KEY, "Example v. Example Commons", Forum.SUPERIOR_COURT, CaseRole.DEFENDANT, CaseStatus.PENDING,
    case_number="26CV000002", drive_folder="26CV000002 - Example", held_back=("*edical*",),
    events=(CaseEvent(date(2026, 1, 5), "complaint served on the association", "the case file: Complaint.pdf"),
            CaseEvent(date(2026, 3, 2), "hearing on the demurrer first set")),
    duties=(CaseDuty("CIV 4935(a)", "litigation is considered in executive session", met=True, evidence="minutes of January 12, 2026"),
            CaseDuty("CCP 430.40(a)", "respond to the complaint", due=date(2026, 2, 4))))
NAME = catalog_name(CASE)

NOTICE = ("Date: February 3, 2026\n\n"
          "The hearing on the demurrer is set for March 2, 2026 at 9:00 a.m. in Department 53. "
          "The moving papers were served by mail on or about January 20, 2026.\n")
ORDER = ("April 6, 2026\n\n"
         "The court continued the hearing on the demurrer to May 4, 2026 and ordered the parties to meet and confer. "
         "The board approved Invoice No. 1042 for a total of $500.00.\n")
EXHIBIT = "Our records show that Invoice No. 1042 has a total of $450.00 after the credit of March 9, 2026.\n"
TRANSCRIPT = "00:00:01 Speaker 1: We met on March 5th and talked about the garage door for an hour.\n"
TRANSCRIPT_NAME = "GMT20260115-173000_Recording.transcript.vtt.txt"
HELD_NAMES = ("Medical record.pdf", "Medical notes.txt", "Veterinary and medical bills.jpeg")
ASK = "When is the hearing on the demurrer, and was the hearing continued?"

TASK = TaskPrompt(TaskKind.RULE_REMINDER, "A reminder of a rule.", Audience.BOARD,
                  topics=("the hearing on the demurrer",), documents=(DocumentKind.DECLARATION,),
                  facts=(FactSource("open_items", why="what is open"),), considerations=("Does it say when?",))


class Community:
    """A made-up association with one legal case that has a case file."""

    def prompt_context(self):
        return ["Example Commons, 12 units"]

    def classify_document(self, name, folder=None):
        return None

    def legal_cases(self):
        return (CASE,)


def _kind(name: str) -> str:
    return "notice" if name.startswith("Notice") else "order" if name.startswith("Minute") else ""


def _row(n: int, name: str, action: str = "download", held: bool = False, local: str | None = None, **more) -> dict:
    return {"id": str(n), "name": name, "path": name, "mimeType": "application/pdf", "md5": "", "modified": "",
            "heldBack": held, "action": action, "local": name if local is None else local, **more}


@pytest.fixture()
def data(tmp_path: Path) -> Path:
    files = tmp_path / "cases" / KEY / "files"
    files.mkdir(parents=True)
    (files / "Notice of hearing.txt").write_text(NOTICE, encoding="utf-8")
    (files / "Minute order.pdf").write_bytes(b"%PDF-1.4 a text layer")
    (files / "Minute order.pdf.txt").write_text(ORDER, encoding="utf-8")
    (files / "Exhibit A.pdf").write_bytes(b"%PDF-1.4 four scanned pages")
    (files / "Exhibit A.pdf.txt").write_text(EXHIBIT, encoding="utf-8")
    (files / "Scan.pdf").write_bytes(b"%PDF-1.4 an image no reader read")
    (files / "Photo log.pdf").write_bytes(b"%PDF-1.4 fetched and not read yet")
    (files / TRANSCRIPT_NAME).write_text(TRANSCRIPT, encoding="utf-8")
    (files / "Medical notes.txt").write_text("Seen on March 1, 2026 for a bite to the left hand.", encoding="utf-8")
    manifest = {"case": KEY, "caseNumber": CASE.case_number, "driveFolder": CASE.drive_folder, "files": [
        _row(1, "Notice of hearing.txt"), _row(2, "Minute order.pdf"), _row(3, "Exhibit A.pdf"), _row(4, "Scan.pdf"),
        _row(5, "Photo log.pdf"), _row(6, "GMT20260115-173000_Recording.transcript.vtt", local=TRANSCRIPT_NAME),
        _row(7, "Medical record.pdf", action="held back", held=True), _row(8, "Medical notes.txt", held=True),
        _row(9, "Veterinary and medical bills.jpeg", action="listed", held=True, local=""),
        _row(10, "Garage door.jpeg", action="listed", local=""), _row(11, "Recording.mp4", action="listed", local=""),
        _row(12, "Answer.pdf", error="the download failed"),
    ], "extracts": {
        "Minute order.pdf": {"text": "Minute order.pdf.txt", "method": "text layer", "sha256": "a", "pages": 2, "version": 1},
        "Exhibit A.pdf": {"text": "Exhibit A.pdf.txt", "method": "ocr", "engine": "made-up-ocr", "sha256": "b", "pages": 4,
                          "scanPages": 4, "unreadPages": 1, "version": 1},
        "Scan.pdf": {"method": "unreadable", "sha256": "c", "reason": "image-only; no reader gave words", "pages": 1,
                     "scanPages": 1, "unreadPages": 1, "version": 1},
    }}
    (tmp_path / "cases" / KEY / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return tmp_path


def _case() -> Collection:
    return collection(Community(), KEY)


def _sources() -> tuple:
    return (*index_sources((CASE,)), *cp.index_sources(collections(Community())))


def _build(data: Path) -> None:
    pi.build(data, sources=_sources(), kind_of=_kind)


def _summary(data: Path) -> cp.Summary:
    return cp.summarize(Community(), data, _case(), today=TODAY)


def _section(page: str, heading: str, mark: str = "## ") -> str:
    """One section's body: from its heading to the next heading of the same level."""
    start = page.index(f"\n{mark}{heading}\n") + 1
    end = page.find(f"\n{mark}", start + len(mark))
    return page[start: end if end != -1 else len(page)]


def _pack(data: Path, task: TaskPrompt = TASK, **kw):
    return assemble(Community(), task, data, mode="keyword", law=[], files=lambda kind: [],
                    fact_runner=lambda tool, args: {"tool": tool, "open": 2}, **kw)


# --- the folder's inventory -------------------------------------------------------------------------------------------

def test_the_inventory_gives_each_file_s_state_and_counts_the_held_ones(data):
    found = inventory(data, CASE)
    assert {f.name: f.state for f in found.files} == {
        "Notice of hearing.txt": FileState.TEXT, TRANSCRIPT_NAME: FileState.TEXT,
        "Minute order.pdf": FileState.EXTRACTED, "Exhibit A.pdf": FileState.EXTRACTED,
        "Photo log.pdf": FileState.NO_EXTRACT, "Scan.pdf": FileState.UNREADABLE,
        "Garage door.jpeg": FileState.LISTED, "Recording.mp4": FileState.LISTED, "Answer.pdf": FileState.FAILED}
    by_name = {f.name: f for f in found.files}
    assert by_name["Exhibit A.pdf"].text == "Exhibit A.pdf.txt" and by_name["Exhibit A.pdf"].extract.unread_pages == 1
    assert by_name["Garage door.jpeg"].why == "a .jpeg file the fetch does not take" and not by_name["Scan.pdf"].readable
    # Three files are held back: one never fetched, one on disk, one the fetch would only have listed.
    assert found.held_back == 3 and found.fetched
    assert not any(held in f.name or held in f.text for f in found.files for held in HELD_NAMES)
    assert inventory(data, replace(CASE, key="nothing-fetched")) == type(found)()
    # Two held files the listing gives one local name (a Doc and its export) are two files.
    path = data / "cases" / KEY / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["files"].append(_row(13, "Medical record", action="held back", held=True, local="Medical record.pdf"))
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert inventory(data, CASE).held_back == 4


# --- the page ---------------------------------------------------------------------------------------------------------

def test_the_page_carries_its_header_its_sections_and_its_confidentiality(data):
    _build(data)
    summary = _summary(data)
    page = summary.markdown(TODAY)
    assert page.startswith("# Summary: Example v. Example Commons\n\n- Generated: by jason on 2026-10-04, by rule (no model), from the 4 documents")
    assert "- Standing: a summary, not the record. Every statement names the file and the passage it rests on." in page
    assert "Nothing here finds that an event happened: it says only that a document says so." in page
    assert "- Confidential: yes. 4 of its sources are held back unless asked; for directors and counsel only." in page
    assert f"- Collection: {KEY} (legal case). Its material is evidence gathered for this matter: neither the record nor the law." in page
    assert f"- Rebuilt, never edited: jason collection {KEY} --write writes this page again whole from the stores." in page
    headings = [line[3:] for line in page.splitlines() if line.startswith("## ")]
    assert headings == [cp.WHAT, "The specification's record of the matter", cp.FILES, cp.MISSING, cp.QUESTIONS,
                        cp.CONFLICTS, cp.CHRONOLOGY, "Caveats"]
    assert summary.confidential and summary.as_dict()["confidential"] and summary.as_dict()["standing"] == "a summary, not the record"
    assert "never quoted in place of the documents" in _section(page, "Caveats")
    # An open collection's page says it is open.
    files = replace(_case(), confidential=False, scope=pi.Scope(catalogs=("nothing",)))
    assert "- Confidential: no." in cp.summarize(Community(), data, replace(files, key="open")).markdown(TODAY)


def test_every_chronology_line_names_its_file_and_passage(data):
    _build(data)
    page = _summary(data).markdown(TODAY)
    chronology = _section(page, cp.CHRONOLOGY)
    lines = chronology.splitlines()
    bullets = [n for n, line in enumerate(lines) if line.startswith("- ")]
    names = ("Notice of hearing.txt", "Minute order.pdf.txt", "Exhibit A.pdf.txt", TRANSCRIPT_NAME)
    assert len(bullets) == 7
    for n in bullets:
        assert re.match(r"- \d{4}-\d{2}-\d{2}( \(on or about\))?: ", lines[n])        # it opens with its day
        assert any(name in lines[n] for name in names) and "[evidence" in lines[n]    # its file, and what the file is
        assert ", passage " in lines[n] or lines[n].endswith("The name is:")          # its place, or the name itself
        assert lines[n + 1].startswith("  > ")                                        # the document's own words
    # An extract's line says which file it is the text of and how that file was read.
    assert "Exhibit A.pdf.txt (Exhibit A.pdf: OCR: made-up-ocr; may misread" in chronology
    # The documents' own dates sit apart from the dates the documents speak about.
    own, other, about = (_section(chronology, h, "### ") for h in (cp.OWN_DATES, cp.OTHER_DATES, cp.ABOUT_DATES))
    assert own.count("\n- ") == 2 and "> Date: February 3, 2026" in own and "> April 6, 2026" in own
    assert "March 2, 2026" not in own and "May 4, 2026" not in own
    assert other.count("\n- ") == 1 and f"> {TRANSCRIPT_NAME}" in other and "a date in the file's name" in other
    assert about.count("\n- ") == 4 and "> The hearing on the demurrer is set for March 2, 2026" in about
    assert "the document's own date at its head: 2026-04-06" in about
    assert about.index("2026-01-20 (on or about)") < about.index("2026-03-02:") < about.index("2026-05-04:")
    assert "None is a finding that the event happened." in chronology


def test_the_specification_s_events_are_in_their_own_section_never_merged(data):
    _build(data)
    summary = _summary(data)
    page = summary.markdown(TODAY)
    record = _section(page, "The specification's record of the matter")
    assert "the specification's record of the matter: the profile's entries, confirmed by a person" in record
    assert "None is a quote from a file" in record
    for line in ("- Matter: Example v. Example Commons", "- Forum: Superior Court", "- The association's role: defendant",
                 "- Status: pending"):
        assert line in record
    events = _section(record, cp.RECORDED_EVENTS, "### ")
    assert events.count("\n- ") == 2
    assert "- 2026-01-05: complaint served on the association (recorded in: the case file: Complaint.pdf)" in events
    assert "- 2026-03-02: hearing on the demurrer first set" in events
    duties = _section(record, cp.RECORDED_DUTIES, "### ")
    assert "- Duty (CCP 430.40(a)), due 2026-02-04: respond to the complaint. The record does not show it either way." in duties
    assert "The record shows it met. (minutes of January 12, 2026)" in duties
    # A document speaks of the same day (the notice sets the hearing for March 2): the two are kept apart.
    chronology = _section(page, cp.CHRONOLOGY)
    assert "first set" not in chronology and "complaint served" not in chronology and "2026-03-02:" in chronology
    assert "not merged here" in chronology and "set for March 2, 2026" not in record
    assert "26CV000002" not in page                               # only what the collection's context holds
    told = summary.as_dict()
    assert [e["source"] for e in told["chronology"]["recorded"]] == ["the specification's record"] * 2
    assert not any("first set" in e["quote"] for e in told["chronology"]["events"])


def test_files_are_listed_by_how_each_was_read_and_a_held_back_file_is_counted_never_named(data):
    _build(data)
    summary = _summary(data)
    page = summary.markdown(TODAY)
    files = _section(page, cp.FILES)
    assert "| File | Kind | Standing | How its words were read | Pages unread | Dated statements |" in files
    assert "| Notice of hearing.txt | notice | evidence | text, as it was fetched |  | 3 |" in files
    assert "| Minute order.pdf | order | evidence | text layer | 0 | 2 |" in files
    assert f"| {TRANSCRIPT_NAME} |  | evidence | text, as it was fetched |  | 1 |" in files
    assert "| Exhibit A.pdf |  | evidence | OCR: made-up-ocr | 1 of 4 | 1 |" in files
    assert "| Scan.pdf |  | not in the index | not read: image-only; no reader gave words | 1 of 1 |  |" in files
    assert "| Photo log.pdf |  | not in the index | not read: no text extract yet: jason cases --extract-text |  |  |" in files
    assert "| Garage door.jpeg |  | not in the index | not read: a .jpeg file the fetch does not take |  |  |" in files
    assert "| Answer.pdf |  | not in the index | not read: the download failed |  |  |" in files
    assert files.index("| Notice of hearing.txt") < files.index("| Answer.pdf")       # the files with text come first
    assert "Held back by the collection's rule: 3 files, not fetched or read. None is named on this page." in files
    assert summary.how_read() == {"OCR: made-up-ocr": 1, "not read": 5, "text layer": 1, "text, as it was fetched": 2}
    counts = summary.counts()
    assert (counts["files"], counts["filesWithText"], counts["filesIndexed"], counts["heldBack"], counts["pagesUnread"]) == (9, 4, 4, 3, 2)
    # A held-back file is in a count and nowhere else: not its name, and not a word of the one on disk.
    everything = page + json.dumps(summary.as_dict())
    for held in (*HELD_NAMES, "Medical", "edical record", "bite to the left hand", "March 1, 2026"):
        assert held not in everything
    assert "Held back by the collection's rule: 3 files, not fetched, not read, and not named here." in page


def test_what_is_missing_or_unread_is_said(data):
    _build(data)
    summary = _summary(data)
    gaps = {gap.key: gap for gap in summary.gaps() if gap.key != "no-text"}
    no_text = [gap.text for gap in summary.gaps() if gap.key == "no-text"]
    assert no_text == ["No text for 1 file (the download failed): Answer.pdf.",
                       "No text for 1 file (a .jpeg file the fetch does not take): Garage door.jpeg.",
                       "No text for 1 file (no text extract yet: jason cases --extract-text): Photo log.pdf.",
                       "No text for 1 file (a .mp4 file the fetch does not take): Recording.mp4.",
                       "No text for 1 file (image-only; no reader gave words): Scan.pdf."]
    assert gaps["pages-unread"].text.startswith("Exhibit A.pdf: 1 of 4 pages are images no reader gave words for")
    assert "which may misread, for 1 file: Exhibit A.pdf. Check a quote against the file." in gaps["may-misread"].text
    assert gaps["no-year"].count == 1 and "1 mention of a month and a day with no year" in gaps["no-year"].text
    assert gaps["held-back"].count == 3 and "no-stored-reading" in gaps and "not-indexed" not in gaps
    missing = _section(summary.markdown(TODAY), cp.MISSING)
    assert missing.count("\n- ") == len(summary.gaps()) == 10
    # Text on disk that the index does not hold is said, and so is a folder never fetched.
    (data / "cases" / KEY / "files" / "Late filing.txt").write_text("Filed on June 1, 2026.", encoding="utf-8")
    late = {gap.key: gap for gap in _summary(data).gaps()}
    assert "for 1 file: Late filing.txt. Run jason index --build." in late["not-indexed"].text

    class Bare(Community):
        def legal_cases(self):
            return (replace(CASE, key="example-bare", drive_folder="A folder never fetched"),)

    bare = cp.summarize(Bare(), data, collection(Bare(), "example-bare"), today=TODAY)
    assert [gap.key for gap in bare.gaps()][0] == "not-fetched" and not bare.files
    assert "The passage index holds no file under the collection's scope." in bare.markdown(TODAY)


def test_the_open_questions_are_the_facts_the_stores_leave_undetermined(data):
    _build(data)
    summary = _summary(data)
    questions = summary.questions()
    assert ("Was this duty met: respond to the complaint (CCP 430.40(a), due 2026-02-04)? The specification's record "
            "does not show it either way.") in questions
    assert not any("executive session" in q for q in questions)                       # the record shows that one met
    # The specification's event of January 5 has no statement of that day in the files; its event of March 2 has one.
    served = [q for q in questions if "complaint served on the association" in q]
    assert len(served) == 1 and "on 2026-01-05 (it names its record as: the case file: Complaint.pdf)" in served[0]
    assert "No statement dated that day was read in the collection's files." in served[0]
    assert not any("first set" in q for q in questions)
    assert any(q.startswith('Which value holds for invoice 1042: the amount under "total"?') and "jason picks neither" in q
               for q in questions)
    undated = [q for q in questions if q.startswith("What is the date of ")]
    assert len(undated) == 2 and any(f"{TRANSCRIPT_NAME}? No date line or labeled date was read at its head (its name prints "
                                     "20260115, which is not taken for the document's own date)." in q for q in undated)
    assert any("Exhibit A.pdf?" in q for q in undated)
    assert any(q.startswith("On what day: Notice of hearing.txt gives January 20, 2026 as on or about") for q in questions)
    asked = _section(summary.markdown(TODAY), cp.QUESTIONS)
    assert asked.count("\n- ") == len(questions) == 6 and "jason answers none" in asked


def test_a_conflict_of_fact_keeps_both_sides_with_their_sources(data):
    _build(data)
    summary = _summary(data)
    conflicts = _section(summary.markdown(TODAY), cp.CONFLICTS)
    assert summary.counts()["conflicts"] == 1 and '### 1. invoice 1042: the amount under "total"' in conflicts
    assert "- Value: $500.00" in conflicts and "- Value: $450.00" in conflicts
    assert "Minute order.pdf.txt (Minute order.pdf: text layer) [evidence, order, confidential], passage 0" in conflicts
    assert "Exhibit A.pdf.txt (Exhibit A.pdf: OCR: made-up-ocr; may misread" in conflicts
    assert "> The board approved Invoice No. 1042 for a total of $500.00." in conflicts
    assert "jason picks neither" in conflicts
    quiet = cp.summarize(Community(), data, replace(_case(), scope=replace(_case().scope, kinds=("notice",))), today=TODAY)
    assert "No conflict was found by the rules. That is not a finding that the documents agree." in quiet.markdown(TODAY)


def test_rebuilding_with_unchanged_inputs_writes_the_same_bytes_apart_from_the_date_line(data):
    _build(data)
    path = cp.write(data, _summary(data), today=TODAY)
    assert path == data / "collections" / KEY / "summary.md" == cp.summary_path(data, _case())
    first = path.read_bytes()
    assert cp.write(data, _summary(data), today=TODAY).read_bytes() == first          # the same day: the same bytes
    later = cp.write(data, _summary(data), today=date(2026, 12, 25)).read_bytes()
    differing = [(a, b) for a, b in zip(first.splitlines(), later.splitlines()) if a != b]
    assert len(first.splitlines()) == len(later.splitlines()) and len(differing) == 1
    assert differing[0][0].startswith(b"- Generated: by jason on 2026-10-04") and differing[0][1].startswith(b"- Generated: by jason on 2026-12-25")
    # The page is written whole: a change made by hand is gone after the next write.
    path.write_text(path.read_text(encoding="utf-8") + "\nA note added by hand.\n", encoding="utf-8")
    assert cp.write(data, _summary(data), today=TODAY).read_bytes() == first


# --- the index --------------------------------------------------------------------------------------------------------

def test_the_page_is_indexed_as_a_confidential_generated_page_in_the_case_s_catalog(data):
    _build(data)
    members = pi.count(data, _case().scope)
    assert members[0] == 4
    before = _summary(data).markdown(TODAY)
    cp.write(data, _summary(data), today=TODAY)
    (source,) = cp.index_sources(collections(Community()))
    (entry,) = source.entries(data)
    assert (entry.catalog, entry.standing, entry.generated, entry.confidential, entry.kind) == (NAME, pi.Standing.PAGE, True, True, "")
    assert entry.path == data / "collections" / KEY / "summary.md" and source.catalogs == (NAME,)
    assert entry.context == f"{SUMMARY_LABEL} (Example v. Example Commons)"
    _build(data)

    # A search that names the catalog finds the summary, as a page jason generated, confidential.
    named = pi.Scope(catalogs=(NAME,), confidential_in=(NAME,))
    hits = pi.search("what is missing or unread: pages no reader gave words for", data_dir=data, scope=named, mode="keyword")
    page = [h for h in hits if h.hit.passage.path.name == "summary.md"]
    assert page and all((h.row.catalog, h.row.standing, h.row.generated, h.row.confidential) == (NAME, pi.Standing.PAGE, True, True)
                        for h in page)
    assert page[0].hit.passage.context.startswith("jason's summary of the collection: a summary, not the record")
    # It is held with the case: a search that does not name the catalog, or does not open it, never sees it.
    for scope in (pi.Scope(), pi.Scope(catalogs=(NAME,)), pi.Scope(standings=(pi.Standing.PAGE,))):
        assert not pi.search("what is missing or unread", data_dir=data, scope=scope, mode="keyword")

    from jason.mcp.county import document_search

    served = document_search("what is missing or unread: pages no reader gave words for", data_dir=data, mode="keyword", catalog=NAME)
    hit = next(h for h in served["hits"] if h["file"] == "summary.md")
    assert (hit["standing"], hit["generated"], hit["confidential"], hit["catalog"]) == ("page", True, True, NAME)
    assert any("standing is page (generated) is jason's own summary, never the rule" in c for c in served["caveats"])
    assert not document_search("what is missing or unread", data_dir=data, mode="keyword")["hits"]

    # The page is companion material, never a member: the collection's scope leaves it out, so its count is what it
    # was and a summary made after the page was indexed is the same page. No lens reads the page back as a document.
    assert pi.count(data, _case().scope) == members and pi.count(data, named)[0] == 5
    assert _summary(data).markdown(TODAY) == before


def test_a_lens_named_for_the_catalog_does_not_read_the_page_back(data, monkeypatch, capsys):
    _build(data)
    cp.write(data, _summary(data), today=TODAY)
    _build(data)
    monkeypatch.setenv("PAYHOA_CATALOG", str(data / "payhoa.db"))
    from jason.cli import build_parser

    args = build_parser().parse_args(["chronology", "--catalog", NAME, "--json"])
    assert args.func(args) == 0
    found = json.loads(capsys.readouterr().out)
    assert found["counts"]["files"] == 4 and not any(f["generated"] for f in found["files"])
    assert not any(e["file"] == "summary.md" for e in found["events"])


def test_the_index_build_takes_each_collection_s_pages(monkeypatch):
    monkeypatch.setattr("jason.community.community", lambda: Community())
    from jason.commands.index import sources

    (pages,) = [s for s in sources() if isinstance(s, cp.PagesSource)]
    assert pages.catalog == NAME and pages.folder == f"collections/{KEY}"


# --- the pack ---------------------------------------------------------------------------------------------------------

def _evidence(pack) -> list[tuple[str, str, str]]:
    return [(s.id, s.file, s.text) for s in pack.sources if s.id.startswith("C")]


def test_the_pack_carries_the_summary_once_labeled_and_the_evidence_is_what_it_was(data):
    _build(data)
    plain = _pack(data, ask=ASK, collection=_case())
    assert _evidence(plain) and not any(s.file.startswith("collections/") for s in plain.sources)
    assert [s.id for s in plain.sources if s.id.startswith("F")] == ["F1", "F2"]
    cp.write(data, _summary(data), today=TODAY)
    _build(data)

    # Why the page is not ranked with the documents: it quotes them all, so a tier that ranked it would give it the
    # places of the documents themselves. A scope that does not leave the pages out shows it.
    loose = replace(_case(), scope=replace(_case().scope, not_folders=()))
    crowded = _pack(data, ask=ASK, collection=loose)
    assert any(file.startswith("collections/") for _, file, _ in _evidence(crowded))
    assert _evidence(crowded) != _evidence(plain)

    pack = _pack(data, ask=ASK, collection=_case())
    assert _evidence(pack) == _evidence(plain)                    # the evidence is what it was before the page existed
    assert all(s.standing is pi.Standing.EVIDENCE for s in pack.sources if s.id.startswith("C"))
    (summary,) = [s for s in pack.sources if s.file.startswith("collections/")]      # at most the one summary source
    assert (summary.id, summary.label, summary.standing) == ("F3", SUMMARY_LABEL, pi.Standing.PAGE)
    assert summary.file == f"collections/{KEY}/summary.md" and summary.title == "Summary: Example v. Example Commons"
    assert "generated by jason on 2026-10-04, by rule" in summary.note and "it is not one of them" in summary.note
    assert "- Generated:" not in summary.text and "- Standing: a summary, not the record." in summary.text
    # The specification's record is its own source (F2), so the summary's copy of it is left out.
    assert "The specification's record of the matter" not in summary.text and "first set" not in summary.text
    for heading in (cp.FILES, cp.MISSING, cp.QUESTIONS, cp.CONFLICTS, "Caveats"):
        assert f"## {heading}" in summary.text
    # Its chronology quotes the documents, and the pack reads the documents themselves: it is left out, and said so.
    assert "Left out of this source: the page's chronology" in summary.text
    assert "> The hearing on the demurrer is set" not in summary.text and cp.ABOUT_DATES not in summary.text
    assert len(summary.text) <= COLLECTION_SUMMARY_CHARS

    assert "[F3] collection (jason's summary of the collection: a summary, not the record): Summary: Example v. Example Commons" in pack.sources_text()
    assert "*Collection: jason's summary of the collection: a summary, not the record — generated by jason on 2026-10-04" in pack.markdown()
    told = pack.task_prompt()
    assert "Source F3 is jason's summary of the collection: a summary, not the record." in told
    assert "never cite it as the record or a rule" in told and "Source F3" not in plain.task_prompt()

    # The same page written again on another day is the same source, so the same pack is the same kept review.
    cp.write(data, _summary(data), today=date(2026, 12, 25))
    again = _pack(data, ask=ASK, collection=_case())
    assert review_store.review_digest(again) == review_store.review_digest(pack)
    assert "generated by jason on 2026-12-25" in next(s.note for s in again.sources if s.id == "F3")


def test_a_long_summary_is_cut_and_a_member_s_task_gets_none_of_it(data):
    _build(data)
    path = cp.write(data, _summary(data), today=TODAY)
    path.write_text(path.read_text(encoding="utf-8") + "\n".join(f"- line {n} of a long page" for n in range(900)), encoding="utf-8")
    with_page = _pack(data, ask=ASK, collection=_case())
    long = next(s for s in with_page.sources if s.label == SUMMARY_LABEL)
    assert long.text.endswith("…(trimmed)") and len(long.text) == COLLECTION_SUMMARY_CHARS + len(" …(trimmed)")
    member = _pack(data, replace(TASK, audience=Audience.MEMBERS), ask=ASK, collection=_case())
    assert not member.collection_included and not any(s.label or s.file.startswith("collections/") for s in member.sources)
    assert "Summary: Example" not in member.markdown() + member.sources_text() + member.task_prompt()
    # A collection with no page yet has no such source, and that is not a gap: nothing of the evidence is missing.
    assert companion_summary(replace(_case(), key="no-page-yet"), data) is None
    without = _pack(data, ask=ASK, collection=replace(_case(), key="no-page-yet"))
    assert without.gaps == with_page.gaps and not any(s.label == SUMMARY_LABEL for s in without.sources)


# --- the command ------------------------------------------------------------------------------------------------------

def test_the_command_prints_the_page_and_writes_only_when_asked(data, monkeypatch, capsys):
    _build(data)
    from jason.cli import build_parser
    from jason.commands import MODULES

    parser = build_parser()                                       # built from the checked-in profile, before the made-up one
    monkeypatch.setattr("jason.community.community", lambda: Community())
    monkeypatch.setattr("jason.config.data_dir", lambda env_file=None: data)

    def run(*argv: str) -> tuple[int, str, str]:
        args = parser.parse_args(["collection", *argv])
        code = args.func(args)
        said = capsys.readouterr()
        return code, said.out, said.err

    assert "collection" in MODULES
    code, out, _ = run(KEY)
    assert code == 0 and out.startswith("# Summary: Example v. Example Commons\n") and f"## {cp.CHRONOLOGY}" in out
    assert not (data / "collections").exists()                    # printing writes nothing
    code, out, _ = run(f"case-{KEY}", "--json")                   # the catalog's name opens the case's files too
    found = json.loads(out)
    assert code == 0 and found["key"] == KEY and found["confidential"] and found["counts"]["datedStatements"] == 7
    assert found["counts"]["statementsByRole"] == {"document": 2, "heading": 0, "name": 1, "embedded": 0, "about": 4}
    assert not (data / "collections").exists()
    code, out, err = run(KEY, "--write")
    page = data / "collections" / KEY / "summary.md"
    assert code == 0 and not out and str(page) in err and "confidential: for directors and counsel" in err
    assert page.read_text(encoding="utf-8").startswith("# Summary: Example v. Example Commons\n")
    code, out, _ = run()
    assert code == 0 and KEY in out and "legal case" in out and "4 files" in out
    code, _, err = run("nothing")
    assert code == 2 and "no collection 'nothing'" in err
