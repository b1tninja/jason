"""The authorities registry and the lawlibrary export."""

from __future__ import annotations

import json
from pathlib import Path

from jason.community.authorities import ACTS, Act, Authority, Basis, Shelf, authorities, parse_statutes, pointers, section_in
from jason.sources.lawlibrary import LawLibrary, OutlineNode, article_groups
from jason.tasks.export_authorities import AUTHORITIES_DIR, authority_pages, authority_text, export_authorities, fetch_publications, heading_title


def test_a_duty_citation_string_becomes_spans_and_title_10_stays_a_pointer():
    found = parse_statutes("CIV 4150, 4205, 4250 to 4275; BPC 11504, 11505; Title 10 sections 2792.1, 2792.23", "why", Basis.DUTY)
    assert [a.citation for a in found] == ["CIV 4150", "CIV 4205", "CIV 4250-4275", "BPC 11504", "BPC 11505", "10 CCR 2792.1", "10 CCR 2792.23"]
    assert found[2].exportable and found[2].official.endswith("lawCode=CIV&sectionNum=4250.")
    reg = found[-1]
    assert reg.shelf is Shelf.REGULATION and not reg.exportable and reg.official.endswith("regs.pdf")
    assert found[0].slug == "CIV-4150" and found[2].slug == "CIV-4250-4275"


def test_the_registry_holds_every_duty_span_and_the_process_spans_without_duplicates():
    found = authorities()
    citations = [a.citation for a in found]
    assert len(citations) == len(set(citations))
    assert "CIV 5200-5240" in citations and "CIV 8400-8494" in citations and "PUC 2869" in citations
    federal = next(a for a in found if a.code == "26 USC")
    assert federal.shelf is Shelf.FEDERAL and federal in pointers()
    assert section_in(Authority("CIV", "5200", "5240", "", Basis.RECORD), "5215") and not section_in(Authority("CIV", "5200", "5240", "", Basis.RECORD), "5300")
    assert section_in(Authority("CCP", "697.310", "697.410", "", Basis.PROCESS), "697.340")


def test_article_groups_tile_an_act_with_articles_and_bare_chapters():
    nodes = (
        OutlineNode("part", "PART 5. Common Interest Developments [4000. - 6150.]", "4000", "6150", 10),
        OutlineNode("chapter", "CHAPTER 1. General Provisions [4000. - 4190.]", "4000", "4190", 4),
        OutlineNode("chapter", "CHAPTER 2. Application of Act [4200. - 4202.]", "4200", "4202", 3),
        OutlineNode("article", "ARTICLE 1. Preliminary Provisions [4000. - 4035.]", "4000", "4035", 2),
        OutlineNode("article", "ARTICLE 2. Definitions [4075. - 4190.]", "4075", "4190", 2),
    )
    groups = article_groups(nodes)
    assert [g.first for g in groups] == ["4000", "4075", "4200"]
    assert heading_title(groups[0].heading) == "Article 1. Preliminary Provisions"
    assert heading_title("CHAPTER 2. Application of Act [4200. - 4202.]") == "Chapter 2. Application of Act"


def _fake_run(payload):
    def section(code, number, heading):
        return {"citation": f"{code} {number}", "code": code, "section": number, "title": f"{number}. (Added by Stats. 2012, Ch. 180.)",
                "text": f"Words of section {number}.", "path": [{"heading": "DIVISION 4. GENERAL PROVISIONS [3274. - 9566.]"}, {"heading": heading}], "session": "2025"}

    out = {"spans": [], "acts": {}}
    for code, start, end in payload.get("spans", []):
        if code == "PUC":
            out["spans"].append({"code": code, "start": start, "end": end, "sections": []})
        elif start == "5200":
            out["spans"].append({"code": code, "start": start, "end": end, "sections": [section(code, "5200", "ARTICLE 5. Record Inspection [5200. - 5240.]"), section(code, "5210", "ARTICLE 5. Record Inspection [5200. - 5240.]")]})
        else:
            out["spans"].append({"code": code, "start": start, "end": end, "sections": [section(code, start, "CHAPTER 2. Application of Act [4200. - 4202.]")]})
    for name in payload.get("acts", []):
        out["acts"][name] = {"found": True, "nodes": [
            {"level": "chapter", "heading": "CHAPTER 6. Association Governance [4800. - 5450.]", "first": "4800", "last": "5450", "count": 2},
            {"level": "article", "heading": "ARTICLE 5. Record Inspection [5200. - 5240.]", "first": "5200", "last": "5240", "count": 2},
        ]}
    return out


