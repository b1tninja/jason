"""The citation closure (``jason cite``) on made-up documents: narrowing, siblings, spans, dates, misses with reasons,
the reference walk, and what cites a section."""

import json
import sqlite3
from datetime import date
from types import SimpleNamespace

import pytest

from jason.community.cite import (Holder, Kind, Miss, Reason, Scope, Target, Treatment, Unit, label_text, of_reference,
                                  parse, scope_of, targets_in)
from jason.community.living import LivingDocument, LivingInstrument, SourceKind, SourceRef
from jason.community.outlines import CitableDocument, DocumentOutline, Section
from jason.community.section_refs import SectionRefError, expand_markdown
from jason.community.symbols import DocumentKind
from jason.tasks.cite import Shelf, markdown, resolve

OLD = ("No more than ten percent (10%) of the Lots shall be let at any one time, except as this Section allows for a "
       "hardship the Board approves in writing.")
NEW = ("No more than fifteen percent (15%) of the Lots shall be let at any one time, except as this Section allows for "
       "a hardship the Board approves in writing.")
NOTICE = "An Owner who lets a Lot shall give the Board written notice of the letting within ten days."
BIRDS = "No poultry or livestock shall be kept on any Lot. The Board may adopt rules for birds kept as pets."

BASE = f"""ARTICLE 6
6.2 Letting of Lots.
(a) Limit. {OLD}
(b) Notice. {NOTICE}
6.3 Animals. {BIRDS}
"""

STATUTE = """- History: made-up

4920. (Made up for a test.)

(a) Except as provided in subdivision (b), notice of a meeting is given four days before it.

(b) (1) An emergency meeting needs no notice.

(2) A meeting held solely in executive session is noticed two days before it.

(c) Notice is given by general delivery.
"""


def _run(text, bold=False, strike=False):
    return {"textRun": {"content": text, "textStyle": {"bold": bold, "strikethrough": strike}}}


def _amendment():
    paragraphs = [
        [_run("NOW, THEREFORE, the Association declares:\n")],
        [_run("Article 6, Section 6.2, subsection (a) (\"Limit\") is hereby amended and restated as follows "
              "(stricken out wording will be removed, and bolded wording will be added):\n")],
        [_run("No more than "), _run("ten percent (10%)", strike=True), _run(" "),
         _run("fifteen percent (15%)", bold=True), _run(OLD.split("(10%)", 1)[1] + "\n")],
        [_run("IN WITNESS WHEREOF, the Board.\n")],
    ]
    return {"revisionId": "rev-1", "body": {"content": [{"paragraph": {"elements": p}} for p in paragraphs]}}


def _outline(key, title, kind, text, sections, **more):
    return DocumentOutline(key, title, kind=kind, text=text, sections=sections, **more)


