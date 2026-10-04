import { useId, type ReactNode } from "react";

export interface TabSpec {
  id: string;
  label: string;
  content: ReactNode;
}

/** `panelHidden` hides the panel and keeps its content mounted, so what a person typed in it survives (a collapsed sheet). */
export function Tabs({ tabs, active, onChange, panelHidden }: { tabs: TabSpec[]; active: string; onChange: (id: string) => void; panelHidden?: boolean }) {
  const base = useId();
  const current = tabs.find((t) => t.id === active) ?? tabs[0];
  return (
    <div>
      <div role="tablist" className="tabs">
        {tabs.map((t) => (
          <button
            key={t.id}
            role="tab"
            id={`${base}-${t.id}`}
            aria-selected={t.id === current?.id}
            aria-controls={`${base}-panel`}
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
