"""jason photos: pick, publish, copy to Drive, and status, against a mock Google."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from jason.community.photos import AlbumNameRule
from jason.google.photos import GooglePhotos
from jason.tasks import photos as task

SHORT = "https://photos.app.goo.gl/abc123"
SHARE = "https://photos.google.com/share/AF1QipXYZ"
RULE = AlbumNameRule(prefix="Mystique")


class Community:
    photo_album_rule = RULE
    photos_drive_folder = ""


def _links(data_dir: Path) -> None:
    target = {"key": SHORT, "kind": "Google Photos album", "url": SHORT, "names": ["roof photos"], "shareUrl": SHARE,
              "labels": [{"date": "2026-08-18", "item": "Maintenance", "subitem": "Roof leak", "agenda": "Agenda"}],
              "topics": ["roof"], "drive": None,
              "incidents": [{"first": "2026-07-01", "causes": ["leak"], "addresses": ["123 Main St"], "buildings": ["2"],
                             "claims": ["CL-9"], "likely": True, "via": "linked beside x.pdf"}]}
    path = data_dir / "meetings" / "agenda-links.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"targets": [target]}), encoding="utf-8")


class Google:
    """Picker and Library endpoints; records every call."""

    def __init__(self, polls_until_set: int = 2, items: list[dict] | None = None) -> None:
        self.calls: list[tuple[str, str]] = []
        self.polls = 0
        self.polls_until_set = polls_until_set
        self.items = items if items is not None else [
            {"id": "m1", "createTime": "2026-08-01T10:00:00Z", "type": "PHOTO",
             "mediaFile": {"baseUrl": "https://lh3.example/m1", "mimeType": "image/jpeg", "filename": "IMG_1.jpg"}},
            {"id": "m2", "createTime": "2026-08-02T11:00:00Z", "type": "PHOTO",
             "mediaFile": {"baseUrl": "https://lh3.example/m2", "mimeType": "image/jpeg", "filename": "IMG_1.jpg"}},
            {"id": "m3", "createTime": "2026-08-03T12:00:00Z", "type": "VIDEO",
             "mediaFile": {"baseUrl": "https://lh3.example/m3", "mimeType": "video/mp4", "filename": "VID.mp4"}},
        ]
        self.batches: list[dict] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path, method = request.url.path, request.method
        self.calls.append((method, str(request.url)))
        if path == "/v1/sessions" and method == "POST":
            return httpx.Response(200, json={"id": "s1", "pickerUri": "https://photos.google.com/picker/s1",
                                             "pollingConfig": {"pollInterval": "3s", "timeoutIn": "600s"}})
        if path == "/v1/sessions/s1" and method == "GET":
            self.polls += 1
            return httpx.Response(200, json={"id": "s1", "mediaItemsSet": self.polls >= self.polls_until_set,
                                             "pollingConfig": {"pollInterval": "4s", "timeoutIn": "600s"}})
        if path == "/v1/sessions/s1" and method == "DELETE":
            return httpx.Response(200, json={})
        if path == "/v1/mediaItems" and method == "GET":
            return httpx.Response(200, json={"mediaItems": self.items})
        if request.url.host == "lh3.example":
            return httpx.Response(200, content=f"bytes of {path}".encode())
        if path == "/v1/albums" and method == "GET":
            return httpx.Response(200, json={"albums": []})
        if path == "/v1/albums" and method == "POST":
            body = json.loads(request.content)
            return httpx.Response(200, json={"id": "alb1", "title": body["album"]["title"], "productUrl": "https://p/alb1"})
        if path == "/v1/uploads":
            return httpx.Response(200, text=f"tok-{len([c for c in self.calls if c[1].endswith('/uploads')])}")
        if path == "/v1/mediaItems:batchCreate":
            body = json.loads(request.content)
            self.batches.append(body)
            return httpx.Response(200, json={"newMediaItemResults": [
                {"uploadToken": n["simpleMediaItem"]["uploadToken"], "status": {"message": "Success"},
                 "mediaItem": {"id": "mi-" + n["simpleMediaItem"]["uploadToken"], "productUrl": "https://p/x"}}
                for n in body["newMediaItems"]]})
        return httpx.Response(404, json={"error": {"message": f"unexpected {method} {path}"}})


class Clock:
    def __init__(self) -> None:
        self.now = 0.0
        self.slept: list[float] = []

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds

    def __call__(self) -> float:
        return self.now


def _pick(tmp_path: Path, google: Google, **kw) -> tuple[dict, Clock]:
    clock = Clock()
    with GooglePhotos("tok", http=httpx.Client(transport=httpx.MockTransport(google))) as photos:
        result = task.pick(photos, tmp_path, Community(), SHORT, log=lambda s: None, sleep=clock.sleep, clock=clock, **kw)
    return result, clock


def test_pick_saves_items_and_manifest(tmp_path: Path) -> None:
    _links(tmp_path)
    google = Google()
    result, clock = _pick(tmp_path, google)
    assert clock.slept == [3.0, 4.0]                     # the session's own poll interval
    assert result["added"] == 3
    m = task.load_manifest(tmp_path, result["slug"])
    assert result["slug"].startswith("2026-08-18-maintenance-")
    assert m["shareUrl"] == SHARE and m["labels"][0]["subitem"] == "Roof leak" and m["incidents"][0]["claims"] == ["CL-9"]
    assert m["locationStripped"] is True and "location" in m["locationNote"]
    names = [i["path"].rsplit("/", 1)[-1] for i in m["items"]]
    assert names == ["IMG_1.jpg", "IMG_1-20260802110000.jpg", "VID.mp4"]
    assert all(len(i["sha256"]) == 64 and len(i["md5"]) == 32 for i in m["items"])
    assert any(u.endswith("/m3=dv") for _, u in google.calls) and any(u.endswith("/m1=d") for _, u in google.calls)
    assert ("DELETE", "https://photospicker.googleapis.com/v1/sessions/s1") in google.calls
    # Picking the same photos again adds nothing.
    again, _ = _pick(tmp_path, Google(polls_until_set=0))
    assert again["added"] == 0 and again["skipped"] == 3


def test_pick_times_out_and_deletes_session(tmp_path: Path) -> None:
    google = Google(polls_until_set=10 ** 6)
    with pytest.raises(task.PickTimeout):
        _pick(tmp_path, google, timeout=10)
    assert google.calls[-1][0] == "DELETE"


def test_unlabeled_album(tmp_path: Path) -> None:
    result, _ = _pick(tmp_path, Google(polls_until_set=0))
    m = task.load_manifest(tmp_path, result["slug"])
    assert result["slug"].startswith("unlabeled-") and m["label"] == "unlabeled" and m["labels"] == []


def test_album_title_rule() -> None:
    labels = [{"date": "2026-08-18", "item": "Maintenance", "subitem": "Roof leak"}]
    incidents = [{"likely": True, "addresses": ["123 Main St"], "claims": ["CL-9", "CL-10"]}]
    assert RULE.title(labels, incidents) == "Mystique 2026-08-18 Maintenance / Roof leak, 123 Main St, claim CL-9, CL-10"
    assert RULE.title(labels, [{**incidents[0], "likely": False}]) == "Mystique 2026-08-18 Maintenance / Roof leak"
    assert RULE.title([], [], picked="2026-09-29T00:00:00+00:00") == "Mystique unlabeled 2026-09-29"
    assert RULE.description(labels) == "2026-08-18 Maintenance / Roof leak"


def test_publish_dry_run_then_yes(tmp_path: Path) -> None:
    _links(tmp_path)
    result, _ = _pick(tmp_path, Google(polls_until_set=0))
    slug = result["slug"]
    plan = task.publish(None, tmp_path, slug, community=Community())
    assert plan["dryRun"] and plan["toUpload"] == 3 and plan["title"].startswith("Mystique 2026-08-18")
    google = Google()
    with GooglePhotos("tok", http=httpx.Client(transport=httpx.MockTransport(google))) as photos:
        done = task.publish(photos, tmp_path, slug, yes=True, community=Community())
        assert done["uploaded"] == 3 and done["albumId"] == "alb1" and not done["failed"]
        again = task.publish(photos, tmp_path, slug, yes=True, community=Community())
    assert again["toUpload"] == 0
    assert google.batches[0]["albumId"] == "alb1"
    assert google.batches[0]["newMediaItems"][0]["description"] == "2026-08-18 Maintenance / Roof leak"
    assert sum(1 for m, u in google.calls if m == "POST" and u.endswith("/albums")) == 1
    m = task.load_manifest(tmp_path, slug)
    assert all(i["mediaItemId"].startswith("mi-tok-") for i in m["items"])


class Drive:
    def __init__(self) -> None:
        self.folders: dict[tuple[str, str], str] = {}
        self.uploads: list[tuple[str, str]] = []

    def child_folder(self, parent_id: str, name: str) -> str:
        return self.folders.get((parent_id, name), "")

    def create_folder(self, name: str, parent_id: str | None = None) -> str:
        self.folders[(parent_id or "", name)] = f"f{len(self.folders) + 1}"
        return self.folders[(parent_id or "", name)]

    def upload_bytes(self, name: str, content: bytes, *, mime_type: str, parent_id: str | None = None) -> str:
        self.uploads.append((name, parent_id or ""))
        return f"d{len(self.uploads)}"


def test_to_drive_and_status(tmp_path: Path) -> None:
    _links(tmp_path)
    slug = _pick(tmp_path, Google(polls_until_set=0))[0]["slug"]
    with pytest.raises(ValueError):
        task.to_drive(Drive(), tmp_path, slug, "", yes=True, community=Community())
    drive = Drive()
    plan = task.to_drive(drive, tmp_path, slug, "PARENT", community=Community())
    assert plan["dryRun"] and plan["toCopy"] == 3 and not drive.uploads
    done = task.to_drive(drive, tmp_path, slug, "PARENT", yes=True, community=Community())
    assert done["copied"] == 3 and {p for _, p in drive.uploads} == {"f1"}
    assert task.to_drive(drive, tmp_path, slug, "PARENT", yes=True, community=Community())["copied"] == 0
    rows = task.status(tmp_path)
    assert rows[0]["items"] == 3 and rows[0]["inDrive"] == 3 and rows[0]["published"] == 0
    assert any("not published" in line for line in task.status_lines(rows))


def test_spec_rows_load() -> None:
    from jason.community import mystique

    rule = task.album_rule(mystique())
    assert rule.prefix == "Mystique"
    assert task.drive_folder(mystique()) == ""
