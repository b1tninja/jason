"""``jason packet``: plan and assemble a packet of documents into one PDF (the annual budget report and policy statement).

``jason packet annual-disclosures --year 2027`` plans: each part found for the year or missing, the tokens filled and
the ones left (the board's decisions), and the insurance terms not yet on file. ``--values`` writes the year's
values.json with every open token to fill. ``--make-templates --yes`` makes the template Docs on the Letterhead from
src/jason/templates/packets/ (a profile's packet_templates/ overrides a file). ``--build --yes`` fills the templates as
copies in My Drive/<packet title>/<year>, fetches
and generates the rest, and merges them into data/packets/<packet>-<year>/packet.pdf with bookmarks, page numbers, and
a manifest; ``--draft`` builds even with parts missing, with a page that names each missing part. A packet made per
building (the annual one: each building's own flood policy) is planned and built once per building, into
building-<n>.pdf, with the parts every building shares made once; ``--building N`` does one. Nothing is sent.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

GOOGLE_DOC = "application/vnd.google-apps.document"
MIN_POINTS = {"NOTICE_ASSESSMENTS_AND_FORECLOSURE": 12}      # Civil Code 5730(a): at least 12-point type


def _data_dir(args: argparse.Namespace) -> Path:
    from jason.config import Settings

    return Settings.load(args.env).payhoa_catalog.parent


def _utf16(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def text_range(doc: dict[str, Any], start_text: str, end_text: str) -> tuple[int, int] | None:
    """The Docs index range from the first ``start_text`` to the end of the next ``end_text`` in the body."""
    tab = ((doc.get("tabs") or [{}])[0].get("documentTab") or doc)
    pieces: list[tuple[int, str]] = []
    for block in (tab.get("body") or {}).get("content") or []:
        for element in (block.get("paragraph") or {}).get("elements") or []:
            run = element.get("textRun") or {}
            if run.get("content") and element.get("startIndex") is not None:
                pieces.append((element["startIndex"], run["content"]))
    text = "".join(t for _, t in pieces)
    begin = text.find(start_text)
    end = text.find(end_text, begin + 1) if begin >= 0 else -1
    if begin < 0 or end < 0:
        return None

    def index_at(offset: int) -> int:
        seen = 0
        for start, content in pieces:
            if seen + len(content) > offset:
                return start + _utf16(content[: offset - seen])
            seen += len(content)
        return pieces[-1][0] + _utf16(pieces[-1][1])

    return index_at(begin), index_at(end + len(end_text))


def _policies(data_dir: Path) -> tuple[list[dict[str, Any]], str]:
    try:
        from jason.mcp.county import insurance_policies

        return insurance_policies(data_dir=data_dir).get("policies") or [], ""
    except Exception as exc:  # the insurance parts are some of the packet; their records missing is a gap, not a stop
        return [], str(exc)


def plans(community: Any, packet: Any, year: int, data_dir: Path, *, only: str = "") -> list[Any]:
    """One plan per variant (each building), or one for a packet without variants: the parts found, the tokens, and
    each variant's own flood policy values and gaps."""
    from jason.tasks.packets import flood_values, insurance_rows, plan

    policies, error = _policies(data_dir)
    units = {int(a.building): a.unit_count for a in community.association_common_areas()}
    out = []
    for variant in ((only,) if only else packet.variants) or ("",):
        found = plan(community, packet, year, data_dir, variant=variant)
        if error:
            found.gaps.append(f"insurance records: {error}")
        elif any(p.source.ref == "insurance-summary" for p in packet.parts):
            found.gaps += insurance_rows(policies, year)[1]
        if not error and any(p.source.ref == "letter:insurance-change-notice.html" for p in packet.parts):
            from jason.tasks.insurance_notice import notice_values

            values, gaps = notice_values(policies, community)
            found.values.update({k: v for k, v in values.items() if k not in found.values})
            found.gaps += gaps
        if variant and not error:
            values, gaps = flood_values(policies, int(variant), units.get(int(variant), 0), fiscal_year=year)
            found.values.update(values)
            found.gaps += gaps
        out.append((variant, found))
    return out


