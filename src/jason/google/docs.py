"""Docs API helper. Edits go through documents.batchUpdate.

A text watermark such as a diagonal DRAFT is not a batchUpdate request.
``export_pdf`` writes the document as it stands, watermark included.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from jason.google.errors import GoogleError

_API = "https://docs.googleapis.com/v1"
_DRIVE_EXPORT = "https://www.googleapis.com/drive/v3/files"


class GoogleDocs:
    """Authenticated Docs v1 client. Share the Drive client's access token."""

    def __init__(
        self,
        access_token: str,
        *,
        http: httpx.Client | None = None,
        owns_http: bool = False,
    ) -> None:
        if not access_token:
            raise GoogleError("missing access token")
        self._token = access_token
        self._http = http or httpx.Client(timeout=60.0)
        self._owns_http = http is None or owns_http

    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    def get(self, document_id: str) -> dict[str, Any]:
        """Read the document, including every tab."""
        response = self._http.get(
            f"{_API}/documents/{document_id}",
            params={"includeTabsContent": True},
            headers=self._headers(),
        )
        return _ok(response, f"reading {document_id}")

    def batch_update(
        self, document_id: str, requests: list[dict[str, Any]], *, write_mode: str | None = None
    ) -> dict[str, Any]:
        """Apply Docs edit requests. The documents scope is required.

        ``write_mode="SUGGEST"`` applies every request as a suggestion the document's editors accept or reject
        (``writeControl.writeMode``, a Google Workspace Developer Preview feature: the project must be enrolled, and
        some requests, such as named ranges and headers, fail in that mode)."""
        if not requests:
            raise GoogleError("batch_update needs at least one request")
        body: dict[str, Any] = {"requests": requests}
        if write_mode:
            body["writeControl"] = {"writeMode": write_mode}
        response = self._http.post(
            f"{_API}/documents/{document_id}:batchUpdate",
            headers={**self._headers(), "Content-Type": "application/json"},
            content=json.dumps(body),
        )
        return _ok(response, f"updating {document_id}")

    def export_pdf(self, document_id: str, dest: str | Path) -> Path:
        """Export the Google Doc to PDF.

        Uses Drive ``files.export`` with ``mimeType=application/pdf``. The
        documents scope does not have its own PDF method. A text watermark
        still on the doc is included in the file.
        """
        path = Path(dest)
        path.parent.mkdir(parents=True, exist_ok=True)
        response = self._http.get(
            f"{_DRIVE_EXPORT}/{document_id}/export",
            params={"mimeType": "application/pdf"},
            headers=self._headers(),
        )
        if not response.is_success:
            raise GoogleError(
                f"HTTP {response.status_code} exporting {document_id} to PDF"
            )
        path.write_bytes(response.content)
        return path

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}


def document_markdown(doc: dict[str, Any]) -> str:
    """Turn a Docs API document into markdown. Quotes the document body only."""
    title = str(doc.get("title") or "Document").strip()
    lines = [f"# {title}", ""]
    tabs = doc.get("tabs")
    if isinstance(tabs, list) and tabs:
        for tab in tabs:
            lines.extend(_tab_lines(tab, depth=2))
    else:
        lines.extend(_body_lines(doc.get("body")))
    return "\n".join(lines).rstrip() + "\n"


def _tab_lines(tab: dict[str, Any], *, depth: int) -> list[str]:
    props = tab.get("tabProperties") if isinstance(tab.get("tabProperties"), dict) else {}
    title = str(props.get("title") or "").strip()
    lines: list[str] = []
    if title:
        lines.extend(["#" * min(depth, 6) + f" {title}", ""])
    document_tab = tab.get("documentTab") if isinstance(tab.get("documentTab"), dict) else {}
    lines.extend(_body_lines(document_tab.get("body")))
    for child in tab.get("childTabs") or []:
        if isinstance(child, dict):
            lines.extend(_tab_lines(child, depth=depth + 1))
    return lines


def _body_lines(body: Any) -> list[str]:
    if not isinstance(body, dict):
        return []
    lines: list[str] = []
    for block in body.get("content") or []:
        if not isinstance(block, dict):
            continue
        paragraph = block.get("paragraph")
        if isinstance(paragraph, dict):
            text = _paragraph_text(paragraph)
            if text:
                lines.append(text)
                lines.append("")
            continue
        table = block.get("table")
        if isinstance(table, dict):
            lines.extend(_table_lines(table))
            lines.append("")
    return lines


def _paragraph_text(paragraph: dict[str, Any]) -> str:
    parts: list[str] = []
    for element in paragraph.get("elements") or []:
        if not isinstance(element, dict):
            continue
        run = element.get("textRun")
        if isinstance(run, dict):
            parts.append(str(run.get("content") or ""))
            continue
        parts.append(_chip_text(element))
    text = "".join(parts).replace("\u000b", "\n").strip()
    if not text:
        return ""
    style = paragraph.get("paragraphStyle") if isinstance(paragraph.get("paragraphStyle"), dict) else {}
    named = str(style.get("namedStyleType") or "")
    level = {
        "TITLE": 1,
        "HEADING_1": 2,
        "HEADING_2": 3,
        "HEADING_3": 4,
        "HEADING_4": 5,
        "HEADING_5": 6,
        "HEADING_6": 6,
    }.get(named)
    if level:
        return "#" * level + " " + " ".join(text.split())
    bullet = paragraph.get("bullet")
    if isinstance(bullet, dict):
        return "- " + " ".join(text.split())
    return text


def _chip_text(element: dict[str, Any]) -> str:
    """A smart chip's visible text: a linked file's title or a person's name. A list of chips is often the whole
    answer in a checklist Doc, so dropping them leaves only the questions."""
    rich = element.get("richLink")
    if isinstance(rich, dict):
        props = rich.get("richLinkProperties") if isinstance(rich.get("richLinkProperties"), dict) else {}
        title = str(props.get("title") or "").strip()
        return f"[{title}]" if title else ""
    person = element.get("person")
    if isinstance(person, dict):
        props = person.get("personProperties") if isinstance(person.get("personProperties"), dict) else {}
        return str(props.get("name") or props.get("email") or "").strip()
    return ""


def _table_lines(table: dict[str, Any]) -> list[str]:
    rows: list[list[str]] = []
    for row in table.get("tableRows") or []:
        if not isinstance(row, dict):
            continue
        cells: list[str] = []
        for cell in row.get("tableCells") or []:
            if not isinstance(cell, dict):
                continue
            bits = _body_lines(cell)
            cells.append(" ".join(bit for bit in bits if bit).replace("|", "\\|"))
        if any(cells):
            rows.append(cells)
    if not rows:
        return []
    width = max(len(row) for row in rows)
    padded = [row + [""] * (width - len(row)) for row in rows]
    header = "| " + " | ".join(padded[0]) + " |"
    rule = "| " + " | ".join("---" for _ in padded[0]) + " |"
    body = ["| " + " | ".join(row) + " |" for row in padded[1:]]
    return [header, rule, *body]


def _ok(response: httpx.Response, action: str) -> dict[str, Any]:
    try:
        body = response.json()
    except json.JSONDecodeError:
        body = {}
    if not isinstance(body, dict):
        body = {}
    if not response.is_success:
        message = ""
        error = body.get("error")
        if isinstance(error, dict):
            message = str(error.get("message") or "")
        detail = f": {message}" if message else ""
        raise GoogleError(f"HTTP {response.status_code} {action}{detail}")
    return body
