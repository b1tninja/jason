"""Recognition (docs/arrivals-design.md, "Recognition is the crux"): is a message or an attachment a response to a form
jason sent, and which copy? The ladder (``jason.tasks.recognize``) is measured here, not trusted.

Everything is made up and offline: a made-up form (``form_lab``, the real fillable-form machinery with the lab's questions),
made-up sent copies, made-up answers, and made-up negatives. Nothing reaches a service, a mailbox, or an owner's data. The
OCR rungs run only when Tesseract's language data is present (they are skipped otherwise, as ``test_response_inbox`` does).

**Measured (the floor this file fixes), October 5, 2026, on this machine:**

- *The corpus of returns.* Two sent copies, each filled with made-up answers, stamped as a sent copy is (printed reference,
  bar mark, hidden field, keywords), then scanned by ``form_scans.simulate`` under the six scanner profiles of
  ``form_fuzz.PROFILES`` (clean 300 dpi, office 200, home 150, phone 120, fax 100 turned 3 degrees, fed upside down) and
  four random profiles (100 to 300 dpi, up to 3 degrees, blur, JPEG 35 to 90, faint or dark): 20 scans. The form reader
  (``form_reader.find_marker``) kept the marker on 18 of 20, and ``recognize`` recognized the same 18 as the right copy
  (the printed marker 7, one of them with the bar mark agreeing; the bar mark alone 11, among them the fax and the
  upside-down page, the fax's with one bar put right and so "medium"), none as a wrong copy. The other 2 (the same random
  profile on each copy: 150 dpi, blur 1.04, 0.67% speckle) lost the marker altogether and came out as Candidates by their
  printed lines (6 lines matched, sureness low): the form is known, the copy is not.
- *The returns that keep no marker.* An unstamped copy of the form (a download printed and filled) is a Candidate by its
  printed lines, never Recognized.
- *The negatives.* An invoice (as a text PDF and as a scan), a certificate-like page, minutes, a blank page, another form,
  a page citing Civil Code 4041 in running text, and a page carrying a reference of the right shape that jason never sent:
  8 negatives, 0 recognized. The citation-only page is a Candidate at the lowest sureness; the rest are not ours; the
  reference we did not send is flagged as one we did not send.
"""

from __future__ import annotations

import json
import random
import shutil
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path

import pymupdf
import pytest

from jason.community.fillable import stamp_reference
from jason.community.form_refs import Channel, make
from jason.community.forms import AnswerCycle
from jason.community.ocr import PyMuPdfTesseract
from jason.community.pdf_fields import fill
from jason.community.response_inbox import ResponseRequest
from jason.tasks import form_lab as fl
from jason.tasks.form_fuzz import PROFILES, random_profile
from jason.tasks.form_references import load, lookup, record
from jason.tasks.form_scans import simulate
from jason.tasks.recognize import (Attachment, Catalog, Outcome, Recognition, Rung, SentCopy, Sure, citation_pattern, compare,
                                   identify_reference, recognize, same_place)

needs_ocr = pytest.mark.skipif(not PyMuPdfTesseract.available(), reason="needs Tesseract's language data")
FORM = replace(fl.LAB_FORM, title="Owner Information", authority="Civil Code 4041")
CYCLE = AnswerCycle(2027, date(2026, 10, 1), return_by=date(2026, 10, 23), reports_mailed=date(2026, 12, 1))
ANSWERS = {"owner-names": "Pat Example", "unit-address": "101 Example Way, Sacramento, CA", "email": "pat@example.org",
           "delivery.by-mail": True, "occupancy": "rented-out"}
CAMPAIGN = "NP27E"


@dataclass
class World:
    data: Path
    request: ResponseRequest
    blank: Path
    refs: list[str]                     # the sent copies' references; copy n is membership 11+n, unit 1+n


