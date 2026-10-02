"""A definition made in PayHOA's form builder, its submissions read back by field, and a signed-in submission matched to
its owner without guessing."""

import json
import sqlite3

from jason.community.form_render import payhoa_questions
from jason.community.spec import spec_module
from jason.tasks.payhoa_forms import create, questions_for, request_body, submission_answers

OWNER_INFO = spec_module("forms").OWNER_INFO


def test_the_definition_becomes_builder_questions():
    kinds = {q.field: q.kind for q in payhoa_questions(OWNER_INFO)}
    assert kinds["delivery.by-mail"] == kinds["delivery.by-email"] == "checkbox"     # choose any: a box an option
    assert kinds["occupancy"] == "select" and kinds["mailing-address"] == "input" and kinds["email"] == "input"
    assert OWNER_INFO.question("mailing-address").paper_lines == 2                  # one line online, two on paper
    email = next(q for q in payhoa_questions(OWNER_INFO) if q.field == "email")
    assert email.description.endswith("(Civil Code §4041(a)(1)(B))")              # each question cites its law
    shown = questions_for(OWNER_INFO)
    numbered = [q.label.split(".")[0] for q in shown if q.kind not in ("hr", "checkbox")] + \
        [q.label.split(".")[0] for q in shown if q.kind == "checkbox" and q.field != "attestation"][:1]
    assert "2" in numbered and shown[-1].field == "attestation" and shown[-1].required   # no gap; certify last
    assert "unit-address" not in [q.field for q in questions_for(OWNER_INFO)]       # the submission names its unit
    built, fields = request_body(OWNER_INFO)
    assert len(built) == len(fields) and [b["sortOrder"] for b in built] == list(range(1, len(built) + 1))
    assert built[fields.index("occupancy")]["options"][0]["label"] == "Owner-occupied"


class _Client:
    def __init__(self):
        self.calls = []

    def create_form(self, org_id, *, name, questions, description):
        self.calls.append(("create", name))
        return {"id": 500, "questions": [{"id": 9000 + n, "sortOrder": q["sortOrder"],
                                          "options": [{"id": 70000 + n * 10 + i, "label": o["label"]}
                                                      for i, o in enumerate(q["options"])]}
                                         for n, q in enumerate(questions)]}

    def set_form_status(self, org_id, form_id, *, enabled=None, private=None):
        self.calls.append(("status", form_id, enabled))


def test_a_made_form_is_recorded_switched_off_and_read_back(tmp_path):
    client = _Client()
    record = create(client, 27889, OWNER_INFO, tmp_path)
    assert client.calls[-1] == ("status", 500, False) and record["enabled"] is False     # off until a person turns it on
    by_field = {v: int(k) for k, v in record["questions"].items()}
    occupancy_option = next(k for k, v in record["options"].items() if v == "Rented out")
    detail = {"submission": {"id": 77, "membershipId": 800001, "unitId": 700002, "createdAt": "2026-10-05T10:00:00Z",
                             "answers": [
                                 {"questionId": by_field["name"], "answer": "Pat Lee"},
                                 {"questionId": by_field["delivery.by-email"], "answer": "1"},
                                 {"questionId": by_field["delivery.by-mail"], "answer": "0"},
                                 {"questionId": by_field["occupancy"], "answer": occupancy_option},       # an option id
                                 {"questionId": by_field["ballots"], "answer": "Paper ballot by mail"},   # a label
                                 {"questionId": by_field["email"], "answer": " pat@example.com "}]}}
    answers = submission_answers(detail, record, OWNER_INFO)
    assert answers.membership_id == 800001 and answers.unit_id == 700002 and answers.source == "payhoa:77"
    assert answers.answers == {"name": "Pat Lee", "delivery": ["By email"], "occupancy": ["Rented out"],
                               "ballots": ["Paper ballot by mail"], "email": "pat@example.com"}
    assert json.loads((tmp_path / "payhoa" / "forms.json").read_text())["forms"][0]["formId"] == 500


def test_a_signed_in_submission_is_matched_by_its_member_and_unit(tmp_path):
    from datetime import date

    from jason.community.forms import AnswerCycle, FormAnswers, FormKey
    from jason.tasks.member_preferences import Standing, match, payhoa_owners

    db = tmp_path / "payhoa.db"
    con = sqlite3.connect(db)
    con.execute("create table people (id, name, email)")
    con.execute("create table units (id, label, raw_json)")
    con.execute("insert into people values (1, 'Patricia Lee Trustee', 'other@example.com')")
    con.execute("insert into units values (10, '3007 ENCHANTED WALK', ?)",
                (json.dumps({"owners": [{"membershipId": 1, "deletedAt": None}]}),))
    con.commit()
    con.close()
    signed = FormAnswers(FormKey.OWNER_INFO, {"delivery": ["By email"]}, source="payhoa:77",
                         submitted="2026-10-05T10:00:00Z", membership_id=1, unit_id=10)      # no address, no matching name
    m = match([signed], payhoa_owners(db), cycle=AnswerCycle(2027, date(2026, 10, 1)), today=date(2026, 10, 6))[0]
    assert m.standing is Standing.CURRENT_OWNER and m.how == "PayHOA sign-in" and m.latest


