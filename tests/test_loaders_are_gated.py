"""Every read the web app serves is gated by its own loader (``jason.web.app.source`` only calls it), so a loader that
forgets is open to anyone who can reach the port. This test calls each loader in ``jason.web.sources.default_loaders()``
through the Flask test client four ways, with a made-up roster and an empty data folder:

- signed out;
- a roster person with no office and no admin ("Rae Roster");
- an administrator with no office ("Ada Admin");
- a manager (an office that opens P2, not an admin).

Which of them are refused (401 or 403) says the gate the loader enforces:

- ``p2``: signed out 401, no office 403, the administrator with no office 403, the manager reads (member data: names,
  units, balances, mail, requests).
- ``p0``: signed out 401, any roster person reads (the association's own data, not a member's).
- ``admin``: signed out 401, the manager 403, the administrator reads (jobs, status, the instance).
- ``p2+admin``: signed out 401, no office 403, the manager and the administrator read.
- ``open``: signed out reads. Each is classified in ``tests/fixtures/loader_gates.json`` with a one-line reason.

Where console sign-in is not set up, a gate of ``jason.web.gates`` lets the read through (the loopback default;
``test_where_sign_in_is_not_set_up_a_gated_loader_answers_as_it_did``).

A loader missing from the file fails, so a NEW ungated loader is classified by someone before it ships; so does a loader
whose observed gate differs from the one the file says (a gate dropped, or one added and not recorded). The file also
names which loaders the owner view (``OWNER_SOURCES``) answers, since those are public to the owner by design.

To list what the loaders do now: ``JASON_GATES_DUMP=out.json pytest tests/test_loaders_are_gated.py -k dump``.
"""

from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest

import webclient

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "loader_gates.json"
GATES = ("open", "p0", "p2", "admin", "p2+admin")
ROWS = webclient.ROSTER + (("Rae Roster", "", "rae@example.org", False),)

# What a loader needs before it will answer anything but a 400 or a 500 (a date, a key): a gate that sits after the
# argument check would otherwise be hidden by it.
ARGS = {
    "agenda-plan": "date=2026-10-20", "meeting": "date=2026-10-20", "meeting-room": "date=2026-10-20",
    "record-slot": "key=records/5200/minutes", "record-bindings": "key=records/5200/minutes",
    "bill-investigation": "tx=1", "unit-record": "unit=7", "loss-packet": "unit=7", "split-session": "id=x",
    "paint-color": "code=SW0000", "response": "id=gmail:1",
}


def _refused(r) -> bool:
    return r.status_code in (401, 403)


def observe(tmp_path, monkeypatch) -> dict[str, dict[str, int]]:
    """loader -> the status each of the four viewers got."""
    from jason.web.app import create_app
    from jason.web.sources import default_loaders

    monkeypatch.setattr("jason.mcp.county._data_dir", lambda d=None: tmp_path)
    monkeypatch.setenv("JASON_DATA_DIR", str(tmp_path))

    def no_network(*a, **kw):
        raise OSError("a loader reached the network in the gate test")

    monkeypatch.setattr(socket, "create_connection", no_network)
    dist = tmp_path / "dist"
    dist.mkdir(exist_ok=True)
    app = create_app(dist, default_loaders(), approvals_live=None, extra_writes=False,
                     sign_in=webclient.roster_sign_in(ROWS))
    viewers = {"out": None, "roster": "Rae Roster", "admin": "Ada Admin", "manager": "A Manager"}
    seen: dict[str, dict[str, int]] = {}
    for name in sorted(default_loaders()):
        seen[name] = {}
        for who, person in viewers.items():
            c = webclient.client(app)
            if person:
                webclient.sign_in(c, person, rows=ROWS)
            seen[name][who] = c.get(f"/api/{name}?{ARGS.get(name, '')}").status_code
    return seen


def gate_of(got: dict[str, int]) -> str:
    out, roster, admin, manager = (got[k] in (401, 403) for k in ("out", "roster", "admin", "manager"))
    if not out:
        return "open"
    if not (roster or admin or manager):
        return "p0"
    if roster and admin and not manager:
        return "p2"
    if roster and not admin and manager:
        return "admin"
    if roster and not admin and not manager:
        return "p2+admin"
    return f"odd:{got}"


