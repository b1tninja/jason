"""A form's style on paper and on screen (``FormStyle``): writing lines with room above them in pale ink, in the Doc and
the HTML; fillable fields that cover that room and print typed answers at the style's size; the lint that holds a
built form to it."""

from dataclasses import replace

from jason.community.forms import FormStyle


def test_the_doc_gives_a_writing_line_room_and_pale_ink_and_a_signature_line_pale_blanks():
    from jason.google.docs_markdown import REPORT, markdown_requests

    style = replace(REPORT, write_above=9, write_ink=(0.6, 0.6, 0.6))
    reqs = markdown_requests(["**1. Owner name(s)**", "_" * 60, "**Signature of owner**  " + "_" * 34], 1, style)
    paras = [r["updateParagraphStyle"] for r in reqs if "updateParagraphStyle" in r]
    above = [p["paragraphStyle"]["spaceAbove"]["magnitude"] for p in paras
             if "spaceAbove" in p["paragraphStyle"] and p["paragraphStyle"]["spaceAbove"]["magnitude"]]
    # the room is the paragraph above's space below (a title's 6) plus this one's space above: 9 either way
    assert above == [3.0, 9.0]                       # the line under the title; the signature under the line
    pale = [r["updateTextStyle"] for r in reqs if "updateTextStyle" in r
            and r["updateTextStyle"]["textStyle"].get("foregroundColor", {}).get("color", {}).get("rgbColor", {}).get("red") == 0.6]
    assert len(pale) == 2
    blank = pale[-1]["range"]
    assert blank["endIndex"] - blank["startIndex"] == 34              # only the signature's blank, not its label
    plain = markdown_requests(["_" * 60], 1, REPORT)                 # a style without one leaves lines as they were
    assert not any("spaceAbove" in r.get("updateParagraphStyle", {}).get("paragraphStyle", {}) and
                   r["updateParagraphStyle"]["paragraphStyle"]["spaceAbove"]["magnitude"] for r in plain)


def test_the_html_form_draws_the_style():
    from jason.community.form_render import paper_html
    from jason.community.spec import spec_module

    form = replace(spec_module("forms").OWNER_INFO, style=FormStyle(write_height=25.0, line_gray=0.5))
    html = paper_html(form)
    assert ".form .line{margin:12pt 0 0;color:rgb(128,128,128)}" in html
    assert "<span class='blank'>" in html


def test_a_typed_field_sits_on_its_rule_and_the_scan_reads_the_whole_writing_room(tmp_path):
    """A viewer centres a single-line field's text, so the field is placed for its baseline to sit just above the
    rule (fillable.field_geometry); a hand writes in the whole room above the rule, so the box the scan reader reads
    reaches up the form's writing height."""
    import pymupdf

    from jason.community.fillable import field_geometry, make_fillable
    from jason.community.form_layout import read_layout
    from jason.community.forms import FormQuestion, FormTemplate, FormKey

    form = FormTemplate(FormKey.OWNER_INFO, "t", "", "", (FormQuestion("Owner name(s)", key="owner-names"),),
                        signature="", style=FormStyle(write_height=26.0, typed_size=11.0))
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "1. Owner name(s)", fontname="hebo", fontsize=11)
    page.insert_text((72, 140), "_" * 50, fontsize=11)
    doc.save(tmp_path / "f.pdf")
    make_fillable(tmp_path / "f.pdf", form=form)
    height, below = field_geometry(11.0)
    with pymupdf.open(tmp_path / "f.pdf") as done:
        w = next(iter(done[0].widgets()))
        rule = w.rect.y1 - below
        assert round(w.rect.height, 1) == height and w.text_fontsize == 11 and 138 < rule < 143
    box = read_layout(tmp_path / "f.pdf", form).fields[0]
    assert box.rect[3] - box.rect[1] >= 26.0 and box.rect[1] > 100              # the room, not the title above it


def test_the_lint_holds_a_built_form_to_its_style(tmp_path):
    import pymupdf

    from jason.community.form_layout import FieldBox, FormLayout
    from jason.community.spec import spec_module
    from jason.tasks.form_fuzz import lint

    form = spec_module("forms").OWNER_INFO
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 140), "_" * 50, fontsize=11)                 # a black writing line
    page.insert_text((72, 200), "Owner name", fontname="cour", fontsize=11)
    doc.save(tmp_path / "f.pdf")
    layout = FormLayout("owner-info", fields=[FieldBox("owner-names", "text", 0, (72, 123, 400, 140))])
    kinds = {f.kind for f in lint(tmp_path / "f.pdf", layout, form)}
    assert {"writing lines dark", "monospaced type", "writing space short"} <= kinds


def test_an_address_is_written_in_its_parts_and_read_back_whole():
    from jason.community.fillable import _part_names
    from jason.community.forms import FormQuestion, ReadAs
    from jason.community.pdf_fields import join_lines, split_lines

    q = FormQuestion("Mailing address", lines=2, key="mailing-address", reads=ReadAs.ADDRESS,
                     same_as="Same as my unit address")
    assert q.in_parts and q.same_as_field == "mailing-address.same-as-my-unit-address"
    assert _part_names(q, q.field, [1, 3]) == [[("mailing-address", "street address, with apt, suite, or PMB")],
                                               [("mailing-address#city", "city"), ("mailing-address#state", "state"),
                                                ("mailing-address#zip", "ZIP")]]
    names = {"a", "a#city", "a#state", "a#zip"}
    parts = split_lines({"a": "12 Elm St, Apt 2, Davis, CA 95616"}, names)
    assert parts == {"a": "12 Elm St, Apt 2", "a#city": "Davis", "a#state": "CA", "a#zip": "95616"}
    assert join_lines(parts)["a"] == "12 Elm St, Apt 2\nDavis, CA 95616"
    assert split_lines({"a": "not an address"}, names) == {"a": "not an address"}           # left whole for a person
    assert join_lines({"a": "", "a#city": "", "a#state": "", "a#zip": ""})["a"] == ""
    assert split_lines({"a": "12 Elm St, Davis, CA 95616"}, {"a", "a#2"}) == {"a": "12 Elm St", "a#2": "Davis, CA 95616"}
