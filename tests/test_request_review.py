"""Request review against the local document catalog (no network)."""

from __future__ import annotations

from jason.catalog import PayhoaCatalog
from jason.tasks.request_review import (
    DEFAULT_TAG_COLOR,
    ReviewItem,
    review_requests,
    significant_words,
)


ORG = 1


class _FakeClient:
    def __init__(self) -> None:
        self.tag_calls: list[tuple] = []
        self.submission_details: dict[int, dict] = {}

    def tag_submissions(self, org_id, submission_ids, value, *, color, display=None):
        self.tag_calls.append((org_id, list(submission_ids), value, color, display))
        return []

    def get_form_submission(self, org_id, submission_id):
        return self.submission_details[submission_id]


def _seed_open_request(
    catalog: PayhoaCatalog,
    *,
    request_id: int = 100,
    form_name: str = "Maintenance Request",
    status: str = "pending",
    title: str = "Fence leaning",
    message: str = "The backyard fence is leaning after the wind.",
    unit_id: int = 10,
    unit_title: str = "Lot 10",
) -> None:
    catalog.upsert_units(
        ORG,
        [
            {
                "id": unit_id,
                "title": unit_title,
                "address": {
                    "line1": "10 Main",
                    "city": "Sacramento",
                    "region": "CA",
                    "postalCode": "95814",
                },
            }
        ],
    )
    answers = [
        {
            "answer": title,
            "question": {"label": "Title", "type": "input"},
        },
        {
            "answer": f"<p>{message}</p>",
            "question": {"label": "Message", "type": "textarea"},
        },
    ]
    catalog.upsert_requests(
        ORG,
        [
            {
                "id": request_id,
                "formId": 7,
                "unitId": unit_id,
                "status": status,
                "createdAt": "2026-03-01",
                "answers": answers,
                "unit": {"id": unit_id, "title": unit_title},
            }
        ],
        form_names={7: form_name},
    )


def _seed_docs(catalog: PayhoaCatalog, rows: list[tuple[int, str, str]]) -> None:
    catalog.upsert_documents(
        ORG,
        [
            {
                "id": doc_id,
                "fileName": name,
                "path": path,
                "directory": False,
                "public": 1,
                "fileSize": 1,
            }
            for doc_id, name, path in rows
        ],
    )


def test_significant_words_skips_short_and_stopwords():
    assert "fence" in significant_words("The fence needs work please")
    assert "needs" not in significant_words("The fence needs work please")
    assert "the" not in significant_words("The fence")


def test_review_matches_document_name_word_and_quotes_request(tmp_path):
    catalog = PayhoaCatalog(tmp_path / "c.db")
    _seed_open_request(catalog)
    _seed_docs(
        catalog,
        [
            (1, "Fence Guidelines.pdf", "Governing Documents/Fence Guidelines.pdf"),
            (2, "Budget.pdf", "Financials/Budget.pdf"),
        ],
    )
    items = review_requests(catalog, _FakeClient(), ORG)
    assert len(items) == 1
    item = items[0]
    assert isinstance(item, ReviewItem)
    assert item.request_id == 100
    assert item.form_name == "Maintenance Request"
    assert item.unit == "Lot 10"
    assert item.quote == "Fence leaning"
    assert item.tag_applied is False
    assert len(item.documents) == 1
    assert item.documents[0].file_name == "Fence Guidelines.pdf"
    assert item.documents[0].path == "Governing Documents/Fence Guidelines.pdf"
    assert "Fence Guidelines.pdf" in item.document_note
    catalog.close()


def test_review_reports_no_document_match(tmp_path):
    catalog = PayhoaCatalog(tmp_path / "c.db")
    _seed_open_request(
        catalog,
        title="Pool heater noise",
        message="The heater rattles at night.",
    )
    _seed_docs(
        catalog,
        [(1, "CCRs.pdf", "Governing Documents/CCRs.pdf")],
    )
    items = review_requests(catalog, _FakeClient(), ORG)
    assert items[0].documents == ()
    assert items[0].document_note == "no document match"
    catalog.close()


def test_skips_closed_statuses_and_other_forms(tmp_path):
    catalog = PayhoaCatalog(tmp_path / "c.db")
    _seed_open_request(catalog, request_id=1, status="pending")
    _seed_open_request(
        catalog,
        request_id=2,
        status="complete",
        title="Done fence",
        message="Already finished.",
    )
    _seed_open_request(
        catalog,
        request_id=3,
        status="Approved",
        form_name="Architectural Request",
        title="Patio fence",
        message="Paint the fence.",
    )
    catalog.upsert_requests(
        ORG,
        [
            {
                "id": 4,
                "formId": 9,
                "unitId": 10,
                "status": "pending",
                "createdAt": "2026-03-02",
                "answers": [
                    {
                        "answer": "Name fix",
                        "question": {"label": "Title", "type": "input"},
                    }
                ],
            }
        ],
        form_names={9: "General Request"},
    )
    _seed_docs(
        catalog,
        [(1, "Fence Rules.pdf", "Governing Documents/Fence Rules.pdf")],
    )
    items = review_requests(catalog, _FakeClient(), ORG)
    assert [i.request_id for i in items] == [1]
    catalog.close()


def test_apply_tag_records_client_call(tmp_path):
    catalog = PayhoaCatalog(tmp_path / "c.db")
    _seed_open_request(catalog)
    client = _FakeClient()
    items = review_requests(
        catalog,
        client,
        ORG,
        apply_tag="Board review",
        tag_color=DEFAULT_TAG_COLOR,
    )
    assert items[0].tag_applied is True
    assert client.tag_calls == [
        (ORG, [100], "Board review", DEFAULT_TAG_COLOR, None)
    ]
    catalog.close()


def test_no_tag_when_apply_tag_omitted(tmp_path):
    catalog = PayhoaCatalog(tmp_path / "c.db")
    _seed_open_request(catalog)
    client = _FakeClient()
    items = review_requests(catalog, client, ORG)
    assert items[0].tag_applied is False
    assert client.tag_calls == []
    catalog.close()


def test_fetches_submission_when_catalog_lacks_message(tmp_path):
    catalog = PayhoaCatalog(tmp_path / "c.db")
    catalog.upsert_units(ORG, [{"id": 10, "title": "Lot 10"}])
    catalog.upsert_requests(
        ORG,
        [
            {
                "id": 55,
                "formId": 7,
                "unitId": 10,
                "status": "pending",
                "createdAt": "2026-04-01",
            }
        ],
        form_names={7: "Architectural Request"},
    )
    _seed_docs(
        catalog,
        [(1, "Paint Policy.pdf", "Governing Documents/Paint Policy.pdf")],
    )
    client = _FakeClient()
    client.submission_details[55] = {
        "id": 55,
        "answers": [
            {
                "answer": "Exterior paint",
                "question": {"label": "Title", "type": "input"},
            },
            {
                "answer": "Want to paint the garage door.",
                "question": {"label": "Message", "type": "textarea"},
            },
        ],
    }
    items = review_requests(catalog, client, ORG)
    assert items[0].quote == "Exterior paint"
    assert items[0].documents[0].file_name == "Paint Policy.pdf"
    catalog.close()


def test_limit_caps_results(tmp_path):
    catalog = PayhoaCatalog(tmp_path / "c.db")
    for i in range(3):
        _seed_open_request(
            catalog,
            request_id=200 + i,
            title=f"Fence issue {i}",
            message=f"Fence number {i}",
            unit_id=10,
        )
    items = review_requests(catalog, _FakeClient(), ORG, limit=2)
    assert len(items) == 2
    catalog.close()
