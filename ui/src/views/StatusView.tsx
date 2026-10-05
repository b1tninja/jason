import { Badge, Card, Caveats, Command, RemoteView, ScreenHeader, StageSteps, type StageGate, type Tone } from "../components";
import type { GlyphName } from "../components/Glyph";
import { useApi } from "../lib/useApi";

/** A job as `GET /api/status` gives it: its command line, how it ended, and its last line masked. */
export interface StatusJob { id: number; command: string; status: string; at: string; summary: string; note: string }

/** One source jason keeps: `lastRead` is its store's own stamp ("" when it holds none), `standing` a word only where the
 * records say it ("" when the source declares no threshold), and `fix` the terminal command. */
export interface StatusSource {
  key: string; name: string; what: string; store: string;
  lastRead: string; ageSeconds: number | null;
  standing: "" | "current" | "stale" | "failed" | "not signed in" | "never read" | string;
  note: string; fix: string; staleAfterDays: number | null; staleAfter?: string; staleSource: string;
  lastJob: StatusJob | null; signIn: string;
}
export interface StatusSignIn { at: string; event: string; name: string; role?: string; as?: string; provider?: string; why?: string }
export interface StatusFailure { kind: "job" | "refresh" | "sync" | string; source: string; name: string; at: string; title: string; detail: string; fix: string; job?: number }
export interface StatusGates {
  found: boolean; note?: string; stage?: string; progress?: Record<string, number>; gates?: StageGate[];
  command: string; setup: string;
}
export interface Status {
  found: boolean; note?: string; asOf: string;
  sources: StatusSource[]; counts: Record<string, number>;
  signIns: StatusSignIn[]; gates: StatusGates; failures: StatusFailure[]; caveats: string[];
}

const STANDING: Record<string, { tone: Tone; glyph: GlyphName }> = {
  current: { tone: "good", glyph: "circle-check" },
  stale: { tone: "warn", glyph: "clock" },
  failed: { tone: "bad", glyph: "triangle-alert" },
  "not signed in": { tone: "warn", glyph: "key-round" },
  "never read": { tone: "neutral", glyph: "circle-dashed" },
};

/** "3 days", "5 hours", "12 minutes": how long ago, from the server's count of seconds. */
export function ageWords(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "";
  const s = Math.max(0, seconds);
  const unit = (n: number, w: string) => `${n} ${w}${n === 1 ? "" : "s"}`;
  if (s >= 86400) return unit(Math.floor(s / 86400), "day");
  if (s >= 3600) return unit(Math.floor(s / 3600), "hour");
  if (s >= 60) return unit(Math.floor(s / 60), "minute");
  return "under a minute";
}

/** "2099-10-03T06:10:00+00:00" as "2099-10-03 06:10 UTC": the stamp as the store wrote it, never re-zoned. */
export function stampText(at: string): string {
  const m = /^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/.exec(at);
  return m ? `${m[1]} ${m[2]} UTC` : at;
}

function Standing({ word }: { word: string }) {
  if (!word) return <span className="muted">no threshold declared</span>;
  const s = STANDING[word];
  return <Badge tone={s?.tone ?? "neutral"} glyph={s?.glyph}>{word}</Badge>;
}

function SourceRow({ s }: { s: StatusSource }) {
  const attention = s.standing !== "" && s.standing !== "current";
  return (
    <li className="status-source" aria-label={s.name} data-standing={s.standing || "none"}>
      <div className="status-source-head">
        <strong>{s.name}</strong> <span className="muted">{s.what}</span>
      </div>
      <div>
        {s.lastRead ? (
          <><time dateTime={s.lastRead}>{stampText(s.lastRead)}</time> <span className="muted">({ageWords(s.ageSeconds)} ago)</span></>
        ) : <span className="muted">no last read in its store</span>}
      </div>
      <div><Standing word={s.standing} /></div>
      {s.note && <p className="status-source-note">{s.note}</p>}
      {s.staleSource && <p className="muted">Stale after {s.staleAfter || `${s.staleAfterDays} days`} ({s.staleSource}).</p>}
      {attention ? <Command cmd={s.fix} /> : (
        <details>
          <summary>Refresh command</summary>
          <Command cmd={s.fix} />
        </details>
      )}
      <p className="muted status-source-store">
        Last read from {s.store || "its store"}.
        {s.lastJob && <> Last queued run: job {s.lastJob.id}, {s.lastJob.status}{s.lastJob.at ? ` ${stampText(s.lastJob.at)}` : ""}.</>}
      </p>
    </li>
  );
}

