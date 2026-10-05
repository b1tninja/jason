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
export { EvidenceEntries } from "./EvidenceEntries";
export { DocumentViewer, CONFIDENTIAL_LINE, recordingLength, isConfidential, viewDocument, humanSize, documentKindWord, looksLikeMarkdown, type DocumentView, type DocumentViewRequest, type DocumentSubmission, type SubmissionQuestion, type SubmissionRowKind, type EvidenceDocument, type EvidenceDocumentKind } from "./DocumentViewer";
export { DrivePreview, ReadAllFromDrive, CHANGED_IN_DRIVE, DRIVE_COPY, copyDay, driveAddress, driveIdOf, googleLink, refreshManyEvidence, type DriveKind, type EvidenceRefreshMany } from "./DrivePreview";
export { DocumentPreview, LocalPreview, DRIVE_COPY_LABEL, RECORDED_COPY, attachedCopies, fileAddress, thumbUrl } from "./DocumentPreview";
export { Doc, DocList, DOC_WORDS, asEvidenceDocument, documentRef, driveThumbUrl, firstDocument, rowRegionName, type DocProps, type DocStatic, type DocVariant } from "./Doc";
export { DOC_KIND_WORD, addressScheme, docKindWord, driveDocRef, driveIdOfAddress, fileDocRef, isDocRef, isRestricted, pathOfAddress, type DocKind, type DocLevel, type DocRef, type EvidenceEntry } from "../lib/docref";
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
export { MeetingStage, HostPanel, COMMON_MOTIONS, MEMBERS_PACKET_LINE, OFF_AGENDA_LABELS, minutesLetter, motionFor, packetFrame, type PacketCopy, type AgendaItem, type HostPanelProps, type MeetingRoomData, type MeetingStageProps, type MinutesLetter, type Motion, type PacketFile, type RoomAction, type RoomRecord, type StageContent } from "./MeetingStage";
export { DockToolbar, Drawer, DockDrawerBody, DOCK_DRAWERS, useDockCounts, dockWrite, screenLabel, DOCK_EVENT, type DockAction } from "./Dock";
export { DeadlineList } from "./DeadlineList";
export { ActionRegister } from "./ActionRegister";
export { Scratchpad } from "./Scratchpad";
export { AskPanel } from "./AskPanel";
export { BoardFields, type BoardFieldsItem } from "./BoardFields";
export { RequestForm, DELIVERIES, type RequestKind, type RecordedRequest, type Delivery } from "./RequestForm";
export { ConsoleShell, ScreenHeader, visibleScreens, landingScreen, DEFAULT_LANDING, OWNER_BANNER, type ConsoleScreen, type ConsoleShellProps, type Audience, type Role, type Move } from "./ConsoleShell";
export { PrivateSwitch, PrivateAsk, PrivateBand, PRIVATE_MINUTES, PRIVATE_DEFAULT, PRIVATE_HINT, clockTime, minutesLeft, type PrivateSwitchProps, type PrivateBandProps } from "./PrivateSwitch";
export type { PrivateView, PrivateOpenBody } from "../lib/api";
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
// The marks (handoff-reconciliation.md, the visual system): glyphs, a person's stamps, jason's seals, routing tags.
export { Glyph, GLYPHS, GLYPH_META, JASON_GLYPH_NAMES, LUCIDE_VERSION, hasGlyph, strokeFor, type GlyphMeta, type GlyphName, type GlyphProps } from "./Glyph";
export { Stamp, type StampProps } from "./Stamp";
export { Seal, type SealProps } from "./Seal";
export { RoutingTag, RoutingTags, type RoutingTagProps } from "./RoutingTag";
export { STAMP_WORDS, SEAL_WORDS, SEAL_STATE_WORDS, NOT_A_MARK, ROLE_GLYPH, UNASSIGNED, isStampWord, isSealWord, roleWords, type StampWord, type StampTone, type SealWord, type SealState, type RoutingOwner } from "../lib/marks";
export { glyphForStatus } from "../lib/statusGlyph";
// Paint (docs/console/screens/paint.md): the palette, a color's detail, and a date with its source. Props only.
export { Swatch, PAINT_STATUS_WORDS, ENTERED_WORD, inkFor, luminance, contrastRatio, parseHex, swatchWord, driftText, type PaintColor, type SwatchSize } from "./Swatch";
export { PaletteMatrix, PAINT_CAPTION, NO_SCHEDULE, NO_PAINT_ROW, ageInDays, copyAge, drift as paintDrift, type PaintSchedule } from "./PaletteMatrix";
export { ColorDetail, TOUCH_UP_CAVEAT, NO_DESCRIPTION, type PaintColorDetail } from "./ColorDetail";
export { SourcedDate, NEEDS_INPUT_INVITATION, dateText as sourcedDateText } from "./SourcedDate";
