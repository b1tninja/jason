"""The notice catalog: each row matches the statute's words on disk, the pinned terms, and the profile's rules and
provisions; the clocks compute their windows; the documents' stricter clocks combine with the statute's."""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

import pytest

from jason.community.notice_catalog import REQUIREMENTS, effective, for_ledger, requirement, rule_requirements
from jason.community.notices import (Anchor, Comparison, Evidence, Method, NoticeKind, NoticeProvision,
                                     NoticeRequirement, Recipients, Timing, Unit, combined)
from jason.community.statutory_terms import term

DATA = Path(__file__).resolve().parents[1] / "data"


def test_keys_are_unique_and_links_resolve():
    keys = [r.key for r in REQUIREMENTS]
    assert len(keys) == len(set(keys))
    for r in REQUIREMENTS:
        if r.carried_by:
            assert requirement(r.carried_by).timing, f"{r.key} rides in {r.carried_by}, which has no clock"
        assert r.verified or r.caveat, f"{r.key}: an unverified row says why"
        assert not r.verified or r.words, f"{r.key}: a verified row names the words it rests on"


@pytest.mark.parametrize("row", [r for r in REQUIREMENTS if r.verified], ids=lambda r: r.key)
def test_the_statute_on_disk_carries_the_rows_words(row):
    from jason.tasks.export_authorities import authority_text

    found = authority_text(DATA, row.statute)
    text = found.get("text") or ""
    if not text:
        pytest.skip(f"{row.statute} is not exported here (jason export-authorities)")
    flat = re.sub(r"\s+", " ", text)
    assert re.search(row.words, flat, re.I), (
        f"{row.statute} no longer reads '{row.words}' ({row.key}); the law may have changed: read the section, update "
        "the row, and run jason law-history --sweep")


@pytest.mark.parametrize("row", [r for r in REQUIREMENTS if r.term], ids=lambda r: r.key)
def test_a_rows_period_is_its_pinned_terms(row):
    clock = row.timing[0]
    value = clock.least if clock.least is not None else clock.most
    assert value == term(row.term).value, f"{row.key}: {value} against {row.term} ({term(row.term).value})"
    assert term(row.term).section in row.statute


def test_every_profile_rule_and_provision_links_to_the_catalog():
    from jason.community import community

    c = community()
    keys = {r.key for r in REQUIREMENTS}
    for rule in c.notice_rules():
        named = set(rule.requirements)
        assert named <= keys, f"{rule.key} names {named - keys}"
    seen = set()
    for p in c.notice_provisions():
        assert p.key not in seen, p.key
        seen.add(p.key)
        assert not p.requirement or p.requirement in keys, f"{p.key}: {p.requirement}"
        assert p.requirement or p.title, f"{p.key}: a document's own notice has a title"
        if p.comparison in (Comparison.LESS, Comparison.DIFFERENT):
            assert p.lead, f"{p.key}: a clause that asks less or differs carries its lead for the conflict register"


def test_a_provisions_section_is_in_its_outline():
    from jason.community import community

    for p in community().notice_provisions():
        path = DATA / "outlines" / f"{p.document}.json"
        if not path.is_file():
            continue
        numbers = {s["number"] for s in json.loads(path.read_text(encoding="utf-8"))["sections"]}
        for part in p.section.split(","):
            head = re.match(r"\s*(\d+(?:\.\d+)*)", part)
            if head:
                assert any(n == head.group(1) or n.startswith(head.group(1) + "(") or n.startswith(head.group(1) + ".")
                           for n in numbers), f"{p.key}: {head.group(1)} is not in {p.document}'s outline"


def test_a_provisions_named_section_is_in_its_outline():
    """A section a document names by heading rather than number ("b) Due Process Requirements", "B-1(d)") is one of
    its outline's numbers or titles, so the duties read from that section find the provision that carries them. A
    trailing parenthetical is a note, and "preamble" is the text before the first heading."""
    from jason.community import community

    for p in community().notice_provisions():
        path = DATA / "outlines" / f"{p.document}.json"
        if not path.is_file():
            continue
        sections = json.loads(path.read_text(encoding="utf-8"))["sections"]
        names = {s["number"].strip() for s in sections} | {s["title"].strip() for s in sections}
        for part in p.section.split(","):
            part = re.sub(r"\s*\([^()]*\)$", "", part.strip())
            if not part or part[0].isdigit() or part == "preamble":
                continue
            assert part in names, f"{p.key}: '{part}' is not a section of {p.document}'s outline"


def test_the_directors_notice_is_four_days_by_mail_and_proved_by_its_methods():
    row = requirement("board-meeting-directors")
    assert row.recipients is Recipients.BOARD and row.timing[0].least == 4
    assert {Evidence.MAILING_DECLARATION, Evidence.DELIVERY_DECLARATION} <= set(row.proof())
    assert for_ledger("board-meeting-directors-2026-10-20").key == "board-meeting-directors"
    assert for_ledger("board-meeting-2026-10-20").key == "board-meeting"


def test_a_rule_delivers_its_named_requirements_or_its_own():
    class Rule:
        key, requirements = "board-meeting", ()

    assert [r.key for r in rule_requirements(Rule)] == ["board-meeting"]
    Rule.requirements = ("discipline-hearing", "discipline-decision")
    assert [r.key for r in rule_requirements(Rule)] == ["discipline-hearing", "discipline-decision"]


