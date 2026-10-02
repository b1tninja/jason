from jason.google.docs_markdown import AGENDA, REPORT, Kind, find_paragraph, inline, parse, requests
from jason.tasks.letters import format_requests, paragraphs
from jason.community.templates import BODIES, CONTINUATION, TemplateKind


def test_inline_marks():
    spans = inline("**Background.** See [the report](https://x.test/r) and _the note_ ==keep or drop== {OWNER_NAME} a_b")
    assert [(s.text, s.bold, s.italic, s.link, s.highlight) for s in spans if s.bold or s.italic or s.link or s.highlight] == [
        ("Background.", True, False, "", False), ("the report", False, False, "https://x.test/r", False),
        ("the note", False, True, "", False), ("keep or drop", False, False, "", True)]
    assert "".join(s.text for s in spans).endswith("{OWNER_NAME} a_b")   # tokens and snake_case stay as written


def test_parse_kinds_and_nesting():
    paras = parse("# T\n\ntext\n1. **one** _(action)_\n   - note\n2. two\n> quoted\n---\n- a\n  - b")
    assert [(p.kind, p.level) for p in paras] == [(Kind.HEADING, 1), (Kind.TEXT, 0), (Kind.NUMBER, 0), (Kind.BULLET, 1),
                                                (Kind.NUMBER, 0), (Kind.QUOTE, 0), (Kind.BULLET, 0), (Kind.BULLET, 1)]


def test_lists_are_made_last_from_the_end_back_with_tabs_for_nesting():
    reqs = requests(parse("intro\n1. one\n   - sub\n2. two\nmid\n- a"), 1, AGENDA)
    assert reqs[0]["insertText"]["text"] == "intro\none\n\tsub\ntwo\nmid\na"
    lists = [r["createParagraphBullets"] for r in reqs if "createParagraphBullets" in r]
    assert [l["range"] for l in lists] == [{"startIndex": 24, "endIndex": 25}, {"startIndex": 7, "endIndex": 19}]
    assert lists[1]["bulletPreset"] == AGENDA.number_preset and lists[0]["bulletPreset"] == AGENDA.bullet_preset
    assert all("createParagraphBullets" in r for r in reqs[-2:])


def test_headings_and_segment():
    reqs = requests(parse("## Section"), 5, REPORT, segment_id="kix.h")
    style = next(r["updateParagraphStyle"] for r in reqs if r.get("updateParagraphStyle", {}).get("paragraphStyle", {}).get("namedStyleType") == "HEADING_2")
    assert style["range"] == {"startIndex": 5, "endIndex": 13, "segmentId": "kix.h"} and "borderBottom" in style["paragraphStyle"]


def test_letter_paragraphs_keep_the_signature_together():
    paras = paragraphs(BODIES[TemplateKind.HEARING_NOTICE])
    signed = next(k for k, p in enumerate(paras) if p.text == "Sincerely,")
    assert all(p.keep_with_next for p in paras[signed:-1]) and not paras[-1].keep_with_next
    assert any(s.bold and s.text == "Date:" for p in paras for s in p.spans)


def test_format_requests_header_and_footer_bold():
    doc = {"documentStyle": {"defaultHeaderId": "h"},
           "headers": {"h": {"content": [{"endIndex": 1, "paragraph": {"elements": [{"startIndex": 0, "textRun": {"content": "\n"}}]}}]}},
           "footers": {"f1": {"content": [{"paragraph": {"elements": [
               {"startIndex": 0, "textRun": {"content": "Mystique Community Association", "textStyle": {"bold": True}}},
               {"startIndex": 30, "textRun": {"content": " · addr\n"}}]}}]},
               "f2": {"content": [{"paragraph": {"elements": [{"startIndex": 0, "textRun": {"content": "Mystique Community Association · addr\n"}}]}}]}}}
    reqs = format_requests(doc, CONTINUATION[TemplateKind.HEARING_NOTICE])
    assert reqs[0]["insertText"]["location"] == {"segmentId": "h", "index": 0}
    assert {r["updateTextStyle"]["range"]["segmentId"] for r in reqs if r.get("updateTextStyle", {}).get("textStyle") == {"bold": True}} == {"f1", "f2"}


