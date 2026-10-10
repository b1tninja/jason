"""Google Vault and Photos clients (mock transport), and the separate scoped token."""

from __future__ import annotations

import json

import httpx
import pytest

from jason.google.errors import GoogleError
from jason.google.photos import GooglePhotos
from jason.google.vault import Corpus, GoogleVault


def _client(handler, seen):
    def wrapped(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)
    return httpx.Client(transport=httpx.MockTransport(wrapped))


def test_vault_lists_matters_and_holds_and_builds_a_drive_or_mail_hold() -> None:
    seen: list[httpx.Request] = []

    def handler(r: httpx.Request) -> httpx.Response:
        if r.url.path == "/v1/matters" and r.method == "GET":
            return httpx.Response(200, json={"matters": [{"matterId": "m1", "name": "26CV016125", "state": "OPEN"}]})
        if r.url.path.endswith("/holds") and r.method == "GET":
            return httpx.Response(200, json={"holds": [{"holdId": "h1", "corpus": "DRIVE", "accounts": [{"email": "a@x.com"}]}]})
        return httpx.Response(200, json={"holdId": "h2", **json.loads(r.content or b"{}")})

    vault = GoogleVault("tok", http=_client(handler, seen))
    assert [m["matterId"] for m in vault.matters()] == ["m1"] and list(vault.holds("m1"))[0]["holdId"] == "h1"
    drive = vault.create_hold("m1", "Drive", Corpus.DRIVE, ["secretary@mystiquecommunity.com"])
    assert drive["query"] == {"driveQuery": {"includeSharedDriveFiles": True}} and drive["accounts"] == [{"email": "secretary@mystiquecommunity.com"}]
    mail = vault.create_hold("m1", "Mail", Corpus.MAIL, ["a@x.com"], terms="dog OR hearing", start="2025-04-01T00:00:00Z")
    assert mail["query"] == {"mailQuery": {"terms": "dog OR hearing", "startTime": "2025-04-01T00:00:00Z"}}
    assert all(r.headers["authorization"] == "Bearer tok" for r in seen)
    with pytest.raises(GoogleError):
        vault.create_hold("m1", "none", Corpus.DRIVE, [])


def test_vault_without_a_role_says_what_is_missing() -> None:
    vault = GoogleVault("tok", http=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(403, json={}))))
    with pytest.raises(GoogleError, match="Vault role"):
        list(vault.matters())


def test_photos_picker_session_lists_and_downloads_with_the_bearer_token(tmp_path) -> None:
    seen: list[httpx.Request] = []

    def handler(r: httpx.Request) -> httpx.Response:
        if r.url.host == "photospicker.googleapis.com" and r.url.path == "/v1/sessions":
            return httpx.Response(200, json={"id": "s1", "pickerUri": "https://photos.google.com/picker/s1", "mediaItemsSet": False})
        if r.url.path == "/v1/mediaItems":
            return httpx.Response(200, json={"mediaItems": [{"id": "i1", "type": "PHOTO", "createTime": "2026-06-05T17:00:00Z",
                                                             "mediaFile": {"baseUrl": "https://lh3.googleusercontent.com/abc", "mimeType": "image/jpeg",
                                                                           "filename": "IMG_1.jpg"}}]})
        if r.url.host == "lh3.googleusercontent.com":
            return httpx.Response(200, content=b"jpeg")
        return httpx.Response(200, json={})

    photos = GooglePhotos("tok", http=_client(handler, seen))
    assert photos.create_session()["pickerUri"].endswith("/s1")
    items = list(photos.picked("s1"))
    path = photos.download(items[0], tmp_path / "IMG_1.jpg")
    assert path.read_bytes() == b"jpeg"
    download = next(r for r in seen if r.url.host == "lh3.googleusercontent.com")
    assert str(download.url).endswith("abc=d") and download.headers["authorization"] == "Bearer tok"
    assert next(r for r in seen if r.url.path == "/v1/mediaItems").url.params["sessionId"] == "s1"


def test_a_scoped_token_lives_beside_drives_and_needs_consent_once(tmp_path) -> None:
    from types import SimpleNamespace

    from jason.google.session import open_vault

    settings = SimpleNamespace(google_oauth_record_uid="uid", google_installation_client=True, google_oauth_token_file=tmp_path / "google-token.json")
    record = SimpleNamespace(custom=[{"label": "client_id", "value": ["cid"]}, {"label": "client_secret", "value": ["sec"]}])
    keeper = SimpleNamespace(load_record=lambda uid: record)
    from jason.google.errors import GoogleAuthRequired

    with pytest.raises(GoogleAuthRequired):
        open_vault(settings, keeper)                      # no token and not interactive: fail fast, no browser
    written = []

    def consent(client_id, client_secret, token_path, *, scopes):
        written.append(scopes)
        token_path.write_text(json.dumps({"refresh_token": "r", "scopes": list(scopes)}), encoding="utf-8")
        return "r"

    http = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"access_token": "t"})))
    assert isinstance(open_vault(settings, keeper, interactive=True, authorize=consent, http=http), GoogleVault)
    assert written == [("https://www.googleapis.com/auth/ediscovery",)] and (tmp_path / "google-vault-token.json").is_file()
    assert not (tmp_path / "google-token.json").exists()     # Drive's token is untouched
