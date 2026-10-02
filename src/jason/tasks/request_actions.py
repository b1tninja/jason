"""Comment, internal note, and file attachment on an existing PayHOA request.

A comment is the thread the owner can see. A note stays internal when
``private`` is true. An attachment is linked to the request after it exists.
None of these approve, deny, or assign the request.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol


class _RequestWriter(Protocol):
    def get_form_submission(self, org_id: int, submission_id: int) -> dict[str, Any]: ...

    def add_submission_comment(
        self,
        submission_id: int,
        message: str,
        *,
        notify_admins: bool = False,
        recipient_member_ids: list[int] | None = None,
    ) -> Any: ...

    def add_submission_note(
        self,
        org_id: int,
        submission_id: int,
        note: str,
        *,
        private: bool = True,
        recipient_member_ids: list[int] | None = None,
    ) -> dict[str, Any]: ...

    def attach_request_file(
        self,
        submission_id: int,
        path: str | Path,
        *,
        notify: bool = False,
        filename: str | None = None,
        content_type: str = "application/octet-stream",
    ) -> dict[str, Any]: ...


def comment_on_request(
    client: _RequestWriter,
    org_id: int,
    request_id: int,
    message: str,
    *,
    notify_owner: bool = True,
    notify_admins: bool = False,
) -> Any:
    """Post a comment. By default the reporter and the unit owners are notified."""
    text = message.strip()
    if not text:
        raise ValueError("comment is empty")
    recipients: list[int] = []
    if notify_owner:
        recipients = _owner_ids(client.get_form_submission(org_id, request_id))
        if not recipients:
            raise ValueError(f"request {request_id} has no reporter or owner to notify")
    return client.add_submission_comment(
        request_id,
        text,
        notify_admins=notify_admins,
        recipient_member_ids=recipients,
    )


def _owner_ids(detail: dict[str, Any]) -> list[int]:
    body = detail.get("submission")
    if not isinstance(body, dict):
        body = detail
    found: list[int] = []

    def add(value: Any) -> None:
        if value is None:
            return
        number = int(value)
        if number not in found:
            found.append(number)

    add(body.get("membershipId"))
    unit = body.get("unit")
    if isinstance(unit, dict):
        for owner in unit.get("owners") or []:
            if isinstance(owner, dict):
                add(owner.get("membershipId"))
    return found


def note_on_request(
    client: _RequestWriter,
    org_id: int,
    request_id: int,
    note: str,
    *,
    private: bool = True,
) -> dict[str, Any]:
    text = note.strip()
    if not text:
        raise ValueError("note is empty")
    return client.add_submission_note(
        org_id, request_id, text, private=private
    )


_CONTENT_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".pdf": "application/pdf",
}


def attach_to_request(
    client: _RequestWriter,
    request_id: int,
    path: str | Path,
    *,
    notify: bool = False,
) -> dict[str, Any]:
    """Link a local file to the request. The owner is not notified unless asked."""
    file = Path(path)
    content_type = _CONTENT_TYPES.get(file.suffix.lower(), "application/octet-stream")
    return client.attach_request_file(
        request_id,
        file,
        notify=notify,
        content_type=content_type,
    )
