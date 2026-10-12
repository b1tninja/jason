import { useEffect, useId, useState, type ReactNode } from "react";
import { ApiError, getJson } from "../lib/api";
import {
  BANDS, bandTitle, hashWithLens, holdsAny, isOwnLens, lensFromHash, notYours, officesText, theOffice, todayCounts,
  type BandKey, type OfficeInfo, type OfficeRow, type OfficeViewData,
} from "../lib/officeView";
import { MINE_HREF, runHref } from "../lib/work";
import { Card } from "./Card";
import { Caveats } from "./Caveats";
import { DueDate } from "./DueDate";
import { Pill } from "./Pill";
import { NudgeWord, daysWords } from "./StepGuide";
import { EmptyState, ErrorNotice, Loading } from "./States";
import "../styles/office-views.css";

/* Office views (docs/console/screens/office-views.md): a lens that lets a board member read another office's landing page.
   Reading another office never changes who the viewer is: the data levels, the writes, and the name on a record are the
   viewer's own. The lens lives in the URL (`?as=treasurer`), not on the server. */

/** The office the hash reads as ("" is the viewer's own), and a way to change it that keeps the rest of the hash. */
export function useOfficeLens(): [string, (office: string) => void] {
  const read = () => (typeof window === "undefined" ? "" : lensFromHash(window.location.hash));
  const [office, setOffice] = useState(read);
  useEffect(() => {
    const on = () => setOffice(read());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return [office, (next) => { window.location.hash = hashWithLens(window.location.hash, next); }];
}

/** The select in the Today header: "My offices" (the default; a person who holds two offices sees the union) and each
 * office the profile names, a vacant one marked. Changing it is a read: nothing is written. */
export function OfficeLens({ offices, mine, value, onChange }: {
  offices: readonly OfficeInfo[]; mine: readonly string[]; value: string; onChange: (office: string) => void;
}) {
  const id = useId();
  if (!offices.length) return null;
  return (
    <div className="office-lens row wrap">
      <label htmlFor={id}>Reading as</label>
      <select id={id} value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">My offices{mine.length ? ` (${mine.join(", ")})` : ""}</option>
        {offices.map((o) => (
          <option key={o.office} value={o.office}>{o.office}{o.vacant ? " (vacant)" : ""}</option>
        ))}
      </select>
    </div>
  );
}

/** "Reading as the treasurer": shown whenever the lens is not the viewer's own, with the way back. It says whose page it is
 * and that the actions only that office can take are shown but not live; it never says "you" for the other office. */
export function OfficeBanner({ data, onBack }: { data: Pick<OfficeViewData, "office" | "ownOffice" | "mine" | "vacant">; onBack: () => void }) {
  if (isOwnLens(data)) return null;
  const who = theOffice(data.office);
  return (
    <div className="office-banner notice" role="status">
      <p>
        <strong>Reading as {who}</strong>
        {" · "}
        {data.mine.length ? `you are ${officesText(data.mine)}` : "you hold no office"}; actions only {who} can take are shown but not live.
        {data.vacant && <> <Pill word="vacant" meaning={`No one holds the office of ${data.office}.`} /> Its bands show what waits with no one to do it.</>}
      </p>
      <button type="button" onClick={onBack}>Back to my offices</button>
    </div>
  );
}

/** A control for an act that belongs to one office (or any of several), disabled with the reason when the viewer's
 * offices do not hold it: "Only the treasurer can sign this. You are the secretary." Never hidden, so a board member
 * sees what the office does. The server refuses the same act whatever the page shows. */
export function DisabledForOffice({ office, mine, what = "do this", children }: {
  office: string | readonly string[]; mine: readonly string[]; what?: string; children: ReactNode;
}) {
  const id = useId();
  if (holdsAny(office, mine)) return <>{children}</>;
  return (
    <div className="disabled-for-office">
      <fieldset disabled aria-describedby={id}>{children}</fieldset>
      <p id={id} className="muted">{notYours(office, mine, what)}</p>
    </div>
  );
}

// A run row links to the run (`#/work/<definition>/<id>`); any other row, to the screen that owns it.
const screenLink = (row: OfficeRow) =>
  (row.type === "run" || row.type === "person-step") && row.definition && row.id ? <a href={runHref(row.definition, row.id)}>Open the run</a>
    : row.screen ? <a href={`#/${row.screen}`}>Open</a> : null;

function RowMarks({ row }: { row: OfficeRow }) {
  return (
    <>
      {row.type === "person-step" && row.band ? (
        <>
          {row.band === "quiet" ? <span className="muted">{row.urgency}</span> : <NudgeWord band={row.band} word={row.urgency ?? ""} />}
          {row.due && row.days !== null && row.days !== undefined && <span className="muted">{daysWords(row.days)}</span>}
          {row.holder && <span className="muted">{row.holder}{row.forOffice ? "" : " (another office)"}</span>}
          {row.escalatedTo && <span className="muted">also seen by {row.escalatedTo === "the whole board" ? row.escalatedTo : theOffice(row.escalatedTo)}</span>}
        </>
      ) : row.urgency && row.urgency !== "coming up" && <Pill word={row.urgency} />}
      {row.type === "plan-to-apply" && row.stale && <span className="muted">will be planned again</span>}
      {row.type === "plan-to-apply" && row.terminalOnly && <span className="muted">applied at the terminal</span>}
      {row.type === "plan-to-apply" && row.pausing && <span className="muted">held by the board's pause</span>}
      {row.type === "plan-to-apply" && row.reminderDue && <span className="muted">reminder due</span>}
      {row.shared && <span className="muted">the board's</span>}
      {row.backup && <span className="muted">as backup</span>}
      {row.basis && <span className="muted">{row.basis}</span>}
    </>
  );
}

/** One row: what it is, its marks, its date, and a link to the screen that owns it. A row is an office's count, kind, or
 * title of an item; the owning screen decides what a name or a unit shows. */
export function OfficeRowItem({ row }: { row: OfficeRow }) {
  return (
    <li className="office-row" data-type={row.type}>
      <span className="office-row-text">{row.text}</span>
      {row.type === "plan-to-apply" && row.note && <span className="muted office-row-note">{row.note}</span>}
      <span className="office-row-marks"><RowMarks row={row} /></span>
      {row.due && <DueDate iso={row.due} />}
      {screenLink(row)}
    </li>
  );
}

/** One band: its heading names the office when the lens is not the viewer's; a band that failed says why; an empty band says
 * so (its absence would read as a failure to load). */
export function OfficeBand({ band, data }: { band: BandKey; data: OfficeViewData }) {
  const rows = data.bands[band] ?? [];
  const total = data.counts?.[band] ?? rows.length;
  const error = data.bandErrors?.[band];
  if (band === "personSteps" && !rows.length && !error) return null;          // quiet by default: a band with nothing in it is not drawn
  const own = isOwnLens(data);
  const who = own ? "you" : theOffice(data.office);
  const empty: Record<BandKey, string> = {
    personSteps: "No step waiting on a person is due, late, or open a while.",
    waitingOnOffice: `Nothing is waiting on ${who}.`,
    signedWaiting: "No plan is signed and waiting to be applied.",
    needsAttention: `Nothing needs attention for ${who}.`,
    comingUp: `Nothing is coming up for ${who}.`,
    work: own ? "No run is waiting on you." : `No run is waiting on ${who}.`,
  };
  return (
    <Card title={bandTitle(band, data)}>
      <div className="office-band" data-band={band}>
        {error ? <p className="notice notice-warn" role="alert">This band could not be read: {error}</p> : null}
        {!error && rows.length === 0 && <EmptyState>{empty[band]}</EmptyState>}
        {rows.length > 0 && <ul className="office-rows">{rows.map((r, i) => <OfficeRowItem key={`${r.type}-${r.key ?? r.id ?? i}-${r.office}`} row={r} />)}</ul>}
        {total > rows.length && <p className="muted">{total - rows.length} more.</p>}
        {band === "personSteps" && rows.length > 0 && data.stepNumbers?.note && (
          <p className="muted office-step-note">
            Escalation is visibility only: a step late for one office is shown to the board, and nothing is sent. The lead time
            ({data.stepNumbers.leadDays} days) and the open-a-while threshold ({Math.round(data.stepNumbers.afterHours / 24)} days) are {data.stepNumbers.note}.
          </p>
        )}
        {band === "work" && own && total > 0 && <p><a href={MINE_HREF}>All your runs ({total} open)</a></p>}
      </div>
    </Card>
  );
}

/** What the page could not build, and why, said plainly. */
export function NotComposed({ items }: { items: OfficeViewData["notComposed"] }) {
  if (!items?.length) return null;
  return (
    <aside className="office-not-composed" aria-label="Not composed on this page">
      <h2>Not composed here</h2>
      <ul>
        {items.map((n, i) => <li key={i}><strong>{n.what}.</strong> <span className="muted">{n.why}</span></li>)}
      </ul>
    </aside>
  );
}

/** The bands of an office's page: the four bands, what could not be composed, and the caveats. */
export function OfficeBands({ data }: { data: OfficeViewData }) {
  return (
    <div className="office-bands stack">
      {BANDS.map((b) => <OfficeBand key={b} band={b} data={data} />)}
      <NotComposed items={data.notComposed} />
      <Caveats items={data.caveats} />
    </div>
  );
}

type Load = { status: "loading" } | { status: "off" } | { status: "error"; error: string } | { status: "ready"; data: OfficeViewData };

/** The office bands for the Today page: the lens, the banner, and the bands, over `GET /api/office-view`. Where the loader
 * is not offered to this viewer (nobody signed in, no office, the owner view) the page is Today as it was: nothing renders. */
export function OfficeToday() {
  const [lens, setLens] = useOfficeLens();
  const [tick, setTick] = useState(0);
  const [state, setState] = useState<Load>({ status: "loading" });
  useEffect(() => {
    const ctl = new AbortController();
    setState({ status: "loading" });
    getJson<OfficeViewData>(`/api/office-view?office=${encodeURIComponent(lens)}`, ctl.signal).then(
      (data) => setState(data && data.bands ? { status: "ready", data } : { status: "off" }), // an answer that is not an office view is none
      (e: Error) => {
        if (e.name === "AbortError") return;
        const code = e instanceof ApiError ? e.status : undefined;
        setState(code === 401 || code === 403 || code === 404 ? { status: "off" } : { status: "error", error: e.message });
      },
    );
    return () => ctl.abort();
  }, [lens, tick]);

  if (state.status === "off") return null;
  if (state.status === "loading") return <Loading label="Reading the office's page…" />;
  if (state.status === "error") {
    return (
      <div className="office-today">
        <ErrorNotice error={state.error} onRetry={() => setTick((t) => t + 1)} />
        {lens && <button type="button" onClick={() => setLens("")}>Back to my offices</button>}
      </div>
    );
  }
  const data = state.data;
  return (
    <section className="office-today" aria-label="Office view">
      <header className="office-today-head row wrap">
        <h2>{isOwnLens(data) ? "My offices" : `The ${data.office}'s page`}</h2>
        <OfficeLens offices={data.offices} mine={data.mine} value={data.office} onChange={setLens} />
      </header>
      {todayCounts(data) && <p className="office-today-counts muted" aria-label="Counts">{todayCounts(data)}</p>}
      <OfficeBanner data={data} onBack={() => setLens("")} />
      {data.note && <p className="muted">{data.note}</p>}
      <OfficeBands data={data} />
    </section>
  );
}
