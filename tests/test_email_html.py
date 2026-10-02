"""Template HTML in one email-safe form, whether it came from PayHOA's composer, a Doc, or a draft."""

from jason.community.email_html import email_tables, normalize, plain_text

# What PayHOA stored after a Doc was pasted into its composer (broadcast2.har, trimmed).
PASTED = (
    '<p>Hi <span class="placeholder">{first name}</span>,</p>\n'
    '<p dir="ltr">The policy</p>\n<ul>\n<li dir="ltr" aria-level="1">\n'
    '<p dir="ltr" role="presentation">Policy number: [POLICY NUMBER]</p>\n</li>\n'
    '<li dir="ltr" aria-level="1">\n<p dir="ltr" role="presentation">Deductible: [DEDUCTIBLE]</p>\n</li>\n</ul>\n'
    '<p dir="ltr">Thank you,</p>\n<p>&nbsp;</p>\n<p>&nbsp;</p>'
)


def test_composer_debris_is_removed():
    assert normalize(PASTED).splitlines() == [
        '<p>Hi <span class="placeholder">{first name}</span>,</p>',
        "<p>The policy</p>",
        "<ul>",
        "<li>Policy number: [POLICY NUMBER]</li>",
        "<li>Deductible: [DEDUCTIBLE]</li></ul>",
        "<p>Thank you,</p>",
    ]


def test_a_docs_export_becomes_tags():
    exported = ('<html><head><style>.c1{font-weight:700}</style></head><body>'
                '<h1>Notice</h1><p><span style="font-weight:700">Due</span> <span style="font-style:italic">now</span>'
                '<span style="text-decoration:line-through">old</span></p><div>Plain</div>'
                '<p><a href="javascript:alert(1)">bad</a> <a href="https://x.org">good</a></p><script>x()</script></body></html>')
    assert normalize(exported).splitlines() == [
        "<h2>Notice</h2>",
        "<p><strong>Due</strong> <em>now</em><s>old</s></p>",
        "<p>Plain</p>",
        '<p>bad <a href="https://x.org">good</a></p>',
    ]


def test_tables_keep_their_cells_and_get_email_borders():
    table = '<table class="x"><tbody><tr><th>Policy</th><td colspan="2" style="text-align:center;color:red">5010000092</td></tr></tbody></table>'
    clean = normalize(table)
    assert '<td colspan="2" style="text-align: center; color: red">5010000092</td>' in clean and "class" not in clean
    styled = email_tables(clean)
    assert '<table style="border-collapse' in styled and styled.count("border: 1px solid") == 2
    assert plain_text(clean) == "Policy | 5010000092"


def test_two_paragraphs_in_a_list_item_become_a_line_break_and_empty_runs_collapse():
    text = "<p>&nbsp;</p><p>A</p><p></p><p> </p><ul><li><p>one</p><p>two</p></li></ul><p>&nbsp;</p>"
    assert normalize(text).splitlines() == ["<p>A</p>", "<p>&nbsp;</p>", "<ul>", "<li>one<br>two</li></ul>"]


def test_the_letterhead_frames_a_body_once_and_strips_cleanly():
    from jason.community.email_html import Letterhead, strip_letterhead, with_letterhead

    lh = Letterhead("MYSTIQUE COMMUNITY ASSOCIATION", "https://img.example/logo.png", font="'Century Gothic', Arial, sans-serif",
                    footer="901 H St Ste 120, PMB 188, Sacramento, CA 95814")
    body = '<p>Dear <span class="placeholder">{first name}</span>,</p>\n<p>Text.</p>'
    framed = with_letterhead(body, lh)
    lines = framed.splitlines()
    assert lines[0] == '<p style="text-align: center"><img src="https://img.example/logo.png" alt="MYSTIQUE COMMUNITY ASSOCIATION" width="66" height="96"></p>'
    assert lines[1].startswith('<h2 style="text-align: center; font-family: \'Century Gothic\'')
    assert lines[-2:] == ["<hr>", '<p style="text-align: center; font-size: 12px; color: #666666">901 H St Ste 120, PMB 188, Sacramento, CA 95814</p>']
    assert with_letterhead(framed, lh) == framed                      # framing twice is framing once
    assert strip_letterhead(framed, lh) == (normalize(body), True)
    assert strip_letterhead(body, lh) == (normalize(body), False)
    moved = Letterhead(lh.name, "https://img.example/new-logo.png", footer=lh.footer)
    assert strip_letterhead(framed, moved)[0] == normalize(body)       # an older logo address is still recognized


def test_a_letterhead_without_a_logo_is_the_name_alone():
    from jason.community.email_html import Letterhead

    assert Letterhead("MYSTIQUE COMMUNITY ASSOCIATION").head() == [
        '<h2 style="text-align: center; font-family: Arial, sans-serif; letter-spacing: 1px">MYSTIQUE COMMUNITY ASSOCIATION</h2>']


def test_a_drafts_pictures_are_uploaded_once_and_linked(tmp_path):
    import pytest

    from jason.community.email_html import host_images, local_images

    (tmp_path / "pics").mkdir()
    (tmp_path / "pics" / "a.png").write_bytes(b"png")
    text = ('<p><img src="pics/a.png" alt="menu"></p><p><img src="pics/a.png"></p>'
            '<p><img src="https://core.payhoa.com/org-logo/1"></p>')
    assert local_images(text) == ["pics/a.png"]
    uploaded = []
    out = host_images(text, tmp_path, lambda p: uploaded.append(p.name) or "https://s3.example/a?x=1&y=2")
    assert uploaded == ["a.png"]
    assert out.count('src="https://s3.example/a?x=1&amp;y=2"') == 2 and "org-logo/1" in out
    with pytest.raises(FileNotFoundError):
        host_images('<img src="pics/missing.png">', tmp_path, lambda p: "")
