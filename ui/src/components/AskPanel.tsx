import { useState } from "react";
import { Badge } from "./Badge";
import { Command } from "./Command";
import { Confirm } from "./Confirm";
import { Evidence } from "./Evidence";
import { EvidenceEntries } from "./EvidenceEntries";
import { RemoteView } from "./Remote";
import { Tabs } from "./Tabs";
import { Caveats } from "./Caveats";
import { useApi } from "../lib/useApi";
import type { EvidenceEntry } from "../lib/docref";
import { dockWrite, screenLabel } from "./Dock";

/** `sourceRefs` are the sources as the loader mapped them, one for one: a citation or a library document is a reference
 * (a `Doc` chip), a tool call jason read is a command, anything else text. An older server leaves them out. */
export interface CommonQuestion { question: string; screen: string; answer: string; sources: string[]; sourceRefs?: EvidenceEntry[]; routed: boolean; note?: string }
export interface Ask { id: string; question: string; answer: string; sources: string[]; sourceRefs?: EvidenceEntry[]; screen: string; routed: boolean; at: string; by: string; task?: string }
type Shown = { q: string; answer: string; sources: string[]; refs?: EvidenceEntry[]; screen: string };
export interface Translation { id: string; englishKey: string; english: string; language: string; draft: string; state: string; by: string; at: string; history?: string[] }
export interface AskData {
  found?: boolean; note?: string; common: CommonQuestion[]; asks: Ask[]; translations: Translation[]; translationStates: string[];
  translateCommand: string; routedAnswer: string; caveats?: string[];
}

const ROUTED = "jason has no sourced answer for this. It went to the action register for the manager to answer.";
const CONTROLS = "The English notice controls.";

/** An answer jason found, with where it was read; or the routed state when it found none. An answer with no source is no answer. */
function Answer({ q, answer, sources, refs, screen, go }: Shown & { go: (s: string) => void }) {
  if (!sources.length)
    return (
      <article className="dock-answer dock-routed" aria-label="No sourced answer">
        <strong>{q}</strong>
        <p>{ROUTED} jason never guesses.</p>
      </article>
    );
  return (
    <article className="dock-answer" aria-label="Answer">
      <strong>{q}</strong>
      <p>{answer}</p>
      {refs?.length ? <EvidenceEntries label="Sources" entries={refs} /> : <Evidence label="Sources" items={sources} />}
      {screen && <div><button type="button" className="link" onClick={() => go(screen)}>Open {screenLabel(screen)}</button></div>}
    </article>
  );
}

/** Ask jason: common questions answered from the stores with citations, a free question that reads the library or
 * is routed to the manager, and a Translate tab where a person's draft sits beside the English record marked
 * "needs review" until a fluent reviewer approves it in Approvals. The English notice controls. */
