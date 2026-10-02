import json

import pytest

from jason.community.content import ModelUnavailable
from jason.community.outlines import DocumentOutline, Section
from jason.community.reference_model import (
    ReferenceModel, build_prompt, catalog, dedupe, find_quote, normalize_target, parse_answer, passages, verify,
)
from jason.community.references import Reference, RefRelation, TargetKind
from jason.tasks import outlines as outline_task
from jason.tasks import reference_review


RULES_TEXT = ("B-1. REGISTRATION\n"
              "Each Owner shall comply with the rules adopted by the Board and with the Association’s Enforcement Policy.\n"
              "B-2. PARKING\n"
              "Parking is governed by Section 6.5(b) of the Declaration and by the Davis-Stirling Act, as provided in the "
              "Declaration.\n")


def _outlines():
    rules = DocumentOutline(key="rules", title="Owner's Manual and Rules", kind="operating_rules", text=RULES_TEXT,
                            aliases=["Owner's Manual", "Rules and Regulations"])
    b2 = RULES_TEXT.index("B-2.")
    rules.sections = [Section("B-1", "B-1. REGISTRATION", 1, 0, b2), Section("B-2", "B-2. PARKING", 1, b2, len(RULES_TEXT))]
    ccrs = DocumentOutline(key="ccrs", title="Restated Declaration", kind="declaration", text="6.5 Parking.\n(b) Guests.\n",
                           aliases=["Declaration", "CC&Rs"])
    ccrs.sections = [Section("6.5", "Parking.", 2, 0, 13), Section("6.5(b)", "Guests.", 3, 13, 24, parent="6.5")]
    enforcement = DocumentOutline(key="enforcement-policy", title="Enforcement Policy", kind="policy", text="Fines.\n",
                                  aliases=["Enforcement Policy", "Fine Schedule"])
    return [rules, ccrs, enforcement]


def _answer(*refs):
    return {"message": {"content": json.dumps({"references": [dict(zip(("kind", "target", "quote", "relation"), r)) for r in refs]})}}


def test_a_passage_is_a_sections_own_words():
    rules = _outlines()[0]
    ps = passages(rules, min_chars=10)
    assert [p.section for p in ps] == ["B-1", "B-2"]
    assert ps[1].text.startswith("B-2. PARKING") and "Enforcement" not in ps[1].text
    whole = DocumentOutline(key="res", title="Resolution", text="line one of a long resolution\n" * 20)
    pieces = passages(whole, max_chars=200, min_chars=10)
    assert len(pieces) > 1 and all(p.section == "" and len(p.text) <= 200 for p in pieces)
    assert "".join(p.text for p in pieces) == whole.text


def test_the_prompt_lists_the_documents_with_their_aliases_and_the_naming_rules():
    outlines = _outlines()
    known = catalog(outlines)
    prompt = build_prompt(passages(outlines[0], min_chars=10)[0], known)
    assert "- enforcement-policy: Enforcement Policy (policy); also called: Enforcement Policy, Fine Schedule" in prompt
    assert "also called: Declaration, CC&Rs" in prompt and "bylaws#7.2" in prompt and "CIV 4000" in prompt
    assert prompt.rstrip().endswith("the Association’s Enforcement Policy.")


def test_quotes_are_verified_against_the_section_folded():
    text = "Each Owner shall comply with  the rules\nadopted by the Board and the Association’s “Enforcement Policy”."
    assert find_quote(text, "the rules adopted by the board") is not None
    start, end = find_quote(text, "the Association's \"Enforcement Policy\"")
    # Quotation marks the model wraps around its quote are not held against it.
    assert text[start:end] == "the Association’s “Enforcement Policy"
    assert find_quote(text, "the Architectural Guidelines") is None
    assert find_quote(text, "the") is None                      # too short to prove anything


def test_verify_keeps_quoted_references_maps_aliases_and_drops_the_rest():
    outlines = _outlines()
    known = catalog(outlines)
    b1, b2 = passages(outlines[0], min_chars=10)
    proposals, bad, error = parse_answer(_answer(
        ("document", "the Association's Enforcement Policy", "the Association's Enforcement Policy", "is subject to"),
        ("document", "Rules and Regulations", "the rules adopted by the Board", "is subject to"),
        ("document", "Architectural Guidelines", "the Architectural Guidelines", "cites"),
    )["message"]["content"])
    assert not bad and not error
    kept, dropped = verify(b1, proposals, outlines[0], known)
    # "Rules and Regulations" is this document itself; the guidelines are not in the text.
    assert [(m.reference.target, m.reference.relation, m.reference.method) for m in kept] == [
        ("enforcement-policy", RefRelation.SUBJECT_TO, "model")]
    assert kept[0].said == "the Association’s Enforcement Policy" and kept[0].reference.source_section == "B-1"
    assert sorted(d["reason"] for d in dropped) == ["quote not in the section", "the document itself"]
    proposals, _, _ = parse_answer(_answer(
        ("statute", "Davis-Stirling Act", "the Davis-Stirling Act", "acts under"),
        ("section", "CC&Rs#6.5 (b)", "Section 6.5(b) of the Declaration", "acts under"),
        ("document", "Declaration", "as provided in the Declaration", "acts under"),
        ("document", "City's conditions of approval", "as provided in the Declaration", "cites"),
    )["message"]["content"])
    kept, dropped = verify(b2, proposals, outlines[0], known)
    assert [m.reference.target for m in kept] == ["CIV 4000", "ccrs#6.5(b)", "ccrs", "named:city's conditions of approval"]
    assert not dropped


