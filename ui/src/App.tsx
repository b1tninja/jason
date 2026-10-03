import { AppShell, Card, ErrorNotice, Loading } from "./components";
import { DigestView, type Digest } from "./DigestView";
import { useApi } from "./lib/useApi";
import { useHash } from "./lib/useHash";
import { AssociationRecordsView } from "./views/AssociationRecordsView";
import { BoardItemsView } from "./views/BoardItemsView";
import { BooksChecksView } from "./views/BooksChecksView";
import { JobsView } from "./views/JobsView";
import { LegalView } from "./views/LegalView";
import { CalendarView } from "./views/CalendarView";
import { CanvasesView } from "./views/CanvasesView";
import { DraftsView } from "./views/DraftsView";
import { DutiesView } from "./views/DutiesView";
import { HearingsView } from "./views/HearingsView";
import { InboxView } from "./views/InboxView";
import { ReservesView } from "./views/ReservesView";
import { TemplatesView } from "./views/TemplatesView";
import { TitleWatchView } from "./views/TitleWatchView";
import { InsuranceView } from "./views/InsuranceView";
import { MeetingsView } from "./views/MeetingsView";
import { MoneyView } from "./views/MoneyView";
import { IngestionView } from "./views/IngestionView";
import { LeadsView } from "./views/LeadsView";

function BoardDigest() {
  const r = useApi<Digest>("/api/board-digest");
  if (r.status === "loading") return <Loading />;
  if (r.status === "error") return <ErrorNotice error={r.error} onRetry={r.reload} />;
  return <DigestView digest={r.data} />;
}

function Status() {
  const r = useApi<{ ok: boolean; ui: boolean; sources: string[]; writes: string[] }>("/api/health");
  if (r.status === "loading") return <Loading />;
  if (r.status === "error") return <ErrorNotice error={r.error} onRetry={r.reload} />;
  return (
    <Card title="Server">
      <p>Sources: {r.data.sources.join(", ") || "none"}</p>
      <p>Writes: {r.data.writes.join(", ") || "none"}</p>
    </Card>
  );
}

const VIEWS: { id: string; label: string; view: () => JSX.Element }[] = [
  { id: "digest", label: "Digest", view: BoardDigest },
  { id: "duties", label: "Duties", view: DutiesView },
  { id: "inbox", label: "Inbox", view: InboxView },
  { id: "drafts", label: "Drafts", view: DraftsView },
  { id: "canvases", label: "Canvases", view: CanvasesView },
  { id: "templates", label: "Templates", view: TemplatesView },
  { id: "calendar", label: "Deadlines", view: CalendarView },
  { id: "money", label: "Money", view: MoneyView },
  { id: "meetings", label: "Meetings", view: MeetingsView },
  { id: "insurance", label: "Insurance", view: InsuranceView },
  { id: "reserves", label: "Reserves", view: ReservesView },
  { id: "title", label: "Title watch", view: TitleWatchView },
  { id: "hearings", label: "Hearings", view: HearingsView },
  { id: "books", label: "Books checks", view: BooksChecksView },
  { id: "legal", label: "Legal", view: LegalView },
  { id: "jobs", label: "Jobs", view: JobsView },
  { id: "board", label: "Board items", view: BoardItemsView },
  { id: "records", label: "Association records", view: AssociationRecordsView },
  { id: "ingestion", label: "Document ingestion", view: IngestionView },
  { id: "leads", label: "Leads", view: LeadsView },
  { id: "status", label: "Status", view: Status },
];

export function App() {
  const [hash, go] = useHash("digest");
  const current = VIEWS.find((v) => v.id === hash.split("/")[0]) ?? VIEWS[0];
  const View = current.view;
  return (
    <AppShell
      title="Jason"
      nav={
        <nav className="nav">
          {VIEWS.map((v) => (
            <a key={v.id} href={`#/${v.id}`} aria-current={v.id === current.id ? "page" : undefined} onClick={(e) => { e.preventDefault(); go(v.id); }}>
              {v.label}
            </a>
          ))}
        </nav>
      }
    >
      <View />
    </AppShell>
  );
}
