"""The platform family: paper mail, email, and running jason itself (docs/workflows/mail-and-platform.md; the disconnect
step is docs/console/screens/integration-disconnect.md).

Seven definitions are built here and registered (``BUILDERS``): the first four (``BOARD_BUILDERS``) are the manager's and the
board's, the last three (``ADMIN_BUILDERS``) the administrator's.

- ``mail-triage``: a period of paper mail, a letter at a time (the manager's).
- ``email-conversation``: one Gmail thread, from the sync to the answer (the manager's).
- ``gmail-draft``: a Gmail draft from an item, never sent (the approvals kind ``gmail-drafts``).
- ``response-inbox``: a returned form, recognized, read, and confirmed; the run ends at the hand-over.

``integration-connect``, ``service-run``, and ``check-in`` (``integration_connect``, ``service_run``, ``check_in``) are
``Visibility.ADMIN``. The page makes the first two the administrator's alone ("never in the owner view, never to a director,
secretary, treasurer, or manager, not even by count") and the third a developer's terminal procedure that "the console never
offers". The Work backend (``jason.web.extra.work``) therefore lists, reads, and starts an ADMIN definition and its runs for an
administrator only, and a non-administrator gets neither the definition nor a run of it (404). ``check-in`` also has
``console_start`` False: the console never starts it (a terminal procedure; ``jason workflow`` does).

This module is pure data: it imports only ``jason.workflows.types``, ``named_check``, and the standard library, and loads no
profile, store, or client. It names no association, person, address, or id. A run's subject is an opaque id and its label carries no sender
name or address: a period (``period:YYYY-MM-DD``), a Gmail thread id, a draft case and key, a request key. jason sends,
mails, scans, forwards, shreds, discards, connects, and revokes nothing in any of them: each such act is a person's step or
an approvals plan a person decides.

No step here is a ``job``. A ``check`` names a read in ``readers.CHECKS`` and a ``job`` a name in ``readers.JOBS``; an
unregistered check can only fail. Fifteen reads are registered by ``jason.workflows.checks.platform`` (disk only: no network,
no service contacted, no write, no vault asked), and their steps are ``check`` steps (``mail-triage.1`` and ``.4``, a wait's
arrival on ``.9``, ``.12``; ``email-conversation.1`` and ``.3``; ``response-inbox.2``, ``.3``, and ``.10``;
``integration-connect.1`` and ``.2``; ``service-run.1``, ``.2``, ``.5``, ``.10``, and ``.12``), role ``jason``. The other steps that want a read, a job, or an approvals kind are
still ``person`` steps whose ``why`` says what they become, and ``WANTED`` lists what is left to add. The one registered
``plan`` kind it needs is ``gmail-drafts``.
"""

from __future__ import annotations

from typing import Any, Callable

from jason.workflows.readers import named_check
from jason.workflows.types import (
    Choice, ClockBasis, ClockDef, Phase, Repeat, Role, SkipRule, StepDef, StepKind, Visibility, Workflow,
)

P, B, D, W, PL, C = StepKind.PERSON, StepKind.BRANCH, StepKind.DECISION, StepKind.WAIT, StepKind.PLAN, StepKind.CHECK
M, A, S, JASON = Role.MANAGER, Role.ADMINISTRATOR, Role.SECRETARY, Role.JASON
ITEM = Repeat.PER_ITEM

MANAGER_OR_SECRETARY = SkipRule((M, S))
MANAGER_ONLY = SkipRule((M,))
ADMIN_ONLY = SkipRule((A,))

MT, EC, GD, RI = "mail-triage", "email-conversation", "gmail-draft", "response-inbox"
IC, SR, CI = "integration-connect", "service-run", "check-in"

KEYS: tuple[str, ...] = (MT, EC, GD, RI)
ADMIN_KEYS: tuple[str, ...] = (IC, SR, CI)

CASES: tuple[str, ...] = ("proposal-request", "hearing", "meeting-notice")
"""The three cases of the approvals kind ``gmail-drafts``; a run's subject is ``<case>:<key>``."""

WANTED: tuple[str, ...] = (
    # reads (readers.CHECKS) still to add; the fifteen built are in jason.workflows.checks.platform. Not possible today:
    #   thread-leads (jason.tasks.threads.threads writes reports/threads.json), mail-findings (mail_links opens the tax store,
    #   which runs CREATE TABLE IF NOT EXISTS: a write path until it has a read-only open), draft-source and draft-preview
    #   (the profile and settings, or Google), thread-closed (a person's note has no store), vault-answers (the vault is the
    #   development environment's store: not asked)
    "check mail-findings (mail-triage.3): the findings of `jason mail --checks` as a count",
    "check thread-leads (email-conversation.7): payments, letters, Drive files, PayHOA requests near the thread, as leads",
    "check thread-closed (email-conversation.15): the status is awaiting them or internal, or a person's note",
    "check draft-source (gmail-draft.1): the system, hearing, or agenda file the draft is about exists and is current",
    "check draft-preview (gmail-draft.6): the dry run of `jason draft` shows a subject and suggested addresses",
    "check vault-answers (integration-connect.3): the backend answers (names only), or says it is not signed in",
    # jobs (readers.JOBS): none wanted. mail-sync, gmail-sync, responses-check, and responses-read are registered as descriptors
    # (jason.workflows.jobs, jobs.READY); their steps stay a person's, and each why still names the job it becomes
    # approvals kinds (the registry)
    "plan payhoa-requests-from-email (email-conversation.6): enter an emailed request in PayHOA (R2, one person)",
    "plan gmail-thread-reply (email-conversation.9): a reply draft in the thread (a second approvals kind)",
    # engine and registry
    "clock basis provider: a vendor's published limit or a credential's life (the page's decision 2); counterparty is used meanwhile",
    "role developer: check-in is a developer's terminal procedure; administrator is used meanwhile",
    "visibility: hide a definition from every viewer who is not an administrator signed in as themselves (ADMIN_KEYS)",
    "per-step item sets: the letters of a period and the arrivals of a request change after the run starts",
    "needs per item: a letter's choice should not wait for every letter to be read",
)


