"""Publishing a Google Doc uploads the exported PDF into a PayHOA folder."""

from pathlib import Path

from jason.tasks.publish_document import publish_google_doc


class _Drive:
    def export_pdf(self, file_id: str, dest: str | Path) -> Path:
        path = Path(dest)
        path.write_bytes(b"%PDF")
        self.file_id = file_id
        return path


class _Payhoa:
    def create_document(self, org_id, parent_id, file_path, *, file_name=None):
        self.args = (org_id, parent_id, Path(file_path).name, file_name)
        return {"id": 2968174, "path": f"Meetings/2026/{file_name}"}


def test_publish_exports_then_creates(tmp_path: Path):
    drive = _Drive()
    client = _Payhoa()
    created = publish_google_doc(
        drive,
        client,  # type: ignore[arg-type]
        org_id=27889,
        document_id="doc-1",
        parent_id=2643621,
        dest=tmp_path / "Minutes of 7_7_26.pdf",
    )
    assert drive.file_id == "doc-1"
    assert client.args == (27889, 2643621, "Minutes of 7_7_26.pdf", "Minutes of 7_7_26.pdf")
    assert created["id"] == 2968174
