from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from jason.community.drive_labels import PROPERTY_BYTES, Fit, Label, LabelProperty, LabelSource, fit, fits
from jason.google.drive import GoogleDrive
from jason.google.drive_properties import query, search as search_properties
from jason.tasks import drive_labels as task

LONG_ITEM = "Reserve Study and the funding plan for the roofs, gutters, and the painting of every building " * 3


def _write(path: Path, body: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body), encoding="utf-8")


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    _write(tmp_path / "drive" / "files.json", {"files": [
        {"id": "doc1", "name": "Roof Proposal.pdf", "path": "My Drive/Proposals/Roof Proposal.pdf", "mimeType": "application/pdf"},
        {"id": "min1", "name": "Minutes of 8/18/26", "path": "My Drive/Meetings/2026/Minutes of 8/18/26",
         "mimeType": "application/vnd.google-apps.document"},
        {"id": "exec1", "name": "Executive Session", "path": "My Drive/Meetings/exec", "mimeType": "application/pdf"},
    ]})
    _write(tmp_path / "drive" / "holdings.json", {"rows": [
        {"id": "doc1", "kind": "proposal", "records": ["enhanced"], "confidential": False},
        {"id": "exec1", "kind": "executive_session", "records": [], "confidential": True},
        {"id": "gone", "kind": "invoice", "records": [], "confidential": False},
    ]})
    labels = [{"date": f"20{y:02d}-0{m}-1{m}", "item": LONG_ITEM, "subitem": "", "agenda": "a"}
              for y in range(10, 27) for m in (1, 5)]
    _write(tmp_path / "meetings" / "agenda-links.json", {"targets": [
        {"key": "doc1", "kind": "Drive file", "inDrive": True, "labels": labels,
         "topics": ["maintenance and repairs", "insurance"], "documentKind": "proposal",
         "drive": {"id": "doc1", "name": "Roof Proposal.pdf", "path": "My Drive/Proposals/Roof Proposal.pdf"},
         "incidents": [{"first": "2022-12-14", "causes": ["water intrusion"], "addresses": ["5639 WHIMSICAL LN"],
                        "buildings": [8], "claims": ["CLM-1"], "likely": True, "via": "the file itself"}]},
        {"key": "album", "kind": "Google Photos album", "inDrive": True, "labels": labels[:1], "drive": None},
        {"key": "https://example.org", "kind": "web page", "inDrive": True, "labels": labels[:1], "drive": None},
    ]})
    _write(tmp_path / "meetings" / "catalog.json", {"meetings": [
        {"date": "2026-08-18", "records": [
            {"kind": "minutes", "where": "Drive", "ref": "min1", "date": "2026-08-18", "confidential": False},
            {"kind": "minutes", "where": "Gmail", "ref": "x", "date": "2026-08-18", "confidential": False}]},
    ]})
    return tmp_path


def test_schema_rows_fit_and_are_jason_keys() -> None:
    rows = task.schema()
    assert {r.label for r in rows} == set(Label)
    for r in rows:
        assert r.key.startswith("jason_") and r.max_value_bytes > 0
    assert Label.HOLD.value not in task.owned_keys(rows)


def test_fit_trims_deterministically() -> None:
    row = LabelProperty(Label.ITEM, "", "", LabelSource.AGENDA_LINKS, fit=Fit.TEXT)
    value = fit(row, "é" * 200)
    assert value == fit(row, "é" * 200) and fits(row.key, value) and value.endswith("…")
    lst = LabelProperty(Label.MEETINGS, "", "", LabelSource.AGENDA_LINKS, fit=Fit.LIST)
    dates = ",".join(f"2026-01-{d:02d}" for d in range(1, 30))
    out = fit(lst, dates)
    assert fits(lst.key, out) and dates.startswith(out) and not out.endswith(",")
    assert fit(LabelProperty(Label.KIND, "", "", LabelSource.DRIVE_HOLDINGS), "x" * 200) is None


