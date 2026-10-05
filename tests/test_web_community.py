"""The community record (``jason.web.extra.community_record``, ``GET /api/community``): each fact with its source, a fact
not on file said so and never filled in, the official email masked outside the private view, a signed-in roster person
only, and never the owner view. A made-up community and made-up people; nothing reaches Google, Keeper, or PayHOA.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import webclient

from jason.community.base import (BoardRule, MeetingSchedule, NoticePeriod, RuleSource, SpeakingLimit, VoteBasis)
from jason.community.identity import Identity
from jason.web.extra.community_record import ASK_COUNSEL, MASKED, NO_SOURCE, NOT_ON_FILE, community_of


class Sample:
    """A made-up association with every fact on file."""

    name = "Sample Commons Association"
    slug = "sample"

    def identity(self):
        return Identity("Sample Commons Association", corporate_name="SAMPLE COMMONS ASSOCIATION",
                        official_address="123 Main St, Anytown, CA 00000", official_email="board@example.org",
                        designated_recipient="Secretary, Sample Commons Association", website="https://example.org",
                        posting_location="The sample bulletin board.", signer="Board of Directors of the sample",
                        management="self-managed by its board", time_zone="Pacific", meeting_platform="Sample Meet")

    def board(self):
        return BoardRule(seats=5, minimum=3, maximum=7, quorum_floor=2, source="Bylaws 9.1", quorum_source="Bylaws 9.3",
                         vote_basis=VoteBasis.MAJORITY_PRESENT, vote_source=RuleSource(cite="Bylaws 9.4"),
                         interested_in_quorum=True,
                         interested_source=RuleSource(cite="Bylaws 9.5", counsel="Sample Counsel, 2099",
                                                      reading="A sample reading."))

    def board_notice_period(self):
        return NoticePeriod(days=7, source="Bylaws 9.6")

    def open_forum_limit(self):
        return SpeakingLimit(minutes=4, source="Sample Resolution 1")

    def fiscal_year_end(self):
        return (6, 30)

    def meeting_schedule(self):
        return MeetingSchedule(weekday=2, nth=2, time="6:30 pm", place="The sample clubhouse", regular_months=(1, 7),
                               annual_month=3, resolution="Sample Resolution 2", practice="every month")

    def units(self):
        return ("1", "2", "3")

    def site(self):
        return "https://example.org"

    def theme(self):
        return SimpleNamespace(wordmark="Sample Commons")


class Bare:
    """A made-up association with nothing on file but its name."""

    name = "Bare Association"
    slug = "bare"

    def identity(self):
        return Identity("Bare Association")

    def units(self):
        return ()


def _fields(node, path=""):
    """Every fact ``{value, source, onFile, note}`` in an answer, with its path."""
    if isinstance(node, dict):
        if {"value", "source", "onFile", "note"} <= set(node):
            yield path, node
            return
        for key, value in node.items():
            yield from _fields(value, f"{path}.{key}" if path else key)


FACTS = ("identity", "board", "noticePeriod", "openForum", "fiscalYearEnd", "meetingSchedule", "units", "site")


def test_each_fact_carries_its_source():
    out = community_of(Sample())
    facts = list(_fields({k: out[k] for k in FACTS}))
    assert len(facts) >= 25
    for path, f in facts:
        assert f["onFile"] is True, path
        assert f["source"], path
    assert out["notOnFile"] == []
    board = out["board"]
    assert board["seats"]["value"] == 5 and board["seats"]["source"] == "Bylaws 9.1"
    assert board["quorum"]["value"] == 3 and board["quorum"]["source"] == "Bylaws 9.3" and board["quorum"]["floor"] == 2
    assert board["voteBasis"]["source"] == "Bylaws 9.4" and board["voteBasis"]["key"] == "majority-present"
    # Counsel's reading is labeled as a reading, never as the provision's words.
    interested = board["interestedInQuorum"]
    assert interested["value"] is True and interested["isReading"] is True and interested["reading"] == "A sample reading."
    assert "a reading, not the provision's words" in interested["source"] and interested["cite"] == "Bylaws 9.5"
    # The documents' longer period governs (4920(b)(3)); it does not reach an executive-only meeting unless it says so.
    assert out["noticePeriod"]["meeting"] == {"value": 7, "source": "Bylaws 9.6; CIV 4920(b)(3)", "onFile": True, "note": ""}
    assert out["noticePeriod"]["executiveOnly"]["value"] == 2 and out["noticePeriod"]["executiveOnly"]["source"] == "CIV 4920(b)(2)"
    assert out["openForum"]["value"] == 4 and out["openForum"]["source"] == "Sample Resolution 1"
    assert out["fiscalYearEnd"]["value"] == {"month": 6, "day": 30} and out["fiscalYearEnd"]["label"] == "June 30"
    schedule = out["meetingSchedule"]
    assert schedule["place"]["value"] == "The sample clubhouse" and schedule["place"]["source"] == "Sample Resolution 2"
    assert schedule["cadence"]["value"] == "the second Wednesday at 6:30 pm, in January and July"
    assert schedule["annual"]["value"] == "the second Wednesday of March"
    assert out["units"]["value"] == 3 and out["site"]["value"] == "https://example.org"
    assert out["theme"] == {"href": "/api/theme", "source": "Community.theme()", "onFile": True,
                            "wordmark": "Sample Commons", "note": ""}
    ident = out["identity"]
    assert ident["signer"]["value"] == "Board of Directors of the sample" and "default" not in ident["signer"]
    assert ident["timeZone"]["source"] == "Community.identity().time_zone"


def test_missing_facts_say_not_on_file_and_nothing_is_filled_in():
    out = community_of(Bare())
    board = out["board"]
    assert board["seats"] == {"value": None, "source": "", "onFile": False, "note": NOT_ON_FILE}
    for key in ("quorum", "voteBasis", "interestedInQuorum"):
        assert board[key]["value"] is None and board[key]["note"] == ASK_COUNSEL
    # No 3-minute forum: none until the board adopts one.
    assert out["openForum"]["value"] is None and out["openForum"]["note"] == "No limit on record; the board sets it (CIV 4925(b))."
    # The statute's period, cited; the documents' own provision is not on file.
    assert out["noticePeriod"]["meeting"]["value"] == 4 and out["noticePeriod"]["meeting"]["source"] == "CIV 4920(a)"
    assert out["noticePeriod"]["provision"]["onFile"] is False
    assert out["noticePeriod"]["provision"]["note"].startswith(NOT_ON_FILE)
    for key in ("fiscalYearEnd", "units", "site"):
        assert out[key]["value"] is None and out[key]["note"] == NOT_ON_FILE
    assert all(f["value"] is None for f in out["meetingSchedule"].values())
    for key in ("postingLocation", "designatedRecipient", "timeZone", "meetingPlatform", "management", "officialEmail"):
        assert out["identity"][key]["onFile"] is False, key
    assert out["theme"]["onFile"] is False and out["theme"]["note"].startswith(NOT_ON_FILE)
    # The signer every template uses when the profile names none is said to be that, not the profile's.
    signer = out["identity"]["signer"]
    assert signer["default"] is True and "the profile names no other signer" in signer["source"]
    for path, f in _fields({k: out[k] for k in FACTS}):
        assert f["source"] or f["note"], path               # every fact says where it comes from, or that it is missing
    assert "board.quorum" in out["notOnFile"] and "openForum" in out["notOnFile"] and "units" in out["notOnFile"]
    assert "noticePeriod.meeting" not in out["notOnFile"]


def test_a_rule_with_no_source_asks_counsel():
    class Unsourced(Bare):
        def board(self):
            return BoardRule(seats=3, minimum=3, maximum=3, vote_basis=VoteBasis.MAJORITY_IN_OFFICE)

    board = community_of(Unsourced())["board"]
    assert board["seats"]["value"] == 3 and board["seats"]["source"] == "" and board["seats"]["note"] == NO_SOURCE
    assert board["quorum"]["value"] == 2 and board["quorum"]["source"] == "" and ASK_COUNSEL in board["quorum"]["note"]
    assert board["voteBasis"]["source"] == "" and board["voteBasis"]["note"] == NO_SOURCE
    assert board["interestedInQuorum"]["note"] == ASK_COUNSEL


def test_the_official_email_is_masked_unless_shown():
    out = community_of(Sample())
    assert out["identity"]["officialEmail"]["value"] == MASKED and out["emailsShown"] is False
    assert "board@example.org" not in json.dumps(out)
    shown = community_of(Sample(), unmask=True)
    assert shown["identity"]["officialEmail"]["value"] == "board@example.org" and shown["emailsShown"] is True


# --- the route -----------------------------------------------------------------------------------------------------------

@pytest.fixture
def app(tmp_path, monkeypatch):
    from jason.web.app import create_app
    from jason.web.extra.community_record import community_record

    root = tmp_path / "data"
    root.mkdir()
    monkeypatch.setattr("jason.mcp.county._data_dir", lambda d: Path(d) if d is not None else root)
    monkeypatch.setenv("JASON_ACCESS_DIR", str(tmp_path / "access"))
    monkeypatch.setattr("jason.community.community", lambda *a, **kw: Sample())
    dist = tmp_path / "dist"
    dist.mkdir()
    return create_app(dist, {"community": community_record}, approvals_live=None, extra_writes=False,
                      sign_in=webclient.roster_sign_in())


def test_the_route_needs_a_sign_in(app):
    r = webclient.client(app).get("/api/community")
    assert r.status_code == 401 and r.json["signIn"] == "/auth/google"


def test_the_owner_view_is_refused(app):
    c = webclient.sign_in(webclient.client(app), "Lee President")
    r = c.get("/api/community?view=owner")
    assert r.status_code == 403 and r.json["ownerView"] is True


def test_the_route_answers_a_roster_person_masked(app):
    c = webclient.sign_in(webclient.client(app), "Dana Director")
    r = c.get("/api/community")
    assert r.status_code == 200, r.json
    assert r.json["board"]["quorum"]["source"] == "Bylaws 9.3"
    assert "board@example.org" not in r.get_data(as_text=True)


def test_the_private_view_shows_the_email_and_logs_it(app, tmp_path):
    c = webclient.sign_in(webclient.client(app), "Sam Secretary")
    assert c.post("/api/private", json={"reason": "community record check"}).status_code == 200
    out = c.get("/api/community").json
    assert out["emailsShown"] is True and out["identity"]["officialEmail"]["value"] == "board@example.org"
    log = (tmp_path / "data" / "access" / "served.jsonl").read_text(encoding="utf-8")
    assert '"address": "api/community"' in log


def test_community_is_registered_and_no_owner_source():
    from jason.web.extra.owner_view import OWNER_SOURCES
    from jason.web.sources import EXTRA_LOADERS

    assert EXTRA_LOADERS["community"] == "jason.web.extra.community_record:community_record"
    assert "community" not in OWNER_SOURCES
