"""The recorded instruments of a community as a graph: instruments, parties, and parcels, joined by typed edges.

County-neutral. A node is an instrument (its number, recording date, filing, kind, and county), a party (a business
or the association; a private person only in the private view), or a parcel. An edge says what one node does to
another, and each edge carries its provenance: the rule that made it, the store it was read from, and whether it is
a lead (a reading, a name handoff, a process seat, or a locator's tie) or firm (the county's own cross-reference, the
stored chain, or a fact the specification pins). A lead is something to read, never a finding.

Edge kinds, each from the later or dependent node to the one it acts on:

====================  =======================================  =========
kind                  source -> target                         family
====================  =======================================  =========
``prior_of``          a chain step -> the earlier deed          chain
``re_records``        a re-recording -> the first recording     chain
``cites``             an instrument -> one it cross-references  citation
``completes``         a notice of completion -> the grant       closing
``beside``            an instrument -> the one it was recorded  closing
                      beside (a closing's or formation's
                      bundle)
``amends``            an amendment -> the declaration           governing
``annexes``           an annexation -> the declaration          governing
``supersedes``        the later instrument -> the one it        governing
                      rescinded
``covers``            an annexation -> a parcel of its phase    governing
``releases``          a reconveyance or release -> the lien     loan
``forecloses``        a trustee's deed -> the deed of trust     loan
``advances``          a later lifecycle step -> its opener      loan
``encumbers``         a deed of trust or lien -> the parcel     parcel
``carries``           a deed -> the parcel it conveys           parcel
``conveys``           grantor -> grantee (``via`` the deed)     party
``vests``             a deed -> its grantee                     party
``names``             an instrument -> a party it names         party
====================  =======================================  =========

Each family is kept a DAG: an edge that would close a cycle in its family is not added; it is reported in
``cycles`` with the path it would have closed (a buy-back, two instruments citing each other, a misread number).

The builders take plain inputs, so any county feeds the graph: asspy's ``FiledInstrument`` rows, an
``OwnershipHistory`` of ``Conveyance`` steps, a process ``Reading``, a lien ``Encumbrance``, the governing records
(``GoverningRecord``), the specification's ``Supersession`` facts and governing document, the document readings,
and the document locator's ``Location`` (or its rows as dicts). Sacramento's stores are read by
``jason.tasks.instrument_graph``; another county's walk calls the same builders.

Privacy. A party that is not plainly a business or the association is a private person. It becomes a node only in
the private view, labeled by its role and parcel ("owner, parcel 000-0000-000-0000"), never by name; its names ride
in ``names`` in the private view alone. The shared view drops private nodes, every edge touching one, and any cycle
that passes through one. Instrument nodes never carry a person's name.
"""

from __future__ import annotations

import hashlib
import re
from collections import deque
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any, Iterable, Mapping


class NodeType(Enum):
    INSTRUMENT = "instrument"
    PARTY = "party"
    PARCEL = "parcel"


class PartyKind(Enum):
    ASSOCIATION = "association"
    BUSINESS = "business"
    PRIVATE = "private"


class View(Enum):
    """Who the export is for. ``SHARED`` may leave the board's hands; ``PRIVATE`` stays with the people who work with
    the owners."""

    SHARED = "shared"
    PRIVATE = "private"


class EdgeKind(Enum):
    PRIOR_OF = "prior_of"
    RE_RECORDS = "re_records"
    CITES = "cites"
    COMPLETES = "completes"
    BESIDE = "beside"
    AMENDS = "amends"
    ANNEXES = "annexes"
    SUPERSEDES = "supersedes"
    COVERS = "covers"
    RELEASES = "releases"
    FORECLOSES = "forecloses"
    ADVANCES = "advances"
    ENCUMBERS = "encumbers"
    CARRIES = "carries"
    CONVEYS = "conveys"
    VESTS = "vests"
    NAMES = "names"

    @property
    def family(self) -> str:
        return FAMILY[self]


FAMILY: dict[EdgeKind, str] = {
    EdgeKind.PRIOR_OF: "chain",
    EdgeKind.RE_RECORDS: "chain",
    EdgeKind.CITES: "citation",
    EdgeKind.COMPLETES: "closing",
    EdgeKind.BESIDE: "closing",
    EdgeKind.AMENDS: "governing",
    EdgeKind.ANNEXES: "governing",
    EdgeKind.SUPERSEDES: "governing",
    EdgeKind.COVERS: "governing",
    EdgeKind.RELEASES: "loan",
    EdgeKind.FORECLOSES: "loan",
    EdgeKind.ADVANCES: "loan",
    EdgeKind.ENCUMBERS: "parcel",
    EdgeKind.CARRIES: "parcel",
    EdgeKind.CONVEYS: "party",
    EdgeKind.VESTS: "party",
    EdgeKind.NAMES: "party",
}

# What each kind means, for a legend and for a person reading an edge.
MEANING: dict[EdgeKind, str] = {
    EdgeKind.PRIOR_OF: "the chain step's earlier deed",
    EdgeKind.RE_RECORDS: "records the same conveyance again",
    EdgeKind.CITES: "cites this instrument",
    EdgeKind.COMPLETES: "the notice of completion recorded before this grant",
    EdgeKind.BESIDE: "recorded beside it, in one closing or formation",
    EdgeKind.AMENDS: "amends this declaration",
    EdgeKind.ANNEXES: "annexes property under this declaration",
    EdgeKind.SUPERSEDES: "rescinded and superseded this instrument",
    EdgeKind.COVERS: "annexed the phase this parcel is in",
    EdgeKind.RELEASES: "releases this lien",
    EdgeKind.FORECLOSES: "the sale under this deed of trust",
    EdgeKind.ADVANCES: "a later step of this lien's lifecycle",
    EdgeKind.ENCUMBERS: "a lien on this parcel",
    EdgeKind.CARRIES: "conveys this parcel",
    EdgeKind.CONVEYS: "conveyed to",
    EdgeKind.VESTS: "vests title in",
    EdgeKind.NAMES: "names this party",
}

CAVEATS = (
    "A graph of what the records on disk say. A dotted edge is a lead (a reading, a name handoff, a process seat, a "
    "locator's tie): something to read, not a finding.",
    "A lien indexes a person, not a parcel: a lien edge joins a parcel through its owner's name and tenure.",
    "An instrument jason has only seen cited is a node marked not loaded; its filing and parties are unknown.",
    "The shared view leaves out every private person; the private view labels them by role and parcel, never by name.",
)

