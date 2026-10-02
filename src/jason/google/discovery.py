"""Watch Google's public API discovery documents for the preview features jason waits on.

The board chose not to join Google's Workspace Developer Preview Program. Two Docs API features jason would use are in
that preview: writing edits as suggestions (``WriteControl.writeMode = SUGGEST``) and anchored comments
(``InsertCommentRequest``). Google marks a preview field in the public discovery document with a "[Developer Preview]"
link in its description; when the mark is gone and the field is still there, the feature is generally available.
``feature_status`` reads that; ``fetch`` gets the document (public, no sign-in).
"""

from __future__ import annotations

from typing import Any

import httpx

DOCS_DISCOVERY = "https://docs.googleapis.com/$discovery/rest?version=v1"
PREVIEW = "Developer Preview"


def fetch(url: str = DOCS_DISCOVERY) -> dict[str, Any]:
    response = httpx.get(url, timeout=30.0)
    response.raise_for_status()
    return response.json()


def _status(description: str | None) -> str:
    if description is None:
        return "absent"
    return "preview" if PREVIEW in description else "general availability"


def feature_status(discovery: dict[str, Any]) -> dict[str, Any]:
    """Each watched feature: absent, preview, or general availability, by the discovery document's own descriptions."""
    schemas = discovery.get("schemas", {})
    mode = schemas.get("WriteControl", {}).get("properties", {}).get("writeMode")
    suggest = None
    if mode and "SUGGEST" in (mode.get("enum") or []):
        suggest = mode.get("enumDescriptions", [""] * len(mode["enum"]))[mode["enum"].index("SUGGEST")] + " " + (mode.get("description") or "")
    comment = schemas.get("InsertCommentRequest")
    return {
        "revision": discovery.get("revision"),
        "features": {
            "suggest_mode": {"status": _status(suggest), "what": "documents.batchUpdate writeControl.writeMode = SUGGEST: edits as suggestions",
                             "jason": "tasks.meeting_agenda.insertion_requests with GoogleDocs.batch_update(write_mode='SUGGEST')"},
            "anchored_comments": {"status": _status(comment.get("description") if comment else None),
                                  "what": "documents.batchUpdate insertComment: a comment anchored to a range",
                                  "jason": "not built; a comment per agenda item or packet note"},
        },
    }


__all__ = ["fetch", "feature_status", "DOCS_DISCOVERY"]