def sent(n: int) -> str:
    return make("NP", 2027, Channel.EMAIL, membership_id=11 + n, unit_id=1 + n).text


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    patch = pytest.MonkeyPatch()
    root = tmp_path_factory.mktemp("recognize")
    patch.setenv("JASON_LOCK_DIR", str(root / "locks"))
    blank = root / "packets" / "lab" / "blank.pdf"
    blank.parent.mkdir(parents=True)
    fl.render(fl.Layout(), blank)
    refs = []
    for n in range(8):
        refs.append(sent(n))
        record(root, refs[-1], form="owner-info", year=2027, membershipId=11 + n, unitId=1 + n, unit=f"{101 + n} Example Way",
               channel="email")
    mailing = make("NP", 2027, Channel.MAIL).text
    record(root, mailing, form="owner-info", year=2027, channel="MAIL", identity="campaign", batch="owner-info-2027-mail")
    request = ResponseRequest("survey-2027", "Owner information request", FORM, CYCLE, payhoa_form="owner-info",
                              marker_campaigns=(CAMPAIGN, "NP27M"), blank="packets/lab/blank.pdf")
    yield World(root, request, blank, refs)
    patch.undo()


def returned(world: World, n: int, name: str = "") -> Path:
    """A sent copy as an owner returns it typed: stamped as ``stamp_reference`` stamps a copy, then filled."""
    stamped = world.data / f"stamped-{name or n}.pdf"
    shutil.copy(world.blank, stamped)
    stamp_reference(stamped, world.refs[n])
    filled = world.data / f"filled-{name or n}.pdf"
    fill(stamped, ANSWERS, filled)
    return filled


def text_pdf(path: Path, lines: list[str], size: float = 11) -> Path:
    doc = pymupdf.open()
    page = doc.new_page()
    y = 72.0
    for line in lines:
        page.insert_text((72, y), line, fontsize=size)
        y += size + 6
    doc.save(path)
    doc.close()
    return path


def scanned(pdf: Path, name: str, **more) -> Path:
    return simulate(pdf, pdf.with_name(name), **{"dpi": 150, "angle": 0.8, "noise": 0.002, **more})


# -- the lookup, the same rules as the record of sent copies ----------------------------------------------------------------

def test_the_catalog_finds_a_reference_by_the_rules_form_references_lookup_has(world):
    catalog = Catalog.load(world.data)
    target = world.refs[3]
    i = len(target) - 4
    smudged = target[:i] + next(ch for ch in "ACEFHK" if ch != target[i]) + target[i + 1:]
    for text in (f"Re: Owner information [Ref {target}]", f"scan: Ref {smudged}", f"Ref{target.lower().replace('-', ' ')}",
                 "nothing here", ""):
        want = [x for x, _ in lookup(world.data, text)]
        got = catalog.find(text)
        assert ([got.reference] if got is not None and got.sent else []) == want, text
    assert catalog.find(smudged).how == "near" and catalog.find(f"Ref {target}").how == "whole"
    assert catalog.copy(target) == SentCopy(target, "owner-info", 2027, "email", "104 Example Way", 4, 14,
                                            catalog.copy(target).first_sent, catalog.copy(target).last_sent)
    assert catalog.copy(target).identity == "copy" and catalog.copy(make("NP", 2027, Channel.MAIL).text).identity == "campaign"
    assert Catalog({}).find(f"Ref {target}") is None                    # with no record at all, nothing is "not sent"


# -- rung 1: the subject and the body, headers only -------------------------------------------------------------------------