# Words that make a party plainly a business or a public body, whatever else it says.
_STRONG = re.compile(
    r"\b(?:LLC|L L C|INC|CORP|CORPORATION|COMPANY|CO|LP|L P|LLP|LTD|PTP|PRTN|PARTNERSHIP|ASSOCIATION|ASSN|ASSOC|HOA|POA|"
    r"COUNTY|CITY|DISTRICT|AGENCY|AUTHORITY|STATE OF|UNITED STATES|DEPARTMENT|BANK|BK|NA|N A|FSB|TRUST COMPANY|"
    r"NATIONAL ASSOCIATION|CREDIT UNION)\b"
)
# Words a private person's or a family trust's name carries.
_PRIVATE = re.compile(r"\b(?:TR|TRS|TRUSTEE|TRUSTEES|TRUST|FAMILY|REVOCABLE|LIVING|ESTATE|ET AL|ETAL|ET UX|ETUX)\b")
# Words that make a party a business when no private word is there.
_WEAK = re.compile(
    r"\b(?:HOMES|COMMUNITIES|BUILDERS|DEVELOPMENT|DEVEL|DEVELOPERS|PROPERTIES|GROUP|VENTURES|INVESTORS|HOLDINGS|"
    r"PARTNERS|PHASE|PHAS|MORTGAGE|SAVINGS|TITLE|ESCROW|FINANCIAL|LENDING|FUNDING|FUND|SOLAR|SERVICES|CAPITAL)\b"
)
_NUMBER = re.compile(r"^[0-9A-Za-z][0-9A-Za-z-]{3,}$")


def _fold(name: str) -> str:
    return " ".join(re.sub(r"[^A-Z0-9 ]+", " ", str(name or "").upper()).split())


def party_kind(name: str, *, association: Iterable[str] = (), developers: Iterable[Any] = ()) -> PartyKind:
    """The association (a name that starts with one of its spellings), a business or public body, or a private
    person. A family trust is a private person. When a name is unclear it is private: the safe side."""
    folded = _fold(name)
    if not folded:
        return PartyKind.PRIVATE
    for spelling in association:
        lead = _fold(spelling)
        if lead and (folded == lead or folded.startswith(lead + " ")):
            return PartyKind.ASSOCIATION
    for developer in developers:
        names = (getattr(developer, "name", ""), *(getattr(developer, "names", ()) or ()))
        if any(_fold(n) and (folded == _fold(n) or folded.startswith(_fold(n) + " ")) for n in names):
            return PartyKind.BUSINESS
    if _STRONG.search(folded):
        return PartyKind.BUSINESS
    if _PRIVATE.search(folded):
        return PartyKind.PRIVATE
    if _WEAK.search(folded):
        return PartyKind.BUSINESS
    return PartyKind.PRIVATE


def _alnum(text: str) -> str:
    return "".join(ch for ch in str(text) if ch.isalnum())


def instrument_id(number: str, county: str = "") -> str:
    return f"inst:{_alnum(county).lower() or 'county'}:{str(number).strip()}"


def parcel_id(apn: str) -> str:
    return f"parcel:{_alnum(apn)}"


def _private_id(name: str) -> str:
    return "person:" + hashlib.sha1(_fold(name).encode("utf-8")).hexdigest()[:12]


def _iso(value: date | None) -> str:
    return value.isoformat() if isinstance(value, date) else (str(value) if value else "")


@dataclass
class Node:
    id: str
    type: NodeType
    label: str
    attrs: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Provenance:
    """Which rule made an edge and from what store. ``lead`` marks a reading, a name match, a seat, or a locator tie."""

    rule: str
    store: str
    lead: bool = False
    note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"rule": self.rule, "store": self.store, "lead": self.lead, "note": self.note}


@dataclass
class Edge:
    kind: EdgeKind
    source: str
    target: str
    provenance: Provenance
    via: str = ""                     # the deed a conveyance went by; the role a process seat names
    also: list[Provenance] = field(default_factory=list)

    @property
    def family(self) -> str:
        return self.kind.family

    @property
    def lead(self) -> bool:
        """A lead only when every rule that made it is a lead: one firm source makes the edge firm."""
        return self.provenance.lead and all(p.lead for p in self.also)

    @property
    def key(self) -> tuple[str, str, str, str]:
        return (self.kind.value, self.source, self.target, self.via)


@dataclass(frozen=True)
class Cycle:
    """An edge left out because its family already reached back from its target to its source."""

    family: str
    edge: Edge
    path: tuple[str, ...]


