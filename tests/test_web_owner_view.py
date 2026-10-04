"""The owner view's server guard (docs/console/security-and-privacy.md, the owner view; ``jason.web.extra.owner_view``).

Each screen the owner nav shows (``ui/src/ownerScreens.json``, which the console's own test checks against its screen
list) reads its sources as the owner view does, ``?view=owner``, from a made-up data folder and made-up board loaders
that hold a delinquent owner, a lien, a hearing, and an executive item. None of them may come back. A board source asked
for in the owner view is refused, and the board's records screen holds the liens back outside the private view.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from jason.web.app import create_app

OWNED = json.loads((Path(__file__).resolve().parents[1] / "ui" / "src" / "ownerScreens.json").read_text(encoding="utf-8"))

# Made-up board-only facts.
OWNER = "Pat Delinquent"
UNIT = "Unit 99"
LIEN = "2099-0000777"
HEARING = "Hearing on the fine for Unit 99"
EXEC = "Executive: collections strategy for Pat Delinquent"
POISON = (OWNER, UNIT, LIEN, HEARING, EXEC)

LIFECYCLE = {"process": "assessment lien", "status": "recorded", "opened": "2099-01-02", "closed": "", "debtor": [OWNER],
             "claimant": ["The Association"], "steps": [{"number": LIEN, "recorded": "2099-01-02", "filing": "LIEN", "effect": "opens"}]}
BOARD = {"found": True, "ownersInDefault": [{"owner": OWNER, "unit": UNIT, "pastDueCents": 123_456}], "liens": [LIFECYCLE],
         "placed": [LIFECYCLE], "hearings": [{"address": UNIT, "statement": HEARING}], "executive": [{"title": EXEC}]}


def _record(kind: str, where: str, name: str, ref: str = "", *, confidential: bool = False, day: str = "") -> dict:
    return {"kind": kind, "where": where, "name": name, "location": name, "ref": ref, "date": day, "confidential": confidential, "note": ""}


def _catalog(root: Path) -> None:
    meetings = [
        {"date": "2099-08-01", "titles": [HEARING], "has": {"transcript": {"Zoom cloud": 1}}, "checks": [EXEC],
         "records": [_record("transcript", "Zoom cloud", f"{HEARING} (transcript)", "zoom-1", confidential=True)]},
        {"date": "2099-09-15", "titles": ["Board meeting", HEARING], "has": {"minutes": {"PayHOA library": 1}}, "checks": [f"executive session: {EXEC}"],
         "records": [_record("minutes", "PayHOA library", "2099-09-15 minutes.pdf", "901"),
                     _record("executive session agenda", "PayHOA library", f"{EXEC}.pdf", "902", confidential=True),
                     _record("transcript", "Zoom cloud", f"{OWNER} transcript", "zoom-2", confidential=True),
                     _record("minutes", "Gmail", f"Re: lien {LIEN}", "msg-1")]},
        {"date": "2099-10-21", "titles": ["Board meeting"], "has": {"agenda": {"Drive": 1, "jason draft": 1}}, "checks": [],
         "records": [_record("agenda", "Drive", "2099-10-21 agenda", "1FakeAgendaDoc"),
                     _record("agenda", "jason draft", f"agenda-2099-10-21 {EXEC}.md")]},
    ]
    (root / "meetings").mkdir(parents=True)
    (root / "meetings" / "catalog.json").write_text(json.dumps({"builtAt": "2099-10-01", "meetings": meetings, "count": 3,
                                                                "scheduleGaps": ["2099-07-20"], "unplaced": [], "caveats": []}), encoding="utf-8")


def _room() -> dict:
    """The meeting room loader's answer, as the board sees it: an executive item, the owner roster, the log."""
    def item(id_, kind, title, **more):
        return {"id": id_, "kind": kind, "label": title, "title": title, "facts": [], "motion": "", "threshold": "majority", "recused": [],
                "allot": 1, "packet": [], "brief": None, "session": "open session", **more}

    return {"found": True, "date": "2099-10-21", "today": "2099-10-01", "directors": ["D. One", "D. Two", "D. Three"], "quorum": 2,
            "items": [item("call", "call", "Call to order"), item("pool", "action", "Resurface the pool deck", facts=["Two bids"], motion="Move to approve bid A."),
                      item("exec", "exec", EXEC, facts=[HEARING], matters=[EXEC], motion=f"Move to adjourn to discuss {EXEC}",
                           packet=[{"id": "p", "name": f"{OWNER} ledger.pdf"}], brief={"question": LIEN}),
                      item("adjourn", "adjourn", "Adjourn")],
            "room": {"date": "2099-10-21", "directors": ["D. One", "D. Two", "D. Three"], "current": 1, "presenter": "jason", "view": "shared", "mode": "co-host",
                     "attendance": {"D. One": "present", "D. Two": "present"}, "calledToOrder": "", "openForum": {"count": 0, "limitMinutes": 3},
                     "motions": [{"id": "m1", "itemId": "pool", "title": "Pool", "text": "Move to approve bid A.", "mover": "D. One", "second": "D. Two", "recused": [],
                                  "threshold": "majority", "votes": {}, "result": "", "decidedAt": "", "movedAt": "", "tally": {}},
                                 {"id": "m2", "itemId": "exec", "title": "Lien", "text": f"Move to record lien {LIEN} against {OWNER}", "mover": "D. One",
                                  "second": "D. Two", "recused": [], "threshold": "majority", "votes": {}, "result": "", "decidedAt": "", "movedAt": "", "tally": {}}],
                     "log": [{"at": "", "title": f"Discussed {EXEC}", "tone": "warn"}], "executive": {"active": True, "startedAt": "x", "endedAt": "", "note": EXEC},
                     "polls": [{"question": HEARING}], "admitted": [OWNER], "transcriptSuggestions": [{"text": OWNER}], "adjournedAt": "",
                     "present": ["D. One", "D. Two"], "quorum": 2, "history": [EXEC]},
            "decisions": [{"title": EXEC}], "plan": {"found": True, "count": 3}, "roster": {"synced": "x", "count": 1, "rows": [{"name": OWNER, "unit": UNIT}], "note": ""},
            "offAgendaPaths": [], "zoom": {"commands": {"caption": EXEC}}, "commands": {"x": OWNER}, "minutesKey": "minutes/2099-10-21",
            "notes": [HEARING], "caveats": ["board caveat"]}


