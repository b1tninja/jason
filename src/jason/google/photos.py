"""Google Photos: the Picker API to take in photos a person picks, and the Library API for albums jason keeps.

Since March 31, 2025 no app can list or read a person's own library: the Library API reaches only media and albums the
app created, and cannot share an album. So there are two halves:

- **Picker** (``photospicker.googleapis.com/v1``, scope ``photospicker.mediaitems.readonly``): ``create_session`` gives
  a ``pickerUri``; the person opens it and picks (an album's photos can be picked all at once); ``session`` is polled
  until ``mediaItemsSet``; ``picked`` lists the items; ``download`` saves each (``=d`` for a photo, which keeps its
  Exif except location, ``=dv`` for a video), with the bearer token, within 60 minutes; ``delete_session`` ends it.
- **Library, app-created only** (``photoslibrary.googleapis.com/v1``): ``create_album``, ``albums`` (jason's own),
  ``upload`` (raw bytes to an upload token), ``add_to_album`` (``mediaItems:batchCreate``, 50 at a time), and
  ``album_items``. Sharing an album is done by a person in the Google Photos app.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

import httpx

from jason.google.errors import GoogleError

PICKER = "https://photospicker.googleapis.com/v1"
LIBRARY = "https://photoslibrary.googleapis.com/v1"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
BATCH = 50


class GooglePhotos:
    def __init__(self, access_token: str, *, http: httpx.Client | None = None) -> None:
        if not access_token:
            raise GoogleError("missing access token")
        self._token = access_token
        self._owns_http = http is None
        self._http = http or httpx.Client(timeout=120.0, follow_redirects=True)

    @classmethod
    def from_refresh_token(cls, *, client_id: str, client_secret: str, refresh_token: str,
                           http: httpx.Client | None = None) -> GooglePhotos:
        client = http or httpx.Client(timeout=120.0, follow_redirects=True)
        response = client.post(_TOKEN_URL, data={"client_id": client_id, "client_secret": client_secret,
                                                 "refresh_token": refresh_token, "grant_type": "refresh_token"})
        token = (response.json() if response.content else {}).get("access_token")
        if not token:
            raise GoogleError("the Photos token was refused; sign in again with `jason photos --login --interactive`")
        photos = cls(str(token), http=client)
        photos._owns_http = http is None
        return photos

    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    def __enter__(self) -> GooglePhotos:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _headers(self, **extra: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}", **extra}

    def _call(self, method: str, url: str, *, params: dict[str, Any] | None = None, json_body: Any = None) -> dict[str, Any]:
        response = self._http.request(method, url, params=params, json=json_body, headers=self._headers())
        if not response.is_success:
            try:
                message = response.json().get("error", {}).get("message", "")
            except Exception:
                message = response.text[:200]
            raise GoogleError(f"HTTP {response.status_code} {method} {url.split('/v1')[-1]}: {message}")
        return response.json() if response.content else {}

    # --- Picker ---------------------------------------------------------------------------------------------------

    def create_session(self) -> dict[str, Any]:
        """A picking session: ``id``, ``pickerUri`` (for the person), ``pollingConfig``, ``mediaItemsSet``."""
        return self._call("POST", f"{PICKER}/sessions", json_body={})

    def session(self, session_id: str) -> dict[str, Any]:
        return self._call("GET", f"{PICKER}/sessions/{session_id}")

    def picked(self, session_id: str) -> Iterator[dict[str, Any]]:
        """The items the person picked: ``id``, ``createTime``, ``type``, ``mediaFile`` (``baseUrl``, ``mimeType``, ``filename``)."""
        params: dict[str, Any] = {"sessionId": session_id, "pageSize": 100}
        while True:
            body = self._call("GET", f"{PICKER}/mediaItems", params=params)
            yield from body.get("mediaItems") or []
            if not body.get("nextPageToken"):
                return
            params["pageToken"] = body["nextPageToken"]

    def download(self, item: dict[str, Any], dest: Path) -> Path:
        """Save a picked item: the photo with its Exif (not its location), or the video."""
        media = item.get("mediaFile") or {}
        suffix = "=dv" if str(item.get("type")).upper() == "VIDEO" else "=d"
        response = self._http.get(media["baseUrl"] + suffix, headers=self._headers())
        if not response.is_success:
            raise GoogleError(f"HTTP {response.status_code} downloading {media.get('filename')}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(response.content)
        return dest

    def delete_session(self, session_id: str) -> None:
        self._call("DELETE", f"{PICKER}/sessions/{session_id}")

    # --- Library, app-created only --------------------------------------------------------------------------------

    def create_album(self, title: str) -> dict[str, Any]:
        return self._call("POST", f"{LIBRARY}/albums", json_body={"album": {"title": title}})

    def albums(self) -> Iterator[dict[str, Any]]:
        """The albums jason created (the only ones the API returns now)."""
        params: dict[str, Any] = {"pageSize": 50, "excludeNonAppCreatedData": True}
        while True:
            body = self._call("GET", f"{LIBRARY}/albums", params=params)
            yield from body.get("albums") or []
            if not body.get("nextPageToken"):
                return
            params["pageToken"] = body["nextPageToken"]

    def upload(self, path: Path, mime_type: str) -> str:
        """Send a file's bytes; the upload token lasts a day and is spent by ``add_to_album``."""
        response = self._http.post(f"{LIBRARY}/uploads", content=Path(path).read_bytes(),
                                   headers=self._headers(**{"Content-type": "application/octet-stream",
                                                            "X-Goog-Upload-Content-Type": mime_type,
                                                            "X-Goog-Upload-Protocol": "raw"}))
        if not response.is_success or not response.text:
            raise GoogleError(f"HTTP {response.status_code} uploading {Path(path).name}")
        return response.text

    def add_to_album(self, album_id: str, uploads: list[tuple[str, str, str]]) -> list[dict[str, Any]]:
        """Create media items from (upload token, file name, description) in the album, 50 per call."""
        results: list[dict[str, Any]] = []
        for start in range(0, len(uploads), BATCH):
            chunk = uploads[start:start + BATCH]
            body = {"albumId": album_id, "newMediaItems": [
                {"description": description[:1000], "simpleMediaItem": {"uploadToken": token, "fileName": name}}
                for token, name, description in chunk]}
            results += self._call("POST", f"{LIBRARY}/mediaItems:batchCreate", json_body=body).get("newMediaItemResults") or []
        return results

    def album_items(self, album_id: str) -> Iterator[dict[str, Any]]:
        body: dict[str, Any] = {"albumId": album_id, "pageSize": 100}
        while True:
            page = self._call("POST", f"{LIBRARY}/mediaItems:search", json_body=body)
            yield from page.get("mediaItems") or []
            if not page.get("nextPageToken"):
                return
            body["pageToken"] = page["nextPageToken"]


def load_token(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8")) if Path(path).is_file() else {}


__all__ = ["GooglePhotos", "LIBRARY", "PICKER", "load_token"]
