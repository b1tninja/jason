import { useState } from "react";
import { Card, Caveats, Command, Confirm, DataTable, Pill, QuestionCard, RemoteView, Seal, StageSteps, type Column, type Question, type StageGate } from "../components";
import { postJson } from "../lib/api";
import { sameName } from "../lib/approvals";
import { useSignIn } from "../lib/session";
import { useApi } from "../lib/useApi";

/** How a connection is made: the terminal commands; the console never takes a secret. */
export interface Connect { commands: string[]; note: string }

/** A queued question's state, never its answer's value (`onboarding_setup._answered`). */
export interface AskState {
  state: string; answeredBy?: string; answeredAt?: string; confirmedBy?: string; confirmedAt?: string;
  highStakes?: boolean; needsConfirmation?: boolean;
}

/** One checklist item as `GET /api/onboarding-session` gives it: its status is computed from its checks. */
export interface SetupItem {
  key: string; group: string; groupTitle: string; title: string; why: string; status: string;
  findings: { passed: boolean; evidence: string }[]; fetch: string; byPerson: boolean; stages: string[];
  ask: ({ id: string; question: string; record: string; stakes: boolean; inQueue: boolean } & AskState) | null;
  connect: Connect | null;
}

export interface SetupQuestion extends Question { record?: string; connect?: Connect | null }
export interface Waiting extends AskState { id: string; kind: string; subject: string; question: string; serves: string; apply: string }

export interface SetupSession {
  found?: boolean; note?: string; command?: string; title: string; asOf: string; stage: string;
  progress: Record<string, number>; groups: { group: string; title: string; present: number; partial: number; missing: number }[];
  gates: StageGate[]; counts: { open: number; answeredNotApplied: number; notYetInQueue: number };
  items: SetupItem[]; next: SetupQuestion[]; nextTotal: number; otherOpen?: { count: number; command: string }; answered: Waiting[];
  apply: { command: string; note: string }; caveats?: string[];
}

/** What the intake route answers (`POST /api/write/intake/<id>`). */
interface Queued { id: string; status: string; answeredBy: string; answeredAt?: string; highStakes: boolean; needsConfirmation: boolean; confirmedBy?: string; apply: string; confirm?: string; next: string }

const day = (iso?: string) => (iso ? iso.slice(0, 10) : "");

/** A connection: the commands to run in a terminal, and why there is no field here. */
function ConnectCommands({ c }: { c: Connect }) {
  return (
    <div className="stack-sm">
      {c.commands.map((cmd) => <Command key={cmd} cmd={cmd} note="Run it in a terminal; the console never takes a secret." />)}
      <p className="muted">{c.note}</p>
    </div>
  );
}