@pytest.fixture
def world(tmp_path):
    lib = tmp_path / "library"
    (lib / "text").mkdir(parents=True)
    with sqlite3.connect(lib / "library.db") as conn:
        conn.execute("CREATE TABLE documents (id TEXT, path TEXT, kind TEXT, confidential INTEGER, sha256 TEXT)")
        conn.execute("INSERT INTO documents VALUES ('1', 'Governing/Covenants.pdf', 'declaration', 0, 'abc')")
    (lib / "text" / "1.txt").write_text(BASE, encoding="utf-8")
    sources = tmp_path / "living" / "decl" / "sources"
    sources.mkdir(parents=True)
    (sources / "doc-2.json").write_text(json.dumps(_amendment()), encoding="utf-8")
    second = SimpleNamespace(title="First Amendment", recorded=date(2024, 3, 1), adopted=None,
                             recorder_number="209901010001")
    living = LivingDocument("decl", "Covenants", DocumentKind.DECLARATION,
                            base=SourceRef(SourceKind.LIBRARY_TEXT, "Governing/Covenants.pdf", sha256="abc"),
                            base_from="the recorded copy",
                            instruments=(LivingInstrument("decl-1st", second, SourceRef(SourceKind.DOC, "doc-2")),))
    outlines = tmp_path / "outlines"
    outlines.mkdir()
    rules_text = ("B-1. Letting.\nOwners who let a Lot follow the Covenants.\nB-2. Pets.\nBirds are pets under the "
                  "Covenants.\n")
    rules = _outline("rules", "Handbook", "operating_rules", rules_text,
                     [Section("B-1", "Letting.", 1, 0, 42), Section("B-2", "Pets.", 1, 42, len(rules_text))],
                     aliases=["Handbook"])
    resolution_text = "RESOLUTION 20990101-1\nThe Board adopts a letting form under Section 6.2(b) of the Covenants."
    resolution = _outline("resolution-letting-form-ab12", "Resolution - Letting Form", "resolution", resolution_text,
                          [], numbers=["20990101-1"])
    for o in (rules, resolution):
        (outlines / f"{o.key}.json").write_text(json.dumps(o.to_dict()), encoding="utf-8")
    rows = [
        {"source": "decl", "source_section": "6.2(a)", "kind": "section", "target": "decl#6.3", "relation": "cites",
         "quote": "see Section 6.3", "offset": 1, "prior": False},
        {"source": "decl", "source_section": "6.3", "kind": "section", "target": "decl#6.2(a)", "relation": "cites",
         "quote": "as Section 6.2(a) limits", "offset": 2, "prior": False},
        {"source": "decl", "source_section": "6.3", "kind": "statute", "target": "CIV 4920(a)", "relation": "cites",
         "quote": "Civil Code 4920(a)", "offset": 3, "prior": False},
        {"source": "rules", "source_section": "B-1", "kind": "section", "target": "decl#6.2(a)",
         "relation": "acts under", "quote": "Owners who let a Lot follow the Covenants.", "offset": 4, "prior": False},
        {"source": "rules", "source_section": "B-2", "kind": "section", "target": "decl#9.9", "relation": "cites",
         "quote": "Birds are pets.", "offset": 5, "prior": False},
        {"source": "resolution-letting-form-ab12", "source_section": "", "kind": "section", "target": "decl#6.2(b)",
         "relation": "acts under", "quote": "under Section 6.2(b) of the Covenants", "offset": 6, "prior": False},
    ]
    (outlines / "references.json").write_text(json.dumps(rows), encoding="utf-8")
    law = tmp_path / "authorities" / "CIV"
    law.mkdir(parents=True)
    (law / "CIV-4900-4955.md").write_text("# Board meetings\n\n## CIV 4920\n" + STATUTE, encoding="utf-8")
    (tmp_path / "authorities" / "manifest.json").write_text(json.dumps({"pages": [{
        "file": "authorities/CIV/CIV-4900-4955.md", "citation": "CIV 4900-4955", "title": "Board Meeting",
        "code": "CIV", "start": "4900", "end": "4955", "sections": ["4920"], "basis": "duty", "why": [],
        "session": "2099"}]}), encoding="utf-8")
    meetings = tmp_path / "meetings"
    (meetings / "minutes-files").mkdir(parents=True)
    (meetings / "minutes-files" / "m1.txt").write_text("The Board met and adopted the letting form.", encoding="utf-8")
    (meetings / "catalog.json").write_text(json.dumps({"meetings": [
        {"date": "2099-01-01", "has": {"minutes": {"Drive": 1}}, "records": [
            {"kind": "minutes", "where": "Drive", "name": "Minutes 1-1-99", "location": "Meetings/Minutes 1-1-99",
             "ref": "m1", "date": "2099-01-01", "confidential": False}]},
        {"date": "2099-02-01", "has": {"agenda": {"Drive": 1}}, "records": [
            {"kind": "agenda", "where": "Drive", "name": "Agenda", "location": "Meetings/Agenda", "ref": "a1"}]}]}),
        encoding="utf-8")
    conflict = SimpleNamespace(key="letting-cap", provision="Covenants 6.2(a)", authority="CIV 4741(b)",
                               says="Caps letting at a share of the Lots.")
    community = SimpleNamespace(
        living_documents=lambda: (living,),
        citable_documents=lambda: (CitableDocument("decl", "Covenants", "doc-1", DocumentKind.DECLARATION,
                                                   aliases=("Covenants", "Declaration"), cite_as="Covenants"),
                                   CitableDocument("rules", "Handbook", "doc-3", DocumentKind.OPERATING_RULES,
                                                   aliases=("Handbook",))),
        conflicts=lambda: (conflict,), notice_provisions=lambda: ())
    return Shelf(community, tmp_path, repo=tmp_path / "no-repo"), tmp_path


