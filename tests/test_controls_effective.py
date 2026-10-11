"""Controls: when a control is in force, and the effective approver (the stricter of a kind's rule and the board's)."""

from __future__ import annotations

from dataclasses import replace
from datetime import date

from controls_support import FULL, LONG_AGO, TODAY, adopted, make, one_person_kind, roster, two_person_kind  # noqa: F401
from jason.approvals.registry import Approver
from jason.community.base import OfficerRole as R
from jason.controls.effective import effective_approver, in_force, roster_problem, signature_problems
from jason.controls.types import Basis, ControlState, Scope, ScopeKind


def test_only_an_adopted_control_with_a_reached_date_and_a_satisfying_roster_is_in_force():
    c = adopted(params={"signers": 2})
    assert in_force(c, TODAY, FULL)
    for state in (ControlState.SUGGESTED, ControlState.PROPOSED, ControlState.DECLINED, ControlState.DEFERRED,
                  ControlState.RETIRED):
        got = in_force(replace(c, state=state), TODAY, FULL)
        assert not got and got.reason == f"{state.value}, not adopted"
    assert in_force(replace(c, effective=None), TODAY, FULL).reason == "adopted, no effective date set"
    assert in_force(replace(c, effective=date(2100, 1, 1)), TODAY, FULL).reason == \
        "adopted, not in force until 2100-01-01"
    assert in_force(replace(c, effective=TODAY), TODAY, FULL)                          # the day itself


def test_a_roster_with_one_director_cannot_satisfy_a_second_director_but_the_control_still_binds():
    c = adopted(params={"signers": 2, "roles": (R.DIRECTOR,)})
    got = in_force(c, TODAY, roster(R.PRESIDENT, R.DIRECTOR))
    assert got.ok and got.lacks == "the roster lacks a second director"            # it binds; the roster is the problem
    assert in_force(c, TODAY, roster(R.DIRECTOR, R.DIRECTOR)).lacks == ""
    assert in_force(c, TODAY, roster(R.PRESIDENT)).lacks == "the roster has no director"


def test_one_person_holding_two_offices_counts_once():
    from jason.community.base import Officer

    both = [Officer(R.SECRETARY, "Pat Example"), Officer(R.TREASURER, "pat example")]
    assert roster_problem(adopted(params={"signers": 2}), both) == "the roster lacks a second board member"
    assert roster_problem(adopted(params={"signers": 2}), both + [Officer(R.DIRECTOR, "Sam Example")]) == ""


def test_the_manager_is_not_a_board_signer_and_a_named_office_must_be_seated():
    assert roster_problem(adopted(params={"signers": 2}), roster(R.PRESIDENT, R.MANAGER))
    c = adopted(params={"signers": 2, "must_include": (R.TREASURER,)})
    assert roster_problem(c, roster(R.PRESIDENT, R.DIRECTOR)) == "the roster has no treasurer"
    assert roster_problem(c, FULL) == ""


def test_a_roster_that_was_not_read_is_not_checked():
    assert in_force(adopted(params={"signers": 2, "roles": (R.DIRECTOR,)}), TODAY, None)


def test_no_controls_leave_the_kinds_own_rule(one_person_kind, two_person_kind):
    one = effective_approver(one_person_kind.key, {}, controls=(), roster=FULL, today=TODAY)
    assert one.builtin is Approver.ONE_PERSON and not one.second_needed(10**9) and one.signers == 1
    assert not one.controls and not one.waiting and one.why == "one person: the kind's own rule"
    two = effective_approver(two_person_kind.key, {}, controls=(), roster=FULL, today=TODAY)
    assert two.second_needed(0) and two.signers == 2 and two.why == "two persons: the kind's own rule"


def test_a_control_adds_a_second_signer_to_a_one_person_kind(one_person_kind):
    c = adopted(params={"signers": 2}, scope=Scope(ScopeKind.KIND, one_person_kind.key))
    got = effective_approver(one_person_kind.key, {}, controls=[c], roster=FULL, today=TODAY)
    assert got.second_needed(0) and got.signers == 2 and got.controls == (c,) and got.stricter_than_builtin
    assert "two signers: the board adopted this on 2099-01-01 (Payment signers)" in got.why


def test_a_threshold_asks_for_the_second_signer_only_above_the_amount(one_person_kind):
    c = adopted(params={"signers": 2, "over_cents": 250000}, scope=Scope(ScopeKind.KIND, one_person_kind.key))
    got = effective_approver(one_person_kind.key, {}, controls=[c], roster=FULL, today=TODAY)
    assert not got.second_needed(250000) and got.second_needed(250001)
    assert got.second_needed(None)                           # an amount not known cannot be shown to be below it
    assert "a second signer above $2,500.00" in got.why