class _Replacing(_Client):
    def __init__(self, submissions):
        super().__init__()
        self.submissions = submissions

    def list_form_submissions(self, form_id):
        return self.submissions

    def delete_form(self, org_id, form_id):
        self.calls.append(("delete", form_id))


def test_a_form_is_made_again_only_while_no_one_has_answered_it(tmp_path):
    import pytest

    from jason.tasks.payhoa_forms import record_for, replace

    first = create(_Client(), 27889, OWNER_INFO, tmp_path)
    client = _Replacing([])
    replace(client, 27889, OWNER_INFO, tmp_path)
    assert ("delete", first["formId"]) in client.calls and client.calls[-1][0] == "status"
    old = next(r for r in json.loads((tmp_path / "payhoa" / "forms.json").read_text())["forms"] if r.get("deleted"))
    assert old["formId"] == first["formId"] and record_for(tmp_path, "owner-info")["formId"] == 500
    answered = _Replacing([{"id": 1}])
    with pytest.raises(RuntimeError):
        replace(answered, 27889, OWNER_INFO, tmp_path)                           # an owner's answer is never deleted
    assert not any(c[0] == "delete" for c in answered.calls)


def test_the_form_states_its_law_on_paper_and_online():
    from datetime import date

    from jason.community.forms import AnswerCycle
    from jason.community.form_render import paper_html, paper_markdown, payhoa_description
    from jason.tasks.payhoa_forms import form_values

    values = form_values(AnswerCycle(2027, date(2026, 10, 1), return_by=date(2026, 10, 23)))
    assert values == {"RETURN_BY": "Friday, October 23, 2026"}
    online = payhoa_description(OWNER_INFO, values)
    assert "<strong>You do not have to provide an email address</strong>" in online
    assert "Friday, October 23, 2026" in online and "{RETURN_BY}" not in online
    assert "Civil Code §4041(c)" in online and "Civil Code §4041(b)(2)(B)" in online
    paper = "\n".join(paper_markdown(OWNER_INFO))
    assert "### Notice delivery (Civil Code §4041(a)(1))" in paper and "**Certification.** I certify" in paper
    assert "{RETURN_BY}" in paper                                          # the Doc fills the year's date later
    page = paper_html(OWNER_INFO, values=values)
    assert "class='section'" in page and "Friday, October 23, 2026" in page


def test_the_certification_is_read_back_from_a_submission(tmp_path):
    record = create(_Client(), 27889, OWNER_INFO, tmp_path)
    by_field = {v: int(k) for k, v in record["questions"].items()}
    detail = {"submission": {"id": 78, "membershipId": 1, "unitId": 2, "answers": [
        {"questionId": by_field["attestation"], "answer": "1"},
        {"questionId": by_field["name"], "answer": "Pat Lee"}]}}
    answers = submission_answers(detail, record, OWNER_INFO)
    assert answers.signature == "certified in PayHOA" and answers.answers == {"name": "Pat Lee"}


def test_an_edit_keeps_each_live_questions_id_and_adds_the_new_ones():
    from jason.tasks.payhoa_forms import merge_questions

    live = [{"id": 11, "formId": 9, "key": "11", "type": "input", "label": "Your name", "sortOrder": 1, "options": []},
            {"id": 12, "formId": 9, "key": "12", "type": "select", "label": "Is your unit", "sortOrder": 2,
             "options": [{"id": 101, "value": "5", "label": "Owner-occupied"}, {"id": 102, "value": "6", "label": "Rented out"}]}]
    want = [{"id": 0, "type": "input", "label": "Your name", "options": []},
            {"id": 0, "type": "input", "label": "Manager's email (optional)", "options": []},
            {"id": 0, "type": "select", "label": "Is your unit",
             "options": [{"id": 0, "label": "Owner-occupied"}, {"id": 0, "label": "Rented out"}, {"id": 0, "label": "Vacant"}]}]
    merged, dropped = merge_questions(live, want)
    assert [q["id"] for q in merged] == [11, 0, 12] and [q["sortOrder"] for q in merged] == [1, 2, 3] and not dropped
    assert [o["id"] for o in merged[2]["options"]] == [101, 102, 0]          # kept options keep their ids
    _, dropped = merge_questions(live, want[:2])
    assert [q["label"] for q in dropped] == ["Is your unit"]                 # an edit that drops one is refused


