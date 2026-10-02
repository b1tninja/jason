"""Filtered reads against the local PayHOA catalog."""

from jason.catalog import PayhoaCatalog


def test_search_requests_filters_status_form_and_text(tmp_path):
    catalog = PayhoaCatalog(tmp_path / "payhoa.db")
    catalog.upsert_requests(
        1,
        [
            {
                "id": 1,
                "formId": 9,
                "unitId": 4,
                "status": "open",
                "createdAt": "2026-01-02",
                "title": "Gutter leak",
            },
            {
                "id": 2,
                "formId": 9,
                "unitId": 5,
                "status": "complete",
                "createdAt": "2026-01-01",
                "title": "Paint",
            },
        ],
        form_names={9: "Maintenance Request"},
    )
    rows = catalog.search_requests(1, status="open", text="gutter")
    assert [row["id"] for row in rows] == [1]
    assert catalog.get_request(1, 1)["formName"] == "Maintenance Request"
    catalog.close()


def test_search_documents_by_path_and_name(tmp_path):
    catalog = PayhoaCatalog(tmp_path / "payhoa.db")
    catalog.upsert_documents(
        1,
        [
            {
                "id": 10,
                "parentId": 1,
                "directory": False,
                "fileName": "ALPR Policy.pdf",
                "path": "Governing Documents/Policies/ALPR Policy.pdf",
            },
            {
                "id": 11,
                "parentId": None,
                "directory": True,
                "fileName": "Policies",
                "path": "Governing Documents/Policies",
            },
            {
                "id": 12,
                "parentId": 2,
                "directory": False,
                "fileName": "Budget.pdf",
                "path": "Financials/Budget.pdf",
            },
        ],
    )
    rows = catalog.search_documents(
        1, path_prefix="Governing Documents/Policies", name_contains="alpr"
    )
    assert [row["fileName"] for row in rows] == ["ALPR Policy.pdf"]
    catalog.close()
