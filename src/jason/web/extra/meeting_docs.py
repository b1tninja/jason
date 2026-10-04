"""Document references for the meetings screens (docs/console/doc-component.md): a meeting's records, and a hearing's
notice, as the ``DocRef``s the console's ``Doc`` shows.

- ``record_refs`` takes a meeting's records as the catalog keeps them (``jason.tasks.meeting_catalog``, each with
  ``kind``, ``where``, ``location``, and ``ref``) and answers the documents among them, grouped by kind: the notice,
  the agendas, the minutes (draft and final), the transcript, and the recordings. A Drive record is ``drive:<id>``, a
  PayHOA library record ``library:<id>``, and a file jason keeps (a draft, a Zoom copy, a Gmail attachment) ``file:``
  its path under the data folder. A record no resolver reads yet (Zoom's cloud, a Gmail message, PayHOA's mailing
  log) is left out: it stays a badge.
- ``hearing_refs`` answers a saved hearing's notice: the Doc made from the template (Drive) and jason's draft beside the
  plan (``zoom/hearings/<file>``). A hearing is a member's discipline, so both are P3 (``zoom/hearings/`` is P3 by
  ``jason.web.access``; the Drive Doc is held at P3 here too).

Reads metadata only: nothing here reaches Google, PayHOA, or Zoom.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

# The record kinds that are documents a person opens, in the order a meeting's records are read.
KINDS = ("meeting notice", "agenda", "executive session agenda", "draft minutes", "minutes", "transcript",
         "audio recording", "video recording")
# Which copy governs first: the posted copy (PayHOA's library), then Drive, then a copy jason keeps.
WHERE_ORDER = ("PayHOA library", "Drive", "jason's copy", "jason draft", "Gmail")
RESTRICTED = "P3"


def _record_ref(root: Path, record: dict[str, Any]) -> dict[str, Any] | None:
    from jason.approvals.docref import drive_ref, file_ref, library_ref

    where = str(record.get("where") or "")
    location = str(record.get("location") or "").replace("\\", "/")
    ref = str(record.get("ref") or "")
    name = " ".join(str(record.get("name") or "").split()) or None
    try:
        if where == "Drive" and ref:
            return drive_ref(ref, name=name, data_dir=root)
        if where == "PayHOA library" and ref:
            return library_ref(ref, name=name, data_dir=root)
        if where in ("jason's copy", "jason draft", "Gmail") and location and not location.startswith(("gmail:", "zoom:")):
            return file_ref(location, name=name, data_dir=root)
    except ValueError:
        return None
    return None


def record_refs(records: list[dict[str, Any]], data_dir: Path) -> list[dict[str, Any]]:
    """A meeting's documents as references, grouped by record kind in ``KINDS`` order: ``[{kind, docs: [DocRef]}]``,
    each group's copies with the posted one first. One copy kept in two places is listed in each."""
    root = Path(data_dir)
    groups: dict[str, list[tuple[int, dict[str, Any]]]] = {}
    for record in records or ():
        kind = str(record.get("kind") or "")
        if kind not in KINDS:
            continue
        ref = _record_ref(root, record)
        if ref is None:
            continue
        where = str(record.get("where") or "")
        rank = WHERE_ORDER.index(where) if where in WHERE_ORDER else len(WHERE_ORDER)
        groups.setdefault(kind, []).append((rank, ref))
    return [{"kind": kind, "docs": [r for _, r in sorted(groups[kind], key=lambda x: x[0])]} for kind in KINDS if kind in groups]


def _held(ref: dict[str, Any]) -> dict[str, Any]:
    """The reference at P3 at least: a hearing's documents open only in the private view."""
    return {**ref, "level": RESTRICTED}


def hearing_refs(hearing: dict[str, Any], data_dir: Path) -> list[dict[str, Any]]:
    """A hearing's notice as references, the Doc sent first: ``drive:<noticeDoc.id>`` when a Doc was made from the
    template, then jason's draft ``zoom/hearings/<file>`` (``notice`` is its path under ``data/zoom``)."""
    from jason.approvals.docref import drive_ref, file_ref
    from jason.tasks.zoom import ZOOM_DIR

    root = Path(data_dir)
    day = str(hearing.get("start") or "")[:10]
    out: list[dict[str, Any]] = []
    doc = hearing.get("noticeDoc") if isinstance(hearing.get("noticeDoc"), dict) else {}
    if doc.get("id"):
        try:
            out.append(_held(drive_ref(str(doc["id"]), name=f"Hearing notice, {day} (Doc)", data_dir=root)))
        except ValueError:
            pass
    notice = str(hearing.get("notice") or "").replace("\\", "/")
    if notice and notice.startswith("hearings/"):                 # jason's draft, as save_hearing names it; nothing else
        try:
            out.append(_held(file_ref(f"{ZOOM_DIR}/{notice}", name=f"Hearing notice, {day} (jason's draft)", data_dir=root)))
        except ValueError:
            pass
    return out


__all__ = ["KINDS", "hearing_refs", "record_refs"]
