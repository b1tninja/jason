from datetime import date

from jason.community.ownership import OwnershipStore
from jason.community.recorder import (
    FiledInstrument,
    Conveyance,
    Filing,
    IndexSession,
    IndexedInstrument,
    NameCandidate,
    Sacramento,
    IndexRole,
    NARROW_FILINGS,
    advances_chain,
    classify_deeds,
    developer_for,
    document_numbers,
    fee_deeds,
    find_deeds,
    handoff_key,
    in_documents,
    OwnerName,
    index_name,
    index_queries,
    merge_candidates,
    name_candidates,
    is_developer,
    name_covers,
    closing_numbers,
    nearby_numbers,
    next_parties,
    other_community,
    owner_restatement,
    party_role,
    buyer_lien,
    instrument_kind,
    relate_instruments,
    same_party,
    succession,
)
from mystique.developers import ASSOCIATION, DEVELOPERS, PROJECT


def test_a_filename_yields_its_document_number():
    assert document_numbers("GD 200709281731.pdf") == ("200709281731",)
    assert document_numbers("GD 202002281258 - Phase 3.pdf") == ("202002281258",)
    assert document_numbers("no stamp here") == ()


def test_the_three_developers_are_pinned():
    assert tuple(developer.name for developer in DEVELOPERS) == (
        "John Laing Homes",
        "Mystique Builders",
        "Watt Communities at Mystique",
    )
    assert developer_for("JOHN LAING HOMES", DEVELOPERS) is developer_for("WL HOMES LLC", DEVELOPERS)
    assert is_developer("WATT COMMUNITIES AT MYSTIQUE", DEVELOPERS)
    assert is_developer("WATT COMMUNIITIES AT MYSTIQUE LLC", DEVELOPERS)
    assert is_developer("MYSTIQUE BLDRS LLC", DEVELOPERS)
    assert is_developer("Mystique Builders, LLC", DEVELOPERS)
    assert not is_developer("WACHOVIA BK", DEVELOPERS)
    assert not is_developer("ALDEA HOMES INC", DEVELOPERS)
    assert not is_developer("DAVID PICK FAMILY PTP L P", DEVELOPERS)
    assert not is_developer("MYSTIQUE COMMUNITY ASSOCIATION", DEVELOPERS)
    assert not is_developer("WATT COMMUNITIES LLC", DEVELOPERS)


def test_a_mystique_builders_grant_reaches_a_developer():
    history = succession(
        (
            Conveyance("201206151335", date(2012, 6, 15), ("MYSTIQUE BLDRS LLC",), ("TESSALY MORGAN D",)),
            Conveyance("201102010742", date(2011, 2, 1), ("DAVID PICK FAMILY PTP L P",), ("MYSTIQUE BLDRS LLC",)),
        ),
        developers=DEVELOPERS,
    )
    assert history.steps[0].priors == ("201102010742",)
    assert history.reached_developer
    assert history.gaps == ("201102010742",)


def test_succession_walks_grantor_back_to_the_developer():
    history = succession(
        (
            Conveyance("201703240140", date(2017, 3, 24), ("ALICE OWNER",), ("BOB BUYER",)),
            Conveyance("201010121565", date(2010, 10, 12), ("WL HOMES LLC",), ("ALICE OWNER",)),
            Conveyance("200709281731", date(2007, 9, 28), ("JOHN LAING HOMES",), ("WL HOMES LLC",)),
        ),
        apn="201-1170-017-0001",
        developers=DEVELOPERS,
    )
    assert history.numbers == ("201703240140", "201010121565", "200709281731")
    assert history.steps[0].priors == ("201010121565",)
    assert history.steps[1].priors == ("200709281731",)
    assert history.steps[2].priors == ()
    assert history.reached_developer
    assert history.gaps == ()


def test_a_cross_reference_is_the_prior_when_the_names_do_not_match():
    history = succession(
        (
            Conveyance(
                "201703240140",
                date(2017, 3, 24),
                ("BANKRUPTCY TRUSTEE",),
                ("BOB BUYER",),
                ("201010121565",),
            ),
            Conveyance("201010121565", date(2010, 10, 12), ("JOHN LAING HOMES",), ("ALICE OWNER",)),
            Conveyance("200605041076", date(2006, 5, 4), ("SOMEONE ELSE",), ("ALICE OWNER",)),
        )
    )
    assert history.steps[0].priors == ("201010121565",)
    assert "200605041076" not in history.steps[0].priors


def test_a_developer_deed_links_to_the_deed_that_conveyed_the_land():
    history = succession(
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
        ),
        developers=DEVELOPERS,
    )
    assert history.steps[0].priors == ("201703240140",)
    assert history.reached_developer
    assert history.gaps == ("201703240140",)


