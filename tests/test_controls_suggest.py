"""The suggestion reader (``jason.controls.suggest``): general phrase evidence on the catalog's types, matched against made-up
provisions of a made-up "Example Bylaws". A match is a suggestion with the provision's words whole and verbatim, a floor only
where one count is certain, jason's labeled proposal, and jason's reading; a weak match is a question; nothing is adopted."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

import pytest

from controls_support import make
from jason.controls import catalog, store, suggest
from jason.controls.suggest import Provision, Suggestions
from jason.controls.types import Basis, ControlAct, ControlState

DOC = "example-bylaws"


def prov(number: str, words: str, depth: int = 1) -> Provision:
    return Provision(DOC, number, f"Example Bylaws {number}", words, depth)


PAYMENT = ("Checks. All checks, drafts, or orders for the payment of money issued in the name of the Association shall be "
           "signed by two directors.")
PAYMENT_OR = ("Checks. All checks, drafts, and orders for the payment of money shall be signed by any two directors, or by "
              "an officer and a director, unless the Board specifies another manner.")
PAYMENT_NO_COUNT = ("Checks. All checks, drafts, and orders for the payment of money shall be signed by such officers as "
                    "the Board determines.")
RESERVE = "Reserve. Money may be withdrawn from the reserve account only upon the signatures of two directors."
CONTRACT = ("Contracts. No officer may bind the Association to any contract unless authorized by resolution of the Board.")
LIMIT = ("Limits. The Board shall not have the power to enter a contract for a term of more than three years.")
MANAGER = ("Manager. The Board may engage a managing agent and shall prescribe the duties of the managing agent.")
CADENCE = ("Review. The Board shall review the bank reconciliation each month and note it in the minutes.")
RECORDER = "Records. The Secretary shall keep the minutes of all meetings of the Board."
NOTHING = "Annual meeting. The members shall meet once a year at a place the Board names in its notice."


def read(*provisions, **kw) -> Suggestions:
    kw.setdefault("duties_read", True)
    kw.setdefault("prior", ())
    return suggest.suggest(None, list(provisions), **kw)


def one(words: str, **kw):
    got = read(prov("99.9", words), **kw)
    assert len(got) == 1, [(s.type_key, s.question) for s in got]
    return got[0]


# --- the gate ----------------------------------------------------------------------------------------------------------------

class Exploding:
    def provisions(self):
        raise AssertionError("the documents were read before the duties were confirmed")


def test_nothing_is_suggested_until_the_duties_are_read_and_the_documents_are_not_even_opened():
    got = suggest.suggest(None, Exploding())                      # duties_read defaults to False
    assert got == [] and isinstance(got, Suggestions) and got.reason == suggest.NOT_READ
    assert "misread" in got.reason
    assert suggest.suggest(None, Exploding(), duties_read=False, prior=()) == []


# --- each family ---------------------------------------------------------------------------------------------------------------

def test_payment_signers_quote_the_provision_whole_and_read_a_floor_only_where_one_count_is_certain():
    s = one(PAYMENT)
    assert s.type_key == "payment-signers" and not s.question and s.key == "payment-signers"
    assert s.basis.words == PAYMENT and s.basis.citation == "Example Bylaws 99.9"          # whole, verbatim
    assert s.floor == {"signers": 2} and 'signers = 2, read from "signed by two"' in s.floor_note
    assert s.parameters["signers"] == 2 and s.digest == suggest.digest_of(PAYMENT)
    assert suggest.LABEL in s.reading and "jason proposes" in s.reading and "not a rule" in s.reading
    assert '"signed by"' in s.reading                                                      # which phrases matched


def test_a_count_followed_by_an_alternative_or_with_no_count_leaves_the_floor_to_a_person():
    for words in (PAYMENT_OR, PAYMENT_NO_COUNT):
        s = one(words)
        assert s.type_key == "payment-signers" and not s.question
        assert s.floor is None and s.floor_note.startswith("floor: read by a person")
        assert s.basis.words == words and not s.basis.floor
    assert "alternative" in one(PAYMENT_OR).floor_note


def test_reserve_signers_and_a_payment_sentence_that_names_the_reserve_is_not_a_payment_rule():
    s = one(RESERVE)
    assert s.type_key == "reserve-signers" and s.floor == {"signers": 2} and s.parameters["signers"] == 2
    both = ("Checks. All checks, drafts, or orders for payment from the reserve fund shall be signed by two directors.")
    assert {x.type_key for x in read(prov("99.9", both))} == {"reserve-signers"}


def test_contract_authorization_limit_checks_manager_cadence_and_recorder():
    cases = {CONTRACT: "contract-authorization", LIMIT: "limit-checks", MANAGER: "manager-spending-authority",
             CADENCE: "review-cadence", RECORDER: "recorder"}
    for words, key in cases.items():
        s = one(words)
        assert s.type_key == key and not s.question, key
        assert s.basis.words == words and s.floor is None and s.floor_note.startswith(suggest.FLOOR_BY_A_PERSON)
    assert one(CONTRACT).parameters == {"resolution_first": True}
    assert one(RECORDER).parameters["recorded_by"][0].value == "secretary"
    assert read(prov("99.9", NOTHING)) == []


def test_an_unrelated_provision_matches_nothing_and_a_type_without_evidence_is_never_suggested():
    assert read(prov("1.1", NOTHING), prov("1.2", "Short.")) == []
    assert catalog.get("second-person-confirmation").evidence == ()


# --- what jason proposes -------------------------------------------------------------------------------------------------------

def test_no_amount_or_period_is_ever_invented_and_the_board_sets_them():
    got = read(*[prov(f"9.{n}", w) for n, w in enumerate(
        (PAYMENT, RESERVE, CONTRACT, LIMIT, MANAGER, CADENCE, RECORDER), 1)])
    assert len(got) == 7 and not any(s.question for s in got)
    for s in got:
        assert not set(s.parameters) & {"over_cents", "max_cents", "limit_cents", "max_term_days", "limit_days",
                                        "every_days"}, s.type_key
    pay = next(s for s in got if s.type_key == "payment-signers")
    assert "over_cents" in pay.left_to_board and "the amount above which the rule applies" in pay.reading
    assert "limit_cents" in next(s for s in got if s.type_key == "limit-checks").left_to_board


def test_the_proposal_never_goes_below_the_floor_it_read():
    s = one("Checks. All checks, drafts, or orders for payment shall be signed by one officer.")
    assert s.floor == {"signers": 1} and s.parameters["signers"] == 2                # jason's proposal is above the floor
    # a floor the catalog cannot enforce (more than two signers) is a person's to read, not a half-enforced floor
    big = one("Checks. All checks, drafts, or orders for payment shall be signed by three directors.")
    assert big.floor is None and "at most 2" in big.floor_note


def test_every_suggestion_validates_as_a_control_the_board_could_take():
    from jason.controls.effective import validate

    for words in (PAYMENT, RESERVE, CONTRACT, LIMIT, MANAGER, CADENCE, RECORDER):
        c = one(words).control()
        assert c.state is ControlState.SUGGESTED and validate(c) == [] and c.history == ()


# --- questions -----------------------------------------------------------------------------------------------------------------

def test_phrases_in_the_section_but_not_in_one_sentence_are_a_question_not_a_suggestion():
    words = ("Checks. All checks, drafts, or orders for the payment of money issued in the name of the Association are "
             "kept by the treasurer. Signatures. A document so issued shall be signed by the person the Board names.")
    s = one(words)
    assert s.question and s.key == "" and s.floor is None and not s.parameters
    assert "not in one sentence" in s.why_question and "no suggestion" in s.reading
    assert s.basis.words == words                                                       # the question carries the words whole


def test_a_section_that_reads_two_ways_about_the_count_is_a_question():
    s = one("Checks. All checks, drafts, or orders for payment shall be signed by two directors. A check over a small sum "
            "shall be signed by one officer.")
    assert s.question and "different counts" in s.why_question


def test_a_long_article_with_scattered_phrases_is_not_a_question():
    long = ("Checks are discussed here. " + "Padding sentence about nothing. " * 120
            + "Orders are signed by the Board.")
    assert len(long) > suggest.QUESTION_MAX_CHARS
    assert read(prov("9", long)) == []


# --- nested sections -------------------------------------------------------------------------------------------------------------

def test_of_nested_sections_the_narrowest_strong_match_is_the_suggestion():
    parent = prov("9.3", "9.3 Checks\n" + PAYMENT + "\n(a) Another line.", depth=2)
    child = prov("9.3(a)", PAYMENT, depth=3)
    got = read(parent, child)
    assert [s.number for s in got] == ["9.3(a)"]
    weak_parent = prov("9.4", "Checks and drafts are kept. Signed by the Board.", depth=2)
    assert [s.number for s in read(weak_parent)] == ["9.4"] and read(weak_parent)[0].question


def test_two_sections_for_one_type_get_distinct_keys_and_the_first_keeps_the_type_key():
    got = read(prov("9.1", PAYMENT), prov("9.7", PAYMENT_NO_COUNT))
    assert [s.key for s in got] == ["payment-signers", "payment-signers-example-bylaws-9-7"]


# --- a provision that changed ----------------------------------------------------------------------------------------------------

def test_a_provision_already_recorded_with_the_same_words_is_not_suggested_again():
    prior = make("payment-signers", {"signers": 2}, basis=Basis("Example Bylaws 99.9", PAYMENT))
    got = suggest.suggest(None, [prov("99.9", PAYMENT)], duties_read=True, prior=[prior])
    assert got == [] and got.known == 1


def test_a_provision_whose_words_changed_is_flagged_under_the_same_key_and_the_control_stays():
    prior = make("payment-signers", {"signers": 2}, basis=Basis("Example Bylaws 99.9", PAYMENT), key="pay",
                 state=ControlState.ADOPTED)
    now = PAYMENT.replace("two directors", "any two officers")
    got = suggest.suggest(None, [prov("99.9", now)], duties_read=True, prior=[prior])
    assert len(got) == 1
    s = got[0]
    assert s.changed and s.key == "pay" and s.was_words == PAYMENT and s.basis.words == now and s.prior_state == "adopted"
    assert prior.state is ControlState.ADOPTED and prior.basis.words == PAYMENT


# --- recording -----------------------------------------------------------------------------------------------------------------

@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setenv("JASON_SPEC_DIR", str(tmp_path / "spec"))
    return tmp_path


def test_recording_appends_suggested_acts_by_jason_and_adopts_nothing(world):
    found = read(prov("9.1", PAYMENT), prov("9.2", RESERVE),
                 prov("9.9", "Checks. Some checks are kept. Signed by the Board when it likes."))
    assert len(found) == 3 and len(found.questions) == 1
    done = suggest.record(found, by="A Secretary", data_dir=world, profile="alpha",
                          now=datetime(2099, 10, 1, tzinfo=timezone.utc))
    assert done.recorded == ("payment-signers", "reserve-signers") and done.questions == 1
    rows = store.acts(world)
    assert [(r["act"], r["by"], r["key"]) for r in rows] == [("suggest", "jason", "payment-signers"),
                                                              ("suggest", "jason", "reserve-signers")]
    assert "A Secretary" in rows[0]["why"] and "Example Bylaws 9.1" in rows[0]["why"]
    controls = store.load(world, "alpha")
    assert {c.state for c in controls} == {ControlState.SUGGESTED}                         # nothing adopted
    assert all(c.decision == "" and c.effective is None for c in controls)
    assert [h.act for h in controls[0].history] == [ControlAct.SUGGEST] and controls[0].history[0].by == "jason"
    assert controls[0].basis.words == PAYMENT and controls[0].reading.startswith(suggest.LABEL)
    snap = suggest.load_readings(world)
    assert len(snap["questions"]) == 1 and snap["questions"][0]["question"] and snap["by"] == "A Secretary"
    assert store.verify(world)[0] is True


def test_recording_twice_records_each_control_once_and_a_changed_provision_is_kept_for_the_screen_not_re_suggested(world):
    found = read(prov("9.1", PAYMENT))
    suggest.record(found, by="A Secretary", data_dir=world, profile="alpha")
    again = suggest.suggest(None, [prov("9.1", PAYMENT)], duties_read=True, data_dir=world,
                            prior=store.load(world, "alpha"))
    assert again == [] and again.known == 1
    changed = suggest.suggest(None, [prov("9.1", PAYMENT + " It is amended.")], duties_read=True, data_dir=world,
                              prior=store.load(world, "alpha"))
    done = suggest.record(changed, by="A Secretary", data_dir=world, profile="alpha")
    assert done.recorded == () and done.changed == 1 and len(store.acts(world)) == 1
    assert suggest.load_readings(world)["changed"][0]["key"] == "payment-signers"


def test_recording_names_the_person_and_a_missing_snapshot_is_empty(world):
    with pytest.raises(ValueError, match="by"):
        suggest.record(read(prov("9.1", PAYMENT)), by=" ", data_dir=world)
    assert suggest.load_readings(world) == {"read": "", "by": "", "questions": [], "changed": []}
    assert not store.acts_path(world).exists()


# --- the evidence is data ----------------------------------------------------------------------------------------------------------

def test_every_evidence_pattern_compiles_and_names_no_association_or_number():
    for t in catalog.CATALOG:
        for ev in t.evidence:
            assert ev.cues
            for cue in (*ev.cues, *ev.unless):
                re.compile(cue.pattern, re.I)
                assert cue.name and not re.search(r"\d", cue.name), (t.key, cue.name)
            for fr in ev.floor:
                t.spec(fr.param)
                for p in fr.patterns:
                    assert "(?P<n>" in p and re.compile(p, re.I)
        for k in t.proposal:
            t.spec(k)
        for k in t.board_sets:
            t.spec(k)
    assert [t.key for t in catalog.CATALOG if not t.evidence] == ["second-person-confirmation"]


def test_the_catalog_and_the_reader_import_no_profile():
    import subprocess
    import sys

    code = "import sys; import jason.controls.suggest, jason.controls.view; print([m for m in sys.modules if m.startswith(('mystique','jason_'))])"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout
    assert out.strip() == "[]"


def test_suggestions_serialize_as_json_with_the_words_whole():
    got = read(prov("9.1", PAYMENT))
    body = json.loads(json.dumps([s.as_dict() for s in got]))
    assert body[0]["words"] == PAYMENT and body[0]["readingLabel"] == suggest.LABEL and body[0]["floor"] == {"signers": 2}
    assert body[0]["parameters"]["must_include"] == ["treasurer"] and body[0]["boardSets"] == ["over_cents"]
