"""The notice of a board meeting: one base template, rendered by the meeting's format, with the law recited from disk.

Every fact here is made up ("Example Commons", "123 Main St"); the statutes are a made-up shelf in tmp_path, so the
tests show the words come from the stored pages and never from jason's own wording."""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
from types import SimpleNamespace

import pytest

from jason.community.base import MeetingSchedule, NoticePeriod, SpeakingLimit
from jason.community.board_items import BoardItem, ItemCategory, ItemStatus, Session
from jason.community.email_html import Letterhead
from jason.community.identity import Identity
from jason.tasks import meeting_notice as mn
from jason.tasks.agenda_plan import MeetingFormat

MEETING = date(2099, 1, 20)

# Made-up statute words in the exported pages' shape: a history note, the section's amendment line, then its words.
SECTIONS = {
    "4041": ("- History: made up for the tests\n\n4041. (Amended by Stats. 2099, Ch. 1, Sec. 1.)\n\n"
             "(a) A member shall tell the association each year all of the following:\n\n"
             "(1) How the member wants notices, which may be one or both of the following:\n\n"
             "(A) A postal address.\n\n(B) An inbox that works.\n\n"
             "(2) A second way to reach the member.\n\n(b) The association asks every year."),
    "4045": ("4045. (Amended by Stats. 2099, Ch. 1, Sec. 2.)\n\n"
             "(a) A general notice goes up on the board by the mailboxes.\n\n"
             "(b) A member who asks gets every general notice delivered to that member alone, the zebra rule."),
    "4930": ("4930. (Added by Stats. 2099, Ch. 1, Sec. 3.)\n\n"
             "(a) Except as described in subdivision (b), the board talks only about listed items, the walrus rule.\n\n"
             "(b) The board may answer a speaker briefly."),
}
PAGES = (("CIV-4000-4070.md", "4000", "4070", ("4041", "4045")), ("CIV-4900-4955.md", "4900", "4955", ("4930",)))


def _shelf(root, *, leave_out: tuple[str, ...] = ()):
    law = root / "authorities" / "CIV"
    law.mkdir(parents=True, exist_ok=True)
    pages = []
    for name, start, end, numbers in PAGES:
        body = "".join(f"\n\n## CIV {n}\n{SECTIONS[n]}" for n in numbers if n not in leave_out)
        (law / name).write_text("# Made-up statutes" + body + "\n", encoding="utf-8")
        pages.append({"file": f"authorities/CIV/{name}", "citation": f"CIV {start}-{end}", "title": "Made up",
                      "code": "CIV", "start": start, "end": end, "sections": [n for n in numbers if n not in leave_out],
                      "basis": "duty", "why": [], "session": "2099"})
    (root / "authorities" / "manifest.json").write_text(json.dumps({"pages": pages}), encoding="utf-8")
    return root


@pytest.fixture
def shelf(tmp_path):
    return _shelf(tmp_path)


def _community(*, period: NoticePeriod | None = None, forum: SpeakingLimit | None = None, identity: Identity | None = None):
    who = identity or Identity("Example Commons Owners Association", official_address="123 Main St, Anytown, CA 90000",
                               official_email="board@example.org", posting_location="the notice board at 123 Main St",
                               signer="Board of Directors")
    return SimpleNamespace(identity=lambda: who, citations=lambda: {}, board_notice_period=lambda: period,
                           open_forum_limit=lambda: forum, meeting_schedule=lambda: MeetingSchedule(1, 3, "7:00 pm", "Zoom"),
                           email_letterhead=lambda: Letterhead("EXAMPLE COMMONS", footer="123 Main St"))


def _item(id: str, title: str, ask: str, *, session: Session | None = None, category=ItemCategory.GOVERNANCE) -> BoardItem:
    return BoardItem(id, title, "", ask, category, status=ItemStatus.PROPOSED, session=session)


ITEMS = [_item("paint", "Repaint the clubhouse", "Approve the painting contract."),
         _item("case", "Zed v. Example Commons 24CV000123", "Direct counsel on the case.", session=Session.EXECUTIVE)]


def _meeting(fmt: MeetingFormat, **kw) -> mn.Meeting:
    base = dict(time="7:00 pm", location="Clubhouse, 123 Main St", join="https://example.org/join/123 (meeting ID 123)",
                dial_in="(555) 010-0000, meeting ID 123", tech_contact="Pat Doe, (555) 010-0001, help@example.org")
    return mn.Meeting(MEETING, fmt, **{**base, **kw})


