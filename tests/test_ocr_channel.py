"""The OCR channel and what it reads: letters learned from aligned text, case by context, real-word errors, the
vocabulary search, and the vision chooser and line reader as scorers and a second reader. Made-up text throughout; no
model runs (each model's reply is a canned dict) and no word list is reached."""

import json
import math

import pytest

from jason.community import ocr_channel as ch
from jason.community import ocr_correct as oc
from jason.community import ocr_models as om
from jason.community import ocr_vocab
from jason.community.lexicon import Lexicon, document_term_forms, document_terms

CORPUS = """The Owner of the Unit shall pay each assessment. The Board may adopt rules for the use of the Common Area.
Each Unit has a Unit number. The Owner shall maintain the Unit and the Association shall maintain the Common Area.
Notice of the meeting shall be given to each Owner of a Unit. Inspect the integrity of the Unit and of the Common Area.
The integrity of the building depends on the Unit and the roof. Any Owner may inspect the records of the Association."""

ENGLISH = {w: 1e-4 for w in ("the of owner unit shall pay each assessment board may adopt rules for use common area has a "
                              "number and maintain association notice meeting be given to inspect integrity building "
                              "depends on roof any records or on in at it is as that if no not").split()}
ENGLISH["ot"] = 2e-7             # a rare word the list knows ("ot" is in some lists), so the English prior never doubts it


def lexicon(**kw):
    lex = Lexicon.from_texts([CORPUS] * 4, english=lambda w: ENGLISH.get(w, 0.0), **kw)
    return lex.with_terms({"unit"}, document_term_forms(CORPUS))


# The channel, learned.

def test_a_read_word_and_its_printed_word_differ_by_letter_groups_not_single_edits():
    assert ch.char_spans("tjnit", "unit") == [("tj", "u")]            # two glyphs for one wide letter
    assert ch.char_spans("rnodern", "modern") == [("rn", "m")]
    assert ch.char_spans("ot", "of") == [("t", "f")]
    assert ch.char_spans("shail", "shall") == [("i", "l")]
    assert ch.char_spans("same", "same") == []
    for read, printed in (("raore", "more"), ("concem", "concern"), ("wnhm", "within")):
        for a, b in ch.char_spans(read, printed):
            assert a and b                                               # every rule has letters on both sides


def test_pairs_are_the_words_read_wrongly_one_for_one():
    read = "the Owner ot the tJnit and rnay".split()
    printed = "the Owner of the Unit and may".split()
    assert ch.aligned_pairs(read, printed) == [("ot", "of"), ("tjnit", "unit"), ("rnay", "may")]
    assert ch.aligned_pairs("a b c".split(), "a b".split()) == []        # a dropped word is no letter confusion


def test_the_channel_counts_chances_not_words_and_keeps_rules_seen_often_enough():
    pairs = [("tjnit", "unit"), ("tjnits", "units"), ("rnay", "may"), ("ot", "of")]
    printed = ["unit"] * 40 + ["units"] * 10 + ["may"] * 5 + ["of"] * 100
    channel = ch.learn(pairs, printed, min_count=2)
    rules = {(a, b): math.exp(v) for a, b, v in channel.rules}
    assert set(rules) == {("tj", "u")}                                   # "rn"/"m" and "t"/"f" were seen once
    assert rules[("tj", "u")] == pytest.approx(2 / (50 + 2))             # 2 reads of "u" in 50 chances to misread it
    assert dict((r, p) for r, p, _ in channel.rules)["tj"] == "u"
    assert list(channel.reads("tjnit")) == [("unit", pytest.approx(math.log(2 / 52)))]
    assert channel.merged(ch.Channel("x", (("rn", "m", -4.0),))).table(5)[0][0] in ("rn", "tj")


# Candidates through the channel, by search, and the options' defaults.

def test_a_two_glyph_misread_is_out_of_reach_of_the_hand_list_and_in_reach_of_a_learned_rule():
    lex = lexicon()
    tokens = "of the tJnit and".split()
    assert oc.correct_token(tokens, 2, lex) is None                      # today: no candidate, no suggestion
    learned = ch.Channel("learned", (("tj", "u", math.log(0.02)),))
    s = oc.correct_token(tokens, 2, lex, opts=oc.Options(channel=learned, case_by_context=True))
    assert s is not None and s.right == "Unit"


def test_search_finds_words_several_edits_away_and_scores_them_by_the_channel():
    lex = lexicon()
    near = ocr_vocab.search("xssessmxnt", lex, oc.HAND_CHANNEL)
    assert "assessment" in near and "assessment" not in oc.candidates("xssessmxnt", lex)   # two arbitrary edits
    assert ocr_vocab.channel_cost("tjnit", "unit", ch.Channel("c", (("tj", "u", -3.0),))) == pytest.approx(-3.0)
    assert ocr_vocab.channel_cost("unit", "unit", None) == 0.0
    s = oc.correct_token("each xssessmxnt shall".split(), 1, lex, opts=oc.Options(search=True))
    assert s is not None and s.right == "assessment"
    assert oc.correct_token("each xssessmxnt shall".split(), 1, lex) is None   # beyond today's candidates


def test_the_default_options_are_todays_behavior():
    lex = lexicon()
    assert oc.Options() == oc.DEFAULT
    for tokens in ("any faiiure of the Board".split(), "each Owner shallpay the".split(), "the Lhe Board".split()):
        for i in range(len(tokens)):
            assert oc.correct_token(tokens, i, lex) == oc.correct_token(tokens, i, lex, opts=oc.DEFAULT)
    assert oc.suggest("the Owner ot the Unit".split(), lex) == oc.suggest("the Owner ot the Unit".split(), lex, opts=oc.DEFAULT)


