import { memo, useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { Badge, Confirm, ScreenHeader } from "../components";
import { useMediaQuery } from "../lib/useMediaQuery";
import { useSession } from "../lib/session";
import { PageGrid, type GridApi } from "./PageGrid";
import { ComparePane, KeyHelp, PageMenu, ZOOMS, Figure, type Zoom } from "./SplitPanes";
import { SegmentList, itemsOf } from "./SplitRail";
import { SplitReview } from "./SplitReview";
import type { SplitBackend } from "./splitApi";
import { FactsCache } from "./splitFacts";
import {
  acceptable, everyNth, marksIn, nextMark, sizeText, splitAtRestarts, splitOnBlanks, startsOf, type BlankKeep, type SegmentRow, type SessionAnswer, type Suggestion,
} from "./splitModel";
import { SplitStore, type Snapshot } from "./splitStore";
import { ThumbLoader } from "./splitThumbs";
import { budgetFor } from "./splitWindow";
import "./split.css";

type View = "album" | "filmstrip" | "scroll" | "list";
const VIEWS: { id: View; words: string }[] = [
  { id: "album", words: "Album" }, { id: "filmstrip", words: "Filmstrip" }, { id: "scroll", words: "Scroll" }, { id: "list", words: "List" },
];
const PHONE = "(max-width: 719px)";
const WIDE = "(min-width: 1200px)";

const deviceMemory = (): number | undefined => (typeof navigator !== "undefined" ? (navigator as unknown as { deviceMemory?: number }).deviceMemory : undefined);

interface Boot { store: SplitStore; facts: FactsCache; loader: ThumbLoader; first: SessionAnswer }

/** The splitter's working screen for one draft (`#/setup/split/<id>`). It loads the draft, then hands a store (the draft and its queue of
 * saves), a facts cache, and a picture loader to the screen. Nothing per page is React state. */
export function SplitEditor({ backend, id }: { backend: SplitBackend; id: string }) {
  const { me } = useSession([]);
  const [boot, setBoot] = useState<Boot | { error: string } | null>(null);
  useEffect(() => {
    let live = true;
    const store = new SplitStore(backend, id, me);
    const loader = new ThumbLoader({ urlOf: (page, size) => backend.thumbUrl(id, page, size), budget: budgetFor({ width: typeof window === "undefined" ? 1024 : window.innerWidth, deviceMemory: deviceMemory() }) });
    let facts: FactsCache | null = null;
    store.load().then(() => {
      const s = store.getSnapshot().session!;
      facts = new FactsCache(backend, id, s.source.pages);
      if (live) setBoot({ store, facts, loader, first: s as SessionAnswer });
    }, (e: Error) => { if (live) setBoot({ error: e.message }); });
    return () => { live = false; loader.clear(); facts?.dispose(); };
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

function EditorBody({ backend, id, by, store, facts, loader, first }: { backend: SplitBackend; id: string; by: string } & Boot) {
  const snap: Snapshot = useSyncExternalStore(store.subscribe, store.getSnapshot, store.getSnapshot);
  const factsVersion = useSyncExternalStore(facts.subscribe, facts.getVersion, facts.getVersion);
  const session = snap.session!;
  const pages = session.source.pages;
  const confidential = !!first.confidential || session.source.confidential;
  const phone = useMediaQuery(PHONE);
  const wideQuery = useMediaQuery(WIDE);
  const wide = typeof window !== "undefined" && typeof window.matchMedia !== "function" ? true : wideQuery;
  const lowMemory = (deviceMemory() ?? 8) <= 2;

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
  const [compare, setCompare] = useState(false);
  const [zoom, setZoom] = useState<Zoom>("fit");
  const [sheet, setSheet] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  const [drop, setDrop] = useState<number[]>(() => { try { return JSON.parse(sessionStorage.getItem(`jason-split-drop-${id}`) ?? "[]"); } catch { return []; } });
  const [showRejected, setShowRejected] = useState(false);
  const [viewTo, setViewTo] = useState<number | undefined>(undefined);
  const gridRef = useRef<GridApi>(null);
  const stripRef = useRef<GridApi>(null);
  const goRef = useRef<HTMLInputElement>(null);
  const chose = useRef(false);
  const setView = (v: View) => { chose.current = true; setViewState(v); setViewTo(focus); };
  // until a person picks a view, the default follows the screen (the list on a phone, the album elsewhere)
  useEffect(() => { if (!chose.current) setViewState(phone || lowMemory ? "list" : "album"); }, [phone, lowMemory]);
  useEffect(() => { try { sessionStorage.setItem(`jason-split-drop-${id}`, JSON.stringify(drop)); } catch { /* storage blocked */ } }, [id, drop]);

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

  const segRows: SegmentRow[] = useMemo(() => {
    const server = new Map(session.segments.map((s) => [s.start, s]));
    return snap.segs.map((s) => ({ key: s.key, path: s.key, start: s.start, end: s.end, pages: s.end - s.start + 1, level: s.level, parent: "", source: s.start === 1 ? "first" : server.get(s.start)?.source ?? "person", labels: server.get(s.start)?.labels ?? {} }));
  }, [snap.segs, session.segments]);
  const topCount = snap.segs.filter((s) => s.level === 0).length;
  const openSug = session.suggestions.filter((s) => s.state === "open");
  const high = useMemo(() => acceptable(session.suggestions, 0.85), [session.suggestions]);
  const medium = useMemo(() => acceptable(session.suggestions, 0.6), [session.suggestions]);
  const items = useMemo(() => itemsOf(segRows, session.suggestions, showRejected), [segRows, session.suggestions, showRejected]);
  const segItems = useMemo(() => items.filter((i) => i.kind === "seg"), [items]);
  const sugItems = useMemo(() => items.filter((i) => i.kind === "sug"), [items]);
  const marks = useMemo(() => marksIn(snap.starts, session.suggestions), [snap.starts, session.suggestions]);
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

  const onKeyDown = (e: React.KeyboardEvent) => {
    const t = e.target as HTMLElement;
    if (t.closest("input, textarea, select, [role=dialog]")) return;
    if (reviewing) return;
    const focus = focusRef.current;
    const k = e.key;
    if (e.ctrlKey || e.metaKey) {
      if (k.toLowerCase() === "z") { e.preventDefault(); if (e.shiftKey) store.redo(); else store.undo(); }
      else if (k.toLowerCase() === "y") { e.preventDefault(); store.redo(); }
      return;
    }
    if (e.altKey) return;
    const cols = gridRef.current?.cols() ?? 1;
    const lower = k.length === 1 ? k.toLowerCase() : k;
    const horizontal = view === "filmstrip" || (view === "scroll" && scrollAxis === "x");
    const stepsOf: Record<string, number> = view === "scroll" && scrollAxis === "y"
      ? { ArrowUp: -1, ArrowDown: 1, ArrowLeft: -1, ArrowRight: 1 }
      : horizontal ? { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -1, ArrowDown: 1 }
      : { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -cols, ArrowDown: cols };
    if (k in stepsOf && view !== "list") { e.preventDefault(); step(stepsOf[k], e.shiftKey); return; }
    switch (lower) {
      case "Home": e.preventDefault(); goTo(1); return;
      case "End": e.preventDefault(); goTo(pages); return;
      case "PageUp": e.preventDefault(); goTo(focus - cols * 3); return;
      case "PageDown": e.preventDefault(); goTo(focus + cols * 3); return;
      case "Enter": case " ":
        if (view === "filmstrip") { e.preventDefault(); store.toggle(focus); setAnchor(focus); }
        return;
      case "n": case "p": { const m = nextMark(marks, focus, lower === "n" ? 1 : -1); if (m !== null) { e.preventDefault(); goTo(m); } return; }
      case "a": { const s = snap.sugByPage.get(focus); if (s) { e.preventDefault(); store.accept([s.id]); } return; }
      case "x": { const s = snap.sugByPage.get(focus); if (s) { e.preventDefault(); store.reject([s.id]); } return; }
      case "m": { e.preventDefault(); const at = startOf(focus); if (at === 1) setMessage("The first page always starts a segment."); else store.unmark([at]); return; }
      case "[": case "]": { if (snap.starts.has(focus) && focus > 1) { e.preventDefault(); const to = focus + (lower === "]" ? 1 : -1); if (to > 1 && to <= pages) { store.move(focus, to); goTo(to); } } return; }
      case "l": e.preventDefault(); setMenu(focus); return;
      case "g": case "/": e.preventDefault(); goRef.current?.focus(); goRef.current?.select(); return;
      case "v": e.preventDefault(); setView(VIEWS[(VIEWS.findIndex((v) => v.id === view) + 1) % VIEWS.length].id); return;
      case "1": case "2": case "3": case "4": e.preventDefault(); setView(VIEWS[Number(lower) - 1].id); return;
      case "+": case "=": e.preventDefault(); if (compare) setZoom(ZOOMS[Math.min(2, ZOOMS.findIndex((z) => z.id === zoom) + 1)].id); else setAlbumW((w) => Math.min(220, w + 16)); return;
      case "-": e.preventDefault(); if (compare) setZoom(ZOOMS[Math.max(0, ZOOMS.findIndex((z) => z.id === zoom) - 1)].id); else setAlbumW((w) => Math.max(64, w - 16)); return;
      case "z": e.preventDefault(); if (e.shiftKey) store.redo(); else store.undo(); return;
      case "y": e.preventDefault(); store.redo(); return;
      case "?": e.preventDefault(); setHelp(true); return;
      case "Escape": if (menu === null && !help) { if (selection) setSelection(null); else if (compare) setCompare(false); } return;
      default:
    }
  };

  // ---- the page menu
  const menuSug = menu !== null ? snap.sugByPage.get(menu) : undefined;
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
  const label = confidential ? "A confidential file" : session.source.kind === "demo" ? `${pages} made-up pages` : `${pages} pages, ${sizeText(session.source.size)}, ${session.source.sha256.slice(0, 8)}`;
  const guardMsg = readOnly ? `This split is ${session.status}.` : "Wait for the draft to finish saving.";

  const jump = (e: React.FormEvent) => {
    e.preventDefault();
    const v = Number(goRef.current?.value);
    if (Number.isInteger(v) && v >= 1 && v <= pages) goTo(v);
    else setMessage(`This file has ${pages} pages.`);
  };

  const common = { count: pages, snap, facts, loader, focus, selection, confidential, onMenu, onMove, onFocusPage };
  const prevPage = focus > 1 ? focus - 1 : null;
  const prevSegFirst = (() => { const at = startOf(focus); if (at <= 1) return null; return startOf(at - 1); })();
  const rail = (
    <div className="split-rail-body">
      <h2>Segments ({topCount}{snap.segs.length > topCount ? `, ${snap.segs.length - topCount} nested` : ""})</h2>
      <SegmentList items={segItems} loader={loader} tall={phone} compact readOnly={readOnly} confidential={confidential} label="Segments" height={300} currentPage={focus} scrollToPage={viewTo}
        onGo={(p) => goTo(p, false)} onRemove={(p) => store.unmark([p])} onLevel={(p, l) => store.setLevel(p, l)} onTitle={(p, t) => store.label(p, "title", t)}
        onAccept={(i) => store.accept([i])} onReject={(i) => store.reject([i])} onWhy={(s) => setMenu(s.page)} />
      <h2>Suggestions ({openSug.length} open)</h2>
      {sugItems.length === 0 ? <p className="muted">{session.suggestions.length === 0 ? "No suggestions yet. Use Suggest to look for starts." : "No open suggestions."}</p> : (
        <SegmentList items={sugItems} loader={loader} tall={phone} compact readOnly={readOnly} confidential={confidential} label="Suggested starts" height={260} currentPage={focus}
          onGo={(p) => goTo(p, false)} onRemove={() => undefined} onLevel={() => undefined} onTitle={() => undefined}
          onAccept={(i) => store.accept([i])} onReject={(i) => store.reject([i])} onWhy={(s) => setMenu(s.page)} />
      )}
      <div className="row wrap split-rail-foot">
        <button type="button" className="primary" disabled={readOnly || snap.pending > 0 || snap.save !== "saved"} onClick={() => { setReviewing(true); setSheet(false); }}>Review and split</button>
        {(readOnly || snap.pending > 0 || snap.save !== "saved") && <span className="muted">{guardMsg}</span>}
      </div>
    </div>
  );

  if (reviewing) {
    return (
      <div className="stack split-view">
        <ScreenHeader title="Split document" summary={label} />
        <SplitReview backend={backend} id={id} by={by} loader={loader} facts={facts} status={session.status} drop={drop} setDrop={setDrop} confidential={confidential}
          onBack={() => setReviewing(false)} onDone={() => { void store.reload(); }} onRename={async (p, t) => { store.label(p, "title", t); await store.idle(); }} />
      </div>
    );
  }

  return (
    <div className="stack split-view" onKeyDown={onKeyDown}>
      <ScreenHeader title="Split document" summary={`${label}. Tap the first page of each document; jason suggests, you decide. Nothing is written until you confirm.`}
        actions={<><a href="#/setup/split">All drafts</a><button type="button" onClick={() => setHelp(true)}>Keyboard map</button></>} />
      {backend.demo && <p className="notice" role="note"><Badge tone="warn" glyph="info">Demo</Badge> Made-up pages, kept in this tab only; reload to start over. <a href="#/setup/split">Back to the splitter</a></p>}
      <p className="split-counts" aria-label="Draft summary">
        <strong>{pages} pages</strong> · <span role="status" aria-live="polite" data-save={snap.save}>{saveWords}</span> · {topCount} {topCount === 1 ? "segment" : "segments"} · suggestions: {openSug.length} open
        {confidential && <> · <Badge tone="warn" glyph="file-lock">Confidential</Badge></>}
        {session.status !== "draft" && <> · <Badge tone="neutral">{session.status}</Badge></>}
      </p>
      <div className="split-live" role="status" aria-live="polite">{message}</div>
      {snap.save === "offline" && <p className="notice notice-warn" role="alert">You are offline. Your marks are kept on this device and will be saved when you are back. <button type="button" onClick={() => store.retry()}>Retry now</button></p>}
      {snap.save === "error" && <p className="notice notice-error" role="alert"><span>Not saved. {snap.message} Your marks are kept on this device.</span><button type="button" onClick={() => store.retry()}>Retry</button></p>}
      {snap.conflict && <Conflict snap={snap} store={store} />}
      {snap.restorable > 0 && <p className="notice" role="note">Unsaved marks from earlier were kept on this device ({snap.restorable} starts). <button type="button" onClick={() => store.restore()}>Restore them</button></p>}
      {readOnly && <p className="notice notice-warn" role="note">This split is {session.status}. It can be looked at but not changed.</p>}
      {(prog.pending > 0 || facts.failed) && <p className="muted" role="status">{facts.failed ? `Page facts could not be read: ${facts.failed}` : `Page facts are still being measured (${prog.known - prog.pending} of ${pages} pages ready).`}</p>}
      {session.notes.length > 0 && <ul className="muted split-notes">{session.notes.map((n) => <li key={n}>{n}</li>)}</ul>}

      <div className="split-toolbar" role="toolbar" aria-label="Splitter controls">
        {phone ? (
          <label className="row">View <select value={view} onChange={(e) => setView(e.target.value as View)}>{VIEWS.map((v) => <option key={v.id} value={v.id}>{v.words}</option>)}</select></label>
        ) : (
          <div role="group" aria-label="View" className="row">{VIEWS.map((v, i) => <button key={v.id} type="button" aria-pressed={view === v.id} onClick={() => setView(v.id)} title={`Key ${i + 1}`}>{v.words}</button>)}</div>
        )}
        {view === "scroll" && <button type="button" onClick={() => setScrollAxis(scrollAxis === "y" ? "x" : "y")}>{scrollAxis === "y" ? "Scroll across" : "Scroll down"}</button>}
        {view === "album" && <label className="row">Size <input type="range" min={64} max={220} step={4} value={albumW} onChange={(e) => setAlbumW(Number(e.target.value))} aria-label="Thumbnail size" /></label>}
        <button type="button" onClick={() => store.undo()} disabled={readOnly || session.counts.undo === 0 && snap.pending === 0}>Undo</button>
        <button type="button" onClick={() => store.redo()} disabled={readOnly || session.counts.redo === 0}>Redo</button>
        <button type="button" aria-pressed={compare} onClick={() => setCompare(!compare)}>Compare</button>
        <details className="split-pop"><summary>Suggest</summary>
          <div className="split-pop-body">
            <button type="button" disabled={readOnly || snap.busy} onClick={() => store.suggest()}>Suggest splits</button>
            <p className="muted">Suggestions come from the shapes and numbers of the pages (a rule pass). They are dashed starts until you accept them.</p>
            <button type="button" disabled={readOnly || high.length === 0} onClick={() => store.acceptBand("high")}>Accept {high.length} at High confidence</button>
            <button type="button" disabled={readOnly || medium.length === 0} onClick={() => store.acceptBand("medium")}>Accept {medium.length} at Medium or better</button>
            <label className="row"><input type="checkbox" checked={showRejected} onChange={(e) => setShowRejected(e.target.checked)} /> Show rejected suggestions</label>
          </div>
        </details>
        <details className="split-pop"><summary>More</summary>
          <div className="split-pop-body">
            <h3>Every Nth page</h3>
            <label className="row">Every <input type="number" min={1} max={500} value={nth} onChange={(e) => setNth(Math.max(1, Number(e.target.value) || 1))} aria-label="Every how many pages" /> pages, {selection ? `in the selection (pages ${lo} to ${hi})` : "across the file"}</label>
            <button type="button" disabled={readOnly || nthPages.length === 0} onClick={() => store.range(selection ? lo : 1, selection ? hi : pages, nth)}>Add {nthPages.length} {nthPages.length === 1 ? "start" : "starts"}</button>
            <h3>Blank pages</h3>
            <label className="row">The blank pages <select value={blankKeep} onChange={(e) => { setBlankKeep(e.target.value as BlankKeep); setBlankPlan(null); }}>
              <option value="before">stay with the segment before</option><option value="after">stay with the segment after</option><option value="drop">are left out of the files</option></select></label>
            <button type="button" disabled={loadingFacts} onClick={() => planBlanks(blankKeep)}>{loadingFacts ? "Reading the pages…" : "Find blank pages"}</button>
            {blankPlan && (
              <div role="status">
                <p>{blankPlan.blanks} blank pages ({Math.round(blankPlan.share * 100)}%). This adds {blankPlan.marks.filter((m) => !snap.starts.has(m)).length} starts{blankPlan.drop.length ? ` and leaves out ${blankPlan.drop.length} pages` : ""}.</p>
                {blankPlan.duplexLooking && <label className="row"><input type="checkbox" checked={duplexOk} onChange={(e) => setDuplexOk(e.target.checked)} /> These blanks look like the backs of pages. Split on them anyway.</label>}
                <button type="button" disabled={readOnly || (blankPlan.duplexLooking && !duplexOk) || blankPlan.marks.length === 0}
                  onClick={() => { store.mark(blankPlan.marks.filter((m) => !snap.starts.has(m))); if (blankPlan.drop.length) setDrop([...new Set([...drop, ...blankPlan.drop])].sort((a, b) => a - b)); setBlankPlan(null); }}>Split on blank pages</button>
              </div>
            )}
            <h3>Page-number restarts</h3>
            <button type="button" disabled={loadingFacts} onClick={findRestarts}>Find where numbering restarts at 1</button>
            {restarts && <div role="status"><p>{restarts.length} pages restart at 1 and are not starts yet.</p><button type="button" disabled={readOnly || restarts.length === 0} onClick={() => { store.mark(restarts); setRestarts(null); }}>Mark {restarts.length} starts</button></div>}
            <h3>Clear</h3>
            <Confirm label="Clear" summary={<p>Remove all {snap.starts.size - 1} of your starts? Page 1 stays. You can undo this.</p>} onConfirm={() => store.clear()} busy={readOnly}>Clear all my marks</Confirm>
          </div>
        </details>
        <button type="button" className="primary" disabled={readOnly || snap.pending > 0 || snap.save !== "saved"} onClick={() => setReviewing(true)}>Review and split</button>
      </div>
      {selSize > 1 && <p className="split-selbar" role="status">{selSize} pages selected ({lo} to {hi}). <button type="button" onClick={() => setSelection(null)}>Clear the selection</button> <span className="muted">Open the page menu (L) for what to do with them.</span></p>}

      <div className={`split-main${wide ? " has-rail" : ""}`}>
        <div className="split-work">
          {view === "album" && <PageGrid ref={gridRef} {...common} axis="y" variant="album" cellW={albumW} label="Pages" onActivate={onActivate} />}
          {view === "scroll" && <PageGrid ref={gridRef} {...common} axis={scrollAxis} variant="scroll" cellW="fit" maxW={scrollAxis === "y" ? 520 : 360} label="Pages, one at a time" onActivate={onActivate} />}
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
            <SegmentList items={items} loader={loader} tall={phone} readOnly={readOnly} confidential={confidential} label="Segments and suggested starts" height={560} currentPage={focus} scrollToPage={viewTo}
              onGo={(p) => { setFocus(p); setViewTo(p); }} onRemove={(p) => store.unmark([p])} onLevel={(p, l) => store.setLevel(p, l)} onTitle={(p, t) => store.label(p, "title", t)}
              onAccept={(i) => store.accept([i])} onReject={(i) => store.reject([i])} onWhy={(s) => setMenu(s.page)} />
          )}
          {compare && <ComparePane page={focus} prev={prevPage} prevSegFirst={prevSegFirst} loader={loader} zoom={zoom} onZoom={setZoom} onClose={() => setCompare(false)} facts={facts} confidential={confidential} starts={snap.starts.has(focus)} />}
        </div>
        {wide ? <aside className="split-rail" aria-label="Segments">{rail}</aside> : null}
      </div>

      {!wide && sheet && <section className="split-sheet" aria-label="Segments and suggestions">{rail}<button type="button" onClick={() => setSheet(false)}>Close</button></section>}

      <div className="split-bar">
        {!wide && <button type="button" className="split-sheet-bar" aria-expanded={sheet} onClick={() => setSheet(!sheet)}>{topCount} {topCount === 1 ? "segment" : "segments"}, {openSug.length} suggestions open</button>}
        <span>Page {focus} of {pages}{snap.docNo[focus] ? `, segment ${snap.docNo[focus]}` : ""}</span>
        <div className="split-slider">
          <input type="range" min={1} max={pages} value={focus} aria-label="Page" aria-valuetext={`Page ${focus} of ${pages}, segment ${snap.docNo[focus] ?? 1}`}
            onChange={(e) => goTo(Number(e.target.value), false)} />
          <TicksM pages={pages} starts={snap.starts} suggestions={session.suggestions} facts={facts} version={factsVersion} />
        </div>
        <form onSubmit={jump} className="row"><label>Go to <input ref={goRef} type="number" min={1} max={pages} defaultValue={focus} key={focus} aria-label="Go to page" /></label><button type="submit">Go</button></form>
      </div>

      {menu !== null && (
        <PageMenu page={menu} a={{
          isStart: snap.starts.has(menu), first: menu === 1, readOnly, sug: menuSug, selectionSize: selSize, canNest: menu > 1, nested: (snap.starts.get(menu) ?? 0) > 0,
          mark: () => store.mark([menu]), unmark: () => store.unmark([menu]), nest: () => (snap.starts.has(menu) ? store.setLevel(menu, 1) : store.mark([menu], 1)),
          level: (l) => store.setLevel(menu, l), larger: () => { setFocus(menu); setCompare(true); }, accept: () => menuSug && store.accept([menuSug.id]), reject: () => menuSug && store.reject([menuSug.id]),
          retry: () => loader.retry(menu), everyNth: (n) => store.range(lo, hi, n), markEach: () => store.mark(Array.from({ length: hi - lo + 1 }, (_, i) => lo + i)),
          mergeSelection: () => store.unmark(Array.from({ length: hi - lo }, (_, i) => lo + 1 + i)), close: () => { const m = menu; setMenu(null); requestAnimationFrame(() => active()?.focusPage(m)); },
        }} />
      )}
      {help && <KeyHelp onClose={() => setHelp(false)} />}
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
