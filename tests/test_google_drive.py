"""Drive helper lists a folder and refuses to download a Google Site."""

import json
from pathlib import Path

import httpx

from jason.google import GoogleAuthRequired, GoogleDocs, GoogleDrive, GoogleError, open_drive


class _Http:
    def __init__(self, responses: list[httpx.Response]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, str]] = []

    def get(self, url, *, params=None, headers=None):
        self.calls.append(("GET", url))
        return self.responses.pop(0)

    def post(self, url, *, data=None, content=None, headers=None):
        self.calls.append(("POST", url))
        self.body = content
        return self.responses.pop(0)

    def close(self) -> None:
        return None


def _response(status: int, body: dict | bytes, *, text: str = "") -> httpx.Response:
    content = body if isinstance(body, bytes) else json.dumps(body).encode()
    return httpx.Response(status, content=content, text=text or content.decode())


def test_list_folder_follows_next_page():
    http = _Http(
        [
            _response(
                200,
                {"files": [{"id": "a", "name": "CCRs.pdf"}], "nextPageToken": "p2"},
            ),
            _response(200, {"files": [{"id": "b", "name": "Bylaws.pdf"}]}),
        ]
    )
    drive = GoogleDrive("token", http=http)  # type: ignore[arg-type]
    rows = drive.list_folder("folder-1", page_size=1)
    assert [row["name"] for row in rows] == ["CCRs.pdf", "Bylaws.pdf"]
    assert http.calls[0][1].endswith("/files")


def test_download_rejects_google_site(tmp_path: Path):
    http = _Http(
        [
            _response(
                403,
                b'{"error":{"errors":[{"reason":"fileNotDownloadable"}]}}',
            )
        ]
    )
    drive = GoogleDrive("token", http=http)  # type: ignore[arg-type]
    try:
        drive.download("site-id", tmp_path / "site")
    except GoogleError as exc:
        assert "site" in str(exc).lower() or "document" in str(exc).lower()
    else:
        raise AssertionError("expected GoogleError")


def test_trash_moves_a_file_to_the_trash_and_never_deletes_it():
    class _Patch:
        def patch(self, url, *, params=None, content=None, headers=None):
            self.url, self.params, self.body = url, params, json.loads(content)
            return _response(200, {"id": "f1", "name": "Old copy", "trashed": True})

    http = _Patch()
    row = GoogleDrive("token", http=http).trash("f1")        # type: ignore[arg-type]
    assert http.url.endswith("/files/f1") and http.body == {"trashed": True}
    assert row["trashed"] is True


def test_trash_refuses_when_drive_refuses():
    class _Refuse:
        def patch(self, url, *, params=None, content=None, headers=None):
            return _response(403, {"error": {"message": "no"}})

    try:
        GoogleDrive("token", http=_Refuse()).trash("f1")      # type: ignore[arg-type]
    except GoogleError as exc:
        assert "403" in str(exc) and "f1" in str(exc)
    else:
        raise AssertionError("expected GoogleError")


def test_upload_bytes_posts_the_file_and_returns_its_id():
    class _Upload:
        def post(self, url, *, params=None, content=None, headers=None, data=None):
            self.url = url
            self.content = content
            return _response(200, {"id": "file-1"})

        def close(self):
            return None

    http = _Upload()
    drive = GoogleDrive("token", http=http)  # type: ignore[arg-type]
    file_id = drive.upload_bytes("gutter.jpg", b"jpeg", mime_type="image/jpeg", parent_id="folder")
    assert file_id == "file-1"
    assert "uploadType=multipart" in http.url
    assert b"gutter.jpg" in http.content
    assert b"jpeg" in http.content


def test_from_refresh_token_reads_access_token():
    http = _Http([_response(200, {"access_token": "ya29.access"})])
    drive = GoogleDrive.from_refresh_token(
        client_id="id",
        client_secret="secret",
        refresh_token="refresh",
        http=http,  # type: ignore[arg-type]
    )
    assert drive._token == "ya29.access"


def test_open_drive_asks_for_browser_when_token_missing(tmp_path: Path):
    token = tmp_path / "google-token.json"
    opened: list[str] = []

    class Settings:
        google_oauth_record_uid = "uid"
        google_oauth_token_file = token

    class Vault:
        def load_record(self, uid: str):
            class Record:
                custom = [
                    {"label": "client_id", "value": ["id"]},
                    {"label": "client_secret", "value": ["secret"]},
                ]

            return Record()

    def sign_in(client_id: str, client_secret: str, path: Path) -> str:
        opened.append(client_id)
        path.write_text(json.dumps({"refresh_token": "refresh"}), encoding="utf-8")
        return "refresh"

    http = _Http([_response(200, {"access_token": "ya29.access"})])
    drive = open_drive(
        Settings(), Vault(), authorize=sign_in, http=http, interactive=True
    )  # type: ignore[arg-type]
    assert opened == ["id"]
    assert json.loads(token.read_text(encoding="utf-8"))["refresh_token"] == "refresh"
    assert drive._token == "ya29.access"


def test_open_drive_fails_fast_by_default(tmp_path: Path):
    class Settings:
        google_oauth_record_uid = "uid"
        google_oauth_token_file = tmp_path / "missing.json"

    class Vault:
        def load_record(self, uid: str):
            class Record:
                custom = [
                    {"label": "client_id", "value": ["id"]},
                    {"label": "client_secret", "value": ["secret"]},
                ]

            return Record()

    def sign_in(*args: object) -> str:
        raise AssertionError("browser should not open")

    try:
        open_drive(Settings(), Vault(), authorize=sign_in)
    except GoogleAuthRequired as exc:
        assert "interactive" in str(exc)
    else:
        raise AssertionError("expected GoogleAuthRequired")


def test_docs_batch_update_posts_requests():
    http = _Http([_response(200, {"documentId": "doc-1", "replies": [{}]})])
    docs = GoogleDocs("token", http=http)  # type: ignore[arg-type]
    body = docs.batch_update(
        "doc-1",
        [{"replaceAllText": {"containsText": {"text": "DRAFT"}, "replaceText": ""}}],
    )
    assert body["documentId"] == "doc-1"
    assert http.calls[0] == ("POST", "https://docs.googleapis.com/v1/documents/doc-1:batchUpdate")
    assert "replaceAllText" in http.body


def test_docs_batch_update_rejects_empty_requests():
    docs = GoogleDocs("token", http=_Http([]))  # type: ignore[arg-type]
    try:
        docs.batch_update("doc-1", [])
    except GoogleError as exc:
        assert "at least one" in str(exc)
    else:
        raise AssertionError("expected GoogleError")


def test_docs_export_pdf_writes_bytes(tmp_path: Path):
    http = _Http([_response(200, b"%PDF-1.4")])
    docs = GoogleDocs("token", http=http)  # type: ignore[arg-type]
    dest = docs.export_pdf("doc-1", tmp_path / "minutes.pdf")
    assert dest.read_bytes().startswith(b"%PDF")
    assert http.calls[0] == (
        "GET",
        "https://www.googleapis.com/drive/v3/files/doc-1/export",
    )


def test_drive_export_pdf_uses_docs(tmp_path: Path):
    http = _Http([_response(200, b"%PDF-1.4")])
    drive = GoogleDrive("token", http=http)  # type: ignore[arg-type]
    dest = drive.export_pdf("doc-1", tmp_path / "minutes.pdf")
    assert dest.read_bytes().startswith(b"%PDF")
    assert http.calls[0][1].endswith("/files/doc-1/export")