def test_several_earlier_deeds_stay_on_the_step():
    history = succession(
        (
            Conveyance("201703240140", date(2017, 3, 24), ("WL HOMES LLC",), ("BOB BUYER",)),
            Conveyance("201010121565", date(2010, 10, 12), ("JOHN LAING HOMES",), ("WL HOMES LLC",)),
            Conveyance("201010121566", date(2010, 10, 12), ("WATT COMMUNITIES AT MYSTIQUE",), ("WL HOMES LLC",)),
        ),
        developers=DEVELOPERS,
    )
    assert history.steps[0].priors == ("201010121566", "201010121565")
    assert history.reached_developer


def test_the_strongest_handoff_is_the_prior_and_the_line_follows_it():
    # Two co-owners sell; one of them also bought a neighbor's unit alone, later. The deed that vested both of them
    # is the prior; the neighbor's deed only shares a name, and the line skips the side strand.
    history = succession(
        (
            Conveyance("2020-0000300", date(2020, 3, 1), ("SAMPLE PAT Q", "EXAMPLE JO"), ("CASEY SAMPLE",)),
            Conveyance("2012-0000200", date(2012, 2, 1), ("NEIGHBOR SELLER",), ("SAMPLE PAT Q",)),
            Conveyance("2010-0000100", date(2010, 1, 1), ("FIRST OWNER",), ("SAMPLE PAT Q", "EXAMPLE JO")),
            Conveyance("2005-0000050", date(2005, 1, 1), ("EXAMPLE HOMES INC",), ("FIRST OWNER",)),
        )
    )
    newest = history.steps[0]
    assert newest.priors == ("2010-0000100", "2012-0000200")
    assert newest.prior == "2010-0000100"
    assert history.line() == ("2020-0000300", "2010-0000100", "2005-0000050")
    assert history.line("2012-0000200") == ("2012-0000200",)


def test_two_spellings_of_one_seller_do_not_outweigh_an_exact_handoff():
    # The estate deed names the decedent twice (with and without a middle initial). A deed whose one grantee matches
    # both spellings loosely counts once, so the deed that vested the decedent's exact name is the prior, though older.
    history = succession(
        (
            Conveyance("2014-0000400", date(2014, 6, 1), ("SAMPLE PAT", "SAMPLE PAT Q"), ("EXAMPLE HEIR",)),
            Conveyance("2009-0000300", date(2009, 7, 1), ("OTHER SELLER",), ("SAMPLE PAT QUINN",)),
            Conveyance("1988-0000200", date(1988, 6, 1), ("PRIOR OWNER",), ("SAMPLE PAT",)),
        )
    )
    assert history.steps[0].prior == "1988-0000200"


def test_a_cited_number_that_was_not_loaded_stays_open():
    history = succession(
        (
            Conveyance(
                "201703240140",
                date(2017, 3, 24),
                ("BANKRUPTCY TRUSTEE",),
                ("BOB BUYER",),
                ("200709120758",),
            ),
        )
    )
    assert history.steps[0].priors == ()
    assert history.steps[0].cited == ("200709120758",)
    assert history.gaps == ("201703240140",)


def test_history_reads_the_index_and_does_not_search_by_name():
    calls: list[str] = []

    def fetch(url, params, headers):
        calls.append(url)
        if "GetSearchResults" in url:
            assert params["LastName"] == ""
            assert params["DocNumberFrom"] == "201703240140"
            return {
                "ResultCount": 1,
                "SearchResults": [
                    {
                        "ID": "99",
                        "PrimaryDocNumber": "201703240140",
                        "DocumentDate": "3/24/2017",
                        "FilingCode": "685",
                        "Names": "(R) JOHN LAING HOMES<br/>(E) ALICE OWNER",
                    }
                ],
            }
        if "GetDocumentDetails" in url:
            return {
                "DocumentSummary": {
                    "DocumentNumber": "201703240140",
                    "DocumentDate": "03/24/2017",
                    "APN": "Reference",
                    "FilingCodes": [{"FilingCodeName": "685", "Description": "GRANT DEED"}],
                }
            }
        return {
            "NamesForPagination": [
                {"Fullname": "JOHN LAING HOMES", "NameTypeDesc": "Grantor", "CrossRefDocNumber": ""},
                {"Fullname": "ALICE OWNER", "NameTypeDesc": "Grantee", "CrossRefDocNumber": ""},
            ]
        }

    history = Sacramento.county_recorder.history(
        ("GD 201703240140.pdf",),
        apn="201-1170-017-0001",
        developers=DEVELOPERS,
        session=IndexSession("issued-key", "issued-password"),
        fetch=fetch,
    )
    assert history.numbers == ("201703240140",)
    assert history.steps[0].conveyance.grantors == ("JOHN LAING HOMES",)
    assert history.steps[0].conveyance.apn == "201-1170-017-0001"
    assert history.reached_developer
    assert any("GetSearchResults" in url for url in calls)


