"""The codes read off documents, as the console shows them (``DocumentCode``).

``jason ingest`` decodes the QR codes on each file and keeps them by the file's hash under
``data/onboarding/ingest/codes``. This reads that cache for ``GET /api/document-codes``: no network and no decoder.

- A payload is masked here (``qr_read.redacted``): the console never receives a meeting passcode or a token.
- A link that joins a video meeting says whether the Zoom index (``data/zoom/meetings.json``) holds a record of it. A meeting
  with none is a lead: it may predate the index's recordings, or have been held on another account.
- A link that names a vendor's report portal carries the portal's key.
- Nothing here opens a link.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CODES = Path("onboarding") / "ingest" / "codes"
TEXT = Path("onboarding") / "ingest" / "text"
FORMATS = {"QRCode": "QR Code", "QR Code": "QR Code", "MicroQRCode": "MicroQRCode"}


def _zoom_ids(root: Path) -> set[str] | None:
    path = root / "zoom" / "meetings.json"
    if not path.is_file():
        return None
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    rows = body.get("meetings", []) if isinstance(body, dict) else body
    return {str(r.get("meetingId")) for r in rows if isinstance(r, dict)}


def _code(raw: dict[str, Any], zoom: set[str] | None) -> dict[str, Any]:
    from jason.community.portal_links import identify, identify_meeting
    from jason.community.qr_read import redacted

    text = str(raw.get("text") or "")
    link = bool(raw.get("link"))
    out: dict[str, Any] = {"text": redacted(text), "format": FORMATS.get(str(raw.get("format")), "QR Code"),
                           "page": int(raw.get("page") or 1), "link": link, "host": str(raw.get("host") or ""),
                           "masked": redacted(text) != text}
    portal = identify(text) if link else None
    if portal:
        out["portal"] = portal.as_dict()
    meeting = identify_meeting(text) if link else None
    if meeting:
        out["meeting"] = {**meeting.as_dict(), "recorded": bool(zoom is not None and meeting.id in zoom)}
        if zoom is None:
            out["meeting"]["recorded"] = False
            out["meeting"]["indexed"] = False                       # no Zoom index to look in: not "unrecorded"
    return out


def view(data_dir: Path, doc: str = "") -> dict[str, Any]:
    """Every document with codes, or the one named by ``doc`` (the start of its hash, or part of its name)."""
    from jason.community import qr_read

    root = Path(data_dir)
    cache = root / CODES
    if not cache.is_dir():
        return {"found": False, "note": "No codes have been read. Run `jason ingest SOURCE` on the documents.", "command": "jason ingest SOURCE"}
    names = {}
    for note in (root / TEXT).glob("*.json") if (root / TEXT).is_dir() else ():
        try:
            names[note.stem] = str(json.loads(note.read_text(encoding="utf-8")).get("file") or "")
        except (OSError, ValueError):
            continue
    zoom = _zoom_ids(root)
    docs = []
    needle = doc.strip().lower()
    for path in sorted(cache.glob("*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        name = names.get(path.stem) or path.stem[:12]
        if needle and not (path.stem.startswith(needle) or needle in name.lower()):
            continue
        if raw:
            docs.append({"sha256": path.stem, "name": name, "codes": [_code(c, zoom) for c in raw]})
    out: dict[str, Any] = {"found": True, "documents": docs, "decoder": qr_read.available() or "", "command": "jason ingest SOURCE",
                           "caveats": ["A code shows where the paper points; jason has not opened it.",
                                       "A passcode or token in a link is masked here and kept whole under data/."]}
    if not docs and needle:
        out.update(found=False, note=f"No document with codes matches {doc!r}.")
    return out


__all__ = ["view"]
