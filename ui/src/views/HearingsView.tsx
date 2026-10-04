import { useMemo, useState } from "react";
import { Badge, Card, Clock, Command, Confirm, DataTable, DocList, DueDate, Findings, Markdown, Pill, RemoteView, type Column, type DocRef } from "../components";
import { postJson } from "../lib/api";
import { useApi } from "../lib/useApi";
import type { Hearing as Base } from "./types";

/** `noticeRefs`: the hearing notice as the loader names it (docs/console/doc-component.md), the Doc made from the template
 * first, then jason's draft under `zoom/hearings/`; both P3, opened only in the private view. */
type Hearing = Base & { key: string; stages: { key: string; label: string; date: string; authority?: string; done?: boolean }[]; decision: { findings: string; decidedOn: string; noticeDueBy: string; by: string; recorded: string; history: string[] } | null; violation?: string; owner?: string; noticeRefs?: DocRef[] };
interface Hearings { found?: boolean; note?: string; hearings: Hearing[] }

/** The decision notice as it would read, from the decision-notice template with the hearing's facts, and the command that fills a Drive copy. */
function NoticePreview({ h }: { h: Hearing }) {
  const q = useMemo(() => {
    const p = new URLSearchParams({ kind: "decision-notice", name: `Decision notice, ${h.address}` });
    p.set("V_ADDRESS", h.address);
    p.set("V_HEARING_DATE", h.start.slice(0, 10));
    if (h.decision) { p.set("V_FINDINGS", h.decision.findings); p.set("V_DATE", h.decision.decidedOn); }
    if (h.violation) p.set("V_VIOLATION", h.violation);
    if (h.owner) p.set("V_OWNER_NAME", h.owner);
    return p.toString();
  }, [h]);
  const r = useApi<{ found: boolean; note?: string; markdown: string; open: string[]; command: string }>(`/api/templates?${q}`);
  return (
    <RemoteView r={r}>
      {(d) => (
        <div className="stack">
          {d.open.length > 0 && <p className="notice notice-warn">Still open in the notice: {d.open.map((t) => t.toLowerCase().replace(/_/g, " ")).join(", ")}</p>}
          <div className="preview"><Markdown text={d.markdown} /></div>
          <Command cmd={d.command} note="Fills a copy of the decision-notice template in Drive; a person reviews it and delivers it within fourteen days of the decision (CIV 5855(f))." />
        </div>
      )}
    </RemoteView>
  );
}

/** One hearing opened: its clock, the decision entered once in the board's words, then the notice. */
function HearingPanel({ h, today, onSaved }: { h: Hearing; today: Date; onSaved: (next: Hearing) => void }) {
  const [findings, setFindings] = useState(h.decision?.findings ?? "");
  const [decidedOn, setDecidedOn] = useState(h.decision?.decidedOn ?? h.start.slice(0, 10));
  const [by, setBy] = useState(h.decision?.by ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const save = async () => {
    setBusy(true); setError("");
    try { onSaved({ ...h, ...(await postJson<Hearing>(`/api/hearings/${encodeURIComponent(h.key)}`, { findings, decidedOn, by })) }); }
    catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };
  return (
    <div className="stack">
      <Clock stages={h.stages} today={today} />
      <Card title="The hearing notice">
        {h.noticeRefs?.length
          ? <DocList docs={h.noticeRefs} variant="card" title="" />
          : <p className="muted">No notice saved with this hearing; `jason hearing` writes its draft beside the plan.</p>}
      </Card>
      <div className="grid-2">
        <Card title={h.decision ? "The board's decision" : "Record the board's decision"}>
          <p className="muted">The findings in the board's words, decided at or after the hearing. The written notice is due to the owner within fourteen days of the board's action. jason records the decision; it decides nothing.</p>
          <div className="fields">
            <label className="wide">Findings and the discipline, as decided <textarea rows={4} value={findings} onChange={(e) => setFindings(e.target.value)} /></label>
            <label>Decided on <input type="date" value={decidedOn} onChange={(e) => setDecidedOn(e.target.value)} /></label>
            <label>Recorded by <input value={by} onChange={(e) => setBy(e.target.value)} /></label>
          </div>
          {findings.trim() && by.trim() && (findings !== h.decision?.findings || decidedOn !== h.decision?.decidedOn) && (
            <Confirm busy={busy} onConfirm={save} summary={<p>Record the decision of {decidedOn} on {h.address}: "{findings.slice(0, 160)}{findings.length > 160 ? "…" : ""}", recorded by {by}. The notice is then due by fourteen days later.</p>}>Record the decision</Confirm>
          )}
          {error && <p className="notice notice-error">{error}</p>}
          {h.decision && <p className="muted">Recorded {h.decision.recorded.slice(0, 10)} by {h.decision.by}; notice due by <strong>{h.decision.noticeDueBy}</strong>.</p>}
        </Card>
        <Card title="The decision notice, as it would read">
          {h.decision ? <NoticePreview h={h} /> : <p className="muted">Record the decision and the notice previews here from the decision-notice template.</p>}
        </Card>
      </div>
    </div>
  );
}

const cols: Column<Hearing>[] = [
  { key: "start", header: "Hearing", render: (h) => <>{h.start.slice(0, 16).replace("T", " ")}{h.scheduled ? <> <Badge tone="good">zoom</Badge></> : <> <Badge>no meeting</Badge></>}</> },
  { key: "address", header: "Unit" },
  { key: "noticeBy", header: "Notice by (5855(a))", render: (h) => <>{h.noticeOn ? <Badge tone="good">{`delivered ${h.noticeOn}`}</Badge> : <DueDate iso={h.noticeBy} />}</>, value: (h) => h.noticeBy },
  { key: "decision", header: "Decision", render: (h) => h.decision ? <><Pill word="done" /> <span className="muted">notice due {h.decision.noticeDueBy}</span></> : <Pill word="open" />, value: (h) => h.decision ? 1 : 0 },
  { key: "standing", header: "Where it stands" },
  { key: "problems", header: "Problems", render: (h) => <Findings items={h.problems ?? []} empty="none" />, value: (h) => h.problems?.length ?? 0 },
];

/** The disciplinary hearings a person planned, against the 5855 clocks, with the board's decision recorded once and the notice from the template. */
export function HearingsView() {
  const r = useApi<Hearings>("/api/hearings");
  const [open, setOpen] = useState("");
  const [patched, setPatched] = useState<Record<string, Hearing>>({});
  const today = new Date();
  return (
    <RemoteView r={r}>
      {(raw) => {
        const rows = [...raw.hearings].map((h) => patched[h.key] ?? h).sort((a, b) => b.start.localeCompare(a.start));
        const current = rows.find((h) => h.key === open);
        return (
          <div className="stack">
            <p className="notice notice-warn">Confidential: for directors. A hearing needs the notice ten days ahead and the written decision within fourteen days of the board's action. jason schedules a meeting only when a person runs the command, never sends the notice, and never decides discipline.</p>
            <Card title={`Hearings (${rows.length})`}>
              <DataTable rows={rows} columns={[...cols, { key: "open", header: "", render: (h) => <button className={open === h.key ? "" : "primary"} onClick={() => setOpen(open === h.key ? "" : h.key)}>{open === h.key ? "Close" : "Open"}</button> }]} searchable={false} />
            </Card>
            {current && <HearingPanel key={current.key + (current.decision?.recorded ?? "")} h={current} today={today} onSaved={(n) => setPatched((p) => ({ ...p, [n.key]: n }))} />}
          </div>
        );
      }}
    </RemoteView>
  );
}
