import { DocumentCodes, CodeRow, inspectionFixtures as fx } from "jason-ui";

/** One code, a link: the host first, the full link second, no button on the first line; opening is a second step. */
export const OneLink = () => <DocumentCodes codes={[fx.codeLink]} onOpenLink={() => {}} />;

/** Several codes: a vendor portal, a recorded meeting, a meeting with no record (a lead), and plain text. */
export const Several = () => <DocumentCodes codes={[fx.codePortal, fx.codeMeetingRecorded, fx.codeMeetingUnrecorded, fx.codeText]} onOpenLink={() => {}} onOpenPortal={() => {}} />;

/** A payload with a secret: shown masked as the server gave it, with "a passcode is in the link". */
export const Masked = () => <DocumentCodes codes={[fx.codeMasked]} />;

/** No code was read on the pages looked at. */
export const NoneRead = () => <DocumentCodes codes={[]} />;

/** The decoder is not installed: a stop with the command, never "no codes". */
export const DecoderMissing = () => <DocumentCodes codes={[]} decoderMissing installCommand={fx.installCommand} />;

/** A single row on its own. */
export const Row = () => <ul style={{ listStyle: "none", padding: 0 }}><CodeRow code={fx.codeLink} onOpenLink={() => {}} /></ul>;
