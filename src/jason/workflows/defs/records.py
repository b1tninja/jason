"""The general workflow definitions of the records family (docs/workflows/documents-records.md): taking a document, a folder,
a checklist, or an association in, and reading what is held. Pure data: it imports the engine's types and ``named_check`` and nothing else of jason.

The definitions, by key (ids are ``<key>.<n>``; the table's id is the ``n``, ``ST-1`` and ``ES-3b`` among them for the gates of
``onboard``, whose group prefix is also the step's ``group``):

- ``document-intake`` (D1 to D21), ``ingest`` (I0 to I9), ``record-slot`` (S1 to S12), ``split-document`` (P1 to P8),
- ``onboard`` (the five gates ST, IN, ES, OP, AD, and the change-of-manager branch CM, 36 steps),
- ``founding-documents`` (F1 to F6), ``key-document`` (K1 to K7), ``parcel-title`` (P-1 to P-5),
- ``careful-reading`` (C1 to C10), and ``records-production`` (M1 to M10), a held definition.

**Which steps are a person's.** The page's ``check`` and ``job`` steps are jason's reads and queued commands. The reads in
``jason.workflows.checks.records`` are registered, so the steps they answer are ``check`` steps (role jason): ``active-community``
(onboard ST-1), the five gate reads and ``onboard-checklist`` (onboard ST-7, IN-7, ES-7, OP-4, AD-4, AD-3), ``onboard-gates-read`` and
``record-slots-read`` (record-slot 12 and 1), ``ingest-gate`` (ingest 9), ``split-review`` (split-document 4), and
``key-document-status`` (key-document 1); round two added ``record-compare`` (record-slot 5), ``profile-own-facts`` (onboard ST-4),
``key-document-verified`` (key-document 5), ``scratch-room`` (careful-reading 1), and ``request-kinds-mapped`` (records-production 3).
The engine knows no job of this family (``readers.JOBS`` holds the owner-information
cycle's and the control's), so each remaining read or job here is a ``person`` step: a person runs the command shown and attests
it, with the record the step asks for. The step's ``why`` says which read or job it becomes, and ``WANTED`` lists every such name
(``check:NAME``, ``job:NAME``, ``plan:KIND``). No plan step: no approvals kind of this family is registered (the proposed
``local.*`` kinds are in ``WANTED``). A person's step cannot be jason's, so the role is the one who runs the command.

**Gates.** A gate is jason's reading of the checklist; the board decides what is done. Each gate step is a read: it passes when
the checklist's reading says the gate is open, and when it is closed it fails and lists the item keys it waits on, never a value.
The read does not pass the gate for the board, and nothing here records a board's decision.

**Roles.** A step the page gives to more than one office (``S or M``, ``M, S, any``) is ``anyone``. A second person (R) is
``anyone`` too: the engine has no ``second`` role on a step yet, and the server refuses the same name for the first and the
second. A decision is recorded by the secretary, never by whoever opened the run.

**Clocks.** A ``law`` clock is on a step only where the statute is on the shelf and the step cannot be skipped (a legal step
has no skip rule): the standing of an amendment (CIV 4270) and the records request's receipt, inspection period, withholding,
and production (CIV 5210, 5215). The membership list's timeframe (CIV 5210(b)(6) with Corp. Code 8330) is not a law clock
until counsel reads it. A handover has no stored deadline: its dates are the transition agreement's or a person's.

**Child runs.** ``spawns`` names a definition built here. The engine finishes a parent step when its child run is done, while
the page keeps a gate apart from its children: so every gate is its own step, read by jason, and no child
completes one.

**Privacy.** A subject is an opaque handle (a request, a document, a parcel, a collection), never a name, a unit, a path, or a
Drive id; a step title names no confidential kind. ``records-production`` withholds and redacts restricted kinds, so it is
held: outside the private view the Work backend shows it as "A records request" with its state, and nothing of the run.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable

from jason.workflows.readers import JOBS, named_check
from jason.workflows.types import (
    Choice, ClockBasis, ClockDef, DateSlot, Phase, Repeat, Role, SkipRule, StepDef, StepKind, Visibility, Workflow,
)

FAMILY = "records"

NAMED: tuple[str, ...] = (
    # reads (a ``check`` step once a read of this name is registered in ``readers.CHECKS``; the reads of
    # ``jason.workflows.checks.records`` are registered and are no longer listed)
    "check:designation-on-file", "check:document-kind-read", "check:parcel-strand-gaps", "check:quotes-verified",
    # queued commands (a ``job`` step once a job of this name is registered in ``readers.JOBS``)
    "job:chronology", "job:citations-scan", "job:conflict-leads", "job:county-lookup", "job:documents-locate",
    "job:index-build", "job:ingest-dry-run", "job:ingest-model", "job:ingest-park", "job:intake-scan", "job:inspections-read", "job:library-drive-sync",
    "job:library-ocr-suggestions", "job:living-build", "job:models-as-of", "job:parcel-gap-lookup", "job:parcel-history",
    "job:parcel-report", "job:preflight", "job:provisions-recite", "job:recorder-reading", "job:record-read",
    "job:review-run", "job:revisions-history", "job:rules-find", "job:segments", "job:split-read-back", "job:split-suggest",
    "job:sync-catalog", "job:vendor-reports",
    # plans (a ``plan`` step once the approvals kind is registered)
    "plan:local.ingest.apply", "plan:local.living.reread",
)
"""Every read, job, and plan kind that a ``person`` step's ``why`` says it becomes (``becomes()`` accepts only these). A test
keeps this list equal to the names the whys give."""

WANTED: tuple[str, ...] = tuple(w for w in NAMED if not (w.startswith("job:") and w[4:] in JOBS))
"""``NAMED`` less the jobs whose descriptor is registered (``jason.workflows.jobs``, ``jobs.READY``): what a step of this family
would use and that is not registered yet. A registered job's step stays a person's (its ``why`` still names the job); what is
left is the checks, the plan kinds, and the jobs that are not one jason command (``jobs.UNDESCRIBED``)."""

M, S, A = Role.MANAGER, Role.SECRETARY, Role.ADMINISTRATOR
ANY, JASON = Role.ANYONE, Role.JASON
P, W, D, B, C = StepKind.PERSON, StepKind.WAIT, StepKind.DECISION, StepKind.BRANCH, StepKind.CHECK

SKIP_M = SkipRule((Role.MANAGER,))
SKIP_ANY = SkipRule((Role.ANYONE,))
ITEM = Repeat.PER_ITEM


def becomes(kind: str, name: str) -> str:
    """The sentence a person-run step carries about what it becomes. The name must be in ``NAMED``."""
    key = f"{kind}:{name}"
    if key not in NAMED:
        raise ValueError(f"{key} is not in NAMED")
    article = {"check": "a check", "job": "a job", "plan": "a plan"}[kind]
    return (f"Becomes {article} step ({name}) when that {kind} is registered; until then a person runs the command shown "
            "and attests the result.")


def _maker(key: str) -> tuple[Callable[[str], str], Callable[..., StepDef]]:
    def sid(n: str) -> str:
        return f"{key}.{n}"

    def step(n: str, title: str, kind: StepKind, role: Role, needs: tuple[str, ...] = (), *, why: str,
             becomes_: tuple[str, str] | None = None, **more: Any) -> StepDef:
        text = why.strip()
        if becomes_ is not None:
            text = f"{text} {becomes(*becomes_)}"
        return StepDef(sid(n), title, kind, role=role, needs=tuple(sid(x) for x in needs), why=text, **more)

    return sid, step


def _phases(sid: Callable[[str], str], rows: tuple[tuple[str, str, tuple[str, ...]], ...]) -> tuple[Phase, ...]:
    return tuple(Phase(k, t, tuple(sid(n) for n in ns)) for k, t, ns in rows)


def _upto(first: int, last: int) -> tuple[str, ...]:
    return tuple(str(i) for i in range(first, last + 1))


# --- 1. document-intake ---------------------------------------------------------------------------------------------------

DI = "document-intake"


def document_intake() -> Workflow:
    """A governing document, amendment, rule, policy, or recorded instrument, from arrival to its lessons (section 2.1).
    The subject is a document handle (a library id, an entry, or an instrument number); nothing is read from its name."""
    sid, st = _maker(DI)
    steps = (
        st("1", "Bring the document in", P, M, why="Evidence is the library row and the catalog row with a hash; it is read again on each sync.",
           command="jason library; jason drive", sop=f"{DI}#1", record="the library row and the catalog row, by hash",
           becomes_=("job", "library-drive-sync")),
        st("2", "It has a kind", P, M, ("1",), why="The kind comes from a person, a name rule, a phrase rule, or a model; a miss stays a miss and parks a classify ask.",
           command="jason intake --scan", sop=f"{DI}#1", record="the kind and how it was found, or the parked classify ask",
           becomes_=("check", "document-kind-read")),
        st("3", "Say what it is", P, ANY, ("2",), why="A person-chosen kind outranks every rule; skipped, with a reason, when step 2 found the kind.",
           command="jason intake --answer ID N --by NAME", sop=f"{DI}#6", record="the ask and the kind chosen", skip=SKIP_ANY),
        st("4", "Read the recorded copy's index row", P, M, ("1",), why="The number, date, and stamp come from the county index; a read that fails is not 'none found'. Skipped for a draft not meant to record.",
           command="MCP recorder_search, recorder_detail", sop=f"{DI}#2", record="the number, date, and stamp read, or that the read failed",
           skip=SKIP_M, becomes_=("job", "recorder-reading")),
        st("5", "Establish its standing: draft, adopted, or recorded", P, ANY, ("4",),
           why="CIV 4270(a)(3): an amendment is effective after, among other things, it \"has been recorded in each county in which a portion of the common interest development is located.\" "
               "The answer names the minutes or the stamp; an amendment's adopted and recorded dates are pinned.",
           command="jason intake --answer ID TEXT --by NAME", sop=f"{DI}#2", record="the ask answered, naming the minutes or the stamp",
           clock=ClockDef(ClockBasis.LAW, cite="CIV 4270(a)(3)", label="an amendment takes effect when recorded")),
        st("6", "A different person confirms", P, ANY, ("5",), why="Refused for the same name, in any case or spacing; the engine has no second-person role on a step yet.",
           command="jason intake --confirm ID --by OTHER", sop=f"{DI}#2", record="the ask confirmed, and the confirmer"),
        st("7", "Add it to the living document and build", P, M, ("5", "6"), why="Built text, the applied and not-in-effect lists, and the before-words findings.",
           command="jason living KEY --fetch --working", sop=f"{DI}#3", record="the version built", skip=SKIP_M,
           becomes_=("job", "living-build")),
        st("8", "Preflight a bulk or scanned PDF", P, M, ("1",), why="A preflight record keyed by hash; the original is never touched. Skipped, with a reason, unless the file is scanned or bulk.",
           command="jason preflight FILE [--render --pdf] [--ocr] [--extract]", sop=f"{DI}#4", record="the preflight record, by hash",
           skip=SKIP_M, becomes_=("job", "preflight")),
        st("9", "Segment a file that holds more than one document", P, M, ("8",), why="Segments are page ranges with parents; the file is never split. A model run takes the GPU lane and fails fast on the preflight.",
           command="jason segments FILE [--model] [--write]", sop=f"{DI}#5", record="the segments written, as page ranges", skip=SKIP_M,
           becomes_=("job", "segments")),
        st("10", "Park every uncertainty", P, M, _upto(2, 9), why="Asks for the kind, an OCR reading, drift, a before-words difference, two readings that differ, or an orphaned note; re-run after each change.",
           command="jason intake --learn-channel; jason intake --scan [--model] [--vision]", sop=f"{DI}#6", record="the asks parked (a count)",
           becomes_=("job", "intake-scan")),
        st("11", "Answer the questions", P, ANY, ("10",), why="Each ask is answered with a name; a likely OCR reading is accepted only after a look. A secret is refused and nothing is stored.",
           command="jason intake --likely; jason intake --answer ID TEXT --by NAME; jason intake --accept-likely --by NAME", sop=f"{DI}#6",
           record="the asks answered (ids)"),
        st("12", "A second person confirms each high-stakes ask", P, ANY, ("11",), why="For standing, readings that differ, a before-words difference, and drift; a new answer clears a confirmation.",
           command="jason intake --confirm ID --by OTHER", sop=f"{DI}#6", record="the asks confirmed, and the confirmer"),
        st("13", "Write OCR suggestions beside scans with no working copy", P, M, ("10",), why="The raw text is unchanged; the model reads on the GPU lane or locally. Skipped, with a reason, when a working copy exists.",
           command="jason intake --library-ocr", sop=f"{DI}#7", record="the suggestions written (a count)", skip=SKIP_M,
           becomes_=("job", "library-ocr-suggestions")),
        st("14", "Apply the answers; build again", P, M, ("11", "12"), why="Terminal only: the transcriptions, person-chosen kinds, facts, and proposals are applied and the question count falls.",
           command="jason intake --apply; jason living KEY", sop=f"{DI}#8", record="what was applied, and the question count after"),
        st("15", "Switch to a better reading of a scanned base", P, M, ("14",), why="A dry run first (the section count close, no transcription unplaced, the word error rate falling); the switch needs a second person.",
           command="jason living KEY --reread cli; jason living KEY --use-reread cli --yes --by NAME", sop=f"{DI}#9",
           record="the dry run's result, and the second person who confirmed the switch", skip=SKIP_M,
           becomes_=("plan", "local.living.reread")),
        st("16", "Check what it changes against the law and the other documents", P, M, ("14",), why="Conflict leads, duties, and notice requirements; once per version, and each January with the law review (jason sop law-review).",
           command="jason conflicts --leads --document KEY", sop=f"{DI}#10", record="the leads read",
           clock=ClockDef(ClockBasis.DOCUMENTS, label="each January, with the law review"), becomes_=("job", "conflict-leads")),
        st("17", "Read each lead beside the statute", P, M, ("16",), why="A Conflict row is proposed as a patch, or a note says there is none; jason notes a conflict and never resolves one.",
           command="jason conflicts", sop=f"{DI}#10", record="a Conflict row proposed as a patch, or a note that there is none"),
        st("18", "Where two readings remain, the board asks counsel", D, S, ("17",), why="Held for the board; the secretary records its decision. Skipped, with a reason, unless step 17 marks a lead for counsel.",
           command="jason board", record="the board item, then the decision as recorded", skip=SKIP_M),
        st("19", "Read the citations, scoped to the document they mean", P, M, ("9",), why="Every ambiguous document is a question, never a pick; no citation moves to another document.",
           command="jason segments ID --write; jason cite --scan FILE; jason cite EXPR --in KEY --on DAY", sop=f"{DI}#11",
           record="each ambiguous citation held as a question", becomes_=("job", "citations-scan")),
        st("20", "Find the rule-making power and the rules on file", P, M, ("14",), why="A subject with rules and no named grant, or a grant with no rule, is a finding for the board, never an accusation. Skipped, with a reason, for a document that grants none.",
           command="jason rules --find --model; jason rules --subjects", sop=f"{DI}#12", record="the findings read", skip=SKIP_M,
           becomes_=("job", "rules-find")),
        st("21", "Record the lessons", P, M, _upto(1, 20), why="A lesson row, and the procedure step changed; a fixed lesson names its guard.",
           command="jason lessons --area governing", sop=f"{DI}#13", record="the lessons added, with their status"),
    )
    phases = _phases(sid, (
        ("bring-in", "Bring it in", _upto(1, 3)), ("standing", "Its standing", _upto(4, 6)), ("build", "Build and read", _upto(7, 9)),
        ("questions", "Questions", _upto(10, 15)), ("law", "Against the law", _upto(16, 20)), ("close", "Close", ("21",))))
    return Workflow(key=DI, title="Take a document in", family=FAMILY, subject="document", steps=steps, phases=phases, procedure=DI)


# --- 2. ingest --------------------------------------------------------------------------------------------------------------

IG = "ingest"


def ingest() -> Workflow:
    """A folder, zip, or Drive folder handed over, from arrival to the ingest gate (section 2.2). The subject is a source
    handle, never its path."""
    sid, st = _maker(IG)
    gate = ("glob:onboarding/ingest-*.json",)
    steps = (
        st("0", "The source arrives", W, M, why="The manager registers it: the source address and the hash list. The sender's date is the clock; a late arrival is flagged and never marked received.",
           clock=ClockDef(ClockBasis.PERSON, "sender_date", 0, label="the date the sender gave")),
        st("1", "Read the dry run", P, M, ("0",), why="Files, duplicates, files already held, versions, copies, questions, and the checklist items and gates that would move.",
           command="jason ingest SOURCE", sop=f"{IG}#1", record="the report read", becomes_=("job", "ingest-dry-run")),
        st("2", "Read the contract terms", P, M, ("1",), why="Each contract's deliverables and findings are leads beside the words and the statute; a deliverable worth tracking becomes a board item or a register row, decided by a person. A remote model sends words to a cloud service and is a person's choice. Skipped, with a reason, when the report holds no contract.",
           command="jason ingest SOURCE --terms-model ollama; jason contract-terms --list", sop=f"{IG}#2",
           record="the deliverables and findings read, and what a person decided", skip=SKIP_M),
        st("3", "Follow the report's QR codes", P, M, ("1",), why="The portal's reports are compared with the library; a protected portal is read by a person. Skipped, with a reason, when no code names a portal.",
           command="jason vendors --reports; jason ingest data/vendors/KEY/reports", sop=f"{IG}#3",
           record="the portal reports compared with the library", skip=SKIP_M, becomes_=("job", "vendor-reports")),
        st("4", "Add the local model for files with no kind", P, M, ("1",), why="Kinds are proposed and the model is unloaded afterward; the run takes the GPU lane and fails fast on the preflight. Skipped, with a reason, unless many files have no kind.",
           command="jason ingest SOURCE --model", sop=f"{IG}#4", record="the kinds proposed (a count)", skip=SKIP_M,
           becomes_=("job", "ingest-model")),
        st("5", "Park the questions and answer them in the ranked queue", P, ANY, ("1",), why="Asks are parked, then answered and applied in the shapes of document-intake steps 11 to 14.",
           command="jason ingest SOURCE --park; jason onboard; jason intake --apply", sop=f"{IG}#5", record="the asks parked and answered (counts)",
           becomes_=("job", "ingest-park")),
        st("6", "Read the dry run again", P, M, ("5",), why="The counts that are ready, need a kind, and need a folder.",
           command="jason ingest SOURCE", sop=f"{IG}#6", record="the counts read", becomes_=("job", "ingest-dry-run")),
        st("7", "File the ready files", P, M, ("6",), why="Terminal only. Files are copied into the library; held files stay held, and a file with an open question is not filed.",
           command="jason ingest SOURCE --apply", sop=f"{IG}#6", record="the filed count", evidence=gate,
           becomes_=("plan", "local.ingest.apply")),
        st("8", "Read a new version of a known document", P, M, ("1",), why="A history is read and reported, never applied; a new version opens a document-intake run. Skipped, with a reason, unless the report finds a version.",
           command="jason revisions KEY", sop=f"{IG}#7", record="the versions found and the intake runs opened", skip=SKIP_M,
           spawns=DI, becomes_=("job", "revisions-history")),
        st("9", "The ingest gate", C, JASON, ("7",), why="The last report's files filed and held, versions, open questions, and the items moved; read again on every open.",
           command="jason ingest --gate", sop=f"{IG}#6", evidence=gate, check=named_check("ingest-gate")),
    )
    phases = _phases(sid, (("arrive", "Arrive", ("0",)), ("read", "Read", _upto(1, 4)), ("ask", "Ask", ("5", "6")),
                           ("file", "File", ("7", "8", "9"))))
    return Workflow(key=IG, title="Take a folder in", family=FAMILY, subject="source", steps=steps,
                    dates=(DateSlot("sender_date", "The date the sender gave", required=False),), phases=phases, procedure=IG)


# --- 3. record-slot and split-document --------------------------------------------------------------------------------------

RS = "record-slot"


def record_slot() -> Workflow:
    """The record checklist of one association, about sixty slots (section 2.3). A slot's state is computed from the stores,
    never set by a step. A run may be started with the slot keys as its items; the engine keeps one item list a run, so the
    steps are done item by item and a step a slot does not use is skipped with a reason (the engine derives no per-item path)."""
    sid, st = _maker(RS)
    steps = (
        st("1", "Read the checklist and its biggest unknowns", C, JASON, why="Counts by state, group, and law, and the slots a gate waits on; read on open.",
           command="jason records --list [--group G] [--state S]", sop="onboard#4", check=named_check("record-slots-read")),
        st("2", "How is this slot answered", P, ANY, ("1",), why="A branch by person for each slot: a file (pick, bind, or upload) or an answer (none, not applicable, waiting). The engine derives no per-item path, so the person records the way and skips the other way's steps with a reason.",
           command="jason records --slot KEY", record="the way chosen", repeat=ITEM),
        st("3", "Pick, bind, or upload", P, ANY, ("2",), why="A pin; a recorded instrument's pin is a key-documents link, a bound folder's files are candidates and never pins, and the file is never touched. Election materials are kept one year (CIV 5200(c)).",
           command="jason records --pick KEY --file ID --by NAME; --bind KEY --folder ID; --upload KEY --file PATH --yes", record="the pin id (never a file name)",
           repeat=ITEM, skip=SKIP_ANY),
        st("4", "Read what was picked", P, ANY, ("3",), why="One reading for each file hash: kind, tier, preflight, segments, and findings; a dry run first. The GPU lane only when a person asked.",
           command="jason records --read KEY --yes --by NAME", sop="onboard#5", record="the reading's pin id", repeat=ITEM, skip=SKIP_ANY,
           becomes_=("job", "record-read")),
        st("5", "Compare with the slot", C, JASON, ("4",), why="The verdict is agrees, differs, or unclassified; a difference sets the slot to problem. "
           "The read counts the verdicts of the slot's kept readings and passes when every pin has one; a difference is what step 6 resolves.",
           command="jason records --slot KEY", sop="onboard#5", repeat=ITEM, skip=SKIP_ANY, check=named_check("record-compare")),
        st("6", "Resolve a wrong-slot pick", P, ANY, ("5",), why="A branch by person: repin to the slot it fits, keep with a required reason, or unpin. Nothing moves until a person confirms. Skipped, with a reason, unless step 5 differs.",
           command="jason records --repin KEY --to SLOT; --keep KEY --reason TEXT; --unpin KEY --pin ID", sop="onboard#5",
           record="repinned, kept (with the reason), or unpinned", repeat=ITEM, skip=SKIP_ANY),
        st("7", "Split a combined scan", P, ANY, ("4",), why="Each confirmed part is pinned to its slot as a new file of just those pages; a split nobody confirmed fills nothing. Skipped, with a reason, unless the reading proposes a split.",
           command="jason records --split KEY --part SEG=SLOT[@PERIOD][#ENTRY] --yes --by NAME", sop="onboard#5",
           record="the parts pinned, or the split-document run", repeat=ITEM, skip=SKIP_ANY, spawns="split-document"),
        st("8", "Two holders: which is current", P, ANY, ("3",), why="A required reason; the profile's own pin changes only by a patch a person applies, so two holders may remain. Skipped, with a reason, unless two hold the slot.",
           command="jason records --current KEY --pin ID --reason TEXT", record="the current holder and the reason", repeat=ITEM, skip=SKIP_ANY),
        st("9", "Answer: none exists, not applicable, or waiting", P, ANY, ("2",), why="Each answer carries a name and the words (where looked, or why not applicable); for waiting, who holds it and the day asked. 'Missing' is not 'none exists'. Reopening is a later act.",
           command="jason records --answer KEY --none | --not-applicable | --waiting WHO --note TEXT --by NAME",
           record="the answer, with the words and, for waiting, who and the day asked", repeat=ITEM, skip=SKIP_ANY,
           clock=ClockDef(ClockBasis.PERSON, label="the day asked, for a waiting slot")),
        st("10", "Wait for the one who holds it", W, ANY, ("9",), why="Ends when a pick arrives for that slot; a date passed opens a follow-up for a person and never marks the arrival.",
           repeat=ITEM, skip=SKIP_ANY, clock=ClockDef(ClockBasis.PERSON, label="a date a person recorded, if any")),
        st("11", "Is there another? / this is all", P, ANY, ("3",), why="A slot that holds several, or a series, is answered only when a person says so.",
           command="jason records --more KEY --value yes|no", record="more or no more", repeat=ITEM, skip=SKIP_ANY),
        st("12", "Read the gates the slots feed", C, JASON, ("1",), why="The checklist items and the gates (start, ingest, establish) are computed from the slots; no control passes a gate.",
           command="jason onboard", check=named_check("onboard-gates-read")),
    )
    phases = _phases(sid, (("read", "Read the checklist", ("1",)), ("fill", "Fill each slot", _upto(2, 11)), ("gates", "The gates", ("12",))))
    return Workflow(key=RS, title="Fill the record checklist", family=FAMILY, subject="association", steps=steps, phases=phases)


SD = "split-document"


def split_document() -> Workflow:
    """A draft split of a combined scan (section 2.3). The only step that writes PDFs is step 6, and only from a person's
    command; a draft is a long-lived session and its own states (draft, confirmed, applied, stale, declined) are the splitter's."""
    sid, st = _maker(SD)
    out = "Skipped, with a reason, when the draft is declined."
    steps = (
        st("1", "Open a draft", P, ANY, why="From an upload or a library id; a copy is kept and a Drive file is not taken yet.",
           command="jason split FILE|ID", sop="onboard#5", record="the draft id"),
        st("2", "Measure the pages and suggest first pages", P, ANY, ("1",), why="Per-page facts and suggestions with a tier (High, Medium, Low), never automatic. " + out,
           command="jason split ID --suggest [--model]", sop="onboard#5", record="the suggestions read", skip=SKIP_ANY, becomes_=("job", "split-suggest")),
        st("3", "Mark first pages; accept or reject suggestions", P, ANY, ("2",), why="Boundaries are saved in order with a version; a stale save shows both copies. " + out,
           command="jason split ID --boundaries ...; --accept ...; --mark/--unmark", sop="onboard#5", record="the boundaries saved, with the version", skip=SKIP_ANY),
        st("4", "Review: counts, collisions, flags, pages to turn and leave out", C, JASON, ("3",), why="Flags (blank only, repeats, sideways, may be over the size limit, slot already filled, may hold more than one document) are readings, not decisions. " + out,
           command="jason split ID --review --flags", sop="onboard#5", skip=SKIP_ANY, check=named_check("split-review")),
        st("5", "Where do the new files go", B, ANY, ("4",), why="By person: held, the library, the slots, or as each part is labelled; a part may differ. " + out,
           command="jason split ID --filing ...", sop="onboard#5", skip=SKIP_ANY,
           choices=(Choice("held"), Choice("library"), Choice("slots"), Choice("each-part"))),
        st("6", "Write the files", P, ANY, ("4", "5"), why="The only command that writes PDFs: new files of page ranges, with /Rotate only in the new file; the original is untouched, and no schedule or job applies a split. A failed segment is retried. " + out,
           command="jason split ID --apply --yes --by NAME", sop="onboard#5", record="the result: filled, taken in, held, skipped, failed", skip=SKIP_ANY),
        st("7", "Read each new part", P, ANY, ("6",), why="A read-back for each part and OCR for library parts; 'no OCR engine' means install one, not retry. " + out,
           command="jason library --ocr-doc ID --yes --by NAME", sop="onboard#5", record="the read-backs started", skip=SKIP_ANY, becomes_=("job", "split-read-back")),
        st("8", "Or decline", P, ANY, ("1",), why="The draft becomes declined and the combined-scan item leaves the checklist. An alternative to step 6; skipped, with a reason, when the files were written.",
           command="jason split ID --decline --by NAME", record="the draft declined", skip=SKIP_ANY),
    )
    phases = _phases(sid, (("draft", "Draft", _upto(1, 4)), ("file", "File", ("5", "6", "7")), ("decline", "Decline", ("8",))))
    return Workflow(key=SD, title="Split a combined scan", family=FAMILY, subject="draft", steps=steps, phases=phases)