class InstrumentGraph:
    """Nodes and typed edges; each edge family stays acyclic. Build with the ``add_*`` functions below."""

    def __init__(self, *, county: str = "", title: str = "") -> None:
        self.county = county
        self.title = title
        self.nodes: dict[str, Node] = {}
        self.edges: list[Edge] = []
        self.cycles: list[Cycle] = []
        self.notes: list[str] = []
        self._by_key: dict[tuple[str, str, str, str], Edge] = {}
        self._out: dict[str, dict[str, set[str]]] = {}

    # Nodes ------------------------------------------------------------------------------------------------------

    def instrument(self, number: str, *, county: str = "", recorded: date | str | None = None, filing: str = "",
                   kind: str = "", role: str = "", loaded: bool = True, **attrs: Any) -> str:
        """Add or fill an instrument. A value already set stays; ``loaded`` only turns on."""
        county = county or self.county
        node_id = instrument_id(number, county)
        fresh = {"number": str(number).strip(), "county": county, "recorded": _iso(recorded), "filing": filing, "kind": kind, "role": role, "loaded": loaded, **attrs}
        node = self.nodes.get(node_id)
        if node is None:
            self.nodes[node_id] = Node(node_id, NodeType.INSTRUMENT, str(number).strip(), {k: v for k, v in fresh.items()})
            return node_id
        for key, value in fresh.items():
            if key == "loaded":
                node.attrs["loaded"] = bool(node.attrs.get("loaded")) or bool(value)
            elif key == "parties":
                node.attrs["parties"] = list(dict.fromkeys([*(node.attrs.get("parties") or []), *(value or [])]))
            elif value not in ("", None, (), []) and node.attrs.get(key) in ("", None, (), []):
                node.attrs[key] = value
        return node_id

    def party(self, name: str, *, association: Iterable[str] = (), developers: Iterable[Any] = (),
              kind: PartyKind | None = None) -> str:
        chosen = kind or party_kind(name, association=association, developers=developers)
        if chosen is PartyKind.ASSOCIATION:
            node_id = "party:association"
            label = "the association"
        elif chosen is PartyKind.BUSINESS:
            node_id = "party:" + _fold(name).lower().replace(" ", "-")
            label = _fold(name)
        else:
            node_id = _private_id(name)
            label = "private person"
        node = self.nodes.get(node_id)
        if node is None:
            node = self.nodes[node_id] = Node(node_id, NodeType.PARTY, label, {"partyKind": chosen.value, "names": []})
        if _fold(name) and _fold(name) not in node.attrs["names"]:
            node.attrs["names"].append(_fold(name))
        return node_id

    def parcel(self, apn: str, *, unit: str = "", **attrs: Any) -> str:
        node_id = parcel_id(apn)
        node = self.nodes.get(node_id)
        if node is None:
            self.nodes[node_id] = Node(node_id, NodeType.PARCEL, str(apn), {"apn": str(apn), "unit": unit, **attrs})
        else:
            for key, value in (("unit", unit), *attrs.items()):
                if value not in ("", None) and node.attrs.get(key) in ("", None):
                    node.attrs[key] = value
        return node_id

    # Edges ------------------------------------------------------------------------------------------------------

    def link(self, kind: EdgeKind, source: str, target: str, *, rule: str, store: str, lead: bool = False,
             note: str = "", via: str = "") -> Edge | None:
        """Add an edge unless it would close a cycle in its family (then it is reported). A repeat of the same edge
        keeps the first and adds the rule to ``also``."""
        provenance = Provenance(rule, store, lead, note)
        edge = Edge(kind, source, target, provenance, via)
        if source not in self.nodes or target not in self.nodes:
            raise KeyError(f"link {kind.value}: {source if source not in self.nodes else target} is not a node")
        held = self._by_key.get(edge.key)
        if held is not None:
            if provenance != held.provenance and provenance not in held.also:
                held.also.append(provenance)
            return held
        if source == target:
            self.cycles.append(Cycle(kind.family, edge, (source,)))
            return None
        path = self._path(kind.family, target, source)
        if path is not None:
            self.cycles.append(Cycle(kind.family, edge, (source, *path)))
            return None
        self.edges.append(edge)
        self._by_key[edge.key] = edge
        self._out.setdefault(kind.family, {}).setdefault(source, set()).add(target)
        return edge

    def _path(self, family: str, start: str, goal: str) -> tuple[str, ...] | None:
        """A path from ``start`` to ``goal`` along one family's edges, or None."""
        out = self._out.get(family, {})
        back: dict[str, str] = {start: ""}
        queue = deque([start])
        while queue:
            current = queue.popleft()
            if current == goal:
                trail = [current]
                while back[trail[-1]]:
                    trail.append(back[trail[-1]])
                return tuple(reversed(trail))
            for nxt in sorted(out.get(current, ())):
                if nxt not in back:
                    back[nxt] = current
                    queue.append(nxt)
        return None

    def merge(self, other: InstrumentGraph) -> InstrumentGraph:
        """Add another graph's nodes and edges (each edge checked again), its cycles, and its notes."""
        for node in other.nodes.values():
            mine = self.nodes.get(node.id)
            if mine is None:
                self.nodes[node.id] = Node(node.id, node.type, node.label, dict(node.attrs))
                continue
            for key, value in node.attrs.items():
                if key == "names":
                    mine.attrs["names"] = list(dict.fromkeys([*mine.attrs.get("names", []), *value]))
                elif key == "loaded":
                    mine.attrs["loaded"] = bool(mine.attrs.get("loaded")) or bool(value)
                elif value not in ("", None, (), []) and mine.attrs.get(key) in ("", None, (), []):
                    mine.attrs[key] = value
        for edge in other.edges:
            for provenance in (edge.provenance, *edge.also):
                self.link(edge.kind, edge.source, edge.target, rule=provenance.rule, store=provenance.store,
                          lead=provenance.lead, note=provenance.note, via=edge.via)
        self.cycles.extend(other.cycles)
        self.notes.extend(note for note in other.notes if note not in self.notes)
        return self

    # Reading it -------------------------------------------------------------------------------------------------

    def edges_of(self, kind: EdgeKind) -> list[Edge]:
        return [edge for edge in self.edges if edge.kind is kind]

    def is_dag(self, family: str) -> bool:
        """True when the family's accepted edges hold no cycle (always, by construction; a test checks it)."""
        out = self._out.get(family, {})
        state: dict[str, int] = {}

        def visit(node: str) -> bool:
            state[node] = 1
            for nxt in out.get(node, ()):
                if state.get(nxt) == 1 or (state.get(nxt) is None and not visit(nxt)):
                    return False
            state[node] = 2
            return True

        return all(state.get(node) == 2 or visit(node) for node in list(out))

    def neighborhood(self, start: str, depth: int = 2) -> InstrumentGraph:
        """The nodes within ``depth`` edges of ``start`` (either direction), with the edges between them."""
        if start not in self.nodes:
            raise KeyError(start)
        touching: dict[str, set[str]] = {}
        for edge in self.edges:
            touching.setdefault(edge.source, set()).add(edge.target)
            touching.setdefault(edge.target, set()).add(edge.source)
        kept = {start}
        frontier = {start}
        for _ in range(depth):
            frontier = {n for node in frontier for n in touching.get(node, ())} - kept
            kept |= frontier
        out = InstrumentGraph(county=self.county, title=self.title)
        for node_id in kept:
            node = self.nodes[node_id]
            out.nodes[node_id] = Node(node.id, node.type, node.label, dict(node.attrs))
        for edge in self.edges:
            if edge.source in kept and edge.target in kept:
                out.edges.append(edge)
                out._by_key[edge.key] = edge
                out._out.setdefault(edge.family, {}).setdefault(edge.source, set()).add(edge.target)
        out.notes = list(self.notes)
        return out

    def _visible(self, view: View) -> set[str]:
        if view is View.PRIVATE:
            return set(self.nodes)
        return {node_id for node_id, node in self.nodes.items()
                if not (node.type is NodeType.PARTY and node.attrs.get("partyKind") == PartyKind.PRIVATE.value)}

    def _private_label(self, node_id: str) -> str:
        """A private person's label: the role the edges give it and the parcels it touched, never a name."""
        vested = [e.source for e in self.edges if e.kind is EdgeKind.VESTS and e.target == node_id]
        by_number: dict[str, list[str]] = {}
        for other in self.nodes.values():
            if other.type is NodeType.INSTRUMENT:
                by_number.setdefault(str(other.attrs.get("number", "")), []).append(other.id)
        granted = [deed for e in self.edges if e.kind is EdgeKind.CONVEYS and e.source == node_id for deed in by_number.get(e.via, ())]
        role = "owner" if vested else "grantor" if granted else "named party"
        parcels: list[str] = []
        for deed in vested + granted:
            for carry in self.edges:
                if carry.kind is EdgeKind.CARRIES and carry.source == deed:
                    apn = self.nodes[carry.target].attrs.get("apn", "")
                    unit = self.nodes[carry.target].attrs.get("unit", "")
                    label = f"unit {unit}" if unit else f"parcel {apn}"
                    if label not in parcels:
                        parcels.append(label)
        if not parcels:
            return role
        return f"{role}, {parcels[0]}" if len(parcels) == 1 else f"{role}, {len(parcels)} parcels"

    def to_dict(self, view: View = View.SHARED, *, names: bool = False) -> dict[str, Any]:
        """Nodes and edges as JSON, with each edge's provenance. ``SHARED`` holds no private person; ``PRIVATE``
        labels each by role and parcel and carries the names only when ``names`` is asked for."""
        visible = self._visible(view)
        nodes = []
        for node_id in sorted(visible, key=_node_order(self)):
            node = self.nodes[node_id]
            attrs = dict(node.attrs)
            label = node.label
            if node.type is NodeType.PARTY and attrs.get("partyKind") == PartyKind.PRIVATE.value:
                label = self._private_label(node_id)     # only the private view reaches here
                if not names:
                    attrs.pop("names", None)
            nodes.append({"id": node_id, "type": node.type.value, "label": label, **attrs})
        edges = []
        for index, edge in enumerate(self.edges):
            if edge.source not in visible or edge.target not in visible:
                continue
            edges.append({
                "id": f"e{index}",
                "kind": edge.kind.value,
                "family": edge.family,
                "source": edge.source,
                "target": edge.target,
                "via": edge.via,
                "lead": edge.lead,
                "meaning": MEANING[edge.kind],
                "provenance": edge.provenance.as_dict(),
                "also": [p.as_dict() for p in edge.also],
            })
        cycles = [
            {"family": c.family, "kind": c.edge.kind.value, "source": c.edge.source, "target": c.edge.target,
             "rule": c.edge.provenance.rule, "path": list(c.path)}
            for c in self.cycles
            if all(node in visible for node in (c.edge.source, c.edge.target, *c.path))
        ]
        hidden = len(self.cycles) - len(cycles)
        counts: dict[str, int] = {}
        for node in nodes:
            counts[node["type"]] = counts.get(node["type"], 0) + 1
        for edge in edges:
            counts[edge["kind"]] = counts.get(edge["kind"], 0) + 1
        notes = list(self.notes)
        if hidden:
            notes.append(f"{hidden} cycle(s) through private persons are left out of this view")
        if view is View.SHARED:
            private = sum(1 for n in self.nodes.values() if n.type is NodeType.PARTY and n.attrs.get("partyKind") == PartyKind.PRIVATE.value)
            if private:
                notes.append(f"{private} private person(s) left out of the shared view, with their edges")
        return {
            "view": view.value,
            "title": self.title,
            "county": self.county,
            "counties": sorted({n.attrs.get("county", "") for n in self.nodes.values() if n.type is NodeType.INSTRUMENT} - {""}),
            "nodes": nodes,
            "edges": edges,
            "cycles": cycles,
            "counts": counts,
            "families": sorted(set(FAMILY.values())),
            "kinds": [{"kind": k.value, "family": k.family, "meaning": MEANING[k]} for k in EdgeKind],
            "notes": notes,
            "caveats": list(CAVEATS),
        }

    def mermaid(self, view: View = View.SHARED, *, kinds: Iterable[EdgeKind] | None = None, direction: str = "LR") -> str:
        """A Mermaid flowchart in ``history_report``'s manner: instruments as ``d<number>`` boxes with the number, the
        date, and what it is; a firm edge solid, a lead dotted; a superseded instrument struck."""
        data = self.to_dict(view)
        wanted = {EdgeKind(k).value if not isinstance(k, EdgeKind) else k.value for k in kinds} if kinds else None
        edges = [e for e in data["edges"] if wanted is None or e["kind"] in wanted]
        used = {e["source"] for e in edges} | {e["target"] for e in edges}
        nodes = [n for n in data["nodes"] if wanted is None or n["id"] in used]
        names: dict[str, str] = {}
        taken: set[str] = set()
        for node in nodes:
            base = {"instrument": "d", "party": "p", "parcel": "a"}[node["type"]] + (_alnum(node.get("number") or node.get("apn") or node["id"]) if node["type"] != "party" else hashlib.sha1(node["id"].encode()).hexdigest()[:8])
            name, n = base, 2
            while name in taken:
                name, n = f"{base}_{n}", n + 1
            taken.add(name)
            names[node["id"]] = name
        rows = [f"flowchart {direction}"]
        struck: list[str] = []
        loose: list[str] = []
        for node in nodes:
            text = _mermaid_label(node)
            if node["type"] == "instrument":
                rows.append(f'    {names[node["id"]]}["{text}"]')
                if node.get("status", "").startswith("superseded") or node.get("supersededBy"):
                    struck.append(names[node["id"]])
                if not node.get("loaded", True):
                    loose.append(names[node["id"]])
            elif node["type"] == "party":
                rows.append(f'    {names[node["id"]]}(["{text}"])')
            else:
                rows.append(f'    {names[node["id"]]}{{{{"{text}"}}}}')
        for edge in edges:
            arrow = "-.->" if edge["lead"] else "-->"
            rows.append(f'    {names[edge["source"]]} {arrow}|{edge["kind"]}| {names[edge["target"]]}')
        if struck:
            rows.append("    classDef superseded stroke-dasharray: 5 5,opacity:0.7")
            rows.append(f"    class {','.join(struck)} superseded")
        if loose:
            rows.append("    classDef unloaded stroke-dasharray: 2 2")
            rows.append(f"    class {','.join(loose)} unloaded")
        return "\n".join(rows)


