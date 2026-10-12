import { RosterCheck } from "jason-ui";

// The roster check on a control's card: offices and counts only, never a name. Made-up offices.
const wide = { maxWidth: 640 } as const;

/** The roster can satisfy the control: what it needs and what is seated, by office and count. */
export const CanSatisfy = () => (
  <div style={wide}>
    <RosterCheck roster={{
      read: true, lacks: "", missing: [],
      needs: [{ office: "treasurer", count: 1 }, { office: "director", count: 1 }],
      seated: [{ office: "treasurer", count: 1 }, { office: "director", count: 3 }, { office: "secretary", count: 1 }],
    }} />
  </div>
);

/** A shortfall: the missing office is listed and the loader's sentence follows the verdict. */
export const Cannot = () => (
  <div style={wide}>
    <RosterCheck roster={{
      read: true, lacks: "No director is seated, so no pair of offices can sign.",
      needs: [{ office: "treasurer", count: 1 }, { office: "director", count: 1 }],
      seated: [{ office: "treasurer", count: 1 }, { office: "secretary", count: 1 }],
      missing: [{ office: "director" }],
    }} />
  </div>
);

/** The control asks for no particular office, and none is seated. */
export const NothingSeated = () => (
  <div style={wide}>
    <RosterCheck roster={{ read: true, lacks: "", needs: [], seated: [], missing: [] }} />
  </div>
);

/** The roster could not be read: the check says so and assumes nothing about who is seated. */
export const NotRead = () => (
  <div style={wide}>
    <RosterCheck roster={{ read: false, lacks: "", needs: [], seated: [], missing: [] }} />
  </div>
);
