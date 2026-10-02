"""Turn a Google Doc into a PDF and upload that PDF into a PayHOA folder."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from payhoa import PayhoaClient


def publish_google_doc(
    drive: Any,
    client: PayhoaClient,
    *,
    org_id: int,
    document_id: str,
    parent_id: int,
    dest: str | Path,
    file_name: str | None = None,
) -> dict[str, Any]:
    """Export ``document_id`` to PDF, then create it under ``parent_id``.

    ``parent_id`` is the PayHOA folder id (for example Meetings/2026). The
    export includes a text watermark if the Doc still has one.
    """
    path = drive.export_pdf(document_id, dest)
    return client.create_document(
        org_id, parent_id, path, file_name=file_name or Path(path).name
    )
