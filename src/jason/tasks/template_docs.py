"""PayHOA's broadcast templates kept as Google Docs, one Doc a template, in "My Drive/Templates/PayHOA Broadcasts".

PayHOA to Docs only: jason cannot save a template in PayHOA (the call was not captured). Each Doc carries the private
appProperty ``jason_payhoa_template`` with the template id; its description names the subject and the attachments.
``data/payhoa/template-docs.json`` keeps, per template, the Doc id and a hash of the template and of the Doc as jason
last wrote them, so a run can tell who changed what:

- a template with no Doc is created;
- a template that changed while its Doc did not is written into the Doc;
- a Doc a person edited while the template did not is left alone ("Doc ahead"): ``jason broadcast --from-doc`` turns it
  into a body to paste into PayHOA;
- both changed is a conflict, and nothing is written;
- a template PayHOA deleted keeps its Doc.

The Doc's body is the template's HTML with ``<span class="placeholder">{first name}</span>`` as plain ``{first name}``;
going back, a known placeholder is wrapped again.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable

from jason.tasks.broadcast import KNOWN_PLACEHOLDERS, PLACEHOLDER

APP_KEY = "jason_payhoa_template"
STATE_FILE = "template-docs.json"
DOC_PREFIX = "PayHOA - "


class Action(Enum):
    CREATE = "create"
    UPDATE = "update"
    UNCHANGED = "unchanged"
    DOC_AHEAD = "doc ahead"
    CONFLICT = "conflict"
    DELETED = "deleted in PayHOA"

    @property
    def writes(self) -> bool:
        return self in (Action.CREATE, Action.UPDATE)


@dataclass(frozen=True)
class Step:
    template_id: int
    subject: str
    action: Action
    doc_id: str = ""
    reason: str = ""


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def template_sha(row: dict[str, Any]) -> str:
    names = ",".join(sorted(str(a.get("id")) for a in row.get("attachments") or []))
    return sha(f"{row.get('subject')}\n{names}\n{row.get('message') or ''}")


def doc_name(row: dict[str, Any]) -> str:
    return DOC_PREFIX + " ".join(str(row.get("subject") or f"Template {row.get('id')}").split())


def subject_of(doc_title: str) -> str:
    return doc_title[len(DOC_PREFIX):] if doc_title.startswith(DOC_PREFIX) else doc_title


def import_html(message: str) -> bytes:
    """The page Drive imports as the Doc: the template's body, placeholders as plain text."""
    from jason.community.email_html import normalize

    body = PLACEHOLDER.sub(lambda m: "{" + m.group(1) + "}", normalize(message or ""))
    return f'<!doctype html><html><head><meta charset="utf-8"></head><body>{body}</body></html>'.encode("utf-8")


def composer_html(doc_html: str) -> str:
    """A Doc's HTML with each known placeholder wrapped the way PayHOA's composer wraps it."""
    def wrap(m: re.Match[str]) -> str:
        name = m.group(1)
        return f'<span class="placeholder">{{{name}}}</span>' if name.casefold() in KNOWN_PLACEHOLDERS else m.group(0)

    return re.sub(r"\{([^{}<>]+)\}", wrap, doc_html)


def description(row: dict[str, Any]) -> str:
    files = "; ".join(f"{a.get('fileName')} (#{a.get('id')})" for a in row.get("attachments") or []) or "none"
    return (f"PayHOA broadcast template {row.get('id')}. Subject: {row.get('subject')}. Attachments: {files}. "
            f"Kept by jason (jason broadcast --sync-docs); after editing here, jason broadcast --from-doc gives the body "
            f"to paste into PayHOA.")


PLACEHOLDER_COLOR = {"red": 0.81, "green": 0.89, "blue": 0.99}      # light blue: PayHOA fills it for each member
FIELD_COLOR = {"red": 1.0, "green": 0.95, "blue": 0.6}              # yellow: a person fills it for each use
FIELD_IN_TEXT = re.compile(r"\[[A-Z][A-Z0-9 /&'-]{1,40}\]")
PLACEHOLDER_IN_TEXT = re.compile(r"\{[a-z][a-z ]{1,30}\}")


