import json
import re

from jason.community.outlines import DocumentOutline, Section
from jason.tasks import outline_viewer as viewer
from jason.tasks import outlines as task

EVIL = 'Section 7.2 says "</script><script>alert(1)</script>" & <!-- more'


def _outlines():
    bylaws_text = "ARTICLE 7 MEETINGS\n7.2 Regular Meetings. The Board meets monthly; see Section 3.8 of the Declaration.\n" + "x" * 3000
    bylaws = DocumentOutline(key="bylaws", title="Bylaws", kind="bylaws", text=bylaws_text, aliases=["Bylaws"])
    bylaws.sections = [Section("7", "MEETINGS", 1, 0, len(bylaws_text)),
                       Section("7.2", "Regular Meetings.", 2, 19, len(bylaws_text), parent="7")]
    ccrs_text = "ARTICLE 3 COMMON AREA\n3.7 Bonds.\n"
    ccrs = DocumentOutline(key="ccrs", title="Restated Declaration (CC&Rs)", kind="declaration", text=ccrs_text, aliases=["Declaration"])
    ccrs.sections = [Section("3", "COMMON AREA", 1, 0, len(ccrs_text)), Section("3.7", "Bonds.", 2, 22, len(ccrs_text), parent="3")]
    policy = DocumentOutline(key="enforcement-policy", title="Enforcement Policy", kind="policy", text="A policy with no sections.")
    return [bylaws, ccrs, policy]


def _rows():
    return [
        {"source": "bylaws", "source_section": "7.2", "kind": "section", "target": "ccrs#3.8", "relation": "cites", "quote": EVIL,
         "offset": 40, "prior": False, "status": "parent only", "nearest": "3"},
        {"source": "enforcement-policy", "source_section": "", "kind": "section", "target": "bylaws#7.2", "relation": "acts under",
         "quote": "under Bylaws Section 7.2", "offset": 3, "prior": False, "status": "found"},
        {"source": "bylaws", "source_section": "7", "kind": "statute", "target": "CIV 4926(a)(3)", "relation": "cites",
         "quote": "Civil Code 4926(a)(3)", "offset": 5, "prior": False, "status": "law on disk"},
        {"source": "ccrs", "source_section": "3.7", "kind": "statute", "target": "CIV 1363", "relation": "cites",
         "quote": "Section 1363", "offset": 25, "prior": True, "status": "prior numbering"},
    ]


def _embedded(html):
    m = re.search(r'<script type="application/json" id="data">(.*?)</script>', html, re.S)
    return json.loads(m.group(1))


def test_the_viewer_embeds_the_sections_and_references(tmp_path):
    outlines, rows = _outlines(), _rows()
    found = ["bylaws cites ccrs#3.8; the outline has 3 but not the subsection",
             "statutes cited by their pre-2014 Davis-Stirling numbers: CIV 1363 (renumbered January 1, 2014)"]
    path = viewer.write_viewer(tmp_path, outlines, rows, found)
    assert path == tmp_path / "reports" / "references.html" and path.is_file()
    data = _embedded(path.read_text(encoding="utf-8"))
    docs = {d["k"]: d for d in data["docs"]}
    assert [s[0] for s in docs["bylaws"]["s"]] == ["7", "7.2"] and docs["bylaws"]["s"][1][3] == 0   # 7.2 hangs from 7
    assert docs["bylaws"]["s"][1][1] == "Regular Meetings." and docs["bylaws"]["s"][1][5] == 1       # trimmed
    assert len(docs["bylaws"]["s"][1][4]) <= viewer.TEXT_LIMIT + 2
    assert docs["enforcement-policy"]["head"] == "A policy with no sections." and docs["ccrs"]["in"] == 1
    assert {r["t"] for r in data["refs"]} == {"ccrs#3.8", "bylaws#7.2", "CIV 4926(a)(3)", "CIV 1363"}
    links = data["findings"][0]["links"]
    assert [(l["d"], l["s"]) for l in links] == [("bylaws", "7.2"), ("ccrs", "3")]
    assert data["findings"][1]["q"] == "prior numbering"
    graph = data["graph"]
    ids = [n["id"] for n in graph["nodes"]]
    assert "law:CIV" in ids and {(ids[e["a"]], ids[e["b"]], e["n"]) for e in graph["edges"]} == {
        ("bylaws", "ccrs", 1), ("enforcement-policy", "bylaws", 1), ("bylaws", "law:CIV", 1), ("ccrs", "law:CIV", 1)}


def test_the_embedded_json_cannot_close_its_script_and_the_page_loads_nothing(tmp_path):
    html = viewer.write_viewer(tmp_path, _outlines(), _rows(), []).read_text(encoding="utf-8")
    # The only script closings are the page's own two; the quote's "</script>" is escaped inside the JSON.
    assert html.count("</script>") == 2 and "<!-- more" not in html
    assert any(r["q"] == EVIL for r in _embedded(html)["refs"])
    assert not re.search(r"""(?:src|href)\s*=\s*["']?\s*(?:https?:)?//""", html, re.I)
    assert "@import" not in html and not re.search(r"url\(\s*['\"]?https?:", html, re.I)
    assert "default-src 'none'" in html


def test_run_writes_the_viewer(tmp_path):
    result = task.run(tmp_path, _outlines())
    assert result["viewer"].endswith("references.html") and (tmp_path / "reports" / "references.html").is_file()
