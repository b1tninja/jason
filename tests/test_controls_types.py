"""Controls: the catalog, the parameter algebra, and the refusal of a control that would go below a floor (docs/controls.md).

Nothing here names an association: the roster and the provisions are made up."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import replace
from datetime import date

import pytest

from jason.community.base import OfficerRole as R
from jason.controls import catalog
from jason.controls.effective import ensure_valid, validate
from controls_support import make, one_person_kind, two_person_kind  # noqa: F401 - fixtures
from jason.controls.types import (Basis, ControlFamily, ControlRefused, ControlState, ParamKind, Scope, ScopeKind,
                                  from_dict, meets, normalize, stricter, to_dict)


def test_importing_controls_loads_no_profile_and_reads_nothing():
    code = ("import sys, jason.controls, jason.controls.types, jason.controls.catalog, jason.controls.store, "
            "jason.controls.effective\n"
            "bad = [m for m in sys.modules if m in ('mystique', 'jason_mystique') or m.startswith(('mystique.', 'jason_mystique.'))]\n"
            "assert not bad, bad\n")
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr


def test_the_catalog_has_the_nine_types_each_with_a_family_and_parameters():
    assert set(catalog.keys()) == {"payment-signers", "reserve-signers", "contract-authorization", "limit-checks",
                                   "manager-spending-authority", "review-cadence", "delivery-class", "recorder",
                                   "second-person-confirmation"}
    for t in catalog.CATALOG:
        assert isinstance(t.family, ControlFamily) and t.governs and t.parameters and t.sources
        assert len({p.key for p in t.parameters}) == len(t.parameters)
        assert set(t.floor) <= {p.key for p in t.parameters}
    assert catalog.get("payment-signers").floor == {"signers": 1}


def test_an_unknown_type_is_refused_by_name():
    with pytest.raises(ControlRefused, match="no control type 'nope'"):
        catalog.get("nope")


def test_the_algebra_picks_the_stricter_of_two_values():
    c = catalog.get("payment-signers")
    signers, roles, must, over = (c.spec(k) for k in ("signers", "roles", "must_include", "over_cents"))
    assert stricter(signers, 1, 2) == 2 and stricter(over, 5000, 2500) == 2500 and stricter(over, None, 2500) == 2500
    assert stricter(roles, (), (R.TREASURER,)) == (R.TREASURER,)
    assert stricter(roles, (R.DIRECTOR, R.TREASURER), (R.TREASURER,)) == (R.TREASURER,)
    assert stricter(must, (R.TREASURER,), (R.SECRETARY,)) == (R.SECRETARY, R.TREASURER)
    choice = catalog.get("delivery-class").spec("method")
    assert stricter(choice, "certified", "standard") == "certified"
    assert meets(choice, "first class", "standard") and not meets(choice, "standard", "first class")


def test_a_value_is_normalized_or_refused():
    c = catalog.get("payment-signers")
    assert normalize(c.spec("roles"), ["director", "treasurer", "director"]) == (R.DIRECTOR, R.TREASURER)
    for key, bad in (("signers", 0), ("signers", 3), ("signers", True), ("signers", "2"), ("over_cents", -1),
                     ("roles", "director"), ("roles", ["janitor"])):
        with pytest.raises(ControlRefused):
            normalize(c.spec(key), bad)
    with pytest.raises(ControlRefused, match="has no parameter"):
        c.spec("colour")


def test_a_control_at_or_above_its_floor_is_valid():
    assert validate(make(params={"signers": 2, "over_cents": 250000, "roles": (R.TREASURER, R.DIRECTOR)})) == []
    assert validate(make(params={})) == []                              # nothing set: the floor itself


def test_a_control_below_the_catalogs_floor_is_refused():
    # the floor is 1, so the lowest value normalize allows is already the floor; the loosening below it is refused there
    with pytest.raises(ControlRefused):
        normalize(catalog.get("payment-signers").spec("signers"), 0)


def test_a_control_below_the_floor_its_provision_sets_is_refused_with_the_provision_named():
    basis = Basis("Bylaws 99.9", "...", {"signers": 2})
    problems = validate(make(params={"signers": 1}, basis=basis))
    assert problems and "below the floor in Bylaws 99.9 (2)" in problems[0] and "only adds" in problems[0]
    assert validate(make(params={"signers": 2}, basis=basis)) == []
    assert validate(make(params={}, basis=basis)) == []                 # absent: the floor itself, never less
    with pytest.raises(ControlRefused, match="Bylaws 99.9"):
        ensure_valid(make(params={"signers": 1}, basis=basis))


def test_a_threshold_looser_than_the_provisions_is_refused_and_a_tighter_one_is_not():
    basis = Basis("Bylaws 99.9", floor={"over_cents": 100000})
    assert validate(make(params={"over_cents": 250000}, basis=basis))
    assert validate(make(params={"over_cents": 50000}, basis=basis)) == []


def test_a_basis_floor_on_a_parameter_the_type_lacks_is_refused():
    assert validate(make(basis=Basis("Bylaws 1.1", floor={"colour": 1})))


def test_offices_that_must_sign_must_be_among_those_who_may():
    assert validate(make(params={"signers": 2, "roles": (R.DIRECTOR,), "must_include": (R.TREASURER,)}))
    assert validate(make(params={"signers": 1, "must_include": (R.TREASURER, R.SECRETARY)}))


def test_a_control_naming_a_two_person_kind_cannot_ask_for_less(two_person_kind, one_person_kind):
    scoped = Scope(ScopeKind.KIND, two_person_kind.key)
    assert validate(make(params={"signers": 1}, scope=scoped))
    assert validate(make(params={"signers": 2, "over_cents": 100}, scope=scoped))       # only above an amount: weaker
    assert validate(make(params={"signers": 2}, scope=scoped)) == []
    assert validate(make("second-person-confirmation", {"required": False}, scope=scoped))
    # the same words on a one-person kind add something, so nothing is refused
    assert validate(make(params={"signers": 1}, scope=Scope(ScopeKind.KIND, one_person_kind.key))) == []


def test_a_scope_naming_no_kind_is_refused_and_a_broad_scope_is_not_checked_against_one_kind():
    assert validate(make(scope=Scope(ScopeKind.KIND, "no-such-kind")))
    assert validate(make(scope=Scope(ScopeKind.FAMILY, "payhoa"))) == []
    assert validate(make("review-cadence", {"every_days": 30}, scope=Scope())) == []


def test_a_control_round_trips_through_its_json():
    c = make(params={"signers": 2, "roles": (R.DIRECTOR, R.TREASURER), "over_cents": 250000},
             basis=Basis("Bylaws 99.9", "words whole", {"signers": 2}), reading="a reading", state=ControlState.ADOPTED,
             decision="2099-10-03#4", effective=date(2099, 11, 14))
    again = from_dict(to_dict(c))
    assert again == c and to_dict(again) == to_dict(c)


def test_a_record_with_an_unknown_state_scope_or_parameter_is_refused_not_guessed():
    good = to_dict(make(params={"signers": 2}))
    for bad in ({**good, "state": "enabled"}, {**good, "scope": {"kind": "kind"}},
                {**good, "parameters": {"colour": 1}}, {**good, "type": "nope"}, {**good, "key": ""},
                {**good, "effective": "tomorrow"}):
        with pytest.raises(ControlRefused):
            from_dict(bad)


def test_the_effective_date_and_adoption_day_read_from_the_record():
    c = make(state=ControlState.ADOPTED, effective=date(2099, 11, 14))
    assert c.adopted_at == "2099-11-14"
    assert replace(c, effective=None).adopted_at == ""
    assert ParamKind.COUNT.value == "count"