def _insurance() -> dict:
    return {"found": True, "asOf": "2099-10-01", "policies": [
        {"kind": "master", "building": None, "number": LIEN, "priorNumbers": [], "carrier": "Example Carrier", "program": "", "agent": OWNER,
         "standing": f"renewal notice to {OWNER}", "termEnd": "2100-01-01", "terms": [{"start": "2099-01-01", "end": "2100-01-01", "paidCents": 99}],
         "findings": [HEARING], "nextTermPayments": [{"date": "2099-12-01", "amountCents": 5}], "letters": [{"text": OWNER}], "notices": [{"kind": HEARING}],
         "email": [{"subject": EXEC}]}],
        "claims": [{"claimNumber": LIEN, "dateOfLoss": OWNER}], "unplacedFloodPayments": [], "caveats": []}


@pytest.fixture
def owner_app(tmp_path, monkeypatch):
    """jason-web over a made-up data folder, with the board's loaders answering the made-up facts."""
    from jason.tasks import records_requests as requests
    from jason.web.sources import default_loaders

    root = tmp_path / "data"
    root.mkdir()
    _catalog(root)
    requests.open_request(root, "2099-09-20", UNIT, "email", ["minutes", "membership_list"], purpose=f"{OWNER} wants the list", by=OWNER)
    monkeypatch.setattr("jason.mcp.county._data_dir", lambda d: Path(d) if d is not None else root)
    board = {name: (lambda a, _n=name: dict(BOARD, source=_n)) for name in (
        "board-digest", "hearings", "delinquency", "association-records", "approvals", "dock", "library", "embeds", "collections",
        "decisions", "meeting", "budget", "legal-cases", "title-watch", "open-items")}
    loaders = {**default_loaders(), **board, "meeting-room": lambda a: _room(), "insurance": lambda a: _insurance()}
    dist = tmp_path / "dist"
    dist.mkdir()
    return create_app(dist, loaders, extra_writes=False, approvals_live=None).test_client()


def _clean(body: str, where: str) -> None:
    for p in POISON:
        assert p not in body, f"{where} sent {p!r}"


def test_the_owner_sources_are_the_owner_screens_sources():
    from jason.web.extra.owner_view import OWNER_SOURCES

    named = {s for sources in OWNED["screens"].values() for s in sources} | set(OWNED["shell"])
    assert set(OWNER_SOURCES) == named


@pytest.mark.parametrize("screen,source", [(screen, s) for screen, sources in OWNED["screens"].items() for s in sources]
                         + [("shell", s) for s in OWNED["shell"]])
def test_each_owner_screen_reads_nothing_of_the_board(owner_app, screen, source):
    r = owner_app.get(f"/api/{source}?view=owner&today=2099-10-01")
    assert r.status_code == 200, (screen, source, r.json)
    assert r.headers["Cache-Control"] == "no-store"
    _clean(r.get_data(as_text=True), f"{screen} ({source})")


