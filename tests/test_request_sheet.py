from PIL import Image

from jason.catalog import PayhoaCatalog
from jason.tasks.request_sheet import (
    attachment_columns,
    embed_sheet_photos,
    image_formula,
    request_image_paths,
    request_sheet_tabs,
    write_request_sheet,
)


def _catalog(tmp_path):
    catalog = PayhoaCatalog(tmp_path / "payhoa.db")
    catalog.upsert_people(
        1,
        [
            {
                "id": 10,
                "email": "owner@example.com",
                "profile": {
                    "givenNames": "Pat",
                    "familyName": "Owner",
                    "phone": "916-555-0100",
                    "address1": "PO Box 9",
                    "city": "Sacramento",
                    "state": "CA",
                    "zip": "95814",
                },
            },
            {
                "id": 20,
                "email": "resident@example.com",
                "profile": {
                    "givenNames": "Sam",
                    "familyName": "Resident",
                    "phone": "916-555-0199",
                    "address1": "5651 Whimsical Ln",
                    "city": "Sacramento",
                    "state": "CA",
                    "zip": "95835",
                },
            },
        ],
    )
    catalog.upsert_units(
        1,
        [
            {
                "id": 4,
                "title": "5651",
                "streetAddress": "5651 Whimsical Ln",
                "owners": [{"membershipId": 10}],
            }
        ],
    )
    catalog.upsert_requests(
        1,
        [
            {
                "id": 260564,
                "formId": 9,
                "unitId": 4,
                "membershipId": 20,
                "status": "pending",
                "createdAt": "2026-09-24T00:00:00Z",
                "answers": [
                    {"answer": "Detached gutter", "question": {"label": "Title"}},
                ],
            },
            {
                "id": 244572,
                "formId": 9,
                "unitId": 4,
                "membershipId": 10,
                "status": "pending",
                "createdAt": "2026-07-23T00:00:00Z",
                "answers": [
                    {"answer": "Door will not latch", "question": {"label": "Title"}},
                ],
            },
        ],
        form_names={9: "Maintenance Request"},
    )
    return catalog


def test_request_sheet_groups_by_kind_and_marks_an_offsite_owner(tmp_path):
    tables = request_sheet_tabs(
        _catalog(tmp_path),
        1,
        files={260564: ["gutter.jpg", "scope.pdf"]},
    )
    association = tables["Association"]
    homeowner = tables["Homeowner"]
    header = association[0]
    gutter = association[1]
    door = homeowner[1]

    assert header[header.index("Vendor")] == "Vendor"
    assert gutter[0] == "City Gutters"
    assert gutter[header.index("Request")] == 260564
    assert gutter[header.index("Owner")] == "Pat Owner"
    assert gutter[header.index("Owner email")] == "owner@example.com"
    assert gutter[header.index("Owner phone")] == "916-555-0100"
    assert gutter[header.index("Owner mail is not the unit")] == "yes"
    assert "PO Box 9" in gutter[header.index("Owner mailing")]
    assert gutter[header.index("Resident")] == "Sam Resident"
    assert gutter[header.index("Resident email")] == "resident@example.com"
    assert gutter[header.index("Photo 1")] == "gutter.jpg"
    assert "scope.pdf" in gutter[header.index("Files")]
    assert door[0] == "Homeowner"
    assert door[header.index("Resident")] == "No separate resident is in the catalog"
    assert tables["Not a repair"] == [header]


def test_attachment_columns_keeps_three_image_urls_and_every_name():
    urls, labels = attachment_columns(
        [
            {"fileName": "a.jpg", "downloadUrl": "https://files.example/a"},
            {"fileName": "scope.pdf", "downloadUrl": "https://files.example/p"},
            {"fileName": "b.PNG", "downloadUrl": "https://files.example/b"},
            {"fileName": "c.webp", "downloadUrl": "https://files.example/c"},
            {"fileName": "d.gif", "downloadUrl": "https://files.example/d"},
        ]
    )
    assert urls == [
        "https://files.example/a",
        "https://files.example/b",
        "https://files.example/c",
    ]
    assert labels == ["a.jpg", "scope.pdf", "b.PNG", "c.webp", "d.gif"]


class _Sheets:
    def __init__(self):
        self.ranges = {}
        self.batch = []

    def create(self, title, *, sheet_titles=None):
        self.title = title
        self.sheet_titles = sheet_titles
        return {
            "spreadsheetId": "sheet-1",
            "sheets": [
                {"properties": {"sheetId": index, "title": name}}
                for index, name in enumerate(sheet_titles or ())
            ],
        }

    def values_update(self, spreadsheet_id, range_a1, rows):
        self.ranges[range_a1] = rows
        return {}

    def batch_update(self, spreadsheet_id, requests):
        self.batch = requests
        return {}


def test_write_request_sheet_creates_one_tab_per_kind():
    sheets = _Sheets()
    report = write_request_sheet(
        sheets,
        "Mystique open requests",
        {
            "Association": [["Vendor"], ["City Gutters"]],
            "Homeowner": [["Vendor"]],
            "Unclear": [["Vendor"]],
            "Not a repair": [["Vendor"], ["No vendor"]],
        },
    )
    assert report.spreadsheet_id == "sheet-1"
    assert report.tabs["Association"] == 1
    assert report.tabs["Homeowner"] == 0
    assert "'Not a repair'!A1" in sheets.ranges
    assert sheets.batch[0]["updateSheetProperties"]["properties"]["gridProperties"]["frozenRowCount"] == 1


def test_request_image_paths_matches_the_payhoa_file_prefix(tmp_path):
    folder = tmp_path / "260564"
    folder.mkdir()
    (folder / "1714811_gutter.jpg").write_bytes(b"jpeg")
    (folder / "scope.pdf").write_bytes(b"pdf")
    assert request_image_paths(folder, ["gutter.jpg"]) == [folder / "1714811_gutter.jpg"]
    assert request_image_paths(folder, ["missing.jpg"]) == []
    assert image_formula("abc") == '=IMAGE("https://lh3.googleusercontent.com/d/abc")'


class _EmbedSheets:
    def __init__(self):
        self.written = {}
        self.batch = []

    def get(self, spreadsheet_id, *, ranges=None, include_grid=False, fields=None):
        return {"sheets": [{"properties": {"sheetId": 1, "title": "Association"}}]}

    def values_get(self, spreadsheet_id, range_a1):
        return {"values": [["City Gutters", "260564"] + [""] * 14 + ["gutter.jpg", "", ""]]}

    def values_update(self, spreadsheet_id, range_a1, rows):
        self.written[range_a1] = rows
        return {}

    def batch_update(self, spreadsheet_id, requests):
        self.batch = requests
        return {}

    def create(self, title, *, sheet_titles=None):
        return {}


class _Drive:
    def list_files(self, query):
        return []

    def create_folder(self, name):
        return "folder-1"

    def upload_bytes(self, name, content, *, mime_type, parent_id=None):
        self.uploaded = (name, mime_type, parent_id, len(content))
        return "file-9"

    def share_with_link(self, file_id):
        self.shared = file_id


def test_embed_sheet_photos_writes_an_image_formula(tmp_path):
    folder = tmp_path / "requests" / "260564"
    folder.mkdir(parents=True)
    Image.new("RGB", (20, 10), "blue").save(folder / "9_gutter.jpg", "JPEG")
    sheets = _EmbedSheets()
    drive = _Drive()
    count = embed_sheet_photos(sheets, drive, "sheet-1", tmp_path / "requests")
    assert count == 1
    assert drive.shared == "file-9"
    assert sheets.written["'Association'!Q2"][0][0] == image_formula("file-9")
