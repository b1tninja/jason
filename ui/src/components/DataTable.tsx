import { useMemo, useState, type KeyboardEvent, type ReactNode } from "react";
import { EmptyState } from "./States";
import { SearchBox } from "./SearchBox";

export interface Column<T> {
  key: string;
  header: string;
  render?: (row: T) => ReactNode;
  /** Sort/filter value; defaults to row[key]. */
  value?: (row: T) => string | number;
  align?: "left" | "right";
  /** `date`: an ISO day that never wraps and uses tabular figures. */
  kind?: "date";
}

type Dir = "asc" | "desc";

/** A sortable, filterable table. With `onSelect`, a whole-row click or Enter selects the row (`aria-selected`, the
 * `selected` class), which replaces an "Open" column; `rowKey` names rows for `selectedKey`. */
export function DataTable<T extends object>({
  rows,
  columns,
  searchable = true,
  caption,
  rowKey,
  selectedKey,
  onSelect,
}: {
  rows: readonly T[];
  columns: Column<T>[];
  searchable?: boolean;
  caption?: string;
  rowKey?: (row: T) => string;
  selectedKey?: string;
  onSelect?: (row: T) => void;
}) {
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<{ key: string; dir: Dir } | null>(null);

  const val = (c: Column<T>, r: T) => (c.value ? c.value(r) : ((r as Record<string, unknown>)[c.key] as string | number | undefined) ?? "");

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    let out = q ? rows.filter((r) => columns.some((c) => String(val(c, r)).toLowerCase().includes(q))) : [...rows];
    const col = sort && columns.find((c) => c.key === sort.key);
    if (col && sort) {
      const sign = sort.dir === "asc" ? 1 : -1;
      out = out.sort((a, b) => {
        const x = val(col, a), y = val(col, b);
        return (typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y), undefined, { numeric: true })) * sign;
      });
    }
    return out;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, columns, query, sort]);

  const toggle = (key: string) =>
    setSort((s) => (s?.key !== key ? { key, dir: "asc" } : s.dir === "asc" ? { key, dir: "desc" } : null));

  const cellClass = (c: Column<T>) => [c.align === "right" ? "num" : "", c.kind === "date" ? "date" : ""].filter(Boolean).join(" ") || undefined;
  const keyOf = (r: T, i: number) => (rowKey ? rowKey(r) : String(i));
  const onKey = (r: T) => (e: KeyboardEvent<HTMLTableRowElement>) => {
    if (onSelect && e.key === "Enter" && e.target === e.currentTarget) { e.preventDefault(); onSelect(r); }
  };

  return (
    <div className="table-wrap">
      {searchable && rows.length > 5 && <SearchBox value={query} onChange={setQuery} />}
      {shown.length === 0 ? (
        <EmptyState>{rows.length ? "No rows match." : "Nothing to show."}</EmptyState>
      ) : (
        <table className={onSelect ? "selectable" : undefined}>
          {caption && <caption>{caption}</caption>}
          <thead>
            <tr>
              {columns.map((c) => (
                <th
                  key={c.key}
                  className={cellClass(c)}
                  aria-sort={sort?.key === c.key ? (sort.dir === "asc" ? "ascending" : "descending") : "none"}
                >
                  <button onClick={() => toggle(c.key)}>{c.header}</button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {shown.map((r, i) => {
              const k = keyOf(r, i);
              const selected = onSelect ? selectedKey !== undefined && selectedKey === k : undefined;
              return (
                <tr
                  key={k}
                  className={selected ? "selected" : undefined}
                  aria-selected={selected}
                  tabIndex={onSelect ? 0 : undefined}
                  onClick={onSelect ? () => onSelect(r) : undefined}
                  onKeyDown={onSelect ? onKey(r) : undefined}
                >
                  {columns.map((c) => (
                    <td key={c.key} className={cellClass(c)}>
                      {c.render ? c.render(r) : String(val(c, r))}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}
