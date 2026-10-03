import { useState, type ReactNode, type Ref } from "react";
import { Badge } from "./Badge";
import { Command } from "./Command";
import { Confirm } from "./Confirm";
import { DecisionBrief } from "./DecisionBrief";
import { embedUrls, type EmbedKind } from "./Embed";
import { Tabs } from "./Tabs";
import { RollCall, outcome, type Threshold } from "./RollCall";

// -- shapes shared with the loader (GET /api/meeting-room) -------------------------------------------------------------

export interface PacketFile { id?: string; name: string; kind?: string; url?: string; ref?: string; real?: boolean }
export interface DecisionBriefData { question: string; criteria: string[]; options: { label: string; values: string[] }[]; facts?: string[] }
export interface AgendaItem {
  id: string; kind: string; label: string; title: string; facts: string[]; motion: string; threshold: Threshold | string; recused: string[];
  allot: number; packet: PacketFile[]; brief: DecisionBriefData | null; session: string; matters?: string[]; suggestion?: string;
}
export interface MotionTally { aye: number; no: number; abstain: number; recused: number; recusedNames: string[]; voters: string[]; needs: number; answered: boolean; state: "open" | "carries" | "fails"; line: string }
export interface Motion {
  id: string; itemId: string; title: string; text: string; mover: string; second: string; recused: string[]; threshold: Threshold | string;
  votes: Record<string, string>; result: "carried" | "failed" | ""; decidedAt: string; movedAt: string; tally: MotionTally;
}
export interface LogEntry { at: string; title: string; tone?: "neutral" | "good" | "warn" | "bad"; by?: string }
export interface RoomRecord {
  date: string; directors: string[]; current: number; presenter: "jason" | "chair"; view: "host" | "shared"; mode: "co-host" | "host" | "portal";
  attendance: Record<string, "present" | "absent" | "remote">; calledToOrder: string; openForum: { count: number; limitMinutes: number };
  motions: Motion[]; log: LogEntry[]; executive: { active: boolean; startedAt: string; endedAt: string; note: string };
  polls: { at: string; question: string; results: Record<string, number>; note: string }[]; admitted: string[];
  transcriptSuggestions: { at: string; text: string; who?: string; state: "suggested" | "added" | "dismissed" }[];
  adjournedAt: string; present: string[]; quorum: number; history: string[];
}
export interface MeetingRoomData {
  found?: boolean; note?: string; date: string; today: string; directors: string[]; quorum: number; items: AgendaItem[]; room: RoomRecord;
  decisions: unknown[]; plan: { found: boolean; count: number }; roster: { synced: string; count: number; rows: { name: string; unit: string }[]; note: string };
  offAgendaPaths: { path: string; text: string }[]; zoom: { commands: Record<string, string>; admitCommand: string; note: string };
  commands: Record<string, string>; minutesKey: string; notes: string[]; caveats: string[];
}
/** What a person's action sends to POST /api/write/meeting-room/<date>; the view adds `by` and `directors`. Resolves to
 * whether the store took it: a refusal is shown by the view, and a sequence of actions stops at the first one refused. */
export type RoomAction = (action: string, body?: Record<string, unknown>) => Promise<boolean>;

// -- the stage -----------------------------------------------------------------------------------------------------------

export type StageContent =
  | { kind: "facts"; facts: string[] }
  | { kind: "motion"; text: string; mover: string; second: string; heading?: string; result?: string }
  | { kind: "attendance"; rows: { name: string; role?: string; present: boolean }[]; quorum: string }
  | { kind: "countdown"; seconds: number; speaker: string }
  | { kind: "executive"; note: string }
  | { kind: "options"; decision: DecisionBriefData }
  | { kind: "packet"; file: PacketFile }
  | { kind: "adjourned"; at: string }
  | { kind: "off-agenda" };

export interface MeetingStageProps {
  wordmark: string; legal?: string; item: { label: string; title: string }; content?: StageContent | null; caption: ReactNode; progress: number;
  live?: boolean; meta?: string; time?: string; stageRef?: Ref<HTMLDivElement>;
}

const mmss = (sec: number) => `${Math.floor(Math.max(0, sec) / 60)}:${String(Math.max(0, sec) % 60).padStart(2, "0")}`;

// DecisionBrief is another agent's component; the stage passes the data the spec names and tolerates a placeholder.
const Brief = DecisionBrief as unknown as (p: { decision: DecisionBriefData; columns?: boolean }) => JSX.Element;

