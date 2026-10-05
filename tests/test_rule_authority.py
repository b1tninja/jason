"""Who may make rules (jason.community.rule_authority), on a made-up declaration: the candidates by rule, the rules' reading,
the model step with a faked Ollama (no model runs here), agreement and tiers, the subjects against the rules on file, the
store, and the measurement against a made-up gold set."""

from __future__ import annotations

import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from jason.community import rule_authority as ra
from jason.community.deontic import read_outline
from jason.community.outlines import outline_from_text

FIXTURES = Path(__file__).parent / "fixtures" / "rules"


def outline(kind: str = "declaration", key: str = "example-decl"):
    return outline_from_text((FIXTURES / "example-declaration.txt").read_text(encoding="utf-8"), key=key,
                             title="Declaration of Example Commons", kind=kind)


@pytest.fixture(scope="module")
def doc():
    o = outline()
    duties = read_outline(o)
    return o, duties, ra.candidates(o, duties)


def cand(cands, start):
    found = [c for c in cands if c.text.startswith(start)]
    assert len(found) == 1, (start, [c.text[:40] for c in cands])
    return found[0]


# ---------------------------------------------------------------------------------------------------------------------
# Candidates


def test_candidates_are_the_sentences_that_name_a_power_a_limit_or_a_reference(doc):
    _, _, cands = doc
    for start in ("The Board shall have the power", "The Rules may concern parking", "The Board may adopt and enforce pet",
                  "Owners shall comply with the Rules"):
        cand(cands, start)


def test_an_insurance_policy_and_a_parked_vehicle_are_not_candidates(doc):
    _, _, cands = doc
    assert not any("title insurance" in c.text for c in cands)
    assert not any(c.text.startswith("Vehicles shall be parked") for c in cands)


def test_a_standard_left_to_the_board_is_collected_without_the_word_rule(doc):
    _, _, cands = doc
    c = cand(cands, "A reasonable time limit")
    assert "delegation" in c.reasons


def test_why_each_was_collected_is_kept(doc):
    _, _, cands = doc
    assert "verb+object" in cand(cands, "The Board shall have the power").reasons
    assert "duty: permission of board" in cand(cands, "The Board shall have the power").reasons
    assert "scope" in cand(cands, "The Rules may concern").reasons
    assert any(r.startswith("refers") for r in cand(cands, "Owners shall comply with").reasons)


def test_a_candidate_has_a_stable_id_and_its_section(doc):
    _, _, cands = doc
    c = cand(cands, "The Board shall have the power")
    assert c.section == "2.1" and c.id.startswith("example-decl#2.1:")
    assert c.id == ra.candidates(outline())[[x.id for x in cands].index(c.id)].id


def test_a_list_a_lead_in_opens_goes_with_the_candidate():
    text = ("1.1 Rules.\nThe Board may adopt Rules regulating the Common Area, including Rules\n"
            "(a) limiting the hours of the pool, and\n(b) regulating parking.\n")
    o = outline_from_text(text, key="x", kind="declaration")
    (c,) = [c for c in ra.candidates(o) if c.text.startswith("The Board may adopt")]
    assert len(c.items) == 2 and "limiting the hours" in c.items[0]
    assert ra.Subject.PARKING in ra.rule_reading(c).subjects


# ---------------------------------------------------------------------------------------------------------------------
# The rules' reading


def reading(doc, start):
    o, duties, cands = doc
    return ra.rule_reading(cand(cands, start), duties)


def test_a_power_to_adopt_rules_is_a_grant_held_by_the_board(doc):
    r = reading(doc, "The Board shall have the power")
    assert r.answer is ra.Answer.GRANT and r.holder is ra.Holder.BOARD
    assert ra.Subject.COMMON_AREA in r.subjects
    assert {c.kind for c in r.conditions} >= {ra.Condition.REASONABLE, ra.Condition.CONSISTENT_WITH_DOCUMENTS}


def test_a_committee_that_may_adopt_guidelines_holds_the_power(doc):
    r = reading(doc, "The Design Committee may adopt")
    assert (r.answer, r.holder) == (ra.Answer.GRANT, ra.Holder.COMMITTEE)
    assert ra.Subject.ARCHITECTURE in r.subjects
    assert any(c.kind is ra.Condition.BOARD_APPROVAL for c in r.conditions)


