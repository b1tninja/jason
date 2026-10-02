"""jason's labels on the association's Drive files, as appProperties.

``plan`` reads what is on disk and gives each Drive file the jason_* properties it should carry: the document kind and
Civil Code 5200 records from `jason drive`, the meeting dates, latest agenda item, topics, incident, and claims from the
agenda links, and the meeting records from the meeting catalog. Only a file in the association's Drive listing
(``data/drive/files.json``) is labeled; a Google Photos album, a web page, or a link to a file not in the listing is
counted and skipped.

``diff`` compares a plan with a file's current appProperties: the cache ``data/drive/app-properties.json`` (what jason
last read or wrote), or a live read. ``apply`` writes only jason's own keys, reads each file live first, and removes a
jason key only when the plan no longer has a value for it. It never writes or removes a key it does not own, including
``jason_hold``. ``search`` finds files by one property. A label is a lead, not a classification.
"""

from __future__ import annotations

import importlib
import json
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from jason.community.drive_labels import (
    LIST_SEPARATOR,
    PROPERTIES_PER_APP,
    Label,
    LabelProperty,
    LabelWriter,
    fit,
    fits,
)

CACHE = Path("drive") / "app-properties.json"


class Origin:
    """Why a file is in the plan."""

    AGENDA_LINK = "agenda link"
    MEETING_RECORD = "meeting record"
    DRIVE_RULE = "drive classification"


def schema(community: Any = None) -> tuple[LabelProperty, ...]:
    """The appProperties rows: the community's ``app_properties()`` when it has them, else ``mystique/labels.py``."""
    hook = getattr(community, "app_properties", None)
    rows = hook() if callable(hook) else None
    if rows:
        return tuple(rows)
    from jason.community import mystique

    mystique()                                   # registers the mystique package
    return tuple(importlib.import_module("mystique.labels").APP_PROPERTIES)


def owned_keys(rows: Iterable[LabelProperty]) -> frozenset[str]:
    """The keys drive-labels writes and may remove."""
    return frozenset(r.key for r in rows if r.writer is LabelWriter.DRIVE_LABELS)


def _load(path: Path) -> Any:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _distinct(values: Iterable[str]) -> list[str]:
    seen: dict[str, None] = {}
    for v in values:
        v = (v or "").strip()
        if v:
            seen.setdefault(v, None)
    return list(seen)


def _topic_names(values: Iterable[str]) -> list[str]:
    from jason.community.topics import Topic

    by_value = {t.value: t.name.lower() for t in Topic}
    return _distinct(by_value.get(v, v) for v in values)


def _incident_text(incident: dict[str, Any]) -> str:
    where = "/".join(incident.get("addresses") or [])
    if not where and incident.get("buildings"):
        where = "bldg " + "/".join(str(b) for b in incident["buildings"])
    causes = ",".join(incident.get("causes") or [])
    return " ".join(p for p in (incident.get("first") or "", where, causes and f"({causes})") if p)


def _derive(link: dict[str, Any] | None, meetings: list[dict[str, Any]], held: dict[str, Any] | None) -> dict[Label, str]:
    values: dict[Label, str] = {}
    kind = (held or {}).get("kind") or (link or {}).get("documentKind")
    if kind:
        values[Label.KIND] = str(kind)
    records = (held or {}).get("records") or []
    if records:
        values[Label.RECORDS] = LIST_SEPARATOR.join(_distinct(records))
    labels = sorted((link or {}).get("labels") or [], key=lambda l: l.get("date") or "", reverse=True)
    dates = _distinct([*(l.get("date") for l in labels), *(m.get("date") for m in meetings)])
    if dates:
        values[Label.MEETINGS] = LIST_SEPARATOR.join(sorted(dates, reverse=True))
    if labels:
        latest = labels[0]
        item = " / ".join(p for p in ((latest.get("item") or "").strip(), (latest.get("subitem") or "").strip()) if p)
        if item:
            values[Label.ITEM] = item
    topics = _topic_names((link or {}).get("topics") or [])
    if topics:
        values[Label.TOPICS] = LIST_SEPARATOR.join(topics)
    likely = [i for i in (link or {}).get("incidents") or [] if i.get("likely")]
    if likely:
        values[Label.INCIDENT] = _incident_text(likely[0])
        claims = _distinct(c for i in likely for c in i.get("claims") or [])
        if claims:
            values[Label.CLAIMS] = LIST_SEPARATOR.join(claims)
    if (held or {}).get("confidential") or any(m.get("confidential") for m in meetings):
        values[Label.CONFIDENTIAL] = "1"
    return values


