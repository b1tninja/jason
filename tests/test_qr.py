"""QR codes for links on paper: made only from links, always printed with the link, and a missing link shown, never
hidden."""

import argparse

import pytest

from jason.community.qr import fill_qr_tokens, is_link, qr_block, qr_png, qr_svg, qr_tokens


def test_only_links_are_encoded():
    assert is_link("https://app.payhoa.com/app/forms/1") and is_link("mailto:hoa@example.com") and is_link("tel:+19165550100")
    assert not is_link("[FORM LINK]") and not is_link("") and not is_link("see the website")
    with pytest.raises(ValueError):
        qr_svg("[FORM LINK]")


def test_a_code_is_svg_for_pages_and_png_for_pasting(tmp_path):
    svg = qr_svg("https://www.example.com/", title="Scan me")
    assert svg.startswith("<svg") and "viewBox" in svg and 'width="' not in svg.split(">")[0]   # the page sets the size
    png = qr_png("https://www.example.com/", tmp_path / "code.png")
    assert png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_the_block_prints_the_link_beside_the_code():
    block = qr_block("https://www.example.com/?a=1&b=2", label="Scan to join")
    assert "<svg" in block and "Scan to join" in block and "https://www.example.com/?a=1&amp;b=2" in block


def test_tokens_become_codes_or_visible_markers():
    text = "<p>Answer online.</p>{QR:OWNER_FORM_LINK}<p>Join.</p>{QR:MEETING_LINK}"
    assert qr_tokens(text) == ["OWNER_FORM_LINK", "MEETING_LINK"]
    out, missing = fill_qr_tokens(text, {"OWNER_FORM_LINK": "https://app.payhoa.com/f", "MEETING_LINK": "[ZOOM LINK]"},
                                  labels={"OWNER_FORM_LINK": "Scan to answer"})
    assert missing == ["MEETING_LINK"] and out.count("<svg") == 1 and "Scan to answer" in out
    assert "[QR code: MEETING_LINK has no link yet]" in out and out.count("<style>") == 1
    plain, none = fill_qr_tokens("<p>No codes.</p>", {})
    assert plain == "<p>No codes.</p>" and none == []                          # no style added without a code


def test_the_owner_letter_asks_for_its_link_until_it_has_one(tmp_path):
    from jason.community import mystique
    from jason.tasks.packets import fill_letter, template_tokens

    assert "OWNER_FORM_LINK" in template_tokens(mystique().packet("owner-information"))
    body, left = fill_letter("letter:owner-information-cover.html", {"OWNER_FORM_LINK": "[FORM LINK]"})
    assert "OWNER_FORM_LINK" in left and "has no link yet" in body
    body, left = fill_letter("letter:owner-information-cover.html", {"OWNER_FORM_LINK": "https://app.payhoa.com/f"})
    assert "OWNER_FORM_LINK" not in left and "<svg" in body and "Scan to answer online in PayHOA" in body


def test_jason_qr_writes_png_or_svg(tmp_path):
    from jason.commands.qr import cmd_qr

    for name in ("code.png", "code.svg"):
        args = argparse.Namespace(link="https://www.example.com/", out=str(tmp_path / name), scale=8, env=None)
        assert cmd_qr(args) == 0 and (tmp_path / name).stat().st_size > 100
    assert cmd_qr(argparse.Namespace(link="not a link", out=None, scale=8, env=None)) == 2


# --- Reading the codes a document prints (ingestion keeps them as metadata) -------------------------------------------

zxingcpp = pytest.importorskip("zxingcpp")


def _pdf_with_code(path, link, page=2):
    import pymupdf

    png = qr_png(link, path.with_suffix(".png"), scale=6)
    document = pymupdf.open()
    for n in range(1, page + 1):
        sheet = document.new_page()
        sheet.insert_text((72, 72), f"Page {n} of an inspection report")
        if n == page:
            sheet.insert_image(pymupdf.Rect(300, 400, 500, 600), filename=str(png))
    document.save(path)
    return path


