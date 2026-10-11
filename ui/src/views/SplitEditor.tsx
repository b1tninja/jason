import { memo, useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { Badge, Confirm } from "../components";
import { useMediaQuery } from "../lib/useMediaQuery";
import { useSession, NO_PEOPLE } from "../lib/session";
import { PageGrid, type GridApi } from "./PageGrid";
import { ComparePane, KeyHelp, PageMenu, ZOOMS, Figure, type Zoom } from "./SplitPanes";
import { Drawer, EdgeTab, useOpenFocus } from "./SplitDrawer";
import { FlagsDialog, WalkBar } from "./SplitFlags";
import { MenuButton, ToolButton, Toolbar, type MenuEntry, type MenuSpec } from "./SplitMenus";
import { SegmentList, itemsOf } from "./SplitRail";
import { SplitReview } from "./SplitReview";
import { type Background, type SplitBackend } from "./splitApi";
import { FactsCache } from "./splitFacts";
import { PIN_PX, RAIL_OPEN_PX, fitCell, loadPrefs, resolveLayout, savePrefs, stripWindow, type LayoutPrefs } from "./splitLayout";
import {
  acceptable, everyNth, isTurn, marksIn, nextMark, sidewaysIn, sizeText, splitAtRestarts, splitOnBlanks, startsOf, type BlankKeep, type FlagsAnswer, type SegmentFlags,
  type SegmentRow, type SessionAnswer, type Suggestion, type Turn, type Turns,
} from "./splitModel";
import { SplitStore, type Snapshot } from "./splitStore";
import { ThumbLoader, fetchPicture } from "./splitThumbs";
import type { ClientPictures, PictureStatus } from "./splitClient";
import { budgetFor, pixelMegabytes } from "./splitWindow";
import { Loupe } from "./Loupe";
import { CORNERS, CORNER_WORDS, FINE_HOVER, LOUPE_MAX_PX, LOUPE_ZOOM_MAX, LOUPE_ZOOM_MIN, SERVER_MAX_PX, VIEWER_SIZES, clampViewerPx, clampZoom, loupeBudget, magnifierOn, releaseSharp, sharpLoader, zoomWords, type ViewerSize } from "./splitLoupe";
import "./split.css";

type View = "album" | "filmstrip" | "scroll" | "list";
const VIEWS: { id: View; words: string }[] = [
  { id: "album", words: "Album" }, { id: "filmstrip", words: "Filmstrip" }, { id: "scroll", words: "Scroll" }, { id: "list", words: "List" },
];
const PHONE = "(max-width: 719px)";
const PIN_QUERY = `(min-width: ${PIN_PX}px)`;
const BIG_QUERY = `(min-width: ${RAIL_OPEN_PX}px)`;
const ASPECT = 1.294;
const NO_SUGGESTIONS: ReadonlyMap<number, Suggestion> = new Map();

const deviceMemory = (): number | undefined => (typeof navigator !== "undefined" ? (navigator as unknown as { deviceMemory?: number }).deviceMemory : undefined);

interface Boot { store: SplitStore; facts: FactsCache; loader: ThumbLoader; first: SessionAnswer; pictures: ClientPictures | null }

/* Pictures: only a file chosen on this computer is drawn in the browser (its `LocalBackend.pictures`); every other draft's pictures are the server's,
 * asked for at the size the cell displays. */

/** The splitter's working screen for one draft (`#/setup/split/<id>`). It loads the draft, then hands a store (the draft and its queue of
 * saves), a facts cache, and a picture loader to the screen. Nothing per page is React state. */
export function SplitEditor({ backend, id }: { backend: SplitBackend; id: string }) {
  const { me } = useSession(NO_PEOPLE);
  const [boot, setBoot] = useState<Boot | { error: string } | null>(null);
  useEffect(() => {
    let live = true;
    const store = new SplitStore(backend, id, me);
    let pictures: ClientPictures | null = backend.pictures ?? null;
    const sized = { width: typeof window === "undefined" ? 1024 : window.innerWidth, deviceMemory: deviceMemory() };
    // With a browser source the loader is asked for `size:page` keys; the source falls back to the server's address by itself.
    const loader = new ThumbLoader({
      urlOf: (page, size) => (pictures ? `${size}:${page}` : backend.thumbUrl(id, page, size)),
      fetcher: (url, signal) => (pictures ? pictures.fetcher(url, signal) : fetchPicture(url, signal)),
      budget: budgetFor(sized),
    });
    if (pictures) { pictures.attach(loader); pictures.start(); }
    let facts: FactsCache | null = null;
    store.load().then(() => {
      const s = store.getSnapshot().session!;
      facts = new FactsCache(backend, id, s.source.pages);
      pictures?.useFacts((n) => facts?.get(n));
      if (live) setBoot({ store, facts, loader, first: s as SessionAnswer, pictures });
    }, (e: Error) => { if (live) setBoot({ error: e.message }); });
    return () => { live = false; loader.clear(); facts?.dispose(); if (pictures && pictures !== backend.pictures) pictures.dispose(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [backend, id]);
  useEffect(() => { if (boot && "store" in boot) boot.store.by = me; }, [boot, me]);
  if (!boot) return <p role="status" className="muted">Opening the draft…</p>;
  if ("error" in boot) {
    return <div role="alert" className="notice notice-error"><span>{boot.error}</span><a href="#/setup/split">Back to the splitter</a></div>;
  }
  return <EditorBody backend={backend} id={id} by={me} {...boot} />;
}

function Ticks({ pages, starts, suggestions, facts, version }: { pages: number; starts: ReadonlyMap<number, number>; suggestions: Suggestion[]; facts: FactsCache; version: number }) {
  const at = (p: number) => `${pages <= 1 ? 0 : ((p - 1) / (pages - 1)) * 100}%`;
  const blanks: number[] = [];
  if (pages <= 4000) for (let n = 1; n <= pages; n++) if (facts.get(n)?.blank === "blank") blanks.push(n);
  void version;
  return (
    <div className="split-ticks" aria-hidden="true">
      {blanks.map((p) => <i key={`b${p}`} className="tick-blank" style={{ left: at(p) }} />)}
      {suggestions.filter((s) => s.state === "open" && !starts.has(s.page)).map((s) => <i key={s.id} className="tick-sug" style={{ left: at(s.page) }} />)}
      {[...starts.keys()].map((p) => <i key={`s${p}`} className="tick-start" style={{ left: at(p) }} />)}
    </div>
  );
}
const TicksM = memo(Ticks);

/** The slim strip of numbered chips: every top-level segment, one tap to jump. It is the always-visible summary of the segments drawer. */
function SegmentStrip({ rows, page, flagged, onGo, onMore }: { rows: SegmentRow[]; page: number; flagged: ReadonlySet<string>; onGo(page: number): void; onMore(): void }) {
  const cur = (() => { let at = 0; rows.forEach((r, i) => { if (r.start <= page) at = i; }); return at; })();
  const { from, to } = stripWindow(rows.length, cur);
  const ref = useRef<HTMLOListElement>(null);
  useEffect(() => { ref.current?.querySelector<HTMLElement>("[aria-current=true]")?.scrollIntoView?.({ block: "nearest", inline: "nearest" }); }, [cur]);
  return (
    <nav className="split-strip" aria-label="Segments, as numbered chips">
      <ol ref={ref}>
        {from > 0 && <li><button type="button" className="split-chipbtn" onClick={onMore} aria-label={`${from} earlier segments: open the segments drawer`}>{`…${from}`}</button></li>}
        {rows.slice(from, to).map((r, i) => {
          const no = from + i + 1;
          const flag = flagged.has(r.key);
          return (
            <li key={r.key}>
              <button type="button" className="split-chipbtn" aria-current={from + i === cur ? "true" : undefined} onClick={() => onGo(r.start)} title={`Segment ${no}: pages ${r.start} to ${r.end}`}
                aria-label={`Go to segment ${no}, pages ${r.start} to ${r.end}${flag ? ", flagged" : ""}`}>
                <b>{no}</b><span aria-hidden="true">p.{r.start}</span>{flag && <span aria-hidden="true" className="split-chipflag">!</span>}
              </button>
            </li>
          );
        })}
        {to < rows.length && <li><button type="button" className="split-chipbtn" onClick={onMore} aria-label={`${rows.length - to} later segments: open the segments drawer`}>{`${rows.length - to}…`}</button></li>}
      </ol>
    </nav>
  );
}

type Tool = "nth" | "blanks" | "restarts" | "sideways" | "clear";
const TOOL_TITLE: Record<Tool, string> = { nth: "Every Nth page", blanks: "Blank pages", restarts: "Page-number restarts", sideways: "Sideways pages", clear: "Clear my marks" };

/** A small panel under the toolbar for a mark rule that needs a choice before it runs (a number, a plan to read). Esc or Close shuts it. */
function ToolPanel({ title, onClose, children }: { title: string; onClose(): void; children: React.ReactNode }) {
  const ref = useRef<HTMLElement>(null);
  useOpenFocus(true, ref);
  return (
    <section ref={ref} role="dialog" aria-modal="false" aria-label={title} tabIndex={-1} className="split-toolpanel" onKeyDown={(e) => { if (e.key === "Escape") { e.stopPropagation(); e.preventDefault(); onClose(); } }}>
      <div className="split-toolpanel-head"><h2>{title}</h2><button type="button" onClick={onClose}>Close</button></div>
      <div className="split-toolpanel-body">{children}</div>
    </section>
  );
}

const NO_STATUS = { subscribe: () => () => undefined, get: (): PictureStatus | null => null };
const NO_BACKGROUND = { subscribe: () => () => undefined, get: (): Background | null => null };

function EditorBody({ backend, id, by, store, facts, loader, first, pictures }: { backend: SplitBackend; id: string; by: string } & Boot) {
  const snap: Snapshot = useSyncExternalStore(store.subscribe, store.getSnapshot, store.getSnapshot);
  const factsVersion = useSyncExternalStore(facts.subscribe, facts.getVersion, facts.getVersion);
  const pic = pictures ? { subscribe: pictures.subscribe, get: pictures.getStatus } : NO_STATUS;
  const pictureStatus = useSyncExternalStore(pic.subscribe, pic.get, pic.get);
  const bgSource = backend.background ?? NO_BACKGROUND;
  const background = useSyncExternalStore(bgSource.subscribe, bgSource.get, bgSource.get);
  // a local file is not yet a draft on the server: its marks are held here until it is
  const notYet = !!background && background.phase !== "saved";
  // the server's draft has arrived: read it again for its starts and suggestions, and ask for the measures that were waiting
  useEffect(() => backend.onServer?.(() => { void store.reload(); facts.refresh(); }), [backend, store, facts]);
  // a page the browser drew white before the server had measured it is checked when its measure arrives
  useEffect(() => { pictures?.reconcile(); }, [pictures, factsVersion]);
  // suggestions and flags follow the measures: when the last page being measured is done, the draft is read again
  const sawPending = useRef(false);
  useEffect(() => {
    if (notYet) return;
    const p = facts.progress();
    if (p.pending > 0) sawPending.current = true;
    else if (sawPending.current && p.known > 0) { sawPending.current = false; void store.reload(); }
  }, [facts, store, factsVersion, notYet]);
  const session = snap.session!;
  const pages = session.source.pages;
  const confidential = !!first.confidential || session.source.confidential;
  const phone = useMediaQuery(PHONE);
  const big = useMediaQuery(BIG_QUERY);
  const canPinQuery = useMediaQuery(PIN_QUERY);
  const canPin = canPinQuery && !phone;
  const lowMemory = (deviceMemory() ?? 8) <= 2;

  // ---- the layout: focus, the drawers, and what is shown; kept for the tab
  const [prefs, setPrefsState] = useState<LayoutPrefs>(() => loadPrefs(id));
  const setPrefs = useCallback((patch: Partial<LayoutPrefs>) => setPrefsState((p) => { const n = { ...p, ...patch }; savePrefs(id, n); return n; }), [id]);
  const { railOpen, docked } = resolveLayout(prefs, { big, canPin });
  const [inspect, setInspect] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  const [reviewBusy, setReviewBusy] = useState(false);
  const [tool, setTool] = useState<Tool | null>(null);
  const showSug = prefs.showSuggestions;
  const setRail = useCallback((open: boolean) => { setPrefs({ rail: open }); if (open && phone) setInspect(false); }, [setPrefs, phone]);
  const openInspect = useCallback((open: boolean) => { setInspect(open); if (open && phone) setPrefs({ rail: false }); }, [setPrefs, phone]);

  const [view, setViewState] = useState<View>(phone || lowMemory ? "list" : "album");
  const [scrollAxis, setScrollAxis] = useState<"y" | "x">("y");
  const [albumW, setAlbumW] = useState(phone ? 92 : 124);
  const [focus, setFocusRaw] = useState(1);
  const focusRef = useRef(1);                                  // the latest focus, for keys that arrive faster than a render
  const setFocusState = useCallback((p: number) => { focusRef.current = p; setFocusRaw(p); }, []);
  const [anchor, setAnchor] = useState<number | null>(null);
  const [selection, setSelection] = useState<{ a: number; b: number } | null>(null);
  const [menu, setMenu] = useState<number | null>(null);
  const [help, setHelp] = useState(false);
  const [zoom, setZoom] = useState<Zoom>("fit");
  const [drop, setDrop] = useState<number[]>(() => { try { return JSON.parse(sessionStorage.getItem(`jason-split-drop-${id}`) ?? "[]"); } catch { return []; } });
  // pages to turn in the new files only (the original and the pictures are never changed); kept for the tab like the pages to leave out
  const [turns, setTurnsState] = useState<Turns>(() => {
    try {
      const raw = JSON.parse(sessionStorage.getItem(`jason-split-turns-${id}`) ?? "{}") as Record<string, unknown>;
      return Object.fromEntries(Object.entries(raw).filter(([k, v]) => Number.isInteger(Number(k)) && isTurn(v)).map(([k, v]) => [Number(k), v as Turn]));
    } catch { return {}; }
  });
  const setTurns = useCallback((t: Turns) => {
    setTurnsState(t);
    try { sessionStorage.setItem(`jason-split-turns-${id}`, JSON.stringify(t)); } catch { /* storage blocked */ }
  }, [id]);
  const setTurnOf = useCallback((page: number, t: Turn | null) => {
    setTurnsState((cur) => {
      const next: Record<number, Turn> = { ...cur };
      if (t === null) delete next[page]; else next[page] = t;
      try { sessionStorage.setItem(`jason-split-turns-${id}`, JSON.stringify(next)); } catch { /* storage blocked */ }
      return next;
    });
  }, [id]);
  const [showRejected, setShowRejected] = useState(false);
  const [viewTo, setViewTo] = useState<number | undefined>(undefined);
  // the server's pre-review flags of each segment (read again whenever the saved draft or the measured facts change)
  const [flags, setFlags] = useState<FlagsAnswer | null>(null);
  const [flagView, setFlagView] = useState<{ flags: SegmentFlags; no: number } | null>(null);
  const [walk, setWalk] = useState<{ pages: number[]; at: number; why: string } | null>(null);
  const [sidewaysSeen, setSidewaysSeen] = useState<number | null>(null);
  const gridRef = useRef<GridApi>(null);
  const stripRef = useRef<GridApi>(null);
  const goRef = useRef<HTMLInputElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const chose = useRef(false);
  const setView = (v: View) => { chose.current = true; setViewState(v); setViewTo(focus); };
  // until a person picks a view, the default follows the screen (the list on a phone, the album elsewhere)
  useEffect(() => { if (!chose.current) setViewState(phone || lowMemory ? "list" : "album"); }, [phone, lowMemory]);
  useEffect(() => { try { sessionStorage.setItem(`jason-split-drop-${id}`, JSON.stringify(drop)); } catch { /* storage blocked */ } }, [id, drop]);

  // focus mode: the console's header and menu give way (split.css, `html[data-split-focus]`)
  useEffect(() => {
    const root = document.documentElement;
    if (prefs.focus) root.setAttribute("data-split-focus", ""); else root.removeAttribute("data-split-focus");
    return () => root.removeAttribute("data-split-focus");
  }, [prefs.focus]);

  // the room the pages have: the album fills it with whole columns, and the scroll views size a page to it
  const [room, setRoom] = useState({ w: 0, h: 0 });
  useEffect(() => {
    const wrap = wrapRef.current;
    if (!wrap || typeof ResizeObserver === "undefined") return;
    const read = () => {
      const box = wrap.querySelector<HTMLElement>(".split-scroll");
      const w = box?.clientWidth ?? 0, h = wrap.clientHeight;
      setRoom((r) => (r.w === w && r.h === h ? r : { w, h }));
    };
    read();
    const ro = new ResizeObserver(read);
    ro.observe(wrap);
    const box = wrap.querySelector<HTMLElement>(".split-scroll");
    if (box) ro.observe(box);
    return () => ro.disconnect();
  }, [view, scrollAxis]);
  // The scroll box keeps its scrollbar's room (scrollbar-gutter in split.css) so a scrollbar appearing does not change the width the columns
  // are fitted to, which would remount the cell a person is on; without that property a scrollbar's width is left out up front.
  const reserve = typeof CSS !== "undefined" && CSS.supports?.("scrollbar-gutter: stable") ? 0 : 18;
  const cellW = view === "album" && prefs.fill && room.w > 0 ? fitCell(room.w - 8 - reserve, albumW).cell : albumW;
  // When the columns refit, or a mark moves pages to other rows, the grid re-lays its rows and may remount the cell a person is on (its
  // window is one render behind the new layout); the focus is given back to the page afterwards.
  const lastLayout = useRef({ cellW, segs: snap.segs });
  const hadCellFocus = useRef(false);
  if ((cellW !== lastLayout.current.cellW || snap.segs !== lastLayout.current.segs) && typeof document !== "undefined") {
    hadCellFocus.current = !!wrapRef.current?.contains(document.activeElement) && document.activeElement !== wrapRef.current;
    lastLayout.current = { cellW, segs: snap.segs };
  }
  useEffect(() => {
    if (!hadCellFocus.current) return;
    hadCellFocus.current = false;
    // the grid settles its window a frame after a refit, so look after two frames
    cancelAnimationFrame(refocus.current);
    refocus.current = requestAnimationFrame(() => { refocus.current = requestAnimationFrame(() => {
      if (!document.activeElement || document.activeElement === document.body) gridRef.current?.focusPage(focusRef.current);
    }); });
  });
  const refocus = useRef(0);
  useEffect(() => () => cancelAnimationFrame(refocus.current), []);
  const scrollMaxW = scrollAxis === "y" ? Math.max(320, Math.min(1100, room.h > 0 ? Math.round((room.h - 40) / ASPECT) : 520)) : Math.max(300, Math.min(720, room.h > 0 ? Math.round((room.h - 40) / ASPECT) : 360));

  const setFocus = useCallback((p: number) => setFocusState(Math.max(1, Math.min(pages, p))), [pages]);
  const active = () => (view === "filmstrip" ? stripRef.current : view === "list" ? null : gridRef.current);
  const goTo = useCallback((p: number, keyboard = true) => {
    const n = Math.max(1, Math.min(pages, p));
    setFocusState(n);
    if (keyboard) { active()?.focusPage(n); } else active()?.scrollToPage(n);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pages, view]);

  // switching view keeps the page in view
  useEffect(() => {
    const t = requestAnimationFrame(() => { if (view === "list") return; active()?.scrollToPage(focus, true); });
    return () => cancelAnimationFrame(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view, scrollAxis]);

  // the browser says it is back online: send what was held
  useEffect(() => {
    const on = () => store.retry();
    window.addEventListener("online", on);
    return () => window.removeEventListener("online", on);
  }, [store]);
  // marks not yet saved are not lost to a closing tab without a word
  useEffect(() => {
    const on = (e: BeforeUnloadEvent) => { if (snap.pending > 0 && (snap.save === "offline" || snap.save === "error")) { e.preventDefault(); e.returnValue = ""; } };
    window.addEventListener("beforeunload", on);
    return () => window.removeEventListener("beforeunload", on);
  }, [snap.pending, snap.save]);

  // flags are read once the draft is saved and again when more facts arrive; a failure only leaves them out (they are readings, not needs)
  const settled = snap.save === "saved" && snap.pending === 0 && !notYet;
  useEffect(() => {
    if (!settled || session.status === "declined") return;
    let live = true;
    const t = setTimeout(() => { backend.session(id, { flags: true }).then((a) => { if (live) setFlags(a.flags ?? null); }, () => undefined); }, 250);
    return () => { live = false; clearTimeout(t); };
  }, [backend, id, settled, snap.version, factsVersion, session.status]);
  const flagsByRange = useMemo(() => new Map((flags?.segments ?? []).map((f) => [`${f.level}:${f.start}-${f.end}`, f])), [flags]);
  const flagsOf = useCallback((s: SegmentRow) => flagsByRange.get(`${s.level}:${s.start}-${s.end}`), [flagsByRange]);

  const segRows: SegmentRow[] = useMemo(() => {
    const server = new Map(session.segments.map((s) => [s.start, s]));
    return snap.segs.map((s) => ({ key: s.key, path: s.key, start: s.start, end: s.end, pages: s.end - s.start + 1, level: s.level, parent: "", source: s.start === 1 ? "first" : server.get(s.start)?.source ?? "person", labels: server.get(s.start)?.labels ?? {} }));
  }, [snap.segs, session.segments]);
  // the album's bands: one per top-level document, with the title the server has for its first page (a guess until confirmed)
  const bands = useMemo(() => segRows.filter((s) => s.level === 0).map((s, i) => ({ no: i + 1, start: s.start, end: s.end, label: s.labels.title || undefined })), [segRows]);
  const topRows = useMemo(() => segRows.filter((s) => s.level === 0), [segRows]);
  const topCount = topRows.length;
  const openSug = session.suggestions.filter((s) => s.state === "open");
  const high = useMemo(() => acceptable(session.suggestions, 0.85), [session.suggestions]);
  const medium = useMemo(() => acceptable(session.suggestions, 0.6), [session.suggestions]);
  const items = useMemo(() => itemsOf(segRows, showSug ? session.suggestions : [], showRejected, flagsOf), [segRows, session.suggestions, showSug, showRejected, flagsOf]);
  const flaggedTop = useMemo(() => (flags?.segments ?? []).filter((f) => f.level === 0 && f.flagged).length, [flags]);
  const flaggedKeys = useMemo(() => new Set((flags?.segments ?? []).filter((f) => f.flagged).map((f) => f.segment)), [flags]);
  const startOfKey = useCallback((key: string) => flags?.segments.find((f) => f.segment === key)?.start ?? null, [flags]);
  const onFlags = useCallback((_s: SegmentRow, no: number, f: SegmentFlags) => setFlagView({ flags: f, no }), []);
  const startWalk = useCallback((pages: number[], why: string) => {
    if (!pages.length) return;
    setReviewing(false); setWalk({ pages, at: 0, why }); setFocus(pages[0]); setViewTo(pages[0]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const stepWalk = (d: 1 | -1) => {
    if (!walk) return;
    const at = Math.max(0, Math.min(walk.pages.length - 1, walk.at + d));
    setWalk({ ...walk, at });
    goTo(walk.pages[at], false);
    setViewTo(walk.pages[at]);
  };
  const segItems = useMemo(() => items.filter((i) => i.kind === "seg"), [items]);
  const sugItems = useMemo(() => items.filter((i) => i.kind === "sug"), [items]);
  const marks = useMemo(() => marksIn(snap.starts, showSug ? session.suggestions : []), [snap.starts, showSug, session.suggestions]);
  const sugByPage = showSug ? snap.sugByPage : NO_SUGGESTIONS;
  // the grid reads suggestions from the snapshot; with them hidden it is given one that has none
  const gridSnap: Snapshot = useMemo(() => (showSug ? snap : { ...snap, sugByPage: NO_SUGGESTIONS as Snapshot["sugByPage"] }), [snap, showSug]);
  const readOnly = snap.readOnly;
  const startOf = (page: number) => { for (let p = page; p >= 1; p--) if (snap.starts.has(p)) return p; return 1; };

  // ---- acts from the grid and the keys
  const onActivate = useCallback((page: number, shift: boolean) => {
    setFocus(page);
    if (shift && anchor !== null) { setSelection({ a: anchor, b: page }); return; }
    setAnchor(page); setSelection(null);
    if (view === "filmstrip") return;
    store.toggle(page);
  }, [anchor, setFocus, store, view]);
  const onMenu = useCallback((page: number) => { setFocus(page); setMenu(page); }, [setFocus]);
  const onMove = useCallback((from: number, to: number) => { store.move(from, to); setFocus(to); }, [store, setFocus]);
  const onFocusPage = useCallback((page: number) => setFocusState(page), []);

  const [message, setMessage] = useState("");
  useEffect(() => { setMessage(snap.message); }, [snap.message]);

  const step = (d: number, extend: boolean) => {
    const cur = focusRef.current;
    const n = Math.max(1, Math.min(pages, cur + d));
    if (extend) { const a = anchor ?? cur; setAnchor(a); setSelection({ a, b: n }); }
    goTo(n);
  };

  const toggleFocus = () => setPrefs({ focus: !prefs.focus });

  // ---- the magnifier (section 5.12): on for a mouse or trackpad that hovers, off for touch, until a person chooses
  const fineHover = useMediaQuery(FINE_HOVER);
  const magOn = magnifierOn(prefs.magnifier, fineHover);
  const magTouch = prefs.magnifier === true;
  const toggleMagnifier = (on = !magOn) => {
    setPrefs({ magnifier: on });
    const fixedWords = prefs.magMode === "fixed";
    setMessage(on
      ? (phone || !fineHover ? `Magnifier on. Press and hold a page, then drag to magnify it${fixedWords ? " in the band above the action bar" : ""}.`
        : fixedWords ? `Magnifier on, in a fixed viewer at the ${CORNER_WORDS[prefs.magCorner].toLowerCase()}. Hold the pointer over a page to magnify it.` : "Magnifier on. Hold the pointer over a page to magnify it.")
      : "Magnifier off.");
  };
  const setMagMode = (mode: "lens" | "fixed") => {
    setPrefs({ magMode: mode });
    setMessage(mode === "fixed" ? `Magnifier: a fixed viewer in the ${CORNER_WORDS[prefs.magCorner].toLowerCase()}.` : "Magnifier: a lens that follows the pointer.");
  };
  const setMagZoom = useCallback((z: number) => setPrefs({ magnifierZoom: clampZoom(z) }), [setPrefs]);
  const sharp = useMemo(() => sharpLoader({
    drawLarge: pictures ? (page, px, signal) => pictures.drawLarge(page, px, signal) : undefined,
    server: (page, signal) => (pictures ? pictures.fetcher(`huge:${page}`, signal) : fetchPicture(backend.thumbUrl(id, page, "huge"), signal)),
  }), [backend, id, pictures]);
  const magBudget = useMemo(() => loupeBudget(pixelMegabytes(), lowMemory), [lowMemory]);
  const dockedRail = docked === "rail";
  const closeTopLayer = (): boolean => {
    if (tool) { setTool(null); return true; }
    if (inspect && docked !== "inspect") { setInspect(false); return true; }
    if (railOpen && !dockedRail) { setRail(false); return true; }
    return false;
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    const t = e.target as HTMLElement;
    if (t.closest("input, textarea, select, [role=dialog], [data-viewer]")) return;
    if (reviewing) return;
    const focus = focusRef.current;
    const k = e.key;
    if (e.ctrlKey || e.metaKey) {
      if (k.toLowerCase() === "z") { e.preventDefault(); if (e.shiftKey) store.redo(); else store.undo(); }
      else if (k.toLowerCase() === "y") { e.preventDefault(); store.redo(); }
      return;
    }
    if (e.altKey) return;
    const lower = k.length === 1 ? k.toLowerCase() : k;
    // the layout keys work from anywhere on the screen, a toolbar button or a drawer included
    switch (lower) {
      case "f": e.preventDefault(); toggleFocus(); return;
      // `M` is taken (merge a segment with the one before), so the magnifier is on `E`
      case "e": e.preventDefault(); toggleMagnifier(); return;
      case "s": e.preventDefault(); setRail(!railOpen); return;
      case "c": e.preventDefault(); openInspect(!inspect); return;
      case "?": e.preventDefault(); setHelp(true); return;
      case "Escape":
        if (menu !== null || help) return;
        if (selection) setSelection(null);
        else if (!closeTopLayer() && prefs.focus) setPrefs({ focus: false });
        return;
      default:
    }
    if (t.closest("[role=toolbar], [role=menu], [data-drawer]")) return;
    const cols = gridRef.current?.cols() ?? 1;
    // rows hold different page counts once the album has bands, so a row step is asked of the grid
    const rowStep = (rows: number) => gridRef.current?.rowDelta(focusRef.current, rows) ?? rows * cols;
    const horizontal = view === "filmstrip" || (view === "scroll" && scrollAxis === "x");
    const stepsOf: Record<string, number> = view === "scroll" && scrollAxis === "y"
      ? { ArrowUp: -1, ArrowDown: 1, ArrowLeft: -1, ArrowRight: 1 }
      : horizontal ? { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -1, ArrowDown: 1 }
      : { ArrowLeft: -1, ArrowRight: 1, ArrowUp: rowStep(-1), ArrowDown: rowStep(1) };
    if (k in stepsOf && view !== "list") { e.preventDefault(); step(stepsOf[k], e.shiftKey); return; }
    switch (lower) {
      case "Home": e.preventDefault(); goTo(1); return;
      case "End": e.preventDefault(); goTo(pages); return;
      case "PageUp": e.preventDefault(); goTo(focus + rowStep(-3)); return;
      case "PageDown": e.preventDefault(); goTo(focus + rowStep(3)); return;
      case "Enter": case " ":
        if (view === "filmstrip") { e.preventDefault(); store.toggle(focus); setAnchor(focus); }
        return;
      case "n": case "p": { const m = nextMark(marks, focus, lower === "n" ? 1 : -1); if (m !== null) { e.preventDefault(); goTo(m); } return; }
      case "a": { const s = sugByPage.get(focus); if (s) { e.preventDefault(); store.accept([s.id]); } return; }
      case "x": { const s = sugByPage.get(focus); if (s) { e.preventDefault(); store.reject([s.id]); } return; }
      case "m": { e.preventDefault(); const at = startOf(focus); if (at === 1) setMessage("The first page always starts a segment."); else store.unmark([at]); return; }
      case "[": case "]": { if (snap.starts.has(focus) && focus > 1) { e.preventDefault(); const to = focus + (lower === "]" ? 1 : -1); if (to > 1 && to <= pages) { store.move(focus, to); goTo(to); } } return; }
      case "l": e.preventDefault(); setMenu(focus); return;
      case "g": case "/": e.preventDefault(); goRef.current?.focus(); goRef.current?.select(); return;
      case "v": e.preventDefault(); setView(VIEWS[(VIEWS.findIndex((v) => v.id === view) + 1) % VIEWS.length].id); return;
      case "1": case "2": case "3": case "4": e.preventDefault(); setView(VIEWS[Number(lower) - 1].id); return;
      case "+": case "=": e.preventDefault(); if (inspect) setZoom(ZOOMS[Math.min(2, ZOOMS.findIndex((z) => z.id === zoom) + 1)].id); else setAlbumW((w) => Math.min(220, w + 16)); return;
      case "-": e.preventDefault(); if (inspect) setZoom(ZOOMS[Math.max(0, ZOOMS.findIndex((z) => z.id === zoom) - 1)].id); else setAlbumW((w) => Math.max(64, w - 16)); return;
      case "z": e.preventDefault(); if (e.shiftKey) store.redo(); else store.undo(); return;
      case "y": e.preventDefault(); store.redo(); return;
      default:
    }
  };

  // A key pressed while the focus is on the page itself (the cell a person was on was remounted, or a menu closed over nothing) is still
  // the screen's: it is handled as if it came from the grid, unless a dialog is open.
  const keys = useRef(onKeyDown); keys.current = onKeyDown;
  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      if (e.target !== document.body || e.defaultPrevented || document.querySelector("[role=dialog][aria-modal=true]")) return;
      keys.current(e as unknown as React.KeyboardEvent);
    };
    document.addEventListener("keydown", on);
    return () => document.removeEventListener("keydown", on);
  }, []);

  // a double click on a page opens the compare drawer on it
  const onDoubleClick = (e: React.MouseEvent) => {
    const b = (e.target as HTMLElement).closest?.<HTMLElement>("button.split-cell-btn");
    const page = Number(b?.dataset.page);
    if (!page) return;
    setFocus(page); openInspect(true);
  };

  // ---- the page menu
  const menuSug = menu !== null ? sugByPage.get(menu) : undefined;
  const selSize = selection ? Math.abs(selection.b - selection.a) + 1 : 0;
  const lo = selection ? Math.min(selection.a, selection.b) : 1, hi = selection ? Math.max(selection.a, selection.b) : pages;

  // ---- bulk acts
  const [nth, setNth] = useState(2);
  const [blankKeep, setBlankKeep] = useState<BlankKeep>("before");
  const [blankPlan, setBlankPlan] = useState<ReturnType<typeof splitOnBlanks> | null>(null);
  const [duplexOk, setDuplexOk] = useState(false);
  const [restarts, setRestarts] = useState<number[] | null>(null);
  const [loadingFacts, setLoadingFacts] = useState(false);
  const nthPages = useMemo(() => everyNth(selection ? lo : 1, selection ? hi : pages, nth, snap.starts), [selection, lo, hi, pages, nth, snap.starts]);
  const readAll = async () => { setLoadingFacts(true); await facts.loadAll(); setLoadingFacts(false); };
  const planBlanks = async (keep: BlankKeep) => { await readAll(); setBlankPlan(splitOnBlanks(facts.all(), pages, keep)); };
  const findRestarts = async () => { await readAll(); setRestarts(splitAtRestarts(facts.all(), pages).filter((p) => !snap.starts.has(p))); };

  const saveWords = snap.save === "saving" ? "Saving…" : snap.save === "saved" ? (snap.savedAt ? `Draft saved ${snap.savedAt}` : "Draft saved") : snap.save === "offline" ? "Offline: marks held on this device" : snap.save === "conflict" ? "Not saved: the draft changed elsewhere" : "Not saved";
  const prog = facts.progress();
  const label = confidential ? "A confidential file" : session.source.kind === "demo" ? `${pages} made-up pages` : `${pages} pages, ${sizeText(session.source.size)}${session.source.sha256 ? `, ${session.source.sha256.slice(0, 8)}` : ""}`;
  const reviewOff = readOnly || snap.pending > 0 || snap.save !== "saved" || notYet;
  const guardMsg = readOnly ? `This split is ${session.status}.` : notYet ? "Wait for the file to finish saving on the server." : "Wait for the draft to finish saving.";
  const undoOff = readOnly || (session.counts.undo === 0 && snap.pending === 0);
  const redoOff = readOnly || session.counts.redo === 0;

  const jump = (e: React.FormEvent) => {
    e.preventDefault();
    const v = Number(goRef.current?.value);
    if (Number.isInteger(v) && v >= 1 && v <= pages) goTo(v);
    else setMessage(`This file has ${pages} pages.`);
  };

  const common = { count: pages, snap: gridSnap, facts, loader, focus, selection, confidential, turns, onMenu, onMove, onFocusPage, noLongPress: magTouch };
  const prevPage = focus > 1 ? focus - 1 : null;
  const prevSegFirst = (() => { const at = startOf(focus); if (at <= 1) return null; return startOf(at - 1); })();
  const goMark = (d: 1 | -1) => { const m = nextMark(marks, focus, d); if (m !== null) goTo(m); };

  // ---- the menus: every item says what it does, with its count where it is a bulk act
  const nextOff = nextMark(marks, focus, 1) === null, prevOff = nextMark(marks, focus, -1) === null;
  const cols = view === "album" ? gridRef.current?.cols() ?? 0 : 0;
  const checkbox = (label: string, checked: boolean, onSelect: () => void, more: Partial<Extract<MenuEntry, { type: "item" }>> = {}): MenuEntry => ({ type: "item", role: "menuitemcheckbox", checked, label, onSelect, ...more });
  const radio = (label: string, checked: boolean, onSelect: () => void, more: Partial<Extract<MenuEntry, { type: "item" }>> = {}): MenuEntry => ({ type: "item", role: "menuitemradio", checked, label, onSelect, ...more });
  const draftEntries: MenuEntry[] = [
    { type: "item", label: "All drafts", href: "#/setup/split", onSelect: () => undefined },
    { type: "item", label: "Undo", keys: "Z", disabled: undoOff, onSelect: () => store.undo() },
    { type: "item", label: "Redo", keys: "Y", disabled: redoOff, onSelect: () => store.redo() },
    { type: "sep" },
    { type: "heading", label: saveWords },
    ...(snap.save === "offline" || snap.save === "error" ? [{ type: "item", label: "Retry saving now", onSelect: () => store.retry() } as MenuEntry] : []),
    ...(snap.restorable > 0 ? [{ type: "item", label: `Restore ${snap.restorable} unsaved starts from earlier`, onSelect: () => store.restore() } as MenuEntry] : []),
    { type: "sep" },
    { type: "item", label: reviewOff ? `Review and split (${guardMsg})` : "Review and split…", disabled: reviewOff, onSelect: () => setReviewing(true) },
  ];
  const viewEntries: MenuEntry[] = [
    { type: "heading", label: "Pages as" },
    ...VIEWS.map((v, i) => radio(v.words, view === v.id, () => setView(v.id), { keys: String(i + 1) })),
    checkbox(scrollAxis === "x" ? "Scrolling across (turn to down)" : "Scroll across", scrollAxis === "x", () => setScrollAxis(scrollAxis === "y" ? "x" : "y"), { disabled: view !== "scroll" }),
    { type: "sep" },
    { type: "heading", label: view === "album" ? `Size and columns (${cols} columns across)` : "Size and columns" },
    { type: "item", label: "Larger pages", keys: "+", disabled: view !== "album", onSelect: () => setAlbumW((w) => Math.min(220, w + 16)) },
    { type: "item", label: "Smaller pages", keys: "-", disabled: view !== "album", onSelect: () => setAlbumW((w) => Math.max(64, w - 16)) },
    checkbox("Fill the width with whole columns", prefs.fill, () => setPrefs({ fill: !prefs.fill }), { disabled: view !== "album" }),
    { type: "sep" },
    { type: "heading", label: "Show" },
    checkbox("Suggestions", showSug, () => setPrefs({ showSuggestions: !showSug })),
    checkbox("Flags", prefs.showFlags, () => setPrefs({ showFlags: !prefs.showFlags })),
    checkbox("Rejected suggestions", showRejected, () => setShowRejected(!showRejected), { disabled: !showSug }),
    { type: "sep" },
    { type: "heading", label: "Magnifier" },
    checkbox(`Magnifier (${magOn ? "on" : "off"})`, magOn, () => toggleMagnifier(), { keys: "E" }),
    ...Array.from({ length: LOUPE_ZOOM_MAX - LOUPE_ZOOM_MIN + 1 }, (_, i) => LOUPE_ZOOM_MIN + i).map((z) =>
      radio(`Magnifier zoom: ${zoomWords(z)} the page`, prefs.magnifierZoom === z, () => setMagZoom(z), { disabled: !magOn })),
    radio("Mode: lens follows the pointer", prefs.magMode === "lens", () => setMagMode("lens")),
    radio("Mode: fixed corner viewer", prefs.magMode === "fixed", () => setMagMode("fixed")),
    ...CORNERS.map((c) => radio(`Viewer corner: ${CORNER_WORDS[c].toLowerCase()}`, prefs.magCorner === c, () => setPrefs({ magCorner: c }), { disabled: prefs.magMode !== "fixed" || phone })),
    ...(Object.keys(VIEWER_SIZES) as ViewerSize[]).map((k) =>
      radio(`Viewer size: ${k} (${VIEWER_SIZES[k]} px)`, prefs.magPx === VIEWER_SIZES[k], () => setPrefs({ magPx: VIEWER_SIZES[k] }), { disabled: prefs.magMode !== "fixed" || phone })),
    radio("Viewer shows: a magnified region", prefs.magView === "region", () => setPrefs({ magView: "region" }), { disabled: prefs.magMode !== "fixed" }),
    radio("Viewer shows: the whole page", prefs.magView === "page", () => setPrefs({ magView: "page" }), { disabled: prefs.magMode !== "fixed" }),
    checkbox("Do not hop (keep the viewer in its corner)", !prefs.magHop, () => setPrefs({ magHop: !prefs.magHop }), { disabled: prefs.magMode !== "fixed" || phone }),
    { type: "sep" },
    { type: "heading", label: "Panels" },
    checkbox("Focus: hide the console's menu and header", prefs.focus, toggleFocus, { keys: "F" }),
    checkbox("Segments drawer", railOpen, () => setRail(!railOpen), { keys: "S" }),
    checkbox("Compare drawer", inspect, () => openInspect(!inspect), { keys: "C" }),
    radio("Segments drawer on the left", prefs.railSide === "left", () => setPrefs({ railSide: "left" }), { disabled: phone }),
    radio("Segments drawer on the right", prefs.railSide === "right", () => setPrefs({ railSide: "right" }), { disabled: phone }),
    checkbox(canPin ? "Pin the segments drawer open" : "Pin the segments drawer open (needs a wider screen)", dockedRail, () => setPrefs({ pinned: dockedRail ? "none" : "rail", rail: true }), { disabled: !canPin }),
  ];
  const markEntries: MenuEntry[] = [
    { type: "item", label: snap.busy ? "Suggest splits (working…)" : "Suggest splits", disabled: readOnly || snap.busy, onSelect: () => store.suggest() },
    { type: "item", label: `Accept ${high.length} at High confidence`, disabled: readOnly || high.length === 0, onSelect: () => store.acceptBand("high") },
    { type: "item", label: `Accept ${medium.length} at Medium or better`, disabled: readOnly || medium.length === 0, onSelect: () => store.acceptBand("medium") },
    { type: "sep" },
    { type: "item", label: "Every Nth page…", onSelect: () => setTool("nth") },
    { type: "item", label: "Split on blank pages…", onSelect: () => setTool("blanks") },
    { type: "item", label: "At page-number restarts…", onSelect: () => setTool("restarts") },
    { type: "sep" },
    { type: "item", label: `Clear all my marks (${snap.starts.size - 1})…`, disabled: readOnly || snap.starts.size <= 1, onSelect: () => setTool("clear") },
  ];
  const pageEntries: MenuEntry[] = [
    { type: "item", label: `Menu for page ${focus}…`, keys: "L", onSelect: () => setMenu(focus) },
    { type: "item", label: "Find and fix sideways pages…", onSelect: () => setTool("sideways") },
    { type: "sep" },
    { type: "item", label: "Next start or suggestion", keys: "N", disabled: nextOff, onSelect: () => goMark(1) },
    { type: "item", label: "Previous start or suggestion", keys: "P", disabled: prevOff, onSelect: () => goMark(-1) },
    { type: "item", label: "First page", keys: "Home", onSelect: () => goTo(1) },
    { type: "item", label: "Last page", keys: "End", onSelect: () => goTo(pages) },
    { type: "item", label: "Jump to a page…", keys: "/", moves: true, onSelect: () => { goRef.current?.focus(); goRef.current?.select(); } },
  ];
  const helpEntries: MenuEntry[] = [{ type: "item", label: "Keyboard map", keys: "?", onSelect: () => setHelp(true) }];
  const menus = {
    draft: { id: "draft", label: "Draft", entries: draftEntries } as MenuSpec,
    view: { id: "view", label: "View", entries: viewEntries } as MenuSpec,
    mark: { id: "mark", label: "Mark", entries: markEntries } as MenuSpec,
    pages: { id: "pages", label: "Pages", entries: pageEntries } as MenuSpec,
    help: { id: "help", label: "Help", entries: helpEntries, align: "end" } as MenuSpec,
    // on a phone one View menu holds the draft's links and the help too
    phone: { id: "view", label: "View", entries: [...viewEntries, { type: "sep" }, { type: "heading", label: "Draft and help" }, draftEntries[0], ...helpEntries] } as MenuSpec,
  };

  const railH = Math.max(220, Math.round((typeof window === "undefined" ? 800 : window.innerHeight) * 0.36));
  const railBody = (
    <div className="split-rail-body">
      <h3>Segments ({topCount}{snap.segs.length > topCount ? `, ${snap.segs.length - topCount} nested` : ""})</h3>
      <SegmentList items={segItems} loader={loader} tall compact flagLine={prefs.showFlags} onFlags={onFlags} readOnly={readOnly} confidential={confidential} label="Segments" height={railH} currentPage={focus} scrollToPage={viewTo}
        onGo={(p) => goTo(p, false)} onRemove={(p) => store.unmark([p])} onLevel={(p, l) => store.setLevel(p, l)} onTitle={(p, t) => store.label(p, "title", t)}
        onAccept={(i) => store.accept([i])} onReject={(i) => store.reject([i])} onWhy={(s) => setMenu(s.page)} />
      {showSug && <>
        <h3>Suggestions ({openSug.length} open)</h3>
        {sugItems.length === 0 ? <p className="muted">{session.suggestions.length === 0 ? "No suggestions yet. Use Suggest splits in the Mark menu." : "No open suggestions."}</p> : (
          <SegmentList items={sugItems} loader={loader} tall compact readOnly={readOnly} confidential={confidential} label="Suggested starts" height={Math.round(railH * 0.8)} currentPage={focus}
            onGo={(p) => goTo(p, false)} onRemove={() => undefined} onLevel={() => undefined} onTitle={() => undefined}
            onAccept={(i) => store.accept([i])} onReject={(i) => store.reject([i])} onWhy={(s) => setMenu(s.page)} />
        )}
      </>}
      <div className="row wrap split-rail-foot">
        <button type="button" className="primary" disabled={reviewOff} onClick={() => setReviewing(true)}>Review and split</button>
        {reviewOff && <span className="muted">{guardMsg}</span>}
      </div>
    </div>
  );

  const head = (
    <header className="split-head">
      <h1>Split document</h1>
      <span className="muted split-sub">{label}</span>
      <p className="split-counts" aria-label="Draft summary">
        <strong>{pages} pages</strong> · <span role="status" aria-live="polite" data-save={snap.save}>{saveWords}</span> · {topCount} {topCount === 1 ? "segment" : "segments"} · suggestions: {openSug.length} open
        {prefs.showFlags && flags && flaggedTop > 0 && <> · <span data-flagged={flaggedTop}>flags: {flaggedTop} {flaggedTop === 1 ? "segment" : "segments"} flagged</span></>}
        {Object.keys(turns).length > 0 && <> · <span>{Object.keys(turns).length} {Object.keys(turns).length === 1 ? "page" : "pages"} to turn</span></>}
        {confidential && <> · <Badge tone="warn" glyph="file-lock">Confidential</Badge></>}
        {session.status !== "draft" && <> · <Badge tone="neutral">{session.status}</Badge></>}
      </p>
      <a className="split-head-link" href="#/setup/split">All drafts</a>
    </header>
  );

  const dockSide: "left" | "right" | null = docked === "rail" ? prefs.railSide : docked === "inspect" ? "right" : null;
  const railSide = phone ? "bottom" : prefs.railSide;
  const sideFor = (s: "left" | "right") => (phone ? "bottom" : s);

  return (
    <div className="split-view split-shell" data-focus={prefs.focus || undefined} data-phone={phone || undefined} onKeyDown={onKeyDown}>
      {head}
      <div className="split-live" role="status" aria-live="polite">{message}</div>
      <Loupe enabled={magOn} touchMode={magTouch} zoom={prefs.magnifierZoom} onZoom={setMagZoom} load={sharp} release={releaseSharp} budget={magBudget}
        maxPx={pictureStatus?.client ? LOUPE_MAX_PX : SERVER_MAX_PX} announce={setMessage}
        mode={prefs.magMode} corner={prefs.magCorner} size={prefs.magPx} view={prefs.magView} hop={prefs.magHop} phone={phone}
        onView={(v) => setPrefs({ magView: v })} onSize={(px) => setPrefs({ magPx: clampViewerPx(px) })} />
      {backend.demo && <p className="notice" role="note"><Badge tone="warn" glyph="info">Demo</Badge> Made-up pages, kept in this tab only; reload to start over. <a href="#/setup/split">Back to the splitter</a></p>}
      {snap.save === "offline" && <p className="notice notice-warn" role="alert">You are offline. Your marks are kept on this device and will be saved when you are back. <button type="button" onClick={() => store.retry()}>Retry now</button></p>}
      {snap.save === "error" && <p className="notice notice-error" role="alert"><span>Not saved. {snap.message} Your marks are kept on this device.</span><button type="button" onClick={() => store.retry()}>Retry</button></p>}
      {snap.conflict && <Conflict snap={snap} store={store} />}
      {snap.restorable > 0 && <p className="notice" role="note">Unsaved marks from earlier were kept on this device ({snap.restorable} starts). <button type="button" onClick={() => store.restore()}>Restore them</button></p>}
      {readOnly && <p className="notice notice-warn" role="note">This split is {session.status}. It can be looked at but not changed.</p>}
      {pictureStatus && <p className="muted split-line split-pictures" role="status" data-pictures={pictureStatus.client ? "browser" : pictureStatus.why === "waiting" ? "waiting" : "server"} data-why={pictureStatus.why}>{pictureStatus.words}</p>}
      {background?.phase === "uploading" && <p className="notice" role="status" data-background="uploading">The file is being saved on the server in the background. Your marks are kept here and are sent, in order, as soon as it is saved.</p>}
      {background?.phase === "refused" && <p className="notice notice-error" role="alert" data-background="refused"><span>The server did not keep this file: {background.words} Your marks cannot be saved. Nothing was sent anywhere else.</span><a href="#/setup/split">Back to the splitter</a></p>}
      {background?.phase === "saved" && background.words && <p className="muted split-line" role="status">{background.words}</p>}
      {(prog.pending > 0 || facts.failed) && <p className="muted split-line" role="status">{facts.failed ? `Page facts could not be read: ${facts.failed}` : notYet ? `The server has not measured the pages yet: blank pages, sideways pages, repeats, page numbers and suggested starts appear as it measures them (${prog.known - prog.pending} of ${pages} pages ready).` : `Page facts are still being measured (${prog.known - prog.pending} of ${pages} pages ready). Each page shows what it is as it is measured.`}</p>}
      {session.notes.length > 0 && <ul className="muted split-notes">{session.notes.map((n) => <li key={n}>{n}</li>)}</ul>}

      {walk && <WalkBar pages={walk.pages} at={walk.at} why={walk.why} isStart={snap.starts.has(walk.pages[walk.at])} readOnly={readOnly}
        onStep={stepWalk} onMark={(p) => store.mark([p])} onDone={() => setWalk(null)} />}

      <Toolbar label="Splitter controls" className="split-toolbar">
        {phone ? (<>
          <MenuButton spec={menus.phone} />
          <ToolButton onClick={() => store.undo()} disabled={undoOff}>Undo</ToolButton>
          <ToolButton onClick={() => store.redo()} disabled={redoOff}>Redo</ToolButton>
          <ToolButton aria-pressed={prefs.focus} onClick={toggleFocus} title="Focus (F)">Focus</ToolButton>
        </>) : (<>
          <MenuButton spec={menus.draft} />
          <MenuButton spec={menus.view} />
          <MenuButton spec={menus.mark} />
          <MenuButton spec={menus.pages} />
          <MenuButton spec={menus.help} />
          {view === "album" && <label className="split-size">Size <input type="range" min={64} max={220} step={4} value={albumW} onChange={(e) => setAlbumW(Number(e.target.value))} aria-label="Thumbnail size" /></label>}
          <span className="split-tb-gap" aria-hidden="true" />
          <ToolButton onClick={() => store.undo()} disabled={undoOff} title="Undo (Z)">Undo</ToolButton>
          <ToolButton onClick={() => store.redo()} disabled={redoOff} title="Redo (Y)">Redo</ToolButton>
          <ToolButton aria-pressed={railOpen} aria-controls="split-drawer-rail" onClick={() => setRail(!railOpen)} title="Segments drawer (S)">Segments <span className="split-count">{topCount}</span></ToolButton>
          <ToolButton aria-pressed={inspect} aria-controls="split-drawer-inspect" onClick={() => openInspect(!inspect)} title="Compare drawer (C)">Compare</ToolButton>
          <ToolButton aria-pressed={magOn} onClick={() => toggleMagnifier()} title={prefs.magMode === "fixed" ? "Magnifier: a viewer in a screen corner (E)" : "Magnifier: a lens over the page under the pointer (E)"}>Magnifier</ToolButton>
          <ToolButton aria-pressed={prefs.focus} onClick={toggleFocus} title="Focus: the pages fill the screen (F)">Focus</ToolButton>
          <ToolButton className="primary" disabled={reviewOff} onClick={() => setReviewing(true)}>Review and split</ToolButton>
        </>)}
      </Toolbar>
      <SegmentStrip rows={topRows} page={focus} flagged={prefs.showFlags ? flaggedKeys : new Set()} onGo={(p) => { goTo(p, false); setViewTo(p); }} onMore={() => setRail(true)} />
      {selSize > 1 && <p className="split-selbar" role="status">{selSize} pages selected ({lo} to {hi}). <button type="button" onClick={() => setSelection(null)}>Clear the selection</button> <span className="muted">Open the page menu (L) for what to do with them.</span></p>}

      <div className="split-stage" data-dock={dockSide ?? undefined} style={dockSide ? ({ "--dock-w": docked === "inspect" ? "min(40rem, 45%)" : "min(24rem, 32%)" } as React.CSSProperties) : undefined}>
        <div className="split-work">
          <div ref={wrapRef} className="split-gridwrap" data-view={view} data-axis={view === "scroll" ? scrollAxis : "y"} onDoubleClick={onDoubleClick}>
            {view === "album" && <PageGrid ref={gridRef} {...common} axis="y" variant="album" bands={bands} cellW={cellW} label="Pages" onActivate={onActivate} />}
            {view === "scroll" && <PageGrid ref={gridRef} {...common} axis={scrollAxis} variant="scroll" cellW="fit" maxW={scrollMaxW} label="Pages, one at a time" onActivate={onActivate} />}
            {view === "filmstrip" && (
              <div className="split-film">
                <div className="row wrap split-film-head">
                  <strong>Page {focus} of {pages}</strong>
                  <button type="button" disabled={readOnly || focus === 1} aria-pressed={snap.starts.has(focus)} onClick={() => store.toggle(focus)}>{snap.starts.has(focus) ? "This page starts a segment: remove" : "This page starts a segment"}</button>
                </div>
                <Figure page={focus} loader={loader} caption="This page" zoom="fit" sizes={["small", "large"]} facts={facts} confidential={confidential} />
                <PageGrid ref={stripRef} {...common} axis="x" variant="strip" cellW={64} label="Pages, as a strip" onActivate={onActivate} />
              </div>
            )}
            {view === "list" && (
              <SegmentList items={items} loader={loader} tall={phone} flagLine={prefs.showFlags} onFlags={onFlags} readOnly={readOnly} confidential={confidential} label="Segments and suggested starts" height={Math.max(360, room.h || 560)} currentPage={focus} scrollToPage={viewTo}
                onGo={(p) => { setFocus(p); setViewTo(p); }} onRemove={(p) => store.unmark([p])} onLevel={(p, l) => store.setLevel(p, l)} onTitle={(p, t) => store.label(p, "title", t)}
                onAccept={(i) => store.accept([i])} onReject={(i) => store.reject([i])} onWhy={(s) => setMenu(s.page)} />
            )}
          </div>
        </div>

        <Drawer id="rail" label="Segments" open={railOpen} side={railSide} docked={dockedRail} onClose={() => setRail(false)} width="min(26rem, 100%)"
          canPin={canPin} onPin={(pin) => setPrefs({ pinned: pin ? "rail" : "none" })} fallbackFocus={() => active()?.focusPage(focusRef.current)}>
          {railBody}
        </Drawer>
        <Drawer id="inspect" label="Compare pages" open={inspect} side={sideFor("right")} docked={docked === "inspect"} onClose={() => setInspect(false)} width="min(44rem, 100%)"
          canPin={canPin} onPin={(pin) => setPrefs({ pinned: pin ? "inspect" : "none" })} full={prefs.inspectFull} onFull={(f) => setPrefs({ inspectFull: f })} fallbackFocus={() => active()?.focusPage(focusRef.current)}>
          <ComparePane page={focus} pages={pages} prev={prevPage} prevSegFirst={prevSegFirst} segFirst={startOf(focus)} loader={loader} zoom={zoom} onZoom={setZoom} onGo={(p) => goTo(p, false)}
            facts={facts} confidential={confidential} starts={snap.starts.has(focus)} />
        </Drawer>
        <Drawer id="review" label="Review and split" open={reviewing} side={sideFor("right")} onClose={() => setReviewing(false)} width="min(64rem, 100%)" locked={reviewBusy} fallbackFocus={() => active()?.focusPage(focusRef.current)}>
          <SplitReview backend={backend} id={id} by={by} loader={loader} facts={facts} status={session.status} drop={drop} setDrop={setDrop} confidential={confidential}
            turns={turns} setTurns={setTurns} onReviewPages={startWalk} onBusy={setReviewBusy}
            onBack={() => setReviewing(false)} onDone={() => { void store.reload(); }} onRename={async (p, t) => { store.label(p, "title", t); await store.idle(); }} />
        </Drawer>

        {!phone && !railOpen && <EdgeTab side={prefs.railSide} drawerId="rail" label="Segments" count={topCount} onOpen={() => setRail(true)} slot={0} />}
        {!phone && !inspect && <EdgeTab side="right" drawerId="inspect" label="Compare" onOpen={() => openInspect(true)} slot={1} />}

        {tool && (
          <ToolPanel title={TOOL_TITLE[tool]} onClose={() => setTool(null)}>
            {tool === "nth" && (<>
              <label className="row">Every <input type="number" min={1} max={500} value={nth} onChange={(e) => setNth(Math.max(1, Number(e.target.value) || 1))} aria-label="Every how many pages" /> pages, {selection ? `in the selection (pages ${lo} to ${hi})` : "across the file"}</label>
              <button type="button" disabled={readOnly || nthPages.length === 0} onClick={() => { store.range(selection ? lo : 1, selection ? hi : pages, nth); setTool(null); }}>Add {nthPages.length} {nthPages.length === 1 ? "start" : "starts"}</button>
            </>)}
            {tool === "blanks" && (<>
              <label className="row">The blank pages <select value={blankKeep} onChange={(e) => { setBlankKeep(e.target.value as BlankKeep); setBlankPlan(null); }}>
                <option value="before">stay with the segment before</option><option value="after">stay with the segment after</option><option value="drop">are left out of the files</option></select></label>
              <button type="button" disabled={loadingFacts} onClick={() => planBlanks(blankKeep)}>{loadingFacts ? "Reading the pages…" : "Find blank pages"}</button>
              {blankPlan && (
                <div role="status">
                  <p>{blankPlan.blanks} blank pages ({Math.round(blankPlan.share * 100)}%). This adds {blankPlan.marks.filter((m) => !snap.starts.has(m)).length} starts{blankPlan.drop.length ? ` and leaves out ${blankPlan.drop.length} pages` : ""}.</p>
                  {blankPlan.duplexLooking && <label className="row"><input type="checkbox" checked={duplexOk} onChange={(e) => setDuplexOk(e.target.checked)} /> These blanks look like the backs of pages. Split on them anyway.</label>}
                  <button type="button" disabled={readOnly || (blankPlan.duplexLooking && !duplexOk) || blankPlan.marks.length === 0}
                    onClick={() => { store.mark(blankPlan.marks.filter((m) => !snap.starts.has(m))); if (blankPlan.drop.length) setDrop([...new Set([...drop, ...blankPlan.drop])].sort((a, b) => a - b)); setBlankPlan(null); setTool(null); }}>Split on blank pages</button>
                </div>
              )}
            </>)}
            {tool === "restarts" && (<>
              <button type="button" disabled={loadingFacts} onClick={findRestarts}>Find where numbering restarts at 1</button>
              {restarts && <div role="status"><p>{restarts.length} pages restart at 1 and are not starts yet.</p><button type="button" disabled={readOnly || restarts.length === 0} onClick={() => { store.mark(restarts); setRestarts(null); setTool(null); }}>Mark {restarts.length} starts</button></div>}
            </>)}
            {tool === "sideways" && (<>
              <button type="button" disabled={loadingFacts} onClick={async () => { await readAll(); setSidewaysSeen(sidewaysIn(facts.all()).length); }}>Find sideways pages</button>
              {sidewaysSeen !== null && (
                <div role="status">
                  <p>{sidewaysSeen === 0 ? "No page is measured sideways. A scan with no text layer is never measured." : `${sidewaysSeen} ${sidewaysSeen === 1 ? "page is" : "pages are"} sideways. Turning is done in the new files only; the original is not changed.`}</p>
                  <button type="button" disabled={readOnly || sidewaysSeen === 0} onClick={() => setTurns({ ...turns, ...Object.fromEntries(sidewaysIn(facts.all()).map((x) => [x.page, "fix" as Turn])) })}>Fix all {sidewaysSeen} sideways {sidewaysSeen === 1 ? "page" : "pages"}</button>
                </div>
              )}
            </>)}
            {tool === "clear" && <Confirm label="Clear" summary={<p>Remove all {snap.starts.size - 1} of your starts? Page 1 stays. You can undo this.</p>} onConfirm={() => { store.clear(); setTool(null); }} busy={readOnly}>Clear all my marks</Confirm>}
          </ToolPanel>
        )}
      </div>

      <div className="split-bar">
        <span className="split-where">Page {focus} of {pages}{snap.docNo[focus] ? `, segment ${snap.docNo[focus]}` : ""}</span>
        <div className="split-slider">
          <input type="range" min={1} max={pages} value={focus} aria-label="Page" aria-valuetext={`Page ${focus} of ${pages}, segment ${snap.docNo[focus] ?? 1}`}
            onChange={(e) => goTo(Number(e.target.value), false)} />
          <TicksM pages={pages} starts={snap.starts} suggestions={showSug ? session.suggestions : []} facts={facts} version={factsVersion} />
        </div>
        <form onSubmit={jump} className="row"><label>Go to <input ref={goRef} type="number" min={1} max={pages} defaultValue={focus} key={focus} aria-label="Go to page" /></label><button type="submit">Go</button></form>
      </div>

      {phone && (
        <Toolbar label="Actions" className="split-actionbar">
          <MenuButton spec={menus.mark} up />
          <MenuButton spec={menus.pages} up />
          <ToolButton aria-pressed={railOpen} aria-controls="split-drawer-rail" onClick={() => setRail(!railOpen)}>Segments <span className="split-count">{topCount}</span></ToolButton>
          <ToolButton aria-pressed={inspect} aria-controls="split-drawer-inspect" onClick={() => openInspect(!inspect)}>Compare</ToolButton>
          <ToolButton aria-pressed={magOn} onClick={() => toggleMagnifier()} title="Magnifier: press and hold a page, then drag">Magnifier</ToolButton>
          <ToolButton className="primary" disabled={reviewOff} onClick={() => setReviewing(true)}>Review and split</ToolButton>
        </Toolbar>
      )}

      {menu !== null && (
        <PageMenu page={menu} a={{
          isStart: snap.starts.has(menu), first: menu === 1, readOnly, sug: menuSug, selectionSize: selSize, canNest: menu > 1, nested: (snap.starts.get(menu) ?? 0) > 0,
          mark: () => store.mark([menu]), unmark: () => store.unmark([menu]), nest: () => (snap.starts.has(menu) ? store.setLevel(menu, 1) : store.mark([menu], 1)),
          level: (l) => store.setLevel(menu, l), larger: () => { setFocus(menu); openInspect(true); }, accept: () => menuSug && store.accept([menuSug.id]), reject: () => menuSug && store.reject([menuSug.id]),
          retry: () => loader.retry(menu), everyNth: (n) => store.range(lo, hi, n), markEach: () => store.mark(Array.from({ length: hi - lo + 1 }, (_, i) => lo + i)),
          fact: facts.get(menu), turn: turns[menu], setTurn: (t) => setTurnOf(menu, t),
          mergeSelection: () => store.unmark(Array.from({ length: hi - lo }, (_, i) => lo + 1 + i)), close: () => { const m = menu; setMenu(null); requestAnimationFrame(() => active()?.focusPage(m)); },
        }} />
      )}
      {help && <KeyHelp onClose={() => setHelp(false)} />}
      {flagView && (
        <FlagsDialog flags={flagView.flags} no={flagView.no} caveats={flags?.caveats ?? []} a={{
          readOnly, go: (p) => { setFocus(p); setViewTo(p); active()?.scrollToPage(p, true); }, walk: startWalk,
          fixSideways: (pages) => setTurns({ ...turns, ...Object.fromEntries(pages.map((p) => [p, "fix" as Turn])) }),
          segStart: startOfKey, close: () => setFlagView(null),
        }} />
      )}
    </div>
  );
}

function Conflict({ snap, store }: { snap: Snapshot; store: SplitStore }) {
  const c = snap.conflict!;
  const theirs = startsOf(c.current.boundaries);
  const mine = snap.starts;
  const onlyMine = [...mine.keys()].filter((p) => !theirs.has(p));
  const onlyTheirs = [...theirs.keys()].filter((p) => !mine.has(p));
  return (
    <section className="notice notice-warn split-conflict" role="alert" aria-label="The draft changed elsewhere">
      <h2>The draft changed elsewhere</h2>
      <p>{c.message}</p>
      <div className="split-conflict-cols">
        <div><h3>Your copy</h3><p>{mine.size} starts.{onlyMine.length ? ` Only in yours: pages ${onlyMine.slice(0, 20).join(", ")}${onlyMine.length > 20 ? ", …" : ""}.` : " Nothing only in yours."}</p></div>
        <div><h3>The other copy</h3><p>{theirs.size} starts, saved {c.current.updated.slice(0, 16).replace("T", " ")}{c.current.by ? ` by ${c.current.by}` : ""}.{onlyTheirs.length ? ` Only in theirs: pages ${onlyTheirs.slice(0, 20).join(", ")}${onlyTheirs.length > 20 ? ", …" : ""}.` : " Nothing only in theirs."}</p></div>
      </div>
      <div className="row wrap">
        <button type="button" onClick={() => store.keepMine(false)}>Keep mine</button>
        <button type="button" onClick={() => store.keepTheirs()}>Keep theirs</button>
        <button type="button" className="primary" onClick={() => store.keepMine(true)}>Merge boundaries (all starts from both)</button>
      </div>
    </section>
  );
}
