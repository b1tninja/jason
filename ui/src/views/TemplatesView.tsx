import { useEffect, useMemo, useState } from "react";
import { Badge, Card, Command, DataTable, DrivePreview, EvidenceVersion, Markdown, ReadAllFromDrive, RemoteView, type Column, type DocRef } from "../components";
import { postJson } from "../lib/api";
import { useApi } from "../lib/useApi";

/** A template; `doc` is its Doc as a document reference (`drive:<id>`), whose original is "Open in Google". */
interface TemplateRow { kind: string; title: string; driveId: string; folderId: string; authority: string; optional: string[]; linkTokens: string[]; tokens: string[]; lint: { profile: string[]; general: string[]; run: string[] }; doc?: DocRef }
interface Listing { found?: boolean; note?: string; templates: TemplateRow[] }
interface Preview { found?: boolean; note?: string; kind: string; title: string; driveId: string; markdown: string; tokens: string[]; open: string[]; command: string }
interface CanvasRow { key: string; title: string; status: string }

const words = (t: string) => t.toLowerCase().replace(/_/g, " ");

/** One template: the tokens the run must fill, the body as it would read, and the command that fills a Drive copy. */
function Fill({ t, back }: { t: TemplateRow; back: () => void }) {
  const [values, setValues] = useState<Record<string, string>>({});
  const [name, setName] = useState(`${t.title} draft`);
  const query = useMemo(() => {
    const p = new URLSearchParams({ kind: t.kind, name });
    for (const [k, v] of Object.entries(values)) if (v.trim()) p.set(`V_${k}`, v);
    return p.toString();
  }, [t.kind, name, values]);
  const [debounced, setDebounced] = useState(query);
  useEffect(() => { const h = setTimeout(() => setDebounced(query), 300); return () => clearTimeout(h); }, [query]);
  const r = useApi<Preview>(`/api/templates?${debounced}`);
  const canvases = useApi<{ found: boolean; canvases: CanvasRow[] }>("/api/canvases");
  const [target, setTarget] = useState("");
  const [kept, setKept] = useState("");
  const keep = async (md: string) => {
    await postJson(`/api/canvases/${encodeURIComponent(target)}`, { clip: { source: `template: ${t.kind}`, label: name, text: md, args: values } });
    setKept(target);
  };
  return (
    <div className="stack">
      <div className="row wrap"><button onClick={back}>← Templates</button><strong>{t.title}</strong>{t.authority && <span className="muted">{t.authority}</span>}{t.doc?.original && <a href={t.doc.original.url} target="_blank" rel="noreferrer">the template Doc<span className="visually-hidden"> ({t.doc.original.label}, opens in a new tab)</span></a>}</div>
      <div className="grid-2">
        <Card title="Fill">
          <div className="fields">
            <label className="wide">Name of the filled letter <input value={name} onChange={(e) => setName(e.target.value)} /></label>
            {t.lint.run.map((k) => (
              <label key={k} className="wide">{words(k)} {t.optional.includes(k) && <Badge>optional</Badge>}
                <input value={values[k] ?? ""} onChange={(e) => setValues({ ...values, [k]: e.target.value })} />
              </label>
            ))}
          </div>
          {(t.lint.profile.length > 0 || t.lint.general.length > 0) && (
            <p className="muted">Filled by the profile: {t.lint.profile.map(words).join(", ")}{t.lint.general.length > 0 && <>; general wording stands in for: {t.lint.general.map(words).join(", ")}</>}. Override one by its token: <code className="chip">--set TOKEN=value</code>.</p>
          )}
        </Card>
        <Card title="As it would read">
          <RemoteView r={r}>
            {(d) => (
              <div className="stack">
                {d.open.length > 0 && <p className="notice notice-warn">Still open: {d.open.map(words).join(", ")} (left as [token in words] for the person who finishes it).</p>}
                <div className="preview"><Markdown text={d.markdown} /></div>
                <Command cmd={d.command} note="Copies the template in Drive and fills it; sends nothing. A person runs it." />
                {canvases.status === "ready" && canvases.data.canvases.length > 0 && (
                  <div className="row wrap">
                    <select aria-label="Canvas" value={target} onChange={(e) => setTarget(e.target.value)}><option value="">keep on a canvas…</option>{canvases.data.canvases.map((c) => <option key={c.key} value={c.key}>{c.title}</option>)}</select>
                    <button onClick={() => keep(d.markdown)} disabled={!target}>Keep</button>
                    {kept && <span className="muted">kept on {kept}</span>}
                  </div>
                )}
              </div>
            )}
          </RemoteView>
        </Card>
      </div>
    </div>
  );
}

const cols: Column<TemplateRow>[] = [
  { key: "title", header: "Template" },
  { key: "kind", header: "Kind", render: (t) => <code className="chip">{t.kind}</code> },
  { key: "authority", header: "Authority" },
  { key: "run", header: "The run fills", value: (t) => t.lint.run.length, render: (t) => <span className="row wrap">{t.lint.run.map((k) => <Badge key={k} tone="warn">{words(k)}</Badge>)}</span> },
  { key: "profile", header: "The profile fills", value: (t) => t.lint.profile.length + t.lint.general.length, render: (t) => <span className="muted">{t.lint.profile.length + t.lint.general.length} tokens</span> },
  // The Doc as jason's copy: a thumbnail from disk, Preview, Read from Drive, and Open in Google (DrivePreview).
  { key: "driveId", header: "Doc", render: (t) => t.driveId ? <DrivePreview driveId={t.driveId} name={t.title} kind="doc" /> : <Badge tone="warn">not built</Badge> },
];

/** The letter templates and a fill form for each: the body previews from the same text the Doc is built from. Each built
 * template's Doc shows as jason's copy of it; "Read every template from Drive" exports them all on one sign-in. */
export function TemplatesView() {
  const r = useApi<Listing>("/api/templates");
  const [open, setOpen] = useState<TemplateRow | null>(null);
  const [version, setVersion] = useState(0);
  if (open) return <Fill t={open} back={() => setOpen(null)} />;
  return (
    <RemoteView r={r}>
      {(d) => (
        <Card title={`Letter templates (${d.templates.length})`}>
          <p className="muted">A template is a Drive Doc with {"{TOKENS}"}; the profile fills most, the run fills the rest, and a letter is a filled copy (`jason letter`). Pick one to fill it here and see how it reads.</p>
          <p className="muted">The Doc column shows jason's copy of each template, read from Drive when a person last asked; nothing is read from Google until someone does.</p>
          <ReadAllFromDrive driveIds={d.templates.map((t) => t.driveId)} what="template" batch="templates" onDone={() => setVersion((v) => v + 1)} />
          <EvidenceVersion.Provider value={version}>
            <DataTable rows={d.templates} columns={[...cols, { key: "fill", header: "", render: (t) => <button className="primary" onClick={() => setOpen(t)}>Fill</button> }]} searchable={false} />
          </EvidenceVersion.Provider>
        </Card>
      )}
    </RemoteView>
  );
}
