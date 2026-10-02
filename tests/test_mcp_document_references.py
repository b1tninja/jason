import json

from jason.community.outlines import DocumentOutline, Section
from jason.mcp.county import document_references
from jason.mcp.server import ALL_TOOLS, PROFILES
from jason.tasks import outlines as task


def _outline(key, text, sections, aliases=(), numbers=()):
    o = DocumentOutline(key=key, title=key.title(), kind="bylaws" if key == "bylaws" else "resolution", text=text,
                        sections=list(sections), aliases=list(aliases), numbers=list(numbers))
    return o


def _store(tmp_path):
    """Two outlines and their resolved references, written the way `jason outlines` writes them."""
    bylaws_text = "ARTICLE 7 Meetings. 7.2 Regular Meetings. Held quarterly, noticed under Section 4.3 of these Bylaws."
    bylaws = _outline("bylaws", bylaws_text, [
        Section("4", "Members", 1, 0, 0), Section("4.3", "Notice", 2, 0, 0, parent="4"),
        Section("7", "Meetings", 1, 0, len(bylaws_text)), Section("7.2", "Regular Meetings.", 2, 20, len(bylaws_text), parent="7")],
        aliases=["Bylaws"])
    res_text = "WHEREAS, Section 7.2 of the Bylaws requires quarterly meetings; Civil Code Section 4926(b) and Section 7.9 of the Bylaws."
    res = _outline("resolution-schedule", res_text, [Section("", "Resolution", 1, 0, len(res_text))], numbers=["20261020-1"])
    outlines = [bylaws, res]
    for o in outlines:
        (tmp_path / "outlines").mkdir(exist_ok=True)
        (tmp_path / "outlines" / f"{o.key}.json").write_text(json.dumps(o.to_dict()), encoding="utf-8")
    rows = task.resolve(task.references(outlines), outlines, tmp_path)
    (tmp_path / "outlines" / "references.json").write_text(json.dumps(rows), encoding="utf-8")
    return rows


def test_no_outlines_is_a_note_and_writes_nothing(tmp_path):
    result = document_references(data_dir=tmp_path)
    assert not result["found"] and "jason outlines" in result["note"] and result["caveats"]
    assert not (tmp_path / "outlines").exists()


def test_the_overview_lists_documents_counts_and_findings(tmp_path):
    rows = _store(tmp_path)
    result = document_references(data_dir=tmp_path)
    by_key = {d["key"]: d for d in result["documents"]}
    assert result["found"] and result["references"] == len(rows)
    assert by_key["bylaws"]["sections"] == 4 and by_key["bylaws"]["referencesIn"] >= 1
    assert by_key["resolution-schedule"]["referencesOut"] == sum(r["source"] == "resolution-schedule" for r in rows)
    assert any("bylaws#7.9" in f for f in result["findings"])
    assert any("OCR" in c for c in result["caveats"]) and any("lead" in c for c in result["caveats"])


def test_a_document_by_key_or_by_the_name_documents_cite_it_by(tmp_path):
    _store(tmp_path)
    result = document_references(document="Bylaws", depth=1, data_dir=tmp_path)
    assert result["found"] and result["key"] == "bylaws"
    assert [s["number"] for s in result["outline"]] == ["4", "7"]
    assert result["citedByDocuments"] == ["resolution-schedule"]
    missing = document_references(document="nope", data_dir=tmp_path)
    assert not missing["found"] and "bylaws" in missing["documents"]


def test_a_section_gives_its_text_what_it_cites_and_what_cites_it(tmp_path):
    _store(tmp_path)
    result = document_references(section="bylaws#7.2", data_dir=tmp_path)
    assert result["found"] and result["title"] == "Regular Meetings." and result["text"].startswith("7.2 Regular")
    assert [(c["target"], c["status"]) for c in result["cites"]] == [("bylaws#4.3", "found")]
    assert [c["source"] for c in result["citedBy"]] == ["resolution-schedule"] and "quarterly" in result["citedBy"][0]["quote"]
    gap = document_references(section="bylaws#7.9", data_dir=tmp_path)
    assert not gap["found"] and gap["nearest"] == "7" and gap["citedBy"][0]["status"] == "parent only"
    assert not document_references(section="bylaws", data_dir=tmp_path)["found"]


def test_cites_takes_a_statute_and_everything_inside_it(tmp_path):
    _store(tmp_path)
    result = document_references(cites="civ 4926", data_dir=tmp_path)
    assert result["found"] and result["target"] == "CIV 4926"
    assert [r["target"] for r in result["references"]] == ["CIV 4926(b)"] and result["bySource"] == {"resolution-schedule": 1}
    inside = document_references(cites="bylaws#7", data_dir=tmp_path)
    assert {r["target"] for r in inside["references"]} == {"bylaws#7.2", "bylaws#7.9"}


def test_the_tool_is_served_but_not_in_the_board_profile():
    assert "document_references" in {tool.__name__ for tool in ALL_TOOLS}
    assert "document_references" not in PROFILES["board"]
