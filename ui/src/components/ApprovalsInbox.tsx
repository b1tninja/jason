import { useState } from "react";
import { Badge } from "./Badge";
import { Command } from "./Command";
import { Confirm } from "./Confirm";
import { Stat } from "./Stat";
import { BOARD, canApprove, type Person } from "../lib/session";
import type { Letter, StageAction, StageBody } from "./DraftLetter";

export interface InboxGroup {
  id: "mine" | "others" | "board" | "requested" | "approved" | "sent";
  /** The letters' stage: "mine", "others", and "board" all split the letters awaiting approval. */
  stage: "requested" | "approved" | "sent";
  label: string; items: Letter[]; emptyText: string;
}

/** The letters by whose turn it is. With `me` set, the letters awaiting approval split in three: those with a personal
 * approver that `me` may approve ("Waiting on you", first), those with a personal approver someone else is ("Waiting on
 * others"), and those whose approver is the board ("Waiting on the board's vote"). The board's approval is no one's
 * turn: it is a vote at a meeting (CIV 4910) on an item on the posted agenda (CIV 4930), which the president or the
 * secretary records afterwards. With no `me`, they stay one "Awaiting approval" group. */
export function groupLetters(letters: readonly Letter[], me = "", people: readonly Person[] = []): InboxGroup[] {
  const by = (stage: Letter["stage"]) => letters.filter((l) => l.stage === stage);
  const requested = by("requested");
  const board = (l: Letter) => (l.approver || BOARD) === BOARD;
  const personal = requested.filter((l) => !board(l));
  const awaiting: InboxGroup[] = me
    ? [
        { id: "mine", stage: "requested", label: "Waiting on you", items: personal.filter((l) => canApprove(me, l.approver, people)), emptyText: "Nothing is waiting on you." },
        { id: "others", stage: "requested", label: "Waiting on others", items: personal.filter((l) => !canApprove(me, l.approver, people)), emptyText: "Nothing is waiting on anyone else." },
        { id: "board", stage: "requested", label: "Waiting on the board's vote", items: requested.filter(board), emptyText: "Nothing is waiting on a board vote." },
      ]
    : [{ id: "requested", stage: "requested", label: "Awaiting approval", items: requested, emptyText: "Nothing is waiting on an approver." }];
  return [
    ...awaiting,
    { id: "approved", stage: "approved", label: "Approved, not sent", items: by("approved"), emptyText: "Nothing approved is waiting to go out." },
    { id: "sent", stage: "sent", label: "Sent", items: by("sent"), emptyText: "Nothing sent yet." },
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

/** Every drafted letter waiting on a person, keyed by its path so the inbox and the document always agree. With someone
 * signed in, the letters that person may approve come first ("Waiting on you"), then those waiting on others, then those
 * waiting on the board's vote, which the president or the secretary records once the board has voted. Approve
 * (or, for the board, Record board approval with the meeting's date) and Send back show only for the matching signed-in
 * person; an approved letter shows the terminal command a person runs; a sent one shows nothing to do. */
export function ApprovalsInbox({ letters, me, people, onAction, busy, go, onOpen, today }: {
  letters: readonly Letter[]; me: string; people: readonly Person[];
  onAction: (key: string, action: StageAction, body: StageBody) => Promise<void> | void;
  busy?: boolean; go?: (screen: string) => void; onOpen?: (key: string) => void;
  /** The day "this month" is read against (ISO date); defaults to now. Previews and tests pass it so the stat is stable. */
  today?: string;
}) {
  const groups = groupLetters(letters, me, people);
  const of = (id: InboxGroup["id"]) => groups.find((g) => g.id === id)?.items ?? [];
  const awaiting = groups.filter((g) => g.stage === "requested").reduce((n, g) => n + g.items.length, 0);
  const sent = of("sent");
  const month = (today || new Date().toISOString()).slice(0, 7);
  const sentThisMonth = sent.filter((l) => (l.sentOn || lastEvent(l)).startsWith(month)).length;
  return (
    <div className="approvals-inbox">
      <div className="stats">
        {me
          ? <Stat label="Waiting on you" value={of("mine").length} hint={`${awaiting} awaiting approval in all`} />
          : <Stat label="Awaiting approval" value={awaiting} />}
        <Stat label="Approved, not sent" value={of("approved").length} />
        <Stat label="Sent this month" value={sentThisMonth} hint={`${sent.length} sent in all`} />
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
                  {g.stage === "requested" && (
                    <>
                      {g.id === "board" && <span className="muted">A vote at a meeting (CIV 4910); the president or the secretary records it with the meeting's date.</span>}
                      {g.id === "board" ? (
                        can && <BoardApprove title={l.title} me={me} busy={busy} onConfirm={(meeting) => onAction(l.key, "approve", { by: me, meeting })} />
                      ) : can ? (
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
                  {g.stage === "approved" && (l.sentCommand ? <Command cmd={l.sentCommand} note="A person runs it in a terminal, then records the send on the document." /> : <span className="muted">Approved; no send command on file.</span>)}
                  {g.stage === "sent" && <span className="muted">Logged: {l.sentRef || "unrecorded"}</span>}
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