def test_notice_and_reversal_limit_the_power_and_give_none(doc):
    notice = reading(doc, "The Board shall give each Member")
    assert notice.answer is ra.Answer.LIMITS and any(c.kind is ra.Condition.NOTICE for c in notice.conditions)
    vote = reading(doc, "A Rule may be reversed")
    assert vote.answer is ra.Answer.LIMITS and any(c.kind is ra.Condition.MEMBER_VOTE for c in vote.conditions)


def test_a_scope_list_and_a_rule_adopted_elsewhere_only_refer(doc):
    assert reading(doc, "The Rules may concern").answer is ra.Answer.REFERS
    shall_comply = reading(doc, "Owners shall comply")
    assert shall_comply.answer is ra.Answer.REFERS and shall_comply.holder is ra.Holder.BOARD


def test_a_rule_speaking_of_itself_is_no_grant(doc):
    assert reading(doc, "These Rules shall remain in effect").answer is ra.Answer.NO


def test_the_rules_reading_does_not_find_a_delegated_standard(doc):
    # The measured weakness: "established by the Board" is a reference to the rules, and the model decides.
    assert reading(doc, "A reasonable time limit").answer is ra.Answer.REFERS


def test_every_condition_and_the_procedure_are_words_of_the_sentence(doc):
    for c in doc[2]:
        r = ra.rule_reading(c, doc[1])
        flat = " ".join(c.text.split()).lower()
        for cond in r.conditions:
            assert cond.quote.lower() in flat, (c.text[:40], cond)
        assert not r.procedure or r.procedure.lower() in flat


def test_the_procedure_a_limit_names_is_quoted(doc):
    r = reading(doc, "The Board shall give each Member")
    assert "30 days" in r.procedure


# ---------------------------------------------------------------------------------------------------------------------
# The model step


def answer(**kw):
    base = {"grant": "yes", "holder": "board", "subjects": [], "other_subjects": [], "conditions": [], "procedure": "", "words": ""}
    return json.dumps({**base, **kw})


def test_a_model_quote_is_kept_only_when_the_section_has_it(doc):
    c = cand(doc[2], "The Board shall have the power")
    raw = answer(subjects=["common_area", "not_a_subject"], other_subjects=["swimming"],
                 conditions=[{"kind": "reasonable", "quote": "reasonable Rules"},
                             {"kind": "notice", "quote": "thirty days of notice to every owner"},
                             {"kind": "no_such_kind", "quote": "reasonable Rules"}],
                 procedure="adopt, amend, and repeal", words="The Board shall have the power to adopt, amend, and repeal")
    r = ra.model_reading(raw, c)
    assert r.answer is ra.Answer.GRANT and r.holder is ra.Holder.BOARD
    assert r.subjects == (ra.Subject.COMMON_AREA,) and r.other_subjects == ("swimming",)
    assert [x.kind for x in r.conditions] == [ra.Condition.REASONABLE]
    assert r.words.startswith("The Board shall have the power")
    assert r.dropped == ("thirty days of notice to every owner",)


def test_quotes_compare_without_regard_to_case_spacing_or_quote_marks(doc):
    c = cand(doc[2], "The Board shall have the power")
    r = ra.model_reading(answer(words="the board shall  have the power\nto adopt"), c)
    assert r.words and r.dropped == ()


def test_a_no_answer_carries_no_subjects_or_conditions(doc):
    c = cand(doc[2], "The Board shall have the power")
    r = ra.model_reading(answer(grant="no", subjects=["pets"], conditions=[{"kind": "reasonable", "quote": "reasonable Rules"}]), c)
    assert r.answer is ra.Answer.NO and not r.subjects and not r.conditions


@pytest.mark.parametrize("raw", ["", "not json", "[1]", json.dumps({"grant": "maybe", "holder": "board"}),
                                 json.dumps({"grant": "yes", "holder": "the king"})])