export function AskPanel({ go, me }: { go: (screen: string) => void; me?: string }) {
  const r = useApi<AskData>("/api/dock?part=ask");
  const [tab, setTab] = useState("ask");
  const [name, setName] = useState("");
  const [q, setQ] = useState("");
  const [shown, setShown] = useState<Shown | null>(null);
  const [pick, setPick] = useState<string>("");
  const [tr, setTr] = useState({ englishKey: "", english: "", language: "", draft: "" });
  const [error, setError] = useState("");
  const by = (me ?? "").trim() || name.trim();

  const write = async <T,>(key: string, body: Parameters<typeof dockWrite>[1]): Promise<T | undefined> => {
    setError("");
    try { return await dockWrite<T>(key, body); } catch (e) { setError((e as Error).message); return undefined; }
  };

  return (
    <RemoteView r={r}>
      {(d) => {
        const current = d.translations.find((t) => t.id === pick) ?? d.translations[0];
        const askTab = (
          <div className="stack dock-panel">
            <div className="dock-add-row">
              <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ask about the rules or the records" aria-label="Question" />
              <Confirm busy={!q.trim() || !by}
                summary={<span>Ask jason "{q.trim()}" as {by}. It answers only from the library and its stores; with no sourced answer the question goes to the action register for the manager.</span>}
                onConfirm={async () => { const a = await write<Ask>("new", { action: "ask", by, question: q.trim() }); if (a) { setShown({ q: a.question, answer: a.answer, sources: a.sources, refs: a.sourceRefs, screen: a.screen }); setQ(""); } }}>
                Ask
              </Confirm>
            </div>
            {!by && <span className="dock-sub">A name is needed to record who asked.</span>}
            <div className="stack-tight">
              <span className="dock-sub">Common questions</span>
              <ul className="dock-list dock-common">
                {d.common.map((c) => (
                  <li key={c.question}>
                    <button type="button" className="dock-q" onClick={() => setShown({ q: c.question, answer: c.answer, sources: c.sources, refs: c.sourceRefs, screen: c.screen })}>
                      <span>{c.question}</span><span aria-hidden="true" className="muted">›</span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
            {shown && <Answer {...shown} go={go} />}
            {d.asks.length > 0 && (
              <details>
                <summary className="dock-sub muted">Asked before ({d.asks.length})</summary>
                <ul className="dock-list">
                  {d.asks.map((a) => (
                    <li key={a.id} className="dock-sub">
                      <button type="button" className="link" onClick={() => setShown({ q: a.question, answer: a.answer, sources: a.sources, refs: a.sourceRefs, screen: a.screen })}>{a.question}</button>
                      {" "}· {a.at.slice(0, 10)} {a.routed && <Badge tone="warn">routed</Badge>}
                    </li>
                  ))}
                </ul>
              </details>
            )}
            <Caveats items={d.caveats} />
          </div>
        );
        const translateTab = (
          <div className="stack dock-panel">
            {d.translateCommand && <Command cmd={d.translateCommand} note="A translation is a draft for a fluent reviewer; the page runs nothing." />}
            {d.translations.length > 0 && (
              <label className="dock-sub row">Translation
                <select value={current?.id ?? ""} onChange={(e) => setPick(e.target.value)} aria-label="Translation">
                  {d.translations.map((t) => <option key={t.id} value={t.id}>{t.englishKey || "notice"} ({t.language}) · {t.state}</option>)}
                </select>
              </label>
            )}
            {current && (
              <div className="stack-tight" aria-label="Translation record">
                <span className="dock-sub">English, the record · {current.englishKey || "notice"}</span>
                <p lang="en" className="dock-en">{current.english}</p>
                <span className="dock-task-head"><span className="dock-sub">{current.language}, draft translation</span><Badge tone={current.state === "approved" ? "good" : "warn"}>{current.state}</Badge></span>
                <p className="dock-draft">{current.draft}</p>
                {current.state === "needs review" && (
                  <Confirm busy={!by}
                    summary={<span>Send the {current.language} draft of "{current.englishKey || "notice"}" to a fluent reviewer through Approvals, by {by}. Nothing goes to members until it is approved. {CONTROLS}</span>}
                    onConfirm={async () => { await write(current.id, { action: "translation_state", by, state: "sent for review" }); }}>
                    Send for review
                  </Confirm>
                )}
                {current.state === "sent for review" && <p className="dock-sub dock-good">Waiting on a fluent reviewer in Approvals. The English notice stays the record.</p>}
                {current.state === "approved" && <p className="dock-sub dock-good">Approved by {current.by}. It goes out with the English notice, which controls.</p>}
              </div>
            )}
            <details open={d.translations.length === 0}>
              <summary className="dock-sub muted">Enter a draft translation</summary>
              <div className="stack-tight dock-add">
                <input value={tr.englishKey} onChange={(e) => setTr({ ...tr, englishKey: e.target.value })} placeholder="What it is (notice-2026-10-21)" aria-label="Record key" />
                <textarea rows={4} value={tr.english} onChange={(e) => setTr({ ...tr, english: e.target.value })} placeholder="The English record, word for word" aria-label="English record" />
                <input value={tr.language} onChange={(e) => setTr({ ...tr, language: e.target.value })} placeholder="Language" aria-label="Language" />
                <textarea rows={4} value={tr.draft} onChange={(e) => setTr({ ...tr, draft: e.target.value })} placeholder="A person's draft; there is no translator here" aria-label="Draft translation" />
                <div className="row wrap">
                  <Badge tone="warn">needs review</Badge>
                  <Confirm busy={!by || !tr.english.trim() || !tr.language.trim() || !tr.draft.trim()}
                    summary={<span>Record the English text and a {tr.language.trim()} draft entered by {by}, marked needs review. jason translated nothing. {CONTROLS}</span>}
                    onConfirm={async () => { const x = await write<Translation>("new", { action: "translate", by, ...tr }); if (x) { setPick(x.id); setTr({ englishKey: "", english: "", language: "", draft: "" }); } }}>
                    Save draft
                  </Confirm>
                </div>
              </div>
            </details>
            <p className="dock-sub dock-caveat">A fluent reader checks every translation before it goes out. If the two versions ever differ, the English notice controls.</p>
          </div>
        );
        return (
          <div className="stack">
            {!me && (
              <div className="dock-panel">
                <label className="dock-sub row">Your name
                  <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Who is asking" aria-label="Your name" />
                </label>
              </div>
            )}
            <Tabs active={tab} onChange={setTab} tabs={[{ id: "ask", label: "Ask", content: askTab }, { id: "translate", label: "Translate", content: translateTab }]} />
            {error && <p className="notice notice-error">{error}</p>}
          </div>
        );
      }}
    </RemoteView>
  );
}
