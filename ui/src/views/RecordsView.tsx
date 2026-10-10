import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { Badge, Caveats, RemoteView, ScreenHeader } from "../components";
import { useApi } from "../lib/useApi";
import { useHash } from "../lib/useHash";
import { useSession } from "../lib/session";
import { DriveChooser, StepPanel, type ChooserTab, type Step } from "./DriveChooser";
import { JobWatch, SlotWord } from "./RecordActs";
import { AckPanel, AnswerPanel, DeclinePanel, KeepPanel, MorePanel, ReadPanel, ReopenPanel, RepinPanel, ReplacePanel, SplitPanel, UnpinPanel } from "./RecordPanels";
import {
  CARDINALITY, LIST_ROUTE, STATE_ORDER, parseRoute, sizeWords, slotRoute, words,
  type Holder, type Plan, type SlotPageData, type SlotRow, type SlotsPage,
} from "./recordTypes";
import "./records.css";

type Panel =
  | { kind: "chooser"; tab: ChooserTab }
  | { kind: "answer" }
  | { kind: "more"; value: "yes" | "no" }
  | { kind: "reopen"; what: "answer" | "more" }
  | { kind: "bind" }
  | { kind: "step"; step: Step }
  | { kind: "read" | "unpin" | "keep" | "repin" | "replace" | "split" | "decline" | "ack"; pin: string };

/** What a person can do next, in the page's own few words, keyed by the state the server computed. */
function nextStep(r: SlotRow): string {
  if (r.hidden) return "Hidden by the profile";
  switch (r.state) {
    case "empty": return r.cardinality === "several" ? "Choose a file, or say none exists" : "Choose a file, or answer";
    case "picked": case "uploaded": return "Read the file";
    case "classified": return "Read the file, then check the reading";
    case "read": return "Check the reading";
    case "problem": return r.problem || "Look at the problem";
    case "waiting": return "Waiting on someone else";
    default: return "";
  }
}

function groupOpen(g: SlotsPage["groups"][number], filtering: boolean, first: boolean): boolean {
  return filtering || first || g.slots.some((s) => s.state === "problem");
}

/** Setup > Records (`#/setup/records`): the checklist of slots, each a record the association must be able to put its hands on,
 * by group, with how many are in each state. Counts and states come from the server. */