def _draw(shelf, fmt: MeetingFormat, community=None, items=ITEMS, plan_items=None, **kw) -> mn.Notice:
    return mn.render(community or _community(), _meeting(fmt, **kw), items, shelf,
                     plan_items={"case": {"subject": "litigation"}} if plan_items is None else plan_items)


TELECONFERENCE_ONLY = ("4926", "roll call", "Technical help", "By telephone", "To join", "request individual delivery of meeting notices")


# --- The format's lines, and never the others' -------------------------------------------------------------------------

def test_a_meeting_held_entirely_by_teleconference_carries_4926s_lines(shelf):
    text = _draw(shelf, MeetingFormat.TELECONFERENCE).markdown
    for needed in ("https://example.org/join/123", "(555) 010-0000", "Pat Doe, (555) 010-0001, help@example.org",
                   "4926(a)(1)(A)", "4926(a)(1)(B)", "4926(a)(1)(C)", "4926(a)(3)", "4926(a)(4)", "roll call",
                   "a member may request individual delivery of meeting notices", "no physical location"):
        assert needed in text, needed
    assert "4090(b)" not in text and "Clubhouse" not in text


def test_a_hybrid_meeting_names_its_physical_location_and_none_of_4926s_lines(shelf):
    text = _draw(shelf, MeetingFormat.HYBRID).markdown
    assert "**Place:** Clubhouse, 123 Main St" in text and "4090(b)" in text
    assert "At least one director or a person the board designates will be present there" in text
    for absent in TELECONFERENCE_ONLY + ("https://example.org/join", "help@example.org"):
        assert absent not in text, absent


def test_an_in_person_meeting_names_its_place_only(shelf):
    text = _draw(shelf, MeetingFormat.IN_PERSON).markdown
    assert "**Place:** Clubhouse, 123 Main St" in text
    for absent in TELECONFERENCE_ONLY + ("4090(b)", "teleconference"):
        assert absent not in text, absent


def test_a_meeting_where_ballots_are_counted_is_never_noticed_as_teleconference_only(shelf):
    with pytest.raises(mn.NoticeRefused, match=r"4926\(b\)"):
        _draw(shelf, MeetingFormat.TELECONFERENCE, ballots_counted=True)
    assert "4090(b)" in _draw(shelf, MeetingFormat.HYBRID, ballots_counted=True).markdown


def test_no_format_is_no_notice():
    with pytest.raises(mn.NoticeRefused, match="format is not set"):
        mn.from_plan(MEETING, {"basics": {"format": ""}})
    meeting = mn.from_plan(MEETING, {"basics": {"format": "hybrid", "start": "18:30", "location": "Clubhouse"},
                                     "zoom": {"joinUrl": "https://example.org/j", "dialIn": "(555) 010-0000"}},
                           tech_contact="Pat Doe")
    assert (meeting.format, meeting.time, meeting.location, meeting.join, meeting.tech_contact) == (
        MeetingFormat.HYBRID, "6:30 pm", "Clubhouse", "https://example.org/j", "Pat Doe")


def test_a_place_the_records_do_not_hold_is_a_blank_for_a_person(shelf):
    notice = _draw(shelf, MeetingFormat.IN_PERSON, location="")
    assert "**Place:** ==[the place of the meeting]==" in notice.markdown and "LOCATION" in notice.blanks
    assert any("the place of the meeting" in line for line in notice.review)


# --- The open forum's limit only when the board adopted one ------------------------------------------------------------

def test_no_forum_limit_line_without_an_adopted_limit(shelf):
    text = _draw(shelf, MeetingFormat.HYBRID).markdown
    assert "Open forum (Civil Code Section 4925(b))" in text
    assert "may speak" not in text and "minutes (" not in text


def test_the_forum_limit_line_with_the_boards_limit(shelf):
    text = _draw(shelf, MeetingFormat.HYBRID, _community(forum=SpeakingLimit(3, "Resolution 2099-01"))).markdown
    assert "Each member may speak for up to 3 minutes (Resolution 2099-01)." in text


# --- The notice period as a date line ----------------------------------------------------------------------------------

