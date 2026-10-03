import { useEffect, useState, type ReactNode } from "react";

export type Audience = "board" | "owner";

/** One screen in the console's nav. `owner` marks the screens an owner sees; `ownerLabel` is its name there. */
export interface ConsoleScreen {
  id: string;
  label: string;
  ownerLabel?: string;
  group: string;
  owner?: boolean;
  /** A count shown after the label, e.g. approvals pending. */
  count?: number;
}

export interface ConsolePerson { name: string; role?: string }

export interface ConsoleShellProps {
  /** The community's short name, in the brand font; the legal name follows it with "· jason". */
  wordmark: string;
  legal: string;
  /** "Records as of …": shown only when a loader gives the day; never invented. */
  recordsAsOf?: string;
  groups: readonly string[];
  screens: readonly ConsoleScreen[];
  current: string;
  onGo: (id: string) => void;
  audience: Audience;
  onAudience: (a: Audience) => void;
  /** The "Signed in as" picker: the chosen name and the people to choose from. Hidden for owners or with no one to pick. */
  session?: { me: string; setMe: (name: string) => void; people: readonly ConsolePerson[] };
  /** The dock toolbar, rendered in the header. */
  dock?: ReactNode;
  /** A pinned drawer: a sticky column beside the page. */
  pinned?: ReactNode;
  /** A floating drawer: rendered outside the row. */
  floating?: ReactNode;
  children: ReactNode;
}

export const OWNER_BANNER = "Owner view, read-only. Payments under review, board action items, duties, and delinquency stay with the board.";

const NARROW = 720;

function useNarrow(): boolean {
  const read = () => typeof window !== "undefined" && window.innerWidth < NARROW;
  const [narrow, setNarrow] = useState(read);
  useEffect(() => {
    const on = () => setNarrow(read());
    window.addEventListener("resize", on);
    return () => window.removeEventListener("resize", on);
  }, []);
  return narrow;
}

/** The screens an audience sees, in nav order. */
export function visibleScreens(screens: readonly ConsoleScreen[], audience: Audience): ConsoleScreen[] {
  return screens.filter((s) => audience === "board" || s.owner);
}

const nameOf = (s: ConsoleScreen, audience: Audience) => (audience === "owner" && s.ownerLabel) || s.label;

/** The console's frame: a sticky header (wordmark, legal name, records date, the sign-in pick, the dock, the Board /
 * Owner view control), a grouped left nav that becomes a "Go to" select under 720px, the main column, and the slots
 * for a pinned or a floating drawer. The shell routes; it decides nothing. */
export function ConsoleShell({ wordmark, legal, recordsAsOf, groups, screens, current, onGo, audience, onAudience, session, dock, pinned, floating, children }: ConsoleShellProps) {
  const narrow = useNarrow();
  const visible = visibleScreens(screens, audience);
  const owner = audience === "owner";
  const grouped = groups.map((g) => ({ label: g, items: visible.filter((s) => s.group === g) })).filter((g) => g.items.length);
  const showSignIn = !owner && session && session.people.length > 0;
  return (
    <div className="console">
      <header className="console-bar">
        <div className="console-bar-inner">
          <div className="console-brand">
            <span className="brand console-wordmark">{wordmark}</span>
            <span className="console-legal">{legal} · jason</span>
          </div>
          {recordsAsOf && <span className="console-meta">Records as of {recordsAsOf}</span>}
          {showSignIn && (
            <label className="console-signin">
              Signed in as
              <select value={session.me} onChange={(e) => session.setMe(e.target.value)}>
                {!session.people.some((p) => p.name === session.me) && <option value="">pick a name</option>}
                {session.people.map((p) => (
                  <option key={p.name} value={p.name}>{p.role ? `${p.name}, ${p.role}` : p.name}</option>
                ))}
              </select>
            </label>
          )}
          {dock}
          <div role="radiogroup" aria-label="View as" className="console-seg">
            <button role="radio" aria-checked={!owner} onClick={() => onAudience("board")}>Board</button>
            <button role="radio" aria-checked={owner} onClick={() => onAudience("owner")}>Owner view</button>
          </div>
        </div>
      </header>
      <div className="console-body">
        {narrow ? (
          <label className="console-goto">
            Go to
            <select value={current} onChange={(e) => { onGo(e.target.value); try { window.scrollTo(0, 0); } catch { /* not every window scrolls */ } }}>
              {visible.map((s) => (
                <option key={s.id} value={s.id}>{s.group} · {nameOf(s, audience)}</option>
              ))}
            </select>
          </label>
        ) : (
          <nav aria-label="Duties" className="console-nav">
            {grouped.map((g) => (
              <div key={g.label} className="console-group">
                <p className="console-group-label">{g.label}</p>
                {g.items.map((s) => (
                  <button key={s.id} aria-current={s.id === current ? "page" : undefined} onClick={() => onGo(s.id)}>
                    {nameOf(s, audience)}{s.count ? ` (${s.count})` : ""}
                  </button>
                ))}
              </div>
            ))}
          </nav>
        )}
        <main className="console-main">
          {owner && <p className="console-owner-banner">{OWNER_BANNER}</p>}
          {children}
        </main>
        {pinned}
      </div>
      {floating}
    </div>
  );
}

/** The screen header pattern: an H1 in the brand font and a one-line muted summary. */
export function ScreenHeader({ title, summary, actions }: { title: ReactNode; summary?: ReactNode; actions?: ReactNode }) {
  return (
    <header className="screen-head">
      <div>
        <h1>{title}</h1>
        {summary && <p className="muted">{summary}</p>}
      </div>
      {actions && <div className="row wrap">{actions}</div>}
    </header>
  );
}