/** An answer in the queue: who gave it and when, never its value; the second person's state; and the apply command. */
function Answered({ w, me, canWrite, onConfirm, busy, error }: {
  w: Waiting; me: string; canWrite: boolean; onConfirm: (id: string) => void; busy?: boolean; error?: string;
}) {
  const mine = sameName(w.answeredBy, me);
  return (
    <li className="stack-sm">
      <strong>{w.question}</strong>
      <span>Answered by {w.answeredBy}{w.answeredAt ? `, ${day(w.answeredAt)}` : ""}: waiting to be applied.</span>
      {w.needsConfirmation ? (
        <div className="row wrap">
          <Seal word="waiting-on" detail="a second person" inline />
          {canWrite && !mine && (
            <Confirm busy={busy} label="Confirm" onConfirm={() => onConfirm(w.id)}
              summary={<p>Confirm {w.answeredBy}'s answer to {w.id} as {me}, the second person. Nothing is applied until a person runs {w.apply}.</p>}>
              Confirm as {me}
            </Confirm>
          )}
          {canWrite && mine && <span className="muted">You gave this answer, so someone else confirms it.</span>}
        </div>
      ) : w.highStakes && w.confirmedBy ? <span className="muted">Confirmed by {w.confirmedBy}{w.confirmedAt ? `, ${day(w.confirmedAt)}` : ""}.</span> : null}
      {error && <p className="notice notice-error" role="alert">{error}</p>}
    </li>
  );
}

/** Setting up the community: the five gates, each checklist item's computed status, the questions a person answers,
 * and what waits to be applied. A signed-in person answers through `Confirm`; the answer goes to the intake queue and a
 * person applies it in a terminal. Nothing here marks an item done: an item is present when its checks pass. */
export function SetupTab() {
  const r = useApi<SetupSession>("/api/onboarding-session");
  const signIn = useSignIn();
  const [queued, setQueued] = useState<Record<string, Queued>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [resets, setResets] = useState<Record<string, number>>({});
  const [busy, setBusy] = useState("");
  const me = signIn.account?.name ?? "";
  const canWrite = !!signIn.account && !signIn.acting;

  const send = async (id: string, body: Record<string, unknown>) => {
    setBusy(id);
    setErrors((e) => ({ ...e, [id]: "" }));
    try {
      const out = await postJson<Queued>(`/api/write/intake/${encodeURIComponent(id)}`, body);
      setQueued((q) => ({ ...q, [id]: out }));
    } catch (e) {
      setErrors((x) => ({ ...x, [id]: e instanceof Error ? e.message : String(e) }));
      setResets((x) => ({ ...x, [id]: (x[id] ?? 0) + 1 }));      // a refused answer is cleared from the field
    } finally {
      setBusy("");
    }
  };

  return (
    <RemoteView r={r}>
      {(d) => {
        const gates = d.gates ?? [];
        const items = d.items ?? [];
        const next = (d.next ?? []).filter((q) => !queued[q.id]);
        const waiting: Waiting[] = [
          ...(d.answered ?? []).map((w) => (queued[w.id] ? { ...w, ...queued[w.id], state: queued[w.id].status } : w)),
          ...Object.values(queued).filter((q) => !(d.answered ?? []).some((w) => w.id === q.id) && q.status === "answered").map((q) => {
            const asked = (d.next ?? []).find((x) => x.id === q.id);
            return { ...q, kind: asked?.kind ?? "", subject: asked?.subject ?? "", question: asked?.question ?? q.id, serves: asked?.serves ?? "", state: q.status };
          }),
        ];
        const cols: Column<SetupItem>[] = [
          { key: "status", header: "Status", render: (i) => <Pill word={i.status} meaning="computed from its checks" /> },
          { key: "title", header: "Item", render: (i) => <><strong>{i.title}</strong><div className="muted">{i.groupTitle}{i.stages.length ? ` · the ${i.stages.join(", ")} gate` : ""}</div></> },
          { key: "findings", header: "What jason checked", value: (i) => i.findings.map((f) => f.evidence).join("; "),
            render: (i) => i.findings.length ? <ul className="plain">{i.findings.map((f) => <li key={f.evidence}>{f.passed ? "ok" : "no"}: {f.evidence}</li>)}</ul> : <span className="muted">nothing in jason holds this yet</span> },
          { key: "next", header: "Next", value: (i) => i.ask?.state ?? "", render: (i) => {
            if (i.status === "present") return <span className="muted">—</span>;
            if (i.connect) return <ConnectCommands c={i.connect} />;
            const q = queued[i.ask?.id ?? ""];
            const state = q?.status ?? i.ask?.state;
            if (i.ask && state === "answered") return <span>Answered by {q?.answeredBy ?? i.ask.answeredBy}: waiting to be applied.</span>;
            if (i.ask) return <span>A question below. {i.ask.record}.</span>;
            return i.fetch ? <code className="chip">{i.fetch}</code> : <span className="muted">a person supplies it</span>;
          } },
        ];
        const total = (d.progress?.present ?? 0) + (d.progress?.partial ?? 0) + (d.progress?.missing ?? 0);
        return (
          <div className="stack">
            <Card title={d.title || "Setting up the community"}>
              <div className="row wrap">
                <Seal word="read" detail="the checklist, from the profile and the stores" date={day(d.asOf)} inline />
              </div>
              <StageSteps gates={gates} current={d.stage} label="The five gates" />
              <p className="muted">
                {d.stage === "operating" ? "Every stage gate is open. The association is operating." : `Working on the ${d.stage} gate.`}{" "}
                {total} items: {d.progress?.present ?? 0} present, {d.progress?.partial ?? 0} partial, {d.progress?.missing ?? 0} missing.
                An item's status is computed from its checks; there is nothing to mark done.
              </p>
            </Card>
            <Card title={`Questions (${next.length} of ${d.nextTotal ?? next.length})`}>
              {!signIn.account && (
                <p className="notice">
                  Sign in to answer: an answer goes on the record under the signed-in name.{" "}
                  {signIn.signInLinks.map((l) => <a key={l.href} href={l.href}>{l.label}</a>)}
                </p>
              )}
              {signIn.acting && <p className="notice">Viewing as {signIn.acting.name || `the ${signIn.acting.role}`} (admin view): answers are refused. Go back to yourself to answer.</p>}
              {next.length === 0 ? <p className="muted">No open questions.</p> : (
                <div className="stack">
                  {next.map((q, n) => q.connect ? (
                    <article key={q.id} className="question-card" aria-label={q.question}>
                      <span className="question-rank">{n + 1}</span>
                      <div className="stack-sm">
                        <h3 className="question-text">{q.question}</h3>
                        <ConnectCommands c={q.connect} />
                      </div>
                    </article>
                  ) : (
                    <QuestionCard key={`${q.id}-${resets[q.id] ?? 0}`} question={q} rank={n + 1} me={me} byFixed compact={!canWrite}
                      busy={busy === q.id} error={errors[q.id]} onAnswer={(b) => send(b.id, { answer: b.answer, by: b.by })} />
                  ))}
                </div>
              )}
              {!!d.otherOpen?.count && <p className="muted">{d.otherOpen.count} more open questions about the documents' words and kinds are in the intake queue: <code className="chip">{d.otherOpen.command}</code></p>}
            </Card>
            <Card title={`Answered, waiting to be applied (${waiting.length})`}>
              {waiting.length === 0 ? <p className="muted">No answer waits to be applied.</p> : (
                <ul className="plain stack">
                  {waiting.map((w) => <Answered key={w.id} w={w} me={me} canWrite={canWrite} busy={busy === w.id} error={errors[w.id]}
                    onConfirm={(id) => send(id, { confirm: true, by: me })} />)}
                </ul>
              )}
              <Command cmd={d.apply?.command ?? "jason onboard --apply"} note={d.apply?.note ?? "Run by a person in a terminal."} />
            </Card>
            <Card title="The checklist">
              <DataTable rows={items} columns={cols} searchable />
            </Card>
            <Caveats items={d.caveats} />
          </div>
        );
      }}
    </RemoteView>
  );
}