def _utf16(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def _tab(doc: dict[str, Any]) -> dict[str, Any]:
    tabs = doc.get("tabs")
    return (tabs[0].get("documentTab") or {}) if isinstance(tabs, list) and tabs else doc


def highlight_requests(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """Background colours on each {placeholder} and [FIELD] in the body (indexes in UTF-16 units, as the Docs API
    counts). The body's HTML ignores background colour, so the sync's hashes do not change."""
    requests: list[dict[str, Any]] = []

    def walk(content: list[dict[str, Any]]) -> None:
        for block in content or []:
            for element in (block.get("paragraph") or {}).get("elements") or []:
                run = element.get("textRun") or {}
                text, start = str(run.get("content") or ""), element.get("startIndex")
                if not text or start is None:
                    continue
                for pattern, color in ((PLACEHOLDER_IN_TEXT, PLACEHOLDER_COLOR), (FIELD_IN_TEXT, FIELD_COLOR)):
                    for m in pattern.finditer(text):
                        begin = start + _utf16(text[:m.start()])
                        requests.append({"updateTextStyle": {
                            "range": {"startIndex": begin, "endIndex": begin + _utf16(m.group(0))},
                            "textStyle": {"backgroundColor": {"color": {"rgbColor": color}}},
                            "fields": "backgroundColor"}})
            for row in (block.get("table") or {}).get("tableRows") or []:
                for cell in row.get("tableCells") or []:
                    walk(cell.get("content") or [])

    walk((_tab(doc).get("body") or {}).get("content") or [])
    return requests


def header_text(row: dict[str, Any]) -> str:
    names = ", ".join(str(a.get("fileName")) for a in row.get("attachments") or []) or "none"
    return (f"PayHOA template {row.get('id')} · Subject: {row.get('subject')}\n"
            f"Attachments in PayHOA: {names}\n"
            "Blue {placeholders} are filled by PayHOA for each member; yellow [FIELDS] are filled in for each use. "
            "This header is not part of the email.")


def header_requests(doc: dict[str, Any], header_id: str, text: str) -> list[dict[str, Any]]:
    """Replace the header's text with ``text`` in small grey type."""
    header = (_tab(doc).get("headers") or {}).get(header_id) or {}
    content = header.get("content") or []
    end = content[-1].get("endIndex", 1) if content else 1
    requests: list[dict[str, Any]] = []
    if end - 1 > 0:
        requests.append({"deleteContentRange": {"range": {"segmentId": header_id, "startIndex": 0, "endIndex": end - 1}}})
    requests.append({"insertText": {"location": {"segmentId": header_id, "index": 0}, "text": text}})
    requests.append({"updateTextStyle": {
        "range": {"segmentId": header_id, "startIndex": 0, "endIndex": _utf16(text)},
        "textStyle": {"fontSize": {"magnitude": 8, "unit": "PT"},
                      "foregroundColor": {"color": {"rgbColor": {"red": 0.4, "green": 0.4, "blue": 0.4}}}},
        "fields": "fontSize,foregroundColor"}})
    return requests


def format_doc(docs: Any, doc_id: str, row: dict[str, Any]) -> int:
    """Give a template Doc its header and highlights. Returns the number of requests applied."""
    doc = docs.get(doc_id)
    header_id = str((_tab(doc).get("documentStyle") or doc.get("documentStyle") or {}).get("defaultHeaderId") or "")
    if not header_id:
        reply = docs.batch_update(doc_id, [{"createHeader": {"type": "DEFAULT"}}])
        header_id = str(((reply.get("replies") or [{}])[0].get("createHeader") or {}).get("headerId") or "")
        doc = docs.get(doc_id)
    requests = highlight_requests(doc) + (header_requests(doc, header_id, header_text(row)) if header_id else [])
    if requests:
        docs.batch_update(doc_id, requests)
    return len(requests)


def load_state(data_dir: Path) -> dict[str, dict[str, Any]]:
    path = data_dir / "payhoa" / STATE_FILE
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_state(data_dir: Path, state: dict[str, dict[str, Any]]) -> Path:
    path = data_dir / "payhoa" / STATE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    return path


def record(row: dict[str, Any], doc_id: str, doc_sha: str) -> dict[str, Any]:
    return {
        "docId": doc_id,
        "subject": row.get("subject"),
        "templateSha": template_sha(row),
        "templateUpdatedAt": row.get("updatedAt"),
        "docSha": doc_sha,
        "attachments": [{"id": a.get("id"), "fileName": a.get("fileName"), "path": a.get("path")}
                        for a in row.get("attachments") or []],
        "syncedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def plan(templates: Iterable[dict[str, Any]], state: dict[str, dict[str, Any]],
         doc_shas: dict[str, str | None]) -> list[Step]:
    """What a sync would do. ``doc_shas`` is each known Doc's current hash, None when the Doc is gone or trashed."""
    steps: list[Step] = []
    live: set[str] = set()
    for row in templates:
        if row.get("deletedAt"):
            continue
        key = str(row.get("id"))
        live.add(key)
        subject = str(row.get("subject") or "")
        entry = state.get(key)
        if not entry:
            steps.append(Step(int(key), subject, Action.CREATE, reason="no Doc yet"))
            continue
        doc_id = str(entry.get("docId") or "")
        current = doc_shas.get(doc_id)
        if current is None:
            steps.append(Step(int(key), subject, Action.CREATE, doc_id, "its Doc is gone or in the trash"))
            continue
        template_changed = template_sha(row) != entry.get("templateSha")
        doc_changed = current != entry.get("docSha")
        if template_changed and doc_changed:
            steps.append(Step(int(key), subject, Action.CONFLICT, doc_id, "PayHOA and the Doc both changed since the last sync"))
        elif template_changed:
            steps.append(Step(int(key), subject, Action.UPDATE, doc_id, f"PayHOA updated it {str(row.get('updatedAt'))[:10]}"))
        elif doc_changed:
            steps.append(Step(int(key), subject, Action.DOC_AHEAD, doc_id, "a person edited the Doc; paste it into PayHOA"))
        else:
            steps.append(Step(int(key), subject, Action.UNCHANGED, doc_id))
    for key, entry in state.items():
        if key not in live:
            steps.append(Step(int(key), str(entry.get("subject") or ""), Action.DELETED, str(entry.get("docId") or ""),
                              "the Doc is kept"))
    return steps


def step_line(step: Step) -> str:
    link = f"  https://docs.google.com/document/d/{step.doc_id}/edit" if step.doc_id else ""
    why = f" ({step.reason})" if step.reason else ""
    return f"{step.action.value:18} {step.template_id}  {html.unescape(step.subject)}{why}{link}"
