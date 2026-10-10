"""The splitter's page pictures (docs/pdf-splitter.md, section 3): one page at a time, kept by content, bounded, and served with an
ETag. Made-up PDFs only; no service."""

import pytest

import webclient
from jason import limits
from jason.community import split_gold
from jason.tasks import record_slots as rs
from jason.tasks import split_session as ss
from jason.tasks import split_thumbs as th

BY = "Jane Example"


@pytest.fixture
def world(tmp_path, monkeypatch):
    root = tmp_path / "data"
    root.mkdir()
    monkeypatch.setattr("jason.mcp.county._data_dir", lambda given=None: root)
    monkeypatch.setattr(rs, "_profile", lambda profile, community=None: profile or "example")
    pdf = tmp_path / "scan.pdf"
    pdf.write_bytes(split_gold.numbered().pdf)
    return type("W", (), {"root": root, "tmp": tmp_path, "pdf": pdf})()


def opened(world, **kw):
    return ss.open_session({"kind": "path", "path": str(world.pdf)}, by=BY, root=world.root, **kw)["session"]


def test_a_page_is_drawn_at_each_size_with_its_longest_side_and_nothing_else_of_the_file(world):
    assert th.renderer_name() in ("pypdfium2", "pymupdf")
    for size in th.SIZES:
        got = th.render_page(world.pdf, 2, size)
        assert max(got.width, got.height) == size and got.mime in ("image/webp", "image/jpeg") and 200 < len(got.data) < 300_000
    assert th.size_of("tiny") == 96 and th.size_of("800") == 800
    with pytest.raises(ValueError, match="96, 200, 800"):
        th.size_of(1600)
    with pytest.raises(th.PageUnreadable):
        th.render_page(world.pdf, 99, 96)
    turned = th.render_page(world.pdf, 2, 200, rotate=90)
    assert turned.width > turned.height                                                # the picture turns (a portrait page, turned 90), never the PDF


def test_no_renderer_is_a_state_with_words_not_a_crash(world, monkeypatch):
    def gone(*a, **kw):
        raise ImportError("no renderer")

    monkeypatch.setattr(th, "_draw_pypdfium2", gone)
    monkeypatch.setattr(th, "_draw_pymupdf", gone)
    with pytest.raises(th.RendererUnavailable, match="No page renderer is installed"):
        th.render_page(world.pdf, 1, 96)
    with pytest.raises(th.RendererUnavailable):
        th.render_page(world.pdf, 1, 96, engine="pypdfium2")


def test_importing_the_module_loads_no_renderer():
    import subprocess
    import sys

    code = "import sys; import jason.tasks.split_thumbs; print([m for m in ('pypdfium2', 'pymupdf', 'fitz') if m in sys.modules])"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env={**__import__('os').environ, "PYTHONPATH": "src"})
    assert out.stdout.strip() == "[]", out.stderr


def test_the_cache_is_addressed_by_hash_page_and_size_and_reuses_the_same_bytes(world):
    s = opened(world)
    sha = s["source"]["sha256"]
    copy = ss.source_file(world.root, sha)
    first = th.get(world.root, copy, sha, 3, 200)
    assert first["cached"] is False and first["kept"] is True and first["etag"] == th.etag(sha, 3, 200)
    path = th.path_of(world.root, sha, 3, 200)
    assert path.is_file() and path.relative_to(world.root).parts[:3] == ("split", "thumbs", sha[:2]) and "scan" not in str(path)
    again = th.get(world.root, copy, sha, 3, 200)
    assert again["cached"] is True and again["data"] == first["data"]
    other = th.get(world.root, copy, sha, 3, 96)                               # another size is another picture
    assert other["cached"] is False and th.path_of(world.root, sha, 3, 96).is_file()
    # the same bytes opened again (even from another place) find the same pictures
    twin = world.tmp / "elsewhere.pdf"
    twin.write_bytes(world.pdf.read_bytes())
    s2 = ss.open_session({"kind": "path", "path": str(twin)}, by=BY, root=world.root)
    assert s2["resumed"] is True and s2["session"]["id"] == s["id"]
    assert '"%s-3-200-%s"' % (sha[:16], th.RENDER_VERSION) == th.etag(sha, 3, 200)


def test_the_bound_removes_the_oldest_pictures_first_and_never_the_page_just_drawn(world, monkeypatch):
    s = opened(world)
    sha = s["source"]["sha256"]
    copy = ss.source_file(world.root, sha)
    sizes = [len(th.render_page(copy, n, 200).data) for n in (1, 2, 3, 4)]
    bound = sum(sizes[:3]) + 10                                                    # room for three of the four
    real = limits.value
    monkeypatch.setattr(limits, "value", lambda key, **kw: bound if key == "split.thumbnail_cache_bytes" else real(key, **kw))
    for n in (1, 2, 3):
        th.get(world.root, copy, sha, n, 200)
        import os, time

        os.utime(th.path_of(world.root, sha, n, 200), (time.time() - 100 + n, time.time() - 100 + n))   # 1 is the oldest
    th.get(world.root, copy, sha, 4, 200)
    held = {n for n in (1, 2, 3, 4) if th.path_of(world.root, sha, n, 200).is_file()}
    assert 4 in held and 1 not in held and th.usage(world.root) <= bound
    # a picture bigger than the whole allowance is refused in the registry's words
    monkeypatch.setattr(limits, "value", lambda key, **kw: 10 if key == "split.thumbnail_cache_bytes" else real(key, **kw))
    with pytest.raises(limits.LimitReached, match="using their whole allowance"):
        th.get(world.root, copy, sha, 5, 800)


