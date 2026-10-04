"""Filing vendors' email attachments in Drive: who sent it, the shelf by kind, no duplicates, and the link kept."""

from __future__ import annotations

import hashlib
import sys
import json
from types import SimpleNamespace

from jason.community.base import EmailFiling, FilingRule
from jason.community.sources import Sender, SourceKind
from jason.community.symbols import DocumentKind
from jason.tasks.vendor_files import Known, file_plan, known_addresses, plan_lines, plan_vendor, query_for, sent_by, vendors

ALARM = Sender("Example Alarm Co", SourceKind.VENDOR, ("EXAMPLE ALARM",), payhoa_vendor="Example Alarm Co.",
               domains=("examplealarm.test",))
HANDY = Sender("Example Handyman", SourceKind.VENDOR, ("EXAMPLE HANDYMAN",), payhoa_vendor="Example Handyman")
LAWYER = Sender("Example Law", SourceKind.LAW_FIRM, ("EXAMPLE LAW",), domains=("examplelaw.test",))
FILING = EmailFiling(root="ROOT", rules=(
    FilingRule(DocumentKind.INSPECTION_REPORT, ("Reports", "Fire Protection", "Fire Alarm"), senders=("Example Alarm Co",)),
    FilingRule(DocumentKind.INSPECTION_REPORT, ("Reports", "{vendor}")),
    FilingRule(DocumentKind.INVOICE, ("Financials", "{year}", "Invoices", "{vendor}")),
    FilingRule(None, ("Legal", "{vendor}"), source_kinds=(SourceKind.LAW_FIRM,)),
))
REPORT = b"%PDF report bytes"
INVOICE = b"%PDF invoice bytes"
OLD = b"%PDF already in drive"


class Profile:
    def senders(self):
        return (ALARM, LAWYER, HANDY)

    def email_filing(self):
        return FILING

    def fiscal_year_end(self):
        return (12, 31)

    def classify_document(self, name, folder=None, path=""):
        if "inspection report" in name.lower():
            return DocumentKind.INSPECTION_REPORT
        return DocumentKind.INVOICE if name.lower().startswith("invoice") else None


MESSAGES = {
    "m1": ("Example Alarm <tech@examplealarm.test>", "Reports", 1_726_000_000_000,
           [("Bldg 1 inspection report.pdf", REPORT), ("logo.png", b"img")]),
    "m2": ("Billing <ar@examplealarm.test>", "Invoice 12", 1_760_000_000_000,
           [("Invoice_12.pdf", INVOICE), ("Old.pdf", OLD)]),
    "m5": ("The Example Alarm Co <quickbooks@notification.test>", "Invoice 13", 1_760_500_000_000,
           [("Invoice_13.pdf", b"%PDF via a shared service")]),
    "m3": ("Board <board@hoa.test>", "Fwd: reports", 1_761_000_000_000, [("Bldg 1 inspection report.pdf", REPORT)]),
    "m4": ("Example Alarm <tech@examplealarm.test>", "Again", 1_762_000_000_000, [("copy.pdf", REPORT)]),
}


class Gmail:
    def iter_messages(self, query, limit=2000):
        return [{"id": k} for k in MESSAGES]

    def get_metadata(self, mid, headers=()):
        sender, subject, at, parts = MESSAGES[mid]
        return {"id": mid, "internalDate": str(at), "headers": {"From": sender, "Subject": subject},
                "attachments": [{"name": n, "attachmentId": f"{mid}:{n}"} for n, _ in parts]}

    def get_attachment(self, mid, aid):
        return dict(MESSAGES[mid][3])[aid.split(":", 1)[1]]


class Drive:
    def __init__(self):
        self.uploads, self.folders = [], {}

    def list_files(self, query, fields=""):
        return []

    def child_folder(self, parent, name):
        return self.folders.get((parent, name), "")

    def create_folder(self, name, parent):
        self.folders[(parent, name)] = f"{parent}/{name}"
        return self.folders[(parent, name)]

    def upload_bytes(self, name, content, **kw):
        self.uploads.append((name, kw))
        return f"id{len(self.uploads)}"


