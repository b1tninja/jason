from datetime import date

from jason.community.index_cache import (
    IndexCache,
    _query_name,
    backfill_empty_kinds,
    builder_leaf,
    chain_ready,
    conveyance,
    descend,
    find_meets,
    keeps_developer,
    name_keeps,
)
from jason.community.recorder import (
    Conveyance,
    FiledInstrument,
    IndexSession,
    Sacramento,
    succession,
)
from jason.mcp.index import recorder_descend
from mystique.developers import DEVELOPERS

_SESSION = IndexSession("issued-key", "issued-password")

_DOCS = {
    "202111021139": ("11/2/2021", "685", "(R) PREWITT GIDEON<br/>(E) HARROW JUNO"),
    "201908130646": ("8/13/2019", "685", "(R) MERROW LARK<br/>(E) PREWITT GIDEON"),
    "201802221332": ("2/22/2018", "685", "(R) HALDEN NELL MARIE<br/>(E) MERROW LARK"),
    "200709281712": ("9/28/2007", "685", "(R) WL HOMES LLC<br/>(E) HALDEN NELL MARIE"),
    "200709281711": ("9/28/2007", "306", "(R) WL HOMES LLC<br/>(E) WL HOMES LLC"),
    "200709281713": ("9/28/2007", "230", "(R) HALDEN NELL MARIE<br/>(E) JOHN LAING MTG L P"),
    "201704101004": ("4/10/2017", "685", "(R) WL HOMES INVS LLC<br/>(E) HAWKRIDGE LAZLO R JR"),
    "201203270988": ("3/27/2012", "685", "(R) FEDERAL NATL MTG ASSN<br/>(E) QUILLFEATHER TAMSIN P"),
}


def _fetch(url, params, headers):
    if "GetMinMaxDate" in url:
        return {"MinimumDate": "01/01/1965", "MaximumDate": "12/31/2026"}
    if "GetDocumentDetails" in url:
        return {"DocumentSummary": {}}
    if "GetNamesForPagination" in url:
        return {"NamesForPagination": []}
    if "GetSearchResults" not in url:
        raise AssertionError(url)
    if int(params.get("StartRow") or "0") > 0:
        return {"ResultCount": 0, "SearchResults": []}
    number = params.get("DocNumberFrom") or ""
    if number:
        row = _DOCS.get(number)
        if row is None:
            return {"ResultCount": 0, "SearchResults": []}
        return {"ResultCount": 1, "SearchResults": [_row(number, *row)]}
    query = params.get("LastName") or ""
    code = params.get("FilingCode") or ""
    found = []
    for doc, (recorded, filing, names) in _DOCS.items():
        parties = [part[4:] for part in names.split("<br/>")]
        if code and code != filing:
            continue
        if query and any(party.startswith(query) for party in parties):
            found.append(_row(doc, recorded, filing, names))
    return {"ResultCount": len(found), "SearchResults": found}


def _row(number, recorded, filing, names):
    return {
        "ID": number,
        "PrimaryDocNumber": number,
        "DocumentDate": recorded,
        "FilingCode": filing,
        "Names": names,
    }


def _queries(fetch):
    seen: list[tuple[str, str]] = []

    def wrapped(url, params, headers):
        if "GetSearchResults" in url and not params.get("DocNumberFrom"):
            seen.append((params.get("LastName") or "", params.get("FilingCode") or ""))
        return fetch(url, params, headers)

    return seen, wrapped


def test_a_name_keeps_the_same_words_and_not_an_extra_one():
    assert name_keeps("BRAMBLETON VESNA", "BRAMBLETON VESNA")
    assert name_keeps("WL HOMES", "WL HOMES LLC")
    assert name_keeps("WATT COMMUNITIES AT MYSTIQUE", "WATT COMMUNITIES AT MYSTIQUE LLC")
    assert not name_keeps("FABLE OTTILIE", "FABLE OTTILIE U")
    assert not name_keeps("WEXMOOR DAGNY T", "WEXMOOR DAGNY T T")
    assert not name_keeps("WEXMOOR DAGNY T T", "WEXMOOR DAGNY T")
    assert not name_keeps("LARKHAVEN RAGNA P JR", "LARKHAVEN RAGNA P")
    assert not name_keeps("LARKHAVEN RAGNA P JR", "LARKHAVEN URSA M")
    assert not name_keeps("CAYMUS CAPITAL RENTAL FUND I LLC", "CAYMUS CAPITAL RENTAL FUND LLC")
    assert _query_name("CAYMUS CAPITAL RENTAL FUND I LLC") == "CAYMUS CAPITAL RENTAL FUND I"
    assert _query_name("WEXMOOR DAGNY T T") == "WEXMOOR DAGNY T T"
    assert _query_name("LARKHAVEN RAGNA P JR") == "LARKHAVEN RAGNA P JR"
    assert keeps_developer("WL HOMES LLC", DEVELOPERS)
    assert not keeps_developer("WL HOMES INVS LLC", DEVELOPERS)
    assert not keeps_developer("WATT COMMUNITIES LLC", DEVELOPERS)


