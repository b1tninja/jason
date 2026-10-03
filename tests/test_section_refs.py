"""Embedded references ({QUOTE:key#n}, {CITE:key#n}) and the detector of copied sections, on made-up documents."""

import json
import sqlite3
from datetime import date
from types import SimpleNamespace

import pytest

from jason.community.embedded_copies import (Copy, CopyKind, Currency, Index, SectionVersion, Version, find,
                                             paraphrases, stream)
from jason.community.living import LivingDocument, LivingInstrument, SourceKind, SourceRef
from jason.community.outlines import CitableDocument, DocumentOutline, Section
from jason.community.section_refs import (CAVEAT, SectionRefError, SectionText, citation_of, expand_html,
                                          expand_markdown, parse, refs_in, TOKEN)
from jason.community.symbols import DocumentKind
from jason.tasks import section_refs as sr

OLD_A = ("Not more than twenty percent (20%) of the Units within the project shall be leased or rented at any "
         "particular time, except as this Section allows for a hardship the Board approves in writing.")
NEW_A = ("Not more than twenty-five percent (25%) of the Units within the project shall be leased or rented at any "
         "particular time, except as this Section allows for a hardship the Board approves in writing.")
PETS = ("No animals other than ordinary household pets shall be kept in any Unit, and no pet shall be kept, bred, or "
        "maintained for any commercial purpose whatsoever within the project.")
APPLY = ("An Owner who wishes to lease a Unit shall apply to the Board in writing before the lease begins, and shall "
         "give the Board a copy of the signed lease within ten days.")


# --- Tokens and rendering ------------------------------------------------------------------------------------------------

class FakeResolver:
    def __init__(self, sections):
        self.sections = sections

    def citation(self, key, number):
        if (key, number) not in self.sections:
            raise SectionRefError(f"{key} has no section {number}")
        return citation_of("Declaration", number)

    def section(self, key, number, as_of=None):
        if (key, number) not in self.sections:
            raise SectionRefError(f"{key} has no section {number}")
        caption, words = self.sections[(key, number)]
        return SectionText(key, number, caption, words, self.citation(key, number), "Declaration", "decl-2nd",
                           "the Second Amendment, recorded 2023-12-06", date(2023, 12, 6), True, as_of)


RESOLVER = FakeResolver({("decl", "4.15(a)"): ("Restrictions.", "Restrictions.\n" + NEW_A),
                         ("decl", "4.16"): ("", PETS)})


def test_a_token_reads_its_document_section_and_date():
    ref = refs_in("See {QUOTE:decl#4.15(a) as-of=2025-01-01} and {CITE:decl#4.16}.")
    assert [(r.verb.value, r.key, r.section, r.as_of) for r in ref] == [
        ("QUOTE", "decl", "4.15(a)", date(2025, 1, 1)), ("CITE", "decl", "4.16", None)]
    assert ref[0].text() == "{QUOTE:decl#4.15(a) as-of=2025-01-01}"


@pytest.mark.parametrize("token, why", [("{QUOTE:decl#4.16 when=2025}", "unknown setting"),
                                        ("{CITE:decl#4.16 as-of=2025-01-01}", "a citation has no date"),
                                        ("{QUOTE:decl#4.16 as-of=Jan}", "as-of is a date")])
def test_a_bad_setting_is_refused(token, why):
    with pytest.raises(SectionRefError, match=why):
        parse(TOKEN.search(token))


def test_a_quote_alone_is_a_block_with_its_citation_provenance_and_caveat():
    text, records = expand_markdown("Leasing:\n\n{QUOTE:decl#4.15(a)}\n\nThanks.", RESOLVER)
    assert "> **Restrictions.**" in text and "> Not more than twenty-five percent (25%)" in text
    assert "_Declaration Section 4.15(a), as amended by the Second Amendment, recorded 2023-12-06, in force from " \
           "2023-12-06._" in text
    assert text.rstrip().endswith(f"_{CAVEAT}_")
    assert records[0].set_by == "decl-2nd" and records[0].dated == "2023-12-06" and len(records[0].digest) == 16


def test_a_quote_in_a_sentence_is_quoted_inline_and_a_cite_is_the_citation():
    text, records = expand_markdown("The rule {QUOTE:decl#4.16} applies ({CITE:decl#4.15(a)}).", RESOLVER)
    assert "“No animals other than ordinary household pets" in text and "(Declaration Section 4.16)" in text
    assert "(Declaration Section 4.15(a))." in text
    assert [r.verb for r in records] == ["QUOTE", "CITE"]


