import { useEffect, useRef, useState } from "react";
import { Badge, Caveats, Confirm, HostPanel, MeetingStage, RemoteView } from "../components";
import { forumLine, motionFor, type AgendaItem, type MeetingRoomData, type MinutesLetter, type PacketFile, type StageContent } from "../components/MeetingStage";
import { postJson } from "../lib/api";
import { useApi } from "../lib/useApi";
import { PHONE_QUERY, useMediaQuery } from "../lib/useMediaQuery";

/** The query after the view's hash: `#/meeting-room?audience=owner&date=2026-10-21`. */
export function hashQuery(): URLSearchParams {
  const h = typeof window === "undefined" ? "" : window.location.hash;
  return new URLSearchParams(h.includes("?") ? h.slice(h.indexOf("?") + 1) : "");
}

const ME_KEY = "jason-meeting-room-me";
const readMe = () => { try { return localStorage.getItem(ME_KEY) ?? ""; } catch { return ""; } };
const keepMe = (v: string) => { try { localStorage.setItem(ME_KEY, v); } catch { /* per-viewer convenience only */ } };

const MODE_LINE = {
  host: "jason hosts on the association's Zoom account as a Zoom App: this panel runs in the Zoom sidebar, and the stage opens in Presentation mode for everyone.",
  "co-host": "jason joins as co-host and shares this stage; the chair's account hosts. Admitting, muting, polls, and recording are the host's acts in Zoom; the room logs them.",
  portal: "jason is not in the call. A director signs in to the community portal, opens this room, and shares the stage from their browser. The Zoom host runs the call.",
};

/** What the stage shows for the current item: attendance at the call, the clock in open forum, the motion or facts on an item,
 * the options or a packet file when the host puts one up, the executive note, or the adjournment. */
export function stageContent(d: MeetingRoomData, item: AgendaItem | undefined, shown: { options?: boolean; packet?: PacketFile | null }, forumLeft: number, speakers: number): StageContent | null {
  const r = d.room;
  if (!item) return null;
  if (shown.packet) return { kind: "packet", file: shown.packet };
  if (shown.options && item.brief) return { kind: "options", decision: item.brief };
  if (item.kind === "call") {
    const here = r.present;
    const ok = here.length >= d.quorum && d.quorum > 0;
    return { kind: "attendance", rows: r.directors.map((n) => ({ name: n, present: here.includes(n) })),
      quorum: ok ? `${here.length} of ${r.directors.length} directors present. A quorum is ${d.quorum}.` : `Only ${here.length} of ${r.directors.length} directors present. The board cannot act without ${d.quorum}.` };
  }
  if (item.kind === "forum") {
    const so = `${speakers} ${speakers === 1 ? "speaker" : "speakers"} so far.`;
    // No clock without a limit on record: the board sets it (CIV 4925(b)); jason never assumes one.
    if (!(r.openForum.limitMinutes > 0)) return { kind: "facts", facts: ["Member comments.", forumLine(r.openForum), so] };
    return { kind: "countdown", seconds: forumLeft, speaker: `Member comments, ${forumLine(r.openForum)} (CIV 4925(b)). ${so}` };
  }
  if (item.kind === "exec") return { kind: "executive", note: `The board is adjourning to executive session to discuss ${(item.matters ?? []).join(" and ") || "the matters noticed"}.` };
  if (item.kind === "adjourn") return { kind: "adjourned", at: r.adjournedAt ? new Date(r.adjournedAt).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) : "" };
  const m = motionFor(r, item);
  if (m) return { kind: "motion", text: m.text, mover: m.mover, second: m.second, result: m.result ? `${m.result === "carried" ? "Carried" : "Failed"}, ${m.tally.aye}–${m.tally.no}–${m.tally.abstain}${m.recused.length ? `, ${m.recused.join(", ")} recused` : ""}` : "" };
  if (item.motion) return { kind: "motion", text: item.motion, mover: "", second: "" };
  return { kind: "facts", facts: item.facts };
}