const FILE_KINDS: Record<string, EmbedKind> = { doc: "doc", docx: "doc", document: "doc", sheet: "sheet", xlsx: "sheet", spreadsheet: "sheet", slides: "slides", presentation: "slides", pdf: "pdf", form: "form", image: "image", drive: "drive", url: "url" };
/** Where a packet file previews, when it is a real file (a URL, a Drive id, or a path under data/); null for a sample. */
export function packetFrame(file: PacketFile): string | null {
  const ref = file.url || file.ref || (file.real ? file.id : "") || "";
  if (!ref) return null;
  const kind = FILE_KINDS[(file.kind ?? "").toLowerCase()] ?? (/^https?:/.test(ref) ? "url" : "drive");
  return embedUrls({ kind, ref, title: file.name }).frame;
}

/** The 16:9 stage: wordmark, item label and title, one content block, jason's caption or the chair's line, and the progress bar.
 * Sized by its container (cqw type, nothing under 1.5cqw), so it fills a Zoom share, an immersive canvas, or a column alike. */
export function MeetingStage({ wordmark, legal, item, content, caption, progress, live, meta = "Board of directors · open meeting", time, stageRef }: MeetingStageProps) {
  const pct = Math.max(0, Math.min(1, progress || 0));
  return (
    <div className="stage" ref={stageRef} role="region" aria-label="Meeting stage" title={legal}>
      <div className="stage-top">
        <span className="stage-wordmark">{wordmark}</span>
        <span className="stage-meta">{meta}{live && <span className="stage-live">live</span>}</span>
        <span className="stage-time">{time ?? ""}</span>
      </div>
      <div className="stage-body">
        <p className="stage-label">{item.label}</p>
        <h2 className="stage-title">{item.title}</h2>
        {content && <StageBlock content={content} />}
      </div>
      <div className="stage-foot">
        <div className="stage-caption">{caption}</div>
        <div className="stage-progress" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(pct * 100)}>
          <span style={{ width: `${pct * 100}%` }} />
        </div>
      </div>
    </div>
  );
}

function StageBlock({ content }: { content: StageContent }) {
  switch (content.kind) {
    case "facts":
      return content.facts.length ? <ul className="stage-facts">{content.facts.map((f, i) => <li key={i}>{f}</li>)}</ul> : null;
    case "motion":
      return (
        <div className="stage-box">
          <span className="stage-kicker">{content.heading ?? (content.result ? "Motion" : content.mover ? "Motion on the floor" : "Proposed motion")}</span>
          <p className="stage-motion">{content.text}</p>
          <span className="stage-byline">{content.mover ? `Moved by ${content.mover}, seconded by ${content.second}` : "Not yet moved"}</span>
          {content.result && <p className="stage-result">{content.result}</p>}
        </div>
      );
    case "attendance":
      return (
        <>
          <div className="stage-roster">
            {content.rows.map((r) => (
              <div key={r.name} className="stage-director"><span className={r.present ? "stage-dot" : "stage-dot stage-dot-off"} />{r.name}{r.role && <span className="stage-role">{r.role}</span>}</div>
            ))}
          </div>
          <p className="stage-quorum">{content.quorum}</p>
        </>
      );
    case "countdown":
      return (
        <>
          <div className="stage-clock">{mmss(content.seconds)}</div>
          <p className="stage-sub">{content.speaker}</p>
        </>
      );
    case "executive":
      return (
        <>
          <p className="stage-motion">{content.note}</p>
          <p className="stage-sub">Members may not attend (CIV 4935). These matters are noted generally in the next open meeting's minutes.</p>
        </>
      );
    case "options":
      return <div className="stage-options"><Brief decision={content.decision} columns /></div>;
    case "packet": {
      const src = packetFrame(content.file);
      return src
        ? <iframe className="stage-doc" src={src} title={content.file.name} />
        : <div className="stage-doc stage-doc-sample"><span>document preview<br />{content.file.name}</span></div>;
    }
    case "adjourned":
      return (
        <>
          <p className="stage-motion">Open meeting adjourned{content.at ? ` at ${content.at}` : ""}.</p>
          <p className="stage-sub">Draft minutes go to members within 30 days (CIV 4950).</p>
        </>
      );
    case "off-agenda":
      return <div className="stage-box stage-box-warn">Not on the posted agenda. The board may respond briefly, ask staff to report back, or place it on a future agenda (CIV 4930).</div>;
    default:
      return null;
  }
}

// -- the host panel ----------------------------------------------------------------------------------------------------