function ChecklistScreen({ query }: { query: URLSearchParams }) {
  const r = useApi<SlotsPage>("/api/record-slots");
  const [state, setState] = useState(query.get("state") ?? "");
  const [group, setGroup] = useState(query.get("group") ?? "");
  return (
    <div className="stack records-view">
      <ScreenHeader
        title="Records"
        summary="Each record the association must be able to put its hands on, with the file a person picked for it or the answer a person gave. A state is jason's reading of those records; no button sets one."
      />
      <RemoteView r={r}>
        {(d) => {
          const filtering = !!state || !!group;
          const shown = d.groups.filter((g) => !group || g.key === group)
            .map((g) => ({ ...g, slots: g.slots.filter((s) => !state || s.state === state) })).filter((g) => g.slots.length > 0);
          const allEmpty = d.counts.total > 0 && (d.counts.byState.empty ?? 0) === d.counts.total;
          const word = (v: string) => d.states.find((s) => s.value === v)?.word ?? words(v);
          return (
            <>
              <p className="muted">As of {d.asOf}. {d.driveCatalog ? `jason's Drive catalog holds ${d.driveCatalog.files} files${d.driveCatalog.syncedAt ? `, synced ${String(d.driveCatalog.syncedAt).slice(0, 10)}` : ""}.` : ""}</p>
              {allEmpty && <p className="notice" role="note">Nothing has been picked yet. Start with the biggest unknowns below, or choose a Drive folder that holds a group of records.</p>}
              <section aria-label="Slots by state" className="record-counts">
                <ul>
                  {STATE_ORDER.map((s) => (
                    <li key={s}>
                      <button type="button" aria-pressed={state === s} onClick={() => setState(state === s ? "" : s)} title={d.states.find((x) => x.value === s)?.meaning}>
                        <span className="record-count-n">{d.counts.byState[s] ?? 0}</span> <span>{word(s)}</span>
                      </button>
                    </li>
                  ))}
                </ul>
                <p className="muted">{d.counts.total} slots. {d.counts.held > 0 ? `${d.counts.held} hold a confidential file, held back outside the private view. ` : ""}{d.counts.hidden > 0 ? `${d.counts.hidden} hidden by the profile, with the reason on the slot.` : ""}</p>
                <details className="record-twin"><summary>Counts as a table</summary>
                  <table><caption className="sr-only">Slots by state</caption>
                    <thead><tr><th scope="col">State</th><th scope="col">Slots</th></tr></thead>
                    <tbody>{STATE_ORDER.map((s) => (<tr key={s}><th scope="row">{word(s)}</th><td>{d.counts.byState[s] ?? 0}</td></tr>))}</tbody>
                  </table>
                </details>
              </section>
              <div className="row wrap record-filters">
                <label htmlFor="records-group">Group</label>
                <select id="records-group" value={group} onChange={(e) => setGroup(e.target.value)}>
                  <option value="">All groups</option>
                  {d.groups.map((g) => <option key={g.key} value={g.key}>{g.title}</option>)}
                </select>
                {filtering && <button type="button" onClick={() => { setState(""); setGroup(""); }}>Show every slot</button>}
              </div>
              {!filtering && d.biggestUnknowns.length > 0 && (
                <section aria-labelledby="records-unknowns" className="record-unknowns">
                  <h2 id="records-unknowns">The biggest unknowns first</h2>
                  <ol>
                    {d.biggestUnknowns.map((u) => (
                      <li key={u.key}><a href={slotRoute(u.key)}>{u.title}</a> <span className="muted">{u.why}{u.blocks.length > 0 ? `; ${u.blocks.length} other ${u.blocks.length === 1 ? "slot waits" : "slots wait"} on it` : ""}</span></li>
                    ))}
                  </ol>
                </section>
              )}
              {shown.length === 0 && <p className="muted" role="status">No slot is {state ? word(state) : "in that group"}.</p>}
              {shown.map((g, i) => (
                <details key={g.key} className="record-group" open={groupOpen(g, filtering, i === 0)}>
                  <summary><h2>{g.title}</h2> <span className="muted">{g.slots.length} {g.slots.length === 1 ? "slot" : "slots"}{g.law ? `, ${g.law}` : ""}; {g.counts.held} held back, {g.counts.answered} answered</span></summary>
                  <div className="record-scroll">
                    <table className="record-table">
                      <caption className="sr-only">{g.title}: {g.slots.length} slots, by state</caption>
                      <thead><tr><th scope="col">Slot</th><th scope="col">State</th><th scope="col">Files</th><th scope="col">Required by</th><th scope="col">Next step</th></tr></thead>
                      <tbody>
                        {g.slots.map((s) => (
                          <tr key={s.key} data-slot={s.key}>
                            <th scope="row" data-label="Slot">
                              <a href={slotRoute(s.key)}>{s.title}</a>
                              <br /><span className="muted">{CARDINALITY[s.cardinality]}{s.closed ? ", closed: this is all" : ""}</span>
                              {s.hidden && <><br /><span className="muted">hidden by the profile: {s.hidden}</span></>}
                            </th>
                            <td data-label="State">
                              <SlotWord state={s.state} word={s.stateWord} />
                              {s.collision && <><br /><Badge tone="warn" glyph="triangle-alert">two holders</Badge></>}
                              {s.problem && <p className="record-problem">{s.problem}</p>}
                              {s.cardinality === "series" && s.periods.length > 0 && (
                                <ul className="record-periods" aria-label={`Periods of ${s.title}`}>
                                  {s.periods.map((p) => <li key={p.period}>{p.period}: <SlotWord state={p.state} /></li>)}
                                </ul>
                              )}
                            </td>
                            <td data-label="Files">{s.pins}{s.held > 0 ? `, ${s.held} held back` : ""}{s.candidates > 0 ? `, ${s.candidates} candidates` : ""}</td>
                            <td data-label="Required by">{s.requires.join(", ") || <span className="muted">jason's own design</span>}</td>
                            <td data-label="Next step">{nextStep(s)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </details>
              ))}
              {d.notes && d.notes.length > 0 && <ul className="muted record-notes">{d.notes.map((n) => <li key={n}>{n}</li>)}</ul>}
              <Caveats items={d.caveats} />
            </>
          );
        }}
      </RemoteView>
    </div>
  );
}

function Section({ title, children, id }: { title: string; children: ReactNode; id?: string }) {
  const h = useId();
  return <section className="record-section" aria-labelledby={`${h}-h`} id={id}><h2 id={`${h}-h`}>{title}</h2>{children}</section>;
}

function Dl({ rows }: { rows: [string, ReactNode][] }) {
  return <dl className="record-facts">{rows.filter(([, v]) => v !== "" && v !== null && v !== undefined && v !== false).map(([k, v]) => (<div key={k}><dt>{k}</dt><dd>{v}</dd></div>))}</dl>;
}

/** What jason found in the pinned file, as the four lines of every pick: you picked X for Y; jason read it as Z, by which readers;
 * what it found; and what you confirm. The split proposal and a changed mark are shown here; their acts are on the holder. */
function Reading({ holder, slot }: { holder: Holder; slot: SlotPageData }) {
  const rb = holder.readback;
  if (!rb) {
    return <p className="muted record-reading">jason has not read this file yet.{holder.reading.readsAs ? ` The library has it as ${holder.reading.readsAs.replace(/_/g, " ")}.` : ""}</p>;
  }
  const verdict = holder.wrongSlot ? "differs" : rb.readsAs ? "agrees" : "unclassified";
  const readers = Object.entries(rb.readers ?? {}).map(([k, v]) => `${k}: ${v ? v.replace(/_/g, " ") : "no reading"}`);
  const pre = rb.preflight;
  return (
    <div className="record-reading">
      <p>
        You picked <strong>{holder.name}</strong> for <strong>{slot.title}</strong>; jason read it as{" "}
        <strong>{rb.readsAs ? rb.readsAs.replace(/_/g, " ") : "nothing it could tell"}</strong>
        {rb.tier ? <> ({rb.tier}{readers.length ? `; ${readers.join("; ")}` : ""})</> : null}.{" "}
        <Badge tone={verdict === "agrees" ? "good" : verdict === "differs" ? "bad" : "warn"} glyph={verdict === "agrees" ? "circle-check" : verdict === "differs" ? "triangle-alert" : "circle-dashed"}>{verdict}</Badge>
        {verdict === "unclassified" && " It stays unclassified until a person says what it is."}
      </p>
      <Dl rows={[
        ["Read", `${rb.readAt.slice(0, 10)}${rb.readBy ? ` by ${rb.readBy}` : ""}`],
        ["File", `${sizeWords(rb.size)}${rb.type ? `, ${rb.type}` : ""}${rb.sha256 ? `, hash ${rb.sha256}` : ""}`],
        ["Text", rb.text?.chars !== undefined ? `${rb.text.chars} characters${rb.text.source ? ` from ${rb.text.source}` : ""}` : ""],
        ["Pages", pre ? `${pre.pages}${pre.blank ? `, ${pre.blank} blank` : ""}${pre.marked ? `, ${pre.marked} marked` : ""}${pre.withText !== undefined ? `, ${pre.withText} with a text layer` : ""}${typeof pre.suspectShare === "number" ? `, ${Math.round(pre.suspectShare * 100)}% of the text layer doubtful` : ""}` : ""],
        ["Already filed", rb.alreadyFiled ? "the library already holds these bytes" : ""],
      ]} />
      {pre?.locked && <p className="notice notice-warn" role="note">{pre.note}</p>}
      {pre && pre.recommend.length > 0 && <ul className="muted">{pre.recommend.map((x) => <li key={`${x.action}-${x.pages}`}>{x.action} pages {x.pages}: {x.reason}</li>)}</ul>}
      {rb.held ? <p className="muted">Its findings are held back outside the private view.</p> : rb.findings.length > 0 && (
        <ul className="record-findings" aria-label="What jason found">{rb.findings.map((f) => <li key={f.code + f.text}><strong>{f.code}</strong>: {f.text}</li>)}</ul>
      )}
      {rb.segments && rb.segments.proposes && (
        <div className="record-proposal">
          <h4>A combined scan: {rb.segments.documents} documents proposed</h4>
          <table>
            <caption className="sr-only">The proposed split</caption>
            <thead><tr><th scope="col">Pages</th><th scope="col">Read as</th><th scope="col">Fits</th><th scope="col">Status</th></tr></thead>
            <tbody>
              {rb.segments.proposal.map((p) => (
                <tr key={p.segment}>
                  <td>{p.pages[0]} to {p.pages[1]}</td><td>{p.kind ? p.kind.replace(/_/g, " ") : "unclassified"} <span className="muted">({p.tier})</span></td>
                  <td>{p.slots.map((s) => s.title).join(", ") || "no slot"}</td>
                  <td>{p.confirmed ? `confirmed${p.confirmedBy ? ` by ${p.confirmedBy}` : ""}` : "proposed only"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {rb.split?.declined && <p>Declined by {rb.split.declined.by}, {rb.split.declined.at}: the file is one document.</p>}
          {rb.split && rb.split.confirmed.length > 0 && (
            <ul>{rb.split.confirmed.map((c) => <li key={c.segment}>Part {c.segment} confirmed into <code>{c.slot}</code> by {c.by}, {c.at}.</li>)}</ul>
          )}
          <p className="muted">{rb.segments.note ?? "A proposal only: no slot is filled until a person confirms the split."}</p>
        </div>
      )}
      {rb.changed && (
        <div className="notice notice-warn" role="alert">
          <strong>The file changed since it was read.</strong>{" "}
          {rb.changed.diff && rb.changed.diff.length > 0
            ? rb.changed.diff.map((x) => `${x.fact}: ${String(x.before ?? "none")} to ${String(x.after ?? "none")}`).join("; ")
            : "Its bytes are different."}
        </div>
      )}
      {!rb.changed && rb.acknowledged ? <p className="muted">The change was seen{typeof rb.acknowledged === "object" && rb.acknowledged.by ? ` by ${rb.acknowledged.by}` : ""}.</p> : null}
    </div>
  );
}

function WrongSlotNotice({ holder, slot, open }: { holder: Holder; slot: SlotPageData; open: (p: Panel) => void }) {
  const w = holder.wrongSlot;
  if (!w) return null;
  const tier = holder.readback?.tier;
  return (
    <div className="notice notice-error record-wrong" role="alert">
      <div>
        <strong>This may be the wrong slot.</strong> You picked <strong>{holder.name}</strong> for {slot.title}. jason reads it as {w.readsAs.replace(/_/g, " ")}{tier ? ` (${tier})` : ""}; this slot expects {w.expects.map((k) => k.replace(/_/g, " ")).join(" or ")}.
        {w.fits.length > 0 ? ` It fits: ${w.fits.map((f) => f.title).join(", ")}.` : " jason found no slot it fits."} Nothing is changed until you choose.
      </div>
      <div className="row wrap">
        {w.fits.length > 0 && <button type="button" onClick={() => open({ kind: "repin", pin: holder.pin })}>Pin it to {w.fits[0].title}{w.fits.length > 1 ? " or another" : " instead"}</button>}
        <button type="button" onClick={() => open({ kind: "keep", pin: holder.pin })}>Keep it here anyway</button>
        {slot.acts.unpin && holder.origin === "person" && <button type="button" onClick={() => open({ kind: "unpin", pin: holder.pin })}>Unpin</button>}
      </div>
    </div>
  );
}

function HolderCard({ holder, slot, open }: { holder: Holder; slot: SlotPageData; open: (p: Panel) => void }) {
  const mine = holder.origin === "person";
  const rb = holder.readback;
  return (
    <li className="record-holder" data-pin={holder.pin}>
      <div className="record-holder-head">
        <strong className="record-holder-name">{holder.name}</strong>
        <SlotWord state={holder.state} word={holder.stateWord} />
        {holder.held && <Badge tone="neutral" glyph="lock">held back</Badge>}
        {holder.kept && <Badge tone="warn" glyph="shield-check">kept by a person</Badge>}
      </div>
      <p className="muted">
        {mine ? `Pinned by ${holder.by || "a person"}, ${holder.at}` : "Pinned by the specification"}
        {holder.period ? `, for ${holder.period}` : ""} · {holder.kind === "drive" ? "a Drive file" : holder.kind === "file" ? "a file in jason's store" : holder.kind === "library" ? "a file in the library" : "a folder"}
        {holder.source ? ` · ${holder.source}` : ""}{holder.opens ? ` · ${holder.opens}` : ""}
      </p>
      {holder.problem && <p className="record-problem" role="note">{holder.problem}</p>}
      {holder.kept && <p>Kept here by {holder.kept.by}, {holder.kept.at}{holder.kept.reason ? `: ${holder.kept.reason}` : ""}. jason still reads it as {holder.kept.readsAs.replace(/_/g, " ")}.</p>}
      {holder.note && <p className="muted">Note: {holder.note}</p>}
      <WrongSlotNotice holder={holder} slot={slot} open={open} />
      <Reading holder={holder} slot={slot} />
      <div className="row wrap record-holder-acts">
        {slot.acts.read && holder.kind !== "folder" && <button type="button" onClick={() => open({ kind: "read", pin: holder.pin })} aria-label={`${rb ? "Read again" : "Read"}: ${holder.name}`}>{rb ? "Read again" : "Read"}</button>}
        {rb?.split?.open && <>
          <button type="button" onClick={() => open({ kind: "split", pin: holder.pin })} aria-label={`Confirm the split of ${holder.name}`}>Confirm the split</button>
          <button type="button" onClick={() => open({ kind: "decline", pin: holder.pin })} aria-label={`Decline the split of ${holder.name}`}>Decline the split</button>
        </>}
        {rb?.changed && slot.acts.ack && <button type="button" onClick={() => open({ kind: "ack", pin: holder.pin })} aria-label={`Acknowledge the change to ${holder.name}`}>I have seen the change</button>}
        {mine && <button type="button" onClick={() => open({ kind: "replace", pin: holder.pin })} aria-label={`Replace ${holder.name}`}>Replace</button>}
        {mine && slot.acts.unpin && <button type="button" onClick={() => open({ kind: "unpin", pin: holder.pin })} aria-label={`Unpin ${holder.name}`}>Unpin</button>}
      </div>
    </li>
  );
}

function BindAsk({ title, onGo, onCancel }: { title: string; onGo: (ref: string) => void; onCancel: () => void }) {
  const id = useId();
  const [ref, setRef] = useState("");
  const head = useRef<HTMLHeadingElement | null>(null);
  useEffect(() => { head.current?.focus(); }, []);
  return (
    <section className="record-act" aria-label={`Bind a folder to ${title}`}>
      <h3 tabIndex={-1} ref={head}>Bind a Drive folder to {title}</h3>
      <div className="record-field"><label htmlFor={id}>Drive folder link or id</label><input id={id} value={ref} onChange={(e) => setRef(e.target.value)} autoComplete="off" /></div>
      <p className="muted">The folder's files become candidates for this slot. For a Civil Code 5200 record the preview shows the sync rule a person could add to the profile; nothing is applied here.</p>
      <div className="row wrap"><button type="button" className="primary" disabled={!ref.trim()} onClick={() => onGo(ref.trim())}>Continue to the preview</button><button type="button" onClick={onCancel}>Cancel</button></div>
    </section>
  );
}

function StandingBlock({ s }: { s: SlotPageData["standing"] }) {
  return (
    <div className="record-standing">
      <h3>Duties that rest on this record</h3>
      {s.duties.length === 0 ? <p className="muted">No duty in jason's list rests on this record.</p> : (
        <ul>{s.duties.map((d) => <li key={d.anchor}><strong>{d.anchor}</strong>: {d.keeps} <span className="muted">({d.cadence}{d.when ? `, ${d.when}` : ""}; {d.because})</span> <code>{d.command}</code></li>)}</ul>
      )}
      <h3>Recorded conflicts that cite what this record requires</h3>
      {s.conflicts.held ? <p className="muted">{s.conflicts.count} recorded {s.conflicts.count === 1 ? "conflict" : "conflicts"}, held back with this confidential slot.</p>
        : s.conflicts.items.length === 0 ? <p className="muted">None recorded.</p> : (
          <ul>{s.conflicts.items.map((c) => <li key={c.key}><strong>{c.provision}</strong> against {c.authority} <span className="muted">({c.status}, {c.clarity}{c.open ? ", open" : ""}; {c.because}{c.boardItem ? `; board item ${c.boardItem}` : ""})</span></li>)}</ul>
        )}
      <h3>Programs</h3>
      <p className="muted">{s.programs.available ? "" : `Unavailable: ${s.programs.why}.`}</p>
      {s.caveats.map((c) => <p key={c} className="muted">{c}</p>)}
    </div>
  );
}

/** One slot (`#/setup/records/<key>`): the law that requires it, what holds it and what jason read, the person's answer, the
 * standing block, the acts, and the trail. Every act is a preview, then a confirm in the signed-in person's name. */
function SlotScreen({ slotKey }: { slotKey: string }) {
  const r = useApi<SlotPageData>(`/api/record-slot?key=${encodeURIComponent(slotKey)}`);
  const { me } = useSession([]);
  const [panel, setPanel] = useState<Panel | null>(null);
  const [notice, setNotice] = useState<{ text: string; job?: number; command?: string; bad?: boolean } | null>(null);
  const opener = useRef<HTMLElement | null>(null);
  const status = useRef<HTMLDivElement | null>(null);
  const open = (p: Panel) => { opener.current = document.activeElement as HTMLElement | null; setNotice(null); setPanel(p); };
  const close = (nothing = false) => {
    setPanel(null);
    if (nothing) setNotice({ text: "Nothing was picked." });
    requestAnimationFrame(() => opener.current?.focus());
  };
  const done = (out: Plan) => {
    setPanel(null);
    const bits = [`Recorded as ${me}.`];
    if (out.declined) bits.push("The proposed split was declined.");
    if (out.filled) bits.push(`${out.filled.length} ${out.filled.length === 1 ? "part was" : "parts were"} filled.`);
    if (out.replaced) bits.push("The new file is pinned and the old one unpinned.");
    if (out.partial) bits.push(out.why ?? "Only half of the replace was written.");
    if (out.notQueued && out.notQueued.length > 0) bits.push("A part could not be queued for reading; read it by hand.");
    if (out.job) bits.push(`The reading is queued as job ${out.job}.`);
    bits.push("Nothing in Drive was changed.");
    setNotice({ text: bits.join(" "), job: out.job, command: out.command, bad: !!out.partial });
    r.reload();
    requestAnimationFrame(() => status.current?.focus());
  };
  return (
    <div className="stack records-view">
      <p className="record-back"><a href={LIST_ROUTE}>Back to the records checklist</a></p>
      <div ref={status} tabIndex={-1} className="record-status" role="status" aria-live="polite">
        {notice && <><p className={notice.bad ? "notice notice-warn" : "notice notice-good"}>{notice.text}</p>
          {notice.job ? <JobWatch id={notice.job} command={notice.command} onFinished={() => r.reload()} /> : null}</>}
      </div>
      <RemoteView r={r}>
        {(d) => {
          const holders = d.holders;
          const person = d.holders.find((h) => h.pin === (panel && "pin" in panel ? panel.pin : ""));
          const common = { data: d, by: me, onDone: done, onCancel: () => close() };
          const hp = person ? { ...common, holder: person } : null;
          const chooserSlot = { key: d.key, title: d.title, cardinality: d.cardinality, source: d.source };
          const answered = d.existence.answer;
          return (
            <>
              <ScreenHeader title={d.title} summary={<><SlotWord state={d.state} word={d.stateWord} /> {CARDINALITY[d.cardinality]}{d.shelf.length ? `; shelf: ${d.shelf.join(", ")}` : ""}</>} />
              {d.hidden && <p className="notice notice-warn" role="note">Hidden by the profile: {d.hidden}</p>}
              <Section title="What requires it">
                {d.requires.length > 0 ? <p>{d.requires.map((c) => <code key={c} className="chip">{c}</code>)}</p> : <p className="muted">No law is named. jason's own design needs this record.</p>}
                {d.why && <p>{d.why}</p>}
                <p className="muted">The words of a statute come from <code>jason cite</code>, not from this page.</p>
                {d.problem && <p className="record-problem">{d.problem}</p>}
              </Section>
              {d.collisions.map((c) => (
                <div key={c.period ?? c.slot} className="notice notice-warn" role="alert">
                  <strong>Two holders{c.period ? ` for ${c.period}` : ""}.</strong> {c.note} {c.holders.map((h) => `${h.origin === "specification" ? "the specification" : h.by || "a person"} (${h.source})`).join(" and ")}.
                  {" "}Unpin the one that is not current.
                </div>
              ))}
              <Section title={`What holds it (${holders.length})`}>
                {holders.length === 0 ? <p className="muted">{d.holding ? `The specification pins a folder: ${d.holding}.` : "No file is pinned for this slot."}</p> : (
                  <ul className="record-holders">{holders.map((h) => <HolderCard key={h.pin} holder={h} slot={d} open={open} />)}</ul>
                )}
                {d.specificationFolders.length > 0 && <p className="muted">Folders the specification pins: {d.specificationFolders.map((f) => f.folder).join(", ")}.</p>}
              </Section>
              <Section title="Your answer">
                {answered ? (
                  <p><SlotWord state={answered.answer === "none" ? "doesNotExist" : answered.answer === "waiting" ? "waiting" : "notApplicable"} word={answered.word} /> by {answered.by}, {answered.at}{answered.who ? `, waiting on ${answered.who}` : ""}{answered.reason ? `: ${answered.reason}` : ""}{answered.held ? " (words held back outside the private view)" : ""}</p>
                ) : <p className="muted">{d.existence.possible ? "Nobody has said whether the association holds one. Empty is not the same as none." : "This record cannot honestly be answered as none."}</p>}
                {d.more && <p>Is there another? {d.more.complete ? <>This is all, said by {d.more.by}, {d.more.at}.</> : <>Yes, said by {d.more.by}, {d.more.at}.</>}</p>}
                <div className="row wrap">
                  {d.acts.answer && <button type="button" onClick={() => open({ kind: "answer" })}>Answer: none, not applicable, or waiting</button>}
                  {d.acts.more && !d.more?.complete && <><button type="button" onClick={() => open({ kind: "more", value: "yes" })}>There is another</button><button type="button" onClick={() => open({ kind: "more", value: "no" })}>This is all</button></>}
                  {d.acts.reopen && answered && <button type="button" onClick={() => open({ kind: "reopen", what: "answer" })}>Reopen the answer</button>}
                  {d.acts.reopen && d.more?.complete && <button type="button" onClick={() => open({ kind: "reopen", what: "more" })}>Reopen the set</button>}
                </div>
              </Section>
              <Section title="Choose a file" id="records-acts">
                <div className="row wrap">
                  {d.acts.pickFile && <button type="button" className="primary" onClick={() => open({ kind: "chooser", tab: "drive" })}>Choose from Drive</button>}
                  {d.acts.pickFile && <button type="button" onClick={() => open({ kind: "chooser", tab: "paste" })}>Paste a link</button>}
                  {d.acts.upload && <button type="button" onClick={() => open({ kind: "chooser", tab: "upload" })}>Upload from this computer</button>}
                  {d.acts.pickFolder && <button type="button" onClick={() => open({ kind: "bind" })}>Bind a Drive folder</button>}
                </div>
                {!d.acts.pickFile && d.acts.why && <p className="muted">{d.acts.why}</p>}
                <p className="muted">A pick records which file you mean. It moves, copies, renames, and shares nothing. jason reads the file only when you ask.</p>
                {panel && panel.kind !== "chooser" && (
                  <div className="record-panel">
                    {panel.kind === "answer" && <AnswerPanel {...common} />}
                    {panel.kind === "more" && <MorePanel {...common} value={panel.value} />}
                    {panel.kind === "reopen" && <ReopenPanel {...common} what={panel.what} />}
                    {panel.kind === "bind" && <BindAsk title={d.title} onGo={(ref) => setPanel({ kind: "step", step: { kind: "bind", ref, name: "the folder" } })} onCancel={() => close()} />}
                    {panel.kind === "step" && <StepPanel slot={chooserSlot} step={panel.step} by={me} onDone={done} onBack={() => close()} />}
                    {hp && panel.kind === "read" && <ReadPanel {...hp} />}
                    {hp && panel.kind === "unpin" && <UnpinPanel {...hp} />}
                    {hp && panel.kind === "keep" && <KeepPanel {...hp} />}
                    {hp && panel.kind === "repin" && <RepinPanel {...hp} />}
                    {hp && panel.kind === "replace" && <ReplacePanel {...hp} />}
                    {hp && panel.kind === "split" && <SplitPanel {...hp} />}
                    {hp && panel.kind === "decline" && <DeclinePanel {...hp} />}
                    {hp && panel.kind === "ack" && <AckPanel {...hp} />}
                  </div>
                )}
              </Section>
              {d.bindings.length > 0 && (
                <Section title="Bound folders">
                  <ul>{d.bindings.map((b) => <li key={b.id}>{b.name} <span className="muted">bound by {b.by}, {b.at}. Its files are candidates, never pins.</span></li>)}</ul>
                </Section>
              )}
              {d.candidates.length > 0 && (
                <Section title="Files jason classified for this slot">
                  <ul>{d.candidates.map((c) => (
                    <li key={c.ref}>{c.name} <span className="muted">{c.why}</span>{" "}
                      {d.acts.pickFile && <button type="button" onClick={() => open({ kind: "step", step: { kind: "pick", ref: c.ref, name: c.name } })} aria-label={`Pin ${c.name} to ${d.title}`}>Pin it</button>}</li>
                  ))}</ul>
                </Section>
              )}
              <Section title="Standing"><StandingBlock s={d.standing} /></Section>
              <Section title="History">
                {d.log.length === 0 ? <p className="muted">No act is recorded for this slot yet.</p> : (
                  <table className="record-log">
                    <caption className="sr-only">Acts on this slot</caption>
                    <thead><tr><th scope="col">Day</th><th scope="col">Who</th><th scope="col">Act</th><th scope="col">Pin</th></tr></thead>
                    <tbody>{d.log.map((l, i) => <tr key={i}><td>{String(l.at ?? "").slice(0, 10)}</td><td>{l.by}</td><td>{l.act}</td><td>{l.pin ?? ""}</td></tr>)}</tbody>
                  </table>
                )}
                <p className="muted">The trail is never emptied. A file's name is not in it.</p>
              </Section>
              <details className="record-commands"><summary>The same acts in a terminal</summary>
                <ul>{Object.entries(d.commands).map(([k, v]) => <li key={k}><code>{v}</code></li>)}</ul></details>
              <Caveats items={d.caveats} />
              {panel?.kind === "chooser" && (
                <DriveChooser slot={chooserSlot} by={me} startTab={panel.tab} onClose={() => close(true)} onDone={done} />
              )}
            </>
          );
        }}
      </RemoteView>
    </div>
  );
}

/** Setup > Records, both screens: `#/setup/records` is the checklist and `#/setup/records/<key>` one slot (the key URL-encoded,
 * slashes and all). A file's name or id is never in a route. */
export function RecordsView() {
  const [hash] = useHash("setup/records");
  const { key, query } = parseRoute(hash);
  return key ? <SlotScreen key={key} slotKey={key} /> : <ChecklistScreen query={query} />;
}