def test_a_law_named_only_in_general_is_dropped_and_a_list_of_subsections_is_split():
    outline = DocumentOutline(key="collection-policy", title="Collection Policy",
                              text="Late charges are as required by law (CC&Rs §6.12(d),(f)) under Civil Code 5650.")
    outline.sections = [Section("6", "Late", 1, 0, len(outline.text))]
    outline.aliases = ["Collection Policy"]
    ccrs = DocumentOutline(key="ccrs", title="Declaration")
    ccrs.aliases = ["CC&Rs", "Declaration"]
    known = catalog([outline, ccrs])
    passage = passages(outline, min_chars=10)[0]
    proposals, _, _ = parse_answer(_answer(
        ("statute", "CIV 4000", "as required by law", "is required by"),
        ("section", "ccrs#6.12(d),(f)", "CC&Rs §6.12(d),(f)", "acts under"),
        ("statute", "CIV 5650", "Civil Code 5650", "acts under"),
    )["message"]["content"])
    kept, dropped = verify(passage, proposals, outline, known)
    assert [m.reference.target for m in kept] == ["ccrs#6.12(d)", "ccrs#6.12(f)", "CIV 5650"]
    assert [d["reason"] for d in dropped] == ["a law named only in general"]
    proposals, _, _ = parse_answer(_answer(
        ("section", "#5650", "Civil Code 5650", "cites"),          # a four-digit "section" is the Civil Code
        ("section", "#a)", "Late charges", "cites"),               # no section number at all
    )["message"]["content"])
    kept, dropped = verify(passage, proposals, outline, known)
    assert [(m.reference.kind, m.reference.target) for m in kept] == [(TargetKind.STATUTE, "CIV 5650")]
    assert [d["reason"] for d in dropped] == ["not a section number"]


def test_targets_follow_the_grammars_conventions():
    rules, *_ = _outlines()
    known = catalog(_outlines())
    assert normalize_target(TargetKind.STATUTE, "Civil Code Section 5850(c)", rules, known) == ("CIV 5850(c)", False)
    assert normalize_target(TargetKind.STATUTE, "civ 1363", rules, known) == ("CIV 1363", True)
    assert normalize_target(TargetKind.STATUTE, "10 CCR 2792.23", rules, known) == ("10 CCR 2792.23", False)
    assert normalize_target(TargetKind.SECTION, "#B-1", rules, known)[0] == "rules#B-1"
    assert normalize_target(TargetKind.SECTION, "Section 6.5(b) of the Declaration", rules, known)[0] == "ccrs#6.5(b)"
    assert normalize_target(TargetKind.RESOLUTION, "resolution:20230130-1", rules, known)[0] == "resolution:20230130-1"
    assert normalize_target(TargetKind.DOCUMENT, "fine schedule", rules, known)[0] == "enforcement-policy"


def test_a_reference_the_grammar_already_found_in_that_section_is_not_new():
    outlines = _outlines()
    known = catalog(outlines)
    b2 = passages(outlines[0], min_chars=10)[1]
    proposals, _, _ = parse_answer(_answer(
        ("section", "ccrs#6.5", "Section 6.5(b) of the Declaration", "acts under"),
        ("document", "Declaration", "as provided in the Declaration", "acts under"),
        ("statute", "Davis-Stirling Act", "the Davis-Stirling Act", "acts under"),
    )["message"]["content"])
    kept, _ = verify(b2, proposals, outlines[0], known)
    grammar = outline_task.references(outlines)
    assert any(r.target == "ccrs#6.5(b)" and r.source_section == "B-2" for r in grammar)
    new, old = dedupe(kept, grammar)
    assert [m.reference.target for m in new] == ["CIV 4000"]
    assert sorted(m.reference.target for m in old) == ["ccrs", "ccrs#6.5"]
    # The same target in another section is new there.
    other = Reference("rules", "B-1", TargetKind.SECTION, "ccrs#6.5(b)", RefRelation.CITES, "", 0)
    assert dedupe(kept[:1], [other])[0] == kept[:1]


