import { LawBlock } from "jason-ui";

// Made-up sample text for a made-up "EX" code. Nothing here is a real statute or its wording.
const base = {
  citation: "EX 123.4", section: "EX 123.4(a)", digest: "d0c5a1", source: "authorities shelf: sample", note: "version in force on 2099-10-09",
  caveats: [] as string[], versions: [] as { digest: string; words: string; label: string }[], undecided: false, missing: "",
  readingLabel: "jason's reading, not the provision", restatement: "jason's consolidated text is not an official restatement.",
  words: "The association shall send a second notice to each member not later than 30 days before the answer-by date. (Sample text, not a statute.)",
};

/** The law's operative words first, with the citation and the version in force; no reading of jason's own. */
export const Recited = () => <LawBlock cite="EX 123.4" law={base} />;

/** The recited words, then jason's reading, labeled as a reading and not the provision. */
export const WithReading = () => (
  <LawBlock cite="EX 123.4" law={{ ...base, reading: "Resend the notice at least 30 days before answers are due.", caveats: ["Sample caveat: the shelf copy omits subdivision (b)."] }} />
);

/** Two versions of the provision are on the shelf and which governs is not decided: both recited, then the board is told to ask counsel. */
export const TwoVersions = () => (
  <LawBlock cite="EX 123.4" law={{
    ...base, undecided: true,
    versions: [
      { digest: "a1", label: "version in force 2098-01-01 to 2099-06-30", words: "A second notice shall be sent not later than 30 days before the answer-by date. (Sample text, not a statute.)" },
      { digest: "b2", label: "version in force from 2099-07-01", words: "A second notice shall be sent not later than 45 days before the answer-by date. (Sample text, not a statute.)" },
    ],
  }} />
);

/** The shelf lacks the section: nothing is recited, and the block says why. */
export const NotOnShelf = () => (
  <LawBlock cite="EX 999.9" law={{ ...base, citation: "EX 999.9", section: "", words: "", missing: "The authorities shelf holds no words for EX 999.9 (sample)" }} />
);