def test_prior_candidates_keep_only_earlier_grantee_rows():
    def fetch(url, params, headers):
        if "GetMinMaxDate" in url:
            return {"MinimumDate": "01/01/1965", "MaximumDate": "09/27/2026"}
        assert params["LastName"] == "WL HOMES LLC"
        assert params["FilingCode"] == Filing.GRANT_DEED.value
        return {
            "ResultCount": 2,
            "SearchResults": [
                {
                    "PrimaryDocNumber": "201010121565",
                    "DocumentDate": "10/12/2010",
                    "FilingCode": "685",
                    "Names": "(R) JOHN LAING HOMES<br/>(E) WL HOMES LLC",
                },
                {
                    "PrimaryDocNumber": "201103180727",
                    "DocumentDate": "3/18/2011",
                    "FilingCode": "685",
                    "Names": "(R) WL HOMES LLC<br/>(E) MYSTIQUE COMMUNITY ASSN",
                },
            ],
        }

    rows = Sacramento.county_recorder.prior_candidates(
        "WL HOMES LLC",
        before=date(2017, 3, 24),
        session=IndexSession("issued-key", "issued-password"),
        fetch=fetch,
    )
    assert tuple(row.number for row in rows) == ("201010121565",)


def test_resolving_a_buyer_hits_the_watt_sale_to_that_buyer():
    def fetch(url, params, headers):
        if "GetMinMaxDate" in url:
            return {"MinimumDate": "01/01/1965", "MaximumDate": "09/27/2026"}
        assert params["LastName"] == "WATT COMMUNITIES AT MYSTIQUE"
        assert params["FilingCode"] == Filing.GRANT_DEED.value
        return {
            "ResultCount": 4,
            "SearchResults": [
                {
                    "PrimaryDocNumber": "202004200705",
                    "DocumentDate": "04/20/2020",
                    "FilingCode": "685",
                    "Names": "(R) WATT COMMUNITIES AT MYSTIQUE LLC<br/>(R) WATT COMMUNITIES LLC<br/>(E) HALLOWAY SILAS<br/>(E) HALLOWAY SHONA",
                },
                {
                    "PrimaryDocNumber": "202001291167",
                    "DocumentDate": "01/29/2020",
                    "FilingCode": "685",
                    "Names": "(R) WATT COMMUNITIES AT MYSTIQUE LLC<br/>(E) PRESCOTT MAEVE A",
                },
                {
                    "PrimaryDocNumber": "201912010001",
                    "DocumentDate": "12/01/2019",
                    "FilingCode": "685",
                    "Names": "(R) WATT COMMUNITIES LLC<br/>(E) HALLOWAY SILAS",
                },
                {
                    "PrimaryDocNumber": "202305240027",
                    "DocumentDate": "05/24/2023",
                    "FilingCode": "685",
                    "Names": "(R) WATT COMMUNITIES AT MYSTIQUE LLC<br/>(E) HALLOWAY SILAS",
                },
            ],
        }

    rows = Sacramento.county_recorder.forward_hits(
        "WATT COMMUNITIES AT MYSTIQUE",
        "HALLOWAY SILAS",
        before=date(2022, 11, 17),
        developers=DEVELOPERS,
        session=IndexSession("issued-key", "issued-password"),
        fetch=fetch,
    )
    assert tuple(row.number for row in rows) == ("202004200705",)
    placed = Sacramento.county_recorder.forward_hits(
        "WATT COMMUNITIES AT MYSTIQUE",
        "HALLOWAY SILAS",
        before=date(2022, 11, 17),
        developers=DEVELOPERS,
        exclude=frozenset({"202004200705"}),
        session=IndexSession("issued-key", "issued-password"),
        fetch=fetch,
    )
    assert placed == ()


