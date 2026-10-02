"""The 5810 notice is generated from the policy records; a sent notice is never rewritten."""

from datetime import date

from jason.community import community
from jason.tasks.insurance_notice import ChangeKind, current_and_prior, notice_values, policy_changes
from jason.tasks.packets import fill_letter, insurance_rows, template_file


def _term(start, end, *, carrier="Carrier A", limit=100_000_00, deductible=1_000_00, key="building_limit"):
    return {"start": start, "end": end, "carrier": carrier, "number": "P-1", "limits": {key: limit}, "deductible": deductible}


MASTER = {"key": "master", "kind": "master", "terms": [
    _term("2025-09-28", "2026-09-28"),
    _term("2026-09-28", "2027-09-28", limit=120_000_00, deductible=5_000_00),
]}


class _Profile:
    def coverages_not_carried(self):
        return ("earthquake",)


def test_the_term_in_force_is_compared_with_the_one_before():
    term, prior = current_and_prior(MASTER, date(2026, 10, 1))
    assert term["start"] == "2026-09-28" and prior["start"] == "2025-09-28"
    term, prior = current_and_prior(MASTER, date(2026, 9, 1))     # renewed ahead of time: report the renewal
    assert term["start"] == "2026-09-28"


def test_a_higher_deductible_is_a_5810_change_and_a_higher_limit_is_not():
    changes, gaps = policy_changes([MASTER], date(2026, 10, 1))
    kinds = [c.kind for c in changes]
    assert kinds[0] is ChangeKind.DEDUCTIBLE_INCREASED and ChangeKind.LIMIT_INCREASED in kinds
    assert [c.kind.significant for c in changes] == [True, False] and not gaps
    assert "from $1,000 to $5,000" in changes[0].sentence


def test_a_canceled_policy_is_a_5810_change_but_a_missing_term_is_only_a_gap():
    ended = {"key": "umbrella", "kind": "umbrella", "terms": [_term("2025-01-01", "2026-01-01", key="each_occurrence")]}
    changes, gaps = policy_changes([ended], date(2026, 3, 1))
    assert changes == [] and "read the renewed declarations" in gaps[0]       # not read yet is not a lapse
    changes, _ = policy_changes([ended | {"status": "canceled"}], date(2026, 3, 1))
    assert changes[0].kind is ChangeKind.LAPSED and "no replacement" in changes[0].sentence


def test_no_named_change_is_a_gap_for_the_board_not_a_notice_decision():
    same = {"key": "master", "kind": "master", "terms": [_term("2025-09-28", "2026-09-28"), _term("2026-09-28", "2027-09-28")]}
    values, gaps = notice_values([same], _Profile(), on=date(2026, 10, 1))
    assert "as it now stands" in values["NOTICE_REASON"]
    assert any("does not require" in g for g in gaps)


def test_the_notice_renders_from_the_base_with_the_profiles_values():
    from jason.community.template_values import profile_values

    values, _ = notice_values([MASTER], _Profile(), on=date(2026, 10, 1))
    assert values["POLICY_LIST"].splitlines()[-1] == "Earthquake: the Association does not carry earthquake insurance."
    html, left = fill_letter("letter:insurance-change-notice.html", profile_values(community()) | values | {"MAILING_DATE": "x"})
    assert "<li>Property (master policy): deductible raised from $1,000 to $5,000.</li>" in html
    assert community().name in html and not left
    assert template_file("insurance-change-notice.html").parent.name == "packets"


def test_coverage_not_carried_comes_from_the_profile():
    policies = [{"key": "master", "kind": "master", "terms": [_term("2026-09-28", "2027-09-28")]}]
    assert insurance_rows(policies, 2027)[0][-1][0] != "Earthquake"
    rows, _ = insurance_rows(policies, 2027, not_carried=community().coverages_not_carried())
    assert rows[-1][0] == "Earthquake"


def test_the_sent_2026_notice_is_kept_as_it_was_sent():
    text = template_file("master-insurance-notice.html").read_text(encoding="utf-8")
    assert "{SIGNER}" not in text and "2026&ndash;2027" in text
