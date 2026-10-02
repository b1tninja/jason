"""Packets: statutory passages cut from the law, parts found for the year, and the parts merged into one PDF."""

import json

import pymupdf

from jason.community import mystique
from jason.community.packets import Part, PartSource, SourceKind, page_list
from jason.community.statute_passages import passages, quoted_after
from jason.tasks.packets import insurance_rows, letter_text, merge, plan, resolve, statement_html

SECTION = (
    "(a) The policy statement shall include the following notice:\n\n\n"
    "“NOTICE\n\nAssessments become delinquent 15 days\nafter they are due. (“due” means owed)”\n\n(b) Other."
)


def test_a_quoted_passage_is_cut_whole_with_its_wrapping_undone():
    assert quoted_after(SECTION, "(a)") == "NOTICE\n\nAssessments become delinquent 15 days after they are due. (“due” means owed)"


def test_every_statutory_token_comes_from_its_section():
    sections = {"CIV 5730": SECTION, "CIV 5965": "(a) Summary:\n“Failure of a member\nmay result.”",
                "CIV 5300": "(9) Summary “This summary.”\n(10) FHA “FHA words.”\n(11) VA “VA words.”"}
    values, gaps = passages(None, lookup=lambda c: {"found": c in sections, "text": sections.get(c, "")})
    assert not gaps
    assert values["ADR_STATEMENT"] == "Failure of a member may result."
    assert (values["INSURANCE_STATEMENT"], values["FHA_STATEMENT"], values["VA_STATEMENT"]) == ("This summary.", "FHA words.", "VA words.")


def test_the_fha_form_fills_its_circled_choices_only_when_known():
    words = "This development [is/is not (circle one)] a condominium project. It [is/is not (circle one)] certified."
    assert "is a condominium project" in statement_html(words) and "[is/is not (circle one)] certified" in statement_html(words)
    assert "It is not certified" in statement_html(words, certified="is not")


def test_page_lists_and_parts_found_for_the_year():
    assert page_list("", 3) == [0, 1, 2] and page_list("1-2,5", 4) == [0, 1]
    library = [{"id": 1, "path": "Financials/2026/Pro Forma Budget - 2026.pdf", "updatedAt": "2026-04-30"},
               {"id": 2, "path": "Financials/2027/Pro Forma Budget - 2027.pdf", "updatedAt": "2026-11-01"},
               {"id": 3, "path": "Financials/2027/Pro Forma Budget - 2027 v2.pdf", "updatedAt": "2026-11-15"}]
    part = Part("Budget", PartSource(SourceKind.LIBRARY, pattern=r"^Financials/{year}/Pro Forma Budget"))
    assert resolve(part, 2027, library=library, drive=[]).ref == "3"          # the newest of the year's
    assert not resolve(part, 2028, library=library, drive=[]).found
    assert not resolve(Part("Cover", PartSource(SourceKind.TEMPLATE, "")), 2027, library=[], drive=[]).found


def test_page_rules_keep_the_declarations_and_never_empty_a_part():
    from jason.community.packets import chosen_pages

    flood = ["Agency cover letter. This packet includes: Flood Insurance Policy Declarations", "Notify us after the flood",
             "RATE CATEGORY INSURED NAME(S) AND MAILING ADDRESS", "PRIVACY POLICY NOTICE"]
    assert chosen_pages(flood, PartSource(SourceKind.LIBRARY, keep=r"INSURED NAME\(S\) AND MAILING ADDRESS")) == ("3", "")
    master = ["notice", "POLICY DECLARATIONS POLICY PERIOD: FROM", "COVERAGES AND LIMITS", "COVERAGE AND LIMITS",
              "SCHEDULE OF FORMS AND ENDORSEMENTS: POLICY DECLARATIONS - Condominium Assoc."]
    assert chosen_pages(master, PartSource(SourceKind.DRIVE, keep=r"POLICY PERIOD:|COVERAGES? AND LIMITS")) == ("2-4", "")
    assert chosen_pages(flood, PartSource(SourceKind.LIBRARY, drop="PRIVACY")) == ("1-3", "")
    pages, note = chosen_pages(flood, PartSource(SourceKind.LIBRARY, keep="NOT THERE"))
    assert pages == "" and note                                                # every page kept, and said so