def test_the_notice_date_follows_the_statutes_period_by_default(shelf):
    notice = _draw(shelf, MeetingFormat.HYBRID)
    assert notice.notice_by == date(2099, 1, 16)
    assert "**Date of this notice:** Friday, January 16, 2099 (notice period: CIV 4920(a))" in notice.markdown
    assert not re.search(r"\b(four|4) days\b", notice.markdown)


def test_the_notice_date_follows_the_documents_longer_period(shelf):
    notice = _draw(shelf, MeetingFormat.HYBRID, _community(period=NoticePeriod(10, "Bylaws 3.4")))
    assert notice.notice_by == date(2099, 1, 10)
    assert "**Date of this notice:** Saturday, January 10, 2099 (notice period: Bylaws 3.4; CIV 4920(b)(3))" in notice.markdown
    assert not re.search(r"\b(ten|10) days\b", notice.markdown)


def test_a_notice_date_after_the_period_is_refused_and_one_within_it_is_printed(shelf):
    with pytest.raises(mn.NoticeRefused, match="late"):
        _draw(shelf, MeetingFormat.HYBRID, notice_date=date(2099, 1, 18))
    notice = _draw(shelf, MeetingFormat.HYBRID, notice_date=date(2099, 1, 12))
    assert "Monday, January 12, 2099" in notice.markdown
    assert not any("last day" in line for line in notice.review)


# --- The agenda: executive matters by their 4935 subject only ----------------------------------------------------------

def test_an_executive_items_title_never_appears(shelf, tmp_path):
    notice = _draw(shelf, MeetingFormat.TELECONFERENCE)
    for leak in ("Zed", "24CV000123", "Direct counsel"):
        assert leak not in notice.markdown
        assert leak not in mn.email_html(notice.markdown)
    assert "Adjourn to executive session (Civil Code Section 4935)" in notice.markdown
    assert "   - litigation (Civil Code 4935(a))" in notice.markdown
    assert "**Repaint the clubhouse** _(action)_" in notice.markdown


def test_an_executive_item_with_no_recorded_subject_is_flagged_for_the_secretary(shelf):
    notice = _draw(shelf, MeetingFormat.HYBRID, plan_items={})
    assert "Zed" not in notice.markdown and "confirm" in notice.markdown
    assert any("Secretary" in line for line in notice.review)


def test_the_plan_marking_an_item_executive_keeps_it_off_the_open_agenda(shelf):
    items = [_item("hearing", "Hearing for unit 7 owner Roe", "Decide the fine.")]
    notice = _draw(shelf, MeetingFormat.HYBRID, items=items,
                   plan_items={"hearing": {"include": True, "kind": "executive", "subject": "member_discipline"}})
    assert "Roe" not in notice.markdown and "unit 7" not in notice.markdown
    assert "New business" not in notice.markdown and "member discipline (Civil Code 4935(a), (b))" in notice.markdown


def test_the_plan_chooses_the_items_when_it_includes_any(shelf):
    items = [*ITEMS, _item("pool", "Pool hours", "Adopt the pool hours.")]
    notice = _draw(shelf, MeetingFormat.HYBRID, items=items, plan_items={"pool": {"include": True, "motion": "Open at 9."}})
    assert "Pool hours" in notice.markdown and "Proposed motion: Open at 9." in notice.markdown
    assert "Repaint" not in notice.markdown and "executive session" not in notice.markdown


# --- The law, recited from the stored pages ----------------------------------------------------------------------------

def test_statute_words_come_from_the_stored_pages(shelf):
    notice = _draw(shelf, MeetingFormat.HYBRID)
    text = notice.markdown
    assert "> (a) Except as described in subdivision (b), the board talks only about listed items, the walrus rule." in text
    assert "> (b) The board may answer a speaker briefly." in text                 # 4930 recited whole
    assert "> (b) A member who asks gets every general notice delivered to that member alone, the zebra rule." in text
    assert "> (a) A general notice goes up" not in text                           # 4045(b), not (a)
    # 4041(a)(1): the lead-in of (a), then (1) with its (A) and (B), and an ellipsis for what follows.
    lead = text.index("> (a) A member shall tell the association each year all of the following:")
    assert lead < text.index("> (1) How the member wants notices") < text.index("> (B) An inbox that works.")
    assert "A second way" not in text and "> …" in text
    assert "History" not in text and "Stats. 2099" not in text
    assert "cannot be unsubscribed" not in text
    assert all(r.found and r.session == "2099" and len(r.digest) == 64 for r in notice.recitals)


