import { useEffect, useState } from "react";
import { Confirm } from "./Confirm";
import { DueDate, daysUntil } from "./DueDate";
import { RemoteView } from "./Remote";
import { Caveats } from "./Caveats";
import { useApi } from "../lib/useApi";
import { DOCK_EVENT, dockWrite, screenLabel } from "./Dock";

export interface DockTask {
  id: string; text: string; source: string; screen: string; owner: string; due: string; done: boolean; doneBy: string; doneAt: string; created: string; by: string; history?: string[];
}
export interface DockTasks { found?: boolean; note?: string; today: string; count: number; overdue: number; open: number; tasks: DockTask[]; editable?: string[]; caveats?: string[] }

const FILTERS: [string, string][] = [["open", "Open"], ["mine", "Mine"], ["overdue", "Overdue"], ["done", "Done"]];

function sourceLabel(t: DockTask): string {
  if (t.source === "scratchpad") return "Scratchpad";
  if (t.source === "ask") return "Ask";
  if (t.source === "manual") return `Added by ${t.by || "a person"}`;
  return screenLabel(t.source);
}

/** The action register: what people said needs doing, filtered Open / Mine / Overdue / Done. The done checkbox
 * stamps who and when (it needs a name); quick add takes an owner and a due date. Every write is two clicks, and
 * jason assigns nothing and marks nothing done on its own. */
export function ActionRegister({ go, me }: { go: (screen: string) => void; me?: string }) {
  const r = useApi<DockTasks>("/api/dock?part=tasks");
  const [filter, setFilter] = useState("open");
  const [name, setName] = useState("");
  const [pending, setPending] = useState<{ id: string; done: boolean } | null>(null);
  const [draft, setDraft] = useState({ text: "", owner: "", due: "" });
  const [error, setError] = useState("");
  const by = (me ?? "").trim() || name.trim();
  useEffect(() => {
    const on = () => r.reload();
    window.addEventListener(DOCK_EVENT, on);
    return () => window.removeEventListener(DOCK_EVENT, on);
  }, [r.reload]);

  const write = async (key: string, body: Parameters<typeof dockWrite>[1]) => {
    setError("");
    try { await dockWrite(key, body); setPending(null); } catch (e) { setError((e as Error).message); }
  };

  return (
    <RemoteView r={r}>
      {(d) => {
        const today = new Date(d.today + "T00:00:00");
        const late = (t: DockTask) => !t.done && !!t.due && daysUntil(t.due, today) < 0;
        const pick = (f: string) => (t: DockTask) => f === "done" ? t.done : f === "mine" ? !t.done && !!by && t.owner === by : f === "overdue" ? late(t) : !t.done;
        const rows = d.tasks.filter(pick(filter)).sort((a, b) => (a.due || "9999").localeCompare(b.due || "9999") || a.created.localeCompare(b.created));
        return (
          <div className="stack dock-panel">
            {!me && (
              <label className="dock-sub row">Your name
                <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Who is writing" aria-label="Your name" />
              </label>
            )}
            <div role="tablist" className="row wrap dock-filters">
              {FILTERS.map(([id, label]) => (
                <button key={id} type="button" role="tab" aria-selected={filter === id} className={`dock-pill${filter === id ? " on" : ""}`} onClick={() => setFilter(id)}>
                  {label} {d.tasks.filter(pick(id)).length}
                </button>
              ))}
            </div>
            {rows.length === 0 && <p className="muted dock-empty">{filter === "mine" ? (by ? "Nothing open is assigned to you." : "Enter your name to see what is yours.") : "Nothing here."}</p>}
            <ul className="dock-list">
              {rows.map((t) => (
                <li key={t.id} className="dock-task">
                  <input type="checkbox" checked={t.done} aria-label={`Done: ${t.text}`} disabled={!by} title={by ? undefined : "A name is needed to stamp who marked it done"}
                    onChange={() => setPending({ id: t.id, done: !t.done })} />
                  <div className="stack-tight">
                    <div className="dock-task-head">
                      <span>{t.text}</span>
                      {!t.done && t.due && <span className="dock-when"><DueDate iso={t.due} today={today} /></span>}
                    </div>
                    <span className="dock-sub">
                      {t.owner || "unassigned"} · {t.screen ? <button type="button" className="link" onClick={() => go(t.screen)}>{sourceLabel(t)}</button> : sourceLabel(t)}
                    </span>
                    {t.done && <span className="dock-sub dock-good">done by {t.doneBy} on {t.doneAt.slice(0, 10)}</span>}
                    {pending?.id === t.id && (
                      <div className="confirm" role="group" aria-label="Confirm">
                        <div>{pending.done ? `Mark "${t.text}" done, stamped ${by} at now. Saved to the dock register only.` : `Reopen "${t.text}" and clear its done stamp, by ${by}.`}</div>
                        <div className="row">
                          <button type="button" className="primary" onClick={() => write(t.id, { action: "task_done", by, done: pending.done })}>Yes, do it</button>
                          <button type="button" onClick={() => setPending(null)}>Cancel</button>
                        </div>
                      </div>
                    )}
                  </div>
                </li>
              ))}
            </ul>
            <div className="stack-tight dock-add">
              <span className="dock-sub">Add to the register</span>
              <input value={draft.text} onChange={(e) => setDraft({ ...draft, text: e.target.value })} placeholder="What needs doing" aria-label="Task" />
              <div className="dock-add-row">
                <input value={draft.owner} onChange={(e) => setDraft({ ...draft, owner: e.target.value })} placeholder="Owner" aria-label="Owner" />
                <input type="date" value={draft.due} onChange={(e) => setDraft({ ...draft, due: e.target.value })} aria-label="Due" />
              </div>
              <div>
                <Confirm
                  busy={!draft.text.trim() || !by}
                  summary={<span>Add "{draft.text.trim()}" to the register{draft.owner ? ` for ${draft.owner}` : ""}{draft.due ? `, due ${draft.due}` : ""}, recorded by {by}. jason's dock store only; it assigns nothing.</span>}
                  onConfirm={async () => { await write("new", { action: "task_add", by, text: draft.text.trim(), owner: draft.owner.trim(), due: draft.due, source: "manual" }); setDraft({ text: "", owner: "", due: "" }); setFilter("open"); }}>
                  Add task
                </Confirm>
              </div>
              {!by && <span className="dock-sub">A name is needed to record who added it.</span>}
            </div>
            {error && <p className="notice notice-error">{error}</p>}
            <Caveats items={d.caveats} />
          </div>
        );
      }}
    </RemoteView>
  );
}
