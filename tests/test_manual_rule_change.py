"""The 4360 course for publishing official rules from a manual: (a) adopted or unchanged text, (b) changes with no
adoption found, recited before and after, and (c) pending suggestions struck from the enclosed text. Made-up
documents only."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from jason.community.manual import AdoptionAction, AdoptionEvent, Concordance
from jason.tasks import manual_rule_change as mrc
from jason.tasks import rule_change as rc

DRAFT = """# Example Commons Owners Association

## Example Rules

R-1. Quiet hours begin at 10 p.m.

R-2. Guests park in marked spaces only. Pets must be leashed at all times.

R-3. Trash goes out before noon on pickup day.
"""

ROWS = [
    Concordance("R-1", 0, "rules#R-1", "rule", True, "same number", "R-1. Quiet hours"),
    Concordance("R-2", 0, "rules#R-2", "rule", True, "same number", "R-2. Guests park"),
    Concordance("R-3", 0, "rules#R-3", "rule", True, "same number", "R-3. Trash goes out"),
    Concordance("Contacts", 0, "manual#contacts", "guidance", False, "the guide", "Who to call"),
    Concordance("F(a)", 0, "fees#F(a)", "policy", False, "moved to fees; same number", "Fee schedule"),
]


def _change(lineage, kind, before, after, a, b, *, number="", finding="no adoption found", ops=()):
    return {"lineage": lineage, "kind": kind, "before": before, "after": after, "fromOn": a, "toOn": b,
            "firstSaved": b, "numberBefore": number, "numberAfter": number, "flags": [], "finding": finding,
            "ops": [{"before": x, "after": y, "noise": False} for x, y in ops]}


RESULT = {
    "lineages": [
        {"id": "L-r2", "current": "R-2", "numbers": ["R-2"]},
        {"id": "L-r3", "current": "R-3", "numbers": ["R-3"]},
        {"id": "L-contacts", "current": "contacts", "numbers": ["contacts"]},
        {"id": "L-r1c", "current": "", "numbers": ["R-1(c)"]},
        {"id": "L-odd", "current": "odd", "numbers": ["odd"]},
        {"id": "L-fee", "current": "F(a)", "numbers": ["F(a)"]},
    ],
    "changes": [
        _change("L-r2", "reworded", "R-2. Guests park anywhere.",
                "R-2. Guests park in marked spaces only. Pets must be leashed at all times.",
                "2098-01-01", "2098-06-01", ops=(("anywhere", "in marked spaces only"),)),
        _change("L-r3", "reworded", "R-3. Trash goes out at dawn.", "R-3. Trash goes out before noon on pickup day.",
                "2096-01-01", "2096-06-01"),
        _change("L-contacts", "reworded", "Call the office.", "Call the manager.", "2097-01-01", "2097-06-01"),
        _change("L-r1c", "removed", "Residents may opt out of the visitor log.", "", "2098-01-01", "2098-06-01",
                number="R-1(c)"),
        _change("L-odd", "added", "", "Something no row places.", "2098-01-01", "2098-06-01"),
        _change("L-fee", "reworded", "Permit $10 a month.", "Permit $12 a month.", "2097-01-01", "2097-06-01"),
        _change("L-fee", "reworded", "Permit $12 a month.", "Permit $20.", "2098-01-01", "2098-06-01"),
        _change("L-r2", "renumbered", "x", "x", "2098-01-01", "2098-06-01"),          # its words kept: not a change
    ],
    "suggestions": [
        {"kind": "insert", "words": "Pets must be leashed at all times.", "since": "2098-02-01"},
        {"kind": "delete", "words": "before noon", "since": "2098-02-01"},
        {"kind": "insert", "words": "hoa@example.com", "since": "2098-03-01"},
    ],
}
NAMES = {"R-2": "R-2", "R-3": "R-3", "contacts": "Contacts", "F(a)": "F(a)"}
EVENTS = [AdoptionEvent(date(2096, 9, 1), AdoptionAction.ADOPTED, ("R-3",), "minutes of 2096-09-01", "rc-2096")]
CONTEXTS = [("insert", "Pets must be leashed at all times.", "R-2. Guests park in marked spaces only.")]


def _part(tmp_path: Path) -> mrc.Partition:
    draft = tmp_path / "rules-and-regulations.md"
    draft.write_text(DRAFT, encoding="utf-8")
    part = mrc.Partition("example-manual", "Example Owner's Guide", "Example Rules", "v3", "rev123", draft, "d1",
                         concordance=[r.__dict__ for r in ROWS if r.official])
    return mrc.separate(part, RESULT, ROWS, NAMES, EVENTS, DRAFT, CONTEXTS)


def test_the_three_kinds_are_kept_apart(tmp_path):
    part = _part(tmp_path)
    official = {u.address: u for u in part.official}
    assert set(official) == {"rules#R-1", "rules#R-2"}
    assert official["rules#R-1"].kind == "removed" and official["rules#R-1"].after == ""   # placed by its parent
    r2 = official["rules#R-2"]
    assert r2.before.startswith("R-2. Guests park anywhere") and r2.in_draft is True
    assert r2.changed_words() == ['"anywhere" became "in marked spaces only"']
    # A change a later adoption names is (a).
    assert [u.address for u, _ in part.cured] == ["rules#R-3"]
    # Guidance needs no notice; a section no row places is for a person.
    assert part.guidance == 1 and [x["number"] for x in part.unplaced] == ["odd"]
    # The policy bound in the manual: both of its changes, earliest words to latest.
    (fee,) = part.other_rules
    assert fee.steps == 2 and fee.before == "Permit $10 a month." and fee.after == "Permit $20."


def test_pending_suggestions_are_found_and_struck_from_the_enclosure(tmp_path):
    part = _part(tmp_path)
    seen = {s.words: s.in_draft for s in part.suggestions}
    assert seen == {"Pets must be leashed at all times.": True, "before noon": True, "hoa@example.com": False}
    body, struck = mrc.enclosure(part)
    assert "~~Pets must be leashed at all times.~~ [a pending suggestion" in body
    assert "before noon" in body and "~~before noon~~" not in body      # a suggested deletion stands until accepted
    assert [s.words for s in struck] == ["Pets must be leashed at all times."]
    assert any(u.suggested for u in part.official if u.address == "rules#R-2")


def test_the_draft_notice(tmp_path):
    part = _part(tmp_path)
    when = rc.timeline(None, notice_date=date(2099, 1, 1), decision=date(2099, 2, 3))
    law = {"CIV 4360(a)": "The notice shall include the text of the proposed rule change and a description of the "
                          "purpose and effect of the proposed rule change."}
    md = mrc.render(part, when, "Example Commons Owners Association", law=law,
                    book_titles={"rules": "Example Rules", "fees": "Fee Schedule"})
    assert "`rules@proposed-2099-01-01`" in md and "jason://rules@proposed-2099-01-01" in md
    notice = md[md.index("NOTICE OF PROPOSED RULE CHANGE"):md.index("## (b) Agenda item")]
    assert notice.index("THE TEXT OF THE PROPOSED RULE CHANGE") < notice.index("THE BOARD'S DESCRIPTION")
    assert "Part 2." in notice and "Part 3." in notice and "Earlier words (the version of 2098-01-01)" in notice
    assert "Residents may opt out of the visitor log." in notice and "stays removed" in notice
    assert "Permit $20." in notice
    assert "- [x] the text of the proposed rule change" in md
    assert "## Enclosure B: the concordance" in md and "| R-2 | rules#R-2 |" in md
    assert "Nothing is sent" in md
    path = mrc.write(tmp_path, date(2099, 1, 1), md)
    assert path == tmp_path / "drafts" / "rule-change-official-rules-2099-01-01.md"


def test_no_send_path():
    import inspect

    source = inspect.getsource(mrc)
    assert ".send(" not in source and "gmail" not in source.lower()