def _maker(key: str) -> Callable[..., StepDef]:
    def step(n: str, title: str, kind: StepKind, role: Role, needs: tuple[str, ...] = (), **more: Any) -> StepDef:
        return StepDef(f"{key}.{n}", title, kind, role=role, needs=tuple(f"{key}.{x}" for x in needs), **more)
    return step


def _ids(key: str, *numbers: str) -> tuple[str, ...]:
    return tuple(f"{key}.{n}" for n in numbers)


def _phases(key: str, *rows: tuple[str, str, tuple[str, ...]]) -> tuple[Phase, ...]:
    return tuple(Phase(k, t, _ids(key, *ns)) for k, t, ns in rows)


def _built(key: str, title: str, subject: str, steps: tuple[StepDef, ...], phases: tuple[Phase, ...],
           procedure: str = "") -> Workflow:
    ids = {s.id for s in steps}
    assert all(x in ids for p in phases for x in p.steps), key
    assert {x for p in phases for x in p.steps} == ids, f"{key}: every step is in a phase"
    return Workflow(key=key, title=title, family="platform", subject=subject, steps=steps, dates=(), phases=phases,
                    procedure=procedure, visibility=Visibility.ADMIN if key in ADMIN_KEYS else Visibility.BOARD,
                    console_start=key != CI)


STALE_PROPOSED = "proposed policy: the cadence and its stale-after are proposed, and nothing runs until a person adopts them"


# --- mail-triage ------------------------------------------------------------------------------------------------------

def mail_triage() -> Workflow:
    """Paper mail, a period at a time (docs/workflows/mail-and-platform.md, 2.1). The subject is ``period:YYYY-MM-DD`` and the
    letters of the period are the run's items, opaque mail ids; no sender, address, or word of a letter is a label, a record,
    or a reason. A letter that carries a credential is held (P4): it opens in no screen, and its ``read`` records only
    "read at a terminal". The 10-day escrow clock (CIV 4530(a)(1)) is on ``checks``; the shred or discard of a legal,
    insurance, tax, or escrow letter is a question for the board and counsel, recorded beside the choice."""
    s = _maker(MT)
    steps = (
        s("1", "Is the mailbox read recently?", C, JASON, command="jason mail --offline", check=named_check("mail-fresh"),
          clock=ClockDef(ClockBasis.PROPOSED_POLICY, label="stale after 3 days (" + STALE_PROPOSED + ")"),
          why="Read the store's own age first (the check mail-fresh: the mail store's last read against the source's stale-after). "
              "Stale or never read fails it and names the command, which a person runs at a terminal before the run goes on. "
              "Never skipped: a lane without the age of the read is not shown."),
        s("2", "Read the mailbox", P, M, ("1",), command="jason mail", skip=MANAGER_ONLY,
          record="the date the mailbox was read again",
          clock=ClockDef(ClockBasis.PROPOSED_POLICY, label="daily 08:00, floor 1 hour (" + STALE_PROPOSED + ")"),
          why="Skipped, with the reason, when the mailbox is fresh. If it cannot be read the mail integration needs a sign-in "
              "(run integration-connect, the administrator's): no letters are listed as new. Becomes a job (mail-sync)."),
        s("3", "Check letters against jason's records", P, M, ("1", "2"), command="jason mail --checks",
          record="the number of findings read (a count, not a letter)",
          clock=ClockDef(ClockBasis.LAW, cite="CIV 4530(a)(1)", label="an escrow or resale request: 10 days from its mailing or "
                         "delivery; jason counts from the day the mail service received it, which is a reading"),
          why="Findings are leads for a person: addresses, escrow clocks, tax bills, bank balances, checks, preliminary notices. "
              "Becomes a check (mail-findings). The start day is jason's reading, not a ruling."),
        s("4", "Read the lanes", C, JASON, ("1", "2"), command="jason mail --days 30", evidence=("file:mail/items.json",),
          check=named_check("mail-lanes"),
          clock=ClockDef(ClockBasis.PERSON, label="a date a letter states is a reading until a person confirms it"),
          why="The lanes as counts (the check mail-lanes): act, review, not scanned, and the rest. A sort, not a reading of any "
              "letter; the letters of the period are this run's items."),
        s("5", "Read each letter", P, M, ("4",), command="jason mail --item ID", repeat=ITEM,
          record="read, or read at a terminal for a held letter",
          why="Held: a letter that carries a credential opens in no screen (P4); read the PDF at a terminal and attest only "
              "'read at a terminal'. Never put a letter's words in a record. The secretary may read too; the engine gives a "
              "step one role."),
        s("6", "Is the sort right, and whose is it?", B, M, ("5",), repeat=ITEM,
          choices=(Choice("board"), Choice("counsel"), Choice("bill"), Choice("file"), Choice("another-association")),
          why="Board, counsel, bill, file, or another association's mail (misdirected, to return or correct with the sender, "
              "never to the board). The engine cannot skip steps per item, so the board step is skipped by hand."),
        s("7", "Record the choice", P, M, ("5",), repeat=ITEM, skip=MANAGER_OR_SECRETARY,
          record="the choice: scan, forward, shred, discard, or keep; no word of the letter",
          why="There is no CLI: the console writes data/mail/triage.json (jason mail --choose is proposed). A later choice "
              "replaces this one and the history keeps both. A shred or discard of a legal, insurance, tax, or escrow letter "
              "is a question for the board and counsel (CIV 5210(a)(1); a records-retention policy is the board's): jason "
              "records the choice and the question, and decides nothing."),
        s("8", "Carry it out at the mail service", P, M, ("7",), repeat=ITEM, skip=MANAGER_ONLY,
          record="the date it was done at the service",
          why="At the service's own site; jason scans, forwards, shreds, and discards nothing, and the service may bill. "
              "Skipped, with the reason, for a letter kept. Nothing in jason can tell it is undone: no step turns done on a guess."),
        s("9", "Wait for the scan", W, M, ("8",), repeat=ITEM, skip=MANAGER_ONLY, command="jason mail",
          check=named_check("mail-scanned"),
          why="Ends when the next read shows the letter scanned (the check mail-scanned), or a person notes the arrival. The age "
              "is jason's own measure "
              "(the median delivery-to-scan time), never a deadline: 'not scanned yet, N days', not failed. Skipped for a "
              "letter whose choice is not a scan."),
        s("10", "Act on a stated date", P, M, ("5",), repeat=ITEM, skip=MANAGER_ONLY,
          command="jason followups --add --date D --text T --by NAME", record="the follow-up added, with its date",
          clock=ClockDef(ClockBasis.PERSON, label="the letter's stated date, a person's once confirmed"),
          why="Skipped, with the reason, for a letter that states no date. The date is a reading from words near 'due', "
              "'respond', or 'effective' until a person confirms it."),
        s("11", "Put it before the board", D, S, ("6",), repeat=ITEM, skip=SkipRule((S, M)),
          record="the board's decision as taken, with its meeting",
          why="Skipped, with the reason, unless the sort sent the letter to the board. The meeting is the meetings family's; the "
              "board item is made at Board action items (the command is not verified). jason decides nothing."),
        s("12", "Close the period", C, JASON, ("7",), check=named_check("mail-period-chosen"),
          why="Done when every letter of the period has a recorded choice (the check mail-period-chosen: 'chosen' equals 'items' "
              "in the mail-triage loader)."),
    )
    phases = _phases(MT, ("read", "Read the mail", ("1", "2", "3", "4")), ("triage", "Read and choose", ("5", "6", "7")),
                     ("carry", "Carry out and act", ("8", "9", "10", "11")), ("close", "Close", ("12",)))
    return _built(MT, "Paper mail triage", "period", steps, phases)


