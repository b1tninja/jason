from datetime import date

from jason.community.assessor import Parcel, SacramentoCountyAssessor
from jason.community.ownership import OwnershipStore


def test_book_and_page_are_the_recorder_document_number():
    def fetch(url):
        assert url.endswith("/20111700220010")
        return {
            "APN": "20111700220010",
            "FullAddress": "1 MACON DR",
            "DocumentType": "GD",
            "DocumentTypeDescription": "GRANT DEED",
            "DocumentBook": "20190719",
            "DocumentPage": "269",
        }

    parcel = SacramentoCountyAssessor().parcel("20111700220010", fetch=fetch)
    assert parcel is not None
    assert parcel.document_type == "GD"
    assert parcel.document_number == "201907190269"


def test_ownership_follows_the_recorder_row():
    def parcel_fetch(url):
        return {
            "APN": "20111700220010",
            "FullAddress": "1 MACON DR",
            "DocumentType": "GD",
            "DocumentTypeDescription": "GRANT DEED",
            "DocumentBook": "20220318",
            "DocumentPage": "703",
        }

    def recorder_fetch(url, params, headers):
        if "GetSecureKey" in url:
            return {"EncryptedKey": "issued-key", "Password": "issued-password"}
        if "GetSearchResults" in url:
            return {
                "ResultCount": 1,
                "SearchResults": [
                    {
                        "PrimaryDocNumber": "202203180703",
                        "DocumentDate": "03/18/2022",
                        "FilingCode": "685",
                        "ID": "19089460",
                        "Names": "",
                    }
                ],
            }
        return {
            "DocumentSummary": {
                "DocumentNumber": "202203180703",
                "DocumentDate": "03/18/2022",
                "DocumentStatus": "Active",
                "Pages": 4,
                "APN": "20111700220010",
                "FilingCodes": [{"FilingCodeName": "685", "Description": "GRANT DEED"}],
            },
            "NamesForPagination": [
                {"Fullname": "WATT COMMUNITIES AT MYSTIQUE LLC", "NameTypeDesc": "Grantor", "CrossRefDocNumber": ""},
                {"Fullname": "MYSTIQUE COMMUNITY ASSOCIATION", "NameTypeDesc": "Grantee", "CrossRefDocNumber": ""},
            ],
        }

    detail = SacramentoCountyAssessor().ownership(
        "201-1170-022-0010",
        fetch=parcel_fetch,
        recorder_fetch=recorder_fetch,
    )
    assert detail is not None
    assert detail.number == "202203180703"
    assert detail.grantors == ("WATT COMMUNITIES AT MYSTIQUE LLC",)
    assert detail.grantees == ("MYSTIQUE COMMUNITY ASSOCIATION",)


def _parcel(number: str, recorded: date) -> Parcel:
    return Parcel(
        apn="20111700220010",
        address="3044 MACON DR",
        document_type="GD",
        document_type_description="GRANT DEED",
        document_book=number[:8],
        document_page=number[8:].lstrip("0") or "0",
        document_date=recorded,
    )


def test_an_unchanged_document_date_does_not_call_the_recorder(tmp_path):
    parcel = _parcel("202006190506", date(2020, 6, 19))

    def parcel_fetch(url):
        return {
            "APN": parcel.apn,
            "FullAddress": parcel.address,
            "DocumentType": "GD",
            "DocumentTypeDescription": "GRANT DEED",
            "DocumentBook": parcel.document_book,
            "DocumentPage": parcel.document_page,
            "DocumentDate": "2020-06-19T00:00:00",
        }

    def recorder_fetch(url, params, headers):
        raise AssertionError("recorder called")

    with OwnershipStore(tmp_path / "ownership.db") as store:
        store.remember(parcel)
        assert SacramentoCountyAssessor().ownership(
            parcel.apn,
            fetch=parcel_fetch,
            recorder_fetch=recorder_fetch,
            store=store,
        ) is None


def test_an_unchanged_document_date_is_not_a_fetch(tmp_path):
    parcel = _parcel("202006190506", date(2020, 6, 19))
    with OwnershipStore(tmp_path / "ownership.db") as store:
        assert store.changed(parcel) is True
        store.remember(parcel)
        assert store.changed(parcel) is False
        assert store.changed(_parcel("202401010001", date(2024, 1, 1))) is True
