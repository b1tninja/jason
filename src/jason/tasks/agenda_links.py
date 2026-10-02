"""The files the board's agendas link to, labeled by the meeting and agenda item that used them.

``fetch`` reads every agenda Google Doc in the Drive listing (read-only) and keeps it in ``data/meetings/agenda-docs``,
fetching one again only when Drive shows it changed. ``build`` reads the links from those Docs and from the agenda PDFs
on disk (the PayHOA library's and the Gmail attachments'), resolves each Drive link against the Drive listing, and
writes ``data/meetings/agenda-links.json``:

- by meeting: each agenda's links under their items;
- by file: each linked target with every label the agendas gave it (meeting date, item, sub-item), the topics the
  labels name (``topics_of``), the document kind its name suggests (``classify_document``), and where it is in Drive,
  or that it is not in the listing (shared from another account, moved to the trash, or never in this Drive).

A label says where the board used a file; it is a lead for filing it, not a classification. Nothing is moved, renamed,
or shared.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from jason.community.agenda_links import AgendaLink, LinkKind, links_in_doc, links_in_pdf
from jason.community.meeting_records import RecordKind, meeting_date, record_kind

DOCS = Path("meetings") / "agenda-docs"
OUT = Path("meetings") / "agenda-links.json"
AGENDAS = (RecordKind.AGENDA, RecordKind.EXECUTIVE_AGENDA)
SKIP_KINDS = {LinkKind.ZOOM, LinkKind.CALENDAR, LinkKind.INTERNAL}   # the meeting's own Zoom link and calendar event, and a jump within the agenda, label no file


def _drive_rows(data_dir: Path) -> list[dict[str, Any]]:
    path = Path(data_dir) / "drive" / "files.json"
    if not path.is_file():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw if isinstance(raw, list) else raw.get("files", [])


def agenda_docs(data_dir: Path, community: Any) -> list[dict[str, Any]]:
    """The agenda Google Docs in the Drive listing, by the specification's record rules."""
    rules = tuple(community.meeting_record_rules())
    return [r for r in _drive_rows(data_dir) if r.get("mimeType") == "application/vnd.google-apps.document"
            and record_kind(r["name"], r.get("path", ""), rules) in AGENDAS]


def fetch(docs: Any, data_dir: Path, community: Any, *, log: Callable[[str], None] | None = None) -> dict[str, int]:
    """Read each agenda Doc that is new or changed since it was kept (read-only)."""
    root = Path(data_dir) / DOCS
    root.mkdir(parents=True, exist_ok=True)
    counts = {"agendas": 0, "fetched": 0, "failed": 0}
    for row in agenda_docs(data_dir, community):
        counts["agendas"] += 1
        path = root / f"{row['id']}.json"
        if path.is_file() and json.loads(path.read_text(encoding="utf-8")).get("_modified") == row.get("modified"):
            continue
        try:
            doc = docs.get(row["id"])
        except Exception as exc:  # a Doc shared with the association and since unshared
            counts["failed"] += 1
            if log:
                log(f"{row['name']}: {exc}")
            continue
        doc["_modified"], doc["_path"] = row.get("modified"), row.get("path")
        path.write_text(json.dumps(doc), encoding="utf-8")
        counts["fetched"] += 1
    return counts


def _pdf_agendas(data_dir: Path, community: Any) -> list[tuple[str, str, Path]]:
    """(name, where, path) of the agenda PDFs on disk: the PayHOA library's and the Gmail attachments'."""
    rules = tuple(community.meeting_record_rules())
    out = []
    lib = Path(data_dir) / "library" / "files"
    if lib.is_dir():
        out += [(p.name, f"PayHOA library: {p.relative_to(lib).as_posix()}", p) for p in lib.rglob("*.pdf")
                if record_kind(p.name, p.as_posix(), rules) in AGENDAS]
    files = Path(data_dir) / "gmail" / "files.json"
    if files.is_file():
        raw = json.loads(files.read_text(encoding="utf-8"))
        for f in raw if isinstance(raw, list) else raw.get("files", []):
            if f.get("name", "").lower().endswith(".pdf") and record_kind(f["name"], "", rules) in AGENDAS:
                out.append((f["name"], f"Gmail: {f['name']}", Path(data_dir) / str(f["path"]).replace("\\", "/")))
    return out


PHOTO_LINKS = Path("meetings") / "photo-links.json"


def resolve_photo_links(data_dir: Path, *, http: Any = None) -> dict[str, str]:
    """Each Google Photos short link (``photos.app.goo.gl``) in the agendas and the album share URL it redirects to,
    kept in ``data/meetings/photo-links.json``. Only the redirect is read; the album is not opened."""
    import httpx

    path = Path(data_dir) / PHOTO_LINKS
    known = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    shorts = {t["url"] for t in load(data_dir).get("targets", []) if t["kind"] == LinkKind.PHOTOS.value and "goo.gl" in t["url"]}
    client = http or httpx.Client(timeout=20, follow_redirects=False, headers={"User-Agent": "Mozilla/5.0"})
    try:
        for url in sorted(shorts - set(known)):
            try:
                response = client.get(url)
            except Exception:
                continue
            location = response.headers.get("location", "") if response.is_redirect else ""
            if "photos.google.com/share/" in location:
                known[url] = location.split("?")[0]
    finally:
        if http is None:
            client.close()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(known, indent=1), encoding="utf-8")
    return known