/** The members' hold card while the board is in executive session: the open record's general note only (CIV 4935(e)). */
export function holdNote(d: MeetingRoomData): string {
  const said = d.room.executive.note;
  return said ? `The board is meeting in executive session to discuss ${said}.` : "The board is meeting in executive session.";
}

/** jason's script for the caption bar, one or two sentences a presenter would say. */
export function script(d: MeetingRoomData, item: AgendaItem | undefined): string {
  const r = d.room;
  if (!item) return "";
  const here = r.present.length, all = r.directors.length;
  if (item.kind === "call") return `Good evening. The president calls the meeting to order. ${here} of ${all} directors are present, ${here >= d.quorum && d.quorum > 0 ? "so the board has a quorum." : "so the board does not have a quorum and cannot act."}`;
  if (item.kind === "forum") return `Open forum. ${r.openForum.limitMinutes > 0 ? `Members may speak for up to ${r.openForum.limitMinutes} minutes each.` : "Members may speak; the board sets the time limit."} The board may respond briefly, but it acts only on items on the posted agenda.`;
  if (item.kind === "exec") return `The open session pauses while the board meets in executive session to discuss ${(item.matters ?? []).join(" and ") || "the matters noticed"}.`;
  if (item.kind === "adjourn") return "The open meeting is adjourned. Draft minutes will be available to members within 30 days.";
  const idx = d.items.indexOf(item) - 1;
  let line = `Item ${idx}, ${item.title}.${item.facts.length ? ` ${item.facts.join(". ")}.` : ""}`;
  if (item.recused.length) line += ` ${item.recused.join(", ")} has disclosed an interest and will not vote.`;
  const m = motionFor(r, item);
  if (m?.result) line += ` The motion ${m.result}, ${m.tally.aye}–${m.tally.no}–${m.tally.abstain}.`;
  else if (m) line += " The motion has been moved and seconded. The secretary will call the roll.";
  else if (item.motion) line += " The proposed motion is on the screen.";
  return line;
}

