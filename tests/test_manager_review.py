"""The manager's review: the order of authority, the task prompts, the context pack, and quotes checked against sources."""

import json
from dataclasses import replace
from pathlib import Path

from jason.community import mystique
from jason.community.authority_order import Tier, tier_of_citation, tier_of_kind
from jason.community.context_pack import LawSection, assemble, cited_statutes
from jason.community.passages import Hit, Passage
from jason.community.prompts import ANSWER_SCHEMA, TaskKind, verify
from jason.community.symbols import DocumentKind
from jason.tasks.manager_review import messages, report, run


def test_the_order_follows_civil_code_4205():
    assert Tier.STATUTE < Tier.DECLARATION < Tier.ARTICLES < Tier.BYLAWS < Tier.OPERATING_RULES < Tier.RECORD
    assert tier_of_kind(DocumentKind.AMENDMENT) is Tier.DECLARATION
    assert tier_of_kind(DocumentKind.ANNEXATION) is Tier.DECLARATION
    assert tier_of_kind(DocumentKind.RESOLUTION) is Tier.OPERATING_RULES
    assert tier_of_kind(DocumentKind.MINUTES) is Tier.RECORD
    assert tier_of_kind(None) is Tier.RECORD
    assert tier_of_citation("CIV 5810") is Tier.STATUTE
    assert tier_of_citation("10 CCR 2792.23") is Tier.REGULATION
    assert tier_of_citation("42 USC 3604") is Tier.FEDERAL_LAW


def test_every_payhoa_template_has_a_task():
    community = mystique()
    subjects = {
        "Notice of Change in Insurance Coverage (Civ. 5810) - Master Policy": TaskKind.INSURANCE_CHANGE,
        "Notice of Change in Insurance Coverage (Civ. 5810) - Flood Insurance": TaskKind.FLOOD_RENEWAL,
        "Annual Fire Alarm System Testing": TaskKind.FIRE_SYSTEM_TESTING,
        "Annual Disclosures - Civ. §5310": TaskKind.ANNUAL_DISCLOSURES,
        "Treasurer's Report": TaskKind.TREASURER_REPORT,
        "Regular Meeting of the Board of Directors - May 19th at 7:00 pm": TaskKind.MEETING_NOTICE,
        "Trash cans left out": TaskKind.RULE_REMINDER,
        "Forward Balance": TaskKind.BALANCE_FORWARD,
    }
    for subject, kind in subjects.items():
        assert community.task_for_subject(subject).kind is kind, subject
    assert community.task_for_subject("Pool party") is None


def test_task_prompts_name_no_sections_and_no_figures():
    """A row says what to look for, never where it is now or what it says: those change with the law and the documents."""
    import re

    pinned = re.compile(r"\b(CIV|CORP|HSC|CCR|NFPA)\b|§|\$\s?\d|\b(?!911\b)\d{3,5}(\.\d+)?\b|\bsection \d|\b\d+\.\d+\(")
    for task in mystique().task_prompts():
        assert task.purpose
        for text in (task.purpose, *task.topics, *task.considerations, *task.guidance):
            assert not pinned.search(text), (task.kind, text)
        if task.kind is not TaskKind.QUESTION:
            assert task.topics and task.documents and task.considerations, task.kind


def test_the_association_context_is_read_from_the_specification():
    lines = mystique().prompt_context()
    assert "81 units in 8 buildings" in lines[0]
    assert any("board@" in line for line in lines)


def test_governing_files_classify_into_tiers():
    community = mystique()
    from jason.community.symbols import PayhoaFolder

    assert tier_of_kind(community.classify_document("CCRs 200709120758.pdf")) is Tier.DECLARATION
    assert tier_of_kind(community.classify_document("owners-manual-and-rules")) is Tier.OPERATING_RULES
    assert tier_of_kind(community.classify_document("Fine Schedule.pdf")) is Tier.OPERATING_RULES
    assert tier_of_kind(community.classify_document("Enforcement Policy")) is Tier.OPERATING_RULES
    assert tier_of_kind(community.classify_document("ACA 8 MYSTIGUE.pdf", PayhoaFolder.ANNEXATIONS)) is Tier.DECLARATION
    assert tier_of_kind(community.classify_document("Mystique - 221120 - Articles of Incorporation.pdf")) is Tier.ARTICLES


def test_cited_statutes_follow_the_documents_and_flag_old_numbers():
    current, prior = cited_statutes(["Notice shall be given per Civil Code Section 5810 and Section 1365(e) of the Civil Code."])
    assert "CIV 5810" in current
    assert "CIV 1365" in prior


CCR = "Trash containers shall be stored in the Unit, screened from view, and returned by 6:00 p.m. on the day of collection."
RULE = "B-16. TRASH RECEPTACLES Trash containers shall be stored in the Unit or in the garage."


