from datetime import date
from pathlib import Path

import jason.community.filings as filings
from jason.community.association_record import recorded_association
from jason.community.filings import Process, encumbrances, instrument_class
from jason.community.index_cache import IndexCache
from jason.community.recorder import FiledInstrument, Filing, IndexedInstrument
from jason.tasks.sync_liens import MECHANICS_FILINGS, lien_queries, sync_liens
from mystique.developers import DEVELOPERS


def _doc(number, code, grantors=(), grantees=(), cites=()):
    recorded = date(int(number[:4]), int(number[4:6]), int(number[6:8]))
    return FiledInstrument(number, recorded, "", tuple(grantors), tuple(grantees), tuple(cites), code, instrument_class(code).name)


def test_the_mechanics_filings_are_classified():
    lien = instrument_class("389")
    assert lien.process is Process.MECHANICS_LIEN and lien.opens and lien.r_side == "owner" and lien.e_side == "claimant"
    assert instrument_class("635").closes and instrument_class("270").closes and instrument_class("269").closes
    assert instrument_class("385").effect == filings.ESCALATES and instrument_class("651").effect == filings.ADVANCES
    assert instrument_class("232").process is Process.MECHANICS_LIEN and instrument_class("305").family is filings.Family.NOTICE


def test_a_lien_is_released_bonded_sued_or_expired(monkeypatch):
    monkeypatch.setattr(filings, "today_for_status", lambda: date(2021, 6, 1))
    released = encumbrances((
        _doc("202101150001", "389", ("WATT COMMUNITIES AT MYSTIQUE LLC",), ("ACME ROOFING INC",)),
        _doc("202102200002", "635", ("ACME ROOFING INC",), ("WATT COMMUNITIES AT MYSTIQUE LLC",), cites=("202101150001",)),
    ))
    assert len(released) == 1 and released[0].process is Process.MECHANICS_LIEN and released[0].status == "closed" and released[0].closed == date(2021, 2, 20)
    bonded = encumbrances((
        _doc("202101150001", "389", ("WATT COMMUNITIES AT MYSTIQUE LLC",), ("ACME ROOFING INC",)),
        _doc("202102200003", "270", ("WATT COMMUNITIES AT MYSTIQUE LLC",), ("ACME ROOFING INC",)),
    ))
    assert bonded[0].status == "closed" and bonded[0].steps[-1].filing.startswith("270")
    sued = encumbrances((
        _doc("202101150001", "389", ("WATT COMMUNITIES AT MYSTIQUE LLC",), ("ACME ROOFING INC",)),
        _doc("202103010004", "385", ("ACME ROOFING INC",), ("WATT COMMUNITIES AT MYSTIQUE LLC",)),
    ))
    assert len(sued) == 1 and sued[0].status == "in suit" and sued[0].process is Process.MECHANICS_LIEN
    withdrawn = encumbrances((
        _doc("202101150001", "389", ("WATT COMMUNITIES AT MYSTIQUE LLC",), ("ACME ROOFING INC",)),
        _doc("202103010004", "385", ("ACME ROOFING INC",), ("WATT COMMUNITIES AT MYSTIQUE LLC",)),
        _doc("202104010005", "651", ("ACME ROOFING INC",), ("WATT COMMUNITIES AT MYSTIQUE LLC",)),
    ))
    assert withdrawn[0].status == "action withdrawn"
    expired = encumbrances((_doc("202101150001", "389", ("WATT COMMUNITIES AT MYSTIQUE LLC",), ("ACME ROOFING INC",)),))
    assert expired[0].status == "expired" and expired[0].unenforceable_after == date(2021, 4, 15) and expired[0].closed is None
    monkeypatch.setattr(filings, "today_for_status", lambda: date(2021, 3, 1))
    assert expired[0].status == "open"
    extended = encumbrances((
        _doc("202101150001", "389", ("WATT COMMUNITIES AT MYSTIQUE LLC",), ("ACME ROOFING INC",)),
        _doc("202103010006", "232", ("WATT COMMUNITIES AT MYSTIQUE LLC",), ("ACME ROOFING INC",)),
    ))
    monkeypatch.setattr(filings, "today_for_status", lambda: date(2021, 9, 1))
    assert extended[0].status == "open" and extended[0].unenforceable_after == date(2022, 1, 15)
    # A notice of action with a loan and a mechanic's lien both open joins the lien.
    both = encumbrances((
        _doc("202001010001", "230", ("OWNER JANE",), ("BIG BANK",)),
        _doc("202101150001", "389", ("OWNER JANE",), ("ACME ROOFING INC",)),
        _doc("202103010004", "385", ("ACME ROOFING INC",), ("OWNER JANE",)),
    ))
    assert [e.process for e in both] == [Process.LOAN, Process.MECHANICS_LIEN] and both[1].status == "in suit" and both[0].status == "open"


