import { useMemo, useState } from "react";
import { Badge, Card, Caveats, Clock, Command, DataTable, Findings, Markdown, RemoteView, type Column } from "../components";
import { useApi } from "../lib/useApi";

interface Row { key: string; slug: string; title: string; document: string; documentTitle: string; purpose: string; effect: string; sections: number; placeholders: string[]; decisions: string[]; authorities: string[] }
interface One {
  found?: boolean; note?: string; key: string; title: string; documentTitle: string; purpose: string; effect: string; authorities: string[]; decisions: string[]; placeholders: string[]; open: string[];
  sectionsMarkdown: string; currentNote: string; stages: { key: string; label: string; date: string; authority?: string }[]; timelineNote: string; today: string; command: string; caveats?: string[];
}

function Change({ k, back }: { k: string; back: () => void }) {
  const [notice, setNotice] = useState("");
  const [decision, setDecision] = useState("");
  const [values, setValues] = useState<Record<string, string>>({});
  const query = useMemo(() => {
    const p = new URLSearchParams({ key: k });
    if (notice) p.set("notice", notice);
    if (decision) p.set("decision", decision);
    for (const [key, v] of Object.entries(values)) if (v.trim()) p.set(`V_${key}`, v);
    return p.toString();
  }, [k, notice, decision, values]);
  const r = useApi<One>(`/api/rule-changes?${query}`);
  return (
    <RemoteView r={r}>
      {(d) => (
        <div className="stack">
          <div className="row wrap"><button onClick={back}>← Rule changes</button><strong>{d.title}</strong><span className="muted">amends {d.documentTitle}</span>{d.authorities.map((a) => <Badge key={a}>{a}</Badge>)}</div>
          <Card title="Why, and what it does"><p>{d.purpose}</p><p className="muted">{d.effect}</p></Card>
          <div className="grid-2">
            <Card title="The board's choices">
              <p className="muted">Each bracket is a choice only the board makes; fill it to see the rule read, nothing is written. The decisions below are settled with counsel before the notice goes out.</p>
              <div className="fields">
                {d.placeholders.map((p) => { const name = p.slice(1, -1); return <label key={p} className="wide">{name} <input value={values[name] ?? ""} onChange={(e) => setValues({ ...values, [name]: e.target.value })} /></label>; })}
              </div>
              <Findings items={d.decisions} empty="no decisions listed" />
              {d.open.length > 0 && <p className="notice notice-warn">Still open: {d.open.join(", ")}</p>}
            </Card>
            <Card title="The 4360 clock">
              <div className="fields">
                <label>Notice goes out <input type="date" value={notice} onChange={(e) => setNotice(e.target.value)} /></label>
                <label>Decision meeting <input type="date" value={decision} onChange={(e) => setDecision(e.target.value)} /></label>
              </div>
              {d.timelineNote ? <p className="notice notice-error">{d.timelineNote}</p> : <Clock stages={d.stages} today={new Date(d.today + "T12:00:00")} />}
              <p className="muted">At least 28 days of notice before the decision (4360(a)); the agenda notice four days before the meeting (4920); notice of adoption within 15 days (4360(c)); members may ask to reverse it within 30 days of that notice (4365).</p>
            </Card>
          </div>
          <Card title="The sections, current and proposed">
            {d.currentNote && <p className="notice notice-warn">{d.currentNote}</p>}
            <div className="preview"><Markdown text={d.sectionsMarkdown} /></div>
          </Card>
          <Command cmd={d.command} note="Saves the member notice as a Gmail draft with no recipients; a person addresses it by each owner's delivery choice and sends it." />
          <Caveats items={d.caveats} />
        </div>
      )}
    </RemoteView>
  );
}

const cols: Column<Row>[] = [
  { key: "title", header: "Proposed change" },
  { key: "documentTitle", header: "Amends" },
  { key: "sections", header: "Sections", align: "right" },
  { key: "placeholders", header: "Board's choices", value: (r) => r.placeholders.length, render: (r) => <span className="row wrap">{r.placeholders.map((p) => <Badge key={p} tone="warn">{p}</Badge>)}</span> },
  { key: "decisions", header: "To settle first", value: (r) => r.decisions.length },
];

/** The proposed rule changes in the specification: each with its sections, the board's bracketed choices, and the 4360 clock. */
export function RuleChangeView() {
  const r = useApi<{ found: boolean; note?: string; changes: Row[] }>("/api/rule-changes");
  const [open, setOpen] = useState("");
  if (open) return <Change k={open} back={() => setOpen("")} />;
  return (
    <RemoteView r={r}>
      {(d) => (
        <Card title={`Proposed rule changes (${d.changes.length})`}>
          <p className="muted">A rule change under Civil Code 4340-4370: the board settles its choices, notices the members at least 28 days ahead, decides at a meeting, and notices the adoption. jason writes the timeline, the notice, and the drafts; the board decides.</p>
          <DataTable rows={d.changes} columns={[...cols, { key: "open", header: "", render: (x) => <button className="primary" onClick={() => setOpen(x.key)}>Open</button> }]} searchable={false} />
        </Card>
      )}
    </RemoteView>
  );
}
