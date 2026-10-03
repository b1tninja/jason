import { ReadingLabel, Recitation } from "jason-ui";

const lease = {
  kind: "section", found: true, citation: "Declaration for Example Village, Article 7, Section 7.3",
  text: "Section 7.3. Leasing. An Owner may lease the Owner's entire Unit, provided that the term of the lease is not less than thirty (30) days and the lease is in writing.\n\nNo Owner may lease less than the entire Unit.",
  inForce: "as amended 2024-03-12, in force from 2024-03-12", address: "decl#7.3",
  caveat: "jason's consolidated text, not an official restatement. The recorded instrument governs.",
  terms: [{ term: "Unit", citation: "Declaration § 1.20", definition: "a separate interest in a Lot shown on the Plan.", found: true }],
};

/** The words whole, the words that answer the question marked, the version in force, a defined term, and the caveat. */
export const Recited = () => <Recitation citation={lease} mark="not less than thirty (30) days" />;

/** A rule that is not in force: a draft amendment, labeled and never merged. */
export const NotInForce = () => <Recitation citation={{ ...lease, citation: "Section 7.3, as the 2027 amendment would set it", version: { inForce: false, note: "a draft: not in force, and never merged into the text in force" } }} />;

/** A miss recites nothing and says why. */
export const Miss = () => <Recitation citation={{ kind: "miss", found: false, citation: "Rules R-9(c)", reason: "no_such_section" }} />;

/** Followed by a labeled reading, never inside it. */
export const WithReading = () => (
  <div className="stack-sm">
    <Recitation citation={lease} />
    <ReadingLabel whose="jason">jason reads Section 7.3 to require a written lease of at least 30 days for the whole unit.</ReadingLabel>
  </div>
);