# --- email-conversation -----------------------------------------------------------------------------------------------

_THREAD_STEPS = ("7", "8", "9", "10", "11", "12", "13", "14")      # leads .. handled: the paths that get an answer


def email_conversation() -> Workflow:
    """One Gmail thread, from the sync to the answer (2.2). The subject is the thread id, opaque; a person opens the run from
    an Inbox row and jason never does. The headers carry names, so no label, record, or reason does. A thread that is
    executive, legal, or counsel's is held for the private view: the ``held`` path ends the run here. A general reply time
    is proposed policy (``response-standards``): the law is silent, so there is no date until the board adopts one. A
    records request is the exception: Civil Code 5210(b) is the clock on ``request``."""
    s = _maker(EC)
    answers = _ids(EC, *_THREAD_STEPS)
    steps = (
        s("1", "Is Gmail read recently?", C, JASON, command="jason gmail", check=named_check("gmail-fresh"),
          clock=ClockDef(ClockBasis.PROPOSED_POLICY, label="stale after 1 hour (" + STALE_PROPOSED + ")"),
          why="The check gmail-fresh: the Gmail store's last read against its stale-after. Checked at each open: what is "
              "awaiting us is only as new as the last read. Stale fails it and names the command a person runs at a terminal."),
        s("2", "Read Gmail headers", P, M, ("1",), command="jason gmail --sync", skip=MANAGER_ONLY,
          record="the date of the read",
          clock=ClockDef(ClockBasis.PROPOSED_POLICY, label="every 10 minutes 07-22, hourly outside, floor 2 minutes (the floor is "
                         "the provider's published quota; adoption is proposed)"),
          why="Headers only, no bodies. Skipped, with the reason, when fresh. Becomes a job (gmail-sync)."),
        s("3", "Whose move is it?", C, JASON, ("1", "2"), command='jason threads --status "awaiting us"',
          check=named_check("thread-status"),
          why="The status from the thread's last message (the check thread-status): awaiting us, awaiting them, notice, or "
              "internal. Always with the caveat that someone may have answered by phone, in person, or from another mailbox, "
              "which jason cannot see. A later inbound message reopens it."),
        s("4", "Read what it asks", P, M, ("3",), command="jason inbox; jason replies",
          record="the intent and topics read (a reading, labeled), and where an answer is likely written",
          clock=ClockDef(ClockBasis.PROPOSED_POLICY, label="response-standards is a proposed policy, not adopted: no usual reply "
                         "time on record, so no date"),
          why="The law is silent on a general reply time; 'likely needs a response' and 'past the usual time' are jason's count "
              "from the association's own history, not a standard, and a question for the board. Leads, never rulings."),
        s("5", "Which path?", B, M, ("4",),
          choices=(Choice("request", _ids(EC, "6") + answers), Choice("vendor", answers), Choice("counsel", answers),
                   Choice("government", answers), Choice("notice"), Choice("held")),
          why="A member's request, a vendor, counsel, a government office, a notice (close), or executive or legal "
              "('held': it opens in the private view and this run ends)."),
        s("6", "Enter an emailed request in PayHOA", P, M, ("5",),
          command="jason request-links --create THREAD --message TEXT --yes", record="the PayHOA request entered (its id)",
          clock=ClockDef(ClockBasis.LAW, cite="CIV 5210(b)", label="records requested by a member: access within 10 business days "
                         "(the current fiscal year) or 30 calendar days (the previous two), from receipt; whether this is a "
                         "proper request for association records is a reading, not jason's"),
          why="A person's --yes; the request is never approved, denied, or assigned. Becomes a plan step when the approvals "
              "kind payhoa-requests-from-email (R2, one person) is registered. Business days skip weekends, not holidays."),
        s("7", "What sits near it", P, M, ("4",), command="jason threads; jason party UNIT",
          record="the leads read (counts): payments, letters, Drive files, PayHOA requests",
          why="From 14 days before to 60 after; leads, never answers. Becomes a check (thread-leads)."),
        s("8", "Decide the reply", B, M, ("5", "7"),
          choices=(Choice("reply", _ids(EC, "9", "11", "12", "13", "14")), Choice("forward", _ids(EC, "10", "12", "13", "14")),
                   Choice("answered", _ids(EC, "14")), Choice("none")),
          why="Reply, forward, answered by other means, or no reply needed. The board decides first if the answer commits the "
              "association (a hearing, an acceptance, a contract); this step records the manager's choice and nothing else."),
        s("9", "Prepare a draft", P, M, ("8",), command="jason respond --draft email:ID --gmail --yes", sop="respond#3",
          record="the draft saved in the thread, or 'written in Gmail'",
          why="A built case goes through gmail-draft; a reply in the thread has no approvals kind yet (becomes a plan step "
              "when gmail-thread-reply is registered). A person reads, edits, and sends it."),
        s("10", "Forward or assign", P, M, ("8",), command="jason followups --add",
          clock=ClockDef(ClockBasis.PERSON, label="the follow-up date the person states"),
          record="the assignee and follow-up date as the person states them",
          why="A forward is never an answer."),
        s("11", "Send it", P, M, ("9",), record="the date sent from Gmail",
          why="jason has no send method; the next sync sees the outbound message."),
        s("12", "Wait for the other side", W, M, ("11", "10"), command="jason gmail --sync",
          clock=ClockDef(ClockBasis.PERSON, label="the follow-up date; 'past the usual time' is labeled as the association's reply history"),
          why="Ends when an inbound message arrives or the follow-up date passes; a person notes the arrival."),
        s("13", "Ask again", P, M, ("12",), skip=MANAGER_ONLY,
          command="jason followups --done ID --by NAME (or --defer, --drop)",
          clock=ClockDef(ClockBasis.PERSON, label="the person's date"),
          record="the follow-up done, deferred, or dropped, with its reason",
          why="Skipped, with the reason, when the other side answered."),
        s("14", "Mark handled offline", P, M, ("4",), skip=MANAGER_ONLY, record="a note: who handled it and on what day",
          why="Append-only and a person's word; a later message reopens the run. There is no CLI and no store yet."),
        s("15", "Close", P, M, ("5", "8", "11", "10"), record="the status read, or a person's note",
          why="Done when the status is awaiting them or internal, or a person has noted it. Becomes a check (thread-closed)."),
    )
    phases = _phases(EC, ("read", "Read the thread", ("1", "2", "3", "4")), ("route", "Route", ("5", "6", "7", "8")),
                     ("answer", "Answer", ("9", "10", "11")), ("follow", "Follow up", ("12", "13", "14", "15")))
    return _built(EC, "Email awaiting us, sync to answer", "thread", steps, phases, procedure="")


