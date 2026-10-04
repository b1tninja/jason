"""Gmail's own Save to Drive: what a person saves, found from metadata alone, and the saved copies moved and tagged."""

from __future__ import annotations

import json

from jason.community.base import EmailFiling, FilingRule
from jason.community.sources import Sender, SourceKind
from jason.community.symbols import DocumentKind
from jason.tasks.vendor_files import adopt_plan, gmail_link, plan_lines, plan_saves, save_list

ALARM = Sender("Example Alarm Co", SourceKind.VENDOR, ("EXAMPLE ALARM",), domains=("examplealarm.test",))
FILING = EmailFiling(root="ROOT", rules=(
    FilingRule(DocumentKind.INSPECTION_REPORT, ("Reports", "Fire Protection", "Fire Alarm"), senders=("Example Alarm Co",)),
    FilingRule(DocumentKind.INVOICE, ("Financials", "{year}", "Invoices", "{vendor}")),
))
DAY = 86_400_000
T0 = 1_760_000_000_000                    # 2025-10-09


class Profile:
    def email_filing(self):
        return FILING

    def fiscal_year_end(self):
        return (12, 31)

    def classify_document(self, name, folder=None, path=""):
        if "report" in name.lower():
            return DocumentKind.INSPECTION_REPORT
        return DocumentKind.INVOICE if name.lower().startswith("invoice") else None


MESSAGES = {
    # An invoice sent "for review" and again "paid" two days later: one document, the later copy to save.
    "m1": ("Billing <ar@examplealarm.test>", "For review", T0, [("Invoice-12.pdf", 1000)]),
    "m2": ("Billing <ar@examplealarm.test>", "Paid", T0 + 2 * DAY, [("Invoice-12.pdf", 1010)]),
    # A report a person has already saved to My Drive with Gmail's button: to be moved.
    "m3": ("Tech <tech@examplealarm.test>", "Reports", T0 + 5 * DAY, [("Bldg 1 report.pdf", 5000), ("logo.png", 10)]),
    # The same file name a year later, a different document.
    "m4": ("Billing <ar@examplealarm.test>", "Next year", T0 + 400 * DAY, [("Invoice-12.pdf", 990)]),
    # Filed before by jason (its message is on the Drive file).
    "m5": ("Billing <ar@examplealarm.test>", "Old", T0 - 300 * DAY, [("Invoice-9.pdf", 700)]),
    # Not from a known address.
    "m6": ("Board <board@hoa.test>", "Fwd", T0, [("Invoice-77.pdf", 1)]),
}


class Gmail:
    def iter_messages(self, query, limit=2000):
        return [{"id": k} for k in MESSAGES]

    def get_metadata(self, mid, headers=()):
        sender, subject, at, parts = MESSAGES[mid]
        return {"id": mid, "threadId": f"t-{mid}", "internalDate": str(at), "headers": {"From": sender, "Subject": subject},
                "attachments": [{"name": n, "attachmentId": f"{mid}:{n}", "size": size} for n, size in parts]}

    def get_attachment(self, mid, aid):
        raise AssertionError("nothing is downloaded")


class Drive:
    def __init__(self):
        self.files = [
            {"id": "saved-report", "name": "Bldg 1 report.pdf", "size": "5000", "parents": ["ROOTID"]},
            {"id": "jason-copy", "name": "Invoice-9.pdf", "size": "700", "parents": ["F"], "appProperties": {"gmailMessageId": "m5"}},
        ]
        self.moves, self.tags, self.folders = [], [], {}

    def list_files(self, query, fields="", page_size=100):
        name = query.split("name = '", 1)[1].split("'", 1)[0]
        return [f for f in self.files if f["name"] == name]

    def root_id(self):
        return "ROOTID"

    def child_folder(self, parent, name):
        return self.folders.get((parent, name), "")

    def create_folder(self, name, parent):
        self.folders[(parent, name)] = f"{parent}/{name}"
        return self.folders[(parent, name)]

    def move(self, file_id, folder):
        self.moves.append((file_id, folder))

    def update_metadata(self, file_id, **kw):
        self.tags.append((file_id, kw))

    def upload_bytes(self, *a, **kw):
        raise AssertionError("nothing is uploaded")


def test_plan_from_metadata_only(tmp_path) -> None:
    plan = plan_saves(Gmail(), Drive(), Profile(), ALARM)
    rows = [(a.message_id, a.name, a.action) for a in plan.attachments]
    assert rows == [("m5", "Invoice-9.pdf", "filed before"), ("m1", "Invoice-12.pdf", "earlier copy"),
                    ("m2", "Invoice-12.pdf", "save"), ("m3", "Bldg 1 report.pdf", "adopt"),
                    ("m4", "Invoice-12.pdf", "save")]
    save = plan.attachments[2]
    assert save.path == ("Financials", "2025", "Invoices", "Example Alarm Co")
    assert gmail_link(save) == "https://mail.google.com/mail/u/0/#all/t-m2"
    listing = save_list([plan])
    assert "## Example Alarm Co (2)" in listing and "(https://mail.google.com/mail/u/0/#all/t-m2)" in listing
    assert any("[invoice from any source]" in line for line in plan_lines(plan))


def test_saved_copy_is_moved_and_tagged_not_uploaded(tmp_path) -> None:
    drive = Drive()
    plan = plan_saves(Gmail(), drive, Profile(), ALARM)
    assert adopt_plan(drive, Profile(), plan, tmp_path) == 1
    assert drive.moves == [("saved-report", "ROOT/Reports/Fire Protection/Fire Alarm")]
    file_id, tags = drive.tags[0]
    assert file_id == "saved-report" and tags["app_properties"]["gmailMessageId"] == "m3"
    assert tags["app_properties"]["via"] == "gmail save to drive"
    logged = json.loads((tmp_path / "drive" / "vendor-files.jsonl").read_text().splitlines()[0])
    assert logged["action"] == "adopted" and logged["parent"] == "ROOT/Reports/Fire Protection/Fire Alarm"