def test_a_code_on_a_pdf_page_is_decoded_with_its_page_and_host(tmp_path):
    from jason.community.qr_read import read_codes

    link = "https://reports.example.com/#/0b1c2d3e"
    found = read_codes(_pdf_with_code(tmp_path / "report.pdf", link))
    assert [(c.text, c.page, c.link, c.host) for c in found] == [(link, 2, True, "reports.example.com")]


def test_an_image_is_read_and_a_page_without_a_code_gives_none(tmp_path):
    from jason.community.qr_read import read_codes

    png = qr_png("mailto:hoa@example.com", tmp_path / "code.png", scale=6)
    assert [c.text for c in read_codes(png)] == ["mailto:hoa@example.com"]
    import pymupdf

    blank = pymupdf.open()
    blank.new_page().insert_text((72, 72), "No code here")
    blank.save(tmp_path / "plain.pdf")
    assert read_codes(tmp_path / "plain.pdf") == [] and read_codes(tmp_path / "missing.pdf") == []


def test_ingest_keeps_the_decoded_code_as_metadata_and_in_the_report(tmp_path):
    from jason.tasks import ingest

    path = _pdf_with_code(tmp_path / "report.pdf", "https://reports.example.com/#/abc", page=1)
    item = ingest.FileItem("file", str(path), "report.pdf", path, "a" * 64, path.stat().st_size, "application/pdf")
    assert ingest.read_codes(item, tmp_path)[0]["host"] == "reports.example.com"
    assert item.row()["codes"][0]["text"] == "https://reports.example.com/#/abc"
    assert (tmp_path / ingest.WORK / "codes" / f"{'a' * 64}.json").is_file()
    again = ingest.FileItem("file", str(path), "report.pdf", tmp_path / "gone.pdf", "a" * 64, 1, "application/pdf")
    assert ingest.read_codes(again, tmp_path) == item.codes                    # the second read comes from the cache


def test_a_secret_in_a_payload_is_masked_for_people_but_kept_whole_as_metadata():
    from jason.community.qr_read import redacted

    link = "https://example.zoom.us/j/83241700599?pwd=AbCd123&lang=en#frag"
    assert redacted(link) == "https://example.zoom.us/j/83241700599?pwd=***&lang=en#frag"
    assert redacted("https://www.example.com/?a=1&Token=xyz") == "https://www.example.com/?a=1&Token=***"
    assert redacted("https://app.example.com/sign-up/27889-x") == "https://app.example.com/sign-up/27889-x"
    assert redacted("") == ""


def test_a_zoom_link_names_its_meeting_and_the_index_may_not_know_it(tmp_path):
    import json
    from types import SimpleNamespace

    from jason.community.portal_links import identify_meeting
    from jason.tasks.ingest import unrecorded_meetings

    found = identify_meeting("https://us06web.zoom.us/j/81392024127?pwd=secret")
    assert found and (found.platform, found.id) == ("zoom", "81392024127") and "secret" not in str(found.as_dict())
    assert identify_meeting("https://example.com/j/81392024127") is None and identify_meeting("https://zoom.us/signin") is None
    codes = lambda link: [{"link": True, "text": link, "meeting": (identify_meeting(link) and identify_meeting(link).as_dict()) or {}}]
    items = [SimpleNamespace(rel="Agenda.pdf", codes=codes("https://us06web.zoom.us/j/81392024127")),
             SimpleNamespace(rel="Notice.pdf", codes=codes("https://us06web.zoom.us/j/88077490565")),
             SimpleNamespace(rel="Notice2.pdf", codes=codes("https://us06web.zoom.us/j/88077490565"))]
    assert unrecorded_meetings(items, tmp_path) == []                       # no Zoom index: nothing can be said
    (tmp_path / "zoom").mkdir()
    (tmp_path / "zoom" / "meetings.json").write_text(json.dumps({"syncedAt": "2026-10-01", "meetings": [{"meetingId": "81392024127"}]}), encoding="utf-8")
    assert unrecorded_meetings(items, tmp_path) == [{"meeting": "88077490565", "files": ["Notice.pdf", "Notice2.pdf"]}]