# --- gmail-draft ------------------------------------------------------------------------------------------------------

def gmail_draft() -> Workflow:
    """A Gmail draft from an item, never sent (2.3). The subject is ``<case>:<key>`` with the case one of ``CASES``, the cases
    of the approvals kind ``gmail-drafts`` (a free-text reply composer is not built). jason never picks who an email goes to
    and never sends it: the person chooses ``to`` and ``cc``, one named approver decides the plan, and the person reads the
    draft in Gmail and sends it. The record names a count of recipients, never an address. A purpose that commits the
    association is not a case: the board's decision is recorded and the run ends."""
    s = _maker(GD)
    plan_path = _ids(GD, "5", "6", "7", "8", "9", "10")
    steps = (
        s("1", "Is the source there and current?", P, M, command="jason inspections; jason hearing; jason board --agenda DOC_ID",
          record="the source found: a system, a saved hearing, or the agenda file",
          why="A system in jason inspections, a saved hearing, or the agenda file jason board --agenda writes. The run says "
              "'stale' when the source changes later. Becomes a check (draft-source)."),
        s("2", "Choose the case", P, M, ("1",), record="the case: proposal-request, hearing, or meeting-notice",
          why="One of the three built cases of the gmail-drafts kind; a free-text composer is not built."),
        s("3", "Does it commit the association?", B, M, ("2",),
          choices=(Choice("no", plan_path), Choice("yes", _ids(GD, "4"))),
          why="None of the three cases accepts, authorizes, or gives notice under a contract. A purpose that does is not a "
              "case: answer yes, the board's recorded decision comes next, and this run ends."),
        s("4", "The board's recorded decision", D, S, ("3",), record="the meeting and the motion",
          why="Only for a purpose that commits the association; the meeting is the meetings family's."),
        s("5", "Choose to and cc", P, M, ("2", "3"), record="the number of addresses chosen (no address)",
          why="None is a default and nothing comes from a document's text; at most 10, each a plain address. A member's name "
              "or unit never goes to a vendor: the kind has no automatic block, so this is the person's check."),
        s("6", "See the email without a recipient", P, M, ("2", "3"), command="jason draft --proposal-request SYSTEM",
          record="the subject and the suggestions seen",
          why="A dry run: a plan with no 'to' has no item ('nothing to approve: jason never picks who an email goes to'). "
              "Becomes a check (draft-preview)."),
        s("7", "Plan, decide, apply", PL, M, ("5", "6"), plan_kind="gmail-drafts",
          command="jason approvals plan gmail-drafts --scope JSON --by NAME",
          why="One item (subject, recipients, attachment names, the body with any line giving a code withheld) and a hash of the "
              "composed email; one named approver decides, then apply (jason approvals decide, submit, apply ID --yes --by NAME). "
              "Planned again after 6 hours (the kind's own limit, not a deadline); a changed source supersedes it. "
              "An apply that times out may have saved the draft: look in Gmail's drafts before planning again."),
        s("8", "Read it in Gmail and send", P, M, ("7",), record="the date sent from Gmail",
          why="jason never sends."),
        s("9", "Sent? Answered?", W, M, ("8",), command="jason gmail --sync",
          why="Ends when the sync sees a later outbound or inbound message; a draft deleted in Gmail reads 'withdrawn'."),
        s("10", "Ask again", P, M, ("9",), skip=MANAGER_ONLY, command="jason followups --add",
          clock=ClockDef(ClockBasis.PERSON, label="the person's date, or the purpose's proposed number (labeled proposed)"),
          record="the follow-up added", why="Optional; a purpose's suggested number is proposed policy and carries no stamp."),
    )
    phases = _phases(GD, ("source", "Source and purpose", ("1", "2", "3", "4")), ("plan", "Plan", ("5", "6", "7")),
                     ("send", "Send and follow", ("8", "9", "10")))
    return _built(GD, "A Gmail draft from an item", "draft", steps, phases)