def _pack(tmp_path: Path, draft: str = ""):
    governing = tmp_path / "artifacts" / "site-docs" / "governing_documents"
    governing.mkdir(parents=True)
    ccrs, manual = governing / "CCRs.md", governing / "Owner's Manual and Rules.md"
    ccrs.write_text(CCR, encoding="utf-8")
    manual.write_text(RULE, encoding="utf-8")

    def search(query, *folders, k, data_dir, mode):
        return (Hit(Passage(manual, 0, 0, RULE), 2.0), Hit(Passage(ccrs, 0, 0, CCR), 1.5),
                Hit(Passage(ccrs, 1, 0, CCR + " "), 1.0))          # a copy of the same words folds away

    chapter = "CIV 5850-5875: Article 2. Discipline and Cost Reimbursement"
    law = [LawSection("CIV 5850", chapter, "The board shall adopt and distribute a schedule of monetary penalties for violations of the operating rules."),
           LawSection("CIV 5855", chapter, "The board shall notify the member in writing at least 10 days prior to the hearing on discipline and fines."),
           LawSection("CIV 4100", "CIV 4075-4190: Definitions", "Common area means the entire common interest development except the separate interests."),
           LawSection("CIV 4350", "CIV 4340-4370: Operating Rules", "An operating rule is valid only if it is reasonable.")]
    records = {DocumentKind.CORRESPONDENCE: [("Courtesy letter on trash containers.pdf", "2025-06", "A courtesy reminder about trash containers and fines.")]}
    community = mystique()
    task = replace(community.task_prompt(TaskKind.RULE_REMINDER),
                   documents=community.task_prompt(TaskKind.RULE_REMINDER).documents + (DocumentKind.CORRESPONDENCE,))
    return assemble(community, task, tmp_path, draft=draft, search=search, law=law,
                    files=lambda kind: records.get(kind, []), fact_runner=lambda tool, args: {"tool": tool})


def test_the_law_is_found_by_topic_not_named(tmp_path):
    pack = _pack(tmp_path)
    law = {s.title for s in pack.sources if s.id.startswith("S")}
    assert {"CIV 5850", "CIV 5855"} <= law                  # found by the task's topics: fines, enforcement, hearings
    assert "CIV 4100" not in law                             # a definition no topic asks for stays on the shelf
    assert "CIV 5850-5875: Article 2. Discipline and Cost Reimbursement" in pack.shelf
    assert "THE LAW ON HAND" in pack.sources_text()


def test_the_pack_orders_sources_by_authority(tmp_path):
    pack = _pack(tmp_path, draft="Hi {first name}, please store your cans.")
    ids = {s.id: s for s in pack.sources}
    assert all(s.tier is Tier.STATUTE for s in pack.sources if s.id.startswith("S"))
    assert ids["R1"].title.startswith("Courtesy letter on trash")   # a record of a kind the task names
    governing = [s for s in pack.sources if s.id.startswith("G")]
    assert [s.tier for s in governing] == [Tier.DECLARATION, Tier.OPERATING_RULES]     # the CC&Rs first, copies folded
    assert ids["D1"].text.startswith("Hi {first name}")
    page = pack.markdown()
    assert page.index("[S1]") < page.index("[G1] CCRs") < page.index("[G2] Owner's Manual")
    assert "THE ASSOCIATION" in page and "Board of Directors" in page
    assert "[D1]" not in pack.sources_text()                    # the draft is in the task, once


def test_quotes_must_be_found_in_the_source_they_cite(tmp_path):
    pack = _pack(tmp_path, draft="Hi {first name}, please store your cans.")
    answer = {"issues": [{"issue": "storage", "rules": [
        {"source": "G1", "quote": "returned by 6:00 p.m. on the day of collection", "force": "required"},
        {"source": "G2", "quote": "returned by 6:00 p.m.", "force": "required"},           # wrong source
        {"source": "S9", "quote": "anything", "force": "required"}],                          # no such source
        "facts": [{"source": "D1", "quote": "please store your cans"}], "application": "", "conclusion": ""}]}
    checked = verify(answer, pack.texts())
    assert checked.grounded == 2
    assert {u["source"] for u in checked.ungrounded} == {"G2", "S9"}
    assert checked.unknown_sources == ["S9"]


def test_run_sends_the_base_prompt_and_schema_and_checks_the_answer(tmp_path):
    pack = _pack(tmp_path)
    hearing = next(s.id for s in pack.sources if s.title == "CIV 5855")
    sent = {}
    answer = {"issues": [{"issue": "i", "rules": [{"source": hearing, "quote": "at least 10 days prior to the hearing", "force": "required"}],
                          "facts": [], "application": "a", "conclusion": "c"}],
              "considerations": [{"consideration": "notice ahead", "sources": [hearing], "status": "met"},
                                 {"consideration": "invented", "sources": ["S99"], "status": "unknown"}],
              "conflicts": [], "board_decisions": ["decide"], "open_questions": [], "draft": "Hi {first name}"}

    def post(url, payload):
        sent.update(payload)
        return {"message": {"content": json.dumps(answer)}}

    checked = run(pack, post=post)
    assert sent["format"] == ANSWER_SCHEMA and sent["options"]["temperature"] == 0 and sent["think"] is False
    system, user = messages(pack)
    assert sent["messages"] == [system, user]
    assert "ORDER OF AUTHORITY" in system["content"] and "THE TEXT CONTROLS" in system["content"]
    assert f"[{hearing}]" in user["content"] and "CONSIDER" in user["content"]
    assert checked.grounded == 1 and not checked.ungrounded
    assert checked.unknown_sources == ["S99"]                 # a consideration that cites nothing real is caught
    page = report(pack, checked)
    assert "1 found in their sources" in page and "## Considerations" in page and "## Draft" in page and "decide" in page
