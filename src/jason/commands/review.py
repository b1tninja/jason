"""``jason review``: a professional community manager's review of a task, from the law down through the rules.

``jason review TASK`` writes the context pack, ``data/briefs/<task>.md``: the base prompt, the task's prompt, and the
sources numbered in order of authority (statutes, the declaration, articles, bylaws, rules and policies, then the
association's records). ``--draft FILE`` adds the current text to review; ``--ask`` adds a question; ``--subject``
picks the task from a template's subject. ``--run`` asks the local model and checks every quote it gives against the
source it cites (``data/briefs/<task>.review.md``). A review is a draft for the board; it decides nothing.
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


def cmd_review(args: argparse.Namespace) -> int:
    from jason.community import mystique
    from jason.community.prompts import TaskKind
    from jason.tasks.manager_review import brief_path, build, run, save_pack, save_review

    community = mystique()
    if args.list:
        for task in community.task_prompts():
            print(f"{task.kind.slug:22} topics {len(task.topics):2}  kinds {len(task.documents):2}  "
                  f"considerations {len(task.considerations):2}  {task.kind.value}")
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
    draft = plain(Path(args.draft).read_text(encoding="utf-8")) if args.draft else ""
    pack = build(community, task, data_dir, ask=args.ask or "", draft=draft, mode=args.mode, k=args.k)
    path = save_pack(pack, brief_path(data_dir, task, args.name or ""))
    tiers: dict[str, int] = {}
    for source in pack.sources:
        tiers[source.tier.label] = tiers.get(source.tier.label, 0) + 1
    print(f"{task.kind.value}: {len(pack.sources)} sources ({', '.join(f'{n} {t}' for t, n in tiers.items())})")
    for gap in pack.gaps:
        print(f"gap: {gap}")
    print(f"context pack: {path}")
    if not args.run:
        print("--run asks the local model and checks its quotes")
        return 0
    checked = run(pack, model=args.model or "")
    json_path, md_path = save_review(pack, checked, path)
    print(f"review: {md_path} ({checked.grounded} quotes found in their sources, {len(checked.ungrounded)} not found)")
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
    p.set_defaults(func=cmd_review)