def cmd_packet(args: argparse.Namespace, agent_factory: Callable[[Any], Any]) -> int:
    from jason.community import mystique
    from jason.tasks.packets import packet_dir, plan_lines, varies

    community = mystique()
    packet = community.packet(args.packet)
    data_dir = _data_dir(args)
    every = plans(community, packet, args.year, data_dir, only=str(args.building or ""))
    first = every[0][1]
    print("\n".join(plan_lines(first)))
    for variant, found in every[1:]:       # the other buildings: only what differs
        own = [r for part, r in zip(packet.parts, found.parts) if varies(part)]
        print(f"\nBuilding {variant}: " + "; ".join(f"{'ok' if r.found else 'MISS'} {r.part.title}"
                                                  + (f" ({r.where})" if r.found and r.where else "") for r in own))
        for gap in found.gaps:
            if gap not in first.gaps:
                print(f"  gap: {gap}")
    out = packet_dir(data_dir, packet, args.year)
    if args.values:
        path = out / "values.json"
        current = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        for token in first.unfilled:
            current.setdefault(token, "")
        out.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(current, indent=2), encoding="utf-8")
        print(f"values to fill: {path}")
    if args.make_templates:
        return _make_templates(args, agent_factory, packet)
    if args.build:
        return _build(args, agent_factory, community, packet, every, out)
    return 0


def _make_templates(args: argparse.Namespace, agent_factory: Callable[[Any], Any], packet: Any) -> int:
    from jason.community.spec import spec_module
    from jason.tasks.letters import markdown_doc
    from jason.tasks.packets import template_markdown, template_style

    from jason.community.profile import load_profile

    home, head = load_profile().drive_home(), load_profile().letterhead()
    from jason.community.packets import SourceKind

    made = [(f"Template - {p.title}", p.source.markdown, p.source.ref) for p in packet.parts
            if p.source.kind is SourceKind.TEMPLATE and p.source.markdown]
    if not args.yes:
        print("would make (or rewrite in place, replacing their text) " + ", ".join(n for n, _, _ in made)
              + " in My Drive/Templates; --yes does it")
        return 0
    with agent_factory(args) as agent:
        drive = agent.drive()
        for name, source, doc_id in made:
            markdown = template_markdown(source)
            result = markdown_doc(drive, drive.docs(), markdown, name=name, folder_id=home.templates,
                                  letterhead_id=head.doc_id, footer=head.footer, doc_id=doc_id,
                                  style=template_style(source))
            print(f"{'made' if result['created'] else 'rewrote'} {name}: {result['url']}")
    print("record any new ids in mystique/packets.py")
    return 0


def _build(args: argparse.Namespace, agent_factory: Callable[[Any], Any], community: Any, packet: Any,
           every: list[tuple[str, Any]], out: Path) -> int:
    missing = {r.part.title for _, found in every for r in found.missing}
    unfilled = {t for _, found in every for t in found.unfilled}
    if (missing or unfilled) and not args.draft:
        print(f"{len(missing)} parts missing and {len(unfilled)} tokens open; --draft builds anyway with a page "
              "naming each missing part", file=sys.stderr)
        return 1
    if not args.yes:
        print("dry run; --build --yes fills the templates as copies in Drive and assembles the PDF"
              + (f" (one per building: {', '.join(v for v, _ in every)})" if every[0][0] else ""))
        return 0
    (out / "parts").mkdir(parents=True, exist_ok=True)
    shared: dict[int, Path] = {}          # a part that is the same in every variant is made once
    with agent_factory(args) as agent:
        for variant, found in every:
            pdf = out / (f"building-{variant}.pdf" if variant else "packet.pdf")
            _assemble(args, agent, community, packet, found, out, variant, shared, pdf)
    return 0