/** The meeting room: the stage with the host panel beside it, or the stage alone for the shared screen and the members' view. */
export function MeetingRoomView({ audience, wordmark = "jason", legal = "the association" }: { audience?: "board" | "owner"; wordmark?: string; legal?: string } = {}) {
  const q = hashQuery();
  const owner = (audience ?? (q.get("audience") === "owner" ? "owner" : "board")) === "owner";
  const [date, setDate] = useState(q.get("date") ?? "");
  const r = useApi<MeetingRoomData>(`/api/meeting-room${date ? `?date=${date}` : ""}`);
  const [me, setMe] = useState(readMe);
  const [presenter, setPresenter] = useState<"jason" | "chair" | null>(null);
  const [view, setView] = useState<"host" | "shared" | null>(null);
  const [mode, setMode] = useState<"co-host" | "host" | "portal" | null>(null);
  const [shown, setShown] = useState<{ options?: boolean; packet?: PacketFile | null }>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [forumLeft, setForumLeft] = useState<number | null>(null);
  const [running, setRunning] = useState(false);
  const [speakers, setSpeakers] = useState(0);
  const [full, setFull] = useState(false);
  // On a phone the host panel is a bottom sheet, and Previous and Next stay in a sticky row under the stage.
  const phone = useMediaQuery(PHONE_QUERY);
  const stageRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!running) return;
    const t = window.setInterval(() => setForumLeft((v) => { const n = Math.max(0, (v ?? 0) - 1); if (n === 0) setRunning(false); return n; }), 1000);
    return () => window.clearInterval(t);
  }, [running]);
  useEffect(() => {
    if (!owner) return;
    const t = window.setInterval(() => r.reload(), 15000); // the shared view follows the host's room record
    return () => window.clearInterval(t);
  }, [owner, r.reload]);
  useEffect(() => {
    const on = () => setFull(!!document.fullscreenElement);
    document.addEventListener("fullscreenchange", on);
    return () => document.removeEventListener("fullscreenchange", on);
  }, []);

  const act = (d: MeetingRoomData) => async (action: string, body: Record<string, unknown> = {}): Promise<boolean> => {
    setBusy(true); setError("");
    try {
      await postJson(`/api/write/meeting-room/${d.date}`, { action, by: me.trim(), directors: d.directors, ...body });
      r.reload();
      return true;
    } catch (e) {
      setError((e as Error).message);   // the store's refusal, in its words
      return false;
    } finally {
      setBusy(false);
    }
  };
  const minutes = async (letter: MinutesLetter) => {
    try {
      await postJson(`/api/write/approvals/${letter.key}`, { action: "draft", by: me.trim(), letter });
    } catch (e) {
      return `Approvals did not take the draft: ${(e as Error).message}`;
    }
  };
  const fullscreen = () => { const el = stageRef.current; if (el?.requestFullscreen) void el.requestFullscreen(); };

  return (
    <RemoteView r={r}>
      {(d) => {
        const room = d.room;
        const idx = Math.min(room.current, d.items.length - 1);
        const item = d.items[idx];
        const pres = presenter ?? room.presenter;
        const vw = owner ? "shared" : (view ?? room.view);
        const md = mode ?? room.mode;
        const left = forumLeft ?? room.openForum.limitMinutes * 60;
        // Members see the hold card for as long as the board is in executive session, whatever item the host has open.
        const holding = owner && room.executive.active;
        const content: StageContent | null = holding ? { kind: "executive", note: holdNote(d) } : stageContent(d, item, shown, left, speakers);
        const caption = pres === "jason"
          ? <><strong>jason</strong> · {holding ? `${holdNote(d)} The open session resumes when the board returns.` : script(d, item)}</>
          : <span>{md === "portal" ? "Chair presenting from the portal · jason taking notes" : `Chair presenting · jason ${md === "host" ? "hosting" : "co-hosting"} and taking notes`}</span>;
        const settingsChanged = pres !== room.presenter || md !== room.mode || (!owner && vw !== room.view);
        const doAct = act(d);
        // Next and Previous: what leaving this item and entering the next one puts in the minutes.
        const transition = (to: number) => {
          const steps: { action: string; body?: Record<string, unknown>; says: string }[] = [];
          const target = d.items[to];
          if (!target) return steps;
          if (item?.kind === "call" && !room.calledToOrder) steps.push({ action: "call_to_order", says: `log the call to order with ${room.present.length} of ${room.directors.length} directors present (quorum ${d.quorum})` });
          if (item?.kind === "forum" && to > idx) steps.push({ action: "open_forum", body: { count: speakers, close: true }, says: `log open forum, ${speakers} ${speakers === 1 ? "speaker" : "speakers"}` });
          if (item?.kind === "exec" && room.executive.active) steps.push({ action: "executive_end", says: "log the return to open session (the host resumes the recording)" });
          steps.push({ action: "go_to", body: { item: to, title: target.title }, says: `open "${target.title}"` });
          if (target.kind === "adjourn" && !room.adjournedAt) steps.push({ action: "adjourn", says: "log the adjournment (draft minutes due within 30 days, CIV 4950)" });
          return steps;
        };
        const run = async (steps: ReturnType<typeof transition>) => {
          for (const s of steps) if (!(await doAct(s.action, s.body))) return;
          setShown({}); setRunning(false); setForumLeft(null);
        };
        const move = (to: number, label: string) => {   // a plain function, not a component: Confirm's armed state must survive re-renders
          const steps = transition(to);
          if (!steps.length) return <button disabled>{label}</button>;
          return <Confirm busy={busy || !me.trim()} onConfirm={() => run(steps)} summary={<p>This will {steps.map((s) => s.says).join(", then ")}.</p>}>{label}</Confirm>;
        };
        return (
          <div className={phone && vw === "host" && !owner ? "stack room room-sheeted" : "stack room"}>
            <header className="room-head">
              <div>
                <h1>Meeting room</h1>
                <p className="muted">Board of directors · open meeting · {d.date}{room.calledToOrder ? ` · called to order ${new Date(room.calledToOrder).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}` : ""}{room.adjournedAt ? " · adjourned" : ""}</p>
                {!owner && <p className="muted room-modeline">{MODE_LINE[md]}</p>}
              </div>
              {owner ? (
                <div className="row wrap"><Badge tone="good">live</Badge><span className="muted">You are watching the open session. Speak during open forum by raising your hand in Zoom.</span><button onClick={fullscreen}>Full screen</button></div>
              ) : (
                <div className="row wrap room-controls">
                  <label>Meeting <input type="date" value={date || d.date} onChange={(e) => setDate(e.target.value)} /></label>
                  <label>Recording as <input value={me} onChange={(e) => { setMe(e.target.value); keepMe(e.target.value); }} placeholder="your name" /></label>
                  <div role="radiogroup" aria-label="Presenter" className="seg">
                    <button role="radio" aria-checked={pres === "jason"} onClick={() => setPresenter("jason")}>jason presents</button>
                    <button role="radio" aria-checked={pres === "chair"} onClick={() => setPresenter("chair")}>Chair presents</button>
                  </div>
                  <div role="radiogroup" aria-label="View" className="seg">
                    <button role="radio" aria-checked={vw === "host"} onClick={() => setView("host")}>Host view</button>
                    <button role="radio" aria-checked={vw === "shared"} onClick={() => setView("shared")}>Shared screen</button>
                  </div>
                  <label>jason joins <select value={md} onChange={(e) => setMode(e.target.value as typeof md)}><option value="co-host">as co-host</option><option value="host">as host (Zoom App)</option><option value="portal">not in the call (portal)</option></select></label>
                  <button onClick={fullscreen}>{full ? "Full screen (on)" : md === "portal" ? "Present full screen" : "Full screen"}</button>
                  {settingsChanged && (
                    <Confirm busy={busy || !me.trim()} onConfirm={async () => { if (pres !== room.presenter) await doAct("set_presenter", { presenter: pres }); if (vw !== room.view) await doAct("set_view", { view: vw }); if (md !== room.mode) await doAct("set_mode", { mode: md }); }}
                      summary={<ul>{pres !== room.presenter && <li>Presenter: {room.presenter} → {pres}</li>}{vw !== room.view && <li>View: {room.view} → {vw}</li>}{md !== room.mode && <li>jason joins: {room.mode} → {md}</li>}<li>Saved to the room record so the shared view follows.</li></ul>}>
                      Save room settings
                    </Confirm>
                  )}
                </div>
              )}
            </header>
            {error && <p className="notice notice-error" role="alert">{error}</p>}
            <div className={vw === "host" ? "room-body" : "room-body room-shared"}>
              <div className="room-stage">
                <MeetingStage stageRef={stageRef} wordmark={wordmark} legal={legal} item={holding ? { label: "Executive session", title: "The board is in executive session" } : { label: item?.label ?? "", title: item?.title ?? "No agenda" }} content={content} caption={caption}
                  progress={d.items.length ? (idx + 1) / d.items.length : 0} live={owner || vw === "shared"} time={item?.allot ? `${item.allot} min` : undefined}
                  audience={owner ? "owner" : "board"} />
                {!owner && (
                  <div className={phone ? "room-nav room-nav-sticky" : "room-nav"} {...(phone ? { role: "group", "aria-label": "Previous and next item" } : {})}>
                    {move(idx - 1, "← Previous")}
                    <span className="muted">{idx + 1} of {d.items.length} · {item?.label}</span>
                    {move(idx + 1, "Next item →")}
                  </div>
                )}
              </div>
              {vw === "host" && !owner && (
                <HostPanel sheet="auto" room={d} onAction={doAct} busy={busy} me={me} shown={shown} onShow={(s) => setShown({ ...shown, ...s })} legal={legal} onMinutes={minutes}
                  forum={{ running, left, speakers, onToggle: () => { if (!running) setForumLeft(left); setRunning(!running); }, onReset: () => { setRunning(false); setForumLeft(null); }, onNextSpeaker: () => { setRunning(false); setForumLeft(null); setSpeakers(speakers + 1); } }} />
              )}
            </div>
            {d.notes.length > 0 && !owner && <p className="muted">{d.notes.join(" · ")}</p>}
            {!owner && <Caveats items={d.caveats} />}
          </div>
        );
      }}
    </RemoteView>
  );
}
