import { Card, RequestForm, type RequestKind } from "jason-ui";

/** The record kinds a member may ask for, as `/api/records-requests` lists them. */
const kinds: RequestKind[] = [
  { record: "minutes", label: "Minutes of member, board, and committee meetings", citation: "CIV 5200(a)(8)", meaning: "Approved minutes and drafts of open meetings." },
  { record: "financials", label: "Financial statements and budgets", citation: "CIV 5200(a)(1)-(3)", meaning: "The annual budget report, review, and statements." },
  { record: "check_register", label: "Check register and general ledger", citation: "CIV 5200(a)(4)" },
  { record: "contracts", label: "Executed contracts", citation: "CIV 5200(a)(5)" },
  { record: "reserve_study", label: "Reserve study", citation: "CIV 5200(a)(7)" },
  { record: "membership_list", label: "Membership list", citation: "CIV 5200(a)(9)", meaning: "Names, addresses, and voting rights; a purpose is required (CIV 5225)." },
];

/** The owner's form, nothing picked yet: Send stays disabled and the line says what to do first. */
export const Fresh = () => <RequestForm kinds={kinds} today="2026-10-03" email="records@sample-commons.example" />;

/** A short list of kinds, inside a card as the owner view frames it. */
export const Short = () => (
  <Card title="Ask for association records">
    <RequestForm kinds={kinds.slice(0, 2)} today="2026-10-03" />
  </Card>
);

/** No kinds given: the fieldset is empty, the form still asks for a unit. */
export const NoKinds = () => <RequestForm kinds={[]} today="2026-10-03" />;
