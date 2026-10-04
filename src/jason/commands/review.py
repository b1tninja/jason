"""``jason review``: a professional community manager's review of a task, from the law down through the rules.

``jason review TASK`` writes the context pack, ``data/briefs/<task>.md``: the base prompt, the task's prompt, and the
sources numbered in order of authority (statutes, the declaration, articles, bylaws, rules and policies, then the
association's records). ``--draft FILE`` adds the current text to review; ``--ask`` adds a question; ``--subject``
picks the task from a template's subject. ``--run`` asks the local model and checks every quote it gives against the
source it cites (``data/briefs/<task>.review.md``). A review is a draft for the board; it decides nothing.

``--collection KEY`` adds a collection's material as its own tier (``jason review --collections`` lists them: a legal
case's file, by the case's key or its catalog's name). ``--catalog``, ``--kind``, and ``--folder`` name an ad hoc one
from the passage index's columns. A confidential collection goes only into a board task's pack.

Every pack written is also kept under ``data/reviews/<task>/<collection>/<digest>.json`` (``review_store``), so a
later review does not write over an earlier one. ``jason review --history TASK`` lists them.
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path
from typing import Any, Callable


def _data_dir(args: argparse.Namespace) -> Path:
    from jason.config import Settings

    return Settings.load(args.env).payhoa_catalog.parent


def plain(text: str) -> str:
    """An HTML body as plain text for the reader: paragraphs and list items on their own lines."""
    if "<" not in text:
        return text
    text = re.sub(r"(?i)</p>|<br\s*/?>|</li>|</h\d>", "\n", text)
    text = re.sub(r"(?i)<li[^>]*>", "- ", text)
    text = html.unescape(re.sub(r"<[^>]+>", "", text))
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def collection_lines(community: Any, data_dir: Path) -> list[str]:
    """The collections the specification gives, each with what the passage index holds for it. Reads only."""
    from jason.community import passage_index
    from jason.community.document_collections import collections

    lines = []
    for found in collections(community):
        counted = passage_index.count(data_dir, found.scope)
        held = "no passage index" if counted is None else f"{counted[0]} files, {counted[1]} passages"
        lines.append(f"{found.key:28} {found.kind.value:11} {'confidential' if found.confidential else 'open':12} "
                     f"{held:28} {found.title}")
    return lines


def history_lines(data_dir: Path, task: str) -> list[str]:
    """The reviews kept for one task. A person at the terminal sees the confidential ones too, marked."""
    from jason.tasks.review_store import history

    lines = []
    for row in history(data_dir, task, include_confidential=True):
        if row["verified"] is None:
            answer = "no answer (pack only)"
        else:
            answer = (f"{'verified' if row['verified'] else 'NOT verified'}: {row['grounded']} quotes found, "
                      f"{row['ungrounded']} not found ({row['model'] or 'model not recorded'}; {row['runs']} runs)")
        mark = " (confidential)" if row["confidential"] else ""
        lines.append(f"{row['asOf']}  {row['collection']}{mark}  {row['digest']}  {row['sources']} sources  {answer}")
    return lines


def chosen_collection(community: Any, args: argparse.Namespace) -> Any:
    """The collection the arguments name, or None for none. Raises ``ValueError`` with what to do for a miss."""
    from jason.community.document_collections import ad_hoc, collection

    filters = bool(args.catalog or args.kind or args.folder)
    if args.collection and filters:
        raise ValueError("give --collection, or --catalog/--kind/--folder for an ad hoc one, not both")
    if args.collection:
        found = collection(community, args.collection)
        if found is None:
            raise ValueError(f"no collection {args.collection!r}: jason review --collections lists them")
        return found
    if filters:
        return ad_hoc(catalogs=args.catalog, kinds=args.kind, folders=args.folder, confidential=args.confidential)
    if args.confidential:
        raise ValueError("--confidential goes with --catalog: it adds that catalog's held files to an ad hoc collection")
    return None


def cmd_review(args: argparse.Namespace) -> int:
    from jason.community import community as active
    from jason.community.prompts import TaskKind
    from jason.tasks import review_store
    from jason.tasks.manager_review import brief_path, build, run, save_pack, save_review

    community = active()
    if args.list:
        for task in community.task_prompts():
            print(f"{task.kind.slug:22} topics {len(task.topics):2}  kinds {len(task.documents):2}  "
                  f"considerations {len(task.considerations):2}  {task.kind.value}")
        return 0
    if args.collections:
        lines = collection_lines(community, _data_dir(args))
        print("\n".join(lines) if lines else "the specification names no legal case with a case file")
        return 0
    if args.subject:
        task = community.task_for_subject(args.subject)
        if task is None:
            print(f"no task's subjects match {args.subject!r}; name the task", file=sys.stderr)
            return 1
    elif args.task:
        task = community.task_prompt(TaskKind.from_slug(args.task))
    else:
        print("name a task (jason review --list) or give --subject", file=sys.stderr)
        return 2
    data_dir = _data_dir(args)
    if args.history:
        lines = history_lines(data_dir, task.kind.slug)
        print("\n".join(lines) if lines else f"no review of {task.kind.slug} is kept yet")
        return 0
    try:
        collection = chosen_collection(community, args)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    draft = plain(Path(args.draft).read_text(encoding="utf-8")) if args.draft else ""
    pack = build(community, task, data_dir, ask=args.ask or "", draft=draft, mode=args.mode, k=args.k, collection=collection)
    path = save_pack(pack, brief_path(data_dir, task, args.name or ""))
    tiers: dict[str, int] = {}
    for source in pack.sources:
        name = "collection" if source.label else source.tier.label
        tiers[name] = tiers.get(name, 0) + 1
    print(f"{task.kind.value}: {len(pack.sources)} sources ({', '.join(f'{n} {t}' for t, n in tiers.items())})")
    if collection is not None:
        print(f"collection: {collection.key} ({collection.kind.value}{', confidential' if collection.confidential else ''}): "
              + (collection.label if pack.collection_included else "refused for this task's audience"))
    for gap in pack.gaps:
        print(f"gap: {gap}")
    print(f"context pack: {path}")
    if not args.run:
        print(f"kept: {review_store.store(pack, data_dir)}")
        print("--run asks the local model and checks its quotes")
        return 0
    from jason.community.ollama_extractor import DEFAULT_MODEL

    checked = run(pack, model=args.model or "")
    json_path, md_path = save_review(pack, checked, path)
    print(f"review: {md_path} ({checked.grounded} quotes found in their sources, {len(checked.ungrounded)} not found)")
    print(f"kept: {review_store.store(pack, data_dir, checked=checked, model=args.model or DEFAULT_MODEL)}")
    return 0


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("review", help="A community manager's review of a task: the law, the documents, the facts (never decides)")
    add_common(p)
    p.add_argument("task", nargs="?", help="the task (jason review --list)")
    p.add_argument("--list", action="store_true", help="list the tasks the specification defines")
    p.add_argument("--subject", help="pick the task from a template's subject or a Doc's title")
    p.add_argument("--draft", metavar="FILE", help="the current text to review (HTML or plain)")
    p.add_argument("--ask", help="a question to answer from the sources")
    p.add_argument("--mode", default="hybrid", choices=("keyword", "exact", "hybrid"),
                   help="retrieval: hybrid (default; BM25 fused with the local embedder, under the GPU lock, keyword when it is "
                        "unavailable), keyword (BM25), or exact")
    p.add_argument("-k", type=int, default=4, help="passages per question before copies are folded (default 4)")
    p.add_argument("--name", help="the pack's file name under data/briefs (default: the task)")
    p.add_argument("--run", action="store_true", help="ask the local model and check every quote against its source")
    p.add_argument("--model", help="the local chat model (default qwen3.6:27b)")
    p.add_argument("--collection", metavar="KEY",
                   help="add a collection's material as its own tier: a legal case's key or its catalog (case-KEY); a "
                        "confidential one only for a board task")
    p.add_argument("--collections", action="store_true",
                   help="list the collections with their files and passages in the passage index (reads only)")
    p.add_argument("--catalog", action="append", default=[], help="an ad hoc collection: this index catalog (repeat)")
    p.add_argument("--kind", action="append", default=[], help="an ad hoc collection: this document kind (repeat)")
    p.add_argument("--folder", action="append", default=[], help="an ad hoc collection: under this data folder (repeat)")
    p.add_argument("--confidential", action="store_true",
                   help="with --catalog: include that catalog's files held back unless asked (board tasks only)")
    p.add_argument("--history", action="store_true",
                   help="list the reviews kept for the task under data/reviews: date, collection, digest, and whether "
                        "the answer's quotes were found (reads only)")
    p.set_defaults(func=cmd_review)