def test_a_page_break_line_starts_the_next_paragraph_on_a_new_page():
    paras = parse("first\n\\pagebreak\n\n## Next")
    assert [p.page_break for p in paras] == [False, True]
    styles = [r["updateParagraphStyle"]["paragraphStyle"] for r in requests(paras, 1, REPORT) if "updateParagraphStyle" in r]
    assert styles[0]["pageBreakBefore"] is False and any(s.get("pageBreakBefore") is True for s in styles[1:])


def test_inserted_text_leaves_any_inherited_list_and_keeps_form_lines():
    paras = parse("Sign below.\n \n________________\nSecretary\n---")
    assert [p.text for p in paras] == ["Sign below.", "", "________________", "Secretary"]    # the rule line is dropped
    reqs = requests(paras, 1, REPORT)
    assert reqs[1] == {"deleteParagraphBullets": {"range": {"startIndex": 1, "endIndex": 1 + len("Sign below.\n\n________________\nSecretary") + 1}}}


def test_find_paragraph():
    doc = {"body": {"content": [{"startIndex": 1, "endIndex": 16, "paragraph": {"elements": [{"textRun": {"content": "{AGENDA_ITEMS}\n"}}]}}]}}
    assert find_paragraph(doc, "{AGENDA_ITEMS}") == (1, 15)


def test_list_notes_lose_their_number_at_the_shifted_index():
    paras = parse("1. **Minutes**\n   See: minutes\n2. Proposals\n   - TaskForge\n      a note")
    assert [(p.kind, p.level) for p in paras] == [(Kind.NUMBER, 0), (Kind.LIST_NOTE, 0), (Kind.NUMBER, 0), (Kind.BULLET, 1),
                                                (Kind.LIST_NOTE, 1)]
    reqs = requests(paras, 1, AGENDA)
    assert reqs[0]["insertText"]["text"] == "Minutes\nSee: minutes\nProposals\n\tTaskForge\n\ta note"
    removed = [r["deleteParagraphBullets"]["range"] for r in reqs if "deleteParagraphBullets" in r][1:]   # after the whole-range reset
    # "See: minutes" at 9; "a note" was at 43 and moves back one for TaskForge's removed tab.
    assert removed == [{"startIndex": 9, "endIndex": 21}, {"startIndex": 42, "endIndex": 48}]


def test_an_email_address_is_a_mailto_link_and_a_written_link_is_left_alone():
    from jason.google.docs_markdown import inline

    spans = inline("Write to hoa@example.com, or [the board](mailto:board@example.com).")
    assert [(s.text, s.link) for s in spans if s.link] == [("hoa@example.com", "mailto:hoa@example.com"),
                                                          ("the board", "mailto:board@example.com")]
    assert not [s for s in inline("see https://x.example/a?to=b@c.example") if s.link.startswith("mailto:")]


def test_a_picture_line_is_a_centered_marker_with_its_file_alt_and_width():
    from jason.google.docs_markdown import Kind, parse, picture_markers, picture_requests

    paras = parse("Steps:\n\n![The Requests page](pics/steps.png){width=600}\n\n![Logo](logo.png)")
    pics = [p for p in paras if p.kind is Kind.PICTURE]
    assert [(p.picture, p.alt, p.width, p.align) for p in pics] == [("pics/steps.png", "The Requests page", 600, "CENTER"),
                                                                   ("logo.png", "Logo", 0, "CENTER")]
    assert pics[0].text == "[[picture pics/steps.png]]"
    doc = {"body": {"content": [{"paragraph": {"elements": [
        {"startIndex": 8, "textRun": {"content": "[[picture pics/steps.png]]\n"}}]}}]}}
    markers = picture_markers(doc)
    assert markers == [("pics/steps.png", 8, 34)]
    assert picture_requests(markers, {"pics/steps.png": "https://x/s"}, {"pics/steps.png": 600})[1] == {
        "insertInlineImage": {"uri": "https://x/s", "location": {"index": 8},
                              "objectSize": {"width": {"magnitude": 450.0, "unit": "PT"}}}}