def test_the_stricter_of_the_builtin_rule_and_every_control_wins(one_person_kind, two_person_kind):
    scope = Scope(ScopeKind.KIND, two_person_kind.key)
    # a (hand-made, unvalidated) control that asks for one signer cannot weaken a two-person kind
    weak = adopted(params={"signers": 1}, scope=scope)
    got = effective_approver(two_person_kind.key, {}, controls=[weak], roster=FULL, today=TODAY)
    assert got.second_needed(0) and got.signers == 2
    # and a threshold control cannot make a two-person kind second-above-an-amount
    thr = adopted(params={"signers": 2, "over_cents": 100000}, scope=scope)
    assert effective_approver(two_person_kind.key, {}, controls=[thr], roster=FULL, today=TODAY).second_needed(1)
    # two controls on a one-person kind: the lower threshold wins; "always" beats any threshold
    k = Scope(ScopeKind.KIND, one_person_kind.key)
    a, b = adopted(params={"signers": 2, "over_cents": 500000}, scope=k, key="a"), \
        adopted(params={"signers": 2, "over_cents": 100000}, scope=k, key="b")
    got = effective_approver(one_person_kind.key, {}, controls=[a, b], roster=FULL, today=TODAY)
    assert got.second_above_cents == 100000 and got.second_needed(100001) and not got.second_needed(100000)
    c = adopted(params={"signers": 2}, scope=k, key="c")
    got = effective_approver(one_person_kind.key, {}, controls=[a, b, c], roster=FULL, today=TODAY)
    assert got.second_always and got.second_above_cents is None and got.second_needed(0)


def test_offices_narrow_by_intersection_and_must_include_widens_by_union(one_person_kind):
    k = Scope(ScopeKind.KIND, one_person_kind.key)
    a = adopted(params={"signers": 2, "roles": (R.DIRECTOR, R.TREASURER), "must_include": (R.TREASURER,)}, scope=k, key="a")
    b = adopted(params={"signers": 2, "roles": (R.TREASURER, R.PRESIDENT), "must_include": (R.PRESIDENT,)}, scope=k, key="b")
    got = effective_approver(one_person_kind.key, {}, controls=[a, b], roster=FULL, today=TODAY)
    assert got.roles == (R.TREASURER,) and got.must_include == (R.PRESIDENT, R.TREASURER) and not got.clash
    c = adopted(params={"signers": 2, "roles": (R.DIRECTOR,)}, scope=k, key="c")
    got = effective_approver(one_person_kind.key, {}, controls=[a, b, c], roster=FULL, today=TODAY)
    assert got.clash and got.roles == (R.TREASURER,) and "no one in common" in got.why


def test_signers_are_checked_against_the_offices_the_rule_names(one_person_kind):
    c = adopted(params={"signers": 2, "roles": (R.DIRECTOR, R.TREASURER), "must_include": (R.TREASURER,)},
                scope=Scope(ScopeKind.KIND, one_person_kind.key))
    got = effective_approver(one_person_kind.key, {}, controls=[c], roster=FULL, today=TODAY)
    by_role = {o.role: o.name for o in FULL}
    ok = [by_role[R.TREASURER], by_role[R.DIRECTOR]]
    assert signature_problems(got, ok, FULL) == []
    assert signature_problems(got, [by_role[R.DIRECTOR], by_role[R.DIRECTOR]], FULL) == ["the treasurer must be among the signers"]
    assert any("does not hold an office that may sign" in p for p in signature_problems(got, [by_role[R.PRESIDENT], by_role[R.TREASURER]], FULL))
    assert signature_problems(got, ok, None)                                   # unreadable roster: said, not assumed
    assert signature_problems(effective_approver(one_person_kind.key, {}, controls=(), today=TODAY), ["Anyone"], None) == []


def test_a_control_before_its_date_waits_binds_nothing_and_warns_when_the_roster_could_not_satisfy_it(one_person_kind):
    k = Scope(ScopeKind.KIND, one_person_kind.key)
    future = adopted(params={"signers": 2}, scope=k, effective=date(2100, 1, 1), key="future")
    future_short = adopted(params={"signers": 2, "roles": (R.DIRECTOR,)}, scope=k, effective=date(2100, 1, 1), key="fs")
    suggested = replace(adopted(params={"signers": 2}, scope=k, key="idea"), state=ControlState.SUGGESTED)
    got = effective_approver(one_person_kind.key, {}, controls=[future, future_short, suggested],
                             roster=roster(R.PRESIDENT, R.DIRECTOR), today=TODAY)
    assert not got.second_needed(0) and not got.controls and not got.refusals
    assert {w.control.key: w.reason for w in got.waiting} == {
        "future": "adopted, not in force until 2100-01-01",
        "fs": "adopted, not in force until 2100-01-01; the roster could not satisfy it now: "
              "the roster lacks a second director"}                                     # a suggestion is not listed


