"""Letter templates: the {TOKEN} model, the body requests, and filling a copy (fake Drive and Docs)."""

from __future__ import annotations

from datetime import date

import pytest

from jason.community import mystique
from jason.community.templates import BODIES, Block, TemplateKind, tokens_in
from jason.tasks.letters import body_requests, fill_letter, hearing_values, parse_assignments
from jason.tasks.zoom import plan_hearing


def test_tokens_are_upper_case_words_in_single_braces() -> None:
    assert tokens_in("{DATE} to {OWNER_NAME}, {DATE}; {not} {X1}") == ("DATE", "OWNER_NAME", "X1")
    assert TemplateKind.from_slug("hearing-notice") is TemplateKind.HEARING_NOTICE
    with pytest.raises(ValueError):
        TemplateKind.from_slug("eviction")


def test_the_hearing_notice_carries_what_5855b_requires() -> None:
    tokens = mystique().document_template(TemplateKind.HEARING_NOTICE).tokens
    for need in ("HEARING_DATE", "HEARING_TIME", "ZOOM_LINK", "VIOLATION"):
        assert need in tokens
    text = "\n".join(line for _, line in BODIES[TemplateKind.HEARING_NOTICE])
    assert "right to attend the hearing and to address the Board" in text and "executive session if you ask" in text


def test_the_notices_state_the_law_as_amended_in_2025_and_drop_the_old_promises() -> None:
    hearing = "\n".join(line for _, line in BODIES[TemplateKind.HEARING_NOTICE])
    decision = "\n".join(line for _, line in BODIES[TemplateKind.DECISION_NOTICE])
    assert "{POSSIBLE_DISCIPLINE}" in hearing and "$100 per violation" in hearing and "5850(e)" in hearing
    assert "question any witness" in hearing and "reasonable accommodation" in hearing and "at no cost" in hearing
    assert "notified before any further fine" in hearing
    for gone in ("fifteen days", "15 days", "without further hearing", "Ironwood", "Legal action"):
        assert gone not in hearing and gone not in decision
    assert "5725(b)" in decision and "{FINDINGS}" in decision


def test_a_possible_suspension_needs_fifteen_days_notice() -> None:
    m = mystique()
    plan = plan_hearing(m, address="3030 Macon Dr", violation="x", today=date(2026, 10, 8), suspension=True)
    # October 8 + 15 days = October 23; the next third Tuesday is November 17.
    assert plan.start.date() == date(2026, 11, 17) and plan.notice_by == date(2026, 11, 2)
    late = plan_hearing(m, address="3030 Macon Dr", violation="x", on=date(2026, 10, 20), notice_on=date(2026, 10, 8), suspension=True)
    assert late.problems and "Corp 7341(c)" in late.problems[0]
    assert not plan_hearing(m, address="3030 Macon Dr", violation="x", on=date(2026, 10, 20), notice_on=date(2026, 10, 8)).problems


def test_the_body_is_replaced_and_styled_at_the_right_indexes() -> None:
    blocks = ((Block.BOLD, "Re: {X}"), (Block.HEADING, "Rights"), (Block.BULLET, "one"), (Block.BULLET, "two"), (Block.TEXT, "end"))
    reqs = body_requests(blocks, body_end=500)
    assert reqs[0] == {"deleteContentRange": {"range": {"startIndex": 1, "endIndex": 499}}}
    assert reqs[1]["insertText"]["text"] == "Re: {X}\nRights\none\ntwo\nend"
    bold = next(r for r in reqs if r.get("updateTextStyle", {}).get("textStyle") == {"bold": True})["updateTextStyle"]["range"]
    heading = next(r for r in reqs if r.get("updateParagraphStyle", {}).get("paragraphStyle", {}).get("namedStyleType") == "HEADING_3")
    heading = heading["updateParagraphStyle"]["range"]
    bullets = [r["createParagraphBullets"]["range"] for r in reqs if "createParagraphBullets" in r]
    assert bold == {"startIndex": 1, "endIndex": 8}          # "Re: {X}"
    assert heading == {"startIndex": 9, "endIndex": 16}      # "Rights" and its newline
    assert bullets == [{"startIndex": 16, "endIndex": 23}]   # "one\ntwo" as one list