# --- 4. onboard -------------------------------------------------------------------------------------------------------------

OB = "onboard"
GATE_NOTE = "A gate is jason's reading of the checklist; the board decides what is done. This step records only that the reading was taken."


def onboard() -> Workflow:
    """Take on an association, or a change of manager (section 2.4). One run an association (the subject is the profile key).
    The five gates are the phases (ST start, IN ingest, ES establish, OP operate, AD adopt); the change-of-manager block CM is
    on a branch the manager answers first, and the new association path skips it. Ids are ``onboard.ST-1`` and so on."""
    sid, st = _maker(OB)
    gate_ids = {"ST": "ST-7", "IN": "IN-7", "ES": "ES-7", "OP": "OP-4", "AD": "AD-4"}
    cm = tuple(f"CM-{i}" for i in range(1, 5))

    def g(prefix: str, n: str, title: str, kind: StepKind, role: Role, needs: tuple[str, ...] = (), **more: Any) -> StepDef:
        step_id = f"{prefix}-{n}"
        return replace(st(step_id, title, kind, role, needs, **more), group=prefix)

    steps = (
        # --- ST: start
        g("ST", "0", "Say whether this is a new association or a change of manager", B, M,
          why="The first fork, by person: a change of manager adds the CM block; a new association skips it.",
          choices=(Choice("new-association"), Choice("change-of-manager", tuple(sid(c) for c in cm)))),
        g("ST", "1", "Choose the community", C, JASON, why="The active profile must equal the run's subject before any job; a mismatch blocks.",
          command="jason which; jason use KEY", sop=f"{OB}#1", check=named_check("active-community")),
        g("ST", "2", "Start the profile package", P, A, ("ST-1",), why="Terminal only. A package from jason's templates and empty private facts; it overwrites nothing, and a person reviews and commits the source files.",
          command="jason onboard --new KEY --name NAME --county COUNTY", sop=f"{OB}#2", record="the package started"),
        g("ST", "3", "Look up the county's finds", P, M, ("ST-2",), why="Leads under the private facts, each becoming a question; an empty or unreachable recorder is a note, not a row. Skipped, with a reason, when no county reader exists.",
          command="jason onboard --lookup", sop=f"{OB}#2", record="the leads parked (a count)", skip=SKIP_M, becomes_=("job", "county-lookup")),
        g("ST", "4", "Confirm only its own facts are read", C, JASON, ("ST-2",), why="Only the profile's own private facts and its topic folder are read. "
          "The read counts the topic files and fails when one is read from the old shared layout; it names no path and reads no value.",
          command="jason spec", sop=f"{OB}#3", check=named_check("profile-own-facts")),
        g("ST", "5", "Set up the community's Google Workspace", P, A, ("ST-1",), why="The client in this community's vault path and one sign-in for each token needed; never asked for consent again while a token covers the scopes; an invalid_grant is never retried.",
          command="jason google status; jason google setup --from-file F --yes; jason google sign-in --name drive --interactive", sop=f"{OB}#6",
          record="the sign-ins made, by token name"),
        g("ST", "6", "Connect the integrations", P, A, ("ST-1",), why="Each credential under its vault path; connected only after a read succeeds, checked by a person at a console.",
          command="jason vault status; jason vault migrate; jason integrations check KEY --live --by NAME", sop=f"{OB}#13", record="each integration read, by name"),
        g("ST", "7", "Gate: start", C, JASON, ("ST-4", "ST-5", "ST-6"), why=f"Open when units, management software, Drive, and the vault are present. {GATE_NOTE}",
          command="jason onboard", check=named_check("onboard-gate-start")),
        # --- IN: ingest
        g("IN", "1", "Read the record checklist", P, M, ("ST-7",), why="A record-slot run is linked and shows the counts by state; the parent step is a link and not the gate.",
          command="jason records --list", sop=f"{OB}#4", record="the child run and the counts read", spawns=RS),
        g("IN", "2", "Read the picks", P, ANY, ("IN-1",), why="The record-slot steps 3 to 11, and a split-document run for a long combined scan.",
          command="jason records --read KEY", sop=f"{OB}#5", record="the picks read"),
        g("IN", "3", "Send each source its request list", P, M, ("ST-7",), why="Each source is asked, with three dates: at once, monthly after late fees, and at transition (or the dates the transition agreement sets); paper comes with a contents list for each box.",
          command="jason onboard --request [SOURCE]", sop=f"{OB}#11", record="the requests recorded: of whom and when",
          clock=ClockDef(ClockBasis.PERSON, label="the three dates a person records, or the documents' where the transition agreement sets them")),
        g("IN", "4", "Wait for each source", W, M, ("IN-3",), why="A date passed opens a follow-up and never marks anything received; the law is silent on a handover, so the date is a person's.",
          clock=ClockDef(ClockBasis.PERSON, label="a date a person recorded for each source")),
        g("IN", "5", "Take in what arrives", P, M, ("IN-4",), why="One ingest run for each source handed over.",
          command="jason ingest SOURCE", record="the ingest run opened", spawns=IG),
        g("IN", "6", "Fetch what jason can read itself", P, M, ("ST-7",), why="The catalog, the library, and the outlines are refreshed; repeat as needed.",
          command="jason sync-catalog; jason library; jason outlines --fetch", sop=f"{OB}#16", record="the fetch run", becomes_=("job", "sync-catalog")),
        g("IN", "7", "Gate: ingest", C, JASON, ("IN-1", "IN-5", "IN-6"), why=f"Open when the records map, minutes, budget reports, financial statements, contracts, and insurance policies are present and no library file waits for a kind. {GATE_NOTE}",
          command="jason onboard; jason ingest --gate", check=named_check("onboard-gate-ingest")),
        # --- ES: establish
        g("ES", "1", "Find and pin the founding instruments", P, M, ("IN-7",), why="The declaration, amendments, annexations, bylaws, and articles are located, asked about, confirmed, and pinned in a founding-documents run.",
          command="jason onboard --locate", record="the founding-documents run opened", spawns="founding-documents"),
        g("ES", "2", "Take each governing instrument in", P, ANY, ("ES-1",), why="One document-intake run for each instrument; a key-document run for each recorded copy is opened from founding-documents.",
          command="jason intake --scan", record="the intake runs opened", spawns=DI),
        g("ES", "3", "Run the session: answer", P, ANY, ("ST-7", "ES-3b"), why="Each question is answered, ranked by what it unblocks; a secret is refused and nothing is stored, and the Keeper record's name is answered instead. The answer is shown to the one who gave it or is confirming it.",
          command="jason onboard --answer ID TEXT --by NAME", sop=f"{OB}#8", record="the questions answered (ids)"),
        g("ES", "3b", "Or answer by conversation", B, ANY, ("ST-7",), why="By person: the same tools through the onboarding tool set (onboarding_status, next_questions, answer_intake_question), and a second person runs onboard_review. Chosen, it skips step ES-3.",
          command="jason-mcp --profile onboarding", sop=f"{OB}#9", choices=(Choice("terminal", ("onboard.ES-3",)), Choice("conversation"))),
        g("ES", "4", "A second person confirms a high-stakes answer", P, ANY, ("ES-3",), why="Which text is in force, whether an instrument was recorded, bank signers; the answerer cannot confirm, in any case or spacing.",
          command="jason onboard --confirm ID --by OTHER", sop=f"{OB}#8", record="the answers confirmed, and the confirmer"),
        g("ES", "5", "Apply the answers", P, M, ("ES-3", "ES-4"), why="Terminal only. Private facts are merged with a backup and a diff, and profile proposals are written for a person to read.",
          command="jason onboard --apply", sop=f"{OB}#8", record="the diff applied, and the proposals written (a count)"),
        g("ES", "6", "Read and apply each profile proposal", P, M, ("ES-5",), why="A patch is read, applied, and committed by a person; jason never edits the profile.",
          command="git apply", record="each proposal read and applied"),
        g("ES", "7", "Gate: establish", C, JASON, ("ES-2", "ES-6"), why=f"Open when the declaration, amendments, annexations, bylaws, and articles are present, each recorded copy is matched in the county index and read with a stamp, and no question is open about which text is in force. {GATE_NOTE}",
          command="jason onboard", check=named_check("onboard-gate-establish")),
        # --- OP: operate
        g("OP", "1", "Put people, accounts, and figures in the private facts", P, M, ("ST-7",), why="In the private facts or the profile's notes; codes and passwords in the vault only. Continuous.",
          sop=f"{OB}#12", record="that the facts were put in the private facts (never the values)"),
        g("OP", "2", "Keep the roster current", P, ANY, ("ES-3",), why="After the minutes record a change of office or a seat is filled, the standing question is answered in its form and a second person confirms; it waits on the minutes.",
          command="jason onboard --questions --group board", sop=f"{OB}#10", record="the minutes that record the change"),
        g("OP", "3", "Adopt the schedules", P, A, ("ST-6",), why="No source runs until adopted, none faster than its floor, no write is scheduled, and the heartbeat is fresh.",
          command="jason cadence; jason serve --install-task; jason daemon status", sop=f"{OB}#14", record="the schedules adopted, by source"),
        g("OP", "4", "Gate: operate", C, JASON, ("OP-1", "OP-2", "OP-3"), why=f"Open when the board rule, roster, signers, accounts, assessments, fiscal year, meeting schedule, notice rules, assignments, and utilities are present. {GATE_NOTE}",
          command="jason onboard", check=named_check("onboard-gate-operate")),
        # --- AD: adopt
        g("AD", "1", "Write the profile's rows", P, M, ("ES-6",), why="A Community subclass, pinned library folders and Drive roots, and the books. The procedure does not flag this step as a person's, and no command does it; it is a person's work, committed by a person.",
          sop=f"{OB}#15", record="the rows written and committed"),
        g("AD", "2", "Take in the rules and policies", P, ANY, ("AD-1",), why="One document-intake run for each operating rule set, election rule, policy, and resolution.",
          command="jason intake --scan", record="the intake runs opened", spawns=DI),
        g("AD", "3", "Run the checklist until only what a person supplies is missing; give each an owner", C, JASON, ("ST-7", "IN-7", "ES-7", "OP-4"),
          why="The checklist report; each missing item has an owner in the schedule. The read says whether only what a person supplies is missing; who owns each is a person's to give in the schedule.",
          command="jason onboard --checklist --write; jason schedule", sop=f"{OB}#17", check=named_check("onboard-checklist")),
        g("AD", "4", "Gate: adopt", C, JASON, ("AD-2", "AD-3"), why=f"Open when the operating rules, election rules, policies, collection and enforcement policies, architectural procedure, governing set, and conflicts are present. {GATE_NOTE}",
          command="jason onboard", check=named_check("onboard-gate-adopt")),
        g("AD", "5", "Close the onboarding", P, M, tuple(gate_ids.values()), why="A note that the board saw the gates open; it closes the run. A design choice: closing is a person's word, and no step marks a gate passed.",
          record="the note that the board saw the gates open"),
        # --- CM: change of manager (the branch ST-0)
        g("CM", "1", "Read the outgoing agreement", P, M, ("ST-7", "ST-0"), why="Its term, its non-renewal and termination clauses, and what it owes at transition. Each notice window is counted back from the term's end, with both edges written down before any notice goes.",
          sop=f"{OB}#18", record="the term, the windows, and both edges of each",
          clock=ClockDef(ClockBasis.DOCUMENTS, "term_ends", 0, label="the outgoing agreement's term end")),
        g("CM", "2", "Decide whether to give notice", D, S, ("CM-1",), why="Added by the design: the procedure assumes the decision. The board decides; the secretary records the decision, the meeting, and the vote as taken.",
          command="jason board", record="the board's decision and the minutes",
          clock=ClockDef(ClockBasis.DOCUMENTS, "term_ends", 0, label="before the first edge of the notice window")),
        g("CM", "3", "Send the notice by the delivery the clause names; keep proof", P, M, ("CM-2",), why="Proof of delivery is kept with the notice. Skipped, with a reason, when the board decided not to give notice.",
          record="the proof of delivery kept", skip=SKIP_M,
          clock=ClockDef(ClockBasis.DOCUMENTS, "term_ends", 0, label="both edges of the window, counted back from the term's end")),
        g("CM", "4", "Before the termination date: request the records, confirm the board's portal access, tell each vendor", P, M, ("CM-2",),
          why="The sources' arrivals are waited on in step IN-4. No stored provision sets a handover deadline and the law is silent here, so the dates are the transition agreement's or a person's.",
          command="jason onboard --request", sop=f"{OB}#19", record="asked, received, and the board's access confirmed",
          clock=ClockDef(ClockBasis.PERSON, "transition_on", 0, label="the transition date, and the three dates a person records")),
    )
    phases = tuple(Phase(key, title, tuple(s.id for s in steps if s.group == prefix)) for key, title, prefix in (
        ("start", "Gate: start", "ST"), ("ingest", "Gate: ingest", "IN"), ("establish", "Gate: establish", "ES"),
        ("operate", "Gate: operate", "OP"), ("adopt", "Gate: adopt", "AD"), ("change-of-manager", "Change of manager", "CM")))
    return Workflow(
        key=OB, title="Take on an association", family=FAMILY, subject="association", steps=steps, phases=phases, procedure=OB,
        dates=(DateSlot("term_ends", "The outgoing agreement's term ends", required=False),
               DateSlot("transition_on", "The transition date", required=False)))


