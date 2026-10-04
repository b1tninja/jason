import { KeyDocuments, type KeyDocumentsData } from "jason-ui";

/* The `/api/key-documents` payload (`jason.tasks.key_documents.checklist`) for a made-up association. `post` is a
 * no-op stand-in: in the console every write goes through Confirm, in the person's name, to the server. */
const post = async () => ({ ok: true });

const full: KeyDocumentsData = {
  found: true, association: "Example Village HOA", county: "placer",
  counts: { held: 2, linked: 1, located: 2, expected: 1, missing: 1 },
  statuses: [
    { value: "held", meaning: "a copy is held" }, { value: "linked", meaning: "a person linked a copy" },
    { value: "located", meaning: "the recording number is known, no copy yet" }, { value: "expected", meaning: "not located yet" },
    { value: "missing", meaning: "a person marked it missing" },
  ],
  limits: { maxUploadBytes: 25 * 1024 * 1024, suffixes: [".pdf", ".tif", ".jpg", ".png"] },
  groups: [
    { item: "declaration", title: "The declaration (CC&Rs), the recorded copy", why: "CIV 4135", entries: [
      { key: "declaration", item: "declaration", title: "The declaration (CC&Rs), the recorded copy", number: "2001-0000020", recorded: "2001-03-08",
        status: "held", statusWhy: "specification pin",
        copies: [{ kind: "drive", ref: "abc", name: "Restated CC&Rs.pdf", source: "specification pin", url: "https://drive.google.com/open?id=abc" }],
        links: [], leads: [{ number: "2001-0000020", filing: "AMENDED RESTRICTION", tie: "names the association" }], notes: [] },
      { key: "declaration/2001-0000010", item: "declaration", title: "Declaration (rescinded)", number: "2001-0000010", recorded: "2001-03-01",
        status: "located", supersededBy: "2001-0000020", copies: [], links: [], leads: [], notes: ["Rescinded by recital F of the restatement."] },
    ] },
    { item: "amendments", title: "Each amendment to the declaration", why: "CIV 4270", repeats: true, entries: [
      { key: "amendments/2010-0000100", item: "amendments", title: "First Amendment", number: "2010-0000100", recorded: "2010-02-01", status: "linked",
        sections: ["4.2", "7.1"], copies: [],
        links: [{ id: "l-1", kind: "upload", ref: "key-documents/example/files/a/First Amendment.pdf", name: "First Amendment.pdf", by: "Jane Example",
          at: "2026-10-02T17:40:00+00:00", url: "/api/file?path=x" }],
        leads: [], notes: [] },
      { key: "amendments/2016-0045501", item: "amendments", title: "Second Amendment", number: "2016-0045501", recorded: "2016-07-22", status: "located",
        copies: [], links: [], leads: [{ number: "2016-0045501", filing: "AMENDMENT", tie: "names the association", source: "the locator" }], notes: [] },
    ] },
    { item: "annexations", title: "Annexations", repeats: true, entries: [
      { key: "annexations/2003-0000050", item: "annexations", title: "Annexation of Phase 2", number: "2003-0000050", recorded: "2003-06-01", phase: 2,
        status: "held", copies: [{ kind: "disk", ref: "recorded/2003-0000050.pdf", name: "2003-0000050.pdf", source: "recorded copy on disk" }],
        links: [], leads: [], notes: [] },
    ] },
    { item: "articles", title: "Articles of incorporation", why: "CIV 4080", entries: [
      { key: "articles", item: "articles", title: "Articles of incorporation", number: "", recorded: "", status: "missing",
        statusWhy: "the prior manager has no copy", copies: [], links: [], leads: [], notes: [] },
    ] },
    { item: "maps", title: "Subdivision and parcel maps", entries: [
      { key: "maps", item: "maps", title: "Subdivision and parcel maps", number: "", recorded: "", status: "expected", copies: [], links: [], leads: [], notes: [] },
    ] },
  ],
  caveats: ["A located recording number is a lead, not a pin.", "Unlinking marks the link removed; the file stays."],
};

const start: KeyDocumentsData = {
  ...full,
  counts: { expected: 3 },
  groups: full.groups.filter((g) => ["declaration", "articles", "maps"].includes(g.item)).map((g) => ({
    ...g, entries: [{ ...g.entries[0], number: "", recorded: "", status: "expected" as const, statusWhy: undefined, copies: [], links: [], leads: [], notes: [] }],
  })),
};

const mid: KeyDocumentsData = { ...full, counts: { held: 2, linked: 1, located: 2, missing: 1 }, groups: full.groups.filter((g) => g.item !== "maps") };

/** Mid-onboarding: the status words (held, linked, located, missing) with its copies, the person's link, the locator's leads, and a rescinded declaration. */
export const Checklist = () => <KeyDocuments data={mid} by="Jane Example" post={post} />;

const later: KeyDocumentsData = { ...full, counts: { linked: 1, located: 1, missing: 1 }, groups: full.groups.filter((g) => ["amendments", "articles"].includes(g.item)) };

/** No name yet: the list asks who is writing before any link, upload, or status change (the amendments and articles). */
export const NoName = () => <KeyDocuments data={later} post={post} />;

/** The first day: nothing located, every entry expected. */
export const FirstDay = () => <KeyDocuments data={start} by="Jane Example" post={post} />;

/** The checklist is unavailable: the loader's note. */
export const Unavailable = () => (
  <KeyDocuments data={{ found: false, note: "No association chosen: pick one under Find the association first.", groups: [] }} post={post} />
);
