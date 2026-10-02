import json
from types import SimpleNamespace

from jason.community.documents import DocumentKind
from jason.community.outlines import CitableDocument, DocumentOutline, Section
from jason.tasks import conflict_leads as cl
from jason.tasks import outlines as outline_store


def _change(section, statute, operative, *, change="amended", inserted=40, hunks=("",)):
    return {"citation": f"CIV {section}", "section": section, "action": "amended", "change": change,
            "statute": statute, "bill": "AB 1", "operative": operative, "after": operative[:4],
            "diff": {"inserted": inserted, "hunks": [{"after": h} for h in hunks]} if inserted is not None else None}


def _history(tmp_path, *rows):
    path = tmp_path / "authorities" / "history"
    path.mkdir(parents=True)
    (path / "changes.json").write_text(json.dumps({"changes": [{"changes": list(rows)}]}), encoding="utf-8")


def test_changes_since_the_recodification_that_change_enough(tmp_path):
    _history(tmp_path,
             _change("4100", "Stats. 2012, Ch. 180, Sec. 2", "2014-01-01"),        # the recodification itself
             _change("5850", "Stats. 2025, Ch. 22", "2025-06-30"),
             _change("5200", "Stats. 2025, Ch. 516", "2026-01-01", inserted=3),     # a small edit
             _change("4741", "Stats. 2021, Ch. 360", "2022-01-01", change="added", inserted=None),
             _change("1363", "Stats. 2011, Ch. 1", "2012-01-01"))                   # the former Act
    found = cl.changes(tmp_path)
    assert [(c.section, c.action) for c in found] == [("4741", "added"), ("5850", "amended")]


def test_after_reads_a_year_as_possibly_after():
    assert cl.after("2022", "2022-06-30") and cl.after("2022", "2025-01-01") and not cl.after("2022", "2021-12-31")
    assert cl.after("2007-09-17", "2014-02-01") and not cl.after("2026-02-01", "2026-01-01")
    assert cl.after("", "2015-01-01")


def _outline(key, title, parts):
    text, sections = "", []
    for number, body in parts:
        sections.append(Section(number, "", 1, len(text)))
        text += body + "\n"
    return DocumentOutline(key, title, kind="policy", text=text, sections=sections)


def test_leads_by_subject_and_citation(tmp_path, monkeypatch):
    _history(tmp_path, _change("5850", "Stats. 2025, Ch. 22", "2025-06-30"),
             _change("4741", "Stats. 2021, Ch. 360", "2022-01-01", change="added", inserted=None))
    filler = " ".join(f"word{i}" for i in range(20))
    policy = _outline("policy", "Enforcement Policy", [
        ("a)", "Fine schedule: a monetary penalty of three hundred dollars per violation for safety " + filler),
        ("b)", "Hearing notice and due process before the board imposes discipline on a member " + filler)])
    ccrs = _outline("ccrs", "CC&Rs", [
        ("4.15(a)", "No more than twenty percent of the units may be leased or rented at any time " + filler),
        ("9.1", "Insurance: the association keeps a master policy on the buildings " + filler)])
    community = SimpleNamespace(
        citable_documents=lambda: (CitableDocument("policy", "Enforcement Policy", "x", DocumentKind.POLICY, written="2022"),
                                   CitableDocument("ccrs", "CC&Rs", "y", DocumentKind.DECLARATION, written="2007")),
        conflicts=lambda: ())
    monkeypatch.setattr(outline_store, "load", lambda d: [policy, ccrs])
    monkeypatch.setattr(outline_store, "load_rows", lambda d: [
        {"source": "policy", "source_section": "b)", "kind": "statute", "target": "CIV 5850(c)", "quote": "Civ. 5850"}])
    queries = {"CIV 5850": "monetary penalty violation fine schedule dollars", "CIV 4741": "rental leased rented percent units"}
    monkeypatch.setattr(cl, "_query", lambda d, c: queries[c.citation])
    found = cl.leads(tmp_path, community)
    got = {(l.document, l.change.citation, l.route, l.section) for l in found}
    assert ("policy", "CIV 5850", "cites", "b)") in got
    assert ("policy", "CIV 5850", "subject", "a)") not in got     # one lead per document and change
    assert ("ccrs", "CIV 4741", "subject", "4.15(a)") in got       # no citation: found by its subject
    assert {l.document for l in cl.leads(tmp_path, community, document="ccrs")} == {"ccrs"}
    assert cl.leads(tmp_path, community, since="2023-01-01") == [l for l in found if l.change.when >= "2023-01-01"]
    text = "\n".join(cl.lines(found, community))
    assert text.startswith("### Enforcement Policy") and "written 2022" in text