def test_a_reference_in_the_subject_is_a_recognized_copy_with_the_owner_and_unit_as_sent(world):
    ref = world.refs[2]
    rec = recognize(world.data, world.request, subject=f"Re: Owner information request, 103 Example Way [Ref {ref}]")
    assert rec.outcome is Outcome.RECOGNIZED and rec.rung is Rung.SUBJECT and rec.sure is Sure.HIGH and rec.recognized
    assert (rec.copy.reference, rec.copy.unit, rec.copy.unit_id, rec.copy.membership_id, rec.copy.channel, rec.copy.year,
            rec.copy.form) == (ref, "103 Example Way", 3, 13, "email", 2027, "owner-info")
    assert rec.copy.first_sent and rec.copy.identity == "copy" and rec.matches_request is True and rec.how == "whole"
    assert rec.form == "owner-info" and rec.authority == "Civil Code 4041" and rec.tried == (Rung.SUBJECT,)
    assert ref in rec.note and "103 Example Way" in rec.note and "subject" in rec.note
    assert rec.to_json()["copy"]["membershipId"] == 13 and rec.to_json()["rungNumber"] == 1
    quoted = recognize(world.data, world.request, subject="Re: your request", body=f"On Monday you wrote:\n> [Ref {ref}]\nthanks")
    assert quoted.recognized and quoted.rung is Rung.SUBJECT and "message's text" in quoted.note


def test_a_mailed_letters_marker_names_the_mailing_not_an_owner(world):
    rec = recognize(world.data, world.request, subject=f"scan Ref {make('NP', 2027, Channel.MAIL).text}")
    assert rec.recognized and rec.copy.identity == "campaign" and rec.copy.unit == "" and rec.copy.batch
    assert "names the mailing, not an owner" in rec.note
    assert compare(rec.copy, owner=type("O", (), dict(unit="101 Example Way", unit_id=1, membership_id=11, name="Pat"))()) \
        .matches_unit is None                                              # a campaign names no unit to compare


def test_a_marker_one_character_off_is_taken_only_to_the_one_sent_marker_near_it(world):
    ref = world.refs[5]
    for i in (len(ref) - 1, len(ref) - 4, 6):                               # a check character, the copy part, the copy part
        wrong = ref[:i] + next(ch for ch in "ACEFHKMNPRTVX" if ch != ref[i]) + ref[i + 1:]
        assert wrong not in load(world.data)                                # a reading that is not itself a sent marker
        rec = recognize(world.data, world.request, subject=f"[Ref {wrong}]")
        assert rec.recognized and rec.copy.reference == ref, wrong
        assert rec.how in ("near", "put right") and rec.sure is Sure.MEDIUM and "One character was put right" in rec.note
    # two characters off is near nothing sent: nothing is taken, and nothing is flagged
    twice = ref[:6] + next(ch for ch in "ACEFHK" if ch != ref[6]) + next(ch for ch in "ACEFHK" if ch != ref[7]) + ref[8:]
    rec = recognize(world.data, world.request, subject=f"[Ref {twice}]")
    assert not rec.recognized and rec.copy is None and not rec.unsent


def test_a_reference_of_the_right_shape_that_no_sent_copy_carries_is_a_finding(world):
    never = make("NP", 2027, Channel.EMAIL, membership_id=999, unit_id=999).text
    assert never not in load(world.data)
    rec = recognize(world.data, world.request, subject=f"Re: Owner information [Ref {never}]")
    assert rec.outcome is Outcome.NOT_OURS and rec.unsent and rec.reference == never and rec.copy is None
    assert "a reference we did not send" in rec.note
    assert not recognize(Path("no-such-folder"), world.request, subject=f"[Ref {never}]").unsent   # no record: cannot say
    # a sent reference beside it still wins
    both = recognize(world.data, world.request, subject=f"[Ref {never}] and [Ref {world.refs[0]}]")
    assert both.recognized and both.copy.reference == world.refs[0]


def test_a_copy_of_another_campaign_is_recognized_and_says_it_is_not_this_requests(world):
    other = ResponseRequest("other", "Another request", FORM, CYCLE, marker_campaigns=("XX27E",))
    rec = recognize(world.data, other, subject=f"[Ref {world.refs[1]}]")
    assert rec.recognized and rec.matches_request is False and "not this request's" in rec.note


# -- rung 2 and rung 3: the text layer and the hidden field -----------------------------------------------------------------

