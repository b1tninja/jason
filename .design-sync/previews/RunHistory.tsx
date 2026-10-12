import { RunHistory } from "jason-ui";

// A run's event log as the work loader sends it. Made-up: Oakview's sample cycle, 2099 dates, `Person 1 office` / `A. Manager`.
const ev = (n: number, kind: string, step: string, stepTitle: string, by: string, at: string, text: string, over: any = {}): any => ({
  n, kind, step, stepTitle, by, at, text, detail: {}, pending: false, ...over,
});

const events = [
  ev(1, "open", "", "", "A. Manager", "2099-10-01T09:00:00+00:00", "Run opened for the Oakview owner-information cycle."),
  ev(2, "step-done", "oi.send", "Send the owner-information letters", "A. Manager", "2099-10-01T09:20:00+00:00", "Step 1, Send the owner-information letters, done: 42 letters sent."),
  ev(3, "set-date", "", "", "Person 1 office", "2099-10-03T14:05:00+00:00", "The answer-by date was set to 2099-10-23."),
  ev(4, "note", "oi.read-forms", "Read the returned forms", "A. Manager", "2099-10-06T16:40:00+00:00", "Eleven forms are back; the rest are due by the answer-by date."),
];

const wide = { maxWidth: 720 } as const;

/** The event log, newest first, each with when it happened. A correction is a later entry, never an edit. */
export const NewestFirst = () => <div style={wide}><RunHistory events={events} /></div>;

/** A read of the run found a change nobody has recorded yet: it is marked, in italics, as not yet recorded. */
export const WithPendingEvent = () => (
  <div style={wide}>
    <RunHistory events={[...events, ev(5, "changed", "oi.read-forms", "Read the returned forms", "", "2099-10-08T08:00:00+00:00", "A returned form changed after step 2 was done.", { pending: true })]} />
  </div>
);

/** For the board's record: oldest first, with who recorded each event and the evidence addresses it kept. */
export const PrintForTheRecord = () => (
  <div style={wide}>
    <RunHistory print events={[
      events[0],
      ev(2, "step-done", "oi.send", "Send the owner-information letters", "A. Manager", "2099-10-01T09:20:00+00:00", "Step 1, Send the owner-information letters, done: 42 letters sent.",
        { detail: { evidence: [{ address: "mailroom:batch-1", hash: "ab12cd34ef56789a" }, { address: "drive:letter-1", hash: "99ee88dd77cc66bb" }] } }),
      ev(3, "changed", "oi.send", "Send the owner-information letters", "A. Manager", "2099-10-05T10:00:00+00:00", "The sent letter differs from the one on file.",
        { detail: { differences: [{ address: "drive:letter-1", was: "99ee88dd77cc", now: "11aa22bb33cc" }] } }),
    ]} />
  </div>
);

/** A run that has not recorded anything yet says so. */
export const NoEvents = () => <div style={wide}><RunHistory events={[]} /></div>;
