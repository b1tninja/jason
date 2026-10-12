import { ControlQuestionRow } from "jason-ui";

// A made-up question for Oakview: a provision that reads two ways. The words are plainly fake sample text.
const QUESTION: any = {
  key: "reserve-signers", type: "payment-signers", title: "Payment signers", family: "money", familyTitle: "Money", kind: "question",
  document: "Example Bylaws", number: "99.9(c)", citation: "Example Bylaws, 99.9(c)",
  words: "Sample bylaw text, not a statute: the reserve may be drawn on the signature of the officer named by the board or, if none, the president.",
  question: true, whyQuestion: "it reads two ways about who may sign for the reserve. A question for the board or counsel.",
};

const List = ({ children }: { children: React.ReactNode }) => <ul className="control-list" style={{ maxWidth: 760 }}>{children}</ul>;

/** A provision jason cannot read cleanly: the dashed warning-bordered row, the badge, the loader's reason, and the words recited whole. */
export const ReadsTwoWays = () => <List><ControlQuestionRow q={QUESTION} /></List>;

/** Two questions in the list, the second with no stored words and the loader's default reason: nothing to propose in either. */
export const TwoQuestions = () => (
  <List>
    <ControlQuestionRow q={QUESTION} />
    <ControlQuestionRow q={{ ...QUESTION, key: "notice-method", citation: "Example Bylaws, 12.4", title: "Notice method", words: "", whyQuestion: "" }} />
  </List>
);