def test_a_returned_pdfs_text_layer_and_a_mail_scans_text_are_read_without_ocr(world):
    pdf = returned(world, 2)
    rec = recognize(world.data, world.request, subject="Owner information", attachments=[Attachment("form.pdf", path=pdf)])
    assert rec.recognized and rec.rung is Rung.TEXT_LAYER and rec.copy.reference == world.refs[2]
    assert rec.tried == (Rung.SUBJECT, Rung.TEXT_LAYER)                    # no page image was read
    mail = recognize(world.data, world.request, attachments=[Attachment("contents.pdf", data=b"", text=f"Owner Information  Ref {world.refs[4]}")])
    assert mail.recognized and mail.rung is Rung.TEXT_LAYER and mail.copy.unit == "105 Example Way"
    from_bytes = recognize(world.data, world.request, attachments=[Attachment("form.pdf", data=pdf.read_bytes())])
    assert from_bytes.recognized and from_bytes.rung is Rung.TEXT_LAYER


def test_a_returned_fillable_pdfs_hidden_reference_field_is_read_when_the_text_layer_has_none(world):
    pdf = returned(world, 6, "field")
    with pymupdf.open(pdf) as doc:                                          # the printed Ref and the keywords are gone
        for page in doc:
            for rect in page.search_for(f"Ref {world.refs[6]}"):
                page.add_redact_annot(rect)
            page.apply_redactions()
        doc.set_metadata({})
        doc.saveIncr()
    with pymupdf.open(pdf) as doc:
        assert world.refs[6] not in "".join(p.get_text() for p in doc) and not (doc.metadata or {}).get("keywords")
    rec = recognize(world.data, world.request, attachments=[Attachment("form.pdf", path=pdf)], images=False)
    assert rec.recognized and rec.rung is Rung.FIELD and rec.copy.reference == world.refs[6] and rec.sure is Sure.HIGH
    assert "hidden reference field" in rec.note and rec.tried[-1] is Rung.FIELD


def test_a_file_that_will_not_open_is_reported_not_raised(world):
    rec = recognize(world.data, world.request, subject="Re: form", attachments=[Attachment("form.pdf", data=b"made-up bytes")])
    assert rec.outcome is Outcome.NOT_OURS and "form.pdf could not be opened" in rec.note


# -- rung 7: the sender decides only whether to download, never the result ----------------------------------------------------

def test_rung_seven_says_whether_a_download_is_worth_it_and_never_decides(world):
    listed = [Attachment("scan.pdf")]                                      # named, not downloaded
    yes = recognize(world.data, world.request, subject="my form", attachments=listed, sender_asked=True)
    assert yes.worth_download and yes.outcome is Outcome.NOT_OURS and yes.rung is not Rung.SENDER
    assert Rung.SENDER in yes.tried and "worth downloading" in yes.note and "scan.pdf" in yes.note
    assert not recognize(world.data, world.request, subject="my form", attachments=listed, sender_asked=False).worth_download
    assert not recognize(world.data, world.request, subject="my form", attachments=listed).worth_download
    assert not recognize(world.data, world.request, subject="hello", attachments=[Attachment("notes.txt")],
                         sender_asked=True).worth_download                # not a PDF or an image
    settled = recognize(world.data, world.request, subject=f"[Ref {world.refs[0]}]", attachments=listed, sender_asked=True)
    assert settled.recognized and not settled.worth_download               # already settled by the subject: nothing to fetch


# -- rung 6, and the pure helpers --------------------------------------------------------------------------------------------

