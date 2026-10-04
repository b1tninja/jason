import { useEffect, useRef } from "react";
import { OwnerNames } from "jason-ui";

/* "Show owners' names" above the instrument graph. Asking for a name is internal state behind the button, so the
 * asking cells click it once after mount, as the HostPanel and AgendaWizard previews do. Names are made up. */
function Asking({ me = "" }: { me?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const b = [...(ref.current?.querySelectorAll("button") ?? [])].find((x) => x.textContent === "Show owners' names");
    b?.click();
  }, []);
  return <div ref={ref}><OwnerNames shown={false} me={me} onShow={() => {}} onHide={() => {}} /></div>;
}

/** Masked, the default: the button and what the mask does. */
export const Masked = () => <OwnerNames shown={false} onShow={() => {}} onHide={() => {}} />;

/** Asking, with the signed-in person's name filled in: the reveal is logged with it. */
export const AskingSignedIn = () => <Asking me="Jane Example" />;

/** Asking with no name yet: Show names waits for a person's name. */
export const AskingNoName = () => <Asking />;

/** Names shown: who asked and when, that the reveal was logged and where, how many persons were named, and Hide names. */
export const Shown = () => (
  <OwnerNames shown me="Jane Example" onShow={() => {}} onHide={() => {}}
    reveal={{ at: "2026-10-03T16:20:00+00:00", by: "Jane Example", scope: "association", named: 2, log: "console/reveals.jsonl" }} />
);
