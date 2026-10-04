import { TieBadge } from "jason-ui";

/* A located document's tie (`jason.community.locator.Tie`): why the locator thinks it is the association's. The rows
 * are cut from the `/api/documents-located` payload; names are made up. */
const doc = (tie: string, tie_label: string, strong: boolean, via = "") =>
  ({ number: "2005-0020001", recorded: "2005-06-10", filing: "DECLARATION OF ANNEXATION", tie, tie_label, strong, via, parties: ["EXAMPLE HOMES INC"] });

/** A strong tie: the instrument names the association. */
export const NamesTheAssociation = () => <TieBadge doc={doc("NAMED", "names the association", true)} />;

/** A strong tie by place: recorded in the same bundle as one of the association's documents. */
export const RecordedBeside = () => <TieBadge doc={doc("BESIDE", "recorded with the association's documents", true, "2005-0020000")} />;

/** A weak tie in warning tone with its words: the builder's filing, which may belong to another community the builder built. */
export const BuildersFiling = () => <TieBadge doc={doc("DECLARANT", "the builder's filing", false, "EXAMPLE HOMES INC")} />;

/** The three ties as a column, as they read down the locator's table. */
export const AllThree = () => (
  <div className="stack-sm">
    <TieBadge doc={doc("NAMED", "names the association", true)} />
    <TieBadge doc={doc("BESIDE", "recorded with the association's documents", true, "2005-0020000")} />
    <TieBadge doc={doc("DECLARANT", "the builder's filing", false, "EXAMPLE HOMES INC")} />
  </div>
);
