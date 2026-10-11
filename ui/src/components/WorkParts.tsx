import type { ReactNode } from "react";
import { Glyph } from "./Glyph";
import { ErrorNotice } from "./States";
import { DEFINITIONS_HREF, WORK_HREF, type Problem, type WorkRemote } from "../lib/work";

/** A read the server refused (401 signed out; 403 for an office that does not open it) or that failed. The server's own
 * sentence is shown, with the sign-in link for a 401. A failed read says so and shows no control, so nothing appears done
 * that is not. */
export function WorkProblem({ r, what, onRetry }: { r: Extract<WorkRemote<unknown>, { status: "error" }>; what: string; onRetry: () => void }) {
  if (r.code === 401 || r.code === 403) {
    return (
      <div className="notice work-held" role="alert">
        <Glyph name="lock" size="1em" /> <span>{r.error}</span>
        {r.code === 401 && r.signIn && <> <a href={r.signIn}>Sign in with Google</a></>}
      </div>
    );
  }
  return <ErrorNotice error={`${what} could not be read: ${r.error}`} onRetry={onRetry} />;
}

/** The trail above a page: Work, then where this is. */
export function WorkCrumbs({ trail, here }: { trail?: { label: string; href: string }[]; here: ReactNode }) {
  return (
    <nav aria-label="Breadcrumb" className="work-crumbs">
      <ol>
        <li><a href={WORK_HREF}>Work</a></li>
        {(trail ?? []).map((t) => <li key={t.href}><a href={t.href}>{t.label}</a></li>)}
        <li aria-current="page">{here}</li>
      </ol>
    </nav>
  );
}

/** The two parts of Work, as links: the open runs, and what can be run. */
export function WorkNav({ current }: { current: "runs" | "definitions" | "start" }) {
  return (
    <nav aria-label="Work" className="work-nav row wrap">
      <a href={WORK_HREF} aria-current={current === "runs" ? "page" : undefined}>Open runs</a>
      <a href={DEFINITIONS_HREF} aria-current={current === "definitions" ? "page" : undefined}>What can be run</a>
    </nav>
  );
}

/** What a read could not build or could not read, plainly. */
export function WorkNotes({ problems, notComposed }: { problems?: readonly Problem[]; notComposed?: readonly Problem[] }) {
  return (
    <>
      {problems && problems.length > 0 && (
        <div className="notice notice-warn work-problems-note" role="note">
          <p><strong>Some of this could not be read.</strong></p>
          <ul>{problems.map((p, i) => <li key={i}>{p.what}: {p.why}</li>)}</ul>
        </div>
      )}
      {notComposed && notComposed.length > 0 && (
        <aside className="work-not-composed" aria-label="Not composed on this page">
          <h2>Not composed here</h2>
          <ul>{notComposed.map((n, i) => <li key={i}><strong>{n.what}.</strong> <span className="muted">{n.why}</span></li>)}</ul>
        </aside>
      )}
    </>
  );
}

/** A link that looks like a button (a route, not an act). */
export function LinkButton({ href, children, primary = false }: { href: string; children: ReactNode; primary?: boolean }) {
  return <a className={`work-btn${primary ? " work-btn-primary" : ""}`} href={href}>{children}</a>;
}
