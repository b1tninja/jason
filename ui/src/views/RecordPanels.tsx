import { useId, useState } from "react";
import { ActPanel, useFileBytes } from "./RecordActs";
import { sizeWords, type Holder, type Plan, type SlotPageData } from "./recordTypes";

interface Common { data: SlotPageData; by: string; onDone: (p: Plan) => void; onCancel: () => void }
interface HolderPanel extends Common { holder: Holder }

const label = (h: Holder) => h.name || "the file";

function Field({ label: text, children }: { label: string; children: (id: string) => React.ReactNode }) {
  const id = useId();
  return <div className="record-field"><label htmlFor={id}>{text}</label>{children(id)}</div>;
}

/** "None exists", "not applicable", or "waiting on someone else": a person's answer, with words, in their name. It never fills
 * a slot or hides one, and never sends the request. */
export function AnswerPanel({ data, by, onDone, onCancel }: Common) {
  const [value, setValue] = useState<"none" | "not_applicable" | "waiting">("none");
  const [note, setNote] = useState("");
  const [who, setWho] = useState("");
  const asks = { none: "Where you looked (required)", not_applicable: "Why it does not apply to this association (required)", waiting: "What you asked for, and the day you asked (optional)" };
  const sentence = { none: "does not exist", not_applicable: "does not apply", waiting: `is waiting on ${who.trim() || "someone"}` };
  const ready = value === "waiting" ? !!who.trim() : !!note.trim();
  return (
    <ActPanel
      slot={data.key} by={by} onDone={onDone} onCancel={onCancel} title={`Answer for ${data.title}`}
      body={() => ({ act: "answer", value, note, who })} ready={ready} whyNot={value === "waiting" ? "Say who has it." : "Write the words the answer needs."}
      previewLabel="Preview the answer" confirmLabel={`Record that ${data.title} ${sentence[value]}`} watch={[value, note, who]}
    >
      <fieldset className="record-radios">
        <legend>What is true of this record</legend>
        <label><input type="radio" name="answer" checked={value === "none"} onChange={() => setValue("none")} /> The association holds none (does not exist)</label>
        <label><input type="radio" name="answer" checked={value === "not_applicable"} onChange={() => setValue("not_applicable")} /> It does not apply to this association (not applicable)</label>
        <label><input type="radio" name="answer" checked={value === "waiting"} onChange={() => setValue("waiting")} /> Someone else has it (waiting on someone else)</label>
      </fieldset>
      {value === "waiting" && <Field label="Who has it (required)">{(id) => <input id={id} value={who} onChange={(e) => setWho(e.target.value)} autoComplete="off" />}</Field>}
      <Field label={asks[value]}>{(id) => <textarea id={id} rows={2} value={note} onChange={(e) => setNote(e.target.value)} />}</Field>
      <p className="muted">This is your answer, kept with your name and the day. It does not hide the slot, and it sends no request: a person sends that.</p>
    </ActPanel>
  );
}

/** "Is there another?" for a set that grows. "No" is "this is all", a person's word. */
export function MorePanel({ data, by, onDone, onCancel, value }: Common & { value: "yes" | "no" }) {
  const [note, setNote] = useState("");
  return (
    <ActPanel
      slot={data.key} by={by} onDone={onDone} onCancel={onCancel} title={value === "no" ? `This is all for ${data.title}` : `There is another for ${data.title}`}
      body={() => ({ act: "more", value, note })} ready previewLabel="Preview" confirmLabel={value === "no" ? "Record that this is all" : "Record that there is another"} watch={[value, note]}
    >
      <Field label="Note (optional)">{(id) => <input id={id} value={note} onChange={(e) => setNote(e.target.value)} autoComplete="off" />}</Field>
    </ActPanel>
  );
}

/** Take back a standing answer, or a closed set. The old answer stays in the trail. */
export function ReopenPanel({ data, by, onDone, onCancel, what }: Common & { what: "answer" | "more" }) {
  const [note, setNote] = useState("");
  return (
    <ActPanel
      slot={data.key} by={by} onDone={onDone} onCancel={onCancel} title={what === "answer" ? `Reopen the answer for ${data.title}` : `Reopen the set for ${data.title}`}
      body={() => ({ act: "reopen", what, note })} ready previewLabel="Preview" confirmLabel={what === "answer" ? "Reopen the answer" : "Reopen the set"} watch={[what, note]}
    >
      <p className="muted">The earlier answer stays in the trail, marked reopened. Nothing is deleted.</p>
      <Field label="Why (optional)">{(id) => <input id={id} value={note} onChange={(e) => setNote(e.target.value)} autoComplete="off" />}</Field>
    </ActPanel>
  );
}

