import { useState } from "react";
import { AgendaWizard, RemoteView, type AgendaPlan, type PlanBody } from "../components";
import { postJson } from "../lib/api";
import { useApi } from "../lib/useApi";

/** Plan a meeting: the four-step wizard over `/api/agenda-plan`. Saves go to jason's own plan store; putting an item on
 * the noticed agenda and writing the Doc stay terminal commands a person runs. */
export function PlanMeetingView() {
  const [date, setDate] = useState("");
  const r = useApi<AgendaPlan>(`/api/agenda-plan${date ? `?date=${date}` : ""}`);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const save = async (day: string, body: PlanBody) => {
    setBusy(true); setError("");
    try {
      await postJson(`/api/write/agenda-plan/${day}`, body);
      r.reload();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="stack">
      <header className="screen-head">
        <h1>Plan a meeting</h1>
        <p className="muted">jason checks which matters are ready to act on and lists what the notice must carry. The board sets the agenda.</p>
      </header>
      <RemoteView r={r}>
        {(d) => (
          <div className="stack">
            <div className="row wrap">
              <label>Meeting <input type="date" value={date || d.date} onChange={(e) => setDate(e.target.value)} /></label>
              <span className="muted">the schedule's next meeting unless chosen; each date keeps its own plan</span>
              {d.updated && <span className="muted num">plan saved {d.updated.slice(0, 16).replace("T", " ")} UTC</span>}
            </div>
            {error && <p className="notice notice-error">{error}</p>}
            <AgendaWizard key={`${d.date}|${d.updated}`} plan={d} busy={busy} onSave={(body) => save(d.date, body)} />
          </div>
        )}
      </RemoteView>
    </div>
  );
}
