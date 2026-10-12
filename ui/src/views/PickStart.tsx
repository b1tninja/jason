import { useId } from "react";
import { navigateTo, pickStartUrl, usePickSetup, type PickPurpose } from "../lib/pick";

/** The button, with in words what happens when it is pressed. Without the community's switch the same place says it is off and who
 * may turn it on. Pressing it leaves the console for the server, which sends the person to Google and back to this route. */
export function PickStart({ purpose, slot = "" }: { purpose: PickPurpose; slot?: string }) {
  const id = useId();
  const setup = usePickSetup();
  if (!setup.known) return null;
  return (
    <section className="pick-start" aria-labelledby={`${id}-h`}>
      <h3 id={`${id}-h`}>From your own Google Drive</h3>
      {setup.enabled ? (
        <>
          <p id={`${id}-d`}>Google will ask which files to share with jason. jason reads each file once and keeps a copy; it writes nothing to Drive and does not keep your Google sign-in.</p>
          <p>
            <button type="button" className="primary" aria-describedby={`${id}-d`}
              onClick={() => navigateTo(pickStartUrl(setup.start, purpose, slot, window.location.hash))}>Choose from my Google Drive</button>
          </p>
          <p className="muted">You leave this page for Google's own page and come back here when you are done. Choose PDFs, not folders.</p>
        </>
      ) : (
        <p className="muted" role="note">
          Picking from your own Drive is off for this community. Your community's administrator can turn it on in <a href="#/setup/limits">Setup, Limits</a> (the row named <code>pick.enabled</code>).
        </p>
      )}
    </section>
  );
}
