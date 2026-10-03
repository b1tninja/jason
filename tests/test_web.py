from jason.web.app import create_app


def _client(tmp_path, loaders=None, built=True):
    if built:
        (tmp_path / "assets").mkdir()
        (tmp_path / "index.html").write_text("<div id=root></div>")
        (tmp_path / "assets" / "a.js").write_text("1")
    return create_app(tmp_path, loaders or {"demo": lambda a: {"n": a.get("n", "0")}}).test_client()


def test_health_and_api(tmp_path):
    c = _client(tmp_path)
    assert c.get("/api/health").json == {"ok": True, "ui": True, "sources": ["demo"], "writes": ["board-items", "canvases", "decisions", "onboarding", "owner-info"]}
    assert c.get("/api/demo?n=3").json == {"n": "3"}
    assert c.get("/api/nope").status_code == 404


def test_loader_errors_are_json(tmp_path):
    def boom(a):
        raise RuntimeError("no store")

    c = _client(tmp_path, {"boom": boom})
    r = c.get("/api/boom")
    assert r.status_code == 500 and "no store" in r.json["error"]


def test_spa_fallback_and_assets(tmp_path):
    c = _client(tmp_path)
    assert b"root" in c.get("/").data
    assert b"root" in c.get("/some/client/route").data
    assert c.get("/assets/a.js").headers["Cache-Control"].startswith("public")
    assert c.get("/api/x/y").status_code == 404
    assert c.get("/..%2f..%2fpyproject.toml").status_code in (200, 404)


def test_unbuilt_is_503(tmp_path):
    assert _client(tmp_path, built=False).get("/").status_code == 503


def test_board_item_write_is_board_fields_only(tmp_path):
    seen = {}

    def writer(item_id, changes):
        if item_id == "missing":
            raise KeyError(item_id)
        if set(changes) - {"status", "owner", "meeting", "notes"}:
            raise ValueError("jason's")
        seen.update(changes)
        return {"id": item_id, **changes}

    c = create_app(tmp_path, {}, board_writer=writer).test_client()
    assert c.post("/api/board-items/x", json={"status": "on agenda", "owner": "A"}).json == {"id": "x", "status": "on agenda", "owner": "A"}
    assert c.post("/api/board-items/x", json={"title": "no"}).status_code == 400
    assert c.post("/api/board-items/missing", json={"notes": "n"}).status_code == 404
    assert c.get("/api/health").json["writes"] == ["board-items", "canvases", "decisions", "onboarding", "owner-info"]
    off = create_app(tmp_path, {}, board_writer=None, canvas_writer=None, decision_writer=None, request_writer=None, owner_info_writer=None).test_client()
    assert off.post("/api/board-items/x", json={"notes": "n"}).status_code == 405
    assert off.get("/api/health").json["writes"] == []


def test_leads_tolerates_missing_stores(monkeypatch):
    from jason.web import sources

    monkeypatch.setattr(sources, "library_status", lambda a: {"unclassified": ["a.pdf"]})
    monkeypatch.setattr(sources, "records_inventory", lambda a: {"records": [{"record": "minutes", "gap": "nothing pinned", "citation": "CIV 5200"}]})
    monkeypatch.setattr(sources, "document_readings", lambda a: (_ for _ in ()).throw(FileNotFoundError("no folder")))
    monkeypatch.setattr(sources, "association_records", lambda a: {"deliveries": [{"delivery": "map", "missing": ["sheet 2"]}], "unplaced": []})
    out = sources.leads({})
    assert out["count"] == 3 and out["counts"] == {"unclassified file": 1, "records gap": 1, "delivery missing": 1}
    assert out["notes"] and "document_readings" in out["notes"][0]
    assert out["caveats"]


def test_set_board_item_refuses_jason_fields():
    import pytest

    from jason.web.sources import set_board_item

    with pytest.raises(ValueError):
        set_board_item("x", {"title": "mine"})
    with pytest.raises(ValueError):
        set_board_item("x", {})


def test_duties_list_needs_no_store():
    from jason.web.sources import duties

    out = duties({})
    assert out["found"] and out["count"] >= 10
    first = out["duties"][0]
    assert {"anchor", "keepsStraight", "sections", "cadence", "records", "produce"} <= set(first)
    assert all(isinstance(d["records"], list) for d in out["duties"])
