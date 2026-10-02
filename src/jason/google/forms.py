"""Google Forms: create a form from a template, read it, and list its responses.

A form is made in two calls: ``POST /v1/forms`` takes only the title, and ``forms.batchUpdate`` adds the description
and the questions. A template is a ``FormTemplate`` row in the specification (``mystique/forms.py``). The token needs
``forms.body`` to create and ``forms.responses.readonly`` to read responses.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from jason.google.errors import GoogleError

_API = "https://forms.googleapis.com/v1/forms"


# The form model is the association's, not Google's (jason.community.forms); it is imported here so existing callers
# keep working. A Google Form is one renderer of it.
from jason.community.forms import (FormKey, FormQuestion, FormTemplate, QuestionKind,  # noqa: E402,F401
                                   TEXT_KINDS)


def question_item(question: FormQuestion) -> dict[str, Any]:
    """One question as a Forms ``Item``: a text question (short for a date-less short answer, an email, or a phone), a
    date question, or a radio or checkbox choice."""
    body: dict[str, Any] = {"required": question.required}
    if question.kind is QuestionKind.DATE:
        body["dateQuestion"] = {"includeYear": True}
    elif question.kind in TEXT_KINDS:
        body["textQuestion"] = {"paragraph": question.kind is QuestionKind.PARAGRAPH}
    else:
        body["choiceQuestion"] = {
            "type": "RADIO" if question.kind is QuestionKind.CHOICE else "CHECKBOX",
            "options": [{"value": o} for o in question.options],
        }
    item: dict[str, Any] = {"title": question.title, "questionItem": {"question": body}}
    if question.help:
        item["description"] = question.help
    return item


def form_requests(template: FormTemplate, *, reference: str = "", values: dict[str, str] | None = None) -> list[dict[str, Any]]:
    """The ``batchUpdate`` requests: the description (with the template's preamble, its ``{TOKENS}`` filled from
    ``values``), each question in order under its section's heading, the attestation as a required box, then (with
    ``reference``) the optional short question an owner's personal link fills with their copy's reference."""
    import re

    def fill(text: str) -> str:
        text = re.sub(r"\{([A-Z_]+)\}", lambda m: (values or {}).get(m.group(1), m.group(0)), text)
        return text.replace("**", "")

    description = "\n\n".join([template.description, *(fill(p) for p in template.preamble)] +
                              ([] if template.preamble else [template.authority]))
    out: list[dict[str, Any]] = [{"updateFormInfo": {"info": {"description": description}, "updateMask": "description"}}]
    items: list[dict[str, Any]] = []
    for question in template.questions:
        if question.section:
            items.append({"title": question.section, "textItem": {}})
        items.append(question_item(question))
    if template.attestation:
        items.append({"title": "Certification", "questionItem": {"question": {"required": True, "choiceQuestion": {
            "type": "CHECKBOX", "options": [{"value": template.attestation}]}}}})
    if reference:
        items.append({"title": reference, "description": "It tells the Association which letter or email you are answering.",
                      "questionItem": {"question": {"required": False, "textQuestion": {"paragraph": False}}}})
    out += [{"createItem": {"item": item, "location": {"index": i}}} for i, item in enumerate(items)]
    return out


def entry_ids(form: dict[str, Any]) -> dict[str, int]:
    """Each question's title to the number its pre-filled link names it by (``entry.<n>``): the API's question id,
    which is hexadecimal, as a decimal number."""
    out: dict[str, int] = {}
    for item in form.get("items") or []:
        qid = ((item.get("questionItem") or {}).get("question") or {}).get("questionId")
        if qid:
            out[item.get("title") or ""] = int(qid, 16)
    return out


def prefill_url(form: dict[str, Any], values: dict[str, str]) -> str:
    """The form's link with ``values`` (question title to text) filled in. Only what is safe in a URL belongs here: a
    reference, never a name, an address, or an email (a link is kept in browser history and server logs)."""
    from urllib.parse import urlencode

    ids = entry_ids(form)
    params = [("usp", "pp_url")] + [(f"entry.{ids[t]}", v) for t, v in values.items() if t in ids and v]
    return f"{form.get('responderUri', '')}?{urlencode(params)}"


class GoogleForms:
    """Forms v1 client on a Google access token."""

    def __init__(self, access_token: str, *, http: httpx.Client | None = None) -> None:
        if not access_token:
            raise GoogleError("missing access token")
        self._token = access_token
        self._http = http or httpx.Client(timeout=60.0)

    @classmethod
    def on(cls, drive: Any) -> GoogleForms:
        return cls(drive._token, http=drive._http)

    def create(self, template: FormTemplate, *, reference: str = "", values: dict[str, str] | None = None) -> dict[str, Any]:
        """Create the form and add its questions (and, with ``reference``, the reference question). Returns the form
        as ``get`` reads it after the update. A form the API makes is unpublished until ``publish``."""
        created = self._post(_API, {"info": {"title": template.title, "documentTitle": template.title}})
        form_id = created.get("formId")
        if not form_id:
            raise GoogleError("Forms create returned no formId")
        self._post(f"{_API}/{form_id}:batchUpdate", {"requests": form_requests(template, reference=reference, values=values)})
        return self.get(form_id)

    def set_email_collection(self, form_id: str, kind: str) -> dict[str, Any]:
        """How the form takes a respondent's email: ``VERIFIED`` (a Google sign-in), ``RESPONDER_INPUT`` (typed), or
        ``DO_NOT_COLLECT``."""
        return self._post(f"{_API}/{form_id}:batchUpdate", {"requests": [{"updateSettings": {
            "settings": {"emailCollectionType": kind}, "updateMask": "emailCollectionType"}}]})

    def publish(self, form_id: str, *, published: bool = True, accepting: bool = True) -> dict[str, Any]:
        """Publish (or unpublish) the form, and open or close it to responses. Publishing makes it public: anyone with
        the link can answer."""
        return self._post(f"{_API}/{form_id}:setPublishSettings", {
            "publishSettings": {"publishState": {"isPublished": published,
                                                 "isAcceptingResponses": accepting and published}},
            "updateMask": "publishState"})

    def get(self, form_id: str) -> dict[str, Any]:
        return self._get(f"{_API}/{form_id}", {})

    def responses(self, form_id: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        token: str | None = None
        while True:
            params: dict[str, Any] = {"pageSize": 5000}
            if token:
                params["pageToken"] = token
            body = self._get(f"{_API}/{form_id}/responses", params)
            rows.extend(body.get("responses") or [])
            token = body.get("nextPageToken")
            if not token:
                return rows

    def _post(self, url: str, body: dict[str, Any]) -> dict[str, Any]:
        response = self._http.post(url, headers={**self._headers(), "Content-Type": "application/json"},
                                   content=json.dumps(body))
        if not response.is_success:
            raise GoogleError(f"HTTP {response.status_code} for {url}: {response.text[:200]}")
        return response.json()

    def _get(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        response = self._http.get(url, params=params, headers=self._headers())
        if not response.is_success:
            raise GoogleError(f"HTTP {response.status_code} for {url}")
        return response.json()

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}


__all__ = ["FormKey", "FormQuestion", "FormTemplate", "GoogleForms", "QuestionKind"]
