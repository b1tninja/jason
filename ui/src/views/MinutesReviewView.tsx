import { useEffect, useMemo, useState } from "react";
import { Badge, Card, Caveats, Command, Confirm, DataTable, Findings, Markdown, RemoteView, type Column } from "../components";
import { postJson } from "../lib/api";
import { useApi } from "../lib/useApi";
import "./minutesreview.css";

interface DraftRow { date: string; file: string; blanks: number; filled: number; reviewed: boolean; reviewedBy: string; savedAt: string; minutesFile: string; privacyFlags: number }
interface Listing { found?: boolean; note?: string; count: number; drafts: DraftRow[]; caveats?: string[] }
interface Blank { id: string; section: string; context: string; marker: string; value: string }
interface Flag { line: number; text: string; member: string; replacement: string; why: string }
interface Section { heading: string; level: number; body: string; blanks: string[] }
interface Review {
  found?: boolean; note?: string; date: string; draft: string; markdown: string; blanks: Blank[]; open: number; privacy: Flag[]; namesFrom?: string;
  sections: Section[]; reviewedBy: string; savedAt: string; history: string[]; minutesFile: string; command: string; commands: { redraft: string; privacy?: string }; caveats?: string[];
}

/** The draft's UNKNOWN marker (jason.community.minutes_template.UNKNOWN), a {braced} instruction, or a [bracketed] one:
 * the same walk as jason.tasks.minutes_review.fill, so the ids line up with the loader's. */
const BLANK = /(?<!")___ \(not in the record\)(?!")|\{[^{}\n]+\}|\[(?![xX ]?\])[^[\]\n]{3,}\](?!\()/g;
const HEADING = /^#{1,6}\s+/;

/** Fills the draft client side with the values typed so far; a blank with no value stays as it was. */
export function fillDraft(text: string, values: Record<string, string>): string {
  let n = 0;
  return text.split(/\r?\n/).map((line) => (HEADING.test(line) ? line : line.replace(BLANK, (m) => { const v = values[`b${++n}`]; return v && v.trim() ? v : m; }))).join("\n");
}

/** One blank as it reads in its line, the marker shown as a gap. */
function Context({ b }: { b: Blank }) {
  const at = b.context.indexOf(b.marker);
  if (at < 0) return <span className="muted">{b.context}</span>;
  return (
    <span className="muted blank-context">
      {b.context.slice(0, at)}<mark className="blank-gap">{b.value.trim() ? b.value : "____"}</mark>{b.context.slice(at + b.marker.length)}
    </span>
  );
}

/** One draft: the blanks as a form on the left, the filled copy on the right, the privacy flags beside the lines they concern. */
function Review({ date, back }: { date: string; back: () => void }) {
  const r = useApi<Review>(`/api/minutes-review?date=${encodeURIComponent(date)}`);
  const [values, setValues] = useState<Record<string, string>>({});
  const [by, setBy] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    if (r.status === "ready") setValues(Object.fromEntries(r.data.blanks.map((b) => [b.id, b.value])));
  }, [r.status === "ready" ? r.data.savedAt + r.data.date : ""]); // eslint-disable-line react-hooks/exhaustive-deps
  const preview = useMemo(() => (r.status === "ready" ? fillDraft(r.data.draft, values) : ""), [r, values]);
  const changed = r.status === "ready" ? r.data.blanks.filter((b) => (values[b.id] ?? "") !== b.value) : [];
  const save = async () => {
    setSaving(true); setError(""); setSaved("");
    try {
      const out = await postJson<Review>(`/api/write/minutes-review/${encodeURIComponent(date)}`, { values: Object.fromEntries(changed.map((b) => [b.id, values[b.id] ?? ""])), by });
      setSaved(out.minutesFile || "saved");
      r.reload();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };
  return (
    <RemoteView r={r}>
      {(d) => {
        const open = d.blanks.filter((b) => !(values[b.id] ?? "").trim()).length;
        const bySection = d.blanks.reduce<Record<string, Blank[]>>((acc, b) => { (acc[b.section] ??= []).push(b); return acc; }, {});
        const flagged = new Set(d.privacy.map((f) => f.text));
        return (
          <div className="stack minutes-review">
            <div className="row wrap">
              <button onClick={back}>← Minutes drafts</button>
              <strong>Minutes draft of {d.date}</strong>
              <Badge tone={open ? "warn" : "good"}>{open ? `${open} blank${open === 1 ? "" : "s"} open` : "every blank filled"}</Badge>
              {d.privacy.length > 0 && <Badge tone="warn">{`${d.privacy.length} privacy flag${d.privacy.length === 1 ? "" : "s"}`}</Badge>}
              {d.reviewedBy && <span className="muted">last saved by {d.reviewedBy} {d.savedAt && `at ${d.savedAt}`}</span>}
            </div>
            <Caveats items={d.caveats} />
            <div className="grid-2">
              <Card title={`Blanks (${d.blanks.length})`}>
                {d.blanks.length === 0 && <p className="muted">The record showed everything the sections ask for; nothing to fill.</p>}
                <div className="fields">
                  {Object.entries(bySection).map(([section, blanks]) => (
                    <div key={section} className="wide blank-section">
                      <h4>{section || "Preamble"}</h4>
                      {blanks.map((b) => (
                        <label key={b.id} className="wide">
                          <span className="blank-label">{b.id}{flagged.has(b.context) && <Badge tone="warn">privacy</Badge>}</span>
                          <Context b={{ ...b, value: values[b.id] ?? "" }} />
                          <input aria-label={`${b.id} in ${section || "Preamble"}`} value={values[b.id] ?? ""} placeholder={b.marker === "___ (not in the record)" ? "what the record did not show" : b.marker.slice(1, -1)} onChange={(e) => setValues({ ...values, [b.id]: e.target.value })} />
                        </label>
                      ))}
                    </div>
                  ))}
                </div>
                <div className="fields">
                  <label className="wide">Reviewed by <input aria-label="Reviewed by" value={by} onChange={(e) => setBy(e.target.value)} placeholder="the Secretary" /></label>
                </div>
                <div className="row wrap">
                  <Confirm busy={saving || !by.trim() || changed.length === 0} onConfirm={save}
                    summary={<span>Saves {changed.length} answer{changed.length === 1 ? "" : "s"} beside the draft and writes the filled copy <code className="chip">minutes-{d.date}.md</code>. The draft is not changed; nothing is posted.</span>}>
                    Save review
                  </Confirm>
                  {saved && <span className="muted">saved: {saved}</span>}
                  {error && <span className="notice notice-warn">{error}</span>}
                </div>
                {d.history.length > 0 && <ul className="muted history">{d.history.map((h, i) => <li key={i}>{h}</li>)}</ul>}
              </Card>
              <Card title="As it would read">
                <div className="preview"><Markdown text={preview} /></div>
              </Card>
            </div>
            <Card title={`Privacy (${d.privacy.length})`}>
              <p className="muted">A member's name beside a delinquency, fine, hearing, lien, or collections word; names read from {d.namesFrom ?? "the text"}. A flag is a lead for the Secretary, not a finding.</p>
              <Findings items={d.privacy.map((f) => `line ${f.line}: "${f.text}" — ${f.why}`)} empty="no member named beside an executive session matter" />
              {d.privacy.length > 0 && d.commands.privacy && <Command cmd={d.commands.privacy} note="Writes a corrected copy with each passage replaced by the general note CIV 4935(e) allows; the original is not changed." />}
            </Card>
            <Card title="Redraft">
              <Command cmd={d.commands.redraft} note="Writes the draft again from the Zoom record with the local model; the saved answers are filled into the new draft by blank order, so check them after." />
            </Card>
          </div>
        );
      }}
    </RemoteView>
  );
}

