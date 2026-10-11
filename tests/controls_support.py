"""Made-up controls, rosters, and approval kinds for tests/test_controls_*.py. Nothing here is an association's."""

from __future__ import annotations

from datetime import date

import pytest

from jason.approvals import model, registry
from jason.approvals.engine import Planned
from jason.approvals.model import PlanItem, Result
from jason.community.base import Officer
from jason.community.base import OfficerRole as R
from jason.controls import catalog
from jason.controls.types import Basis, Control, ControlState, HistoryEntry, ControlAct, Scope
from jason.locks import Resource

TODAY = date(2099, 12, 1)
LONG_AGO = date(2020, 1, 1)


def make(type_key="payment-signers", params=None, **kw) -> Control:
    return Control(kw.pop("key", type_key), catalog.get(type_key), params or {}, kw.pop("scope", Scope()),
                   kw.pop("basis", Basis("Bylaws 1.1")), **kw)


def adopted(type_key="payment-signers", params=None, *, effective=LONG_AGO, **kw) -> Control:
    hist = (HistoryEntry(ControlAct.ADOPT, "A Secretary", "2099-01-01T00:00:00+00:00", "voted", "dec-1"),)
    return make(type_key, params, state=ControlState.ADOPTED, effective=effective, decision="dec-1", history=hist, **kw)


def roster(*roles: R) -> list[Officer]:
    """One made-up person a role, named by the role and its position."""
    return [Officer(r, f"Person {i} {r.value}") for i, r in enumerate(roles)]


FULL = roster(R.PRESIDENT, R.SECRETARY, R.TREASURER, R.DIRECTOR, R.DIRECTOR)


def _plan(live, scope):
    items = [PlanItem(model.item_id("fake", "tag +", "member:1", "x"), "tag +", "member:1", "member 1", "x", "a test",
                      basis=model.digest("one"))]
    return Planned(items, scope=dict(scope), cost_cents=scope.get("cost"))


def _apply(live, planned, items, recorder):
    for i in items:
        recorder.applying([i.id])
        recorder.done(i.id, Result.APPLIED, "written")


def _kind(key, approver, system="fake", cost="") -> registry.ActionKind:
    return registry.register(registry.ActionKind(key, key, "none", system, Resource.STORE, registry.Risk.R2, approver,
                                                 "yes", _plan, _apply, cost=cost))


@pytest.fixture
def one_person_kind():
    kind = _kind("fake-one", registry.Approver.ONE_PERSON, cost="made up")
    yield kind
    registry.unregister("fake-one")


@pytest.fixture
def two_person_kind():
    kind = _kind("fake-two", registry.Approver.TWO_PERSON)
    yield kind
    registry.unregister("fake-two")
