import { useEffect, useState } from "react";
import { Badge } from "./Badge";
import { DocumentPreview, attachedCopies } from "./DocumentPreview";
import { getJson } from "../lib/api";

export interface DriveFile { id: string; name: string; kind: string; url: string }
interface CatalogRow { id: string; name: string; path?: string; kind: string; link?: string; modified?: string }
interface Catalog { found: boolean; note?: string; syncedAt?: string; matching?: number; files: CatalogRow[] }

export const DRIVE_ATTACH_NOTE = "Google Picker is not configured; this searches the Drive catalog jason synced.";
const isReal = (url: string) => /^https?:\/\//.test(url);

/** Attach Drive files to a record or an agenda item. The rows: kind badge, name, Open (real URL only), Remove. The
 * dialog searches the Drive catalog on disk (`/api/drive-files?q=`), never Drive itself, and says so.
 *
 * `previews` gives each attached file its `DocumentPreview` (jason's copy: a thumbnail, Preview, Read from Drive, Open in
 * Google) in place of the bare Open link. */
export function DriveAttach({ files, onChange, searchPath = "/api/drive-files", previews = false }: { files: DriveFile[]; onChange: (files: DriveFile[]) => void; searchPath?: string; previews?: boolean }) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [sel, setSel] = useState<Record<string, boolean>>({});
  const [rows, setRows] = useState<CatalogRow[]>([]);
  const [note, setNote] = useState("");
  useEffect(() => {
    if (!open) return;
    const ctl = new AbortController();
    const t = setTimeout(() => {
      getJson<Catalog>(`${searchPath}?q=${encodeURIComponent(q)}&limit=30`, ctl.signal).then(
        (c) => { setRows(c.found === false ? [] : c.files ?? []); setNote(c.found === false ? c.note ?? "no Drive catalog" : c.syncedAt ? `catalog synced ${String(c.syncedAt).slice(0, 10)}` : ""); },
        (e: Error) => { if (e.name !== "AbortError") { setRows([]); setNote(e.message); } },
      );
    }, 150);
    return () => { clearTimeout(t); ctl.abort(); };
  }, [open, q, searchPath]);
  const attached = new Set(files.map((f) => f.id));
  const results = rows.filter((r) => !attached.has(r.id));
  const picked = results.filter((r) => sel[r.id]);
  const choose = () => {
    if (picked.length) onChange([...files, ...picked.map((r) => ({ id: r.id, name: r.name, kind: r.kind, url: r.link ?? "" }))]);
    setOpen(false); setSel({});
  };
  return (
    <div className="attach">
      {files.length > 0 && (
        <ul className="attach-list">
          {files.map((f) => {
            const copies = previews ? attachedCopies(f) : null;
            return (
              <li key={f.id} className={copies ? "attach-with-preview" : undefined}>
                <span className="attach-name"><Badge>{f.kind || "file"}</Badge><span>{f.name}</span></span>
                <span className="attach-acts">
                  {!copies && isReal(f.url) && <a href={f.url} target="_blank" rel="noopener noreferrer">Open</a>}
                  <button className="link" onClick={() => onChange(files.filter((x) => x.id !== f.id))}>Remove</button>
                </span>
                {copies && <DocumentPreview name={f.name} driveId={copies.driveId} kind={copies.kind} path={copies.path} recordedLabel="File on disk" />}
              </li>
            );
          })}
        </ul>
      )}
      <div className="row wrap">
        <button onClick={() => { setOpen(true); setQ(""); setSel({}); }}>Attach from Drive</button>
        <span className="muted attach-note">{DRIVE_ATTACH_NOTE}</span>
      </div>
      {open && (
        <div className="attach-scrim" onClick={() => setOpen(false)}>
          <div role="dialog" aria-modal="true" aria-label="Choose files from Drive" className="attach-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="row" style={{ justifyContent: "space-between" }}><strong>Choose files from Drive</strong><Badge tone="warn">Drive catalog</Badge></div>
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search the catalog" aria-label="Search the Drive catalog" autoFocus />
            <ul className="attach-results">
              {results.map((r) => (
                <li key={r.id}>
                  <label>
                    <input type="checkbox" checked={!!sel[r.id]} onChange={() => setSel((s) => ({ ...s, [r.id]: !s[r.id] }))} />
                    <span className="attach-result">
                      <span>{r.name}</span>
                      <span className="muted">{r.kind}{r.modified ? ` · modified ${String(r.modified).slice(0, 10)}` : ""}{r.path ? ` · ${r.path}` : ""}</span>
                    </span>
                  </label>
                </li>
              ))}
              {results.length === 0 && <li className="muted attach-empty">{note || "No matching file in the catalog."}</li>}
            </ul>
            <p className="muted attach-note">{DRIVE_ATTACH_NOTE}{note && results.length > 0 ? ` ${note[0].toUpperCase()}${note.slice(1)}.` : ""}</p>
            <div className="row" style={{ justifyContent: "flex-end" }}>
              <button onClick={() => setOpen(false)}>Cancel</button>
              <button className="primary" onClick={choose} disabled={picked.length === 0}>{picked.length ? `Attach ${picked.length}` : "Attach"}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