/** Take a pick back out of the slot. The pin is marked unpinned with who and when; the file is not touched. */
export function UnpinPanel({ data, holder, by, onDone, onCancel }: HolderPanel) {
  const [note, setNote] = useState("");
  return (
    <ActPanel
      slot={data.key} by={by} onDone={onDone} onCancel={onCancel} title={`Unpin ${label(holder)}`}
      body={() => ({ act: "unpin", pin: holder.pin, note })} ready previewLabel="Preview the unpin" confirmLabel={`Unpin ${label(holder)} from ${data.title}`} watch={[note]}
    >
      <p className="muted">The file is not deleted, moved, or changed. The pin is marked unpinned, with your name and the day.</p>
      <Field label="Why (optional)">{(id) => <input id={id} value={note} onChange={(e) => setNote(e.target.value)} autoComplete="off" />}</Field>
    </ActPanel>
  );
}

/** Keep a pick that jason reads as another kind, in the person's words. The reading still says what jason read. */
export function KeepPanel({ data, holder, by, onDone, onCancel }: HolderPanel) {
  const [reason, setReason] = useState("");
  return (
    <ActPanel
      slot={data.key} by={by} onDone={onDone} onCancel={onCancel} title={`Keep ${label(holder)} here anyway`}
      body={() => ({ act: "keep", pin: holder.pin, note: reason })} ready={!!reason.trim()} whyNot="Write why this file belongs here."
      previewLabel="Preview" confirmLabel={`Keep ${label(holder)} in ${data.title}`} watch={[reason]}
    >
      <p className="muted">jason reads this file as {holder.wrongSlot?.readsAs.replace(/_/g, " ") ?? "another kind"}. Keeping it here is your decision and goes on the record under your name. The reading is not changed.</p>
      <Field label="Why this file belongs here (required)">{(id) => <textarea id={id} rows={2} value={reason} onChange={(e) => setReason(e.target.value)} />}</Field>
    </ActPanel>
  );
}

/** Move a pick to the slot it fits: a new pin there, the old one unpinned, the reading copied. */
export function RepinPanel({ data, holder, by, onDone, onCancel }: HolderPanel) {
  const fits = holder.wrongSlot?.fits ?? [];
  const [to, setTo] = useState(fits[0]?.key ?? "");
  const [period, setPeriod] = useState("");
  const [entry, setEntry] = useState("");
  return (
    <ActPanel
      slot={data.key} by={by} onDone={onDone} onCancel={onCancel} title={`Move ${label(holder)} to the slot it fits`}
      body={() => ({ act: "repin", pin: holder.pin, to, period, entry })} ready={!!to} whyNot="jason found no slot this file fits."
      previewLabel="Preview the move" confirmLabel={`Pin ${label(holder)} to ${fits.find((f) => f.key === to)?.title ?? "the other slot"} instead`} watch={[to, period, entry]}
    >
      <Field label="Slot it fits">{(id) => (
        <select id={id} value={to} onChange={(e) => setTo(e.target.value)}>
          {fits.length === 0 && <option value="">No slot found</option>}
          {fits.map((f) => <option key={f.key} value={f.key}>{f.title}</option>)}
        </select>
      )}</Field>
      <Field label="Period, if that slot is a series (optional)">{(id) => <input id={id} value={period} onChange={(e) => setPeriod(e.target.value)} autoComplete="off" />}</Field>
      <Field label="Instrument's recording number, if it needs one (optional)">{(id) => <input id={id} value={entry} onChange={(e) => setEntry(e.target.value)} autoComplete="off" />}</Field>
    </ActPanel>
  );
}

/** Queue the reading of a pinned file. The dry run says what would be fetched and how big it is; the real act queues a job in
 * the signed-in person's name and the page watches it. */