def plan(data_dir: str | Path, community: Any = None) -> dict[str, Any]:
    """Each Drive file's jason_* properties from the stores on disk, with counts. Reads nothing from Google."""
    data_dir = Path(data_dir)
    rows = schema(community)
    by_label = {r.label: r for r in rows}
    listing = {f["id"]: f for f in (_load(data_dir / "drive" / "files.json") or {}).get("files") or [] if f.get("id")}
    holdings = {r["id"]: r for r in (_load(data_dir / "drive" / "holdings.json") or {}).get("rows") or [] if r.get("id")}
    from jason.tasks.agenda_kinds import decisions

    agenda_kinds = decisions(data_dir, "Drive")
    links: dict[str, dict[str, Any]] = {}
    skipped: Counter[str] = Counter()
    for t in (_load(data_dir / "meetings" / "agenda-links.json") or {}).get("targets") or []:
        drive_id = (t.get("drive") or {}).get("id")
        if not drive_id or not t.get("inDrive"):
            skipped[t.get("kind") or "unknown"] += 1
            continue
        links[drive_id] = t
    meetings: dict[str, list[dict[str, Any]]] = {}
    for m in (_load(data_dir / "meetings" / "catalog.json") or {}).get("meetings") or []:
        for r in m.get("records") or []:
            if r.get("where") == "Drive" and r.get("ref"):
                meetings.setdefault(r["ref"], []).append(r)
    classified = {i for i, h in holdings.items() if h.get("kind") or h.get("records") or h.get("confidential")}
    files: list[dict[str, Any]] = []
    problems: list[str] = []
    not_listed = 0
    for file_id in sorted(set(links) | set(meetings) | classified):
        entry = listing.get(file_id)
        if entry is None:
            not_listed += 1
            continue
        origins = [o for o, hit in ((Origin.AGENDA_LINK, file_id in links), (Origin.MEETING_RECORD, file_id in meetings),
                                    (Origin.DRIVE_RULE, file_id in classified)) if hit]
        props: dict[str, str] = {}
        held = holdings.get(file_id)
        if not (held or {}).get("kind") and file_id in agenda_kinds:
            # The Drive rules left the file unclassified; the agenda items that used it decided (jason.tasks.agenda_kinds).
            held = {**(held or {}), "kind": agenda_kinds[file_id]["kind"]}
        for label, raw in _derive(links.get(file_id), meetings.get(file_id, []), held).items():
            row = by_label.get(label)
            if row is None or row.writer is not LabelWriter.DRIVE_LABELS:
                continue
            value = fit(row, raw)
            if value is None:
                problems.append(f"{file_id}: {row.key} value is too long to write exactly")
                continue
            props[row.key] = value
        if not props:
            continue
        files.append({"id": file_id, "name": entry.get("name"), "path": entry.get("path"),
                      "mimeType": entry.get("mimeType"), "origins": origins, "properties": props})
    by_kind = Counter(f["properties"].get(Label.KIND.value, "(none)") for f in files)
    by_topic = Counter(t for f in files for t in (f["properties"].get(Label.TOPICS.value) or "").split(LIST_SEPARATOR) if t)
    by_origin = Counter(o for f in files for o in f["origins"])
    by_key = Counter(k for f in files for k in f["properties"])
    return {
        "builtAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "files": files,
        "counts": {
            "files": len(files),
            "byOrigin": dict(by_origin.most_common()),
            "byKey": dict(by_key.most_common()),
            "byKind": dict(by_kind.most_common()),
            "byTopic": dict(by_topic.most_common()),
            "linksWithoutDriveFile": dict(skipped.most_common()),
            "notInDriveListing": not_listed,
        },
        "problems": problems,
        "caveats": [
            "A label is a lead from jason's rules, not a classification; a person confirms it from the file.",
            "appProperties are private to jason's OAuth application: the Drive UI does not show them.",
            "A search matches a whole value exactly; a list label (meetings, topics, claims) matches only as written.",
        ],
    }


def load_cache(data_dir: str | Path) -> dict[str, dict[str, str]]:
    """Each file's appProperties as jason last read or wrote them."""
    body = _load(Path(data_dir) / CACHE) or {}
    return {k: dict(v) for k, v in (body.get("files") or {}).items()}


def save_cache(data_dir: str | Path, files: dict[str, dict[str, str]]) -> Path:
    path = Path(data_dir) / CACHE
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {"savedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"), "files": files}
    path.write_text(json.dumps(body, indent=2, sort_keys=True), encoding="utf-8")
    return path


def diff(planned: dict[str, str], current: dict[str, str], rows: Iterable[LabelProperty], *,
         today: str | None = None) -> dict[str, str | None]:
    """The jason keys to set (a value) or remove (None). Only owned keys appear; ``jason_labeled_at`` is set when any
    other owned key changes."""
    rows = tuple(rows)
    owned = owned_keys(rows) - {Label.LABELED_AT.value}
    changes: dict[str, str | None] = {}
    for key in sorted(owned):
        new, old = planned.get(key), current.get(key)
        if new != old and (new is not None or old is not None):
            changes[key] = new
    if changes and Label.LABELED_AT.value in owned_keys(rows):
        changes[Label.LABELED_AT.value] = today or date.today().isoformat()
    return changes


def pending(plan_body: dict[str, Any], cache: dict[str, dict[str, str]], rows: Iterable[LabelProperty]) -> list[dict[str, Any]]:
    """Each planned file whose cached appProperties differ from the plan, with the changes."""
    rows = tuple(rows)
    out: list[dict[str, Any]] = []
    for f in plan_body["files"]:
        changes = diff(f["properties"], cache.get(f["id"], {}), rows)
        if changes:
            out.append({**f, "cached": f["id"] in cache, "changes": changes})
    return out


