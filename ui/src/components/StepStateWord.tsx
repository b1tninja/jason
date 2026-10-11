import { Glyph } from "./Glyph";
import { STATES, isStepState } from "../lib/work";

/** A step's state: the engine's own word, always shown, with a glyph named for the idea. Colour only repeats the word. A
 * word the engine did not define is shown as it came. `changed` adds "changed since" beside a done step the stores moved
 * under. */
export function StepStateWord({ state, changed = false }: { state: string; changed?: boolean }) {
  const look = isStepState(state) ? STATES[state] : null;
  return (
    <span className="step-state-wrap">
      <span className={`badge badge-${look?.tone ?? "neutral"} step-state step-state-${state.replace(/\s+/g, "-")}`} title={look?.meaning}>
        {look && <Glyph name={look.glyph} size="1em" className="badge-glyph" />}
        {state}
      </span>
      {changed && (
        <span className="badge badge-warn step-state step-state-changed" title="A store moved under this step after it was done.">
          <Glyph name="triangle-alert" size="1em" className="badge-glyph" />
          changed since
        </span>
      )}
    </span>
  );
}