def test_a_missing_statute_is_a_visible_miss_not_a_paraphrase(tmp_path):
    root = _shelf(tmp_path, leave_out=("4041",))
    notice = _draw(root, MeetingFormat.HYBRID)
    (miss,) = notice.misses
    assert miss.citation == "CIV 4041(a)(1)"
    assert "==Civil Code Section 4041(a)(1): not on disk (" in notice.markdown
    assert "Its words are not paraphrased here" in notice.markdown
    assert "How the member wants notices" not in notice.markdown and "preferred delivery method" not in notice.markdown
    assert any("4041(a)(1) is not on disk" in line for line in notice.review)


def test_a_subdivision_not_in_the_words_is_a_miss(shelf):
    r = mn.recite(shelf, "CIV 4045(z)")
    assert not r.found and "could not find (z)" in r.reason


# --- The signer, the delivery, and the files ---------------------------------------------------------------------------

def test_the_signer_and_name_come_from_the_identity(shelf):
    who = Identity("Example Commons Owners Association", official_email="board@example.org",
                   posting_location="the notice board", signer="Jane Roe, Secretary")
    text = _draw(shelf, MeetingFormat.HYBRID, _community(identity=who)).markdown
    assert text.rstrip().endswith("Jane Roe, Secretary\nExample Commons Owners Association")
    assert "jason" not in text.split("the official code controls.)_")[-1]
    assert "by direction of the board" not in text
    assert "write to board@example.org." in text


def test_no_posting_location_is_a_blank_not_a_guess(shelf):
    who = Identity("Example Commons Owners Association", official_address="123 Main St")
    notice = _draw(shelf, MeetingFormat.HYBRID, _community(identity=who))
    assert "GENERAL_DELIVERY" in notice.blanks
    assert "==[where general notices are posted" in notice.markdown


def test_a_full_record_leaves_no_token_and_no_blank(shelf):
    notice = _draw(shelf, MeetingFormat.TELECONFERENCE)
    assert not notice.blanks and not mn.TOKEN.search(notice.markdown) and "<!--" not in notice.markdown


def test_the_files_are_the_source_the_email_and_the_recitals(shelf):
    notice = _draw(shelf, MeetingFormat.HYBRID)
    paths = mn.write(shelf, notice, Letterhead("EXAMPLE COMMONS", footer="123 Main St"))
    assert paths["markdown"].parent == shelf / "board" / "notices"
    assert paths["markdown"].read_text(encoding="utf-8") == notice.markdown
    html = paths["html"].read_text(encoding="utf-8")
    assert "EXAMPLE COMMONS" in html and "<blockquote>" in html and "4090(b)" in html and "4926" not in html
    refs = json.loads(paths["refs"].read_text(encoding="utf-8"))
    assert refs["key"] == "board-meeting-2099-01-20" and {r["citation"] for r in refs["recitals"]} == set(mn.RECITALS.values())


def test_the_base_is_checked_against_the_catalog():
    from jason.tasks import notice_templates as nt

    checks = [c for c in nt.check_all(("board-meeting",)) if c.base.where.endswith("board-meeting-notice.md")]
    (c,) = checks
    assert not c.error and not [f.element for f in c.missing]


def test_the_command_writes_the_notice_and_sends_nothing(shelf, monkeypatch, capsys):
    from jason import cli

    monkeypatch.setattr("jason.community.community", lambda: _community())
    plan = shelf / "meetings" / "plan-2099-01-20.json"
    plan.parent.mkdir(parents=True)
    plan.write_text(json.dumps({"basics": {"format": "hybrid", "location": "Clubhouse, 123 Main St", "start": "19:00"}}),
                    encoding="utf-8")
    args = argparse.Namespace(date="2099-01-20", format="", location="", tech_contact="", ballots_counted=False,
                              notice_date="")
    assert cli._board_notice(args, shelf) == 0
    out = capsys.readouterr().out
    assert "notice-2099-01-20.md (hybrid)" in out and "nothing sent" in out
    assert "jason letter --markdown" in out and "--notice board-meeting-2099-01-20" in out
    assert (shelf / "board" / "notices" / "notice-2099-01-20.html").is_file()
    args.format, args.ballots_counted = "teleconference", True
    assert cli._board_notice(args, shelf) == 2
