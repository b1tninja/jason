import { Card, Badge, Stat, Money, Caveats } from "jason-ui";

/** A titled card with plain prose: the section the treasurer reads first. */
export const Titled = () => (
  <Card title="Payments with questions">
    <p style={{ margin: 0 }}>
      Each finding is a question for the treasurer: re-attach, re-categorize, or recover. "Paid twice" is confirmed only by a next-bill credit or two debits at the bank.
    </p>
  </Card>
);

/** The action slot: a status badge on the right, a muted note of what the data runs through. */
export const WithActions = () => (
  <Card title="Records under Civil Code 5200 (23)" actions={<Badge tone="bad">{`${3} gaps`}</Badge>}>
    <p style={{ margin: 0 }}>Twenty of twenty-three record kinds are pinned to a Drive file. The three gaps are the reserve study, the insurance summary, and the 2024 minutes.</p>
  </Card>
);

/** A checkbox control in the action slot, as the board items and meetings cards use. */
export const WithControl = () => (
  <Card
    title="Board action items"
    actions={
      <label style={{ display: "flex", gap: 6, alignItems: "center", fontSize: ".9rem" }}>
        <input type="checkbox" defaultChecked={false} readOnly /> show closed
      </label>
    }
  >
    <ul style={{ margin: 0, paddingLeft: "1.2rem" }}>
      <li>Replace the pool gate latch <Badge tone="warn">executive</Badge></li>
      <li>Adopt the 2027 budget by 2026-11-01 <Badge>finance</Badge></li>
      <li>Renew the landscape contract <Badge>vendors</Badge></li>
    </ul>
  </Card>
);

/** A reconciliation card: stats in a row, then the caveat, with a muted date in the action slot. */
export const Composed = () => (
  <Card title="Operating checking …4417" actions={<span style={{ color: "var(--muted)" }}>reconciled through 2026-08</span>}>
    <div className="stats" style={{ marginBottom: 12 }}>
      <Stat label="Statement ending" value={<Money cents={8421377} />} />
      <Stat label="Register" value={<Money cents={8396102} />} />
      <Stat label="Open items" value={4} />
      <Stat label="Months with no reconciliation" value={2} hint="2026-03, 2026-06" />
    </div>
    <Caveats items={["A difference between statement and register is a question for the treasurer, not a finding of error."]} />
  </Card>
);

/** No title and no actions: the header is omitted, not left as an empty bar. */
export const Untitled = () => (
  <Card>
    <p style={{ margin: 0 }}>Executive session (CIV 4935). jason records nothing here and never submits an account to a collection agency, records a lien, or starts a foreclosure.</p>
  </Card>
);
