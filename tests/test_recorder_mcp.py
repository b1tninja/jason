from datetime import date

from jason.community.recorder import (
    FilingType,
    IndexParty,
    IndexedInstrument,
    InstrumentDetail,
    NameSearch,
)
from jason.mcp.index import _detail, _priors, _search


class _Index:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def search(self, **kwargs):
        self.calls.append(("search", kwargs))
        return (
            IndexedInstrument(
                "201608110889",
                date(2016, 8, 11),
                "0889",
                "685",
                "GRANT DEED",
                ("(R) MARLO A KESTREL TRUST", "(E) SAMPLE AVERY W"),
                "99",
            ),
        )

    def for_parties(self, names, **kwargs):
        self.calls.append(("for_parties", names, kwargs))
        return (NameSearch("KESTREL MARLO", 1, self.search()),)

    def detail(self, internal_id, **kwargs):
        self.calls.append(("detail", internal_id))
        return InstrumentDetail(
            "201608110889",
            date(2016, 8, 11),
            "Active",
            3,
            "20111700170001",
            (FilingType("685", "GRANT DEED"),),
            (
                IndexParty("MARLO A KESTREL TRUST", "Grantor", "201001010001"),
                IndexParty("SAMPLE AVERY W", "Grantee", ""),
            ),
        )

    def prior_candidates(self, grantor, **kwargs):
        self.calls.append(("priors", grantor, kwargs))
        return self.search()


def test_a_document_search_is_a_hit_and_not_a_pin():
    index = _Index()
    found = _search(index, number="201608110889", name="", text="", filing="", after="", before="", limit=20)
    assert found["hits"][0]["number"] == "201608110889"
    assert found["hits"][0]["grantors"] == ["MARLO A KESTREL TRUST"]
    assert "not a pin" in found["note"]
    assert index.calls[0][0] == "search"


def test_a_name_search_uses_the_narrow_filings():
    index = _Index()
    found = _search(index, number="", name="Kestrel Marlo", text="", filing="", after="", before="", limit=20)
    assert found["query"] == "KESTREL MARLO"
    kind, names, kwargs = index.calls[0]
    assert kind == "for_parties"
    assert names == ("Kestrel Marlo",)
    assert tuple(item.value for item in kwargs["filings"]) == ("685", "689", "368", "372")


def test_detail_returns_the_apn_and_the_cited_number():
    found = _detail(_Index(), "201608110889")
    assert found["found"] is True
    assert found["apn"] == "201-1170-017-0001"
    assert found["crossReferences"] == ["201001010001"]
    assert found["grantors"] == ["MARLO A KESTREL TRUST"]


def test_priors_keep_a_capped_grant_deed_to_that_party():
    class Index:
        def __init__(self) -> None:
            self.kwargs = {}

        def search(self, **kwargs):
            self.kwargs = kwargs
            return (
                IndexedInstrument(
                    "201001010001",
                    date(2010, 1, 1),
                    "0001",
                    "685",
                    "GRANT DEED",
                    ("(R) WL HOMES LLC", "(E) KESTREL MARLO A TR"),
                    "1",
                ),
                IndexedInstrument(
                    "201608110889",
                    date(2016, 8, 11),
                    "0889",
                    "685",
                    "GRANT DEED",
                    ("(R) KESTREL MARLO A TR", "(E) SAMPLE AVERY W"),
                    "2",
                ),
            )

    index = Index()
    found = _priors(index, name="KESTREL MARLO A TR", before="2016-08-11", filing="GRANT_DEED", limit=20)
    assert found["query"] == "KESTREL MARLO"
    assert [hit["number"] for hit in found["hits"]] == ["201001010001"]
    assert index.kwargs["before"] == date(2016, 8, 11)
    assert index.kwargs["limit"] == 20
    assert index.kwargs["filing"].value == "685"


def test_a_trustees_deed_is_a_filing():
    class Index:
        def __init__(self) -> None:
            self.kwargs = {}

        def search(self, **kwargs):
            self.kwargs = kwargs
            return ()

    index = Index()
    found = _priors(index, name="QUARRY PARVIN", before="2012-04-30", filing="694", limit=10)
    assert found["hits"] == []
    assert index.kwargs["filing"].name == "TD"