def test_a_years_values_can_stub_in_a_linked_document(tmp_path):
    from jason.tasks.packets import drive_id

    doc = "1t61dEl-6IsyyCiiU_Z04q2sAWciEOs2AJvIXBydnZ0k"
    assert drive_id(f"https://docs.google.com/document/d/{doc}/edit?usp=sharing") == doc
    assert drive_id(f"https://drive.google.com/open?id={doc}") == doc and drive_id(doc) == doc
    assert drive_id("not a link") == ""

    community = mystique()
    annual = community.packet("annual-disclosures")
    folder = tmp_path / "packets" / "annual-disclosures-2027"
    folder.mkdir(parents=True)
    (folder / "values.json").write_text(json.dumps({"_links": {
        "Disclosure regarding pending litigation": f"https://docs.google.com/document/d/{doc}/edit",
        "No such part": doc}}))
    found = plan(community, annual, 2027, tmp_path, library=[], drive=[{"id": doc, "path": "My Drive/Pending Litigation Disclosure"}],
                 passages=lambda d: ({}, []), variant="1")
    linked = next(r for r in found.parts if r.part.title == "Disclosure regarding pending litigation")
    assert linked.found and linked.ref == doc and linked.where == "My Drive/Pending Litigation Disclosure"
    assert "_links" not in found.values                                       # a link is not a token
    assert any("No such part" in g for g in found.gaps)


def test_the_annual_packet_plans_with_its_tokens(tmp_path):
    community = mystique()
    found = plan(community, community.packet("annual-disclosures"), 2027, tmp_path, library=[], drive=[],
                 passages=lambda d: ({"ADR_STATEMENT": "x"}, []))
    assert "FISCAL_YEAR" in found.tokens and found.values["FISCAL_YEAR"] == "2027"
    assert "DEFERRAL_STATEMENT" in found.unfilled                            # the board's statement stays open
    (tmp_path / "packets" / "annual-disclosures-2027").mkdir(parents=True)
    (tmp_path / "packets" / "annual-disclosures-2027" / "values.json").write_text(json.dumps({"DEFERRAL_STATEMENT": "None."}))
    again = plan(community, community.packet("annual-disclosures"), 2027, tmp_path, library=[], drive=[],
                 passages=lambda d: ({}, []))
    assert "DEFERRAL_STATEMENT" not in again.unfilled


def _pdf(path, pages):
    doc = pymupdf.open()
    for i in range(pages):
        doc.new_page().insert_text((72, 72), f"{path.stem} page {i + 1}")
    doc.save(path)
    return path


def test_merge_orders_parts_with_bookmarks_and_page_numbers(tmp_path):
    a, b = _pdf(tmp_path / "a.pdf", 2), _pdf(tmp_path / "b.pdf", 3)
    record = merge([("Cover", a, ""), ("Budget", b, "2-3")], tmp_path / "packet.pdf", footer="Mystique")
    doc = pymupdf.open(tmp_path / "packet.pdf")
    assert doc.page_count == 4
    assert doc.get_toc() == [[1, "Cover", 1], [1, "Budget", 3]]
    assert "Page 4 of 4" in doc[3].get_text() and "b page 2" in doc[2].get_text()
    assert record[1]["firstPage"] == 3 and record[1]["pageCount"] == 2 and len(record[0]["sha256"]) == 64


def test_a_part_on_its_own_sheet_gets_its_own_paper_when_printed_on_both_sides(tmp_path):
    from jason.tasks.packets import BLANK

    a, b, c = _pdf(tmp_path / "a.pdf", 1), _pdf(tmp_path / "fha.pdf", 1), _pdf(tmp_path / "va.pdf", 1)
    record = merge([("Cover", a, ""), ("FHA", b, "", True), ("VA", c, "", True), ("Policy", a, "")], tmp_path / "p.pdf")
    doc = pymupdf.open(tmp_path / "p.pdf")
    # cover | blank (back of the cover) | FHA | blank | VA | blank | policy
    assert [r["firstPage"] for r in record] == [1, 3, 5, 7] and doc.page_count == 7
    assert all(BLANK in doc[i].get_text() for i in (1, 3, 5))
    community = mystique()
    sheets = [p.title for p in community.packet("annual-disclosures").parts if p.own_sheet]
    assert sheets == ["FHA statement", "VA statement"]                             # 5300(b)(10), (11)


def test_the_insurance_summary_uses_only_terms_in_force_when_the_year_begins():
    policies = [
        {"key": "master", "kind": "master", "terms": [{"start": "2025-09-28", "end": "2026-09-28", "carrier": "A",
                                                        "limits": {"building_limit": 100}, "deductible": 10}]},
        {"key": "flood-3", "kind": "flood", "building": 3, "terms": [{"start": "2026-12-03", "end": "2027-12-03",
         "carrier": "PHILADELPHIA INDEMNITY", "number": "501", "limits": {"limit": 300000000}, "deductible": 200000}]},
        {"key": "workers-comp", "kind": "workers_comp", "terms": []},
    ]
    rows, gaps = insurance_rows(policies, 2027, not_carried=("earthquake",))
    assert rows[0] == ["Flood (Building 3)", "Philadelphia Indemnity", "501", "Dec 3, 2026 to Dec 3, 2027", "$3,000,000", "$2,000"]
    assert rows[-1][0] == "Earthquake"
    assert len(gaps) == 1 and "master" in gaps[0]                            # last year's term is never printed