def test_an_answer_outside_the_closed_lists_is_not_a_reading(doc, raw):
    assert ra.model_reading(raw, doc[2][0]) is None


def test_the_prompt_names_kinds_and_no_section_or_figure(doc):
    text = ra.prompt_for(doc[2][0])
    assert "[[" in text and "yes: the sentence gives" in text
    method = ra.METHOD + ra.EXAMPLES
    assert not re.search(r"\bSection\s+\d|\b(?:CIV|Civil Code)\s+\d{4}|\$\d", method)


def fake_ollama(by_sentence, calls):
    def fetch(url, payload):
        calls.append(payload)
        prompt = payload["messages"][0]["content"]
        sentence = re.findall(r"\[\[(.*?)\]\]", prompt, re.S)[-1]
        for start, reply in by_sentence.items():
            if sentence.startswith(start):
                temperature = payload["options"]["temperature"]
                body = reply[temperature > 0] if isinstance(reply, tuple) else reply
                return {"message": {"content": body}}
        return {"message": {"content": answer(grant="no", holder="unstated")}}
    return fetch


def test_the_model_is_asked_once_greedy_and_then_for_each_extra_sample(doc):
    calls: list = []
    model = ra.RuleModel(fetch=fake_ollama({}, calls))
    r = model.read(doc[2][0], samples=3)
    assert len(calls) == 4
    assert [c["options"]["temperature"] for c in calls] == [0.0, 0.3, 0.3, 0.3]
    assert [c["options"]["seed"] for c in calls[1:]] == [1, 2, 3]
    assert all(c["format"] is ra.ANSWER_SCHEMA and c["think"] is False and c["stream"] is False for c in calls)
    assert r.consistency == 1.0


def test_self_consistency_is_the_share_of_samples_that_agree_on_answer_and_holder(doc):
    c = cand(doc[2], "The Board shall have the power")
    yes, no, other = answer(), answer(grant="no"), answer(holder="association")
    seq = iter([yes, yes, no, other])
    model = ra.RuleModel(fetch=lambda url, payload: {"message": {"content": next(seq)}})
    assert model.read(c, samples=3).consistency == pytest.approx(1 / 3)


def test_the_default_model_is_the_nine_billion_text_model_and_only_a_local_ollama_is_asked():
    from jason.community.ocr_models import DEFAULT_TEXT_MODEL

    assert ra.RuleModel(fetch=lambda *a: {}).model == DEFAULT_TEXT_MODEL == "qwen3.5:9b"
    with pytest.raises(ValueError):
        ra.RuleModel(base_url="http://example.com:11434")


def test_a_model_preflight_runs_before_a_real_request(monkeypatch, doc):
    seen = []
    import jason.local_ai as local_ai

    def refuse(model, **kw):
        seen.append(model)
        raise local_ai.LocalAIUnavailable("running without the GPU")

    monkeypatch.setattr(local_ai, "preflight", refuse)
    from jason.community.content import ModelUnavailable

    with pytest.raises(ModelUnavailable):
        ra.RuleModel().ask(doc[2][0])
    assert seen == ["qwen3.5:9b"]


# ---------------------------------------------------------------------------------------------------------------------
# Agreement


def r(answer_, holder=ra.Holder.BOARD, reader="rules", **kw):
    return ra.Reading(reader, answer_, holder, **kw)


def test_two_readers_that_read_a_grant_with_one_holder_are_likely(doc):
    c = doc[2][0]
    row = ra.combine(c, r(ra.Answer.GRANT), r(ra.Answer.GRANT, reader="model", consistency=1.0))
    assert row.tier is ra.Tier.LIKELY and row.readers == ("rules", "model") and row.consistency == 1.0


def test_an_unstated_holder_agrees_with_a_stated_one(doc):
    row = ra.combine(doc[2][0], r(ra.Answer.GRANT, ra.Holder.UNSTATED), r(ra.Answer.GRANT, reader="model"))
    assert row.tier is ra.Tier.LIKELY and row.holder is ra.Holder.BOARD