def test_a_chain_is_ready_when_each_later_deed_has_one_prior():
    ready = succession(
        (
            Conveyance("201802221332", date(2018, 2, 22), ("HALDEN NELL MARIE",), ("MERROW LARK",)),
            Conveyance("200709281712", date(2007, 9, 28), ("WL HOMES LLC",), ("HALDEN NELL MARIE",)),
        ),
        developers=DEVELOPERS,
    )
    assert chain_ready(ready)
    branched = succession(
        (
            Conveyance("201203270988", date(2012, 3, 27), ("ALICE",), ("BOB",)),
            Conveyance("200709281712", date(2007, 9, 28), ("WL HOMES LLC",), ("ALICE",)),
            Conveyance("200809110902", date(2008, 9, 11), ("JOHN LAING HOMES",), ("ALICE",)),
        ),
        developers=DEVELOPERS,
    )
    assert not chain_ready(branched)
    gap = succession(
        (Conveyance("201203270988", date(2012, 3, 27), ("ALICE",), ("BOB",)),),
        developers=DEVELOPERS,
    )
    assert not chain_ready(gap)


def test_a_citation_and_a_handoff_meet_in_the_middle():
    current = {
        "2": FiledInstrument("2", date(2012, 1, 1), "fee", ("ALICE",), ("BOB",), ("1",)),
    }
    developer = {
        "1": FiledInstrument("1", date(2010, 1, 1), "fee", ("WL HOMES LLC",), ("ALICE",)),
    }
    meets = find_meets(current, developer, {"2": ""}, {"1": ""})
    kinds = {item.kind for item in meets}
    assert kinds == {"citation", "handoff"}
    assert meets[0].numbers == ("2", "1")
    uncited = {
        "2": FiledInstrument("2", date(2012, 1, 1), "fee", ("ALICE",), ("BOB",)),
    }
    other = {
        "1": FiledInstrument("1", date(2010, 1, 1), "fee", ("WL HOMES LLC",), ("CARL",)),
    }
    assert find_meets(uncited, other, {"2": ""}, {"1": ""}) == ()


def test_leaf_one_is_the_developer_grant_and_caches_every_row(tmp_path):
    queries, fetch = _queries(_fetch)
    with IndexCache(tmp_path / "index-cache.db") as cache:
        found = builder_leaf(
            Sacramento.county_recorder,
            cache,
            currents={"20111700170005": "201802221332"},
            developers=DEVELOPERS,
            after=date(2007, 9, 26),
            leaf=1,
            session=_SESSION,
            fetch=fetch,
        )
        assert "200709281712" in found.sales
        assert "201704101004" not in found.sales
        assert cache.get("201704101004") is not None
        assert "not a pinned developer grantor" in cache.notes("201704101004")
        assert cache.get("200709281711") is not None
        assert "same day as 200709281712" in cache.notes("200709281711")
        assert any(item.kind == "handoff" and item.developer == "200709281712" for item in found.meets)
        assert cache.apn("200709281712") == "20111700170005"
        assert not any(query.startswith("HALDEN") for query, _code in queries)