def test_a_passage_is_found_in_a_doc_by_its_ends():
    from jason.commands.packet import text_range

    doc = {"body": {"content": [{"paragraph": {"elements": [
        {"startIndex": 1, "textRun": {"content": "Intro.\n"}},
        {"startIndex": 8, "textRun": {"content": "\U0001F3E0 NOTICE begins here and ends.\n"}}]}}]}}
    assert text_range(doc, "NOTICE begins", "ends.") == (11, 39)          # the emoji is two UTF-16 units


def test_one_form_definition_makes_the_paper_form_and_the_payhoa_sheet():
    from jason.community.form_render import BOX, paper_markdown, payhoa_sheet
    from jason.community.spec import spec_module
    from jason.tasks.packets import template_markdown

    form = spec_module("forms").OWNER_INFO
    paper = "\n".join(paper_markdown(form))
    sheet = "\n".join(payhoa_sheet(form))
    assert "You do not have to provide an email address" in paper                 # CIV 4041(b)(2)(A)
    assert "change your preferences at any time" in paper                          # CIV 4041(b)(2)(B)
    assert f"{BOX} By mail" in paper and f"{BOX} Rented out" in paper and "Signature of owner" in paper
    for q in form.questions:                                                       # the same questions, both ways
        assert q.title.replace(" (optional)", "") in paper and q.title in sheet
    rendered = "\n".join(template_markdown("form:owner-info"))
    # the form prints the way online, not a link: one printed form serves every unit, and a PayHOA form link must
    # name the unit (an emailed copy links the phrase to its own unit's form)
    assert "{RETURN_BY}" in rendered and "online in PayHOA: sign in, choose Requests" in rendered
    assert "{OWNER_FORM_LINK}" not in rendered


def test_the_annual_packet_ends_with_the_owner_form_and_it_also_stands_alone():
    community = mystique()
    annual = community.packet("annual-disclosures")
    assert annual.parts[-1].source.markdown == "form:owner-info"
    alone = community.packet("owner-information")
    assert alone.parts[0].source.ref == "letter:owner-information-cover.html"           # a cover letter, then the form
    assert [p.source.markdown for p in alone.parts][-1] == "form:owner-info"
    # no page of its own for signing in to PayHOA: a sixth billed page would add $2.25 of postage a letter
    assert len(alone.parts) == 2 and "{PAYHOA_SIGN_UP}" in letter_text("letter:owner-information-cover.html")
    values = dict(alone.values)
    assert values["PAYHOA_SIGN_UP"].startswith("https://app.payhoa.com/sign-up/27889-")


def test_the_annual_packet_is_made_per_building_with_each_buildings_flood_policy(tmp_path):
    from jason.tasks.packets import varies

    community = mystique()
    annual = community.packet("annual-disclosures")
    assert annual.variants == tuple(str(b) for b in range(1, 9))
    library = [{"id": 7, "path": "Insurance/FLOOD POLICY 25-26 BLDG 4.pdf", "updatedAt": "2025-12-01"},
               {"id": 8, "path": "Insurance/FLOOD POLICY 26-27 BLDG 3.pdf", "updatedAt": "2026-10-01"},
               {"id": 9, "path": "Insurance/Certificate of Insurance 2026-2027.pdf", "updatedAt": "2026-10-01"}]
    for variant, expected in (("3", "8"), ("4", "7")):
        found = plan(community, annual, 2027, tmp_path, library=library, drive=[],
                     passages=lambda d: ({}, []), variant=variant)
        by_title = {r.part.title: r for r in found.parts}
        assert by_title[f"Flood policy declarations, Building {variant}"].ref == expected
        assert by_title["Certificate of Insurance"].ref == "9"                 # {prior}-{year}: 2026-2027
        assert found.values["BUILDING"] == variant
    shared = [p.title for p in annual.parts if not varies(p)]
    assert "Notice of the Association's insurance" in shared and "Insurance summary" in shared
    assert not any("{building}" in t for t in shared)


def _flood(*terms):
    return [{"key": "flood-4", "kind": "flood", "building": 4, "terms": [
        {"start": s, "end": e, "number": "501", "carrier": "PHILADELPHIA INDEMNITY INSURANCE COMPANY",
         "limits": {"limit": limit}, "deductible": deductible} for s, e, limit, deductible in terms]}]