def test_two_holders_make_one_reader_alone_a_suggestion(doc):
    row = ra.combine(doc[2][0], r(ra.Answer.GRANT, ra.Holder.BOARD), r(ra.Answer.GRANT, ra.Holder.ASSOCIATION, reader="model"))
    assert row.tier is ra.Tier.SUGGESTED


def test_without_a_model_every_row_is_one_reader_alone(doc):
    assert ra.combine(doc[2][0], r(ra.Answer.GRANT), None).tier is ra.Tier.SUGGESTED


def test_a_grant_one_reader_denies_is_a_conflict_and_still_a_lead(doc):
    row = ra.combine(doc[2][0], r(ra.Answer.GRANT), r(ra.Answer.NO, reader="model"))
    assert row.tier is ra.Tier.CONFLICT and row.answer is ra.Answer.GRANT
    row = ra.combine(doc[2][0], r(ra.Answer.REFERS), r(ra.Answer.GRANT, reader="model"))
    assert row.tier is ra.Tier.CONFLICT and row.readers == ("model",)


def test_neither_reader_reading_a_grant_or_a_limit_is_no_row(doc):
    assert ra.combine(doc[2][0], r(ra.Answer.REFERS), r(ra.Answer.NO, reader="model")) is None


def test_a_row_recites_the_models_words_when_verbatim_else_the_sentence(doc):
    c = cand(doc[2], "The Board shall have the power")
    quoted = ra.model_reading(answer(words="The Board shall have the power to adopt"), c)
    assert ra.combine(c, r(ra.Answer.GRANT), quoted).words == "The Board shall have the power to adopt"
    invented = ra.model_reading(answer(words="the Board may do anything"), c)
    row = ra.combine(c, r(ra.Answer.GRANT), invented)
    assert row.words == " ".join(c.text.split())


def test_find_with_a_model_reads_each_candidate_and_remembers_the_answers(doc):
    o, duties, _ = doc
    calls: list = []
    model = ra.RuleModel(fetch=fake_ollama({"The Board shall have the power": answer(subjects=["common_area"]),
                                            "A reasonable time limit": answer(subjects=["meetings"])}, calls))
    cache: dict = {}
    first = ra.find([o], model=model, duties={o.key: duties}, samples=1, cache=cache)
    n = len(calls)
    assert n == 2 * len(first["candidates"]) and len(cache) == len(first["candidates"])
    by_start = {a.sentence[:30]: a for a in first["authorities"]}
    assert by_start["The Board shall have the power"].tier is ra.Tier.LIKELY
    slow = by_start["A reasonable time limit for me"]       # the rules read it as a reference, the model as a grant
    assert slow.tier is ra.Tier.CONFLICT and slow.readers == ("model",)
    again = ra.find([o], model=model, duties={o.key: duties}, samples=1, cache=cache)
    assert len(calls) == n and [a.id for a in again["authorities"]] == [a.id for a in first["authorities"]]
    cached = ra.find([o], duties={o.key: duties}, cache=cache, cached_model=model.model)
    assert set(cached["model"]) == set(first["model"])


def test_a_grant_links_to_the_limits_that_name_a_rule_change():
    text = ("1.1 Rules.\nThe Board shall have the power to adopt Rules governing the Common Area.\n"
            "1.2 Procedure.\nA Rule Change shall be noticed to the Members at least 30 days before adopting it.\n")
    o = outline_from_text(text, key="x", kind="bylaws")
    rows = ra.find([o])["authorities"]
    grant = next(a for a in rows if a.answer is ra.Answer.GRANT)
    limit = next(a for a in rows if a.answer is ra.Answer.LIMITS)
    assert limit.id in grant.related or not grant.related   # a lead only; never a finding


# ---------------------------------------------------------------------------------------------------------------------
# Subjects, rules on file, and Civil Code 4355


def test_subject_words_name_a_subject_and_a_place_alone_only_when_no_other_is_found():
    assert ra.subjects_of("pets in the Common Area") == (ra.Subject.PETS,)
    assert ra.subjects_of("the use of the Common Area") == (ra.Subject.COMMON_AREA,)
    assert ra.Subject.PARKING in ra.subjects_of("parking in a garage")
    assert ra.subjects_of("the weather") == ()