def test_the_export_writes_one_page_per_span_folds_cited_spans_into_the_act_article_and_lists_misses(tmp_path: Path):
    library = LawLibrary(tmp_path, run=_fake_run)
    spans = (
        Authority("CIV", "5200", "5240", "the records article", Basis.RECORD),
        Authority("CIV", "4200", "4200", "application", Basis.DUTY),
        Authority("PUC", "2869", "2869", "solar notice", Basis.SOLAR),
        Authority("26 USC", "6321", "6325", "federal lien", Basis.PROCESS, Shelf.FEDERAL, "https://uscode.house.gov/x"),
    )
    report = export_authorities(library, tmp_path, spans=spans, acts=(Act("davis-stirling", "CIV", "the Act", Basis.DUTY),))
    assert report.session == "2025" and report.misses == ["PUC 2869"]
    assert [p.citation for p in report.pages] == ["CIV 5200-5240", "CIV 4200"]
    article = report.pages[0]
    assert article.title == "Article 5. Record Inspection" and article.why == ["the Act", "the records article"] and article.sections == ["5200", "5210"]
    text = (tmp_path / article.file).read_text(encoding="utf-8")
    assert text.startswith("# CIV 5200-5240: Article 5. Record Inspection") and "## CIV 5210" in text and "Words of section 5210." in text
    assert "- Why Jason holds it: the records article" in text and "2025 session publication" in text
    manifest = json.loads((tmp_path / AUTHORITIES_DIR / "manifest.json").read_text(encoding="utf-8"))
    assert [p["citation"] for p in manifest["pointers"]][:1] == ["26 USC 6321-6325"] and any(p["shelf"].startswith("an agency") for p in manifest["pointers"])
    assert [p.citation for p in authority_pages(tmp_path)] == ["CIV 5200-5240", "CIV 4200"]
    hit = authority_text(tmp_path, "civ 5210")
    assert hit["found"] and hit["text"].endswith("Words of section 5210.") and hit["title"] == "Article 5. Record Inspection"
    assert authority_text(tmp_path, "CIV 5300")["found"] is False and "not in the exported" in authority_text(tmp_path, "CIV 5300")["reason"]
    assert authority_text(tmp_path, "nonsense")["found"] is False


def test_a_title_10_section_is_cut_from_the_commissioners_regulations_when_the_pdf_is_on_disk(tmp_path: Path):
    import pymupdf

    from jason.tasks.export_authorities import PUBLICATIONS_DIR, REGULATIONS_FILE, regulation_sections

    pdf = tmp_path / PUBLICATIONS_DIR / REGULATIONS_FILE
    pdf.parent.mkdir(parents=True)
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 72), "2792.22. Reasonable Arrangements - Something Else.\nOther words.\n2792.23. Reasonable Arrangements - Inspection of Books.\nThe governing instruments shall provide for inspection.\n2792.24. Next Section.\nMore.")
    doc.save(str(pdf))
    doc.close()
    sections = regulation_sections(pdf)
    assert sections["2792.23"] == ("Reasonable Arrangements - Inspection of Books", "The governing instruments shall provide for inspection.")
    assert regulation_sections(tmp_path / "missing.pdf") == {}

    spans = (Authority("10 CCR", "2792.23", "2792.23", "developer file", Basis.DEVELOPER, Shelf.REGULATION, "https://www.dre.ca.gov/files/pdf/relaw/regs.pdf"),
             Authority("10 CCR", "2792.99", "2792.99", "not printed", Basis.DEVELOPER, Shelf.REGULATION, "https://www.dre.ca.gov/files/pdf/relaw/regs.pdf"))
    report = export_authorities(LawLibrary(tmp_path, run=_fake_run), tmp_path, spans=spans, acts=())
    assert [p.citation for p in report.pages] == ["10 CCR 2792.23"] and [p["citation"] for p in report.pointers][:1] == ["10 CCR 2792.99"]
    hit = authority_text(tmp_path, "10 CCR 2792.23")
    assert hit["found"] and hit["text"].endswith("The governing instruments shall provide for inspection.") and hit["session"] == "DRE publication"


def test_the_worker_is_only_run_when_the_checkout_exists(tmp_path: Path):
    library = LawLibrary(tmp_path / "nowhere")
    assert not library.available()
    try:
        library.spans([("CIV", "5200", "5200")])
    except Exception as exc:
        assert "lawlibrary checkout not found" in str(exc)
    else:
        raise AssertionError("expected LawLibraryUnavailable")
    assert library.spans([]) == ()


def test_fetch_publications_writes_the_file_and_a_note_and_keeps_what_is_there(tmp_path: Path):
    from jason.community.authorities import Publication

    pubs = (Publication("Reserve Study Guidelines", "https://example.test/re25.pdf", "reserves", number="RE 25"),)
    calls = []

    def fetch(url):
        calls.append(url)
        return b"%PDF-1.4"

    assert fetch_publications(tmp_path, fetch=fetch, publications=pubs) == ["re25.pdf"]
    assert fetch_publications(tmp_path, fetch=fetch, publications=pubs) == [] and calls == ["https://example.test/re25.pdf"]
    note = (tmp_path / "authorities" / "publications" / "re25.pdf.md").read_text(encoding="utf-8")
    assert note.startswith("# Reserve Study Guidelines") and "RE 25" in note
