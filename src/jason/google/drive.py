"""Drive API helper. Jason calls this; he does not implement Drive itself.

New Google Sites are Drive files (``application/vnd.google-apps.site``). This
client can read that file's metadata and list embedded folders. It cannot
edit site text, layout, or components.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

import httpx

from jason.google.docs import GoogleDocs
from jason.google.errors import GoogleError, GoogleExportTooLarge, GoogleHttpError
from jason.google.gmail import GoogleGmail
from jason.google.sheets import GoogleSheets

SITE_MIME_TYPE = "application/vnd.google-apps.site"
FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"
GOOGLE_DOC_MIME_TYPE = "application/vnd.google-apps.document"
DOCX_MIME_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_API = "https://www.googleapis.com/drive/v3"
_UPLOAD = "https://www.googleapis.com/upload/drive/v3/files"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_FILE_FIELDS = "id,name,mimeType,size,modifiedTime,parents,webViewLink"
# The hosts a file's thumbnailLink points at; jason's token is sent to no other.
THUMBNAIL_HOSTS = ("googleusercontent.com", "google.com", "googleapis.com")


class GoogleDrive:
    """Authenticated Drive v3 client. Pass an access token or refresh one."""

    def __init__(self, access_token: str, *, http: httpx.Client | None = None) -> None:
        if not access_token:
            raise GoogleError("missing access token")
        self._token = access_token
        self._http = http or httpx.Client(timeout=60.0)
        self._owns_http = http is None
        # Set by from_refresh_token: a new access token for a client that outlives its hour (the Gmail sync).
        self._renew: Callable[[], str] | None = None

    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    def __enter__(self) -> GoogleDrive:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    @classmethod
    def from_refresh_token(
        cls,
        *,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        http: httpx.Client | None = None,
    ) -> GoogleDrive:
        """Exchange a refresh token. The stored token must include drive.readonly."""
        if not client_id or not client_secret or not refresh_token:
            raise GoogleError("client id, client secret, and refresh token are required")
        client = http or httpx.Client(timeout=60.0)

        def renew() -> str:
            response = client.post(
                _TOKEN_URL,
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            token = _json(response).get("access_token")
            if not token:
                raise GoogleError(
                    "token response had no access_token; the refresh token may lack drive.readonly"
                )
            return str(token)

        drive = cls(renew(), http=client)
        drive._owns_http = http is None
        drive._renew = renew
        return drive

    def get_file(self, file_id: str) -> dict[str, Any]:
        return self._get(
            f"/files/{file_id}",
            {"fields": _FILE_FIELDS, "supportsAllDrives": True},
        )

    def list_folder(self, folder_id: str, *, page_size: int = 100) -> list[dict[str, Any]]:
        """Children of a folder, including nested folders. Does not walk them."""
        query = f"'{folder_id}' in parents and trashed = false"
        return self.list_files(query, page_size=page_size)

    def list_files(self, query: str, *, page_size: int = 100, fields: str = "") -> list[dict[str, Any]]:
        """Every file matching ``query``, page by page. ``fields`` replaces the default file fields (read-only)."""
        rows: list[dict[str, Any]] = []
        page_token: str | None = None
        while True:
            params: dict[str, Any] = {
                "q": query,
                "pageSize": page_size,
                "fields": f"nextPageToken,files({fields or _FILE_FIELDS})",
                "supportsAllDrives": True,
                "includeItemsFromAllDrives": True,
            }
            if page_token:
                params["pageToken"] = page_token
            body = self._get("/files", params)
            rows.extend(body.get("files") or [])
            page_token = body.get("nextPageToken")
            if not page_token:
                return rows

    def list_comments(self, file_id: str) -> list[dict[str, Any]]:
        """Every comment on a file, with its quoted words and replies (read-only). A comment the API creates on a Google
        Doc shows unanchored; anchored comments need the Docs API's insertComment, in developer preview."""
        rows: list[dict[str, Any]] = []
        page_token: str | None = None
        fields = ("nextPageToken,comments(id,createdTime,modifiedTime,resolved,deleted,anchor,content,quotedFileContent,"
                  "author(displayName),replies(id,createdTime,content,action,author(displayName)))")
        while True:
            params: dict[str, Any] = {"fields": fields, "pageSize": 100}
            if page_token:
                params["pageToken"] = page_token
            body = self._get(f"/files/{file_id}/comments", params)
            rows.extend(body.get("comments") or [])
            page_token = body.get("nextPageToken")
            if not page_token:
                return rows

    def download(self, file_id: str, dest: str | Path) -> Path:
        """Save a binary file. Google Docs, Sheets, and Sites need export, not this."""
        path = Path(dest)
        path.parent.mkdir(parents=True, exist_ok=True)
        response = self._http.get(
            f"{_API}/files/{file_id}",
            params={"alt": "media", "supportsAllDrives": True},
            headers=self._headers(),
        )
        if response.status_code == 403 and "fileNotDownloadable" in response.text:
            raise GoogleError(
                f"{file_id} is a Google document or site; Drive cannot download it as bytes"
            )
        if not response.is_success:
            raise GoogleError(
                f"HTTP {response.status_code} downloading {file_id}"
            )
        path.write_bytes(response.content)
        return path

    def export_pdf(self, file_id: str, dest: str | Path) -> Path:
        """Write a Google Doc as PDF. Implemented on ``GoogleDocs.export_pdf``."""
        return self.docs().export_pdf(file_id, dest)

    def export_bytes(self, file_id: str, mime_type: str) -> bytes:
        """A Google file exported as ``mime_type`` (``DOCX_MIME_TYPE`` for a Doc), in memory (``files.export``)."""
        response = self._http.get(f"{_API}/files/{file_id}/export", params={"mimeType": mime_type},
                                  headers=self._headers())
        if not response.is_success:
            raise GoogleError(f"HTTP {response.status_code} exporting {file_id} as {mime_type}")
        return response.content

    def file_metadata(self, file_id: str, fields: str) -> dict[str, Any]:
        """One file's metadata with the ``fields`` asked (``capabilities``, ``thumbnailLink``, ``downloadRestrictions``),
        read-only (``files.get``). A refusal is ``GoogleHttpError`` with Google's status and reason."""
        response = self._http.get(f"{_API}/files/{file_id}", params={"fields": fields, "supportsAllDrives": True},
                                  headers=self._headers())
        if not response.is_success:
            raise _http_error(response, f"reading {file_id}'s metadata")
        return _json(response)

    def export_file(self, file_id: str, mime_type: str) -> bytes:
        """A Google Doc, Sheet, or Slides file exported as ``mime_type`` (``files.export``), in memory, read-only.
        Over Google's export limit (10 MB) is ``GoogleExportTooLarge``; another refusal (a type Google does not export
        the file as) is ``GoogleHttpError`` with its status and reason."""
        response = self._http.get(f"{_API}/files/{file_id}/export", params={"mimeType": mime_type},
                                  headers=self._headers())
        if not response.is_success:
            raise _http_error(response, f"exporting {file_id} as {mime_type}")
        return response.content

    def download_bytes(self, file_id: str) -> bytes:
        """A stored file's bytes (a PDF, an image) in memory (``files.get?alt=media``), read-only. A Google Doc, Sheet,
        or Slides file needs ``export_file``."""
        response = self._http.get(f"{_API}/files/{file_id}", params={"alt": "media", "supportsAllDrives": True},
                                  headers=self._headers())
        if not response.is_success:
            raise _http_error(response, f"downloading {file_id}")
        return response.content

    def fetch_link(self, url: str) -> tuple[bytes, str]:
        """The bytes and content type behind a file's ``thumbnailLink``, read with this token. The link is short-lived,
        so a caller keeps what it reads. Only Google's own hosts (``THUMBNAIL_HOSTS``) are asked: the token is never
        sent elsewhere."""
        from urllib.parse import urlsplit

        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        if parts.scheme != "https" or not any(host == h or host.endswith("." + h) for h in THUMBNAIL_HOSTS):
            raise GoogleError(f"not a Google link: {host or url[:40]}")
        response = self._http.get(url, headers=self._headers(), follow_redirects=False)
        if not response.is_success:
            raise _http_error(response, "reading a thumbnail")
        return response.content, response.headers.get("Content-Type", "")

    def list_revisions(self, file_id: str) -> list[dict[str, Any]]:
        """Every revision Drive keeps of a file, oldest first (read-only): its id, when it was saved, and for a Google
        Doc the links that export its text then (``exportLinks``). Drive merges a Doc's older edits, so the list is
        the revisions kept, not every edit made."""
        rows: list[dict[str, Any]] = []
        page_token: str | None = None
        while True:
            params: dict[str, Any] = {"fields": "nextPageToken,revisions(id,modifiedTime,mimeType,size,keepForever,"
                                                "published,exportLinks)", "pageSize": 200}
            if page_token:
                params["pageToken"] = page_token
            body = self._get(f"/files/{file_id}/revisions", params)
            rows.extend(body.get("revisions") or [])
            page_token = body.get("nextPageToken")
            if not page_token:
                return rows

    def export_revision(self, link: str, *, attempts: int = 6, pause: float = 5.0) -> bytes:
        """The bytes behind one revision's export link (read-only). Google limits these exports tightly: a 429 or
        503 is retried after its Retry-After, or after ``pause`` seconds doubled each time."""
        import time

        for attempt in range(attempts):
            response = self._http.get(link, headers=self._headers(), follow_redirects=True)
            if response.is_success:
                return response.content
            if response.status_code not in (429, 503) or attempt == attempts - 1:
                break
            wait = response.headers.get("Retry-After", "")
            time.sleep(float(wait) if wait.isdigit() else pause * (2 ** attempt))
        raise GoogleError(f"HTTP {response.status_code} exporting a revision")

    def download_revision(self, file_id: str, revision_id: str) -> bytes:
        """One revision of a binary file (a PDF or a Word file Drive keeps versions of), read-only."""
        response = self._http.get(f"{_API}/files/{file_id}/revisions/{revision_id}", params={"alt": "media"},
                                  headers=self._headers())
        if not response.is_success:
            raise GoogleError(f"HTTP {response.status_code} downloading revision {revision_id} of {file_id}")
        return response.content

    def docs(self) -> GoogleDocs:
        """Docs client on this same access token. Does not close the Drive HTTP client."""
        return GoogleDocs(self._token, http=self._http)

    def gmail(self) -> GoogleGmail:
        """Read-only Gmail client on this same access token."""
        return GoogleGmail(self._token, http=self._http, renew=self._renew)

    def sheets(self) -> GoogleSheets:
        """Sheets client on this same access token."""
        return GoogleSheets(self._token, http=self._http)

    def create_folder(self, name: str, parent_id: str | None = None) -> str:
        """Create a folder this app can write, in ``parent_id`` or My Drive. Needs the drive.file scope."""
        metadata: dict[str, Any] = {"name": name, "mimeType": FOLDER_MIME_TYPE}
        if parent_id:
            metadata["parents"] = [parent_id]
        body = self._post("/files", metadata, params={"fields": "id", "supportsAllDrives": True})
        folder_id = str(body.get("id") or "")
        if not folder_id:
            raise GoogleError(f"folder {name} was not created")
        return folder_id

    def upload_bytes(
        self,
        name: str,
        content: bytes,
        *,
        mime_type: str,
        parent_id: str | None = None,
        convert_to: str | None = None,
        description: str | None = None,
        app_properties: dict[str, str] | None = None,
    ) -> str:
        """Upload a file this app created. Needs the drive.file scope.

        ``convert_to`` (``GOOGLE_DOC_MIME_TYPE``) imports the content as a Google file, e.g. HTML as a Doc."""
        metadata: dict[str, Any] = {"name": name}
        if parent_id:
            metadata["parents"] = [parent_id]
        if convert_to:
            metadata["mimeType"] = convert_to
        if description is not None:
            metadata["description"] = description
        if app_properties:
            metadata["appProperties"] = app_properties
        boundary = "jason-upload"
        payload = (
            f"--{boundary}\r\n"
            "Content-Type: application/json; charset=UTF-8\r\n\r\n"
            f"{json.dumps(metadata)}\r\n"
            f"--{boundary}\r\n"
            f"Content-Type: {mime_type}\r\n\r\n"
        ).encode() + content + f"\r\n--{boundary}--".encode()
        response = self._http.post(
            f"{_UPLOAD}?uploadType=multipart&fields=id",
            headers={
                **self._headers(),
                "Content-Type": f"multipart/related; boundary={boundary}",
            },
            content=payload,
        )
        body = _json(response)
        if not response.is_success:
            raise GoogleError(f"HTTP {response.status_code} uploading {name}")
        file_id = str(body.get("id") or "")
        if not file_id:
            raise GoogleError(f"upload of {name} did not return an id")
        return file_id

    def replace_content(self, file_id: str, content: bytes, *, mime_type: str) -> dict[str, Any]:
        """Replace a file's content in place (``uploadType=media``); the file keeps its id, link, and sharing. HTML
        sent to a Google Doc is imported as the Doc's new body. A person's edits since are replaced too."""
        response = self._http.patch(
            f"{_UPLOAD}/{file_id}",
            params={"uploadType": "media", "supportsAllDrives": True, "fields": "id,name,modifiedTime"},
            headers={**self._headers(), "Content-Type": mime_type},
            content=content,
        )
        body = _json(response)
        if not response.is_success:
            raise GoogleError(f"HTTP {response.status_code} replacing the content of {file_id}")
        return body

    def root_id(self) -> str:
        """The id of the root of My Drive (the folder the "root" alias names)."""
        return str(self._get("/files/root", {"fields": "id"}).get("id") or "")

    def update_metadata(self, file_id: str, *, name: str | None = None, description: str | None = None,
                        app_properties: dict[str, str] | None = None) -> dict[str, Any]:
        """Rename a file, set its description, or set jason's private ``appProperties`` (merged into those it has).
        Fields not given are left as they are."""
        payload: dict[str, Any] = {k: v for k, v in (("name", name), ("description", description)) if v is not None}
        if app_properties:
            payload["appProperties"] = app_properties
        if not payload:
            raise GoogleError("update_metadata needs a name, a description, or app properties")
        response = self._http.patch(
            f"{_API}/files/{file_id}",
            params={"supportsAllDrives": True, "fields": "id,name,description"},
            headers={**self._headers(), "Content-Type": "application/json"},
            content=json.dumps(payload),
        )
        body = _json(response)
        if not response.is_success:
            raise GoogleError(f"HTTP {response.status_code} updating {file_id}")
        return body

    def trash(self, file_id: str) -> dict[str, Any]:
        """Move a file to Drive's trash (``trashed: true``): reversible from the trash for thirty days, never a permanent
        delete. The caller names the file and has a person's word for it."""
        response = self._http.patch(
            f"{_API}/files/{file_id}",
            params={"supportsAllDrives": True, "fields": "id,name,trashed"},
            headers={**self._headers(), "Content-Type": "application/json"},
            content=json.dumps({"trashed": True}),
        )
        body = _json(response)
        if not response.is_success:
            raise GoogleError(f"HTTP {response.status_code} trashing {file_id}")
        return body

    def copy(self, file_id: str, name: str, parent_id: str | None = None) -> str:
        """Copy a file (a template Doc) under a new name into ``parent_id``; return the copy's id. The original is
        unchanged."""
        metadata: dict[str, Any] = {"name": name}
        if parent_id:
            metadata["parents"] = [parent_id]
        body = self._post(f"/files/{file_id}/copy", metadata, params={"fields": "id", "supportsAllDrives": True})
        copy_id = str(body.get("id") or "")
        if not copy_id:
            raise GoogleError(f"copy of {file_id} did not return an id")
        return copy_id

    def child_folder(self, parent_id: str, name: str) -> str:
        """The id of the folder named ``name`` directly in ``parent_id``, or an empty string."""
        safe = name.replace("\\", "\\\\").replace("'", "\\'")
        hits = self.list_files(f"'{parent_id}' in parents and name = '{safe}' and mimeType = '{FOLDER_MIME_TYPE}' and trashed = false")
        return str(hits[0]["id"]) if hits else ""

    def move(self, file_id: str, folder_id: str) -> dict[str, Any]:
        """Move a file into ``folder_id``: its parents become that folder alone. Nothing is copied or deleted, and the
        file keeps its id, link, and sharing. Needs the full Drive scope for a file jason did not create."""
        current = self._get(f"/files/{file_id}", {"fields": "id,parents", "supportsAllDrives": True})
        remove = ",".join(p for p in current.get("parents") or [] if p != folder_id)
        params: dict[str, Any] = {"addParents": folder_id, "supportsAllDrives": True, "fields": "id,name,parents"}
        if remove:
            params["removeParents"] = remove
        response = self._http.patch(f"{_API}/files/{file_id}", params=params, headers=self._headers())
        body = _json(response)
        if not response.is_success:
            raise GoogleError(f"HTTP {response.status_code} moving {file_id}")
        return body

    def share_with_link(self, file_id: str) -> None:
        """Let anyone with the link read the file. Sheets fetches photos that way."""
        self._post(
            f"/files/{file_id}/permissions",
            {"type": "anyone", "role": "reader"},
        )

    def _post(
        self,
        path: str,
        payload: dict[str, Any],
        *,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        response = self._http.post(
            f"{_API}{path}",
            params=params,
            headers={**self._headers(), "Content-Type": "application/json"},
            content=json.dumps(payload),
        )
        body = _json(response)
        if not response.is_success:
            raise GoogleError(f"HTTP {response.status_code} for {path}")
        return body

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        response = self._http.get(
            f"{_API}{path}", params=params, headers=self._headers()
        )
        body = _json(response)
        if not response.is_success:
            raise GoogleError(f"HTTP {response.status_code} for {path}")
        return body

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}


def _http_error(response: httpx.Response, what: str) -> GoogleHttpError:
    """Google's refusal as an error: its status, its first reason, and its message; an export over the limit as
    ``GoogleExportTooLarge``."""
    error = _json(response).get("error")
    error = error if isinstance(error, dict) else {}
    reasons = [str(e.get("reason") or "") for e in error.get("errors") or () if isinstance(e, dict)]
    reason = next((r for r in reasons if r), "")
    said = str(error.get("message") or "")
    message = f"HTTP {response.status_code} {what}" + (f": {said}" if said else "")
    kind = GoogleExportTooLarge if reason == "exportSizeLimitExceeded" else GoogleHttpError
    return kind(message, status=response.status_code, reason=reason)


def _json(response: httpx.Response) -> dict[str, Any]:
    try:
        body = response.json()
    except json.JSONDecodeError:
        body = {}
    return body if isinstance(body, dict) else {}
