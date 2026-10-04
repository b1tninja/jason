import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
import { Badge, type Tone } from "./Badge";
import { Caveats } from "./Caveats";
import { Command } from "./Command";
import { ErrorNotice } from "./States";
import {
  LEAD_NOT_PIN, STANDING_MEANING, associationsPath, countyName, evidenceText, useDebounced, useKeptJson, yearsText,
  type AssociationChoice, type Directory, type DirectoryRow,
} from "../lib/discovery";

const STANDING_TONE: Record<string, Tone> = { confirmed: "good", likely: "neutral", named: "neutral" };

/** The row's facts in words: kind and standing badges, the years it recorded, and what the recordings show. */
function RowFacts({ row }: { row: DirectoryRow }) {
  const years = yearsText(row.first, row.last);
  const ev = evidenceText(row.evidence);
  return (
    <>
      <span className="row wrap assoc-badges">
        <Badge>{row.kind}</Badge>
        <span title={STANDING_MEANING[row.standing]}><Badge tone={STANDING_TONE[row.standing] ?? "neutral"}>{row.standing}</Badge></span>
        {years && <span className="muted">{years}</span>}
      </span>
      {ev && <span className="muted assoc-evidence">{ev}</span>}
    </>
  );
}

/** The directory's size in words: "412 associations: 230 confirmed · 120 likely · 62 named". */
function summaryText(d: Directory): string {
  const by = d.summary?.byStanding;
  if (!by) return "";
  const total = Object.values(by).reduce((a, b) => a + b, 0);
  const parts = Object.entries(by).filter(([, n]) => n > 0).map(([k, n]) => `${n.toLocaleString("en-US")} ${k}`);
  return `${total.toLocaleString("en-US")} ${total === 1 ? "association" : "associations"}${parts.length ? `: ${parts.join(" · ")}` : ""}`;
}

/** Choose the association from the county's directory (built from the county recorder's public index): a county, a
 * search box that is a WAI-ARIA combobox over a listbox of results (arrows move, Enter chooses, Escape closes), each
 * result with its name, kind and standing, the years it recorded, and what its recordings show. The chosen row shows
 * every spelling the index holds. Choosing only emits `onPick`; it writes nothing. A directory row is a lead, not a
 * pin. A county with no directory shows the command that builds it. */
