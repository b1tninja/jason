import { useState } from "react";
import { Badge, Card, Kanban, Pill, RemoteView } from "../components";
import { useApi } from "../lib/useApi";
import "./jobs.css";

export interface Job {
  id: number; command: string; resource: string; status: string; writes: boolean; confirmedBy: string | null; added: string | null;
  attempts: number; maxAttempts: number; started: string | null; finished: string | null; exitCode: number | null; note: string | null; summary: string | null;
}
export interface Jobs { found?: boolean; note?: string; jobs: Job[]; byStatus?: Record<string, number> }
export interface JobDetail { found?: boolean; note?: string; job: Job; log: string[] }

export const JOB_STATUSES = ["queued", "running", "done", "failed", "cancelled"] as const;

/** The end of one job's log, fetched when the card is opened. */
function JobLog({ id }: { id: number }) {
  const r = useApi<JobDetail>(`/api/jobs?job=${encodeURIComponent(String(id))}`);
  return (
    <RemoteView r={r}>
      {(d) => (d.log.length ? <pre className="job-log" aria-label={`log of job ${id}`}>{d.log.join("\n")}</pre> : <p className="muted">No log yet.</p>)}
    </RemoteView>
  );
}

/** One job. Everything shown is what the queue recorded; the card changes nothing. */
export function JobCard({ job }: { job: Job }) {
  const [open, setOpen] = useState(false);
  const toggle = () => setOpen((o) => !o);
  return (
    <article
      className="item job"
      data-status={job.status}
      role="button"
      tabIndex={0}
      aria-expanded={open}
      aria-label={`job ${job.id}`}
      onClick={toggle}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          toggle();
        }
      }}
    >
      <header className="row wrap">
        <span className="muted">#{job.id}</span>
        <Pill word={job.status} />
        <Badge>{job.resource}</Badge>
        {job.writes && <Badge tone="warn">{`writes · confirmed by ${job.confirmedBy || "nobody recorded"}`}</Badge>}
      </header>
      <p>
        <code>jason {job.command}</code>
      </p>
      <p className="job-facts">
        <span>attempts {job.attempts}/{job.maxAttempts}</span>
        {job.added && <span>added {job.added}</span>}
        {job.started && <span>started {job.started}</span>}
        {job.finished && <span>finished {job.finished}</span>}
        {job.exitCode !== null && job.exitCode !== undefined && <span>exit {job.exitCode}</span>}
      </p>
      {job.note && <p className="muted">{job.note}</p>}
      {job.summary && <p className="job-summary">{job.summary}</p>}
      {open && (
        <div onClick={(e) => e.stopPropagation()}>
          <JobLog id={job.id} />
        </div>
      )}
    </article>
  );
}

export function JobsView() {
  const [all, setAll] = useState(false);
  const r = useApi<Jobs>(`/api/jobs${all ? "?all=1" : ""}`);
  return (
    <div className="stack">
      <Card
        title="Job queue"
        actions={
          <label>
            <input type="checkbox" checked={all} onChange={(e) => setAll(e.target.checked)} /> show all
          </label>
        }
      >
        <p className="muted">
          This page adds, runs, and cancels nothing. <code>jason jobs add --confirm NAME -- &lt;command&gt;</code> queues a write and{" "}
          <code>jason worker</code> runs it. A job marked <em>writes</em> ran only because a person confirmed it; a failed write waits for a person.
          Click a card for the end of its log.
        </p>
      </Card>
      <RemoteView r={r}>
        {(d) => (
          <Kanban lanes={JOB_STATUSES} items={d.jobs} laneOf={(j) => j.status} keyOf={(j) => String(j.id)} render={(j) => <JobCard job={j} />} />
        )}
      </RemoteView>
    </div>
  );
}
