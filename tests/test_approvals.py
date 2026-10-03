"""The approvals store: a letter's stages, who may approve, and the inbox loader."""

import os
import sys
import types
from pathlib import Path

import pytest

import jason  # noqa: E402

# The made-up officers in tests/fixtures/spec, found from the package so the test runs from any folder.
os.environ["JASON_SPEC_DIR"] = str(Path(jason.__path__[0]).resolve().parents[1] / "tests" / "fixtures" / "spec")

from jason.tasks import approvals as store  # noqa: E402

PRESIDENT, VICE, TREASURER, SECRETARY, DIRECTOR, MANAGER = "Quill Ashgrove", "Bram Tidewell", "Ilse Varnholt", "Odo Fennimore", "Wren Castlebury", "Pell Marchbanks"
KEY = "Drive/Collections/Unit 7/release.docx"
TEXT = {"kind": "Lien release", "title": "Release of Notice of Delinquent Assessment", "date": "2026-10-03", "to": "County Recorder; copy to the owner of record, Unit 7",
        "via": "Recording; first-class mail to the owner", "body": ["The association releases the notice.", "Recorded on request."], "signoff": "The Board of Directors",
        "approver": "the board", "sentCommand": "jason letter release --unit 7 --yes"}


def _requested(tmp_path, approver="the board", key=KEY):
    store.draft(tmp_path, key, {**TEXT, "approver": approver}, by=MANAGER)
    store.step(tmp_path, key, "save", by=MANAGER)
    return store.step(tmp_path, key, "request", by=MANAGER)


def test_the_officers_come_from_the_fixture_facts():
    from jason.community import community
    from jason.community.base import OfficerRole

    rows = community().officers()
    assert [o.role for o in rows] == [OfficerRole.PRESIDENT, OfficerRole.VICE_PRESIDENT, OfficerRole.TREASURER, OfficerRole.SECRETARY, OfficerRole.DIRECTOR, OfficerRole.MANAGER]
    by = {o.name: o for o in rows}
    assert by[PRESIDENT].approves == ("the president",) and by[VICE].approves == ("a fluent reviewer",) and by[DIRECTOR].approves == ()
    assert by[PRESIDENT].can_approve("the board") and by[SECRETARY].can_approve("the board") and not by[TREASURER].can_approve("the board")


def test_draft_save_request_and_the_trail(tmp_path):
    letter = store.draft(tmp_path, KEY, TEXT, by=MANAGER)
    assert letter["stage"] == "draft" and letter["body"] == TEXT["body"] and letter["log"][0]["by"] == MANAGER
    assert store.pending_count(tmp_path) == 0
    letter = store.step(tmp_path, KEY, "save", by=MANAGER)
    assert letter["stage"] == "saved"
    letter = store.draft(tmp_path, KEY, {"body": "A new first paragraph.\n\nA second."}, by=MANAGER, note="tightened")
    assert letter["stage"] == "draft" and letter["body"] == ["A new first paragraph.", "A second."] and letter["title"] == TEXT["title"]
    store.step(tmp_path, KEY, "save", by=MANAGER)
    letter = store.step(tmp_path, KEY, "request", by=MANAGER)
    assert letter["stage"] == "requested" and store.pending_count(tmp_path) == 1
    assert [e["title"][:5] for e in letter["log"]] == ["Draft", "Draft", "Draft", "Draft", "Appro"]
    assert store.get(tmp_path, KEY)["key"] == KEY and store.all(tmp_path)[0]["key"] == KEY
    with pytest.raises(ValueError):
        store.draft(tmp_path, KEY, {"title": "changed while requested"}, by=MANAGER)
    with pytest.raises(ValueError):
        store.step(tmp_path, KEY, "save", by=MANAGER)       # not a draft any more
    with pytest.raises(ValueError):
        store.step(tmp_path, KEY, "record_sent", by=MANAGER, sent_ref="x")  # not approved
    with pytest.raises(ValueError):
        store.step(tmp_path, KEY, "mail", by=MANAGER)       # no such transition
    with pytest.raises(ValueError):
        store.step(tmp_path, KEY, "withdraw", by="")        # every step is named
    with pytest.raises(KeyError):
        store.step(tmp_path, "Drive/nope.docx", "save", by=MANAGER)
    with pytest.raises(ValueError):
        store.draft(tmp_path, "Drive/x.docx", {"title": "x", "approver": "the dog"}, by=MANAGER)
    with pytest.raises(ValueError):
        store.draft(tmp_path, "Drive/x.docx", {"kind": "no title"}, by=MANAGER)


def test_the_board_approves_by_vote_recorded_by_the_president_or_secretary(tmp_path):
    _requested(tmp_path)
    with pytest.raises(ValueError, match="4910"):
        store.step(tmp_path, KEY, "approve", by=TREASURER, meeting="2026-10-20")
    with pytest.raises(ValueError, match="meeting"):
        store.step(tmp_path, KEY, "approve", by=PRESIDENT)
    with pytest.raises(ValueError):
        store.step(tmp_path, KEY, "approve", by="Nobody Known", meeting="2026-10-20")
    letter = store.step(tmp_path, KEY, "approve", by=SECRETARY, meeting="2026-10-20")
    assert letter["stage"] == "approved" and letter["meeting"] == "2026-10-20"
    assert "2026-10-20" in letter["log"][-1]["title"] and "CIV 4910" in letter["log"][-1]["title"] and letter["log"][-1]["tone"] == "good"
    with pytest.raises(ValueError, match="sentRef"):
        store.step(tmp_path, KEY, "record_sent", by=MANAGER)
    letter = store.step(tmp_path, KEY, "record_sent", by=MANAGER, sent_ref="mailroom communication 48213")
    assert letter["stage"] == "sent" and letter["sentRef"] == "mailroom communication 48213" and letter["sentOn"]
    with pytest.raises(ValueError):
        store.step(tmp_path, KEY, "approve", by=PRESIDENT, meeting="2026-10-20")  # already sent