def _check(file_id: str, changes: dict[str, str | None], current: dict[str, str], owned: frozenset[str]) -> None:
    for key, value in changes.items():
        if key not in owned:
            raise ValueError(f"{file_id}: {key} is not a key drive-labels owns")
        if value is not None and not fits(key, value):
            raise ValueError(f"{file_id}: {key} does not fit in 124 bytes")
    after = {**current, **{k: v for k, v in changes.items() if v is not None}}
    for key, value in changes.items():
        if value is None:
            after.pop(key, None)
    if len(after) > PROPERTIES_PER_APP:
        raise ValueError(f"{file_id}: {len(after)} appProperties would exceed {PROPERTIES_PER_APP}")


def apply(drive: Any, plan_body: dict[str, Any], *, yes: bool, data_dir: str | Path | None = None,
          rows: Iterable[LabelProperty] | None = None, limit: int = 0, only: str = "", today: str | None = None,
          log: Callable[[str], None] | None = None) -> dict[str, Any]:
    """Write each file's jason keys. Without ``yes`` nothing is sent. Each file is read live first and diffed; only its
    changed jason keys are sent, so every other key is kept. The cache is updated with what Drive returned."""
    from jason.google.drive_properties import get_app_properties, set_app_properties

    if not yes:
        raise PermissionError("drive-labels writes need --yes")
    rows = tuple(rows) if rows is not None else schema()
    owned = owned_keys(rows)
    cache = load_cache(data_dir) if data_dir is not None else {}
    result: dict[str, Any] = {"written": 0, "unchanged": 0, "failed": [], "files": []}
    for f in plan_body["files"]:
        if only and f["id"] != only:
            continue
        if limit and result["written"] >= limit:
            break
        try:
            current = get_app_properties(drive, f["id"])
            changes = diff(f["properties"], current, rows, today=today)
            if not changes:
                cache[f["id"]] = current
                result["unchanged"] += 1
                continue
            _check(f["id"], changes, current, owned)
            after = set_app_properties(drive, f["id"], changes)
        except Exception as exc:  # one file's failure is reported; the others go on
            result["failed"].append({"id": f["id"], "error": str(exc)})
            if log:
                log(f"failed {f['id']}: {exc}")
            continue
        cache[f["id"]] = after
        result["written"] += 1
        result["files"].append({"id": f["id"], "name": f.get("name"), "changes": changes})
        if log:
            log(f"labeled {f.get('name')} ({f['id']}): {', '.join(changes)}")
    if data_dir is not None:
        result["cache"] = str(save_cache(data_dir, cache))
    return result


def show(plan_body: dict[str, Any], file_id: str, current: dict[str, str], rows: Iterable[LabelProperty]) -> dict[str, Any]:
    """One file's planned properties beside its current appProperties and the changes."""
    rows = tuple(rows)
    f = next((x for x in plan_body["files"] if x["id"] == file_id), None)
    planned = (f or {}).get("properties") or {}
    return {"id": file_id, "inPlan": f is not None, "name": (f or {}).get("name"), "path": (f or {}).get("path"),
            "origins": (f or {}).get("origins") or [], "planned": planned, "current": current,
            "changes": diff(planned, current, rows) if f is not None else {},
            "notOwned": sorted(k for k in current if k not in owned_keys(rows))}


def search(drive: Any, key: str, value: str) -> list[dict[str, Any]]:
    """Files whose appProperty ``key`` equals ``value`` exactly. Read-only."""
    from jason.google.drive_properties import search as search_properties

    return search_properties(drive, key, value)


def summary_lines(plan_body: dict[str, Any], waiting: list[dict[str, Any]], *, limit: int = 10) -> list[str]:
    c = plan_body["counts"]
    lines = [f"{c['files']} Drive files to label; {len(waiting)} differ from the cache (data/drive/app-properties.json)",
             f"not in the Drive listing: {c['notInDriveListing']}; links with no Drive file: "
             + ", ".join(f"{k} {v}" for k, v in c["linksWithoutDriveFile"].items())]
    for title, key in (("by origin", "byOrigin"), ("by key", "byKey"), ("by kind", "byKind"), ("by topic", "byTopic")):
        items = list(c[key].items())
        shown = ", ".join(f"{k} {v}" for k, v in items[:15]) + (f", ... ({len(items) - 15} more)" if len(items) > 15 else "")
        lines.append(f"{title}: {shown}")
    for p in plan_body["problems"][:limit]:
        lines.append(f"problem: {p}")
    if waiting and limit:
        lines.append("")
        lines.append(f"dry run: the first {min(limit, len(waiting))} files and the exact properties that would be set")
        for f in waiting[:limit]:
            lines.append(f"  {f['id']}  {f.get('path') or f.get('name')}")
            for k, v in f["changes"].items():
                lines.append(f"      {k} = {'(remove)' if v is None else repr(v)}")
    return lines


__all__ = ["CACHE", "Origin", "apply", "diff", "load_cache", "owned_keys", "pending", "plan", "save_cache", "schema",
           "search", "show", "summary_lines"]
