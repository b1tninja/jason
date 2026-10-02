from datetime import date

from jason.community.recorder import Filing, IndexSession, Sacramento, expected_companions, parties


def test_sacramento_parses_the_declaration_number():
    parsed = Sacramento.county_recorder.parse("200709120758")
    assert parsed is not None
    assert parsed.number == "200709120758"
    assert parsed.recorded == date(2007, 9, 12)
    assert parsed.sequence == "0758"


def test_a_short_number_is_not_a_sacramento_document():
    assert Sacramento.county_recorder.parse("20070912") is None


def test_index_names_split_into_grantor_and_grantee():
    grantors, grantees = parties(["(R) MYSTIQUE COMMUNITY ASSOCIATION", "(E) JOHN LAING HOMES"])
    assert grantors == ("MYSTIQUE COMMUNITY ASSOCIATION",)
    assert grantees == ("JOHN LAING HOMES",)


def test_assessor_tokens_map_to_the_recorder_filing_code():
    from jason.community.recorder import DocType, conveys, conveys_fee

    assert DocType.GD.token == "GD"
    assert DocType.GD.value == "GRANT DEED/CORP. DEED/GIFT DEED/JNT TEN DEED"
    assert DocType.GD.code == "685"
    assert DocType.QC.value == "QUITCLAIM DEED"
    assert DocType.from_code("689") is DocType.QC
    assert DocType.from_code("694") is DocType.TD
    assert DocType.from_code("695") is DocType.TDSL
    assert conveys_fee("689")
    assert conveys_fee("QC")
    assert conveys_fee("801")
    assert conveys("681")
    assert not conveys_fee("681")
    assert not conveys_fee("EASD")
    assert conveys_fee("DETH")
    assert not conveys_fee("RCNV")
    assert not conveys("230")


def test_annexation_is_a_filing_code():
    assert Filing.DECLARATION_OF_ANNEXATION.value == "320"
    assert Filing.NOTICE_OF_COMPLETION.value == "306"
    assert Filing.DECLARATION.value == "162"
    assert Filing.DEED_OF_TRUST.value == "230"


def test_index_row_uses_the_document_number_and_the_filing_name():
    payload = {
        "SearchResults": [
            {
                "PrimaryDocNumber": "200709120758",
                "FilingCode": "162",
                "Names": "(R) MYSTIQUE COMMUNITY ASSOCIATION<br/>(E) JOHN LAING HOMES",
            }
        ]
    }
    seen = {}

    def fetch(url, params, headers):
        seen["params"] = params
        seen["headers"] = headers
        return payload

    row = Sacramento.county_recorder.search(
        number="200709120758",
        session=IndexSession("issued-key", "issued-password"),
        fetch=fetch,
    )[0]
    assert seen["headers"]["EncryptedKey"] == "issued-key"
    assert seen["params"]["NameTypeID"] == "0"
    assert seen["params"]["DocNumberFrom"] == "200709120758"
    assert seen["params"]["DocNumberTo"] == "200709120758"
    assert row.number == "200709120758"
    assert row.recorded.isoformat() == "2007-09-12"
    assert row.filing_name == "DECLARATION"
    assert row.grantors == ("MYSTIQUE COMMUNITY ASSOCIATION",)
    assert row.grantees == ("JOHN LAING HOMES",)


def test_a_document_range_keeps_the_callers_dates():
    seen = {}

    def fetch(url, params, headers):
        seen["params"] = params
        return {"ResultCount": 0, "SearchResults": []}

    Sacramento.county_recorder.search(
        number="201102010742",
        number_to="201102010769",
        after=date(2011, 2, 1),
        before=date(2011, 2, 1),
        session=IndexSession("issued-key", "issued-password"),
        fetch=fetch,
    )
    assert seen["params"]["DocNumberFrom"] == "201102010742"
    assert seen["params"]["DocNumberTo"] == "201102010769"
    assert seen["params"]["MinRecordedDate"] == "02/01/2011"
    assert seen["params"]["MaxRecordedDate"] == "02/01/2011"


def test_a_second_name_keeps_only_that_party():
    def fetch(url, params, headers):
        return {
            "ResultCount": 2,
            "SearchResults": [
                {
                    "PrimaryDocNumber": "200710291637",
                    "DocumentDate": "10/29/2007",
                    "FilingCode": "685",
                    "Names": "(R) WL HOMES LLC<br/>(E) ALDER CASEY A",
                },
                {
                    "PrimaryDocNumber": "200805300226",
                    "DocumentDate": "5/30/2008",
                    "FilingCode": "685",
                    "Names": "(R) WL HOMES LLC<br/>(E) BRAMBLE MICAH",
                },
            ],
        }

    rows = Sacramento.county_recorder.search(
        name="WL HOMES",
        text="ALDER CASEY A",
        session=IndexSession("issued-key", "issued-password"),
        fetch=fetch,
    )
    assert [row.number for row in rows] == ["200710291637"]
    assert expected_companions("200710291637") == (("200710291636", "306"), ("200710291638", "230"))


def test_a_null_index_body_is_no_rows():
    assert Sacramento.county_recorder.search(
        number="200709120758",
        session=IndexSession("issued-key", "issued-password"),
        fetch=lambda url, params, headers: None,
    ) == ()


def test_detail_reads_filing_types_and_parties():
    def fetch(url, params, headers):
        if "GetDocumentDetails" in url:
            return {
                "DocumentSummary": {
                    "DocumentNumber": "202312060284",
                    "DocumentDate": "12/06/2023",
                    "DocumentStatus": "Active",
                    "Pages": 4,
                    "APN": "Reference",
                    "FilingCodes": [
                        {"FilingCodeName": "220", "Description": "AMENDED RESTRICTION"},
                    ],
                }
            }
        return {
            "NamesForPagination": [
                {"Fullname": "MYSTIQUE COMMUNITY ASSOCIATION", "NameTypeDesc": "Grantor", "CrossRefDocNumber": "200709120758"},
                {"Fullname": "MYSTIQUE COMMUNITY ASSOCIATION", "NameTypeDesc": "Grantee", "CrossRefDocNumber": ""},
            ]
        }

    detail = Sacramento.county_recorder.detail(
        "24098955",
        session=IndexSession("issued-key", "issued-password"),
        fetch=fetch,
    )
    assert detail is not None
    assert detail.filings[0].code == "220"
    assert detail.filings[0].description == "AMENDED RESTRICTION"
    assert detail.pages == 4
    assert detail.grantors == ("MYSTIQUE COMMUNITY ASSOCIATION",)
    assert detail.cross_references == ("200709120758",)


def test_names_page_carries_the_cross_reference():
    payload = {
        "NamesForPagination": [
            {
                "Fullname": "MYSTIQUE COMMUNITY ASSOCIATION",
                "NameTypeDesc": "GRANTEE",
                "CrossRefDocNumber": "200709120758",
            }
        ]
    }
    party = Sacramento.county_recorder.names(
        "513362",
        session=IndexSession("issued-key", "issued-password"),
        fetch=lambda url, params, headers: payload,
    )[0]
    assert party.cross_reference == "200709120758"
    assert party.role == "GRANTEE"
