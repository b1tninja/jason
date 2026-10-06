"""Forms: one definition, its paper and fillable PDF renderings, the PDF field primitives, and answers read back and
checked against the definition."""

from pathlib import Path
from urllib.parse import urlparse
from urllib.request import url2pathname

import pymupdf
import pytest

from jason.community.forms import FormAnswers, FormKey, FormQuestion, FormTemplate, QuestionKind, answer_rows, check

FORM = FormTemplate(
    key=FormKey.OWNER_INFO, title="Test form", authority="", description="Answer each question.",
    questions=(
        FormQuestion("Owner name(s)", key="owner-names"),
        FormQuestion("Deliver notices", QuestionKind.CHECKBOX, key="delivery", options=("By mail", "By email")),
        FormQuestion("Is your unit", QuestionKind.CHOICE, key="occupancy",
                     options=("Owner-occupied", "Rented out to a long-term tenant")),
        FormQuestion("Email address", QuestionKind.EMAIL, required=False, key="email"),
        FormQuestion("Move-in date", QuestionKind.DATE, required=False),
    ),
)


# -- the definition ---------------------------------------------------------------------------------------------------

def test_a_question_has_a_stable_field_and_finds_its_options_from_a_cut_label():
    q = FORM.question("occupancy")
    assert q is FORM.question("Is your unit") is FORM.question("3")
    assert FORM.question("Move-in date").field == "move-in-date"                      # a slug when no key is given
    assert FormQuestion("Legal representative (optional)").field == "legal-representative"
    assert q.option_for("rented-out-to-a") == "Rented out to a long-term tenant"     # a label that wrapped


def test_check_names_what_is_wrong_and_nothing_when_right():
    good = {"owner-names": "Pat", "delivery": ["By mail", "By email"], "occupancy": ["Owner-occupied"],
            "email": "pat@example.com", "move-in-date": "10/01/2026"}
    assert check(FORM, good) == []
    bad = {"delivery": ["By fax"], "occupancy": ["Owner-occupied", "Rented out to a long-term tenant"],
           "email": "pat at example", "move-in-date": "soon"}
    problems = check(FORM, bad)
    assert "Owner name(s): required, left blank" in problems
    assert any("not an option on the form: By fax" in p for p in problems)
    assert any("one choice asked, 2 given" in p for p in problems)
    assert any("not an email address" in p for p in problems) and any("not a date" in p for p in problems)
    phone = FormTemplate(FormKey.IDR, "", "", "", (FormQuestion("Phone", QuestionKind.PHONE),))
    assert check(phone, {"phone": "(916) 555-0100"}) == [] and check(phone, {"phone": "555-01"})


def test_answer_rows_are_in_question_order_with_their_problems():
    header, rows = answer_rows(FORM, [FormAnswers(FORM.key, {"owner-names": "Pat", "delivery": ["By mail"],
                                                             "occupancy": ["Owner-occupied"]}, source="a.pdf")])
    assert header[:4] == ["source", "Owner name(s)", "Deliver notices", "Is your unit"] and header[-1] == "problems"
    assert rows[0][:4] == ["a.pdf", "Pat", "By mail", "Owner-occupied"] and rows[0][-1] == ""


def test_google_forms_get_a_date_question_and_text_for_email():
    from jason.google.forms import form_requests, question_item

    assert "dateQuestion" in question_item(FORM.question("Move-in date"))["questionItem"]["question"]
    assert question_item(FORM.question("email"))["questionItem"]["question"]["textQuestion"] == {"paragraph": False}
    assert question_item(FORM.question("occupancy"))["questionItem"]["question"]["choiceQuestion"]["type"] == "RADIO"
    assert len(form_requests(FORM)) == 1 + len(FORM.questions)


def test_every_specification_form_has_unique_fields():
    from jason.community import community

    for form in community().forms():
        fields = [q.field for q in form.questions]
        assert len(fields) == len(set(fields)), form.key


# -- the PDF field primitives -----------------------------------------------------------------------------------------

def _blank(tmp_path: Path) -> Path:
    doc = pymupdf.open()
    doc.new_page()
    doc.save(tmp_path / "blank.pdf")
    return tmp_path / "blank.pdf"


