import { useState } from "react";
import { Card, Caveats, Command, Confirm, Pill, QuestionCard, RemoteView, Seal, StageSteps, type GlyphName, type Question, type StageGate } from "../components";
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

/** An item's `FactAsk`: the question, where its answer goes, whether a second person confirms it (`stakes`), the legal
 * clock it sets as the profile names it (never a date), and whether it is `standing` (asked whatever the item's
 * status: an office, a term). */
export type ItemAsk = { id: string; question: string; record: string; stakes: boolean; standing?: boolean; clock?: string; inQueue: boolean } & AskState;

/** One checklist item as `GET /api/onboarding-session` gives it: its status is computed from its checks. */
export interface SetupItem {
  key: string; group: string; groupTitle: string; title: string; why: string; status: string;
  findings: { passed: boolean; evidence: string }[]; fetch: string; byPerson: boolean; stages: string[];
  ask: ItemAsk | null;
  connect: Connect | null;
}

export interface SetupQuestion extends Question { record?: string; connect?: Connect | null; standing?: boolean }
export interface Waiting extends AskState { id: string; kind: string; subject: string; question: string; serves: string; apply: string }
export interface SetupGroup { group: string; title: string; present: number; partial: number; missing: number }

export interface SetupSession {
  found?: boolean; note?: string; command?: string; title: string; asOf: string; stage: string;
  progress: Record<string, number>; groups: SetupGroup[];
  gates: StageGate[]; counts: { open: number; answeredNotApplied: number; notYetInQueue: number };
  items: SetupItem[]; next: SetupQuestion[]; nextTotal: number; otherOpen?: { count: number; command: string }; answered: Waiting[];
  apply: { command: string; note: string }; caveats?: string[];
}

/** What the intake route answers (`POST /api/write/intake/<id>`). */
interface Queued { id: string; status: string; answeredBy: string; answeredAt?: string; highStakes: boolean; needsConfirmation: boolean; confirmedBy?: string; apply: string; confirm?: string; next: string }

const day = (iso?: string) => (iso ? iso.slice(0, 10) : "");

/** An item's computed status as words and a glyph, never colour alone. */
const STATUS_GLYPH: Record<string, GlyphName> = { present: "circle-check", partial: "circle-dashed", missing: "circle-question-mark" };
const STATUS_MEANING: Record<string, string> = {
  present: "computed: every check passed", partial: "computed: some checks passed", missing: "computed: no check passed",
};

const gateWord = (stage: string) => `the ${stage} gate`;
const scrollTo = (id: string) => document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "center" });

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

/** What holds the gate being worked: every item behind it not yet present (the server's rule), the high-stakes ones
 * first and marked, and the gate's own checks that did not pass. A gate is never clicked open. */
function GateHold({ gate, items }: { gate: StageGate; items: Map<string, SetupItem> }) {
  const rows = (gate.waiting ?? []).map((w) => ({ w, item: items.get(w.key) }))
    .sort((a, b) => Number(!!b.item?.ask?.stakes) - Number(!!a.item?.ask?.stakes));
  const failed = (gate.checks ?? []).filter((c) => !c.passed);
  if (!rows.length && !failed.length) return null;
  return (
    <section className="stack-sm" aria-label={`What holds ${gateWord(gate.stage)}`}>
      <h3>What holds {gateWord(gate.stage)}</h3>
      <p className="muted">Each item behind a gate holds it until its checks pass. A high-stakes item's answer also waits on a second person.</p>
      <ul className="plain stack-sm">
        {rows.map(({ w, item }) => (
          <li key={w.key} className="row wrap">
            <Pill word={w.status} meaning={STATUS_MEANING[w.status]} glyph={STATUS_GLYPH[w.status]} />
            {item ? <button type="button" className="link" onClick={() => scrollTo(`setup-item-${w.key}`)}>{item.title}</button> : <span>{w.key}</span>}
            {item?.ask?.stakes && <span className="badge badge-warn">high stakes</span>}
          </li>
        ))}
        {failed.map((c) => <li key={c.evidence}><Seal word="could-not-confirm" detail={c.evidence} inline /></li>)}
      </ul>
    </section>
  );
}

