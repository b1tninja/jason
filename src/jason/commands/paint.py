"""``jason paint``: the association's paint schedule with each color's catalog data, and a check against the maker.

``jason paint`` prints each schedule row with the Sherwin-Williams color's hex, light reflectance value (LRV), family,
and whether the maker lists it for exteriors. ``--check`` compares each printed number and name with the catalog and
reports a color renamed, discontinued, or missing (exit 1 when one needs a person). ``--find TEXT`` searches the
catalog by name or number. ``--match CODE`` lists the closest current colors, for a discontinued color or a
touch-up question. ``--page`` writes a swatch page to the paint folder. The catalog is one open API call kept on disk
for a week (``jason.sources.sherwin_williams``); ``--refresh`` fetches it again. It changes nothing in the
specification: a renamed or discontinued color is for the board and the architectural record.
"""

from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path
from typing import Any, Callable


def _catalog(args: argparse.Namespace):
    from jason.commands._shared import data_dir
    from jason.sources.sherwin_williams import SherwinWilliams

    cache = data_dir(args) / "paint" / "sherwin-williams-colors.json"
    sw = SherwinWilliams(cache)
    sw.load(refresh=bool(args.refresh))
    return sw


def _line(color: Any) -> str:
    kinds = "exterior" if color.exterior else "interior only"
    status = "  DISCONTINUED" if color.archived else ""
    return f"{color.code:8} {color.name:28} {color.hex}  LRV {color.lrv:5.1f}  {', '.join(color.families) or '-':24} {kinds}{status}"


def cmd_paint(args: argparse.Namespace, agent_factory: Callable[[Any], Any]) -> int:
    from jason.community import community
    from jason.commands._shared import to_json
    from jason.community.paint import FindingKind, check

    with _catalog(args) as sw:
        if args.to_doc:
            return _to_doc(args, sw, agent_factory)
        if args.read:
            return _read(args, sw)
        if args.find:
            hits = sw.search(args.find)
            print("\n".join(_line(c) for c in hits) or f"no color matches {args.find!r}")
            return 0 if hits else 1
        if args.match:
            color = sw.color(args.match)
            if color is None:
                print(f"no catalog color {args.match!r}", file=sys.stderr)
                return 2
            print(f"closest current colors to {_line(color)}")
            for distance, near in sw.nearest(color, exterior=True if args.exterior else None):
                print(f"  dE {distance:4.1f}  {_line(near)}")
            return 0
        schedules = community().paint_schedules()
        if not schedules:
            print("no paint schedule in this profile: add PaintSchedule rows and Community.paint_schedules()")
            return 0
        if args.page:
            path = _write_page(args, schedules, sw)
            print(f"wrote {path}")
            return 0
        problems = 0
        for schedule in schedules:
            findings = check(schedule, sw)
            if args.json:
                print(to_json({"title": schedule.title, "source": schedule.source, "findings": findings}))
                problems += sum(f.needs_a_person for f in findings)
                continue
            print(f"{schedule.title}  [{schedule.prepared}]\n  original: {schedule.source}")
            for row in schedule.rows:
                print(f"{row.label}" + (f"  ({row.note})" if row.note else ""))
                for spec in row.specs:
                    found = next(f for f in findings if f.surface == row.label and f.scheme == spec.scheme and f.code == spec.code)
                    color = sw.color(spec.code) if found.kind is not FindingKind.NOT_CHECKED else None
                    detail = _line(color) if color else f"{spec.code} {spec.name} (not a Sherwin-Williams color)"
                    flag = "" if found.kind in (FindingKind.OK, FindingKind.NOT_CHECKED) else f"   <- {found.kind.value}: printed {spec.name!r}"
                    print(f"  scheme {spec.scheme}: {detail}{flag}")
            problems += sum(f.needs_a_person for f in findings)
        if args.check and problems:
            print(f"\n{problems} color(s) differ from the catalog; the number governs, and the board decides.", file=sys.stderr)
            return 1
    return 0


def _read(args: argparse.Namespace, sw: Any) -> int:
    """Read a schedule's picture with the local model, check it against the catalog, and compare it with the profile's."""
    from jason.commands._shared import data_dir, to_json
    from jason.community import community
    from jason.community.ollama_extractor import DEFAULT_MODEL, OllamaUnavailable
    from jason.community.paint import FindingKind, check
    from jason.community.paint_reader import differences, read_schedule

    try:
        read = read_schedule(Path(args.read), model=args.model or DEFAULT_MODEL)
    except OllamaUnavailable as exc:
        print(f"cannot read it: {exc}", file=sys.stderr)
        return 2
    findings = check(read, sw)
    print(f"{read.title}  [{read.prepared}]  (read by a local model: evidence, not the record)")
    for row in read.rows:
        print(f"{row.label}" + (f"  ({row.note})" if row.note else ""))
        for spec in row.specs:
            f = next(f for f in findings if f.surface == row.label and f.scheme == spec.scheme and f.code == spec.code)
            tail = f"{f.catalog_name} {f.hex}" if f.kind is not FindingKind.NOT_CHECKED else "not a Sherwin-Williams code"
            flag = "" if f.kind in (FindingKind.OK, FindingKind.NOT_CHECKED) else f"   <- {f.kind.value}"
            print(f"  scheme {spec.scheme}: {spec.code} {spec.name}  ->  {tail}{flag}")
    for known in community().paint_schedules():
        for line in differences(read, known):
            print(f"  vs {known.title}: {line}")
    if args.save:
        out = data_dir(args) / "paint" / "readings" / (Path(args.read).stem + ".json")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(to_json({"source": str(args.read), "model": args.model or DEFAULT_MODEL, "schedule": read, "findings": findings}), encoding="utf-8")
        print(f"saved {out}")
    return 0


