import { StepStateWord } from "jason-ui";

const row = { display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" } as const;

/** The states of a step that has not finished: the engine's word with a glyph named for the idea. */
export const OpenStates = () => (
  <div style={row}>
    <StepStateWord state="not started" />
    <StepStateWord state="ready" />
    <StepStateWord state="running" />
    <StepStateWord state="waiting" />
    <StepStateWord state="needs a person" />
  </div>
);

/** The states a step settles into, and the two that stop it. */
export const SettledStates = () => (
  <div style={row}>
    <StepStateWord state="done" />
    <StepStateWord state="skipped" />
    <StepStateWord state="superseded" />
    <StepStateWord state="blocked" />
    <StepStateWord state="failed" />
  </div>
);

/** A done step the stores moved under carries "changed since" beside its word. */
export const ChangedSince = () => (
  <div style={row}>
    <StepStateWord state="done" changed />
    <StepStateWord state="skipped" changed />
  </div>
);

/** A word the engine did not define is shown as it came, with no glyph. */
export const UnknownState = () => (
  <div style={row}>
    <StepStateWord state="on hold" />
  </div>
);