# --- The grammar --------------------------------------------------------------------------------------------------------

NAMES = {"covenants": "decl", "declaration": "decl", "decl": "decl", "handbook": "rules", "rules": "rules"}


@pytest.mark.parametrize("expression, expect", [
    ("Covenants § 6.2(a)", "decl#6.2(a)"),
    ("Section 6.2(a) of the Declaration", "decl#6.2(a)"),
    ("Covenants, Section 6.2 (a)", "decl#6.2(a)"),
    ("Handbook B-1", "rules#B-1"),
    ("decl#6.2(a)", "decl#6.2(a)"),
    ("Covenants 6.2(a) and (b)", "decl#6.2(a),6.2(b)"),
    ("Covenants Sections 6.2 through 6.3", "decl#6.2..6.3"),
    ("Covenants", "decl"),
    ("Resolution 20990101-1", "resolution:20990101-1"),
    ("Administrative Resolution No. 20990101-1", "resolution:20990101-1"),
    ("Doc. No. 209901010001", "instrument:209901010001"),
    ("209901010001", "instrument:209901010001"),
    ("minutes of the meeting of 2099-01-01", "minutes:2099-01-01"),
    ("CIV 4920(a)", "CIV 4920(a)"),
    ("Civil Code § 4920(b)(1)", "CIV 4920(b)(1)"),
    ("Cal. Civ. Code section 4920", "CIV 4920"),
    ("Section 4920 of the Civil Code", "CIV 4920"),
    ("CIV 4000-6150", "CIV 4000-6150"),
    ("10 CCR 2792.23", "10 CCR 2792.23"),
    ("Section 5200", "CIV 5200"),
    ("decl#6.2(a)@2024-01-01", "decl#6.2(a)@2024-01-01"),
    ("Covenants 6.2(a) as of 2024-01-01", "decl#6.2(a)@2024-01-01"),
])
def test_the_forms_people_and_documents_write(expression, expect):
    found = parse(expression, NAMES)
    assert isinstance(found, Target), found
    assert found.id == expect


def test_an_article_is_named_as_one():
    found = parse("Covenants Art. 6", NAMES)
    assert found.article and found.number == "6"


@pytest.mark.parametrize("expression, reason", [("", Reason.EMPTY), ("6.2(a)", Reason.UNPARSED),
                                                ("Bylaws 6.2", Reason.UNKNOWN_DOCUMENT),
                                                ("nope#1.1", Reason.UNKNOWN_DOCUMENT),
                                                ("Covenants 6.2(a) whereupon", Reason.UNPARSED)])
def test_what_cannot_be_read_is_a_miss_with_its_reason(expression, reason):
    found = parse(expression, NAMES)
    assert isinstance(found, Miss) and found.reason is reason


def test_free_text_names_sections_statutes_and_lettered_rules():
    found = {t.id for t in targets_in("Covenants 6.2(a) and 6.3 yield to CIV 4741(b); see Handbook B-2 and "
                                      "rules#B-1.", NAMES)}
    assert {"decl#6.2(a)", "CIV 4741(b)", "rules#B-2", "rules#B-1"} <= found


def test_scope_and_references():
    a, whole = of_reference("decl#6.2(a)"), of_reference("decl#6.2")
    assert scope_of(a, whole) is Scope.WITHIN and scope_of(whole, a) is Scope.ENCLOSING
    assert scope_of(of_reference("decl"), a) is None            # the document by name does not cite each section
    assert of_reference("named:the Act") is None and of_reference("CIV 4920(a)").base == "CIV 4920"


def test_a_statute_subdivision_is_split_from_its_section():
    assert label_text(STATUTE, ["b", "2"]).startswith("(2) A meeting held solely in executive session")
    assert label_text(STATUTE, ["b"]).count("(") >= 2 and "(c)" not in label_text(STATUTE, ["b"])
    assert label_text(STATUTE, ["d"]) == ""


# --- The closure ---------------------------------------------------------------------------------------------------------

def test_narrowing_step_by_step_gives_the_documents_own_citation_and_words(world):
    shelf, _ = world
    c = shelf.doc("Covenants").section("6.2")("a")
    assert str(c) == "Covenants Section 6.2(a)" and c.kind is Kind.SECTION and c.found
    assert "fifteen percent (15%)" in c.text
    assert c.version["setBy"] == "decl-1st" and c.version["amended"]
    assert "First Amendment" in c.in_force and "2024-03-01" in c.in_force
    assert [h["instrument"] for h in c.history] == ["decl-1st"]
    assert shelf.doc("Covenants").section("6.2(a)").id == c.id
    assert c.containing("hardship").startswith("No more than fifteen")