# --- 5. founding-documents, key-document, parcel-title ------------------------------------------------------------------------

FD = "founding-documents"


def founding_documents() -> Workflow:
    """Locate, ask about, confirm, and pin the recorded founding instruments (section 2.5). A located number is a lead, never
    a pin. No procedure covers it. The subject is the association."""
    sid, st = _maker(FD)
    steps = (
        st("1", "Choose the association from the county directory", P, M, why="A directory row is a lead, not a pin. Skipped, with a reason, when the profile names it.",
           command="jason onboard --associations --county C [--find WORDS]", record="the directory row chosen", skip=SKIP_M),
        st("2", "Locate its recorded documents", P, M, ("1",), why="Ties are read as leads: it names the association, it was recorded with its documents, or the builder's filing may be another community's. A county read that fails is a failure, not 'none found'.",
           command="jason onboard --locate", record="the items located and not located (counts)", becomes_=("job", "documents-locate")),
        st("3", "Ask the board about each", P, ANY, ("2",), why="A fact question for each item; the declaration and the amendments are high stakes.",
           command="jason onboard --questions", record="the questions answered (ids)"),
        st("4", "A second person confirms which is the declaration", P, ANY, ("3",), why="The answerer cannot confirm, in any case or spacing.",
           command="jason onboard --confirm ID --by OTHER", record="the answers confirmed, and the confirmer"),
        st("5", "Pin it in the profile", P, M, ("4",), why="A proposal patch is applied by a person; a located number is a lead until the recorded copy is read. A key-document run is opened for each entry.",
           command="git apply", record="the patch applied and the key-document runs opened", spawns="key-document"),
        st("6", "Not located: ask for the recording number", W, M, ("2",), why="A number arrives from the board or the prior manager; the date is a person's. Skipped, with a reason, when every item is located.",
           skip=SKIP_M, clock=ClockDef(ClockBasis.PERSON, label="a date a person records for the ask")),
    )
    phases = _phases(sid, (("find", "Find", ("1", "2")), ("confirm", "Ask and confirm", ("3", "4")), ("pin", "Pin", ("5", "6"))))
    return Workflow(key=FD, title="Find and pin the founding instruments", family=FAMILY, subject="association", steps=steps, phases=phases)


