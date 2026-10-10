import { useState } from "react";
import { Badge } from "./Badge";
import { Command } from "./Command";
import { Glyph } from "./Glyph";
import { Pill } from "./Pill";
import { DECODER_MISSING, NOT_OPENED, NO_ZOOM_RECORD, PASSCODE_IN_LINK, codeHost, codeKind, plural, type DocumentCode } from "../lib/inspections";

/** One code. A code is where paper points, not a fact about the paper. The first line is the host, then the full link, and
 * has no control on it. Opening is a second step: "Review before opening" shows the host again and says jason has not
 * opened it, and only its own button opens. A masked payload is shown as the server gave it ("***"): the component never
 * has the secret, so there is nothing to unmask. A payload that is not a link is plain text.
 * Without `onOpenLink`, the second step's button is a plain link to the payload (never for a masked one). */
export function CodeRow({ code, onOpenLink, onOpenPortal }: { code: DocumentCode; onOpenLink?: (code: DocumentCode) => void; onOpenPortal?: (portal: NonNullable<DocumentCode["portal"]>) => void }) {
  const [review, setReview] = useState(false);
  const kind = codeKind(code);
  const host = codeHost(code);
  const canOpen = code.link && !!host && (!!onOpenLink || !code.masked);
  return (
    <li className="insp-code" data-kind={kind} data-masked={code.masked ? "true" : undefined}>
      <div className="insp-code-first row wrap">
        <Glyph name={kind === "meeting" ? "video" : kind === "text" ? "qr-code" : "link"} size="1em" />
        {kind === "text"
          ? <><span className="muted">Plain text, not a link:</span> <code className="insp-code-text">{code.text}</code></>
          : <><strong className="insp-host">{host || "(no host)"}</strong><code className="insp-code-text">{code.text}</code></>}
        <Badge>{`${code.format} · page ${code.page}`}</Badge>
        {code.masked && <Pill word="masked" meaning="The server hid a secret in this payload; this page never receives it." glyph="eye-off" />}
      </div>
      {code.masked && <p className="muted">{PASSCODE_IN_LINK}</p>}
      {code.portal && <p>A vendor's report portal ({code.portal.platform}) at {code.portal.host}.</p>}
      {code.meeting && (
        <p>
          A video meeting ({code.meeting.platform}), meeting number <strong className="num">{code.meeting.id}</strong>.{" "}
          {code.meeting.recorded
            ? <Pill word="recorded" meaning="The Zoom index holds a record of this meeting." glyph="circle-check" />
            : <><Pill word="lead" meaning="A meeting with no entry in the index is a lead to look into, not a finding." glyph="circle-dashed" /> {NO_ZOOM_RECORD}</>}
        </p>
      )}
      {(canOpen || (code.portal && onOpenPortal)) && (
        <div className="insp-code-actions row wrap">
          {code.portal && onOpenPortal && <button onClick={() => onOpenPortal(code.portal!)}>Open the portal's reports</button>}
          {canOpen && !review && <button aria-expanded={false} onClick={() => setReview(true)}>Review before opening</button>}
        </div>
      )}
      {canOpen && review && (
        <div className="insp-open-step notice" role="group" aria-label={`Open ${host}`}>
          <p>This opens <strong>{host}</strong>, outside jason. {NOT_OPENED}</p>
          <div className="row wrap">
            {onOpenLink
              ? <button className="primary" onClick={() => { setReview(false); onOpenLink(code); }}>Open {host}</button>
              : <a className="insp-open-link" href={code.text} target="_blank" rel="noopener noreferrer" onClick={() => setReview(false)}>Open {host}</a>}
            <button onClick={() => setReview(false)}>Cancel</button>
          </div>
        </div>
      )}
    </li>
  );
}

/** A document's codes (the QR codes read off its pages). None read, one, or several; the decoder not installed is a
 * stop that says so and shows the command, never "no codes". `onOpenLink` and `onOpenPortal` are a person's acts. */
export function DocumentCodes({ codes, decoderMissing = false, installCommand, onOpenLink, onOpenPortal }: {
  codes: readonly DocumentCode[];
  decoderMissing?: boolean;
  installCommand?: string;
  onOpenLink?: (code: DocumentCode) => void;
  onOpenPortal?: (portal: NonNullable<DocumentCode["portal"]>) => void;
}) {
  if (decoderMissing)
    return (
      <section className="insp-codes" aria-label="Codes">
        <p className="notice notice-warn" role="status">{DECODER_MISSING}</p>
        {installCommand && <Command cmd={installCommand} />}
      </section>
    );
  return (
    <section className="insp-codes" aria-label="Codes">
      <h3>Codes ({codes.length})</h3>
      <p className="muted">A code is where the paper points. It is not a fact about the paper, and jason has not opened any link.</p>
      {codes.length === 0
        ? <p className="muted">No code was read on the pages jason looked at.</p>
        : <ul className="insp-code-list" aria-label={plural(codes.length, "code")}>{codes.map((c, i) => <CodeRow key={`${c.page}-${i}`} code={c} onOpenLink={onOpenLink} onOpenPortal={onOpenPortal} />)}</ul>}
    </section>
  );
}
