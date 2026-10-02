from jason.community.markdown_html import message_html, render


def test_one_markdown_source_becomes_the_email_body():
    body = render("Dear {first name},\n\n"
                  "Answer for {unit address} by **Friday**.\n\n"
                  "## Three ways\n\n"
                  "1. Sign in at [app.payhoa.com](https://app.payhoa.com).\n"
                  "2. Choose **Requests**.\n"
                  "   - a note under it\n"
                  "3. Submit.\n\n"
                  "![The steps](pics/steps.png){width=560}\n\n"
                  "- Email hoa@example.com.\n\n"
                  "Mail it to:\\\nMystique Community Association\\\nSacramento, CA 95814\n\n"
                  "==a note for whoever edits the Doc==\n")
    assert '<p>Dear <span class="placeholder">{first name}</span>,</p>' in body
    assert '<span class="placeholder">{unit address}</span> by <strong>Friday</strong>' in body
    assert "<h3>Three ways</h3>" in body
    assert ('<ol><li>Sign in at <a href="https://app.payhoa.com">app.payhoa.com</a>.</li><li>Choose <strong>Requests'
            '</strong>.<ul><li>a note under it</li></ul></li><li>Submit.</li></ol>') in body
    assert '<img src="pics/steps.png" alt="The steps" width="560">' in body
    assert '<a href="mailto:hoa@example.com">hoa@example.com</a>' in body
    assert "<p>Mail it to:<br>Mystique Community Association<br>Sacramento, CA 95814</p>" in body
    assert "<p>a note for whoever edits the Doc</p>" in body                      # the highlight is the Doc's only


def test_a_message_file_is_rendered_only_when_it_is_markdown():
    assert message_html("**hi**", ".md") == "<p><strong>hi</strong></p>"
    assert message_html("<p>**hi**</p>", ".html") == "<p>**hi**</p>"


def test_the_doc_from_markdown_links_citations_and_fills_help_as_the_email_does():
    from types import SimpleNamespace

    from jason.community.links import fill_help_markdown, link_citations_markdown

    text = link_citations_markdown("Under Civil Code §4041(a), see [Civil Code 5220](https://x) and `CIV 1`.")
    assert text.startswith("Under [Civil Code §4041(a)](https://leginfo.legislature.ca.gov/")   # the section's page
    assert "sectionNum=4041.), see [Civil Code 5220](https://x) and `CIV 1`." in text     # links and code untouched
    article = SimpleNamespace(key="request", title="How to Submit a Request", url="https://help/x", steps="click Requests")
    filled, missing = fill_help_markdown("Guide: {HELP:request} ({HELP_STEPS:request}); {HELP:nope}", [article])
    assert filled == "Guide: [How to Submit a Request](https://help/x) (click Requests); {HELP:nope}"
    assert missing == ["nope"]
