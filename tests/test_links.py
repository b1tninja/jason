"""Links in letters, forms, and emails: statute citations, web addresses, and email addresses, without changing what
prints."""

from jason.community.links import link_pdf, linkify, pdf_targets, statute_url


def test_citations_addresses_and_emails_become_links_and_existing_links_stand():
    text = ('<p>By law (Civil Code §4041(b)(2)(A); CIV 5220) answer at https://app.payhoa.com/app/forms/114478. '
            'Write hoa@mystiquecommunity.com or <a href="mailto:x@y.org">x@y.org</a>.</p>')
    out = linkify(text, subject="Owner Information Form 2027")
    assert f'href="{statute_url("CIV", "4041").replace("&", "&amp;")}">Civil Code §4041(b)(2)(A)</a>' in out
    assert ">CIV 5220</a>" in out
    assert '<a href="https://app.payhoa.com/app/forms/114478">https://app.payhoa.com/app/forms/114478</a>.' in out
    assert 'mailto:hoa@mystiquecommunity.com?subject=Owner%20Information%20Form%202027' in out
    assert out.count("x@y.org") == 2 and 'href="mailto:x@y.org"' in out          # the template's own link stands
    assert linkify(out) == linkify(linkify(out))                                     # linking twice changes nothing
    assert "<p>" in out and out.replace("<a ", "").count("<p") == 1                 # the text itself is unchanged


def test_a_pdf_gets_links_over_what_it_prints(tmp_path):
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "Under Civil Code 4041, email hoa@mystiquecommunity.com.", fontsize=11)
    doc.save(tmp_path / "a.pdf")
    assert link_pdf(tmp_path / "a.pdf", subject="Form") == 2
    links = [l["uri"] for l in pymupdf.open(tmp_path / "a.pdf")[0].get_links()]
    assert any("sectionNum=4041" in u for u in links) and "mailto:hoa@mystiquecommunity.com?subject=Form" in links
    assert link_pdf(tmp_path / "a.pdf") == 0                                         # already linked
    assert [t for t, _ in pdf_targets("see Corporations Code 7231")] == ["Corporations Code 7231"]


def test_help_tokens_name_the_vendors_own_guides_and_report_unknown_ones():
    from jason.community import mystique
    from jason.community.links import fill_help_tokens

    text, missing = fill_help_tokens("Update it ({HELP_STEPS:update-contact}; {HELP:update-contact}). {HELP:nope}",
                                     mystique().help_articles())
    assert "Account Settings, then User Settings" in text
    assert '>How To Update Contact Information</a>' in text and "articles/3443969" in text
    assert missing == ["nope"] and "{HELP:nope}" in text