KD = "key-document"


def key_document() -> Workflow:
    """Get one recorded instrument (section 2.5): an entry of the key documents list. The subject is the entry (a row and a
    number); a reading is a lead, not a pin."""
    sid, st = _maker(KD)
    steps = (
        st("1", "Status from the stores: expected, located, held, linked", C, JASON, why="'Missing' is only ever a person's word and needs a note.",
           command="jason key-documents", check=named_check("key-document-status")),
        st("2", "Order the recorded copy", P, M, ("1",), why="The copy-order list holds the instruments the records lack, with the price in cents; jason never sends it. Skipped, with a reason, when the copy is held.",
           command="jason records-request", record="the copy-order entry", skip=SKIP_M),
        st("3", "Wait for the copy", W, M, ("2",), why="Ends when a scan arrives; the date is a person's. Skipped, with a reason, when no copy was ordered.",
           skip=SKIP_M, clock=ClockDef(ClockBasis.PERSON, label="a date a person records for the order")),
        st("4", "Link or upload the copy", P, ANY, ("3",), why="A link (a file, a Drive file, or a document) or an upload kept in the profile's folder; unlink marks and never deletes. Skipped, with a reason, when step 7 records none on record.",
           command="jason key-documents --link KEY ...; jason key-documents --upload KEY --file PATH --by NAME", record="the link or upload (a pin id, never a file name)", skip=SKIP_ANY),
        st("5", "Read the stamp and match the county index", C, JASON, ("4",), why="The recorded copy is matched in the index and read with a stamp; none is read without one. "
           "The read passes when the entry has a recording number and a recorded copy on disk carries it; an entry with no number is noted as not recorded. "
           "Skipped, with a reason, when there is no copy.",
           command="jason onboard", skip=SKIP_M, check=named_check("key-document-verified")),
        st("6", "Say whether it took effect", P, ANY, ("5",), why="CIV 4270(a)(3): an amendment is effective after, among other things, it \"has been recorded in each county in which a portion of the common interest development is located.\" "
           "An amendment with no number is noted as not recorded. The standing is the document-intake steps 5 and 6.",
           command="jason intake --answer ID TEXT --by NAME", record="the standing answered, and who confirmed it",
           clock=ClockDef(ClockBasis.LAW, cite="CIV 4270(a)(3)", label="an amendment takes effect when recorded")),
        st("7", "Or: none on record, with the note", P, ANY, ("1",), why="Status 'missing' with what was looked for and where; reopened by linking a copy. Skipped, with a reason, when a copy was linked.",
           command="jason key-documents --status KEY --set missing --note TEXT --by NAME", record="what was looked for, and where", skip=SKIP_ANY),
    )
    phases = _phases(sid, (("status", "Status", ("1",)), ("copy", "Get the copy", _upto(2, 4)), ("read", "Read it", ("5", "6")),
                           ("none", "Or none on record", ("7",))))
    return Workflow(key=KD, title="Get one recorded instrument", family=FAMILY, subject="entry", steps=steps, phases=phases)