# --- response-inbox ---------------------------------------------------------------------------------------------------

def response_inbox() -> Workflow:
    """A returned form, recognized, read, and confirmed (2.4). The subject is a request key; the arrivals are the items, opaque
    ids. This ends at 'confirmed' and hands over: the cycle's dates, the return-by clocks, and the apply belong to the
    members family, so ``handover`` is a person step that points to that run rather than adopting its plan. A reading is
    evidence for a person, never an answer; no record holds an answer."""
    s = _maker(RI)
    steps = (
        s("1", "Look at every channel", P, M, command="jason responses --check", sop="owner-info-cycle#14",
          record="the check made, with its date",
          clock=ClockDef(ClockBasis.PROPOSED_POLICY, label="stale after 1 day; responses-gmail hourly and responses-payhoa every "
                         "2 hours are proposed cadences"),
          why="PayHOA, email, a mailed scan, a Google Form, keyed by hand; a channel no request uses is skipped. Becomes a job "
              "(responses-check)."),
        s("2", "Did each channel answer?", C, JASON, ("1",), command="jason responses --list",
          check=named_check("responses-channels"),
          why="Each channel's end (the check responses-channels): ok, sign-in, failed, skipped, or never checked, with the last "
              "success. A sign-in end pauses that integration's sources; no retry on a timer."),
        s("3", "Whose copy is it?", C, JASON, ("1",), repeat=ITEM, command="jason responses --check",
          check=named_check("responses-recognized"),
          why="Recognition runs inside --check and --read, by rung, with how sure. The check responses-recognized says "
              "recognized (a sent copy), candidate (a form, no copy), or not ours from the arrival's stored reading, or from its "
              "subject alone when it is not read yet (then a subject naming no copy of ours is 'not decided', never 'not ours'). "
              "A reference jason did not send is a finding, not an arrival. A lead for the person at the next step, never an answer."),
        s("4", "Recognized, candidate, or not ours", B, M, ("3",), repeat=ITEM,
          choices=(Choice("recognized"), Choice("candidate"), Choice("not-ours")),
          why="Recognized goes on; a candidate is attached to a campaign by a person (the command is not verified); not ours "
              "leaves, and the steps after are skipped by hand."),
        s("5", "Look at it", P, M, ("4",), repeat=ITEM, skip=MANAGER_OR_SECRETARY,
          command="jason responses --seen ID --by NAME", sop="owner-info-cycle#14", record="seen, with the arrival id",
          why="Skipped, with the reason, for an arrival that is not ours."),
        s("6", "Read the returned form", P, M, ("5",), repeat=ITEM, skip=MANAGER_OR_SECRETARY,
          command="jason responses --read ID --by NAME", sop="owner-info-cycle#14", record="the reading made (one per file hash)",
          why="A reading is evidence, never an answer; a PayHOA or Google Form arrival is structured and skips it. A model "
              "reading holds the GPU lock and fails fast short of commit. Becomes a job (responses-read)."),
        s("7", "Confirm what it says", P, M, ("6",), repeat=ITEM, command="jason responses --confirm ID --by NAME [--set F=V]",
          sop="owner-info-cycle#14", record="the arrival confirmed, and the fields corrected by name (no answer)",
          why="Nothing is an answer until a person confirms it. The copy comparison (sent to, written, read) shows a wrong unit."),
        s("8", "Not an answer", P, M, ("3",), repeat=ITEM, skip=MANAGER_ONLY,
          command="jason responses --dismiss ID --by NAME --why TEXT", record="dismissed, with the reason",
          why="Optional, before the answer is recorded; not reversible today. The reason names no owner."),
        s("9", "Key a paper return", P, M, (), skip=MANAGER_ONLY, command="jason responses --add-manual",
          record="a manual arrival, naming how it came",
          why="Optional; for a return that came on paper or by phone and is in no channel."),
        s("10", "Who has not answered", C, JASON, ("1",), command="jason responses --outstanding", sop="owner-info-cycle#15",
          check=named_check("responses-outstanding"),
          why="Owners sent a copy less answers, as counts (the check responses-outstanding; no unit, name, or address). "
              "Never-asked and unreachable owners are listed apart. The cycle dates are the members family's."),
        s("11", "Apply the confirmed answers", P, M, ("7",), command="jason owner-info --apply --payhoa", sop="owner-info-cycle#17",
          record="the run or approval that applies them (an id)",
          why="Hand over to the members family: the owner-info-tags plan is in the owner-information run, which adopts it. This "
              "run does not, so two runs never take one plan. 'Recorded' follows the writes."),
    )
    phases = _phases(RI, ("check", "Check the channels", ("1", "2", "9")), ("read", "Recognize and read", ("3", "4", "5", "6")),
                     ("confirm", "Confirm and hand over", ("7", "8", "10", "11")))
    return _built(RI, "The response inbox", "request", steps, phases)


