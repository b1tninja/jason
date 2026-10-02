from datetime import date
from pathlib import Path

from jason.community.duties import DUTIES, Cadence, duty_named
from jason.community.readings import Reader
from jason.community.records_inventory import inventory, inventory_markdown
from jason.community.symbols import AssociationRecord, DocumentRule, PayhoaFolder
from jason.tasks.association_pages import duties_markdown, duty_brief, write_association_pages


def test_the_duty_registry_covers_the_anchors_and_finds_one_by_name():
    assert len(DUTIES) == 18 and duty_named("assessments").anchor == "Assessments" and duty_named("Manager").anchor == "Manager's own duties"
    assert duty_named("nothing") is None
    money = duty_named("Money")
    assert money.cadence is Cadence.EVERY_THREE_YEARS and AssociationRecord.RESERVE_ACCOUNT in money.records and "5550" in money.when
    assert all(duty.queries and duty.produce for duty in DUTIES)
    assert duty_named("Records").records == tuple(AssociationRecord)


class _Folder:
    def __init__(self, folder, payhoa_id, path, records=()):
        self.folder, self.payhoa_id, self.path, self.records = folder, payhoa_id, path, records


class _File:
    def __init__(self, name, records=()):
        self.name, self.records = name, records


class _Rule:
    def __init__(self, id, drive_folder, destination, records=()):
        self.id, self.drive_folder, self.destination, self.records = id, drive_folder, destination, records


class _Community:
    org_id = 1

    def library_folders(self):
        return (_Folder(PayhoaFolder.MEETINGS, 1, "Meetings/", (AssociationRecord.MINUTES,)), _Folder(PayhoaFolder.CONTRACTS, 2, "Contracts/", (AssociationRecord.EXECUTED_CONTRACT,)))

    def known_files(self):
        return (_File("Membership", (AssociationRecord.MEMBERSHIP_LIST,)),)

    sync_rules = (_Rule(DocumentRule.GOVERNING_ROOT, "Governing Documents", PayhoaFolder.GOVERNING_DOCUMENTS, (AssociationRecord.GOVERNING_DOCUMENTS,)),)


def test_the_inventory_names_holders_counts_files_and_finds_gaps(tmp_path: Path):
    reading = Reader().read("RECORDING REQUESTED BY (SPACE ABOVE THIS LINE FOR RECORDER'S USE) SECOND AMENDMENT TO RESTATED DECLARATION OF COVENANTS FOR MYSTIQUE\nDATED: ______________, 2023", tmp_path / "CCRs - 2nd Amendment.md")
    assert reading.unsigned and reading.stamp.unrecorded_copy
    holdings = inventory(_Community(), ("Meetings/2024/0123/minutes.pdf", "Meetings/2025/minutes.pdf", "Financials/2024/x.pdf"), readings=(reading,))
    by_kind = {h.kind: h for h in holdings}
    assert by_kind[AssociationRecord.MINUTES].documents == 2 and by_kind[AssociationRecord.MINUTES].gap == "" and "permanently" in by_kind[AssociationRecord.MINUTES].retention
    assert by_kind[AssociationRecord.EXECUTED_CONTRACT].gap.startswith("a folder is pinned but the catalog holds no file")
    assert by_kind[AssociationRecord.MEMBERSHIP_LIST].files == ["Membership"] and by_kind[AssociationRecord.MEMBERSHIP_LIST].gap == ""
    assert by_kind[AssociationRecord.TAX_RETURN].gap.startswith("nothing pinned")
    assert by_kind[AssociationRecord.GOVERNING_DOCUMENTS].rules == ["governing-root: Drive Governing Documents to PayHOA governing_documents"]
    assert by_kind[AssociationRecord.GOVERNING_DOCUMENTS].notes == ["CCRs - 2nd Amendment: an unrecorded copy, unsigned; the recorded instrument is the record"]
    text = inventory_markdown(holdings, title="T")
    assert "| minutes | CIV 5200(a)(8) |" in text and "## The governing copies" in text and "unsigned" in text


def test_the_adoption_reader_reads_dates_and_effective_clauses():
    fine = Reader().read("FINE SCHEDULE ... Non-approved alterations $10 to $50 per day Adopted Aug 30, 2022")
    assert fine.adopted == date(2022, 8, 30) and not fine.unsigned
    policy = Reader().read("These Election Rules shall be effective on the date of adoption, and certify that these Election Rules were duly adopted by the Board of Directors on March 3, 2020.")
    assert policy.adopted == date(2020, 3, 3) and policy.effective == "the date of adoption"


