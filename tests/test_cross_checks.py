"""Cross-checks between agendas and minutes: amounts, prior minutes, insurance renewals, stale items. Each is a lead."""

from __future__ import annotations

import json
from pathlib import Path

from jason.tasks import cross_checks as cc


def _write(tmp: Path, rel: str, data) -> None:
    path = tmp / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _item(item, notes=(), related=(), expects=("proposal", "invoice"), subitem=""):
    return {"item": item, "subitem": subitem, "expects": list(expects), "notes": list(notes), "related": list(related), "refersTo": []}


def _rel(ref, name, kind=None, relation="linked", where="Drive"):
    return {"relation": relation, "where": where, "ref": ref, "name": name, "path": f"My Drive/{name}", "nameKind": kind}


def _minutes(rid, day, actions=(), items=(), prior_approved=None):
    return {"id": rid, "name": f"Minutes of {day}.pdf", "kind": "minutes", "period": day, "hasText": True,
            "fields": {"meeting_date": day, "actions": list(actions), "items": list(items), "prior_minutes_approved": prior_approved}}


def _action(text, amount=None, outcome="approved"):
    return {"text": text, "outcome": outcome, "amount": amount}


def _texts(by_ref: dict[str, str]):
    return lambda doc: (by_ref.get(doc.get("ref") or "", ""), "test text" if doc.get("ref") in by_ref else "")


class _Kind:
    def __init__(self, value):
        self.value = value


class _Community:
    """Names a file a policy by its name, like the specification's rules; no policies of its own."""

    def classify_document(self, name, path=""):
        return _Kind("insurance_policy") if name.upper().startswith("FLOOD POLICY") else None

    def insurance(self):
        raise LookupError("no catalog in the test")


# --- amounts ----------------------------------------------------------------------------------------------------------

def test_document_totals_prefer_a_grand_total_and_read_the_next_line() -> None:
    text = "Line item $100.00\nSubtotal $900.00\nTOTAL\n$9,968.00\nGrand Total: $10,468.00\nDeposit $996.80"
    totals = cc.document_totals(text)
    assert totals[0]["amount"] == 1_046_800 and totals[0]["rank"] == 0
    assert 996_800 in [t["amount"] for t in totals]
    assert 90_000 not in [t["amount"] for t in totals]                  # a subtotal is not a total
    assert cc.document_totals("losses totaling $250,000 or more") == []


def test_cents_reads_dollars_and_cents() -> None:
    assert cc.cents("approved $1,850 and $29,137.95; $12") == [185_000, 2_913_795, 1_200]


def test_amount_matches_differs_and_approved_without_a_linked_document() -> None:
    agenda = {"date": "2026-03-19", "items": [_item("Proposals", ["[Proposal 750977-1.pdf]"], [
        _rel("a", "Proposal 750977-1.pdf", "proposal"),
        _rel("b", "Proposal 750977-1 (2) - signed.pdf", "proposal", relation="named", where="Gmail"),
        _rel("c", "Gutter Cleaning.pdf", "proposal"),
    ])]}
    decisions = cc.decisions_of(_minutes("m1", "2026-03-19", [
        _action("The board approved repairs to the roof leak at a cost of $2,584.", 258_400),
        _action("The board approved replacing a street light ballast, not exceeding $500.", 50_000),
    ]))
    texts = _texts({"a": "Proposal\nTOTAL $4,216.00", "b": "Proposal\nTOTAL $2,584.00"})
    rows = {(r["document"] or {}).get("name", "none"): r for r in cc.check_amounts(agenda, decisions, texts, {})}
    assert rows["Proposal 750977-1 (2) - signed.pdf"]["outcome"] == cc.AmountOutcome.MATCHES.value
    # The original's total is not what was approved; its signed copy's is: a revised proposal, for a person to look at.
    original = rows["Proposal 750977-1.pdf"]
    assert original["outcome"] == cc.AmountOutcome.DIFFERS.value
    assert original["documentAmount"] == 421_600 and original["approvedAmounts"] == [258_400]
    assert rows["Gutter Cleaning.pdf"]["outcome"] == cc.AmountOutcome.NO_DECISION.value
    assert rows["none"]["outcome"] == cc.AmountOutcome.WITHOUT_DOC.value and rows["none"]["approvedAmounts"] == [50_000]


