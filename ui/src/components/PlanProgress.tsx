import { Command } from "./Command";
import { Glyph, type GlyphName } from "./Glyph";
import {
  applyCountsWords, commands, cleanName, isJason, personName, tally, when, writtenTo,
  type Approval, type KindFacts,
} from "../lib/approvals";
import "../styles/plan-progress.css";

export type StepKey = "review" | "sign" | "second" | "apply" | "done";

const NAMES: Record<StepKey, string> = { review: "Review", sign: "Sign", second: "Second signature", apply: "Apply", done: "Done" };

/** The step a plan is at, from its status and what it holds, or null for a plan that ended without being applied
 * (withdrawn, replaced). Review ends when every approvable change is marked; the plan then waits for a signature. */
export function currentStep(a: Approval, second: boolean): StepKey | null {
  switch (a.status) {
    case "planned":
    case "in_review": {
      const t = tally(a);
      return t.undecided === 0 && (t.approvable > 0 || t.exceptions > 0) ? "sign" : "review";
    }
    case "approved":
    case "partially_approved": return second && !a.second ? "second" : "apply";
    case "applying":
    case "failed": return "apply";
    case "applied": return "done";
    default: return null;
  }
}

/** The command a person runs at a terminal: a terminal-only kind's own (its `cli`, with the plan's id and fingerprint
 * filled in), else `jason approvals apply`. */
export function terminalCommand(a: Pick<Approval, "id" | "fingerprint">, me: string, kind?: KindFacts | null): string {
  if (kind?.terminalOnly && kind.cli) return kind.cli.replace("FINGERPRINT", a.fingerprint).replace(/\bID\b/, a.id);
  return commands.apply(a.id, me);
}

/** One line of up to five steps above a plan: Review, Sign, Second signature (only where the plan needs one), Apply,
 * Done. The step the plan is at is `aria-current="step"`; a done step says who did it and when; the next action is
 * named. The Apply step says where apply happens: here (`canApplyHere`, the server allows it), or at a terminal with the
 * command and Copy; a terminal-only kind says it is applied only there. Under it, the standing line: until the plan is
 * applied, **nothing has been written** to the kind's system and what applying will do, in counts; after, the result.
 * It reads from the plan, never from who is looking. `ready` is a signed plan that apply would accept now. */
export function PlanProgress({ approval: a, me = "", kind, needsSecond: second, canApplyHere = false, ready = false, tooOld = false, blocked = false }: {
  approval: Approval; me?: string; kind?: KindFacts | null; needsSecond: boolean; canApplyHere?: boolean;
  ready?: boolean; tooOld?: boolean; blocked?: boolean;
}) {
  const keys: StepKey[] = second ? ["review", "sign", "second", "apply", "done"] : ["review", "sign", "apply", "done"];
  const at = currentStep(a, second);
  const here = at ? keys.indexOf(at) : -1;
  const terminalOnly = !!kind?.terminalOnly;
  const first = a.first ? personName(a.first.name) : "";
  const result = a.result ?? {};
  const ranBy = typeof result.by === "string" ? personName(result.by) : "";
  const ranAt = typeof result.at === "string" ? when(result.at) : "";
  const reviewers = [...new Set(a.items.filter((i) => i.decision !== "undecided" && i.decidedBy && !isJason(i.decidedBy)).map((i) => cleanName(i.decidedBy)))];
  const lastMark = a.items.map((i) => i.decidedAt ?? "").filter(Boolean).sort().at(-1);
  const closed = a.status === "withdrawn" || a.status === "superseded";
  const to = writtenTo(kind);
  const open = !closed && !["applying", "applied", "failed"].includes(a.status);
  const applyReached = at === "apply";
  const showCommand = applyReached && ready && (terminalOnly || !canApplyHere);

  /** What each step says: who did it and when once done, else what it waits on or who does it next. */
  const detail = (k: StepKey, done: boolean): string => {
    switch (k) {
      case "review":
        return done ? `Marked by ${reviewers.length ? reviewers.join(" and ") : "a person"}${lastMark ? `, ${when(lastMark)}` : ""}` : "Any board member or the manager marks each change approved, rejected, or held.";
      case "sign":
        return done && a.first ? `Signed by ${first}, ${when(a.first.at)}` : "The person who reviewed signs the plan.";
      case "second":
        return done && a.second ? `Signed by ${personName(a.second.name)}, ${when(a.second.at)}` : `A second person${first ? `, not ${first},` : ""} signs the same plan.`;
      case "apply":
        if (done) return `${a.status === "failed" ? "Ran" : "Applied"}${ranBy ? ` by ${ranBy}` : ""}${ranAt ? `, ${ranAt}` : ""}`;
        if (a.status === "applying") return "Applying now.";
        if (a.status === "failed") return "Some changes were not made. A person looks at what failed.";
        if (terminalOnly) return ready ? "Applied only at a terminal, by a person:" : "Applied only at a terminal, by a person, once signed.";
        if (!applyReached) return canApplyHere ? "Once signed, apply from here." : "Once signed, a person applies this at a terminal.";
        if (blocked) return "The plan changed since review: plan it again first.";
        if (tooOld) return "Read too long ago: apply plans it again before it writes anything.";
        return canApplyHere ? "Apply from here." : "A person applies this at a terminal:";
      case "done":
        return a.status === "applied" ? "Read back and recorded: the result is below." : "jason reads back and records what was applied, what failed, and what was refused.";
    }
  };

  const signedBy = a.first ? [first, a.second ? personName(a.second.name) : ""].filter(Boolean).join(" and ") : "";
  const next = ready && applyReached ? `Signed by ${signedBy || "the signers"}, ready to apply.` : "";

  return (
    <section className="plan-progress" aria-label="Plan progress">
      {closed ? (
        <p className="plan-written">Nothing was written {to}.</p>
      ) : (
        <ol className="plan-steps">
          {keys.map((k, n) => {
            const complete = a.status === "applied" || (at !== null && n < here);
            const current = k === at;
            const glyph: GlyphName = complete ? "check" : current ? "arrow-right" : "circle-dashed";
            return (
              <li key={k} className={`plan-step ${complete ? "plan-step-done" : current ? "plan-step-now" : "plan-step-later"}`} aria-current={current ? "step" : undefined}>
                <span className="plan-step-head">
                  <Glyph name={glyph} size="1em" />
                  <strong className="plan-step-name">{NAMES[k]}</strong>
                  <span className="plan-step-state">{complete ? "complete" : current ? "you are here" : "not yet"}</span>
                </span>
                <span className="plan-step-detail">{detail(k, complete)}</span>
              </li>
            );
          })}
        </ol>
      )}
      {showCommand && (
        <Command cmd={terminalCommand(a, me, kind)}
          note={terminalOnly ? "This kind is applied only at a terminal. jason-web never applies it. jason reads live again first." : "Apply from a terminal. jason reads live again first and writes nothing if anything changed."} />
      )}
      {next && <p className="plan-next">{next}</p>}
      {open || a.status === "applying" ? (
        <p className="plan-written">
          <strong>{a.status === "applying" ? `Writing ${to} now.` : `Nothing has been written ${to} yet.`}</strong>{" "}
          {a.status === "applying" ? "" : applyCountsWords(a)}
        </p>
      ) : null}
    </section>
  );
}
