"""OCR post-correction: the English prior, the text rules, the guard, agreement as confidence, the model readers'
parsing, and the intake queue's tiers. Made-up text throughout; no model and no word list is reached."""

import json
import sqlite3
from collections import Counter

import pytest

from jason.community import ocr_correct as oc
from jason.community import ocr_models as om
from jason.community.lexicon import Lexicon, TokenClass, core, document_terms, language_of
from jason.community.living import CurrentDocument, Provision
from jason.community.ocr import parse_tsv
from jason.community.outlines import DocumentOutline, Section
from jason.tasks import intake as intake_task
from jason.tasks import ocr_correct as ocr_task

CORPUS = """The Owner of the Unit shall pay each assessment. The Board may adopt rules for the use of the Common Area.
No Owner shall lease a Unit for a term of less than thirty days. Any failure of the Board to enforce any provision of
this Declaration shall not be a waiver. The Owner shall maintain the Unit in good condition, and the Association shall
maintain the Common Area. Notice of the meeting shall be given to each Owner. The Board shall keep the records of the
Association. Each Owner shall pay the assessment when due. The Association may impose a lien for any assessment not
paid. The Board of Directors may adopt rules after notice to the Owners. Any Owner may inspect the records."""

# A tiny "general English" list in place of wordfreq, so the tests give the same answers on any machine.
ENGLISH = {w: 1e-4 for w in "the of owner unit shall pay each assessment board may adopt rules for use common area no "
                                "lease a term less than thirty days any failure to enforce provision this declaration "
                                "not be waiver maintain in good condition and association notice meeting given keep "
                                "records impose lien paid directors after owners inspect when due is are lessee".split()}
ENGLISH["ofthe"] = 2e-6          # web text has run-together words; the prior must still split them


def lexicon(text=CORPUS):
    lex = Lexicon.from_texts([text] * 3, english=lambda w: ENGLISH.get(w, 0.0))
    return lex


def test_what_a_token_may_be():
    lex = lexicon()
    assert lex.classify("Owner's") is TokenClass.WORD
    assert lex.classify("4.15(a)") is TokenClass.NUMBER and lex.classify("$1,250.00") is TokenClass.NUMBER
    assert lex.classify("(iv)") is TokenClass.LABEL
    assert lex.classify("FHLMC") is TokenClass.ABBREVIATION
    assert lex.classify("mutandis") is TokenClass.TERM_OF_ART
    assert lex.classify("faiiure").suspect and lex.classify("ofthe").suspect
    assert not lex.classify("(S)HE").suspect and not lex.classify("Owner(s)").suspect
    assert core("(Owner's,") == "Owner's"


def test_a_run_together_word_splits_by_the_language_model_and_keeps_its_letters():
    lex = lexicon()
    pieces, _ = lex.segment("ofthe")
    assert pieces == ["of", "the"]
    assert lex.segment("ofCommon")[0] == ["of", "Common"]
    assert lex.run_together("assessment") is None              # a word of the corpus is never split
    s = oc.correct_token("each Owner shallpay the".split(), 2, lex)
    assert (s.right, s.fix, s.guard) == ("shall pay", oc.Fix.SPLIT, "")   # spacing alone is editorial


def test_a_misread_word_is_read_through_the_noisy_channel_in_context():
    lex = lexicon()
    s = oc.correct_token("any faiiure of the Board".split(), 1, lex)
    assert s.right == "failure" and s.fix is oc.Fix.CHARACTER and s.methods == (oc.Method.LEXICON,)
    assert oc.correct_token("each Owner shall pay".split(), 1, lex) is None   # a word is never touched
    assert oc.correct_token("Section 4.1S(a) applies".split(), 1, lex) is None  # nor a number