def test_a_parent_names_the_subsection_an_amendment_changed(world):
    shelf, _ = world
    c = shelf("Covenants 6.2")
    assert "fifteen percent (15%)" in c.text and c.version["setBy"] == "decl"
    assert c.in_force.startswith("as written in the Covenants, except 6.2(a), as amended by First Amendment")
    assert "in force from 2024-03-01" in c.in_force
    assert c.version["amended"] and [p["section"] for p in c.version["parts"]] == ["6.2(a)"]
    text, _ = expand_markdown("{QUOTE:decl#6.2}", shelf)
    assert "except 6.2(a), as amended by First Amendment" in text


def test_every_sections_history_and_provenance_agree(world):
    """A guard: a section whose history lists an instrument in force reads as amended, and its provenance names that
    instrument; a section with no such history reads as written."""
    shelf, _ = world
    doc, _ = shelf.resolver.document("decl")
    for p in doc.provisions:
        if not p.number or p.removed:
            continue
        c = shelf(f"decl#{p.number}")
        if c.kind is not Kind.SECTION:                  # an article is an outline: each node carries its own flag
            continue
        applied =[h for h in c.history if h.get("applied") and h.get("instrument")]
        assert bool(applied) == bool(c.version["amended"]), p.number
        for h in applied:
            assert h["describe"] in c.version["provenance"], (p.number, h["describe"], c.version["provenance"])
        if not applied:
            assert c.version["provenance"].startswith("as written in") and " except " not in c.version["provenance"]


def test_the_closure_and_a_token_share_one_reader(world):
    shelf, _ = world
    text, records = expand_markdown("{QUOTE:decl#6.2(a)}", shelf)          # the shelf is a Resolver
    c = shelf("Covenants 6.2(a)")
    assert records[0].citation == str(c) and records[0].digest == c.version["digest"]
    assert c.text.strip().splitlines()[-1] in text


def test_as_of_gives_the_words_in_force_that_day(world):
    shelf, _ = world
    before = shelf("Covenants 6.2(a)").as_of("2024-01-01")
    assert "ten percent (10%)" in before.text and not before.version["amended"]
    assert "ten percent (10%)" in shelf("decl#6.2(a)@2024-01-01").text
    assert shelf("Handbook B-1").as_of("2024-01-01").reason is Reason.NOT_KEPT_AS_AMENDED


def test_siblings_spans_articles_and_the_document_are_outlines(world):
    shelf, _ = world
    both = shelf.doc("decl").section("6.2")("a", "b")
    assert both.kind is Kind.OUTLINE and both.found and str(both) == "Covenants Sections 6.2(a) and (b)"
    assert [n["number"] for n in both.outline] == ["6.2(a)", "6.2(b)"] and both.text == ""
    span = shelf.doc("decl").section("6.2").through("6.3")
    assert span.kind is Kind.OUTLINE and [n["number"] for n in span.outline] == ["6.2", "6.2(a)", "6.2(b)", "6.3"]
    assert shelf("Covenants Art. 6").kind is Kind.OUTLINE
    whole = shelf.doc("Covenants")
    assert whole.kind is Kind.OUTLINE and str(whole) == "Covenants"
    assert shelf.doc("decl").section("6.2").subdivisions == ["6.2(a)", "6.2(b)"]
    missing = shelf.doc("decl").section("6.2")("a", "q")
    assert not missing.found and missing.reason is Reason.NOT_IN_DOCUMENT


