"""PayHOA requests joined to their email, and drafts for the emailed requests PayHOA lacks."""

from __future__ import annotations

from types import SimpleNamespace

from jason.community import mystique
from jason.community.request_forms import form_for
from jason.community.topics import Topic
from jason.tasks.request_links import _notice_links, _score, create


def _request(**kw) -> dict:
    base = {"id": 1, "form": "Maintenance Request", "unitId": 7, "unit": "3024 MACON DR", "status": "pending",
            "created": "2026-09-11 17:02:00", "updated": "2026-09-11 17:02:00", "completed": None,
            "title": "Garage Door Spring", "message": "The spring broke", "comments": [], "topics": ["maintenance and repairs"]}
    return {**base, **kw}


def test_a_payhoa_notice_joins_the_request_created_within_minutes() -> None:
    requests = [_request(), _request(id=2, form="General Request", created="2026-09-11 17:05:00")]
    threads = {"t1": [{"threadId": "t1", "at": "2026-09-11T17:03:10+00:00", "domains": ["payhoa.com"],
                       "subject": "Maintenance Request Submission"}],
               "t2": [{"threadId": "t2", "at": "2026-09-12T09:00:00+00:00", "domains": ["payhoa.com"],
                       "subject": "Maintenance Request Submission"}]}
    links = _notice_links(requests, threads)
    assert [l["threadId"] for l in links[1]] == ["t1"] and 2 not in links


def test_an_owners_thread_scores_on_topic_words_and_timing() -> None:
    thread = {"subject": "Grindlije garage door", "first": "2026-09-09", "topics": ["maintenance and repairs"]}
    score, reasons = _score(thread, _request())
    assert score >= 4 and any(r.startswith("words") for r in reasons) and "within three days" in reasons
    unrelated = {"subject": "Parking rules", "first": "2026-06-01", "topics": ["parking"]}
    assert _score(unrelated, _request())[0] < 2


def test_a_draft_goes_on_the_form_its_topics_name() -> None:
    forms = mystique().request_forms()
    assert form_for([Topic.PESTS], forms).name == "Maintenance Request"
    assert form_for([Topic.ARCHITECTURE], forms).name == "Architectural Request"
    assert form_for([Topic.PARKING], forms).name == "General Request"


def test_entering_a_draft_sends_its_title_and_message_to_the_forms_questions() -> None:
    sent = {}

    def create_form_submission(org_id, form_id, unit_ids, answers, *, send_notification_to_owner=False):
        sent.update(org=org_id, form=form_id, units=unit_ids, answers=answers, notify=send_notification_to_owner)
        return [999]

    client = SimpleNamespace(create_form_submission=create_form_submission)
    draft = {"formId": 55146, "unitId": 606944, "title": "Wasps - Building 3", "message": "draft message"}
    assert create(client, 27889, mystique(), draft, message="Wasps nesting above the entry") == [999]
    assert sent["form"] == 55146 and sent["units"] == [606944] and not sent["notify"]
    assert sent["answers"] == [{"formQuestionId": 194100, "answer": "Wasps - Building 3"},
                               {"formQuestionId": 194101, "answer": "Wasps nesting above the entry"}]