@pytest.fixture(scope="module")
def observed(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    try:
        return observe(tmp_path_factory.mktemp("gates"), mp)
    finally:
        mp.undo()


def _baseline() -> dict[str, dict[str, str]]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["loaders"]


def test_every_loader_is_classified_and_gated_as_classified(observed):
    baseline = _baseline()
    new = sorted(set(observed) - set(baseline))
    gone = sorted(set(baseline) - set(observed))
    assert not new, ("these loaders are not in tests/fixtures/loader_gates.json; gate each (jason.web.access: "
                     f"signed_in(), allow(viewer, Level.P2)) or classify it with a reason: {new}")
    assert not gone, f"these are no longer loaders; remove them from tests/fixtures/loader_gates.json: {gone}"
    differ = {n: (baseline[n]["gate"], gate_of(observed[n]), observed[n]) for n in observed
              if gate_of(observed[n]) != baseline[n]["gate"]}
    assert not differ, f"loader: (recorded gate, observed gate, statuses out/roster/admin/manager): {differ}"


def test_the_baseline_is_well_formed(observed):
    for name, row in _baseline().items():
        assert row["gate"] in GATES, name
        assert row.get("why", "").strip(), f"{name}: say in one line why it is {row['gate']}"


def test_an_open_loader_is_not_one_that_serves_member_data(observed):
    """The words in an open loader's reason are not an excuse: a loader recorded open never names members' data."""
    for name, row in _baseline().items():
        if row["gate"] == "open":
            assert not any(w in row["why"].lower() for w in ("owner names", "balances", "addresses", "mail", "logs")), name


def _app(tmp_path, monkeypatch, *, configured: bool):
    from jason.web.app import create_app
    from jason.web.sources import default_loaders

    monkeypatch.setattr("jason.mcp.county._data_dir", lambda d=None: tmp_path)
    dist = tmp_path / "dist"
    dist.mkdir(exist_ok=True)
    return create_app(dist, default_loaders(), approvals_live=None, extra_writes=False,
                      sign_in=webclient.roster_sign_in(ROWS, configured=configured))


@pytest.mark.parametrize("name", ("delinquency", "collections", "jobs", "board-items", "budget"))
def test_where_sign_in_is_not_set_up_a_gated_loader_answers_as_it_did(tmp_path, monkeypatch, name):
    """The loopback default has no Google client and no one to sign in: the console works as it always has there."""
    app = _app(tmp_path, monkeypatch, configured=False)
    assert webclient.client(app).get(f"/api/{name}").status_code == 200


def _owner_sources():
    from jason.web.extra.owner_view import OWNER_SOURCES

    return sorted(OWNER_SOURCES)


@pytest.mark.parametrize("name", _owner_sources())
def test_the_owner_view_still_reads_what_it_reads_with_sign_in_set_up(tmp_path, monkeypatch, name):
    """The owner view is a view, not a sign-in (``OWNER_SOURCES``): its loaders call the board's, which pass for it."""
    app = _app(tmp_path, monkeypatch, configured=True)
    r = webclient.client(app).get(f"/api/{name}?view=owner&{ARGS.get(name, '')}")
    assert r.status_code not in (401, 403), (name, r.status_code, r.get_data(as_text=True)[:200])


def test_the_owner_view_does_not_open_the_boards_loader_of_the_same_name(tmp_path, monkeypatch):
    """``?view=owner`` is answered by the owner loader; the board's answer to the same name needs the sign-in."""
    app = _app(tmp_path, monkeypatch, configured=True)
    c = webclient.client(app)
    assert c.get("/api/records-requests").status_code == 401
    assert c.get("/api/insurance").status_code == 401
    assert c.get("/api/meeting-room?date=2026-10-20").status_code == 401


def test_a_gated_loader_called_outside_a_request_is_not_checked(tmp_path, monkeypatch):
    """A script or the Python API is the person at the terminal."""
    from jason.web.sources import default_loaders

    monkeypatch.setattr("jason.mcp.county._data_dir", lambda d=None: tmp_path)
    assert default_loaders()["collections"]({}) is not None


def test_every_name_in_the_table_is_a_loader():
    from jason.web import gates
    from jason.web.sources import default_loaders

    assert not sorted(set(gates.GATES) - set(default_loaders())), "gates.GATES names a source that is not a loader"


def test_dump_the_observed_gates(observed, tmp_path):
    """``JASON_GATES_DUMP=path pytest tests/test_loaders_are_gated.py -k dump`` writes what each loader does now."""
    import os

    target = os.environ.get("JASON_GATES_DUMP")
    if not target:
        pytest.skip("set JASON_GATES_DUMP to a file to write the observed gates")
    Path(target).write_text(json.dumps({n: {"gate": gate_of(g), "statuses": g} for n, g in observed.items()}, indent=1), encoding="utf-8")