# --- integration-connect (the administrator's; not registered) -----------------------------------------------------------

def integration_connect() -> Workflow:
    """Connect an integration and keep it connected (2.5), with the disconnect (docs/console/screens/integration-disconnect.md).
    The subject is an integration for one community, or for the instance (``integration:KEY``); the run stays open as the
    watch (``keep``). Every step is the administrator's own, at a terminal or a browser, in their own name: jason never
    connects, signs in, checks live, or revokes. The vault is the development environment's store only (Keeper); a hosted
    installation reads its own secret store, so the vault steps are skipped there with a reason, and no step assumes it. No
    credential, token, or account number is ever a record: a record names a path or a token name, never a value. Not
    registered (see the module note): only an administrator signed in as themselves may see it."""
    s = _maker(IC)
    steps = (
        s("1", "Which community and data folder?", C, JASON, command="jason which; jason use --list", sop="onboard#1",
          check=named_check("instance-which"),
          why="Never skipped: a default community must be visible before any --yes command (lesson a-default-community-must-be-visible). "
              "The check instance-which records the community in use and where the choice came from, and says when it is a default."),
        s("2", "Read the integration's state", C, JASON, ("1",), command="jason integrations list",
          check=named_check("integration-state"),
          clock=ClockDef(ClockBasis.PROPOSED_POLICY, label="stale after the integration's own stale-after (the defaults are proposed)"),
          why="One of: not set up, needs sign-in, connected, failing, paused (the check integration-state), from disk and the "
              "settings with counts and dates, never an account, a path, or an error's words. The vault is not asked, so a "
              "credential kept only there reads as not set. 'Connected' is never taken from here until a live check by a person "
              "succeeds (step 8)."),
        s("3", "Does the credential store answer?", P, A, ("1",), command="jason vault status", sop="onboard#13",
          skip=ADMIN_ONLY, record="the backend, and whether it answers (names only)",
          clock=ClockDef(ClockBasis.COUNTERPARTY, label="provider: Keeper signs out after 30 days idle; the design warns from day 25 "
                         "(not verified as built)"),
          why="The vault is the development environment's store; a hosted installation reads its own, chosen when it is hosted, "
              "and skips this with that reason. Becomes a check (vault-answers)."),
        s("4", "Sign in to the store", P, A, ("3",), command="jason login", skip=ADMIN_ONLY, record="a fresh session, by date",
          clock=ClockDef(ClockBasis.COUNTERPARTY, label="provider: 30 days idle"),
          why="Skipped, with the reason, when the store answers or the installation has none. An interactive terminal only; "
              "an agent never signs in."),
        s("5", "Set up the provider's console", P, A, ("1",), repeat=ITEM, skip=ADMIN_ONLY, sop="onboard#6",
          record="the setup step done (a name, no value)",
          clock=ClockDef(ClockBasis.COUNTERPARTY, label="provider: a redirect URI may take minutes to hours to take effect"),
          why="Per setup step the registry names: a Cloud project, the APIs, branding, audience Internal, scopes, a Web client, or "
              "a Zoom app (docs/google-workspace-setup.md). Skipped for an integration that needs none."),
        s("6", "Put the credential in the store", P, A, ("5", "4"), sop="onboard#6",
          command="jason google setup --from-file F --yes; jason vault migrate (then --yes)",
          record="the entry is 'set' at its path (never its value)",
          why="The registry names jason integrations import, which does not exist; use the commands shown. In a hosted "
              "installation the secret goes to that installation's own store."),
        s("7", "Consent once", P, A, ("6",), repeat=ITEM, command="jason google sign-in --name drive --interactive", sop="onboard#6",
          record="the token name saved to the store (no value)",
          clock=ClockDef(ClockBasis.COUNTERPARTY, label="provider: a refresh token is given once, at consent; never retry an 'invalid grant' error"),
          why="One sign-in per token name, in a browser; the token is saved at once (lesson "
              "a-consent-gives-the-refresh-token-once-save-it-first)."),
        s("8", "A read that proves it", P, A, ("7",), command="jason integrations check KEY --live --by NAME", sop="onboard#13",
          record="connected, by the administrator's name, and the read that proved it",
          why="Only a person at a terminal, never an agent or a timer. Repeats after any failure; a failure shows in plain words, "
              "masked of emails, numbers, and tokens."),
        s("9", "Which capabilities are on", P, A, ("8",), skip=ADMIN_ONLY, record="the capabilities on",
          why="Read capabilities on; a write capability stays off until used, and each use still needs --yes. This is "
              "configuration, not a decision for the board, so it is a person step; how it is switched at a terminal is not verified."),
        s("10", "Adopt the schedules", P, A, ("8",), repeat=ITEM, skip=ADMIN_ONLY, command="jason cadence --restore SOURCE --by NAME",
          sop="onboard#14", record="the source adopted",
          clock=ClockDef(ClockBasis.PROPOSED_POLICY, label="defaults and floors are published by the provider; adopting them is proposed"),
          why="Never faster than a source's floor and never a write: a scheduled write is the board's decision (lesson "
              "scheduled-defaults-need-adoption)."),
        s("11", "Wait for the first scheduled read", W, A, ("10",), repeat=ITEM, command="jason cadence",
          why="Ends when the source's last-read stamp shows on Status; a person notes the arrival."),
        s("12", "Stay connected", W, A, ("8",), command="jason integrations list",
          clock=ClockDef(ClockBasis.COUNTERPARTY, label="provider: Keeper day 25; Google tokens end after six months unused, on a "
                         "password change with Gmail scopes, at the 101st token, or after seven days in Testing"),
          why="The watch: it reopens on needs sign-in, failing, paused, or a token near its end, and each end opens the sign-in "
              "or the login again. A sign-in pause clears only on a good live check or --resume "
              "(lesson keeper-login-does-not-clear-sign-in-pause)."),
        s("13", "Disconnect, pause instead, or keep", B, A,
          choices=(Choice("keep"), Choice("pause-instead", _ids(IC, "13.1")),
                   Choice("disconnect", _ids(IC, "13.1", "13.2", "13.3", "13.4"))),
          why="Designed, not built: the jason integrations disconnect command (KEY --community C --yes --by NAME) does not exist, so "
              "each part is a person's step. Refused for an instance integration, the vault, an integration with nothing to "
              "connect, and the console sign-in. To undo, reconnect from the start: a deleted credential cannot be restored."),
        s("13.1", "Pause the integration's schedules", P, A, ("13",), command="jason cadence --pause SOURCE --why TEXT --by NAME",
          record="the sources paused (names)",
          why="A person's pause, so a later good check cannot restart reads. Data already read stays where it is; queued jobs "
              "and planned approvals that name this integration are not cancelled."),
        s("13.2", "Revoke the grant at the provider", P, A, ("13.1",), skip=ADMIN_ONLY,
          record="revoked at the provider by hand, on the day, and what was done",
          why="jason cannot revoke today: remove the app in Google's account page or Admin console, deactivate a Zoom app in its "
              "Marketplace, change the password where that ends a grant. Revoke before deleting: the entry is the only copy of "
              "a refresh token. Skipped, with the reason, where there is no grant."),
        s("13.3", "Delete the credential entry", P, A, ("13.2",), skip=ADMIN_ONLY,
          record="the path deleted (a name, never a value)",
          why="Designed as the third part of the disconnect; no command calls the store's delete for it yet. Another holder of "
              "the same credential (a legacy .env record, a local token file) stays until a person removes it."),
        s("13.4", "Record the disconnect", P, A, ("13.3",), record="disconnected on the day, state 'not set up'",
          why="The log of connection acts is designed, not built (integration-acts.jsonl, append only, counts and names, never a value)."),
    )
    phases = _phases(
        IC, ("find", "Where it stands", ("1", "2", "3", "4")), ("connect", "Connect", ("5", "6", "7", "8", "9")),
        ("adopt", "Adopt and watch", ("10", "11", "12")), ("disconnect", "Disconnect", ("13", "13.1", "13.2", "13.3", "13.4")))
    return _built(IC, "Connect an integration", "integration", steps, phases)


