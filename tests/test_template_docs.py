"""PayHOA broadcast templates as Google Docs: the Doc's body as composer HTML, and who changed what since the last sync."""

import json

from jason.google.docs_html import document_html
from jason.google.drive import GOOGLE_DOC_MIME_TYPE, GoogleDrive
from jason.tasks.template_docs import (Action, composer_html, doc_name, import_html, plan, record, sha, subject_of,
                                       template_sha)


def _run(text, **style):
    return {"textRun": {"content": text, "textStyle": style}}


def _para(*runs, bullet=None, named="NORMAL_TEXT"):
    paragraph = {"elements": list(runs), "paragraphStyle": {"namedStyleType": named}}
    if bullet:
        paragraph["bullet"] = bullet
    return {"paragraph": paragraph}


DOC = {
    "title": "PayHOA - Notice",
    "tabs": [{"documentTab": {
        "lists": {"b": {"listProperties": {"nestingLevels": [{"glyphSymbol": "●"}, {"glyphSymbol": "○"}]}},
                  "n": {"listProperties": {"nestingLevels": [{"glyphType": "DECIMAL"}]}}},
        "body": {"content": [
            _para(_run("\n")),
            _para(_run("Dear {first name},\n")),
            _para(_run("What we insure\n"), named="HEADING_2"),
            _para(_run("Master", bold=True), _run(" policy & more\n")),
            _para(_run("Umbrella\n"), bullet={"listId": "b"}),
            _para(_run("Federal\n"), bullet={"listId": "b", "nestingLevel": 1}),
            _para(_run("Crime\n"), bullet={"listId": "b"}),
            _para(_run("Register at "), _run("eoidirect", link={"url": "https://www.eoidirect.com/"}, underline=True),
                  _run("\n"), bullet={"listId": "n"}),
            _para(_run("Thank you,\u000bBoard\n")),
            _para(_run("\n")),
            _para(_run("\n")),
        ]},
    }}],
}


def test_document_html_is_rich_composer_html():
    assert document_html(DOC).splitlines() == [
        "<p>Dear {first name},</p>",
        "<h2>What we insure</h2>",          # Heading 2 keeps its level
        "<p><strong>Master</strong> policy &amp; more</p>",
        "<ul>",
        "<li>Umbrella",
        "<ul>",
        "<li>Federal</li></ul></li>",
        "<li>Crime</li></ul>",
        "<ol>",
        '<li>Register at <a href="https://www.eoidirect.com/">eoidirect</a></li></ol>',
        "<p>Thank you,<br>Board</p>",
    ]


def test_tables_rules_and_strikethrough_come_through():
    table_doc = {"body": {"content": [
        {"table": {"tableRows": [
            {"tableCells": [{"content": [_para(_run("Building\n", bold=True))]}, {"content": [_para(_run("Limit\n", bold=True))]}]},
            {"tableCells": [{"content": [_para(_run("3\n"))]}, {"content": [_para(_run("$3,000,000\n"))]}]},
        ]}},
        {"paragraph": {"elements": [{"horizontalRule": {}}, _run("\n")]}},
        _para(_run("old", strikethrough=True), _run(" new\n")),
    ]}}
    assert document_html(table_doc).splitlines() == [
        "<table>",
        "<tr><th>Building</th><th>Limit</th></tr>",
        "<tr><td>3</td><td>$3,000,000</td></tr></table>",
        "<hr>",
        "<p><s>old</s> new</p>",
    ]


def test_the_first_form_is_kept_for_the_stored_hashes():
    got = document_html(DOC, rich=False)
    assert got.splitlines() == [
        "<p>Dear {first name},</p>",
        "<p><strong>What we insure</strong></p>",
        "<p><strong>Master</strong> policy &amp; more</p>",
        "<ul>",
        "<li>Umbrella",
        "<ul>",
        "<li>Federal</li>",
        "</ul></li>",
        "<li>Crime</li>",
        "</ul>",
        "<ol>",
        '<li>Register at <a href="https://www.eoidirect.com/">eoidirect</a></li>',
        "</ol>",
        "<p>Thank you,<br>Board</p>",
    ]


def test_placeholders_round_trip():
    message = '<p>Hi <span class="placeholder">{first name}</span>, {unit}</p>'
    assert b"Hi {first name}, {unit}" in import_html(message)
    assert composer_html("<p>Hi {first name}, {unit}</p>") == message


def test_names():
    row = {"id": 13417, "subject": "Notice of  Change (Civ. 5810)"}
    assert doc_name(row) == "PayHOA - Notice of Change (Civ. 5810)"
    assert subject_of(doc_name(row)) == "Notice of Change (Civ. 5810)"


