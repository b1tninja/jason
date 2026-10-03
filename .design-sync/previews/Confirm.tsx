import { Card, Confirm } from "jason-ui";

const summary = (
  <ul>
    <li>
      status: <s>proposed</s> → on agenda
    </li>
    <li>
      meeting: <s>—</s> → 2026-10-21
    </li>
  </ul>
);

/** Idle: a primary button. The first click arms it and shows the summary; nothing is written until the second click. */
export const Idle = () => (
  <Confirm summary={summary} onConfirm={() => {}}>
    Save board fields
  </Confirm>
);

/** Idle and busy: the button is disabled while a write is in flight. */
export const Busy = () => (
  <Confirm summary={summary} onConfirm={() => {}} busy>
    Save board fields
  </Confirm>
);

/** Idle inside a card beside a muted note, as the board item card shows it under the editable fields. */
export const InCard = () => (
  <Card title="Unit 14 delinquency">
    <p className="muted">Two board fields changed.</p>
    <Confirm summary={summary} onConfirm={() => {}}>
      Save board fields
    </Confirm>
  </Card>
);

/** What the armed state shows (the summary and Yes/Cancel), rendered with the same markup since the armed state is internal and cannot be set from props. */
export const ArmedLookalike = () => (
  <div className="confirm" role="group" aria-label="Confirm">
    <div>{summary}</div>
    <div className="row">
      <button className="primary">Yes, do it</button>
      <button>Cancel</button>
    </div>
  </div>
);
