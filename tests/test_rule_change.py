"""The rule change notices: 28-day date math against the meeting schedule, the 4360 elements, and no send path."""

from __future__ import annotations

import inspect
import json
from datetime import date
from pathlib import Path

import pytest

from jason.community.base import MeetingSchedule
from jason.community.rule_changes import RuleChange, SectionChange
from jason.tasks import rule_change as rc

SCHEDULE = MeetingSchedule(weekday=1, nth=3, time="7:00 pm", place="Zoom", regular_months=(1, 4, 7, 10), annual_month=11,
                           practice="the third Tuesday of every month")

CHANGE = RuleChange(
    key="test-change", title="Payments", document="policy", document_title="Assessment Collection Policy",
    purpose="The lockbox is closing.", effect="Owners pay online beginning on [effective date].",
    sections=(
        SectionChange("10", "Notice.", strike="in certified funds.", proposed="by an accepted method."),
        SectionChange("20", "Methods of Payment.", proposed="Pay online from [effective date]. Fee: [returned payment charge]."),
    ),
    decisions=("[effective date]",),
    caveats=("DRAFT.",),
)


def test_decision_is_first_meeting_at_least_28_days_out_monthly():
    # Notice on Sept 30, 2026: Oct 20 is only 20 days out, so the decision falls on Nov 17.
    when = rc.timeline(SCHEDULE, notice_date=date(2026, 9, 30))
    assert when.decision == date(2026, 11, 17)
    assert when.notice_by == date(2026, 10, 20)
    assert when.lead_days == 48
    assert when.adoption_notice_by == date(2026, 12, 2)
    assert when.agenda_notice_by == date(2026, 11, 13)
    assert when.comment_deadline == date(2026, 11, 16)
    assert when.reversal_request_by == date(2027, 1, 1)


def test_exactly_28_days_counts():
    # Oct 20, 2026 is 28 days after Sept 22.
    assert rc.first_decision_date(SCHEDULE, date(2026, 9, 22)) == date(2026, 10, 20)
    assert rc.first_decision_date(SCHEDULE, date(2026, 9, 23)) == date(2026, 11, 17)


def test_regular_months_only_skips_to_january():
    when = rc.timeline(SCHEDULE, notice_date=date(2026, 9, 30), monthly=False)
    assert when.decision == date(2027, 1, 19)


def test_too_soon_decision_refused():
    with pytest.raises(ValueError, match="4360"):
        rc.timeline(SCHEDULE, notice_date=date(2026, 9, 30), decision=date(2026, 10, 20))


def test_policy_statement_window():
    when = rc.timeline(SCHEDULE, notice_date=date(2026, 9, 30), fiscal_year_end=date(2026, 12, 31))
    assert when.policy_statement == (date(2026, 10, 2), date(2026, 12, 1))


def _outline(tmp_path: Path) -> Path:
    text = "10. Notice. Payment may be required in certified funds. More.\n20. Address. Mail checks to the lockbox.\n"
    sections = [{"number": "10", "start": 0, "end": text.index("20.")}, {"number": "20", "start": text.index("20."), "end": len(text)}]
    (tmp_path / "outlines").mkdir()
    (tmp_path / "outlines" / "policy.json").write_text(json.dumps({"text": text, "sections": sections}), encoding="utf-8")
    return tmp_path


def test_member_notice_has_required_elements(tmp_path):
    current = rc.current_sections(_outline(tmp_path), "policy")
    assert "lockbox" in current["20"]
    when = rc.timeline(SCHEDULE, notice_date=date(2026, 9, 30))
    notice = rc.member_notice(CHANGE, when, current, "Mystique Community Association", SCHEDULE)
    elements = rc.required_elements(notice, CHANGE, when)
    assert len(elements) == len(rc.REQUIRED_ELEMENTS)
    assert all(ok for _, _, ok in elements), elements
    assert "Tuesday, November 17, 2026" in notice.text
    assert "Monday, November 16, 2026" in notice.text
    assert "[effective date]" in notice.text            # the board's choice stays a placeholder
    assert "4365" in notice.text


def test_missing_purpose_fails_the_check():
    when = rc.timeline(SCHEDULE, notice_date=date(2026, 9, 30))
    notice = rc.member_notice(CHANGE, when, {}, "M", SCHEDULE)
    stripped = rc.Notice(notice.subject, notice.text.replace("PURPOSE OF THE PROPOSED CHANGE", ""))
    names = {name: ok for name, _, ok in rc.required_elements(stripped, CHANGE, when)}
    assert names["A description of the purpose of the proposed rule change"] is False


def test_strike_amendment_applies_inside_section(tmp_path):
    current = rc.current_sections(_outline(tmp_path), "policy")
    amended = rc.proposed_section_text(CHANGE.sections[0], current["10"])
    assert "by an accepted method." in amended and "certified funds" not in amended and "More." in amended


def test_markdown_written_with_three_parts(tmp_path):
    data = _outline(tmp_path)
    when = rc.timeline(SCHEDULE, notice_date=date(2026, 9, 30))
    md = rc.render_markdown(CHANGE, when, rc.current_sections(data, "policy"), "Mystique Community Association", SCHEDULE,
                            [{"citation": "CIV 4360", "found": False, "page": "", "session": "", "text": "", "reason": "not exported"}])
    path = rc.write(data, CHANGE, md)
    assert path == data / "board" / "rule-change-test-change.md"
    body = path.read_text(encoding="utf-8")
    for part in ("(a) Member notice", "(b) Agenda item", "(c) Notice of the adopted rule change", "CIV 4360: not verified"):
        assert part in body
    assert "annual meeting month" in body


