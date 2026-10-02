"""The marker's algebraic repair, the bar mark, and the reading hints."""

import pytest

from jason.community.form_refs import ALPHABET, Channel, Marker, correct, make, parse, repaired


def _body(m: Marker) -> str:
    return m.text.replace("-", "")


def test_one_misread_character_anywhere_is_put_right_by_the_checks_alone():
    m = make("NP", 2027, Channel.EMAIL, membership_id=42, unit_id=7)
    whole = _body(m)
    assert correct(whole) == whole
    for i in range(len(whole)):
        for ch in ALPHABET:
            if ch != whole[i]:
                assert correct(whole[:i] + ch + whole[i + 1:]) == whole      # the body or either check character


def test_a_repaired_marker_is_a_hint_found_only_where_parse_finds_none():
    m = make("NP", 2027, Channel.MAIL)
    text = m.text
    wrong = text[:2] + ("0" if text[2] != "0" else "1") + text[3:]          # the year's first digit misread
    assert parse(f"Ref {wrong}") == [] and repaired(f"Ref {wrong}") == [m]
    assert repaired(f"Ref {text}") == []                                     # a whole marker needs no repair


def test_the_bar_mark_round_trips_and_reads_turned_round():
    from jason.community.form_marks import Bar, bars, decode

    for m in (make("NP", 2027, Channel.MAIL), make("NP", 2027, Channel.EMAIL, membership_id=1, unit_id=2)):
        states = bars(m)
        assert len(states) == 4 + 3 * len(_body(m)) and states[0] is Bar.FULL and states[-1] is Bar.FULL
        assert decode(states) == (m, False)
        flip = {Bar.ASCENDER: Bar.DESCENDER, Bar.DESCENDER: Bar.ASCENDER}
        assert decode([flip.get(b, b) for b in reversed(states)]) == (m, False)    # a page fed upside down


def test_one_misread_bar_is_put_right_and_says_so():
    from jason.community.form_marks import Bar, bars, decode

    m = make("NP", 2027, Channel.EMAIL, membership_id=3, unit_id=4)
    states = bars(m)
    i = 2 + 3 * 6 + 2                                     # the last bar of the copy's second character
    states[i] = Bar((states[i] + 1) % 4)
    found = decode(states)
    assert found is not None and found[0] == m and found[1] is True


def test_a_drawn_bar_mark_reads_back_from_the_page_image():
    import numpy as np
    import pymupdf

    from jason.community import form_marks

    m = make("NP", 2027, Channel.EMAIL, membership_id=9, unit_id=10)
    doc = pymupdf.open()
    page = doc.new_page()
    form_marks.draw(page, m, gray=0.35)
    pix = page.get_pixmap(dpi=150, colorspace=pymupdf.csGRAY)
    gray = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
    assert form_marks.read(gray, 150) == [(m, False)]
    doc.close()


def test_what_was_sent_is_kept_only_when_ocr_could_have_read_it_either_way():
    from jason.community.form_hints import community_hints, put_right
    from jason.community.forms import ReadAs

    hints = community_hints({"email": "lolly.illoli01@example.org"})
    sent = hints.expected["email"]
    assert put_right("1olly.i11oli0l@example.org", ReadAs.EMAIL, hints, sent) == (sent, "sent")   # look-alikes only
    changed, how = put_right("loly.illoli01@example.org", ReadAs.EMAIL, hints, sent)              # a real change
    assert changed == "loly.illoli01@example.org" and how != "sent"


