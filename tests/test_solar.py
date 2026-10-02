from datetime import date
from pathlib import Path

from jason.community.association_record import ParcelLien
from jason.community.filings import CLOSES, OPENS, Encumbrance, Process, Step
from jason.community.index_cache import IndexCache
from jason.community.parcel_history import HistoryStep, ParcelHistory
from jason.community.property_report import parcel_markdown, solar_markdown
from jason.community.recorder import Filing, IndexedInstrument
from jason.community.solar import (
    SecuredPartyKind,
    SolarProgram,
    SolarStanding,
    classify_secured_party,
    solar_record,
)
from jason.tasks.sync_solar import sync_solar
from mystique.solar import SOLAR_PROGRAM

PROGRAM = SolarProgram(
    "shared solar", "Watt", (1, 2), ("ULTRALIGHT RESIDENTIAL SOLAR LLC", "DORADO I RESI SOLAR LLC"), ("ULTRALIGHT", "DORADO"),
    servicer="SunStrong", note="tell escrow",
)


def _lifecycle(number, debtor, secured, *, closed_by=None, closed_on=None):
    opened = Step(number, date(int(number[:4]), int(number[4:6]), int(number[6:8])), "368 UCC FINANCING STATEMENT", OPENS, (debtor,), (secured,))
    steps = [opened]
    if closed_by:
        steps.append(Step(closed_by, closed_on, "372 UCC TERMINATION", CLOSES, (secured,), (debtor,)))
    return Encumbrance(Process.FIXTURE_FILING, (debtor,), (secured,), tuple(steps))


def _lien(owner, lifecycle, during=True):
    return ParcelLien(owner, lifecycle, during, False)


def test_the_secured_party_says_what_a_fixture_filing_is():
    assert classify_secured_party(("ULTRALIGHT 2 RESIDENTIAL SOLAR LLC",), SOLAR_PROGRAM) is SecuredPartyKind.PROGRAM_LESSOR
    assert classify_secured_party(("DORADO I SOLARBLOOM LLC",), SOLAR_PROGRAM) is SecuredPartyKind.PROGRAM_LESSOR
    assert classify_secured_party(("TESLA INC",)) is SecuredPartyKind.SOLAR_LESSOR
    assert classify_secured_party(("SOLARCITY CORP",)) is SecuredPartyKind.SOLAR_LESSOR
    assert classify_secured_party(("LOANPAL LLC",)) is SecuredPartyKind.SOLAR_LENDER
    assert classify_secured_party(("SACTO MUNI UTILY DIST",)) is SecuredPartyKind.UTILITY
    assert classify_secured_party(("BANK OF SACTO",)) is SecuredPartyKind.LENDER
    assert classify_secured_party(("VELOCITY COMML CAPITAL LLC",)) is SecuredPartyKind.LENDER
    assert classify_secured_party(("MCCORMICK PEREZ & ASSOCS",)) is SecuredPartyKind.OTHER
    # Without a program, a program lessor still reads as a solar lessor by its name.
    assert classify_secured_party(("ULTRALIGHT RESIDENTIAL SOLAR LLC",)) is SecuredPartyKind.SOLAR_LESSOR


def test_solar_standing_follows_the_filings_against_the_owners():
    assert solar_record(3, ("ANYONE",), (), PROGRAM).standing is SolarStanding.OUTSIDE_PROGRAM
    none = solar_record(1, ("BUYER ONE",), (_lien("BUYER ONE", _lifecycle("202101010001", "BUYER ONE", "SACTO MUNI UTILY DIST")),), PROGRAM)
    assert none.standing is SolarStanding.NO_FILING and none.filings == ()  # the utility's filing is not a lease
    leased = solar_record(1, ("BUYER ONE",), (_lien("BUYER ONE", _lifecycle("202101010002", "BUYER ONE", "ULTRALIGHT RESIDENTIAL SOLAR LLC")),), PROGRAM)
    assert leased.standing is SolarStanding.LEASE_ON_CURRENT_OWNER and leased.leased and leased.lessor == "ULTRALIGHT RESIDENTIAL SOLAR LLC"
    assert leased.current_filing.number == "202101010002" and "Escrow should carry the lease" in leased.note
    prior = solar_record(1, ("BUYER TWO",), (_lien("BUYER ONE", _lifecycle("202101010002", "BUYER ONE", "ULTRALIGHT RESIDENTIAL SOLAR LLC")),), PROGRAM)
    assert prior.standing is SolarStanding.LEASE_ON_PRIOR_OWNER and prior.current_filing is None and "never terminated" in prior.note
    ended = solar_record(
        1, ("BUYER TWO",),
        (_lien("BUYER ONE", _lifecycle("202101010002", "BUYER ONE", "ULTRALIGHT RESIDENTIAL SOLAR LLC", closed_by="202406270045", closed_on=date(2024, 6, 27))),),
        PROGRAM, sales=(date(2021, 12, 28), date(2024, 6, 27)),
    )
    assert ended.standing is SolarStanding.LEASE_TERMINATED and "on the day of the 2024-06-27 sale" in ended.note
    transferred = solar_record(
        1, ("BUYER TWO",),
        (
            _lien("BUYER ONE", _lifecycle("202101010002", "BUYER ONE", "ULTRALIGHT RESIDENTIAL SOLAR LLC")),
            _lien("BUYER TWO", _lifecycle("202501090176", "BUYER TWO", "ULTRALIGHT RESIDENTIAL SOLAR LLC")),
        ),
        PROGRAM,
    )
    assert transferred.standing is SolarStanding.LEASE_ON_CURRENT_OWNER and transferred.current_filing.owner == "BUYER TWO" and len(transferred.filings) == 2
    from jason.community.solar import shared_filings

    shared = shared_filings({"a": leased, "b": leased, "c": transferred})
    assert shared == {"a": ("b",), "b": ("a",)}
    # A filing on an owner from another time or property does not make the unit leased.
    elsewhere = solar_record(1, ("BUYER TWO",), (_lien("BUYER ONE", _lifecycle("201910160001", "BUYER ONE", "ULTRALIGHT RESIDENTIAL SOLAR LLC"), during=False),), PROGRAM)
    assert elsewhere.standing is SolarStanding.NO_FILING


