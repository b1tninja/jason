from datetime import date

from jason.community.history_report import (
    candidates_markdown,
    history_markdown,
    parcel_candidates,
    sections_markdown,
    slice_history,
)
from jason.community.recorder import Conveyance, NameCandidate, OwnershipHistory, succession
from mystique.developers import DEVELOPERS


def _chain() -> object:
    return succession(
        (
            Conveyance(
                "202203180704",
                date(2022, 3, 18),
                ("WATT COMMUNITIES AT MYSTIQUE LLC",),
                ("MYSTIQUE COMMUNITY ASSOCIATION",),
            ),
            Conveyance(
                "201703240140",
                date(2017, 3, 24),
                ("ALDEA HOMES INC",),
                ("WATT COMMUNITIES AT MYSTIQUE LLC",),
            ),
            Conveyance(
                "200605041076",
                date(2006, 5, 4),
                ("REYNEN & BARDIS COMMUNITIES INC",),
                ("WL HOMES LLC",),
            ),
        ),
        developers=DEVELOPERS,
    )


def test_a_succession_report_has_a_table_and_a_diagram():
    text = history_markdown("Community deeds", _chain(), note="Pinned grant deeds.")
    assert "| Document | Date | Grantors | Grantees | Comes from | Developer |" in text
    assert "| 202203180704 | 2022-03-18 |" in text
    assert "| Watt Communities at Mystique |" in text
    assert "```mermaid" in text
    assert "flowchart TD" in text
    assert "d201703240140 --> d202203180704" in text
    assert "d200605041076 --> d201703240140" not in text


def test_a_unit_chain_stops_at_the_shared_land_deed():
    history = _chain()
    sliced = slice_history(history, "202203180704", stop=frozenset({"201703240140"}))
    assert sliced.numbers == ("202203180704", "201703240140")
    text = sections_markdown("Units", (("201-1170-017-0001", sliced),))
    assert "| 201-1170-017-0001 | 2 | yes |" in text
    assert "d201703240140 --> d202203180704" in text


def test_gaps_and_cited_numbers_are_followups():
    history = succession(
        (
            Conveyance(
                "202407100627",
                date(2024, 7, 10),
                ("QUILLAN NORA JEAN TRUSTEE",),
                ("PEMBERLY OTTO V",),
                ("201006011361",),
            ),
        ),
        developers=DEVELOPERS,
    )
    text = history_markdown("5685 Whimsical", history)
    assert "| gap | 202407100627 | search QUILLAN NORA JEAN TRUSTEE |" in text
    assert "| unknown | 201006011361 | load the document cited by 202407100627 |" in text
    assert 'g202407100627["unknown<br/>QUILLAN NORA JEAN TRUSTEE"]' in text
    assert "g202407100627 -.-> d202407100627" in text
    assert 'd201006011361["201006011361<br/>unknown"]' in text
    assert "d201006011361 -.-> d202407100627" in text
    empty = sections_markdown(
        "Units",
        (("201-1170-022-0014", OwnershipHistory("201-1170-022-0014", ())),),
    )
    assert "| unknown |  | no document in this chain |" in empty


def test_name_candidates_become_a_table():
    rows = (
        (
            "201-1170-017-0008",
            "KHOA VAN TRIEU/HANH MAI THI LAM FAMILY LIV TR",
            "KHOA V TRIEU",
            parcel_candidates(
                "KHOA VAN TRIEU/HANH MAI THI LAM FAMILY LIV TR",
                "KHOA V TRIEU & HANH M T LAM FMLY ETC",
            ),
        ),
    )
    text = candidates_markdown(rows)
    assert "| FMLY | FAMILY | 1 |" in text
    assert "| V | VAN | 1 |" in text
    assert "201-1170-017-0008" in text
    assert NameCandidate("TR", "TRIEU") not in rows[0][3]
