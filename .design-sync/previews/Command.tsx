import { Command } from "jason-ui";

/** The exact command a person runs in a terminal; the page shows and copies it, never runs it. */
export const EnterRequest = () => (
  <Command cmd="jason request-links --create 18f2a4c9e1b7 --yes" note="Enters the request in PayHOA; it is never approved, denied, or assigned." />
);

export const FillLetter = () => (
  <Command cmd="jason letter --template hearing-notice --name 'Hearing, unit 12' --set 'OWNER_NAME=J. Doe' --set 'HEARING_DATE=2026-10-20' --yes" note="Copies the template in Drive and fills it; sends nothing." />
);

export const DefaultNote = () => <Command cmd="jason board --packet --doc --yes" />;
