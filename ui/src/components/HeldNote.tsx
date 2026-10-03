import { isApprovable, personName, plural, when, type PlanItem } from "../lib/approvals";

function BoardItems({ ids, boardHref }: { ids: string[]; boardHref?: (id: string) => string }) {
  if (!ids.length) return null;
  return (
    <>
      {ids.map((id, n) => (
        <span key={id}>
          {n > 0 && ", "}
          {boardHref ? <a href={boardHref(id)}>{id}</a> : <code className="chip">{id}</code>}
        </span>
      ))}
    </>
  );
}

const uniq = (xs: (string | undefined)[]) => [...new Set(xs.filter((x): x is string => !!x))];

/** Why changes are held for the board, in two kinds kept apart:
 * - "Held for the board": jason's policy finding (the planner's `held_for_board` class, a question no rule answers). Never
 *   approvable; only the board's decision releases it. It names the board item it waits on.
 * - "Held for the board by NAME": a person's decision (`decision: "held"`) on an approvable item, with the reason.
 * Pass the items; each kind present renders its own note (`role="note"`). `inline` is one line for a single row. */
export function HeldNote({ items, inline = false, boardHref }: { items: readonly PlanItem[]; inline?: boolean; boardHref?: (id: string) => string }) {
  const policy = items.filter((i) => i.class === "held_for_board");
  const byPerson = items.filter((i) => isApprovable(i) && i.decision === "held");
  if (!policy.length && !byPerson.length) return null;

  if (inline) {
    const i = policy[0] ?? byPerson[0];
    return policy.length ? (
      <p className="held-note held-inline" role="note">
        Held for the board <span className="held-source">jason's policy finding</span>
        {i.boardItem && <>: board item <BoardItems ids={[i.boardItem]} boardHref={boardHref} /></>}
      </p>
    ) : (
      <p className="held-note held-inline held-by-person" role="note">
        Held for the board by {personName(i.decidedBy)}<span className="held-source">decision</span>{i.reason ? <>: <q>{i.reason}</q></> : null}
      </p>
    );
  }

  const people = uniq(byPerson.map((i) => i.decidedBy || "(no person named)"));
  return (
    <>
      {policy.length > 0 && (
        <section className="held-note" role="note" aria-label="Held for the board: jason's policy finding">
          <h3>{plural(policy.length, "change", "changes")} held for the board <span className="held-source">jason's policy finding</span></h3>
          <p>No rule the board has adopted answers these. jason does not apply them, and approving this plan does not approve them.</p>
          {uniq(policy.map((i) => i.boardItem)).length > 0 && (
            <p className="muted">Board item <BoardItems ids={uniq(policy.map((i) => i.boardItem))} boardHref={boardHref} />.</p>
          )}
        </section>
      )}
      {people.map((who) => {
        const mine = byPerson.filter((i) => (i.decidedBy || "(no person named)") === who);
        const reasons = uniq(mine.map((i) => i.reason));
        const at = mine.map((i) => i.decidedAt).filter(Boolean).sort().pop();
        return (
          <section key={who} className="held-note held-by-person" role="note" aria-label={`Held for the board by ${personName(who)}`}>
            <h3>{plural(mine.length, "change", "changes")} held for the board by {personName(who)} <span className="held-source">decision</span></h3>
            {reasons.map((r) => <p key={r}>Reason: <q>{r}</q></p>)}
            <p className="muted">{at ? `${when(at)} · ` : ""}not written; the board takes it up.</p>
          </section>
        );
      })}
    </>
  );
}
