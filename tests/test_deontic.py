import json

from jason.community.deontic import (
    Bearer, DeadlineRelation, DocumentDuty, DutyKind, NORMS, ReviewStatus, find_bearer, find_deadline, find_recurrence,
    read_outline, read_passage, sentences,
)
from jason.community.duty_model import DutyModel, merge_review, read_prompt, review_prompt, to_duties
from jason.community.outlines import DocumentOutline, Section
from jason.tasks import document_duties as dd


def _norms(text, **kw):
    return [d for d in read_passage(text, **kw)[0] if d.kind in NORMS]


def _one(text):
    found = _norms(text)
    assert len(found) == 1, [(d.kind, d.marker, d.quote) for d in found]
    return found[0]


def test_sentences_split_at_full_stops_but_not_after_abbreviations():
    text = "The Board shall act under Cal. Civ. Code Sec. 4900. Each Owner shall pay.\nNo Owner shall smoke."
    got = [text[s:e] for s, e in sentences(text)]
    assert got == ["The Board shall act under Cal. Civ. Code Sec. 4900.", "Each Owner shall pay.", "No Owner shall smoke."]


def test_the_kinds_of_norm_from_the_drafting_forms():
    assert _one("The Board shall send written notice to the Owner.").kind is DutyKind.DUTY
    assert _one("No Owner shall keep a boat in the Common Area.").kind is DutyKind.PROHIBITION
    assert _one("An Owner shall not paint the exterior.").kind is DutyKind.PROHIBITION
    assert _one("The Board may adopt rules for the pool.").kind is DutyKind.PERMISSION
    assert _one("The Board shall have the power to levy fines.").kind is DutyKind.PERMISSION
    assert _one("Each Member shall be entitled to one copy of the minutes.").kind is DutyKind.RIGHT
    assert _one("Vehicles parked in a fire lane shall be subject to towing.").kind is DutyKind.CONDITION
    assert _one("The Owner is responsible to provide a copy of the rules to the tenant.").kind is DutyKind.DUTY
    assert _one("Smoking is prohibited in the Common Area.").kind is DutyKind.PROHIBITION
    assert _one("The Board shall be authorized to grant variances.").kind is DutyKind.PERMISSION
    assert _one("Any installment not paid within fifteen days shall be delinquent.").kind is DutyKind.CONDITION
    assert _one("Proxies shall otherwise be prohibited.").kind is DutyKind.PROHIBITION
    assert _norms("The term shall not include sedans.") == [] and _norms("Officers shall hold office for one year.") == []
    between = find_deadline("Not less than 30 days and not more than 90 days prior to the end of the fiscal year")
    assert between.relation is DeadlineRelation.BETWEEN and between.amount == 30


def test_definitions_and_statements_of_status_are_not_norms():
    for text in ('"Member" shall mean an Owner of a Lot.',
                 "Each Owner shall be a Member of the Association.",
                 "Membership shall pass automatically to the transferee.",
                 "The provisions of this Declaration shall be deemed independent and severable.",
                 "The Association is not responsible for vehicles parked on the property.",
                 "Each Owner shall have an undivided interest in the Common Area."):
        assert _norms(text) == [], text


def test_a_modal_in_a_relative_or_conditional_clause_is_not_a_norm():
    found = _norms("Unless the Board shall designate otherwise, assessments shall be paid monthly.")
    assert [(d.kind, d.marker) for d in found] == [(DutyKind.DUTY, "shall")]
    assert _norms("The office shall be located at such place as the Board may establish.") == []
    assert _norms("Residents may be exposed to construction noise.") == []
    assert _norms("Foreclosure may occur either by a court action or without one.") == []
    assert _norms("WHEREAS, the Board may invest reserve funds;") == []


def test_a_passive_duty_names_its_agent_and_a_recipient_is_not_the_bearer():
    given = _one("Members shall be given notice of each meeting at least four days before the meeting.")
    assert given.kind is DutyKind.DUTY and given.bearer is Bearer.UNSTATED and given.passive and given.notice
    by = _one("Notice shall be mailed by the Secretary to each Owner.")
    assert by.bearer is Bearer.OFFICER and by.passive
    paid = _one("Regular Assessments shall be paid in twelve equal monthly installments.")
    assert paid.bearer is Bearer.OWNER and paid.recurrence_months == 1


def test_the_subject_after_a_leading_clause_and_a_pronoun():
    found = _norms("If the Owner fails to appear, the Board must consider the evidence, and it must decide.")
    assert [d.bearer for d in found] == [Bearer.BOARD, Bearer.BOARD]
    neg = _one("Except as provided in Section 4.3, no Lot, or any part of it, shall be used for business.")
    assert neg.kind is DutyKind.PROHIBITION and neg.marker == "no ... shall"


