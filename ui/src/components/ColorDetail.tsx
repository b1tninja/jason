import { useId } from "react";
import { Caveats } from "./Caveats";
import { PAINT_CAPTION } from "./PaletteMatrix";
import { Swatch, type PaintColor } from "./Swatch";

/** One color's detail (docs/paint-ui-design.md), as `SherwinWilliams.related`, `.nearest` and a person's click on the
 * description give it. */
export interface PaintColorDetail {
  color: PaintColor;
  /** Fetched only on a person's click; absent otherwise. */
  description?: string;
  family?: string;
  /** The schedule's surfaces that use it, as printed: "ENTRY DOORS". */
  usedOn?: string[];
  coordinating?: PaintColor[];
  similar?: PaintColor[];
  /** The closest current colors, for a discontinued one. */
  closestCurrent?: PaintColor[];
}

export const TOUCH_UP_CAVEAT = "A touch-up on aged paint may not match the code.";
export const NO_DESCRIPTION = "No description on file.";

function Chips({ title, colors, onOpen }: { title: string; colors?: PaintColor[]; onOpen?: (c: PaintColor) => void }) {
  const id = useId();
  if (!colors?.length) return null;
  return (
    <section className="paint-chips" aria-labelledby={id}>
      <h4 id={id} className="paint-chips-title">{title}</h4>
      <ul className="paint-chip-list">
        {colors.map((c) => <li key={c.code}><Swatch color={c} size="chip" onOpen={onOpen} /></li>)}
      </ul>
    </section>
  );
}

/** A panel for one color: its swatch, description, light reflectance, family, where the schedule uses it, its coordinating
 * and similar colors as chips, and for a discontinued color its closest current ones. Always the touch-up caveat and the
 * caption that the number governs. `onOpenColor` opens a chip's own detail; `onFetchDescription` is a person's click. */
export function ColorDetail({ detail, onOpenColor, onFetchDescription }: {
  detail: PaintColorDetail; onOpenColor?: (c: PaintColor) => void; onFetchDescription?: () => void;
}) {
  const id = useId();
  const { color } = detail;
  return (
    <section className="paint-detail" aria-labelledby={id}>
      <h3 id={id} className="paint-detail-title">{color.code} {color.name}</h3>
      <Swatch color={color} size="tile" showStatus />
      <p className="paint-description">
        {detail.description ?? <span className="muted">{NO_DESCRIPTION}</span>}
        {!detail.description && onFetchDescription && <> <button type="button" onClick={onFetchDescription}>Fetch the description</button></>}
      </p>
      <dl className="kv paint-facts">
        <dt>Light reflectance</dt><dd>{color.lrv !== undefined ? color.lrv : <span className="muted">None on record</span>}</dd>
        <dt>Family</dt><dd>{detail.family ?? <span className="muted">None on record</span>}</dd>
        <dt>Used on</dt>
        <dd>{detail.usedOn?.length ? detail.usedOn.join(", ") : <span className="muted">Not on the schedule</span>}</dd>
      </dl>
      {color.status === "discontinued" && (
        detail.closestCurrent?.length
          ? <Chips title="Closest current colors" colors={detail.closestCurrent} onOpen={onOpenColor} />
          : <p className="muted">No closest current colors are on file.</p>
      )}
      <Chips title="Coordinating colors" colors={detail.coordinating} onOpen={onOpenColor} />
      <Chips title="Similar colors" colors={detail.similar} onOpen={onOpenColor} />
      <Caveats items={[TOUCH_UP_CAVEAT, PAINT_CAPTION]} />
    </section>
  );
}