/** Common motions, as templates a person edits. The brackets are blanks; the text is the board's once moved. */
export const COMMON_MOTIONS: { id: string; label: string; threshold: Threshold; cite?: string; note?: string; text: string }[] = [
  { id: "approve-minutes", label: "Approve the minutes", threshold: "majority", text: "Move to approve the minutes of the [date] open meeting as presented." },
  { id: "approve-contract", label: "Approve a contract", threshold: "majority", cite: "Corp. Code 7233; CIV 5350", note: "An interested director may not vote; the vote must carry without them.", text: "Move to approve the contract with [vendor] for [scope] at [amount], and authorize [officer] to sign." },
  { id: "adopt-resolution", label: "Adopt a resolution", threshold: "majority", text: "Move to adopt the resolution as presented." },
  { id: "continue", label: "Continue to a later meeting", threshold: "majority", cite: "CIV 4930(d)(3)", note: "Within 30 days, the next meeting may act without re-noticing the item.", text: "Move to continue this item to the [date] meeting." },
  { id: "refer", label: "Direct the manager to report back", threshold: "majority", cite: "CIV 4930(c)", text: "Move to direct the manager to report back on [matter] at the [date] meeting." },
  { id: "table", label: "Table the item", threshold: "majority", text: "Move to table this item." },
  { id: "exec", label: "Adjourn to executive session", threshold: "majority", cite: "CIV 4935(a)", text: "Move to adjourn to executive session to discuss [general description]." },
  { id: "emergency", label: "Act on an item not on the agenda", threshold: "two-thirds", cite: "CIV 4930(d)(2), (e)", note: "Identify the item to members first. Two-thirds of directors present, or every director present if fewer than two-thirds of the board is here.", text: "Move to find that [matter] needs immediate action and came to the board's attention after the agenda was posted." },
  { id: "adjourn", label: "Adjourn", threshold: "majority", text: "Move to adjourn." },
];

/** The five ways a board may take up a topic not on the posted agenda (CIV 4930), as the guard offers them. */
export const OFF_AGENDA_LABELS: Record<string, string> = {
  b: "Respond briefly, ask a question, or announce (CIV 4930(b))",
  c: "Ask staff to report back, or place it on a future agenda (CIV 4930(c))",
  d1: "A majority finds an emergency (CIV 4930(d)(1))",
  d2: "Two-thirds find an immediate need that arose after posting (CIV 4930(d)(2))",
  d3: "It was on an agenda within 30 days and was continued (CIV 4930(d)(3))",
};

export interface MinutesLetter { key: string; kind: string; title: string; date: string; to: string; via: string; body: string[]; signoff: string; approver: string; sentCommand: string }

export interface HostPanelProps {
  room: MeetingRoomData;
  onAction: RoomAction;
  busy?: boolean;
  /** The signed-in person, who every entry is recorded as. */
  me: string;
  /** What the stage shows beside the item: the options view, or one packet file. */
  shown?: { options?: boolean; packet?: PacketFile | null };
  onShow?: (shown: { options?: boolean; packet?: PacketFile | null }) => void;
  /** Open forum: the speaker clock lives in the view (it drives the stage); the panel's buttons steer it. */
  forum?: { running: boolean; left: number; speakers: number; onToggle: () => void; onReset: () => void; onNextSpeaker: () => void };
  /** Builds the draft minutes for Approvals (the secretary approves). Resolves to an error message, or nothing. */
  onMinutes?: (letter: MinutesLetter) => Promise<string | void>;
  /** The wordmark's legal name, for the minutes' sign-off. */
  legal?: string;
}

const hhmm = (iso: string) => (iso ? new Date(iso).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) : "");

export function motionFor(room: RoomRecord, item: AgendaItem | undefined): Motion | undefined {
  if (!item) return undefined;
  const mine = room.motions.filter((m) => m.itemId === item.id);
  return mine.find((m) => !m.result) ?? mine[mine.length - 1];
}

/** The minutes as the room recorded them: the roster and the quorum, then each logged line with its time, then the executive note. */
export function minutesLetter(data: MeetingRoomData, legal: string): MinutesLetter {
  const r = data.room;
  const absent = r.directors.filter((n) => !r.present.includes(n));
  const roster = `Present: ${r.present.join(", ") || "none recorded"}.${absent.length ? ` Absent: ${absent.join(", ")}.` : ""}`;
  const exec = data.items.find((i) => i.kind === "exec");
  return {
    key: data.minutesKey, kind: "Draft minutes", title: `Minutes of the open meeting of the board, ${data.date} (draft)`, date: data.date,
    to: "Board, for approval at the next meeting; members on request (CIV 4950)", via: "Drive and the members' portal", approver: "the secretary",
    signoff: `Secretary, ${legal}`, sentCommand: data.commands.minutesDraft ?? "",
    body: [`Open meeting of the board of directors, ${data.date}. ${roster} A quorum is ${data.quorum} directors.`]
      .concat(r.log.map((l) => `${hhmm(l.at)}. ${l.title}`))
      .concat(exec?.matters?.length ? [`The board met in executive session to discuss ${exec.matters.join(" and ")} (Civil Code 4935(e)).`] : []),
  };
}