def test_layout_rules():
    lex = lexicon()
    tokens = "the Owner | shall pay - 12 - each assess- ment {c) the Board,shall keep".split()
    found = {(s.wrong, s.right, s.fix) for s in oc.layout_suggestions(tokens, lex)}
    assert ("|", "", oc.Fix.STRAY) in found
    assert ("- 12 -", "", oc.Fix.FOLIO) in found
    assert ("assess- ment", "assessment", oc.Fix.JOIN) in found
    assert ("{c)", "(c)", oc.Fix.LABEL) in found
    assert ("Board,shall", "Board, shall", oc.Fix.PUNCTUATION) in found
    # A vision model's transcription writes tables between bars, and bullets and checkboxes as marks: all text.
    assert not oc.layout_suggestions("Fee | 10 | due • [ ] paid".split(), lex, tables=True)
    # A comma spaced off its word and an ellipsis are the text's own.
    assert not oc.layout_suggestions("On June , the Board ... met".split(), lex)


def test_the_guard_holds_numbers_operative_words_and_added_or_dropped_words_for_a_person():
    assert oc.guard("ofthe", "of the") == ""
    assert oc.guard("faiiure", "failure") == ""
    assert "number" in oc.guard("- 12 -", "", oc.Fix.FOLIO)
    assert "operative" in oc.guard("shail", "shall")
    assert oc.guard("in :", "in person") == "adds a word"
    assert oc.guard("Granting ofEasements.", "") != ""            # a run-in caption is not junk


def test_agreement_is_the_likely_tier():
    s = oc.Suggestion(0, 1, "ofthe", "of the", oc.Fix.SPLIT, (oc.Method.LEXICON,))
    assert oc.tier(s) is oc.Tier.SUGGESTED                          # one reader
    m = oc.Suggestion(0, 1, "ofthe", "of the", oc.Fix.SPLIT, (oc.Method.LOCAL_MODEL,), 0.99)
    (both,) = oc.combine([s], [m])
    assert both.methods == (oc.Method.LEXICON, oc.Method.LOCAL_MODEL) and oc.tier(both) is oc.Tier.LIKELY
    rules = oc.Suggestion(0, 1, "ofthe", "of the", oc.Fix.SPLIT, (oc.Method.LEXICON, oc.Method.LAYOUT))
    assert oc.tier(rules) is oc.Tier.SUGGESTED                      # the text rules are one family
    shall = oc.Suggestion(0, 1, "shail", "shall", oc.Fix.CHARACTER, (oc.Method.LEXICON, oc.Method.LOCAL_MODEL))
    assert oc.tier(shall) is oc.Tier.SUGGESTED                      # an operative word needs the page
    seen = oc.Suggestion(0, 1, "shail", "shall", oc.Fix.CHARACTER, (oc.Method.LEXICON, oc.Method.VISION))
    assert oc.tier(seen) is oc.Tier.LIKELY
    other = oc.Suggestion(0, 1, "ofthe", "oft he", oc.Fix.SPLIT, (oc.Method.LOCAL_MODEL,))
    assert oc.tier(both, [other]) is oc.Tier.CONFLICT


def test_apply_takes_non_overlapping_suggestions_for_a_reading_copy():
    tokens = "the ofthe | Board".split()
    sugs = [oc.Suggestion(1, 2, "ofthe", "of the", oc.Fix.SPLIT, (oc.Method.LEXICON,)),
            oc.Suggestion(2, 3, "|", "", oc.Fix.STRAY, (oc.Method.LAYOUT,))]
    assert oc.apply(tokens, sugs) == ["the", "of", "the", "Board"]


def test_document_terms_are_the_documents_own_defined_terms_but_not_its_slips():
    lex = lexicon()
    text = 'The term "Zephyrine Court" shall mean the street. Zephyrine Zephyrine Zephyrine. "Board ofDirectors"'
    terms = document_terms(text, lex)
    assert "zephyrine" in terms and "ofdirectors" not in terms


def test_a_passage_in_another_language_is_named_and_left_alone():
    pytest.importorskip("wordfreq")
    lex = lexicon()
    spanish = "Aviso a los propietarios: la junta directiva se reunirá el martes para considerar el presupuesto."
    assert language_of(spanish, lex).language == "es"
    assert language_of("The lien shall attach pro rata, mutatis mutandis, to each Unit and Owner.", lex).english
    assert oc.suggest(spanish.split(), lex) == []