def test_a_citation_is_a_lead_not_proof_and_the_title_makes_it_a_stronger_one(world):
    cites = recognize(world.data, world.request, body="As Civil Code section 4041 requires, the Association asks owners to "
                                                       "update their contact details each year.")
    assert cites.outcome is Outcome.CANDIDATE and cites.rung is Rung.CITATION and cites.sure is Sure.LOW
    assert cites.copy is None and cites.form == "owner-info" and "not a copy we sent" in cites.note
    both = recognize(world.data, world.request, body="Owner Information\nPursuant to Civ. Code § 4041, please complete this.")
    assert both.outcome is Outcome.CANDIDATE and both.sure is Sure.MEDIUM and "printed title" in both.note
    other = recognize(world.data, world.request, body="Civil Code section 40411 and Civil Code 4040 are different sections.")
    assert other.outcome is Outcome.NOT_OURS


def test_helpers_read_citations_and_places_the_way_a_text_writes_them():
    pattern = citation_pattern("Civil Code 4041")
    for text in ("Civil Code 4041", "Civ. Code, § 4041(a)", "California Civil Code section 4041", "CIV 4041", "civil code §4041"):
        assert pattern.search(text), text
    for text in ("Civil Code 40411", "Civil Code 4040", "Health and Safety Code 4041", "Penal Code 4041"):
        assert not pattern.search(text), text
    assert citation_pattern("a made-up authority") is None
    assert same_place("101 EXAMPLE WAY", "101 Example Way, Sacramento, CA 95835") and same_place("4000 Oak Dr", "4000 Oak Drive")
    assert same_place("101 Example Way", "102 Example Way") is False and same_place("", "101 Example Way") is None


def test_the_copy_as_sent_is_compared_with_the_owner_the_sender_matches_and_the_unit_written(world):
    copy = Catalog.load(world.data).copy(world.refs[0])                    # membership 11, unit 1, "101 Example Way"
    me = type("O", (), dict(unit="101 Example Way", unit_id=1, membership_id=11, name="Pat Example"))()
    ok = compare(copy, owner=me, written_unit="101 Example Way, Sacramento, CA")
    assert (ok.matches_unit, ok.matches_owner, ok.matches_written, ok.notes) == (True, True, True, ())
    other = type("O", (), dict(unit="102 Example Way", unit_id=2, membership_id=12, name="Ben Sample"))()
    bad = compare(copy, owner=other, written_unit="105 Example Way", sent_name="Pat Example")
    assert (bad.matches_unit, bad.matches_owner, bad.matches_written) == (False, False, False)
    assert len(bad.notes) == 2 and "belongs to 102 Example Way" in bad.notes[0] and "the form names 105 Example Way" in bad.notes[1]
    co_owner = type("O", (), dict(unit="101 Example Way", unit_id=1, membership_id=12, name="Ben Sample"))()
    assert compare(copy, owner=co_owner, sent_name="Pat Example").notes == (
        "the copy was sent to Pat Example, but the sender's address belongs to Ben Sample",)
    assert compare(copy) == compare(None) == compare(copy, owner=None, written_unit="")      # nothing to compare: not "no"
    assert identify_reference(Catalog.load(world.data), f"Ref {world.refs[1]}", Rung.MARK, request=world.request).copy.unit \
        == "102 Example Way"
    assert identify_reference(Catalog.load(world.data), "nothing", Rung.MARK) is None


# -- rung 4 and 5: the corpus of scans ---------------------------------------------------------------------------------------

def marker_kept(scan: Path) -> str:
    """What the form reader finds on the scan's first page (printed marker and bar mark), as ``read_scan`` does."""
    from jason.community.form_reader import find_marker, gray_of, ocr_lines, scan_pages

    page = scan_pages(scan)[0]
    text = "\n".join(t for t, _ in ocr_lines(gray_of(page), dpi=200))
    return find_marker(page, text, dpi=200)[0]


