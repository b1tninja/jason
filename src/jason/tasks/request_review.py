"""Review open PayHOA requests against the local document catalog.

Does not approve, deny, or assign. Citations are only (a) short quotes from the
request's own title/message/answers, or (b) catalog document file names/paths
that share a significant word with that request text. Never invents governing-
document quotations.
"""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from typing import Any, Protocol

from jason.catalog import PayhoaCatalog, unit_label

CLOSED_STATUSES = frozenset({"complete", "Complete", "Approved", "approved"})
DEFAULT_FORM_NAMES = ("Maintenance Request", "Architectural Request")
DEFAULT_TAG_COLOR = "#7A64C8"

_STOPWORDS = frozenset(
    {
        "about",
        "after",
        "again",
        "also",
        "around",
        "been",
        "before",
        "being",
        "building",
        "could",
        "does",
        "every",
        "from",
        "have",
        "hello",
        "here",
        "into",
        "just",
        "like",
        "message",
        "need",
        "needs",
        "please",
        "request",
        "should",
        "that",
        "their",
        "them",
        "then",
        "there",
        "these",
        "they",
        "this",
        "those",
        "title",
        "today",
        "unit",
        "very",
        "want",
        "were",
        "what",
        "when",
        "where",
        "which",
        "will",
        "with",
        "would",
        "your",
    }
)

_TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)
_HTML_TAG_RE = re.compile(r"<[^>]+>")


class _TaggingClient(Protocol):
    def tag_submissions(
        self,
        org_id: int,
        submission_ids: list[int],
        value: str,
        *,
        color: str,
        display: str | None = None,
    ) -> Any: ...

    def get_form_submission(self, org_id: int, submission_id: int) -> dict[str, Any]: ...


@dataclass(frozen=True)
class DocumentMatch:
    file_name: str
    path: str


@dataclass(frozen=True)
class ReviewItem:
    """One open request paired with catalog document name matches only."""

    request_id: int
    form_name: str
    unit: str
    quote: str
    documents: tuple[DocumentMatch, ...]
    tag_applied: bool

    @property
    def document_note(self) -> str:
        if not self.documents:
            return "no document match"
        return "; ".join(f"{doc.file_name} ({doc.path})" for doc in self.documents)


def review_requests(
    catalog: PayhoaCatalog,
    client: _TaggingClient | None,
    org_id: int,
    *,
    form_names: tuple[str, ...] = DEFAULT_FORM_NAMES,
    limit: int | None = None,
    apply_tag: str | None = None,
    tag_color: str = DEFAULT_TAG_COLOR,
) -> list[ReviewItem]:
    """Match open maintenance/architectural requests to catalog document names.

    Prefer synced ``requests.raw_json`` and ``documents``. Call the client only
    to apply ``apply_tag`` (when set) or to ``get_form_submission`` when a row
    has no message/title in catalog answers.
    """
    if apply_tag and client is None:
        raise ValueError("client is required when apply_tag is set")

    docs = _load_documents(catalog, org_id)
    unit_labels = _load_unit_labels(catalog, org_id)
    items: list[ReviewItem] = []

    for row in _load_open_requests(catalog, org_id, form_names=form_names):
        raw = _parse_raw(row["raw_json"])
        title, message = _title_and_message(raw)
        if not title and not message and client is not None:
            detail = _unwrap_submission(client.get_form_submission(org_id, int(row["id"])))
            title, message = _title_and_message(detail)
            if detail:
                raw = {**raw, **detail}

        request_text = " ".join(part for part in (title, message) if part)
        quote = _quote_from_request(title, message)
        matches = _match_documents(request_text, docs)
        unit = _unit_for_row(row, raw, unit_labels)

        items.append(
            ReviewItem(
                request_id=int(row["id"]),
                form_name=str(row["form_name"] or ""),
                unit=unit,
                quote=quote,
                documents=tuple(matches),
                tag_applied=False,
            )
        )
        if limit is not None and len(items) >= limit:
            break

    if apply_tag and items:
        assert client is not None
        ids = [item.request_id for item in items]
        client.tag_submissions(org_id, ids, apply_tag, color=tag_color)
        items = [
            ReviewItem(
                request_id=item.request_id,
                form_name=item.form_name,
                unit=item.unit,
                quote=item.quote,
                documents=item.documents,
                tag_applied=True,
            )
            for item in items
        ]

    return items