class FakeDocs:
    def __init__(self, text: str) -> None:
        self.text, self.updates = text, []

    def get(self, doc_id: str) -> dict:
        return {"body": {"content": [{"paragraph": {"elements": [{"startIndex": 1, "textRun": {"content": self.text}}]}}]}}

    def batch_update(self, doc_id: str, requests: list[dict]) -> dict:
        self.updates.append(requests)
        for r in requests:
            if "replaceAllText" in r:
                self.text = self.text.replace(r["replaceAllText"]["containsText"]["text"], r["replaceAllText"]["replaceText"])
        return {}


class FakeDrive:
    def __init__(self) -> None:
        self.copies = []

    def copy(self, file_id: str, name: str, parent_id: str | None = None) -> str:
        self.copies.append((file_id, name, parent_id))
        return "new-doc"


def test_a_letter_is_a_filled_copy_that_lists_what_is_left() -> None:
    template = mystique().document_template(TemplateKind.HEARING_NOTICE)
    template = type(template)(**{**template.__dict__, "drive_id": "tmpl"})
    docs, drive = FakeDocs("Join: {ZOOM_LINK} {CURE}\nDear {OWNER_NAME}, {VIOLATION}"), FakeDrive()
    out = fill_letter(drive, docs, template, {"ZOOM_LINK": "https://us06web.zoom.us/j/1", "VIOLATION": "Trash", "NOPE": "x"},
                      name="Notice of Hearing - 3030 Macon Dr", folder_id="folder")
    assert drive.copies == [("tmpl", "Notice of Hearing - 3030 Macon Dr", "folder")]
    assert docs.text == "Join: https://us06web.zoom.us/j/1 \nDear {OWNER_NAME}, Trash"   # the optional CURE is removed
    assert out["unfilled"] == ["OWNER_NAME"] and out["ignored"] == ["NOPE"]
    link = docs.updates[-1][0]["updateTextStyle"]
    assert link["range"] == {"startIndex": 7, "endIndex": 7 + len("https://us06web.zoom.us/j/1")}
    assert link["textStyle"]["link"]["url"].endswith("/j/1")


def test_a_hearing_plan_fills_its_dates_and_zoom_details() -> None:
    plan = plan_hearing(mystique(), address="3030 Macon Dr", violation="Trash cans", on=date(2026, 10, 20))
    plan.zoom = {"id": 85550001111, "joinUrl": "https://us06web.zoom.us/j/85550001111", "passcode": "123456", "dialIn": ["+1 669 900 6833 (San Jose)"]}
    v = hearing_values(plan, city_state_zip="Sacramento, CA 95835", today=date(2026, 10, 1))
    assert v["DATE"] == "October 1, 2026" and v["HEARING_DATE"] == "Tuesday, October 20, 2026" and v["HEARING_TIME"] == "7:00 PM"
    assert v["ZOOM_MEETING_ID"] == "85550001111" and v["OWNER_NAME"] == "" and v["VIOLATION"] == "Trash cans"


def test_the_letterheads_sample_title_line_is_removed_from_the_header() -> None:
    from jason.tasks.letters import banner_requests

    def para(start: int, end: int, text: str) -> dict:
        return {"startIndex": start, "endIndex": end, "paragraph": {"elements": [{"textRun": {"content": text}}]}}

    doc = {"headers": {"h1": {"content": [para(0, 2, "\n"), para(2, 33, "MYSTIQUE COMMUNITY ASSOCIATION\n"), para(33, 44, "LETTERHEAD\n")]}}}
    assert banner_requests(doc) == [{"deleteContentRange": {"range": {"segmentId": "h1", "startIndex": 32, "endIndex": 43}}}]
    assert banner_requests({"headers": {"h1": {"content": [para(0, 5, "Name\n")]}}}) == []


def test_command_line_assignments() -> None:
    assert parse_assignments(["owner_name=A B", "{BODY}=line 1\\nline 2"]) == {"OWNER_NAME": "A B", "BODY": "line 1\nline 2"}
    with pytest.raises(ValueError):
        parse_assignments(["nothing"])