def test_an_officer_approves_only_for_the_role_named(tmp_path):
    key = "Drive/Finance/2026/09 questions/vendor.docx"
    _requested(tmp_path, "the secretary", key)
    with pytest.raises(ValueError, match="cannot approve"):
        store.step(tmp_path, key, "approve", by=TREASURER)
    with pytest.raises(ValueError):
        store.step(tmp_path, key, "approve", by=DIRECTOR)
    letter = store.step(tmp_path, key, "send_back", by=SECRETARY, note="name the invoice")
    assert letter["stage"] == "saved" and letter["log"][-1]["tone"] == "warn" and letter["log"][-1]["title"].endswith("name the invoice")
    store.step(tmp_path, key, "request", by=MANAGER)
    assert store.step(tmp_path, key, "withdraw", by=MANAGER)["stage"] == "saved"
    store.step(tmp_path, key, "request", by=MANAGER)
    letter = store.step(tmp_path, key, "approve", by=SECRETARY)
    assert letter["stage"] == "approved" and letter["log"][-1]["title"] == f"Approved by {SECRETARY} (secretary) as the secretary"
    _requested(tmp_path, "a fluent reviewer", "Drive/Notices/spanish.docx")
    assert store.step(tmp_path, "Drive/Notices/spanish.docx", "approve", by=VICE)["stage"] == "approved"


def test_without_officers_no_approval_is_recorded(tmp_path, monkeypatch):
    from jason.community import community

    _requested(tmp_path, "the treasurer")
    monkeypatch.setattr(type(community()), "officers", lambda self: ())
    with pytest.raises(ValueError, match="officers"):
        store.step(tmp_path, KEY, "approve", by=TREASURER)


@pytest.fixture
def county(tmp_path):
    saved = {k: sys.modules.get(k) for k in ("jason.mcp", "jason.mcp.county")}
    fake = types.ModuleType("jason.mcp.county")
    fake._data_dir = lambda _root=None: tmp_path
    pkg = types.ModuleType("jason.mcp")
    pkg.__path__ = []
    pkg.county = fake
    sys.modules["jason.mcp"], sys.modules["jason.mcp.county"] = pkg, fake
    try:
        yield tmp_path
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v


def test_the_loader_groups_letters_and_names_the_people(county):
    from jason.web.extra import approvals as web

    empty = web.approvals({})
    assert empty["found"] is True and empty["letters"] == [] and empty["pending"] == 0 and empty["note"]
    out = web.write("-", {"action": "draft", "by": MANAGER, "letter": {**TEXT, "key": KEY}})
    assert out["key"] == KEY and out["stage"] == "draft"
    web.write(KEY, {"action": "save", "by": MANAGER})
    web.write(KEY, {"action": "request", "by": MANAGER})
    web.write("Drive/Finance/vendor.docx", {"action": "draft", "by": MANAGER, "letter": {**TEXT, "approver": "the treasurer", "title": "Request for an itemized invoice"}})
    page = web.approvals({})
    assert page["groups"] == {"requested": [KEY], "approved": [], "sent": [], "drafts": ["Drive/Finance/vendor.docx"]} and page["pending"] == 1
    people = {p["name"]: p for p in page["people"]}
    assert people[PRESIDENT]["canApproveBoard"] and people[SECRETARY]["canApproveBoard"] and not people[TREASURER]["canApproveBoard"]
    assert people[VICE]["approves"] == ["a fluent reviewer"] and people[TREASURER]["role"] == "treasurer"
    assert page["stages"] == list(store.STAGES) and any("4910" in c for c in page["caveats"])
    with pytest.raises(ValueError):
        web.write(KEY, {"action": "approve", "by": TREASURER, "meeting": "2026-10-20"})
    with pytest.raises(ValueError):
        web.write(KEY, {"action": "send", "by": PRESIDENT})
    approved = web.write(KEY, {"action": "approve", "by": PRESIDENT, "meeting": "2026-10-20"})
    assert approved["stage"] == "approved" and approved["sentCommand"] == TEXT["sentCommand"]
    sent = web.write(KEY, {"action": "record_sent", "by": MANAGER, "sentRef": "mailroom 1"})
    assert sent["stage"] == "sent"
    one = web.approvals({"key": KEY})
    assert one["found"] and one["letter"]["sentRef"] == "mailroom 1"
    assert web.approvals({"key": "Drive/none"})["found"] is False
    assert web.approvals({})["groups"]["sent"] == [KEY]
    with pytest.raises(KeyError):
        web.write("Drive/none", {"action": "save", "by": MANAGER})
    with pytest.raises(ValueError):
        web.write("-", {"action": "draft", "by": MANAGER})
