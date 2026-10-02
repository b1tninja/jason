"""Download request attachments and save comments and internal notes beside them."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from payhoa import PayhoaClient

from jason.catalog import PayhoaCatalog

_UNSAFE = re.compile(r"[^\w.\- ]+", re.UNICODE)


@dataclass
class SavedRequestFile:
    request_id: int
    file_id: int
    path: Path
    skipped: bool = False


@dataclass
class RequestFilesReport:
    requests: int = 0
    files: int = 0
    skipped: int = 0
    missing_url: int = 0
    saved: list[SavedRequestFile] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        parts = [
            f"requests={self.requests}",
            f"files={self.files}",
            f"skipped={self.skipped}",
            f"missing_url={self.missing_url}",
        ]
        if self.errors:
            parts.append(f"errors={len(self.errors)}")
        return " ".join(parts)


def sync_request_files(
    client: PayhoaClient,
    org_id: int,
    dest_dir: str | Path,
    *,
    catalog: PayhoaCatalog | None = None,
    request_ids: list[int] | None = None,
) -> RequestFilesReport:
    """Pull each request's files, comments, and internal notes.

    Form-answer files and later-linked files both come from the PayHOA client.
    A file already on disk with the same size is left in place.
    """
    ids = list(request_ids) if request_ids is not None else []
    if not ids and catalog is not None:
        ids = catalog.request_ids(org_id)
    root = Path(dest_dir)
    report = RequestFilesReport(requests=len(ids))
    for request_id in ids:
        folder = root / "requests" / str(request_id)
        try:
            _save_related(client, org_id, request_id, folder)
            records = client.request_files(org_id, request_id)
        except Exception as exc:  # noqa: BLE001 — one request should not stop the rest
            report.errors.append(f"{request_id}: {exc}")
            continue
        for record in records:
            _save_file(client, request_id, record, folder, report)
    return report


def _save_related(
    client: PayhoaClient, org_id: int, request_id: int, folder: Path
) -> None:
    comments = client.list_submission_comments(request_id, org_id)
    notes = client.list_submission_notes(org_id, request_id)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "comments.json").write_text(
        json.dumps(comments, indent=2), encoding="utf-8"
    )
    (folder / "notes.json").write_text(json.dumps(notes, indent=2), encoding="utf-8")


def _save_file(
    client: PayhoaClient,
    request_id: int,
    record: dict[str, Any],
    folder: Path,
    report: RequestFilesReport,
) -> None:
    file_id = int(record["id"])
    name = _safe_name(str(record.get("fileName") or f"{file_id}"))
    dest = folder / f"{file_id}_{name}"
    size = record.get("fileSize")
    if dest.is_file() and size is not None and dest.stat().st_size == int(size):
        report.skipped += 1
        report.saved.append(
            SavedRequestFile(request_id, file_id, dest, skipped=True)
        )
        return
    url = record.get("downloadUrl")
    if not url:
        report.missing_url += 1
        report.errors.append(f"{request_id}: file {file_id} has no downloadUrl")
        return
    client.download_signed_url(str(url), dest)
    report.files += 1
    report.saved.append(SavedRequestFile(request_id, file_id, dest))


def _safe_name(name: str) -> str:
    cleaned = Path(name).name
    cleaned = _UNSAFE.sub("_", cleaned).strip(" .")
    return cleaned or "file"
