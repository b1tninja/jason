"""The general required-elements check: the signs kept in step with the catalog, a made-up notice read element by
element, the law's own words not counted as the element, and the statements of law found with their proposals."""

from __future__ import annotations

from jason.community.notice_catalog import requirement
from jason.community.notice_elements import (SIGNS, Status, check, law_statements, mask_recitals, missing,
                                             signs_for)
from jason.community.notices import NoticeRequirement, Recipients


def test_every_sign_row_matches_its_requirements_content():
    for key, rows in SIGNS.items():
        content = requirement(key).content
        assert tuple(s.element for s in rows) == content, key


def test_an_element_with_no_sign_is_never_passed():
    row = NoticeRequirement("example-notice", "Example", "CIV 9999", Recipients.ALL_MEMBERS, None, (),
                            content=("the moon's phase",))
    (sign,) = signs_for(row)
    assert not sign.checkable
    (finding,) = check(row, "The moon's phase is full.")
    assert finding.status is Status.UNCHECKED and not finding.ok


HEARING = """123 Main St

## Date, time, and place
**Date:** {HEARING_DATE}
**Time:** {HEARING_TIME}
**Place:** by video conference

## The alleged violation
{VIOLATION}

## Your rights
- You have the right to attend the hearing and to address the Board.
- You may cure the violation before the hearing, or give a financial commitment to cure it.
"""


def test_a_made_up_hearing_notice_missing_executive_session():
    found = {f.element: f for f in check(requirement("discipline-hearing"), HEARING)}
    assert found["the date, time, and place of the meeting"].status is Status.PRESENT
    assert "line 4" in found["the date, time, and place of the meeting"].where
    assert found["that the member may attend and address the board"].ok
    gone = [f.element for f in missing(found.values())]
    assert gone == ["that the member may ask for executive session"]


def test_a_token_supplies_its_element():
    found = check(requirement("insurance-change"), "<p>{NOTICE_REASON}</p><ul>{CHANGES_LIST}</ul><ul>{POLICY_LIST}</ul>")
    assert [f.status for f in found] == [Status.TOKEN, Status.TOKEN]


def test_a_recited_statute_is_not_the_element():
    text = ('Civil Code section 4360(a) provides: "The notice shall include the text of the proposed rule change and a '
            'description of the purpose and effect of the proposed rule change."\n')
    assert "text of the proposed" not in mask_recitals(text)
    found = check(requirement("rule-change-proposed"), text)
    assert all(f.status is Status.MISSING for f in found)
    found = check(requirement("rule-change-proposed"), text + "THE TEXT OF THE PROPOSED RULE CHANGE\nRule 1.\n"
                  "PURPOSE\nShade.\nEFFECT\nNone.\n")
    assert all(f.ok for f in found)


def test_a_conditional_element_says_its_condition():
    found = check(requirement("rule-change-adopted"), "THE TEXT OF THE RULE CHANGE AS ADOPTED\nRule 1.\n")
    emergency = found[1]
    assert emergency.status is Status.MISSING and "emergency" in emergency.applies


def test_an_enclosed_element():
    text = "## 9. Insurance\n\nA summary of the association's property and liability insurance is enclosed.\n"
    sign = next(f for f in check(requirement("annual-budget-report"), text) if "insurance summary" in f.element)
    assert sign.status is Status.ENCLOSED


def test_law_statements_and_their_proposed_references():
    text = ("A fine may not exceed $100 per violation unless the Board makes a written finding at an open meeting "
            "(Civil Code Section 5850(c), (d)). No late charge is charged on a fine (Section 5850(e)).\n"
            "## 8. Discipline and fines (§5310(a)(8), §5850)\n")
    found = law_statements(text)
    first = found[0]
    assert first.citations == ("CIV 5850(c)", "CIV 5850(d)")
    assert first.tokens == ("{CITE:CIV#5850(c)}", "{CITE:CIV#5850(d)}")
    assert not first.heading
    heading = found[-1]
    assert heading.heading and heading.citations == ("CIV 5310(a)(8)", "CIV 5850")


def test_a_dollar_amount_is_not_a_section():
    assert law_statements("The charge is $1,000 under the policy.") == []