def _vendor_info(tmp_path) -> None:
    (tmp_path / "payhoa").mkdir()
    (tmp_path / "payhoa" / "vendor-info.json").write_text(json.dumps({"rows": [
        {"vendorName": "Example Alarm Co.", "email": "office@alarm-billing.test", "website": "https://www.examplealarm.test"},
        {"vendorName": "Example Handyman", "email": "handyman123@gmail.com"},
    ]}))


def test_only_vendors_and_their_known_addresses(tmp_path) -> None:
    assert vendors(Profile()) == [ALARM, HANDY] and vendors(Profile(), "example alarm co") == [ALARM]
    _vendor_info(tmp_path)
    alarm, handy = known_addresses(ALARM, tmp_path), known_addresses(HANDY, tmp_path)
    assert alarm == Known(("alarm-billing.test", "examplealarm.test"), ())
    assert handy == Known((), ("handyman123@gmail.com",))
    assert query_for(handy) == "from:handyman123@gmail.com OR to:handyman123@gmail.com"
    assert not known_addresses(HANDY)


def test_sent_by_known_domain_or_email_only() -> None:
    known = Known(("examplealarm.test",), ("handyman123@gmail.com",))
    assert sent_by(known, "Tech <tech@examplealarm.test>") and sent_by(known, "<a@mail.examplealarm.test>")
    assert sent_by(known, "Pat <Handyman123@gmail.com>")
    assert not sent_by(known, '"The Example Alarm Co" <quickbooks@notification.test>')
    assert not sent_by(known, "Someone <other@gmail.com>")


def test_plan_shelves_skips_and_files_with_link(tmp_path) -> None:
    known = {hashlib.md5(OLD).hexdigest(): "My Drive/Old.pdf"}
    drive = Drive()
    plan, blobs = plan_vendor(Gmail(), drive, Profile(), ALARM, known=known, seen=set())
    by_name = {a.name: a for a in plan.attachments}
    # The board's forward and the shared-service invoice are not from a known address; the image is not a document;
    # a repeat is filed once.
    assert set(by_name) == {"Bldg 1 inspection report.pdf", "Invoice_12.pdf", "Old.pdf", "copy.pdf"}
    report_plan = by_name["Bldg 1 inspection report.pdf"]
    assert (report_plan.action, report_plan.path) == ("file", ("Reports", "Fire Protection", "Fire Alarm"))
    assert report_plan.rule == "inspection_report from Example Alarm Co"
    assert by_name["Old.pdf"].action == "in drive" and by_name["copy.pdf"].action == "repeat"
    assert by_name["Invoice_12.pdf"].path == ("Financials", "2025", "Invoices", "Example Alarm Co")
    assert by_name["Old.pdf"].action == "in drive" and plan.counts()["file"] == 2
    assert by_name["Old.pdf"].action == "in drive"
    assert plan.counts() == {"file": 2, "in drive": 1, "repeat": 1}
    assert any("Invoice_12.pdf" in line for line in plan_lines(plan))

    assert file_plan(drive, Profile(), plan, blobs, tmp_path) == 2
    report, invoice = drive.uploads
    assert report[1]["parent_id"] == "ROOT/Reports/Fire Protection/Fire Alarm"
    assert invoice[1]["parent_id"] == "ROOT/Financials/2025/Invoices/Example Alarm Co"
    assert invoice[1]["app_properties"]["gmailMessageId"] == "m2"
    assert invoice[1]["app_properties"]["gmailSha256"] == hashlib.sha256(INVOICE).hexdigest()
    logged = [json.loads(line) for line in (tmp_path / "drive" / "vendor-files.jsonl").read_text().splitlines()]
    assert [r["name"] for r in logged] == ["Bldg 1 inspection report.pdf", "Invoice_12.pdf"]


def test_no_known_address_is_skipped() -> None:
    plan, blobs = plan_vendor(Gmail(), Drive(), Profile(), HANDY, known={}, seen=set())
    assert not plan.attachments and not blobs and "skipped" in plan_lines(plan)[0]


def test_filed_before_is_not_filed_again() -> None:
    class Filed(Drive):
        def list_files(self, query, fields=""):
            return [{"id": "x"}] if "appProperties" in query else []

    plan, blobs = plan_vendor(Gmail(), Filed(), Profile(), ALARM, known={}, seen=set())
    assert {a.action for a in plan.attachments} == {"filed before", "repeat"} and not blobs