def test_plan_labels_only_listed_drive_files(data_dir: Path) -> None:
    plan = task.plan(data_dir)
    ids = {f["id"] for f in plan["files"]}
    assert ids == {"doc1", "min1", "exec1"}
    assert plan["counts"]["notInDriveListing"] == 1
    assert plan["counts"]["linksWithoutDriveFile"] == {"Google Photos album": 1, "web page": 1}
    for f in plan["files"]:
        for key, value in f["properties"].items():
            assert key.startswith("jason_") and key != Label.HOLD.value
            assert len(key.encode()) + len(value.encode()) <= PROPERTY_BYTES
    doc = next(f for f in plan["files"] if f["id"] == "doc1")["properties"]
    assert doc["jason_kind"] == "proposal" and doc["jason_topics"] == "maintenance,insurance"
    assert doc["jason_meetings"].startswith("2026-05-15,2026-01-11")
    assert doc["jason_item"].endswith("…")
    assert doc["jason_incident"].startswith("2022-12-14 5639 WHIMSICAL LN") and doc["jason_claims"] == "CLM-1"
    assert next(f for f in plan["files"] if f["id"] == "exec1")["properties"]["jason_confidential"] == "1"
    assert next(f for f in plan["files"] if f["id"] == "min1")["properties"]["jason_meetings"] == "2026-08-18"


def _mock(store: dict[str, dict[str, str]], sent: list[dict]) -> GoogleDrive:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "GET" and path == "/drive/v3/files":
            q = request.url.params["q"]
            hits = [{"id": i, "name": i, "appProperties": p} for i, p in store.items()
                    if any(f"key='{k}' and value='{v}'" in q for k, v in p.items())]
            return httpx.Response(200, json={"files": hits})
        file_id = path.rsplit("/", 1)[-1]
        if request.method == "GET":
            return httpx.Response(200, json={"id": file_id, "appProperties": store.get(file_id, {})})
        if request.method == "PATCH":
            body = json.loads(request.content)
            sent.append({"id": file_id, **body})
            props = store.setdefault(file_id, {})
            for k, v in body["appProperties"].items():
                if v is None:
                    props.pop(k, None)
                else:
                    props[k] = v
            return httpx.Response(200, json={"id": file_id, "appProperties": props})
        return httpx.Response(404)

    return GoogleDrive("token", http=httpx.Client(transport=httpx.MockTransport(handler)))


def test_apply_writes_only_jason_keys_and_keeps_others(data_dir: Path) -> None:
    store = {"doc1": {"other_app_key": "keep", "jason_hold": "matter-1", "jason_claims": "OLD", "jason_legacy": "x"}}
    sent: list[dict] = []
    drive = _mock(store, sent)
    plan = task.plan(data_dir)
    with pytest.raises(PermissionError):
        task.apply(drive, plan, yes=False)
    assert sent == []
    result = task.apply(drive, plan, yes=True, data_dir=data_dir, today="2026-09-29")
    assert result["written"] == 3 and not result["failed"]
    owned = task.owned_keys(task.schema())
    for call in sent:
        for key, value in call["appProperties"].items():
            assert key in owned and key.startswith("jason_")
            assert value is None or len(key.encode()) + len(value.encode()) <= PROPERTY_BYTES
    assert store["doc1"]["other_app_key"] == "keep" and store["doc1"]["jason_hold"] == "matter-1"
    assert store["doc1"]["jason_legacy"] == "x"                # a jason_ key not in the schema is not jason's to remove
    assert store["doc1"]["jason_claims"] == "CLM-1" and store["doc1"]["jason_labeled_at"] == "2026-09-29"
    # a second run sends nothing and the cache matches Drive
    sent.clear()
    again = task.apply(drive, plan, yes=True, data_dir=data_dir)
    assert again["written"] == 0 and again["unchanged"] == 3 and sent == []
    assert task.pending(plan, task.load_cache(data_dir), task.schema()) == []


def test_removed_value_is_unset_and_limit_holds(data_dir: Path) -> None:
    store = {"min1": {"jason_topics": "parking"}}
    sent: list[dict] = []
    drive = _mock(store, sent)
    plan = task.plan(data_dir)
    result = task.apply(drive, plan, yes=True, only="min1")
    assert result["written"] == 1 and sent[0]["appProperties"]["jason_topics"] is None
    sent.clear()
    assert task.apply(drive, plan, yes=True, limit=1)["written"] == 1 and len(sent) == 1


def test_search_query_and_show(data_dir: Path) -> None:
    assert query("jason_kind", "o'brien") == "appProperties has { key='jason_kind' and value='o\\'brien' } and trashed = false"
    store = {"doc1": {"jason_kind": "proposal"}}
    hits = search_properties(_mock(store, []), "jason_kind", "proposal")
    assert [h["id"] for h in hits] == ["doc1"]
    shown = task.show(task.plan(data_dir), "doc1", {"other": "1", "jason_kind": "proposal"}, task.schema())
    assert shown["notOwned"] == ["other"] and "jason_kind" not in shown["changes"]