def test_a_malformed_answer_is_counted_not_trusted():
    assert parse_answer("this is not json")[2] == "the model did not answer in JSON"
    assert parse_answer(json.dumps({"refs": []}))[2]
    proposals, bad, error = parse_answer(json.dumps({"references": [
        {"kind": "document", "target": "Declaration", "quote": ""}, "a string", {"kind": "document", "target": "Declaration",
                                                                                  "quote": "the Declaration", "relation": 7}]}))
    assert bad == 2 and not error and proposals[0]["relation"] == "7"


def test_model_references_round_trip_and_the_grammars_rows_do_not_change():
    ref = Reference("rules", "B-2", TargetKind.STATUTE, "CIV 4000", RefRelation.PURSUANT_TO, "q", 5, method="model")
    assert Reference.from_dict(ref.to_dict()) == ref and ref.to_dict()["method"] == "model"
    plain = Reference("rules", "B-2", TargetKind.STATUTE, "CIV 4000", RefRelation.CITES, "q", 5)
    assert "method" not in plain.to_dict() and Reference.from_dict(plain.to_dict()) == plain


def test_the_reader_asks_only_a_local_ollama_with_the_schema():
    with pytest.raises(ValueError):
        ReferenceModel(base_url="https://example.com")
    calls = []

    def fetch(url, payload):
        calls.append((url, payload))
        return _answer()

    outlines = _outlines()
    raw = ReferenceModel(fetch=fetch).read(passages(outlines[0], min_chars=10)[0], catalog(outlines))
    assert json.loads(raw) == {"references": []}
    url, payload = calls[0]
    assert url == "http://localhost:11434/api/chat" and payload["think"] is False and payload["options"]["temperature"] == 0
    assert payload["format"]["required"] == ["references"] and "Fine Schedule" in payload["messages"][0]["content"]


def test_the_task_writes_what_it_added_and_skips_what_it_read(tmp_path):
    outlines = _outlines()

    def fetch(url, payload):
        prompt = payload["messages"][0]["content"]
        if "B-2. PARKING" in prompt.split("Text:\n")[-1]:
            return _answer(("statute", "Davis-Stirling Act", "the Davis-Stirling Act", "acts under"),
                           ("document", "Architectural Guidelines", "the Architectural Guidelines", "cites"))
        return {"message": {"content": "not json"}}

    result = reference_review.run(tmp_path, picks=["rules"], reader=ReferenceModel(fetch=fetch), outlines=outlines, log=lambda _: None)
    assert [e["section"] for e in result["read"]] == ["B-1", "B-2"]
    assert [(r["target"], r["status"], r["method"], r["said"]) for r in result["added"]] == [
        ("CIV 4000", "law not on disk", "model", "the Davis-Stirling Act")]
    assert sorted(d["reason"] for d in result["dropped"]) == ["quote not in the section", "the model did not answer in JSON"]
    stored = json.loads(reference_review.store_path(tmp_path).read_text(encoding="utf-8"))
    assert len(stored["references"]) == 1 and len(stored["passages"]) == 2
    # The store sits in a subfolder, where the outline loader does not read it as an outline.
    assert reference_review.store_path(tmp_path).parent.name == "model"
    again = reference_review.run(tmp_path, picks=["rules#B-2"], reader=ReferenceModel(fetch=fetch), outlines=outlines, log=lambda _: None)
    assert again["chosen"] == 0
    again = reference_review.run(tmp_path, picks=["rules#B-2"], again=True, reader=ReferenceModel(fetch=fetch), outlines=outlines,
                                 log=lambda _: None)
    assert [e["section"] for e in again["read"]] == ["B-2"]
    stored = json.loads(reference_review.store_path(tmp_path).read_text(encoding="utf-8"))
    assert len(stored["references"]) == 1                     # re-read, not doubled
    with pytest.raises(ValueError):
        reference_review.run(tmp_path, picks=["bylaws"], reader=ReferenceModel(fetch=fetch), outlines=outlines)


def test_the_task_fails_fast_when_the_model_cannot_run(tmp_path):
    class Down(ReferenceModel):
        def preflight(self):
            raise ModelUnavailable("Ollama at http://localhost:11434 is not answering")

        def read(self, passage, catalog):
            raise AssertionError("never asked")

    with pytest.raises(ModelUnavailable):
        reference_review.run(tmp_path, reader=Down(), outlines=_outlines(), log=lambda _: None)
    assert not reference_review.store_path(tmp_path).is_file()