@pytest.mark.parametrize("expression, reason", [
    ("Covenants 9.9", Reason.NOT_IN_DOCUMENT),
    ("Covenants 6.2(a)(iv)", Reason.PARENT_ONLY),
    ("Bylaws 1.1", Reason.UNKNOWN_DOCUMENT),
    ("CIV 1363", Reason.PRIOR_NUMBERING),
    ("CIV 5300", Reason.STATUTE_NOT_ON_DISK),
    ("CIV 4920(z)", Reason.LABEL_NOT_FOUND),
    ("CIV 4920@2020-01-01", Reason.EDITION_NOT_HELD),
    ("Resolution 20000101-9", Reason.NO_RESOLUTION),
    ("Doc. No. 200001010001", Reason.UNKNOWN_INSTRUMENT),
    ("minutes 2099-02-01", Reason.NO_MINUTES),
    ("record:nothing", Reason.UNKNOWN_RECORD),
])
def test_misses_carry_reasons_and_never_raise(world, expression, reason):
    shelf, _ = world
    got = resolve(expression, shelf=shelf)
    assert got["kind"] == "miss" and not got["found"] and got["reason"] == reason.value


def test_records_and_statutes_are_recited_from_what_is_stored(world):
    shelf, _ = world
    law = shelf("CIV 4920(b)(2)")
    assert law.kind is Kind.STATUTE and law.text.startswith("(2) A meeting held solely") and not law.version["official"]
    assert shelf("CIV 4920").version["official"] and shelf("CIV 4920").subdivisions == ["(a)", "(b)", "(c)"]
    assert shelf("CIV 4900-4955").kind is Kind.OUTLINE
    resolution = shelf.resolution("20990101-1")
    assert resolution.kind is Kind.RECORD and "letting form" in resolution.text
    instrument = shelf.instrument("209901010001")
    assert instrument.found and instrument.version["amends"] == "decl"
    minutes = shelf.minutes("2099-01-01")
    assert minutes.found and minutes.text.startswith("The Board met")


def test_the_walk_marks_missing_targets_and_stops_at_a_repeat(world):
    shelf, _ = world
    root = shelf("Covenants 6.2(a)").hops(None).refs
    assert [c.id for c in root.children] == ["decl#6.3"]
    loop = root.children[0]
    assert {c.id for c in loop.children} == {"decl#6.2(a)", "CIV 4920(a)"}
    back = next(c for c in loop.children if c.id == "decl#6.2(a)")
    assert back.repeat and not back.children
    assert next(c for c in loop.children if c.id == "CIV 4920(a)").found
    one = shelf("Covenants 6.2(a)").hops(1).refs
    assert one.children[0].children == [] and one.children[0].stopped
    same = shelf("Covenants 6.2(a)").hops(None).same().refs
    assert {c.id for c in same.children[0].children} == {"decl#6.2(a)"}
    only = shelf("Covenants 6.3").only("statute").refs
    assert [c.id for c in only.children] == ["CIV 4920(a)"]
    dangling = shelf("Handbook B-2").refs
    assert dangling.children[0].id == "decl#9.9" and not dangling.children[0].found
    assert dangling.children[0].reason == "not_in_document"
    chart = shelf("Handbook B-2").chart
    assert chart.startswith("flowchart LR") and "missing" in chart


def test_cited_by_gives_documents_and_jasons_records_with_a_reading_beside_the_words(world):
    shelf, _ = world
    rows = shelf("Covenants 6.2(a)").cited_by
    by = {(r.holder, r.key) for r in rows}
    assert (Holder.DOCUMENT, "rules#B-1") in by and (Holder.CONFLICT, "conflict:letting-cap") in by
    assert all(r.key != "decl#6.2(a)" for r in rows)              # its own words are not a citation of it
    conflict = next(r for r in rows if r.holder is Holder.CONFLICT and r.field == "provision")
    assert conflict.reading == "Caps letting at a share of the Lots." and "fifteen percent" in conflict.words
    assert conflict.treatment is Treatment.AMENDED
    law = shelf("CIV 4741").cited_by
    assert any(r.holder is Holder.CONFLICT and r.field == "authority" and r.scope is Scope.WITHIN for r in law)
    whole = shelf("Covenants 6.2").cited_by
    assert {r.scope for r in whole} >= {Scope.WITHIN}
    page = markdown(shelf("Covenants 6.2(a)"))
    assert page.index("> No more than fifteen") < page.index("jason's reading")