PT = "parcel-title"


def parcel_title() -> Workflow:
    """A parcel's title history, read from a matter (section 2.5): a read, not a procedure. The subject is an opaque parcel
    handle. Owners' names are masked by role; a named person's reveal is logged, and this run records only that it was done."""
    sid, st = _maker(PT)
    steps = (
        st("1", "Read the parcel's deed history", P, M, why="A county read; one that cannot reach the index is a failure, never 'none found'. Every join is 'read as', never 'is'.",
           command="jason instrument-graph --parcel APN", record="the history read", becomes_=("job", "parcel-history")),
        st("2", "Check the strand and the gaps", P, M, ("1",), why="A gap is a lead, not a finding of fact.", record="the gaps found (a count)",
           becomes_=("check", "parcel-strand-gaps")),
        st("3", "Look up a gap", P, M, ("2",), why="A person asks for it; the lookup reads the county. Skipped, with a reason, when there is no gap.",
           record="the gaps looked up", skip=SKIP_M, becomes_=("job", "parcel-gap-lookup")),
        st("4", "Reveal names", P, M, ("2",), why="Names are masked by role; a reveal is logged with who and when, and this step records the log entry, never a name. Skipped, with a reason, when names are not needed.",
           record="the reveal log entry (who and when)", skip=SKIP_M),
        st("5", "Export the report", P, M, ("2",), why="The export is masked unless a reveal was logged.", command="jason instrument-graph --parcel APN",
           record="the report exported", becomes_=("job", "parcel-report")),
    )
    phases = _phases(sid, (("read", "Read", ("1", "2")), ("follow", "Follow up", ("3", "4")), ("export", "Export", ("5",))))
    return Workflow(key=PT, title="Read a parcel's title history", family=FAMILY, subject="parcel", steps=steps, phases=phases)


