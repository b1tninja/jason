"""The association's forms in PayHOA's form builder: made from the definition, and their submissions read back by field.

PayHOA is the record of owners' answers (``jason.community.tags``), and a PayHOA submission is signed in: it names the
member who sent it and, for a form that requires a unit, the unit. So a definition (``mystique/forms.py``) is made in
PayHOA as a form (``form_render.payhoa_questions``), the PayHOA question ids are recorded against the definition's
fields in ``data/payhoa/forms.json``, and each submission reads back into a ``FormAnswers`` with its member and unit,
ready for ``forms.check`` and ``member_preferences.match`` without guessing who answered.

Creating a form changes PayHOA and is done only on a person's ``--yes``; a new form is on and visible to owners, so it
is switched off until a person turns it on, unless asked otherwise.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jason.community.form_render import ATTESTATION, PayhoaQuestion, payhoa_description, payhoa_questions
from jason.community.forms import FormAnswers, FormTemplate, QuestionKind


def questions_for(form: FormTemplate, *, requires_unit: bool = True) -> list[PayhoaQuestion]:
    """The PayHOA questions for a definition. With ``requires_unit`` the submission names its unit, so a question the
    definition prefills with the unit's address is left out."""
    skip = {q.field for q in form.questions if requires_unit and q.prefill == "UNIT_ADDRESS"}
    return payhoa_questions(form, skip=skip)


def request_body(form: FormTemplate, *, requires_unit: bool = True) -> tuple[list[dict[str, Any]], list[str]]:
    """The builder's question list and, in the same order, the field each answers."""
    from payhoa.client import PayhoaClient

    questions = questions_for(form, requires_unit=requires_unit)
    long = [f"{q.label} ({len(q.description)})" for q in questions if len(q.description or "") > DESCRIPTION_MAX]
    if long:
        raise ValueError(f"PayHOA keeps {DESCRIPTION_MAX} characters of a question's help; shorten: " + "; ".join(long))
    built = [PayhoaClient.form_question(q.label, q.kind, sort_order=n, description=q.description, required=q.required,
                                        options=q.options) for n, q in enumerate(questions, 1)]
    return built, [q.field for q in questions]


# PayHOA cuts a question's help (``description``) at this many characters (form 114542, October 1, 2026).
DESCRIPTION_MAX = 255


def records_path(data_dir: Path) -> Path:
    return Path(data_dir) / "payhoa" / "forms.json"


def load_records(data_dir: Path) -> list[dict[str, Any]]:
    path = records_path(data_dir)
    return json.loads(path.read_text(encoding="utf-8")).get("forms", []) if path.is_file() else []


def record_for(data_dir: Path, key: str) -> dict[str, Any] | None:
    """The latest PayHOA form made from definition ``key`` that has not been deleted."""
    rows = [r for r in load_records(data_dir) if r.get("key") == key and not r.get("deleted")]
    return rows[-1] if rows else None


