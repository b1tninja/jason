"""Drive Activity client, parsing, and the agenda-missing and folder reports (mock transport)."""

from __future__ import annotations

import json

import httpx
import pytest

from jason.google.drive_activity import (
    ActionType,
    ActivityNotVisible,
    ActorKind,
    CUSTODY_ACTIONS,
    DeleteType,
    DriveActivityClient,
    build_filter,
    parse_activity,
)
from jason.tasks.drive_activity import Standing, activity_for, agenda_missing, folder_watch, missing_targets, write

ME = {"user": {"knownUser": {"personName": "people/111", "isCurrentUser": True}}}
OTHER = {"user": {"knownUser": {"personName": "people/222"}}}


def _file(fid: str, title: str = "Doc") -> dict:
    return {"driveItem": {"name": f"items/{fid}", "title": title, "mimeType": "application/pdf", "file": {},
                          "driveFile": {}, "owner": OTHER}}


def _folder(fid: str) -> dict:
    return {"driveItem": {"name": f"items/{fid}", "title": f"Folder {fid}", "driveFolder": {"type": "STANDARD_FOLDER"}}}


MOVE = {"primaryActionDetail": {"move": {"addedParents": [_folder("new")], "removedParents": [_folder("old")]}},
        "actors": [OTHER], "targets": [_file("f1")], "timestamp": "2026-03-02T10:00:00Z",
        "actions": [{"detail": {"move": {}}}]}
SHARE = {"primaryActionDetail": {"permissionChange": {
            "addedPermissions": [{"role": "VIEWER", "anyone": {}}],
            "removedPermissions": [{"role": "EDITOR", "user": {"knownUser": {"personName": "people/333"}}}]}},
         "actors": [ME], "targets": [_file("f1")], "timeRange": {"startTime": "2026-04-01T00:00:00Z",
                                                                 "endTime": "2026-04-01T00:05:00Z"}}
TRASH = {"primaryActionDetail": {"delete": {"type": "TRASH"}}, "actors": [OTHER], "targets": [_file("f1")],
         "timestamp": "2026-05-01T00:00:00Z"}
RENAME = {"primaryActionDetail": {"rename": {"oldTitle": "A", "newTitle": "B"}}, "actors": [{"administrator": {}}],
          "targets": [_file("f1", "B")], "timestamp": "2026-01-01T00:00:00Z"}
PURGE = {"primaryActionDetail": {"delete": {"type": "PERMANENT_DELETE"}}, "actors": [{"anonymous": {}}],
         "targets": [_file("f2")], "timestamp": "2026-06-01T00:00:00Z"}


def _client(handler, seen: list[httpx.Request]) -> DriveActivityClient:
    def wrapped(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)
    return DriveActivityClient("tok", http=httpx.Client(transport=httpx.MockTransport(wrapped)))


def test_parse_reads_move_share_trash_rename_and_actors() -> None:
    move = parse_activity(MOVE)
    assert move.action is ActionType.MOVE and move.time == "2026-03-02T10:00:00Z"
    assert [p.item_id for p in move.added_parents] == ["new"] and move.removed_parents[0].folder
    assert move.targets[0].item_id == "f1" and move.targets[0].owner == "people/222"
    share = parse_activity(SHARE)
    assert share.time == "2026-04-01T00:05:00Z" and share.link_shared
    assert share.actors[0].is_current_user and share.actors[0].person == "people/111"
    assert share.removed_permissions[0].grantee == "people/333" and share.removed_permissions[0].role == "EDITOR"
    assert parse_activity(TRASH).delete_type is DeleteType.TRASH
    rename = parse_activity(RENAME)
    assert (rename.old_title, rename.new_title) == ("A", "B") and rename.actors[0].kind is ActorKind.ADMINISTRATOR
    assert parse_activity(PURGE).actors[0].kind is ActorKind.ANONYMOUS
    assert parse_activity({"primaryActionDetail": {"somethingNew": {}}}).action is ActionType.UNKNOWN


def test_filter_joins_time_and_action_cases() -> None:
    assert build_filter("2026-01-01") == 'time >= "2026-01-01T00:00:00Z"'
    assert build_filter(None, (ActionType.DELETE, ActionType.PERMISSION_CHANGE)) == \
        "detail.action_detail_case:(DELETE PERMISSION_CHANGE)"
    assert build_filter() is None