def test_model_corrections_are_mapped_to_tokens_trimmed_to_the_change_and_lost_ones_counted():
    tokens = "the amount ofthree dollars shall be paid".split()
    answer = json.dumps({"corrections": [
        {"original": "amount ofthree", "corrected": "amount of three", "kind": "split", "reason": "run together",
         "confidence": 0.99},
        {"original": "not in the passage", "corrected": "x", "kind": "other", "reason": "", "confidence": 0.5}]})
    found, lost = om.parse_corrections(answer, tokens)
    (s,) = found
    assert (s.start, s.end, s.wrong, s.right, s.confidence) == (2, 3, "ofthree", "of three", 0.99) and len(lost) == 1
    readings = om.parse_readings(json.dumps({"readings": [{"n": 2, "text": "of three"}, {"n": 4, "text": "shall"}]}),
                                 tokens, [2, 4])
    assert [(r.start, r.right) for r in readings] == [(2, "of three")]   # an unchanged token is no suggestion
    assert om.minimal(s) and not om.minimal(oc.Suggestion(0, 1, "hereof.", "the provisions of", oc.Fix.OTHER, ()))


def test_the_model_as_a_scorer_weighs_only_the_readings_it_is_given():
    seen = {}

    def fetch(url, body):
        seen.update(body)
        return {"message": {"content": "B"}, "logprobs": [{"token": "B", "top_logprobs": [
            {"token": "B", "logprob": -0.1}, {"token": "A", "logprob": -2.5}, {"token": " B", "logprob": -4.0}]}]}

    corrector = om.OllamaTextCorrector(fetch=fetch)
    probs = corrector.choose("the Rules may concem, but need".split(), 3, ["concem,", "concern,"])
    assert seen["logprobs"] is True and seen["options"]["num_predict"] == 1
    assert max(probs, key=probs.get) == "concern," and abs(sum(probs.values()) - 1) < 1e-9


def test_the_vision_reader_sends_the_crops_and_anchors_only_when_asked():
    bodies = []

    def fetch(url, body):
        bodies.append(body)
        return {"message": {"content": json.dumps({"text": "shall"})}}

    reader = om.VisionWordReader(model="a-vision-model", fetch=fetch)
    assert reader.read("d29yZA==", "bGluZQ==") == "shall"
    assert len(bodies[0]["messages"][0]["images"]) == 2 and "OCR engine read" not in bodies[0]["messages"][0]["content"]
    reader.read("d29yZA==", "bGluZQ==", ocr_line="the Owner shail pay", ocr_word="shail")
    assert "shail" in bodies[1]["messages"][0]["content"]


def test_tesseract_tsv_words_keep_their_boxes_and_confidence():
    tsv = ("level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
           "4\t1\t1\t1\t1\t0\t10\t10\t300\t30\t-1\t\n"
           "5\t1\t1\t1\t1\t1\t10\t10\t40\t30\t96.5\tof\n"
           "5\t1\t1\t1\t1\t2\t60\t10\t60\t30\t91.0\tthe\n")
    words = parse_tsv(tsv, page=3)
    assert [(w.text, w.page, w.left, w.confidence) for w in words] == [("of", 3, 10, 96.5), ("the", 3, 60, 91.0)]


def _current(body, number="1.1"):
    return CurrentDocument("doc", "Doc", "base", [Provision(number, "Use.", body, 2, "doc", history=["base"])])


def _copy(body):
    text = "1.1 Use.\n" + body + "\n"
    return DocumentOutline("doc", "Doc", kind="declaration", text=text, sections=[Section("1.1", "Use.", 1, 0)])


def test_an_ocr_reading_is_likely_when_the_working_copy_and_the_rules_agree():
    lex = lexicon()
    current = _current("Each Owner shallpay the assessment when due.")
    asks = intake_task.ocr_reading_asks("doc", current, _copy("Each Owner shall pay the assessment when due."),
                                        Counter(), lexicon=lex)
    (ask,) = asks
    assert ask.likely and ask.detail["methods"] == ["working copy", "lexicon"] and ask.detail["guard"] == ""


