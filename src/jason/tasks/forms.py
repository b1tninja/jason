"""The association's request forms in Google Forms: create one from its template, and read its responses into rows.

Templates are ``FORM_TEMPLATES`` in ``mystique/forms.py``. A created form is recorded in ``data/forms/forms.json``.
Responses are saved to ``data/forms/<formId>/responses.json`` on local disk only; a response is a member's personal
data and is not written anywhere shared.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jason.google.forms import FormKey, FormTemplate, GoogleForms


def template(key: str | FormKey) -> FormTemplate:
    from jason.community.spec import spec_module

    FORM_TEMPLATES = spec_module("forms").FORM_TEMPLATES

    wanted = FormKey(key) if isinstance(key, str) else key
    for row in FORM_TEMPLATES:
        if row.key is wanted:
            return row
    raise LookupError(f"no form template {wanted.value}")


def forms_dir(data_dir: Path) -> Path:
    return Path(data_dir) / "forms"


def plan_lines(tpl: FormTemplate) -> list[str]:
    out = [f"Form: {tpl.title}", f"  {tpl.authority}"]
    for q in tpl.questions:
        extra = f" [{' / '.join(q.options)}]" if q.options else ""
        out.append(f"  - {q.title} ({q.kind.value}{', required' if q.required else ''}){extra}")
    return out


def create(forms: GoogleForms, tpl: FormTemplate, data_dir: Path, *, channel: Any = None,
           values: dict[str, str] | None = None) -> dict[str, Any]:
    """Create the form and record it in ``forms.json``. With a ``GoogleFormChannel`` the form gets the reference
    question an owner's personal link fills, and takes the respondent's email the channel's way; it stays unpublished."""
    form = forms.create(tpl, reference=channel.reference if channel else "", values=values)
    if channel:
        forms.set_email_collection(form["formId"], channel.email.value)
        # Google says a form the API makes after June 30, 2026 starts unpublished; on October 1, 2026 one came out
        # published and open, so it is unpublished here, and published only by a person's --publish --yes
        forms.publish(form["formId"], published=False)
    record = {"formId": form.get("formId"), "key": tpl.key.value, "title": tpl.title,
              "responderUri": form.get("responderUri"),
              "created": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    path = forms_dir(data_dir) / "forms.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = json.loads(path.read_text(encoding="utf-8")).get("forms", []) if path.is_file() else []
    path.write_text(json.dumps({"forms": rows + [record]}, indent=1), encoding="utf-8")
    return record


def fetch_responses(forms: GoogleForms, form_id: str, data_dir: Path) -> Path:
    """Save the form and its responses to ``data/forms/<formId>/responses.json``."""
    body = {"form": forms.get(form_id), "responses": forms.responses(form_id),
            "fetched": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    path = forms_dir(data_dir) / form_id / "responses.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body, indent=1), encoding="utf-8")
    return path


def form_items(saved: dict[str, Any]) -> list[dict[str, Any]]:
    """The form's questions in order, each with its id, title, the section it sits in (the page break's title), which
    occurrence of that section it is (a form that repeats "Additional Owner Information" has occurrences 1 and 2), and
    whether it takes a file upload."""
    from collections import Counter

    out: list[dict[str, Any]] = []
    section, seen = "", Counter()
    for item in (saved.get("form") or {}).get("items") or []:
        if "pageBreakItem" in item:
            section = item.get("title") or ""
            seen[section] += 1
            continue
        question = (item.get("questionItem") or {}).get("question") or {}
        if question.get("questionId"):
            out.append({"id": question["questionId"], "title": item.get("title") or "", "section": section,
                        "occurrence": seen[section], "file": "fileUploadQuestion" in question})
    return out


def _texts(answer: dict[str, Any]) -> list[str]:
    return [a.get("value", "") for a in (answer.get("textAnswers") or {}).get("answers") or []]


def import_responses(saved: dict[str, Any], rules: Any) -> list[Any]:
    """An outside form's responses read into the association's definition by its ``FormImport`` rules: each response a
    ``FormAnswers`` with the fields the rules fill (options mapped, two answers to one text field joined), the people it
    names (one per occurrence of a contact section), and when it was sent. File uploads are never read."""
    from jason.community.forms import CONTACT, FormAnswers

    items = form_items(saved)
    out = []
    for response in saved.get("responses") or []:
        answers: dict[str, Any] = {}
        contacts: dict[tuple[str, int], dict[str, str]] = {}
        given = response.get("answers") or {}
        for item in items:
            values = [v.strip() for v in _texts(given.get(item["id"]) or {}) if v.strip()]
            rule = None if item["file"] or not values else rules.rule(item["section"], item["title"])
            if rule is None:
                continue
            if rule.field.startswith(CONTACT):
                person = contacts.setdefault((item["section"], item["occurrence"]), {"role": rule.role})
                person[rule.field[len(CONTACT):]] = values[0]
            elif rule.options:
                mapped = dict(rule.options)
                chosen = answers.setdefault(rule.field, [])
                chosen += [mapped.get(v, v) for v in values if mapped.get(v, v) not in chosen]
            else:
                text = "; ".join(values)
                answers[rule.field] = f"{answers[rule.field]}; {text}" if rule.field in answers else text
        people = [p for p in contacts.values() if p.get("name") or p.get("email")]
        owners = [p for p in people if p["role"] == "owner"]
        if owners:
            answers["name"] = owners[0].get("name", "")          # the first owner named; the rest are contacts
            if "By email" in answers.get("delivery", []) and "email" not in answers:
                answers["email"] = next((p["email"] for p in owners if p.get("email")), "")
        out.append(FormAnswers(rules.form, answers, source=f"google:{response.get('responseId')}",
                               submitted=response.get("lastSubmittedTime") or response.get("createTime") or "",
                               contacts=people))
    return sorted(out, key=lambda a: a.submitted)


def response_rows(saved: dict[str, Any]) -> list[dict[str, Any]]:
    """Each response as one row: submitted time, then each question's title to its answer text. A title the form
    repeats (an owner's name in each owner section) is prefixed with its section and occurrence, so no answer is
    overwritten by another."""
    from collections import Counter

    items = form_items(saved)
    repeats = Counter(i["title"] for i in items)
    titles: dict[str, str] = {}
    for item in items:
        title = item["title"] or item["id"]
        if repeats[item["title"]] > 1:
            title = f"{item['section']} {item['occurrence']}: {title}"
        titles[item["id"]] = title
    rows = []
    for response in saved.get("responses") or []:
        row: dict[str, Any] = {"responseId": response.get("responseId"),
                               "submitted": response.get("lastSubmittedTime") or response.get("createTime")}
        for qid, answer in (response.get("answers") or {}).items():
            values = [a.get("value", "") for a in (answer.get("textAnswers") or {}).get("answers") or []]
            row[titles.get(qid, qid)] = "; ".join(values)
        rows.append(row)
    return sorted(rows, key=lambda r: r.get("submitted") or "")


def load_rows(data_dir: Path, form_id: str) -> list[dict[str, Any]]:
    path = forms_dir(data_dir) / form_id / "responses.json"
    return response_rows(json.loads(path.read_text(encoding="utf-8")))


# -- fillable PDFs ----------------------------------------------------------------------------------------------------

def fill_tokens(lines: list[str], values: dict[str, str]) -> list[str]:
    """``{TOKEN}`` in each line replaced by its value; a token with no value is left for a person to see."""
    import re

    return [re.sub(r"\{([A-Z][A-Z0-9_]*)\}", lambda m: values.get(m.group(1)) or m.group(0), line) for line in lines]


def form_pdf(form: FormTemplate, out: Path, *, association: str, logo: Path | None = None, preamble: list[str] = (),
             closing: list[str] = (), values: dict[str, str] | None = None, prefill: dict[str, Any] | None = None,
             run: Any = None) -> list[str]:
    """A fillable PDF of ``form`` from its definition alone, with no Doc: the paper form printed on the letterhead by
    the installed Chrome or Edge, then made fillable (``fillable.make_fillable``). ``preamble`` and ``closing`` are
    lines with ``{TOKENS}`` filled from ``values``; ``prefill`` sets fields by name for one recipient (the unit's
    address under its question's field). Returns the field names."""
    import subprocess
    import tempfile

    from jason.community.fillable import make_fillable
    from jason.community.form_render import paper_html
    from jason.community.pdf_fields import fill
    from jason.tasks.packets import page_html, print_pdf

    from jason.community.qr import fill_qr_tokens

    values = values or {}
    body = paper_html(form, preamble=fill_tokens(list(preamble), values), closing=fill_tokens(list(closing), values))
    body, _ = fill_qr_tokens(body, values, labels={"OWNER_FORM_LINK": "Scan to answer online in PayHOA"})
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        printed = Path(tmp) / "printed.pdf"
        print_pdf(page_html(form.title, body, association=association, logo=logo), printed, run=run or subprocess.run)
        names = make_fillable(printed, out=out, form=form)
    if prefill:
        missing = fill(out, prefill, out.with_suffix(".tmp.pdf"))
        out.with_suffix(".tmp.pdf").replace(out)
        if missing:
            raise KeyError(f"no field for {', '.join(missing)} (fields: {', '.join(names)})")
    return names


def read_pdfs(form: FormTemplate, paths: list[Path]) -> tuple[list[str], list[list[str]]]:
    """Each returned PDF read by question and checked against the form (``forms.check``): a header and one row a
    file, with the problems last, for a person to review and enter."""
    from jason.community.fillable import read_answers
    from jason.community.forms import answer_rows

    return answer_rows(form, [read_answers(Path(p), form, source=Path(p).name) for p in paths])


__all__ = ["create", "fetch_responses", "fill_tokens", "form_pdf", "forms_dir", "load_rows", "plan_lines", "read_pdfs",
           "response_rows", "template"]