def test_draft_has_no_recipients_and_no_send_path():
    when = rc.timeline(SCHEDULE, notice_date=date(2026, 9, 30))
    draft = rc.email_draft(rc.member_notice(CHANGE, when, {}, "M", SCHEDULE))
    assert draft.to == () and draft.cc == () and draft.bcc == ()

    calls = []

    class FakeGmail:
        def create(self, d):
            calls.append(("create", d))
            return {"id": "r1"}

        def send(self, d):  # pragma: no cover - must never be called
            raise AssertionError("send called")

    assert rc.save_draft(FakeGmail(), draft) == {"id": "r1"}
    assert [c[0] for c in calls] == ["create"]
    from jason.google.gmail_drafts import DraftMessage, GmailDrafts

    with pytest.raises(ValueError):
        rc.save_draft(FakeGmail(), DraftMessage(to=("a@example.com",), subject="s", text="t"))
    assert not hasattr(GmailDrafts, "send")
    source = inspect.getsource(rc) + Path(inspect.getsourcefile(rc)).with_name("..").joinpath("commands", "rule_change.py").resolve().read_text(encoding="utf-8")
    assert ".send(" not in source and "messages/send" not in source


LAW = {"CIV 4360(a)": "The notice shall include the text of the proposed rule change and a description of the "
                      "purpose and effect of the proposed rule change."}


def test_member_notice_follows_4360a_order_and_labels_the_description():
    when = rc.timeline(SCHEDULE, notice_date=date(2026, 9, 30))
    text = rc.member_notice(CHANGE, when, {}, "Example Commons Owners Association", SCHEDULE, law=LAW).text
    assert text.index(rc.TEXT_HEADING) < text.index(rc.DESCRIPTION_HEADING) < text.index("PURPOSE OF THE PROPOSED")
    assert "the Board's own explanation" in text
    assert 'provides: "The notice shall include the text of the proposed rule change' in " ".join(text.split())
    from jason.community.notice_catalog import requirement
    from jason.community.notice_elements import check

    assert all(f.ok for f in check(requirement("rule-change-proposed"), text))


def test_member_notice_without_the_law_states_it_in_its_own_words():
    when = rc.timeline(SCHEDULE, notice_date=date(2026, 9, 30))
    text = rc.member_notice(CHANGE, when, {}, "M", SCHEDULE).text
    assert "provides:" not in text and "requires the Board to give members notice" in " ".join(text.split())


def test_adoption_notice_recites_the_adopted_text():
    when = rc.timeline(SCHEDULE, notice_date=date(2026, 9, 30))
    text = rc.adoption_notice(CHANGE, when, "M").text
    assert rc.ADOPTED_TEXT_HEADING in text
    assert '"in certified funds." are replaced with "by an accepted method."' in " ".join(text.split())
    assert "Pay online from [effective date]." in text


def test_proposed_text_is_a_stage_version_cited_as_itself():
    when = rc.timeline(SCHEDULE, notice_date=date(2026, 9, 30))
    version = rc.proposed_version(CHANGE, when, book="pol")
    assert version.label() == "@proposed-2026-09-30"
    assert not version.in_force_on(date(2030, 1, 1))
    assert rc.version_address(version, "20") == "jason://pol@proposed-2026-09-30/20"


class _Found:
    def __init__(self, number: str, words: str):
        self.found, self.text, self.reason = bool(words), words, None
        self.address, self.pid = f"jason://pol/{number}", f"pol@base/{number}"
        self.in_force = "as written in the Example Policy"
        self._n = number

    def __str__(self):
        return f"Example Policy Section {self._n}"

    def section(self, number):
        return _Found(number, {"10": "10. Notice. Pay in certified funds."}.get(number, ""))


class _Shelf:
    def __init__(self, data_dir):
        self.data_dir = data_dir

    def doc(self, name):
        return _Found("", "x")


def test_sections_are_recited_through_the_shelf_with_the_outline_as_fallback(tmp_path):
    data = _outline(tmp_path)
    recitals = rc.recite_sections(CHANGE, shelf=_Shelf(data))
    assert recitals["10"].source == "shelf" and recitals["10"].address == "jason://pol/10"
    assert recitals["10"].pid == "pol@base/10" and "certified funds" in recitals["10"].words
    # The shelf has no section 20: it is read from the outline, and the page says so.
    assert recitals["20"].source == "outline" and "lockbox" in recitals["20"].words
    when = rc.timeline(SCHEDULE, notice_date=date(2026, 9, 30))
    version = rc.proposed_version(CHANGE, when, book="pol")
    md = rc.render_markdown(CHANGE, when, rc.words_of(recitals), "M", SCHEDULE, [], recitals=recitals,
                            version=version, law=LAW)
    assert "## The versions cited" in md and "`jason://pol@proposed-2026-09-30/20`" in md
    assert "pol@base/10" in md and "the outline, read directly" in md
    assert "Required elements of `rule-change-proposed`" in md


def test_specification_row_is_well_formed():
    from jason.community import mystique

    change = rc.find_change(tuple(mystique().rule_changes()), "collection-policy-payments")
    assert change.document == "collection-policy"
    assert {s.number for s in change.sections} >= {"14", "20"}
    assert "[effective date]" in change.placeholders()
    with pytest.raises(LookupError):
        rc.find_change(tuple(mystique().rule_changes()), "nope")