def test_a_minutes_item_that_attaches_the_document_decides_it_and_a_fine_is_not_spending() -> None:
    agenda = {"date": "2025-02-18", "items": [_item("Review Proposals", [], [_rel("e", "E&R Landscaping Contract.pdf", "contract")])]}
    reading = _minutes("m2", "2025-02-18", [_action("The board imposed a $40 fine on the owner.", 4_000)], [
        {"title": "Review Proposals", "notes": "", "attachments": [], "subitems": [
            {"title": "E&R Landscaping Contract", "notes": "The board approved the new landscape contract.",
             "attachments": ["E&R Landscaping Contract.pdf"], "subitems": []}]}])
    rows = cc.check_amounts(agenda, cc.decisions_of(reading), _texts({}), {})
    assert [r["outcome"] for r in rows] == [cc.AmountOutcome.DECIDED.value]
    assert "the minutes item attaches it" in rows[0]["decisions"][0]["because"]


def test_a_common_word_alone_does_not_match() -> None:
    agenda = {"date": "2025-04-15", "items": [_item("Review Proposals", [], [_rel("r", "Whimsical Lane roof repair bid.pdf", "proposal")])]}
    decisions = cc.decisions_of(_minutes("m3", "2025-04-15", [_action("The board agreed to approve the garage repairs.", 241_800)]))
    rows = cc.check_amounts(agenda, decisions, _texts({"r": "TOTAL ESTIMATED COST: $1,138.00"}), {})
    assert rows[0]["outcome"] == cc.AmountOutcome.NO_DECISION.value


def test_model_amounts_count_only_when_grounded() -> None:
    reading = _minutes("m4", "2025-12-16")
    grounded = {"amounts_approved": {"model": ["$9,968 for structural repairs"], "verdict": "model only"}}
    ungrounded = {"amounts_approved": {"model": ["$9,968 for structural repairs"], "verdict": "ungrounded"}}
    assert [d.amounts for d in cc.decisions_of(reading, grounded)] == [[996_800]]
    assert cc.decisions_of(reading, ungrounded) == []


# --- prior minutes ----------------------------------------------------------------------------------------------------

def _catalog(*days):
    return {d: {"date": d, "records": [{"kind": "minutes", "where": "Drive", "name": f"Minutes of {d}"}]} for d in days}


def test_an_agenda_link_where_minutes_belong_is_reported() -> None:
    agendas = [{"date": "2025-06-17", "titles": ["Agenda for 6/17/25"], "items": [
        _item("Approval of minutes of previous meeting", ["See: [Minutes of 5/20/25]"],
              [_rel("x", "Agenda for 5/20/25", "agenda")], expects=["minutes"])]}]
    readings = {"2025-06-17": [_minutes("m5", "2025-06-17")]}
    rows = cc.check_prior_minutes(agendas, readings, {}, _catalog("2025-05-20"))
    issues = [i["issue"] for i in rows[0]["issues"]]
    assert rows[0]["names"] == ["2025-05-20"]
    assert cc.MinutesIssue.LINKS_AGENDA.value in issues
    assert cc.MinutesIssue.NOT_RECORDED.value in issues
    assert cc.MinutesIssue.NOT_HELD.value not in issues


