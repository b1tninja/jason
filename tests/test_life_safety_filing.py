"""Life-safety reports go to their system's folder in Drive: loose in the root they move, in another folder they are copied
(the original stays), missing they are uploaded; a record already tagged as filed is left, so a second run does nothing."""

from __future__ import annotations

import hashlib
import json
import re

from jason.community import community
from jason.tasks.report_portals import drive_name, plan_filing
from jason.tasks.vendor_files import file_plan, move_plan

SITE = "Example Community Association -Bldg. 8"


class FakeDrive:
    """Just enough of the Drive client: a root with files, folders made on demand, and the calls the filing makes."""

    def __init__(self, root_files=()):
        self.root_files = list(root_files)
        self.calls: list[tuple] = []
        self.tagged: list[str] = []                          # the content hashes filings were tagged with
        self._folders: dict[tuple[str, str], str] = {}

    def root_id(self):
        return "ROOT"

    def list_files(self, query, *, page_size=100, fields=""):
        if "'ROOT' in parents" in query:
            return list(self.root_files)
        found = re.search(r"key='gmailSha256' and value='([0-9a-f]+)'", query)
        if found:
            return [{"id": "tagged"}] if found.group(1) in self.tagged else []
        return []

    def child_folder(self, parent, name):
        return self._folders.get((parent, name), "")

    def create_folder(self, name, parent):
        self._folders[(parent, name)] = f"{parent}/{name}"
        return f"{parent}/{name}"

    def upload_bytes(self, name, data, *, mime_type, parent_id, description, app_properties):
        self.calls.append(("upload", name, parent_id))
        self.tagged.append(app_properties["gmailSha256"])
        return "new-id"

    def move(self, file_id, folder_id):
        self.calls.append(("move", file_id, folder_id))
        return {}

    def copy(self, file_id, name, parent_id=None):
        self.calls.append(("copy", file_id, name, parent_id))
        return "copy-id"

    def update_metadata(self, file_id, *, description=None, app_properties=None, name=None):
        self.calls.append(("tag", file_id))
        if app_properties and app_properties.get("gmailSha256"):
            self.tagged.append(app_properties["gmailSha256"])


def _box(tmp_path):
    root = tmp_path / "vendors" / "signalservice"
    (root / "reports").mkdir(parents=True)
    rows, pdfs = [], {}
    for n, (day, label) in enumerate((("2025-09-19", "loose"), ("2024-09-05", "elsewhere"), ("2026-03-11", "missing"))):
        data = f"%PDF-1.4 {label} {SITE}".encode()
        (root / "reports" / f"{label}.pdf").write_bytes(data)
        rows.append({"urlUuid": f"u{n}", "day": day, "site": SITE, "template": "Fire Alarm System - NFPA 72 (2013)",
                     "file": f"reports/{label}.pdf", "pdfUrl": f"https://reports.example.test/viewReport.php?id=u{n}"})
        pdfs[label] = data
    (root / "reports.json").write_text(json.dumps({"reports": rows}), encoding="utf-8")
    md5 = {k: hashlib.md5(v).hexdigest() for k, v in pdfs.items()}
    (tmp_path / "drive").mkdir()
    (tmp_path / "drive" / "files.json").write_text(json.dumps({"files": [
        {"id": "FALSE-ALARM-1", "path": "My Drive/False Alarm/exhibit.pdf", "md5": md5["elsewhere"]}]}), encoding="utf-8")
    known = {md5["loose"]: "My Drive/loose report.pdf", md5["elsewhere"]: "My Drive/False Alarm/exhibit.pdf"}
    drive = FakeDrive([{"id": "ROOT-FILE-1", "name": "loose report.pdf", "md5Checksum": md5["loose"]}])
    portal = next(p for p in community().vendor_portals() if p.key == "signalservice")
    return portal, drive, known


def test_a_report_loose_in_the_root_moves_one_elsewhere_is_copied_and_a_missing_one_is_uploaded(tmp_path):
    portal, drive, known = _box(tmp_path)
    plan, blobs = plan_filing(drive, community(), portal, tmp_path, known=known)
    assert {a.url.rsplit("=", 1)[1]: a.action for a in plan.attachments} == {"u0": "move", "u1": "copy", "u2": "file"}
    assert len(blobs) == 1 and all(a.where == "My Drive/Reports/Fire Protection/Fire Alarm" for a in plan.attachments)
    by_url = {a.url.rsplit("=", 1)[1]: a for a in plan.attachments}
    assert by_url["u0"].name == drive_name({"day": "2025-09-19", "site": SITE, "template": "Fire Alarm System - NFPA 72 (2013)"})
    assert file_plan(drive, community(), plan, blobs, tmp_path) == 1
    assert move_plan(drive, community(), plan, tmp_path) == 2
    kinds = [c[0] for c in drive.calls]
    assert kinds.count("upload") == 1 and kinds.count("move") == 1 and kinds.count("copy") == 1
    assert [c for c in drive.calls if c[0] == "move"] == [("move", "ROOT-FILE-1", "root/Reports/Fire Protection/Fire Alarm")]
    assert [c for c in drive.calls if c[0] == "copy"][0][1] == "FALSE-ALARM-1"        # the original is copied, never moved
    log = [json.loads(line) for line in (tmp_path / "drive" / "vendor-files.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(log) == 3 and {r["action"] for r in log} == {"file", "moved", "copied"}


def test_a_second_run_finds_everything_filed(tmp_path):
    portal, drive, known = _box(tmp_path)
    plan, blobs = plan_filing(drive, community(), portal, tmp_path, known=known)
    file_plan(drive, community(), plan, blobs, tmp_path)
    move_plan(drive, community(), plan, tmp_path)
    again, blobs2 = plan_filing(drive, community(), portal, tmp_path, known=known)
    assert not blobs2 and {a.action for a in again.attachments} <= {"filed before", "in drive"}     # nothing to upload, move, or copy