def test_fields_are_added_read_filled_and_flattened(tmp_path):
    from jason.community import pdf_fields as pf

    doc = pymupdf.open(_blank(tmp_path))
    page = doc[0]
    pf.text_field(page, "name", (72, 72, 300, 90), required=True, tooltip="Owner name(s)", max_len=60)
    pf.check_box(page, "mail", (72, 100, 84, 112), tooltip="By mail")
    group = pf.radio_group(doc, "occupancy", [(0, (72, 130, 84, 142), "owned"), (0, (150, 130, 162, 142), "rented")],
                           required=True, tooltip="Is your unit")
    doc.save(tmp_path / "form.pdf")

    form = pymupdf.open(tmp_path / "form.pdf")
    form_page = form[0]                                  # a widget needs its page kept alive
    widgets = list(form_page.widgets())
    name = next(w for w in widgets if w.field_name == "name")
    assert name.field_flags & pf.REQUIRED and name.field_label == "Owner name(s)" and name.text_maxlen == 60
    radios = [w for w in widgets if w.field_type == pymupdf.PDF_WIDGET_TYPE_RADIOBUTTON]
    assert {w.on_state() for w in radios} == {"owned", "rented"} and {w.field_name for w in radios} == {"occupancy"}
    for w in radios:                                     # the kids keep no field keys of their own, null or not
        assert "/FT" not in form.xref_object(w.xref, compressed=True)
    assert form.xref_get_key(group, "TU")[1] == "Is your unit"
    assert int(form.xref_get_key(group, "Ff")[1]) & pf.REQUIRED
    form.close()

    assert pf.values(tmp_path / "form.pdf") == {"name": "", "mail": False, "occupancy": None}
    missing = pf.fill(tmp_path / "form.pdf", {"name": "Pat", "mail": True, "occupancy": "rented", "nope": 1},
                      tmp_path / "filled.pdf")
    assert missing == ["nope"]
    assert pf.values(tmp_path / "filled.pdf") == {"name": "Pat", "mail": True, "occupancy": "rented"}
    pf.fill(tmp_path / "filled.pdf", {"occupancy": "owned"}, tmp_path / "changed.pdf")      # one choice at a time
    assert pf.values(tmp_path / "changed.pdf")["occupancy"] == "owned"

    flat = pf.flatten(tmp_path / "filled.pdf", tmp_path / "flat.pdf")
    archived = pymupdf.open(flat)
    assert not list(archived[0].widgets()) and "Pat" in archived[0].get_text()


# -- a printed form made fillable, and read back ----------------------------------------------------------------------

def _printed(tmp_path: Path, signature: str = "Signature of owner") -> Path:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "1. Owner name(s)", fontname="helvetica-bold")
    page.insert_text((72, 90), "_" * 40)
    page.insert_text((72, 120), "2. Deliver notices", fontname="helvetica-bold")
    page.insert_htmlbox(pymupdf.Rect(72, 126, 540, 146), "Check all that apply. ☐ By mail &nbsp; ☐ By email")
    page.insert_text((72, 170), "3. Is your unit", fontname="helvetica-bold")
    page.insert_htmlbox(pymupdf.Rect(72, 176, 540, 200), "☐ Owner-occupied &nbsp; ☐ Rented out to a")  # wraps
    page.insert_text((72, 230), "4. Email address", fontname="helvetica-bold")
    page.insert_text((72, 248), "_" * 40)
    page.insert_text((72, 280), f"{signature} " + "_" * 20 + "  Date " + "_" * 10)
    doc.save(tmp_path / "printed.pdf")
    return tmp_path / "printed.pdf"


def test_a_printed_form_becomes_fillable_by_its_definition(tmp_path):
    from jason.community.fillable import make_fillable

    names = make_fillable(_printed(tmp_path), out=tmp_path / "fill.pdf", form=FORM)
    assert names == ["owner-names", "delivery.by-mail", "delivery.by-email", "occupancy", "email", "signature", "date"]
    doc = pymupdf.open(tmp_path / "fill.pdf")
    kinds = {}
    for w in doc[0].widgets():
        kinds.setdefault(w.field_name, set()).add(w.field_type_string)
    assert kinds["delivery.by-mail"] == {"CheckBox"} and kinds["delivery.by-email"] == {"CheckBox"}   # check all: boxes
    assert kinds["occupancy"] == {"RadioButton"}                                                      # check one: a group
    owner = next(w for w in doc[0].widgets() if w.field_name == "owner-names")
    assert owner.field_label == "Owner name(s)"