def test_from_its_date_a_control_the_roster_cannot_satisfy_binds_and_refuses_the_act_with_the_reason(one_person_kind):
    k = Scope(ScopeKind.KIND, one_person_kind.key)
    short = adopted(params={"signers": 2, "roles": (R.DIRECTOR,)}, scope=k, key="short")
    got = effective_approver(one_person_kind.key, {}, controls=[short], roster=roster(R.PRESIDENT, R.DIRECTOR),
                             today=TODAY)
    assert got.second_needed(0) and got.controls == (short,) and not got.waiting             # no fall back to one person
    assert got.refusals == ("a control the board adopted on 2099-01-01 requires two signers; "
                            "the roster lacks a second director",)
    ok = effective_approver(one_person_kind.key, {}, controls=[short], roster=roster(R.DIRECTOR, R.DIRECTOR),
                            today=TODAY)
    assert ok.second_needed(0) and not ok.refusals


def test_a_threshold_control_the_roster_cannot_satisfy_refuses_only_a_plan_above_the_amount(one_person_kind):
    k = Scope(ScopeKind.KIND, one_person_kind.key)
    c = adopted(params={"signers": 2, "roles": (R.DIRECTOR,), "over_cents": 100000}, scope=k)
    thin = roster(R.PRESIDENT, R.DIRECTOR)

    def refusals(amount):
        return effective_approver(one_person_kind.key, {}, controls=[c], roster=thin, today=TODAY,
                                  amount_cents=amount).refusals

    assert refusals(100000) == () and len(refusals(100001)) == 1 and len(refusals(None)) == 1


def test_scope_all_applies_to_kinds_in_the_types_category_and_a_named_scope_always_applies(one_person_kind):
    broad = adopted(params={"signers": 2})                                    # a payment type, scope all
    assert not effective_approver(one_person_kind.key, {}, controls=[broad], roster=FULL, today=TODAY).controls
    got = effective_approver(one_person_kind.key, {}, controls=[broad], roster=FULL, today=TODAY,
                             categories=["payment"])
    assert got.controls == (broad,)
    # the board's second-person confirmation is for any kind
    any_kind = adopted("second-person-confirmation", {"required": True})
    assert effective_approver(one_person_kind.key, {}, controls=[any_kind], roster=FULL, today=TODAY).second_always
    # a family scope matches the system the kind works in; an account scope matches the plan's account
    fam = adopted(params={"signers": 2}, scope=Scope(ScopeKind.FAMILY, one_person_kind.system), key="fam")
    acct = adopted(params={"signers": 2}, scope=Scope(ScopeKind.ACCOUNT, "acct-1"), key="acct")
    assert effective_approver(one_person_kind.key, {}, controls=[fam], today=TODAY).second_always
    assert not effective_approver(one_person_kind.key, {"account": "acct-2"}, controls=[acct], today=TODAY).controls
    assert effective_approver(one_person_kind.key, {"account": "acct-1"}, controls=[acct], today=TODAY).second_always


def test_a_control_of_a_type_that_does_not_govern_approvals_is_not_applied(one_person_kind):
    c = adopted("review-cadence", {"every_days": 30}, scope=Scope(ScopeKind.KIND, one_person_kind.key))
    assert not effective_approver(one_person_kind.key, {}, controls=[c], today=TODAY).controls


def test_manager_spending_authority_asks_a_second_person_above_its_amount(one_person_kind):
    c = adopted("manager-spending-authority", {"over_cents": 50000, "asked": (R.TREASURER,)})
    got = effective_approver(one_person_kind.key, {}, controls=[c], roster=FULL, today=TODAY)
    assert got.second_needed(50001) and not got.second_needed(50000) and got.must_include == (R.TREASURER,)
    assert in_force(c, TODAY, roster(R.PRESIDENT)).lacks == "the roster has no treasurer"


def test_the_provisions_own_floor_binds_the_controls_value_in_force():
    basis = Basis("Bylaws 99.9", floor={"signers": 2})
    c = adopted(params={}, basis=basis)                                       # absent: the floor itself
    assert c.value("signers") == 2
