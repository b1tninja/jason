"""The authorities registry, the lawlibrary export, and the three AnythingLLM catalogs."""

from __future__ import annotations

import json
from pathlib import Path

from jason.community.anythingllm import AnythingLLM
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


def test_the_sync_keeps_the_three_catalogs_in_their_own_folders_and_workspaces(tmp_path: Path):
    from jason.tasks.anythingllm_sync import CATALOGS, catalog_named, sync_catalogs

    data = tmp_path / "data"
    project = tmp_path / "project"
    (data / "authorities" / "CIV").mkdir(parents=True)
    (data / "authorities" / "CIV" / "CIV-5200-5240.md").write_text("# CIV 5200-5240: Article 5. Record Inspection\n\ntext", encoding="utf-8")
    (data / "authorities" / "publications").mkdir()
    (data / "authorities" / "publications" / "re25.pdf").write_bytes(b"%PDF-1.4")
    (data / "authorities" / "publications" / "re25.pdf.md").write_text("# Reserve Study Guidelines\n\n- Number: RE 25", encoding="utf-8")
    (data / "artifacts" / "site-docs" / "governing_documents").mkdir(parents=True)
    (data / "artifacts" / "site-docs" / "governing_documents" / "CCRs.pdf").write_bytes(b"%PDF-1.4")
    (data / "artifacts" / "site-docs" / "governing_documents" / "Bylaws.pdf").write_bytes(b"%PDF-1.4")
    (data / "reports").mkdir()
    (data / "reports" / "records.md").write_text("# records", encoding="utf-8")
    (project / "docs").mkdir(parents=True)
    (project / "SKILLS.md").write_text("# skills", encoding="utf-8")
    calls = []

    def fetch(method, url, payload):
        calls.append((method, url, payload))
        if url.endswith("/workspaces"):
            return {"workspaces": [{"slug": "association-records", "name": "Association Records"}]}
        if url.endswith("/workspace/new"):
            return {"workspace": {"slug": payload["name"].lower().replace(" ", "-")}}
        if url.endswith("/documents"):
            return {"localFiles": {"items": [
                {"type": "folder", "name": "custom-documents", "items": [{"type": "file", "name": "Bylaws.pdf-1.json", "title": "Bylaws.pdf"}]},
                {"type": "folder", "name": "jason-pages", "items": [{"type": "file", "name": "records.md-2.json", "title": "reports: records"}]},
            ]}}
        return {"success": True}

    report = sync_catalogs(AnythingLLM(api_key="k", fetch=fetch), data, project)
    assert report.workspaces == {"combined": "mystique", "authorities": "authorities", "association-records": "association-records",
                                 "mail": "mail", "insurance": "insurance", "jason-pages": "jason-pages"}
    assert report.uploaded == ["CIV 5200-5240: Article 5. Record Inspection", "Reserve Study Guidelines", "CCRs.pdf", "instructions: SKILLS"]
    assert report.moved == ["Bylaws.pdf"] and report.skipped == ["reports: records"] and report.errors == []
    statute = next(c for c in calls if c[1].endswith("/document/upload/authorities"))
    meta = json.loads(statute[2]["metadata"])
    assert statute[2]["addToWorkspaces"] == "authorities,mystique" and meta["docAuthor"] == "California Legislature and agencies" and meta["description"].startswith("authoritative source")
    move = next(c for c in calls if c[1].endswith("/document/move-files"))
    assert move[2]["files"] == [{"from": "custom-documents/Bylaws.pdf-1.json", "to": "association-records/Bylaws.pdf-1.json"}]
    embeds = [c for c in calls if "/update-embeddings" in c[1]]
    assert [c[1].rsplit("/", 2)[1] for c in embeds] == ["association-records", "mystique"] and embeds[0][2]["adds"] == ["association-records/Bylaws.pdf-1.json"]
    folders = [c[2]["name"] for c in calls if c[1].endswith("/document/create-folder")]
    assert folders == ["authorities", "association-records", "mail", "insurance", "jason-pages"]
    assert catalog_named("jason-pages") is CATALOGS[4] and catalog_named("mail") is CATALOGS[2] and catalog_named("nothing") is None
    assert catalog_named("insurance") is CATALOGS[3]
    assert "uploaded=4 refreshed=0 moved=1 skipped=1" in report.summary()

    only = sync_catalogs(AnythingLLM(api_key="k", fetch=fetch), data, project, names=("authorities",), combined="")
    assert list(only.workspaces) == ["authorities"]
    assert ACTS[0].code == "CIV"


