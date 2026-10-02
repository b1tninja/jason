"""Gmail drafts: build an RFC 5322 message and save it as a draft in the signed-in mailbox.

This client has no send method and no delete method. It calls ``users.drafts.create``, ``list``, ``get``, and ``update``
and nothing else, so a person reads each draft in Gmail and sends it (or discards it) there. The token needs
``gmail.compose``.

An edit is an update in place: the draft keeps its id, its thread, and the recipients a person typed in Gmail (an edit
that names no recipients keeps the draft's own). An edit never drops an attachment silently: a draft that has one is
refused unless the new message carries its files or the caller says to drop them. A text replacement that does not find
its text is an error, so a refinement is never lost quietly.
"""

from __future__ import annotations

import base64
import json
import mimetypes
from dataclasses import dataclass, field
from email.message import EmailMessage
from pathlib import Path
from typing import Any

import httpx

from jason.google.errors import GoogleError

_API = "https://gmail.googleapis.com/gmail/v1/users/me/drafts"


@dataclass(frozen=True)
class DraftMessage:
    """One message to save as a draft. ``html`` is an optional alternative to ``text``; ``attachments`` are file paths."""

    to: tuple[str, ...]
    subject: str
    text: str
    cc: tuple[str, ...] = ()
    bcc: tuple[str, ...] = ()
    html: str | None = None
    attachments: tuple[Path, ...] = field(default_factory=tuple)

    def email(self) -> EmailMessage:
        message = EmailMessage()
        if self.to:                                   # a draft may leave the recipients to the person
            message["To"] = ", ".join(self.to)
        if self.cc:
            message["Cc"] = ", ".join(self.cc)
        if self.bcc:
            message["Bcc"] = ", ".join(self.bcc)
        message["Subject"] = self.subject
        message.set_content(self.text)
        if self.html:
            message.add_alternative(self.html, subtype="html")
        for path in self.attachments:
            kind, _ = mimetypes.guess_type(path.name)
            maintype, subtype = (kind or "application/octet-stream").split("/", 1)
            message.add_attachment(path.read_bytes(), maintype=maintype, subtype=subtype, filename=path.name)
        return message

    def raw(self) -> str:
        """The message as Gmail's ``raw`` field: base64url of the RFC 5322 bytes."""
        return base64.urlsafe_b64encode(self.email().as_bytes()).decode("ascii")


class GmailDrafts:
    """Create and list drafts. Never sends."""

    def __init__(self, access_token: str, *, http: httpx.Client | None = None) -> None:
        if not access_token:
            raise GoogleError("missing access token")
        self._token = access_token
        self._http = http or httpx.Client(timeout=60.0)

    @classmethod
    def on(cls, drive: Any) -> GmailDrafts:
        """A drafts client on a ``GoogleDrive``'s token and HTTP client."""
        return cls(drive._token, http=drive._http)

    def create(self, draft: DraftMessage) -> dict[str, Any]:
        response = self._http.post(
            _API,
            headers={**self._headers(), "Content-Type": "application/json"},
            content=json.dumps({"message": {"raw": draft.raw()}}),
        )
        if not response.is_success:
            raise GoogleError(f"HTTP {response.status_code} creating a Gmail draft: {response.text[:200]}")
        return response.json()

    def list(self, *, max_results: int = 50) -> list[dict[str, Any]]:
        response = self._http.get(_API, params={"maxResults": max_results}, headers=self._headers())
        if not response.is_success:
            raise GoogleError(f"HTTP {response.status_code} listing Gmail drafts")
        return list(response.json().get("drafts") or [])

    def get(self, draft_id: str) -> SavedDraft:
        """One draft as it stands in Gmail: its recipients, subject, plain text, and attachment names."""
        response = self._http.get(f"{_API}/{draft_id}", params={"format": "full"}, headers=self._headers())
        if response.status_code == 404:
            raise DraftNotFound(f"no Gmail draft {draft_id} (sent or discarded in Gmail?)")
        if not response.is_success:
            raise GoogleError(f"HTTP {response.status_code} reading Gmail draft {draft_id}")
        return SavedDraft.parse(response.json())

    def update(self, draft_id: str, draft: DraftMessage, *, drop_attachments: bool = False) -> dict[str, Any]:
        """Replace a draft's message in place. Recipients the new message leaves empty are kept from the draft; an
        attachment the draft has and the new message lacks is refused unless ``drop_attachments``."""
        current = self.get(draft_id)
        if current.attachments and not draft.attachments and not drop_attachments:
            raise GoogleError(f"draft {draft_id} has attachments ({', '.join(current.attachments)}); the edit would drop them")
        draft = DraftMessage(to=draft.to or current.to, cc=draft.cc or current.cc, bcc=draft.bcc or current.bcc,
                             subject=draft.subject, text=draft.text, html=draft.html, attachments=draft.attachments)
        message: dict[str, Any] = {"raw": draft.raw()}
        if current.thread_id:
            message["threadId"] = current.thread_id
        response = self._http.put(
            f"{_API}/{draft_id}",
            headers={**self._headers(), "Content-Type": "application/json"},
            content=json.dumps({"id": draft_id, "message": message}),
        )
        if not response.is_success:
            raise GoogleError(f"HTTP {response.status_code} updating Gmail draft {draft_id}: {response.text[:200]}")
        return response.json()

    def edit(self, draft_id: str, *, replace: tuple[tuple[str, str], ...] = (), subject: str | None = None,
             text: str | None = None, to: tuple[str, ...] = (), cc: tuple[str, ...] = (),
             yes: bool = False) -> DraftEdit:
        """A refinement of a saved draft: replacements in its text (each must be found), a new subject or text, or
        recipients. Without ``yes`` it only returns the before and after; with it, the draft is updated in place."""
        current = self.get(draft_id)
        new_text = current.text if text is None else text
        for old, new in replace:
            if old not in new_text:
                raise GoogleError(f"draft {draft_id} does not contain {old[:60]!r}; nothing was changed")
            new_text = new_text.replace(old, new)
        after = DraftMessage(to=to, cc=cc, subject=current.subject if subject is None else subject, text=new_text)
        edit = DraftEdit(draft_id, current, after)
        if yes and edit.changed:
            if current.attachments:
                raise GoogleError(f"draft {draft_id} has attachments ({', '.join(current.attachments)}); edit it in Gmail")
            self.update(draft_id, after)
        return edit

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}


