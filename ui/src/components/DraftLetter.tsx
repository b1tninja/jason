import { useEffect, useState } from "react";
import { Badge, type Tone } from "./Badge";
import { Command } from "./Command";
import { Confirm } from "./Confirm";
import { Timeline, type TimelineEvent } from "./Timeline";
import { BOARD, canApprove as mayApprove, type Person } from "../lib/session";

export type Stage = "draft" | "saved" | "requested" | "approved" | "sent";
export type StageAction = "save" | "request" | "withdraw" | "send_back" | "approve" | "record_sent";

export interface LetterLog { id: string; date: string; title: string; tone?: Tone; by?: string }

/** A letter jason drafted, as the approvals store keeps it, keyed by its path. */
export interface Letter {
  key: string; kind: string; title: string; date: string; to: string; via: string; body: string[]; signoff: string;
  approver: string; stage: Stage; log: LetterLog[]; created?: string; updated?: string;
  sentCommand?: string; sentRef?: string; sentOn?: string; meeting?: string; ownerBadge?: string;
  /** Where replies go: the association's designated recipient and address for official communications (CIV 4035),
   * from the profile through the server. Empty: the approval line says it is not on file yet. */
  replyTo?: string;
}

export const REPLIES = "Replies: to the association's designated recipient for official communications (Civil Code 4035)";
export const REPLIES_MISSING = "— not on file yet (onboarding: official-address)";

const APPROVAL = /^(approved\b|the board approved)/i;
const MEETING = /meeting of (\d{4}-\d{2}-\d{2})/i;

/** The letter's approval line, one clause each: who drafted it, who approved it, that jason is automated and the
 * officers sign, and where replies go. Read from the trail and the letter, never inferred. It is the console's record
 * of the letter, not text in the mailed letter: `letterText` leaves it out. */
export function approvalLine(l: Letter): string[] {
  const log = l.log ?? [];
  const approver = l.approver || BOARD;
  const saved = log.find((e) => /^draft saved/i.test(e.title));
  const drafted = saved
    ? `Drafted by jason${saved.by ? ` for ${saved.by}` : ""}${saved.date ? `, ${saved.date}` : ""}`
    : "jason drafts; not yet saved";
  const done = l.stage === "approved" || l.stage === "sent";
  const entry = done ? [...log].reverse().find((e) => APPROVAL.test(e.title)) : undefined;
  let approved = `Not yet approved (approver: ${approver})`;
  if (done && approver === BOARD) {
    const day = l.meeting || entry?.title.match(MEETING)?.[1] || "";
    approved = `Approved by the board${day ? ` at its meeting of ${day}` : " at a meeting"}${entry?.by ? `, recorded by ${entry.by}` : ""}`;
  } else if (done) {
    approved = `Approved${entry?.by ? ` by ${entry.by} as ${approver}` : ` by ${approver}`}${entry?.date ? `, ${entry.date}` : ""}`;
  }
  const reply = l.replyTo?.trim();
  return [drafted, approved, "jason is automated; the officers sign, jason never does.", reply ? `${REPLIES}: ${reply}` : REPLIES];
}

function ApprovalLine({ letter }: { letter: Letter }) {
  return (
    <p className="draft-letter-approval">
      {approvalLine(letter).join(" · ")}
      {!letter.replyTo?.trim() && <> <em className="muted">{REPLIES_MISSING}</em></>}
    </p>
  );
}

export interface StageBody { by: string; note?: string; meeting?: string; sentRef?: string }

export const STAGE_BADGE: Record<Stage, [string, Tone]> = {
  draft: ["draft", "warn"], saved: ["draft", "warn"], requested: ["awaiting approval", "warn"], approved: ["approved", "good"], sent: ["sent", "good"],
};

export function letterText(l: Letter): string {
  return [l.title, `Date: ${l.date}`, `To: ${l.to}`, `Delivery: ${l.via}`, "", ...l.body, "", l.signoff].join("\n");
}

function CopyText({ letter }: { letter: Letter }) {
  const [copied, setCopied] = useState(false);
  useEffect(() => setCopied(false), [letter.key]);
  return (
    <button onClick={async () => { try { await navigator.clipboard.writeText(letterText(letter)); } catch { /* selectable text */ } setCopied(true); }}>
      {copied ? "Copied" : "Copy text"}
    </button>
  );
}

/** A document jason drafted for a person to review, approve, and send. One stage at a time, each step behind
 * `Confirm`, recorded under the person's name (`me`). Approve shows only for a person who may approve for the letter's
 * `approver`; "the board" approves by a vote at a meeting (CIV 4910) that the president or secretary records with
 * the meeting's date. The approved stage shows the terminal command; nothing here sends. `readonly` is the owner's
 * view: the document only. Every stage, readonly too, ends with the approval line (`approvalLine`). */