def test_deadlines_recurrences_triggers_and_conditions():
    d = _one("Within thirty (30) days after receipt of an application, the Board shall approve or deny it, unless the "
             "applicant withdraws it.")
    assert d.deadline.relation is DeadlineRelation.WITHIN and d.deadline.amount == 30 and d.deadline.unit == "days"
    assert d.conditions and d.conditions[0].startswith("unless")
    before = find_deadline("at least ten days before the hearing")
    assert before.relation is DeadlineRelation.BEFORE and before.amount == 10 and before.event == "the hearing"
    assert find_recurrence("at least once every three years") == ("at least once every three years", 36)
    assert find_recurrence("shall review the study annually")[1] == 12
    assert find_recurrence("on at least a quarterly basis")[1] == 3
    t = _one("Upon the sale of a Lot, the seller shall deliver the documents to the buyer.")
    assert t.trigger.startswith("Upon the sale of a Lot")


def test_a_lead_in_passes_its_kind_and_bearer_to_the_list_items_under_it():
    text = ("6.4 Duties of the Inspector.\nThe Inspector of Elections shall:\n"
            "(a) Deliver the ballots to the members at least thirty (30) days before the election;\n"
            "(b) Count the ballots in public.\n")
    outline = DocumentOutline(key="rules", title="Election Rules", text=text)
    a, b = text.index("(a)"), text.index("(b)")
    outline.sections = [Section("6.4", "Duties of the Inspector.", 1, 0, len(text)),
                        Section("6.4(a)", "", 2, a, b, parent="6.4"), Section("6.4(b)", "", 2, b, len(text), parent="6.4")]
    found = [d for d in read_outline(outline) if d.kind in NORMS]
    items = [d for d in found if d.inherited]
    assert [d.section for d in items] == ["6.4(a)", "6.4(b)"]
    assert all(d.kind is DutyKind.DUTY and d.bearer is Bearer.INSPECTOR for d in items)
    assert items[0].deadline.amount == 30 and items[0].notice


def test_lines_under_a_colon_inherit_but_a_table_does_not():
    text = ("If the owner fails to repair it, the Association may:\nPerform the repairs.\nCharge the owner for the cost.\n"
            "The Board may impose the following fines:\nFirst violation\n$25 or warning\n")
    found = _norms(text)
    assert [(d.kind, d.bearer, d.inherited) for d in found if d.inherited] == [
        (DutyKind.PERMISSION, Bearer.ASSOCIATION, True), (DutyKind.PERMISSION, Bearer.ASSOCIATION, True)]


def test_find_bearer_takes_the_first_party_named():
    assert find_bearer("The Board of Directors")[0] is Bearer.BOARD
    assert find_bearer("The Inspector of Elections")[0] is Bearer.INSPECTOR
    assert find_bearer("Membership in the Association")[0] is Bearer.ASSOCIATION
    assert find_bearer("the notice")[0] is Bearer.UNSTATED


def test_a_reading_round_trips_and_its_id_is_stable():
    d = _one("Within 15 days after the hearing, the Board shall mail its decision to the Owner.")
    again = DocumentDuty.from_dict(json.loads(json.dumps(d.to_dict())))
    assert again == d and again.id == d.id and again.id.startswith("#:")


def _fake_outline():
    text = ("1.1 Notice.\nThe Board shall mail notice of each meeting to the Members at least ten days before the meeting.\n"
            "1.2 Pets.\nNo Owner shall keep more than two pets.\n")
    outline = DocumentOutline(key="sample-rules", title="Sample Rules", kind="operating_rules", text=text)
    b = text.index("1.2")
    outline.sections = [Section("1.1", "Notice.", 1, 0, b), Section("1.2", "Pets.", 1, b, len(text))]
    return outline


def test_the_store_keeps_a_review_across_rereads_and_orphans_one_whose_words_changed(tmp_path):
    outline = _fake_outline()
    duties = dd.read_document(outline)
    dd.save(tmp_path, outline.key, duties)
    notice = next(d for d in duties if d.section == "1.1")
    dd.review(tmp_path, outline.key, notice.id, ReviewStatus.CORRECTED, note="the manager mails it", bearer=Bearer.MANAGER,
              tracked_by="board calendar: meeting notice")
    dd.save(tmp_path, outline.key, dd.read_document(outline))
    back = {d.id: d for d in dd.stored(tmp_path, outline.key)}
    assert back[notice.id].review is ReviewStatus.CORRECTED and back[notice.id].bearer is Bearer.MANAGER
    assert dd.tracking(back[notice.id]) == "board calendar: meeting notice"
    outline.text = outline.text.replace("ten days", "fifteen days")
    dd.save(tmp_path, outline.key, dd.read_document(outline))
    raw = dd.load_store(tmp_path, outline.key)
    assert notice.id in raw["orphaned"] and not raw["reviews"]


