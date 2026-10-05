"""The role class the console derives from a person's offices (jason.web.signin.role_class): officer, manager,
administrator, or none, and whose it is while an admin views the console as someone else."""

from __future__ import annotations

import pytest

from jason.web.signin import Account, Acting, Person, role_class, role_of_session

ROSTER = (Person("Pat Example", "president, treasurer", "p@example.org"), Person("Mo Manager", "manager", "m@example.org"),
          Person("Ana Admin", "admin", "a@example.org", True), Person("Dee Director", "director", "d@example.org"))


@pytest.mark.parametrize("offices, admin, expected", [
    ("president", False, "officer"),
    ("vice president", False, "officer"),
    ("treasurer, secretary", False, "officer"),
    ("director", False, "officer"),
    ("manager", False, "manager"),
    ("manager, treasurer", False, "officer"),        # a board office wins over the manager's
    ("admin", True, "administrator"),
    ("", True, "administrator"),
    ("president", True, "officer"),                   # an admin who holds an office is that office's class
    ("", False, ""),
    ("homeowner", False, ""),
])
def test_role_class(offices, admin, expected):
    assert role_class(offices, admin) == expected


def _account(name, role, admin=False):
    return Account(name=name, role=role, email="x@example.org", sub="1", at="2026-10-04T00:00:00Z", provider="google", admin=admin)


def test_the_signed_in_person_and_whom_an_admin_views_as():
    admin = _account("Ana Admin", "admin", True)
    assert role_of_session(admin, None, ROSTER) == "administrator"
    assert role_of_session(None, None, ROSTER) == ""                                  # signed out: no role
    assert role_of_session(admin, Acting("Pat Example", ""), ROSTER) == "officer"     # a person: that person's offices
    assert role_of_session(admin, Acting("Mo Manager", ""), ROSTER) == "manager"
    assert role_of_session(admin, Acting("", "treasurer"), ROSTER) == "officer"       # an office
    assert role_of_session(admin, Acting("", "manager"), ROSTER) == "manager"
    assert role_of_session(admin, Acting("Nobody Known", ""), ROSTER) == ""           # not on the roster: no seat