def test_a_returned_form_is_read_and_checked(tmp_path):
    from jason.community import pdf_fields as pf
    from jason.community.fillable import make_fillable, read_answers, read_fillable

    make_fillable(_printed(tmp_path), out=tmp_path / "fill.pdf", form=FORM)
    pf.fill(tmp_path / "fill.pdf", {"owner-names": "Pat", "delivery.by-mail": True, "delivery.by-email": True,
                                    "occupancy": "rented-out-to-a-long-term-tenant", "email": "pat at example",
                                    "signature": "Pat", "date": "10/2/2026"}, tmp_path / "returned.pdf")
    answers = read_answers(tmp_path / "returned.pdf", FORM, source="returned.pdf")
    assert answers.answers == {"owner-names": "Pat", "delivery": ["By mail", "By email"],
                               "occupancy": ["Rented out to a long-term tenant"], "email": "pat at example"}
    assert (answers.signature, answers.signed) == ("Pat", "10/2/2026")
    assert check(FORM, answers.answers) == ["Email address: not an email address: pat at example"]
    assert read_fillable(tmp_path / "returned.pdf", FORM.questions)["Is your unit"] == ["Rented out to a long-term tenant"]


def test_the_signature_line_is_found_by_the_forms_own_label(tmp_path):
    from dataclasses import replace

    from jason.community.fillable import make_fillable

    member = replace(FORM, signature="Signature of member")
    names = make_fillable(_printed(tmp_path, "Signature of member"), out=tmp_path / "fill.pdf", form=member)
    assert names[-2:] == ["signature", "date"]


# -- one layout, two renderings ---------------------------------------------------------------------------------------

def test_markdown_and_html_print_the_same_marks():
    from jason.community.form_render import BOX, paper_html, paper_markdown

    markdown, page = "\n".join(paper_markdown(FORM)), paper_html(FORM)
    for q in FORM.questions:
        assert q.title in markdown and q.title in page
    for option in ("By mail", "Owner-occupied"):
        assert f"{BOX} {option}" in markdown and f"{BOX} {option}" in page
    assert "Month/day/year." in markdown and "Month/day/year." in page              # a date question's hint
    assert "Signature of owner" in markdown and "Signature of owner" in page


def _story_chrome(args, **kwargs):
    """Stands in for headless Chrome: lays the page's HTML out with PyMuPDF's Story into --print-to-pdf."""
    out = next(a.split("=", 1)[1] for a in args if a.startswith("--print-to-pdf="))
    html = Path(url2pathname(urlparse(args[-1]).path)).read_text(encoding="utf-8")
    story = pymupdf.Story(html)
    writer = pymupdf.DocumentWriter(out)
    more = True
    while more:
        device = writer.begin_page(pymupdf.paper_rect("letter"))
        more, _ = story.place(pymupdf.paper_rect("letter") + (54, 54, -54, -54))
        story.draw(device)
        writer.end_page()
    writer.close()


def test_a_form_pdf_is_made_from_its_definition_and_prefilled(tmp_path, monkeypatch):
    import jason.tasks.email_review as email_review
    from jason.community import pdf_fields as pf
    from jason.tasks.forms import fill_tokens, form_pdf

    monkeypatch.setattr(email_review, "browser", lambda: "chrome")
    assert fill_tokens(["Return by {RETURN_BY} to {NOBODY}"], {"RETURN_BY": "Oct 23"}) == ["Return by Oct 23 to {NOBODY}"]
    names = form_pdf(FORM, tmp_path / "form.pdf", association="Test Association", run=_story_chrome,
                     prefill={"owner-names": "Pat"})
    assert "occupancy" in names and "delivery.by-mail" in names and names[-2:] == ["signature", "date"]
    assert pf.values(tmp_path / "form.pdf")["owner-names"] == "Pat"
    with pytest.raises(KeyError):
        form_pdf(FORM, tmp_path / "again.pdf", association="Test", run=_story_chrome, prefill={"no-such-field": "x"})


def test_a_printed_form_from_older_rows_is_refused(tmp_path):
    """The fields are named by question number: a template Doc printed from rows since moved would mislabel them."""
    from dataclasses import replace

    import pytest

    from jason.community.fillable import make_fillable

    moved = replace(FORM, questions=(FORM.questions[0], FormQuestion("Manager's name"), *FORM.questions[1:]))
    with pytest.raises(ValueError, match="does not match"):
        make_fillable(_printed(tmp_path), out=tmp_path / "fill.pdf", form=moved)