/** The host's side of the room: six tabs that read the loader's data and send each change through `onAction`, behind `Confirm`. */
export function HostPanel({ room: data, onAction, busy, me, shown = {}, onShow, forum, onMinutes, legal = "the association" }: HostPanelProps) {
  const [tab, setTab] = useState("agenda");
  const r = data.room;
  const item = data.items[Math.min(r.current, data.items.length - 1)];
  const canWrite = !busy && !!me.trim();
  const needName = !me.trim() && <p className="notice notice-warn">Enter who is recording (above) before making an entry.</p>;
  return (
    <aside className="hostpanel" aria-label="Host panel">
      <Tabs active={tab} onChange={setTab} tabs={[
        { id: "agenda", label: "Agenda", content: <AgendaTab data={data} item={item} onAction={onAction} canWrite={canWrite} shown={shown} onShow={onShow} forum={forum} onMotion={() => setTab("motion")} /> },
        { id: "motion", label: "Motion", content: <MotionTab key={item?.id} data={data} item={item} onAction={onAction} canWrite={canWrite} onFloor={() => setTab("roll")} /> },
        { id: "roll", label: "Roll call", content: <RollTab key={`${item?.id}:${motionFor(r, item)?.id ?? ""}`} data={data} item={item} onAction={onAction} canWrite={canWrite} /> },
        { id: "packet", label: "Packet", content: <PacketTab item={item} shown={shown} onShow={onShow} /> },
        { id: "minutes", label: "Minutes", content: <MinutesTab data={data} onAction={onAction} canWrite={canWrite} onMinutes={onMinutes} legal={legal} /> },
        { id: "zoom", label: "Zoom", content: <ZoomTab data={data} item={item} onAction={onAction} canWrite={canWrite} /> },
      ]} />
      {needName}
    </aside>
  );
}

type TabProps = { data: MeetingRoomData; item: AgendaItem | undefined; onAction: RoomAction; canWrite: boolean };

function AgendaTab({ data, item, onAction, canWrite, shown, onShow, forum, onMotion }: TabProps & Pick<HostPanelProps, "shown" | "onShow" | "forum"> & { onMotion: () => void }) {
  const [guard, setGuard] = useState(false);
  const [topic, setTopic] = useState("");
  const [pick, setPick] = useState<number | null>(null);
  const r = data.room;
  const resultOf = (it: AgendaItem) => motionFor(r, it)?.result;
  const picked = pick !== null && pick !== r.current ? data.items[pick] : undefined;
  return (
    <div className="hp-stack">
      {item?.kind === "forum" && forum && (
        <div className="row wrap">
          <button className="primary" onClick={forum.onToggle}>{forum.running ? "Pause" : "Start"}</button>
          <button onClick={forum.onReset}>Reset</button>
          <button onClick={forum.onNextSpeaker}>Next speaker</button>
          <span className="muted">{forum.speakers} {forum.speakers === 1 ? "speaker" : "speakers"} · {r.openForum.limitMinutes} min each</span>
        </div>
      )}
      <ol className="hp-agenda">
        {data.items.map((it, i) => (
          <li key={it.id} aria-current={i === r.current ? "step" : undefined}>
            <span className="hp-time">{it.allot ? `${it.allot} min` : ""}</span>
            {i === r.current ? <strong>{it.title}</strong> : <button className="link hp-jump" aria-pressed={pick === i} onClick={() => setPick(i)}>{it.title}</button>}
            <span>{resultOf(it) && <Badge tone={resultOf(it) === "carried" ? "good" : "bad"}>{resultOf(it)!}</Badge>}</span>
          </li>
        ))}
      </ol>
      {picked && (
        <Confirm busy={!canWrite} onConfirm={async () => { await onAction("go_to", { item: pick, title: picked.title }); setPick(null); }} summary={<p>Open "{picked.title}" on the stage. Logged in the minutes as opened.</p>}>
          Open "{picked.title}"
        </Confirm>
      )}
      {item?.brief && onShow && (
        shown?.options
          ? <button onClick={() => onShow({ options: false })}>Back to the item</button>
          : <button onClick={() => onShow({ options: true, packet: null })}>Show the options on stage</button>
      )}
      {!guard && <button onClick={() => setGuard(true)}>A topic not on the agenda</button>}
      {guard && (
        <div className="hp-guard" role="group" aria-label="Off-agenda guard">
          <p>Not on the posted agenda (CIV 4930). The board may only:</p>
          <label className="hp-field">Topic, for the log <input value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="the pool gate" /></label>
          {data.offAgendaPaths.map((p) => (
            <Confirm key={p.path} busy={!canWrite} onConfirm={async () => { if (!(await onAction("off_agenda", { path: p.path, topic }))) return; setGuard(false); if (p.path === "d2") onMotion(); }}
              summary={<p>Log in the minutes: {topic ? `"${topic}". ` : ""}{p.text}{p.path.startsWith("d") ? " The board identifies the item to members first (CIV 4930(e))." : ""}</p>}>
              {OFF_AGENDA_LABELS[p.path] ?? p.text}
            </Confirm>
          ))}
          <button className="link" onClick={() => setGuard(false)}>Dismiss</button>
        </div>
      )}
    </div>
  );
}

