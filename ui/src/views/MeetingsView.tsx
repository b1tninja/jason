import { useState } from "react";
import { Badge, Card, Caveats, DataTable, DocList, Findings, RemoteView, type Audience, type Column, type DocRef } from "../components";
import { useApi } from "../lib/useApi";
import type { Meeting, Meetings } from "./types";

const KINDS = ["agenda", "notice", "minutes", "transcript", "recording", "summary", "chat", "attendance"];

/** One meeting's documents as `GET /api/meetings?date=` answers them (`jason.web.extra.meeting_docs.record_refs`):
 * references grouped by the catalog's record kind, each group's posted copy first. */
export interface MeetingDocGroup { kind: string; docs: DocRef[] }
interface OneMeeting { found?: boolean; note?: string; date: string; docs?: MeetingDocGroup[] }

/** "meeting notice" → "Meeting notice". */
const heading = (kind: string) => kind.charAt(0).toUpperCase() + kind.slice(1);

function Has({ has }: { has: Meeting["has"] }) {
  return (
    <span className="row wrap">
      {KINDS.filter((k) => Object.keys(has).some((h) => h.startsWith(k))).map((k) => {
        const key = Object.keys(has).find((h) => h.startsWith(k))!;
        const where = Object.entries(has[key]).map(([w, n]) => `${w} ${n}`).join(", ");
        return <span key={k} title={where}><Badge tone="good">{k}</Badge></span>;
      })}
      {!Object.keys(has).some((h) => h.startsWith("minutes")) && <Badge tone="warn">no minutes</Badge>}
    </span>
  );
}

/** One meeting's documents, a row list per record kind (notice, agendas, minutes, transcript, recordings). A record jason
 * cannot open yet (Zoom's cloud, a Gmail message, PayHOA's mailing log) stays a badge in the table above. */
export function MeetingDocs({ date, owner = false }: { date: string; owner?: boolean }) {
  const r = useApi<OneMeeting>(`/api/meetings?date=${encodeURIComponent(date)}${owner ? "&view=owner" : ""}`);
  return (
    <Card title={`Records of ${date}`}>
      <RemoteView r={r}>
        {(d) => d.found === false
          ? <p className="muted">{d.note ?? `No records on ${date}.`}</p>
          : !(d.docs ?? []).length
            ? <p className="muted">No record of this meeting is a document jason keeps or reads (Drive, the PayHOA library, or a copy on disk).</p>
            : (
              <div className="stack">
                {(d.docs ?? []).map((g) => <DocList key={g.kind} docs={g.docs} variant="row" level={3} title={`${heading(g.kind)} (${g.docs.length})`} />)}
              </div>
            )}
      </RemoteView>
    </Card>
  );
}

const cols: Column<Meeting>[] = [
  { key: "date", header: "Meeting" },
  { key: "titles", header: "Titles", value: (r) => r.titles.join("; ") },
  { key: "has", header: "Records on hand", render: (r) => <Has has={r.has} />, value: (r) => Object.keys(r.has).length },
  { key: "checks", header: "Checks", render: (r) => <Findings items={r.checks} empty="none" />, value: (r) => r.checks.length },
];

/** Every meeting's records and checks (minutes 30 days on, a recording held after the minutes, a transcript into executive session).
 * The owner view (`audience="owner"`) reads `GET /api/meetings?view=owner`: each meeting's open-session records on file
 * (the notice, the agendas, the minutes), with no titles, checks, or schedule gaps, which are the board's. */
export function MeetingsView({ audience = "board" }: { audience?: Audience } = {}) {
  const owner = audience === "owner";
  const r = useApi<Meetings>(owner ? "/api/meetings?view=owner" : "/api/meetings");
  const [flagged, setFlagged] = useState(false);
  const [open, setOpen] = useState("");
  return (
    <RemoteView r={r}>
      {(d) => {
        const rows = [...d.meetings].sort((a, b) => b.date.localeCompare(a.date)).filter((m) => !flagged || m.checks.length);
        const records: Column<Meeting> = { key: "records", header: "", render: (m) => (
          <button type="button" className={open === m.date ? "" : "primary"} aria-expanded={open === m.date} aria-label={`${open === m.date ? "Close" : "Show"} the records of ${m.date}`}
            onClick={() => setOpen(open === m.date ? "" : m.date)}>{open === m.date ? "Close" : "Records"}</button>
        ) };
        const shown = owner ? cols.filter((c) => c.key === "date" || c.key === "has") : cols;
        return (
          <div className="stack">
            <Card title={`Meetings (${d.meetings.length})`} actions={owner ? undefined : <label><input type="checkbox" checked={flagged} onChange={(e) => setFlagged(e.target.checked)} /> only with checks</label>}>
              <DataTable rows={rows} columns={[...shown, records]} />
            </Card>
            {open && <MeetingDocs key={open} date={open} owner={owner} />}
            {!owner && !!d.scheduleGaps?.length && (
              <Card title={`Scheduled days with no record (${d.scheduleGaps.length})`}>
                <p className="row wrap">{d.scheduleGaps.map((g) => <Badge key={g} tone="warn">{g}</Badge>)}</p>
              </Card>
            )}
            <Caveats items={d.caveats} />
          </div>
        );
      }}
    </RemoteView>
  );
}
