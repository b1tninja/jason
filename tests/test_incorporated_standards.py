"""Incorporated standards: the open 'incorporated' rows of the made-up contracts, and made-up cases of our own."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from jason.community.incorporated_standards import (
    STANDARD_ROWS,
    Family,
    describe,
    find_standards,
    incorporated,
    incorporates,
    label,
)

FIXTURES = Path(__file__).parent / "fixtures" / "contracts"


def _rows() -> list[tuple[str, dict]]:
    expected = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))
    return [(name, row) for name, entry in expected.items() if isinstance(entry, dict)
            for part in ("expect", "open") for row in entry.get(part, {}).get("incorporated", [])]


def _sentence(text: str, contains: str) -> str:
    """The sentence of ``text`` (whitespace collapsed) that holds ``contains``."""
    flat = " ".join(text.split())
    i = flat.lower().find(" ".join(contains.split()).lower())
    assert i >= 0, contains
    starts = [m.end() for m in re.finditer(r"[.!?;]\s", flat[:i])]
    end = re.search(r"[.!?;](?=\s|$)", flat[i:])
    return flat[starts[-1] if starts else 0: i + (end.end() if end else len(flat) - i)]


@pytest.mark.parametrize(("name", "row"), _rows(), ids=lambda v: v if isinstance(v, str) else v.get("standard"))
def test_fixture_rows(name: str, row: dict) -> None:
    text = (FIXTURES / name).read_text(encoding="utf-8")
    sentence = _sentence(text, row["contains"])
    assert incorporates(sentence)
    assert describe(incorporated(sentence)) == row["standard"]
    # The whole document reads the same standards, with the cue on each.
    whole = incorporated(text)
    first = row["standard"].split(",")[0].split(" (")[0]
    assert any(label(s).startswith(first) for s in whole)


def test_fixture_rows_exist() -> None:
    names = {name for name, _ in _rows()}
    assert {"01_monitoring_second_person.txt", "02_sprinkler_proposal_bullets.txt"} <= names


def test_fixture_02_title_19_shares_the_cue() -> None:
    text = (FIXTURES / "02_sprinkler_proposal_bullets.txt").read_text(encoding="utf-8")
    found = find_standards(text)
    nfpa = [s for s in found if s.family == "nfpa"]
    title19 = [s for s in found if s.family == "title-19"]
    assert nfpa and title19
    assert nfpa[0].cue == "in strict accordance with"
    assert title19[0].cue == "in strict accordance with"
    assert text[nfpa[0].start:nfpa[0].end].startswith("NFPA #25")


def test_families_and_names() -> None:
    text = ("Work shall be done per the manufacturer's installation instructions, in accordance with the "
            "California Building Code, the CFC, Title 24, 19 CCR, NFPA 13, 2019 Edition, UL 300, all applicable "
            "local codes and ordinances, the ADA, and Cal/OSHA. Devices shall be UL-listed.")
    got = {(s.family, s.name) for s in find_standards(text)}
    assert ("manufacturer", "manufacturer's installation instructions") in got
    assert ("cbc", "California Building Code") in got
    assert ("cfc", "CFC") in got
    assert ("title-24", "Title 24") in got
    assert ("title-19", "19 CCR") in got
    assert ("nfpa", "NFPA 13, 2019 Edition") in got
    assert ("ul", "UL 300") in got
    assert ("ul", "UL-listed") in got
    assert ("local-code", "all applicable local codes and ordinances") in got
    assert ("ada", "ADA") in got
    assert ("osha", "Cal/OSHA") in got
    assert {f.value for f in Family} == {r.family.value for r in STANDARD_ROWS}


def test_label_nfpa_edition() -> None:
    (s,) = find_standards("Tested to NFPA 72, 2019 edition.")
    assert label(s) == "NFPA 72 (2019 Edition)"
    (s,) = find_standards("See NFPA 25.")
    assert label(s) == "NFPA 25"


@pytest.mark.parametrize("sentence", [
    "Example Alarm, Inc. will test the System per NFPA 72.",
    "All work shall comply with the California Fire Code.",
    "Repairs pursuant to Title 19 fire regulations are billed separately.",
    "Install per the manufacturer's recommendations.",
    "Ramps at 123 Main St shall be built as required by the ADA.",
    # Near-misses of the fixes below: each still incorporates.
    "Fees are $40 per inspection, and ramps are built per UL 300.",
    "Per Title 19, California Code of Regulations, extinguishers are serviced yearly.",
    "Per Title 19, extinguishers are serviced under the State Fire Marshal's rules.",
    "Contractor shall not begin work until the permit issues, and shall comply with NFPA 25.",
    "Contractor shall follow NFPA-72.",
    "The panel conforms to NFPA 72.",
    "The system meets the requirements of NFPA 13.",
    "Contractor follows the manufacturer's instructions.",
])
def test_cues_that_incorporate(sentence: str) -> None:
    assert incorporates(sentence)


@pytest.mark.parametrize("sentence", [
    "Fees are $40 per ADA ramp inspected.",
    "Per Title 19 of the Municipal Code, parking is prohibited.",
    "Per Title 19 of the Example City Municipal Code, parking is prohibited.",
    "Contractor shall not be obligated to perform work not in accordance with NFPA 25.",
    "Contractor is not obligated to inspect devices in accordance with NFPA 72.",
    "Repairs pursuant to Title 19 are billed separately.",
    "Crews follow ADA ramp layouts.",
    "Fees are $40 per UL listed device.",
])
def test_review_false_positives(sentence: str) -> None:
    assert not incorporates(sentence)


def test_bare_title_19_needs_context() -> None:
    assert find_standards("Per Title 19 of the Municipal Code, parking is prohibited.") == []
    assert find_standards("Repairs pursuant to Title 19 are billed separately.") == []
    assert find_standards("Title 19 of the County Code applies.") == []
    (s,) = find_standards("Inspections per CCR Title 19.")
    assert s.family == "title-19" and s.cue == "per"


def test_nfpa_hyphen_and_follow() -> None:
    (s,) = incorporated("Contractor shall follow NFPA-72.")
    assert s.family == "nfpa" and s.cue == "follow" and label(s) == "NFPA 72"


@pytest.mark.parametrize("sentence", [
    "Devices are tested in accordance with the 2019 edition of NFPA 72.",
    "Devices are tested in accordance with NFPA 72 (2019).",
])
def test_edition_kept_in_name(sentence: str) -> None:
    (s,) = incorporated(sentence)
    assert s.name == "NFPA 72 (2019)"
    assert label(s) == "NFPA 72 (2019)"


@pytest.mark.parametrize("sentence", [
    "The fee is $90 per month.",
    "We charge $150 per visit; all devices are inspected to NFPA 72.",
    "Service is billed per visit and the panel is listed by NFPA 72 for reference.",
    "The fee is $90 per month. NFPA 72 is a national standard.",
    "Our technicians graduated from the ADA program.",
])
def test_not_incorporated(sentence: str) -> None:
    assert not incorporates(sentence)


def test_lower_case_acronyms_are_not_names() -> None:
    assert find_standards("the ada and ul crews arrived; cbc pending") == []