def test_other_files_pictures_go_before_the_open_files_own(world, monkeypatch):
    import os

    a, b = "a1" * 32, "b2" * 32
    for sha, n in ((a, 1), (b, 1), (b, 2)):
        p = th.path_of(world.root, sha, n, 96)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x" * 1000)
    os.utime(th.path_of(world.root, b, 1, 96), (1, 1))                            # b's page 1 is the oldest of all
    os.utime(th.path_of(world.root, a, 1, 96), (5, 5))
    keep = th.path_of(world.root, b, 2, 96)
    freed = th._evict(world.root, 1000, keep, 2500, b)                             # 2 files of 1000 + the one kept = over 2500 by 500
    assert freed == 1000 and not th.path_of(world.root, a, 1, 96).is_file() and th.path_of(world.root, b, 1, 96).is_file() and keep.is_file()


def test_a_drive_short_of_room_serves_the_picture_once_and_keeps_nothing(world, monkeypatch):
    s = opened(world)
    sha = s["source"]["sha256"]
    monkeypatch.setattr("jason.storage.room_problem", lambda dest, need, **kw: "This file is 1 MB, but C: has 0 MB free.")
    got = th.get(world.root, ss.source_file(world.root, sha), sha, 2, 200)
    assert got["data"] and got["kept"] is False and "free" in got["note"]
    assert not th.path_of(world.root, sha, 2, 200).exists()


def test_purge_removes_the_pictures_of_one_file_and_never_the_copy(world):
    s = opened(world)
    sha = s["source"]["sha256"]
    th.get(world.root, ss.source_file(world.root, sha), sha, 1, 96)
    assert th.purge(world.root, sha) > 0 and not th.folder_of(world.root, sha).exists()
    assert ss.source_file(world.root, sha).is_file()


# --- the route ---------------------------------------------------------------------------------------------------------------------

def _app(world):
    from jason.web.app import create_app
    from jason.web.sources import default_loaders

    return create_app(world.tmp, default_loaders(), sign_in=webclient.roster_sign_in(required=False))


def test_the_route_serves_a_picture_with_an_etag_and_answers_304_to_the_same_tag(world):
    s = opened(world)
    c = webclient.client(_app(world))
    url = f"/api/split/thumb?id={s['id']}&page=2&size=200"
    assert c.get(url).status_code == 401                                          # signed out
    webclient.sign_in(c, "A Manager")
    r = c.get(url)
    assert r.status_code == 200 and r.mimetype in ("image/webp", "image/jpeg") and r.headers["ETag"] == th.etag(s["source"]["sha256"], 2, 200)
    assert r.headers["Cache-Control"] == "private, max-age=31536000, immutable" and r.headers["X-Content-Type-Options"] == "nosniff"
    again = c.get(url, headers={"If-None-Match": r.headers["ETag"]})
    assert again.status_code == 304 and again.data == b"" and again.headers["ETag"] == r.headers["ETag"]
    assert c.get(url.replace("size=200", "size=99")).status_code == 400
    assert c.get(url.replace("page=2", "page=99")).status_code == 400
    assert c.get(url.replace("page=2", "page=x")).status_code == 400
    assert c.get(f"/api/split/thumb?id=ffffffff&page=1&size=96").status_code == 404
    assert c.get(url + "&view=owner").status_code == 403                          # the owner view is refused


def test_a_picture_is_served_only_to_a_person_whose_offices_open_the_board_level(world):
    s = opened(world)
    c = webclient.client(_app(world))
    webclient.sign_in(c, "Pat Example")                                           # a treasurer opens P2
    assert c.get(f"/api/split/thumb?id={s['id']}&page=1&size=96").status_code == 200
    log = (world.root / "access" / "served.jsonl").read_text(encoding="utf-8")
    assert s["id"] in log and "scan" not in log and ".pdf" not in log             # the session and the page, never a name


def test_a_confidential_files_pictures_need_the_private_view_and_are_never_kept_by_the_browser(world, monkeypatch):
    import sqlite3

    from jason.tasks.library import SCHEMA

    (world.root / "library" / "files").mkdir(parents=True)
    (world.root / "library" / "files" / "Held.pdf").write_bytes(world.pdf.read_bytes())
    with sqlite3.connect(world.root / "library" / "library.db") as conn:
        conn.execute(SCHEMA)
        conn.execute("INSERT INTO documents (id, source, path, name, kind, category, records, method, period, confidential, evidence, sha256)"
                     " VALUES ('9001','payhoa','Held.pdf','Held.pdf','bank_statement','financial','enhanced','NAME','2099-06',1,'','')")
    s = ss.open_session({"kind": "library", "id": "9001"}, by=BY, root=world.root)["session"]
    assert s["source"]["confidential"] is True and s["source"]["ref"] == ""      # the reference is masked
    c = webclient.client(_app(world))
    webclient.sign_in(c, "A Manager")
    refused = c.get(f"/api/split/thumb?id={s['id']}&page=1&size=96")
    assert refused.status_code == 403 and "private view" in refused.json["error"]
    listing = c.get("/api/split-sessions").json["sessions"][0]
    assert listing["label"] == "a confidential file"
    assert "Held" not in c.get(f"/api/split-session?id={s['id']}").get_data(as_text=True)