def test_the_duty_brief_and_the_pages_search_the_documents(tmp_path: Path):
    docs = tmp_path / "artifacts" / "site-docs" / "governing_documents"
    docs.mkdir(parents=True)
    (docs / "CCRs.md").write_text("Section 5.2 Delinquent assessments. Any assessment not paid within fifteen days is delinquent and bears a late charge and interest, and the Association may record a notice of delinquent assessment lien. " * 3 + "Section 9.1 Insurance. The Association shall maintain liability insurance. " * 3, encoding="utf-8")
    laws = tmp_path / "laws"
    laws.mkdir()
    (laws / "obligations.md").write_text("Assessment collection has its own notice sequence (CIV 5660 to 5730). Recording a lien or foreclosing is not a Jason task.", encoding="utf-8")
    brief = duty_brief(duty_named("Assessments"), tmp_path, laws)
    hits = brief["passages"]["delinquent assessments late charges interest lien"]
    assert hits and hits[0]["file"] == "CCRs.md" and any(h["file"] == "obligations.md" for h in hits)
    text = duties_markdown(tmp_path, laws, title="T")
    assert "## Assessments" in text and "*CCRs.md*, passage 0: Section 5.2 Delinquent assessments" in text and "Jason does not lien" in text
    report = write_association_pages(_Community(), tmp_path, tmp_path / "reports", laws=laws, title="T")
    assert [p.name for p in report.written] == ["records.md", "duties.md"] and report.duties == 18 and any(g.startswith("tax_return") for g in report.gaps)


def test_once_the_statute_is_exported_the_brief_quotes_the_duty_sections_not_the_notes(tmp_path: Path):
    import json

    docs = tmp_path / "artifacts" / "site-docs" / "governing_documents"
    docs.mkdir(parents=True)
    (docs / "CCRs.md").write_text("Section 5.2 Delinquent assessments bear a late charge and interest. " * 3, encoding="utf-8")
    laws = tmp_path / "laws"
    laws.mkdir()
    (laws / "obligations.md").write_text("Delinquent assessments lien notice summary.", encoding="utf-8")
    page = tmp_path / "authorities" / "CIV" / "CIV-5650-5690.md"
    page.parent.mkdir(parents=True)
    page.write_text(
        "# CIV 5650-5690: Article 2. Assessment Payment and Delinquency\n\n- Source: 2025\n\n"
        "## CIV 5650\n\n5650. (Added by Stats. 2012.)\n\n(a) A regular or special assessment becomes a delinquent assessment if not paid within 15 days; late charges and interest may be recovered.\n\n"
        "## CIV 5660\n\n5660. (Added by Stats. 2012.)\n\nAt least 30 days prior to recording a lien upon the separate interest the association shall notify the owner.\n",
        encoding="utf-8",
    )
    other = tmp_path / "authorities" / "CIV" / "CIV-4000-4070.md"
    other.write_text("# CIV 4000-4070: Article 1\n\n## CIV 4000\n\n4000. Delinquent assessments late charges interest lien words that should not be searched.\n", encoding="utf-8")
    (tmp_path / "authorities" / "manifest.json").write_text(json.dumps({"session": "2025", "pages": [
        {"file": "authorities/CIV/CIV-5650-5690.md", "citation": "CIV 5650-5690", "title": "Article 2", "code": "CIV", "start": "5650", "end": "5690",
         "sections": ["5650", "5660"], "basis": "a duty", "why": [], "session": "2025"},
        {"file": "authorities/CIV/CIV-4000-4070.md", "citation": "CIV 4000-4070", "title": "Article 1", "code": "CIV", "start": "4000", "end": "4070",
         "sections": ["4000"], "basis": "a duty", "why": [], "session": "2025"},
    ]}), encoding="utf-8")
    brief = duty_brief(duty_named("Assessments"), tmp_path, laws)
    hits = brief["passages"]["delinquent assessments late charges interest lien"]
    shelves = {h["shelf"] for h in hits}
    assert shelves == {"governing document", "statute"} and "law note" not in shelves
    statute = [h for h in hits if h["shelf"] == "statute"]
    assert statute[0]["file"] == "CIV 5650" and "15 days" in statute[0]["text"] and all(h["file"] != "CIV 4000" for h in statute)
    text = duties_markdown(tmp_path, laws, title="T")
    assert "- *CIV 5650*: 5650. (Added by Stats. 2012.) (a) A regular or special assessment" in text
    section = text.split("## Assessments")[1].split("\n## ")[0]
    assert "(Jason's note)" not in section and "(Jason's note)" in text
