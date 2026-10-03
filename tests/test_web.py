from jason.web.app import create_app


def _client(tmp_path, loaders=None, built=True):
    if built:
        (tmp_path / "assets").mkdir()
        (tmp_path / "index.html").write_text("<div id=root></div>")
        (tmp_path / "assets" / "a.js").write_text("1")
    return create_app(tmp_path, loaders or {"demo": lambda a: {"n": a.get("n", "0")}}).test_client()


def test_health_and_api(tmp_path):
    c = _client(tmp_path)
    assert c.get("/api/health").json == {"ok": True, "ui": True, "sources": ["demo"]}
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