def test_a_buyer_lien_matches_the_grantee_and_a_reconveyance_cites_the_deed_of_trust():
    assert instrument_kind(("694",), ("TRUSTEES DEED UPON SALE",)) == "foreclosure"
    assert instrument_kind(("695",), ("TRUSTEES DEED UPON SALE",)) == "foreclosure"
    assert instrument_kind(("801",), ("DEED IN LIEU OF FORECLOSURE",)) == "foreclosure"
    assert instrument_kind(("685",), ("GRANT DEED",)) == "fee"
    assert instrument_kind(("230",), ("DEED OF TRUST",)) == "lien"
    assert instrument_kind(("239", "238"), ("SUBSTITUTION OF TRUSTEE", "RECONVEYANCE")) == "release"
    assert instrument_kind(("239", "613"), ("SUBSTITUTION OF TRUSTEE", "PARTIAL RECONVEYANCE")) == "release"
    assert instrument_kind(("306",), ("NOTICE OF COMPLETION",)) == "notice"
    assert instrument_kind(("239",), ("SUBSTITUTION OF TRUSTEE",)) == "substitution"
    assert instrument_kind(("531",), ("NOTICE OF DEFAULT",)) == "default"
    assert instrument_kind(("543",), ("NOTICE OF TRUSTEES SALE",)) == "default"
    assert instrument_kind(("531",), ("NOTICE OF DEFAULT AND ELECTION TO SELL UNDER DEED OF TRUST",)) == "default"
    assert instrument_kind(("153",), ("AFFIDAVIT OF DEATH",)) == "death"
    assert instrument_kind((), ("ASSIGNMENT OF DEED OF TRUST",)) == "assignment"
    assert instrument_kind(("681",), ("EASEMENT DEED",)) == "easement"
    grant = FiledInstrument(
        "201203270988",
        date(2012, 3, 27),
        "fee",
        ("FEDERAL NATL MTG ASSN",),
        ("RENWICK HALLE P", "OAKHURST RENWICK"),
    )
    lien = FiledInstrument(
        "201203270989",
        date(2012, 3, 27),
        "lien",
        ("RENWICK HALLE P", "OAKHURST RENWICK"),
        ("AMERICAN INTERNET MTG INC",),
    )
    stranger = FiledInstrument(
        "201203270987",
        date(2012, 3, 27),
        "lien",
        ("WINSLOW DARA",),
        ("WELLS FARGO BK",),
    )
    links = relate_instruments(grant, (lien, stranger))
    assert [item.relation for item in links] == ["subject", "buyer lien", "other parties"]
    assert links[1].grantor_role == "trustor"
    assert links[1].grantee_role == "beneficiary"
    assert buyer_lien(("CAYMUS CAPITAL RENTAL FUND LLC",), ("CAYMUS CAPITAL RENTAL FUND I LLC",)) is False
    release = FiledInstrument(
        "201502170547",
        date(2015, 2, 17),
        "release",
        (),
        ("ELLERY GWYN U",),
        ("200412290375",),
    )
    old = FiledInstrument(
        "200412290375",
        date(2004, 12, 29),
        "lien",
        ("ELLERY GWYN U",),
        ("FUNDING SOLUTIONS BANCORP",),
    )
    beside = FiledInstrument(
        "201502170546",
        date(2015, 2, 17),
        "",
        ("ELLERY GWYN U",),
        (),
        ("200412290375",),
    )
    released = relate_instruments(release, (old, beside), issued=date(2008, 2, 1))
    assert [item.relation for item in released] == ["subject", "released lien", "same citation"]
    assert released[1].before_community
    assert released[1].grantee_role == "beneficiary"


def test_a_restatement_and_a_notice_do_not_advance_the_buyer():
    assert owner_restatement(("YARROW KATHRYN M",), ("YARROW KATHRYN M TRUSTEE", "KATHRYN M YARROW REV FAMILY TRUST"))
    assert not advances_chain(
        "fee",
        ("YARROW KATHRYN M",),
        ("YARROW KATHRYN M TRUSTEE", "KATHRYN M YARROW REV FAMILY TRUST"),
    )
    assert advances_chain("fee", ("WL HOMES LLC",), ("DUVALL RINA MARIE",))
    assert not advances_chain("notice", ("WL HOMES LLC",), ())
    assert not advances_chain("substitution", ("ABERNATHY JERROD",), (),)
    assert not advances_chain("death", ("HOLCOMB PAULA A DEC",), ("HOLCOMB JONAS M",))
    assert other_community("MYSTIQUE COMMUNITY ASSN")
    assert other_community("RIVAGE HOMEOWNERS ASSOCIATION")
    assert other_community("VALENCIA COMMUNITY ASSN")
    assert not advances_chain("fee", ("WL HOMES LLC",), ("MYSTIQUE COMMUNITY ASSN",))


def test_a_shorter_party_name_matches_the_index_form():
    assert same_party("Watt Communities at Mystique", "WATT COMMUNITIES AT MYSTIQUE LLC")
    assert not same_party("WATT COMMUNITIES LLC", "WATT COMMUNITIES AT MYSTIQUE LLC")
    assert not same_party("", "WL HOMES LLC")


