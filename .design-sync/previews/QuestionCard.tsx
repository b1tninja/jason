import { QuestionCard, type Question } from "jason-ui";

const declaration: Question = {
  id: "fact-declaration-in-force", kind: "fact", subject: "declaration", question: "Which version of the declaration is in force?",
  choices: ["The 2019 restated declaration, as amended in 2022", "The 2019 restated declaration alone"],
  suggestion: "The 2019 restated declaration, as amended in 2022", likely: true, highStakes: true,
  evidence: ["Restated declaration, 2019 (recorded)", "First amendment, 2022 (recorded)"], priority: 1240,
  unblocks: { clocks: ["notice:board-meeting", "notice:annual-budget"], gates: ["establish"], items: [{ key: "declaration", status: "partial" }] },
};
const folder: Question = {
  id: "map-folder-insurance", kind: "map", question: "Which record does the Drive folder \"Insurance 2025\" fill?",
  choices: ["Insurance policies (CIV 5200)", "Contracts", "Not an association record"], suggestion: "Insurance policies (CIV 5200)",
  evidence: ["Drive folder Insurance 2025: 6 files"], unblocks: { records: ["record insurance"], items: [{ key: "insurance", status: "missing" }] },
};

/** Rank 1, high stakes: what it unblocks, jason's suggestion labeled and not chosen, and the answer form. */
export const HighStakes = () => <QuestionCard question={declaration} rank={1} me="Jane Example" onAnswer={() => {}} />;

/** A lower-ranked mapping question. */
export const MapQuestion = () => <QuestionCard question={folder} rank={4} me="Jane Example" onAnswer={() => {}} />;

/** Answered, waiting on a second person's confirmation. */
export const Answered = () => <QuestionCard question={declaration} rank={1} answered={{ answer: "The 2019 restated declaration, as amended in 2022", answeredBy: "Jane Example", answeredAt: "2026-10-03T09:10:00Z" }} />;

/** The compact form for Today: the rank, the question, and what it unblocks. */
export const Compact = () => <QuestionCard question={declaration} rank={1} compact />;
