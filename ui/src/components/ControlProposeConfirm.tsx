import { useState, type ReactNode } from "react";
import { Confirm } from "./Confirm";
import { postJson } from "../lib/api";
import { proposeUrl, WORDS, type ProposeAnswer } from "../lib/controls";

/** The one write on the Controls screen: put a suggestion before the board as a board item, with the provision as its
 * evidence, in the signer's own name. The body is `{act: "propose"}` and nothing else: the server takes the name from the
 * sign-in (a `by` naming someone else is refused), adopts nothing, and changes no rule. A suggestion, a deferred, or a
 * declined control may be proposed; one already proposed refreshes its item.
 *
 * It goes through `Confirm` (two clicks, the change spelled out). An administrator viewing as someone else gets the
 * sentence in its place, because the server refuses the act then. A refusal is shown as the server said it. `label` is the
 * button's words ("Propose to the board" on the card, "Propose" on a row, with the control's title for a screen reader). */
export function ControlProposeConfirm({ controlKey, title, by = "", actingAs = "", label = WORDS.propose, compact = false, onProposed, post = postJson }: {
  controlKey: string; title: string; by?: string; actingAs?: string; label?: string; compact?: boolean;
  onProposed?: (answer: ProposeAnswer) => void;
  post?: <T>(path: string, body: unknown) => Promise<T>;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  if (actingAs)
    return <p className="muted control-propose-note" role="note">Viewing as {actingAs} (admin view): go back to yourself first. A control is put before the board in a person's own name.</p>;
  const send = async () => {
    setBusy(true);
    setError("");
    try {
      const answer = await post<ProposeAnswer>(proposeUrl(controlKey), { act: "propose" });
      onProposed?.(answer);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const name: ReactNode = by ? by : "the signed-in person";
  return (
    <div className="control-propose">
      <Confirm
        busy={busy}
        label="Propose"
        onConfirm={send}
        summary={
          <>
            <p><strong>{title}.</strong> Create a board item, <code className="chip">control-{controlKey}</code>, with this provision as its evidence, as {name}. It adopts nothing and changes no rule; the board decides at a meeting and the secretary records it.</p>
          </>
        }
      >
        {compact ? <>Propose<span className="visually-hidden"> {title} to the board</span></> : label}
      </Confirm>
      {error && <p role="alert" className="notice notice-error control-propose-error">{error}</p>}
    </div>
  );
}