# --- service-run (the administrator's; not registered) ----------------------------------------------------------------

def service_run() -> Workflow:
    """Running the service (2.6). The subject is a community's service, ``service:COMMUNITY`` (an install, or a recovery after
    a stale or stopped heartbeat; healthy operation is a state on Status, not an open run). The administrator's alone, so it
    is not registered (see the module note). jason starts nothing here: the start, a limit change, the drain, and the
    schedules are the administrator's commands, shown and never run. The heartbeat constants (beat 30 s, stale 90 s) are
    jason's own, not a policy. Whether a scheduled write is allowed is the board's decision, left standing open."""
    s = _maker(SR)
    steps = (
        s("1", "Which community?", C, JASON, command="jason which", sop="onboard#1", check=named_check("instance-which"),
          why="Never skipped (lesson a-default-community-must-be-visible). The check instance-which records the community in use."),
        s("2", "Is the service alive?", C, JASON, ("1",), command="jason daemon status", check=named_check("service-heartbeat"),
          why="The heartbeat file, judged as jason serve judges it (the check service-heartbeat): none, running, draining, "
              "stale, or stopped. Stale is 90 seconds with no beat, beating every 30 (jason's own constants). A stale beat may "
              "be a hung process; Task Scheduler restarts a failure, not a hang (lesson task-restart-on-failure-limits, open). "
              "Reads the file only; it contacts no process."),
        s("3", "Start it", P, A, ("2",), skip=ADMIN_ONLY, sop="onboard#14",
          command="jason serve; jason serve --install-task (then --yes)", record="running, by date",
          why="At a terminal, the install as an administrator of the machine; skipped, with the reason, when it is running. "
              "The service has no log under Task Scheduler (lesson serve-logs-nowhere-under-task-scheduler, open)."),
        s("4", "Why did it refuse?", B, A, ("2",), skip=ADMIN_ONLY, command="jason daemon status",
          choices=(Choice("second-process"), Choice("part-failed")),
          why="Another worker holds the community (a second process), or a part failed. Skipped when it did not refuse."),
        s("5", "Check the limits in force", C, JASON, ("1",), command="jason limits", check=named_check("service-limits"),
          why="Each limit's value, source, range, and last change (the check service-limits): counts, and for a limit that is not "
              "the code's default its key, value, layer, range, and day. A limits file that cannot be read fails it: jason holds "
              "the stricter value until it is fixed."),
        s("6", "Change a limit", P, A, ("5",), repeat=ITEM, skip=ADMIN_ONLY,
          command="jason limits --set KEY=VALUE --reason TEXT --by NAME (then again with --yes)",
          record="the limit and the reason (no names in it)",
          why="A dry run, then a confirmed change; recorded under the signed-in name."),
        s("7", "Adopt the schedules", P, A, ("2",), repeat=ITEM, sop="onboard#14",
          command="jason cadence; jason cadence --restore SOURCE --by NAME", record="the source adopted",
          clock=ClockDef(ClockBasis.PROPOSED_POLICY, label="defaults and floors; adopting them is proposed"),
          why="As in integration-connect: never faster than the floor, never a write."),
        s("8", "Allow a scheduled write?", D, S, ("7",), skip=ADMIN_ONLY,
          record="the board's decision, recorded or refused",
          why="The board's, and a standing open decision: until it is recorded the scheduler refuses every --yes command. "
              "Skipped, with the reason, when the board has not been asked."),
        s("9", "A sign-in pause", B, A, ("7",), repeat=ITEM, skip=ADMIN_ONLY,
          command="jason cadence --resume SOURCE --by NAME", choices=(Choice("sign-in"), Choice("person")),
          why="A pause by sign-in clears only on a good live check (jason integrations check KEY --live) or --resume; a person's "
              "pause clears only by --resume. Skipped when nothing is paused."),
        s("10", "Read the queue", C, JASON, ("2",), command="jason jobs", check=named_check("service-queue"),
          why="The queue as counts: queued, running, failed, done (the check service-queue). A failed read retries 3 times, "
              "5 minutes apart; a failed write waits for a person."),
        s("11", "Ask it to stop", P, A, ("2",), skip=ADMIN_ONLY, command="jason daemon stop", record="the drain requested, by date",
          why="Writes only the drain request: each lane finishes its running job, a write is never cut, nothing is killed."),
        s("12", "Everything current?", C, JASON, ("7",), command="jason storage --check", check=named_check("service-verify"),
          why="Each source against its own stale-after, a fresh heartbeat, and room on the drives jason writes to (the check "
              "service-verify). A stale, failed, or not-signed-in source fails it; a source never read is counted and does not "
              "(a community may not use every source). Free space is said as at least or under 20 GB, never as a figure."),
    )
    phases = _phases(SR, ("find", "Where it stands", ("1", "2", "3", "4")), ("limits", "Limits", ("5", "6")),
                     ("schedule", "Schedules", ("7", "8", "9")), ("watch", "Queue and stop", ("10", "11", "12")))
    return _built(SR, "Run the service", "service", steps, phases)