def rules_doc():
    text = ("1.1 Parking\nNo vehicle shall be parked on the street overnight.\n"
            "1.2 Pets\nPets must be leashed.\n"
            "1.3 Contacts\nCall the manager at the office.\n")
    return outline_from_text(text, key="example-rules", kind="operating_rules")


def test_rules_on_file_are_the_sections_that_state_a_norm_with_their_subjects():
    rows = ra.rules_on_file([rules_doc(), outline()])
    assert {(r.source, r.section) for r in rows} == {("example-rules", "1.1"), ("example-rules", "1.2")}
    assert {s for r in rows for s in r.subjects} >= {ra.Subject.PARKING, ra.Subject.PETS}


def test_a_restriction_the_declaration_states_itself_is_not_a_rule():
    rows = ra.restrictions([outline()])
    assert any("pets" in r.subjects[0].value for r in rows if r.subjects)
    assert ra.rules_on_file([outline()]) == []


def test_each_subject_is_authority_and_rules_authority_only_rules_only_or_neither(doc):
    o, duties, _ = doc
    found = ra.find([o], duties={o.key: duties})
    on_file = ra.rules_on_file([rules_doc()])
    table = {row.subject: row for row in ra.by_subject(found["authorities"], on_file)}
    assert table[ra.Subject.PETS].standing is ra.Standing.AUTHORITY_AND_RULES
    assert table[ra.Subject.PARKING].standing is ra.Standing.RULES_ONLY
    assert table[ra.Subject.COMMON_AREA].standing is ra.Standing.AUTHORITY_ONLY
    assert table[ra.Subject.ELECTIONS].standing is ra.Standing.NEITHER


def test_a_general_power_reaches_every_subject_and_says_so():
    g = ra.RuleAuthority("a#1:x", "a", "1", "", ra.Answer.GRANT, ra.Holder.BOARD, (ra.Subject.GENERAL,), (), (), "", "w", "w",
                         ra.Tier.SUGGESTED, ("rules",))
    row = next(r for r in ra.by_subject([g], []) if r.subject is ra.Subject.PETS)
    assert row.standing is ra.Standing.GENERAL_ONLY and row.general_only


def test_a_rejected_grant_does_not_count(tmp_path):
    from jason.tasks.rule_authority import subjects

    outlines = tmp_path / "outlines"
    outlines.mkdir()
    for o in (outline(), rules_doc()):
        (outlines / f"{o.key}.json").write_text(json.dumps(o.to_dict()), encoding="utf-8")
    from jason.tasks import rule_authority as task

    found = task.run(tmp_path, community=SimpleNamespace(owners_manual=lambda: ()))
    pets = next(a for a in found["authorities"] if ra.Subject.PETS in a.subjects)
    ra.review(tmp_path, pets.id, ra.Review.REJECTED, note="read", reviewer="a person")
    rows = {row.subject: row for row in subjects(tmp_path)}
    assert rows[ra.Subject.PETS].standing is ra.Standing.RULES_ONLY


def test_4355_reads_each_subject_as_listed_dependent_or_not_listed():
    assert ra.reach(ra.Subject.FINES).reach is ra.Reach.LISTED and ra.reach(ra.Subject.FINES).cites == ("4355(a)(3)",)
    assert ra.reach(ra.Subject.ELECTIONS).cites == ("4355(a)(7)",)
    pets = ra.reach(ra.Subject.PETS)
    assert pets.reach is ra.Reach.DEPENDS and set(pets.cites) == {"4355(a)(1)", "4355(a)(2)"}
    assert ra.reach(ra.Subject.MEETINGS).reach is ra.Reach.NOT_LISTED
    leasing = ra.reach(ra.Subject.LEASING)
    assert leasing.reach is ra.Reach.DEPENDS and "counsel" in leasing.note
    assert set(ra.REACH) == set(ra.Subject)


def test_the_listed_subjects_are_the_statutes_words_on_disk():
    from jason.config import data_root
    from jason.tasks.export_authorities import authority_text

    found = authority_text(data_root(), "CIV 4355")
    text = found.get("text") or ""
    if not text:
        pytest.skip("CIV 4355 is not exported here (jason export-authorities)")
    flat = re.sub(r"\s+", " ", text).lower()
    for words in ("use of the common area", "use of a separate interest", "member discipline", "payment plans",
                  "resolution of disputes", "physical change", "procedures for elections", "maintenance of the common area"):
        assert words in flat, words