def test_an_initial_matches_the_full_middle_name_whichever_side_is_searched():
    from jason.community.filings import same_party

    # The deed spells the owner out; the fixture filing and the judgment use the initial. Same length, either order.
    assert same_party("GARROWAY BENNETT JONATHAN", "GARROWAY BENNETT J") and same_party("GARROWAY BENNETT J", "GARROWAY BENNETT JONATHAN")
    assert same_party("BRANNIGAN BRIDGET KATE", "BRANNIGAN BRIDGET K")
    assert not same_party("SAMPLE JOHN A", "SAMPLE JOHN B") and not same_party("MALLORY MICAH W", "MALLORY MICAH DEAN")
    assert same_party("MALLORY MICAH W", "MALLORY MICAH")


def test_a_filing_that_drops_the_deeds_middle_name_is_a_namesake_risk():
    from jason.community.filings import NameMatch, name_match

    assert name_match("MALLORY MICAH W", "MALLORY MICAH") is NameMatch.BARE
    assert name_match("MALLORY MICAH W", "MALLORY MICAH W") is NameMatch.FULL
    assert name_match("GARROWAY BENNETT JONATHAN", "GARROWAY BENNETT J") is NameMatch.PARTIAL
    # The deed gives two words; the filing cannot say more.
    assert name_match("VO KIA", "VO KIA") is NameMatch.FULL
    assert name_match("WATT COMMUNITIES AT MYSTIQUE LLC", "WATT COMMUNITIES AT MYSTIQUE LLC") is NameMatch.FULL
    assert name_match("MALLORY MICAH W", "MALLORY MICAH DEAN") is None


def test_find_deeds_selects_a_grantor_and_a_grantee():
    deeds = (
        Conveyance(
            "202203180704",
            date(2022, 3, 18),
            ("WATT COMMUNITIES AT MYSTIQUE LLC",),
            ("MYSTIQUE COMMUNITY ASSOCIATION",),
        ),
        Conveyance(
            "202011041576",
            date(2020, 11, 4),
            ("WATT COMMUNITIES AT MYSTIQUE LLC",),
            ("A UNIT BUYER",),
        ),
        Conveyance("201703240140", date(2017, 3, 24), ("ALDEA HOMES INC",), ("WATT COMMUNITIES AT MYSTIQUE LLC",)),
    )
    association = find_deeds(
        deeds,
        grantor="WATT COMMUNITIES AT MYSTIQUE",
        grantee="MYSTIQUE COMMUNITY ASSOCIATION",
    )
    assert tuple(item.number for item in association) == ("202203180704",)


def test_paths_keep_each_branch_walking_backward():
    history = succession(
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
            Conveyance("201310300906", date(2013, 10, 30), ("DAVID PICK FAMILY PTP L P",), ("ALDEA HOMES INC",)),
            Conveyance("201209211820", date(2012, 9, 21), ("DAVID PICK FAMILY PTP L P",), ("ALDEA HOMES INC",)),
        )
    )
    assert history.granted_to("MYSTIQUE COMMUNITY ASSOCIATION")[0].number == "202203180704"
    assert history.paths("202203180704") == (
        ("202203180704", "201703240140", "201310300906"),
        ("202203180704", "201703240140", "201209211820"),
    )
    assert history.paths("missing") == ()


def test_classify_deeds_keeps_search_hits_out_of_the_pins():
    rows = (
        IndexedInstrument("201010121565", date(2010, 10, 12), "1565", "685", "GRANT DEED", ()),
        IndexedInstrument("201103180727", date(2011, 3, 18), "0727", "685", "GRANT DEED", ()),
    )
    findings = classify_deeds(rows, ("GD 201010121565.pdf",))
    assert tuple(row.number for row in findings.pinned) == ("201010121565",)
    assert tuple(row.number for row in findings.candidates) == ("201103180727",)


def test_in_documents_keeps_only_known_numbers():
    rows = (
        IndexedInstrument("201010121565", date(2010, 10, 12), "1565", "685", "GRANT DEED", ()),
        IndexedInstrument("201103180727", date(2011, 3, 18), "0727", "685", "GRANT DEED", ()),
    )
    kept = in_documents(rows, ("GD 201010121565.pdf",))
    assert tuple(row.number for row in kept) == ("201010121565",)


def test_document_numbers_reads_several_filenames():
    assert document_numbers("GD 200709281731.pdf", "GD 200709281731.PDF", "GD 200805280293.PDF") == (
        "200709281731",
        "200805280293",
    )