def test_an_unknown_section_fails_loudly_and_renders_nothing():
    with pytest.raises(SectionRefError) as err:
        expand_markdown("{QUOTE:decl#9.9} and {CITE:decl#8.8} and {QUOTE:decl#4.16}", RESOLVER)
    assert "9.9" in str(err.value) and "8.8" in str(err.value)


def test_html_is_escaped_and_a_block_is_a_blockquote():
    resolver = FakeResolver({("decl", "1.1"): ("", "Owners & Residents shall keep <quiet> hours after ten o'clock "
                                                   "in the evening in every part of the project.")})
    text, _ = expand_html("<p>Rule:</p>\n{QUOTE:decl#1.1}\n", resolver)
    assert '<blockquote class="quoted-provision"><p>Owners &amp; Residents shall keep &lt;quiet&gt;' in text


@pytest.mark.parametrize("number, article, expect", [("4.15(a)", False, "Declaration Section 4.15(a)"),
                                                     ("8", True, "Declaration Article 8"),
                                                     ("B-18(e)", False, "Declaration B-18(e)")])
def test_citation_style(number, article, expect):
    assert citation_of("Declaration", number, article=article) == expect


# --- The detector ----------------------------------------------------------------------------------------------------------

def _versions():
    return [SectionVersion("decl", "4.15(a)", "Restrictions.", NEW_A, Version.CURRENT, "decl-2nd"),
            SectionVersion("decl", "4.15(a)", "Restrictions.", OLD_A, Version.SUPERSEDED, "base"),
            SectionVersion("decl", "4.15(b)", "Applications.", APPLY, Version.CURRENT, "base"),
            SectionVersion("decl", "4.16", "Pets.", PETS, Version.CURRENT, "base")]


def test_a_verbatim_copy_of_an_unamended_section():
    host = f"Welcome to the project.\n\nPets: {PETS}\n\nCall the board with questions."
    copies = find("guide.md", host, Index.build(_versions()))
    assert [(c.number, c.kind, c.currency) for c in copies] == [("4.16", CopyKind.VERBATIM, Currency.UNAMENDED)]
    assert host[copies[0].start:copies[0].end].startswith("No animals")


def test_a_copy_of_the_replaced_words_is_stale_and_ocr_noise_still_matches():
    noisy = OLD_A.replace("Not more", "Notmore").replace("of the Units", "ofthe Units").replace("leased", "1eased")
    copies = find("manual.pdf", f"Leasing. {noisy} Other rules follow.", Index.build(_versions()))
    assert len(copies) == 1 and copies[0].currency is Currency.STALE and copies[0].matched == "base"
    assert copies[0].kind in (CopyKind.VERBATIM, CopyKind.NEAR_VERBATIM)


def test_a_copy_of_the_current_words_is_current_and_one_short_of_the_change_is_undecided():
    index = Index.build(_versions())
    assert find("a", NEW_A, index)[0].currency is Currency.CURRENT
    tail = ("of the Units within the project shall be leased or rented at any particular time, except as this Section "
            "allows for a hardship the Board approves in writing")
    found = find("b", f"Remember: {tail}.", index)
    assert found and found[0].kind is not CopyKind.VERBATIM and found[0].currency is Currency.UNDECIDED


def test_a_draft_reading_is_named():
    versions = [*_versions(), SectionVersion("decl", "4.16", "", PETS.replace("ordinary household pets",
                                                                              "two household pets"),
                                             Version.PENDING, "decl-3rd (draft)")]
    found = find("x", PETS.replace("ordinary household pets", "two household pets"), Index.build(versions))
    assert found[0].currency is Currency.DRAFT


def test_a_paragraph_two_sections_share_is_one_copy_naming_both():
    versions = [*_versions(), SectionVersion("decl", "4.20", "", PETS, Version.CURRENT, "base")]
    found = find("x", PETS, Index.build(versions))
    assert len(found) == 1 and {found[0].number, *found[0].also} == {"4.16", "4.20"}


