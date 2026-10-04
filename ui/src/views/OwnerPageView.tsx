import { Badge, Card, Caveats, Embed, RemoteView, Stat } from "../components";
import { useApi } from "../lib/useApi";

interface Page { page: string; label: string; path: string; url: string }
interface Mailing { kind: string; label: string; zip: string }
interface Contact { label: string; purpose: string; kind: string; email: string }
interface RecordKind { record: string; citation: string; meaning: string; onFile: boolean }
export interface CommunityProfile {
  found: boolean;
  slug: string;
  name: string;
  corporateName: string;
  wordmark: string;
  site: string;
  pages: Page[];
  mailing: Mailing[];
  contacts: Contact[];
  calendarId: string;
  timeZone: string;
  records: { kinds: RecordKind[]; onFile: number; total: number; note: string };
  asOf: string;
  caveats: string[];
}

const CONTACT_LEAD: Record<string, string> = {
  general: "For anything about your account, your unit, or the association.",
  management: "The manager's mail: repairs, questions, and requests.",
  board: "The board of directors. Have something that can't wait until open forum?",
  architectural: "Architectural review: changes to your unit's exterior.",
};

/** The association's public owner page, read from `/api/community-profile`: the brand's surface layer (`data-reach="full"`),
 * the hero, how to reach the association, the records on file, the calendar, and the footer. Every fact on it comes from
 * the loader; a field the profile leaves empty shows nothing. */
export function OwnerPageView() {
  const r = useApi<CommunityProfile>("/api/community-profile");
  return (
    <RemoteView r={r}>
      {(p) => {
        const legal = p.name || p.corporateName;
        const pages = p.pages.filter((x) => x.url || x.path);
        const onFile = p.records.kinds.filter((k) => k.onFile);
        return (
          <div className="owner-page" data-reach="full">
            {pages.length > 0 && (
              <nav aria-label="Site" className="op-nav">
                {pages.map((x) => (
                  <a key={x.page} href={x.url || x.path} target={x.url ? "_blank" : undefined} rel={x.url ? "noreferrer" : undefined}>{x.label}</a>
                ))}
              </nav>
            )}
            <section className="op-hero">
              <div className="stack">
                {legal && <p className="op-kicker">{legal}</p>}
                <h1 className="brand">{p.wordmark || legal || "Owner page"}</h1>
                <p className="op-lead">The association's records, how to reach it, and what the law asks it to disclose, read by jason from its records.</p>
                {p.site && <p><a className="op-button" href={p.site} target="_blank" rel="noreferrer">The association's site</a></p>}
              </div>
              {p.mailing.length > 0 && (
                <div className="op-box">
                  <p className="op-box-label">Write to the association</p>
                  {p.mailing.map((m) => <p key={m.label}>{m.label}{m.zip ? ` ${m.zip}` : ""}</p>)}
                </div>
              )}
            </section>

            {p.contacts.length > 0 && (
              <section className="stack">
                <h2 className="brand">Reach the association</h2>
                <div className="grid-3">
                  {p.contacts.map((c) => (
                    <Card key={c.email} title={c.label}>
                      <p className="muted">{CONTACT_LEAD[c.kind] ?? c.purpose}</p>
                      <a href={`mailto:${c.email}`}><strong>{c.email}</strong></a>
                    </Card>
                  ))}
                </div>
              </section>
            )}

            <section className="stack">
              <h2 className="brand">From the association's records</h2>
              <div className="stats">
                <Stat label="Records on file" value={p.records.total ? `${p.records.onFile} of ${p.records.total}` : "—"} hint="Civil Code 5200 kinds" />
                {p.asOf && <Stat label="Read as of" value={p.asOf} hint="from jason's stores" />}
              </div>
              {p.records.note && <p className="muted">{p.records.note}</p>}
              {p.records.kinds.length > 0 && (
                <Card title="Records members may inspect (CIV 5205)">
                  <ul className="op-records">
                    {p.records.kinds.map((k) => (
                      <li key={k.record}>
                        <span>{k.meaning || k.record.replace(/_/g, " ")} <span className="muted">{k.citation}</span></span>
                        <Badge tone={k.onFile ? "good" : "neutral"}>{k.onFile ? "on file" : "not on file"}</Badge>
                      </li>
                    ))}
                  </ul>
                  <p className="muted">{onFile.length} of {p.records.kinds.length} on file. Ask for any of them in writing; the association answers within the time Civil Code 5210 sets.</p>
                </Card>
              )}
            </section>

            {p.calendarId && (
              <section className="stack">
                <h2 className="brand">Calendar</h2>
                <Embed a={{ kind: "calendar", ref: p.calendarId, title: `${legal || "Association"} calendar`, opts: { mode: "AGENDA", tz: p.timeZone || undefined } }} height={400} load="mount" />
              </section>
            )}

            <footer className="op-foot">
              <blockquote className="brand">
                “…association records, and any information from them, may not be sold, used for a commercial purpose, or used for any other purpose not reasonably related to a member's interest as a member.”
                <span className="muted">(Civ. Code § 5230)</span>
              </blockquote>
              <Caveats items={p.caveats} />
              {legal && <p className="muted">{legal}{p.corporateName && p.corporateName !== legal ? ` (${p.corporateName})` : ""}</p>}
            </footer>
          </div>
        );
      }}
    </RemoteView>
  );
}
