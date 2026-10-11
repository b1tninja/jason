import { useEffect, useId, useLayoutEffect, useRef, useState, type ReactNode } from "react";

/** The splitter's toolbar and its menus (docs/pdf-splitter.md, section 5.9). A toolbar has one tab stop (arrow keys, Home and End move along
 * it); a menu button opens a menu with the arrow keys, Enter, or Space; inside, the arrows, Home, End, and the first letter move, Enter runs,
 * Esc closes and gives the focus back to the button, and Left and Right go to the next menu. A chosen item is a check mark and a word, never a
 * colour. An item states what it will do, with its count, in its own label. */

export type MenuEntry =
  | {
    type: "item"; label: string; onSelect(): void;
    /** the key that does the same, shown at the right and in the item's description */
    keys?: string;
    /** shown and focusable but does nothing; the label says why */
    disabled?: boolean;
    role?: "menuitem" | "menuitemradio" | "menuitemcheckbox"; checked?: boolean;
    /** the act moves the focus itself (it goes to a field): the menu does not give the focus back to its button */
    moves?: boolean;
    /** a link: followed instead of run */
    href?: string;
  }
  | { type: "sep" }
  | { type: "heading"; label: string };

export interface MenuSpec { id: string; label: string; entries: MenuEntry[]; align?: "start" | "end"; title?: string }

const ROVING = "[data-roving]:not(:disabled)";

/** A toolbar with one tab stop. Its controls carry `data-roving`; the arrow keys move between them. */
export function Toolbar({ label, className, children }: { label: string; className?: string; children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  const current = useRef<HTMLElement | null>(null);
  const items = () => Array.from(ref.current?.querySelectorAll<HTMLElement>(ROVING) ?? []);
  const sync = () => {
    const els = items();
    const at = current.current && els.includes(current.current) ? current.current : els[0];
    for (const e of els) e.tabIndex = e === at ? 0 : -1;
  };
  useLayoutEffect(sync);
  const onKeyDown = (e: React.KeyboardEvent) => {
    const t = e.target as HTMLElement;
    if (!t.matches?.("[data-roving]")) return;
    const els = items();
    const i = els.indexOf(t);
    let to = -1;
    if (e.key === "ArrowRight") to = (i + 1) % els.length;
    else if (e.key === "ArrowLeft") to = (i - 1 + els.length) % els.length;
    else if (e.key === "Home") to = 0;
    else if (e.key === "End") to = els.length - 1;
    if (to < 0) return;
    e.preventDefault(); e.stopPropagation();
    els[to]?.focus();
  };
  return (
    <div ref={ref} role="toolbar" aria-label={label} className={className} onKeyDown={onKeyDown}
      onFocusCapture={(e) => { const t = e.target as HTMLElement; if (t.matches?.("[data-roving]")) { current.current = t; sync(); } }}>
      {children}
    </div>
  );
}

/** A plain toolbar button that takes part in the arrow-key movement. */
export function ToolButton(p: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button type="button" data-roving="" {...p} />;
}

export function MenuButton({ spec, up }: { spec: MenuSpec; up?: boolean }) {
  const [open, setOpen] = useState(false);
  const btn = useRef<HTMLButtonElement>(null);
  const menu = useRef<HTMLDivElement>(null);
  const wrap = useRef<HTMLSpanElement>(null);
  const uid = useId();
  const items = () => Array.from(menu.current?.querySelectorAll<HTMLElement>("[role^=menuitem]") ?? []);
  const close = (refocus: boolean) => { setOpen(false); if (refocus) btn.current?.focus(); };
  useEffect(() => {
    if (!open) return;
    const away = (e: Event) => { if (!wrap.current?.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("pointerdown", away);
    return () => document.removeEventListener("pointerdown", away);
  }, [open]);
  useEffect(() => { if (open) items().find((e) => e.getAttribute("aria-disabled") !== "true")?.focus(); }, [open]);

  const sibling = (d: 1 | -1) => {
    const bar = btn.current?.closest("[role=toolbar]");
    const all = Array.from(bar?.querySelectorAll<HTMLElement>("[data-menubtn]") ?? []);
    const at = all.indexOf(btn.current!);
    setOpen(false);
    all[(at + d + all.length) % all.length]?.click();
  };
  const onMenuKey = (e: React.KeyboardEvent) => {
    const els = items();
    const i = els.indexOf(document.activeElement as HTMLElement);
    const go = (n: number) => { e.preventDefault(); els[(n + els.length) % els.length]?.focus(); };
    switch (e.key) {
      case "ArrowDown": go(i + 1); break;
      case "ArrowUp": go(i < 0 ? els.length - 1 : i - 1); break;
      case "Home": go(0); break;
      case "End": go(els.length - 1); break;
      case "Escape": e.preventDefault(); close(true); break;
      case "Tab": close(true); return;
      case "ArrowRight": e.preventDefault(); sibling(1); break;
      case "ArrowLeft": e.preventDefault(); sibling(-1); break;
      default: {
        if (e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey && e.key !== " ") {
          const ch = e.key.toLowerCase();
          const order = [...els.slice(i + 1), ...els.slice(0, i + 1)];
          const hit = order.find((x) => (x.textContent ?? "").replace(/^\s*[✓•]?\s*/, "").toLowerCase().startsWith(ch));
          if (hit) { e.preventDefault(); hit.focus(); }
          break;
        }
        return;
      }
    }
    e.stopPropagation();
  };
  const run = (en: Extract<MenuEntry, { type: "item" }>) => {
    if (en.disabled) return;
    en.onSelect();
    close(!en.moves);
  };
  return (
    <span ref={wrap} className="split-menuwrap" data-align={spec.align ?? "start"} data-up={up || undefined}>
      <button ref={btn} type="button" data-roving="" data-menubtn={spec.id} className="split-menubtn" aria-haspopup="menu" aria-expanded={open} aria-controls={open ? `${uid}-menu` : undefined}
        title={spec.title} onClick={() => setOpen(!open)}
        onKeyDown={(e) => { if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); e.stopPropagation(); setOpen(true); } }}>
        {spec.label}<span className="split-caret" aria-hidden="true">{up ? "▴" : "▾"}</span>
      </button>
      {open && (
        <div ref={menu} id={`${uid}-menu`} role="menu" aria-label={spec.label} className="split-menupop" onKeyDown={onMenuKey}>
          {spec.entries.map((en, i) => {
            if (en.type === "sep") return <div key={i} role="separator" className="split-mi-sep" />;
            if (en.type === "heading") return <div key={i} role="presentation" className="split-mi-head">{en.label}</div>;
            const role = en.role ?? "menuitem";
            const checked = role === "menuitem" ? undefined : !!en.checked;
            const inner = (<>
              <span className="split-mi-check" aria-hidden="true">{checked ? "✓" : ""}</span>
              <span className="split-mi-label">{en.label}</span>
              {en.keys && <kbd className="split-mi-keys" aria-hidden="true">{en.keys}</kbd>}
            </>);
            return en.href ? (
              <a key={i} role="menuitem" tabIndex={-1} className="split-mi" href={en.href} onClick={() => setOpen(false)}>{inner}</a>
            ) : (
              <button key={i} type="button" role={role} tabIndex={-1} className="split-mi" aria-checked={checked} aria-disabled={en.disabled || undefined}
                aria-keyshortcuts={en.keys && en.keys.length === 1 ? en.keys : undefined} data-checked={checked || undefined} onClick={() => run(en)}>{inner}</button>
            );
          })}
        </div>
      )}
    </span>
  );
}