def test_one_meeting_as_the_owner_view_reads_it(owner_app):
    listed = owner_app.get("/api/meetings?view=owner").json
    assert [m["date"] for m in listed["meetings"]] == ["2099-10-21", "2099-09-15"]          # the hearing-only call is not one
    sept = next(m for m in listed["meetings"] if m["date"] == "2099-09-15")
    assert sept["has"] == {"minutes": {"PayHOA library": 1}} and sept["titles"] == [] and sept["checks"] == []
    assert listed["scheduleGaps"] == []
    for day in ("2099-09-15", "2099-08-01", "2099-10-21"):
        r = owner_app.get(f"/api/meetings?date={day}&view=owner")
        assert r.status_code == 200
        _clean(r.get_data(as_text=True), f"meetings {day}")
    assert owner_app.get("/api/meetings?date=2099-08-01&view=owner").json["found"] is False


def test_the_owner_digest(owner_app):
    for url in ("/api/owner-digest?today=2099-10-01", "/api/owner-digest?view=owner&today=2099-10-01"):
        d = owner_app.get(url).json
        assert d["found"] is True
        assert d["nextMeeting"]["date"] <= "2099-10-21"
        assert d["latestMinutes"]["date"] == "2099-09-15"
        assert {r["key"] for r in d["disclosures"]} >= {"annual-budget-report", "annual-policy-statement"}
        assert d["policies"]["adopted"] == [] and d["policies"]["note"]
        assert d["recordsRequest"]["screen"] == "records-requests" and d["recordsRequest"]["clocks"]
        _clean(json.dumps(d), url)


def test_the_records_screen_sends_no_members_request(owner_app):
    d = owner_app.get("/api/records-requests?view=owner").json
    assert d["requests"] == [] and d["count"] == 0 and d["kinds"]
    assert all(set(k) == {"record", "label", "citation", "meaning", "retention"} for k in d["kinds"])   # no shelf counts
    board = owner_app.get("/api/records-requests").json                                                    # the board's view
    assert board["requests"][0]["unit"] == UNIT


def test_the_meeting_room_stage_alone(owner_app):
    d = owner_app.get("/api/meeting-room?view=owner").json
    assert [i["id"] for i in d["items"]] == ["call", "pool", "exec", "adjourn"]
    ex = d["items"][2]
    assert ex["title"] == "Executive session" and ex["matters"] == [] and ex["facts"] == [] and ex["packet"] == [] and ex["brief"] is None
    assert [m["id"] for m in d["room"]["motions"]] == ["m1"]                                   # the open item's motion only
    assert d["room"]["log"] == [] and d["room"]["admitted"] == [] and d["room"]["polls"] == [] and d["room"]["executive"]["note"] == ""
    assert d["roster"]["rows"] == [] and d["decisions"] == [] and d["commands"] == {} and d["zoom"]["commands"] == {}
    assert d["room"]["current"] == 1 and d["room"]["present"] == ["D. One", "D. Two"]


def test_the_insurance_summary(owner_app):
    d = owner_app.get("/api/insurance?view=owner").json
    (p,) = d["policies"]
    assert set(p) == {"kind", "building", "carrier", "termEnd", "terms", "deductibleCents"}
    assert p["carrier"] == "Example Carrier" and p["terms"] == [{"start": "2099-01-01", "end": "2100-01-01"}]
    assert d["claims"] == []


@pytest.mark.parametrize("source", ["board-digest", "hearings", "delinquency", "association-records", "approvals", "dock", "library",
                                    "embeds", "collections", "decisions", "meeting", "budget", "legal-cases"])
def test_a_board_source_is_refused_in_the_owner_view(owner_app, source):
    r = owner_app.get(f"/api/{source}?view=owner")
    assert r.status_code == 403 and r.json["ownerView"] is True
    _clean(r.get_data(as_text=True), source)
    assert OWNER in owner_app.get(f"/api/{source}").get_data(as_text=True)     # the board's view, for contrast


def test_a_confidential_listing_and_other_reads_are_refused_too(owner_app):
    assert owner_app.get("/api/library?view=owner&confidential=1").status_code == 403
    assert owner_app.get("/api/evidence?view=owner&address=library:1").status_code == 403
    assert owner_app.get("/api/approvals/anything?view=owner").status_code == 403
    assert owner_app.get("/api/session?view=owner").status_code == 200


def test_the_records_screen_holds_the_liens_back_outside_the_private_view(monkeypatch):
    import jason.mcp.county as county
    from jason.web import access, sources

    monkeypatch.setattr(county, "association_records", lambda: {"found": True, "placed": [LIFECYCLE], "against": [], "governing": []})
    held = sources.association_records({})
    assert held["placed"] == [] and held["placedHeld"] == 1 and held["placedNote"]
    _clean(json.dumps(held), "association-records")
    monkeypatch.setattr(access, "private_open", lambda viewer=None: True)
    assert sources.association_records({})["placed"] == [LIFECYCLE]
