import { Card, Caveats, Command, DataTable, RemoteView, RoutingTag, RoutingTags, ScreenHeader, type Column, type RoutingOwner } from "../components";
import { useApi } from "../lib/useApi";

/** One person in an office, as `GET /api/people` gives them. */
export interface PeopleHolder { name: string; approves: string[]; recordsBoard: boolean; canSignIn: boolean; portfolio?: boolean }
export interface PeopleDuty { key: string; title: string; adoption: string; owners: RoutingOwner[]; assigned: boolean; routing: string; backup: string }
export interface PeopleOffice {
  office: string; holders: PeopleHolder[]; vacant: boolean; vacancy: string;
  provision: { source: string; words: string } | null; provisionNote: string; duties: PeopleDuty[];
}
export interface PeoplePerson { name: string; offices: string[]; approves: string[]; recordsBoard: boolean; canSignIn: boolean; admin: boolean; email: string }
export interface PeopleAdmin { name: string; holds: string[]; canSignIn: boolean; note: string }
export interface People {
  found: boolean; note?: string; asOf: string;
  offices: PeopleOffice[];
  directors: { holders: PeopleHolder[]; seats: { seats: number; source: string } | null };
  management: { holders: PeopleHolder[]; note: string; vacant: boolean; vacancy: string; duties: PeopleDuty[] };
  admins: PeopleAdmin[];
  people: PeoplePerson[];
  vacant: string[];
  terms: { onFile: boolean; note: string };
  change: { note: string; onboardingItem: string; screen: string; built: boolean; commands: string[]; gap: string };
  emailsShown: boolean; emailsNote: string;
  caveats: string[];
}

function approvesWords(h: { approves: string[]; recordsBoard: boolean }): string {
  const alone = h.approves.length ? `Approves ${h.approves.join(", ")}` : "Approves nothing alone";
  return h.recordsBoard ? `${alone}; records the board's vote` : alone;
}

const signsIn = (yes: boolean) => (yes ? "can sign in" : "cannot sign in (no address on the roster)");

function Holders({ office, holders }: { office: string; holders: PeopleHolder[] }) {
  return (
    <ul className="findings">
      {holders.map((h) => (
        <li key={h.name}>
          <RoutingTag owner={{ role: office, name: h.name }} />{" "}
          <span className="muted">{approvesWords(h)} · {signsIn(h.canSignIn)}{h.portfolio ? " · a portfolio manager" : ""}</span>
        </li>
      ))}
    </ul>
  );
}

function Duties({ duties }: { duties: PeopleDuty[] }) {
  if (!duties.length) return null;
  return (
    <details>
      <summary>{duties.length} {duties.length === 1 ? "duty" : "duties"} the assignments give this office</summary>
      <ul className="findings">
        {duties.map((d) => (
          <li key={d.key}>
            {d.title} <RoutingTags owners={d.assigned ? d.owners : []} />{" "}
            <span className="muted">{d.routing}{d.backup ? `; the assignment names ${d.backup} as backup` : ""}</span>
          </li>
        ))}
      </ul>
    </details>
  );
}

function Office({ o }: { o: PeopleOffice }) {
  return (
    <section aria-label={o.office} className="stack">
      <h3>{o.office.charAt(0).toUpperCase() + o.office.slice(1)}</h3>
      {o.vacant ? (
        <>
          <p><RoutingTag owner={{ role: o.office }} /> {o.vacancy}</p>
          {o.provision ? (
            <blockquote>
              {o.provision.words && <p>{o.provision.words}</p>}
              <cite>{o.provision.source}</cite>
            </blockquote>
          ) : (
            <p className="muted">{o.provisionNote}</p>
          )}
        </>
      ) : (
        <Holders office={o.office} holders={o.holders} />
      )}
      <Duties duties={o.duties} />
    </section>
  );
}

const personCols = (emailsShown: boolean): Column<PeoplePerson>[] => [
  { key: "name", header: "Person" },
  { key: "offices", header: "Offices", value: (p) => p.offices.join(", "),
    render: (p) => (p.offices.length ? <RoutingTags owners={p.offices.map((role) => ({ role }))} /> : <span className="muted">no office</span>) },
  { key: "approves", header: "Approves", value: (p) => approvesWords(p), render: (p) => approvesWords(p) },
  { key: "canSignIn", header: "Sign-in", value: (p) => (p.canSignIn ? 1 : 0), render: (p) => signsIn(p.canSignIn) },
  { key: "email", header: emailsShown ? "Email" : "Email (masked)", render: (p) => p.email || <span className="muted">none</span> },
  { key: "admin", header: "jason admin", value: (p) => (p.admin ? 1 : 0), render: (p) => (p.admin ? "yes" : "") },
];

/** People and offices: who holds each office, what it approves, and who can sign in. Read-only: a change of office is
 * the board's act, recorded in the minutes, then recorded through onboarding's board-roster item. */
export function PeopleView() {
  const r = useApi<People>("/api/people");
  return (
    <RemoteView r={r}>
      {(d) => (
        <div className="stack">
          <ScreenHeader title="People and offices" summary={`Who holds each office, what it approves, and who can sign in. Read from the profile and the roster as of ${d.asOf}.`} />
          <Card title="Offices">
            {d.offices.map((o) => <Office key={o.office} o={o} />)}
          </Card>
          <Card title="Directors">
            {d.directors.holders.length ? <Holders office="director" holders={d.directors.holders} /> : <p className="muted">No director without an office is on the roster.</p>}
            {d.directors.seats && <p className="muted">Seats: {d.directors.seats.seats}{d.directors.seats.source ? ` (${d.directors.seats.source})` : ""}</p>}
          </Card>
          <Card title="Management">
            <p className="muted">{d.management.note}</p>
            {d.management.vacant ? <p><RoutingTag owner={{ role: "manager" }} /> {d.management.vacancy}</p> : <Holders office="manager" holders={d.management.holders} />}
            <Duties duties={d.management.duties} />
          </Card>
          <Card title="By person">
            <p className="muted">{d.emailsNote}</p>
            <DataTable rows={d.people} columns={personCols(d.emailsShown)} searchable={false} rowKey={(p) => p.name} />
          </Card>
          <Card title="jason's administrators">
            {d.admins.length ? (
              <ul className="findings">
                {d.admins.map((a) => (
                  <li key={a.name}>{a.name}: {a.note}{a.holds.length ? ` (also holds ${a.holds.join(", ")}, listed under the office)` : ""} · {signsIn(a.canSignIn)}</li>
                ))}
              </ul>
            ) : <p className="muted">No administrator is set up for this installation.</p>}
          </Card>
          <Card title="Terms">
            <p>{d.terms.note}</p>
          </Card>
          <Card title="Recording a change">
            <p>{d.change.note}</p>
            <p>Onboarding item: <a href={`#/${d.change.screen}`}>{d.change.onboardingItem}</a></p>
            {!d.change.built && <p className="muted">{d.change.gap}</p>}
            {d.change.commands.map((c) => <Command key={c} cmd={c} />)}
          </Card>
          <Caveats items={d.caveats} />
        </div>
      )}
    </RemoteView>
  );
}
