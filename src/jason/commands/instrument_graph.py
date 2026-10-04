"""``jason instrument-graph``: the community's recorded instruments as a graph, printed as Mermaid or JSON.

``--association`` (the default) draws the governing instruments, what amends, annexes, and supersedes what, the
common-area deeds, and the land chain. ``--parcel APN`` (repeatable) and ``--unit N`` draw a parcel's chain with its
closings (notice of completion, buyer's lien, reconveyances), its owners' liens, and the annexation of its phase.
``--all`` draws both for every parcel. ``--around NUMBER`` keeps the part within ``--depth`` edges of one instrument.
The shared view (the default) holds no private person; ``--private`` labels owners by role and parcel.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Callable


def cmd_instrument_graph(args: argparse.Namespace, agent_factory: Callable[[Any], Any]) -> int:
    from jason.commands._shared import data_dir, to_json
    from jason.community import community as active
    from jason.community.instrument_graph import EdgeKind, View
    from jason.tasks import instrument_graph as ig

    root = data_dir(args)
    the = active()
    view = View.PRIVATE if args.private else View.SHARED
    apns = list(args.parcel or [])
    if args.unit is not None:
        found = ig.unit_apns(the, args.unit)
        if not found:
            print(f"unit {args.unit}: no parcel carries that number on this community", file=sys.stderr)
            return 1
        if len(found) > 1:
            print(f"unit {args.unit} names {len(found)} parcels (two numberings); drawing each: {', '.join(found)}", file=sys.stderr)
        apns.extend(found)
    if args.all:
        graph = ig.community_graph(the, root)
    elif apns:
        association = ig.association_graph(the, root, readings=False, located=False, land=False)
        graph = ig.parcel_graph(the, root, apns, association=association)
    else:
        graph = ig.association_graph(the, root)
    if args.around:
        try:
            graph = ig.focus(graph, args.around, args.depth)
        except KeyError:
            print(f"{args.around} is not on this graph", file=sys.stderr)
            return 1
    kinds = None
    if args.kinds:
        try:
            kinds = [EdgeKind(k.strip()) for k in args.kinds.split(",") if k.strip()]
        except ValueError as exc:
            print(f"{exc}; the kinds are {', '.join(k.value for k in EdgeKind)}", file=sys.stderr)
            return 2
    if args.names and not args.private:
        print("--names needs --private: the shared view holds no private person", file=sys.stderr)
        return 2
    if args.json:
        text = to_json(ig.payload(graph, view, mermaid=False, names=args.names))
    else:
        text = graph.mermaid(view, kinds=kinds, direction=args.direction)
        if args.markdown:
            data = graph.to_dict(view)
            text = "\n".join([f"# {graph.title}", "", "```mermaid", text, "```", "",
                              *(f"- {n}" for n in data["notes"]), "", *(f"> {c}" for c in data["caveats"]), ""])
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
        print(f"wrote {out} ({view.value} view)")
    else:
        print(text)
    if graph.cycles and not args.json:
        print(f"{len(graph.cycles)} edge(s) left out: each would have closed a cycle in its family (--json lists them)", file=sys.stderr)
    return 0


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("instrument-graph", help="The recorded instruments as a graph (Mermaid or JSON): declaration, amendments, annexations, deeds, closings, liens")
    add_common(p)
    p.add_argument("--association", action="store_true", help="the association's governing instruments and land chain (the default)")
    p.add_argument("--parcel", action="append", metavar="APN", help="one parcel's chain, closings, and liens (repeatable)")
    p.add_argument("--unit", type=int, metavar="N", help="the parcel or parcels a unit number names")
    p.add_argument("--all", action="store_true", help="the association and every parcel (slow)")
    p.add_argument("--around", metavar="NUMBER", help="keep only the part around this instrument number")
    p.add_argument("--depth", type=int, default=2, help="with --around: how many edges out (default 2)")
    p.add_argument("--kinds", metavar="K1,K2", help="only these edge kinds in the Mermaid (e.g. amends,annexes,supersedes)")
    p.add_argument("--private", action="store_true", help="the private view: owners as nodes, labeled by role and parcel")
    p.add_argument("--names", action="store_true", help="with --private --json: carry each private person's names (for the board's own use; never share)")
    p.add_argument("--json", action="store_true", help="nodes and edges with each edge's provenance, as JSON")
    p.add_argument("--markdown", action="store_true", help="a Markdown page with the Mermaid diagram, notes, and caveats")
    p.add_argument("--direction", default="LR", choices=("LR", "TD", "RL", "BT"), help="the Mermaid flow direction")
    p.add_argument("--out", metavar="FILE", help="write to a file instead of printing")
    p.set_defaults(func=lambda args: cmd_instrument_graph(args, agent_factory))