def _load_open_requests(
    catalog: PayhoaCatalog,
    org_id: int,
    *,
    form_names: tuple[str, ...],
) -> list[dict[str, Any]]:
    rows = catalog.search_requests(
        org_id,
        form_names=form_names,
        exclude_statuses=CLOSED_STATUSES,
        include_raw=True,
        limit=None,
    )
    rows.sort(key=lambda row: (str(row.get("created_at") or ""), int(row["id"])))
    return rows


def _load_documents(catalog: PayhoaCatalog, org_id: int) -> list[DocumentMatch]:
    rows = catalog.search_documents(org_id, files_only=True, limit=None)
    return [
        DocumentMatch(file_name=str(row["fileName"]), path=str(row["path"] or ""))
        for row in rows
        if row.get("fileName")
    ]


def _load_unit_labels(catalog: PayhoaCatalog, org_id: int) -> dict[int, str]:
    rows = catalog._conn.execute(
        "SELECT id, label FROM units WHERE org_id = ?",
        (org_id,),
    ).fetchall()
    return {int(row["id"]): str(row["label"] or "") for row in rows}


def _parse_raw(raw_json: str | None) -> dict[str, Any]:
    if not raw_json:
        return {}
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _unwrap_submission(data: dict[str, Any]) -> dict[str, Any]:
    nested = data.get("submission")
    if isinstance(nested, dict):
        return nested
    return data


def _answer_by_label(raw: dict[str, Any], label: str) -> str:
    answers = raw.get("answers")
    if not isinstance(answers, list):
        return ""
    wanted = label.strip().lower()
    for item in answers:
        if not isinstance(item, dict):
            continue
        question = item.get("question")
        qlabel = ""
        if isinstance(question, dict):
            qlabel = str(question.get("label") or "")
        elif item.get("label"):
            qlabel = str(item.get("label") or "")
        if qlabel.strip().lower() != wanted:
            continue
        return _plain_text(str(item.get("answer") or ""))
    return ""


def _title_and_message(raw: dict[str, Any]) -> tuple[str, str]:
    title = _answer_by_label(raw, "Title") or _plain_text(str(raw.get("title") or ""))
    message = _answer_by_label(raw, "Message") or _plain_text(
        str(raw.get("message") or "")
    )
    return title, message


def _plain_text(value: str) -> str:
    text = _HTML_TAG_RE.sub(" ", value)
    text = html.unescape(text)
    return " ".join(text.split()).strip()


def _quote_from_request(title: str, message: str) -> str:
    if title:
        return title if len(title) <= 160 else title[:157].rstrip() + "..."
    if message:
        return message if len(message) <= 160 else message[:157].rstrip() + "..."
    return ""


def significant_words(text: str) -> set[str]:
    """Tokens long enough to be a meaningful name overlap (not stopwords)."""
    words: set[str] = set()
    for token in _TOKEN_RE.findall(text.lower()):
        if len(token) < 4:
            continue
        if token in _STOPWORDS:
            continue
        words.add(token)
    return words


def _match_documents(request_text: str, docs: list[DocumentMatch]) -> list[DocumentMatch]:
    words = significant_words(request_text)
    if not words:
        return []
    matches: list[DocumentMatch] = []
    seen: set[tuple[str, str]] = set()
    for doc in docs:
        name_words = significant_words(doc.file_name)
        if not (words & name_words):
            continue
        key = (doc.file_name, doc.path)
        if key in seen:
            continue
        seen.add(key)
        matches.append(doc)
    return matches


def _unit_for_row(
    row: dict[str, Any],
    raw: dict[str, Any],
    unit_labels: dict[int, str],
) -> str:
    unit_id = row.get("unit_id")
    if unit_id is not None:
        label = unit_labels.get(int(unit_id), "")
        if label:
            return label
    unit = raw.get("unit")
    if isinstance(unit, dict):
        return unit_label(unit)
    return ""
