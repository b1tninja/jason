import { useState } from "react";
import { ApprovalsInbox, Caveats, DraftLetter, RemoteView } from "../components";
import type { Letter, StageAction, StageBody } from "../components/DraftLetter";
import { postJson } from "../lib/api";
import { useApi } from "../lib/useApi";
import { useSession, type Person } from "../lib/session";
import { PlanApprovals } from "./PlanApprovals";

interface Page {
  found?: boolean; note?: string; letters: Letter[]; groups: Record<string, string[]>; pending: number; people: Person[]; stages: string[]; caveats?: string[];
}

/** The approvals inbox: who is signed in (Google sign-in, else the sample picker), the approvals engine's plans of writes (`PlanApprovals`, each opening to a
 * `PlanReview`), every letter jason drafted by where it stands, and the selected letter as a `DraftLetter` below. Every
 * letter step is a POST to `/api/write/approvals/<key>`, every plan step a POST to `/api/approvals/<id>`, in the
 * signed-in person's name. */
export function ApprovalsView({ go }: { go?: (screen: string) => void } = {}) {
  const r = useApi<Page>("/api/approvals");
  const people = r.status === "ready" ? r.data.people : undefined;
  const { me, setMe, account, acting } = useSession(people);
  const [open, setOpen] = useState("");
  const [plan, setPlan] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const act = async (key: string, action: StageAction, body: StageBody) => {
    setBusy(true); setError("");
    try {
      await postJson(`/api/write/approvals/${encodeURIComponent(key)}`, { action, ...body });
      r.reload();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="stack approvals-view">
      <header className="approvals-head">
        <h1>Approvals</h1>
        <p className="muted">Everything jason drafted that is waiting on a person. Nothing goes out without approval.</p>
        {account && acting ? (
          <p className="approvals-signin" role="status">Viewing as <strong>{acting.name || `the ${acting.role}`}</strong> (admin view): this is what they would see, and every step is refused until you go back to yourself.</p>
        ) : account ? (
          <p className="approvals-signin">Signed in with Google as <strong>{account.name}</strong>: every step here goes on the record in that name.</p>
        ) : (
          <label className="approvals-signin">
            <span>Sample sign-in: this picks whose name goes on the record</span>
            <select value={me} onChange={(e) => setMe(e.target.value)} aria-label="Signed in as">
              <option value="">— pick a person —</option>
              {(people ?? []).map((p) => <option key={p.name} value={p.name}>{p.name}, {p.role}</option>)}
            </select>
          </label>
        )}
      </header>
      {error && <p className="notice notice-error" role="alert">{error}</p>}
      <RemoteView r={r}>
        {(d) => {
          const letter = d.letters.find((l) => l.key === open);
          return (
            <>
              <PlanApprovals page={d} me={me} open={plan} onOpen={setPlan} />
              <div className="approvals-group"><h2>Letters</h2></div>
              <ApprovalsInbox letters={d.letters} me={me} people={d.people} onAction={act} busy={busy} go={go} onOpen={setOpen} />
              {letter && (
                <section className="approvals-open" aria-label="Open letter">
                  <div className="row wrap">
                    <strong>{letter.key}</strong>
                    <button className="link" onClick={() => setOpen("")}>Close</button>
                  </div>
                  <DraftLetter letter={letter} me={me} people={d.people} busy={busy} onStage={(action, body) => act(letter.key, action, body)} />
                </section>
              )}
              <Caveats items={d.caveats} />
            </>
          );
        }}
      </RemoteView>
    </div>
  );
}