# --- 6. careful-reading ------------------------------------------------------------------------------------------------------

CR = "careful-reading"


def careful_reading() -> Workflow:
    """A question that turns on a set of documents (section 2.6). The workflow keeps three things apart as the procedure does:
    what the documents say, what the provisions mean, and whether the facts meet them. The subject is an opaque question
    handle; the question's words and the collection's name are never in a label, and a confidential collection is refused
    for a members' task by the review itself."""
    sid, st = _maker(CR)
    steps = (
        st("1", "Check where scratch and caches go", C, JASON, why="Temp and the county cache on the data drive with room. The read names the drives "
           "and their free space in whole gigabytes, never a path, and fails when a drive is short.",
           command="jason storage --check", sop=f"{CR}#1", check=named_check("scratch-room")),
        st("2", "See what the index holds and cannot read", P, M, ("1",), why="Unreadable or partly read files are listed for a person; a held-back record is never extracted. Built on the GPU lane; run again when files change.",
           command="jason index --plan; jason cases --extract-text --case KEY; jason index --build", sop=f"{CR}#2", record="the files indexed and the files listed unread",
           becomes_=("job", "index-build")),
        st("3", "Search the slice that matters", P, ANY, ("2",), why="Hits carry their standing (the law, the record, evidence, a reference, or jason's own page, which is a summary and never the rule).",
           command="jason index --search Q --catalog NAME [--kind K] [--standing S]", sop=f"{CR}#3", record="the slice searched"),
        st("4", "Lay out what the documents say happened, and where they differ", P, M, ("2",), why="Each event states what a document says; a conflict between facts keeps both documents.",
           command="jason chronology --catalog NAME; jason fact-conflicts --catalog NAME", sop=f"{CR}#4", record="the chronology laid out",
           becomes_=("job", "chronology")),
        st("5", "See what should be on file and is not", P, M, ("2",), why="'Not on file' never means 'not done'; an undetermined answer is a question for a person. Skipped, with a reason, when no inspection applies.",
           command="jason inspections; jason applies", sop=f"{CR}#5", record="what is not on file", skip=SKIP_M, becomes_=("job", "inspections-read")),
        st("6", "Recite each provision's words before any reading", P, M, ("3",), why="The provision whole, in force on the day, with its caveat; a reading is labeled as one.",
           command="jason readings --recite CITATION; jason cite KEY", sop=f"{CR}#6", record="the provisions recited", becomes_=("job", "provisions-recite")),
        st("7", "Review under the task's pack, the collection its own tier", P, M, ("4", "5", "6"), why="A kept review (the pack digest and the runs) on the GPU lane; kept, not overwritten. A confidential collection is refused for a members' task.",
           command="jason review TASK --collection KEY --ask Q --run", sop=f"{CR}#7", record="the review kept", becomes_=("job", "review-run")),
        st("8", "Judge date-dependent findings as of the date that matters", P, M, ("7",), why="Only the lens's findings move with the date. Skipped, with a reason, when nothing is date-dependent.",
           command="jason models --as-of DATE", sop=f"{CR}#8", record="the findings judged as of the date", skip=SKIP_M,
           clock=ClockDef(ClockBasis.PERSON, "as_of", 0, label="the date that matters"), becomes_=("job", "models-as-of")),
        st("9", "Check every quotation against the stored words", P, M, ("7",), why="Each quotation is FOUND, in the provision the answer names; an ALTERED, MISATTRIBUTED, OTHER VERSION, or NOT FOUND result blocks step 10. Run every time the answer changes.",
           command="jason verify-quotes FILE --as-of DAY", sop=f"{CR}#9", record="the result of each quotation", becomes_=("check", "quotes-verified")),
        st("10", "Give the answer as a proposal", P, M, ("9",), why="The facts with their sources, the provisions recited, the reading labeled, and the application; the board or counsel decides. Its clock, if any, is its parent run's.",
           sop=f"{CR}#10", record="the proposal given"),
    )
    phases = _phases(sid, (("prepare", "Prepare", ("1", "2")), ("read", "Read", _upto(3, 6)), ("review", "Review", ("7", "8")), ("answer", "Answer", ("9", "10"))))
    return Workflow(key=CR, title="Read a set of documents and answer from them", family=FAMILY, subject="question", steps=steps,
                    dates=(DateSlot("as_of", "The date the findings are judged as of", required=False),), phases=phases, procedure=CR)


