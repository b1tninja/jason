/** One stage gate as `onboarding_status` gives it (`onboarding_session.status_dict`'s `gates`). `open: true` is a gate
 * that has opened (its checks passed); a closed gate names what it waits on. */
export interface StageGate {
  stage: string; title: string; open: boolean; opensWhen?: string;
  waiting?: { key: string; status: string }[]; checks?: { passed: boolean; evidence: string }[];
}

/** The stages in order, each with its gate in words ("Gate open", or what it waits on); the mark repeats the words. The
 * stage being worked (`current`, the session's `stage`) carries `aria-current="step"`. A gate is jason's reading of the
 * checklist; the board decides what is done. */
export function StageSteps({ gates, current, label = "Stages" }: { gates: readonly StageGate[]; current?: string; label?: string }) {
  if (!gates.length) return <p className="muted">No stages.</p>;
  return (
    <ol className="stage-steps" aria-label={label}>
      {gates.map((g, n) => {
        const failed = (g.checks ?? []).filter((c) => !c.passed);
        const waits = [...(g.waiting ?? []).map((w) => `${w.key} (${w.status})`), ...failed.map((c) => c.evidence)];
        return (
          <li key={g.stage} className={`stage-step ${g.open ? "stage-open" : "stage-waiting"}`} aria-current={g.stage === current ? "step" : undefined}>
            <span className="stage-mark" aria-hidden="true">{g.open ? "✓" : n + 1}</span>
            <div className="stack-sm">
              <strong className="stage-name">{g.stage.replace(/^./, (c) => c.toUpperCase())}</strong>
              <span className="muted">{g.title}</span>
              <span className={g.open ? "stage-state stage-state-open" : "stage-state"}>{g.open ? "Gate open" : "Gate closed"}{g.stage === current ? " · working now" : ""}</span>
              {!g.open && (waits.length > 0 || g.opensWhen) && (
                <p className="stage-waits"><strong>Waiting on:</strong> {waits.length ? waits.slice(0, 4).join("; ") + (waits.length > 4 ? `; and ${waits.length - 4} more` : "") : g.opensWhen}</p>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