def test_a_document_sent_twice_is_filed_once_from_the_latest(monkeypatch) -> None:
    import jason.tasks.vendor_files as vf

    words = {INVOICE: "Invoice 12 for Example HOA, amount 480.00, status Due",
             b"%PDF invoice paid": "Invoice 12 for Example HOA, amount 480.00, status Due",
             REPORT: "Inspection of building 1", OLD: "Something else"}
    monkeypatch.setattr(vf, "pdf_words", lambda name, data: words.get(data, ""))
    paid = dict(MESSAGES, m6=("Billing <ar@examplealarm.test>", "Paid: Invoice 12", 1_765_000_000_000,
                              [("Invoice_12.pdf", b"%PDF invoice paid")]))
    monkeypatch.setattr(sys.modules[__name__], "MESSAGES", paid)
    plan, blobs = plan_vendor(Gmail(), Drive(), Profile(), ALARM, known={}, seen=set())
    invoices = [a for a in plan.attachments if a.name == "Invoice_12.pdf"]
    assert [a.action for a in invoices] == ["earlier copy", "file"]
    assert invoices[1].message_id == "m6" and len([a for a in plan.attachments if a.action == "file"]) == 3
    assert vf.same_document("A.pdf", "Total 1,234.00 due", "a.PDF", "Total 1,234.50 paid") is False
    assert vf.same_document("A.pdf", "Invoice 7 total 100.00 for the work", "A.pdf", "Invoice 7 total 100.00 for the work ")


def test_rules_by_kind_then_source_then_fallback() -> None:
    other = Sender("Other Vendor", SourceKind.VENDOR, ("OTHER",), domains=("other.test",))
    assert FILING.path_for(ALARM, DocumentKind.INSPECTION_REPORT, 2026)[0] == ("Reports", "Fire Protection", "Fire Alarm")
    assert FILING.path_for(other, DocumentKind.INSPECTION_REPORT, 2026)[0] == ("Reports", "Other Vendor")
    assert FILING.path_for(LAWYER, None, 2026)[0] == ("Legal", "Example Law")
    path, rule = FILING.path_for(other, DocumentKind.PROPOSAL, 2026)
    assert path == ("Vendors", "Other Vendor", "2026") and rule is None


def test_fiscal_year_is_named_by_its_end() -> None:
    from jason.tasks.vendor_files import fiscal_year

    assert fiscal_year("2026-07-15T00:00:00+00:00", (12, 31)) == 2026
    assert fiscal_year("2026-07-15T00:00:00+00:00", (6, 30)) == 2027
    assert fiscal_year("2026-06-30T00:00:00+00:00", (6, 30)) == 2026
    assert fiscal_year("2026-07-15T00:00:00+00:00", None) == 2026


def test_held_documents_are_not_uploaded(tmp_path) -> None:
    from jason.tasks.vendor_files import hold

    drive = Drive()
    plan, blobs = plan_vendor(Gmail(), drive, Profile(), ALARM, known={}, seen=set())
    held = hold(plan, blobs, ("invoice_*",))
    assert [a.name for a in held] == ["Invoice_12.pdf"] and held[0].action == "held"
    file_plan(drive, Profile(), plan, blobs, tmp_path)
    assert "Invoice_12.pdf" not in [name for name, _ in drive.uploads]


def test_gmail_filters_label_each_vendor_by_its_known_addresses(tmp_path) -> None:
    import xml.etree.ElementTree as ET

    from jason.tasks.vendor_files import filters_xml

    _vendor_info(tmp_path)
    xml, skipped = filters_xml(Profile(), tmp_path)
    ns = {"a": "http://www.w3.org/2005/Atom", "apps": "http://schemas.google.com/apps/2006"}
    entries = ET.fromstring(xml).findall("a:entry", ns)
    props = [{p.get("name"): p.get("value") for p in e.findall("apps:property", ns)} for e in entries]
    assert props[0]["from"] == "alarm-billing.test OR examplealarm.test" and props[0]["label"] == "Vendors/Example Alarm Co"
    assert props[1]["from"] == "handyman123@gmail.com" and props[1]["label"] == "Vendors/Example Handyman"
    assert skipped == [] and len(entries) == 2
    assert filters_xml(Profile())[1] == ["Example Handyman"]