function MotionTab({ data, item, onAction, canWrite, onFloor }: TabProps & { onFloor: () => void }) {
  const r = data.room;
  const current = motionFor(r, item);
  const defaultTpl = item?.kind === "exec" ? "exec" : item?.kind === "adjourn" ? "adjourn" : item?.kind === "consent" ? "approve-minutes" : item?.kind === "discussion" ? "continue" : "adopt-resolution";
  const [tpl, setTpl] = useState(defaultTpl);
  const [text, setText] = useState(item?.motion || COMMON_MOTIONS.find((m) => m.id === defaultTpl)?.text || "");
  const [mover, setMover] = useState("");
  const [second, setSecond] = useState("");
  const [recused, setRecused] = useState<string[]>(item?.recused ?? []);   // the panel keys this tab by item, so a new item resets the draft
  if (!item || item.kind === "call" || item.kind === "forum") {
    return <p className="muted">{item?.kind === "call" ? "Take attendance in Roll call. The board has no motion during the call to order." : "The board takes no action during open forum (CIV 4930(a))."}</p>;
  }
  if (current && !current.result) return <p>On the floor: "{current.text}" moved by {current.mover}, seconded by {current.second}. <button className="link" onClick={onFloor}>Vote in Roll call</button></p>;
  const tplObj = COMMON_MOTIONS.find((m) => m.id === tpl) ?? COMMON_MOTIONS[0];
  const threshold: Threshold = tplObj.threshold;
  const here = r.present;
  const movers = here.filter((n) => !recused.includes(n));
  const quorumOk = here.length >= data.quorum && data.quorum > 0;
  const ready = !!mover && !!second && mover !== second && quorumOk && text.trim().length > 0;
  return (
    <div className="hp-stack">
      {current?.result && <p className="muted">Decided: {current.result}, {current.tally.aye}–{current.tally.no}–{current.tally.abstain}. A new motion is a new vote.</p>}
      <div className="wrap row" role="group" aria-label="Common motions">
        {COMMON_MOTIONS.map((m) => <button key={m.id} className="hp-chip" aria-pressed={tpl === m.id} onClick={() => { setTpl(m.id); setText(m.id === defaultTpl && item.motion ? item.motion : m.text); }}>{m.label}</button>)}
      </div>
      {(tplObj.note || tplObj.cite) && <p className="muted">{[tplObj.note, tplObj.cite].filter(Boolean).join(" ")}</p>}
      <label className="hp-field">Motion <textarea rows={4} value={text} onChange={(e) => setText(e.target.value)} /></label>
      <div className="grid-2 hp-grid">
        <label className="hp-field">Moved by <select value={mover} onChange={(e) => setMover(e.target.value)}><option value="">choose</option>{movers.map((n) => <option key={n}>{n}</option>)}</select></label>
        <label className="hp-field">Seconded by <select value={second} onChange={(e) => setSecond(e.target.value)}><option value="">choose</option>{movers.map((n) => <option key={n}>{n}</option>)}</select></label>
      </div>
      <fieldset className="hp-recuse"><legend className="muted">Recused (disclosed an interest; counts toward the quorum, not the vote)</legend>
        {here.map((n) => <label key={n}><input type="checkbox" checked={recused.includes(n)} onChange={(e) => setRecused(e.target.checked ? [...recused, n] : recused.filter((x) => x !== n))} /> {n}</label>)}
      </fieldset>
      <div className="row wrap">
        {ready ? (
          <Confirm busy={!canWrite} onConfirm={async () => { if (await onAction("motion_draft", { itemId: item.id, title: item.title, text: text.trim(), mover, second, recused, threshold })) onFloor(); }}
            summary={<p>Put on the floor: "{text.trim()}" moved by {mover}, seconded by {second}{recused.length ? `; ${recused.join(", ")} recused` : ""}. Threshold: {threshold}. {here.length} of {r.directors.length} directors present, quorum {data.quorum}. Logged in the minutes.</p>}>
            Put the motion on the floor
          </Confirm>
        ) : <span className="muted">{!quorumOk ? `No quorum: ${here.length} present, ${data.quorum} needed. Take attendance in Roll call.` : "Choose two different directors: one moves, one seconds."}</span>}
      </div>
    </div>
  );
}

