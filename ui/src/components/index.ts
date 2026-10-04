export { AppShell } from "./AppShell";
export { Badge, type Tone } from "./Badge";
export { Card } from "./Card";
export { Caveats } from "./Caveats";
export { Clock, type ClockStage } from "./Clock";
export { Command } from "./Command";
export { Embed, embedUrls, googleId, type Attachment, type EmbedKind } from "./Embed";
export { Markdown, setMermaidUrl } from "./Markdown";
export { Confirm } from "./Confirm";
export { ConfirmList, type ConfirmRow } from "./ConfirmList";
export { DataTable, type Column } from "./DataTable";
export { DecisionCard, OUTCOMES, type DecisionDraft } from "./DecisionCard";
export { DueDate, daysUntil } from "./DueDate";
export { Evidence, EvidencePanel, EvidenceVersion, evidenceUrl, refreshAllEvidence, refreshEvidence, RefreshAllEvidence, RereadIcon, type EvidenceRefreshAll, type EvidenceRefreshable, type EvidenceRefreshed, type EvidenceRefreshRequest, type EvidenceAnswer, type EvidenceSource, type EvidenceField, type EvidenceRefresh, type EvidenceKind } from "./Evidence";
export { DocumentViewer, viewDocument, humanSize, documentKindWord, looksLikeMarkdown, type DocumentView, type DocumentViewRequest, type DocumentSubmission, type SubmissionQuestion, type SubmissionRowKind, type EvidenceDocument, type EvidenceDocumentKind } from "./DocumentViewer";
export { Findings } from "./Findings";
export { Kanban } from "./Kanban";
export { Money } from "./Money";
export { Pill } from "./Pill";
export { RegisterGrid } from "./RegisterGrid";
export { RemoteView } from "./Remote";
export { RollCall, tally, outcome, VOTE_WORDS, type VoteWord, type Threshold, type Outcome, type OutcomeOptions } from "./RollCall";
export { SearchBox } from "./SearchBox";
export { Stat } from "./Stat";
export { EmptyState, ErrorNotice, Loading } from "./States";
export { Tabs, type TabSpec } from "./Tabs";
export { Timeline, type TimelineEvent } from "./Timeline";
// Console build (design handoff 2026-10-03): one line per file, each owned by the agent that builds it.
export { DraftLetter, STAGE_BADGE, letterText, type Letter, type LetterLog, type Stage, type StageAction, type StageBody } from "./DraftLetter";
export { ApprovalsInbox, groupLetters, type InboxGroup } from "./ApprovalsInbox";
export { Checklist, type ChecklistItem } from "./Checklist";
export { DecisionBrief, BRIEF_FOOTER, type Brief, type BriefOption } from "./DecisionBrief";
export { AgendaWizard, ReadinessRow, addMinutes, clock, type AgendaPlan, type AgendaCandidate, type PlanBody, type ReadinessCheck } from "./AgendaWizard";
export { DriveAttach, type DriveFile } from "./DriveAttach";
export { MeetingStage, HostPanel, COMMON_MOTIONS, OFF_AGENDA_LABELS, minutesLetter, motionFor, packetFrame, type AgendaItem, type HostPanelProps, type MeetingRoomData, type MeetingStageProps, type MinutesLetter, type Motion, type PacketFile, type RoomAction, type RoomRecord, type StageContent } from "./MeetingStage";
export { DockToolbar, Drawer, DockDrawerBody, DOCK_DRAWERS, useDockCounts, dockWrite, screenLabel, DOCK_EVENT, type DockAction } from "./Dock";
export { DeadlineList } from "./DeadlineList";
export { ActionRegister } from "./ActionRegister";
export { Scratchpad } from "./Scratchpad";
export { AskPanel } from "./AskPanel";
export { BoardFields, type BoardFieldsItem } from "./BoardFields";
export { RequestForm, DELIVERIES, type RequestKind, type RecordedRequest, type Delivery } from "./RequestForm";
export { ConsoleShell, ScreenHeader, visibleScreens, OWNER_BANNER, type ConsoleScreen, type ConsoleShellProps, type Audience } from "./ConsoleShell";
// Approvals engine (jason.approvals): the engine's JSON in, no mapping layer. lib/approvals.ts has the types and rules.
export { PlanReview, PLAN_CAVEATS } from "./PlanReview";
export { WriteRow } from "./WriteRow";
export { HeldNote } from "./HeldNote";
export { ChangedBanner } from "./ChangedBanner";
export { ApproveBar } from "./ApproveBar";
export { SecondConfirm } from "./SecondConfirm";
export { CostLine } from "./CostLine";
export { ApplyResult } from "./ApplyResult";
export { Recitation, type Citation, type RecitedTerm } from "./Recitation";
export { ReadingLabel, type Whose } from "./ReadingLabel";
export { AuditLog, auditWords } from "./AuditLog";
export { QuestionCard, unblocksText, type Question, type Unblocks, type Answered } from "./QuestionCard";
export { StageSteps, type StageGate } from "./StageSteps";
export { KeyDocuments, Day, type KeyDocumentsData, type KeyGroup, type KeyEntry, type KeyCopy, type KeyLink, type KeyLead, type KeyStatusWord } from "./KeyDocuments";
export { InstrumentGraph, OwnerNames, layout as instrumentGraphLayout, type InstrumentGraphData, type GraphNode, type GraphEdge, type GraphCycle, type Provenance } from "./InstrumentGraph";
export { AssociationPicker } from "./AssociationPicker";
export { DocumentLocator, LocatedDocuments, BoardList, TieBadge } from "./DocumentLocator";
export type { AssociationChoice, DirectoryRow, Directory as AssociationDirectory, LocatedDoc, LocatedItem, Location as DocumentLocation, LocationResult, NotLocated } from "../lib/discovery";
export {
  cleanName, sameName, isJason, signerProblem, personName, tally as approvalTally, needsSecond, staleness, waitsOn, decisionProblem, groupItems, changeText,
  type Approval, type ApprovalStatus, type PlanItem, type ItemClass, type ItemDecision, type ItemResult, type Change, type EvidenceRef,
  type DecisionRecord, type Signature, type AuditEntry, type AuditEvent, type ChainCheck, type ChangedItem, type Recheck,
  type DecideBody, type SignBody, type DecisionWord, type Staleness,
} from "../lib/approvals";