# --- check-in (a developer's; not registered) -----------------------------------------------------------------------------

def check_in() -> Workflow:
    """Checking work in and recording lessons (2.7), the ``check-in`` procedure as a run. A developer's terminal procedure the
    console never starts, advances, or lists, so it is not registered (see the module note). The engine has no developer
    role, so every step is the administrator's. jason never commits or pushes: the commit is a person's, by path, because other
    sessions stage in the shared index, and a push waits for the person to say so."""
    s = _maker(CI)
    steps = (
        s("1", "Keep the community's facts in the profile", P, A, command="pytest tests/test_profile.py", sop=f"{CI}#1",
          record="the boundary test passed", why="No association fact in general code, docs, or fixtures."),
        s("2", "Is the new file's name free?", P, A, repeat=ITEM, command="ls PATH; git status --short PATH", sop=f"{CI}#2",
          record="the path is free, or it is a file meant to change",
          why="Write replaces an existing file silently (lesson new-module-name-already-taken)."),
        s("3", "Made-up values in fixtures", P, A, repeat=ITEM, sop=f"{CI}#3", record="the fixture checked",
          why="The operator's own ids stay in .env (lesson no-real-data-in-fixtures)."),
        s("4", "Scan what will be committed", P, A, ("1",), command="git diff --staged", sop=f"{CI}#4",
          record="the diff scanned",
          why="No owner or deed party, personal mailbox, signed link, or token; no vendor, street, or association name in a "
              "general module's comment (lesson comment-carried-profile-facts)."),
        s("5", "Commit; push only when told", P, A, ("4", "1"), command="git commit -- PATHS", sop=f"{CI}#5",
          record="the commit, by path",
          why="Other sessions stage in the shared index, so a commit names its paths and its stat is read."),
        s("6", "Record what went wrong", P, A, skip=ADMIN_ONLY,
          command="jason lessons --area AREA", record="the lesson added, with its status",
          why="A lesson true of any association goes in src/jason/community/lessons.py, a private one in the profile's lessons.py; "
              "a fixed lesson names its guard. Skipped, with the reason, when nothing went wrong."),
        s("7", "Update the procedure", P, A, ("6",), skip=ADMIN_ONLY, command="jason sop KEY",
          record="the procedure step added or changed, naming the lesson",
          why="With each lesson, in procedures.py. Skipped when there is no lesson."),
    )
    phases = _phases(CI, ("before", "Before the commit", ("1", "2", "3", "4")), ("commit", "Commit", ("5",)),
                     ("lessons", "Lessons", ("6", "7")))
    return _built(CI, "Check work in", "change", steps, phases, procedure=CI)


BOARD_BUILDERS: tuple[Callable[[], Workflow], ...] = (mail_triage, email_conversation, gmail_draft, response_inbox)
"""The manager's mail and email runs (``KEYS``): every office that opens P2 sees them."""

ADMIN_BUILDERS: tuple[Callable[[], Workflow], ...] = (integration_connect, service_run, check_in)
"""The administrator's (``ADMIN_KEYS``, ``Visibility.ADMIN``): listed, read, and started by an administrator only. ``check_in``
is a terminal procedure the console never starts (``console_start`` is False)."""

BUILDERS: tuple[Callable[[], Workflow], ...] = BOARD_BUILDERS + ADMIN_BUILDERS
"""The definitions ``register_general`` registers: the four above and the three of the administrator."""


__all__ = ["ADMIN_BUILDERS", "ADMIN_KEYS", "BOARD_BUILDERS", "BUILDERS", "CASES", "KEYS", "WANTED", "check_in", "email_conversation", "gmail_draft",
           "integration_connect", "mail_triage", "response_inbox", "service_run"]