function RollTab({ data, item, onAction, canWrite }: TabProps) {
  const r = data.room;
  const [att, setAtt] = useState<Record<string, string>>({});
  const [votes, setVotes] = useState<Record<string, string>>({});
  const stateOf = (n: string) => att[n] ?? r.attendance[n] ?? "absent";
  const changes = r.directors.filter((n) => att[n] && att[n] !== (r.attendance[n] ?? "absent"));
  const current = motionFor(r, item);
  const open = current && !current.result ? current : null;
  const here = r.present;
  const quorumOk = here.length >= data.quorum && data.quorum > 0;
  const result = open ? outcome(votes, { present: here, recused: open.recused, threshold: open.threshold as Threshold, seats: r.directors.length }) : null;
  return (
    <div className="hp-stack">
      {r.directors.length === 0 && <p className="notice notice-warn">No directors on file (jason board --members).</p>}
      <div className="hp-attendance">
        {r.directors.map((n) => (
          <label key={n}><span>{n}</span>
            <select aria-label={`${n} attendance`} value={stateOf(n)} onChange={(e) => setAtt({ ...att, [n]: e.target.value })}>
              <option value="present">present</option><option value="remote">remote</option><option value="absent">absent</option>
            </select>
          </label>
        ))}
      </div>
      <div className="row wrap">
        <Badge tone={quorumOk ? "good" : "bad"}>{quorumOk ? `quorum, ${here.length} of ${r.directors.length}` : `no quorum, ${here.length} of ${r.directors.length}`}</Badge>
        <span className="muted">A quorum is {data.quorum}.</span>
        {changes.length > 0 && (
          <Confirm busy={!canWrite} onConfirm={async () => { await onAction("attendance", { attendance: Object.fromEntries(changes.map((n) => [n, att[n]])) }); setAtt({}); }}
            summary={<ul>{changes.map((n) => <li key={n}>{n}: {r.attendance[n] ?? "absent"} → {att[n]}</li>)}</ul>}>
            Record attendance
          </Confirm>
        )}
      </div>
      {!open && <p className="muted">No motion on the floor.</p>}
      {open && result && (
        <div className="hp-vote">
          <p className="muted">{open.threshold === "two-thirds"
            ? `Roll call. Needs two-thirds of the directors present (${result.needs} yes), or every one of them if fewer than two-thirds of the board is here (CIV 4930(d)(2)).`
            : `Roll call. Needs a majority of the directors present: ${result.needs} yes.`}</p>
          <RollCall directors={here} votes={votes} onChange={setVotes} present={here} recused={open.recused} threshold={open.threshold as Threshold} seats={r.directors.length} />
          {open.recused.length > 0 && <p className="limit">{open.recused.join(", ")} disclosed an interest and does not vote (Corp. Code 7233; CIV 5350). Still counts toward the quorum.</p>}
          {result.answered ? (
            <Confirm busy={!canWrite} onConfirm={async () => { for (const n of result.voters) if (!(await onAction("vote", { motion: open.id, name: n, vote: votes[n] }))) return; if (await onAction("decide", { motion: open.id })) setVotes({}); }}
              summary={<p>Record the roll call in the minutes and the decisions: {result.voters.map((n) => `${n} ${votes[n]}`).join(", ")}. {result.line} Threshold: {open.threshold}.</p>}>
              Record the vote
            </Confirm>
          ) : <span className="muted">Each director present answers aye, no, or abstain, by name.</span>}
        </div>
      )}
    </div>
  );
}

function PacketTab({ item, shown, onShow }: { item: AgendaItem | undefined } & Pick<HostPanelProps, "shown" | "onShow">) {
  const files = item?.packet ?? [];
  if (!files.length) return <p className="muted">Nothing attached to this item. Attach files in Plan a meeting.</p>;
  return (
    <ul className="hp-files">
      {files.map((f, i) => {
        const on = shown?.packet && (shown.packet.id ?? shown.packet.name) === (f.id ?? f.name);
        const frame = packetFrame(f);
        return (
          <li key={f.id ?? i}>
            <span className="hp-file"><Badge>{(f.kind || "file").toLowerCase()}</Badge><span className="hp-filename">{f.name}</span></span>
            <span className="row">
              {frame && <a href={frame} target="_blank" rel="noreferrer">open</a>}
              {onShow && (on ? <button className="link" onClick={() => onShow({ packet: null })}>Hide</button> : <button className="link" onClick={() => onShow({ packet: f, options: false })}>Show on stage</button>)}
            </span>
          </li>
        );
      })}
    </ul>
  );
}

