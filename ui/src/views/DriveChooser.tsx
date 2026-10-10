import { useEffect, useId, useRef, useState } from "react";
import { Glyph } from "../components/Glyph";
import { postJson } from "../lib/api";
import { ActPanel, useFileBytes, useUploadCap } from "./RecordActs";
import { sizeWords, type Cardinality, type DriveItem, type DriveListing, type DriveResolved, type Plan } from "./recordTypes";

export interface ChooserSlot { key: string; title: string; cardinality: Cardinality; source: string }
export type ChooserTab = "drive" | "paste" | "upload";

const TABS: { id: ChooserTab; label: string }[] = [
  { id: "drive", label: "Drive" }, { id: "paste", label: "Paste a link" }, { id: "upload", label: "From this computer" },
];

export interface Step { kind: "pick" | "bind"; ref: string; name: string }

/** The fields every pick shares: the period of a series, the instrument number of a repeating key document, and a note. */
function PickFields({ slot, period, setPeriod, entry, setEntry, note, setNote }: {
  slot: ChooserSlot; period: string; setPeriod: (s: string) => void; entry: string; setEntry: (s: string) => void; note: string; setNote: (s: string) => void;
}) {
  const id = useId();
  return (
    <div className="record-fields">
      {slot.cardinality === "series" && (
        <div className="record-field"><label htmlFor={`${id}-p`}>Period this file is for (required, for example 2099-06)</label>
          <input id={`${id}-p`} value={period} onChange={(e) => setPeriod(e.target.value)} autoComplete="off" /></div>
      )}
      {slot.cardinality === "several" && slot.source === "key documents" && (
        <div className="record-field"><label htmlFor={`${id}-e`}>Instrument's recording number (only for a repeating key document)</label>
          <input id={`${id}-e`} value={entry} onChange={(e) => setEntry(e.target.value)} autoComplete="off" /></div>
      )}
      <div className="record-field"><label htmlFor={`${id}-n`}>Note (optional; no names or secrets)</label>
        <input id={`${id}-n`} value={note} onChange={(e) => setNote(e.target.value)} autoComplete="off" /></div>
    </div>
  );
}

/** The last step of choosing: the pick (or the folder binding) as a preview then a confirm. A pick records an intention. It moves,
 * copies, renames, and shares nothing. */
export function StepPanel({ slot, step, by, onDone, onBack }: { slot: ChooserSlot; step: Step; by: string; onDone: (p: Plan) => void; onBack: () => void }) {
  const [period, setPeriod] = useState("");
  const [entry, setEntry] = useState("");
  const [note, setNote] = useState("");
  const bind = step.kind === "bind";
  return (
    <ActPanel
      slot={slot.key} by={by} onDone={onDone} onCancel={onBack}
      title={bind ? `Bind the folder ${step.name} to ${slot.title}` : `Pick ${step.name} for ${slot.title}`}
      body={() => bind ? { act: "bind", folder: step.ref, note } : { act: "pick", file: step.ref, period, entry, note }}
      ready={bind || slot.cardinality !== "series" || !!period.trim()} whyNot="Name the period this file is for."
      previewLabel={bind ? "Preview the binding" : "Preview the pick"}
      confirmLabel={bind ? `Bind ${step.name} to ${slot.title}` : `Pin ${step.name} to ${slot.title}`}
      watch={[period, entry, note, step.ref]}
    >
      <p className="muted">{bind
        ? "A binding makes the folder's files candidates for this slot. Nothing is pinned, filed, or moved, and no rule is applied."
        : "This records a pick. It moves, copies, renames, and shares nothing in Drive."}</p>
      {!bind && <PickFields slot={slot} period={period} setPeriod={setPeriod} entry={entry} setEntry={setEntry} note={note} setNote={setNote} />}
      {bind && <div className="record-field"><label htmlFor="bind-note">Note (optional)</label><input id="bind-note" value={note} onChange={(e) => setNote(e.target.value)} autoComplete="off" /></div>}
    </ActPanel>
  );
}

