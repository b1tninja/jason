"""Routing to the page, the options a person names, and the learned channel's file. Made-up text; no model runs (the
vision reader is a stub) and no word list is reached."""

import json
import math

import pytest

from jason.community import ocr_channel as ch
from jason.community import ocr_correct as oc
from jason.community.lexicon import Lexicon, document_term_forms
from jason.tasks import ocr_correct as task

CORPUS = """The Owner of the Unit shall pay each assessment. The Board may adopt rules for the use of the Common Area.
Each Unit has a Unit number. The Owner shall maintain the Unit and the Association shall maintain the Common Area.
Notice of the meeting shall be given to each Owner of a Unit. Inspect the integrity of the Unit and of the Common Area.
The integrity of the building depends on the Unit and the roof. Any Owner may inspect the records of the Association."""

ENGLISH = {w: 1e-4 for w in ("the of owner unit shall pay each assessment board may adopt rules for use common area has a "
                              "number and maintain association notice meeting be given to inspect integrity building "
                              "depends on roof any records or on in at it is as that if no not").split()}
ENGLISH["ot"] = 2e-7


def lexicon():
    lex = Lexicon.from_texts([CORPUS] * 4, english=lambda w: ENGLISH.get(w, 0.0))
    return lex.with_terms({"unit"}, document_term_forms(CORPUS))


def test_the_page_is_read_for_what_the_text_rules_cannot_settle(monkeypatch):
    lex = lexicon()
    passage = "each Owner shall pay zzqx and the intcgrity ot the Unit".split()
    opts = oc.Options(route_real=0.2, real_ratio=1.0)
    doubted = task.routed({"1.1": passage}, lex, "doubts", opts)
    assert "zzqx" in {s.wrong for s in doubted["1.1"]}                     # nothing in reach: send it to the page
    assert "intcgrity" not in {s.wrong for s in doubted["1.1"]}            # the rules settle this one
    everything = task.routed({"1.1": passage}, lex, "suspects", opts)
    assert {"zzqx", "intcgrity"} <= {s.wrong for s in everything["1.1"]}
    assert task.routed({"1.1": passage}, lex, "guarded") == {}             # today's route is the rules' own guarded ones

    words = [{"text": t, "page": 0, "box": [0, 0, 1, 1], "block": 0, "line": 0} for t in passage]
    monkeypatch.setattr(task, "crops", lambda pdf, words, k, **kw: ("d29yZA==", "bGluZQ=="))
    replies = {"zzqx": "xyzzy", "intcgrity": "integrity", "ot": "of"}

    class Reader:
        current = ""

        def read(self, word, line):
            return replies[self.current]

    reader = Reader()
    taken = []
    for s in everything["1.1"]:
        reader.current = s.wrong
        for found in task.vision_readings(None, words, {"1.1": passage}, {"1.1": [s]}, reader, lexicon=lex).values():
            taken += [(f.wrong, f.right, f.methods) for f in found]
    assert ("intcgrity", "integrity", (oc.Method.VISION,)) in taken
    assert all(w != "zzqx" for w, _, _ in taken)                           # "xyzzy" is a suspect itself: not taken


def test_a_crop_reading_is_held_to_what_a_crop_can_say():
    lex = lexicon()
    assert task.usable_reading("reoccupy", "reoccupy his", lex) is False   # a crop that took in a neighbour
    assert task.usable_reading("ofthe", "of the", lex) is True             # run together is two words
    assert task.usable_reading("shail", "sha?l", lex) is False             # unreadable
    assert task.usable_reading("a", "a\nb", lex) is False                  # spans lines
    assert task.usable_reading("shail", "shail", lex) is False             # the same


def test_options_are_named_and_no_name_is_todays_behavior():
    assert task.options_for() == oc.DEFAULT
    on = task.options_for(["search", "case", "terms", "real-words"], ch.Channel("learned", (("tj", "u", -4.0),)))
    assert on.search and on.case_by_context and on.term_bonus > 0 and on.real_words > 0 and on.route_real > 0
    assert any(r == "tj" for r, _, _ in on.channel.rules) and any(r == "rn" for r, _, _ in on.channel.rules)
    with pytest.raises(ValueError):
        task.options_for(["nonsense"])


def test_rendered_text_read_back_gives_the_misreads_and_leaves_out_what_is_not_a_letter_confusion():
    from jason.tasks import ocr_synth

    printed = "the Owner shall pay each assessment when due and the Board may adopt rules".split()
    read = "tbe Owner shall pay each assessrnent when dueand the Board may adopt ru1es".split()
    assert ocr_synth.misreads(read, printed) == [("tbe", "the"), ("assessrnent", "assessment")]   # "dueand" is not one
    assert ocr_synth.misreads(printed, printed) == []
    words = ocr_synth.source_words(["---\ntitle: x\n---\n# Heading\nThe board **shall** keep records."] * 3, per_text=50)
    assert words[:3] == ["Heading", "The", "board"] or "shall" in words and "title" not in words


def test_a_learned_channel_is_letters_only_and_round_trips_through_the_data_folder(tmp_path):
    pairs = [("tjnit", "unit"), ("tjnits", "units"), ("tjser", "user")]
    channel = task.learn_channel(pairs, ["unit", "units", "user"] * 10, tmp_path)
    saved = json.loads(task.channel_path(tmp_path).read_text(encoding="utf-8"))
    assert [(r, p) for r, p, _ in saved["rules"]] == [("tj", "u")]
    assert saved["rules"][0][2] == pytest.approx(math.log(3 / 33), abs=1e-5)
    assert task.load_channel(tmp_path).rules[0][:2] == ("tj", "u") and channel.rules[0][:2] == ("tj", "u")
    assert task.load_channel(tmp_path / "nowhere") is None