def replace(client: Any, org_id: int, form: FormTemplate, data_dir: Path, *, enable: bool = False,
            values: dict[str, str] | None = None) -> dict[str, Any]:
    """Make the form again from the definition, deleting the one made before, but only while it has no submissions
    (an owner's answer is never deleted to change a question; ``update`` edits a form in place instead). The old record
    is kept, marked deleted."""
    old = record_for(data_dir, form.key.value)
    if old is not None and old.get("locked"):
        raise RuntimeError(f"PayHOA form {old['formId']} is live ({old['locked']}): it is never deleted, because "
                           "letters, QR codes, and emails link to it. Edit it in place: jason forms --payhoa "
                           f"{form.key.value} --update")
    if old is not None:
        submissions = client.list_form_submissions(int(old["formId"]))
        if submissions:
            raise RuntimeError(f"PayHOA form {old['formId']} has {len(submissions)} submission(s); it is not deleted. "
                               "Change its questions in PayHOA instead.")
        client.delete_form(org_id, int(old["formId"]))
        rows = load_records(data_dir)
        for row in rows:
            if row.get("formId") == old["formId"]:
                row["deleted"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        records_path(data_dir).write_text(json.dumps({"forms": rows}, indent=1), encoding="utf-8")
    return create(client, org_id, form, data_dir, enable=enable, values=values)


def form_values(cycle: Any) -> dict[str, str]:
    """The year's values a form's preamble names, from the cycle (the return date, written out)."""
    day = getattr(cycle, "return_by", None)
    return {"RETURN_BY": f"{day:%A, %B} {day.day}, {day.year}"} if day else {}


def create(client: Any, org_id: int, form: FormTemplate, data_dir: Path, *, enable: bool = False,
           values: dict[str, str] | None = None) -> dict[str, Any]:
    """Make the form in PayHOA, switch it off unless ``enable``, and record its question ids by field. ``values`` fill
    the preamble's tokens (``form_values``)."""
    built, fields = request_body(form)
    made = client.create_form(org_id, name=form.title, questions=built, description=payhoa_description(form, values))
    if not enable:
        client.set_form_status(org_id, int(made["id"]), enabled=False)
    by_order = sorted(made.get("questions") or [], key=lambda q: q.get("sortOrder") or 0)
    record = {
        "key": form.key.value, "formId": made["id"], "title": form.title, "enabled": enable,
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "questions": {str(q["id"]): field for q, field in zip(by_order, fields)},
        "options": {str(o["id"]): o.get("label") for q in by_order for o in q.get("options") or []},
    }
    path = records_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"forms": load_records(data_dir) + [record]}, indent=1), encoding="utf-8")
    return record


def lock(data_dir: Path, key: str, why: str) -> dict[str, Any]:
    """Mark the recorded form live: something sent links to it, so it is edited in place and never deleted
    (``replace`` refuses). The board's rule of October 1, 2026, after a deleted form broke the letter's link."""
    record = record_for(data_dir, key)
    if record is None:
        raise RuntimeError(f"no PayHOA form recorded for {key}")
    rows = load_records(data_dir)
    for row in rows:
        if row.get("formId") == record["formId"] and not row.get("deleted"):
            row["locked"] = why
    records_path(data_dir).write_text(json.dumps({"forms": rows}, indent=1), encoding="utf-8")
    return record_for(data_dir, key) or record


OWNER_APP = "https://app.payhoa.com/app"
# A form link as PayHOA's owner app reads it: an owner's submission names its unit, so the link must carry the unit
# (an Angular matrix parameter, ";unitId="). Without it the form opens only for an administrator; an owner who follows
# it can't answer. Found after the 2027 owner-information request went out with bare links (October 1, 2026).
FORM_LINK = re.compile(r"https://app\.payhoa\.com/app/forms/(?P<form>\d+)(?P<unit>;unitId=\d+)?")


def owner_link(form_id: int, unit_id: int) -> str:
    """The link an owner of ``unit_id`` follows to answer form ``form_id``."""
    return f"{OWNER_APP}/forms/{int(form_id)};unitId={int(unit_id)}"


def requests_link(unit_id: int) -> str:
    """The unit's Requests tab in the owner app, where every form the owner may answer is listed."""
    return f"{OWNER_APP}/unit/detail/{int(unit_id)}?tab=requests"


def with_unit(text: str, unit_id: int) -> str:
    """``text`` with every PayHOA form link given the unit (a link already naming a unit is left as it is)."""
    return FORM_LINK.sub(lambda m: m.group(0) if m.group("unit") else owner_link(int(m.group("form")), unit_id), text)


