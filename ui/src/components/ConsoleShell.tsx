import { useEffect, useRef, useState, type ReactNode } from "react";

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
  /** Who is signed in. With `account` (an officer signed in with Google), the header names them with a Sign out button
   * and there is no picker. Without it, the "Signed in as" picker (the chosen name and the people to choose from; hidden
   * with no one to pick) and `signInLinks`, one "Sign in with Google" link a provider. Hidden for owners. */
  session?: {
    me: string; setMe: (name: string) => void; people: readonly ConsolePerson[];
    account?: { name: string; role?: string; email?: string } | null;
    signInLinks?: readonly { label: string; href: string }[]; signInError?: string; onSignOut?: () => void;
    /** Under `jason-web --dev`, a signed-in admin's "View as": the people and offices to view the console as,
     * whom they view it as now (`acting`), and the change. Writes are refused while acting. */
    actAs?: { people: readonly ConsolePerson[]; roles: readonly string[]; acting?: { name: string; role: string } | null; onChange: (target: { name?: string; role?: string }) => void };
  };
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

/** The sticky header's height as `--console-bar-h` on the page root, kept current as it wraps (sign-in, the admin
 * view, the dock): the nav and a pinned drawer stick below it, and `scroll-padding-top` keeps a jumped-to heading
 * from landing under it. */
function useBarHeight() {
  const ref = useRef<HTMLElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof document === "undefined") return;
    const root = document.documentElement;
    const set = () => root.style.setProperty("--console-bar-h", `${Math.ceil(el.getBoundingClientRect().height)}px`);
    set();
    if (typeof ResizeObserver === "undefined") return () => root.style.removeProperty("--console-bar-h");
    const watch = new ResizeObserver(set);
    watch.observe(el);
    return () => { watch.disconnect(); root.style.removeProperty("--console-bar-h"); };
  }, []);
  return ref;
}

/** The screens an audience sees, in nav order. */
export function visibleScreens(screens: readonly ConsoleScreen[], audience: Audience): ConsoleScreen[] {
  return screens.filter((s) => audience === "board" || s.owner);
}

const nameOf = (s: ConsoleScreen, audience: Audience) => (audience === "owner" && s.ownerLabel) || s.label;

const actingValue = (a?: { name: string; role: string } | null) => (!a ? "" : a.name ? `p:${a.name}` : `r:${a.role}`);
const actingTarget = (v: string): { name?: string; role?: string } =>
  v.startsWith("p:") ? { name: v.slice(2) } : v.startsWith("r:") ? { role: v.slice(2) } : {};

/** The console's frame: a sticky header (wordmark, legal name, records date, the sign-in pick, the dock, the Board /
 * Owner view control), a grouped left nav that becomes a "Go to" select under 720px, the main column, and the slots
 * for a pinned or a floating drawer. The shell routes; it decides nothing. */
export function ConsoleShell({ wordmark, legal, recordsAsOf, groups, screens, current, onGo, audience, onAudience, session, dock, pinned, floating, children }: ConsoleShellProps) {
  const narrow = useNarrow();
  const bar = useBarHeight();
  const visible = visibleScreens(screens, audience);
  const owner = audience === "owner";
  const grouped = groups.map((g) => ({ label: g, items: visible.filter((s) => s.group === g) })).filter((g) => g.items.length);
  const account = !owner ? session?.account : null;
  const showPicker = !owner && !account && session && session.people.length > 0;
  const googleLinks = !owner && !account ? session?.signInLinks ?? [] : [];
  return (
    <div className="console">
      <header className="console-bar" ref={bar}>
        <div className="console-bar-inner">
          <div className="console-brand">
            <span className="brand console-wordmark">{wordmark}</span>
            <span className="console-legal">{legal} · jason</span>
          </div>
          {recordsAsOf && <span className="console-meta">Records as of {recordsAsOf}</span>}
          {account && (
            <span className="console-signin" title={account.email ? `${account.email}, signed in with Google` : "Signed in with Google"}>
              Signed in as <strong className="console-signin-name">{account.role ? `${account.name}, ${account.role}` : account.name}</strong>
              {session?.onSignOut && <button className="link" onClick={session.onSignOut}>Sign out</button>}
            </span>
          )}
          {account && session?.actAs && (
            <label className="console-signin console-actas">
              Admin view
              <select value={actingValue(session.actAs.acting)} onChange={(e) => session.actAs!.onChange(actingTarget(e.target.value))}>
                <option value="">myself</option>
                <optgroup label="A person">
                  {session.actAs.people.filter((p) => p.name !== account.name).map((p) => (
                    <option key={p.name} value={`p:${p.name}`}>{p.role ? `${p.name}, ${p.role}` : p.name}</option>
                  ))}
                </optgroup>
                <optgroup label="An office">
                  {session.actAs.roles.map((r) => <option key={r} value={`r:${r}`}>the {r}</option>)}
                </optgroup>
              </select>
            </label>
          )}
          {account && session?.actAs?.acting && (
            <span className="console-acting" role="status">
              Viewing as {session.actAs.acting.name || `the ${session.actAs.acting.role}`} (admin view): writes are off
            </span>
          )}
          {showPicker && (
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
          {googleLinks.map((l) => <a key={l.href} className="console-signin-google" href={l.href}>{l.label}</a>)}
          {!owner && session?.signInError && <span className="console-signin-error" role="alert">{session.signInError}</span>}
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
