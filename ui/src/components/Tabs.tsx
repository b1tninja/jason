import { useEffect, useId, useRef, type KeyboardEvent, type ReactNode } from "react";

export interface TabSpec {
  id: string;
  label: string;
  content: ReactNode;
}

/** Bring the selected tab into the tab row's own view. Only the row scrolls (its scrollLeft), never the page, so a
 * tab chosen while the row is off screen does not move what the person is reading. */
function revealSelected(list: HTMLElement | null) {
  const tab = list?.querySelector<HTMLElement>('[role="tab"][aria-selected="true"]');
  if (!list || !tab || list.scrollWidth <= list.clientWidth) return;
  const row = list.getBoundingClientRect();
  const box = tab.getBoundingClientRect();
  const pad = 16; // a little of the neighbour shows, so the row reads as one that scrolls
  if (box.left < row.left) list.scrollLeft -= row.left - box.left + pad;
  else if (box.right > row.right) list.scrollLeft += box.right - row.right + pad;
}

/** The ARIA tabs pattern: one tab in the Tab order (the selected one); Left and Right move between tabs and select
 * the one they reach, Home and End go to the first and last. On a narrow screen the row scrolls sideways (`.tabs`),
 * and the selected tab is scrolled into the row's view whenever it changes.
 * `panelHidden` hides the panel and keeps its content mounted, so what a person typed in it survives (a collapsed sheet). */
export function Tabs({ tabs, active, onChange, panelHidden }: { tabs: TabSpec[]; active: string; onChange: (id: string) => void; panelHidden?: boolean }) {
  const base = useId();
  const listRef = useRef<HTMLDivElement>(null);
  const current = tabs.find((t) => t.id === active) ?? tabs[0];
  useEffect(() => { revealSelected(listRef.current); }, [current?.id]);

  function onKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    const at = tabs.findIndex((t) => t.id === current?.id);
    const to = e.key === "ArrowRight" ? (at + 1) % tabs.length
      : e.key === "ArrowLeft" ? (at - 1 + tabs.length) % tabs.length
      : e.key === "Home" ? 0
      : e.key === "End" ? tabs.length - 1
      : -1;
    if (to < 0 || !tabs.length) return;
    e.preventDefault();
    onChange(tabs[to].id);
    listRef.current?.querySelector<HTMLElement>(`[id="${base}-${tabs[to].id}"]`)?.focus();
  }

  return (
    <div className="tabset">
      <div role="tablist" className="tabs" ref={listRef} onKeyDown={onKeyDown}>
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            id={`${base}-${t.id}`}
            aria-selected={t.id === current?.id}
            aria-controls={`${base}-panel`}
            tabIndex={t.id === current?.id ? 0 : -1}
            onClick={() => onChange(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div role="tabpanel" id={`${base}-panel`} aria-labelledby={current && `${base}-${current.id}`} hidden={panelHidden || undefined}>
        {current?.content}
      </div>
    </div>
  );
}