# --- 7. records-production (a held definition) -------------------------------------------------------------------------------

RP = "records-production"


def records_production() -> Workflow:
    """The records side of a member's request (section 2.7): which record answers, what is withheld, what it costs, and the
    production. The subject is an opaque request handle (never a name or a unit), and the items, if any, are opaque kind codes.

    **Held** (``Visibility.HELD``, held title "A records request"). Step 6 weighs withholding and redaction, which reaches
    restricted kinds (an executive-session matter among them), and the record a person attests is shown in the run, so the Work
    backend shows a run of this definition outside the private view by its general title and state only (CIV 4935(e)) and logs
    each opening in the private view. Its law clocks are those whose statutes are on the shelf, on steps that cannot be
    skipped; the membership list's timeframe (CIV 5210(b)(6) with Corp. Code 8330) is not a law clock until counsel reads it."""
    sid, st = _maker(RP)
    steps = (
        st("1", "Open the request", P, M, why="A row in the request store keyed by the request's day and unit, with the kinds asked, the years, and the purpose in the member's words; no command exists, so it is a console write. The run's subject is an opaque handle.",
           record="the request handle", clock=ClockDef(ClockBasis.LAW, "received_on", 0, cite="CIV 5210(b)", label="the request received; the clocks start")),
        st("2", "Designation, if a representative asks", P, M, ("1",), why="The member's written designation is on file. Skipped, with a reason, when the member asks for themselves.",
           record="the designation seen", skip=SKIP_M,
           becomes_=("check", "designation-on-file")),
        st("3", "Map each kind to its record and its holder", C, JASON, ("1",), why="Each kind to its paragraph of CIV 5200(a), the slot's state, and the inspection period: \"For the current fiscal year and for each of the previous two fiscal years.\" (CIV 5210(a)(1)). "
           "The read counts the kinds mapped to a paragraph and a slot, with the slots' states, and names no kind.",
           command="jason records --slot KEY", repeat=ITEM,
           check=named_check("request-kinds-mapped"),
           clock=ClockDef(ClockBasis.LAW, cite="CIV 5210(a)", label="the inspection periods")),
        st("4", "A record not held: look, ask, or say none exists", P, ANY, ("3",), why="The record-slot answer for that kind (none exists, or waiting); 'missing' is not 'none exists'. Skipped, with a reason, when it is held.",
           command="jason records --answer KEY ...", record="the answer given", skip=SKIP_ANY),
        st("5", "Weigh the stated purpose, for a kind that needs one", P, M, ("1",), why="CIV 5225: the member states a purpose \"reasonably related to the requester's interest as a member\"; the member's words are quoted, never paraphrased or scored. Counsel is asked where needed. Skipped, with a reason, when no such kind is asked.",
           record="whether the purpose was adequate, with the member's words", skip=SKIP_M),
        st("6", "Decide what to withhold or redact, and on what basis", P, M, ("3",), why="CIV 5215: the association \"may withhold or redact information\" on the bases the section lists; the manager gives each basis in words, with counsel where needed. A list built with opt-outs removed is handed to no one by jason.",
           record="each record withheld, with the reason given", repeat=ITEM, clock=ClockDef(ClockBasis.LAW, cite="CIV 5215", label="withholding and redaction")),
        st("7", "Tell the member the cost and wait for agreement", W, M, ("6",), why="CIV 5205(f): \"the member shall agree to pay those costs, before copying and sending the requested documents.\" The redaction estimate has its own cap in CIV 5205(g); the statute's words are shown, and a figure above it is the manager's reason to record. Skipped, with a reason, for inspection only.",
           skip=SKIP_M),
        st("8", "Produce: make available, deliver copies, or send electronically", P, M, ("5", "6", "7"), why="Nothing is sent by jason; a cover email is a draft a person sends.",
           record="the day produced, and inspected or copies", clock=ClockDef(ClockBasis.LAW, "received_on", 30, cite="CIV 5210(b)", label="the outer edge for the previous two fiscal years")),
        st("9", "If asked, give the written explanation of a denial or redaction", P, M, ("6",), why="CIV 5215(d): \"an association that denies or redacts records shall provide a written explanation specifying the legal basis for withholding or redacting the requested records.\" Skipped, with a reason, unless the member asked.",
           record="the explanation given", skip=SKIP_M),
        st("10", "Wait to the production date", W, M, ("1",), why="Read on its face as open, produced, or overdue; a date passed opens a follow-up and never marks the production. The current year's stage is ten business days (CIV 5210(b)(1)), "
           "computed by the members' request code for a person to check; the clock here is the outer edge, 30 calendar days (CIV 5210(b)(2)). The membership list's timeframe (CIV 5210(b)(6) with Corp. Code 8330) is held for counsel and is not a law clock.",
           clock=ClockDef(ClockBasis.LAW, "received_on", 30, cite="CIV 5210(b)(2)", label="30 calendar days following receipt")),
    )
    phases = _phases(sid, (("open", "Open", ("1", "2")), ("map", "Map the records", ("3", "4")), ("withhold", "Withhold and weigh", ("5", "6")),
                           ("produce", "Cost and production", ("7", "8", "9", "10"))))
    return Workflow(key=RP, title="Produce records to a member", family=FAMILY, subject="request", steps=steps,
                    dates=(DateSlot("received_on", "The request was received"),), phases=phases,
                    visibility=Visibility.HELD, held_title="A records request")


BUILDERS: tuple[Callable[[], Workflow], ...] = (
    document_intake, ingest, record_slot, split_document, onboard, founding_documents, key_document, parcel_title,
    careful_reading, records_production,
)
"""The definitions registered by ``register_general``. ``records_production`` is held (see its docstring)."""

NOT_OFFERED: tuple[Callable[[], Workflow], ...] = ()
"""Nothing is left out any more (``records_production`` moved into ``BUILDERS`` as a held definition)."""

__all__ = ["BUILDERS", "FAMILY", "NAMED", "NOT_OFFERED", "WANTED", "becomes", "careful_reading", "document_intake", "founding_documents",
           "ingest", "key_document", "onboard", "parcel_title", "record_slot", "records_production", "split_document"]
