import { useState } from "react";
import { Badge } from "./Badge";
import { Command } from "./Command";
import { Confirm } from "./Confirm";
import { Stat } from "./Stat";
import { BOARD, canApprove, type Person } from "../lib/session";
import type { Letter, StageAction, StageBody } from "./DraftLetter";

export interface InboxGroup { id: "requested" | "approved" | "sent"; label: string; items: Letter[]; emptyText: string }

export function groupLetters(letters: readonly Letter[]): InboxGroup[] {
  const by = (stage: Letter["stage"]) => letters.filter((l) => l.stage === stage);
  return [
    { id: "requested", label: "Awaiting approval", items: by("requested"), emptyText: "Nothing is waiting on an approver." },
    { id: "approved", label: "Approved, not sent", items: by("approved"), emptyText: "Nothing approved is waiting to go out." },
    { id: "sent", label: "Sent", items: by("sent"), emptyText: "Nothing sent yet." },
  ];
}

function lastEvent(l: Letter): string {
  const e = l.log?.length ? l.log[l.log.length - 1] : null;
  return e ? `${e.date} · ${e.title}` : "";
}

/** The board's approval, recorded by the president or secretary with the date of the meeting at which it voted. */
function BoardApprove({ title, me, busy, onConfirm }: { title: string; me: string; busy?: boolean; onConfirm: (meeting: string) => void }) {
  const [meeting, setMeeting] = useState("");
  return (
    <Confirm busy={busy} onConfirm={() => onConfirm(meeting)} summary={
      <div className="stack-sm">
        <p>Record that the board approved "{title}" by a vote at a meeting (CIV 4910); recorded by {me}. The vote goes in the minutes.</p>
        <label className="draft-letter-field">Meeting date<input type="date" value={meeting} onChange={(e) => setMeeting(e.target.value)} aria-label="Meeting date" /></label>
      </div>
    }>Record board approval</Confirm>
  );
}

/** Every drafted letter waiting on a person, keyed by its path so the inbox and the document always agree. Approve
 * (or, for the board, Record board approval with the meeting's date) and Send back show only for the matching signed-in
 * person; an approved letter shows the terminal command a person runs; a sent one shows nothing to do. */
export function ApprovalsInbox({ letters, me, people, onAction, busy, go, onOpen }: {
  letters: readonly Letter[]; me: string; people: readonly Person[];
  onAction: (key: string, action: StageAction, body: StageBody) => Promise<void> | void;
  busy?: boolean; go?: (screen: string) => void; onOpen?: (key: string) => void;
}) {
  const groups = groupLetters(letters);
  const month = new Date().toISOString().slice(0, 7);
  const sentThisMonth = groups[2].items.filter((l) => (l.sentOn || lastEvent(l)).startsWith(month)).length;
  return (
    <div className="approvals-inbox">
      <div className="stats">
        <Stat label="Awaiting approval" value={groups[0].items.length} />
        <Stat label="Approved, not sent" value={groups[1].items.length} />
        <Stat label="Sent this month" value={sentThisMonth} hint={`${groups[2].items.length} sent in all`} />
      </div>
      {groups.map((g) => (
        <section key={g.id} className="approvals-group" aria-label={g.label}>
          <h2>{g.label}</h2>
          {g.items.length === 0 && <p className="muted">{g.emptyText}</p>}
          {g.items.map((l) => {
            const approver = l.approver || BOARD;
            const board = approver === BOARD;
            const can = canApprove(me, approver, people);
            return (
              <article key={l.key} className="approvals-row">
                <div className="approvals-row-head">
                  <div className="row wrap">
                    <Badge>{l.kind || "Document"}</Badge>
                    <button className="link approvals-title" onClick={() => onOpen?.(l.key)}>{l.title}</button>
                  </div>
                  <span className="muted num">{lastEvent(l)}</span>
                </div>
                <p className="muted">To {l.to} · {l.via} · approver: {approver}</p>
                <div className="row wrap">
                  {g.id === "requested" && (
                    <>
                      {can ? (
                        board ? (
                          <BoardApprove title={l.title} me={me} busy={busy} onConfirm={(meeting) => onAction(l.key, "approve", { by: me, meeting })} />
                        ) : (
                          <Confirm busy={busy} onConfirm={() => onAction(l.key, "approve", { by: me })} summary={<>Approve "{l.title}" as {me}, for {approver}. It can then be sent to {l.to} by a person.</>}>Approve</Confirm>
                        )
                      ) : (
                        <span className="muted">{board ? "Needs a board vote at a meeting (CIV 4910)" : `Only ${approver} can approve`}</span>
                      )}
                      {can && (
                        <Confirm busy={busy} onConfirm={() => onAction(l.key, "send_back", { by: me })} summary={<>Send "{l.title}" back to the drafter. It returns to a saved draft.</>}>Send back</Confirm>
                      )}
                    </>
                  )}
                  {g.id === "approved" && (l.sentCommand ? <Command cmd={l.sentCommand} note="A person runs it in a terminal, then records the send on the document." /> : <span className="muted">Approved; no send command on file.</span>)}
                  {g.id === "sent" && <span className="muted">Logged: {l.sentRef || "unrecorded"}</span>}
                  {onOpen && <button className="link" onClick={() => onOpen(l.key)}>Open the document</button>}
                  {go && <button className="link" onClick={() => go(l.key)}>Open its screen</button>}
                </div>
              </article>
            );
          })}
        </section>
      ))}
    </div>
  );
}
