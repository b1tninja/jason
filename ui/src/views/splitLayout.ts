/** The splitter's screen layout (docs/pdf-splitter.md, section 5.9): focus mode, the drawers, and the grid's columns. Pure helpers and the
 * per-tab preferences; nothing here touches React or the page. */

export type Side = "left" | "right" | "bottom";
export type DrawerId = "rail" | "inspect";

/** What a person chose for the layout, kept for the tab (sessionStorage), never sent anywhere.
 * `rail` null: the screen decides (open from `RAIL_OPEN_PX` up). `pinned` null: the screen decides (the rail docks from the same width);
 * "none": nothing docks, every drawer overlays. */
export interface LayoutPrefs {
  focus: boolean;
  rail: boolean | null;
  railSide: "left" | "right";
  pinned: DrawerId | "none" | null;
  inspectFull: boolean;
  /** the album's columns fill the width with whole columns (on), or keep the slider's size exactly (off) */
  fill: boolean;
  showSuggestions: boolean;
  showFlags: boolean;
}

export const DEFAULT_PREFS: LayoutPrefs = { focus: false, rail: null, railSide: "left", pinned: null, inspectFull: false, fill: true, showSuggestions: true, showFlags: true };

/** The segments drawer opens by itself, docked, only on a screen this wide; under it the default is closed. */
export const RAIL_OPEN_PX = 1400;
/** A drawer can dock (pin) only on a screen this wide; under it a drawer only overlays. */
export const PIN_PX = 1200;

const key = (id: string) => `jason-split-layout-${id}`;

export function loadPrefs(id: string): LayoutPrefs {
  try {
    const raw = JSON.parse(sessionStorage.getItem(key(id)) ?? "{}") as Partial<LayoutPrefs>;
    const out: LayoutPrefs = { ...DEFAULT_PREFS };
    if (typeof raw.focus === "boolean") out.focus = raw.focus;
    if (typeof raw.rail === "boolean" || raw.rail === null) out.rail = raw.rail;
    if (raw.railSide === "left" || raw.railSide === "right") out.railSide = raw.railSide;
    if (raw.pinned === "rail" || raw.pinned === "inspect" || raw.pinned === "none" || raw.pinned === null) out.pinned = raw.pinned;
    if (typeof raw.inspectFull === "boolean") out.inspectFull = raw.inspectFull;
    if (typeof raw.fill === "boolean") out.fill = raw.fill;
    if (typeof raw.showSuggestions === "boolean") out.showSuggestions = raw.showSuggestions;
    if (typeof raw.showFlags === "boolean") out.showFlags = raw.showFlags;
    return out;
  } catch { return { ...DEFAULT_PREFS }; }
}

export function savePrefs(id: string, p: LayoutPrefs): void {
  try { sessionStorage.setItem(key(id), JSON.stringify(p)); } catch { /* storage blocked: the layout simply is not remembered */ }
}

/** Whether the segments drawer is open, which drawer (if any) is docked, from the preferences and the screen. */
export function resolveLayout(p: LayoutPrefs, width: { big: boolean; canPin: boolean }): { railOpen: boolean; docked: DrawerId | null } {
  const railOpen = p.rail ?? width.big;
  const wanted: DrawerId | null = p.pinned === "none" ? null : p.pinned ?? (width.big ? "rail" : null);
  return { railOpen, docked: width.canPin ? wanted : null };
}

/** The columns and the cell width that fill `avail` px with whole columns of about `target` px, `gap` apart. A column is never narrower than
 * `min`; the cell is at most `target` plus one column's share, so the slider still means "about this big". */
export function fitCell(avail: number, target: number, gap = 8, min = 48): { cols: number; cell: number } {
  const t = Math.max(min, target);
  const room = Math.max(avail, t);
  const cols = Math.max(1, Math.floor((room + gap) / (t + gap)));
  const cell = Math.max(min, Math.floor((room - gap * (cols - 1)) / cols));
  return { cols, cell };
}

/** What a drag on a drawer's handle means. A drag counts only past `threshold` px and only when it runs along the drawer's axis, so a tap,
 * a scroll across the handle, or a boundary drag in the grid is never read as one. */
export function dragIntent(dx: number, dy: number, side: Side, open: boolean, threshold = 12): "open" | "close" | null {
  const along = side === "bottom" ? dy : dx;
  const across = side === "bottom" ? dx : dy;
  if (Math.abs(along) < threshold || Math.abs(along) < Math.abs(across) * 1.2) return null;
  // toward the middle of the screen opens, toward the edge closes
  const toward = side === "left" ? along > 0 : along < 0;
  return toward ? (open ? null : "open") : (open ? "close" : null);
}

/** The chips of the slim strip: all of them up to `max`, otherwise a run around the current one. `from` and `to` are indexes, `to` exclusive. */
export function stripWindow(count: number, current: number, max = 240): { from: number; to: number } {
  if (count <= max) return { from: 0, to: count };
  const from = Math.max(0, Math.min(count - max, current - Math.floor(max / 2)));
  return { from, to: from + max };
}