def _assemble(args: argparse.Namespace, agent: Any, community: Any, packet: Any, found: Any, out: Path, variant: str,
              shared: dict[int, tuple[Path, str]], pdf: Path) -> None:
    from jason.community.packets import SourceKind
    from jason.tasks.packets import (fill_doc, fill_letter, insurance_html, insurance_rows, merge, page_html,
                                     print_pdf, statement_html, today_long, varies)

    values = dict(found.values)
    values.setdefault("MAILING_DATE", today_long())
    name = community.name
    logo = community.letterhead().logo_path(_data_dir(args))
    pieces: list[tuple[str, Path, str, bool]] = []
    drive, client = agent.drive(), agent.payhoa()
    docs = drive.docs()
    folder = ""
    for n, resolved in enumerate(found.parts, 1):
        part, source = resolved.part, resolved.part.source
        own = varies(packet.parts[n - 1])
        target = out / "parts" / (f"{variant}-{n:02d}.pdf" if own and variant else f"{n:02d}.pdf")
        if source.kind is SourceKind.ADDENDUM:
            continue
        if not own and n in shared:
            pieces.append((part.title, *shared[n], part.own_sheet))
            continue
        pages = source.pages if resolved.found else ""
        if not resolved.found:
            print_pdf(page_html(part.title, f"<p><strong>To be enclosed.</strong> {resolved.reason}</p>"
                                f"<p class='small'>{part.authority}</p>", association=name, logo=logo), target)
        elif source.ref.startswith("letter:"):
            body, left = fill_letter(source.ref, values)
            print_pdf(page_html(part.title, body, association=name, logo=logo), target)
            print(f"printed {part.title}" + (f" (open: {', '.join(left)})" if left else ""))
        elif source.kind is SourceKind.TEMPLATE:
            if not folder:
                root = drive.child_folder(_my_drive(), packet.title) or drive.create_folder(packet.title, _my_drive())
                folder = drive.child_folder(root, str(args.year)) or drive.create_folder(str(args.year), root)
            older: list[str] = []
            doc_id, left = fill_doc(drive, docs, source.ref, values, name=f"{part.title} {args.year}", folder_id=folder,
                                    extras=older)
            if older:
                print(f"  {len(older)} older cop{'y' if len(older) == 1 else 'ies'} of {part.title} {args.year} left in "
                      "the folder (jason refreshes the newest; remove the rest by hand): "
                      + ", ".join(f"https://docs.google.com/document/d/{x}/edit" for x in older))
            if source.markdown.startswith("form:"):     # each question stays on one page with its lines
                from jason.tasks.packets import keep_together_requests

                keep = keep_together_requests(docs.get(doc_id))
                for i in range(0, len(keep), 200):
                    docs.batch_update(doc_id, keep[i:i + 200])
            for token, points in MIN_POINTS.items():
                words = values.get(token, "")
                span = text_range(docs.get(doc_id), words[:40], words[-40:]) if words else None
                if span:
                    docs.batch_update(doc_id, [{"updateTextStyle": {"range": {"startIndex": span[0], "endIndex": span[1]},
                                                                     "textStyle": {"fontSize": {"magnitude": points, "unit": "PT"}},
                                                                     "fields": "fontSize"}}])
            docs.export_pdf(doc_id, target)
            print(f"filled {part.title}: https://docs.google.com/document/d/{doc_id}/edit" + (f" (open: {', '.join(left)})" if left else ""))
        elif source.kind in (SourceKind.LIBRARY, SourceKind.DRIVE):
            if source.kind is SourceKind.LIBRARY:
                client.download_document(agent.org_id, int(resolved.ref), target)
            elif drive.get_file(resolved.ref).get("mimeType") == GOOGLE_DOC:
                docs.export_pdf(resolved.ref, target)          # a linked Google Doc prints as it stands
            else:
                drive.download(resolved.ref, target)
            pages = _pages(target, source, part.title)
        elif source.ref == "insurance-summary":
            rows, _ = insurance_rows(_policies(_data_dir(args))[0], args.year, not_carried=community.coverages_not_carried())
            print_pdf(page_html("Summary of insurance (Civil Code §5300(b)(9))",
                                insurance_html(rows, values.get("INSURANCE_STATEMENT", "")), association=name, logo=logo), target)
        elif source.ref in ("fha-statement", "va-statement"):          # each on its own sheet (Part.own_sheet)
            token = "FHA" if source.ref == "fha-statement" else "VA"
            title = ("Federal Housing Administration statement" if token == "FHA"
                     else "Department of Veterans Affairs statement")
            print_pdf(page_html(title, statement_html(values.get(f"{token}_STATEMENT", ""),
                                                      certified=values.get(f"{token}_CERTIFIED", "")),
                                association=name, logo=logo), target)
        if not own:
            shared[n] = (target, pages)
        pieces.append((part.title, target, pages, part.own_sheet))
    record = merge(pieces, pdf, footer=f"{name} · {packet.title}, {args.year}" + (f" · Building {variant}" if variant else ""))
    _fillable_forms(packet, record, pdf, out)
    from jason.community.links import link_pdf

    subject = values.get("EMAIL_SUBJECT", "")                   # citations, addresses, and emails clickable in the PDFs
    for linked in [pdf, *sorted(out.glob("*-fillable.pdf"))]:
        link_pdf(linked, subject=subject)
    (pdf.with_suffix(".json") if variant else out / "manifest.json").write_text(json.dumps(
        {"packet": packet.key, "year": args.year, "variant": variant, "parts": record,
         "missing": [r.part.title for r in found.missing], "open": found.unfilled, "gaps": found.gaps}, indent=2), encoding="utf-8")
    import pymupdf

    with pymupdf.open(pdf) as merged:              # blank backs for parts on their own sheet count too
        pages = merged.page_count
    print(f"packet: {pdf} ({pages} pages, {len(record)} parts; {len(found.missing)} to be enclosed)")


