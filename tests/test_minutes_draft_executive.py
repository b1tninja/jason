"""The minutes draft never gives the model the agenda's own words for an executive item (Civil Code 4935(e)).

Each executive item reaches the model only by its 4935 subject in the statute's general words (the agenda plan's, else
jason's reading of the item's words), or as a blank for the Secretary; the checks count any line about the executive
session that uses the item's words. All names below are made up.
"""

import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from jason.community.models.meetings import ExecutiveSubject
from jason.tasks import minutes_draft as md

DAY = "2099-10-07"
# The agenda's executive items: each names a made-up member, party, case, or unit.
EXECUTIVE_ITEMS = ("Lawsuit v. Quincy Zebulon 24CV000123", "Payment plan for Unit 999 (Xavier Yarrow)",
                   "Garage door contract with Acme Example Co", "Quentin Vexley request", "Wobblefrotz matter")
PARTICULARS = ("Quincy", "Zebulon", "24CV000123", "999", "Xavier", "Yarrow", "Garage", "Acme", "Quentin", "Vexley",
               "Wobblefrotz")


class _Board:
    def quorum(self, in_office):
        return in_office // 2 + 1


COMMUNITY = SimpleNamespace(meeting_schedule=lambda: None, agenda_link_rules=lambda: (), directors=lambda: ["Ana Example"],
                            board=lambda: _Board())


def _heading(text, level):
    return {"paragraph": {"paragraphStyle": {"namedStyleType": f"HEADING_{level}"},
                          "elements": [{"textRun": {"content": text + "\n"}}]}}


def _data(tmp_path: Path) -> Path:
    folder = "meetings/2099-10-07-made-up"
    zoom = tmp_path / "zoom"
    (zoom / folder).mkdir(parents=True)
    (zoom / "meetings.json").write_text(json.dumps({"meetings": [
        {"date": DAY, "folder": folder, "kind": "board", "uuid": "made-up-uuid", "start": f"{DAY}T19:00:00-07:00",
         "topic": "Regular Meeting of the Board of Directors", "duration": 3600}]}), encoding="utf-8")
    (zoom / folder / "transcript.txt").write_text("[7:00 PM] Ana Example: I call the meeting to order.\n", encoding="utf-8")
    content = [_heading("Call to order", 4), _heading("Roof repair proposal", 4), _heading("Adjourn to Executive Session", 4),
               *(_heading(t, 5) for t in EXECUTIVE_ITEMS), _heading("Adjournment", 4)]
    docs = tmp_path / "meetings" / "agenda-docs"
    docs.mkdir(parents=True)
    (docs / "agenda.json").write_text(json.dumps({"title": f"Board Agenda {DAY}", "body": {"content": content}}),
                                      encoding="utf-8")
    # The agenda plan names one matter's 4935 subject; its board item's title is the agenda's words for it.
    (tmp_path / "meetings" / f"plan-{DAY}.json").write_text(json.dumps({"items": {"vexley": {"subject": "member_discipline"}}}),
                                                            encoding="utf-8")
    (tmp_path / "board").mkdir()
    (tmp_path / "board" / "items.json").write_text(json.dumps({"items": [
        {"id": "vexley", "title": "Quentin Vexley request", "summary": "", "ask": "", "category": "governance"}]}),
        encoding="utf-8")
    return tmp_path


def test_the_model_gets_each_executive_item_only_by_its_4935_subject(tmp_path):
    record = md.meeting_record(_data(tmp_path), COMMUNITY, date.fromisoformat(DAY))
    assert record["executive"] == [
        "On the agenda for executive session: litigation, a member's payment of assessments, matters relating to the "
        "formation of contracts with third parties and member discipline (Civil Code 4935(a), (b), (c)).",
        md.SUBJECT_NOT_ON_RECORD + "."]
    assert record["executiveSources"] == {md.PLAN: 1, md.WORDING: 3, md.NOT_NAMED: 1}
    assert "Roof repair proposal" in record["items"] and not any("Zebulon" in i for i in record["items"])
    text = md.prompt(date.fromisoformat(DAY), {**record, "quorum": md.quorum_check(record, COMMUNITY)})
    for word in PARTICULARS:
        assert word.casefold() not in text.casefold(), word
    assert md.SUBJECT_NOT_ON_RECORD in text and "write exactly" in text