export function AssociationPicker({
  counties = ["placer"], defaultCounty, onPick, onClear, picked, limit = 25, debounceMs = 300,
}: {
  counties?: readonly string[];
  defaultCounty?: string;
  onPick: (choice: AssociationChoice) => void;
  onClear?: () => void;
  /** A choice already made (the view's), shown instead of the search. */
  picked?: AssociationChoice | null;
  limit?: number;
  debounceMs?: number;
}) {
  const uid = useId();
  const [county, setCounty] = useState(defaultCounty ?? counties[0] ?? "");
  const [words, setWords] = useState("");
  const q = useDebounced(words, debounceMs);
  const [open, setOpen] = useState(true);
  const [active, setActive] = useState(-1);
  const [chosen, setChosen] = useState<AssociationChoice | null>(picked ?? null);
  useEffect(() => setChosen(picked ?? null), [picked]);
  const input = useRef<HTMLInputElement>(null);
  const r = useKeptJson<Directory>(associationsPath(county, q, limit));
  const d = r.data;
  const rows = d?.surveyed ? d.results ?? [] : [];
  useEffect(() => setActive(-1), [d]);
  const expanded = open && !chosen && rows.length > 0;
  const listId = `${uid}-list`;
  const optId = (i: number) => `${uid}-opt-${i}`;

  const choose = (row: DirectoryRow) => {
    const c: AssociationChoice = { key: row.key, name: row.name, county, row };
    setChosen(c);
    setOpen(false);
    onPick(c);
  };
  const again = () => {
    setChosen(null);
    setOpen(true);
    onClear?.();
    setTimeout(() => input.current?.focus(), 0);
  };
  const onKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (!open) { setOpen(true); setActive(0); return; }
      setActive((a) => Math.min(a + 1, rows.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => Math.max(a - 1, 0));
    } else if (e.key === "Enter") {
      if (expanded && active >= 0 && rows[active]) { e.preventDefault(); choose(rows[active]); }
    } else if (e.key === "Escape") {
      if (expanded) { e.preventDefault(); setOpen(false); setActive(-1); }
      else if (words) { e.preventDefault(); setWords(""); }
    }
  };

  const status = r.loading ? "Searching the directory…"
    : !d ? ""
    : !d.surveyed ? `The ${countyName(county)} directory is not built yet.`
    : rows.length ? `${rows.length} ${rows.length === 1 ? "association matches" : "associations match"}${q.trim() ? ` "${q.trim()}"` : ""}. Arrow keys move; Enter chooses.`
    : q.trim() ? `No association in the ${countyName(county)} directory matches "${q.trim()}".` : "The directory has no associations.";

  const caveats = [LEAD_NOT_PIN, ...(d?.caveats ?? []).filter((c) => c !== LEAD_NOT_PIN)];

  return (
    <div className="assoc-picker stack-sm">
      {chosen ? (
        <section className="assoc-chosen notice" aria-labelledby={`${uid}-chosen`}>
          <div className="stack-sm">
            <span className="muted">Chosen from the {countyName(chosen.county)} directory</span>
            <strong id={`${uid}-chosen`} className="assoc-name">{chosen.name}</strong>
            <RowFacts row={chosen.row} />
            {chosen.row.governing > 0 && <span className="muted">{chosen.row.governing} governing {chosen.row.governing === 1 ? "instrument" : "instruments"} under the name</span>}
            {chosen.row.spellings.length > 0 && (
              <details>
                <summary>{chosen.row.spellings.length} {chosen.row.spellings.length === 1 ? "spelling" : "spellings"} in the index</summary>
                <ul className="assoc-spellings">{chosen.row.spellings.map((s) => <li key={s}><code className="chip">{s}</code></li>)}</ul>
              </details>
            )}
            <div className="row wrap"><button type="button" onClick={again}>Choose another</button></div>
          </div>
        </section>
      ) : (
        <>
          <div className="row wrap assoc-fields">
            {counties.length > 1 ? (
              <label className="assoc-field">County
                <select value={county} onChange={(e) => { setCounty(e.target.value); setOpen(true); }}>
                  {counties.map((c) => <option key={c} value={c}>{countyName(c)}</option>)}
                </select>
              </label>
            ) : (
              <span className="assoc-field"><span className="muted">County</span> <strong>{countyName(county)}</strong></span>
            )}
            <label className="assoc-field assoc-search" htmlFor={`${uid}-q`}>Association's name</label>
            <input
              id={`${uid}-q`} ref={input} type="text" className="search" role="combobox" autoComplete="off" spellCheck={false}
              aria-autocomplete="list" aria-expanded={expanded} aria-controls={listId}
              aria-activedescendant={expanded && active >= 0 ? optId(active) : undefined}
              aria-describedby={`${uid}-hint`}
              placeholder="a few words of the name" value={words}
              onChange={(e) => { setWords(e.target.value); setOpen(true); }} onKeyDown={onKey}
            />
          </div>
          <p id={`${uid}-hint`} className="muted">As the county recorder's index names it. The directory lists association-named parties only, never an owner.</p>
          <p className="muted" role="status" aria-live="polite">{status}</p>
          {d && !d.surveyed && (
            <div className="notice notice-warn stack-sm">
              <p>{d.note || `jason has no association directory for ${countyName(county)} yet. A person builds it once from the county recorder's public index.`}</p>
              {d.command && <Command cmd={d.command} note="Builds the directory; read-only against the county. Run it in a terminal." />}
            </div>
          )}
          {d?.surveyed && summaryText(d) && <p className="muted">The {countyName(county)} directory holds {summaryText(d)}.</p>}
          {r.error && <ErrorNotice error={`jason could not read the association directory: ${r.error}`} onRetry={r.reload} />}
          <ul id={listId} role="listbox" aria-label={`Associations in the ${countyName(county)} directory`} className="assoc-list" hidden={!expanded}>
            {rows.map((row, i) => (
              <li
                key={row.key} id={optId(i)} role="option" aria-selected={i === active}
                className={i === active ? "assoc-option assoc-active" : "assoc-option"}
                onMouseDown={(e) => e.preventDefault()} onClick={() => choose(row)} onMouseMove={() => setActive(i)}
              >
                <span className="assoc-name">{row.name}</span>
                <RowFacts row={row} />
                {row.spellings.length > 1 && <span className="muted">{row.spellings.length} spellings</span>}
              </li>
            ))}
          </ul>
        </>
      )}
      <Caveats items={caveats} />
    </div>
  );
}
