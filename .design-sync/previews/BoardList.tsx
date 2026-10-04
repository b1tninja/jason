import { BoardList } from "jason-ui";

/* The same located documents as `LocatedDocuments`, as the board's printable checklist. Made-up association. */
const located = {
  association: "Example Village HOA", county: "placer", located_at: "2026-10-02T15:04:00", searches: 42, liens: 386,
  spellings: ["EXAMPLE VILLAGE HOMEOWNERS ASSOCIATION", "EXAMPLE VILLAGE HOA"],
  items: [
    { item: "declaration", title: "The declaration (CC&Rs), the recorded copy", question: "Which is the association's declaration (the CC&Rs later amendments amend)?", stakes: true,
      located: [{ number: "2001-0000020", recorded: "2001-03-08", filing: "AMENDED RESTRICTION", tie: "NAMED", tie_label: "names the association", strong: true, via: "", parties: ["EXAMPLE HOMES INC"] }] },
    { item: "annexations", title: "Annexations", question: "Which of these annex a phase into the association (or take one out)?", stakes: false,
      located: [
        { number: "2003-0000050", recorded: "2003-06-01", filing: "DECLARATION OF ANNEXATION", tie: "BESIDE", tie_label: "recorded with the association's documents", strong: true, via: "2003-0000049", parties: [] },
        { number: "2007-0030003", recorded: "2007-01-15", filing: "DECLARATION OF ANNEXATION", tie: "DECLARANT", tie_label: "the builder's filing", strong: false, via: "EXAMPLE HOMES INC", parties: [] },
      ] },
  ],
  not_located: [{ item: "maps", title: "The subdivision maps", ask: "Ask the board or the prior manager for the recording number." }],
  notes: [], caveats: [],
};

/** The board's list: each document with boxes for "we hold a copy" and "order a copy", the weak tie marked, and the items to ask about; a print button. */
export const ForTheBoard = () => <BoardList location={located} />;

/** A short list: only the declaration, nothing left to ask. */
export const DeclarationOnly = () => <BoardList location={{ ...located, items: located.items.slice(0, 1), not_located: [] }} />;
