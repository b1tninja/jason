"""The Davis-Stirling Act's history as jason stores and reads it: successors of former sections, and changes since."""

from __future__ import annotations

import json
from pathlib import Path

from jason.community.models.governing_shared import repealed_finding, repealed_sections, sections_now
from jason.community.succession import changes, now_at, successors
from jason.tasks.law_history import export


def _row(former, part, targets, source="disposition_table", succession="continued", act="davis-stirling"):
    return {"former": {"citation": f"CIV {former}{part}", "section": former, "part": part},
            "targets": [{"citation": t} for t in targets], "succession": succession, "source": source, "act": act,
            "report": {"title": "Disposition Table (AB 805, Stats. 2012, Ch. 180)", "url": "http://www.clrc.ca.gov/x.pdf", "line": 82}}


class FakeLibrary:
    """Stands in for lawlibrary's worker; the rows are shaped like its JSON, with no statute text."""

    def recodification(self, code, act):
        return [{"section": "1363", "citation": "CIV 1363", "recodifications": [{"act": act, "title": "Davis-Stirling",
                                                                                 "statute": "Stats. 2012, Ch. 180"}],
                 "rows": [_row("1363", "(f)", ["CIV 5850(a)"]), _row("1363", "(g)", ["CIV 5855"]),
                          _row("1363", "(g)", ["CIV 5855"], source="commission_comment", succession="continued_with_changes"),
                          _row("1363", "(g)", [], act="commercial-industrial", succession="not_continued")]},
                {"section": "1350.7", "rows": [_row("1350.7", "", [], succession="omitted")]}]

    def changes(self, code, spans, *, since=None, until=None):
        return {"found": True, "changes": [
            {"citation": "CIV 5855", "section": "5855", "before": "2011", "after": "2013", "change": "added",
             "statute": "Stats. 2012, Ch. 180, Sec. 2", "operative": "2014-01-01"},
            {"citation": "CIV 5855", "section": "5855", "before": "2023", "after": "2025", "change": "amended",
             "statute": "Stats. 2025, Ch. 22, Sec. 4", "bill": "AB 130", "operative": "2025-06-30",
             "summary": "151 words inserted", "diff": {"inserted": 151, "deleted": 0}}]}


def test_the_export_keeps_both_readings_and_the_reader_narrows_to_the_cited_subdivision(tmp_path: Path):
    done = export(FakeLibrary(), tmp_path)
    assert (done["sections"], done["rows"], done["official"], done["changes"]) == (2, 4, 4, 2)
    rows = successors(tmp_path, "1363(g)")
    assert [(r.targets, r.source) for r in rows] == [(("CIV 5855",), "disposition_table"), (("CIV 5855",), "commission_comment")]
    assert all(r.act == "davis-stirling" for r in successors(tmp_path, "Civil Code 1363"))
    assert now_at(tmp_path, "1363(g)") == "1363(g) is now CIV 5855 (commission comment and disposition table)"
    assert now_at(tmp_path, "1363").startswith("1363 is now CIV 5850, 5855")
    assert now_at(tmp_path, "1350.7") == "1350.7 was not continued (omitted)"
    assert now_at(tmp_path, "1370") == ""
    assert [c["change"] for c in changes(tmp_path, "CIV 5855")] == ["added", "amended"]
    assert [c["after"] for c in changes(tmp_path, since="2025")] == ["2025"]
    page = (tmp_path / "authorities" / "history" / "davis-stirling-changes.md").read_text(encoding="utf-8")
    assert "Stats. 2025, Ch. 22, Sec. 4 (AB 130)" in page and "+151/-0 words" in page
    assert "CIV 1363(g) -> CIV 5855" in (tmp_path / "authorities" / "history" / "davis-stirling-recodification.md").read_text(encoding="utf-8")


def test_the_sweep_lists_changes_of_law_not_renumberings(tmp_path: Path):
    from jason.community.succession import standing, version_note
    from jason.tasks.law_sweep import sweep

    class Renumbered(FakeLibrary):
        def recodification(self, code, act):
            found = super().recodification(code, act)
            found.append({"section": "1350", "rows": [
                _row("1350", "", ["CIV 4000"]),
                _row("1350", "", ["CIV 4000"], source="commission_comment", succession="continued_without_substantive_change")]})
            return found

        def changes(self, code, spans, *, since=None, until=None):
            found = super().changes(code, spans, since=since, until=until)
            found["changes"].insert(0, {"citation": "CIV 4000", "section": "4000", "before": "2011", "after": "2013",
                                        "change": "added", "statute": "Stats. 2012, Ch. 180, Sec. 2"})
            return found

    data = tmp_path / "data"
    export(Renumbered(), data)
    assert standing(data, "4000").same_effect and standing(data, "4000").origin == "continued"
    assert standing(data, "5855").origin == "continued_with_changes" and not standing(data, "5855").same_effect
    assert "AB 130" in version_note(data, "5855") and version_note(data, "4000").startswith("continues former CIV 1350")
    project = tmp_path / "project"
    (project / "docs").mkdir(parents=True)
    (project / "docs" / "notes.md").write_text("Title: CIV 4000.\nHearings: CIV 5855(c).\nOld bylaws: Civil Code 1363(g).\n",
                                                encoding="utf-8")
    entries = {e.section: e for e in sweep(project, data, since="2025")}
    assert set(entries) == {"5855", "1363"}                       # 4000 is the same law under a new number
    assert entries["5855"].kind == "amended" and "AB 130" in entries["5855"].summary
    assert entries["5855"].cites[0].path == "docs/notes.md" and entries["5855"].cites[0].line == 2
    assert entries["1363"].kind == "former" and "1363(g) is now CIV 5855" in entries["1363"].summary


def test_a_governing_documents_former_citations_keep_their_subdivisions_and_name_their_successors(tmp_path: Path):
    export(FakeLibrary(), tmp_path)
    cited = repealed_sections("as provided in Civil Code Section 1363(g) and Section 1363 of the Civil Code")
    assert cited == ("1363(g)", "1363")
    message = repealed_finding(cited, sections_now(cited, tmp_path))[0].message   # the store is read apart from the finding
    assert "1363(g) is now CIV 5855" in message
    assert "is now" not in repealed_finding(cited)[0].message      # without the stored history, the finding says only "former"
    assert json.loads((tmp_path / "authorities" / "history" / "former-sections.json").read_text(encoding="utf-8"))["act"] == "davis-stirling"