def test_unrelated_text_finds_nothing_and_a_paraphrase_is_a_lead():
    index = Index.build(_versions())
    assert find("x", "The pool opens in May. Bring a towel and sunscreen to every swim session.", index) == []
    para = ("Ordinary household pets may be kept in a Unit, but no animals may be bred or maintained for a commercial "
            "purpose, and owners must keep their pets from becoming a nuisance anywhere in the project grounds.")
    leads = paraphrases("x", para, _versions(), least=0.5, rare=3, min_words=8)
    assert [(c.number, c.kind) for c in leads] == [("4.16", CopyKind.PARAPHRASE)]


def test_the_stream_drops_spacing_and_punctuation():
    assert stream("Each-Owner shall,  purchase") == stream("EachOwner shallpurchase") == "eachownershallpurchase"


# --- On disk: a living document, the versions, the resolver, the scan, the patch, and the guide -------------------------

BASE = f"""ARTICLE 4
4.15 Rental of Units.
(a) Restrictions. {OLD_A}
(b) Applications. {APPLY}
4.16 Pets. {PETS}
"""


def _run(text, bold=False, strike=False):
    return {"textRun": {"content": text, "textStyle": {"bold": bold, "strikethrough": strike}}}


def _amendment():
    paragraphs = [
        [_run("NOW, THEREFORE, the Association declares:\n")],
        [_run("Article 4, Section 4.15, subsection (a) (\"Restrictions\") is hereby amended and restated as follows "
              "(stricken out wording will be removed, and bolded wording will be added):\n")],
        [_run("Not more than "), _run("twenty percent (20%)", strike=True), _run(" "),
         _run("twenty-five percent (25%)", bold=True), _run(OLD_A.split("(20%)", 1)[1] + "\n")],
        [_run("IN WITNESS WHEREOF, the Board.\n")],
    ]
    return {"revisionId": "rev-1", "body": {"content": [{"paragraph": {"elements": p}} for p in paragraphs]}}


@pytest.fixture
def world(tmp_path):
    lib = tmp_path / "library"
    (lib / "text").mkdir(parents=True)
    with sqlite3.connect(lib / "library.db") as conn:
        conn.execute("CREATE TABLE documents (id TEXT, path TEXT, kind TEXT, confidential INTEGER, sha256 TEXT)")
        conn.execute("INSERT INTO documents VALUES ('1', 'Governing/Declaration.pdf', 'declaration', 0, 'abc')")
        conn.execute("INSERT INTO documents VALUES ('2', 'Rules/Handbook.pdf', 'operating_rules', 0, 'def')")
    (lib / "text" / "1.txt").write_text(BASE, encoding="utf-8")
    (lib / "text" / "2.txt").write_text(f"HANDBOOK\n\nLeasing. {OLD_A}\n\nPets. {PETS}\n", encoding="utf-8")
    cache = tmp_path / "living" / "decl" / "sources"
    cache.mkdir(parents=True)
    (cache / "doc-2.json").write_text(json.dumps(_amendment()), encoding="utf-8")
    second = SimpleNamespace(title="Second Amendment", recorded=date(2023, 12, 6), adopted=None,
                             recorder_number="000000000001")
    living = LivingDocument("decl", "Declaration", DocumentKind.DECLARATION,
                            base=SourceRef(SourceKind.LIBRARY_TEXT, "Governing/Declaration.pdf", sha256="abc"),
                            base_from="the recorded copy",
                            instruments=(LivingInstrument("decl-2nd", second, SourceRef(SourceKind.DOC, "doc-2")),))
    rules_text = "B-1. Quiet Hours.\nResidents shall keep quiet hours from ten at night until seven in the morning."
    rules = DocumentOutline("rules", "Rules", kind="operating_rules", text=rules_text,
                            sections=[Section("B-1", "Quiet Hours.", 1, 0, len(rules_text))])
    (tmp_path / "outlines").mkdir()
    (tmp_path / "outlines" / "rules.json").write_text(json.dumps(rules.to_dict()), encoding="utf-8")
    community = SimpleNamespace(
        living_documents=lambda: (living,),
        citable_documents=lambda: (CitableDocument("decl", "Declaration", "doc-1", DocumentKind.DECLARATION,
                                                   aliases=("Declaration",), cite_as="Declaration"),
                                   CitableDocument("rules", "Rules", "doc-3", DocumentKind.OPERATING_RULES,
                                                   aliases=("Rules",))),
        conflicts=lambda: (), notice_provisions=lambda: ())
    return tmp_path, community


