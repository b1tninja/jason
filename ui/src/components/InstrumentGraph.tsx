import { useMemo, useState } from "react";
import { Badge } from "./Badge";
import { Caveats } from "./Caveats";
import { Markdown } from "./Markdown";

/** One node of the instrument graph (`jason.community.instrument_graph`): an instrument, a party, or a parcel. A private
 * person reaches the console only in the private view, labeled by role and parcel, never by name. */
export interface GraphNode {
  id: string; type: "instrument" | "party" | "parcel"; label: string;
  number?: string; recorded?: string; county?: string; filing?: string; kind?: string; role?: string; phase?: number | null;
  status?: string; supersededBy?: string; loaded?: boolean; item?: string; tie?: string; partyKind?: string; apn?: string; unit?: string;
  [key: string]: unknown;
}
export interface Provenance { rule: string; store: string; lead: boolean; note?: string }
export interface GraphEdge {
  id: string; kind: string; family: string; source: string; target: string; via?: string; lead: boolean; meaning?: string;
  provenance: Provenance; also?: Provenance[];
}
export interface GraphCycle { family: string; kind: string; source: string; target: string; rule: string; path: string[] }
/** The `/api/instrument-graph` payload. */
export interface InstrumentGraphData {
  found?: boolean; note?: string; title?: string; view?: "shared" | "private"; scope?: string;
  nodes: GraphNode[]; edges: GraphEdge[]; cycles?: GraphCycle[]; counts?: Record<string, number>;
  kinds?: { kind: string; family: string; meaning: string }[]; notes?: string[]; caveats?: string[]; mermaid?: string;
}

const COL = 170, ROW = 46, W = 150, H = 34, PAD = 16;
const TYPE_WORD: Record<GraphNode["type"], string> = { instrument: "Instruments", parcel: "Parcels", party: "Parties" };

function nodeText(n: GraphNode): string {
  if (n.type === "instrument") return n.number || n.label;
  if (n.type === "parcel") return n.unit ? `unit ${n.unit}` : `parcel ${n.apn ?? n.label}`;
  return n.label;
}

function nodeDetail(n: GraphNode): string {
  if (n.type === "instrument") {
    const what = n.role || n.filing || n.kind || (n.loaded === false ? "cited, not loaded" : "");
    return [n.recorded, what, n.phase ? `phase ${n.phase}` : "", n.supersededBy ? `superseded by ${n.supersededBy}` : ""].filter(Boolean).join(" · ");
  }
  if (n.type === "parcel") return [n.apn, n.phase ? `phase ${n.phase}` : ""].filter(Boolean).join(" · ");
  return n.partyKind ?? "";
}

/** A layered timeline: parcels in the first column, instruments in one column per recording year (undated last),
 * parties in the last column. Positions only; nothing here decides anything. */
export function layout(nodes: GraphNode[]): Map<string, { x: number; y: number }> {
  const at = new Map<string, { x: number; y: number }>();
  const parcels = nodes.filter((n) => n.type === "parcel");
  const parties = nodes.filter((n) => n.type === "party");
  const instruments = nodes.filter((n) => n.type === "instrument");
  const year = (n: GraphNode) => (n.recorded ? n.recorded.slice(0, 4) : "undated");
  const years = [...new Set(instruments.map(year))].sort((a, b) => (a === "undated" ? 1 : b === "undated" ? -1 : a.localeCompare(b)));
  const first = parcels.length ? 1 : 0;
  parcels.forEach((n, i) => at.set(n.id, { x: PAD, y: PAD + 22 + i * ROW }));
  years.forEach((y, c) => {
    instruments.filter((n) => year(n) === y).sort((a, b) => (a.recorded ?? "").localeCompare(b.recorded ?? "") || (a.number ?? "").localeCompare(b.number ?? ""))
      .forEach((n, i) => at.set(n.id, { x: PAD + (first + c) * COL, y: PAD + 22 + i * ROW }));
  });
  const last = first + years.length;
  parties.forEach((n, i) => at.set(n.id, { x: PAD + last * COL, y: PAD + 22 + i * ROW }));
  return at;
}

function columnHeads(nodes: GraphNode[]): { x: number; text: string }[] {
  const heads: { x: number; text: string }[] = [];
  const instruments = nodes.filter((n) => n.type === "instrument");
  const years = [...new Set(instruments.map((n) => (n.recorded ? n.recorded.slice(0, 4) : "undated")))]
    .sort((a, b) => (a === "undated" ? 1 : b === "undated" ? -1 : a.localeCompare(b)));
  const first = nodes.some((n) => n.type === "parcel") ? 1 : 0;
  if (first) heads.push({ x: PAD, text: "parcels" });
  years.forEach((y, c) => heads.push({ x: PAD + (first + c) * COL, text: y }));
  if (nodes.some((n) => n.type === "party")) heads.push({ x: PAD + (first + years.length) * COL, text: "parties" });
  return heads;
}