def test_minutes_listed_twice_and_minutes_never_listed() -> None:
    def approval(day, minutes_of, label):
        return {"date": day, "titles": [f"Agenda for {day}"], "items": [
            _item("Approval of minutes of previous meeting(s)", [f"See: [{label}]"],
                  [_rel(minutes_of, label, "minutes")], expects=["minutes"])]}

    agendas = [approval("2026-06-16", "2026-05-19", "Minutes of 5/19/26"),
               {"date": "2026-07-07", "titles": ["Agenda for 7/7/26"], "items": [_item("Proposals")]},
               approval("2026-07-21", "2026-05-19", "Minutes of 5/19/26")]
    readings = {"2026-06-16": [_minutes("m6", "2026-06-16", [_action("They approved the May meeting minutes.")])]}
    rows = cc.check_prior_minutes(agendas, readings, {}, _catalog("2026-05-19", "2026-06-16", "2026-07-07"))
    by_date = {r["date"]: r for r in rows if r["item"]}
    assert by_date["2026-06-16"]["approvalRecorded"] is True
    relisted = [i for i in by_date["2026-07-21"]["issues"] if i["issue"] == cc.MinutesIssue.RELISTED.value]
    assert relisted and relisted[0]["earlierAgendas"] == ["2026-06-16"]
    never = [r for r in rows if not r["item"]]
    assert [r["date"] for r in never] == ["2026-06-16", "2026-07-07"]      # held, and no agenda listed them


# --- insurance --------------------------------------------------------------------------------------------------------

def test_insurance_renewal_decision_and_policy_for_the_new_term(tmp_path) -> None:
    _write(tmp_path, "drive/files.json", [
        {"id": "f1", "name": "FLOOD POLICY 26-27 BLDG 5.pdf", "path": "My Drive/Insurance/2026/FLOOD POLICY 26-27 BLDG 5.pdf",
         "mimeType": "application/pdf", "created": "2026-09-01T00:00:00Z"},
        {"id": "f2", "name": "FLOOD POLICY 25-26 BLDG 5.pdf", "path": "My Drive/Insurance/2025/FLOOD POLICY 25-26 BLDG 5.pdf",
         "mimeType": "application/pdf", "created": "2025-09-01T00:00:00Z"},
        {"id": "f3", "name": "Renewal Ltr - Umbrella.pdf", "path": "My Drive/Insurance/2026/Renewal Ltr - Umbrella.pdf",
         "mimeType": "application/pdf", "created": "2026-09-10T00:00:00Z"},
    ])
    policies = cc._policy_files(tmp_path, _Community())
    assert [p["name"] for p in policies] == ["FLOOD POLICY 26-27 BLDG 5.pdf", "FLOOD POLICY 25-26 BLDG 5.pdf"]
    agenda = {"date": "2026-09-15", "items": [_item("Proposals", ["[Renewal Ltr - Umbrella.pdf], [FLOOD POLICY 26-27 BLDG 5.pdf]"], [
        _rel("f3", "Renewal Ltr - Umbrella.pdf"), _rel("f1", "FLOOD POLICY 26-27 BLDG 5.pdf", "insurance_policy", relation="named")],
        subitem="Insurance Renewal")]}
    patterns = cc.line_patterns(None)
    decided = cc.decisions_of(_minutes("m7", "2026-09-15", [_action("The board approved the insurance renewal of $30,000.", 3_000_000)]))
    rows = cc.check_insurance(agenda, decided, policies, patterns)
    assert rows[0]["terms"] == ["26-27"] and rows[0]["lines"] == ["flood", "umbrella"]
    assert rows[0]["decisionRecorded"] is True
    assert [p["name"] for p in rows[0]["policiesForNewTerm"]["flood"]] == ["FLOOD POLICY 26-27 BLDG 5.pdf"]
    assert rows[0]["missingLines"] == ["umbrella"] and "umbrella" in rows[0]["lead"]
    unread = cc.check_insurance(agenda, None, policies, patterns)
    assert unread[0]["decisionRecorded"] is None and "not read" in unread[0]["lead"]


# --- stale ------------------------------------------------------------------------------------------------------------

