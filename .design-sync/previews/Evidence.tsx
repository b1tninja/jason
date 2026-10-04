import { Evidence, EvidencePanel, type EvidenceAnswer } from "jason-ui";

/** What a board item cites: a recorded instrument, a Drive path, and the command that produced the figure. */
export const BoardItemEvidence = () => (
  <Evidence
    items={[
      "instrument 2023-061501",
      "Drive/Board/2026/09-15 minutes.pdf",
      "jason books-check --month 2026-09",
    ]}
  />
);

/** A duty's outputs with the label changed to Tools. */
export const DutyTools = () => (
  <Evidence label="Tools" items={["jason calendar", "jason inbox --deadlines", "board_digest (MCP)"]} />
);

/** Chips with no label at all, as the definition list in Duties shows them. */
export const Unlabeled = () => (
  <Evidence label="" items={["data/mailroom/sent.jsonl", "data/payhoa/forms.json", "Reserve study 2024 (Drive)"]} />
);

/** One citation only. */
export const SingleRecord = () => <Evidence items={["Civil Code 5855(a) — 10 days' notice"]} />;

/** Many chips wrap inside a narrow column. */
export const WrappedInNarrowColumn = () => (
  <div style={{ maxWidth: 280 }}>
    <Evidence
      label="Records"
      items={[
        "2004-112233 Amended and Restated CC&Rs",
        "2019-083001 Notice of Delinquent Assessment",
        "2021-021001 Release of Lien",
        "Assessor parcel 123-456-789-0000",
        "PayHOA ledger, unit 207",
      ]}
    />
  </div>
);

/** A plan's evidence: a ref with an address is a chip that opens what jason stored; one without stays a plain chip. */
export const OpenableRefs = () => (
  <Evidence
    label="Read from"
    approval="owner-info-tags-0001"
    items={[
      { label: "PayHOA request 1234", address: "payhoa:submission:1234" },
      { label: "Declaration § 7.3", address: "jason://decl/7.3" },
      { label: "Unit 12 ledger" },
    ]}
  />
);

/** The panel opened on a PayHOA request: changed since the plan was read, its fields (one masked), the link, the command
 * that reads it again, and the caveat. Rendered from `data`, so nothing is fetched. */
export const Opened = () => (
  <div style={{ maxWidth: 560 }}>
    <EvidencePanel
      address="payhoa:submission:1234"
      level={4}
      today={new Date("2099-10-03T12:00:00")}
      data={{
        found: true, address: "payhoa:submission:1234", label: "PayHOA request 1234", kind: "payhoa_submission",
        changed: true, changedNote: "The mailing address answer differs from the one the plan read.",
        sources: [{
          name: "PayHOA request export", readAt: "2099-09-30T18:38:00+00:00", digest: "3f9a02c1d4e7aa", text: "", citation: "", caveat: "", note: "",
          fields: [
            { name: "Owner", value: "Jane Doe", masked: false },
            { name: "Mailing address", value: "123 Main St", masked: false },
            { name: "Email", value: "j***@example.com", masked: true },
          ],
        }],
        link: "https://app.payhoa.example/requests/1234",
        refresh: [{ command: "jason sync-catalog --requests", live: true, what: "Reads the requests again", system: "PayHOA" }],
        caveats: ["A stored copy is what jason read then, not the record now."], note: "",
      }}
    />
  </div>
);

/** The panel opened on a citation: the stored words recited, then the citation and its caveat. */
export const OpenedCitation = () => (
  <div style={{ maxWidth: 560 }}>
    <EvidencePanel
      address="jason://decl/7.3"
      data={{
        found: true, address: "jason://decl/7.3", label: "Declaration § 7.3", kind: "citation", changed: false, changedNote: "",
        sources: [{
          name: "Declaration", readAt: "", digest: "", fields: [], note: "",
          text: "No owner shall keep more than two pets in a unit.", citation: "Declaration § 7.3",
          caveat: "jason's consolidated text, not an official restatement. The recorded instrument governs.",
        }],
        link: "", refresh: [{ command: "jason cite jason://decl/7.3", live: false, what: "Recites the stored words" }], caveats: [], note: "",
      }}
    />
  </div>
);

const refreshableAnswer: EvidenceAnswer = {
  found: true, address: "payhoa:submission:1234", label: "PayHOA request 1234", kind: "payhoa_submission",
  changed: false, changedNote: "",
  sources: [{
    name: "PayHOA request export", readAt: "2099-09-30T18:38:00+00:00", digest: "3f9a02c1d4e7aa", text: "", citation: "", caveat: "", note: "",
    fields: [
      { name: "Owner", value: "Jane Doe", masked: false },
      { name: "Mailing address", value: "123 Main St", masked: false },
      { name: "Email", value: "j***@example.com", masked: true },
    ],
  }],
  link: "https://app.payhoa.example/requests/1234",
  refresh: [{ command: "jason sync-catalog --requests", live: true, what: "Reads the requests again", system: "PayHOA" }],
  refreshable: { system: "PayHOA", what: "Reads this request from PayHOA again" },
  caveats: ["A stored copy is what jason read then, not the record now."], note: "",
};

/** A refreshable answer: the read-again icon beside Close. Clicking it reads again through `onRefresh` (no server
 * here): after a second, the answer is replaced in place with the fresh read, changed since the plan was read. */
export const Refreshable = () => (
  <div style={{ maxWidth: 560 }}>
    <EvidencePanel
      address="payhoa:submission:1234"
      approval="owner-info-tags-0001"
      today={new Date("2099-10-03T12:00:00")}
      by="Jane Example"
      onClose={() => {}}
      data={refreshableAnswer}
      onRefresh={() => new Promise<EvidenceAnswer>((done) => setTimeout(() => done({
        ...refreshableAnswer, changed: true, changedNote: "The mailing address answer differs from the one the plan read.",
        sources: [{ ...refreshableAnswer.sources[0], readAt: "2099-10-03T19:02:00+00:00", digest: "9a0c11e2bb4f",
          fields: [{ name: "Owner", value: "Jane Doe", masked: false }, { name: "Mailing address", value: "456 Oak Ave", masked: false }, { name: "Email", value: "j***@example.com", masked: true }] }],
        refreshed: { at: "2099-10-03T19:02:00+00:00", by: "Jane Example", system: "PayHOA" },
      }), 1000))}
    />
  </div>
);

/** The live read in flight, forced by `refreshing`: the icon spins (not under reduced motion), the button is busy, and
 * the status says so. */
export const Refreshing = () => (
  <div style={{ maxWidth: 560 }}>
    <EvidencePanel
      address="payhoa:submission:1234"
      today={new Date("2099-10-03T12:00:00")}
      by="Jane Example"
      onClose={() => {}}
      data={refreshableAnswer}
      onRefresh={() => new Promise<EvidenceAnswer>(() => {})}
      refreshing
    />
  </div>
);

/** A miss: the note and the command that fills it, never an empty box. */
export const OpenedMiss = () => (
  <div style={{ maxWidth: 560 }}>
    <EvidencePanel
      address="payhoa:submission:9999"
      data={{
        found: false, address: "payhoa:submission:9999", label: "PayHOA request 9999", kind: "payhoa_submission", changed: null, changedNote: "",
        sources: [], link: "", caveats: [], note: "No PayHOA request 9999 on disk.",
        refresh: [{ command: "jason sync-catalog --requests", live: true, what: "Reads the requests", system: "PayHOA" }],
      }}
    />
  </div>
);
