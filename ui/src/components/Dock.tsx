import { useEffect, type ReactNode } from "react";
import { useApi } from "../lib/useApi";
import { postJson } from "../lib/api";
import { DeadlineList } from "./DeadlineList";
import { ActionRegister } from "./ActionRegister";
import { Scratchpad } from "./Scratchpad";
import { AskPanel } from "./AskPanel";

/** The dock's four drawers. Owners see only Ask. */
export const DOCK_DRAWERS: { id: string; label: string; title: string; owner: boolean }[] = [
  { id: "deadlines", label: "Deadlines", title: "Deadlines", owner: false },
  { id: "tasks", label: "Tasks", title: "Action register", owner: false },
  { id: "notes", label: "Scratchpad", title: "Scratchpad", owner: false },
  { id: "ask", label: "Ask", title: "Ask jason", owner: true },
];

/** The console screen a dock row points at, by id, in words. Unknown ids read as themselves. */
const SCREEN_LABELS: Record<string, string> = {
  digest: "Board digest", approvals: "Approvals", duties: "Duties", actions: "Action items", decisions: "Decisions", agenda: "Plan a meeting",
  room: "Meeting room", meetings: "Meetings", records: "Records", liens: "Liens", payments: "Payments", reserves: "Reserves", insurance: "Insurance",
  disclosures: "Disclosures", calendar: "Calendar",
};
export function screenLabel(id: string | undefined | null): string {
  return (id && SCREEN_LABELS[id]) || id || "";
}

/** Fired on `window` after any dock write, so the toolbar's counts and other open drawers reload. */
export const DOCK_EVENT = "jason:dock";

export type DockAction = "task_add" | "task_update" | "task_done" | "note_add" | "note_update" | "ask" | "translate" | "translation_state";

/** One write to the dock store: `POST /api/write/dock/<key>` (`new` for a create). Every call names who made it. */
export async function dockWrite<T>(key: string, body: { action: DockAction; by: string } & Record<string, unknown>): Promise<T> {
  const out = await postJson<T>(`/api/write/dock/${encodeURIComponent(key || "new")}`, body);
  window.dispatchEvent(new Event(DOCK_EVENT));
  return out;
}

interface Counts { found?: boolean; deadlines?: number; tasks?: number }

/** The red counts on the dock pills: overdue deadlines and overdue open tasks, from `/api/dock?part=counts`. */
export function useDockCounts(): { deadlines: number; tasks: number } {
  const r = useApi<Counts>("/api/dock?part=counts");
  useEffect(() => {
    const on = () => r.reload();
    window.addEventListener(DOCK_EVENT, on);
    return () => window.removeEventListener(DOCK_EVENT, on);
  }, [r.reload]);
  const d = r.status === "ready" ? r.data : undefined;
  return { deadlines: d?.deadlines ?? 0, tasks: d?.tasks ?? 0 };
}

/** The pill group in the console header: one pill per drawer, the open one filled, with red overdue counts. */
export function DockToolbar({ open, onToggle, counts, audience }: {
  open: string | null; onToggle: (id: string) => void; counts: { deadlines: number; tasks: number }; audience: "board" | "owner";
}) {
  const shown = DOCK_DRAWERS.filter((d) => audience !== "owner" || d.owner);
  return (
    <div role="toolbar" aria-label="Dock" className="dock">
      {shown.map((d) => {
        const n = d.id === "deadlines" ? counts.deadlines : d.id === "tasks" ? counts.tasks : 0;
        return (
          <button key={d.id} type="button" aria-expanded={open === d.id} className={`dock-pill${open === d.id ? " on" : ""}`} onClick={() => onToggle(d.id)}>
            {d.label}
            {n > 0 && <span className="dock-count" aria-label={`${n} overdue`}>{n}</span>}
          </button>
        );
      })}
    </div>
  );
}

/** A drawer: pinned, a sticky column card the shell places in its row; floating, a fixed panel on the right. */
export function Drawer({ id, title, pinned, canDock, onPin, onUnpin, onClose, children }: {
  id: string; title: string; pinned: boolean; canDock: boolean; onPin: () => void; onUnpin: () => void; onClose: () => void; children: ReactNode;
}) {
  const head = (
    <div className="drawer-head">
      <strong className="drawer-title">{title}</strong>
      <span className="row">
        {pinned ? <button type="button" onClick={onUnpin}>Float</button> : canDock && <button type="button" onClick={onPin}>Dock it</button>}
        <button type="button" onClick={onClose} aria-label="Close">Close</button>
      </span>
    </div>
  );
  if (pinned)
    return (
      <aside aria-label={title} className="drawer drawer-pinned" data-drawer={id}>
        {head}
        <div className="drawer-body">{children}</div>
      </aside>
    );
  return (
    <aside role="dialog" aria-label={title} aria-modal="false" className="drawer drawer-float" data-drawer={id}>
      {head}
      <div className="drawer-body">{children}</div>
    </aside>
  );
}

/** The drawer's contents by id. Each panel loads its own part of `/api/dock`. */
export function DockDrawerBody({ id, go, me }: { id: string; go: (screen: string) => void; me?: string }) {
  if (id === "deadlines") return <DeadlineList go={go} />;
  if (id === "tasks") return <ActionRegister go={go} me={me} />;
  if (id === "notes") return <Scratchpad me={me} />;
  if (id === "ask") return <AskPanel go={go} me={me} />;
  return <p className="muted">No drawer named {id}.</p>;
}