def test_index_name_is_the_surname_and_given_name():
    assert index_name("CORRAN KENDALL R SR TRUSTEE") == "CORRAN KENDALL"
    assert index_name("ULTRALIGHT RESIDENTIAL SOLAR LLC") == "ULTRALIGHT RESIDENTIAL"


def test_a_ucc_does_not_lead_to_the_lender():
    row = IndexedInstrument(
        "202009220428",
        date(2020, 9, 22),
        "0428",
        "368",
        "UCC FINANCING STATEMENT",
        ("(R) CORRAN ROSALIND", "(E) ULTRALIGHT RESIDENTIAL SOLAR LLC"),
    )
    assert next_parties(row) == ()


def test_trace_searches_the_other_party_and_not_the_developer():
    def fetch(url, params, headers):
        if "GetSearchResults" not in url:
            return {"MinimumDate": "01/01/1965", "MaximumDate": "12/31/2026"}
        query = params["LastName"]
        if query == "DELACROIX VINCENT" and params["Rows"] != "1":
            return {
                "ResultCount": 1,
                "SearchResults": [{
                    "ID": "1",
                    "PrimaryDocNumber": "202205120581",
                    "DocumentDate": "5/12/2022",
                    "FilingCode": "685",
                    "Names": "(R) ESTERHAUS ANIKA<br/>(E) DELACROIX VINCENT JEAN-LUC",
                }],
            }
        if query == "ESTERHAUS ANIKA" and params["Rows"] != "1":
            return {
                "ResultCount": 1,
                "SearchResults": [{
                    "ID": "2",
                    "PrimaryDocNumber": "202011041576",
                    "DocumentDate": "11/4/2020",
                    "FilingCode": "685",
                    "Names": "(R) WATT COMMUNITIES AT MYSTIQUE LLC<br/>(E) ESTERHAUS ANIKA",
                }],
            }
        if query in ("DELACROIX VINCENT", "ESTERHAUS ANIKA"):
            return {"ResultCount": 1, "SearchResults": []}
        raise AssertionError(query)

    results = Sacramento.county_recorder.trace(
        ("DELACROIX VINCENT JEAN-LUC",),
        after=date(2006, 1, 1),
        before=date(2026, 12, 31),
        hops=2,
        developers=DEVELOPERS,
        session=IndexSession("issued-key", "issued-password"),
        fetch=fetch,
    )
    history = succession(fee_deeds(results), developers=DEVELOPERS)
    assert history.step("202205120581").priors == ("202011041576",)
    assert history.reached_developer
    assert all(item.query != "WATT COMMUNITIES" for item in results)


def test_a_wide_name_is_not_followed():
    def fetch(url, params, headers):
        if "GetSearchResults" not in url:
            return {"MinimumDate": "01/01/1965", "MaximumDate": "12/31/2026"}
        return {"ResultCount": 80, "SearchResults": []}

    results = Sacramento.county_recorder.for_parties(
        ("THORNBURY DORIAN",),
        after=date(2006, 1, 1),
        before=date(2026, 12, 31),
        limit=30,
        session=IndexSession("issued-key", "issued-password"),
        fetch=fetch,
    )
    assert results[0].query == "THORNBURY DORIAN"
    assert results[0].wide
    assert results[0].rows == ()


def test_the_chain_is_remembered_by_parcel(tmp_path):
    history = succession(
        (
            Conveyance("201703240140", date(2017, 3, 24), ("ALICE OWNER",), ("BOB BUYER",)),
            Conveyance("200709281731", date(2007, 9, 28), ("JOHN LAING HOMES",), ("ALICE OWNER",)),
        ),
        apn="201-1170-017-0001",
        developers=DEVELOPERS,
    )
    with OwnershipStore(tmp_path / "ownership.db") as store:
        store.remember_history(history)
        stored = store.parcel_history("201-1170-017-0001", developers=DEVELOPERS)
        assert stored is not None
        assert stored.numbers == ("201703240140", "200709281731")
        assert stored.steps[0].priors == ("200709281731",)
        assert stored.reached_developer
        assert store.solved_numbers(developers=DEVELOPERS) == frozenset(
            {"201703240140", "200709281731"}
        )
        open_chain = succession(
            (
                Conveyance(
                    "202111021139",
                    date(2021, 11, 2),
                    ("ADEYEMI TALIA",),
                    ("KERRIGAN ROLAND LEROY LINDQVIST",),
                ),
            ),
            apn="201-1170-017-0005",
            developers=DEVELOPERS,
        )
        store.remember_history(open_chain)
        assert "202111021139" not in store.solved_numbers(developers=DEVELOPERS)