def _node_order(graph: InstrumentGraph):
    rank = {NodeType.PARCEL: 0, NodeType.INSTRUMENT: 1, NodeType.PARTY: 2}

    def key(node_id: str):
        node = graph.nodes[node_id]
        return (rank[node.type], node.attrs.get("recorded") or "9999", node.attrs.get("number") or node.label, node_id)
    return key


def _mermaid_label(node: Mapping[str, Any]) -> str:
    if node["type"] == "instrument":
        parts = [node.get("number", "")]
        if node.get("recorded"):
            parts.append(node["recorded"])
        what = node.get("role") or node.get("filing") or node.get("kind") or ("cited, not loaded" if not node.get("loaded", True) else "")
        if what:
            parts.append(what + (f" phase {node['phase']}" if node.get("phase") else ""))
        if node.get("supersededBy"):
            parts.append(f"superseded by {node['supersededBy']}")
        text = "<br/>".join(str(p) for p in parts if p)
    elif node["type"] == "parcel":
        text = f"parcel {node.get('apn', '')}" + (f"<br/>unit {node['unit']}" if node.get("unit") else "")
    else:
        text = str(node.get("label", ""))
        if len(text) > 42:
            text = text[:41] + "…"
    return text.replace('"', "'")


# Builders -----------------------------------------------------------------------------------------------------------

_CONVEYANCE_KINDS = frozenset({"fee", "foreclosure"})
_LIEN_KINDS = frozenset({"lien"})
_RELEASE_KINDS = frozenset({"release"})


