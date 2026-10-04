import { LocatedDocuments } from "jason-ui";

/* The `/api/documents-located` payload (`jason.tasks.document_locator`) for a made-up association. Owners on an
 * instrument (P1) are made up too. */
const located = {
  association: "Example Village HOA", county: "placer", located_at: "2026-10-02T15:04:00", searches: 42, liens: 386,
  spellings: ["EXAMPLE VILLAGE HOMEOWNERS ASSOCIATION", "EXAMPLE VILLAGE HOA"],
  items: [
    { item: "declaration", title: "The declaration (CC&Rs), the recorded copy", question: "Which is the association's declaration (the CC&Rs later amendments amend)?", stakes: true,
      located: [
        { number: "2001-0000020", recorded: "2001-03-08", filing: "AMENDED RESTRICTION", tie: "NAMED", tie_label: "names the association", strong: true, via: "",
          parties: ["EXAMPLE HOMES INC", "EXAMPLE VILLAGE HOA"] },
      ] },
    { item: "annexations", title: "Annexations", question: "Which of these annex a phase into the association (or take one out)?", stakes: false,
      located: [
        { number: "2003-0000050", recorded: "2003-06-01", filing: "DECLARATION OF ANNEXATION", tie: "BESIDE", tie_label: "recorded with the association's documents", strong: true,
          via: "2003-0000049", parties: ["EXAMPLE HOMES INC"] },
        { number: "2007-0030003", recorded: "2007-01-15", filing: "DECLARATION OF ANNEXATION", tie: "DECLARANT", tie_label: "the builder's filing", strong: false,
          via: "EXAMPLE HOMES INC", parties: ["EXAMPLE HOMES INC"] },
      ] },
    { item: "deeds", title: "Common-area deeds", question: "Which deeds conveyed the common area to the association?", stakes: false,
      located: [
        { number: "2002-0004410", recorded: "2002-05-14", filing: "GRANT DEED", tie: "NAMED", tie_label: "names the association", strong: true, via: "",
          parties: ["EXAMPLE HOMES INC", "EXAMPLE VILLAGE HOA"], people: [{ name: "SAMPLE PAT Q", side: "E" }] },
      ] },
  ],
  not_located: [
    { item: "maps", title: "The subdivision maps", ask: "None in the index under the association's names; ask the board or the prior manager for the recording number." },
    { item: "articles", title: "Articles of incorporation", ask: "Filed with the Secretary of State, not the county: ask for the filed copy." },
  ],
  notes: ["The index before 1997 is not searchable by name."],
  caveats: ["A located document is a lead, not a pin: the recorded copy is read before it is pinned.", "Owners on an instrument are shown to the people who work with them, never committed."],
};

/** A finished locate: each checklist item's question, its documents with their ties in words, the second-person mark on the declaration, what was not located with its ask, and the caveats. */
export const Located = () => <LocatedDocuments location={located} questionHref={(item) => `#question-${item}`} />;

/** With the page's actions slot filled (the locate-again button the console puts there) and no question route. */
export const WithActions = () => (
  <LocatedDocuments location={{ ...located, items: located.items.slice(1, 2), not_located: [] }} actions={<div className="row"><button type="button">Locate documents again</button></div>} />
);

/** Nothing tied to the association yet: every item asked of the board. */
export const NoneLocated = () => (
  <LocatedDocuments location={{ ...located, searches: 18, liens: 0, items: [], notes: [],
    not_located: [
      { item: "declaration", title: "The declaration (CC&Rs), the recorded copy", ask: "No declaration names the association; ask the board for the recorded copy's number." },
      ...located.not_located,
    ] }} />
);