def test_a_ledger_key_names_its_requirement_by_prefix():
    assert for_ledger("board-meeting-2026-10-20").key == "board-meeting"
    assert for_ledger("board-meeting-executive-2026-10-20").key == "board-meeting-executive"
    assert for_ledger("rule-change-proposed").key == "rule-change-proposed"
    assert for_ledger("owner-info-2027") is None


def test_windows_before_and_after():
    meeting = date(2026, 10, 20)
    assert Timing(Anchor.MEETING, least=4).window(meeting) == (None, date(2026, 10, 16))
    assert Timing(Anchor.DUE_DATE, least=30, most=60).window(date(2027, 1, 1)) == (date(2026, 11, 2), date(2026, 12, 2))
    assert Timing(Anchor.ACTION, after=True, most=14).window(meeting) == (meeting, date(2026, 11, 3))
    # Business days skip the weekend: a request on Friday, October 2, 2026 has ten business days to October 16.
    assert Timing(Anchor.REQUEST_RECEIVED, after=True, most=10, unit=Unit.BUSINESS_DAYS).window(date(2026, 10, 2))[1] \
        == date(2026, 10, 16)
    # 48 hours before an application on the 10th: by the 8th.
    assert Timing(Anchor.APPLICATION_OF_PESTICIDE, least=48, unit=Unit.HOURS).window(date(2026, 10, 10))[1] \
        == date(2026, 10, 8)


def _provision(comparison: Comparison, *timing: Timing, key: str = "p") -> NoticeProvision:
    return NoticeProvision(key, "bylaws", "1.1", "says", comparison, "x", timing, lead="lead")


def test_a_document_that_asks_more_narrows_the_clock_and_one_that_asks_less_does_not():
    statute = (Timing(Anchor.RULE_CHANGE, least=28),)
    clocks, notes = combined(statute, [_provision(Comparison.MORE, Timing(Anchor.RULE_CHANGE, least=30))])
    assert clocks[0].least == 30 and notes
    clocks, _ = combined(statute, [_provision(Comparison.LESS, Timing(Anchor.RULE_CHANGE, least=20))])
    assert clocks[0].least == 28
    window = (Timing(Anchor.FISCAL_YEAR_END, least=30, most=90),)
    clocks, _ = combined(window, [_provision(Comparison.MORE, Timing(Anchor.FISCAL_YEAR_END, most=60))])
    assert (clocks[0].least, clocks[0].most) == (30, 60)
    clocks, notes = combined(window, [_provision(Comparison.MORE, Timing(Anchor.FISCAL_YEAR_END, most=20))])
    assert (clocks[0].least, clocks[0].most) == (30, 90) and "cannot be met" in notes[0]


def test_effective_reads_the_profiles_provisions_and_the_carriers_clock():
    class Community:
        def notice_provisions(self):
            return (NoticeProvision("a", "bylaws", "9.9(g)", "60 days", Comparison.MORE, "collection-policy-notice",
                                    (Timing(Anchor.FISCAL_YEAR_END, most=60),)),
                    NoticeProvision("b", "bylaws", "8.5(g)", "15 days", Comparison.LESS, "discipline-decision",
                                    (Timing(Anchor.ACTION, after=True, most=15),), lead="14 days now"))

    _, clocks, notes, found = effective("collection-policy-notice", Community())
    assert (clocks[0].least, clocks[0].most) == (30, 60) and len(found) == 1
    _, clocks, notes, _ = effective("discipline-decision", Community())
    assert clocks[0].most == 14 and any("14 days now" in n for n in notes)


def test_the_evidence_follows_the_methods():
    r = requirement("pre-lien-notice")
    assert Evidence.CERTIFIED_RECEIPTS in r.proof() and Evidence.ANCHOR_DATE in r.proof()
    assert Evidence.POSTING in requirement("board-meeting").proof()
    assert Evidence.AGENDA in requirement("board-meeting").proof()
    assert Evidence.PROOF_OF_SERVICE in requirement("foreclosure-decision").proof()
    assert Evidence.FOLLOW_UPS in requirement("annual-budget-report").proof()
    assert Evidence.REQUEST_ON_FILE in requirement("records-current-year").proof()
    bare = NoticeRequirement("k", "t", "CIV 1", Recipients.MEMBER, NoticeKind.INDIVIDUAL, (Method.INDIVIDUAL,))
    assert bare.proof()[0] is Evidence.TEXT_AS_SENT


def test_the_secondary_copies_follow_4040b():
    # Article 7 of Chapter 6 (5300-5320) and Article 2 of Chapter 8 (5650-5690), and 5710.
    for r in REQUIREMENTS:
        if r.secondary_copies:
            number = int(re.match(r"CIV (\d+)", r.statute).group(1))
            assert 5300 <= number <= 5320 or 5650 <= number <= 5690 or number in (5710, 5730), r.key


def test_every_instrument_kind_names_notices_in_the_catalog():
    from jason.community.instruments import INSTRUMENTS

    keys = {r.key for r in REQUIREMENTS}
    assert len({i.key for i in INSTRUMENTS}) == len(INSTRUMENTS)
    for i in INSTRUMENTS:
        assert set(i.notices) <= keys, f"{i.key}: {set(i.notices) - keys}"
        assert i.missing, f"{i.key}: say what the living model lacks, or 'Nothing'"