def _to_doc(args: argparse.Namespace, sw: Any, agent_factory: Callable[[Any], Any]) -> int:
    """The palette as a Google Doc: HTML with each swatch a shaded table cell, imported by Drive. The Doc's id is kept in
    paint/doc.json, so a rerun refreshes the same Doc (edits made in the Doc since are replaced)."""
    import json

    from jason.commands._shared import data_dir
    from jason.community import community
    from jason.community.paint_page import doc_html
    from jason.google.drive import GOOGLE_DOC_MIME_TYPE

    schedules = tuple(community().paint_schedules())
    if not schedules:
        print("no paint schedule in this profile", file=sys.stderr)
        return 2
    folder = data_dir(args) / "paint"
    state_file = folder / "doc.json"
    state = json.loads(state_file.read_text(encoding="utf-8")) if state_file.exists() else {}
    title = f"Paint palette - {schedules[0].title}"
    if not args.yes:
        where = f"in folder {args.folder}" if args.folder else "at the top level of the signed-in Drive"
        print(f"would {'refresh' if state.get('docId') else 'make'} the Doc {title!r} {where} and save its PDF beside it; --yes does it")
        return 0
    page = doc_html(schedules, sw, lambda code: sw.related(code, descriptions=folder / "details" if args.descriptions else False)).encode("utf-8")
    folder.mkdir(parents=True, exist_ok=True)
    with agent_factory(args) as agent:
        drive = agent.drive()
        doc_id = state.get("docId")
        if doc_id:
            drive.replace_content(doc_id, page, mime_type="text/html")
            drive.update_metadata(doc_id, name=title)
        else:
            doc_id = drive.upload_bytes(title, page, mime_type="text/html", parent_id=args.folder or None,
                                        convert_to=GOOGLE_DOC_MIME_TYPE,
                                        description="Paint palette (jason paint --to-doc): the schedule's swatches from the maker's catalog.")
        pdf = drive.docs().export_pdf(doc_id, folder / "palette.pdf")
    state_file.write_text(json.dumps({"docId": doc_id, "title": title}), encoding="utf-8")
    print(f"{title}: https://docs.google.com/document/d/{doc_id}/edit")
    print(f"PDF: {pdf}")
    return 0


def _write_page(args: argparse.Namespace, schedules: Any, sw: Any) -> Path:
    from jason.commands._shared import data_dir
    from jason.community.paint_page import page

    folder = data_dir(args) / "paint"
    out = folder / "schedule.html"
    folder.mkdir(parents=True, exist_ok=True)
    out.write_text(page(tuple(schedules), sw, lambda code: sw.related(code, descriptions=folder / "details" if args.descriptions else False)), encoding="utf-8")
    return out


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("paint", help="The paint schedule with each color's hex and LRV, checked against the maker's catalog")
    add_common(p)
    p.add_argument("--check", action="store_true", help="exit 1 when a color is renamed, discontinued, or missing")
    p.add_argument("--find", metavar="TEXT", help="search the catalog by color name or number")
    p.add_argument("--match", metavar="CODE", help="the closest current colors to this one (SW 7027)")
    p.add_argument("--exterior", action="store_true", help="with --match: only colors the maker lists for exteriors")
    p.add_argument("--read", metavar="IMAGE", help="read a schedule's picture with the local vision model and check it against the catalog")
    p.add_argument("--model", help="with --read: the Ollama model (default: jason's shared one)")
    p.add_argument("--save", action="store_true", help="with --read: keep the reading in the paint folder")
    p.add_argument("--page", action="store_true", help="write a swatch page to the paint folder")
    p.add_argument("--refresh", action="store_true", help="fetch the catalog again instead of using the week-old copy")
    p.add_argument("--json", action="store_true", help="print the findings as JSON")
    p.add_argument("--to-doc", action="store_true", help="make the palette a Google Doc with its swatches, and save its PDF; --yes does it")
    p.add_argument("--folder", metavar="DRIVE_ID", help="with --to-doc: the Drive folder (default: the signed-in Drive's top level)")
    p.add_argument("--yes", action="store_true", help="with --to-doc: really make or refresh the Doc")
    p.add_argument("--descriptions", action="store_true", help="with --page or --to-doc: also fetch each color's description (one call per color; the rest is read from the catalog on disk)")
    p.set_defaults(func=lambda args: cmd_paint(args, agent_factory))
