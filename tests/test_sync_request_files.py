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


class _WithStatus(_Scripted):
    """The same request, its detail naming its form and status (Example Village's fake request 502)."""

    def _request(self, method, path, *, auth=True, params=None, json_body=None):
        got = super()._request(method, path, auth=auth, params=params, json_body=json_body)
        if path.endswith("/form-submissions/7"):
            got["submission"].update(id=7, formId=950, status="complete", unit={"title": "102 EXAMPLE WAY"})
        return got


def test_sync_request_files_keeps_the_submission_read_once(tmp_path: Path):
    from jason.catalog import PayhoaCatalog
    from jason.tasks import submission_cache

    client = _WithStatus()
    report = sync_request_files(client, 27889, tmp_path, request_ids=[7])
    assert report.submissions == 1 and "submissions=1" in report.summary()
    assert [c for c in client.calls if "form-submissions/7" in c and "/comments" not in c
            and "/notes" not in c] == ["/organizations/27889/form-submissions/7"]     # one full read a request
    kept = submission_cache.read(tmp_path, 7)
    assert kept["via"] == "jason sync-request-files" and kept["status"] == "complete" and kept["formId"] == 950
    assert kept["submission"]["submission"]["unit"]["title"] == "102 EXAMPLE WAY" and kept["readAt"]
    assert (tmp_path / "requests" / "7" / "9_gutter.jpg").is_file()                  # its answers' files, as before

    # with a catalog: the form's name and, where the submission has none, the status come from its list row
    with PayhoaCatalog(tmp_path / "payhoa.db") as cat:
        cat.upsert_requests(27889, [{"id": 7, "formId": 950, "unitId": 2, "status": "pending",
                                     "createdAt": "2026-10-05T00:00:00Z"}], form_names={950: "Maintenance request"})
        sync_request_files(_Scripted(), 27889, tmp_path, catalog=cat, request_ids=[7])
    kept = submission_cache.read(tmp_path, 7)
    assert kept["formName"] == "Maintenance request" and kept["formId"] == 950 and kept["status"] == "pending"
