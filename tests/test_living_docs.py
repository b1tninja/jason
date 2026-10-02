import json
import sqlite3
from types import SimpleNamespace

import pytest

from jason.community.living import (AnnotationKind, LivingDocument, LivingInstrument, SourceKind, SourceRef,
                                    Standing, TextCheck, standing_of)
from jason.community.symbols import DocumentKind
from jason.tasks import living_docs as ld

BASE = """ARTICLE 4
4.15 Rental of Condominiums.
(a) Restrictions. Not more than twenty percent (20%) of the Units shall be leased at any time.
(b) Applications. An Owner shall apply in writing.
"""


def _library(tmp_path, path, text, sha="abc"):
    lib = tmp_path / "library"
    (lib / "text").mkdir(parents=True)
    with sqlite3.connect(lib / "library.db") as conn:
        conn.execute("CREATE TABLE documents (id TEXT, path TEXT, sha256 TEXT)")
        conn.execute("INSERT INTO documents VALUES ('1', ?, ?)", (path, sha))
    (lib / "text" / "1.txt").write_text(text, encoding="utf-8")


def _run(text, bold=False, strike=False):
    return {"textRun": {"content": text, "textStyle": {"bold": bold, "strikethrough": strike}}}


def _amendment_doc():
    paragraphs = [
        [_run("NOW, THEREFORE, the Association declares:\n")],
        [_run("Article 4, Section 4.15, subsection (a) (\"Restrictions\") is hereby amended and restated as follows "
              "(stricken out wording will be removed, and bolded wording will be added):\n")],
        [_run("Not more than "), _run("twenty percent (20%)", strike=True), _run(" "),
         _run("twenty-five (25%)", bold=True), _run(" of the Units shall be leased at any time.\n")],
        [_run("IN WITNESS WHEREOF, the Board.\n")],
    ]
    return {"revisionId": "rev-1", "body": {"content": [{"paragraph": {"elements": p}} for p in paragraphs]}}


def _living(sha="abc"):
    recorded = SimpleNamespace(title="Second Amendment", recorded=__import__("datetime").date(2023, 12, 6),
                               adopted=None, recorder_number="000000000001")
    return LivingDocument(
        "decl", "Declaration", DocumentKind.DECLARATION,
        base=SourceRef(SourceKind.LIBRARY_TEXT, "Governing/Declaration.pdf", sha256=sha), base_from="the recorded copy",
        instruments=(LivingInstrument("decl-2nd", recorded, SourceRef(SourceKind.DOC, "doc-2")),),
        checks=(TextCheck("4.15(a)", "(25%)", "LeasingRules.cap_percent = 25"),))


def test_build_applies_a_recorded_amendment_and_checks_the_rule_row(tmp_path):
    _library(tmp_path, "Governing/Declaration.pdf", BASE)
    cache = ld.living_dir(tmp_path, "decl") / "sources"
    cache.mkdir(parents=True)
    (cache / "doc-2.json").write_text(json.dumps(_amendment_doc()), encoding="utf-8")
    built = ld.build(_living(), tmp_path)
    assert "twenty-five (25%)" in built.current.text_of("4.15(a)")
    assert built.current.provision("4.15(a)").set_by == "decl-2nd"
    assert built.revisions == {"decl-2nd": "rev-1"} and built.checks[0][1] is True
    path = ld.write(built, tmp_path)
    assert "As amended through" in path.read_text(encoding="utf-8")
    assert json.loads((path.parent / "report.json").read_text(encoding="utf-8"))["checks"][0]["found"] is True


def test_a_changed_library_file_is_held_out(tmp_path):
    _library(tmp_path, "Governing/Declaration.pdf", BASE, sha="other")
    with pytest.raises(ValueError, match="changed since it was reviewed"):
        ld.build(_living(), tmp_path)


def test_a_doc_not_read_yet_is_held(tmp_path):
    _library(tmp_path, "Governing/Declaration.pdf", BASE)
    built = ld.build(_living(), tmp_path)
    assert built.held and "not read yet" in built.held[0]
    assert "twenty percent (20%)" in built.current.text_of("4.15(a)")


def test_standing_from_the_specification_dates():
    assert standing_of(SimpleNamespace(recorded="2023-12-06", adopted=None)) is Standing.RECORDED
    assert standing_of(SimpleNamespace(recorded=None, adopted="2023-11-16")) is Standing.ADOPTED
    assert standing_of(SimpleNamespace()) is Standing.DRAFT


@pytest.mark.parametrize("content,quote,kind", [
    ("Second Amendment", "twenty", AnnotationKind.PROVENANCE),
    ("old code", "Civil Code Section 1363", AnnotationKind.OUTDATED_CITATION),
    ("Should be made a rule", "reasonable number", AnnotationKind.POLICY_CANDIDATE),
    ("Update the rules to match", "x", AnnotationKind.ACTION_ITEM),
    ("not allowed anymore per SB323", "", AnnotationKind.INTERPRETATION),
    ("which is?", "", AnnotationKind.QUESTION),
    ("Federal Housing Administration (FHA)", "FHA", AnnotationKind.DEFINITION),
    ("the streets meant", "public streets", AnnotationKind.CONTEXT),
])
def test_a_comment_reads_as_a_kind(content, quote, kind):
    assert ld.kind_of(content, quote) is kind


def test_comments_become_annotations_and_keep_a_persons_kind(tmp_path):
    comments = [{"id": "c1", "content": "Should be made a rule", "createdTime": "2023-01-06T00:00:00Z",
                 "quotedFileContent": {"value": "reasonable number"}, "replies": [{"content": "agreed"}]},
                {"id": "c2", "content": "gone", "deleted": True}]
    found = ld.comments_to_annotations(comments, None)
    assert [(a.source, a.kind, a.text) for a in found] == [
        ("comment:c1", AnnotationKind.POLICY_CANDIDATE, "Should be made a rule (replies: agreed)")]
    ld.save_annotations(tmp_path, "decl", found)
    path = ld.annotations_path(tmp_path, "decl")
    rows = json.loads(path.read_text(encoding="utf-8"))
    rows[0].update(kind="question", kind_set_by_person=True)
    path.write_text(json.dumps(rows), encoding="utf-8")
    again = ld.save_annotations(tmp_path, "decl", found)
    assert again[0].kind is AnnotationKind.QUESTION
    assert ld.load_annotations(tmp_path, "decl")[0].kind is AnnotationKind.QUESTION
