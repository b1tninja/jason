import { useState } from "react";
import { Badge, Card, ConsoleShell, ScreenHeader, Stat, type Audience, type ConsoleScreen } from "jason-ui";

const GROUPS = ["Overview", "Governance", "Money", "Records"];
const SCREENS: ConsoleScreen[] = [
  { id: "digest", label: "Board digest", ownerLabel: "Overview", group: "Overview", owner: true },
  { id: "approvals", label: "Approvals", group: "Overview", count: 2 },
  { id: "actions", label: "Board action items", group: "Governance", count: 7 },
  { id: "meetings", label: "Meetings and minutes", group: "Governance", owner: true },
  { id: "duties", label: "Duties and deadlines", group: "Governance" },
  { id: "liens", label: "Liens and delinquency", group: "Money" },
  { id: "money", label: "Budget and reserves", ownerLabel: "Finances", group: "Money", owner: true },
  { id: "records", label: "Records (CIV 5200)", group: "Records", owner: true },
  { id: "library", label: "Document library", ownerLabel: "Documents", group: "Records", owner: true },
];
const PEOPLE = [
  { name: "D. Okafor", role: "president" },
  { name: "R. Lind", role: "secretary" },
  { name: "M. Chen", role: "treasurer" },
];

function Body({ audience }: { audience: Audience }) {
  return (
    <>
      <ScreenHeader title={audience === "owner" ? "Overview" : "Board digest"} summary="What needs the board's attention this week, with the authority for each item." />
      <div className="stats">
        <Stat label="Deadlines in 14 days" value={3} hint="2 notices, 1 filing" />
        <Stat label="Awaiting approval" value={2} />
        <Stat label="Open action items" value={7} />
      </div>
      <Card title="Next meeting">
        <p>
          <Badge tone="warn">notice due 2026-10-17</Badge> Board meeting, 2026-10-21 at 6:30 pm, clubhouse (CIV 4920).
        </p>
        <p className="muted">Each item is a matter to decide, never the decision.</p>
      </Card>
    </>
  );
}

function Shell({ audience: initial, current: start = "digest", recordsAsOf, me: startMe = "D. Okafor", dock }: {
  audience: Audience; current?: string; recordsAsOf?: string; me?: string; dock?: boolean;
}) {
  const [audience, setAudience] = useState<Audience>(initial);
  const [current, setCurrent] = useState(start);
  const [me, setMe] = useState(startMe);
  return (
    <ConsoleShell
      wordmark="Sample Commons"
      legal="Sample Commons Owners Association"
      recordsAsOf={recordsAsOf}
      groups={GROUPS}
      screens={SCREENS}
      current={current}
      onGo={setCurrent}
      audience={audience}
      onAudience={setAudience}
      session={{ me, setMe, people: PEOPLE }}
      dock={dock && audience === "board" ? <div className="dock"><button className="link">Inbox (3)</button><button className="link">Scratchpad</button></div> : undefined}
    >
      <Body audience={audience} />
    </ConsoleShell>
  );
}

/** The board's console: wordmark, legal name, records date, the sign-in pick, the Board / Owner view control, and the grouped nav with counts. */
export const Board = () => <Shell audience="board" recordsAsOf="2026-10-02" dock />;

/** The owner view: board-only screens, the sign-in, and the dock gone; the read-only banner over the page; owner labels in the nav. */
export const Owner = () => <Shell audience="owner" recordsAsOf="2026-10-02" dock />;

/** No records date (no loader gave one, so none is shown), no dock, and no one picked as signed in yet. */
export const Bare = () => <Shell audience="board" current="liens" me="" />;
