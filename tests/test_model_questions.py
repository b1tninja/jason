"""Model answers: grounded in the text, judged against the rule reader, and never counted when the quote is not there."""

from __future__ import annotations

import json

from jason.community.question_sets import MINUTES
from jason.community.questions import AnswerType, Question, QuestionSet, Verdict, grounded, judge, schema
from jason.community.symbols import DocumentKind

TEXT = """MYSTIQUE COMMUNITY ASSOCIATION  Regular Meeting of the Board of Directors  Held on Mar 19, 2026 7:00 PM
I. Call to Order  The meeting was called to order at 7:02 pm. A quorum was present.
II. Approval of minutes  The minutes of 2/17/26 were approved unanimously."""


def test_a_quote_must_be_in_the_text_allowing_a_letter_of_ocr_noise() -> None:
    assert grounded("called to order at 7:02 pm", TEXT)
    assert grounded("The minutes of 2/17/26 were aproved unanimously", TEXT)          # one letter off
    assert not grounded("The board approved a $12,000 roof repair", TEXT)


def test_each_answer_is_judged_against_the_rule_readers_field() -> None:
    q = {x.key: x for x in MINUTES.questions}
    fields = {"meeting_date": "2026-03-19", "quorum": None, "actions": [{"text": "a"}], "directors_present": []}
    assert judge(q["meeting_date"], {"stated": True, "value": "2026-03-19", "quote": "Held on Mar 19, 2026"}, TEXT,
                 fields)["verdict"] == Verdict.AGREES.value
    assert judge(q["quorum"], {"stated": True, "value": True, "quote": "A quorum was present."}, TEXT,
                 fields)["verdict"] == Verdict.MODEL_ONLY.value
    assert judge(q["decision_topics"], {"stated": True, "value": ["roof repair $9,000", "tree pruning $4,000"], "quote": "were approved unanimously"}, TEXT,
                 fields)["verdict"] == Verdict.DIFFERS.value                            # no topic in common with the one action
    gap = judge(q["directors_present"], {"stated": False, "value": [], "quote": ""}, TEXT, fields)
    assert gap["verdict"] == Verdict.GAP.value and gap["lead"].startswith("the minutes list no directors")
    made_up = judge(q["reserve_transfer"], {"stated": True, "value": True, "quote": "transferred $5,000 from reserves"},
                    TEXT, {"reserve_transfer": ""})
    assert made_up["verdict"] == Verdict.UNGROUNDED.value


def test_the_schema_asks_every_question_and_the_run_stores_verdicts(tmp_path, monkeypatch) -> None:
    qs = QuestionSet(DocumentKind.MINUTES, "Minutes.", (Question("quorum", "Quorum?", AnswerType.YES_NO, field="quorum"),))
    assert schema(qs)["required"] == ["quorum"]
    (tmp_path / "documents").mkdir()
    (tmp_path / "documents" / "readings.json").write_text(json.dumps({"readings": [
        {"id": "7", "name": "Minutes of 3/19/26", "kind": "minutes", "hasText": True, "fields": {"quorum": True}}]}),
        encoding="utf-8")
    from jason.tasks import library, model_questions

    monkeypatch.setattr(library, "text_for", lambda root, doc_id: TEXT)

    class Community:
        def question_sets(self):
            return {DocumentKind.MINUTES: qs}

    result = model_questions.run(tmp_path, Community(), DocumentKind.MINUTES,
                                 ask=lambda text, fmt: {"quorum": {"stated": True, "value": True, "quote": "A quorum was present."}})
    assert result["files"][0]["answers"][0]["verdict"] == "agrees" and result["byQuestion"] == {"quorum": {"agrees": 1}}
    assert (tmp_path / "documents" / "questions-minutes.json").is_file()


def test_joined_passages_are_each_checked_and_silence_agrees_with_the_rules_no() -> None:
    assert grounded("called to order at 7:02 pm... were approved unanimously", TEXT)
    assert not grounded("called to order at 7:02 pm... the board approved a roof", TEXT)
    q = {x.key: x for x in MINUTES.questions}
    assert judge(q["draft"], {"stated": False, "value": None, "quote": ""}, TEXT, {"draft": False})["verdict"] == "agrees"
