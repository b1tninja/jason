import { useState } from "react";
import { Badge, Card, Caveats, Command, DataTable, DueDate, Markdown, Pill, RemoteView, Stat, Tabs, type Column } from "../components";
import { useApi } from "../lib/useApi";
import type { BoardItem } from "./types";

type Row = BoardItem & { agendaSession: string };
interface Meeting {
  found?: boolean; note?: string; date: string; today: string; noticeBy: string; executiveNoticeBy: string; items: Row[]; openCount: number; executiveCount: number;
  agendaMarkdown: string; packetMarkdown: string; minutesTemplate: string; notes: string[];
  commands: { agendaDoc: string; packetDoc: string; minutesDraft: string; notice: string }; caveats?: string[];
}

const cols: Column<Row>[] = [
  { key: "agendaSession", header: "Session", render: (r) => <Badge tone={r.agendaSession === "open session" ? "neutral" : "warn"}>{r.agendaSession}</Badge> },
  { key: "priority", header: "Priority", render: (r) => <Pill word={r.priority} /> },
  { key: "title", header: "Item" },
  { key: "ask", header: "The board is asked to" },
  { key: "authority", header: "Authority" },
  { key: "status", header: "Status", render: (r) => <Pill word={r.status} /> },
  { key: "meeting", header: "Noticed for", value: (r) => r.meeting || "" },
];

/** One meeting as the board sees it: notice deadlines, the items by session, then the agenda, the packet, and the minutes frame as drafts. */
export function MeetingView() {
  const [date, setDate] = useState("");
  const r = useApi<Meeting>(`/api/meeting${date ? `?date=${date}` : ""}`);
  const [tab, setTab] = useState("agenda");
  return (
    <RemoteView r={r}>
      {(d) => (
        <div className="stack">
          <div className="row wrap">
            <label>Meeting <input type="date" value={date || d.date} onChange={(e) => setDate(e.target.value)} /></label>
            <span className="muted">the schedule's next meeting unless chosen</span>
          </div>
          <div className="stats">
            <Stat label="Notice by (open meeting, CIV 4920(a))" value={<DueDate iso={d.noticeBy} today={new Date(d.today + "T12:00:00")} />} />
            <Stat label="Notice by (executive only, 4920(b)(2))" value={<DueDate iso={d.executiveNoticeBy} today={new Date(d.today + "T12:00:00")} />} />
            <Stat label="Open session items" value={d.openCount} />
            <Stat label="Executive session items" value={d.executiveCount} hint="listed by title only; CIV 4935" />
          </div>
          <Card title={`Items proposed or on the agenda (${d.items.length})`}>
            <p className="muted">An item is noticed for a meeting with the board's own columns; no action may be taken on one not on the noticed agenda (CIV 4930).</p>
            <DataTable rows={d.items} columns={cols} searchable={false} />
            <Command cmd={d.commands.notice} note="Sets the board's status and meeting on an item; nothing else changes." />
          </Card>
          <Tabs active={tab} onChange={setTab} tabs={[
            { id: "agenda", label: "Agenda draft", content: (
              <Card title="Agenda" actions={<span className="muted">from the items above and last month's Doc</span>}>
                <div className="preview"><Markdown text={d.agendaMarkdown || "_No items proposed or on the agenda._"} /></div>
                <Command cmd={d.commands.agendaDoc} note="Writes the agenda Doc from last month's (its id) with these items; a Drive write a person confirms." />
              </Card>
            ) },
            { id: "packet", label: "Board packet", content: (
              <Card title="Packet">
                <p className="muted">Each item: background, the question for the board, the law quoted, what the records show now, the board's notes with live reports, options, and a draft motion. Executive items by title only.</p>
                {d.packetMarkdown ? <div className="preview"><Markdown text={d.packetMarkdown} /></div> : <p className="notice notice-warn">{d.notes.find((n) => n.startsWith("packet")) ?? "No packet for this meeting."}</p>}
                <Command cmd={d.commands.packetDoc} note="Writes the packet as a confidential Doc, private until shared; a Drive write a person confirms." />
              </Card>
            ) },
            { id: "minutes", label: "Minutes frame", content: (
              <Card title="Minutes frame">
                <p className="muted">The Secretary's frame: each section with its instructions, the business section once per item, and the roll-call tables. After the meeting, the draft from the record fills what it can and leaves blanks.</p>
                {d.minutesTemplate ? <div className="preview"><Markdown text={d.minutesTemplate} /></div> : <p className="notice notice-warn">{d.notes.find((n) => n.startsWith("minutes")) ?? "No frame."}</p>}
                <Command cmd={d.commands.minutesDraft} note="Drafts the minutes from the meeting's record (open portion only) with blanks for the Secretary; a local model, reads disk." />
              </Card>
            ) },
          ]} />
          <Caveats items={d.caveats} />
        </div>
      )}
    </RemoteView>
  );
}
