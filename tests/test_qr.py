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