@dataclass(frozen=True)
class Context:
    """What the builders need to know about the community: the county, the association's index spellings, and the
    developers (``jason.community.base.Developer`` rows: ``name`` and the index ``names``)."""

    county: str = ""
    association: tuple[str, ...] = ()
    developers: tuple[Any, ...] = ()

    def party(self, graph: InstrumentGraph, name: str) -> str:
        return graph.party(name, association=self.association, developers=self.developers)

    def kind_of(self, name: str) -> PartyKind:
        return party_kind(name, association=self.association, developers=self.developers)

    def public(self, names: Iterable[str]) -> list[str]:
        """The names that are a business or the association: the only names an instrument node carries."""
        return [_fold(n) for n in names if _fold(n) and self.kind_of(n) is not PartyKind.PRIVATE]


def _family_of(filing_code: str, filing_name: str) -> str:
    try:
        from jason.community.filings import instrument_class

        return instrument_class(filing_code, filing_name).family.value
    except Exception:  # noqa: BLE001 - a county whose filings asspy does not class still adds its instruments
        return ""


def add_filed(graph: InstrumentGraph, items: Iterable[Any], ctx: Context, *, store: str = "index",
              lead: bool = False, apn: str = "") -> list[str]:
    """Instruments from index rows (asspy ``FiledInstrument``: number, recorded, kind, grantors, grantees,
    cross_references, filing_code, filing_name). A conveyance conveys and vests; any other filing names its business
    parties. Each cross-reference is a ``cites`` edge (to a not-loaded node when the cited number is not in hand); a
    release that cites a lien ``releases`` it. With ``apn``, a deed ``carries`` the parcel and a lien ``encumbers``
    it."""
    added: list[str] = []
    rows = list(items)
    for item in rows:
        node = _filed_node(graph, item, ctx)
        added.append(node)
        _parties(graph, item, node, ctx, store=store, lead=lead)
        if apn:
            parcel = graph.parcel(apn)
            if item.kind in _CONVEYANCE_KINDS:
                graph.link(EdgeKind.CARRIES, node, parcel, rule="index.parcel", store=store, lead=lead)
            elif item.kind in _LIEN_KINDS:
                graph.link(EdgeKind.ENCUMBERS, node, parcel, rule="index.parcel", store=store, lead=True,
                           note="a lien indexes a person: joined to this parcel through its owner")
    by_number = {item.number: item for item in rows}
    for item in rows:
        source = instrument_id(item.number, ctx.county)
        for cited in getattr(item, "cross_references", ()) or ():
            if not cited or cited == item.number:
                continue
            other = by_number.get(cited)
            target = _filed_node(graph, other, ctx) if other is not None else graph.instrument(cited, county=ctx.county, loaded=False)
            graph.link(EdgeKind.CITES, source, target, rule="index.cross-reference", store=store)
            if item.kind in _RELEASE_KINDS and (other is None or other.kind in _LIEN_KINDS):
                graph.link(EdgeKind.RELEASES, source, target, rule="index.cross-reference", store=store,
                           note="a release that cites the lien")
            if item.kind == "foreclosure" and other is not None and other.kind in _LIEN_KINDS:
                graph.link(EdgeKind.FORECLOSES, source, target, rule="index.cross-reference", store=store)
    return added


def _filed_node(graph: InstrumentGraph, item: Any, ctx: Context, **attrs: Any) -> str:
    code = str(getattr(item, "filing_code", "") or "")
    name = str(getattr(item, "filing_name", "") or "")
    filing = f"{code} {name}".strip()
    return graph.instrument(
        item.number, county=ctx.county, recorded=item.recorded, filing=filing, kind=str(getattr(item, "kind", "") or ""),
        family=_family_of(code, name), parties=ctx.public((*item.grantors, *item.grantees)), **attrs,
    )


def _parties(graph: InstrumentGraph, item: Any, node: str, ctx: Context, *, store: str, lead: bool) -> None:
    grantors = tuple(n for n in item.grantors if _fold(n))
    grantees = tuple(n for n in item.grantees if _fold(n))
    if getattr(item, "kind", "") in _CONVEYANCE_KINDS:
        _convey(graph, node, item.number, grantors, grantees, ctx, store=store, lead=lead)
        return
    for name in (*grantors, *grantees):
        graph.link(EdgeKind.NAMES, node, ctx.party(graph, name), rule="index.party", store=store, lead=lead)


def _convey(graph: InstrumentGraph, node: str, number: str, grantors: Iterable[str], grantees: Iterable[str], ctx: Context,
            *, store: str, lead: bool, rule: str = "index.party") -> None:
    givers = [ctx.party(graph, name) for name in grantors if _fold(name)]
    takers = [ctx.party(graph, name) for name in grantees if _fold(name)]
    for taker in takers:
        graph.link(EdgeKind.VESTS, node, taker, rule=rule, store=store, lead=lead)
        for giver in givers:
            if giver != taker:
                graph.link(EdgeKind.CONVEYS, giver, taker, rule=rule, store=store, lead=lead, via=number)


def add_ownership_history(graph: InstrumentGraph, history: Any, ctx: Context, *, store: str = "chain",
                          unit: str = "") -> list[str]:
    """One parcel's chain (``OwnershipHistory`` of ``ChainStep``): each deed ``carries`` the parcel, each step is
    ``prior_of`` its earlier deeds, each cited number not loaded is a not-loaded node it ``cites``, and each deed
    conveys from its grantors to its grantees. A step that cites its prior is firm; one placed by a name handoff is
    a lead."""
    apn = str(getattr(history, "apn", "") or "")
    parcel = graph.parcel(apn, unit=unit) if apn else ""
    added: list[str] = []
    for step in history.steps:
        item = step.conveyance
        node = graph.instrument(item.number, county=ctx.county, recorded=item.recorded, kind="fee",
                                parties=ctx.public((*item.grantors, *item.grantees)), chain=True)
        added.append(node)
        if parcel:
            graph.link(EdgeKind.CARRIES, node, parcel, rule="chain.step", store=store)
        _convey(graph, node, item.number, item.grantors, item.grantees, ctx, store=store, lead=False, rule="chain.step")
    for step in history.steps:
        item = step.conveyance
        node = instrument_id(item.number, ctx.county)
        refs = set(getattr(item, "cross_references", ()) or ())
        for prior in step.priors:
            target = graph.instrument(prior, county=ctx.county)
            cited = prior in refs
            graph.link(EdgeKind.PRIOR_OF, node, target, rule="chain.cites" if cited else "chain.prior", store=store,
                       lead=False if cited else bool(refs), note="" if cited or not refs else "placed by a name handoff, not a citation")
        for number in step.cited:
            target = graph.instrument(number, county=ctx.county, loaded=False)
            graph.link(EdgeKind.CITES, node, target, rule="chain.cited", store=store, note="cited, not loaded")
    return added


