"""Links in Docs (tabs, footers, footnotes, split runs, internal links, typed URLs) and in PDFs (anchors, headings)."""

from __future__ import annotations

from jason.community import mystique
from jason.community.agenda_links import LinkKind, Section, links_in_doc, links_in_pdf

RULES = mystique().agenda_link_rules()


def _para(style, *els, heading_id=""):
    ps = {"namedStyleType": style}
    if heading_id:
        ps["headingId"] = heading_id
    return {"paragraph": {"paragraphStyle": ps, "elements": list(els)}}


def _run(text, url="", heading=""):
    style = {"link": {"url": url}} if url else {"link": {"headingId": heading}} if heading else {}
    return {"textRun": {"content": text, "textStyle": style}}


DOC = {"tabs": [
    {"tabProperties": {"title": "Agenda"}, "documentTab": {
        "body": {"content": [
            _para("HEADING_4", _run("Adopt Resolutions"), heading_id="h.res"),
            _para("NORMAL_TEXT", _run("A", "https://docs.google.com/document/d/1tFeKdAMNE9KxBPEve4dK0000000000/edit"),
                  _run("genda", "https://docs.google.com/document/d/1tFeKdAMNE9KxBPEve4dK0000000000/edit"),
                  _run(" see https://www.davis-stirling.com/HTML-Files/civil-code-5855 today")),
            _para("HEADING_4", _run("Discussion")),
            _para("NORMAL_TEXT", _run("As in "), _run("the resolutions", heading="h.res"),
                  {"footnoteReference": {"footnoteId": "fn1"}},
                  {"dateElement": {"dateElementProperties": {"displayText": "Mar 19, 2026"}}}),
        ]},
        "footers": {"f1": {"content": [_para("NORMAL_TEXT", _run("Zoom", "https://us06web.zoom.us/j/81392024127"))]}},
        "footnotes": {"fn1": {"content": [_para("NORMAL_TEXT", _run("Nahrstedt", "https://law.justia.com/cases/x"))]}},
    }, "childTabs": [{"tabProperties": {"title": "Exhibits"}, "documentTab": {"body": {"content": [
        _para("HEADING_4", _run("Exhibit A")),
        _para("NORMAL_TEXT", {"richLink": {"richLinkProperties": {
            "title": "Reserve Study 2026.pdf", "uri": "https://drive.google.com/file/d/1ABCDEFGHIJKLMNOPQRSTUVWX/view"}}}),
    ]}}}]},
]}


def test_a_doc_gives_every_link_with_its_item_section_and_tab() -> None:
    links = links_in_doc(DOC, RULES)
    by = {(l.kind, l.section): l for l in links}
    agenda = by[(LinkKind.GOOGLE_DOC, Section.BODY)]
    assert agenda.text == "Agenda" and agenda.item == "Adopt Resolutions"             # one link, not two runs
    assert by[(LinkKind.LAW, Section.BODY)].url.endswith("civil-code-5855")            # a URL typed as text
    internal = by[(LinkKind.INTERNAL, Section.BODY)]
    assert internal.item == "Discussion" and internal.refers_to == "Adopt Resolutions"
    assert by[(LinkKind.ZOOM, Section.FOOTER)].item == ""                              # the whole Doc's
    assert by[(LinkKind.LAW, Section.FOOTNOTE)].item == "Discussion"                   # where it is referenced
    chip = by[(LinkKind.DRIVE_FILE, Section.BODY)]
    assert chip.tab == "Exhibits" and chip.item == "Exhibit A" and chip.target == "1ABCDEFGHIJKLMNOPQRSTUVWX"


def test_a_pdf_places_each_link_under_its_numbered_item_and_keeps_its_words(tmp_path) -> None:
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    y = 72
    rows = [("MYSTIQUE COMMUNITY ASSOCIATION", 20, True), ("I. Call to Order", 11, True),
            ("II. Treasurer's Report", 11, True), ("See: Treasurer's Report - 2025-11.pdf", 11, False),
            ("III. Proposals", 11, True), ("i. Roof Inspection", 11, False), ("Roof proposal.pdf", 11, True),
            ("IV. Adjourn", 11, True)]
    boxes = {}
    for text, size, bold in rows:
        page.insert_text((72, y), text, fontsize=size, fontname="hebo" if bold else "helv")
        boxes[text] = pymupdf.Rect(72, y - size, 400, y + 2)
        y += 24
    page.insert_link({"kind": pymupdf.LINK_URI, "from": boxes["See: Treasurer's Report - 2025-11.pdf"],
                      "uri": "https://drive.google.com/file/d/1TREASURERxxxxxxxxxxxxxxxx/view"})
    page.insert_link({"kind": pymupdf.LINK_URI, "from": boxes["Roof proposal.pdf"],
                      "uri": "https://drive.google.com/file/d/1ROOFxxxxxxxxxxxxxxxxxxxxx/view"})
    path = tmp_path / "agenda.pdf"
    doc.save(path)
    links = {l.target: l for l in links_in_pdf(path, RULES)}
    treasurer = links["1TREASURERxxxxxxxxxxxxxxxx"]
    assert treasurer.item == "II. Treasurer's Report" and "2025-11" in treasurer.text
    roof = links["1ROOFxxxxxxxxxxxxxxxxxxxxx"]
    assert roof.item == "III. Proposals" and roof.subitem == "i. Roof Inspection"      # a bold chip title heads nothing
