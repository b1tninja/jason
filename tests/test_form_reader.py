"""The form-aware scan reader and the markers on sent copies."""

import pytest

from jason.community.form_refs import ALPHABET, LOOKALIKE, Channel, Marker, campaign, check, closest, make, parse


def test_a_copy_marker_is_stable_says_nothing_and_survives_how_people_and_ocr_write_it():
    m = make("NP", 2027, Channel.EMAIL, membership_id=800001, unit_id=700001)
    r = m.text
    assert m == make("NP", 2027, Channel.EMAIL, membership_id=800001, unit_id=700001)   # a resend: the same marker
    assert m != make("NP", 2027, Channel.EMAIL, membership_id=800001, unit_id=606995)   # each copy its own
    assert m.campaign == "NP27E" and len(m.copy) == 5 and r.startswith("NP27E-")
    assert "800001" not in r and "700001" not in r
    assert parse(f"Re: Owner information request [Ref {r}]") == [m]
    assert parse(f"Ref{r}") == [m]                                         # a label run into it
    assert parse(r.lower().replace("-", " ").replace("0", "o")) == [m]    # lower case, a space, an O for a zero


def test_a_campaign_marker_names_the_mailing_not_a_copy():
    m = make("NP", 2027, Channel.MAIL)
    assert m == Marker("NP27M") and m.copy == "" and m.text == "NP27M-" + check("NP27M")
    assert make("NP", 2027, Channel.MAIL, membership_id=1) == m           # a copy needs both owner and unit
    assert parse(f"scan: Ref {m.text} Owner Information") == [m]
    assert campaign("np", 2031, Channel.PAYHOA) == "NP31P"
    with pytest.raises(ValueError):
        campaign("OI", 2027, Channel.MAIL)                                  # I is not in the alphabet


def test_the_alphabet_keeps_apart_what_ocr_confuses():
    assert len(ALPHABET) == 23 and not set("BDGIJLOQSUYZ") & set(ALPHABET)
    assert all(ch.translate(LOOKALIKE) in ALPHABET for ch in "ODQIJLZSGBUY")
    m = make("NP", 2027, Channel.EMAIL, membership_id=1, unit_id=2)
    misread = m.text.replace("0", "O").replace("1", "l").replace("5", "S").replace("8", "B").replace("6", "G")
    assert parse(misread) == [m]                                          # look-alikes read as what they stand for


def test_every_single_misread_and_neighbour_swap_fails_the_check():
    body = make("NP", 2027, Channel.EMAIL, membership_id=7, unit_id=9).text.replace("-", "")[:-2]
    tail = check(body)
    for i in range(len(body)):
        for ch in ALPHABET:
            if ch != body[i]:
                assert check(body[:i] + ch + body[i + 1:]) != tail
        if i + 1 < len(body) and body[i] != body[i + 1]:
            assert check(body[:i] + body[i + 1] + body[i] + body[i + 2:]) != tail


def test_a_misread_is_never_matched_but_may_be_taken_to_the_one_sent_marker_it_is_near():
    sent = [make("NP", 2027, Channel.EMAIL, membership_id=n, unit_id=n + 1) for n in range(50)]
    m = sent[17]
    i = m.text.index("-") + 2
    wrong = m.text[:i] + next(ch for ch in "ACEFHK" if ch != m.text[i]) + m.text[i + 1:]
    assert parse(wrong) == []                                             # caught by the check
    assert closest(wrong, sent) == m                                      # a hint against what was really sent
    assert closest("nothing here", sent) is None


