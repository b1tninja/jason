"""The contract-terms reader against the made-up contracts in tests/fixtures/contracts.

Each fixture is one shape a real vendor contract took (a second-person form, a contract printed twice, a firm's initials,
a letterhead with a customer block, an association's own form that defines "we"). ``expected.json`` holds, per file,
what the reader must give now (``expect``) and what a later fix should give (``open``, not tested here). Move a row from
``open`` to ``expect`` when its fix lands. A ``contains`` is matched case-insensitively after collapsing whitespace.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from jason.tasks.contract_terms import read

FIXTURES = Path(__file__).parent / "fixtures" / "contracts"
EXPECTED = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))
CASES = sorted(name for name in EXPECTED if not name.startswith("_"))
OBLIGATIONS = ("duty", "prohibition", "permission", "right", "condition")


def _n(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip().lower()


@pytest.fixture(scope="module")
def readings():
    return {name: read((FIXTURES / name).read_text(encoding="utf-8"), key=f"fixture-{name}", name=name).as_dict()
            for name in CASES}


@pytest.mark.parametrize("name", CASES)
def test_parties_and_licenses(readings, name):
    r, exp = readings[name], EXPECTED[name]["expect"]
    assert _n(r["counterparty"]) == _n(exp["counterparty"])
    for bad in exp.get("counterparty_not", []):
        assert _n(r["counterparty"]) != _n(bad)
    numbers = [str(lic["number"]) for lic in r["licenses"]]
    for want in exp.get("licenses", []):
        assert want["number"] in numbers, f"license {want['number']} not read: {numbers}"


@pytest.mark.parametrize("name", CASES)
def test_terms_and_parties(readings, name):
    r, exp = readings[name], EXPECTED[name]["expect"]
    terms = r["terms"]
    if exp.get("no_duplicate_quotes"):
        quotes = [_n(t["quote"]) for t in terms]
        assert len(quotes) == len(set(quotes)), "a quote is read twice"
    if "max_unstated_pct" in exp:
        obligations = [t for t in terms if t["kind"] in OBLIGATIONS]
        pct = round(100 * sum(t["party"] == "unstated" for t in obligations) / len(obligations)) if obligations else 100
        assert pct <= exp["max_unstated_pct"], f"{pct}% of obligations have no party"
    for want in exp.get("terms", []):
        hit = next((t for t in terms if _n(want["contains"]) in _n(t["quote"])), None)
        assert hit is not None, f"no term holds {want['contains']!r}"
        assert hit["kind"] == want["kind"], f"{want['contains']!r}: {hit['kind']}"
        if "party" in want:
            assert hit["party"] == want["party"], f"{want['contains']!r}: {hit['party']}"
    for pair in exp.get("separate_terms", []):
        assert not any(all(_n(p) in _n(t["quote"]) for p in pair) for t in terms), f"one term holds {pair}"


@pytest.mark.parametrize("name", CASES)
def test_noise_notices_and_passive_duties(readings, name):
    r, exp = readings[name], EXPECTED[name]["expect"]
    quotes = [_n(t["quote"]) for t in r["terms"]]
    for words in exp.get("noise_excluded", []):
        assert not any(_n(words) in q for q in quotes), f"page noise read as a term: {words!r}"
    for words in exp.get("statutory_notice", []):
        hits = [t for t in r["terms"] if _n(words) in _n(t["quote"])]
        assert all(t["topic"] == "statutory notice" for t in hits), f"{words!r} read as {[t['topic'] for t in hits]}"
        assert not any(t["id"] in r["deliverables"] or t["kind"] in OBLIGATIONS for t in hits)
    if exp.get("statutory_notice"):
        assert any(f["code"] == "statutory-notice" for f in r["findings"])
    for want in exp.get("passive", []):
        hit = next((t for t in r["terms"] if _n(want["contains"]) in _n(t["quote"])), None)
        assert hit is not None, f"no term holds {want['contains']!r}"
        assert hit["party"] == want["party"], f"{want['contains']!r}: {hit['party']}"
        if "deliverable" in want:
            assert (hit["id"] in r["deliverables"]) is want["deliverable"]


@pytest.mark.parametrize("name", CASES)
def test_deliverables_and_findings(readings, name):
    r, exp = readings[name], EXPECTED[name]["expect"]
    by_id = {t["id"]: t for t in r["terms"]}
    delivered = [_n(by_id[i]["quote"]) for i in r["deliverables"] if i in by_id]
    for want in exp.get("deliverables", []):
        assert any(_n(want) in d for d in delivered), f"no deliverable holds {want!r}"
    codes = {f["code"] for f in r["findings"]}
    for code in exp.get("findings", []):
        assert code in codes, f"finding {code} missing: {sorted(codes)}"


def _term(r, words):
    return next((t for t in r["terms"] if _n(words) in _n(t["quote"])), None)


@pytest.mark.parametrize("name", CASES)
def test_aliases_roles_and_topics(readings, name):
    r, exp = readings[name], EXPECTED[name]["expect"]
    vocab = r["parties"]["counterparty"]
    for alias in exp.get("aliases", []):
        assert alias.lower() in vocab, f"alias {alias!r} not a counterparty word: {vocab}"
    for want in exp.get("alias_terms", []) + exp.get("role_labels", []) + exp.get("prohibition", []):
        hit = _term(r, want["contains"])
        assert hit is not None, f"no term holds {want['contains']!r}"
        assert hit["kind"] == want.get("kind", "prohibition" if want in exp.get("prohibition", []) else "duty")
        assert hit["party"] == want["party"], f"{want['contains']!r}: {hit['party']}"
    from jason.community.contract_terms import topic_of

    text = (FIXTURES / name).read_text(encoding="utf-8")
    for want in exp.get("topic", []):
        line = next(x for x in text.splitlines() if _n(want["contains"]) in _n(x))
        got = topic_of("", line.lstrip("-0123456789. ").split("–")[-1]).value
        if "topic" in want:
            assert got.startswith(want["topic"]), f"{want['contains']!r}: {got}"
        assert got != want.get("not_topic"), f"{want['contains']!r}: {got}"


@pytest.mark.parametrize("name", CASES)
def test_exemptions_discretion_standards_and_options(readings, name):
    r, exp = readings[name], EXPECTED[name]["expect"]
    for words in exp.get("exemptions", []):
        hit = _term(r, words)
        assert (hit is not None and hit["kind"] == "exemption") or any(_n(words) in _n(x) for x in r["excluded"]), \
            f"exemption not read: {words!r}"
    for words in exp.get("not_prohibition", []):
        assert _term(r, words)["kind"] != "prohibition"
    for want in exp.get("discretion", []) + exp.get("effort_standard", []):
        hit = _term(r, want["contains"])
        assert hit is not None, f"no term holds {want['contains']!r}"
        assert hit["discretion"] == want.get("degree", "effort standard"), f"{want['contains']!r}: {hit['discretion']}"
        assert hit["party"] == want["holder"], f"{want['contains']!r}: {hit['party']}"
    for want in exp.get("incorporated", []):
        hit = _term(r, want["contains"])
        assert hit is not None and all(s.strip() in hit["standards"] for s in want["standard"].split(","))
    options = {o["label"]: o["checked"] for o in r["options"]}
    chosen = exp.get("checked_options", {})
    assert all(options.get(x) is True for x in chosen.get("selected", []))
    assert all(options.get(x) is False for x in chosen.get("not_selected", []))
    if exp.get("options_not_read"):
        assert all(options.get(x, "missing") is None for x in exp["options_not_read"]), options
        assert any(f["code"] == "options-not-read" for f in r["findings"])
