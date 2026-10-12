"""The held copies from Google's Picker as the console uses them (docs/google-picker.md, "The UI"): the list of copies on the start page
(``GET /api/drive-held``) and the hand-over of a held copy to a record slot (``{"act": "upload", "heldId"}``). Fakes only."""

from __future__ import annotations

import base64
import hashlib
import json

import pytest
import webclient

from jason.tasks import drive_pick
from test_record_intake_phase3 import BY, MIN, _pdf  # noqa: F401
from test_record_intake_phase2 import _app, world  # noqa: F401  (world is a fixture)


def _hold(root, data: bytes, *, day="2026-10-01", confidential=False, pages=1) -> str:
    sha = hashlib.sha256(data).hexdigest()
    drive_pick._write_atomic(drive_pick.held_file(root, sha), data)
    note = {"sha256": sha, "size": len(data), "pages": pages, "mime": "application/pdf", "confidential": confidential,
            "picks": [{"by": "A Manager", "at": f"{day}T10:00:00+00:00", "via": drive_pick.VIA, "driveIdHash": "ab" * 8, "modified": ""}]}
    drive_pick._write_atomic(drive_pick._prov_file(root, sha), json.dumps(note).encode("utf-8"))
    return sha


def test_the_listing_is_numbers_sizes_and_days_newest_first_with_no_name_or_id_for_a_confidential_copy(tmp_path):
    a = _hold(tmp_path, b"%PDF-1 a", day="2026-09-01", pages=2)
    b = _hold(tmp_path, b"%PDF-1 bb", day="2026-10-02", pages=3)
    c = _hold(tmp_path, b"%PDF-1 ccc", day="2026-10-03", confidential=True, pages=9)
    out = drive_pick.listing(tmp_path)
    assert [r["n"] for r in out["copies"]] == [1, 2, 3] and out["total"] == 3
    assert [r["day"] for r in out["copies"]] == ["2026-10-03", "2026-10-02", "2026-09-01"]
    hidden, plain, older = out["copies"]
    assert hidden["confidential"] and hidden["held"] and hidden["id"] == "" and hidden["size"] is None and hidden["pages"] is None
    assert plain["id"] == b and plain["size"] == len(b"%PDF-1 bb") and plain["pages"] == 3 and older["id"] == a
    assert c not in json.dumps(out)
    shown = drive_pick.listing(tmp_path, private=True)["copies"][0]
    assert shown["id"] == c and shown["size"] == len(b"%PDF-1 ccc") and not shown["held"]
    assert drive_pick.listing(tmp_path / "nothing")["copies"] == []


def test_the_source_is_the_boards_and_read_only(world, monkeypatch):  # noqa: F811
    sha = _hold(world.root, _pdf(2), pages=2)
    c = webclient.client(_app(world, monkeypatch, sign_in=webclient.roster_sign_in()))
    assert c.get("/api/drive-held").status_code in (401, 403)
    webclient.sign_in(c, "A Manager")
    got = c.get("/api/drive-held")
    assert got.status_code == 200 and got.json["copies"][0]["id"] == sha and got.json["copies"][0]["pages"] == 2
    assert c.get("/api/drive-held?view=owner").status_code == 403
    assert "name" not in got.json["copies"][0]


def test_a_held_copy_is_handed_to_a_slot_by_the_server_and_never_pinned_as_a_drive_file(world, monkeypatch):  # noqa: F811
    data = _pdf(2)
    sha = _hold(world.root, data, pages=2)
    c = webclient.client(_app(world, monkeypatch))
    url = "/api/write/records/" + MIN
    body = {"act": "upload", "heldId": sha, "name": "Minutes June", "period": "2099-06", "by": BY}
    plan = c.post(url, json={**body, "dryRun": True})
    assert plan.status_code == 200 and plan.json["would"]["size"] == len(data) and not (world.root / "record-intake").exists()
    made = c.post(url, json=body)
    assert made.status_code == 200 and made.json["pin"].startswith("p-") and made.json["sha256"] == sha[:12]
    store = json.loads((world.spec / "example" / "records.json").read_text(encoding="utf-8")) if (world.spec / "example" / "records.json").exists() else {}
    pins = store.get("pins", [])
    assert pins and pins[-1]["kind"] == "file" and pins[-1]["name"] == "Minutes June.pdf"
    assert c.post(url, json={**body, "heldId": "0" * 64}).status_code == 400
    assert c.post(url, json={**body, "heldId": "../../x"}).status_code == 400
    assert c.post(url, json={**body, "base64": base64.b64encode(data).decode()}).status_code == 400