def test_the_record_of_sent_copies_finds_a_copy_from_any_text(tmp_path, monkeypatch):
    monkeypatch.setenv("JASON_LOCK_DIR", str(tmp_path / "locks"))
    from jason.tasks.form_references import load, lookup, record

    r = make("NP", 2027, Channel.EMAIL, membership_id=1, unit_id=2).text
    record(tmp_path, r, form="owner-info", year=2027, membershipId=1, unitId=2, sent={"fields": {"email": "abc"}})
    record(tmp_path, r, form="owner-info", year=2027, membershipId=1, unitId=2)        # a resend keeps the first date
    entry = load(tmp_path)[r]
    assert entry["firstSent"] <= entry["lastSent"] and entry["membershipId"] == 1
    assert [x for x, _ in lookup(tmp_path, f"thanks, see attached ({r})")] == [r]
    i = len(r) - 4
    smudged = r[:i] + next(ch for ch in "ACEFHK" if ch != r[i]) + r[i + 1:]
    assert [x for x, _ in lookup(tmp_path, f"scan: Ref {smudged}")] == [r]          # one character off: the near match


def test_the_engines_differ_in_identity_and_pace_and_keep_their_batch_ids():
    from jason.community.spec import spec_module
    from jason.tasks.delivery_engines import ENGINES, Identity

    form = spec_module("forms").OWNER_INFO
    email, mail = ENGINES[Channel.EMAIL], ENGINES[Channel.MAIL]
    assert (email.identity, mail.identity) == (Identity.COPY, Identity.CAMPAIGN)
    assert email.batch_id(form, 2027) == "owner-info-2027-email" and mail.batch_id(form, 2027) == "owner-info-2027-mail"
    assert email.marker(form, 2027, membership_id=1, unit_id=2).copy
    assert mail.marker(form, 2027, membership_id=1, unit_id=2) == make("NP", 2027, Channel.MAIL)   # one for the mailing
    assert mail.pace().interval > email.pace().interval


def test_a_stamped_copy_reads_its_reference_back(tmp_path):
    import pymupdf

    from jason.community.fillable import read_answers, stamp_reference
    from jason.community.spec import spec_module

    doc = pymupdf.open()
    doc.new_page()
    doc.save(tmp_path / "a.pdf")
    r = make("NP", 2027, Channel.EMAIL, membership_id=1, unit_id=2).text
    stamp_reference(tmp_path / "a.pdf", r)
    with pymupdf.open(tmp_path / "a.pdf") as done:
        assert f"Ref {r}" in done[0].get_text() and f"jason-reference:{r}" in done.metadata["keywords"]
    assert read_answers(tmp_path / "a.pdf", spec_module("forms").OWNER_INFO).reference == r


def test_the_alignment_recovers_a_turned_scaled_and_shifted_page():
    import math

    from jason.community.form_reader import fit_points

    angle, scale, shift = math.radians(1.5), 0.97, (12.0, -7.0)

    def turned(x, y):
        return (scale * (x * math.cos(angle) - y * math.sin(angle)) + shift[0],
                scale * (x * math.sin(angle) + y * math.cos(angle)) + shift[1])

    src = [(x, y) for x in (72, 200, 330, 460, 540) for y in (90, 300, 520, 700)]
    dst = [turned(x, y) for x, y in src]
    dst[3] = (dst[3][0] + 40, dst[3][1])                                  # one word matched wrongly
    fit = fit_points(src, dst)
    assert fit.residual < 0.01                                            # the wrong match is dropped
    for x, y in ((100, 100), (500, 750)):
        assert all(abs(a - b) < 0.01 for a, b in zip(fit(x, y), turned(x, y)))


def test_specks_and_rule_slivers_are_dropped_and_letters_kept():
    import numpy as np

    from jason.community.form_reader import specks_out

    region = np.zeros((40, 120), dtype=bool)
    region[30:32, 5:115] = True                     # a sliver of the printed line
    region[5, 60] = True                            # dust
    region[8:26, 10:14] = True                      # a letter's stroke
    region[20:23, 40:46] = True                     # a hyphen: flat but short, kept
    kept = specks_out(region)
    assert not kept[30:32].any() and not kept[5, 60] and kept[8:26, 10:14].all() and kept[20:23, 40:46].all()


