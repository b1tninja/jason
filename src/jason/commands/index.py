"""``jason index``: the passage index (``jason.community.passage_index``), one store a search can be scoped by.

``--build`` cuts the sources' text files into passages and embeds what has no vector yet. It copies the old cache's
vectors and re-cuts only changed files, so a second build is quick. ``--no-embed`` cuts without the GPU. A legal case's
fetched file (``jason cases --fetch-files``) is its own confidential catalog, ``case-<key>``.
``--status`` reports what the index holds.
``--search QUESTION`` ranks the passages, optionally scoped by ``--catalog``, ``--standing``, ``--kind``, or
``--folder``, with the confidential files only on ``--confidential``.
A hit is a passage to read; nothing here pins a fact.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Callable


def sources() -> tuple:
    """What a build takes: ``passage_index.SOURCES``, and each legal case's fetched file as its own confidential catalog
    (``case_files.index_sources``, read from the active profile when the build runs)."""
    from jason.community import community
    from jason.community import passage_index as pi
    from jason.tasks.case_files import index_sources

    return (*pi.SOURCES, *index_sources(community().legal_cases()))


def cmd_index(args: argparse.Namespace) -> int:
    from jason.community import passage_index as pi
    from jason.config import data_dir as active_data_dir

    data = active_data_dir()
    if args.build:
        from jason.community import retrieval
        from jason.locks import Resource, hold

        embedder = None if args.no_embed else retrieval.OllamaEmbedder()
        with hold(Resource.STORE, "retrieval-index", purpose="build the passage index"):
            report = pi.build(data, sources=sources(), embedder=embedder, say=lambda line: print(line, file=sys.stderr))
        for line in report.lines():
            print(line)
        return 1 if report.missing and embedder is not None else 0
    if args.search:
        try:
            standings = tuple(pi.Standing(s) for s in args.standing)
        except ValueError:
            print(f"standings: {', '.join(s.value for s in pi.Standing)}", file=sys.stderr)
            return 2
        scope = pi.Scope(catalogs=tuple(args.catalog), standings=standings, kinds=tuple(args.kind),
                         folders=tuple(args.folder), confidential=args.confidential)
        try:
            hits = pi.search(args.search, data_dir=data, scope=scope, k=args.k, mode=args.mode)
        except FileNotFoundError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps([{"file": h.hit.passage.title, "path": str(h.hit.passage.path), "passage": h.hit.passage.index,
                               "section": h.hit.passage.heading, "score": h.hit.score, "catalog": h.row.catalog,
                               "standing": h.row.standing.value, "kind": h.row.kind, "generated": h.row.generated,
                               "text": h.hit.passage.text, "alsoIn": [str(p.path) for p in h.hit.also]}
                              for h in hits], indent=1))
            return 0
        for n, h in enumerate(hits, 1):
            p = h.hit.passage
            label = f"{h.row.standing.value}{', generated' if h.row.generated else ''}"
            print(f"{n}. {p.title} #{p.index} [{h.row.catalog}; {label}{'; ' + h.row.kind if h.row.kind else ''}] "
                  f"{p.heading}")
            print(f"   {p.text[:300]}{'...' if len(p.text) > 300 else ''}")
        print("A hit is a passage to read, not a finding; a generated page is a summary, never the rule.")
        return 0
    print(json.dumps(pi.status(data), indent=1))
    return 0


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("index", help="The passage index: build it, report it, or search it by scope")
    add_common(p)
    p.add_argument("--build", action="store_true", help="cut the sources into passages and embed what is new")
    p.add_argument("--no-embed", action="store_true", help="with --build: cut and copy cached vectors only")
    p.add_argument("--status", action="store_true", help="what the index holds (the default)")
    p.add_argument("--search", metavar="QUESTION", help="rank the passages for a question")
    p.add_argument("--mode", default="hybrid", choices=("keyword", "exact", "dense", "hybrid"))
    p.add_argument("-k", type=int, default=8)
    p.add_argument("--catalog", action="append", default=[], help="only this catalog (repeat)")
    p.add_argument("--standing", action="append", default=[], help="authority, record, reference, or page (repeat)")
    p.add_argument("--kind", action="append", default=[], help="only this document kind (repeat)")
    p.add_argument("--folder", action="append", default=[], help="only under this data folder (repeat)")
    p.add_argument("--confidential", action="store_true", help="include the files held back unless asked")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_index)
