"""The document library: name rules, the 5200 records, the content stages, and the ingestion chain."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from jason.community import mystique
from jason.community.content import ModelClassifier, classify_text, parse_model_answer, period_from_text, records_from_text
from jason.community.library import Classified, LibraryDocument, Method, classify_by_name, coverage, library_markdown, payhoa_documents, period_of
from jason.community.symbols import AssociationRecord, DocumentKind


def _doc(path: str, doc_id: str = "1") -> LibraryDocument:
    name = path.rsplit("/", 1)[-1]
    return LibraryDocument("payhoa", doc_id, path, name, path.rsplit("/", 1)[0] + "/" if "/" in path else "")


def test_the_name_and_folder_rules_place_the_librarys_files():
    community = mystique()
    cases = {
        "PayHOA Resources and Templates (Populated by PayHOA)/Meeting Resources/Board Meeting MinutesTemplate.docx": DocumentKind.TEMPLATE,
        "Meetings/2024/0206/Executive Session Agenda - 2_6_24.pdf": DocumentKind.EXECUTIVE_SESSION,
        "Meetings/2025/Minutes of 1_21_25.pdf": DocumentKind.MINUTES,
        "Email Attachments/Agenda for 7_16_24.pdf": DocumentKind.AGENDA,
        "Confidential/Complete Financial Statements/2025/Statements/20250131-statements-5286-.pdf": DocumentKind.BANK_STATEMENT,
        "Confidential/Complete Financial Statements/2023/Mystique - 230308 - Financial Statements - JAN2023.pdf": DocumentKind.FINANCIAL_STATEMENT,
        "Financials/2025/Reserve Study - 2025.pdf": DocumentKind.RESERVE_STUDY,
        "Financials/2025/Pro Forma Budget_2025.pdf": DocumentKind.BUDGET,
        "Financials/2022/Mystique Review & Tax EL YE 12-31-2022 - Newman.pdf": DocumentKind.CONTRACT,
        "Insurance/FLOOD POLICY 25-26 BLDG 3.pdf": DocumentKind.INSURANCE_POLICY,
        "Insurance/Certificate of Insurance 2025-2026.pdf": DocumentKind.EVIDENCE_OF_INSURANCE,
        "Resale Documents/Insurance Summary Disclosure 25-26.pdf": DocumentKind.ANNUAL_DISCLOSURE,
        "Governing Documents/Policies/Assessment Collection Policy.pdf": DocumentKind.POLICY,
        "Governing Documents/Owner's Manual and Rules.pdf": DocumentKind.OPERATING_RULES,
        "Governing Documents/Forms/Towing Authorization Form.pdf": DocumentKind.FORM,
        "Legal/MECHANICS LIEN 202203010880.pdf": DocumentKind.RECORDED_LIEN,
        "Confidential/Delinquencies/Notice of Default and Demand for Payment - WICKHAM D FARROWAY.pdf": DocumentKind.DELINQUENCY_NOTICE,
        "Elections/Certified 2023 Election Results.pdf": DocumentKind.ELECTION_RESULTS,
        "Email Attachments/Mystique Community Newsletter April 2024.pdf": DocumentKind.CORRESPONDENCE,
        "Plans/Paint Schedule.png": DocumentKind.PLAN_SET,
        "Email Attachments/PXL_20240101_1 (1).jpg": DocumentKind.IMAGE,
        "Contracts/Helsing - Management Agreement.pdf": DocumentKind.CONTRACT,
    }
    for path, wanted in cases.items():
        assert classify_by_name(community, _doc(path)).kind is wanted, path
    assert classify_by_name(community, _doc("Email Attachments/606935.pdf")).method is Method.NONE


def test_a_kind_brings_its_5200_record_and_the_resale_packet_adds_the_transfer_record():
    community = mystique()
    budget = classify_by_name(community, _doc("Resale Documents/Pro Forma Budget - 2026.pdf"))
    assert budget.records == (AssociationRecord.FINANCIAL_DISCLOSURE, AssociationRecord.TRANSFER_FINANCIAL)
    agenda = classify_by_name(community, _doc("Meetings/Agenda for 7_16_24.pdf"))
    assert agenda.records == (AssociationRecord.MINUTES,)
    executive = classify_by_name(community, _doc("Meetings/2024/0206/Executive Session Agenda - 2_6_24.pdf"))
    assert executive.records == () and executive.confidential
    statement = classify_by_name(community, _doc("Email Attachments/20240329-statements-5286-.pdf"))
    assert statement.records == (AssociationRecord.ENHANCED,) and statement.confidential
    template = classify_by_name(community, _doc("PayHOA Resources and Templates (Populated by PayHOA)/Election Resources/Election Ballot.docx"))
    assert template.kind is DocumentKind.TEMPLATE and template.records == ()


def test_the_name_gives_the_period_and_a_recorder_number_is_not_a_year():
    assert period_of("20250131-statements-5286-.pdf") == "2025-01-31"
    assert period_of("Minutes of 1_21_25.pdf") == "2025-01-21"
    assert period_of("Treasurer's Report - 2025-02_Redacted.pdf") == "2025-02"
    assert period_of("Mystique - 230308 - Financial Statements - JAN2023.pdf") == "2023-01"
    assert period_of("Reserve Study 2024.pdf") == "2024"
    assert period_of("GD 200709281712.pdf") == "" and period_of("Bylaws.pdf") == ""


def test_the_phrase_rules_name_a_kind_and_refine_the_record():
    kind, evidence = classify_text("MINUTES OF THE REGULAR MEETING OF THE BOARD\nThe meeting was called to order at 6:30 pm.")
    assert kind is DocumentKind.MINUTES and evidence == 'title: "minutes of the"'
    assert classify_text("Statement Period 01/01/2025 - 01/31/2025\nBeginning Balance $1,000\nEnding Balance $900")[0] is DocumentKind.BANK_STATEMENT
    assert classify_text("nothing to see here")[0] is None
    reserve = records_from_text(DocumentKind.BANK_STATEMENT, "Account: MYSTIQUE CA RESERVE MONEY MARKET")
    assert reserve[0][0] is AssociationRecord.RESERVE_ACCOUNT
    approval = records_from_text(DocumentKind.MINUTES, "Motion to approve the proposal from Cal Pro Painting carried 3-0.")
    assert approval[0][0] is AssociationRecord.VENDOR_APPROVAL
    balcony = records_from_text(DocumentKind.INSPECTION_REPORT, "Inspection of exterior elevated elements under Civil Code 5551")
    assert balcony[0][0] is AssociationRecord.ELEVATED_ELEMENT_REPORT
    assert records_from_text(DocumentKind.MINUTES, "no approvals tonight") == ()
    assert period_from_text("Board meeting held January 21, 2025 at the clubhouse") == "2025-01-21"


def test_the_model_answers_from_the_closed_list_and_nothing_else():
    sent = {}

    def fetch(url, payload):
        sent.update(payload)
        return {"message": {"content": json.dumps({"kind": "form", "confidence": 0.8, "period": "2025-03", "reason": "has blanks for name, phone, and signature"})}}

    answer = ModelClassifier(model="test", fetch=fetch).classify("Contact Information.pdf", "Name ____ Phone ____ Signature ____")
    assert answer.kind is DocumentKind.FORM and answer.confidence == 0.8 and answer.period == "2025-03"
    assert "form" in sent["format"]["properties"]["kind"]["enum"] and sent["options"]["temperature"] == 0
    assert parse_model_answer('{"kind": "spaceship", "confidence": 2}').kind is None
    assert parse_model_answer('{"kind": "minutes", "confidence": 2, "period": "last week"}').confidence == 1.0
    assert parse_model_answer("not json").kind is None


def test_the_chain_reads_text_classifies_what_names_missed_and_stores_every_row(tmp_path: Path):
    from jason.tasks.library import STORE, ingest, load

    db = tmp_path / "payhoa.db"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE documents (org_id INT, id INT, parent_id INT, file_name TEXT, path TEXT, directory INT, public INT, file_size INT, raw_json TEXT, synced_at TEXT)")
        rows = [
            (1, 10, 0, "Email Attachments", "Email Attachments", 0, 0, 0, "", ""),
            (1, 11, 0, "606935.txt", "Email Attachments/606935.txt", 0, 0, 10, "", ""),
            (1, 12, 0, "20240329-statements-6177-.txt", "Email Attachments/20240329-statements-6177-.txt", 0, 0, 10, "", ""),
            (1, 13, 0, "Minutes of 1_21_25.txt", "Meetings/2025/Minutes of 1_21_25.txt", 0, 0, 10, "", ""),
            (1, 14, 0, "Mystery Sheet.txt", "Email Attachments/Mystery Sheet.txt", 0, 0, 10, "", ""),
        ]
        conn.executemany("INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
    files = tmp_path / "library" / "files"
    (files / "Email Attachments").mkdir(parents=True)
    (files / "Meetings" / "2025").mkdir(parents=True)
    (files / "Email Attachments" / "606935.txt").write_text("INVOICE # 606935\nBill To: Mystique HOA\nAmount Due: $450.00", encoding="utf-8")
    (files / "Email Attachments" / "20240329-statements-6177-.txt").write_text("Account: MYSTIQUE RESERVE\nStatement Period March 2024", encoding="utf-8")
    (files / "Meetings" / "2025" / "Minutes of 1_21_25.txt").write_text("Minutes. Motion to approve the proposal from the painter carried.", encoding="utf-8")
    (files / "Email Attachments" / "Mystery Sheet.txt").write_text("Name ____ Unit ____", encoding="utf-8")

    def fetch(url, payload):
        return {"message": {"content": json.dumps({"kind": "form", "confidence": 0.9, "reason": "blanks for name and unit"})}}

    docs = payhoa_documents(db)
    assert [d.name for d in docs][0] != "Email Attachments" and len(docs) == 4
    rows_out, report = ingest(mystique(), tmp_path, model=ModelClassifier(model="t", fetch=fetch))
    by = {row.document.name: row for row in rows_out}
    assert by["606935.txt"].kind is DocumentKind.INVOICE and by["606935.txt"].method is Method.CONTENT
    assert by["Mystery Sheet.txt"].kind is DocumentKind.FORM and by["Mystery Sheet.txt"].method is Method.MODEL and by["Mystery Sheet.txt"].confidence == 0.9
    assert AssociationRecord.RESERVE_ACCOUNT in by["20240329-statements-6177-.txt"].records
    assert AssociationRecord.VENDOR_APPROVAL in by["Minutes of 1_21_25.txt"].records
    assert report.with_text == 4 and report.by_content == 1 and report.by_model == 1 and report.refined == 2
    stored = {row["name"]: row for row in load(tmp_path)}
    assert (tmp_path / STORE).is_file() and stored["606935.txt"]["method"] == "CONTENT" and stored["20240329-statements-6177-.txt"]["confidential"]
    assert "reserve_account" in stored["20240329-statements-6177-.txt"]["records"]
    page = library_markdown(rows_out, title="T")
    assert "## Civil Code 5200 records held" in page and "| vendor approval | CIV 5200(a)(5) | 1 |" in page
    assert coverage(rows_out).by_method == {"NAME": 2, "CONTENT": 1, "MODEL": 1}


def test_a_classified_row_says_what_it_is():
    row = Classified(_doc("Meetings/2025/Minutes of 1_21_25.pdf"), DocumentKind.MINUTES, Method.NAME, "2025-01-21")
    data = row.as_dict()
    assert data["kind"] == "minutes" and data["category"] == "meeting" and data["records"] == ["minutes"] and data["method"] == "NAME"


def test_the_title_pass_tells_agenda_from_minutes_and_a_recorded_amendment_from_one_discussed():
    from jason.community.content import body_of

    agenda = "MYSTIQUE COMMUNITY ASSOCIATION Regular Meeting of the Board of Directors To be held on: at 7:00pm Mar 18, 2025 via Zoom"
    minutes = "MYSTIQUE COMMUNITY ASSOCIATION Regular Meeting of the Board of Directors Held at 7:00pm Mar 18, 2025 via Zoom I. Call to Order"
    silent_minutes = ("MYSTIQUE COMMUNITY ASSOCIATION Regular Meeting of the Board of Directors I. Call to Order. The meeting was called to order. "
                      "A motion was made and seconded, and carried 3-0. The meeting adjourned at 8:10.")
    assert classify_text(agenda)[0] is DocumentKind.AGENDA and classify_text(minutes)[0] is DocumentKind.MINUTES
    assert classify_text(silent_minutes)[0] is DocumentKind.MINUTES
    report = "Mystique Community Association Treasurer's Report - 2026-08 Included Reports: Balance Sheet"
    agenda_listing_report = agenda + " I. Call to Order II. Approval of minutes III. Treasurer's Report"
    assert classify_text(report)[0] is DocumentKind.TREASURER_REPORT and classify_text(agenda_listing_report)[0] is DocumentKind.AGENDA
    recorded = "RECORDING REQUESTED BY: AND WHEN RECORDED MAIL TO: Berding & Weil " + "x " * 100 + "SECOND AMENDMENT TO DECLARATION OF COVENANTS"
    discussed = minutes + " The board discussed an amendment to the declaration."
    assert classify_text(recorded)[0] is DocumentKind.AMENDMENT and classify_text(discussed)[0] is DocumentKind.MINUTES
    extract = "# CCRs.pdf\n- drive_id: `abc`\n- mime: `application/pdf`\n- path: `governing_documents/CCRs.pdf`\n\nThe words."
    assert body_of(extract) == "The words."
    kind, evidence = classify_text(report)
    assert evidence.startswith("title:")


def test_the_scorecard_measures_a_reader_against_the_names_and_takes_a_sample_per_kind(tmp_path: Path):
    from jason.tasks.library import TEXT_DIR, score

    text_dir = tmp_path / TEXT_DIR
    text_dir.mkdir(parents=True)
    body = "Mystique Community Association Treasurer's Report - 2026-08 Included Reports: Balance Sheet " + "x " * 120
    rows = []
    for index in range(3):
        doc = _doc(f"Financials/2026/Treasurer's Report - 2026-0{index + 1}.pdf", str(index))
        (text_dir / f"{index}.txt").write_text(body, encoding="utf-8")
        rows.append(Classified(doc, DocumentKind.TREASURER_REPORT, Method.NAME))
    wrong = _doc("Meetings/Minutes of 1_21_25.pdf", "9")
    (text_dir / "9.txt").write_text(body, encoding="utf-8")
    rows.append(Classified(wrong, DocumentKind.MINUTES, Method.NAME))
    card = score(tmp_path, tuple(rows))
    assert card.cases == 4 and card.agree == 3 and card.misses == [{"path": wrong.path, "name": "minutes", "text": "treasurer_report"}]
    assert round(card.accuracy, 2) == 0.75
    sample = score(tmp_path, tuple(rows), per_kind=1)
    assert sample.cases == 2 and sample.as_dict()["perKind"]["treasurer_report"]["cases"] == 1


def test_copies_of_one_file_collapse_and_keep_every_record_their_folders_give():
    from jason.tasks.library import distinct

    rows = [
        {"id": "1", "path": "Financials/2026/Pro Forma Budget - 2026.pdf", "name": "Pro Forma Budget - 2026.pdf", "kind": "budget",
         "records": ["financial_disclosure"], "period": "2026", "confidential": False, "sha256": "abc"},
        {"id": "2", "path": "Resale Documents/Pro Forma Budget - 2026.pdf", "name": "Pro Forma Budget - 2026.pdf", "kind": "budget",
         "records": ["financial_disclosure", "transfer_financial"], "period": "2026", "confidential": False, "sha256": "abc"},
        {"id": "3", "path": "Meetings/2025/Minutes of 1_21_25.pdf", "name": "Minutes of 1_21_25.pdf", "kind": "minutes",
         "records": ["minutes"], "period": "2025-01-21", "confidential": False, "sha256": ""},
        {"id": "4", "path": "Email Attachments/Minutes of 1_21_25.pdf", "name": "Minutes of 1_21_25.pdf", "kind": "minutes",
         "records": ["minutes"], "period": "2025-01-21", "confidential": False, "sha256": ""},
    ]
    kept = distinct(rows)
    assert len(kept) == 2 and kept[0]["records"] == ["financial_disclosure", "transfer_financial"]
    assert kept[0]["copies"] == ["Financials/2026/Pro Forma Budget - 2026.pdf", "Resale Documents/Pro Forma Budget - 2026.pdf"]
    assert kept[1]["copies"] == ["Meetings/2025/Minutes of 1_21_25.pdf", "Email Attachments/Minutes of 1_21_25.pdf"]


def test_a_vision_reading_comes_first_and_replaces_the_text_when_it_read_every_page(tmp_path: Path):
    import json

    import pymupdf

    from jason.tasks.library import TEXT_DIR, VISION_END, VISION_MARK, text_for, vision_read

    folder = tmp_path / TEXT_DIR
    folder.mkdir(parents=True)
    pdf = tmp_path / "deed.pdf"
    document = pymupdf.open()
    for _ in range(2):
        document.new_page()
    document.save(pdf)
    (folder / "d1.txt").write_text("GRANT DEED garbled stamp", encoding="utf-8")
    (folder / "d1.json").write_text(json.dumps({"file": str(pdf)}), encoding="utf-8")

    class Fake:
        name, model = "ollama-vision", "qwen3.6:27b"

        def __init__(self, text):
            self.text = text

        def text_of(self, path):
            return self.text

    assert vision_read(tmp_path, "d1", pages=1, engine=Fake("Doc# 201905221469")) == "Doc# 201905221469"
    assert text_for(tmp_path, "d1") == f"{VISION_MARK}\nDoc# 201905221469\n{VISION_END}\n\nGRANT DEED garbled stamp"
    assert vision_read(tmp_path, "d1", pages=1, engine=Fake("other")) == "Doc# 201905221469"
    vision_read(tmp_path, "d1", engine=Fake("both pages"), refresh=True)
    assert text_for(tmp_path, "d1") == "both pages"
    assert text_for(tmp_path, "missing") == ""


# A synthetic receivables aging in PayHOA's layout: the board version lists units; the member version keeps the totals.
BOARD_AGING = ("Accounts Receivable\n$1,000.00\nAging of Accounts as of: 08/31/2026\nUnit\nCurrent\n1-30 Days Past Due\n"
               "31-60 Days Past Due\n90+ Days Past Due\n3022 Enchanted Walk\n$315.87\n$0.00\n3101 Macon Dr\n$684.13\n$0.00\n"
               "Totals\n$1,000.00\nGeneral Ledger\nRepairs - 3048 Macon Dr gutter\n$250.00\n")
MEMBER_AGING = ("Accounts Receivable\n$1,000.00\nAging of Accounts as of: 08/31/2026\nUnit\nCurrent\n1-30 Days Past Due\n"
                "90+ Days Past Due\nTotals\n$1,000.00\nGeneral Ledger\nRepairs - 3048 Macon Dr gutter\n$250.00\n")


def test_member_level_receivables_make_a_treasurers_report_confidential_wherever_it_is_filed():
    from jason.community.content import aging_units, private_content

    assert aging_units(BOARD_AGING) == ("3022 ENCHANTED WALK", "3101 MACON DR")
    assert aging_units(MEMBER_AGING) == () and aging_units("no aging here") == ()
    assert "CIV 5215" in private_content(DocumentKind.TREASURER_REPORT, BOARD_AGING)
    assert private_content(DocumentKind.TREASURER_REPORT, MEMBER_AGING) == ""
    assert private_content(DocumentKind.MINUTES, BOARD_AGING) == ""
    doc = LibraryDocument("payhoa", "1", "Email Attachments/Treasurer's Report.pdf", "Treasurer's Report.pdf", "Email Attachments")
    shared = Classified(doc, DocumentKind.TREASURER_REPORT, Method.NAME)
    assert not shared.confidential
    assert Classified(doc, DocumentKind.TREASURER_REPORT, Method.NAME, private="aging lists units").confidential