def test_leaf_two_walks_each_buyer_once_across_every_sale(tmp_path):
    queries, fetch = _queries(_fetch)
    with IndexCache(tmp_path / "index-cache.db") as cache:
        first = builder_leaf(
            Sacramento.county_recorder,
            cache,
            currents={"20111700170005": "202111021139"},
            developers=DEVELOPERS,
            after=date(2007, 9, 26),
            leaf=1,
            session=_SESSION,
            fetch=fetch,
        )
        assert first.meets == ()
        assert not any(query.startswith("HALDEN") for query, _code in queries)
        second = builder_leaf(
            Sacramento.county_recorder,
            cache,
            currents={"20111700170005": "202111021139"},
            developers=DEVELOPERS,
            after=date(2007, 9, 26),
            leaf=2,
            session=_SESSION,
            fetch=fetch,
        )
        assert "201802221332" in second.reached
        assert any(query.startswith("HALDEN") for query, _code in queries)
        assert not any(query.startswith("MERROW") for query, _code in queries)


def test_a_search_caches_rows_that_do_not_match_the_party(tmp_path):
    with IndexCache(tmp_path / "index-cache.db") as cache:
        cache.put(FiledInstrument("1", date(2010, 1, 1), "fee", ("A",), ("B",)))
        cache.note("1", "other community")
        cache.note("1", "other community")
        cache.set_apn("1", "201-1170-017-0005")
        assert cache.notes("1") == ("other community", "on parcel 20111700170005")
        assert cache.apn("1") == "20111700170005"


def test_the_walk_meets_after_builder_leaves_then_one_current_leaf(tmp_path):
    queries, fetch = _queries(_fetch)
    with IndexCache(tmp_path / "index-cache.db") as cache:
        first = descend(
            Sacramento.county_recorder,
            cache,
            current=("202111021139",),
            developers=DEVELOPERS,
            after=date(2007, 9, 26),
            depth=1,
            developer_depth=1,
            session=_SESSION,
            fetch=fetch,
        )
        assert first.meets == ()
        assert "200709281712" in first.developer
        assert "201704101004" not in first.developer
        assert not any(query.startswith("HALDEN") for query, _code in queries)
        second = descend(
            Sacramento.county_recorder,
            cache,
            current=("202111021139",),
            developers=DEVELOPERS,
            after=date(2007, 9, 26),
            depth=3,
            developer_depth=2,
            session=_SESSION,
            fetch=fetch,
        )
        assert second.meets
        assert any(item.developer == "201802221332" or item.current == "201802221332" for item in second.meets)
        calls = len(queries)
        third = descend(
            Sacramento.county_recorder,
            cache,
            current=("202111021139",),
            developers=DEVELOPERS,
            after=date(2007, 9, 26),
            depth=3,
            developer_depth=2,
            session=_SESSION,
            fetch=fetch,
        )
        assert len(queries) == calls
        assert third.meets
        blocked = descend(
            Sacramento.county_recorder,
            cache,
            current=("202111021139",),
            developers=DEVELOPERS,
            after=date(2007, 9, 26),
            depth=1,
            developer_depth=1,
            exclude=frozenset({"200709281712"}),
            session=_SESSION,
            fetch=fetch,
        )
        assert "200709281712" not in blocked.developer


def test_a_lender_is_not_searched(tmp_path):
    queries, fetch = _queries(_fetch)
    with IndexCache(tmp_path / "index-cache.db") as cache:
        found = descend(
            Sacramento.county_recorder,
            cache,
            current=("201203270988",),
            developers=DEVELOPERS,
            after=date(2007, 9, 26),
            depth=1,
            developer_depth=0,
            session=_SESSION,
            fetch=fetch,
        )
    assert found.meets == ()
    assert not any("FEDERAL" in query for query, _code in queries)


