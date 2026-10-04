import { useEffect, useState } from "react";
import {
  Card, ConsoleShell, DOCK_DRAWERS, DockDrawerBody, DockToolbar, Drawer, ErrorNotice, Loading, useDockCounts, visibleScreens,
  type Audience, type ConsoleScreen,
} from "./components";
import { DigestView, type Digest } from "./DigestView";
import { useApi } from "./lib/useApi";
import { useHash } from "./lib/useHash";
import { privateActs, useSession } from "./lib/session";
import { useTheme } from "./lib/theme";
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
import { MeetingView } from "./views/MeetingView";
import { CommunitiesView, OnboardingView } from "./views/OnboardingView";
import { OwnerInfoView } from "./views/OwnerInfoView";
import { RuleChangeView } from "./views/RuleChangeView";
import { RegistersView } from "./views/RegistersView";
import { DelinquencyView } from "./views/DelinquencyView";
import { MinutesReviewView } from "./views/MinutesReviewView";
import { InsuranceRenewalsView } from "./views/InsuranceRenewalsView";
import { ReserveFindingsView } from "./views/ReserveFindingsView";
import { RecordsRequestsView } from "./views/RecordsRequestsView";
import { MailTriageView } from "./views/MailTriageView";
import { MeetingsView } from "./views/MeetingsView";
import { MoneyView } from "./views/MoneyView";
import { IngestionView } from "./views/IngestionView";
import { LeadsView } from "./views/LeadsView";
import { ApprovalsView } from "./views/ApprovalsView";
import { DecisionsView } from "./views/DecisionsView";
import { PlanMeetingView } from "./views/PlanMeetingView";
import { MeetingRoomView } from "./views/MeetingRoomView";
import { OwnerPageView } from "./views/OwnerPageView";

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

export const GROUPS = ["Overview", "Governance", "Money", "Records"] as const;

interface ScreenDef extends ConsoleScreen {
  view: (p: { audience: Audience }) => JSX.Element;
  /** Older hash ids that still land here. */
  aliases?: string[];
}

/** Every screen, grouped as the console's nav shows them. `owner` marks what an owner sees. */
export const SCREENS: ScreenDef[] = [
  // Overview
  { id: "digest", label: "Board digest", ownerLabel: "Overview", group: "Overview", owner: true, view: () => <BoardDigest /> },
  { id: "approvals", label: "Approvals", group: "Overview", view: () => <ApprovalsView /> },
  { id: "duties", label: "Duties by cadence", group: "Overview", view: () => <DutiesView /> },
  { id: "inbox", label: "Inbox", group: "Overview", view: () => <InboxView /> },
  { id: "mail-triage", label: "Mail triage", group: "Overview", view: () => <MailTriageView /> },
  { id: "drafts", label: "Drafts", group: "Overview", view: () => <DraftsView /> },
  { id: "leads", label: "Leads", group: "Overview", view: () => <LeadsView /> },
  { id: "jobs", label: "Jobs", group: "Overview", view: () => <JobsView /> },
  { id: "communities", label: "Communities", group: "Overview", view: () => <CommunitiesView /> },
  { id: "onboarding", label: "Onboarding", group: "Overview", view: () => <OnboardingView /> },
  { id: "status", label: "Status", group: "Overview", view: () => <Status /> },
  // Governance
  { id: "actions", label: "Board action items", group: "Governance", aliases: ["board"], view: () => <BoardItemsView /> },
  { id: "decisions", label: "Decisions", group: "Governance", view: () => <DecisionsView /> },
  { id: "agenda", label: "Plan a meeting", group: "Governance", view: () => <PlanMeetingView /> },
  { id: "room", label: "Meeting room", ownerLabel: "Live meeting", group: "Governance", owner: true, view: () => <MeetingRoomView /> },
  { id: "meetings", label: "Meetings and minutes", group: "Governance", owner: true, view: () => <MeetingsView /> },
  { id: "meeting", label: "Next meeting", group: "Governance", view: () => <MeetingView /> },
  { id: "minutes-review", label: "Minutes review", group: "Governance", view: () => <MinutesReviewView /> },
  { id: "disclosures", label: "Annual disclosures", group: "Governance", owner: true, aliases: ["calendar"], view: () => <CalendarView /> },
  { id: "rules", label: "Rule changes", group: "Governance", view: () => <RuleChangeView /> },
  { id: "hearings", label: "Hearings", group: "Governance", view: () => <HearingsView /> },
  { id: "owner-info", label: "Owner information", group: "Governance", view: () => <OwnerInfoView /> },
  { id: "canvases", label: "Canvases", group: "Governance", view: () => <CanvasesView /> },
  { id: "templates", label: "Templates", group: "Governance", view: () => <TemplatesView /> },
  { id: "registers", label: "Registers", group: "Governance", view: () => <RegistersView /> },
  // Money
  { id: "payments", label: "Payments with questions", group: "Money", aliases: ["money"], view: () => <MoneyView /> },
  { id: "reserves", label: "Reserves and budget", group: "Money", owner: true, view: () => <ReservesView /> },
  { id: "reserve-findings", label: "Reserve findings", group: "Money", view: () => <ReserveFindingsView /> },
  { id: "liens", label: "Liens and delinquency", group: "Money", aliases: ["delinquency"], view: () => <DelinquencyView /> },
  { id: "books", label: "Books checks", group: "Money", view: () => <BooksChecksView /> },
  { id: "title", label: "Title watch", group: "Money", view: () => <TitleWatchView /> },
  // Records
  { id: "records", label: "Records (CIV 5200)", group: "Records", owner: true, view: () => <AssociationRecordsView /> },
  { id: "records-requests", label: "Records requests", ownerLabel: "Request a record", group: "Records", owner: true, view: ({ audience }) => <RecordsRequestsView audience={audience} /> },
  { id: "insurance", label: "Insurance", group: "Records", owner: true, view: () => <InsuranceView /> },
  { id: "renewals", label: "Insurance renewals", group: "Records", view: () => <InsuranceRenewalsView /> },
  { id: "legal", label: "Legal", group: "Records", view: () => <LegalView /> },
  { id: "ingestion", label: "Document ingestion", group: "Records", view: () => <IngestionView /> },
  { id: "owner-page", label: "Owner page", group: "Records", owner: true, view: () => <OwnerPageView /> },
];

