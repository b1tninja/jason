import { RefusedRow } from "jason-ui";

// A control that would go below a floor is listed with the floor, recited. Made-up: "Example Bylaws", plainly fake words.
const list = { listStyle: "none", margin: 0, padding: 0, display: "grid", gap: 10, maxWidth: 720 } as const;

/** One refused control: the title, a "refused" badge with its glyph, the reason, and the floor's words recited with the citation. */
export const Refused = () => (
  <ul style={list}>
    <RefusedRow r={{
      title: "One signer for reserve withdrawals",
      why: "The floor is two board members (Example Bylaws, 99.9(b)).",
      floor: { citation: "Example Bylaws, 99.9(b)", words: "Withdrawals from the reserve account require the signatures of two board members. (Sample text, not a governing document.)" },
    }} />
  </ul>
);

/** Several refusals, each with its own floor, in the list's spacing. */
export const SeveralRefused = () => (
  <ul style={list}>
    <RefusedRow r={{
      title: "One signer for reserve withdrawals",
      why: "The floor is two board members (Example Bylaws, 99.9(b)).",
      floor: { citation: "Example Bylaws, 99.9(b)", words: "Withdrawals from the reserve account require the signatures of two board members. (Sample text.)" },
    }} />
    <RefusedRow r={{
      title: "Skip the notice to members",
      why: "The floor is a written notice before the vote (EX 123.4).",
      floor: { citation: "EX 123.4", words: "The association shall give written notice to each member before the vote. (Sample text, not a statute.)" },
    }} />
  </ul>
);