export function DraftLetter({ letter, readonly = false, me = "", people = [], onStage, busy }: {
  letter: Letter; readonly?: boolean; me?: string; people?: readonly Person[];
  onStage?: (action: StageAction, body: StageBody) => Promise<void> | void; busy?: boolean;
}) {
  const [meeting, setMeeting] = useState("");
  const [sentRef, setSentRef] = useState("");
  const [note, setNote] = useState("");
  const approver = letter.approver || BOARD;
  const board = approver === BOARD;
  const stage: Stage = letter.stage ?? "draft";
  const [badgeText, badgeTone] = STAGE_BADGE[stage] ?? STAGE_BADGE.draft;
  const person = people.find((p) => p.name === me);
  const can = mayApprove(me, approver, people);
  const step = (action: StageAction, extra: Partial<StageBody> = {}) => onStage?.(action, { by: me, note: note || undefined, ...extra });
  const title = letter.title || "this document";
  const events: TimelineEvent[] = (letter.log ?? []).map((e) => ({ id: e.id, date: e.date, title: e.title, tone: e.tone, detail: e.by ? `by ${e.by}` : undefined }));

  return (
    <article className="draft-letter">
      <header className="draft-letter-head">
        <div className="row wrap">
          <Badge tone={readonly ? "neutral" : badgeTone}>{readonly ? letter.ownerBadge || "posted" : badgeText}</Badge>
          <strong>{letter.kind || "Document"}</strong>
        </div>
        <span className="muted">{readonly ? "As delivered to members." : "jason drafts it. Nothing is sent without approval."}</span>
      </header>
      <div className="draft-letter-body">
        <h3>{letter.title}</h3>
        <dl>
          <dt>Date</dt><dd className="num">{letter.date}</dd>
          <dt>To</dt><dd>{letter.to}</dd>
          <dt>Delivery</dt><dd>{letter.via}</dd>
        </dl>
        {letter.body.map((p, i) => <p key={i}>{p}</p>)}
        <p className="draft-letter-signoff">{letter.signoff}</p>
      </div>
      {!readonly && (
        <footer className="draft-letter-foot">
          {!me && stage !== "sent" && <p className="muted">Pick whose name goes on the record before taking a step.</p>}
          <div className="row wrap">
            {stage === "draft" && (
              <>
                <Confirm busy={busy || !me} onConfirm={() => step("save")} summary={<>Save the draft at <code>{letter.key}</code>, in {me}'s name. Nothing is mailed, posted, or recorded without approval.</>}>Save draft</Confirm>
                <CopyText letter={letter} />
              </>
            )}
            {stage === "saved" && (
              <>
                <Confirm busy={busy || !me} onConfirm={() => step("request")} summary={<>Ask {approver} to approve the draft at <code>{letter.key}</code>. Nothing goes out until they approve.</>}>Ask {approver} to approve</Confirm>
                <CopyText letter={letter} />
                <span className="muted">Saved to {letter.key}.</span>
              </>
            )}
            {stage === "requested" && (
              <>
                <span>Waiting on {approver}.</span>
                {can ? (
                  board ? (
                    <Confirm busy={busy} onConfirm={() => step("approve", { meeting })} summary={
                      <div className="stack-sm">
                        <p>Record that the board approved "{title}" by a vote at an open meeting. The board acts only at a meeting (CIV 4910); the vote goes in the minutes. Recorded by {me}{person ? `, ${person.role}` : ""}.</p>
                        <label className="draft-letter-field">Meeting date<input type="date" value={meeting} onChange={(e) => setMeeting(e.target.value)} aria-label="Meeting date" /></label>
                        {!meeting && <span className="muted">The meeting's date is required.</span>}
                      </div>
                    }>Record the board's approval</Confirm>
                  ) : (
                    <Confirm busy={busy} onConfirm={() => step("approve")} summary={<>Approve "{title}" as {me}{person ? `, ${person.role}` : ""}, for {approver}. It can then be sent by a person.</>}>Approve as {me}</Confirm>
                  )
                ) : (
                  <span className="muted">{board ? "Needs a board vote at a meeting (CIV 4910). The president or secretary records it." : me ? `Signed in as ${me}, who is not ${approver}.` : `Only ${approver} can approve.`}</span>
                )}
                {can && (
                  <Confirm busy={busy} onConfirm={() => step("send_back")} summary={<>Send "{title}" back to the drafter. It returns to a saved draft.</>}>Send back</Confirm>
                )}
                <button className="link" disabled={busy || !me} onClick={() => step("withdraw")}>Withdraw</button>
              </>
            )}
            {stage === "approved" && (
              <div className="stack-sm draft-letter-send">
                <p className="muted">Approved. A person sends it by running the command; the page never does.</p>
                {letter.sentCommand ? <Command cmd={letter.sentCommand} /> : <p className="muted">No send command on file; use <code>jason letter</code> or <code>jason mailroom</code>.</p>}
                <Confirm busy={busy || !me} onConfirm={() => step("record_sent", { sentRef })} summary={
                  <div className="stack-sm">
                    <p>Record that "{title}" was sent to {letter.to || "the recipient"} by {letter.via || "the delivery on file"}, in {me}'s name. This records the send; it does not send.</p>
                    <label className="draft-letter-field">Where it was logged<input value={sentRef} onChange={(e) => setSentRef(e.target.value)} placeholder="mailroom communication id or log line" aria-label="Where it was logged" /></label>
                  </div>
                }>Record as sent</Confirm>
              </div>
            )}
            {stage === "sent" && <span className="draft-letter-sent">Sent {letter.sentOn || (letter.log?.at(-1)?.date ?? "")}. Logged: {letter.sentRef || "unrecorded"}.</span>}
          </div>
          {stage !== "sent" && me && (
            <label className="draft-letter-field draft-letter-note">Note for the trail (optional)<input value={note} onChange={(e) => setNote(e.target.value)} aria-label="Note for the trail" /></label>
          )}
          {events.length > 0 && <Timeline events={events} />}
          <ApprovalLine letter={letter} />
        </footer>
      )}
      {readonly && (
        <footer className="draft-letter-foot">
          <ApprovalLine letter={letter} />
        </footer>
      )}
    </article>
  );
}
