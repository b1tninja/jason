import { useState } from "react";
import { isDocRef, type EvidenceEntry } from "../lib/docref";
import { Doc, type DocStatic } from "./Doc";

/* An older store's evidence as the loader maps it (`jason.approvals.docref.refs_from_strings`; docs/console/
 * doc-component.md): each entry a document reference, a command, or text. A reference is a `Doc` chip that opens the
 * document as one logged view; a command is shown as code to copy, never run; text stays as written. Nothing is
 * guessed here: the server decided which strings name a document. */

/** A command to copy, in a chip row: the page shows it and never runs it. */
function CommandChip({ cmd }: { cmd: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(cmd);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* no clipboard: the text is selectable */
    }
  };
  return (
    <span className="evidence-command">
      <code className="chip">{cmd}</code>
      <button type="button" className="link" aria-label={`Copy the command ${cmd}`} title="Run it in a terminal. The page never runs a command." onClick={() => void copy()}>
        {copied ? "Copied" : "Copy"}
      </button>
      <span className="visually-hidden" role="status">{copied ? "Copied the command." : ""}</span>
    </span>
  );
}

/** The entries in order, after `label` (none when empty). The `DocStatic` props pass to each chip (previews, tests). */
export function EvidenceEntries({ entries, label = "Evidence", ...rest }: DocStatic & {
  entries?: readonly EvidenceEntry[] | null; label?: string;
}) {
  if (!entries?.length) return null;
  return (
    <div className="evidence">
      {label && <span className="muted">{label}: </span>}
      {entries.map((e, i) =>
        isDocRef(e) ? <Doc key={i} doc={e} variant="chip" {...rest} />
          : "command" in e ? <CommandChip key={i} cmd={e.command} />
          : <span key={i} className="chip">{e.text}</span>,
      )}
    </div>
  );
}