def _pages(path: Path, source: Any, title: str) -> str:
    """The pages of a downloaded part to print: its listed pages, narrowed by its keep and drop rules."""
    import pymupdf

    from jason.community.packets import chosen_pages

    if not (source.keep or source.drop):
        return source.pages
    with pymupdf.open(path) as doc:
        pages, note = chosen_pages([page.get_text() for page in doc], source)
        print(f"{title}: pages {pages or 'all'} of {doc.page_count}" + (f" ({note})" if note else ""))
    return pages


def _fillable_forms(packet: Any, record: list[dict[str, Any]], pdf: Path, out: Path) -> None:
    """Make each form part fillable where it sits in the packet ``pdf``, and save it alone in ``out``
    (``<form>-fillable.pdf``) to attach to an email: boxes check and lines take typing on screen, and the page still
    prints for pen and paper."""
    import pymupdf

    from jason.community.fillable import make_fillable
    from jason.community.spec import spec_module

    forms = {f.key.value: f for f in spec_module("forms").FORM_TEMPLATES}
    for part in packet.parts:
        if not part.source.markdown.startswith("form:"):
            continue
        form = forms.get(part.source.markdown.split(":", 1)[1])
        placed = next((r for r in record if r["title"] == part.title), None)
        if form is None or placed is None:
            continue
        pages = range(placed["firstPage"] - 1, placed["firstPage"] - 1 + placed["pageCount"])
        fields = make_fillable(pdf, pages=pages, form=form)
        alone = pymupdf.open()
        alone.insert_pdf(pymupdf.open(Path(placed["file"])))
        single = out / f"{form.key.value}-fillable.pdf"
        alone.save(single)
        alone.close()
        make_fillable(single, form=form)
        print(f"fillable: {part.title} ({len(fields)} fields) in the packet, and alone in {single}")


def _my_drive() -> str:
    from jason.community.profile import load_profile

    return load_profile().drive_home().my_drive


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("packet", help="Plan and assemble a packet of documents into one PDF (annual disclosures)")
    add_common(p)
    p.add_argument("packet", nargs="?", default="annual-disclosures", help="the packet (default annual-disclosures)")
    p.add_argument("--year", type=int, required=True, help="the fiscal year the packet is for")
    p.add_argument("--values", action="store_true", help="write the year's values.json with every open token")
    p.add_argument("--make-templates", action="store_true", help="make the template Docs on the Letterhead (--yes)")
    p.add_argument("--build", action="store_true", help="fill, fetch, generate, and merge into one PDF (--yes)")
    p.add_argument("--draft", action="store_true", help="with --build: build with missing parts named on their own pages")
    p.add_argument("--building", type=int, help="one building's packet only (a packet made per building)")
    p.add_argument("--yes", action="store_true", help="write the Docs and the PDF (default: plan only)")
    p.set_defaults(func=lambda a: cmd_packet(a, agent_factory))
