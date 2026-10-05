import { useState } from "react";
import { Badge, Card, Caveats, Command, DataTable, DecisionCard, Doc, DocumentPreview, DueDate, Embed, EvidenceVersion, Markdown, Pill, ReadAllFromDrive, RemoteView, Stat, Tabs, attachedCopies, type Column, type DecisionDraft, type DocRef } from "../components";
import type { DriveFile } from "../components/DriveAttach";
import { postJson } from "../lib/api";
import { fileDocRef } from "../lib/docref";
import { useApi } from "../lib/useApi";
import type { BoardItem } from "./types";

/** One agenda item's packet files, as the plan for the meeting keeps them (`GET /api/agenda-plan`'s `candidates`). */
export interface PacketItem { id: string; title: string; include?: boolean; session?: string; packet: DriveFile[] }

/** The meeting's packet files, item by item, each as jason's copy (`DocumentPreview`: a thumbnail, Preview, Read from
 * Drive, Open in Google), and "Read every packet file from Drive" for the Drive files among them: one sign-in, a
 * person's click, never on load. Items not on the agenda and items with no file are left out. */
export function PacketFiles({ items }: { items: PacketItem[] }) {
  const [version, setVersion] = useState(0);
  const shown = items.filter((i) => i.include !== false && (i.packet ?? []).length > 0);
  if (!shown.length) return <p className="muted">No packet files are attached to the items on the agenda. Attach them in Plan a meeting.</p>;
  const driveIds = shown.flatMap((i) => i.packet.map((f) => attachedCopies(f).driveId)).filter(Boolean);
  return (
    <div className="stack">
      <ReadAllFromDrive driveIds={driveIds} what="packet file" batch="packet" onDone={() => setVersion((v) => v + 1)} />
      <EvidenceVersion.Provider value={version}>
        {shown.map((i) => (
          <section key={i.id} aria-label={`Packet files for ${i.title}`}>
            <h4>{i.title}{i.session === "executive session" && <> <Badge tone="warn">executive session</Badge></>}</h4>
            <ul className="packet-previews">
              {i.packet.map((f) => {
                const c = attachedCopies(f);
                return (
                  <li key={f.id}>
                    <span className="packet-previews-name"><Badge>{f.kind || "file"}</Badge><span>{f.name}</span></span>
                    <DocumentPreview name={f.name} driveId={c.driveId} kind={c.kind} path={c.path} recordedLabel="File on disk" />
                  </li>
                );
              })}
            </ul>
          </section>
        ))}
      </EvidenceVersion.Provider>
    </div>
  );
}

function MeetingPacketFiles({ date }: { date: string }) {
  const r = useApi<{ found?: boolean; note?: string; candidates?: PacketItem[] }>(`/api/agenda-plan?date=${encodeURIComponent(date)}`);
  return (
    <Card title="Packet files">
      <RemoteView r={r}>
        {(p) => (p.found === false ? <p className="muted">{p.note ?? "No plan for this meeting."}</p> : <PacketFiles items={p.candidates ?? []} />)}
      </RemoteView>
    </Card>
  );
}

/** An item as the loader gives it. Outside the private view an executive one is `held`: no title, ask, or id, only its
 * Civil Code 4935 subject (`subject`, in the statute's words `general`; 4935(e)). */
type Row = BoardItem & { agendaSession: string; held?: boolean; subject?: string; general?: string };
interface Decision extends DecisionDraft { id: string; meeting: string; item: string; session: string; recorded: string; updated: string; history: string[]; tally: Record<string, number>; suggested: string }
interface Meeting {
  found?: boolean; note?: string; date: string; today: string; noticeBy: string; executiveNoticeBy: string; items: Row[]; openCount: number; executiveCount: number;
  executiveHeld?: number; executiveHeldNote?: string;
  directors: string[]; decisions: Decision[];
  agendaMarkdown: string; packetMarkdown: string; minutesTemplate: string; notes: string[];
  commands: { agendaDoc: string; packetDoc: string; minutesDraft: string; notice: string }; caveats?: string[];
}

/** A recording's file as `/api/embeds` lists it, with its reference (`doc`, the server's level) when the loader gives one. */
interface RecordingFile { type: string; name: string; path: string; doc?: DocRef }
interface Recording { date: string; topic: string; uuid: string; shareUrl: string; playUrl: string; files: RecordingFile[] }
interface Embeds { found: boolean; note?: string; calendarId: string; timeZone: string; recordings: Recording[] }

const isAudioFile = (f: { type: string; name: string }) => f.type === "audio" || /\.(m4a|mp3|wav|ogg)$/i.test(f.name);

/** A recording file's reference: the loader's, else one built from its path (no level: the server decides it, and the
 * player waits for "Show the document"). */
const audioRef = (f: RecordingFile, topic: string): DocRef =>
  f.doc ?? { ...fileDocRef(f.path, f.name || `${topic} (audio)`), kind: "audio" };

