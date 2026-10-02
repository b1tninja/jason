import base64
import json
from io import BytesIO

from PIL import Image

from jason.catalog import PayhoaCatalog
from jason.tasks.export_requests import export_requests


def test_export_requests_embeds_images_and_links_other_files(tmp_path):
    catalog = PayhoaCatalog(tmp_path / "payhoa.db")
    catalog.upsert_requests(
        1,
        [
            {
                "id": 7,
                "formId": 9,
                "unitId": 4,
                "status": "open",
                "createdAt": "2026-03-01T00:00:00Z",
                "unit": {"title": "12"},
                "answers": [
                    {
                        "answer": "Gutter leak",
                        "question": {"label": "Title", "type": "input"},
                    },
                    {
                        "answer": "<p>Water at the entry.</p>",
                        "question": {"label": "Message", "type": "textarea"},
                    },
                ],
                "comments": [{"message": "catalog comment", "createdAt": "2026-03-02"}],
            }
        ],
        form_names={9: "Maintenance Request"},
    )
    folder = tmp_path / "payhoa-files" / "requests" / "7"
    folder.mkdir(parents=True)
    Image.new("RGB", (2400, 1600), "red").save(folder / "9_gutter.jpg", "JPEG")
    (folder / "10_scope.pdf").write_bytes(b"pdf")
    (folder / "comments.json").write_text(
        json.dumps(
            [
                {
                    "message": "see photo",
                    "createdAt": "2026-03-03",
                    "membership": {"profile": {"givenNames": "Ada", "familyName": "Lovelace"}},
                }
            ]
        ),
        encoding="utf-8",
    )
    (folder / "notes.json").write_text(
        json.dumps([{"note": "association", "createdAt": "2026-03-04"}]),
        encoding="utf-8",
    )

    report = export_requests(
        catalog,
        1,
        tmp_path / "payhoa-requests.md",
        files_dir=tmp_path / "payhoa-files",
    )
    text = report.path.read_text(encoding="utf-8")
    assert report.requests == 1
    assert report.attachments == 2
    assert "## Gutter leak" in text
    assert "**7**" in text
    assert "newest first" in text
    assert "Water at the entry." in text
    assert "Ada Lovelace" in text
    assert "see photo" in text
    assert "catalog comment" not in text
    assert "association" in text
    assert "![9_gutter.jpg](payhoa-requests-images/7/9_gutter.jpg)" in text
    assert "[10_scope.pdf](payhoa-files/requests/7/10_scope.pdf)" in text
    with Image.open(tmp_path / "payhoa-requests-images" / "7" / "9_gutter.jpg") as image:
        assert max(image.size) <= 800
    html_text = (tmp_path / "payhoa-requests.html").read_text(encoding="utf-8")
    assert 'width="640"' in html_text
    catalog.close()


def test_export_requests_saves_an_inline_base64_image(tmp_path):
    buffer = BytesIO()
    Image.new("RGB", (1200, 400), "blue").save(buffer, "PNG")
    uri = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()
    catalog = PayhoaCatalog(tmp_path / "payhoa.db")
    catalog.upsert_requests(
        1,
        [
            {
                "id": 152364,
                "formId": 9,
                "status": "complete",
                "createdAt": "2025-06-06T16:05:28.000000Z",
                "unit": {"title": "5611 WHIMSICAL LN"},
                "answers": [
                    {"answer": "OS&Y Leaking", "question": {"label": "Title"}},
                    {
                        "answer": f"<p>Valve is leaking. <img src=\"{uri}\" alt=\"\"></p>",
                        "question": {"label": "Message"},
                    },
                ],
            }
        ],
        form_names={9: "Maintenance Request"},
    )
    report = export_requests(
        catalog,
        1,
        tmp_path / "payhoa-requests.md",
        files_dir=tmp_path / "payhoa-files",
    )
    text = report.path.read_text(encoding="utf-8")
    assert "data:image" not in text
    assert "Valve is leaking." in text
    saved = tmp_path / "payhoa-requests-images" / "152364" / "inline-1.jpg"
    with Image.open(saved) as image:
        assert max(image.size) <= 800
    catalog.close()
