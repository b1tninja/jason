"""``jason index``: the passage index (``jason.community.passage_index``), one store a search can be scoped by.

``--build`` cuts the sources' text files into passages and embeds what has no vector yet. It copies the old cache's
vectors and re-cuts only changed files, so a second build is quick. ``--no-embed`` cuts without the GPU. A legal case's
fetched file (``jason cases --fetch-files``) is its own confidential catalog, ``case-<key>``. The classified library,
the mail, jason's reports, and jason's documentation are the catalogs ``library``, ``mail``, ``reports``, and ``docs``
(``jason.tasks.index_sources``), each file with its own confidential flag.
``--plan`` lists what a build would take, catalog by catalog: the files, how many are confidential, and what is left
out and why. It reads only.
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
    """What a build takes: ``passage_index.SOURCES``, the agency publications' text by what each is
    (``export_authorities.PublicationSource``), each legal case's fetched file as its own confidential catalog
    (``case_files.index_sources``, read from the active profile when the build runs), each collection's generated
    pages in the collection's own catalog (``collection_pages.index_sources``), and the library, the mail,
    jason's reports, and jason's documentation, each file with its own flags (``jason.tasks.index_sources``)."""
    from jason.community import community
    from jason.community import passage_index as pi
    from jason.community.document_collections import collections
    from jason.tasks import collection_pages
    from jason.tasks import index_sources as files
    from jason.tasks.case_files import index_sources

    from jason.tasks.export_authorities import PublicationSource

    active = community()
    return (*pi.SOURCES, PublicationSource(), *index_sources(active.legal_cases()),
            *collection_pages.index_sources(collections(active)), *files.sources())


LIBRARY_HOLDS = "the library holds a copy as confidential"


def plan(data_dir: Any, build_sources: tuple | None = None) -> list[dict[str, Any]]:
    """What a build would take, a row a catalog: its files, how many are confidential and by which row, and what its
    sources left out and why (a source with a ``plan`` says; a folder source leaves nothing out). A file a source gives
    openly that the library holds as confidential is counted as the build would flag it. Reads only."""
    from pathlib import Path

    from jason.tasks.index_sources import library_holds

    held = library_holds(Path(data_dir))
    rows: dict[str, dict[str, Any]] = {}

    def row_of(name: str) -> dict[str, Any]:
        return rows.setdefault(name, {"catalog": name, "files": 0, "confidential": 0, "confidentialBy": {}, "leftOut": {}})

    for source in sources() if build_sources is None else build_sources:
        made = source.plan(Path(data_dir)) if hasattr(source, "plan") else None
        for name in source.catalogs:
            row_of(name)
        for entry in made.entries if made is not None else source.entries(Path(data_dir)):
            row = row_of(entry.catalog)
            row["files"] += 1
            if entry.confidential:
                row["confidential"] += 1
            elif held(entry.path):
                row["confidential"] += 1
                row["confidentialBy"][LIBRARY_HOLDS] = row["confidentialBy"].get(LIBRARY_HOLDS, 0) + 1
        if made is not None:
            for key, counts in (("confidentialBy", made.held), ("leftOut", made.left_out)):
                for reason, count in counts.items():
                    row_of(made.catalog)[key][reason] = row_of(made.catalog)[key].get(reason, 0) + count
    return list(rows.values())


def cmd_index(args: argparse.Namespace) -> int:
    from jason.community import passage_index as pi
    from jason.config import data_dir as active_data_dir

    data = active_data_dir()
    if args.plan:
        print(json.dumps(plan(data), indent=1))
        return 0
    if args.build:
        from jason.community import retrieval
        from jason.locks import Resource, hold

        embedder = None if args.no_embed else retrieval.OllamaEmbedder()
        from jason.tasks.index_sources import library_holds

        with hold(Resource.STORE, "retrieval-index", purpose="build the passage index"):
            report = pi.build(data, sources=sources(), embedder=embedder, held=library_holds(data),
                              say=lambda line: print(line, file=sys.stderr))
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
                               "confidential": h.row.confidential, "context": h.hit.passage.context,
                               "text": h.hit.passage.text, "alsoIn": [str(p.path) for p in h.hit.also]}
                              for h in hits], indent=1))
            return 0
        for n, h in enumerate(hits, 1):
            p = h.hit.passage
            label = (f"{h.row.standing.value}{', generated' if h.row.generated else ''}"
                     f"{', confidential' if h.row.confidential else ''}")
            print(f"{n}. {p.title} #{p.index} [{h.row.catalog}; {label}{'; ' + h.row.kind if h.row.kind else ''}] "
                  f"{p.heading}")
            if p.context:
                print(f"   ({p.context})")
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
    p.add_argument("--plan", action="store_true", help="what a build would take, by catalog: files, how many are "
                                                       "confidential, and what is left out and why (reads only)")
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
