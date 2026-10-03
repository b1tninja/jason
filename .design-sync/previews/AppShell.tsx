import { AppShell, Badge, Card } from "jason-ui";

const nav = (current: string) => (
  <nav className="nav">
    {["Digest", "Duties", "Inbox", "Deadlines", "Money", "Meetings", "Board items"].map((label) => (
      <a key={label} href={`#/${label.toLowerCase().replace(" ", "-")}`} aria-current={label === current ? "page" : undefined}>
        {label}
      </a>
    ))}
  </nav>
);

/** The shell: brand at left, the nav beside it with the current page highlighted, and a card in the main column. */
export const Digest = () => (
  <AppShell title="Jason" nav={nav("Digest")}>
    <Card title="Board digest">
      <p>
        <Badge tone="bad">2 overdue</Badge> <Badge tone="warn">5 due in 14 days</Badge> <Badge tone="good">insurance current</Badge>
      </p>
      <p className="muted">Each item is a matter to decide, never the decision.</p>
    </Card>
  </AppShell>
);

/** A different page current, with two stacked cards in the main column. */
export const Meetings = () => (
  <AppShell title="Jason" nav={nav("Meetings")}>
    <div className="stack" style={{ display: "grid", gap: "1rem" }}>
      <Card title="Next meeting">
        <p>Board meeting, 2026-10-21 at 6:30 pm, clubhouse. Notice posted 2026-10-16 at the latest (CIV 4920).</p>
      </Card>
      <Card title="Minutes outstanding">
        <p className="muted">September 16: draft due to owners by 2026-10-16 (CIV 4950).</p>
      </Card>
    </div>
  </AppShell>
);

/** No nav at all: the brand alone in the bar. */
export const NoNav = () => (
  <AppShell title="Jason">
    <Card>
      <p>Server: sources payhoa, google; writes none.</p>
    </Card>
  </AppShell>
);