/** An item's next step: nothing, a terminal command (a connection, or the command that reads it), or its question. */
function NextStep({ item, queued, shown }: { item: SetupItem; queued?: Queued; shown: Set<string> }) {
  const a = item.ask;
  if (item.status === "present" && !a?.standing) return <span className="muted">Nothing to do: its checks pass.</span>;
  if (item.connect) return <ConnectCommands c={item.connect} />;
  if (a) {
    const state = queued?.status ?? a.state;
    if (state === "answered") {
      const second = queued ? queued.needsConfirmation : !!a.needsConfirmation;
      return (
        <div className="row wrap">
          <span>Answered by {queued?.answeredBy ?? a.answeredBy}{(queued?.answeredAt ?? a.answeredAt) ? `, ${day(queued?.answeredAt ?? a.answeredAt)}` : ""}: waiting to be applied.</span>
          {second && <Seal word="waiting-on" detail="a second person" inline />}
        </div>
      );
    }
    if (state === "applied") return <span className="muted">Its answer was applied; the checks read it on the next run.</span>;
    if (state === "dismissed") return <span className="muted">Its question was dismissed. {item.fetch ? <code className="chip">{item.fetch}</code> : "A person supplies it."}</span>;
    return (
      <div className="stack-sm">
        <span>{a.standing ? "A standing question" : "A question"}: {a.question}</span>
        <span className="muted">The answer goes to the {a.record}{a.stakes ? "; a second person confirms it" : ""}.{a.clock ? ` Clock: ${a.clock}.` : ""}</span>
        {shown.has(a.id) ? (
          <span><button type="button" className="link" onClick={() => scrollTo(`setup-q-${a.id}`)}>Answer it under Questions</button></span>
        ) : a.inQueue ? (
          <Command cmd={`jason onboard --questions --group ${item.group}`} note="Ranked below the questions shown here: list it in a terminal." />
        ) : (
          <Command cmd="jason onboard --scan" note="Parks the question in the intake queue so it can be answered." />
        )}
      </div>
    );
  }
  if (item.fetch) return <Command cmd={item.fetch} note="Reads it once access is set up. Run it in a terminal." />;
  return <span className="muted">A person supplies it: no jason command reads it.</span>;
}

/** One checklist item: its computed status in words and a glyph, what jason checked as seals, and its next step. */
function ChecklistRow({ item, queued, shown }: { item: SetupItem; queued?: Queued; shown: Set<string> }) {
  return (
    <li id={`setup-item-${item.key}`} className="stack-sm" aria-label={item.title}>
      <div className="row wrap">
        <Pill word={item.status} meaning={STATUS_MEANING[item.status]} glyph={STATUS_GLYPH[item.status]} />
        <strong>{item.title}</strong>
        {item.ask?.standing && <span className="badge badge-neutral" title="Asked whatever the item's status: a record kept as it changes">standing</span>}
        {item.ask?.stakes && <span className="badge badge-warn">high stakes</span>}
        {item.stages.length > 0 && <span className="muted">holds {item.stages.map(gateWord).join(" and ")}</span>}
      </div>
      {item.why && <span className="muted">{item.why}</span>}
      <div className="row wrap" aria-label="What jason checked">
        {item.findings.length
          ? item.findings.map((f) => <Seal key={f.evidence} word={f.passed ? "read" : "could-not-confirm"} detail={f.evidence} inline />)
          : <Seal word="could-not-confirm" detail="nothing in jason holds this yet" inline />}
      </div>
      <div className="stack-sm"><strong>Next</strong><NextStep item={item} queued={queued} shown={shown} /></div>
    </li>
  );
}

/** The checklist by the server's groups, in its order; a group holding the gate being worked opens first. */
function Groups({ d, queued, shown }: { d: SetupSession; queued: Record<string, Queued>; shown: Set<string> }) {
  const items = d.items ?? [];
  const groups: SetupGroup[] = d.groups?.length ? d.groups : [...new Map(items.map((i) => [i.group, {
    group: i.group, title: i.groupTitle,
    present: items.filter((x) => x.group === i.group && x.status === "present").length,
    partial: items.filter((x) => x.group === i.group && x.status === "partial").length,
    missing: items.filter((x) => x.group === i.group && x.status === "missing").length,
  }])).values()];
  const holding = new Set((d.gates ?? []).find((g) => g.stage === d.stage)?.waiting?.map((w) => w.key) ?? []);
  return (
    <div className="stack-sm">
      {groups.map((g) => {
        const rows = items.filter((i) => i.group === g.group);
        const total = g.present + g.partial + g.missing;
        const stages = [...new Set(rows.flatMap((i) => i.stages))];
        return (
          <details key={g.group} open={rows.some((i) => holding.has(i.key))}>
            <summary>
              <strong>{g.title}</strong>{" "}
              <span className="muted">
                {g.present} of {total} present, {g.partial} partial, {g.missing} missing{stages.length ? ` · holds ${stages.map(gateWord).join(" and ")}` : ""}
              </span>
            </summary>
            {rows.length ? (
              <ul className="plain stack">
                {rows.map((i) => <ChecklistRow key={i.key} item={i} queued={i.ask ? queued[i.ask.id] : undefined} shown={shown} />)}
              </ul>
            ) : <p className="muted">No item in this group.</p>}
          </details>
        );
      })}
    </div>
  );
}

