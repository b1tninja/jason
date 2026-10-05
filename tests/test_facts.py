"""Community facts over made-up rows."""

import dataclasses

from jason.community.facts import Fact, FactScope, FactStatus, PlanFactCoverage, ScopeKind, coverage_by_plan


def fact(key, status, kind=ScopeKind.PLAN, name="Plan A"):
    return Fact(key, f"A statement about {key}.", ("paint",), FactScope(kind, name), status)


def test_coverage_by_plan_counts_each_status_per_plan():
    facts = (
        fact("a", FactStatus.DOCUMENTED),
        fact("b", FactStatus.DOCUMENTED),
        fact("c", FactStatus.REPORTED),
        fact("d", FactStatus.ASSUMED, name="Plan B"),
        fact("e", FactStatus.ASSUMED, ScopeKind.COMMUNITY, ""),
        fact("f", FactStatus.ASSUMED, ScopeKind.BUILDING, "Plan A"),
    )
    rows = coverage_by_plan(facts, ["Plan A", "Plan B", "Plan C"])
    assert rows == (
        PlanFactCoverage("Plan A", 2, 1, 0),
        PlanFactCoverage("Plan B", 0, 0, 1),
        PlanFactCoverage("Plan C", 0, 0, 0),
    )
    assert rows[0].total == 3


def test_a_fact_stores_expressions_not_words():
    f = Fact("k", "s", ("t",), FactScope(ScopeKind.COMMUNITY), FactStatus.DOCUMENTED, provisions=("doc#1.2",))
    assert f.provisions == ("doc#1.2",) and f.confirmations == 0 and f.as_of == ""
    assert dataclasses.is_dataclass(f)


def test_fact_wording_guard():
    f = fact("k", FactStatus.REPORTED)
    text = " ".join(str(v) for v in dataclasses.asdict(f).values()).lower()
    for word in ("covered", "not covered", "at fault", "your responsibility"):
        assert word not in text


def test_the_profile_supplies_valid_rows():
    from jason.community import community

    for f in community().facts():
        assert isinstance(f.status, FactStatus) and f.key
