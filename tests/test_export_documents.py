"""Document export keeps the fields a Drive sync rule would match."""

import json
from pathlib import Path

from payhoa.client import PayhoaClient

from jason.catalog import PayhoaCatalog
from jason.tasks.export_documents import export_documents


class _Scripted(PayhoaClient):
    def __init__(self) -> None:
        super().__init__()
        self._token = "token"

    def _request(self, method, path, *, auth=True, params=None, json_body=None):
        assert path == "/organizations/27889/documents/flat"
        return [
            {
                "id": 2,
                "parentId": 1,
                "directory": False,
                "fileName": "CCRs.pdf",
                "path": "Governing/CCRs.pdf",
                "fileSize": 10,
                "public": True,
                "updatedAt": "2026-01-01",
                "uploadedBy": 9,
                "uploader": {"email": "hidden@example.com"},
            },
            {
                "id": 1,
                "parentId": None,
                "directory": True,
                "fileName": "Governing",
                "path": "Governing",
                "fileSize": None,
                "public": False,
                "updatedAt": "2026-01-01",
            },
        ]


def test_export_documents_refreshes_catalog_and_drops_uploader(tmp_path: Path):
    catalog = PayhoaCatalog(tmp_path / "payhoa.db")
    dest = tmp_path / "documents.json"
    report = export_documents(catalog, 27889, dest, client=_Scripted())
    assert report.directories == 1
    assert report.files == 1
    rows = json.loads(dest.read_text(encoding="utf-8"))
    assert [row["path"] for row in rows] == ["Governing", "Governing/CCRs.pdf"]
    assert "uploader" not in rows[1]
    assert "uploadedBy" not in rows[1]
    assert catalog.list_documents(27889)[0]["fileName"] in {"Governing", "CCRs.pdf"}
    catalog.close()