function itemNotes(it: DriveItem): string[] {
  const out: string[] = [];
  if (it.jason?.inLibrary) out.push(`already in the library as ${it.jason.inLibrary.replace(/_/g, " ")}`);
  else if (it.jason?.kind) out.push(`jason reads it as ${it.jason.kind.replace(/_/g, " ")}`);
  if (it.jason?.ruleCovers) out.push("in a folder a sync rule covers");
  if (it.jason?.pinnedFor?.length) out.push(`pinned for ${it.jason.pinnedFor.join(", ")}`);
  if (it.doc) out.push(it.doc);
  if (it.opens) out.push(it.opens);
  return out;
}

interface Crumb { id: string; name: string; drive: string }

function NotConnected({ d }: { d: { why?: string; command?: string } }) {
  return (
    <div className="notice notice-warn" role="alert">
      <p>{d.why ?? "jason cannot read Drive."}</p>
      {d.command && <p>A person runs <code>{d.command}</code> in a terminal. The upload tab still works.</p>}
    </div>
  );
}

function DriveTab({ slot, onPick, onBind }: { slot: ChooserSlot; onPick: (it: DriveItem) => void; onBind: (c: Crumb) => void }) {
  const [crumbs, setCrumbs] = useState<Crumb[]>([]);
  const [listing, setListing] = useState<DriveListing | null>(null);
  const [items, setItems] = useState<DriveItem[]>([]);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");
  const [q, setQ] = useState("");
  const [searched, setSearched] = useState("");
  const [selected, setSelected] = useState<DriveItem | null>(null);
  const [said, setSaid] = useState("");
  const id = useId();

  const run = async (path: "list" | "search", payload: Record<string, unknown>, append: boolean, label: string) => {
    setBusy(true); setError(""); setSelected(null);
    try {
      const out = await postJson<DriveListing>(`/api/write/drive/${path}`, payload);
      setListing(out);
      const got = out.items ?? [];
      setItems((prev) => (append ? [...prev, ...got] : got));
      if (out.found) setSaid(`${label}, ${got.length + (append ? 0 : out.drives?.length ?? 0)} items`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const open = (trail: Crumb[], page = "") => {
    setCrumbs(trail); setSearched("");
    const top = trail[trail.length - 1];
    void run("list", top ? { parent: top.id, drive: top.drive, page } : { page }, !!page, top ? `Opened ${top.name}` : "Opened My Drive");
  };
  useEffect(() => { open([]); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);
  const search = () => { setCrumbs([]); setSearched(q.trim()); void run("search", { q: q.trim() }, false, "Search done"); };
  const more = () => {
    const page = listing?.next ?? "";
    if (searched) void run("search", { q: searched, page }, true, "More results");
    else open(crumbs, page);
  };
  const here = crumbs[crumbs.length - 1];
  const unavailable = listing && !listing.found && listing.driveConnected === false;

  return (
    <div className="record-drive">
      <form className="record-search" role="search" onSubmit={(e) => { e.preventDefault(); if (q.trim()) search(); }}>
        <label htmlFor={`${id}-q`}>Search by file name</label>
        <div className="row wrap">
          <input id={`${id}-q`} type="search" value={q} onChange={(e) => setQ(e.target.value)} autoComplete="off" />
          <button type="submit" disabled={busy || q.trim().length < 2}>Search</button>
          {searched && <button type="button" onClick={() => { setQ(""); open([]); }}>Back to folders</button>}
        </div>
        <p className="muted">The name goes to Google in a request body and never sits in a web address.</p>
      </form>
      {listing?.account && <p className="muted">jason's Drive account ({listing.account}) can see these files. A file it cannot see is not listed: share it with that account, or upload it.</p>}
      {!searched && !unavailable && (
        <nav aria-label="Folder path" className="record-crumbs">
          <button type="button" onClick={() => open([])} aria-current={crumbs.length === 0 ? "page" : undefined}>My Drive</button>
          {crumbs.map((c, i) => (
            <span key={`${c.id}-${i}`}> <span aria-hidden="true">/</span>{" "}
              <button type="button" onClick={() => open(crumbs.slice(0, i + 1))} aria-current={i === crumbs.length - 1 ? "page" : undefined}>{c.name}</button></span>
          ))}
        </nav>
      )}
      <div className="sr-only" role="status" aria-live="polite">{said}</div>
      {busy && <p className="muted" role="status">Loading the folder</p>}
      {error && <p className="notice notice-error" role="alert">{error} Nothing was picked.</p>}
      {unavailable && <NotConnected d={listing} />}
      {listing && !listing.found && !unavailable && <p className="notice notice-warn" role="alert">{listing.why} Nothing was picked.</p>}
      {listing?.found && (
        <>
          {!searched && crumbs.length === 0 && (listing.drives?.length ?? 0) > 0 && (
            <ul className="record-files" aria-label="Shared drives">
              {listing.drives?.map((d) => (
                <li key={d.id}><button type="button" className="link" onClick={() => open([{ id: d.id, name: d.name, drive: d.id }])}><Glyph name="folder" size="1em" /> {d.name}</button> <span className="muted">shared drive</span></li>
              ))}
            </ul>
          )}
          {items.length > 0 && (
            <fieldset className="record-files-set">
              <legend className="sr-only">Files in this folder</legend>
              <ul className="record-files">
                {items.map((it, i) => {
                  const notes = itemNotes(it);
                  const rid = `${id}-f${i}`;
                  if (it.type === "folder") {
                    return (
                      <li key={`${it.id}-${i}`}>
                        <button type="button" className="link" onClick={() => open([...crumbs, { id: it.id, name: it.name, drive: here?.drive ?? "" }])} aria-label={`Open the folder ${it.name}`}><Glyph name="folder" size="1em" /> {it.name}</button>{" "}
                        <span className="muted">folder · {it.modified}</span>
                      </li>
                    );
                  }
                  const ok = it.readable && !!it.id;
                  return (
                    <li key={`${it.id}-${i}`} className={ok ? undefined : "record-file-off"}>
                      <input type="radio" id={rid} name={`${id}-pick`} disabled={!ok} checked={selected === it} onChange={() => setSelected(it)} />{" "}
                      <label htmlFor={rid}>
                        <span className="record-file-name">{it.name}</span>{" "}
                        <span className="muted">{it.type}, {sizeWords(it.size)}, modified {it.modified}{it.owner ? `, owner ${it.owner}` : ""}</span>
                      </label>
                      {selected === it && <span className="record-selected"> selected</span>}
                      {!it.readable && <p className="record-file-why">jason cannot open this file{it.why ? `: ${it.why}` : ""}. Share it with the account shown, or upload it.</p>}
                      {notes.length > 0 && <p className="muted record-file-notes">{notes.join(" · ")}</p>}
                    </li>
                  );
                })}
              </ul>
            </fieldset>
          )}
          {listing.empty && items.length === 0 && <p className="muted">{listing.empty}</p>}
          {listing.next && <button type="button" onClick={more} disabled={busy}>Show more</button>}
        </>
      )}
      <div className="record-chooser-foot row wrap">
        <span role="status">{selected ? `1 file selected for ${slot.title}: ${selected.name}` : `No file selected for ${slot.title}`}</span>
        <button type="button" className="primary" disabled={!selected} onClick={() => selected && onPick(selected)}>Pick</button>
        {here && !searched && <button type="button" onClick={() => onBind(here)}>Choose this folder for {slot.title}</button>}
      </div>
    </div>
  );
}

function PasteTab({ slot, onPick, onBind }: { slot: ChooserSlot; onPick: (ref: string, name: string) => void; onBind: (ref: string, name: string) => void }) {
  const id = useId();
  const [ref, setRef] = useState("");
  const [found, setFound] = useState<DriveResolved | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const look = async () => {
    setBusy(true); setError(""); setFound(null);
    try { setFound(await postJson<DriveResolved>("/api/write/drive/resolve", { ref: ref.trim() })); } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };
  const unavailable = found && !found.found && found.driveConnected === false;
  return (
    <div className="record-paste">
      <form onSubmit={(e) => { e.preventDefault(); if (ref.trim()) void look(); }}>
        <div className="record-field"><label htmlFor={`${id}-r`}>Drive link or id</label>
          <input id={`${id}-r`} value={ref} onChange={(e) => { setRef(e.target.value); setFound(null); }} autoComplete="off" /></div>
        <div className="row wrap"><button type="submit" disabled={busy || !ref.trim()}>Look it up</button>
          <span className="muted">jason reads the name and size only, then you preview the pick. The link is sent in a request body, never in a web address.</span></div>
      </form>
      {error && <p className="notice notice-error" role="alert">{error}</p>}
      {unavailable && <NotConnected d={found} />}
      {found && !found.found && !unavailable && <p className="notice notice-warn" role="alert">{found.why}</p>}
      {found?.found && (
        <div className="record-found" role="status">
          <p>Found: <strong>{found.name}</strong>, {found.kind === "folder" ? "a folder" : `a ${found.type}`}{found.kind === "folder" ? "" : `, ${sizeWords(found.size ?? null)}`}, modified {found.modified}{found.ownerDomain ? `, owned in ${found.ownerDomain}` : ""}.</p>
          {found.readable === false && <p className="notice notice-warn">jason cannot open this file{found.why ? `: ${found.why}` : ""}. Share it with the account shown, or upload it.</p>}
          {found.opens && <p className="muted">{found.opens}</p>}
          {found.doc && <p className="muted">{found.doc}</p>}
          {found.kind === "folder"
            ? (<><p className="muted">{found.offer}</p><button type="button" className="primary" onClick={() => onBind(ref.trim(), found.name ?? "the folder")}>Choose this folder for {slot.title}</button></>)
            : (<button type="button" className="primary" disabled={found.readable === false} onClick={() => onPick(ref.trim(), found.name ?? "the file")}>Pick this file for {slot.title}</button>)}
        </div>
      )}
    </div>
  );
}

function UploadTab({ slot, by, onDone, onCancel }: { slot: ChooserSlot; by: string; onDone: (p: Plan) => void; onCancel: () => void }) {
  const id = useId();
  const cap = useUploadCap();
  const f = useFileBytes();
  const [period, setPeriod] = useState("");
  const [entry, setEntry] = useState("");
  const [note, setNote] = useState("");
  const [allow, setAllow] = useState(false);
  const [allowed, setAllowed] = useState("");
  const [reason, setReason] = useState("");
  const over = cap.bytes !== null && !!f.file && f.file.size > cap.bytes;
  return (
    <ActPanel
      slot={slot.key} by={by} onDone={onDone} onCancel={onCancel} title={`Upload a file for ${slot.title}`}
      body={() => ({ act: "upload", name: f.file?.name, base64: f.file?.base64, period, entry, note, ...(allow ? { override: { allowed, reason } } : {}) })}
      ready={!!f.file && (slot.cardinality !== "series" || !!period.trim()) && (!allow || (!!allowed.trim() && !!reason.trim()))}
      whyNot={!f.file ? "Choose a file first." : slot.cardinality === "series" && !period.trim() ? "Name the period this file is for." : "Give the size you allow and a reason."}
      previewLabel="Preview the upload" confirmLabel={`Keep ${f.file?.name ?? "the file"} and pin it to ${slot.title}`}
      watch={[f.file, period, entry, note, allow, allowed, reason]}
    >
      <div className="record-field">
        <label htmlFor={`${id}-file`}>File (a PDF, an image, or a Word file)</label>
        <input id={`${id}-file`} type="file" accept=".pdf,.png,.jpg,.jpeg,.tif,.tiff,.doc,.docx" onChange={(e) => f.choose(e.target.files?.[0])} />
        <span className="muted">{cap.words ? `The largest file allowed here is ${cap.words}. ` : ""}It is kept in jason's own store, not sent to Drive or anywhere else.</span>
      </div>
      {f.busy && <p role="status" className="muted">Reading the file</p>}
      {f.error && <p className="notice notice-error" role="alert">{f.error}</p>}
      {f.file && <p role="status">Chosen: <strong>{f.file.name}</strong>, {sizeWords(f.file.size)}.</p>}
      {over && <p className="notice notice-warn" role="note">That file is {sizeWords(f.file?.size)}, over the {cap.words} limit. Larger files belong on Drive: share the file with jason's Drive account and pick it. An administrator may allow this one file past the limit (below); the server decides.</p>}
      <PickFields slot={slot} period={period} setPeriod={setPeriod} entry={entry} setEntry={setEntry} note={note} setNote={setNote} />
      <div className="record-field">
        <label><input type="checkbox" checked={allow} onChange={(e) => setAllow(e.target.checked)} /> Allow this one file past the limit (the community's administrator, with a reason)</label>
        {allow && (
          <>
            <label htmlFor={`${id}-a`}>Size to allow, for this file only (for example 200 MB)</label>
            <input id={`${id}-a`} value={allowed} onChange={(e) => setAllowed(e.target.value)} autoComplete="off" />
            <label htmlFor={`${id}-r`}>Reason (kept in the limits record)</label>
            <input id={`${id}-r`} value={reason} onChange={(e) => setReason(e.target.value)} autoComplete="off" />
          </>
        )}
      </div>
    </ActPanel>
  );
}

/** "Choose a file from Drive for THE SLOT": a modal dialog with three sources, each ending in the same preview and confirm. Drive is
 * browsed or searched through jason's own Drive token (a POST for each read, so a name or link is never in a web address); a pasted
 * link is looked up; an upload stays in jason's store. Escape closes it and nothing is picked. */
export function DriveChooser({ slot, by, startTab = "drive", onClose, onDone }: {
  slot: ChooserSlot; by: string; startTab?: ChooserTab; onClose: () => void; onDone: (p: Plan) => void;
}) {
  const id = useId();
  const [tab, setTab] = useState<ChooserTab>(startTab);
  const [step, setStep] = useState<Step | null>(null);
  const dialog = useRef<HTMLDivElement | null>(null);
  const head = useRef<HTMLHeadingElement | null>(null);
  useEffect(() => { head.current?.focus(); }, []);

  const keys = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") { e.stopPropagation(); onClose(); return; }
    if (e.key !== "Tab" || !dialog.current) return;
    const all = Array.from(dialog.current.querySelectorAll<HTMLElement>("button, input, [href], select, textarea, [tabindex]:not([tabindex='-1'])")).filter((el) => !(el as HTMLButtonElement).disabled && el.tabIndex >= 0);
    if (all.length === 0) return;
    const first = all[0], last = all[all.length - 1];
    if (e.shiftKey && (document.activeElement === first || document.activeElement === dialog.current || document.activeElement === head.current)) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  };
  const tabKeys = (e: React.KeyboardEvent) => {
    const i = TABS.findIndex((t) => t.id === tab);
    const next = e.key === "ArrowRight" ? (i + 1) % TABS.length : e.key === "ArrowLeft" ? (i + TABS.length - 1) % TABS.length : e.key === "Home" ? 0 : e.key === "End" ? TABS.length - 1 : -1;
    if (next < 0) return;
    e.preventDefault(); setTab(TABS[next].id);
    requestAnimationFrame(() => document.getElementById(`${id}-t-${TABS[next].id}`)?.focus());
  };

  return (
    <div className="record-overlay" onKeyDown={keys}>
      <div role="dialog" aria-modal="true" aria-labelledby={`${id}-h`} className="record-dialog" ref={dialog}>
        <header className="record-dialog-head">
          <h2 id={`${id}-h`} tabIndex={-1} ref={head}>{`Choose a file from Drive for ${slot.title}`}</h2>
          <button type="button" onClick={onClose} aria-label="Close without picking anything">Close</button>
        </header>
        {step ? (
          <StepPanel slot={slot} step={step} by={by} onDone={onDone} onBack={() => setStep(null)} />
        ) : (
          <>
            <div role="tablist" aria-label="Where the file is" className="record-tabs" onKeyDown={tabKeys}>
              {TABS.map((t) => (
                <button key={t.id} id={`${id}-t-${t.id}`} role="tab" type="button" aria-selected={tab === t.id} aria-controls={`${id}-p-${t.id}`} tabIndex={tab === t.id ? 0 : -1} onClick={() => setTab(t.id)}>{t.label}</button>
              ))}
            </div>
            <div role="tabpanel" id={`${id}-p-${tab}`} aria-labelledby={`${id}-t-${tab}`} className="record-tabpanel">
              {tab === "drive" && <DriveTab slot={slot} onPick={(it) => setStep({ kind: "pick", ref: it.id, name: it.name })} onBind={(c) => setStep({ kind: "bind", ref: c.id, name: c.name })} />}
              {tab === "paste" && <PasteTab slot={slot} onPick={(ref, name) => setStep({ kind: "pick", ref, name })} onBind={(ref, name) => setStep({ kind: "bind", ref, name })} />}
              {tab === "upload" && <UploadTab slot={slot} by={by} onDone={onDone} onCancel={onClose} />}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
