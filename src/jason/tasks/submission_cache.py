"""The latest full read of each PayHOA request, kept on disk: ``payhoa-files/requests/<id>/submission.json``.

PayHOA's request list (the catalog's ``requests`` table) holds each request's status, never its answers, and
``sync-request-files`` saved a request's comments, notes, and attachments but not the submission itself. Every
owner-information plan reads each submission in full (``payhoa_forms.fetch_submissions``), so whatever reads one keeps
it here, replacing the last read:

``{"readAt": ISO UTC, "via": the command or task that read it, "formId", "formName", "status",
"submission": the raw get_form_submission JSON}``

Writers: ``owner_info_apply.gather_answers`` (a plan's live read), ``jason sync-request-files``, and the console's
refresh of one record (``jason.approvals.evidence.refresh``). Each writes a temporary file and replaces, so a reader
never sees half a file. The folder is the one ``sync-request-files`` fills (``Settings.payhoa_catalog.parent /
"payhoa-files"``). Nothing here reads or writes PayHOA.

Privacy: the submission holds an owner's answers as read (P2, like the catalog), on local disk only;
``jason.approvals.evidence`` masks contact details and other P2 answers before anything leaves the server.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

FILE = "submission.json"
FILES_DIR = "payhoa-files"

log = logging.getLogger(__name__)


def files_dir(data_dir: Path) -> Path:
    """``payhoa-files`` in the data folder: where ``sync-request-files`` keeps each request's folder."""
    return Path(data_dir) / FILES_DIR


def path_for(root: Path, request_id: int) -> Path:
    """The cache file for ``request_id`` under ``root`` (a ``payhoa-files`` folder)."""
    return Path(root) / "requests" / str(int(request_id)) / FILE


def body(detail: dict[str, Any] | None) -> dict[str, Any]:
    """The submission itself: ``get_form_submission`` answers ``{"submission": {...}}`` or the object bare."""
    detail = detail if isinstance(detail, dict) else {}
    nested = detail.get("submission")
    return nested if isinstance(nested, dict) else detail


def form_of(detail: dict[str, Any] | None) -> tuple[int | None, str]:
    """The form a submission answers, as it says itself: its id and name, each None or "" when it does not."""
    sub = body(detail)
    form = sub.get("form") if isinstance(sub.get("form"), dict) else {}
    form_id = sub.get("formId") or form.get("id")
    name = sub.get("formName") or form.get("name") or form.get("title") or ""
    try:
        return (int(form_id) if form_id not in (None, "") else None), str(name)
    except (TypeError, ValueError):
        return None, str(name)


def write(root: Path, request_id: int, detail: dict[str, Any], *, via: str, form_id: int | None = None,
          form_name: str = "", status: str = "", read_at: str = "") -> Path:
    """Keep ``detail`` (one ``get_form_submission`` answer, raw) as the latest read of ``request_id``, replacing the
    last. ``form_id``, ``form_name``, and ``status`` come from the caller (the list row, the catalog, the form record)
    where it knows them, else from the submission itself."""
    sub = body(detail)
    found_id, found_name = form_of(detail)
    record = {"readAt": read_at or datetime.now(timezone.utc).isoformat(timespec="seconds"), "via": via,
              "formId": form_id if form_id is not None else found_id, "formName": form_name or found_name,
              "status": str(status or sub.get("status") or ""), "submission": detail}
    file = path_for(root, request_id)
    file.parent.mkdir(parents=True, exist_ok=True)
    tmp = file.with_name(FILE + ".tmp")
    tmp.write_text(json.dumps(record, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, file)
    return file


def read(root: Path, request_id: int) -> dict[str, Any] | None:
    """The latest read of ``request_id`` as kept, or None when none is (a file that cannot be read raises
    ``ValueError`` with why)."""
    file = path_for(root, request_id)
    if not file.is_file():
        return None
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"{file.name} could not be read ({type(exc).__name__})") from exc
    if not isinstance(data, dict) or not isinstance(data.get("submission"), dict):
        raise ValueError(f"{file.name} is not a kept submission")
    return data


def keeper(root: Path, *, via: str, form_id: int | None = None,
           form_name: str = "") -> Callable[[dict[str, Any], dict[str, Any]], None]:
    """A ``fetch_submissions`` ``keep`` callback: each submission read is written as it is read, with its list row's
    status. A cache that cannot be written is logged and never stops the read that made it."""

    def keep(row: dict[str, Any], detail: dict[str, Any]) -> None:
        sid = (row or {}).get("id") or body(detail).get("id")
        if sid in (None, ""):
            return
        try:
            write(root, int(sid), detail, via=via, form_id=form_id, form_name=form_name,
                  status=str((row or {}).get("status") or ""))
        except OSError as exc:
            log.warning("request %s: its read was not kept (%s: %s)", sid, type(exc).__name__, exc)

    return keep


__all__ = ["FILE", "FILES_DIR", "body", "files_dir", "form_of", "keeper", "path_for", "read", "write"]
