import { RemoteView, Card, Money } from "jason-ui";

type Delinquency = {
  found?: boolean;
  note?: string;
  hint?: string;
  asOf?: string;
  count?: number;
  totalCents?: number;
  accounts?: { unit: string; owner: string; balanceCents: number; days: number }[];
};

const reload = () => {};

const ready = {
  status: "ready" as const,
  reload,
  data: {
    found: true,
    asOf: "2026-10-01",
    count: 3,
    totalCents: 412350,
    accounts: [
      { unit: "Unit 14", owner: "Owner of record", balanceCents: 186000, days: 92 },
      { unit: "Unit 27", owner: "Owner of record", balanceCents: 142350, days: 61 },
      { unit: "Unit 33", owner: "Owner of record", balanceCents: 84000, days: 34 },
    ],
  } satisfies Delinquency,
};

const render = (d: Delinquency) => (
  <Card title={`Delinquent accounts (${d.count})`}>
    <p className="muted" style={{ margin: "0 0 .5rem" }}>
      As of {d.asOf} · total <Money cents={d.totalCents ?? 0} />
    </p>
    <ul style={{ margin: 0, paddingLeft: "1.2rem" }}>
      {d.accounts?.map((a) => (
        <li key={a.unit}>
          {a.unit}: <Money cents={a.balanceCents} /> · {a.days} days past due
        </li>
      ))}
    </ul>
  </Card>
);

/** While the request is in flight: the Loading line. */
export const LoadingState = () => <RemoteView r={{ status: "loading", reload }}>{render}</RemoteView>;

/** The fetch failed: an ErrorNotice with Retry wired to `reload`. */
export const ErrorState = () => <RemoteView r={{ status: "error", error: "Could not reach jason-mcp: connection refused (127.0.0.1:8765).", reload }}>{render}</RemoteView>;

/** The tool answered `found: false`: its own note shows as the empty state, and children are not called. */
export const NotFound = () => (
  <RemoteView r={{ status: "ready", reload, data: { found: false, note: "No delinquency sheet on disk yet. Run `jason delinquency` to build one." } as Delinquency }}>{render}</RemoteView>
);

/** Data arrived and fits the view: children render a Card from it. */
export const Ready = () => <RemoteView r={ready}>{render}</RemoteView>;

/** A typed view written against a shape the data does not fit: it reads `rows[0]` and throws while rendering. */
function MismatchedView({ d }: { d: Delinquency }) {
  const first = (d as unknown as { rows: { unit: string }[] }).rows[0];
  return <Card title={first.unit}>unreachable</Card>;
}

/** The view throws; the boundary shows the notice, a generic digest of the data, and the raw JSON, so the person still sees what the tool returned. */
export const ChildrenThrow = () => <RemoteView r={ready}>{(d) => <MismatchedView d={d} />}</RemoteView>;