def test_a_live_form_is_never_deleted_and_a_broken_link_is_found_before_a_send(tmp_path):
    import json

    import pytest

    from jason.tasks.payhoa_forms import live_problem, lock, replace

    (tmp_path / "payhoa").mkdir()
    (tmp_path / "payhoa" / "forms.json").write_text(json.dumps({"forms": [
        {"key": "owner-info", "formId": 114542, "created": "2026-10-01T22:00:00+00:00", "questions": {}}]}))
    record = lock(tmp_path, "owner-info", "linked from the letter")
    assert record["locked"] == "linked from the letter"

    class Client:
        forms = [{"id": 114542, "isEnabled": True}]

        def list_forms(self):
            return self.forms

        def delete_form(self, *a):
            raise AssertionError("a live form is never deleted")

        def list_form_submissions(self, *a):
            return []

    client = Client()
    with pytest.raises(RuntimeError, match="never deleted"):
        replace(client, 27889, None or __import__("mystique.forms", fromlist=["OWNER_INFO"]).OWNER_INFO, tmp_path)
    assert "names no unit" in live_problem(client, record, "https://app.payhoa.com/app/forms/114542")
    link = "https://app.payhoa.com/app/forms/114542;unitId=700001"
    assert live_problem(client, record, link) == ""
    assert "another" not in live_problem(client, record, link) and \
        "recorded form is 114542" in live_problem(client, record, "https://app.payhoa.com/app/forms/114522")
    client.forms = [{"id": 114542, "isEnabled": 0}]
    assert "switched off" in live_problem(client, record, link)
    client.forms = []
    assert "not in PayHOA" in live_problem(client, record, link)


def test_a_payhoa_checkbox_is_an_icon_and_the_unit_answers_the_unit_address():
    """An owner's submission (October 1, 2026): a checked box reads as fa-check-square-o, an unchecked one fa-times;
    the online form asks no unit address, so the submission's unit fills it."""
    import importlib

    from jason.tasks.payhoa_forms import _truthy, submission_answers

    assert _truthy('<i class="fa fa-check-square-o"></i>') and not _truthy('<i class="fa fa-times"></i>')
    form = importlib.import_module("mystique.forms").OWNER_INFO
    record = {"questions": {"1": "delivery.by-mail", "2": "delivery.by-email", "3": "attestation"}, "options": {}}
    detail = {"submission": {"id": 7, "membershipId": 5, "unitId": 9, "unit": {"title": "5651 WHIMSICAL LN"},
                             "answers": [{"formQuestionId": 1, "answer": '<i class="fa fa-times"></i>'},
                                         {"formQuestionId": 2, "answer": '<i class="fa fa-check-square-o"></i>'},
                                         {"formQuestionId": 3, "answer": '<i class="fa fa-check-square-o"></i>'}]}}
    got = submission_answers(detail, record, form)
    assert got.answers["delivery"] == ["By email"] and got.answers["unit-address"] == "5651 WHIMSICAL LN"
    assert got.signature == "certified in PayHOA"


def test_a_reworded_question_keeps_its_id_by_the_field_it_answers():
    from jason.tasks.payhoa_forms import merge_questions

    live = [{"id": 12, "formId": 9, "key": "12", "type": "select", "label": "12. Is your unit", "sortOrder": 1,
             "options": [{"id": 101, "value": "1", "label": "Owner-occupied"}]}]
    want = [{"id": 0, "type": "select", "label": "12. Is your unit owner-occupied, rented out, or vacant?",
             "options": [{"id": 0, "label": "Owner-occupied"}]}]
    merged, dropped = merge_questions(live, want, fields=["occupancy"], known={"12": "occupancy"})
    assert merged[0]["id"] == 12 and merged[0]["options"][0]["id"] == 101 and not dropped
    _, dropped = merge_questions(live, want)                         # by label alone it would look removed
    assert dropped


def test_an_owner_link_names_the_unit_and_a_named_unit_is_kept():
    from jason.tasks.payhoa_forms import owner_link, requests_link, with_unit

    assert owner_link(114542, 700001) == "https://app.payhoa.com/app/forms/114542;unitId=700001"
    assert requests_link(700001) == "https://app.payhoa.com/app/unit/detail/700001?tab=requests"
    text = "at https://app.payhoa.com/app/forms/114542. Or https://app.payhoa.com/app/forms/114542;unitId=1"
    assert with_unit(text, 700001) == ("at https://app.payhoa.com/app/forms/114542;unitId=700001. "
                                       "Or https://app.payhoa.com/app/forms/114542;unitId=1")
