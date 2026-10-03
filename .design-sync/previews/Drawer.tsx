import type { ReactNode } from "react";
import { Badge, Drawer, DueDate } from "jason-ui";

/** Every preview is read as of October 3, 2026 so each due date's distance is the same on every capture. */
const today = new Date("2026-10-03T12:00:00");

/** A static deadlines body, so the drawer frame is what the cell shows (the live bodies have their own previews). */
const body = (
  <div className="stack dock-panel" style={{ marginTop: 0 }}>
    <div className="row wrap">
      <Badge tone="bad">2 overdue</Badge>
      <Badge tone="warn">2 in 14 days</Badge>
      <Badge>2 later</Badge>
    </div>
    <section className="dock-group" aria-label="Overdue">
      <h3 className="dock-h">Overdue</h3>
      <div className="dock-row">
        <span className="dock-row-main"><button type="button" className="link dock-link">Annual policy statement to members</button><span className="dock-sub">CIV 5310 · Disclosures</span></span>
        <span className="dock-when"><DueDate iso="2026-09-28" today={today} /></span>
      </div>
      <div className="dock-row">
        <span className="dock-row-main"><button type="button" className="link dock-link">D&amp;O renewal certificate</button><span className="dock-sub">the policy term · Insurance</span></span>
        <span className="dock-when"><DueDate iso="2026-09-30" today={today} /></span>
      </div>
    </section>
    <section className="dock-group" aria-label="Next 14 days">
      <h3 className="dock-h">Next 14 days</h3>
      <div className="dock-row">
        <span className="dock-row-main"><button type="button" className="link dock-link">Budget report to members</button><span className="dock-sub">CIV 5300 · Reserves</span></span>
        <span className="dock-when"><DueDate iso="2026-10-10" today={today} /></span>
      </div>
    </section>
  </div>
);

/** A floating drawer is `position: fixed` on the page's right edge; the cell stands in for the page with a sized, transformed box so the drawer stays inside it. */
function Page({ children }: { children: ReactNode }) {
  return (
    <div style={{ position: "relative", height: 460, overflow: "hidden", transform: "translateZ(0)", background: "var(--bg)", border: "1px solid var(--line)", borderRadius: 8 }}>
      <div style={{ padding: 20, maxWidth: 360 }}>
        <h2 style={{ margin: "0 0 8px" }}>Board digest</h2>
        <p className="muted" style={{ margin: 0 }}>Two approvals waiting, one duty due this week, and the October 21 agenda notice to send by the 17th.</p>
      </div>
      {children}
    </div>
  );
}

const noop = () => {};

/** Floating over the console: a fixed panel on the right with Dock it and Close in its head, the body scrolling under a title. */
export const Floating = () => (
  <Page>
    <Drawer id="deadlines" title="Deadlines" pinned={false} canDock onPin={noop} onUnpin={noop} onClose={noop}>{body}</Drawer>
  </Page>
);

/** Floating where the shell has no room to dock (a narrow window): Close only. */
export const FloatingNoDock = () => (
  <Page>
    <Drawer id="deadlines" title="Deadlines" pinned={false} canDock={false} onPin={noop} onUnpin={noop} onClose={noop}>{body}</Drawer>
  </Page>
);

/** Pinned: a bordered column card the shell places beside the screen, with Float to let it go and Close. */
export const Pinned = () => (
  <div style={{ maxWidth: 440 }}>
    <Drawer id="deadlines" title="Deadlines" pinned canDock onPin={noop} onUnpin={noop} onClose={noop}>{body}</Drawer>
  </div>
);