# Case, and the document's own terms.

def test_case_comes_from_the_sentence_and_the_documents_terms_not_the_misread_glyph():
    lex = lexicon()
    assert document_term_forms(CORPUS).get("unit") == "Unit"          # "Unit" mid-sentence, always, though lists know "unit"
    assert "the" not in document_term_forms(CORPUS) and "of" not in document_term_forms(CORPUS)
    # "Lhe" read with a capital L: mid-sentence it is "the"; after a sentence's end, "The"; the old rule keeps the L.
    assert oc.case_for("the", "Lhe", "integrity", lex) == "the"
    assert oc.case_for("the", "Lhe", "shall.", lex) == "The"
    assert oc._match_case("Lhe", "the") == "The"
    assert oc.case_for("unit", "tjnit", "of", lex) == "Unit"             # a defined term in its defined capitals
    assert oc.case_for("owner", "OWNER", "the", lex) == "OWNER"          # all capitals stay
    assert oc.case_for("the", "Lhe", "(a)", lex) == "The"                # after a label the token's own case stands
    assert oc.case_for("the", "lhe", "", lex) == "the"


def test_a_defined_term_ranks_up_among_candidates():
    lex = lexicon()
    loose = oc.readings("of the tnit and".split(), 2, lex, oc.Options(case_by_context=True))
    bonus = oc.readings("of the tnit and".split(), 2, lex, oc.Options(case_by_context=True, term_bonus=3.0))
    assert bonus["Unit"] > loose["Unit"]


# Real-word errors: the word list knows "ot", the context does not.

def test_a_real_word_read_for_another_is_found_by_the_noisy_channel_over_real_words():
    lex = lexicon()
    tokens = "the integrity ot the Unit and of the Common Area".split()
    assert lex.classify("ot").suspect is False or lex.classify("ot").suspect is True   # whichever the lists say
    on = oc.Options(real_words=0.5, real_ratio=1.0, case_by_context=True)
    found = oc.real_word_readings(tokens, 2, lex, on)
    assert found and max(found, key=found.get) in ("of", "or", "on", "at", "it")
    hits = [s for s in oc.lexicon_suggestions(tokens, lex, opts=on) if s.wrong == "ot"]
    assert hits and hits[0].right == "of"
    # A word the context supports is left alone, and with the switch off nothing is read for a real word.
    assert not [s for s in oc.lexicon_suggestions("the integrity of the Unit".split(), lex, opts=on)]
    assert oc.correct_token(tokens, 2, lex) is None or lex.classify("ot").suspect


def test_doubts_are_what_the_text_rules_cannot_settle_and_the_page_should():
    lex = lexicon()
    tokens = "of the Unit zzqx and the intcgrity ot the".split()
    found = {d.index: d.why for d in oc.doubts(tokens, lex, oc.Options(route_real=0.3, real_ratio=1.0))}
    assert found.get(3) == "no candidate"                                # nothing in reach: send it to the page
    assert 6 not in found                                                # "intcgrity" has a settled reading
    assert oc.doubts("the Owner shall".split(), lex) == []


# The vision model as a scorer, and as a second reader of a line.

def test_the_vision_chooser_sends_the_crop_and_reads_the_letters_probabilities():
    seen = {}

    def fetch(url, body):
        seen.update(body)
        return {"message": {"content": "B"}, "logprobs": [{"token": "B", "top_logprobs": [
            {"token": "B", "logprob": -0.05}, {"token": "A", "logprob": -3.0}, {"token": "C", "logprob": -6.0}]}]}

    chooser = om.VisionChooser(model="a-vision-model", fetch=fetch)
    probs = chooser.choose("d29yZA==", "bGluZQ==", "tJnit", ["tJnit", "Unit"])
    assert seen["logprobs"] is True and seen["options"]["num_predict"] == 1
    assert len(seen["messages"][0]["images"]) == 2 and "tJnit" in seen["messages"][0]["content"]
    assert max(probs, key=probs.get) == "Unit" and abs(sum(probs.values()) - 1) < 1e-9
    assert set(probs) == {"tJnit", "Unit", om.NONE_OF_THESE}             # it is never asked to write a reading
    assert om.letter_weights({}, "AB") == {"A": 0.5, "B": 0.5}


def test_a_line_reread_is_taken_only_on_the_tokens_the_rules_doubt_and_only_if_minimal():
    tokens = "breaches of the watertight integrity ot Lhe tJnit and for the presence".split()
    reread = "breaches of the watertight integrity of the Unit and for the presence"
    found = om.line_suggestions(tokens, reread, doubted=[7])            # only "tJnit" is doubted; "ot" is not
    assert [(s.wrong, s.right) for s in found] == [("tJnit", "Unit")]
    assert all(s.methods == (oc.Method.VISION,) for s in found)
    both = om.line_suggestions(tokens, reread, doubted=[5, 6, 7])
    assert [(s.wrong, s.right) for s in both] == [("ot", "of"), ("Lhe", "the"), ("tJnit", "Unit")]
    # A re-reading with an unreadable mark, or one that wandered to another length, is not used.
    assert om.line_suggestions(tokens, "breaches of the ? integrity", doubted=[7]) == []
    assert om.line_suggestions(tokens, "breaches of", doubted=[7]) == []
    # An edit that is not minimal (a different word) is not taken.
    assert om.line_suggestions(["the", "tJnit", "and"], "the Association and", doubted=[1]) == []
    seen = {}

    def fetch(url, body):
        seen.update(body)
        return {"message": {"content": json.dumps({"text": "of the Unit"})}}

    assert om.VisionLineReader(model="a-vision-model", fetch=fetch).read("bGluZQ==") == "of the Unit"
    assert len(seen["messages"][0]["images"]) == 1