/** The screen a hash id names, through its aliases. */
export function findScreen(id: string): ScreenDef | undefined {
  return SCREENS.find((s) => s.id === id || s.aliases?.includes(id));
}

const DOCK_WIDE = 1200;

function useWide(): boolean {
  const read = () => typeof window !== "undefined" && window.innerWidth >= DOCK_WIDE;
  const [wide, setWide] = useState(read);
  useEffect(() => {
    const on = () => setWide(read());
    window.addEventListener("resize", on);
    return () => window.removeEventListener("resize", on);
  }, []);
  return wide;
}

/** The console. The hash is `#/<screen>` with `?view=owner` for the owner view, so a shared link lands on the same screen
 * as the same audience. Old ids (`board`, `calendar`, `money`, `delinquency`) still land. */
export function App() {
  const [hash] = useHash("digest");
  const [rawId, query = ""] = hash.split("?");
  const [audience, setAudienceState] = useState<Audience>(() => (new URLSearchParams(query).get("view") === "owner" ? "owner" : "board"));
  const theme = useTheme();
  const session = useSession();
  const approvals = useApi<{ pending?: number }>("/api/approvals");
  const pending = approvals.status === "ready" ? approvals.data.pending ?? 0 : 0;
  const counts = useDockCounts();
  const wide = useWide();
  const [drawer, setDrawer] = useState<string | null>(null);
  const [pinned, setPinned] = useState(false);

  const visible = visibleScreens(SCREENS, audience) as ScreenDef[];
  const found = findScreen(rawId.split("/")[0]);
  const current = found && visible.some((s) => s.id === found.id) ? found : (visible[0] as ScreenDef);

  const navigate = (id: string, a: Audience) => { window.location.hash = `/${id}${a === "owner" ? "?view=owner" : ""}`; };
  const go = (id: string) => {
    navigate(id, audience);
    if (!(pinned && wide)) setDrawer(null); // a floating drawer closes on navigation; a pinned one stays
    try { window.scrollTo(0, 0); } catch { /* not every window scrolls */ }
  };
  const setAudience = (a: Audience) => {
    setAudienceState(a);
    const next = SCREENS.filter((s) => a === "board" || s.owner).some((s) => s.id === current.id) ? current.id : "digest";
    navigate(next, a);
    if (a === "owner" && drawer && !DOCK_DRAWERS.find((d) => d.id === drawer)?.owner) setDrawer(null);
  };

  const screens: ConsoleScreen[] = SCREENS.map(({ view: _view, aliases: _aliases, ...s }) => (s.id === "approvals" ? { ...s, count: pending } : s));
  const View = current.view;
  const drawerDef = drawer ? DOCK_DRAWERS.find((d) => d.id === drawer) : undefined;
  const drawerNode = drawerDef && (
    <Drawer id={drawerDef.id} title={drawerDef.title} pinned={pinned && wide} canDock={wide} onPin={() => setPinned(true)} onUnpin={() => setPinned(false)} onClose={() => setDrawer(null)}>
      <DockDrawerBody id={drawerDef.id} go={go} me={session.me} />
    </Drawer>
  );

  return (
    <ConsoleShell
      wordmark={theme?.found ? theme.wordmark : "jason"}
      legal={theme?.found ? "" : "Board console"}
      groups={GROUPS}
      screens={screens}
      current={current.id}
      onGo={go}
      audience={audience}
      onAudience={setAudience}
      session={{ me: session.me, setMe: session.setMe, people: session.people, account: session.account,
                 signInLinks: session.signInLinks, signInError: session.signInError, onSignOut: () => { void session.signOut(); },
                 actAs: session.canActAs ? {
                   people: session.actAsPeople, roles: session.actAsRoles, acting: session.acting,
                   // every screen reads who is viewing from the server's session, so a change reloads the page
                   onChange: (t) => { void session.actAs(t).then(() => window.location.reload()); },
                 } : undefined,
                 // the screens fetch on load, so opening, closing, and expiry each reload the page (privateActs)
                 privateView: session.privateView ? {
                   view: session.privateView, onOpen: privateActs.open, onClose: privateActs.close,
                   onExpired: privateActs.expired, focus: session.privateFocus,
                 } : undefined }}
      dock={<DockToolbar open={drawer} onToggle={(id) => setDrawer((d) => (d === id ? null : id))} counts={counts} audience={audience} />}
      pinned={pinned && wide ? drawerNode : undefined}
      floating={!(pinned && wide) ? drawerNode : undefined}
    >
      <View audience={audience} />
    </ConsoleShell>
  );
}
