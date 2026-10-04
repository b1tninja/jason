import { InstrumentGraph, type GraphEdge, type GraphNode, type InstrumentGraphData } from "jason-ui";

/* The `/api/instrument-graph?scope=association` payload (`jason.tasks.instrument_graph.payload`), cut to one small
 * made-up subdivision: the declaration and its restatement, two annexations, an amendment, a phase's grant deed with
 * its notice of completion, an assessment lien and its release, two parcels, and the parties. Names are made up. */
const inst = (number: string, recorded: string, role: string, extra: Partial<GraphNode> = {}): GraphNode =>
  ({ id: `inst:example:${number}`, type: "instrument", label: number, number, recorded, role, ...extra });
const edge = (id: string, kind: string, family: string, source: string, target: string, lead: boolean, rule: string, store: string,
  meaning = "", note = ""): GraphEdge =>
  ({ id, kind, family, source, target, lead, meaning, provenance: { rule, store, lead, note: note || undefined } });
const I = (n: string) => `inst:example:${n}`;

const nodes: GraphNode[] = [
  { id: "parcel:1", type: "parcel", label: "000-0000-000-0012", apn: "000-0000-000-0012", unit: "12", phase: 1 },
  { id: "parcel:2", type: "parcel", label: "000-0000-000-0031", apn: "000-0000-000-0031", unit: "31", phase: 2 },
  inst("2001-0000010", "2001-03-01", "declaration", { supersededBy: "2001-0000020" }),
  inst("2001-0000020", "2001-03-08", "restated declaration"),
  inst("2002-0004410", "2002-05-14", "grant deed", { filing: "GRANT DEED" }),
  inst("2002-0004588", "2002-05-20", "notice of completion"),
  inst("2003-0000050", "2003-06-01", "annexation", { phase: 2 }),
  inst("2005-0020001", "2005-06-10", "annexation", { phase: 3 }),
  inst("2010-0000100", "2010-02-01", "first amendment"),
  inst("2019-0081234", "2019-08-02", "assessment lien", { filing: "NOTICE OF DELINQUENT ASSESSMENT" }),
  inst("2020-0010077", "2020-01-21", "release of lien", { filing: "RELEASE" }),
  { id: "party:association", type: "party", label: "the association", partyKind: "association" },
  { id: "party:builder", type: "party", label: "EXAMPLE HOMES INC", partyKind: "business" },
];

const edges: GraphEdge[] = [
  edge("e0", "supersedes", "governing", I("2001-0000020"), I("2001-0000010"), false, "spec.supersession", "specification",
    "rescinded and superseded this instrument", "recital F"),
  edge("e1", "annexes", "governing", I("2003-0000050"), I("2001-0000020"), false, "reading.annexed", "document readings",
    "annexes property under this declaration", "read from the recorded copy"),
  edge("e2", "annexes", "governing", I("2005-0020001"), I("2001-0000020"), true, "governing.role", "association record",
    "annexes property under this declaration", "by its role"),
  edge("e3", "amends", "governing", I("2010-0000100"), I("2001-0000020"), false, "spec.amendment", "specification", "amends this declaration"),
  edge("e4", "covers", "governing", I("2003-0000050"), "parcel:2", true, "spec.phase", "public reports", "annexes this parcel's phase"),
  edge("e5", "completes", "closing", I("2002-0004588"), I("2002-0004410"), true, "closing.window", "county index",
    "the notice of completion for this grant", "recorded within 30 days"),
  edge("e6", "carries", "parcel", I("2002-0004410"), "parcel:1", false, "deed.apn", "ownership store", "conveys this parcel"),
  edge("e7", "encumbers", "parcel", I("2019-0081234"), "parcel:1", false, "lien.apn", "ownership store", "a lien on this parcel"),
  edge("e8", "releases", "loan", I("2020-0010077"), I("2019-0081234"), false, "lien.release", "county index", "releases this lien"),
  edge("e9", "names", "party", I("2019-0081234"), "party:association", false, "index.party", "county index", "names this party"),
  edge("e10", "names", "party", I("2001-0000020"), "party:builder", false, "index.party", "county index", "names this party"),
  edge("e11", "names", "party", I("2001-0000020"), "party:association", false, "index.party", "county index", "names this party"),
];

const base: InstrumentGraphData = {
  found: true, view: "shared", scope: "association", nodes, edges,
  cycles: [{ family: "citation", kind: "cites", source: I("2001-0000010"), target: I("2001-0000020"), rule: "index.cross-reference", path: [] }],
  notes: ["3 private person(s) left out of the shared view, with their edges"],
  caveats: ["A dotted edge is a lead: confirm it from the recorded copy before it is pinned.", "The graph holds what jason has read; an instrument not loaded is cited, not read."],
  mermaid: "flowchart LR\n  d1[2001-0000010] -->|superseded by| d2[2001-0000020]\n  a1[2003-0000050] -->|annexes| d2",
};

const owners: GraphNode[] = [
  { id: "person:a", type: "party", label: "owner, unit 12", partyKind: "private" },
  { id: "person:b", type: "party", label: "owner, unit 12 (second)", partyKind: "private" },
];
const ownerEdges: GraphEdge[] = [
  edge("p1", "vests", "party", I("2002-0004410"), "person:a", false, "deed.grantee", "ownership store", "vests title in this grantee"),
  edge("p2", "vests", "party", I("2002-0004410"), "person:b", false, "deed.grantee", "ownership store", "vests title in this grantee"),
  edge("p3", "conveys", "party", "party:builder", "person:a", false, "deed.parties", "ownership store", "conveys to this grantee"),
];

/** The association's graph in the shared view: a column per recording year, parcels on the left and parties on the right; solid edges firm, dotted ones leads; the cycle left out is noted. */
export const SharedView = () => <InstrumentGraph data={base} />;

/** One instrument chosen from the node list: the restated declaration with what supersedes, annexes, and amends it, each edge's provenance on focus. */
export const Focused = () => <InstrumentGraph data={base} initial={I("2001-0000020")} />;

/** The private view, masked: the grant deed's two grantees appear as private persons labeled by role and parcel, never by name. */
export const PrivateMasked = () => (
  <InstrumentGraph data={{ ...base, view: "private", notes: [], nodes: [...nodes, ...owners], edges: [...edges, ...ownerEdges] }} initial={I("2002-0004410")} />
);

/** Owners' names shown after a person asked (the reveal is logged): each private person's names, with the role and parcel beside them. */
export const NamesShown = () => (
  <InstrumentGraph
    data={{
      ...base, view: "private", notes: [], names: true,
      nodes: [...nodes, { ...owners[0], names: ["EXAMPLE OWNER A"] }, { ...owners[1], names: ["SAMPLE PAT Q"] }],
      edges: [...edges, ...ownerEdges],
      reveal: { at: "2026-10-03T16:20:00+00:00", by: "Jane Example", scope: "association", named: 2, log: "console/reveals.jsonl" },
    }}
    initial={I("2002-0004410")}
  />
);

/** Nothing to draw yet: the loader's note in place of the graph. */
export const NotRead = () => (
  <InstrumentGraph data={{ found: false, note: "No instruments read for this association yet: run jason onboard --locate first.", nodes: [], edges: [] }} />
);
