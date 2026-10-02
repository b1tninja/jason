"""Request file sync writes bytes plus comments and notes."""

import json
from pathlib import Path

from payhoa.client import PayhoaClient

from jason.tasks.sync_request_files import sync_request_files


class _Scripted(PayhoaClient):
    def __init__(self) -> None:
        super().__init__()
        self._token = "token"
        self.calls: list[str] = []

    def _request(self, method, path, *, auth=True, params=None, json_body=None):
        self.calls.append(path)
        if path.endswith("/form-submissions/7"):
            return {
                "submission": {
                    "answers": [
                        {
                            "files": [
                                {
                                    "id": 9,
                                    "fileName": "gutter.jpg",
                                    "fileSize": 3,
                                    "downloadUrl": "https://s3.example/gutter",
                                }
                            ]
                        }
                    ]
                }
            }
        if path == "/files/submission/7":
            return []
        if path.endswith("/comments"):
            return [{"id": 1, "message": "see photo"}]
        if path.endswith("/notes"):
            return [{"id": 2, "note": "association", "private": True}]
        raise AssertionError(path)

    def download_signed_url(self, url: str, dest: str | Path) -> Path:
        path = Path(dest)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"jpg")
        return path


def test_sync_request_files_saves_attachment_comments_and_notes(tmp_path: Path):
    report = sync_request_files(
        _Scripted(), 27889, tmp_path, request_ids=[7]
    )
    assert report.summary().startswith("requests=1 files=1")
    folder = tmp_path / "requests" / "7"
    assert (folder / "9_gutter.jpg").read_bytes() == b"jpg"
    assert json.loads((folder / "comments.json").read_text(encoding="utf-8"))[0]["message"] == "see photo"
    assert json.loads((folder / "notes.json").read_text(encoding="utf-8"))[0]["private"] is True

    again = sync_request_files(_Scripted(), 27889, tmp_path, request_ids=[7])
    assert again.files == 0
    assert again.skipped == 1