def test_a_flood_notice_says_where_the_buildings_policy_stands():
    from datetime import date

    from jason.tasks.packets import flood_values

    renewed = _flood(("2025-12-03", "2026-12-03", 250000000, 200000), ("2026-12-03", "2027-12-03", 250000000, 200000))
    values, gaps = flood_values(renewed, 4, 10, fiscal_year=2027, today=date(2026, 10, 1))
    assert "has renewed" in values["FLOOD_STANDING"] and "December 3, 2026" in values["FLOOD_STANDING"]
    assert values["FLOOD_LIMIT"] == "$2,500,000 (10 units at $250,000 each, the federal maximum)"
    assert values["FLOOD_CARRIER"] == "Philadelphia Indemnity Insurance Company" and not gaps
    assert "same limit and deductible" in values["FLOOD_CHANGE"]

    pending = _flood(("2025-12-19", "2026-12-19", 250000000, 200000))
    values, gaps = flood_values(pending, 4, 10, fiscal_year=2027, today=date(2026, 10, 1))
    assert "due to renew" in values["FLOOD_STANDING"] and gaps                        # never last term as this year's

    raised = _flood(("2025-12-03", "2026-12-03", 250000000, 200000), ("2026-12-03", "2027-12-03", 250000000, 500000))
    values, gaps = flood_values(raised, 4, 9, fiscal_year=2027, today=date(2026, 10, 1))
    assert "$2,000 to $5,000" in values["FLOOD_CHANGE"] and any("5810" in g for g in gaps)
    assert values["FLOOD_LIMIT"] == "$2,500,000"                                     # not 9 units at the maximum


def test_a_letter_is_filled_with_escaped_values_and_names_what_is_open():
    from jason.tasks.packets import fill_letter

    body, left = fill_letter("letter:flood-notice.html", {"BUILDING": "3", "FLOOD_CARRIER": "A & B"})
    assert "Building 3" in body and "A &amp; B" in body
    assert "FLOOD_NUMBER" in left and "BUILDING" not in left


class _Drive:
    """A stand-in Drive: the folder's Docs, and every write."""

    def __init__(self, files):
        self.files, self.calls = files, []

    def list_files(self, query, *, fields=""):
        return list(self.files)

    def export_bytes(self, file_id, mime_type):
        self.calls.append(("export", file_id))
        return b"docx"

    def replace_content(self, file_id, content, *, mime_type):
        self.calls.append(("replace", file_id))

    def copy(self, file_id, name, parent_id=None):
        self.calls.append(("copy", file_id))
        return "new"

    def _get(self, path, params):
        return {"appProperties": {}}

    _http = None


class _Docs:
    def batch_update(self, doc_id, requests):
        pass

    def get(self, doc_id):
        return {"body": {"content": []}}


def test_a_filled_doc_is_refreshed_in_place_and_older_copies_are_only_reported(monkeypatch):
    from jason.google import drive_properties
    from jason.tasks.packets import fill_doc

    monkeypatch.setattr(drive_properties, "set_app_properties", lambda drive, file_id, props: props)
    drive = _Drive([{"id": "old", "modifiedTime": "2026-10-01T08:00:00Z"},
                    {"id": "newest", "modifiedTime": "2026-10-01T09:00:00Z"},
                    {"id": "another template's", "modifiedTime": "2026-10-01T10:00:00Z",
                     "appProperties": {"jason_filled_from": "other"}}])
    extras: list[str] = []
    doc_id, _ = fill_doc(drive, _Docs(), "tpl", {"A": "1"}, name="Form 2027", folder_id="f", extras=extras)
    assert doc_id == "newest" and ("replace", "newest") in drive.calls and not any(c[0] == "copy" for c in drive.calls)
    assert extras == ["old"]                                          # reported, never deleted
    empty = _Drive([])
    assert fill_doc(empty, _Docs(), "tpl", {}, name="Form 2027", folder_id="f")[0] == "new"
    assert ("copy", "tpl") in empty.calls


def test_a_forms_questions_are_kept_on_one_page_each():
    from jason.tasks.packets import keep_together_requests

    def para(start, text, style="NORMAL_TEXT"):
        return {"startIndex": start, "endIndex": start + len(text) + 1,
                "paragraph": {"elements": [{"textRun": {"content": text + "\n"}}], "paragraphStyle": {"namedStyleType": style}}}

    doc = {"body": {"content": [para(1, "Owner Information", "TITLE"), para(20, "Each year ..."),
                                para(40, "1. Owner name(s)"), para(60, "As shown on the deed."), para(90, "____"),
                                para(100, ""), para(102, "Notice delivery", "HEADING_3"), para(120, "2. How should ..."),
                                para(140, "Check one. ☐ By mail"), para(170, ""),
                                para(172, "Certification. I certify ..."), para(200, "Signature of owner ____"),
                                para(230, "The Association uses this information ...")]}}
    styles = [(r["updateParagraphStyle"]["range"]["startIndex"], r["updateParagraphStyle"]["paragraphStyle"]["keepWithNext"])
              for r in keep_together_requests(doc)]
    assert styles == [(40, True), (60, True), (90, False),                 # question 1, its help, its line; not the blank
                      (120, True), (140, False),
                      (172, True), (200, False)]                           # the certification with the signature