def test_the_sync_caches_the_lessors_filings_from_the_index(tmp_path: Path):
    calls = []

    class Recorder:
        def search(self, *, name, filing, rows, session=None, fetch=None):
            calls.append((name, filing))
            if name == "ULTRALIGHT" and filing is Filing.UCC_FINANCING:
                return (
                    IndexedInstrument("202009220499", date(2020, 9, 22), "0499", "368", "UCC FINANCING STATEMENT", ("(R) QUILL JENNA", "(E) ULTRALIGHT RESIDENTIAL SOLAR LLC"), "a"),
                    IndexedInstrument("202009220500", date(2020, 9, 22), "0500", "368", "UCC FINANCING STATEMENT", ("(R) SOMEONE ELSE", "(E) ULTRALIGHT AVIATION LLC"), "b"),
                )
            if name == "ULTRALIGHT" and filing is Filing.UCC_TERMINATION:
                return (IndexedInstrument("202211101191", date(2022, 11, 10), "1191", "372", "UCC TERMINATION", ("(R) ULTRALIGHT RESIDENTIAL SOLAR LLC", "(E) RAFTER SETH"), "c"),)
            return ()

    with IndexCache(tmp_path / "index-cache.db") as cache:
        result = sync_solar(cache, Recorder(), PROGRAM)
        assert result.searched == 4 and result.rows == 2 and result.added == 2 and not result.errors
        stored = cache.get("202009220499")
        assert stored is not None and stored.filing_code == "368" and stored.grantees == ("ULTRALIGHT RESIDENTIAL SOLAR LLC",)
        assert cache.get("202009220500") is None  # not a lessor
        assert cache.cached_search("ULTRALIGHT|368|lessor||") == (False, ("202009220499",))
        again = sync_solar(cache, Recorder(), PROGRAM)
        assert again.added == 0 and again.rows == 2
    assert len(calls) == 8 and "searched=4" in result.summary()


def _step(order, number, process, grantees, *, price=None, developer="", reassesses=True):
    recorded = date(int(number[:4]), int(number[4:6]), int(number[6:8]))
    return HistoryStep(order, number, recorded, ("SELLER",), grantees, (), process, True, reassesses, developer, price, None, None, False, None, None, None, "handoff", "", "")


def test_the_pages_state_the_solar_standing():
    record = solar_record(1, ("BUYER ONE",), (_lien("BUYER ONE", _lifecycle("202101010002", "BUYER ONE", "ULTRALIGHT RESIDENTIAL SOLAR LLC")),), PROGRAM)
    steps = (_step(1, "202012010001", "developer closing", ("BUYER ONE",), price=30_000_000, developer="Watt"),)
    item = ParcelHistory("1", "A ST", None, 1, None, "", "Watt", steps[-1].number, steps[-1].recorded, (), steps, (), (), True, 2021, 2025, solar=record)
    text = parcel_markdown(item)
    assert "## Solar" in text and "- **Standing** leased: the lessor's filing stands against the current owner" in text
    assert "- **Lease filing** 202101010002 recorded 2021-01-01 by ULTRALIGHT RESIDENTIAL SOLAR LLC against BUYER ONE" in text
    assert "| 2021-01-01 | 368 UCC FINANCING STATEMENT 202101010002 | ULTRALIGHT RESIDENTIAL SOLAR LLC | BUYER ONE | open |  | yes |" in text
    outside = ParcelHistory("2", "B ST", None, 3, None, "", "John Laing Homes", steps[-1].number, steps[-1].recorded, (), steps, (), (), True, 2021, 2025,
                            solar=solar_record(3, ("BUYER ONE",), (), PROGRAM))
    page = solar_markdown((item, outside), PROGRAM, title="Solar")
    assert page.startswith("# Solar\n\nshared solar. Developer: Watt. Buildings 1, 2.")
    assert "| lease on current owner | 1 |" in page
    assert "| 1 | [A ST](1.md) | BUYER ONE | lease on current owner | ULTRALIGHT RESIDENTIAL SOLAR LLC | 202101010002 | 2021-01-01 |  |" in page
    assert "1 units in the other buildings are outside the program" in page