def live_problem(client: Any, record: dict[str, Any], link: str = "") -> str:
    """Why the recorded form can't take answers now, or "": it must still be in PayHOA, switched on, and (given the
    link a letter or email prints) the form that link opens, with the unit an owner's answer needs. A person can
    delete a form in PayHOA; this finds it before anything is sent pointing to it."""
    form_id = int(record["formId"])
    found_link = FORM_LINK.fullmatch(link.rstrip("/")) if link else None
    if link and (found_link is None or int(found_link.group("form")) != form_id):
        return f"the link sent is {link}, but the recorded form is {form_id}: update the link (values.json, drafts)"
    if found_link is not None and not found_link.group("unit"):
        return (f"the link sent ({link}) names no unit, and PayHOA opens a form for an owner only with the unit "
                "(;unitId=): each copy needs its own unit's link (payhoa_forms.owner_link)")
    found = next((f for f in client.list_forms() if int(f.get("id") or 0) == form_id), None)
    if found is None:
        return (f"PayHOA form {form_id} is not in PayHOA (deleted?): every letter, QR code, and email linking to it "
                "is broken. Make it again (jason forms --payhoa ... --yes), then update the links")
    enabled = found.get("isEnabled", found.get("enabled", True))
    if enabled in (False, 0, "0"):
        return f"PayHOA form {form_id} is switched off: owners who follow the link can't answer"
    return ""


