"""Drive appProperties on a file: read, set, and search. Uses the ``GoogleDrive`` client's HTTP session and token.

appProperties are private to the OAuth application that sets them. files.update merges: a key not in the body is kept,
and a key set to null is removed. Each key and value together is at most 124 bytes of UTF-8.
"""

from __future__ import annotations

import json
from typing import Any

from jason.google.drive import GoogleDrive
from jason.google.errors import GoogleError

_API = "https://www.googleapis.com/drive/v3"
PROPERTY_BYTES = 124


def get_app_properties(drive: GoogleDrive, file_id: str) -> dict[str, str]:
    """The file's appProperties for this application (an empty dict when it has none)."""
    body = drive._get(f"/files/{file_id}", {"fields": "id,appProperties", "supportsAllDrives": True})
    return {str(k): str(v) for k, v in (body.get("appProperties") or {}).items()}


def set_app_properties(drive: GoogleDrive, file_id: str, properties: dict[str, str | None]) -> dict[str, str]:
    """Set (or, with None, remove) the given keys and return the file's appProperties after the update. Keys not
    given are left as they are."""
    for key, value in properties.items():
        size = len(key.encode("utf-8")) + len((value or "").encode("utf-8"))
        if size > PROPERTY_BYTES:
            raise GoogleError(f"appProperty {key} on {file_id} is {size} bytes; the limit is {PROPERTY_BYTES}")
    response = drive._http.patch(
        f"{_API}/files/{file_id}",
        params={"fields": "id,appProperties", "supportsAllDrives": True},
        headers={**drive._headers(), "Content-Type": "application/json"},
        content=json.dumps({"appProperties": properties}),
    )
    try:
        body = response.json()
    except json.JSONDecodeError:
        body = {}
    if not response.is_success:
        raise GoogleError(f"HTTP {response.status_code} setting appProperties on {file_id}")
    return {str(k): str(v) for k, v in ((body or {}).get("appProperties") or {}).items()}


def query(key: str, value: str) -> str:
    """The files.list query for an exact key and value."""
    def quote(text: str) -> str:
        return text.replace("\\", "\\\\").replace("'", "\\'")

    return f"appProperties has {{ key='{quote(key)}' and value='{quote(value)}' }} and trashed = false"


def search(drive: GoogleDrive, key: str, value: str) -> list[dict[str, Any]]:
    """Every file whose appProperty ``key`` equals ``value`` exactly."""
    return drive.list_files(query(key, value), fields="id,name,mimeType,webViewLink,appProperties")


__all__ = ["PROPERTY_BYTES", "get_app_properties", "query", "search", "set_app_properties"]
