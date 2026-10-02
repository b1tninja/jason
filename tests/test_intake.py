import json
from collections import Counter

import pytest

from jason.community import intake
from jason.community.intake import Ask, AskKind, AskStatus
from jason.community.library import Classified, LibraryDocument, Method
from jason.community.living import CurrentDocument, Provision
from jason.community.outlines import DocumentOutline, Section
from jason.community.symbols import DocumentKind
from jason.tasks import intake as intake_task
from jason.tasks import library as library_task
from jason.tasks import living_docs


def _ask(n, **kw):
    fields = dict(kind=AskKind.OCR_READING, subject=f"doc#{n}", question="?")
    fields.update(kw)
    return Ask(intake.ask_id(fields["kind"], fields["subject"], str(n)), **fields)


def test_a_run_keeps_answers_adds_new_asks_and_marks_vanished_ones_stale():
    old = [_ask(1), _ask(2), _ask(3, subject="other#3")]
    intake.answer(old, old[0].id, "yes", "A Person")
    new = [_ask(1), _ask(4)]
    merged = {a.id: a for a in intake.merge(old, new, scope=("doc#",))}
    assert merged[old[0].id].status is AskStatus.ANSWERED and merged[old[0].id].answer == "yes"
    assert merged[old[1].id].status is AskStatus.STALE           # in scope, no longer asked
    assert merged[old[2].id].status is AskStatus.OPEN            # outside the run's scope
    assert merged[_ask(4).id].status is AskStatus.OPEN


def test_an_answer_names_its_person_and_may_pick_a_choice_by_number(tmp_path):
    asks = [_ask(1, choices=("first", "second"))]
    with pytest.raises(ValueError):
        intake.answer(asks, asks[0].id, "1", "")
    assert intake.answer(asks, asks[0].id, "2", "A Person").answer == "second"
    intake.save(tmp_path, asks)
    assert intake.load(tmp_path)[0].answered_by == "A Person"


@pytest.mark.parametrize("old,new,likely", [
    (["Condommmms"], ["Condominiums"], True),
    (["(51", "%)"], ["(51%)"], True),                       # spacing only
    (["Mx111q1,u:"], [], True),                             # a garbled footer
    (["Decision", "ofBoard", "Conclusive."], [], False),    # a run-in caption, not junk
    (["hours"], ["number"], False),                         # two real words: a person reads the page
])
def test_likely_readings(old, new, likely):
    vocab = Counter({w: 2 for w in "condominiums decision board conclusive hours number".split()})
    assert intake_task._likely(old, new, vocab) is likely


def _outline(body):
    text = "1.1 Use.\n" + body + "\n"
    return DocumentOutline("doc", "Doc", kind="declaration", text=text, sections=[Section("1.1", "Use.", 1, 0)])


def test_ocr_readings_become_transcriptions_the_next_build_applies(tmp_path):
    current = CurrentDocument("doc", "Doc", "base", [Provision("1.1", "Use.", "Units are pcnnitted for homes only.", 2,
                                                               "doc", history=["base"])])
    copy = _outline("Units are permitted for homes only.")
    vocab = Counter({"permitted": 2, "units": 2, "are": 2, "for": 2, "homes": 2, "only": 2})
    (ask,) = intake_task.ocr_reading_asks("doc", current, copy, vocab)
    assert ask.likely and ask.detail["wrong"] == "pcnnitted" and ask.suggestion == "permitted"
    asks = [ask]
    intake_task.accept_likely(asks, "A Person")
    (done,) = intake_task.apply(asks, tmp_path)
    assert done.status is AskStatus.APPLIED
    (fix,) = living_docs.transcriptions(tmp_path, "doc")
    assert (fix.section, fix.wrong, fix.right, fix.kind.value) == ("1.1", "pcnnitted", "permitted", "transcribed")
    assert "A Person" in fix.source


def test_a_persons_classification_outranks_the_rules(tmp_path):
    library_task.set_person_kind(tmp_path, "Folder/x.pdf", "contract", "A Person", note="the vendor agreement")
    row = Classified(LibraryDocument("payhoa", "1", "Folder/x.pdf", "x.pdf", "Folder"), None, Method.NONE)
    chosen = library_task.by_person(row, library_task.person_kinds(tmp_path))
    assert chosen.kind is DocumentKind.CONTRACT and chosen.method is Method.PERSON and "A Person" in chosen.evidence
    stored = json.loads((tmp_path / library_task.PERSON_KINDS).read_text(encoding="utf-8"))
    assert stored["Folder/x.pdf"]["kind"] == "contract"


def test_a_classify_answer_that_is_not_a_kind_is_left_for_a_person(tmp_path):
    asks = [_ask(1, kind=AskKind.CLASSIFY, detail={"path": "Folder/y.pdf"})]
    intake.answer(asks, asks[0].id, "a receipt of some sort", "A Person")
    assert intake_task.apply(asks, tmp_path) == [] and asks[0].status is AskStatus.ANSWERED