def test_a_planned_subject_wins_and_an_unclassified_item_is_a_blank():
    planned = [("Quentin Vexley request", ExecutiveSubject.DISCIPLINE), ("Other planned item", ExecutiveSubject.PERSONNEL)]
    found = md.executive_subjects(["Quentin Vexley request", "Legal Matters", "Wobblefrotz matter",
                                   "Other matters Civil Code Section 4935(a) permits in executive session"], planned)
    assert found == [(ExecutiveSubject.DISCIPLINE, md.PLAN), (ExecutiveSubject.LITIGATION, md.WORDING),
                     (None, md.NOT_NAMED), (None, md.NOT_NAMED)]
    # Two planned items whose titles the agenda's words contain, with different subjects: not the plan's to say.
    both = [("Vexley", ExecutiveSubject.DISCIPLINE), ("Quentin", ExecutiveSubject.PERSONNEL)]
    assert md.executive_subjects(["Quentin Vexley request"], both) == [(None, md.NOT_NAMED)]
    assert md.executive_agenda_notes([(None, md.NOT_NAMED)] * 2) == [md.SUBJECT_NOT_ON_RECORD + " (2 agenda items)."]


def test_the_particular_words_are_the_names_not_the_subjects():
    words = md.particular_words(list(EXECUTIVE_ITEMS) + ["Delinquencies", "Legal Matters"])
    assert {"zebulon", "quincy", "24cv000123", "999", "xavier", "vexley", "wobblefrotz"} <= set(words)
    assert not {"lawsuit", "payment", "plan", "contract", "matter", "legal", "delinquencies", "unit"} & set(words)


def test_recheck_lists_a_line_that_names_an_executive_item(tmp_path):
    data = _data(tmp_path)
    draft = data / "board" / f"minutes-draft-{DAY}.md"
    draft.write_text("\n".join([
        "# DRAFT Minutes of 10/7/99", "", "_Drafted by jason._", "",
        "## Executive session", "", "The board discussed the lawsuit brought by Quincy Zebulon.", "",
        "## Adjournment", "", "The board adjourned to executive session at 8:15 PM to discuss litigation (Civil Code 4935(a)).",
        ""]), encoding="utf-8")
    found = md.recheck(data, COMMUNITY, date.fromisoformat(DAY))
    assert found["executiveParticulars"] == ["The board discussed the lawsuit brought by Quincy Zebulon."]
    block = "\n".join(md.check_lines(found))
    assert "1 line(s) about the executive session use the agenda's own words" in block
    assert "1 from the agenda plan, 3 read by jason" in block and "1 not on record" in block
    assert "Zebulon" not in block                    # the checks count the lines; they never quote them
    assert "## jason's checks" in draft.read_text(encoding="utf-8")


def test_the_general_subjects_are_not_flagged():
    record = {"directors": [], "attendance": [], "executiveWords": ["zebulon"]}
    text = "## Executive session\n\nDelinquencies and legal matters.\n"
    found = md.checks(record, text, SimpleNamespace(board=lambda: None))
    assert found["executiveParticulars"] == [] and found["confidential"] == []


def test_draft_gives_the_model_no_executive_item_words(tmp_path):
    data = _data(tmp_path)
    asked: list[str] = []

    def ask(prompt, schema):
        asked.append(prompt)
        return {}

    result = md.draft(data, COMMUNITY, date.fromisoformat(DAY), ask=ask)
    assert Path(result["file"]).is_file() and len(asked) == 2
    for word in PARTICULARS:
        assert word.casefold() not in asked[0].casefold(), word