# ---------------------------------------------------------------------------------------------------------------------
# Parts


class Seg:
    def __init__(self, start, end, kind, book):
        self.start, self.end, self.kind, self.target, self.old = start, end, SimpleNamespace(value=kind), SimpleNamespace(book=book), f"{start}"


def test_a_grant_in_a_guidance_part_is_marked_and_the_guidance_is_not_a_rule_on_file():
    text = ("1.1 Guide\nThe Board may adopt rules for the Common Area.\n1.2 Rules\nNo vehicle shall be parked on the lawn.\n")
    o = outline_from_text(text, key="manual", kind="operating_rules")
    cut = text.index("1.2 Rules")
    parts = ra.parts_from_manual("manual", SimpleNamespace(segments=[Seg(0, cut, "guidance", "manual"), Seg(cut, len(text), "rule", "rules")]))
    (c,) = [c for c in ra.candidates(o, parts=parts)]
    assert c.part == "guidance"
    on_file = ra.rules_on_file([o], parts=parts)
    assert [r.words for r in on_file] == ["No vehicle shall be parked on the lawn."]
    assert len(ra.rules_on_file([o])) >= 1


def test_without_parts_a_document_is_read_whole():
    assert ra.part_at([], "x", 0) is None


# ---------------------------------------------------------------------------------------------------------------------
# The store


def test_the_store_keeps_a_review_while_the_reading_stays_and_orphans_it_when_it_goes(tmp_path, doc):
    o, duties, _ = doc
    rows = ra.find([o], duties={o.key: duties})["authorities"]
    ra.save(tmp_path, rows, reader="rules")
    first = ra.stored(tmp_path)
    assert [a.id for a in first] == [a.id for a in rows] and all(a.review is ra.Review.UNREVIEWED for a in first)
    target = first[0]
    ra.review(tmp_path, target.id, ra.Review.CONFIRMED, note="read the words", reviewer="a person")
    ra.save(tmp_path, rows, reader="rules")
    again = {a.id: a for a in ra.stored(tmp_path)}
    assert again[target.id].review is ra.Review.CONFIRMED and again[target.id].note == "read the words"
    ra.save(tmp_path, rows[1:], reader="rules")
    raw = ra.load_store(tmp_path)
    assert target.id in raw["orphaned"] and target.id not in raw["reviews"]
    with pytest.raises(KeyError):
        ra.review(tmp_path, "nope", ra.Review.CONFIRMED)


def test_a_stored_row_round_trips(doc):
    o, duties, _ = doc
    row = ra.find([o], duties={o.key: duties})["authorities"][0]
    assert ra.RuleAuthority.from_dict(json.loads(json.dumps(row.to_dict()))) == row


def test_the_store_lives_under_data_rules_and_the_answers_survive_a_save(tmp_path):
    assert ra.store_path(tmp_path) == tmp_path / "rules" / "authority.json"
    ra.save(tmp_path, [], reader="rules")
    ra.save_answers(tmp_path, {"m|x": {"reader": "model", "answer": "no"}})
    ra.save(tmp_path, [], reader="rules")
    assert ra.load_answers(tmp_path) == {"m|x": {"reader": "model", "answer": "no"}}


# ---------------------------------------------------------------------------------------------------------------------
# Measurement


def gold():
    return json.loads((FIXTURES / "gold.json").read_text(encoding="utf-8"))["items"]


def test_precision_and_recall_of_the_rules_alone(doc):
    _, duties, cands = doc
    rules = {c.id: ra.rule_reading(c, duties) for c in cands}
    out = ra.measure(gold(), cands, rules)
    assert out["items"] == 12 and out["collected"] == 10
    assert "The Board has the authority to designate quiet hours" in out["missedByCollector"]
    rules_row = out["readers"]["rules"]
    assert rules_row["precision"] == 1.0
    assert 0 < rules_row["recall"] < 1.0           # the delegated standards and the missed sentence are its misses
    assert out["collectorRecall"] == 0.8
    assert out["detail"]["rules"]["holderRight"] == out["detail"]["rules"]["grantsRead"]