def _incident_index(data_dir: Path) -> dict[str, dict[str, Any]]:
    """Each Drive path (and each copy) that `jason incidents` placed in an event, with the event's summary."""
    path = Path(data_dir) / "reports" / "incidents.json"
    if not path.is_file():
        return {}
    out: dict[str, dict[str, Any]] = {}
    for e in json.loads(path.read_text(encoding="utf-8")).get("events", []):
        summary = {"first": e.get("first"), "causes": e.get("causes") or [], "addresses": e.get("addresses") or [],
                   "buildings": e.get("buildings") or [], "claims": e.get("claims") or []}
        for d in e.get("documents") or []:
            for ref in [d.get("ref", "")] + list(d.get("also") or []):
                if str(ref).startswith("drive:"):
                    out.setdefault(ref[len("drive:"):], summary)
    return out


def build(data_dir: Path, community: Any) -> dict[str, Any]:
    from jason.community.topics import topics_of

    rules = tuple(community.agenda_link_rules())
    schedule = community.meeting_schedule()
    drive = {r["id"]: r for r in _drive_rows(data_dir)}
    topic_rules = tuple(getattr(community, "topic_rules", lambda: ())())
    agendas: list[dict[str, Any]] = []
    by_doc_url: dict[tuple[str, str], AgendaLink] = {}

    for path in sorted((Path(data_dir) / DOCS).glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        day = meeting_date(doc.get("title", ""), doc.get("_path", ""), schedule=schedule)
        links = [l for l in links_in_doc(doc, rules) if l.kind not in SKIP_KINDS]
        for link in links:
            by_doc_url.setdefault((str(day), link.url), link)
        agendas.append({"date": day.isoformat() if day else None, "title": doc.get("title"), "source": f"Google Doc {path.stem}",
                        "links": links})
    for name, where, path in _pdf_agendas(data_dir, community):
        day = meeting_date(name, schedule=schedule)
        links = [l for l in links_in_pdf(path, rules) if l.kind not in SKIP_KINDS]
        for link in links:                     # a PDF exported from the Doc takes the Doc's item for the same link
            known = by_doc_url.get((str(day), link.url))
            if known:
                link.item, link.subitem, link.text = known.item, known.subitem, known.text
        if links:
            agendas.append({"date": day.isoformat() if day else None, "title": name, "source": where, "links": links})

    photo_links = json.loads((Path(data_dir) / PHOTO_LINKS).read_text(encoding="utf-8")) if (Path(data_dir) / PHOTO_LINKS).is_file() else {}
    targets: dict[str, dict[str, Any]] = {}
    for agenda in agendas:
        for link in agenda["links"]:
            key = link.target or link.url
            t = targets.setdefault(key, {"key": key, "kind": link.kind.value, "url": link.url, "names": [], "labels": [], "topics": [],
                                         "documentKind": None, "drive": None})
            if link.text and link.text not in t["names"]:
                t["names"].append(link.text)
            label = {"date": agenda["date"], "item": link.item, "subitem": link.subitem, "agenda": agenda["title"]}
            # A PDF exported from the Doc repeats the Doc's label: one label per meeting, item, and sub-item.
            if link.label() and not any((l["date"], l["item"], l["subitem"]) == (label["date"], label["item"], label["subitem"])
                                        for l in t["labels"]):
                t["labels"].append(label)
    for t in targets.values():
        t["labels"].sort(key=lambda l: l["date"] or "", reverse=True)
        row = drive.get(t["key"])
        if row:
            t["drive"] = {"id": row["id"], "name": row["name"], "path": row.get("path"), "mimeType": row.get("mimeType")}
        name = (row or {}).get("name") or (t["names"][0] if t["names"] else "")
        kind = community.classify_document(name, path=(row or {}).get("path", "")) if name else None
        t["documentKind"] = kind.value if kind is not None else None
        words = " ".join([name] + [f"{l['item']} {l['subitem']}" for l in t["labels"]])
        t["topics"] = [topic.value for topic in topics_of(words, topic_rules)] if topic_rules else []
        t["inDrive"] = row is not None or t["kind"] not in (LinkKind.DRIVE_FILE.value, LinkKind.DRIVE_FOLDER.value,
                                                              LinkKind.GOOGLE_DOC.value)
        if t["kind"] == LinkKind.PHOTOS.value:
            t["shareUrl"] = photo_links.get(t["url"]) or (t["url"] if "photos.google.com/share/" in t["url"] else None)

    # A photo album, a folder, or a web page is known by its neighbors: the files linked beside it under the same
    # item. Their incidents (by `jason incidents`) are the target's likely incidents.
    incidents = _incident_index(data_dir)
    by_label: dict[tuple, list[dict[str, Any]]] = defaultdict(list)
    for t in targets.values():
        for l in t["labels"]:
            by_label[(l["date"], l["item"], l["subitem"])].append(t)
    for t in targets.values():
        found: dict[str, dict[str, Any]] = {}
        own = (t.get("drive") or {}).get("path")
        if own and own in incidents:
            found[json.dumps(incidents[own], sort_keys=True)] = {**incidents[own], "via": "the file itself"}
        for l in t["labels"]:
            for sib in by_label[(l["date"], l["item"], l["subitem"])]:
                p = (sib.get("drive") or {}).get("path")
                if sib is not t and p in incidents:
                    found.setdefault(json.dumps(incidents[p], sort_keys=True), {**incidents[p], "via": f"linked beside {p.rsplit('/', 1)[-1]}"})
        # An incident that began within six months before a meeting that used the target is likely; older ones are
        # listed after it as possible (a standing contract linked beside the claim's papers, for instance).
        uses = [l["date"] for l in t["labels"] if l["date"]]

        def gap(e: dict[str, Any]) -> int:
            from datetime import date as _date

            if not uses or not e.get("first"):
                return 10 ** 6
            return min(abs((_date.fromisoformat(u) - _date.fromisoformat(e["first"])).days) for u in uses)

        ranked = sorted(found.values(), key=gap)
        t["incidents"] = [{**e, "likely": gap(e) <= 183} for e in ranked]

    def row(link: AgendaLink) -> dict[str, Any]:
        return {"item": link.item, "subitem": link.subitem, "text": link.text, "url": link.url, "kind": link.kind.value,
                "target": link.target or None, "page": link.page}

    result = {
        "builtAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "agendas": [{**a, "links": [row(l) for l in a["links"]]} for a in sorted(agendas, key=lambda a: a["date"] or "", reverse=True)],
        "targets": sorted(targets.values(), key=lambda t: (-len(t["labels"]), t["key"])),
    }
    out = Path(data_dir) / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=1), encoding="utf-8")
    return result


