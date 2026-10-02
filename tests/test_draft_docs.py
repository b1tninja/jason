from jason.tasks.draft_docs import import_page, list_kinds, marker_ranges, numbering_requests, picture_requests


def _doc(content):
    return {"tabs": [{"documentTab": {"body": {"content": content}}}]}


def test_the_import_turns_pictures_into_markers_and_placeholders_into_text():
    page, pictures = import_page('<p>Dear <span class="placeholder">{first name}</span>,</p>'
                                 '<p><img src="pics/steps.png" alt="Steps" width="560"></p>'
                                 '<p><img src="https://example.com/logo.png"></p>')
    text = page.decode("utf-8")
    assert "Dear {first name}," in text and "[[picture pics/steps.png]]" in text
    assert "https://example.com/logo.png" in text                  # a web picture is Drive's to fetch
    assert pictures == [("pics/steps.png", 560)]


def test_each_marker_becomes_its_picture_last_first_at_the_drafts_width():
    doc = _doc([{"paragraph": {"elements": [
        {"startIndex": 1, "textRun": {"content": "See [[picture a.png]] and [[picture b.png]]\n"}}]}}])
    markers = marker_ranges(doc)
    assert [m[0] for m in markers] == ["a.png", "b.png"] and markers[0][1] == 5
    requests = picture_requests(markers, {"a.png": "https://x/a", "b.png": "https://x/b"}, {"a.png": 400})
    assert requests[1]["insertInlineImage"]["uri"] == "https://x/b"            # the later one first
    assert requests[3]["insertInlineImage"]["objectSize"]["width"]["magnitude"] == 300.0
    assert "objectSize" not in requests[1]["insertInlineImage"]


def test_a_numbered_list_is_numbered_again_after_the_import():
    assert list_kinds("<ol><li>a<ul><li>x</li></ul></li></ol><ul><li>b</li></ul>") == ["ol", "ul"]
    doc = _doc([
        {"startIndex": 1, "endIndex": 5, "paragraph": {"bullet": {"listId": "L1"}}},
        {"startIndex": 5, "endIndex": 9, "paragraph": {"bullet": {"listId": "L1"}}},
        {"startIndex": 9, "endIndex": 12, "paragraph": {"elements": []}},
        {"startIndex": 12, "endIndex": 15, "paragraph": {"bullet": {"listId": "L2"}}},
    ])
    requests = numbering_requests(doc, ["ol", "ul"])
    assert requests == [{"createParagraphBullets": {"range": {"startIndex": 1, "endIndex": 8},
                                                    "bulletPreset": "NUMBERED_DECIMAL_ALPHA_ROMAN"}}]