function Counts({ counts }: { counts: Record<string, number> }) {
  const words = Object.entries(counts).map(([w, n]) => `${n} ${w}`);
  return <>{words.join(" · ") || "No sources."}</>;
}

/** The server's own switches (`GET /api/health`): the loaders it serves and the writes that are on. */
function Server() {
  const h = useApi<{ sources?: string[]; writes?: string[] }>("/api/health");
  if (h.status !== "ready") return null;
  return (
    <Card title="Server">
      <p>Writes on: {h.data.writes?.join(", ") || "none"}</p>
      <p className="muted">{h.data.sources?.length ?? 0} sources served.</p>
    </Card>
  );
}

/** The administrator's Status (`GET /api/status`): each source jason keeps with its last read and standing, the fix as a
 * terminal command, who signed in, setup's five gates, and what failed; and the server's switches. Read-only: nothing
 * here but copying a command. */
export function StatusView() {
  const r = useApi<Status>("/api/status");
  return (
    <RemoteView r={r}>
      {(d) => (
        <div className="stack">
          <ScreenHeader title="Status" summary={<>The administrator's view: which sources jason reads and when it last read them, who signed in, where setup stands, and what failed. Read from disk as of {stampText(d.asOf)}. <Counts counts={d.counts} />.</>} />
          <Card title="Sources">
            <ul className="status-sources" aria-label="Sources">
              {d.sources.map((s) => <SourceRow key={s.key} s={s} />)}
            </ul>
          </Card>
          <Card title="Failures">
            {d.failures.length ? (
              <ul className="findings" aria-label="Failures">
                {d.failures.map((f, i) => (
                  <li key={`${f.kind}-${f.at}-${i}`}>
                    <strong>{f.title}</strong> <span className="muted">{stampText(f.at)}</span>
                    {f.detail && <><br /><span>{f.detail}</span></>}
                    {f.fix && <Command cmd={f.fix} />}
                  </li>
                ))}
              </ul>
            ) : <p className="muted">No failed job, refresh, or sync on record.</p>}
          </Card>
          <Card title="Sign-ins">
            {d.signIns.length ? (
              <ul className="findings" aria-label="Sign-ins">
                {d.signIns.map((s, i) => (
                  <li key={`${s.at}-${i}`}>
                    <span className="muted">{stampText(s.at)}</span> {s.event}{s.name ? `: ${s.name}` : ""}{s.role ? `, ${s.role}` : ""}
                    {s.as ? ` (as ${s.as})` : ""}{s.why ? ` (${s.why})` : ""}
                  </li>
                ))}
              </ul>
            ) : <p className="muted">No sign-in on record.</p>}
            <p className="muted">From the sign-in log (web/sign-ins.jsonl); who may sign in comes from the roster.</p>
          </Card>
          <Card title="Setup">
            {d.gates.found ? <StageSteps gates={d.gates.gates ?? []} current={d.gates.stage} label="Setup's gates" /> : <p className="muted">{d.gates.note}</p>}
            <p><a href={d.gates.setup}>Open setup</a></p>
            <Command cmd={d.gates.command} />
          </Card>
          <Server />
          <Caveats items={d.caveats} />
        </div>
      )}
    </RemoteView>
  );
}