def test_the_resolver_quotes_the_current_words_and_the_words_on_a_date(world):
    data, community = world
    resolver = sr.DiskResolver(data, community)
    now = resolver.section("decl", "4.15(a)")
    assert "twenty-five percent (25%)" in now.words and now.amended and now.set_by == "decl-2nd"
    assert now.citation == "Declaration Section 4.15(a)" and now.dated == date(2023, 12, 6)
    before = resolver.section("decl", "4.15(a)", date(2023, 1, 1))
    assert "twenty percent (20%)" in before.words and not before.amended
    assert (data / "section-refs" / "versions-decl.json").is_file()
    again = sr.DiskResolver(data, community).versions("decl")          # read back from the cache
    assert len(again.snapshots) == 2 and again.now.until is None


def test_an_outline_document_quotes_but_has_no_dates(world):
    data, community = world
    resolver = sr.DiskResolver(data, community)
    assert resolver.section("rules", "B-1").citation == "Rules B-1"
    with pytest.raises(SectionRefError, match="not kept as amended"):
        resolver.section("rules", "B-1", date(2020, 1, 1))
    with pytest.raises(SectionRefError, match="no document"):
        resolver.section("nope", "1")


def test_fill_reads_nothing_without_a_token(world):
    data, community = world
    assert sr.fill_markdown("No references here.", data, community) == ("No references here.", [])
    assert not (data / "section-refs").exists()


def test_the_scan_finds_a_stale_copy_in_an_adopted_rule_and_proposes_a_token_for_jasons_own(world):
    data, community = world
    (data / "drafts").mkdir()
    guide = data / "drafts" / "pets-guide.md"
    guide.write_text(f"# Pets\n\nThe Declaration says:\n\n> {PETS}\n\nThanks.\n", encoding="utf-8")
    found = sr.scan(data, community, own_sources=False)
    by_host = {r.host.name: r for r in found.results}
    handbook = by_host["Rules/Handbook.pdf"]
    assert handbook.host.owner is sr.Owner.ADOPTED
    stale = [c for c in handbook.copies if c.number == "4.15(a)"]
    assert stale and stale[0].currency is Currency.STALE
    assert by_host["Governing/Declaration.pdf"].host.owner is sr.Owner.SELF
    mine = by_host["drafts/pets-guide.md"]
    assert mine.host.owner is sr.Owner.JASON
    proposals = sr.proposals(found)
    assert len(proposals) == 1 and "{QUOTE:decl#4.16}" in proposals[0].new and PETS not in proposals[0].new
    assert "> " not in proposals[0].new.split("{QUOTE")[0].splitlines()[-1]       # the block quote's line replaced
    sr.apply(proposals[0])
    assert "{QUOTE:decl#4.16}" in guide.read_text(encoding="utf-8") and guide.with_suffix(".md.bak").is_file()
    path = sr.save(found, data)
    assert "Stale copies" in path.read_text(encoding="utf-8")
    view = sr.embedded_copies(data, stale_only=True)
    assert [h["host"] for h in view["hosts"]] == ["Rules/Handbook.pdf"]


def test_apply_refuses_a_file_changed_since_the_scan(world):
    data, community = world
    (data / "drafts").mkdir()
    page = data / "drafts" / "note.md"
    page.write_text(f"{PETS}\n", encoding="utf-8")
    proposal = sr.proposals(sr.scan(data, community, own_sources=False))[0]
    page.write_text("edited\n", encoding="utf-8")
    with pytest.raises(ValueError, match="changed since the scan"):
        sr.apply(proposal)


def test_the_guide_marks_amended_sections_and_where_they_are_copied(world):
    data, community = world
    sr.save(sr.scan(data, community, own_sources=False), data)
    paths = sr.guide(data, community)
    text = (data / "section-refs" / "guide" / "decl.md").read_text(encoding="utf-8")
    assert "Declaration Section 4.15(a): Restrictions" in text and "**Amended**: set by Second Amendment" in text
    assert "--as-of 2023-12-05" in text and "Rules/Handbook.pdf (adopted document; " in text
    assert "rules" in (data / "section-refs" / "guide" / "README.md").read_text(encoding="utf-8")
    assert paths[0].name == "README.md"