/** The Sunday-to-Saturday week holding an ISO date, as Google's `dates=` range (`YYYYMMDD/YYYYMMDD`). */
export function weekOf(iso: string): string {
  const d = new Date(iso + "T12:00:00");
  if (Number.isNaN(d.getTime())) return "";
  const sun = new Date(d); sun.setDate(d.getDate() - d.getDay());
  const sat = new Date(sun); sat.setDate(sun.getDate() + 6);
  const ymd = (x: Date) => `${x.getFullYear()}${String(x.getMonth() + 1).padStart(2, "0")}${String(x.getDate()).padStart(2, "0")}`;
  return `${ymd(sun)}/${ymd(sat)}`;
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
  const embeds = useApi<Embeds>("/api/embeds");
  const em = embeds.status === "ready" && embeds.data.found !== false ? embeds.data : null;
  const [tab, setTab] = useState("agenda");
  const [saved, setSaved] = useState<Record<string, Decision>>({});
  const [busy, setBusy] = useState(false);
  const save = async (meeting: string, item: Row | null, d: DecisionDraft) => {
    setBusy(true);
    try {
      const out = await postJson<Decision>("/api/decisions", { meeting, title: d.title, motion: d.motion, item: item?.id ?? "", session: item?.agendaSession ?? "open session", mover: d.mover, second: d.second, votes: d.votes, recused: d.recused, outcome: d.outcome, by: d.by, notes: d.notes });
      setSaved((s) => ({ ...s, [out.id]: out }));
    } finally {
      setBusy(false);
    }
  };
  return (
    <RemoteView r={r}>
      {(d) => {
        const recording = (em?.recordings ?? []).find((x) => x.date === d.date);
        const week = weekOf(d.date);
        return (
        <div className="stack">
          <div className="row wrap">
            <label>Meeting <input type="date" value={date || d.date} onChange={(e) => setDate(e.target.value)} /></label>
            <span className="muted">the schedule's next meeting unless chosen</span>
          </div>
          {em && em.calendarId && week && (
            <Card title="That week on the calendar">
              <Embed a={{ kind: "calendar", ref: em.calendarId, title: `Association calendar, week of ${d.date}`, opts: { mode: "WEEK", dates: week, tz: em.timeZone } }} height={260} load="mount" />
            </Card>
          )}
          <div className="stats">
            <Stat label="Notice by (open meeting, CIV 4920(a))" value={<DueDate iso={d.noticeBy} today={new Date(d.today + "T12:00:00")} />} />
            <Stat label="Notice by (executive only, 4920(b)(2))" value={<DueDate iso={d.executiveNoticeBy} today={new Date(d.today + "T12:00:00")} />} />
            <Stat label="Open session items" value={d.openCount} />
            <Stat label="Executive session items" value={d.executiveCount} hint="by the 4935 subject on the agenda; CIV 4935(e)" />
          </div>
          <Card title={`Items proposed or on the agenda (${d.items.length})`}>
            <p className="muted">An item is noticed for a meeting with the board's own columns; no action may be taken on one not on the noticed agenda (CIV 4930).</p>
            {d.executiveHeldNote && <p className="notice">{d.executiveHeldNote}</p>}
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
              <div className="stack">
              <MeetingPacketFiles date={d.date} />
              <Card title="Packet">
                <p className="muted">Each item: background, the question for the board, the law quoted, what the records show now, the board's notes with live reports, options, and a draft motion. Executive items by their 4935 subject only; their research goes to the directors separately.</p>
                {d.packetMarkdown ? <div className="preview"><Markdown text={d.packetMarkdown} /></div> : <p className="notice notice-warn">{d.notes.find((n) => n.startsWith("packet")) ?? "No packet for this meeting."}</p>}
                <Command cmd={d.commands.packetDoc} note="Writes the packet as a confidential Doc, private until shared; a Drive write a person confirms." />
              </Card>
              </div>
            ) },
            { id: "decisions", label: `Decisions (${d.decisions.length + Object.keys(saved).length})`, content: (
              <Card title="What the board did">
                <p className="muted">One motion per item, in the board's words: who moved and seconded, each director's vote, and the outcome. jason records the board's decision; it decides nothing. A roll call is kept for every vote (a lien needs one in open session, CIV 5673).</p>
                {d.directors.length === 0 && <p className="notice notice-warn">No directors on file (`jason board --members`); type names into the roll call as you go.</p>}
                {recording && (
                  <div className="stack">
                    {/* Zoom's own page is the original, opened in a new tab with the person's own session; never a frame of it
                        (docs/console/doc-component.md, "No frames of outside hosts"). */}
                    {(recording.shareUrl || recording.playUrl) && (
                      <p><a href={recording.shareUrl || recording.playUrl} target="_blank" rel="noreferrer">Open in Zoom<span className="visually-hidden"> ({recording.topic}, opens in a new tab)</span></a></p>
                    )}
                    {/* The kept audio is a Doc on file:<path>: the viewer's player, from a logged view's short-lived link,
                        at the level the server gives it (P3 for a call that ran into executive session). */}
                    {(recording.files ?? []).filter(isAudioFile).map((f) => <Doc key={f.path} doc={audioRef(f, recording.topic)} variant="inline" headingLevel={4} />)}
                    <p className="muted">A kept recording may be under a litigation hold; the page shows it and deletes nothing.</p>
                  </div>
                )}
                {(d.executiveHeld ?? 0) > 0 && <p className="muted">A decision on an executive matter is recorded in the private view, where its title is shown.</p>}
                {d.items.filter((item) => !item.held).map((item) => {
                  const existing = saved[`${d.date}--${item.id}`] ?? d.decisions.find((x) => x.item === item.id);
                  return <DecisionCard key={item.id + (existing?.updated ?? "")} title={item.title} directors={d.directors} initial={existing ? { ...existing } : { session: item.agendaSession }} busy={busy} onSave={(dd) => save(d.date, item, dd)} />;
                })}
                <DecisionCard key="other" title="Another motion (not on an item)" directors={d.directors} busy={busy} onSave={(dd) => save(d.date, null, { ...dd, title: dd.motion.slice(0, 60) })} />
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
        );
      }}
    </RemoteView>
  );
}