def test_the_copys_reading_alone_is_not_likely_and_a_copy_slip_is_asked():
    lex = lexicon()
    # The copy drops a run-in caption: one reader, and it drops words.
    current = _current("Granting ofEasements. The Board may adopt rules.")
    (ask,) = intake_task.ocr_reading_asks("doc", current, _copy("The Board may adopt rules."), Counter(), lexicon=lex)
    assert not ask.likely and "drops a word" in " ".join(ask.evidence)
    # The copy keeps the OCR's run-together word: the rules ask about it, and it is not likely (the readers disagree).
    current = _current("Notice ofthe meeting shall be given to each Owner.")
    (ask,) = intake_task.ocr_reading_asks("doc", current, _copy("Notice ofthe meeting shall be given to each Owner."),
                                          Counter(), lexicon=lex)
    assert not ask.likely and ask.suggestion.startswith("of the") and "working copy reads" in " ".join(ask.evidence)


def test_without_a_copy_one_reader_is_held_and_a_second_makes_it_likely():
    lex = lexicon()
    current = _current("Notice ofthe meeting shall be given to each Owner.")
    held = []
    assert intake_task.ocr_reading_asks("doc", current, None, Counter(), lexicon=lex, held=held) == []
    assert [(section, s.right) for section, s in held] == [("1.1", "of the")]
    model = oc.Suggestion(1, 2, "ofthe", "of the", oc.Fix.SPLIT, (oc.Method.LOCAL_MODEL,), 0.99)
    (ask,) = intake_task.ocr_reading_asks("doc", current, None, Counter(), lexicon=lex, extra={"1.1": [model]})
    assert ask.likely and ask.detail["methods"] == ["lexicon", "local model"]


def test_library_suggestions_are_written_beside_the_text_never_into_it(tmp_path):
    (tmp_path / "library" / "text").mkdir(parents=True)
    with sqlite3.connect(tmp_path / "library" / "library.db") as conn:
        conn.execute("CREATE TABLE documents (id TEXT, path TEXT, kind TEXT)")
        conn.execute("INSERT INTO documents VALUES ('7', 'Folder/scan.pdf', 'policy')")
        conn.execute("INSERT INTO documents VALUES ('8', 'Folder/typed.pdf', 'policy')")
    raw = "# scan.pdf - ocr: `tesseract-cli`\n\nEach Owner shallpay the assessment | when due."
    (tmp_path / "library" / "text" / "7.txt").write_text(raw, encoding="utf-8")
    (tmp_path / "library" / "text" / "8.txt").write_text("Each Owner shall pay the assessment.", encoding="utf-8")
    (row,) = ocr_task.library_suggestions(tmp_path, lexicon=lexicon())
    assert row["id"] == "7" and row["engine"] == "tesseract-cli" and row["suggestions"] == 2
    side = json.loads((tmp_path / "library" / "text" / "7.ocr-suggestions.json").read_text(encoding="utf-8"))
    assert {i["right"] for i in side["items"]} == {"shall pay", ""}
    assert (tmp_path / "library" / "text" / "7.txt").read_text(encoding="utf-8") == raw


def test_the_corpus_leaves_out_the_document_being_read(tmp_path):
    (tmp_path / "outlines").mkdir()
    (tmp_path / "authorities" / "CIV").mkdir(parents=True)
    (tmp_path / "authorities" / "CIV" / "4000.md").write_text("The association shall keep records.", encoding="utf-8")
    (tmp_path / "outlines" / "doc.json").write_text(json.dumps({"text": "its own words"}), encoding="utf-8")
    (tmp_path / "outlines" / "other.json").write_text(json.dumps({"text": "another document"}), encoding="utf-8")
    texts = ocr_task.corpus_texts(tmp_path, exclude=("doc",))
    assert "its own words" not in texts and "another document" in texts and len(texts) == 2