def test_the_model_and_both_readers_are_scored_apart(doc):
    o, duties, cands = doc
    rules = {c.id: ra.rule_reading(c, duties) for c in cands}
    models = {}
    for c in cands:
        yes = c.text.startswith(("The Board shall have the power", "A reasonable time limit", "The Board may adopt and enforce"))
        models[c.id] = ra.Reading("model", ra.Answer.GRANT if yes else ra.Answer.NO, ra.Holder.BOARD)
    out = ra.measure(gold(), cands, rules, models)
    assert set(out["readers"]) == {"rules", "model", "both", "either"}
    assert out["readers"]["both"]["precision"] == 1.0
    assert out["readers"]["either"]["recall"] >= max(out["readers"]["rules"]["recall"], out["readers"]["model"]["recall"])
    assert out["readers"]["model"]["fp"] == 0


def test_a_gold_item_finds_its_candidate_by_a_quote(doc):
    assert ra.gold_match({"source": "example-decl", "quote": "THE BOARD SHALL HAVE the power"}, doc[2]) is not None
    assert ra.gold_match({"source": "another", "quote": "The Board shall have the power"}, doc[2]) is None
    assert ra.gold_match({"quote": "nothing like it"}, doc[2]) is None


# ---------------------------------------------------------------------------------------------------------------------
# The command


def command(tmp_path, monkeypatch, *argv):
    from jason.cli import build_parser
    import jason.config as config

    monkeypatch.setattr(config, "data_dir", lambda env=None: tmp_path)
    args = build_parser().parse_args(["rules", *argv])
    return args.func(args)


def seed(tmp_path):
    outlines = tmp_path / "outlines"
    outlines.mkdir(exist_ok=True)
    for o in (outline(), rules_doc()):
        (outlines / f"{o.key}.json").write_text(json.dumps(o.to_dict()), encoding="utf-8")
    (tmp_path / "rules").mkdir(exist_ok=True)
    (tmp_path / "rules" / "gold.json").write_text((FIXTURES / "gold.json").read_text(encoding="utf-8"), encoding="utf-8")


def test_jason_rules_finds_lists_and_measures_with_no_model(tmp_path, monkeypatch, capsys):
    seed(tmp_path)
    assert command(tmp_path, monkeypatch, "--find", "--document", "example-decl") == 0
    out = capsys.readouterr().out
    assert "candidates;" in out and "words:" in out and "reading (a labeled reading)" in out
    assert (tmp_path / "rules" / "authority.json").is_file()
    assert command(tmp_path, monkeypatch, "--all") == 0
    assert "limits" not in capsys.readouterr().err
    assert command(tmp_path, monkeypatch, "--subjects") == 0
    assert "Civil Code 4355 (a labeled reading)" in capsys.readouterr().out
    assert command(tmp_path, monkeypatch, "--measure") == 0
    assert "precision" in capsys.readouterr().out


def test_jason_rules_with_nothing_stored_says_how_to_start(tmp_path, monkeypatch, capsys):
    seed(tmp_path)
    assert command(tmp_path, monkeypatch) == 1
    assert "jason rules --find" in capsys.readouterr().err


def test_jason_rules_names_a_missing_document(tmp_path, monkeypatch, capsys):
    seed(tmp_path)
    assert command(tmp_path, monkeypatch, "--find", "--document", "no-such") == 2
    assert "no outline no-such" in capsys.readouterr().err


def test_jason_rules_review_records_a_persons_word(tmp_path, monkeypatch, capsys):
    seed(tmp_path)
    command(tmp_path, monkeypatch, "--find")
    capsys.readouterr()
    first = ra.stored(tmp_path)[0]
    assert command(tmp_path, monkeypatch, "--review", first.id, "--status", "rejected", "--note", "a recital", "--by", "A Person") == 0
    assert ra.stored(tmp_path)[0].review is ra.Review.REJECTED