class DraftNotFound(GoogleError):
    """The draft is gone: sent or discarded in Gmail."""


def _addresses(value: str) -> tuple[str, ...]:
    from email.utils import getaddresses

    return tuple(addr for _, addr in getaddresses([value]) if addr) if value else ()


def _decode(data: str) -> str:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", errors="replace")


@dataclass(frozen=True)
class SavedDraft:
    id: str
    message_id: str
    thread_id: str
    to: tuple[str, ...]
    cc: tuple[str, ...]
    bcc: tuple[str, ...]
    subject: str
    text: str
    attachments: tuple[str, ...] = ()

    @classmethod
    def parse(cls, raw: dict[str, Any]) -> SavedDraft:
        message = raw.get("message") or {}
        payload = message.get("payload") or {}
        headers = {h["name"].lower(): h["value"] for h in payload.get("headers") or []}
        texts: list[str] = []
        files: list[str] = []

        def walk(part: dict[str, Any]) -> None:
            if part.get("filename"):
                files.append(part["filename"])
            elif part.get("mimeType") == "text/plain" and (part.get("body") or {}).get("data"):
                texts.append(_decode(part["body"]["data"]))
            for child in part.get("parts") or []:
                walk(child)

        walk(payload)
        return cls(id=raw.get("id", ""), message_id=message.get("id", ""), thread_id=message.get("threadId", ""),
                   to=_addresses(headers.get("to", "")), cc=_addresses(headers.get("cc", "")),
                   bcc=_addresses(headers.get("bcc", "")), subject=headers.get("subject", ""),
                   text="".join(texts).replace("\r\n", "\n").rstrip("\n"), attachments=tuple(files))


@dataclass(frozen=True)
class DraftEdit:
    draft_id: str
    before: SavedDraft
    after: DraftMessage

    @property
    def changed(self) -> bool:
        return (self.before.subject, self.before.text) != (self.after.subject, self.after.text.rstrip("\n")) or \
            bool(self.after.to and self.after.to != self.before.to) or bool(self.after.cc and self.after.cc != self.before.cc)

    def diff(self) -> str:
        """A unified diff of the subject and text."""
        import difflib

        old = [f"Subject: {self.before.subject}", ""] + self.before.text.splitlines()
        new = [f"Subject: {self.after.subject}", ""] + self.after.text.rstrip("\n").splitlines()
        return "\n".join(difflib.unified_diff(old, new, "before", "after", lineterm=""))


__all__ = ["DraftEdit", "DraftMessage", "DraftNotFound", "GmailDrafts", "SavedDraft"]