const cols: Column<DraftRow>[] = [
  { key: "date", header: "Meeting" },
  { key: "blanks", header: "Blanks", render: (d) => <span>{d.filled}/{d.blanks} filled</span> },
  { key: "privacyFlags", header: "Privacy", render: (d) => d.privacyFlags ? <Badge tone="warn">{`${d.privacyFlags} flag${d.privacyFlags === 1 ? "" : "s"}`}</Badge> : <span className="muted">none</span> },
  { key: "reviewedBy", header: "Reviewed", render: (d) => d.reviewed ? <span>{d.reviewedBy} <span className="muted">{d.savedAt}</span></span> : <Badge tone="warn">not yet</Badge> },
  { key: "minutesFile", header: "Filled copy", render: (d) => d.minutesFile ? <code className="chip">minutes-{d.date}.md</code> : <span className="muted">none</span> },
];

/** The minutes drafts `jason board --minutes DATE` wrote, and one as a form the Secretary fills. */
export function MinutesReviewView() {
  const r = useApi<Listing>("/api/minutes-review");
  const [open, setOpen] = useState("");
  if (open) return <Review date={open} back={() => setOpen("")} />;
  return (
    <RemoteView r={r}>
      {(d) => (
        <div className="stack">
          <Card title={`Minutes drafts (${d.drafts.length})`}>
            <p className="muted">A draft is jason's reading of the Zoom record, with a blank wherever the record did not show what a section asks for. The Secretary fills the blanks here; the board adopts the minutes at its next meeting.</p>
            {d.drafts.length === 0 && <div className="stack"><p className="muted">{d.note || "no minutes draft yet"}</p><Command cmd="jason board --minutes YYYY-MM-DD" /></div>}
            {d.drafts.length > 0 && <DataTable rows={d.drafts} columns={[...cols, { key: "review", header: "", render: (row) => <button className="primary" onClick={() => setOpen(row.date)}>Review</button> }]} searchable={false} />}
          </Card>
          <Caveats items={d.caveats} />
        </div>
      )}
    </RemoteView>
  );
}
