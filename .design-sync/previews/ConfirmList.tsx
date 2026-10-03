import { useState } from "react";
import { Card, Command, ConfirmList, type ConfirmRow } from "jason-ui";

const planned: ConfirmRow[] = [
  { key: "tag|unit-7|owner-occupied", label: "Unit 7: tag owner-occupied", detail: "answer: lives at the unit", why: "owner's form answer" },
  { key: "tag|unit-12|rented", label: "Unit 12: tag rented", detail: "answer: tenant since 2025-06", why: "owner's form answer" },
  { key: "tag|unit-12|mailing", label: "Unit 12: mailing address off-site", detail: "answer: PO Box 4567", why: "owner's form answer" },
];

function Working({ initial, who }: { initial: ConfirmRow[]; who: string }) {
  const [rows, setRows] = useState(initial);
  const toggle = (row: ConfirmRow, confirmed: boolean) =>
    setRows((rs) => rs.map((r) => (r.key === row.key ? { ...r, by: confirmed ? who : undefined, on: confirmed ? "2026-10-03T16:00:00Z" : undefined } : r)));
  return (
    <ConfirmList rows={rows} who={who} onToggle={toggle}>
      <Command cmd="jason owner-info --apply --payhoa --yes" note="Every write confirmed; a person runs this from a terminal." />
    </ConfirmList>
  );
}

/** Nothing confirmed yet, a name entered: three ticks to work through, the next step held back. */
export const Pending = () => <Working initial={planned} who="D. Okafor" />;

/** Two of three confirmed, each with the confirmer's name and day beside it. */
export const Partial = () => (
  <Working
    who="D. Okafor"
    initial={[
      { ...planned[0], by: "D. Okafor", on: "2026-10-02T21:10:00Z" },
      { ...planned[1], by: "M. Chen", on: "2026-10-03T15:02:00Z" },
      planned[2],
    ]}
  />
);

/** Every row confirmed: the gated child appears, here the terminal command that applies the writes. */
export const AllConfirmed = () => (
  <Working who="D. Okafor" initial={planned.map((r, i) => ({ ...r, by: i % 2 ? "M. Chen" : "D. Okafor", on: "2026-10-03T15:02:00Z" }))} />
);

/** No name entered: the boxes are disabled and the count line says why. */
export const NoName = () => <Working initial={planned} who="" />;

/** The empty state inside a card. */
export const Empty = () => (
  <Card title="Planned writes">
    <ConfirmList rows={[]} who="D. Okafor" onToggle={() => {}} empty="No writes planned; the last run found nothing to tag." />
  </Card>
);
