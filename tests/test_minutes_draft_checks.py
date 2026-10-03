"""The minutes draft's own checks: the quorum counted from the attendance, and subjects the open minutes keep general."""

from types import SimpleNamespace

from jason.tasks.minutes_draft import check_lines, checks, directors_on_call, quorum_check


class _Board:
    def quorum(self, in_office):
        return max(in_office // 2 + 1, 2)


COMMUNITY = SimpleNamespace(board=lambda: _Board())
DIRECTORS = ["Ana Example", "Ben Sample", "Cy Placeholder", "Dee Testcase"]


def _record(attendance, unidentified=()):
    return {"directors": DIRECTORS, "attendance": attendance, "unidentified": list(unidentified)}


def test_a_first_name_on_the_call_matches_one_director_and_a_caller_only_raises_the_count():
    present, maybe = directors_on_call(_record([("Ana Example", 30), ("Ben", 20), ("Some Member", 25)], ["5550100"]))
    assert present == ["Ana Example", "Ben Sample"] and maybe == ["5550100"]
    q = quorum_check(_record([("Ana Example", 30), ("Ben", 20)], ["5550100"]), COMMUNITY)
    assert q["needed"] == 3 and q["standing"] == "depends on an unidentified caller"


def test_two_of_four_is_no_quorum_and_a_carried_motion_is_flagged():
    text = "\n".join(["# DRAFT", "", "## Attendance and quorum", "", "A quorum was present.", "", "## Business", "",
                      "- **Motion:** Approve a repair.", "", "## Executive session", "", "Delinquencies and legal matters."])
    found = checks(_record([("Ana Example", 30), ("Ben Sample", 20)]), text, COMMUNITY)
    assert found["quorum"]["standing"] == "not on the record" and found["claimsQuorum"] and found["motions"] == 1
    assert found["confidential"] == []                     # the executive session's general headings are by design
    block = "\n".join(check_lines(found))
    assert "does not support it" in block and "without a quorum on the record" in block


def test_a_lawsuit_discussed_in_the_open_business_is_listed_for_the_secretary():
    text = "## Business\n\nThe directors discussed the lawsuit against the association.\n"
    found = checks(_record([("Ana Example", 1), ("Ben Sample", 1), ("Cy Placeholder", 1)]), text, COMMUNITY)
    assert found["quorum"]["standing"] == "present" and len(found["confidential"]) == 1


def test_the_meeting_type_and_pronouns_are_checked_and_the_quorum_is_given_as_a_fact():
    from jason.tasks.minutes_draft import _quorum_fact, meeting_kind

    assert meeting_kind("Special Meeting of the Board of Directors") == "special" and meeting_kind("Board call") == ""
    record = {**_record([("Ana Example", 30), ("Ben Sample", 20)]), "kind": "special"}
    text = "## Meeting\n\nRegular meeting held by Zoom.\n\n## Business\n\nBen Sample said he would call the vendor.\n"
    found = checks(record, text, COMMUNITY)
    assert found["kindDiffers"] and found["kindSaid"] == "regular" and len(found["pronouns"]) == 1
    block = "\n".join(check_lines(found))
    assert "the meeting's title says special" in block and "he or she" in block
    assert "NOT present" in _quorum_fact(found["quorum"])


def test_a_draft_that_says_no_quorum_is_not_read_as_claiming_one():
    text = "## Attendance and quorum\n\nNo quorum was present; a quorum was present only for the first item.\n"
    assert not checks(_record([("Ana Example", 1)]), text, COMMUNITY)["claimsQuorum"]