def merge_questions(current: list[dict[str, Any]], desired: list[dict[str, Any]], *, fields: list[str] = (),
                    known: dict[str, str] | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """The definition's questions in the editor's shape, each matched to a live question, which keeps its id, key,
    and its options' ids by label, so the submissions made to it stay tied to it. A live question matches first by the
    field it is recorded to answer (``known``: question id to field, from ``data/payhoa/forms.json``; ``fields``: the
    desired questions' fields in order), so a reworded question keeps its id; then by type and label. A question with
    no match is new (id 0). Returns the questions to save and the live ones nothing matched."""
    pool = sorted(current, key=lambda q: q.get("sortOrder") or 0)
    known = {str(k): v for k, v in (known or {}).items()}
    used: set[int] = set()
    merged = []
    for n, want in enumerate(desired, 1):
        field = fields[n - 1] if n - 1 < len(fields) else ""
        have = next((q for q in pool if int(q["id"]) not in used and q.get("type") == want["type"]
                     and field and known.get(str(q["id"])) == field), None) or             next((q for q in pool if int(q["id"]) not in used and q.get("type") == want["type"]
                  and (q.get("label") or "").strip() == want["label"].strip()), None)
        q = dict(want, sortOrder=n)
        if have is not None:
            used.add(int(have["id"]))
            by_label = {(o.get("label") or "").strip(): o for o in have.get("options") or []}
            q.update(id=int(have["id"]), formId=int(have.get("formId") or 0), key=str(have.get("key") or have["id"]))
            q["options"] = [dict(o, id=int(by_label[o["label"].strip()]["id"]),
                                 value=by_label[o["label"].strip()].get("value"),
                                 formQuestionId=int(have["id"])) if o["label"].strip() in by_label else o
                            for o in want.get("options") or []]
        merged.append(q)
    return merged, [q for q in pool if int(q["id"]) not in used]


def update(client: Any, org_id: int, form: FormTemplate, data_dir: Path, *, values: dict[str, str] | None = None,
           dry_run: bool = False) -> dict[str, Any]:
    """Edit the recorded form in place to match the definition (``update_form``, as PayHOA's editor saves): kept
    questions keep their ids, so the answers already submitted stay readable; new ones are added. Removing a question
    was not captured, so an edit that would drop one is refused (change it in PayHOA's editor). Returns what changed;
    with ``dry_run`` nothing is saved."""
    record = record_for(data_dir, form.key.value)
    if record is None:
        raise RuntimeError(f"no PayHOA form recorded for {form.key.value}: create it first")
    problem = live_problem(client, record)
    if problem:
        raise RuntimeError(problem)
    live = client.get_form(org_id, int(record["formId"]))
    desired, fields = request_body(form)
    merged, dropped = merge_questions(live.get("questions") or [], desired, fields=fields,
                                      known=record.get("questions") or {})
    if dropped:
        raise RuntimeError("the definition no longer has these questions, and removing one was not captured: "
                           + "; ".join(f"{q.get('type')} {q.get('label')!r}" for q in dropped))
    live_labels = {int(q["id"]): (q.get("label") or "").strip() for q in live.get("questions") or []}
    live_help = {int(q["id"]): (q.get("description") or "").strip() for q in live.get("questions") or []}
    changes = {"kept": sum(1 for q in merged if q["id"]), "added": [q["label"] for q in merged if not q["id"]],
               "reworded": [f"{live_labels[q['id']]!r} -> {q['label']!r}" for q in merged
                            if q["id"] and live_labels.get(q["id"]) != q["label"].strip()],
               "help changed": [q["label"] for q in merged
                                if q["id"] and live_help.get(q["id"]) != (q.get("description") or "").strip()]}
    if dry_run:
        return changes
    saved = client.update_form(org_id, {**live, "name": form.title, "description": payhoa_description(form, values),
                                        "questions": merged})
    by_order = sorted(saved.get("questions") or [], key=lambda q: q.get("sortOrder") or 0)
    if len(by_order) != len(fields):
        raise RuntimeError(f"PayHOA saved {len(by_order)} questions, the definition has {len(fields)}: check the form")
    rows = load_records(data_dir)
    for row in rows:
        if row.get("formId") == record["formId"] and not row.get("deleted"):
            row["questions"] = {str(q["id"]): field for q, field in zip(by_order, fields)}
            row["options"] = {str(o["id"]): o.get("label") for q in by_order for o in q.get("options") or []}
            row["updated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    records_path(data_dir).write_text(json.dumps({"forms": rows}, indent=1), encoding="utf-8")
    return changes


def _truthy(value: Any) -> bool:
    """A checked box. PayHOA stores a checkbox answer as an icon (an owner's submission, October 1, 2026):
    ``<i class="fa fa-check-square-o"></i>`` checked, ``<i class="fa fa-times"></i>`` not."""
    text = str(value).strip().casefold()
    if "fa-check" in text:
        return True
    if "fa-times" in text:
        return False
    return text in ("1", "true", "yes", "on", "checked")


def submission_answers(detail: dict[str, Any], record: dict[str, Any], form: FormTemplate) -> FormAnswers:
    """One PayHOA submission (``get_form_submission``) as answers by field, with the member and unit that sent it.
    A select answer may arrive as the option's label, its value, or its id; each is read back to the option."""
    submission = detail.get("submission") or detail
    answers: dict[str, Any] = {}
    attested = False
    options = {str(k): v for k, v in (record.get("options") or {}).items()}
    same: set[str] = set()
    for answer in submission.get("answers") or []:
        field_name = record["questions"].get(str(answer.get("questionId") or answer.get("formQuestionId")))
        value = answer.get("answer") if "answer" in answer else answer.get("value")
        if not field_name or value in (None, ""):
            continue
        base, _, option = field_name.partition(".")
        if base == ATTESTATION:                                   # the certification box, not a question
            attested = _truthy(value)
            continue
        question = form.question(base)
        if option and question.same_as and field_name == question.same_as_field:
            if _truthy(value):
                same.add(base)                                    # "Same as my unit address"
        elif option:
            if _truthy(value):
                answers.setdefault(base, []).append(question.option_for(option))
        elif question.kind in (QuestionKind.CHOICE, QuestionKind.CHECKBOX):
            text = options.get(str(value), str(value))
            answers[base] = [question.option_for(text) if text not in question.options else text]
        else:
            answers[base] = str(value).strip()
    for base in same:                                             # an address written out stands, box or no box
        answers.setdefault(base, form.question(base).same_as)
    # the online form asks no unit address: the submission names its unit, so a question prefilled with it is answered
    unit = submission.get("unit") or {}
    title = str(unit.get("title") or unit.get("streetAddress") or "").strip()
    for q in form.questions:
        if q.prefill == "UNIT_ADDRESS" and title and not answers.get(q.field):
            answers[q.field] = title
    return FormAnswers(form.key, answers, source=f"payhoa:{submission.get('id')}",
                       signature="certified in PayHOA" if attested else "",
                       submitted=str(submission.get("createdAt") or ""),
                       membership_id=submission.get("membershipId"), unit_id=submission.get("unitId"))


def owner_answers(form: FormTemplate, record: dict[str, Any], live: dict[str, Any],
                  values: dict[str, Any]) -> list[dict[str, Any]]:
    """Answers by field (as ``FormAnswers.answers``: text, or the chosen options as a list; ``attestation`` true) as
    PayHOA's owner app sends them (``submit_unit_form``): only what is answered, a dropdown by its option's value, each
    checkbox "true" or "false"."""
    by_id = {str(q["id"]): q for q in live.get("questions") or []}
    out = []
    for qid, field_name in record["questions"].items():
        q = by_id.get(str(qid))
        if q is None or q.get("type") in ("hr", "plaintext"):
            continue
        base, _, option = field_name.partition(".")
        answer = None
        if base == ATTESTATION:
            answer = "true" if values.get(ATTESTATION) else None
        elif option and form.question(base).same_as and field_name == form.question(base).same_as_field:
            answer = "true" if values.get(base) == form.question(base).same_as else "false"
        elif option:
            chosen = values.get(base) or []
            answer = "true" if form.question(base).option_for(option) in chosen else "false"
        elif q.get("type") == "select":
            chosen = values.get(base)
            label = (chosen[0] if isinstance(chosen, list) else chosen) if chosen else ""
            match = next((o for o in q.get("options") or [] if (o.get("label") or "").strip() == label.strip()), None)
            if label and match is None:
                raise ValueError(f"{base}: {label!r} is not one of the form's options")
            answer = str(match["value"]) if match else None
        elif values.get(base):
            answer = str(values[base])
        if answer is not None:
            out.append({"questionId": int(qid), "answer": answer})
    return out


def sample_values(form: FormTemplate) -> dict[str, Any]:
    """Made-up answers to every question (the example domain, a 555 number, the last option of each choice, every box
    of each checkbox question), certified: a round trip touches every field."""
    out: dict[str, Any] = {}
    for q in form.questions:
        if q.prefill == "UNIT_ADDRESS":
            continue
        if q.kind is QuestionKind.CHOICE:
            out[q.field] = [q.options[-1]]
        elif q.kind is QuestionKind.CHECKBOX:
            out[q.field] = list(q.options)
        elif q.kind is QuestionKind.EMAIL:
            out[q.field] = f"{q.field}@example.com"
        elif q.kind is QuestionKind.PHONE:
            out[q.field] = "916-555-0100"
        else:
            out[q.field] = f"Test {q.field.replace('-', ' ')}"
    out[ATTESTATION] = True
    return out


def round_trip(admin: Any, owner: Any, org_id: int, form: FormTemplate, record: dict[str, Any], unit_id: int,
               values: dict[str, Any]) -> tuple[int, list[str]]:
    """Submit ``values`` as an owner (the test account) and read the submission back as the admin reads every owner's:
    the new submission's id and each field that came back different. PayHOA sends the owner no copy."""
    live = admin.get_form(org_id, int(record["formId"]))
    ids = owner.submit_unit_form(org_id, int(record["formId"]), unit_id, owner_answers(form, record, live, values),
                                 notify_owner=False)
    got = submission_answers(admin.get_form_submission(org_id, ids[0]), record, form)
    wrong = [f"{k}: sent {v!r}, read {got.answers.get(k)!r}" for k, v in values.items()
             if k != ATTESTATION and got.answers.get(k) != v]
    if bool(values.get(ATTESTATION)) != (got.signature == "certified in PayHOA"):
        wrong.append("attestation: not read back as sent")
    return ids[0], wrong


def fetch_submissions(client: Any, org_id: int, record: dict[str, Any], form: FormTemplate) -> list[FormAnswers]:
    """Every submission to the recorded form, read by field."""
    rows = client.list_form_submissions(int(record["formId"]))
    return [submission_answers(client.get_form_submission(org_id, int(r["id"])), record, form) for r in rows]


__all__ = ["create", "fetch_submissions", "live_problem", "load_records", "lock", "merge_questions", "questions_for", "record_for", "request_body",
           "owner_answers", "round_trip", "sample_values", "submission_answers", "update"]