# What each process seat role makes, and which way the edge runs ("in": seat -> anchor; "out": anchor -> seat).
SEAT_EDGES: dict[str, tuple[EdgeKind, str]] = {
    "notice of completion": (EdgeKind.COMPLETES, "in"),
    "buyer lien": (EdgeKind.BESIDE, "in"),
    "companion vesting": (EdgeKind.BESIDE, "in"),
    "partial reconveyance": (EdgeKind.BESIDE, "in"),
    "released lien": (EdgeKind.BESIDE, "in"),
    "deed of trust": (EdgeKind.FORECLOSES, "out"),
    "prior deed": (EdgeKind.PRIOR_OF, "out"),
    "trustee's deed": (EdgeKind.PRIOR_OF, "out"),
    "first recording": (EdgeKind.RE_RECORDS, "out"),
    "re-recording": (EdgeKind.RE_RECORDS, "in"),
    "companion transfer": (EdgeKind.BESIDE, "in"),
    "same-day deed, same parties": (EdgeKind.BESIDE, "in"),   # another parcel the buyer took, or a duplicate
}
# A seat's reason that says the seat holds nothing of this closing's.
_UNSEATED = frozenset({"missing", "absent", "other parties", "not found"})


@dataclass(frozen=True)
class Seat:
    """One instrument a process placed beside a chain deed: the seat's role, the number, and what is known of it."""

    role: str
    number: str
    reason: str = "present"
    recorded: date | None = None
    kind: str = ""
    filing: str = ""
    grantors: tuple[str, ...] = ()
    grantees: tuple[str, ...] = ()


def add_seats(graph: InstrumentGraph, anchor: str, seats: Iterable[Seat], ctx: Context, *, process: str,
              apn: str = "", store: str = "process") -> None:
    """The instruments a process reading seats around one chain deed, as edges by role (``SEAT_EDGES``). A seat is a
    lead. A buyer's lien also ``encumbers`` the parcel; a partial reconveyance ``releases`` the lien the same reading
    seats as released."""
    anchor_id = instrument_id(anchor, ctx.county)
    if anchor_id not in graph.nodes:
        graph.instrument(anchor, county=ctx.county)
    seats = [s for s in seats if s.number and s.number != anchor and s.reason not in _UNSEATED]
    placed: dict[str, str] = {}
    for seat in seats:
        node = graph.instrument(seat.number, county=ctx.county, recorded=seat.recorded, filing=seat.filing, kind=seat.kind,
                                loaded=bool(seat.filing or seat.kind), parties=ctx.public((*seat.grantors, *seat.grantees)))
        placed[seat.role] = node
        kind, way = SEAT_EDGES.get(seat.role, (EdgeKind.BESIDE, "in"))
        source, target = (node, anchor_id) if way == "in" else (anchor_id, node)
        graph.link(kind, source, target, rule=f"process.{process or 'reading'}.{seat.role}", store=store, lead=True,
                   note=seat.reason if seat.reason != "present" else "", via=seat.role)
        if seat.role == "buyer lien" and apn:
            graph.link(EdgeKind.ENCUMBERS, node, graph.parcel(apn), rule=f"process.{process or 'reading'}.buyer lien",
                       store=store, lead=True)
        if seat.kind in _CONVEYANCE_KINDS and (seat.grantors or seat.grantees):
            _convey(graph, node, seat.number, seat.grantors, seat.grantees, ctx, store=store, lead=True,
                    rule=f"process.{process or 'reading'}.{seat.role}")
    if "partial reconveyance" in placed and "released lien" in placed:
        graph.link(EdgeKind.RELEASES, placed["partial reconveyance"], placed["released lien"],
                   rule=f"process.{process or 'reading'}.released lien", store=store, lead=True)


def add_reading(graph: InstrumentGraph, anchor: str, reading: Any, ctx: Context, *, apn: str = "",
                load: Any = None, store: str = "process") -> None:
    """A process ``Reading`` (``jason.community.processes``) around a chain deed: its filled slots as seats. ``load``
    (number -> FiledInstrument or None) fills what is known of each seat."""
    seats = []
    for slot in getattr(reading, "slots", ()):
        if not slot.number or slot.number == anchor:
            continue
        item = load(slot.number) if load else None
        seats.append(Seat(slot.role, slot.number, slot.reason,
                          getattr(item, "recorded", None), getattr(item, "kind", "") or "",
                          f"{getattr(item, 'filing_code', '')} {getattr(item, 'filing_name', '')}".strip() if item else "",
                          tuple(getattr(item, "grantors", ()) or ()), tuple(getattr(item, "grantees", ()) or ())))
    add_seats(graph, anchor, seats, ctx, process=getattr(reading, "process", ""), apn=apn, store=store)


def add_encumbrance(graph: InstrumentGraph, encumbrance: Any, ctx: Context, *, apn: str = "", store: str = "lifecycle",
                    note: str = "") -> str:
    """A lien lifecycle (asspy ``Encumbrance``): the opening instrument, each later step ``advances`` it or, when it
    closes the lifecycle, ``releases`` it. With ``apn``, the opener ``encumbers`` the parcel (a lead: a lien indexes a
    person). The claimant is named when it is a business or the association."""
    steps = tuple(getattr(encumbrance, "steps", ()) or ())
    if not steps:
        return ""
    process = getattr(getattr(encumbrance, "process", None), "value", "") or ""
    opener = steps[0]
    opened = graph.instrument(opener.number, county=ctx.county, recorded=opener.recorded, filing=opener.filing,
                              process=process, parties=ctx.public(getattr(encumbrance, "claimant", ())))
    for name in getattr(encumbrance, "claimant", ()) or ():
        if ctx.kind_of(name) is not PartyKind.PRIVATE:
            graph.link(EdgeKind.NAMES, opened, ctx.party(graph, name), rule="lifecycle.claimant", store=store)
    for step in steps[1:]:
        node = graph.instrument(step.number, county=ctx.county, recorded=step.recorded, filing=step.filing, process=process)
        closes = str(getattr(step, "effect", "")) == "closes"
        graph.link(EdgeKind.RELEASES if closes else EdgeKind.ADVANCES, node, opened, rule="lifecycle.step", store=store,
                   lead=True, note=f"{getattr(step, 'effect', '')} the {process.replace('_', ' ')}".strip())
    if apn:
        graph.link(EdgeKind.ENCUMBERS, opened, graph.parcel(apn), rule="lifecycle.owner", store=store, lead=True,
                   note=note or "a lien indexes a person: joined to this parcel through its owner's name")
    return opened


# Governing instruments --------------------------------------------------------------------------------------------

_DECLARATION = frozenset({"declaration", "restated declaration"})
_AMENDS = frozenset({"amendment", "restatement or amendment", "covenant modification"})
_PLAN_AMENDMENT = frozenset({"condominium plan amendment"})


