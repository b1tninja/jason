"""The instrument graph for the active profile, from the Sacramento stores on disk.

``association_graph`` reads the association's record in the index cache (the governing records and the common-area
deeds), the specification (the declaration and its amendments, the supersessions), the document readings of the
recorded copies on disk, the locator's leads, and the stored land chain (the developers' deeds into the community).
``parcel_graph`` reads one parcel's assembled history (``build_parcel_history``: the chain, each deed's process
seats and beside instruments, and its owners' lien lifecycles) and ties the parcel to the annexation of its phase.
``community_graph`` is both for every parcel. Nothing here searches the county; another county's walk feeds the same
builders in ``jason.community.instrument_graph``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from jason.community.instrument_graph import (
    Context,
    EdgeKind,
    InstrumentGraph,
    View,
    add_governing,
    add_governing_document,
    add_located,
    add_ownership_history,
    add_parcel_history,
    add_readings,
    add_supersessions,
    instrument_id,
    parcel_id,
)


def _digits(apn: str) -> str:
    return "".join(ch for ch in str(apn) if ch.isdigit())


def context(community: Any) -> Context:
    from jason.tasks.key_documents import _county

    spellings = tuple(x for x in (community.index_association(), getattr(community, "corporate_name", ""), community.name) if x)
    return Context(_county(community), spellings, tuple(community.developers()))


def association_graph(community: Any = None, root: Path | None = None, profile: str | None = None, *, record: Any = None,
                      readings: bool = True, located: bool = True, land: bool = True) -> InstrumentGraph:
    """The community's governing instruments, their amendments and annexations, what supersedes what, the
    common-area deeds, and the land chain into the community."""
    from jason.tasks.key_documents import _profile, _root, located_rows

    if community is None:
        from jason.community import community as active

        community = active()
    root = _root(root)
    ctx = context(community)
    graph = InstrumentGraph(county=ctx.county, title=f"{community.name}: recorded instruments")
    if record is None and (root / "index-cache.db").is_file():
        from jason.tasks.property_history import load_association_record

        try:
            record = load_association_record(community, root)
        except Exception as exc:  # noqa: BLE001 - the specification alone still draws the declaration
            graph.notes.append(f"the association's record could not be read from the index cache ({type(exc).__name__}: {exc})")
    if record is None:
        graph.notes.append("no index cache on disk: the graph holds what the specification and the leads say only")
    else:
        add_governing(graph, record.governing, ctx, unplaced=record.unplaced)
    try:
        document = community.ccrs
    except Exception:  # noqa: BLE001 - a profile with no declaration in the specification yet
        document = None
    if document is not None:
        add_governing_document(graph, document, ctx)
    add_supersessions(graph, tuple(community.supersessions() or ()), ctx)
    if readings:
        try:
            from jason.tasks.key_documents import _EXTRACT_FOLDERS
            from jason.community.readings import read_folder

            add_readings(graph, read_folder(*(root.joinpath(*parts) for parts in _EXTRACT_FOLDERS)), ctx)
        except Exception as exc:  # noqa: BLE001 - a reading is a lead; without it the record still stands
            graph.notes.append(f"the recorded copies on disk could not be read ({type(exc).__name__}: {exc})")
    if located:
        rows = located_rows(root, _profile(profile))
        if rows:
            add_located(graph, rows, ctx)
    if land and (root / "ownership.db").is_file():
        from jason.community.ownership import OwnershipStore

        with OwnershipStore(root / "ownership.db") as store:
            pinned = store.pinned_history(developers=tuple(community.developers()))
        if pinned is not None:
            add_ownership_history(graph, pinned, ctx, store="land chain")
    return graph


def parcel_histories(community: Any, root: Path, apns: Iterable[str]) -> list[Any]:
    """Each parcel's history, built from the stores as the property-history pages build it, without the tax bills
    and scans the graph does not draw."""
    from jason.community.index_cache import IndexCache
    from jason.community.ownership import OwnershipStore
    from jason.community.parcel_history import build_parcel_history

    developers = tuple(community.developers())
    reports = {report.building: report for report in community.public_reports()}
    blocks = community.unit_blocks()
    wanted = [_digits(a) for a in apns]
    found = []
    with OwnershipStore(root / "ownership.db") as store, IndexCache(root / "index-cache.db") as cache:
        histories = {_digits(h.apn): h for h in store.unit_histories(developers=developers)}
        chain_numbers = frozenset(step.conveyance.number for h in histories.values() for step in h.steps)
        currents = {_digits(r.apn): r for r in store.records()}
        common = {_digits(a) for a in community.common_areas()}
        pinned = store.pinned_history(developers=developers) if common & set(wanted) else None
        for apn in wanted:
            history = histories.get(apn)
            association = apn in common
            if association and pinned is not None and currents.get(apn) is not None:
                from jason.community.history_report import slice_history
                from jason.community.recorder import OwnershipHistory

                sliced = slice_history(pinned, currents[apn].document_number, depth=12)
                history = OwnershipHistory(apn, sliced.steps, developers) if sliced.steps else None
            building = _building(apn, blocks)
            found.append(build_parcel_history(
                apn, history=history, developers=developers, building=building, report=reports.get(building),
                blocks=blocks, load=cache.get, notes=cache.notes, current=currents.get(apn), placed=cache.placed_on,
                load_naming=None if association else cache.naming_party, association=association,
                association_name=community.index_association(), chain_numbers=chain_numbers,
            ))
    return found


def _building(apn: str, blocks) -> int | None:
    from jason.community.reports import plan_block

    found = plan_block(apn, blocks)
    return int(found.building) if found is not None else None


def parcel_graph(community: Any = None, root: Path | None = None, apns: Iterable[str] = (), *,
                 association: InstrumentGraph | None = None) -> InstrumentGraph:
    """Each parcel's chain with its closings and liens, and the annexation that covers its phase (a lead, from the
    phase the public reports give its building)."""
    from jason.tasks.key_documents import _root

    if community is None:
        from jason.community import community as active

        community = active()
    root = _root(root)
    ctx = context(community)
    apns = [a for a in apns if _digits(a)]
    graph = InstrumentGraph(county=ctx.county, title=f"{community.name}: " + (", ".join(apns) if len(apns) < 4 else f"{len(apns)} parcels"))
    if not (root / "ownership.db").is_file():
        graph.notes.append("no ownership store on disk (data/ownership.db): run the property-history walks first")
        return graph
    for history in parcel_histories(community, root, apns):
        add_parcel_history(graph, history, ctx)
        if not history.steps:
            graph.notes.append(f"{history.apn}: no deed is stored for this parcel")
    _cover_phases(graph, community, association)
    return graph


def _cover_phases(graph: InstrumentGraph, community: Any, association: InstrumentGraph | None) -> None:
    """``covers``: the annexation in force for each parcel's phase. The phase is the public report's for the parcel's
    building, so the edge is a lead."""
    by_phase: dict[int, str] = {}
    source = association
    if source is None:
        source = graph
    for node in source.nodes.values():
        attrs = node.attrs
        if attrs.get("role") == "annexation" and attrs.get("phase") and not attrs.get("supersededBy"):
            by_phase[int(attrs["phase"])] = node.id
    if not by_phase:
        return
    for node in list(graph.nodes.values()):
        phase = node.attrs.get("phase") if node.id.startswith("parcel:") else None
        target = by_phase.get(int(phase)) if phase else None
        if target is None:
            continue
        if target not in graph.nodes and association is not None:
            held = association.nodes[target]
            graph.instrument(held.attrs["number"], county=held.attrs.get("county", ""), recorded=held.attrs.get("recorded"),
                             filing=held.attrs.get("filing", ""), role="annexation", phase=held.attrs.get("phase"))
        graph.link(EdgeKind.COVERS, target, node.id, rule="spec.phase", store="public reports", lead=True,
                   note=f"phase {phase}, from the public report for the parcel's building")


def unit_apns(community: Any, unit: int) -> list[str]:
    """Every parcel a unit number can mean (two numberings can both use it)."""
    from jason.community.reports import unit_parcels

    return [apn for _, apn in unit_parcels(int(unit), community.unit_blocks())]


def community_graph(community: Any = None, root: Path | None = None, profile: str | None = None) -> InstrumentGraph:
    """The association's graph with every parcel's beside it."""
    from jason.tasks.key_documents import _root

    if community is None:
        from jason.community import community as active

        community = active()
    root = _root(root)
    graph = association_graph(community, root, profile)
    parcels = parcel_graph(community, root, [*community.units(), *community.common_areas()], association=graph)
    return graph.merge(parcels)


def payload(graph: InstrumentGraph, view: View = View.SHARED, *, mermaid: bool = True, names: bool = False) -> dict[str, Any]:
    data = graph.to_dict(view, names=names)
    if mermaid:
        data["mermaid"] = graph.mermaid(view)
    data["found"] = bool(data["nodes"])
    if not data["found"]:
        data["note"] = "; ".join(graph.notes) or "nothing on disk to draw"
    return data


def focus(graph: InstrumentGraph, number: str, depth: int = 2) -> InstrumentGraph:
    """The part of the graph around one instrument number."""
    node = instrument_id(number, graph.county)
    if node not in graph.nodes:
        node = next((n for n in graph.nodes if n.endswith(":" + number)), "")
    if not node:
        raise KeyError(number)
    return graph.neighborhood(node, depth)


__all__ = ["association_graph", "community_graph", "context", "focus", "parcel_graph", "parcel_histories",
           "parcel_id", "payload", "unit_apns"]