TEMPLATE = {"id": 1, "subject": "S", "message": "<p>a</p>", "updatedAt": "2025-09-26T01:14:52Z",
            "attachments": [{"id": 9, "fileName": "x.pdf", "path": "Email Attachments/x.pdf"}]}


def _state(doc_sha="d1"):
    return {"1": record(TEMPLATE, "DOC", doc_sha)}


def test_plan_covers_each_case():
    assert plan([TEMPLATE], {}, {})[0].action is Action.CREATE
    assert plan([TEMPLATE], _state(), {"DOC": "d1"})[0].action is Action.UNCHANGED
    assert plan([TEMPLATE], _state(), {"DOC": "d2"})[0].action is Action.DOC_AHEAD
    changed = {**TEMPLATE, "message": "<p>b</p>"}
    assert plan([changed], _state(), {"DOC": "d1"})[0].action is Action.UPDATE
    assert plan([changed], _state(), {"DOC": "d2"})[0].action is Action.CONFLICT
    assert plan([changed], _state(), {"DOC": None})[0].action is Action.CREATE        # trashed: made again
    gone = plan([{**TEMPLATE, "deletedAt": "2026-01-01"}], _state(), {"DOC": "d1"})
    assert [s.action for s in gone] == [Action.DELETED]


def test_a_new_attachment_is_a_template_change():
    more = {**TEMPLATE, "attachments": TEMPLATE["attachments"] + [{"id": 10}]}
    assert template_sha(more) != template_sha(TEMPLATE)
    assert sha("x") == sha("x")


class _Http:
    def __init__(self):
        self.calls = []

    def post(self, url, *, headers=None, content=None, **kwargs):
        import httpx
        self.calls.append((url, content))
        return httpx.Response(200, json={"id": "NEWDOC"}, request=httpx.Request("POST", url))


def test_upload_bytes_imports_html_as_a_doc_with_its_property():
    drive = GoogleDrive("token", http=_Http())
    doc_id = drive.upload_bytes("PayHOA - S", b"<p>a</p>", mime_type="text/html", parent_id="F",
                                convert_to=GOOGLE_DOC_MIME_TYPE, description="d", app_properties={"jason_payhoa_template": "1"})
    assert doc_id == "NEWDOC"
    metadata = json.loads(drive._http.calls[0][1].split(b"\r\n\r\n", 1)[1].split(b"\r\n", 1)[0])
    assert metadata == {"name": "PayHOA - S", "parents": ["F"], "mimeType": GOOGLE_DOC_MIME_TYPE, "description": "d",
                        "appProperties": {"jason_payhoa_template": "1"}}


def test_highlights_find_placeholders_and_fields_at_utf16_indexes():
    from jason.tasks.template_docs import FIELD_COLOR, PLACEHOLDER_COLOR, highlight_requests

    doc = {"body": {"content": [
        {"paragraph": {"elements": [{"startIndex": 1, "textRun": {"content": "\U0001F3E0 Hi {first name}, Building [BUILDING].\n"}}]}},
        {"table": {"tableRows": [{"tableCells": [{"content": [
            {"paragraph": {"elements": [{"startIndex": 60, "textRun": {"content": "[POLICY NUMBER]\n"}}]}}]}]}]}},
    ]}}
    ranges = [(r["updateTextStyle"]["range"]["startIndex"], r["updateTextStyle"]["range"]["endIndex"],
               r["updateTextStyle"]["textStyle"]["backgroundColor"]["color"]["rgbColor"]) for r in highlight_requests(doc)]
    # the house emoji is two UTF-16 units, so "{first name}" starts at 1 + 2 + 4 = 7
    assert ranges == [(7, 19, PLACEHOLDER_COLOR), (30, 40, FIELD_COLOR), (60, 75, FIELD_COLOR)]


def test_the_header_is_replaced_in_small_grey_type():
    from jason.tasks.template_docs import header_requests, header_text

    text = header_text({"id": 9087, "subject": "Flood", "attachments": [{"fileName": "FLOOD POLICY 26-27 BLDG 3.pdf"}]})
    assert "PayHOA template 9087" in text and "FLOOD POLICY 26-27 BLDG 3.pdf" in text and "not part of the email" in text
    doc = {"headers": {"h1": {"content": [{"endIndex": 12}]}}}
    requests = header_requests(doc, "h1", text)
    assert requests[0] == {"deleteContentRange": {"range": {"segmentId": "h1", "startIndex": 0, "endIndex": 11}}}
    assert requests[1]["insertText"]["location"] == {"segmentId": "h1", "index": 0}
    assert requests[2]["updateTextStyle"]["textStyle"]["fontSize"] == {"magnitude": 8, "unit": "PT"}