def test_a_rendering_whose_words_changed_is_stale(world):
    shelf, root = world
    drafts = root / "drafts"
    drafts.mkdir()
    (drafts / "letting.rendered.md.refs.json").write_text(json.dumps({"source": "drafts/letting.md",
        "rendered": "2099-01-02", "references": [
            {"token": "{QUOTE:decl#6.2(a)}", "verb": "QUOTE", "key": "decl", "section": "6.2(a)", "as_of": "",
             "digest": "0000000000000000"},
            {"token": "{QUOTE:decl#6.2(b)}", "verb": "QUOTE", "key": "decl", "section": "6.2(b)", "as_of": "",
             "digest": shelf("decl#6.2(b)").version["digest"]}]}), encoding="utf-8")
    (drafts / "letting.md").write_text("Letting: {QUOTE:decl#6.2(a)}", encoding="utf-8")
    stale = shelf.stale()
    assert [(r.holder, r.target, r.treatment) for r in stale if r.holder is Holder.EMBEDDED] == [
        (Holder.EMBEDDED, "decl#6.2(a)", Treatment.WORDS_CHANGED)]
    assert any(r.target == "decl#9.9" and r.treatment is Treatment.MISSING for r in stale)
    rows = shelf("Covenants 6.2(a)").cited_by
    assert any(r.holder is Holder.EMBEDDED and r.treatment is Treatment.FILLED for r in rows)


def test_a_record_read_from_the_working_copy_is_compared_with_it_too(world):
    shelf, root = world
    copy_text = ("6.2 Letting of Lots.\n(a) Limit. No more than fifteen percent (15%) of the Lots shall be let at any one "
                 "time.\n6.5 Gardens. Each Owner shall keep the yard neat.\n")
    copy = _outline("decl", "Covenants", "declaration", copy_text,
                    [Section("6.2", "Letting of Lots.", 2, 0, 22), Section("6.2(a)", "Limit.", 3, 22, 108),
                     Section("6.5", "Gardens.", 2, 108, len(copy_text))])
    (root / "outlines" / "decl.json").write_text(json.dumps(copy.to_dict()), encoding="utf-8")
    shelf = Shelf(shelf.community, root, repo=root / "no-repo")
    treatment, note = shelf.treat(Target(Unit.SECTION, "decl", "6.5"))
    assert treatment is Treatment.RENUMBERED and "outlines/decl.json" in note
    treatment, _ = shelf.treat(Target(Unit.SECTION, "decl", "6.9"))
    assert treatment is Treatment.MISSING
    treatment, _ = shelf.treat(Target(Unit.SECTION, "decl", "6.2(a)"), quote="Lots shall be let at any one time")
    assert treatment is Treatment.CURRENT
    treatment, _ = shelf.treat(Target(Unit.SECTION, "decl", "6.2(a)"), quote="twenty Lots may be let")
    assert treatment is Treatment.WORDS_CHANGED
    assert shelf.treat(Target(Unit.SECTION, "decl", "RECITALS"))[0] is Treatment.NOT_CHECKED


def test_a_records_section_field_gives_its_numbers():
    from jason.tasks.cite import _numbers_in

    assert _numbers_in("8.5(c), 8.6") == ["8.5(c)", "8.6"]
    assert _numbers_in("12.12(a)-(c)") == ["12.12(a)", "12.12(b)", "12.12(c)"]
    assert _numbers_in("15.2 (the outline's 15.1(a))") == ["15.2"]
    assert _numbers_in("PAYMENTS; preamble") == []


def test_survey_and_most_cited(world):
    shelf, _ = world
    found = shelf.survey()
    assert found["references"] == 6 and found["missed"] == 1 and found["reasons"] == {"not_in_document": 1}
    top = {r["target"]: r for r in shelf.most_cited(200)}
    assert top["decl#6.2(a)"]["total"] >= 3 and top["decl#6.2(a)"]["by"]["conflict row"] == 1


def test_a_document_only_an_outline_knows_is_cited_by_its_title(world):
    shelf, _ = world
    assert shelf.section("rules", "B-1").citation == "Handbook B-1"
    with pytest.raises(SectionRefError) as err:
        shelf.section("decl", "9.9")
    assert err.value.reason == "not_in_document"


def test_the_dict_puts_the_recitation_first(world):
    shelf, _ = world
    got = resolve("Covenants 6.2(a)", shelf=shelf, cited_by=True)
    assert list(got)[:5] == ["kind", "found", "citation", "text", "inForce"]
    assert "official restatement" in got["caveat"]
    reading = next(r for r in got["citedBy"] if r.get("jasonsReading"))
    assert reading["recitedWords"].startswith("Limit.") or "fifteen" in reading["recitedWords"]
