from datetime import date
from pathlib import Path

from jason.community.extraction import Case, RegexExtractor, evaluate
from jason.community.model_extractor import ClaudeExtractor, ExtractionUnavailable, parse_answer
from jason.community.passages import passages_of, rank, search
from jason.community.readings import DocumentKindGuess, Relation
from tests.test_readings import MODERN, OLD


def test_the_regex_reader_is_scored_field_by_field(tmp_path: Path):
    phase4 = tmp_path / "Annexation - Phase 4.pdf"
    phase4.write_bytes(b"%PDF-1.4 placeholder")
    (tmp_path / "Annexation - Phase 4.pdf.md").write_text(MODERN, encoding="utf-8")
    phase2 = tmp_path / "Annexation - Phase 2.pdf"
    phase2.write_bytes(b"%PDF-1.4 placeholder")
    (tmp_path / "Annexation - Phase 2.pdf.md").write_text(OLD, encoding="utf-8")
    items = (
        Case(phase4, "202003021215", 4, 48, 57, 7, ("201905221469",), "phase 4 annexation"),
        Case(phase2, "200712171310", 2, 21, 32, 3, (), "phase 2 annexation"),
        Case(tmp_path / "missing.pdf", "200709200938", label="numbered file"),
    )
    card = evaluate(RegexExtractor(), items)
    assert card.cases == 3 and card.extractor == "regex"
    assert card.fields["number"].hits == 2 and card.fields["number"].misses == 1
    assert card.fields["phase"].hits == 2 and card.fields["last_unit"].hits == 2 and card.fields["supersedes"].hits == 1
    assert card.failures == [{"case": "missing.pdf", "field": "number", "expected": "200709200938", "actual": None}]
    assert card.as_dict()["fields"]["number"]["total"] == 3


def test_passages_are_ranked_by_the_question(tmp_path: Path):
    a = tmp_path / "a.md"
    a.write_text("The easement over A.C.A. 3 is reserved for the benefit of the Annexed Property. " * 5 + "Nothing else here. " * 200, encoding="utf-8")
    b = tmp_path / "b.md"
    b.write_text("Assessment liens follow Civil Code section 5675 and the collection policy. " * 5, encoding="utf-8")
    assert len(passages_of(a)) >= 2 and passages_of(b)[0].start_word == 0
    hits = search("easement reserved over A.C.A. 3", tmp_path, k=3)
    assert hits and hits[0].passage.path == a and hits[0].score > 0
    liens = search("assessment lien collection policy", tmp_path, k=3)
    assert liens[0].passage.path == b
    assert rank("", passages_of(a)) == ()


def test_the_model_answer_parses_into_the_same_records():
    answer = """Here is the reading:
    {"number": "2020-0302-1215", "recorded": "2020-03-02", "pages": 6, "unrecorded_copy": false,
     "title": "AMENDED AND RESTATED DECLARATION OF ANNEXATION AND RESERVATION OF EASEMENTS FOR MYSTIQUE, PHASE 4",
     "phase": 4, "declarant": "Watt Communities at Mystique, LLC",
     "annexed": {"first_unit": 48, "last_unit": 57, "association_common_area": 7, "condominium_common_area": 7},
     "citations": [{"number": "201901161002", "recorded": "2019-01-16", "title": "Condominium Plan", "relation": "plan"},
                   {"number": "201905221469", "recorded": "2019-05-22", "title": "Declaration of Annexation, Phase 4", "relation": "rescinds"},
                   {"number": "202003021215", "recorded": "2020-03-02", "title": "itself", "relation": "references"}],
     "sections": []}"""
    reading = parse_answer(answer, "Annexation - Phase 4.pdf")
    assert reading.number == "202003021215" and reading.stamp.recorded == date(2020, 3, 2) and reading.stamp.pages == 6
    assert reading.kind is DocumentKindGuess.ANNEXATION and reading.phase == 4
    assert (reading.annexed.first_unit, reading.annexed.last_unit, reading.annexed.association_common_areas) == (48, 57, (7,))
    assert [(c.number, c.relation) for c in reading.citations] == [("201901161002", Relation.PLAN), ("201905221469", Relation.RESCINDS)]
    assert [c.number for c in reading.supersedes] == ["201905221469"]
    empty = parse_answer("no json here")
    assert empty.number == "" and empty.citations == ()
    # The local models leave "phase" null and put it in the title; the title is where the phase lives anyway.
    titled = parse_answer('{"number": "202003021215", "title": "DECLARATION OF ANNEXATION FOR MYSTIQUE, PHASE 4", "phase": null, "citations": []}')
    assert titled.phase == 4


def test_the_model_extractor_fails_fast_without_a_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    try:
        ClaudeExtractor().extract(Path("nowhere.pdf"))
    except ExtractionUnavailable as exc:
        assert "ANTHROPIC_API_KEY" in str(exc)
    else:
        raise AssertionError("the extractor sent something without a key")


def test_the_model_extractor_sends_page_images_and_parses_the_reply(tmp_path: Path, monkeypatch):
    import jason.community.model_extractor as module

    monkeypatch.setattr(module, "page_images", lambda path, **kw: ["aGVsbG8="])
    sent = {}

    class Messages:
        def create(self, **kwargs):
            sent.update(kwargs)

            class Block:
                type = "text"
                text = '{"number": "201912201433", "title": "AMENDED AND RESTATED DECLARATION OF ANNEXATION, PHASE 3", "phase": 3, "annexed": {"first_unit": 1, "last_unit": 7, "association_common_area": 1}, "citations": [{"number": "201901161003", "relation": "rescinds"}]}'

            class Response:
                content = [Block()]

            return Response()

    class Client:
        messages = Messages()

    reading = ClaudeExtractor(client=Client()).extract(tmp_path / "phase3.pdf")
    assert sent["model"] == module.MODEL and sent["messages"][0]["content"][0]["type"] == "image" and sent["messages"][0]["content"][-1]["type"] == "text"
    assert reading.number == "201912201433" and reading.phase == 3 and [c.number for c in reading.supersedes] == ["201901161003"]