export function ReadPanel({ data, holder, by, onDone, onCancel }: HolderPanel) {
  return (
    <ActPanel
      slot={data.key} by={by} onDone={onDone} onCancel={onCancel} title={`Read ${label(holder)}`}
      body={() => ({ act: "read", pin: holder.pin })} ready previewLabel="Show what would be read" confirmLabel={`Queue the reading of ${label(holder)}`} watch={[holder.pin]}
    >
      <p className="muted">The first step fetches nothing and says how big the file is. Confirming queues the reading as a job; it is never run inside this page.</p>
    </ActPanel>
  );
}

/** Mark the "changed since read" mark as seen. It stays on the reading as history. */
export function AckPanel({ data, holder, by, onDone, onCancel }: HolderPanel) {
  return (
    <ActPanel
      slot={data.key} by={by} onDone={onDone} onCancel={onCancel} title={`Acknowledge the change to ${label(holder)}`}
      body={() => ({ act: "ack", pin: holder.pin })} ready previewLabel="Preview" confirmLabel="Record that I have seen the change" watch={[holder.pin]}
    >
      <p className="muted">This records that you have seen that the file changed since it was read. The mark stays on the reading, with your name; read the file again to bring the reading up to date.</p>
    </ActPanel>
  );
}

/** Confirm the parts of a combined scan's proposal: choose a slot for each part you confirm; a part you do not choose fills
 * nothing. A slot that already holds a file is a collision, shown in the preview and not written. */
export function SplitPanel({ data, holder, by, onDone, onCancel }: HolderPanel) {
  const seg = holder.readback?.segments;
  const open = (seg?.proposal ?? []).filter((p) => !p.confirmed);
  const [pick, setPick] = useState<Record<string, { slot: string; period: string; entry: string }>>({});
  const [note, setNote] = useState("");
  const set = (segment: string, patch: Partial<{ slot: string; period: string; entry: string }>) =>
    setPick((p) => ({ ...p, [segment]: { ...(p[segment] ?? { slot: "", period: "", entry: "" }), ...patch } }));
  const chosen = open.filter((p) => pick[p.segment]?.slot);
  return (
    <ActPanel
      slot={data.key} by={by} onDone={onDone} onCancel={onCancel} title={`Confirm the split of ${label(holder)}`}
      body={() => ({ act: "split", pin: holder.pin, note, parts: chosen.map((p) => ({ segment: p.segment, slot: pick[p.segment].slot, period: pick[p.segment].period, entry: pick[p.segment].entry })) })}
      ready={chosen.length > 0} whyNot="Choose a slot for at least one part." previewLabel="Preview the split"
      confirmLabel={`Confirm ${chosen.length} ${chosen.length === 1 ? "part" : "parts"} of ${label(holder)}`} watch={[pick, note]}
    >
      <p className="muted">jason proposes; nothing is filled until you confirm. Each confirmed part becomes a new file of just those pages. The original scan and its pin stay.</p>
      <ul className="record-split">
        {open.map((p) => (
          <li key={p.segment}>
            <p><strong>Pages {p.pages[0]} to {p.pages[1]}</strong>: read as {p.kind ? p.kind.replace(/_/g, " ") : "nothing jason could tell"} ({p.tier}{p.readers.length ? `, ${p.readers.join(" and ")}` : ""}){p.date ? `, dated ${p.date}` : ""}.</p>
            <Field label={`Slot for pages ${p.pages[0]} to ${p.pages[1]}`}>{(id) => (
              <select id={id} value={pick[p.segment]?.slot ?? ""} onChange={(e) => set(p.segment, { slot: e.target.value })}>
                <option value="">Fill nothing with this part</option>
                {p.slots.map((s) => <option key={s.key} value={s.key}>{s.title}{s.held ? " (already holds a file)" : ""}</option>)}
              </select>
            )}</Field>
            {pick[p.segment]?.slot && (
              <div className="row wrap">
                <Field label="Period (a series needs one)">{(id) => <input id={id} value={pick[p.segment].period} onChange={(e) => set(p.segment, { period: e.target.value })} autoComplete="off" />}</Field>
                <Field label="Recording number (a repeating key document)">{(id) => <input id={id} value={pick[p.segment].entry} onChange={(e) => set(p.segment, { entry: e.target.value })} autoComplete="off" />}</Field>
              </div>
            )}
          </li>
        ))}
      </ul>
      <Field label="Note (optional)">{(id) => <input id={id} value={note} onChange={(e) => setNote(e.target.value)} autoComplete="off" />}</Field>
    </ActPanel>
  );
}

