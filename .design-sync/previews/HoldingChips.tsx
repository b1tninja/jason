import { HoldingChips } from "jason-ui";

/** One chip per place the same content lives. */
export const Places = () => <HoldingChips holdings={[
  { place: "library", where: "Email Attachments/Fire Alarm 2029-09-19.pdf", identical: true },
  { place: "drive", where: "My Drive/Reports/Fire Protection/Fire Alarm", identical: true },
  { place: "payhoa", where: "Documents/Reports", identical: true },
  { place: "email", where: "attachment of 2029-09-20", identical: true },
  { place: "portal", where: "viewReport?id=r2", identical: true },
]} />;

/** A copy that is not byte-identical is marked "a different copy". */
export const DifferentCopy = () => <HoldingChips holdings={[
  { place: "library", where: "Email Attachments/Fire Alarm 2029-09-19.pdf", identical: true },
  { place: "drive", where: "My Drive/Reports/Fire Protection/Fire Alarm", identical: false },
]} />;

/** None: said in words, as a lead. */
export const None = () => <HoldingChips holdings={[]} />;