function ProvenanceText({ edge, nodes }: { edge: GraphEdge; nodes: Map<string, GraphNode> }) {
  const all = [edge.provenance, ...(edge.also ?? [])];
  return (
    <div>
      <p>
        <strong>{nodeText(nodes.get(edge.source)!)}</strong> {edge.meaning ?? edge.kind} <strong>{nodeText(nodes.get(edge.target)!)}</strong>
        {edge.via ? <span className="muted"> (via {edge.via})</span> : null}
      </p>
      <p>{edge.lead ? <Badge tone="warn">lead</Badge> : <Badge tone="good">firm</Badge>} <span className="muted">{edge.lead ? "a reading, a match, or a seat: something to read, not a finding" : "the county's cross-reference, the stored chain, or a fact the specification pins"}</span></p>
      <ul>
        {all.map((p, i) => (
          <li key={i}><code>{p.rule}</code> from {p.store}{p.lead ? " (lead)" : ""}{p.note ? `: ${p.note}` : ""}</li>
        ))}
      </ul>
    </div>
  );
}

/** The instrument graph: a layered timeline in SVG (a solid line is firm, a dashed one a lead; a struck box was
 * superseded), with a keyboard-accessible list of nodes beside it. Choosing a node lists its edges; focusing an edge
 * shows which rule and store made it. The Mermaid source renders on request through `Markdown`. */
