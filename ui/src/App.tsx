import { useEffect, useState } from "react";
import {
  ConsoleShell, DOCK_DRAWERS, DockDrawerBody, DockToolbar, Drawer, ErrorNotice, Loading, landingScreen, useDockCounts, visibleScreens,
  type Audience, type ConsoleScreen,
} from "./components";
import { roleMoves, roleOf } from "./lib/roles";
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
import { OwnerDigestView } from "./views/OwnerDigestView";
import { PeopleView } from "./views/PeopleView";
import { StatusView } from "./views/StatusView";

function BoardDigest() {
  const r = useApi<Digest>("/api/board-digest");
  if (r.status === "loading") return <Loading />;
  if (r.status === "error") return <ErrorNotice error={r.error} onRetry={r.reload} />;
  return <DigestView digest={r.data} />;
}

export const GROUPS = ["Overview", "Governance", "Money", "Records"] as const;

interface ScreenDef extends ConsoleScreen {
  view: (p: { audience: Audience }) => JSX.Element;
  /** Older hash ids that still land here. */
  aliases?: string[];
  /** Hash ids that land here in the owner view (a board screen's id an owner link once named). */
  ownerAliases?: string[];
  /** One of jason's admins only, viewing as themselves (the server refuses anyone else; the nav follows it). */
  admin?: boolean;
}

/** Whether the session is one of jason's admins as themselves: the administrator's role, or an admin who also holds an
 * office. Never in the owner view, and never while an admin views the console as someone else. */
export function adminSession(s: { account?: { admin?: boolean } | null; acting?: unknown }, role: string | undefined, audience: Audience): boolean {
  return audience !== "owner" && !s.acting && (role === "administrator" || !!s.account?.admin);
}

/** Every screen, grouped as the console's nav shows them. `owner` marks what an owner sees: each such screen reads only
 * the sources `ownerScreens.json` names for it, and in the owner view the server answers them from the owner loaders
 * (`jason.web.extra.owner_view`). The owner view shows what a member is entitled to: open-session meetings and minutes,
 * the annual disclosures and the summaries they carry, and the records request form. Never the board's digest, the
 * document library, delinquency, liens, discipline, or another owner's facts. */
export const SCREENS: ScreenDef[] = [
  // Overview
  { id: "digest", label: "Board digest", ownerLabel: "Overview", group: "Overview", owner: true,
    view: ({ audience }) => (audience === "owner" ? <OwnerDigestView /> : <BoardDigest />) },
  { id: "approvals", label: "Approvals", group: "Overview", view: () => <ApprovalsView /> },
  { id: "duties", label: "Duties by cadence", group: "Overview", view: () => <DutiesView /> },
  { id: "inbox", label: "Inbox", group: "Overview", view: () => <InboxView /> },
  { id: "mail-triage", label: "Mail triage", group: "Overview", view: () => <MailTriageView /> },
  { id: "drafts", label: "Drafts", group: "Overview", view: () => <DraftsView /> },
  { id: "leads", label: "Leads", group: "Overview", view: () => <LeadsView /> },
  { id: "jobs", label: "Jobs", group: "Overview", view: () => <JobsView /> },
  { id: "communities", label: "Communities", group: "Overview", view: () => <CommunitiesView /> },
  { id: "onboarding", label: "Onboarding", group: "Overview", view: () => <OnboardingView /> },
  // The administrator's landing: sources, sign-ins, setup's gates, failures (GET /api/status, an admin only).
  { id: "status", label: "Status", group: "Overview", admin: true, view: () => <StatusView /> },
  // Governance
  { id: "actions", label: "Board action items", group: "Governance", aliases: ["board"], view: () => <BoardItemsView /> },
  { id: "decisions", label: "Decisions", group: "Governance", roles: ["officer", "administrator"], view: () => <DecisionsView /> },
  { id: "agenda", label: "Plan a meeting", group: "Governance", view: () => <PlanMeetingView /> },
  { id: "room", label: "Meeting room", ownerLabel: "Live meeting", group: "Governance", owner: true, view: ({ audience }) => <MeetingRoomView audience={audience} /> },
  { id: "meetings", label: "Meetings and minutes", group: "Governance", owner: true, view: ({ audience }) => <MeetingsView audience={audience} /> },
  { id: "meeting", label: "Next meeting", group: "Governance", view: () => <MeetingView /> },
  { id: "minutes-review", label: "Minutes review", group: "Governance", view: () => <MinutesReviewView /> },
  { id: "disclosures", label: "Annual disclosures", group: "Governance", owner: true, aliases: ["calendar"], view: ({ audience }) => <CalendarView audience={audience} /> },
  { id: "rules", label: "Rule changes", group: "Governance", view: () => <RuleChangeView /> },
  { id: "hearings", label: "Hearings", group: "Governance", view: () => <HearingsView /> },
  { id: "owner-info", label: "Owner information", group: "Governance", view: () => <OwnerInfoView /> },
  { id: "canvases", label: "Canvases", group: "Governance", view: () => <CanvasesView /> },
  { id: "templates", label: "Templates", group: "Governance", view: () => <TemplatesView /> },
  { id: "registers", label: "Registers", group: "Governance", view: () => <RegistersView /> },
  // Money
  { id: "payments", label: "Payments with questions", group: "Money", aliases: ["money"], view: () => <MoneyView /> },
  { id: "reserves", label: "Reserves and budget", group: "Money", owner: true, view: ({ audience }) => <ReservesView audience={audience} /> },
  { id: "reserve-findings", label: "Reserve findings", group: "Money", view: () => <ReserveFindingsView /> },
  { id: "liens", label: "Liens and delinquency", group: "Money", aliases: ["delinquency"], view: () => <DelinquencyView /> },
  { id: "books", label: "Books checks", group: "Money", view: () => <BooksChecksView /> },
  { id: "title", label: "Title watch", group: "Money", view: () => <TitleWatchView /> },
  // Records
  // The board's records inventory and recorded instruments; an owner asks for records through the request form instead.
  { id: "records", label: "Records (CIV 5200)", group: "Records", view: () => <AssociationRecordsView /> },
  { id: "records-requests", label: "Records requests", ownerLabel: "Records", group: "Records", owner: true, ownerAliases: ["records"], view: ({ audience }) => <RecordsRequestsView audience={audience} /> },
  { id: "insurance", label: "Insurance", group: "Records", owner: true, view: ({ audience }) => <InsuranceView audience={audience} /> },
  { id: "renewals", label: "Insurance renewals", group: "Records", view: ({ audience }) => <InsuranceRenewalsView audience={audience} /> },
  { id: "legal", label: "Legal", group: "Records", view: () => <LegalView /> },
  { id: "ingestion", label: "Document ingestion", group: "Records", view: () => <IngestionView /> },
  { id: "owner-page", label: "Owner page", group: "Records", owner: true, view: () => <OwnerPageView /> },
  // Who holds each office, read-only; board only (no owner loader: the server refuses /api/people in the owner view).
  { id: "people", label: "People and offices", group: "Records", view: () => <PeopleView /> },
];