/** Decline the whole proposal: the file is one document. The proposal stops waiting in the queue. */
export function DeclinePanel({ data, holder, by, onDone, onCancel }: HolderPanel) {
  const [note, setNote] = useState("");
  return (
    <ActPanel
      slot={data.key} by={by} onDone={onDone} onCancel={onCancel} title={`Decline the split of ${label(holder)}`}
      body={() => ({ act: "split", pin: holder.pin, decline: true, note })} ready previewLabel="Preview" confirmLabel="Record that this file is one document" watch={[note]}
    >
      <p className="muted">This records that you want none of the proposed split. The scan stays pinned as it is.</p>
      <Field label="Note (optional)">{(id) => <input id={id} value={note} onChange={(e) => setNote(e.target.value)} autoComplete="off" />}</Field>
    </ActPanel>
  );
}

/** Replace a person's pin in one step: the new file (a Drive link or an upload) is pinned and the old one unpinned. The preview
 * shows both halves; a pin someone kept needs the box ticked. */
export function ReplacePanel({ data, holder, by, onDone, onCancel }: HolderPanel) {
  const f = useFileBytes();
  const [mode, setMode] = useState<"link" | "file">("link");
  const [link, setLink] = useState("");
  const [period, setPeriod] = useState("");
  const [entry, setEntry] = useState("");
  const [force, setForce] = useState(false);
  const ready = mode === "link" ? !!link.trim() : !!f.file;
  const newName = mode === "file" ? f.file?.name ?? "the new file" : "the new file";
  return (
    <ActPanel
      slot={data.key} by={by} onDone={onDone} onCancel={onCancel} title={`Replace ${label(holder)}`}
      body={() => ({ act: "replace", pin: holder.pin, period, entry, force, ...(mode === "link" ? { file: link.trim() } : { name: f.file?.name, base64: f.file?.base64 }) })}
      ready={ready} whyNot={mode === "link" ? "Paste the new file's Drive link." : "Choose the new file."}
      previewLabel="Preview both halves" confirmLabel={`Pin ${newName} and unpin ${label(holder)}`} watch={[mode, link, f.file, period, entry, force]}
    >
      <p className="muted">One act, two halves: the new file is pinned, then the old pin is unpinned. History keeps both; no file is deleted.</p>
      <fieldset className="record-radios">
        <legend>The new file</legend>
        <label><input type="radio" name="replace-mode" checked={mode === "link"} onChange={() => setMode("link")} /> A Drive link or id</label>
        <label><input type="radio" name="replace-mode" checked={mode === "file"} onChange={() => setMode("file")} /> A file from this computer</label>
      </fieldset>
      {mode === "link"
        ? <Field label="Drive link or id">{(id) => <input id={id} value={link} onChange={(e) => setLink(e.target.value)} autoComplete="off" />}</Field>
        : <Field label="File">{(id) => <input id={id} type="file" accept=".pdf,.png,.jpg,.jpeg,.tif,.tiff,.doc,.docx" onChange={(e) => f.choose(e.target.files?.[0])} />}</Field>}
      {mode === "file" && f.file && <p role="status">Chosen: <strong>{f.file.name}</strong>, {sizeWords(f.file.size)}.</p>}
      {f.error && <p className="notice notice-error" role="alert">{f.error}</p>}
      <div className="row wrap">
        <Field label="Period (optional)">{(id) => <input id={id} value={period} onChange={(e) => setPeriod(e.target.value)} autoComplete="off" />}</Field>
        <Field label="Recording number (optional)">{(id) => <input id={id} value={entry} onChange={(e) => setEntry(e.target.value)} autoComplete="off" />}</Field>
      </div>
      {holder.kept && (
        <label className="record-force"><input type="checkbox" checked={force} onChange={(e) => setForce(e.target.checked)} /> {holder.kept.by} kept this pick although jason reads it as {holder.kept.readsAs.replace(/_/g, " ")}. Replace it anyway.</label>
      )}
    </ActPanel>
  );
}