def test_tracking_matches_a_recurring_deadline_by_its_words():
    class Row:
        name = "Annual budget report and policy statement"

    d = _one("The Board shall distribute the annual budget report to the Members annually.")
    assert dd.tracking(d, [Row()]) == "obligation: Annual budget report and policy statement"
    other = _one("The Board shall review the reconciliation of the operating account quarterly.")
    assert dd.tracking(other, [Row()]) == ""
    assert [t for _, t in dd.untracked([other], [Row()])] == [""]


def test_the_model_reading_keeps_only_quotes_in_the_text_and_known_kinds():
    text = "The Board shall mail its decision to the Owner within fifteen days. Each Owner shall be a Member."
    raw = json.dumps({"norms": [
        {"quote": "The Board shall mail its decision", "kind": "duty", "bearer": "board", "action": "mail its decision",
         "trigger": "", "deadline": "within fifteen days", "recurrence": "", "notice": True},
        {"quote": "The Board must send its ruling", "kind": "duty", "bearer": "board", "action": "", "trigger": "",
         "deadline": "", "recurrence": "", "notice": True},
        {"quote": "Each Owner shall be a Member", "kind": "definition", "bearer": "owner", "action": "", "trigger": "",
         "deadline": "", "recurrence": "", "notice": False}]})
    kept, dropped = to_duties(raw, text, source="x", section="1", base=100)
    assert len(kept) == 1 and kept[0].marker_at == 100 + text.index("shall") and kept[0].deadline.amount == 15
    assert kept[0].method == "model" and sorted(d["why"] for d in dropped) == ["its quote is not in the section", "not a norm"]
    assert to_duties("not json", text, source="x", section="1", base=0)[0] == []


def test_the_hybrid_takes_the_models_verdicts_on_the_candidates():
    text = "Members shall be given notice of each meeting. The term shall mean the period."
    cands = _norms(text, source="x", section="1")
    assert len(cands) == 1
    raw = json.dumps({"candidates": [{"n": 1, "norm": True, "kind": "duty", "bearer": "board", "deadline": "",
                                      "recurrence": "", "notice": True}],
                      "missed": [{"quote": "The term shall mean the period", "kind": "condition", "bearer": "unstated",
                                  "action": "", "trigger": "", "deadline": "", "recurrence": "", "notice": False}]})
    full, _ = merge_review(raw, cands, text, source="x", section="1", base=0)
    assert full[0].bearer is Bearer.BOARD and full[0].method == "hybrid" and len(full) == 2
    fill, _ = merge_review(raw, cands, text, source="x", section="1", base=0, fill_only=True)
    assert [(d.kind, d.bearer) for d in fill] == [(DutyKind.DUTY, Bearer.BOARD)]
    dropped = json.dumps({"candidates": [{"n": 1, "norm": False, "kind": "none", "bearer": "unstated", "deadline": "",
                                          "recurrence": "", "notice": False}], "missed": []})
    assert merge_review(dropped, cands, text, source="x", section="1", base=0)[0] == []


def test_the_prompts_name_kinds_not_facts_and_the_model_asks_only_locally():
    import re

    from jason.community.duty_model import EXAMPLES, METHOD

    p = read_prompt("The Board shall act.", source="x", title="Sample Rules", section="2.1", lead="The Board shall:")
    assert 'introduced by: "The Board shall:"' in p and "Kinds:" in p and "invented" in p
    assert not re.search(r"\bSection\s+\d|\d+\.\d+|\$\d", METHOD + EXAMPLES)       # no section number, no figure
    cands = _norms("The Board shall act.")
    assert "[[shall]]" in review_prompt("The Board shall act.", cands)
    seen = {}

    def fetch(url, payload):
        seen.update(payload)
        return {"message": {"content": '{"norms": []}'}}

    model = DutyModel(fetch=fetch, model="test-model")
    assert model.read("The Board shall act.") == '{"norms": []}' and seen["think"] is False and seen["format"]["required"] == ["norms"]
    try:
        DutyModel(base_url="http://example.com:11434")
    except ValueError:
        pass
    else:
        raise AssertionError("a remote Ollama must be refused")


def test_evaluate_scores_kinds_fields_and_optional_items():
    text = "The Board shall mail notice. Owners may keep pets. Each Owner shall be a Member."
    gold = [{"id": "x@0", "items": [
        {"quote": "The Board shall mail notice", "kind": "duty", "bearer": ["board"], "notice": True},
        {"quote": "Owners may keep pets", "kind": "permission", "bearer": ["owner"]},
        {"quote": "Each Owner shall be a Member", "kind": "condition", "bearer": ["owner"], "optional": True}]}]
    found = {"x@0": _norms(text, source="x", section="", base=0)}
    result = dd.evaluate(gold, found, {"x@0": text})
    assert (result["tp"], result["fp"], result["fn"]) == (2, 0, 0) and result["fields"]["notice"] == "2/2"