def test_the_index_matches_a_name_from_the_front():
    assert name_covers("MYSTIQUE", "MYSTIQUE PHASE 3")
    assert name_covers("MYSTIQUE", "MYSTIQUE PHAS 8")
    assert name_covers("MYSTIQUE COMMUNITY", "MYSTIQUE COMMUNITY ASSN")
    assert name_covers("MYSTIQUE COMMUNITY", "MYSTIQUE COMMUNITY ASSOCIATION")
    assert not name_covers("MYSTIQUE", "WATT COMMUNITIES AT MYSTIQUE LLC")
    assert party_role(
        "MYSTIQUE",
        project=PROJECT,
        association=ASSOCIATION,
        developers=DEVELOPERS,
    ) is IndexRole.PROJECT
    assert party_role(
        "MYSTIQUE COMMUNITY ASSOC",
        project=PROJECT,
        association=ASSOCIATION,
        developers=DEVELOPERS,
    ) is IndexRole.ASSOCIATION
    assert party_role(
        "MYSTIQUE PHAS 8",
        project=PROJECT,
        association=ASSOCIATION,
        developers=DEVELOPERS,
    ) is IndexRole.PHASE
    assert party_role(
        "MYSTIQUE BLDRS LLC",
        project=PROJECT,
        association=ASSOCIATION,
        developers=DEVELOPERS,
    ) is IndexRole.DEVELOPER
    assert party_role(
        "MYSTIQUE DINING",
        project=PROJECT,
        association=ASSOCIATION,
        developers=DEVELOPERS,
    ) is IndexRole.OTHER


def test_spelling_differences_still_hand_off():
    assert handoff_key("MYSTIQUE COMMUNITY ASSN") == handoff_key("MYSTIQUE COMMUNITY ASSOCIATION")
    assert handoff_key("MYSTIQUE PHAS 8") == handoff_key("MYSTIQUE PHASE 8")
    association = succession(
        (
            Conveyance("201604280702", date(2016, 4, 28), ("MYSTIQUE COMMUNITY ASSOCIATION",), ("A BUYER",)),
            Conveyance("200709281731", date(2007, 9, 28), ("WL HOMES LLC",), ("MYSTIQUE COMMUNITY ASSN",)),
        ),
        developers=DEVELOPERS,
    )
    assert association.steps[0].priors == ("200709281731",)
    kestrel = succession(
        (
            Conveyance("202111301834", date(2021, 11, 30), ("KESTREL ABBOTT C",), ("KESTREL REGAN R",)),
            Conveyance("202102241030", date(2021, 2, 24), ("WATT COMMUNITIES AT MYSTIQUE LLC",), ("KESTREL ABBOTT CHASE",)),
        ),
        developers=DEVELOPERS,
    )
    assert kestrel.steps[0].priors == ("202102241030",)
    typo = succession(
        (
            Conveyance("202102241018", date(2021, 2, 24), ("WATT COMMUNIITIES AT MYSTIQUE LLC",), ("QUAYLE",)),
            Conveyance("201703240140", date(2017, 3, 24), ("ALDEA HOMES INC",), ("WATT COMMUNITIES AT MYSTIQUE LLC",)),
        ),
        developers=DEVELOPERS,
    )
    assert typo.steps[0].priors == ("201703240140",)
    other_watt = succession(
        (
            Conveyance("202003231397", date(2020, 3, 23), ("WATT COMMUNITIES LLC",), ("SOMEONE ELSE",)),
            Conveyance("201703240140", date(2017, 3, 24), ("ALDEA HOMES INC",), ("WATT COMMUNITIES AT MYSTIQUE LLC",)),
        ),
        developers=DEVELOPERS,
    )
    assert other_watt.steps[0].priors == ()


def test_a_completion_notice_is_the_number_before_the_deed():
    assert closing_numbers("202203210713") == ("202203210712", "202203210714")
    assert closing_numbers("201206151335") == ("201206151334", "201206151336")
    assert nearby_numbers("202102241018", before=1) == ("202102241017",)
    assert "202102251017" not in nearby_numbers("202102241018")
    queries = index_queries(PROJECT, ASSOCIATION, DEVELOPERS)
    completions = tuple(item for item in queries if item.filing is Filing.NOTICE_OF_COMPLETION)
    assert completions
    assert all(item.role is IndexRole.DEVELOPER for item in completions)
    assert all(item.name != "MYSTIQUE" for item in completions)
    assert any(item.name == "WL HOMES" for item in completions)
    assert any(item.name == "MYSTIQUE COMMUNITY" and item.filing is None for item in queries)