/** The screen a hash id names, through its aliases; in the owner view, an owner alias first. */
export function findScreen(id: string, audience: Audience = "board"): ScreenDef | undefined {
  const owned = audience === "owner" ? SCREENS.find((s) => s.ownerAliases?.includes(id)) : undefined;
  return owned ?? SCREENS.find((s) => s.id === id || s.aliases?.includes(id));
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
  const hashAudience: Audience = new URLSearchParams(query).get("view") === "owner" ? "owner" : "board";
  const [audience, setAudienceState] = useState<Audience>(hashAudience);
  // The hash is the audience's one source (the reads take `view=owner` from it, `forView`): a link followed or a hash
  // edited by hand moves the view with it.
  useEffect(() => setAudienceState(hashAudience), [hashAudience]);
  const theme = useTheme();
  const session = useSession();
  // The owner view reads no board source: no approvals count, no dock counts (the owner shows neither).
  const approvals = useApi<{ pending?: number; approvalsWaiting?: number }>(audience === "owner" ? "/api/approvals?view=owner" : "/api/approvals");
  const pending = approvals.status === "ready" ? approvals.data.pending ?? 0 : 0;
  // The engine's plans waiting on a person's decision, submission, or second signature (the server counts them) wait on
  // any named person, so they count for everyone beside the letters.
  const plansOpen = approvals.status === "ready" ? approvals.data.approvalsWaiting ?? 0 : 0;
  const counts = useDockCounts();
  const wide = useWide();
  const [drawer, setDrawer] = useState<string | null>(null);
  const [pinned, setPinned] = useState(false);

  // What the signed-in person is to the console, from the server: a manager does not see Decisions, an administrator
  // lands on Status. With none known the nav is filtered by the audience alone, as before roles. An admin-only screen
  // (Status) is in the nav only for one of jason's admins as themselves; the server refuses it to anyone else.
  const role = audience === "owner" ? undefined : roleOf(session.roleClass);
  const admin = adminSession(session, role, audience);
  const allowed = SCREENS.filter((s) => !s.admin || admin);
  const visible = visibleScreens(allowed, audience, role) as ScreenDef[];
  const found = findScreen(rawId.split("/")[0], audience);
  const current = found && visible.some((s) => s.id === found.id) ? found : (visible[0] as ScreenDef);

  const navigate = (id: string, a: Audience) => { window.location.hash = `/${id}${a === "owner" ? "?view=owner" : ""}`; };
  // A person who opens the console with no route in the address lands where their role does (an explicit link is kept).
  useEffect(() => {
    const start = role ? landingScreen(role) : undefined;
    if (start && !window.location.hash.replace(/^#\/?/, "") && allowed.some((s) => s.id === start)) navigate(start, "board");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [role]);
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

  // The Approvals badge: the letters waiting on this person's approval when signed in (the dock's counts), else everyone's,
  // plus the plans of writes waiting on a person.
  const waiting = (counts.scope === "mine" && typeof counts.approvals === "number" ? counts.approvals : pending) + plansOpen;
  const screens: ConsoleScreen[] = allowed.map(({ view: _view, aliases: _aliases, ...s }) => (s.id === "approvals" ? { ...s, count: waiting } : s));
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
      role={role}
      moves={role && session.account ? roleMoves(role, { approvals: counts.approvals, pending, tasks: counts.tasks, deadlines: counts.deadlines }, { go, openDrawer: (id) => setDrawer(id) }) : undefined}
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
      {/* keyed by the audience: switching views mounts the screen again, so it reads again as that view */}
      <View key={audience} audience={audience} />
    </ConsoleShell>
  );
}
