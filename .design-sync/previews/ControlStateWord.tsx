import { ControlStateWord } from "jason-ui";

const row = { display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" } as const;
const col = { display: "grid", gap: 10, justifyItems: "start" } as const;

/** One word per standing the loader names: a suggestion, a proposal, and a control in force. The word and the mark carry the state, never the colour alone. */
export const Standings = () => (
  <div style={col}>
    <ControlStateWord standing="suggested" />
    <ControlStateWord standing="proposed" />
    <ControlStateWord standing="in-force" />
  </div>
);

/** Adopted but not binding, two ways: the date is ahead (a calendar, with the date), and the date has come but the roster cannot satisfy it. */
export const AdoptedButNotBinding = () => (
  <div style={col}>
    <ControlStateWord standing="adopted-not-in-force" effective="2099-01-01" />
    <ControlStateWord standing="adopted-not-in-force" />
    <ControlStateWord standing="in-force-roster-lacks" />
  </div>
);

/** The board's other outcomes: declined, deferred, retired. All neutral. */
export const BoardOutcomes = () => (
  <div style={row}>
    <ControlStateWord standing="declined" />
    <ControlStateWord standing="deferred" />
    <ControlStateWord standing="retired" />
  </div>
);

/** With `detail`, the loader's own sentence follows the short word, so the page invents none. */
export const WithDetail = () => (
  <div style={col}>
    <ControlStateWord detail standing="in-force" word="Adopted by the board on 2098-11-14; it applies to every payment over the limit." />
    <ControlStateWord detail standing="adopted-not-in-force" effective="2099-01-01" word="Adopted on 2098-11-14; it applies from 2099-01-01." />
    <ControlStateWord detail standing="suggested" word="jason suggests this; the board has not taken it up." />
  </div>
);

/** A standing the page does not know is shown as the loader's word, plainly, as a neutral badge. */
export const UnknownStanding = () => (
  <div style={row}>
    <ControlStateWord standing="under-review" word="Under review" />
    <ControlStateWord standing="" />
  </div>
);