def test_the_association_record_lists_construction_liens_against_the_developers(monkeypatch):
    monkeypatch.setattr(filings, "today_for_status", lambda: date(2026, 1, 1))
    items = (
        _doc("200802151352", "389", ("WL HOMES LLC",), ("GUDGEL ROOFING INC",)),
        _doc("200805010100", "635", ("GUDGEL ROOFING INC",), ("WL HOMES LLC",), cites=("200802151352",)),
        _doc("202101150001", "389", ("WATT COMMUNITIES AT MYSTIQUE LLC",), ("ACME ROOFING INC",)),
        _doc("200712190219", "389", ("ZELNIK ANTON",), ("VEK CONST",)),
    )
    record = recorded_association(items, project="MYSTIQUE", association="MYSTIQUE COMMUNITY", developers=DEVELOPERS)
    assert [(e.debtor[0], e.status) for e in record.construction] == [("WL HOMES LLC", "closed"), ("WATT COMMUNITIES AT MYSTIQUE LLC", "expired")]


def test_the_sync_searches_new_names_and_narrows_wide_ones(tmp_path: Path):
    calls = []

    class Recorder:
        def search(self, *, name, filing=None, limit=0, after=None, before=None, session=None, fetch=None, rows=10, start=0):
            calls.append((name, filing.value if filing else ""))
            if name == "SAMPLE JOHN" and filing is None:
                return tuple(IndexedInstrument(f"20200101{i:04d}", date(2020, 1, 1), f"{i:04d}", "685", "GRANT DEED", ("(R) SAMPLE JOHN", "(E) X")) for i in range(60))
            if name == "SAMPLE JOHN" and filing is Filing.MECHANICS_LIEN:
                return (IndexedInstrument("202101150001", date(2021, 1, 15), "0001", "389", "NOTICE OF CLAIM OR MECHANICS LIEN", ("(R) SAMPLE JOHN", "(E) ACME ROOFING INC")),)
            return ()

        def detail(self, internal_id, *, session=None, fetch=None):
            return None

    def fetch(url, params, headers):
        return {"EncryptedKey": "k", "Password": "p"}

    with IndexCache(tmp_path / "index-cache.db") as cache:
        cache.put_search("DOE JANE||cache||", ("1",), wide=False)  # narrow: already complete
        cache.put_search("SAMPLE JOHN||cache||", (), wide=True)  # wide: never narrowed under the lien filings
        result = sync_liens(cache, Recorder(), ("DOE JANE", "SAMPLE JOHN"), project="MYSTIQUE", association="MYSTIQUE COMMUNITY", developers=DEVELOPERS, fetch=fetch)
        assert result.skipped == 1 and result.narrowed == len(MECHANICS_FILINGS) and result.searched == 0 and not result.errors
        assert cache.get("202101150001") is not None and cache.get("202101150001").filing_code == "389"
        assert cache.cached_search("SAMPLE JOHN|389|cache||") == (False, ("202101150001",))
        again = sync_liens(cache, Recorder(), ("SAMPLE JOHN",), project="MYSTIQUE", association="MYSTIQUE COMMUNITY", developers=DEVELOPERS, fetch=fetch)
        assert again.narrowed == 0  # every filing is keyed now
    assert ("SAMPLE JOHN", "389") in calls and ("DOE JANE", "") not in calls


def test_lien_queries_cover_developers_the_association_and_owners():
    class Step:
        def __init__(self, grantees):
            self.grantees = grantees

    class Item:
        association = False
        steps = (Step(("WL HOMES LLC",)), Step(("MARCHETTI DOMINIC C", "MARCHETTI MIRA S")), Step(("BANK OF AMERICA",)))

    class Community:
        def developers(self):
            return DEVELOPERS

        def index_association(self):
            return "MYSTIQUE COMMUNITY"

    queries = lien_queries(Community(), (Item(),))
    assert "WATT COMMUNITIES AT MYSTIQUE" in queries and "MYSTIQUE COMMUNITY" in queries and "MARCHETTI DOMINIC" in queries and "MARCHETTI MIRA" in queries
    assert "WL HOMES LLC" not in queries and not any("BANK" in q for q in queries)