def add_governing(graph: InstrumentGraph, records: Iterable[Any], ctx: Context, *, store: str = "association record",
                  unplaced: Iterable[Any] = ()) -> list[str]:
    """The governing records (``jason.community.governing.GoverningRecord``): each instrument with its role, phase,
    delivery, developer, and standing. An annexation ``annexes`` and an amendment ``amends`` the declaration it
    cites, else the declaration in force (a lead, by role). A plan amendment amends the plan it cites. A common-area
    deed conveys to the association. ``unplaced`` records (a developer's filing tied to no phase) are added as leads
    with no edge."""
    rows = list(records)
    added: list[str] = []
    for record in rows:
        node = _governing_node(graph, record, ctx)
        added.append(node)
        if record.role == "common area deed":
            names = tuple(record.parties)
            ours = [n for n in names if ctx.kind_of(n) is PartyKind.ASSOCIATION]
            others = [n for n in names if n not in ours]
            _convey(graph, node, record.number, others, ours, ctx, store=store, lead=False, rule="governing.common-area deed")
        else:
            for name in record.parties:
                if ctx.kind_of(name) is not PartyKind.PRIVATE:
                    graph.link(EdgeKind.NAMES, node, ctx.party(graph, name), rule="governing.party", store=store)
    for record in unplaced:
        node = _governing_node(graph, record, ctx, unplaced=True)
        added.append(node)
    in_force = [r for r in rows if r.role in _DECLARATION and not r.superseded_by]
    declaration = instrument_id(in_force[-1].number, ctx.county) if in_force else ""
    roles = {r.number: r.role for r in rows}
    for record in rows:
        node = instrument_id(record.number, ctx.county)
        for cited in record.cites:
            if cited and cited != record.number:
                graph.link(EdgeKind.CITES, node, graph.instrument(cited, county=ctx.county, loaded=cited in roles),
                           rule="index.cross-reference", store=store)
        kind = EdgeKind.ANNEXES if record.role == "annexation" else EdgeKind.AMENDS if record.role in _AMENDS else None
        if kind is not None:
            cited_decl = [c for c in record.cites if roles.get(c) in _DECLARATION]
            if cited_decl:
                for cited in cited_decl:
                    graph.link(kind, node, instrument_id(cited, ctx.county), rule="governing.cites", store=store)
            elif declaration and declaration != node:
                graph.link(kind, node, declaration, rule="governing.role", store=store, lead=True,
                           note="by its role: it cites no declaration in the index")
        if record.role in _PLAN_AMENDMENT:
            for cited in record.cites:
                if roles.get(cited, "").startswith("condominium plan"):
                    graph.link(EdgeKind.AMENDS, node, instrument_id(cited, ctx.county), rule="governing.cites", store=store)
    return added


def _governing_node(graph: InstrumentGraph, record: Any, ctx: Context, *, unplaced: bool = False) -> str:
    delivery = getattr(record, "delivery", None)
    attrs: dict[str, Any] = {
        "delivery": getattr(delivery, "value", "") if delivery is not None else "",
        "phase": record.phase,
        "developer": getattr(record, "developer", "") or "",
        "status": record.status if hasattr(record, "status") else "",
        "parties": ctx.public(record.parties),
    }
    if getattr(record, "superseded_by", ""):
        attrs["supersededBy"] = record.superseded_by
    if unplaced:
        attrs["unplaced"] = True
    return graph.instrument(record.number, county=ctx.county, recorded=record.recorded, filing=record.filing,
                            role=record.role, **attrs)


def add_supersessions(graph: InstrumentGraph, facts: Iterable[Any], ctx: Context, *, store: str = "specification") -> None:
    """The specification's ``Supersession`` facts: the later instrument ``supersedes`` the earlier, firm, with the
    source the fact cites."""
    for fact in facts:
        later = graph.instrument(fact.superseded_by, county=ctx.county)
        earlier = graph.instrument(fact.number, county=ctx.county, supersededBy=fact.superseded_by,
                                   status=f"rescinded and superseded by {fact.superseded_by}")
        graph.nodes[earlier].attrs["supersededBy"] = fact.superseded_by
        graph.nodes[earlier].attrs["status"] = f"rescinded and superseded by {fact.superseded_by}"
        if getattr(fact, "phase", None) and not graph.nodes[earlier].attrs.get("phase"):
            graph.nodes[earlier].attrs["phase"] = fact.phase
        graph.link(EdgeKind.SUPERSEDES, later, earlier, rule="spec.supersession", store=store,
                   note="; ".join(x for x in (getattr(fact, "reason", ""), getattr(fact, "source", "")) if x))


def add_governing_document(graph: InstrumentGraph, document: Any, ctx: Context, *, store: str = "specification") -> None:
    """The specification's governing document (``GoverningDocument``) and its amendments: each recorded amendment
    ``amends`` the recorded document, firm, with the sections it changes. One with no number is not recorded and is
    noted, not drawn."""
    number = getattr(document, "recorder_number", "") or ""
    if not number:
        graph.notes.append(f"{getattr(document, 'title', 'the governing document')}: no recording number in the specification")
        return
    kind = getattr(getattr(document, "document_kind", None), "value", "") or "governing document"
    # A role the governing records already gave it ("restated declaration") stays: ``instrument`` never overwrites.
    base = graph.instrument(number, county=ctx.county, recorded=getattr(document, "recorded", None), role=kind,
                            title=getattr(document, "title", ""), pinned=True)
    for amendment in getattr(document, "amendments", ()) or ():
        title = getattr(amendment, "title", "") or "an amendment"
        if not getattr(amendment, "recorder_number", ""):
            graph.notes.append(f"{title}: not recorded (no number in the specification); an amendment takes effect when recorded")
            continue
        node = graph.instrument(amendment.recorder_number, county=ctx.county, recorded=getattr(amendment, "recorded", None),
                                role="amendment", title=title, pinned=True, sections=list(getattr(amendment, "sections", ()) or ()))
        sections = ", ".join(getattr(amendment, "sections", ()) or ())
        graph.link(EdgeKind.AMENDS, node, base, rule="spec.amendment", store=store,
                   note=f"sections {sections}" if sections else "")


_RELATION_EDGE = {
    "amends": EdgeKind.AMENDS,
    "annexes property under": EdgeKind.ANNEXES,
    "rescinds and supersedes": EdgeKind.SUPERSEDES,
}


def add_readings(graph: InstrumentGraph, readings: Iterable[Any], ctx: Context) -> None:
    """Document readings (``jason.community.readings.DocumentReading``): each citation in a stamped copy's text, as
    the edge its verb names (amends, annexes under, rescinds and supersedes) or ``cites``. A reading is a lead. A copy
    with no stamp cannot bind itself to a number and is counted, not drawn."""
    unstamped = 0
    for reading in readings:
        number = getattr(reading, "number", "") or ""
        if not number:
            unstamped += 1
            continue
        path = getattr(reading, "path", None)
        store = f"reading:{getattr(path, 'name', path) or 'text'}"
        node = graph.instrument(number, county=ctx.county, recorded=getattr(reading.stamp, "recorded", None),
                                title=getattr(reading, "title", "") or "", readOnDisk=True,
                                phase=getattr(reading, "phase", None))
        for citation in reading.citations:
            if not citation.number or citation.number == number:
                continue
            relation = getattr(citation.relation, "value", str(citation.relation))
            target = graph.instrument(citation.number, county=ctx.county, recorded=citation.recorded)
            graph.link(_RELATION_EDGE.get(relation, EdgeKind.CITES), node, target, rule=f"reading.{relation}",
                       store=store, lead=True, note=relation if relation not in _RELATION_EDGE else "")
    if unstamped:
        graph.notes.append(f"{unstamped} copy(ies) read with no recorder's stamp: their citations bind to no number")