def test_query_pages_and_sends_item_name_filter_and_bearer() -> None:
    seen: list[httpx.Request] = []

    def handler(r: httpx.Request) -> httpx.Response:
        body = json.loads(r.content)
        if "pageToken" not in body:
            return httpx.Response(200, json={"activities": [TRASH], "nextPageToken": "p2"})
        return httpx.Response(200, json={"activities": [MOVE]})

    client = _client(handler, seen)
    got = list(client.query(item="f1", since="2026-01-01", actions=CUSTODY_ACTIONS))
    assert [a.action for a in got] == [ActionType.DELETE, ActionType.MOVE]
    first, second = (json.loads(r.content) for r in seen)
    assert first["itemName"] == "items/f1" and "ancestorName" not in first
    assert first["filter"].startswith('time >= "2026-01-01T00:00:00Z" AND detail.action_detail_case:(DELETE MOVE')
    assert second["pageToken"] == "p2"
    assert all(r.method == "POST" and r.headers["authorization"] == "Bearer tok" for r in seen)
    with pytest.raises(Exception):
        list(client.query(item="a", ancestor="b"))


def test_forbidden_is_not_visible() -> None:
    client = _client(lambda r: httpx.Response(403, json={"error": {"message": "denied"}}), [])
    with pytest.raises(ActivityNotVisible):
        list(client.query(item="x"))
    result = activity_for(client, ["x"])
    assert result["x"].standing is Standing.NOT_VISIBLE and result["x"].status == 403


def _agenda(tmp_path) -> None:
    targets = [
        {"key": "f1", "kind": "Drive file", "inDrive": False, "names": ["Moved"], "labels": [{"date": "2026-02-01"}]},
        {"key": "f2", "kind": "Google Doc, Sheet, or Slides", "inDrive": False, "names": ["Purged"], "labels": []},
        {"key": "f3", "kind": "Drive folder", "inDrive": False, "names": ["Private"], "labels": []},
        {"key": "f4", "kind": "Drive file", "inDrive": True, "names": ["Held"], "labels": []},
        {"key": "https://x", "kind": "web page", "inDrive": False, "names": [], "labels": []},
    ]
    (tmp_path / "meetings").mkdir()
    (tmp_path / "meetings" / "agenda-links.json").write_text(json.dumps({"targets": targets}), encoding="utf-8")


def test_agenda_missing_reports_each_standing(tmp_path) -> None:
    _agenda(tmp_path)
    assert [t["key"] for t in missing_targets(tmp_path)] == ["f1", "f2", "f3"]

    def handler(r: httpx.Request) -> httpx.Response:
        if r.url.host == "www.googleapis.com":
            fid = r.url.path.rsplit("/", 1)[1]
            if fid == "f1":
                return httpx.Response(200, json={"id": "f1", "trashed": True})
            return httpx.Response(404, json={})
        name = json.loads(r.content)["itemName"]
        if name == "items/f1":
            return httpx.Response(200, json={"activities": [MOVE, TRASH, SHARE, RENAME]})
        if name == "items/f2":
            return httpx.Response(200, json={"activities": [PURGE]})
        return httpx.Response(200, json={})      # the Activity API answers an unseen item with nothing

    seen: list[httpx.Request] = []
    report = agenda_missing(_client(handler, seen), tmp_path)
    rows = {r["id"]: r for r in report["files"]}
    assert rows["f1"]["standing"] == Standing.TRASHED.value
    assert rows["f1"]["lastAction"]["action"] == "delete" and rows["f1"]["anyoneLinkAdded"]
    assert len(rows["f1"]["moved"]) == 1 and len(rows["f1"]["sharingChanged"]) == 1
    assert {"person": "people/111", "isCurrentUser": True} in rows["f1"]["actors"]
    assert rows["f1"]["agendas"] == ["2026-02-01"]
    assert rows["f2"]["standing"] == Standing.PERMANENTLY_DELETED.value
    assert rows["f3"]["standing"] == Standing.NOT_VISIBLE.value and not rows["f3"]["visible"]
    assert report["items"] == 3 and all(r.method in ("GET", "POST") for r in seen)
    out = write(tmp_path, report)
    assert out.name == "activity-agenda-missing.json" and out.parent.name == "drive"


def test_folder_watch_uses_ancestor_name() -> None:
    seen: list[httpx.Request] = []
    client = _client(lambda r: httpx.Response(200, json={"activities": [MOVE, SHARE]}), seen)
    report = folder_watch(client, "fold", since="2026-01-01")
    assert json.loads(seen[0].content)["ancestorName"] == "items/fold"
    assert report["count"] == 2 and report["byAction"] == {"move": 1, "permissionChange": 1}
    assert report["anyoneLinkAdded"] == 1 and report["name"] == "folder-fold"


def test_command_registers(tmp_path) -> None:
    import argparse

    from jason.commands.drive_activity import register

    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers()
    register(sub, lambda p: p.add_argument("--env"), lambda a: None)
    args = parser.parse_args(["drive-activity", "--folder", "abc", "--since", "2026-01-01"])
    assert args.folder == "abc" and args.since == "2026-01-01" and callable(args.func)