def test_a_wide_name_can_be_sliced_by_filing():
    def fetch(url, params, headers):
        if "GetSearchResults" not in url:
            return {"MinimumDate": "01/01/1965", "MaximumDate": "12/31/2026"}
        if params["FilingCode"] == "":
            return {"ResultCount": 80, "SearchResults": []}
        if params["FilingCode"] == Filing.GRANT_DEED.value:
            return {
                "ResultCount": 1,
                "SearchResults": [{
                    "PrimaryDocNumber": "202005130602",
                    "DocumentDate": "5/13/2020",
                    "FilingCode": "685",
                    "Names": "(R) WATT COMMUNITIES AT MYSTIQUE LLC<br/>(E) THORNBURY DORIAN DEAN III",
                }],
            }
        return {"ResultCount": 50, "SearchResults": []}

    results = Sacramento.county_recorder.for_parties(
        ("THORNBURY DORIAN",),
        after=date(2006, 1, 1),
        before=date(2026, 12, 31),
        limit=30,
        filings=NARROW_FILINGS,
        session=IndexSession("issued-key", "issued-password"),
        fetch=fetch,
    )
    assert results[0].rows[0].number == "202005130602"
    assert not results[0].wide


def test_owner_names_compare_by_candidate_spelling():
    assert OwnerName("WEXLEY MARISOL GABRIELA PENDLETON") == "PENDLETON WEXLEY MARISOL GABRIELA"
    assert OwnerName("UNDERHILL CONRAD S") == OwnerName("UNDERHILL CONRAD SIMON")
    assert OwnerName("KHOA V TRIEU") == "KHOA VAN TRIEU"
    assert OwnerName("HANH M T LAM FMLY") == "HANH MAI THI LAM FAMILY"
    assert OwnerName("UNDERHILL CONRAD S") != "UNDERHILL DESMOND SIMON"
    assert OwnerName("DUNMORE RYAN PHILLIP") != "DUNMORE BRYAN PHILLIP"
    assert OwnerName("WATT COMMUNITIES LLC") != "WATT COMMUNITIES AT MYSTIQUE LLC"
    history = succession(
        (
            Conveyance("202406010001", date(2024, 6, 1), ("UNDERHILL CONRAD S",), ("A BUYER",)),
            Conveyance("202001010001", date(2020, 1, 1), ("WATT COMMUNITIES AT MYSTIQUE LLC",), ("UNDERHILL CONRAD SIMON",)),
        ),
        developers=DEVELOPERS,
    )
    assert history.steps[0].priors == ("202001010001",)
    reordered = succession(
        (
            Conveyance("202405240538", date(2024, 5, 24), ("WEXLEY MARISOL GABRIELA PENDLETON",), ("WHITCOMBE DIANTHE",)),
            Conveyance("202203160959", date(2022, 3, 16), ("WATT COMMUNITIES AT MYSTIQUE LLC",), ("PENDLETON WEXLEY MARISOL GABRIELA",)),
        ),
        developers=DEVELOPERS,
    )
    assert reordered.steps[0].priors == ("202203160959",)
    try:
        hash(OwnerName("UNDERHILL CONRAD S"))
    except TypeError:
        return
    raise AssertionError("owner names are not hashed")


def test_assessor_abbreviations_stay_candidates():
    trieu = name_candidates(
        "KHOA VAN TRIEU/HANH MAI THI LAM FAMILY LIV TR",
        "KHOA V TRIEU & HANH M T LAM FMLY ETC",
        "LAM HANH M T TR",
        "TRIEU KHOA V TR",
    )
    assert NameCandidate("V", "VAN") in trieu
    assert NameCandidate("M", "MAI") in trieu
    assert NameCandidate("T", "THI") in trieu
    assert NameCandidate("FMLY", "FAMILY") in trieu
    assert all(item.short != "TR" for item in trieu)
    underhill = name_candidates("UNDERHILL CONRAD SIMON", "UNDERHILL CONRAD S")
    assert underhill == (NameCandidate("S", "SIMON"),)
    calloway = name_candidates("CALLOWAY JORDAN WILLIAM", "CALLOWAY JORDAN W")
    assert calloway == (NameCandidate("W", "WILLIAM"),)
    pemberly = name_candidates(
        "OTTO V PEMBERLY REVOCABLE TRUST",
        "PEMBERLY OTTO V TRUSTEE",
        "OTTO V PEMBERLY REVOCABLE TRUST",
    )
    assert pemberly == ()
    dunmore = name_candidates("DUNMORE RYAN PHILLIP/VERA", "DUNMORE BRYAN PHILLIP", "DUNMORE VERA")
    assert dunmore == ()
    merged = merge_candidates(trieu + trieu[:1])
    family = next(item for item in merged if item.short == "FMLY")
    assert family.count == 2
    assert merged[0].count >= merged[-1].count