export function InstrumentGraph({ data, initial = "" }: { data: InstrumentGraphData; initial?: string }) {
  const nodes = useMemo(() => new Map(data.nodes.map((n) => [n.id, n])), [data.nodes]);
  const families = useMemo(() => [...new Set(data.edges.map((e) => e.family))].sort(), [data.edges]);
  const [off, setOff] = useState<Record<string, boolean>>({});
  const [selected, setSelected] = useState(initial && nodes.has(initial) ? initial : "");
  const [edgeId, setEdgeId] = useState("");
  const [mermaid, setMermaid] = useState(false);
  const pos = useMemo(() => layout(data.nodes), [data.nodes]);
  if (data.found === false || !data.nodes.length) return <p className="muted">{data.note ?? "Nothing on disk to draw."}</p>;
  const edges = data.edges.filter((e) => !off[e.family]);
  const width = Math.max(...[...pos.values()].map((p) => p.x)) + W + PAD;
  const height = Math.max(...[...pos.values()].map((p) => p.y)) + H + PAD;
  const touching = selected ? edges.filter((e) => e.source === selected || e.target === selected) : [];
  const near = new Set(touching.flatMap((e) => [e.source, e.target]));
  const focusEdge = edges.find((e) => e.id === edgeId);
  const byType = (t: GraphNode["type"]) => data.nodes.filter((n) => n.type === t);
  return (
    <div className="stack instrument-graph">
      <div className="row wrap" role="group" aria-label="Edge families shown">
        {families.map((f) => (
          <label key={f} className="row"><input type="checkbox" checked={!off[f]} onChange={() => setOff({ ...off, [f]: !off[f] })} />{f}</label>
        ))}
        <span className="muted">{data.view === "private" ? "Private view: owners labeled by role and parcel" : "Shared view: no private person"}</span>
      </div>
      <div className="grid-2">
        <div role="region" aria-label="Graph drawing; the list beside it holds the same nodes" tabIndex={0} style={{ overflow: "auto", maxHeight: "70vh", border: "1px solid var(--line)" }}>
          <svg width={width} height={height} role="img" aria-label={`${data.nodes.length} nodes and ${edges.length} edges`} style={{ display: "block" }}>
            <defs>
              <marker id="ig-arrow" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                <path d="M0,0 L10,5 L0,10 z" fill="var(--muted)" />
              </marker>
            </defs>
            {columnHeads(data.nodes).map((h) => <text key={h.x} x={h.x} y={PAD + 8} fontSize="12" fill="var(--muted)">{h.text}</text>)}
            {edges.map((e) => {
              const a = pos.get(e.source), b = pos.get(e.target);
              if (!a || !b) return null;
              const lit = selected && (e.source === selected || e.target === selected);
              const x1 = a.x + (b.x >= a.x ? W : 0), x2 = b.x + (b.x >= a.x ? 0 : W);
              return (
                <line key={e.id} x1={x1} y1={a.y + H / 2} x2={x2 === x1 ? x2 + 1 : x2} y2={b.y + H / 2}
                  stroke={lit ? "var(--accent)" : "var(--muted)"} strokeWidth={lit || e.id === edgeId ? 2 : 1}
                  strokeDasharray={e.lead ? "5 4" : undefined} opacity={selected && !lit ? 0.25 : 0.8} markerEnd="url(#ig-arrow)">
                  <title>{`${e.kind}: ${e.provenance.rule}${e.lead ? " (lead)" : ""}`}</title>
                </line>
              );
            })}
            {data.nodes.map((n) => {
              const p = pos.get(n.id)!;
              const struck = Boolean(n.supersededBy);
              const dim = selected && n.id !== selected && !near.has(n.id);
              return (
                <g key={n.id} transform={`translate(${p.x},${p.y})`} opacity={dim ? 0.35 : 1} onClick={() => { setSelected(n.id); setEdgeId(""); }} style={{ cursor: "pointer" }}>
                  <rect width={W} height={H} rx={n.type === "party" ? 17 : n.type === "parcel" ? 2 : 4}
                    fill="var(--panel)" stroke={n.id === selected ? "var(--accent)" : "var(--line)"} strokeWidth={n.id === selected ? 2 : 1}
                    strokeDasharray={struck || n.loaded === false ? "4 3" : undefined} />
                  <text x={8} y={14} fontSize="12" fill="var(--ink)" textDecoration={struck ? "line-through" : undefined}>{nodeText(n).slice(0, 22)}</text>
                  <text x={8} y={28} fontSize="10" fill="var(--muted)">{(n.type === "instrument" ? n.role || n.filing || n.kind || "" : n.type === "parcel" ? n.apn ?? "" : n.partyKind ?? "").slice(0, 26)}</text>
                </g>
              );
            })}
          </svg>
        </div>
        <div className="stack-sm">
          <nav aria-label="Nodes">
            {(["parcel", "instrument", "party"] as const).map((t) => byType(t).length > 0 && (
              <div key={t}>
                <h3>{TYPE_WORD[t]}</h3>
                <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
                  {byType(t).map((n) => (
                    <li key={n.id}>
                      <button className="link" aria-pressed={n.id === selected} onClick={() => { setSelected(n.id); setEdgeId(""); }}>
                        {nodeText(n)}
                      </button> <span className="muted">{nodeDetail(n)}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </nav>
        </div>
      </div>
      {selected && nodes.has(selected) && (
        <section aria-label="Chosen node" className="card stack-sm">
          <strong>{nodeText(nodes.get(selected)!)}</strong>
          <span className="muted">{nodeDetail(nodes.get(selected)!)}</span>
          {!touching.length ? <p className="muted">No edges in the families shown.</p> : (
            <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
              {touching.map((e) => {
                const other = nodes.get(e.source === selected ? e.target : e.source)!;
                return (
                  <li key={e.id}>
                    <button className="link" onFocus={() => setEdgeId(e.id)} onClick={() => setEdgeId(e.id)} aria-describedby={e.id === edgeId ? "ig-provenance" : undefined}>
                      {e.source === selected ? `${e.kind} → ${nodeText(other)}` : `${nodeText(other)} ${e.kind} → this`}
                    </button> {e.lead ? <Badge tone="warn">lead</Badge> : <Badge tone="good">firm</Badge>}
                  </li>
                );
              })}
            </ul>
          )}
          <div id="ig-provenance" role="status" aria-live="polite">
            {focusEdge && (focusEdge.source === selected || focusEdge.target === selected) ? <ProvenanceText edge={focusEdge} nodes={nodes} /> : <span className="muted">Focus an edge to see which rule made it.</span>}
          </div>
        </section>
      )}
      {(data.cycles?.length ?? 0) > 0 && (
        <div className="notice-warn" role="note">
          {data.cycles!.length} edge{data.cycles!.length === 1 ? "" : "s"} left out: each would have closed a cycle in its family.
          <ul>{data.cycles!.map((c, i) => <li key={i}><code>{c.kind}</code> {nodes.get(c.source) ? nodeText(nodes.get(c.source)!) : c.source} → {nodes.get(c.target) ? nodeText(nodes.get(c.target)!) : c.target} <span className="muted">({c.rule})</span></li>)}</ul>
        </div>
      )}
      {data.mermaid && (
        <div>
          <button aria-expanded={mermaid} onClick={() => setMermaid(!mermaid)}>{mermaid ? "Hide the Mermaid diagram" : "Show as a Mermaid diagram"}</button>
          {mermaid && <Markdown text={"```mermaid\n" + data.mermaid + "\n```"} />}
        </div>
      )}
      {data.notes?.length ? <ul className="muted">{data.notes.map((n, i) => <li key={i}>{n}</li>)}</ul> : null}
      <Caveats items={data.caveats} />
    </div>
  );
}