def add_located(graph: InstrumentGraph, rows: Iterable[Any], ctx: Context, *, store: str = "locator") -> list[str]:
    """The document locator's finds (``jason.tasks.document_locator.Located``, or dicts with the same fields: number,
    recorded, filing, item, tie, parties, via). Each is a lead: an instrument tagged with the checklist item it may
    serve; one found beside another is ``beside`` it; a builder's filing names the builder."""
    added: list[str] = []
    for row in rows:
        get = row.get if isinstance(row, Mapping) else (lambda key, default=None, _r=row: getattr(_r, key, default))
        number = str(get("number", "") or "").strip()
        if not number:
            continue
        tie = get("tie", "")
        tie = getattr(tie, "value", tie) or ""
        recorded = get("recorded", None)
        node = graph.instrument(number, county=ctx.county, recorded=recorded if isinstance(recorded, (date, str)) else None,
                                filing=str(get("filing", "") or ""), item=str(get("item", "") or ""), tie=tie,
                                parties=ctx.public(get("parties", ()) or ()), located=True)
        added.append(node)
        for name in get("parties", ()) or ():
            if ctx.kind_of(name) is not PartyKind.PRIVATE:
                graph.link(EdgeKind.NAMES, node, ctx.party(graph, name), rule="locator.party", store=store, lead=True)
        via = str(get("via", "") or "").strip()
        if not via:
            continue
        if _NUMBER.match(via) and any(ch.isdigit() for ch in via) and not re.search(r"[A-Za-z]{3,}", via):
            graph.link(EdgeKind.BESIDE, node, graph.instrument(via, county=ctx.county), rule="locator.beside", store=store,
                       lead=True, note=tie)
        else:
            graph.link(EdgeKind.NAMES, node, ctx.party(graph, via), rule="locator.builder", store=store, lead=True,
                       note=tie or "the builder's filing; may be another community's")
    return added


def add_location(graph: InstrumentGraph, location: Any, ctx: Context | None = None) -> list[str]:
    """A ``Location`` from the document locator: its county, its association's spellings, and every find."""
    ctx = ctx or Context(getattr(location, "county", "") or graph.county, tuple(getattr(location, "spellings", ()) or ()))
    for note in getattr(location, "notes", ()) or ():
        if note not in graph.notes:
            graph.notes.append(note)
    return add_located(graph, getattr(location, "found", ()) or (), ctx)


def add_parcel_history(graph: InstrumentGraph, history: Any, ctx: Context, *, store: str = "parcel history") -> None:
    """One parcel's assembled history (``jason.community.parcel_history.ParcelHistory``): the chain, each step's
    seated and beside instruments, and the lien lifecycles that opened while an owner held it (or the association's
    own)."""
    apn = history.apn
    unit = str(history.unit) if getattr(history, "unit", None) is not None else ""
    parcel = graph.parcel(apn, unit=unit, building=getattr(history, "building", None), phase=getattr(history, "phase", None),
                          association=bool(getattr(history, "association", False)))
    for step in history.steps:
        node = graph.instrument(step.number, county=ctx.county, recorded=step.recorded, kind="fee", process=step.process,
                                developer=step.developer, parties=ctx.public((*step.grantors, *step.grantees)), chain=True)
        graph.link(EdgeKind.CARRIES, node, parcel, rule="chain.step", store=store)
        _convey(graph, node, step.number, step.grantors, step.grantees, ctx, store=store, lead=False, rule="chain.step")
    for step in history.steps:
        node = instrument_id(step.number, ctx.county)
        for prior in step.priors:
            graph.link(EdgeKind.PRIOR_OF, node, graph.instrument(prior, county=ctx.county), rule="chain.prior", store=store)
        seats = [Seat(r.role, r.number, r.reason, r.recorded, r.kind, r.filing, tuple(r.grantors), tuple(r.grantees))
                 for r in step.related]
        add_seats(graph, step.number, seats, ctx, process=step.process, apn=apn, store=store)
    for lien in getattr(history, "liens", ()) or ():
        if not (lien.community or lien.during_tenure):
            continue
        add_encumbrance(graph, lien.encumbrance, ctx, apn=apn, store=store,
                        note="the association's own lien" if lien.community else "opened while that owner held this parcel; a lien indexes a person")


def add_process_steps(graph: InstrumentGraph, steps: Iterable[Any], ctx: Context, *, apn: str = "",
                      store: str = "process") -> None:
    """A county walk's chain deeds with their process readings and same-day companions (Placer's
    ``jason.community.placer.processes.ProcessStep``: number, recorded, kind, filing_name, grantors, grantees,
    process, companions, reading). The chain's ``prior_of`` edges come from its ``OwnershipHistory``
    (``add_ownership_history``); this adds what the processes seat."""
    for step in steps:
        node = graph.instrument(step.number, county=ctx.county, recorded=step.recorded, kind=step.kind,
                                filing=getattr(step, "filing_name", ""), process=step.process,
                                parties=ctx.public((*step.grantors, *step.grantees)))
        if apn:
            graph.link(EdgeKind.CARRIES, node, graph.parcel(apn), rule="chain.step", store=store)
        companions = {c.number: c for c in getattr(step, "companions", ()) or ()}
        reading = getattr(step, "reading", None)
        if reading is not None:
            add_reading(graph, step.number, reading, ctx, apn=apn, load=companions.get, store=store)
            seated = {slot.number for slot in reading.slots}
        else:
            seated = set()
        for number, item in companions.items():
            if number in seated or number == step.number:
                continue
            other = _filed_node(graph, item, ctx)
            graph.link(EdgeKind.BESIDE, other, node, rule=f"process.{step.process or 'reading'}.companion", store=store,
                       lead=True, note="recorded the same day beside the chain deed")


__all__ = [
    "CAVEATS", "Context", "Cycle", "Edge", "EdgeKind", "FAMILY", "InstrumentGraph", "MEANING", "Node", "NodeType",
    "PartyKind", "Provenance", "SEAT_EDGES", "Seat", "View", "add_encumbrance", "add_filed", "add_governing",
    "add_governing_document", "add_located", "add_location", "add_ownership_history", "add_parcel_history",
    "add_process_steps", "add_reading", "add_readings", "add_seats", "add_supersessions", "instrument_id",
    "parcel_id", "party_kind",
]
