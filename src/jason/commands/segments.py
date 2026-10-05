"""``jason segments``: the documents in a file, and the parts of each.

One scan is often several documents (a stack of recorded instruments, a board packet, a vendor's batch), and one document
holds parts that are cited on their own (the rules inside the owner's manual, an exhibit). ``jason segments`` reads a
PDF's pages and writes where each document starts (its page range, kind, title, date, and parties) and each titled part.
The reading is kept at ``data/library/segments/<id>.json``; the PDF is never split or rewritten, and a segment is a page
range of it, addressed ``library:ID#p3-7`` (``#seg=s2``, ``#part=rules``).

The rule pass reads the pages' own marks (a recorder's stamp, "Page 1 of N", a numbering that restarts, a title block, a
footer that changes, a signature before) and needs no model. ``--model`` adds the local vision model as a second reader
(it holds the GPU lock, runs ``jason local-ai`` checks first, and releases the model afterward), and ``--embed`` the
embedder. Two readers agreeing make a boundary likely; one alone is a suggestion. Nothing is written without ``--write``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable


def _data_dir(args: argparse.Namespace) -> Path:
    from jason.config import Settings

    return Settings.load(getattr(args, "env", None)).ownership_db.parent


def _resolve(args: argparse.Namespace, data_dir: Path) -> tuple[Path, str] | None:
    """The PDF to read and its store id: a file named, or a library document by its id."""
    from jason.tasks import segments as task

    if args.file:
        path = Path(args.file)
        return (path, task.file_id(path)) if path.is_file() else None
    if args.id:
        from jason.approvals.evidence import library_row

        row = library_row(data_dir, args.id) or {}
        path = data_dir / "library" / "files" / str(row.get("path") or "")
        return (path, args.id) if row and path.is_file() else None
    return None


def lines(seg: Any, *, moves: bool = False) -> list[str]:
    """A reading as text: the tree of documents, each with its address and its parts; with ``moves``, the moves the walk
    made (push, pop, new) and what decided each."""
    from jason.community.document_segments import address

    nested = sum(1 for s in seg.segments if s.parent)
    out = [f"{seg.id}: {seg.page_count} pages, {len(seg.segments)} documents ({nested} inside another), {len(seg.parts)} parts "
           f"(readers: {', '.join(k for k in seg.readers if not k.endswith('Seconds'))})"]
    for s in seg.segments:
        pages = f"p{s.start}" if s.start == s.end else f"p{s.start}-{s.end}"
        runs = "" if len(s.runs) <= 1 else " (own " + ", ".join(f"{a}-{b}" if a != b else str(a) for a, b in s.runs) + ")"
        bits = [s.kind or "kind unread", s.date, "; ".join(s.parties)]
        indent = "  " * s.depth
        out.append(f"  {indent}{s.key:6s} {pages:9s}{runs} {s.tier.value:9s} {' + '.join(r.value for r in s.readers):14s} "
                   f"{(s.label + ': ' if s.label else '')}{s.title[:44]!r} {' | '.join(b for b in bits if b)}")
        out.append(f"  {indent}       {address(seg.id, segment=s.key)}  ({address(seg.id, pages=s.pages)})")
        for p in (x for x in seg.parts if x.segment == s.key):
            span = f"p{p.start}" if p.start == p.end else f"p{p.start}-{p.end}"
            out.append(f"  {indent}       part {p.key:28s} {span:9s} {p.kind.value:9s} via {p.basis}"
                       + (f"; book {p.book}" if p.book else "") + f"  {address(seg.id, part=p.key)}")
    if moves:
        out.append("moves:")
        for m in seg.moves:
            closed = f", closed {' and '.join(m.closed)}" if m.closed else ""
            model = f"; model says {max(m.model, key=m.model.get)} ({max(m.model.values()):.2f})" if m.model else ""
            out.append(f"  p{m.page:<4d} {m.kind.value:5s} -> {m.segment}{closed} [{m.tier.value}] {'; '.join(m.signals[:3])}{model}")
    return out


def cmd_segments(args: argparse.Namespace) -> int:
    from jason.tasks import segments as task

    data_dir = _data_dir(args)
    if args.list:
        folder = task.store_dir(data_dir)
        for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
            seg = task.load(data_dir, path.stem)
            if seg:
                print(f"{seg.id}: {seg.page_count} pages, {len(seg.segments)} documents, {len(seg.parts)} parts  {seg.name}")
        return 0
    if args.show:
        seg = task.load(data_dir, args.show)
        if seg is None:
            print(f"jason segments: no reading stored for {args.show}", file=sys.stderr)
            return 1
        print("\n".join(lines(seg, moves=getattr(args, "moves", False))))
        return 0
    found = _resolve(args, data_dir)
    if found is None:
        print("jason segments: name a PDF (--file PATH) or a library document id", file=sys.stderr)
        return 1
    pdf, doc_id = found
    model = embedder = None
    if args.model:
        model = task.OllamaPageReader(model=args.model, pair=args.pair, dpi=args.dpi)
    if args.embed:
        from jason.community.retrieval import OllamaEmbedder

        embedder = OllamaEmbedder()
    from jason.community import community

    try:
        seg = task.segment_file(pdf, doc_id=doc_id, data_dir=data_dir, model=model, embedder=embedder, ocr=args.ocr,
                                community=community(), accept=args.accept, write=args.write, force=args.again,
                                progress=None)
    finally:
        if args.model:
            try:
                from jason.local_ai import unload

                unload(args.model)
            except Exception:  # noqa: BLE001 - releasing the model is best effort
                pass
    if args.json:
        print(json.dumps({k: v for k, v in seg.to_dict().items() if k != "pages"}, indent=1))
    else:
        print("\n".join(lines(seg, moves=getattr(args, "moves", False))))
    print(("stored at " + str(task.store_path(data_dir, doc_id))) if args.write else "dry run: add --write to store it")
    return 0


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("segments", help="The documents in a scanned file and the parts of each: page ranges, kinds, titles, "
                                        "dates, and parties; the file is never split")
    add_common(p)
    p.add_argument("id", nargs="?", default="", help="a library document id")
    p.add_argument("--file", default="", help="a PDF anywhere on disk (its store id is its SHA-256's first sixteen digits)")
    p.add_argument("--write", action="store_true", help="store the reading at data/library/segments/ID.json")
    p.add_argument("--again", action="store_true", help="read the pages again, not from the stored reading")
    p.add_argument("--model", nargs="?", const="qwen3.5:9b", default="",
                   help="add the local vision model as a second reader (default qwen3.5:9b); it holds the GPU lock")
    p.add_argument("--pair", action="store_true", help="with --model: show it the page before as well")
    p.add_argument("--dpi", type=int, default=72, help="with --model: the thumbnail's resolution")
    p.add_argument("--embed", action="store_true", help="add the embedder's change points as a reader")
    p.add_argument("--ocr", action="store_true", help="read a page with no text layer by OCR (slow)")
    p.add_argument("--accept", choices=["any", "agree", "rules"], default="any",
                   help="keep any reader's boundary (default), only those two readers share, or the rules'")
    p.add_argument("--show", default="", metavar="ID", help="print a stored reading")
    p.add_argument("--list", action="store_true", help="list the stored readings")
    p.add_argument("--moves", action="store_true", help="also print the moves the walk made at each page (push, pop, new) and what decided them")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_segments)


__all__ = ["cmd_segments", "lines", "register"]