def test_an_item_carried_three_agendas_without_a_decision_is_stale() -> None:
    def agenda(day, *extra):
        return {"date": day, "titles": [f"Agenda for {day}"], "items": [
            _item("Maintenance", ["Review all open maintenance requests"]),
            _item("Review Proposals", ["Fruit Trees", *extra], [_rel("r", "Rodent Proofing - Estimate 000999.pdf", "proposal")])]}

    agendas = [agenda("2025-02-18"), agenda("2025-03-18"), agenda("2025-04-15")]
    decisions = {"2025-02-18": cc.decisions_of(_minutes("a", "2025-02-18", [_action("Fruit Trees", outcome="tabled")])),
                 "2025-03-18": [],
                 "2025-04-15": cc.decisions_of(_minutes("c", "2025-04-15", [_action("The board approved rodent proofing.")]))}
    rows = cc.check_stale(agendas, decisions)
    labels = {r["label"]: r for r in rows}
    assert "Fruit Trees" in labels and labels["Fruit Trees"]["count"] == 3 and labels["Fruit Trees"]["tabled"]
    assert "Rodent Proofing - Estimate 000999.pdf" not in labels            # decided at the third meeting
    assert not any("maintenance" in k for k in labels)                    # a standing item is not carried business
    # A document the amounts check found decided is not stale either.
    rows = cc.check_stale(agendas, {d: [] for d in decisions}, {("2025-03-18", cc._variant("Rodent Proofing - Estimate 000999.pdf"))})
    assert "Rodent Proofing - Estimate 000999.pdf" not in {r["label"] for r in rows}


# --- build ------------------------------------------------------------------------------------------------------------

def test_build_writes_the_cross_checks(tmp_path) -> None:
    _write(tmp_path, "meetings/agenda-items.json", {"meetings": [
        {"date": "2026-01-20", "agenda": "Agenda for 1/20/26", "items": [
            _item("Approval of minutes of previous meeting(s)", ["See: [Minutes of 12/16/25]"],
                  [_rel("m", "Minutes of 12/16/25", "minutes")], expects=["minutes"]),
            _item("Proposals", ["Newman CPA - Annual Tax Preparation [Engagement Letter.pdf]"],
                  [_rel("e", "Engagement Letter.pdf", "contract")])]}]})
    _write(tmp_path, "documents/readings.json", {"readings": [_minutes("100", "2026-01-20", [
        _action("The board approved a $1,850 engagement letter for annual tax preparation with Newman CPA.", 185_000)])]})
    _write(tmp_path, "meetings/catalog.json", {"meetings": [
        {"date": "2025-12-16", "records": [{"kind": "minutes", "where": "Drive", "name": "Minutes of 12/16/25"}]}]})
    result = cc.build(tmp_path, _Community(), texts=_texts({"e": "Engagement\nTotal fee: $1,850.00"}))
    assert (tmp_path / "meetings" / "cross-checks.json").is_file()
    assert result["counts"]["amounts"] == {cc.AmountOutcome.MATCHES.value: 1}
    assert result["priorMinutes"][0]["names"] == ["2025-12-16"]
    assert any("lead for a person" in c for c in result["caveats"])
    assert cc.summary_lines(result)[0].startswith("1 agendas")


def test_the_model_question_counts_only_a_grounded_answer() -> None:
    text = "The board approved the gutter cleaning proposal for $1,760 for all 8 buildings."

    def ask(prompt, schema):
        assert "Gutter Cleaning" in prompt and set(schema["properties"]) == {"decision", "amount"}
        return {"decision": {"stated": True, "value": "approved", "quote": "approved the gutter cleaning proposal"},
                "amount": {"stated": True, "value": 1760, "quote": "for $9,999 in total"}}

    out = cc.ask_decision("Gutter Cleaning.pdf", "Proposals", text, ask)
    assert out["decision"]["grounded"] and out["decision"]["value"] == "approved"
    assert not out["amount"]["grounded"] and out["amount"]["value"] is None