def test_each_kind_of_answer_has_its_own_repairs():
    from jason.community.form_hints import community_hints, put_right
    from jason.community.forms import ReadAs

    hints = community_hints()
    assert put_right("omar sato@example net", ReadAs.EMAIL, hints)[0] == "omar.sato@example.net"
    assert put_right("jo@gmial.corn", ReadAs.EMAIL, hints)[0] == "jo@gmail.com"
    assert put_right("(916) 555-O1l2", ReadAs.PHONE, hints)[0] == "(916) 555-0112"
    assert put_right("1O054 Mesmerizlng Walk Apt 15B", ReadAs.ADDRESS, hints)[0] == "10054 Mesmerizing Walk Apt 15B"
    assert put_right("Pat Lee pat.lee@example org", ReadAs.CONTACT, hints)[0] == "Pat Lee pat.lee@example.org"
    # where an email starts among a contact's words is a guess; only the word joined to its "@" is taken
    assert put_right("Pat Lee pat lee@example org", ReadAs.CONTACT, hints)[0] == "Pat Lee pat lee@example.org"


def test_an_answer_reads_as_its_question_says():
    from jason.community.forms import ReadAs
    from jason.community.spec import spec_module

    form = spec_module("forms").OWNER_INFO
    reads = {q.field: q.reads_as for q in form.questions}
    assert reads["email"] is ReadAs.EMAIL and reads["unit-address"] is ReadAs.ADDRESS
    assert reads["name"] is ReadAs.NAME and reads["representative-name"] is ReadAs.NAME
    assert reads["representative-email"] is ReadAs.EMAIL and reads["representative-phone"] is ReadAs.PHONE
    assert reads["second-mailing-address"] is ReadAs.ADDRESS and reads["second-email"] is ReadAs.EMAIL
    assert ReadAs.CONTACT not in reads.values()                 # no question takes a mixed contact any more


def test_a_period_ending_a_word_does_not_change_an_answer():
    from jason.tasks.owner_prefill import normalize

    assert normalize("owner-names", "Mary-Kate St. John Jr.") == normalize("owner-names", "Mary-Kate St John Jr")
    assert normalize("email", "a.b@example.org") == "a.b@example.org"


def test_the_fuzzer_is_repeatable_invents_its_answers_and_lints_the_form(tmp_path):
    import random

    import pymupdf

    from jason.community.form_layout import FormLayout
    from jason.community.spec import spec_module
    from jason.tasks import form_fuzz as fz

    form = spec_module("forms").OWNER_INFO
    one = fz.answers(form, random.Random(5), fz.Style.LOOKALIKE)
    assert one == fz.answers(form, random.Random(5), fz.Style.LOOKALIKE)
    assert all(v.split("@")[1] in fz.DOMAINS for k, v in one.items() if isinstance(v, str) and "@" in v)
    case = fz.cases(2, 3, fills=list(fz.Fill), styles=list(fz.Style), profiles=["home", "random"])[1]
    assert fz.Case.from_json(case.as_json()) == case
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "Return it online at [FORM LINK] by {RETURN_BY}.")
    page.insert_text((40, 25), "letterhead in the bar mark's place")
    doc.save(tmp_path / "f.pdf")
    kinds = {(f.kind, f.detail) for f in fz.lint(tmp_path / "f.pdf", FormLayout("owner-info"), form)}
    assert ("token left unfilled", "[FORM LINK]") in kinds and ("token left unfilled", "{RETURN_BY}") in kinds
    assert any(k == "marker place not clear" for k, _ in kinds)


def test_a_fuzz_case_runs_end_to_end(tmp_path):
    """One typed case on a clean scan: every answer read right, the marker read."""
    from pathlib import Path

    from jason.community.form_layout import read_layout
    from jason.community.ocr import PyMuPdfTesseract
    from jason.community.spec import spec_module
    from jason.tasks import form_fuzz as fz

    blank = Path("data/packets/owner-information-2027/owner-info-fillable.pdf")
    if not blank.is_file() or not PyMuPdfTesseract.available():
        pytest.skip("needs the built form and Tesseract's language data")
    form = spec_module("forms").OWNER_INFO
    case = fz.Case(1035, fz.Fill.TYPED, fz.Style.CAPS, fz.PROFILES["clean"])
    result = fz.run_case(case, form, blank, read_layout(blank, form), tmp_path)
    assert not result.error and result.aligned and result.marker_right
    assert result.share_hinted >= 0.9