def test_refresh_replaces_a_stale_generated_page_but_never_an_association_record(tmp_path: Path):
    import os

    from jason.tasks.anythingllm_sync import is_stale, sync_catalogs

    data = tmp_path / "data"
    (data / "reports").mkdir(parents=True)
    page = data / "reports" / "records.md"
    page.write_text("# records, regenerated", encoding="utf-8")
    (data / "artifacts" / "site-docs" / "governing_documents").mkdir(parents=True)
    pdf = data / "artifacts" / "site-docs" / "governing_documents" / "Bylaws.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    for path in (page, pdf):
        os.utime(path, (1_800_000_000, 1_800_000_000))  # 2027-01-15, after the stored copies
    old = "9/28/2026, 12:51:40 PM"
    calls = []

    def fetch(method, url, payload):
        calls.append((method, url, payload))
        if url.endswith("/workspaces"):
            return {"workspaces": [{"slug": "jason-pages", "name": "Jason Pages"}, {"slug": "association-records", "name": "Association Records"}]}
        if url.endswith("/documents"):
            return {"localFiles": {"items": [
                {"type": "folder", "name": "jason-pages", "items": [{"type": "file", "name": "records.md-2.json", "title": "reports: records", "published": old}]},
                {"type": "folder", "name": "association-records", "items": [{"type": "file", "name": "Bylaws.pdf-1.json", "title": "Bylaws.pdf", "published": old}]},
            ]}}
        return {"success": True}

    client = AnythingLLM(api_key="k", fetch=fetch)
    kept = sync_catalogs(client, data, None, names=("jason-pages", "association-records"), combined="")
    assert kept.refreshed == [] and sorted(kept.skipped) == ["Bylaws.pdf", "reports: records"]
    calls.clear()
    fresh = sync_catalogs(client, data, None, names=("jason-pages", "association-records"), combined="", refresh=True)
    assert fresh.refreshed == ["reports: records"] and fresh.skipped == ["Bylaws.pdf"] and fresh.errors == []
    order = [c[1].rsplit("/api/v1", 1)[-1] if "/api/v1" in c[1] else c[1] for c in calls if c[0] in ("POST", "DELETE") and ("upload" in c[1] or "remove" in c[1])]
    assert [o.rsplit("/", 2)[-2] + "/" + o.rsplit("/", 1)[-1] for o in order] == ["upload/jason-pages", "system/remove-documents"]
    remove = next(c for c in calls if c[1].endswith("/system/remove-documents"))
    assert remove[0] == "DELETE" and remove[2] == {"names": ["jason-pages/records.md-2.json"]}
    assert not is_stale(page, {"published": "not a time"}) and is_stale(page, {"published": old})


