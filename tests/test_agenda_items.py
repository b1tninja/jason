"""Agenda items: their notes and links, the kinds they bring, what they name, and the documents related to them."""

from __future__ import annotations

import json

from jason.community import mystique
from jason.community.agenda_items import expected_kinds, items_in_doc, mentions
from jason.community.symbols import DocumentKind as K

M = mystique()


def _para(style, *els):
    return {"paragraph": {"paragraphStyle": {"namedStyleType": style}, "elements": list(els)}}


def _t(text):
    return {"textRun": {"content": text}}


def _chip(title, uri):
    return {"richLink": {"richLinkProperties": {"title": title, "uri": uri, "mimeType": "application/pdf"}}}


DOC = {"title": "Agenda for 7/7/26", "tabs": [{"documentTab": {"body": {"content": [
    _para("HEADING_4", _t("Treasurer’s Report")),
    _para("NORMAL_TEXT", _chip("Treasurer's Report - 2026-06_Redacted.pdf", "https://drive.google.com/file/d/1x4pd_wcXi8mjbLKteNdGxC_HjLTWnH6m/view")),
    _para("HEADING_4", _t("Insurance Claim(s)")),
    _para("NORMAL_TEXT", _t("Water loss; see estimate 000999 and the mitigation invoice.")),
    _para("NORMAL_TEXT", _chip("AAA Repair Estimate.pdf", "https://drive.google.com/file/d/1OImTbE-IgBSPFHCn31-CXq8teS1V7Kbn/view")),
]}}}]}


def test_items_carry_their_notes_and_links_and_the_kinds_they_bring() -> None:
    items = items_in_doc(DOC, M.agenda_link_rules())
    assert [i.title for i in items] == ["Treasurer’s Report", "Insurance Claim(s)"]
    claim = items[1]
    assert claim.notes[0].startswith("Water loss") and claim.links[0].text == "AAA Repair Estimate.pdf"
    assert K.TREASURER_REPORT in expected_kinds(items[0].title, M.agenda_item_rules())
    assert expected_kinds(claim.title, M.agenda_item_rules())[:2] == (K.CLAIM_LETTER, K.CLAIM_ESTIMATE)


def test_an_item_names_files_and_numbered_documents_but_not_a_year() -> None:
    found = mentions("See Proposal #6021-1, estimate 000999, [AAA Repair Estimate.pdf], claim AZ260311, and the 2026 policy")
    assert found == ["AAA Repair Estimate.pdf", "6021-1", "000999", "AZ260311"]


def test_related_documents_are_judged_against_the_item_and_hint_a_kind(tmp_path) -> None:
    from jason.tasks.agenda_items import build

    (tmp_path / "meetings" / "agenda-docs").mkdir(parents=True)
    (tmp_path / "meetings" / "agenda-docs" / "d.json").write_text(json.dumps({**DOC, "_path": "My Drive/Meetings/2026/x"}), encoding="utf-8")
    (tmp_path / "drive").mkdir()
    (tmp_path / "drive" / "files.json").write_text(json.dumps([
        {"id": "1x4pd_wcXi8mjbLKteNdGxC_HjLTWnH6m", "name": "Treasurer's Report - 2026-06_Redacted.pdf", "path": "My Drive/Financials/x.pdf"},
        {"id": "1OImTbE-IgBSPFHCn31-CXq8teS1V7Kbn", "name": "AAA Repair Estimate.pdf", "path": "My Drive/AAA Repair Estimate.pdf"},
        {"id": "e1", "name": "Rodent Proofing - Estimate 000999.pdf", "path": "My Drive/Proposals / Estimates/Rodent Proofing - Estimate 000999.pdf"},
    ]), encoding="utf-8")
    result = build(tmp_path, M)
    items = {i["item"]: i for i in result["meetings"][0]["items"]}
    treasurer = items["Treasurer’s Report"]["related"][0]
    assert treasurer["relation"] == "linked" and treasurer["judgment"] == "agrees"
    claim = items["Insurance Claim(s)"]["related"]
    assert [r["relation"] for r in claim] == ["linked", "named"] and claim[1]["mention"] == "000999"
    hint = next(h for h in result["hints"] if h["name"] == "AAA Repair Estimate.pdf")
    assert hint["uses"][0]["item"] == "Insurance Claim(s)" and hint["suggested"][0] == "claim_letter"