def test_a_wide_name_caches_the_page_and_is_not_walked(tmp_path):
    docs = {
        "201501150001": ("1/15/2015", "685", "(R) QUILLFEATHER TAMSIN P<br/>(E) LATER BUYER"),
    }

    def fetch(url, params, headers):
        if "GetMinMaxDate" in url:
            return {"MinimumDate": "01/01/1965", "MaximumDate": "12/31/2026"}
        if "GetDocumentDetails" in url:
            return {"DocumentSummary": {}}
        if "GetNamesForPagination" in url:
            return {"NamesForPagination": []}
        number = params.get("DocNumberFrom") or ""
        if number:
            row = docs.get(number)
            if row is None:
                return {"ResultCount": 0, "SearchResults": []}
            return {"ResultCount": 1, "SearchResults": [_row(number, *row)]}
        if int(params.get("StartRow") or "0") > 0:
            return {"ResultCount": 0, "SearchResults": []}
        query = params.get("LastName") or ""
        if "QUILLFEATHER" not in query:
            return {"ResultCount": 0, "SearchResults": []}
        rows = [
            _row(f"20100101{index:04d}", "1/1/2010", "685", "(R) OTHER PERSON<br/>(E) QUILLFEATHER TAMSIN P")
            for index in range(41)
        ]
        return {"ResultCount": 80, "SearchResults": rows}

    with IndexCache(tmp_path / "index-cache.db") as cache:
        found = descend(
            Sacramento.county_recorder,
            cache,
            current=("201501150001",),
            developers=DEVELOPERS,
            after=date(2007, 9, 26),
            depth=1,
            developer_depth=0,
            limit=40,
            session=_SESSION,
            fetch=fetch,
        )
        assert found.current == ("201501150001",)
        assert "201001010000" not in found.current
        wide = [
            row
            for row in cache._conn.execute("SELECT key, wide, numbers FROM searches").fetchall()
            if "QUILLFEATHER" in row["key"]
        ]
        assert wide
        assert all(row["wide"] for row in wide)
        assert cache.get("201001010000") is not None
        assert cache.count() > 1


def test_recorder_descend_rejects_a_short_number():
    found = recorder_descend("1234")
    assert found["meets"] == []
    assert "twelve digits" in found["error"]


def test_backfill_classifies_a_notice_and_keeps_the_filing(tmp_path):
    def fetch(url, params, headers):
        if "GetMinMaxDate" in url or "GetSecureKey" in url:
            return {"MinimumDate": "01/01/1965", "MaximumDate": "12/31/2026", "EncryptedKey": "k", "Password": "p"}
        if "GetDocumentDetails" in url:
            return {
                "DocumentSummary": {
                    "DocumentNumber": "200709260228",
                    "DocumentDate": "9/26/2007",
                    "DocumentStatus": "Active",
                    "Pages": 1,
                    "APN": "Reference",
                    "FilingCodes": [{"FilingCodeName": "306", "Description": "NOTICE OF COMPLETION"}],
                }
            }
        if "GetNamesForPagination" in url:
            return {
                "NamesForPagination": [
                    {"Fullname": "WL HOMES LLC", "NameTypeDesc": "Grantor", "CrossRefDocNumber": ""},
                ]
            }
        if params.get("DocNumberFrom") == "200709260228":
            return {
                "ResultCount": 1,
                "SearchResults": [{
                    "ID": "1",
                    "PrimaryDocNumber": "200709260228",
                    "DocumentDate": "9/26/2007",
                    "FilingCode": "306",
                    "Names": "(R) WL HOMES LLC",
                }],
            }
        return {"ResultCount": 0, "SearchResults": []}

    with IndexCache(tmp_path / "index-cache.db") as cache:
        cache.put(FiledInstrument("200709260228", date(2007, 9, 26), "", ("WL HOMES LLC",), ()))
        assert cache.empty_kind_numbers() == ("200709260228",)
        counts = backfill_empty_kinds(
            Sacramento.county_recorder,
            cache,
            developers=DEVELOPERS,
            session=_SESSION,
            fetch=fetch,
        )
        item = cache.get("200709260228")
        assert item is not None
        assert item.kind == "notice"
        assert item.filing_code == "306"
        assert counts.get("notice") == 1
        assert "notice of completion" in " ".join(cache.notes("200709260228")).lower()


def test_a_re_recorded_developer_grant_is_a_step_and_not_a_second_root():
    from jason.community.recorder import ChainStep, OwnershipHistory

    first = Conveyance("202112281312", date(2021, 12, 28), ("WATT COMMUNITIES AT MYSTIQUE LLC",), ("KETTLEBY EMRYS", "SALTMARSH CORVINA"))
    again = Conveyance("202201200309", date(2022, 1, 20), ("WATT COMMUNITIES AT MYSTIQUE LLC",), ("KETTLEBY EMRYS", "SALTMARSH CORVINA"))
    ready = OwnershipHistory("20111700250021", (ChainStep(again, ("202112281312",)), ChainStep(first)), DEVELOPERS)
    assert chain_ready(ready)
    two_roots = OwnershipHistory("20111700250021", (ChainStep(again), ChainStep(first)), DEVELOPERS)
    assert not chain_ready(two_roots)