def test_a_simulated_scan_is_read_back(tmp_path):
    """The whole path on a real form: fill, scan (turned, scaled, speckled), align, drop out, read."""
    from pathlib import Path

    from jason.community.form_layout import read_layout
    from jason.community.form_reader import read_scan
    from jason.community.ocr import PyMuPdfTesseract
    from jason.community.pdf_fields import fill
    from jason.community.spec import spec_module
    from jason.tasks.form_scans import simulate

    blank = Path("data/packets/owner-information-2027/owner-info-fillable.pdf")
    if not blank.is_file() or not PyMuPdfTesseract.available():
        pytest.skip("needs the built form and Tesseract's language data")
    form = spec_module("forms").OWNER_INFO
    fill(blank, {"delivery.by-mail": True, "occupancy": "rented-out", "ballots": "paper-ballot-by-mail",
                 "email": "pat@example.org"}, tmp_path / "filled.pdf")
    reading = read_scan(simulate(tmp_path / "filled.pdf", tmp_path / "scan.pdf", angle=0.8, noise=0.002), form,
                        read_layout(blank, form))
    assert reading.residual < 1.5
    assert reading.fields["delivery.by-mail"].value is True and reading.fields["delivery.by-email"].value is False
    assert reading.fields["occupancy"].value == "rented-out" and reading.fields["ballots"].value == "paper-ballot-by-mail"
    assert "example" in reading.fields["email"].value


def test_a_scanned_page_is_known_by_its_printed_lines_with_no_marker(tmp_path):
    """The form is recognised from its own text: a mailed letter whose marker is lost is still the owner form."""
    from pathlib import Path

    from jason.community.form_layout import read_layout
    from jason.community.form_reader import identify_form, scan_pages
    from jason.community.ocr import PyMuPdfTesseract
    from jason.community.spec import spec_module
    from jason.tasks.form_scans import simulate

    blank = Path("data/packets/owner-information-2027/owner-info-fillable.pdf")
    if not blank.is_file() or not PyMuPdfTesseract.available():
        pytest.skip("needs the built form and Tesseract's language data")
    layout = read_layout(blank, spec_module("forms").OWNER_INFO)
    page = scan_pages(simulate(blank, tmp_path / "scan.pdf", angle=-0.6, noise=0.002))[0]
    found, index, lines = identify_form(page, [layout])
    assert found is layout and index == 0 and lines >= 4


def test_a_stamped_copys_email_link_carries_its_reference(tmp_path):
    import pymupdf

    from jason.community.fillable import stamp_reference, with_reference

    assert with_reference("mailto:a@example.com?subject=Form", "NP27E-AAAAA-AA") == \
        "mailto:a@example.com?subject=Form%20%5BRef%20NP27E-AAAAA-AA%5D"
    once = with_reference("mailto:a@example.com?subject=Form", "NP27E-AAAAA-AA")
    assert with_reference(once, "NP27E-AAAAA-AA") == once                       # stamped twice, named once
    pdf = tmp_path / "f.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_link({"kind": pymupdf.LINK_URI, "from": pymupdf.Rect(72, 72, 200, 90),
                      "uri": "mailto:a@example.com?subject=Form"})
    doc.save(pdf)
    stamp_reference(pdf, "NP27E-AAAAA-AA")
    uris = [l["uri"] for l in pymupdf.open(pdf)[0].get_links()]
    assert uris == ["mailto:a@example.com?subject=Form%20%5BRef%20NP27E-AAAAA-AA%5D"]


def test_a_copy_links_the_printed_way_online_to_its_units_form(tmp_path):
    import pymupdf

    from jason.community.fillable import link_phrase
    from jason.tasks.payhoa_forms import with_unit

    path = tmp_path / "form.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Return it by email, or online in PayHOA: sign in, choose Requests.")
    page.insert_link({"kind": pymupdf.LINK_URI, "from": pymupdf.Rect(72, 90, 200, 100),
                      "uri": "https://app.payhoa.com/app/forms/114542"})
    doc.save(path)
    doc.close()
    assert link_phrase(path, "online in PayHOA", "https://app.payhoa.com/app/forms/114542;unitId=7",
                       rewrite=lambda u: with_unit(u, 7)) == 1
    with pymupdf.open(path) as done:
        uris = sorted(link["uri"] for link in done[0].get_links())
    assert uris == ["https://app.payhoa.com/app/forms/114542;unitId=7"] * 2
