"""Export the PayHOA document library so sync rules can be written against it."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from payhoa import PayhoaClient

from jason.catalog import PayhoaCatalog

EXPORT_FIELDS = (
    "id",
    "parentId",
    "directory",
    "fileName",
    "path",
    "fileSize",
    "public",
    "updatedAt",
)


@dataclass
class DocumentExport:
    path: Path
    count: int
    directories: int
    files: int

    def summary(self) -> str:
        return (
            f"documents={self.count} directories={self.directories} "
            f"files={self.files} path={self.path}"
        )


def document_row(row: dict[str, Any]) -> dict[str, Any]:
    """Fields a sync rule can match. Omits uploader profile data."""
    return {key: row.get(key) for key in EXPORT_FIELDS}


def export_documents(
    catalog: PayhoaCatalog,
    org_id: int,
    dest: str | Path,
    *,
    client: PayhoaClient | None = None,
) -> DocumentExport:
    """Write the flat library as JSON.

    Pass a client to refresh the catalog from PayHOA first. Without a client,
    the export is whatever ``sync-catalog`` last stored.
    """
    if client is not None:
        catalog.upsert_documents(org_id, client.list_documents(org_id))
    rows = [document_row(row) for row in catalog.list_documents(org_id)]
    rows.sort(key=lambda row: (str(row.get("path") or ""), str(row.get("fileName") or "")))
    path = Path(dest)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    directories = sum(1 for row in rows if row.get("directory"))
    return DocumentExport(
        path=path,
        count=len(rows),
        directories=directories,
        files=len(rows) - directories,
    )
