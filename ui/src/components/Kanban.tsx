import type { ReactNode } from "react";

/** Cards grouped into the given lanes, in the given order. A lane with nothing shows as empty, never dropped. */
export function Kanban<T>({ lanes, items, laneOf, render, keyOf }: {
  lanes: readonly string[];
  items: readonly T[];
  laneOf: (item: T) => string;
  render: (item: T) => ReactNode;
  keyOf: (item: T) => string;
}) {
  return (
    <div className="kanban">
      {lanes.map((lane) => {
        const inLane = items.filter((i) => laneOf(i) === lane);
        return (
          <section key={lane} className="lane" aria-label={lane}>
            <h3>
              {lane} <span className="muted">{inLane.length}</span>
            </h3>
            {inLane.map((i) => (
              <div key={keyOf(i)}>{render(i)}</div>
            ))}
          </section>
        );
      })}
    </div>
  );
}