def load(data_dir: Path) -> dict[str, Any]:
    path = Path(data_dir) / OUT
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def for_meeting(data_dir: Path, day: str) -> list[dict[str, Any]]:
    """The links of the agendas for one meeting, by item, with each Drive target's name and path."""
    data = load(data_dir)
    targets = {t["key"]: t for t in data.get("targets", [])}
    out = []
    for a in data.get("agendas", []):
        if a["date"] == day:
            for l in a["links"]:
                t = targets.get(l["target"] or l["url"], {})
                out.append({**l, "agenda": a["title"], "source": a["source"], "path": (t.get("drive") or {}).get("path"),
                            "documentKind": t.get("documentKind"), "topics": t.get("topics")})
    return out


def lookup(data_dir: Path, query: str) -> list[dict[str, Any]]:
    """The linked targets whose Drive id, URL, name, or path holds ``query``, with their labels."""
    q = query.split("?")[0].casefold()
    return [t for t in load(data_dir).get("targets", [])
            if q in t["key"].casefold() or q in t["url"].casefold() or any(q in n.casefold() for n in t["names"])
            or q in json.dumps(t.get("drive") or {}).casefold() or q in (t.get("shareUrl") or "").casefold()]


def summary_lines(result: dict[str, Any], *, limit: int = 30) -> list[str]:
    targets = result.get("targets", [])
    kinds: dict[str, int] = defaultdict(int)
    for t in targets:
        kinds[t["kind"]] += 1
    missing = [t for t in targets if not t["inDrive"]]
    lines = [f"{len(result.get('agendas', []))} agendas link {len(targets)} targets: " + ", ".join(f"{v} {k}" for k, v in sorted(kinds.items())),
             f"{len(missing)} Drive links are not in the Drive listing (shared from another account, trashed, or never here)", ""]
    for t in targets[:limit]:
        where = (t.get("drive") or {}).get("path") or t["url"]
        labels = "; ".join(f"{l['date']} {l['item']}" + (f" / {l['subitem']}" if l["subitem"] else "") for l in t["labels"][:4])
        extra = f" [{t['documentKind']}]" if t.get("documentKind") else ""
        lines.append(f"- {t['kind']}: {(t['names'] or [''])[0][:60]}{extra} -> {where[:90]}")
        lines.append(f"    used at: {labels}" + (f" (+{len(t['labels']) - 4} more)" if len(t["labels"]) > 4 else ""))
        if t.get("topics"):
            lines.append(f"    topics: {', '.join(t['topics'])}")
    return lines


__all__ = ["agenda_docs", "build", "fetch", "for_meeting", "load", "lookup", "summary_lines"]