def test_ask_prefers_the_shared_workspace_and_labels_each_source_by_catalog():
    from jason.tasks.anythingllm_sync import ask

    asked = []

    def fetch(method, url, payload):
        if url.endswith("/workspaces"):
            return {"workspaces": [{"slug": "my-workspace", "name": "My Workspace"}, {"slug": "mystique", "name": "Mystique"}, {"slug": "authorities", "name": "Authorities"}]}
        if url.endswith("/chat"):
            asked.append(url.rsplit("/", 2)[-2])
            return {"textResponse": "Ten business days.", "sources": [{"title": "CIV 5200-5240: Article 5. Record Inspection", "text": "5210..."}, {"title": "reports: records", "text": "summary"}]}
        if url.endswith("/documents"):
            return {"localFiles": {"items": [
                {"type": "folder", "name": "authorities", "items": [{"type": "file", "name": "a.json", "title": "CIV 5200-5240: Article 5. Record Inspection"}]},
                {"type": "folder", "name": "jason-pages", "items": [{"type": "file", "name": "b.json", "title": "reports: records"}]},
            ]}}
        return {}

    client = AnythingLLM(api_key="k", fetch=fetch)
    result = ask(client, "How long to produce records?")
    assert asked == ["mystique"] and result["found"]
    assert [(s["catalog"], s["shelf"].split(":")[0]) for s in result["sources"]] == [("authorities", "authority"), ("jason-pages", "summary")]
    ask(client, "q", catalog="authorities")
    assert asked[-1] == "authorities"
    missing = ask(client, "q", catalog="jason-pages")
    assert missing["found"] is False and "run jason anythingllm --sync" in missing["note"]


def test_a_document_still_embedded_elsewhere_is_unembedded_moved_and_re_embedded(tmp_path: Path):
    from jason.tasks.anythingllm_sync import sync_catalogs

    data = tmp_path / "data"
    (data / "artifacts" / "site-docs" / "governing_documents").mkdir(parents=True)
    (data / "artifacts" / "site-docs" / "governing_documents" / "Bylaws.pdf").write_bytes(b"%PDF-1.4")
    calls = []
    moves = {"n": 0}

    def fetch(method, url, payload):
        calls.append((method, url, payload))
        if url.endswith("/workspaces"):
            return {"workspaces": [{"slug": "my-workspace", "name": "My Workspace"}, {"slug": "association-records", "name": "Association Records"}]}
        if url.endswith("/documents"):
            return {"localFiles": {"items": [{"type": "folder", "name": "custom-documents", "items": [{"type": "file", "name": "Bylaws.pdf-1.json", "title": "Bylaws.pdf"}]}]}}
        if url.endswith("/document/move-files"):
            moves["n"] += 1
            return {"success": True, "message": "1/1 files not moved. Unembed them from all workspaces."} if moves["n"] == 1 else {"success": True, "message": None}
        return {"success": True}

    report = sync_catalogs(AnythingLLM(api_key="k", fetch=fetch), data, None, names=("association-records",), combined="")
    assert report.moved == ["Bylaws.pdf"] and report.errors == [] and moves["n"] == 2
    embeds = [(c[1].rsplit("/", 2)[1], c[2]) for c in calls if "/update-embeddings" in c[1]]
    assert embeds[:2] == [("my-workspace", {"adds": [], "deletes": ["custom-documents/Bylaws.pdf-1.json"]}), ("association-records", {"adds": [], "deletes": ["custom-documents/Bylaws.pdf-1.json"]})]
    assert embeds[-1] == ("association-records", {"adds": ["association-records/Bylaws.pdf-1.json"], "deletes": []})


def test_an_answer_drops_the_models_thinking_and_workspaces_get_the_retrieval_settings():
    from jason.community.anythingllm import WORKSPACE_SETTINGS
    from jason.tasks.anythingllm_sync import ensure_workspace

    calls = []

    def fetch(method, url, payload):
        calls.append((method, url, payload))
        if url.endswith("/chat"):
            return {"textResponse": "<think>weighing the passages\n</think>\n\nThe deductible is $10,000.", "sources": []}
        if url.endswith("/workspaces"):
            return {"workspaces": [{"slug": "insurance", "name": "insurance"}]}
        return {"workspace": {"slug": "insurance"}}

    client = AnythingLLM(api_key="k", fetch=fetch)
    assert client.query("insurance", "deductible?").text == "The deductible is $10,000."
    assert ensure_workspace(client, "insurance") == "insurance"
    assert ("POST", "http://localhost:3001/api/v1/workspace/insurance/update", WORKSPACE_SETTINGS) in calls
