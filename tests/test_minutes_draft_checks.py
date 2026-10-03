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