@needs_ocr
def test_every_simulated_return_that_keeps_its_marker_is_recognized_as_the_right_copy(world):
    scans = []
    rng = random.Random(2027)
    profiles = [*PROFILES.values(), *(random_profile(rng) for _ in range(4))]
    for n in (1, 5):
        filled = returned(world, n)
        for index, p in enumerate(profiles):
            out = filled.with_name(f"scan-{n}-{index}-{p.name}.pdf")
            simulate(filled, out, dpi=p.dpi, angle=p.angle, scale=p.scale, shift=p.shift, noise=p.noise, blur=p.blur,
                     jpeg=p.jpeg, gamma=p.gamma, seed=index + 7)
            scans.append((world.refs[n], p, out))
    kept = recognized = wrong = 0
    lost = []
    for ref, p, scan in scans:
        keeps = marker_kept(scan) == ref
        rec = recognize(world.data, world.request, attachments=[Attachment(scan.name, path=scan)])
        kept += keeps
        if rec.recognized:
            recognized += 1
            wrong += rec.copy.reference != ref
            assert rec.rung is Rung.MARK
        if keeps:                                                         # the floor: a marker that survives is recognized
            assert rec.recognized and rec.copy.reference == ref, (p, rec.note)
        else:                                                             # a marker lost: never a copy, and a form we know
            lost.append(rec)
    assert wrong == 0 and len(scans) == 20
    assert recognized == kept >= 17, (kept, recognized)                   # measured: 18 of 20 kept their marker
    assert all(r.outcome is Outcome.CANDIDATE and r.rung is Rung.LAYOUT and r.copy is None for r in lost), [r.note for r in lost]


@needs_ocr
def test_the_clean_office_home_phone_and_upside_down_profiles_each_read_their_copy(world):
    filled = returned(world, 3)
    for name in ("clean", "office", "home", "phone", "upside-down"):
        p = PROFILES[name]
        scan = simulate(filled, filled.with_name(f"profile-{name}.pdf"), dpi=p.dpi, angle=p.angle, scale=p.scale,
                        shift=p.shift, noise=p.noise, blur=p.blur, jpeg=p.jpeg, gamma=p.gamma)
        rec = recognize(world.data, world.request, attachments=[Attachment(scan.name, path=scan)])
        assert rec.recognized and rec.copy.reference == world.refs[3] and rec.rung is Rung.MARK, (name, rec.note)
        assert rec.copy.unit == "104 Example Way"
        assert rec.sure in (Sure.HIGH, Sure.MEDIUM)                          # medium when a character was put right


@needs_ocr
def test_a_photograph_in_an_image_file_is_read_like_a_scanned_pdf(world):
    scan = scanned(returned(world, 4), "photo-source.pdf", dpi=150)
    with pymupdf.open(scan) as doc:
        png = doc[0].get_pixmap(dpi=150).tobytes("png")
    rec = recognize(world.data, world.request, attachments=[Attachment("IMG_0042.png", data=png)])
    assert rec.recognized and rec.copy.reference == world.refs[4] and rec.rung is Rung.MARK


@needs_ocr
def test_a_copy_with_no_marker_is_known_by_its_printed_lines_and_is_a_candidate_never_recognized(world):
    plain = scanned(world.blank, "download-printed.pdf", angle=-0.6)        # the form downloaded, not a sent copy
    rec = recognize(world.data, world.request, attachments=[Attachment(plain.name, path=plain)])
    assert rec.outcome is Outcome.CANDIDATE and rec.rung is Rung.LAYOUT and rec.copy is None and rec.lines >= 4
    assert rec.form == "owner-info" and rec.sure in (Sure.MEDIUM, Sure.LOW) and "not a copy we sent" in rec.note
    assert Rung.MARK in rec.tried and Rung.LAYOUT in rec.tried
    no_request = recognize(world.data, attachments=[Attachment(plain.name, path=plain)])     # no layout to match
    assert no_request.outcome is Outcome.NOT_OURS


# -- the negatives -----------------------------------------------------------------------------------------------------------

