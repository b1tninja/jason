"""The unit record, the loss packet, and the paint schedule: who may read them and whose name they are written in."""

from __future__ import annotations

import pytest

import webclient


@pytest.fixture
def app(tmp_path, monkeypatch):
    from jason.web.app import create_app
    from jason.web.extra import paint, unit_records

    monkeypatch.setattr("jason.mcp.county._data_dir", lambda d: tmp_path)
    dist = tmp_path / "dist"
    dist.mkdir()
    loaders = {"unit-record": unit_records.unit_record, "loss-packet": unit_records.loss_packet,
               "paint": paint.paint_view, "paint-color": paint.paint_color}
    return create_app(dist, loaders, approvals_live=None, extra_writes=True, sign_in=webclient.roster_sign_in(dev=True))


READS = ("/api/unit-record?unit=7", "/api/loss-packet?unit=7")


@pytest.mark.parametrize("url", READS)
def test_a_unit_s_record_needs_a_sign_in_and_an_office_that_opens_p2(app, url):
    assert webclient.client(app).get(url).status_code == 401
    assert webclient.sign_in(webclient.client(app), "Ada Admin").get(url).status_code == 403     # a roster person with no office
    for name in ("A Manager", "Dana Director", "Sam Secretary", "Pat Example"):
        assert webclient.sign_in(webclient.client(app), name).get(url).status_code == 200, name


@pytest.mark.parametrize("url", READS + ("/api/paint", "/api/paint/color?code=SW0000"))
def test_the_owner_view_reads_none_of_them(app, url):
    joiner = "&" if "?" in url else "?"
    r = webclient.sign_in(webclient.client(app), "A Manager").get(url + joiner + "view=owner")
    assert r.status_code == 403


def test_the_paint_schedule_needs_a_sign_in_but_no_office(app):
    assert webclient.client(app).get("/api/paint").status_code == 401
    assert webclient.sign_in(webclient.client(app), "Ada Admin").get("/api/paint").status_code == 200


def test_a_loss_packet_confirmation_is_in_the_signers_name_and_a_body_by_is_not_trusted(app, tmp_path):
    body = {"unit": "7", "incident": "inc-1", "step": 1, "shows": ["the faucet is an upgrade"]}
    url = "/api/write/loss-packet/confirm"
    assert webclient.client(app).post(url, json=body).status_code in (401, 403)                    # signed out
    c = webclient.sign_in(webclient.client(app), "Ada Admin")
    assert c.post(url, json=body).status_code == 403                                               # no office: not P2
    c = webclient.sign_in(webclient.client(app), "Dana Director")
    assert c.post(url, json={**body, "by": "Somebody Else"}).status_code == 403
    r = c.post(url, json=body)
    assert r.status_code == 200 and r.json["confirmed_by"] == "Dana Director"


def test_a_unit_entry_is_in_the_signers_name_and_refused_without_p2(app):
    url = "/api/write/unit-record/entry"
    body = {"unit": "7", "component": "kitchen", "kind": "upgrade", "what": "new faucet"}
    assert webclient.sign_in(webclient.client(app), "Ada Admin").post(url, json=body).status_code == 403
    r = webclient.sign_in(webclient.client(app), "A Manager").post(url, json=body)
    assert r.status_code in (200, 400), r.json                     # 400: the entry's own validation, not the gate
    assert r.status_code != 403


def test_they_are_registered_and_no_owner_source():
    from jason.web.extra.owner_view import OWNER_SOURCES

    for name in ("unit-record", "loss-packet", "paint", "paint-color"):
        assert name not in OWNER_SOURCES


def test_the_paint_files_are_the_associations_own():
    from pathlib import Path

    from jason.web.access import Level, level_of_path

    assert level_of_path("paint/catalog.json", Path(".")) is Level.P0