function MinutesTab({ data, onAction, canWrite, onMinutes, legal }: Omit<TabProps, "item"> & Pick<HostPanelProps, "onMinutes"> & { legal: string }) {
  const r = data.room;
  const [line, setLine] = useState("");
  const [who, setWho] = useState("");
  const [status, setStatus] = useState<{ ok?: boolean; text: string } | null>(null);
  const suggestions = r.transcriptSuggestions.map((s, i) => ({ ...s, i })).filter((s) => s.state === "suggested");
  return (
    <div className="hp-stack">
      {r.log.length ? (
        <ol className="hp-log">{r.log.map((l, i) => <li key={i} className={l.tone ? `hp-log-${l.tone}` : undefined}><span className="hp-time">{hhmm(l.at)}</span><span>{l.title}</span></li>)}</ol>
      ) : <p className="muted">jason records the call to order, motions, votes, and adjournment as they happen.</p>}
      <div className="hp-section">
        <div className="row wrap"><span className="muted">Suggested from the transcript</span><Badge tone="warn">leads, not minutes</Badge></div>
        {suggestions.length === 0 && <p className="muted">Nothing new. Transcript lines are leads for the secretary, not minutes.</p>}
        {suggestions.map((s) => (
          <div key={s.i} className="hp-suggestion">
            {s.who && <span className="muted">{s.who}</span>}
            <span>{s.text}</span>
            <span className="row">
              <Confirm busy={!canWrite} onConfirm={() => onAction("suggestion_state", { index: s.i, state: "added" })} summary={<p>Add to the minutes' log, marked as from the transcript and checked by the secretary: "{s.text}"</p>}>Add to minutes</Confirm>
              <Confirm busy={!canWrite} onConfirm={() => onAction("suggestion_state", { index: s.i, state: "dismissed" })} summary={<p>Dismiss this line. It stays in the room record as dismissed.</p>}>Dismiss</Confirm>
            </span>
          </div>
        ))}
        <div className="hp-grid grid-2">
          <label className="hp-field">Who said it <input value={who} onChange={(e) => setWho(e.target.value)} placeholder="a member, unit 7" /></label>
          <label className="hp-field">Transcript line <input value={line} onChange={(e) => setLine(e.target.value)} /></label>
        </div>
        {line.trim() && <Confirm busy={!canWrite} onConfirm={async () => { await onAction("suggest", { who: who.trim(), text: line.trim() }); setLine(""); }} summary={<p>Keep as a suggestion for the secretary: "{line.trim()}". It is not in the minutes until added.</p>}>Suggest for the minutes</Confirm>}
      </div>
      <div className="hp-section">
        {onMinutes && (
          <Confirm busy={!canWrite} onConfirm={async () => { const err = await onMinutes(minutesLetter(data, legal)); setStatus(err ? { ok: false, text: err } : { ok: true, text: "Draft minutes queued in Approvals for the secretary. Approving them is a consent item at the next meeting." }); }}
            summary={<p>Draft the minutes from this log ({r.log.length} entries) as a letter in Approvals, key {data.minutesKey}, approver the secretary. Nothing is posted or sent; the secretary reviews it first.</p>}>
            Prepare draft minutes
          </Confirm>
        )}
        {status && <p className={status.ok ? "notice" : "notice notice-error"}>{status.text}</p>}
        {data.commands.minutesDraft && <Command cmd={data.commands.minutesDraft} note="Drafts the minutes from the meeting's record (open portion only), with blanks for the Secretary; reads disk." />}
      </div>
    </div>
  );
}

function ZoomTab({ data, item, onAction, canWrite }: TabProps) {
  const r = data.room;
  const [waiting, setWaiting] = useState<string[]>([]);
  const [joiner, setJoiner] = useState("");
  const [question, setQuestion] = useState("");
  const [results, setResults] = useState("");
  const chair = "the chair";
  const status: [string, string][] = r.mode === "host"
    ? [["Host", "jason, association account"], ["Chair", chair], ["Alternative hosts", `${r.directors.length} directors`], ["Stage", "Presentation mode, sent to all"]]
    : r.mode === "co-host"
      ? [["Host", `${chair}, association account`], ["Co-host", "jason"], ["Stage", "jason shares its screen"], ["Polls", "co-hosts can launch"]]
      : [["Host", chair], ["jason", "not in the call"], ["Stage", "shared from the portal tab"]];
  status.push(["Recording", r.executive.active ? "paused for executive session (by the host)" : "cloud, with transcript"], ["Live transcript", r.executive.active ? "paused" : "on (association account)"]);
  const match = (name: string) => {
    const q = name.trim().toLowerCase();
    const hit = data.roster.rows.find((row) => row.name.toLowerCase() === q) ?? data.roster.rows.find((row) => q && row.name.toLowerCase().includes(q));
    return hit ? { ok: true, detail: `owner of record · ${hit.unit}` } : { ok: false, detail: data.roster.count ? "no match on the owner roster" : "roster not synced" };
  };
  const matched = waiting.filter((n) => match(n).ok && !r.admitted.includes(n));
  const parsed = results.split("\n").map((l) => l.split("=").map((s) => s.trim())).filter((p) => p[0]).map(([k, v]) => [k, Number(v) || 0] as const);
  return (
    <div className="hp-stack">
      <dl className="hp-status">{status.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>
      {r.mode === "portal" ? (
        <div className="hp-section">
          <span className="muted">Presenting from the portal</span>
          <ol className="hp-steps"><li>Sign in to the community portal and open Meeting room.</li><li>In Zoom, share this browser tab (Share screen, then the tab).</li><li>Press Present full screen. Keep this panel on a second screen or another tab.</li></ol>
          <p className="muted">The Zoom host admits members, mutes, and runs polls. jason still keeps the record here.</p>
        </div>
      ) : (
        <div className="hp-section">
          <div className="row wrap"><span className="muted">Waiting room</span>
            {matched.length > 0 && (
              <Confirm busy={!canWrite} onConfirm={async () => { await onAction("admit", { names: matched }); setWaiting([]); }}
                summary={<p>Log that {matched.join(", ")} ({matched.length}) were admitted as matched owners of record. {data.zoom.admitCommand ? "Then run the command shown." : "jason has no command that admits anyone: the host admits them in Zoom; this is the record of it."} Anyone unmatched waits for the chair (CIV 4925).</p>}>
                Admit matched owners
              </Confirm>
            )}
          </div>
          {data.zoom.admitCommand && <Command cmd={data.zoom.admitCommand} />}
          {!data.roster.count && <p className="notice notice-warn">roster not synced{data.roster.note ? `: ${data.roster.note}` : ""}</p>}
          <div className="row wrap">
            <input aria-label="Joiner's name" value={joiner} onChange={(e) => setJoiner(e.target.value)} placeholder="name as shown in Zoom" />
            <button onClick={() => { if (joiner.trim()) { setWaiting([...waiting, joiner.trim()]); setJoiner(""); } }}>Add to waiting room</button>
          </div>
          {waiting.map((n) => { const m = match(n); return <div key={n} className="hp-waiting"><span><span>{n}</span><span className="muted">{m.detail}</span></span>{r.admitted.includes(n) ? <Badge tone="good">admitted</Badge> : <Badge tone={m.ok ? "neutral" : "warn"}>{m.ok ? "matched" : "waits for the chair"}</Badge>}</div>; })}
          {r.admitted.length > 0 && <p className="muted">Admitted so far: {r.admitted.join(", ")}.</p>}
          <p className="limit">Only members may attend open meetings (CIV 4925). The chair decides on anyone jason can't match to the owner roster; jason admits no one it cannot match and removes no one.</p>
        </div>
      )}
      <div className="hp-section">
        <span className="muted">Polls and surveys</span>
        {r.polls.map((p, i) => <div key={i} className="hp-poll"><strong>{p.question}</strong><ul>{Object.entries(p.results).map(([k, v]) => <li key={k}><span>{k}</span><span className="num">{v}</span></li>)}</ul><span className="muted">{p.note}</span></div>)}
        <label className="hp-field">Question <input value={question} onChange={(e) => setQuestion(e.target.value)} /></label>
        <label className="hp-field">Results, one per line as answer = count <textarea rows={3} value={results} onChange={(e) => setResults(e.target.value)} placeholder={"Yes = 5\nNo = 1"} /></label>
        {question.trim() && parsed.length > 0 && (
          <Confirm busy={!canWrite} onConfirm={async () => { await onAction("poll", { question: question.trim(), results: Object.fromEntries(parsed) }); setQuestion(""); setResults(""); }}
            summary={<p>Record the poll "{question.trim()}": {parsed.map(([k, v]) => `${k} ${v}`).join(", ")}. Member input, not a board vote.</p>}>
            Record poll results
          </Confirm>
        )}
        <p className="muted">Polls are for members' input, never for board votes. Director votes are a roll call by name (CIV 4926(a)(3)).</p>
      </div>
      {item?.kind === "forum" && <p className="muted">When a member has the floor, the host unmutes them for {r.openForum.limitMinutes} minutes.</p>}
      <div className="hp-section">
        <p>Executive session: members leave the room, and the recording and transcript stop. Executive session minutes are not open to inspection (CIV 4935, 5215).</p>
        {!r.executive.active ? (
          <Confirm busy={!canWrite} onConfirm={() => onAction("executive_start", { note: item?.matters?.join(" and ") ?? "" })}
            summary={<p>Log that the board adjourned to executive session{item?.matters?.length ? ` to discuss ${item.matters.join(" and ")}` : ""}. The host pauses the cloud recording and the live transcript and moves the {r.present.length} directors present; jason does not control Zoom from here.</p>}>
            Start executive session
          </Confirm>
        ) : (
          <Confirm busy={!canWrite} onConfirm={() => onAction("executive_end")} summary={<p>Log that the board returned to open session. The host resumes the recording and the live transcript; the open minutes note the matters generally (CIV 4935(e)).</p>}>
            Return to open session
          </Confirm>
        )}
        {r.executive.active && <p className="limit">In executive session since {hhmm(r.executive.startedAt)}. Members wait for the open session to resume.</p>}
      </div>
      <p className="muted">{data.zoom.note}</p>
      {data.zoom.commands.sync && <Command cmd={data.zoom.commands.sync} note="Reads the Zoom account's meetings, transcripts, and summaries to disk after the meeting." />}
    </div>
  );
}