@needs_ocr
def test_what_is_not_ours_is_never_recognized(world):
    invoice_lines = ["ACME PEST CONTROL, INC.", "INVOICE No. 2291-B", "Bill to: Example Homeowners Association",
                     "Service date: September 12, 2026    Due: October 12, 2026", "Quarterly pest service, common areas   $1,204.00",
                     "Backflow test report (3 devices)    $225.00", "Total due: $1,429.00", "Remit to: PO Box 100, Example City",
                     "Thank you for your business. Terms: net 30. A 1.5% monthly charge applies to balances past due."]
    certificate = ["CERTIFICATE OF LIABILITY INSURANCE", "Date: 09/20/2026", "Producer: Example Insurance Agency",
                   "Insured: Example Homeowners Association", "General aggregate $2,000,000   Each occurrence $1,000,000",
                   "Certificate holder: Example Management Company", "Policy period 10/01/2026 to 10/01/2027",
                   "This certificate is issued as a matter of information only and confers no rights on the holder."]
    minutes = ["MINUTES OF THE REGULAR MEETING OF THE BOARD OF DIRECTORS", "Held September 24, 2026 at 6:30 p.m.",
               "Present: the president, the secretary, the treasurer. A quorum was present.", "1. Approval of the agenda.",
               "2. Treasurer's report: the operating account balance was reviewed. 3. Landscape contract.",
               "Motion carried. The meeting was adjourned at 7:45 p.m."]
    other_form = ["POOL KEY REQUEST", "Name: ______________________________", "Unit address: ______________________",
                  "[ ] I need a replacement key   [ ] I need an additional key", "Number of keys: ____    Signature: ___________",
                  "Return this request to the management office. A $25 deposit is due for each key."]
    running = ["Dear owner,", "As the Association's policy statement explains, Civil Code section 4041 requires the Association "
               "to", "send each member a request for their delivery preferences once a year, and the Association does so.",
               "This letter reports that the board met on the matter and made no change to its practice.", "Sincerely,",
               "The Board of Directors"]
    foreign = ["Owner Information", "Ref " + make("NP", 2027, Channel.EMAIL, membership_id=999, unit_id=999).text,
               "A form from some other association: please keep this copy for your records."]
    paper = world.data / "negatives"
    paper.mkdir()
    corpus = {"invoice, a text PDF": text_pdf(paper / "invoice.pdf", invoice_lines),
              "invoice, scanned": scanned(text_pdf(paper / "invoice2.pdf", invoice_lines), "invoice-scan.pdf"),
              "certificate, scanned": scanned(text_pdf(paper / "cert.pdf", certificate), "cert-scan.pdf", dpi=200),
              "minutes, scanned": scanned(text_pdf(paper / "minutes.pdf", minutes), "minutes-scan.pdf"),
              "blank page, scanned": scanned(text_pdf(paper / "blank.pdf", [" "]), "blank-scan.pdf"),
              "another form, scanned": scanned(text_pdf(paper / "pool.pdf", other_form), "pool-scan.pdf"),
              "a page citing the section, scanned": scanned(text_pdf(paper / "running.pdf", running), "running-scan.pdf"),
              "a reference we did not send, scanned": scanned(text_pdf(paper / "foreign.pdf", foreign), "foreign-scan.pdf", dpi=200)}
    assert len(corpus) == 8
    results = {name: recognize(world.data, world.request, attachments=[Attachment(path.name, path=path)])
               for name, path in corpus.items()}
    assert not [name for name, r in results.items() if r.recognized], {n: r.note for n, r in results.items() if r.recognized}
    assert all(r.copy is None for r in results.values())
    for name in ("invoice, a text PDF", "invoice, scanned", "certificate, scanned", "minutes, scanned", "blank page, scanned",
                 "another form, scanned"):
        assert results[name].outcome is Outcome.NOT_OURS, (name, results[name].note)
    cited = results["a page citing the section, scanned"]
    assert cited.outcome is Outcome.CANDIDATE and cited.rung is Rung.CITATION and cited.sure is Sure.LOW   # at most a candidate
    foreign_result = results["a reference we did not send, scanned"]
    assert foreign_result.unsent and "a reference we did not send" in foreign_result.note and not foreign_result.recognized
