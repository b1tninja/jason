"""Which statutes a document cites, and whether the authorities shelf holds them."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace

from jason.community.outlines import outline_from_text
from jason.community.references import TargetKind, extract
from jason.tasks.citation_coverage import Standing, survey


def statutes(text: str, *, external: bool = True) -> set[str]:
    refs = extract(outline_from_text(text, key="doc", title="doc"), {}, external=external)
    return {r.target for r in refs if r.kind is TargetKind.STATUTE}


def test_a_guides_phrasings_read_as_the_codes_they_name():
    assert "GOV 66427" in statutes("Compliance follows Section 66427 of the Government Code for a condominium plan.")
    assert "BPC 11010.4" in statutes("An exemption applies under BPC Section 11010.4 of the SLA.")
    assert {"BPC 11000.1", "BPC 11004.5"} <= statutes("Sections 11000.1 and 11004.5 of the SLA add undivided interests.")
    assert "GOV 66424" in statutes("Section 66424 of the Map Act defines a subdivision.")
    assert "CIV 4175" in statutes("A planned development is defined in Section 4175 of the Davis-Stirling Act.")
    assert {"BPC 10000", "BPC 10580"} <= statutes("codified in the Business and Professions Code (BPC), Sections 10000-10580, and is")
    assert "PRC 21000" in statutes("CEQA, California Public Resources Code Sections 21000-21177, was adopted in 1970.")


def test_a_code_named_later_in_the_sentence_is_not_the_code_of_a_number_before_it():
    cited = statutes("The Health and Safety Code (Section 18214 at 11000)\n"
                     "The Government Code (Sections 66424 et al., Map Act at 11000 et al.)")
    assert "HSC 18214" in cited and "GOV 11000" not in cited and "GOV 18214" not in cited


def test_a_bare_number_is_a_regulation_only_when_the_text_says_whose():
    said = "The Regulations of the Real Estate Commissioner are in Title 10. Article 12 addresses subdivisions in Sections 2790-2804."
    assert {"10 CCR 2790", "10 CCR 2804"} <= statutes(said)
    assert not any(t.startswith("CIV 27") for t in statutes(said))
    assert statutes("The rule appears in Sections 2790 and 2804 and nothing says whose.") == set()


def test_an_association_documents_bare_four_digit_section_is_still_the_civil_code():
    text = "Notice is given under Section 5855 of these Bylaws and Section 4920."
    assert "CIV 4920" in statutes(text, external=False)


def _shelf(tmp_path: Path) -> Path:
    pages = [{"code": "GOV", "start": "66410", "end": "66424.6", "sections": ["66410", "66424"]},
             {"code": "BPC", "start": "11000", "end": "11023", "sections": ["11000", "11010", "11010.4", "11018.5"]},
             {"code": "10 CCR", "start": "2792.9", "end": "2792.9", "sections": ["2792.9"]}]
    (tmp_path / "authorities").mkdir()
    (tmp_path / "authorities" / "manifest.json").write_text(json.dumps({"pages": pages}), encoding="utf-8")
    return tmp_path


class FakeLaw:
    def __init__(self, held: set[tuple[str, str]]):
        self.held, self.asked = held, []

    def spans(self, spans):
        self.asked.extend(spans)
        return tuple(SimpleNamespace(code=c, start=a, end=b, found=(c, a) in self.held) for c, a, b in spans)


TEXT = ("<<PAGE 1>>\nUnder Government Code Section 66424 a subdivision is the division of land. "
        "<<PAGE 2>>\nSee Government Code Section 66427, and Section 11001.1 of the SLA, and BPC Section 11010.4. Again, BPC Section 11010.4 applies, and so does BPC Section 11500. "
        "The Civil Code Sections 1350-1378 became Civil Code Section 4000. The Real Estate Commissioner's Regulations, 10 CCR 2792.9 and 10 CCR 2792.10 apply. "
        "The Sacramento City Code Section 5.20.100.")


def test_each_cited_section_is_placed_against_the_shelf_and_the_law(tmp_path: Path):
    law = FakeLaw({("GOV", "66427"), ("BPC", "11500"), ("CIV", "4000")})
    found = survey({"guide": TEXT}, _shelf(tmp_path), library=law, external=True)
    standing = {r.citation: r.standing for r in found.rows}
    assert standing["GOV 66424"] is Standing.ON_SHELF and standing["BPC 11010.4"] is Standing.ON_SHELF
    assert standing["GOV 66427"] is Standing.NOT_EXPORTED and standing["BPC 11500"] is Standing.NOT_EXPORTED
    assert standing["BPC 11001.1"] is Standing.NOT_FOUND          # inside the shelf page's range, and the page lacks it
    assert standing["CIV 1350"] is Standing.RENUMBERED and standing["CIV 1378"] is Standing.RENUMBERED
    assert standing["10 CCR 2792.9"] is Standing.ON_SHELF and standing["10 CCR 2792.10"] is Standing.REGULATION
    assert standing["CIV 4000"] is Standing.NOT_EXPORTED
    assert found.law_checked and ("GOV", "66424", "66424") not in law.asked           # the shelf answered; lawlibrary was not asked
    assert found.proposal() == "BPC 11500; CIV 4000; GOV 66427"
    row = next(r for r in found.rows if r.citation == "BPC 11010.4")
    assert row.mentions == 2 and row.page == "2"


def test_a_page_fetched_on_demand_is_on_the_shelf_as_the_shelfs_own_reader_counts_it(tmp_path: Path):
    _shelf(tmp_path)
    manifest = json.loads((tmp_path / "authorities" / "manifest.json").read_text(encoding="utf-8"))
    manifest["on_demand"] = [{"code": "GOV", "start": "66427", "end": "66427", "sections": ["66427"]}]
    (tmp_path / "authorities" / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    law = FakeLaw({("BPC", "11500")})
    found = survey({"guide": TEXT}, tmp_path, library=law, external=True)
    assert {r.citation: r.standing for r in found.rows}["GOV 66427"] is Standing.ON_SHELF
    assert ("GOV", "66427", "66427") not in law.asked and "GOV 66427" not in found.proposal()


def test_without_a_lawlibrary_what_is_off_the_shelf_is_unchecked_not_missing(tmp_path: Path):
    found = survey({"guide": TEXT}, _shelf(tmp_path), library=None, external=True)
    assert not found.law_checked
    assert next(r for r in found.rows if r.citation == "GOV 66427").standing is Standing.UNCHECKED
    assert found.proposal() == "" and "lawlibrary was not asked" in found.markdown()


def test_a_lawlibrary_that_fails_leaves_the_sections_unchecked_and_says_so(tmp_path: Path):
    class Broken:
        def spans(self, spans):
            raise RuntimeError("worker died")

    found = survey({"guide": TEXT}, _shelf(tmp_path), library=Broken(), external=True)
    assert not found.law_checked and any("worker died" in n for n in found.notes)


def test_a_document_with_no_citation_reports_none(tmp_path: Path):
    found = survey({"letter": "Dear owner, the meeting is Tuesday."}, tmp_path, external=False)
    assert found.rows == [] and found.lines() == ["no statute cited"]


def test_ingest_reports_the_statutes_each_distinct_file_cites(tmp_path: Path):
    from jason.tasks.ingest import cited_statutes

    items = [SimpleNamespace(duplicate_of="", sha256="a", rel="one.pdf"), SimpleNamespace(duplicate_of="one.pdf", sha256="a", rel="copy.pdf"),
             SimpleNamespace(duplicate_of="", sha256="b", rel="blank.pdf")]
    texts = {"a": "Fees follow Civil Code Section 5650.", "b": ""}
    result = cited_statutes(items, texts, tmp_path, FakeLaw({("CIV", "5650")}))
    assert [r.citation for r in result.rows] == ["CIV 5650"] and result.rows[0].sources == ["one.pdf"]


def test_ingest_reads_the_associations_own_habit_only_in_the_documents_that_have_it(tmp_path: Path):
    from jason.tasks.ingest import cited_statutes

    text = "The Regulations of the Real Estate Commissioner are in Title 10. Article 12 addresses subdivisions in Sections 2790-2804."
    items = [SimpleNamespace(duplicate_of="", sha256="a", rel="letter.pdf", kind="correspondence"),
             SimpleNamespace(duplicate_of="", sha256="b", rel="bylaws.pdf", kind="bylaws"),
             SimpleNamespace(duplicate_of="", sha256="c", rel="unsorted.pdf", kind=""),
             SimpleNamespace(duplicate_of="", sha256="d", rel="return.pdf", kind="tax_return"),
             SimpleNamespace(duplicate_of="", sha256="e", rel="minutes.pdf", kind="minutes")]
    texts = {"a": text, "b": "Notice under Section 4920.", "c": "Notice under Section 4920.",
             "d": "Form 1120-ND (section 4951 taxes) and Civil Code Section 5650.", "e": "Fees under Section 5650."}
    found = {r.citation: r.sources for r in cited_statutes(items, texts, tmp_path).rows}
    assert found["10 CCR 2790"] == ["letter.pdf"]                        # outside text: whose regulations the text says
    assert found["CIV 4920"] == ["bylaws.pdf"]                           # a governing document: a bare section is the Civil Code
    assert sorted(found["CIV 5650"]) == ["minutes.pdf", "return.pdf"]    # named by its code, it is read anywhere
    assert "CIV 4951" not in found and "CIV 2790" not in found          # a tax form's section is not a Civil Code gap
    assert "unsorted.pdf" not in str(found)                              # no kind yet: a bare number is left alone, not guessed


def test_the_lawlibrary_worker_asks_for_every_section_and_never_splits_a_span_at_a_decimal_midpoint():
    """Splitting 66499 to 66499.28 at 66499.14 started the right half at 66499.141, past every section after it, so
    sections .15 to .28 vanished. The worker now passes ``limit=None`` and splits nothing."""
    from jason.sources import lawlibrary as source

    numbers = [f"66499.{n}" for n in range(1, 29)]
    calls = []

    def fake_range(code, start, end, text=False, session=None, limit=30):
        calls.append(limit)
        if limit is not None and len(numbers) > limit:
            return {"found": True, "reason": "span_too_large", "nodes": []}
        return {"found": True, "sections": [{"citation": f"{code} {n}", "section": n} for n in numbers]}

    sys.modules["query"] = SimpleNamespace(range=fake_range, act=lambda n: {}, outline=lambda *a, **k: {}, section_key=lambda n: n)
    stdin, stdout = sys.stdin, sys.stdout
    sys.stdin, sys.stdout = io.StringIO(json.dumps({"spans": [["GOV", "66499", "66499.28"]]})), io.StringIO()
    try:
        exec(compile(source._WORKER, "worker", "exec"), {"__name__": "__main__"})
        out = json.loads(sys.stdout.getvalue())
    finally:
        sys.stdin, sys.stdout = stdin, stdout
        sys.modules.pop("query", None)
    assert calls == [None] and len(out["spans"][0]["sections"]) == 28