/** Setting up the community: the five gates and what holds the one being worked, the questions a person answers, what
 * waits to be applied, and the checklist by the server's groups, each item with its computed status, what jason
 * checked, and its next step. A signed-in person answers through `Confirm`; the answer goes to the intake queue and a
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
        const byKey = new Map(items.map((i) => [i.key, i]));
        const current = gates.find((g) => g.stage === d.stage);
        const next = (d.next ?? []).filter((q) => !queued[q.id]);
        const shown = new Set(next.map((q) => q.id));
        const waiting: Waiting[] = [
          ...(d.answered ?? []).map((w) => (queued[w.id] ? { ...w, ...queued[w.id], state: queued[w.id].status } : w)),
          ...Object.values(queued).filter((q) => !(d.answered ?? []).some((w) => w.id === q.id) && q.status === "answered").map((q) => {
            const asked = (d.next ?? []).find((x) => x.id === q.id);
            return { ...q, kind: asked?.kind ?? "", subject: asked?.subject ?? "", question: asked?.question ?? q.id, serves: asked?.serves ?? "", state: q.status };
          }),
        ];
        const present = d.progress?.present ?? 0;
        const total = present + (d.progress?.partial ?? 0) + (d.progress?.missing ?? 0);
        const operating = d.stage === "operating";
        const firstRun = present === 0 && waiting.length === 0;
        const gateName = operating ? "" : gateWord(d.stage);
        return (
          <div className="stack">
            <Card title={d.title || "Setting up the community"}>
              <div className="row wrap">
                <Seal word="read" detail="the checklist, from the profile and the stores" date={day(d.asOf)} inline />
              </div>
              {firstRun && !operating && (
                <p className="notice">
                  First run: nothing on the checklist is present yet. Begin with {gateName}{current?.opensWhen ? `, ${current.opensWhen}` : ""}.
                </p>
              )}
              <StageSteps gates={gates} current={d.stage} label="The five gates" />
              <p className="muted">
                {operating ? "Every stage gate is open. The association is operating." : `Working on ${gateName}.`}{" "}
                {total} items: {present} present, {d.progress?.partial ?? 0} partial, {d.progress?.missing ?? 0} missing.
                An item's status is computed from its checks; there is nothing to mark done.
              </p>
              {current && !current.open && <GateHold gate={current} items={byKey} />}
            </Card>
            <Card title={`Questions (${next.length} of ${d.nextTotal ?? next.length})`}>
              {!signIn.account && (
                <p className="notice">
                  Sign in to answer: an answer goes on the record under the signed-in name.{" "}
                  {signIn.signInLinks.map((l) => <a key={l.href} href={l.href}>{l.label}</a>)}
                </p>
              )}
              {signIn.acting && <p className="notice">Viewing as {signIn.acting.name || `the ${signIn.acting.role}`} (admin view): answers are refused. Go back to yourself to answer.</p>}
              {next.length === 0 ? (
                <p className="muted">
                  {operating ? "No open questions." : `No open questions for ${gateName}: what holds it is read by a command or supplied by a person, as each item below says.`}
                </p>
              ) : (
                <div className="stack">
                  {next.map((q, n) => (
                    <div key={q.id} id={`setup-q-${q.id}`} className="stack-sm">
                      {q.standing && (
                        <p className="row wrap">
                          <span className="badge badge-neutral">standing</span>
                          <span className="muted">Asked whatever the item's status: a record kept as it changes.</span>
                        </p>
                      )}
                      {q.connect ? (
                        <article className="question-card" aria-label={q.question}>
                          <span className="question-rank">{n + 1}</span>
                          <div className="stack-sm">
                            <h3 className="question-text">{q.question}</h3>
                            <ConnectCommands c={q.connect} />
                          </div>
                        </article>
                      ) : (
                        <QuestionCard key={`${q.id}-${resets[q.id] ?? 0}`} question={q} rank={n + 1} me={me} byFixed compact={!canWrite}
                          busy={busy === q.id} error={errors[q.id]} onAnswer={(b) => send(b.id, { answer: b.answer, by: b.by })} />
                      )}
                    </div>
                  ))}
                </div>
              )}
              {!!d.otherOpen?.count && <p className="muted">{d.otherOpen.count} more open questions about the documents' words and kinds are in the intake queue: <code className="chip">{d.otherOpen.command}</code></p>}
            </Card>
            <Card title={`Answered, waiting to be applied (${waiting.length})`}>
              {waiting.length === 0 ? (
                <p className="muted">
                  No answer waits to be applied.{firstRun && !operating ? ` An answer to a question for ${gateName} waits here, with who gave it, until a person applies it.` : ""}
                </p>
              ) : (
                <ul className="plain stack">
                  {waiting.map((w) => <Answered key={w.id} w={w} me={me} canWrite={canWrite} busy={busy === w.id} error={errors[w.id]}
                    onConfirm={(id) => send(id, { confirm: true, by: me })} />)}
                </ul>
              )}
              <Command cmd={d.apply?.command ?? "jason onboard --apply"} note={d.apply?.note ?? "Run by a person in a terminal."} />
            </Card>
            <Card title="The checklist">
              <Groups d={d} queued={queued} shown={shown} />
            </Card>
            <Caveats items={d.caveats} />
          </div>
        );
      }}
    </RemoteView>
  );
}
