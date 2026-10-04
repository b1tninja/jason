# Conversations: design spec

The build spec for the conversation catalog that [gmail-conversations.md](gmail-conversations.md) proposes: which messages belong together, who answered whom, what was forwarded, and what is still waiting on the association. That page holds the research and its sources. This one is the contract to build to:
- the store and its records;
- the sync;
- the threading, side, and forward rules;
- the interfaces;
- the console screens and their components;
- privacy;
- the tests;
- a rollout with acceptance criteria.

It follows AGENTS.md: facts are data, a miss stays a miss, nothing is sent, and where the law is silent the board writes the rule.

## Goals

1. **One conversation per exchange.** A conversation Gmail split, by a subject edit, a reply from another mail program, or more than 100 messages, is one conversation again.
2. **Who answered whom.** Every message has an author and a side. A reply links to the message it answers.
3. **Waiting on the association, by author.** A conversation waits on the association until someone acting for it answers, from any mailbox the association uses, a group, or an officer's known account. An automatic reply is never an answer.
4. **Forwards are seen.** A forward links to its original when the original is in the store. It records the original's sender and date, and how sure jason is of them.
5. **A forward is never an answer.** It assigns work, routes misdelivered mail, or shares a copy. An assignment is followed to its outcome, or its inaction, as a handoff.
6. **Every mailbox jason reads,** deduplicated by `Message-ID`.
7. **Nothing breaks on the way.** Every current caller (`threads()`, `reply_needed`, `open_items`, `email_intents`, `thread_topics`, `party_brief`, the MCP tools) keeps its shape until it moves.

## Not goals

- **Sending.** jason drafts replies (`responses.make_reply`) and sends nothing.
- **Changing labels, archiving, or deleting** in Gmail.
- **Storing message bodies.** Only a forward's parsed block and a hash.
- **Reading a group's archive.** There is no API for it ([setup.md, jason's mailbox](setup.md#6-jasons-mailbox)).
- **Judging an assignee's work.** jason tracks that the assignee wrote back, and when; whether the answer was good is a person's reading.

## The store

`data/gmail/catalog.db`, SQLite in WAL mode, written under the store lock `gmail-catalog` (`jason.locks`), read by everything else. The level is P2: addresses and subjects. There are no bodies, and P4 never enters.

### Tables

```sql
CREATE TABLE message (
  msg_key        TEXT PRIMARY KEY,   -- the Message-ID without <>, lower-cased domain part; synthetic "gmail:MAILBOX:ID" when absent
  synthetic_key  INTEGER NOT NULL,   -- 1 when msg_key is synthetic
  subject        TEXT NOT NULL,
  base_subject   TEXT NOT NULL,      -- subjects.base(subject)
  author         TEXT NOT NULL,      -- the author's address, lower-case
  author_name    TEXT NOT NULL,      -- the display name as given
  author_source  TEXT NOT NULL,      -- AuthorSource
  side           TEXT NOT NULL,      -- Side
  date_header    TEXT,               -- the Date header as an ISO time, when it parses
  first_seen     TEXT NOT NULL,      -- the earliest internalDate across mailboxes (ISO)
  list_id        TEXT,
  auto           INTEGER NOT NULL,   -- 1 when the message is automatic
  auto_reason    TEXT,               -- AutoReason
  in_reply_to    TEXT,               -- the first id in In-Reply-To
  references_json TEXT NOT NULL,     -- the ids in References, in order
  thread_index_guid TEXT,            -- from Thread-Index
  thread_index_depth INTEGER,
  to_json        TEXT NOT NULL,      -- [[name, address]] for To
  cc_json        TEXT NOT NULL,
  attachments_json TEXT NOT NULL,    -- [{name, type, depth}] for every part with a filename or a message/rfc822 type
  resent_json    TEXT,               -- the Resent-* blocks, newest first, when present
  version        INTEGER NOT NULL    -- the parser's version; a new version reparses
);
CREATE TABLE mailbox_copy (
  mailbox        TEXT NOT NULL,      -- the account's address
  gmail_id       TEXT NOT NULL,
  msg_key        TEXT NOT NULL REFERENCES message(msg_key),
  gmail_thread   TEXT NOT NULL,
  labels_json    TEXT NOT NULL,
  internal_date  TEXT NOT NULL,
  delivered_to_json TEXT NOT NULL,
  forwarded_to   TEXT,               -- X-Forwarded-To / X-Forwarded-For / X-Gm-Original-To
  via_group      TEXT,               -- the List-Id or X-Original-Sender group
  gone           INTEGER NOT NULL DEFAULT 0,   -- deleted in Gmail (history said so)
  PRIMARY KEY (mailbox, gmail_id)
);
CREATE TABLE edge (
  src            TEXT NOT NULL,      -- msg_key
  dst            TEXT NOT NULL,      -- msg_key, or a placeholder id not (yet) in the store
  kind           TEXT NOT NULL,      -- EdgeKind
  evidence       TEXT NOT NULL,      -- Evidence
  confidence     REAL NOT NULL,      -- 0..1, from the rule table
  PRIMARY KEY (src, dst, kind, evidence)
);
CREATE TABLE forward (
  msg_key        TEXT PRIMARY KEY REFERENCES message(msg_key),
  forwarder      TEXT NOT NULL,
  method         TEXT NOT NULL,      -- ForwardMethod
  original       TEXT,               -- msg_key of the original when found
  original_from  TEXT,
  original_date  TEXT,
  original_subject TEXT,
  original_to_json TEXT,
  parse_confidence REAL NOT NULL,
  block_sha256   TEXT,               -- the parsed block's hash, never the block
  read_at        TEXT NOT NULL
);
CREATE TABLE conversation (
  conv_id        TEXT PRIMARY KEY,   -- "c" + the first 16 hex of sha256(root msg_key)
  root           TEXT NOT NULL,
  base_subject   TEXT NOT NULL,
  first_at       TEXT NOT NULL,
  last_at        TEXT NOT NULL,
  last_outside   TEXT,               -- msg_key of the last non-auto message from outside
  last_association TEXT,             -- msg_key of the last association message
  awaiting       TEXT NOT NULL,      -- Awaiting: the asker's wait, which a forward never ends
  gmail_threads_json TEXT NOT NULL,  -- the Gmail thread ids folded in, by mailbox
  built_at       TEXT NOT NULL
);
CREATE TABLE handoff (                -- a forward by the association is an assignment, tracked to its outcome
  handoff_id     TEXT PRIMARY KEY,   -- "h" + the first 16 hex of sha256(forward msg_key + assignee)
  conv_id        TEXT NOT NULL,      -- the conversation whose question was handed off (follows redirects)
  forward_msg    TEXT NOT NULL,      -- msg_key of the association's forward
  by             TEXT NOT NULL,      -- who forwarded it (the author)
  assignee       TEXT NOT NULL,      -- the address it went to (one row per assignee)
  assignee_kind  TEXT NOT NULL,      -- HandoffKind
  intent         TEXT NOT NULL,      -- ForwardIntent: assignment | routing | copy
  intent_source  TEXT NOT NULL,      -- "rule" | "reading" (jason's, labeled) | "person" (confirmed or changed)
  at             TEXT NOT NULL,
  follow_up_by   TEXT,               -- an assignment's at + the HandoffRule's days; none for routing or a copy
  status         TEXT NOT NULL,      -- HandoffStatus, the latest event's
  status_at      TEXT NOT NULL
);
CREATE TABLE handoff_event (          -- the handoff's trail: what the mail showed, and what a person recorded
  handoff_id     TEXT NOT NULL,
  at             TEXT NOT NULL,
  status         TEXT NOT NULL,      -- HandoffStatus
  source         TEXT NOT NULL,      -- "mail" (a message showed it) | "person" (recorded in the console or the CLI) | "clock"
  msg_key        TEXT,               -- the message that showed it
  by             TEXT,               -- the person who recorded it
  outcome        TEXT,               -- HandoffOutcome, for a person's record
  note           TEXT,               -- a person's few words; checked by intake.secret_reason, contacts masked
  PRIMARY KEY (handoff_id, at, status)
);
CREATE TABLE conversation_member (conv_id TEXT NOT NULL, msg_key TEXT NOT NULL, depth INTEGER NOT NULL,
                                   parent TEXT, PRIMARY KEY (conv_id, msg_key));
CREATE TABLE sync_state (mailbox TEXT PRIMARY KEY, history_id TEXT, last_full_sync TEXT, last_history_sync TEXT,
                         window_days INTEGER, capped INTEGER NOT NULL DEFAULT 0);
CREATE INDEX message_base ON message(base_subject);
CREATE INDEX copy_thread ON mailbox_copy(mailbox, gmail_thread);
CREATE INDEX edge_dst ON edge(dst);
CREATE INDEX member_msg ON conversation_member(msg_key);
```

### The closed sets

Each is an `Enum` in `jason.gmail_catalog.model`. JSON stores the word, and the loader turns it back into the member.

| Enum | Members |
|---|---|
| `Side` | `association` (an association address, a group post by an officer or the manager, an officer's known address), `board` (a director's personal address not in the roster's official ones; kept apart so it can be counted either way), `member`, `vendor`, `counsel`, `government`, `other`, `unknown` |
| `AuthorSource` | `from`, `x_original_from`, `reply_to`, `x_original_sender` |
| `AutoReason` | `auto_submitted`, `x_autoreply`, `precedence`, `report` (multipart/report), `null_return_path`, `subject` |
| `EdgeKind` | `reply`, `forward`, `resend`, `attached` |
| `Evidence` | `in_reply_to`, `references`, `rfc822_part`, `msg_file`, `inline_block`, `subject_prefix`, `resent_block`, `server_headers`, `thread_index`, `gmail_thread`, `subject_match` |
| `ForwardMethod` | `rfc822`, `msg_file`, `inline_gmail`, `inline_outlook`, `inline_apple`, `server`, `prefix_only` |
| `Awaiting` | `association`, `other`, `none`. The asker's wait only; a forward never changes it |
| `HandoffKind` | `counsel`, `manager`, `vendor`, `board`, `insurer`, `agency`, `accountant`, `other` (from the parties, the vendor contacts, and the profile's counsel and manager) |
| `ForwardIntent` | `assignment` (someone is to act or answer: followed up), `routing` (the mail belonged elsewhere: redirected to whoever it was for), `copy` (shared for information, e.g. with a group: nothing expected) |
| `HandoffStatus` | `routed` and `shared` (the closing states of routing and a copy), `assigned` (forwarded), `replied` (the assignee wrote back to the association), `answered_asker` (after the handoff, the assignee or the association wrote to the asker), `stalled` (no word from the assignee by `follow_up_by`), `reassigned` (forwarded on to someone else), `closed` (a person recorded an outcome) |
| `HandoffOutcome` | `handled_offline` (a call, a meeting, in person), `answered_elsewhere` (mail jason does not read), `no_action_needed`, `withdrawn` (the asker withdrew), `to_board` (taken to a board item), `other` |

**Side** comes from the profile and the parties, never from a mailbox label:
- `Community.email_domains()` and `Community.google_groups()` say what is the association's;
- `Community.officers()` and `jason.access.managers()` give the people acting for it, with `Officer.email` and the private roster's other addresses;
- `PartyResolver` and the vendor contacts classify the rest.

## The sync

`jason gmail --sync` keeps its name and its flags. Underneath, `jason.gmail_catalog.sync`:

1. **For each mailbox the profile names:** `Community.gmail_mailboxes()`, a new method with the empty default `()`, meaning "the signed-in account".
   - **With a `history_id` that is under 6 days old:** `history.list` (`messageAdded`, `messageDeleted`, `labelAdded`, `labelRemoved`). Fetch the added messages; mark deleted ones `gone`; apply label changes.
   - **On a 404, an old id, or no id:** a full listing of the window, `messages.list` with `-in:drafts -in:spam -in:trash` and today's PostScanMail exclusion. Fetch every id not in `mailbox_copy`. At the end, store the profile's `historyId` (`users.getProfile`).
   - **The cap:** when the listing exceeds the cap, record `capped` and the oldest date reached, and say so in the sync's report and in every conversation answer's caveats. Never drop silently.
2. **The fetch:** `messages.get`, `format=full`, with a `fields` mask:
   - `id,threadId,labelIds,internalDate,payload(headers,mimeType,filename,parts(...))`, to a part depth of 6;
   - the client keeps only these headers: `From, To, Cc, Subject, Date, Message-ID, In-Reply-To, References, Reply-To, Delivered-To, List-Id, X-BeenThere, X-Original-From, X-Original-Sender, Auto-Submitted, X-Autoreply, X-Autorespond, Precedence, Return-Path, Content-Type, Thread-Index, Thread-Topic, X-Forwarded-To, X-Forwarded-For, X-Gm-Original-To, Resent-From, Resent-Date, Resent-To, Resent-Message-ID`.
   - A message with the `DRAFT` label is skipped, even if the query let it through.
3. **The parse** is pure functions in `jason.gmail_catalog.headers`, each tested on its own:
   - `msg_key(headers, mailbox, gmail_id)`: the Message-ID trimmed of `<>`. Its domain part is lower-cased and its local part kept. A missing, empty, or malformed id gives the synthetic key. When the same Message-ID already exists with a different `first_seen` and a different author, the later one gets the synthetic key too (RFC 5256: duplicates are unique).
   - `author(headers, profile)`: X-Original-From, then Reply-To when From is a group's address, then X-Original-Sender, then From. It records which one won.
   - `side(author, profile, parties)`.
   - `auto(headers)`: `Auto-Submitted` other than `no` first, then the rest of the AutoReason list. A message from the association is never auto unless `Auto-Submitted` says so.
   - `thread_index(value)`: base64 to the 22-byte header's GUID and the depth `(len - 22) / 5`. Invalid gives none.
   - `subjects.base(subject)`: below.
   - `attachments(payload)`: every part with a filename or a `message/*` type, with its depth.
4. **The write:** `message` (insert, or update when the parser's `version` moved), then `mailbox_copy`, then the edges this message implies. All under the lock, committed every 100 messages, so an interrupted sync loses at most one batch.
5. **The rebuild:** conversations are rebuilt for the messages touched, and for any conversation a new edge reaches. A full rebuild is `jason gmail --rebuild`.
6. **The view:** `correspondence.json` is regenerated from the catalog in today's shape, so every current reader works unchanged until it moves.

### Backfill

Today's store has Gmail ids but no threading headers. The first run after the change re-fetches every stored id's headers, throttled under the per-minute quota at 20 units each. It reports its progress and is resumable, because `mailbox_copy` rows are the bookmark. Ids that no longer exist in Gmail are kept as `gone`, with what the old store knew, synthetic keys, and `side` from the old `direction`.

### Subjects

`jason.gmail_catalog.subjects.base(s)`, the one normalizer that replaces the three regexes in `responses`, `request_links`, and `legal_hold`:
1. Decode RFC 2047; collapse whitespace; strip a trailing `(fwd)`.
2. Repeatedly strip a leading reply or forward prefix, followed by `:`, with an optional `[n]` or `(n)`. The prefixes are `re`, `fw`, `fwd`, and the profile-free list of translations: `aw`, `wg`, `sv`, `vs`, `rv`, `tr`, `antw`, `doorst`, `odp`, `pd`, `ynt`, `i`, `回复`, `转发`, `答复`. A leading bracket tag (`[EXTERNAL]`, `[list-name]`) is stripped the same way.
3. Unwrap `[fwd: …]`.
4. Case-fold for comparison; keep the original for display.

`subjects.marks(s)` reports whether the subject began with a reply or a forward prefix. That is the RFC 5256 "is a reply or forward" bit the merge rule needs.

## Threading

`jason.gmail_catalog.thread.build(messages, edges)` follows RFC 5256 REFERENCES, adapted:

1. **Edges first.**
   - **References:** each id in a message's References gives a `references` edge to it. The last id is the parent (`depth` follows); the earlier ids chain each to the next, as RFC 5256 step 1A links them.
   - **In-Reply-To:** with no References, its first id gives an `in_reply_to` edge as the sole parent.
   - **Placeholders:** an id not in the store is a placeholder node.
   - **Loops:** a link that would make a loop is skipped.
2. **The root set:** the nodes with no parent.
3. **Placeholders:** an empty placeholder with no children is dropped. One with a single child is replaced by the child at the root. One with several children stays as a placeholder root.
4. **Subject merge:** roots are grouped by `base_subject` (non-empty only). Two roots merge only when RFC 5256 step 5 allows it:
   - one is a placeholder; or
   - the current root's subject was marked as a reply or forward and the other's was not.

   jason adds one more condition: they merge only if their `first_seen` are within 60 days. That keeps a recurring subject ("Pool key") from swallowing a year.
5. **Hints, never overrides:**
   - **Same Gmail thread:** two roots in one mailbox's same `gmail_thread`, whose base subjects are equal, merge as `gmail_thread` evidence. That covers mail that carried no References.
   - **Same Thread-Index GUID:** two roots merge as `thread_index` evidence.
   - **Never across a header link:** neither hint ever splits what the headers joined.
6. **Order:** a conversation's members sort by `first_seen`, and its `root` is the earliest real message.
7. **Ids:** `conv_id` comes from the root's `msg_key`, so it is stable while the root is. When two conversations merge, the new id is the earlier root's. `conversation_redirect(old, new)` is kept, so links and evidence addresses to the old id still resolve.

Each merge records the evidence in `edge` (`subject_match`, `gmail_thread`, `thread_index`, at their rule confidence), so the console can say why two messages were joined.

## Sides and "awaiting"

For each conversation, in member order:
- **The open question:** `last_outside` is the last message whose side is not the association's and that is not automatic.
- **The answer:** `last_association` is the last message whose side is `association`, or `board` when the profile counts board members' personal mail as the association's (`Community.conversation_policy().board_counts`, default true).
- **What it waits on (`awaiting`):**
  - `association` when `last_outside` exists and no association message to the asker came after it. A forward of the question to someone else is not a message to the asker, so it never ends the wait;
  - `other` when the last non-automatic message is the association's to the asker;
  - `none` when everything is automatic or internal.

`threads()` keeps its statuses: `awaiting us` = `association`, `awaiting them` = `other`, `notice`, `internal`. A conversation waiting on us with an open handoff also carries the handoff's stage ("assigned to counsel"), but stays "awaiting us".

`reply_needed` measures reply days from the first `last_outside` to the first association message to the asker after it, from any mailbox, never counting an automatic reply or a forward.

## Handoffs: a forward is an assignment

A forward is never a completion (decided 2026-10-04). When the association forwards a question to counsel, a vendor, the manager, the board, an insurer, or an agency, it assigns the work. jason tracks the assignment to its outcome, or to its inaction, beside the asker's wait, which stays open until someone writes back to the asker.

**Creating one.** An association-side message with a `forward` edge, or a server forward the association set up, opens one `handoff` row per recipient. That includes a recipient inside the association: an officer forwarding to the manager is kind `manager`. Assigning within the association is still work to follow.

**What kind of forward it is.** Not every forward assigns work. A forward is one of three intents, and only an assignment is followed up:

| Intent | What it means | What jason does |
|---|---|---|
| `assignment` | Someone is to act or answer: counsel to advise, a vendor to fix, the manager to handle | `assigned`, a `follow_up_by` date, and the statuses below; it can stall |
| `routing` | The mail belonged elsewhere: misdelivered, another association's, a city or utility matter, the right department | `routed` and closed. If the original was never meant for the association (the mail sort's misdirected flag, or the association was not among its recipients), the asker's wait ends with it. If an owner asked the association and it routed the question to someone else, the owner's wait stays open until someone tells them, and the conversation shows "routed to the city, Oct 3" |
| `copy` | Shared for information: a copy to the board's group, an FYI to the manager or counsel | `shared` and closed; nothing is expected; the asker's wait is unchanged |

The intent comes from three sources, in order:
1. **A person's word.** The conversation view's "What was this forward?" choice, a `Confirm` under the signed-in name, logged as a `handoff_event`. A person can change it at any time, and the latest word wins.
2. **A rule row** (`HandoffRule.intent` for the assignee's kind). For example, the profile's own groups default to `copy`, and counsel and vendors to `assignment`. A server forward the association set up takes its rule's intent, `routing` or `copy`, never `assignment`.
3. **jason's reading**, labeled as jason's and shown as a lead for a person to confirm:
   - `routing` when the original was misdelivered (the mail sort's misdirected flag, or no association address among its recipients);
   - `copy` when the recipient is one of the association's own groups and the forward adds no words of its own;
   - `assignment` when the forward adds a request (a question, "please", "can you", a date);
   - otherwise `assignment`. Unsure means follow it up, never drop it. The view marks it "jason's reading: assignment. Is that right?"

  Reading the forward's own words is the same body read as forward detection: only the request markers found are kept, not the text.

**What the mail shows for an assignment**, recomputed on every rebuild; each change is a `handoff_event` with `source = "mail"`:

| Status | When |
|---|---|
| `replied` | A message authored by the assignee (or from the assignee's firm domain, for counsel and vendors) after the handoff that replies to the forward (a `reply` or `references` edge to it), or that sits in the conversation |
| `answered_asker` | After the handoff, a message to the asker from the assignee, or from the association. The asker's wait ends with it; the handoff's job is done |
| `reassigned` | The assignee, or the association, forwards it on; the new forward opens its own handoff |
| `stalled` | `follow_up_by` passed with no `replied` or `answered_asker` (`source = "clock"`, recorded the first time a rebuild sees it) |

**What a person records.** An outcome the mail can't show: a call, a meeting, a reply to the asker from mail jason does not read, a withdrawn question. In the console, the conversation view's "Record the outcome" is a `Confirm` under the signed-in person's name. On the command line: `jason handoffs --close HANDOFF_ID --outcome handled_offline --note "…" --by NAME`.
- It writes a `handoff_event` (`source = "person"`, `closed`, a `HandoffOutcome`, the note) to jason's own store, under the lock, and nothing else.
- A note is checked by `intake.secret_reason`, with contact details masked.
- Recording an outcome never closes the asker's wait unless the outcome says the asker was answered (`handled_offline`, `answered_elsewhere`, `withdrawn`). Then the conversation's `awaiting` becomes `none` with that event as its reason.

**When to follow up.** A rule row per kind, from the profile (`Community.handoff_rules()`, default `()`). With no row, jason's general default applies, and the caveat says it is jason's default, not the association's:

```python
@dataclass(frozen=True)
class HandoffRule:
    kind: HandoffKind
    follow_up_days: int          # calendar days from the forward to "stalled" (an assignment only)
    intent: ForwardIntent = ForwardIntent.ASSIGNMENT   # the default intent for this kind of recipient
    note: str = ""               # why: a retainer letter's response time, a vendor contract's term
DEFAULT_FOLLOW_UP_DAYS = 7       # jason's general default when the profile has no row for the kind
```

A contract or a retainer that states a response time is the source of a row. Quote it, then cite it (AGENTS.md, "Recite the rule; label the reading").

**Inaction is the finding.** A stalled handoff shows:
- in the Inbox (the Assigned filter);
- in the dock's deadlines;
- in `open_items` as "No word from counsel since Oct 3 (12 days; follow up was Oct 13)".

jason drafts nothing and nags no one on its own. The person chooses:
- **Draft a follow-up**, a draft to the assignee through the existing draft path;
- **Add to the action register**, a task with an owner and a due date, behind `Confirm`;
- **Take it to the board**, a board item, behind `Confirm`;
- **Record the outcome**.

Each is a person's act, logged.

**Board members' personal mail.** Whether a board member's personal address counts as the association's is `Community.conversation_policy().board_counts` (default true). The board may say otherwise for record-keeping: personal accounts are a records risk, and counsel can advise.

## Forwards

`jason.gmail_catalog.forwards.detect(message, payload, body_reader)` checks these in order. The first that holds decides `method`. The rest add evidence.

| Order | Signal | Method | Original's fields | Confidence |
|---|---|---|---|---|
| 1 | A `message/rfc822` part | `rfc822` | The part's own headers, read with the part (`messages.attachments.get` when it is not inline); its Message-ID links the original | 0.98 |
| 2 | An attachment of type `application/vnd.ms-outlook` or named `*.msg` | `msg_file` | None without an OLE reader; the fact only | 0.9 for the fact |
| 3 | `X-Forwarded-To`, `X-Forwarded-For`, `X-Gm-Original-To`, or 2 or more `Delivered-To` | `server` | The message itself is the original; the edge says a rule moved it | 0.95 |
| 4 | `Resent-From` | `resend` edge (not a forward) | The message is the original; `Resent-*` names the redirector | 0.95 |
| 5 | A forward prefix, or a body read finds an inline block | `inline_gmail`, `inline_outlook`, `inline_apple` | From/Date/Subject/To parsed from the block | 0.6 to 0.85 (below) |
| 6 | A forward prefix and no block found | `prefix_only` | None | 0.4 |

**The body read** happens only in case 5: a message whose subject was marked as a forward, or whose References points into the store under a different base subject.
- `get_body` reads the `text/plain` part, else the HTML as text, through the existing pattern set in `community/signatures.py`, which grows a parser: `forward_block(text) -> ForwardBlock | None`.
- The body is not stored. Only the parsed fields and `block_sha256` are.
- The level is P2, read on this machine (security-and-privacy.md gets the row when it ships).

**Inline-block confidence** starts at 0.6. It gains:
- 0.1 when the From field gives an address, not only a name;
- 0.1 when the Date field parses with a time zone;
- 0.05 when the Subject equals a stored message's.

**Linking the original.** For inline forwards the original is found by:
1. a Message-ID in the References that is in the store and outside this conversation; else
2. a stored message from `original_from`, within 1 day of `original_date`, with the same base subject.

A match sets `forward.original` and adds a `forward` edge from the forward to the original.

**Nested forwards:** only the outermost block is recorded. Its own text is not re-read.

## Interfaces

**Python** (`jason.api` and `jason.gmail_catalog`):
- `conversations(*, awaiting=None, since=None, party=None, topic=None, limit=200) -> list[ConversationRow]`
- `conversation(conv_id) -> Conversation | None`, following redirects
- `message(msg_key) -> Message | None`

**CLI:**
- `jason gmail --sync`, unchanged on the surface; `jason gmail --rebuild`; `jason gmail --mailboxes` (which are read, and their history state);
- `jason conversations` (open ones first) and `jason conversations --show CONV_ID`, plus `--awaiting association|other|none` and `--assigned`;
- `jason handoffs` (open assignments, stalled first), `jason handoffs --close HANDOFF_ID --outcome OUTCOME --note TEXT --by NAME`, and `jason handoffs --intent HANDOFF_ID assignment|routing|copy --by NAME`.

**MCP**, read-only, P2 masked:
- `conversations`, `conversation`, and `handoffs`, beside `email_threads`. `email_threads` keeps its shape and reads the catalog. MCP never records an outcome or an intent.

**jason-web:**
- `GET /api/conversations?awaiting=&since=&party=&limit=` returns rows: `{convId, subject, awaiting, firstAt, lastAt, ageDays, messages, sides: {side: n}, lastOutside: {author, side, at}, lastAssociation, handoffs: [{handoffId, assignee, kind, intent, intentSource, at, followUpBy, status, statusAt}], topics, likelyNeedsResponse, pastUsualTime, gmailLinks: [{mailbox, url}]}`.
- `GET /api/handoffs?status=&kind=` lists handoffs with their conversation's subject and the asker's wait.
- `POST /api/handoffs/<id>/outcome` with `{outcome, note}`, and `POST /api/handoffs/<id>/intent` with `{intent}`. Both are behind the write guard and the token, signed in, with `by` the account's name; refused while an admin views as someone else. Each writes one `handoff_event` and nothing else.
- `GET /api/conversations/<id>` returns the conversation with its members:
  - `messages: [{msgKey, at, author, authorName, side, to, cc, subject, auto, autoReason, viaGroup, depth, parent, attachments: [DocRef], edges: [{kind, to, evidence, confidence}], forward?: {...}, gmail: [{mailbox, url}]}]`;
  - plus `caveats` and `why` (each merge's evidence in words).
- **Masking:** addresses are masked as P2 in both routes. Names are P1. A person reveals one address through the existing logged reveal.

**Evidence addresses** (the evidence service):
- `gmail:<msg_key>` resolves to the message's headers as a source. Its documents are its attachments on disk (`gmail/files/…`), and, once a body view is built, the message.
- `conversation:<conv_id>` resolves to the conversation summary. Board items and briefs can cite either.

**Gmail links:**
- `https://mail.google.com/mail/u/?authuser=<mailbox>#all/<gmail_thread>`, which replaces today's `/u/0` assumption, and `#search/rfc822msgid:<msg_key>` for one message.
- They are originals: a new tab, the person's own session.

## The console

### The Inbox's email tab

"Email awaiting us" becomes **Conversations**, with a segmented filter:
- **Waiting on us**, the default, which is `association`;
- **Assigned**: open assignments (`assigned`, `replied`, `stalled`), stalled first, whatever the asker's wait;
- **Waiting on them**: `other`;
- **All**.

| Column | Shows |
|---|---|
| Last | The date of the last message, with `DueDate`-style "3d ago" |
| From | The `lastOutside` author's name and side as a `Badge` (member, vendor, counsel...) |
| Subject | The base subject, as a link to the conversation view; "Re:" and "Fwd:" never shown |
| Messages | Count, with a hint of the sides ("3 owner · 2 association") |
| Handed off | The open handoff in words: "assigned to counsel Oct 3; no word, follow up was Oct 13" (stalled, in the warn tone), "counsel replied Oct 5", "routed to the city Oct 3", "copy to the board" |
| Reply? | Today's `likely` / `past usual time` badges |

Caveats: the cap when it applied; "jason reads N mailboxes: …" (names, not addresses); "An automatic reply never counts as an answer."

### The conversation view (`#/conversations/<id>`)

A full screen (`ScreenHeader` with the base subject and the awaiting `Pill`). Below it, in order:
1. **The question line.** "Waiting on the association since Oct 1 (3 days): the last word is from an owner." Or "Answered Oct 2 by the manager." Or "Assigned to counsel Oct 3; counsel replied Oct 5; the owner has had no answer yet." Or "Routed to the city Oct 3; it was never the association's." A forward is never shown as an answer.
2. **The messages**, oldest first, as a ledger: one `MessageRow` each, indented by `depth` up to 3 (deeper reads flat with "in reply to NAME, DATE").
3. **Why these are together.** A `Findings`-style list of each merge's evidence in words: "Joined by the reply headers"; "Joined by the same subject within 60 days (no reply headers)"; "Gmail kept these in one thread". A low-confidence join is marked "a lead, not a finding".
4. **Caveats:**
   - "The headers say who replied to what; a reading of what was said is not jason's."
   - "Only the mailboxes jason reads."
   - "A forward assigns, routes, or shares; it never answers the asker."
5. **The handoffs.** One `HandoffCard` per handoff, beside the forward that opened it.
6. **Actions**, each a person's act, signed in:
   - **Open in Gmail**, per mailbox;
   - **Draft a reply**, the existing `make_reply` path. It drafts and never sends. It is shown only when the conversation waits on the association;
   - **On a handoff:** "What was this forward?" (assignment, routing, copy), "Record the outcome", "Draft a follow-up" (to the assignee; a draft), "Add to the action register", "Take it to the board". Each is behind `Confirm`, and each but the draft writes only jason's store.

### Components (jason-ui)

**`ConversationList`** (`rows`, `filter`, `onFilter`, `onOpen`)
- The Inbox tab's table with the segmented filter.
- It owns no fetching: the screen passes rows.

**`MessageRow`** (`message`, `me?`, `onOpenDoc`)
- One message: the date (tabular), the author's name with a side `Badge`, "to NAME, NAME" (masked addresses only on reveal), and the subject only when it differs from the base.
- **The edge line** in words: "replied to Jane Doe, Oct 1"; "forwarded to counsel"; "a rule forwarded this (server)"; "redirected by NAME".
- **Attachments** as `Doc` chips.
- **Group mail:** a `via` group line.
- **An automatic message** renders muted and collapsed to one line: "Automatic reply from NAME (out of office)". It is never styled as an answer.
- **A board member's personal address** gets a quiet "personal address" mark, so the board sees it was counted.

**`ForwardCard`** (`forward`, `original?`)
- Inside a `MessageRow`: "Forwarded from SENDER, sent DATE", with the method in words ("an attached message", "the forwarded-message block", "by subject only") and the confidence as words, not a number:
  - "exact" at 0.95 and above;
  - "close" at 0.75 and above;
  - "approximate" at 0.5 and above;
  - "a guess" below that.
- When the original is in the store, a link to its `MessageRow`, even in another conversation.

**`HandoffCard`** (`handoff`, `events`, `me?`, `onIntent`, `onOutcome`, `onFollowUp`, `onRegister`, `onBoard`)
- Who it went to, its kind as a `Badge`, and its intent in words. The intent is marked "jason's reading: is that right?" until a person confirms it, or "set by NAME".
- **For an assignment:**
  - the status as a `Pill`: assigned, replied, stalled, reassigned, closed;
  - "follow up by Oct 13" as a `DueDate`;
  - the trail (`events`) as a short `Timeline`: "forwarded Oct 3 by the secretary", "counsel replied Oct 5", "closed Oct 9 by NAME: handled by phone".
- **For routing and a copy:** one line ("Routed to the city Oct 3", "A copy to the board Oct 3") and the intent choice. No clock.
- The actions as the view lists them. A stalled assignment puts "Draft a follow-up" first.

**`ConversationLine`** (`conversation`): the question line, used both in the view and in a dock or brief.

**`JoinEvidence`** (`items`): the "why these are together" list.

**Styling:**
- **Existing classes and tokens only** (`.stack`, `.row`, `.muted`, `.notice`, `--rule`, `--serif` for subjects).
- **Indentation** is `margin-inline-start: calc(var(--depth) * 1.25rem)`, capped at 3.
- **Sides are words in a `Badge`, never color alone.**

**Accessibility:**
- The ledger is a list (`ol`) of `article`s, each labelled "NAME, DATE".
- The edge line is text, not an icon.
- The collapsed auto-reply is a `details` element.

**Previews** (`.design-sync/previews/`), all fake (Example Village, Jane Doe):
- `ConversationList`: waiting, assigned (one stalled), all;
- `HandoffCard`: an assignment on jason's reading, replied, stalled, closed by a person, routing, a copy;
- `MessageRow`: a reply, a forward with each confidence, an auto-reply, group mail, a personal address;
- `ForwardCard`: rfc822, inline, prefix only;
- `ConversationLine`: each awaiting state.

## Privacy

- **Level.** The catalog is P2. `message` holds addresses and subjects. `forward` holds a parsed sender and date and a block hash. No body is stored.
- **Reading bodies.** The only body read is the forward check (case 5). It is logged in the sync's report as a count, never the text.
- **Executive and legal mail.** A conversation is P3 when one of these holds:
  - a party is a party to a legal case (`Community.legal_cases()`);
  - a board item whose session is executive (`board_items.agenda_session`, CIV 4935) cites it (`conversation:` or `gmail:` evidence);
  - its `via_group` is a group the profile marks confidential (`GoogleGroup.confidential`).

  A P3 conversation opens only in the private view, and its row in lists reads "A confidential conversation (open the private view)".
- **Owners.** The owner view never lists conversations.
- **Logging.** The MCP and jason-web mask addresses. A reveal is the existing logged act.

## Tests

Fixtures are synthetic messages (`tests/fixtures/gmail/`), built as header dicts by a small factory, `msg(subject, frm, to, msgid, irt=None, refs=(), labels=(), auto=None, parts=())`. Each case is one test:

| Case | Expectation |
|---|---|
| A reply from another client with References, under an edited subject | One conversation, joined by `references` |
| A reply with no References, same subject, in the same Gmail thread | One conversation, joined by `gmail_thread`, marked a lead |
| Same subject, no ids, 90 days apart | Two conversations |
| A placeholder parent (References names an unseen id) shared by two replies | One conversation under a placeholder root |
| An out-of-office with In-Reply-To | Linked, `auto`, never an answer; the conversation still waits |
| An officer answering from a personal address in the roster | `side=board`, counted as answered by default |
| A group post by the manager (From rewritten, X-Original-From the manager) | Author is the manager, `side=association` |
| A draft in the listing | Skipped |
| A member's inline Gmail forward to the board's group | `forward` with `inline_gmail`, its original from, date, and subject; linked to the original when stored |
| A forward as attachment | `rfc822`, exact; the original linked by its Message-ID |
| A server forward (X-Forwarded-To) | `server`, not a person's forward |
| A redirect (Resent-From) | A `resend` edge |
| The association forwards a member's question to counsel and says nothing to the member | The member still waits (`association`); a handoff `assigned`, kind `counsel`, intent `assignment` |
| Counsel replies to the forward | The handoff becomes `replied`; the member still waits |
| The manager then writes to the member | The handoff `answered_asker`; the member's wait ends |
| No word from counsel by `follow_up_by` | `stalled`, once, from the clock |
| A misdelivered letter (the association not among its recipients) forwarded on | Intent `routing` by jason's reading; `routed`; no one waits on the association |
| A forward to the association's own group with no words added | Intent `copy`; `shared`; no clock |
| A person changes a forward's intent, or records "handled by phone" | A `handoff_event` from `person`, with the name; the latest word wins; the asker's wait ends only for the outcomes that say the asker was answered |
| A server forward the association set up | Its rule's intent, never `assignment` |
| The same message in two mailboxes | One `message`, two `mailbox_copy` rows |
| A missing or duplicated Message-ID | Synthetic keys; never merged on a duplicate |
| History: a deleted message, a label change, a 404 | `gone`; labels updated; a full sync |
| The cap reached | `capped` recorded; the caveat shown |
| A merge of two conversations | The new id is the earlier root's; the old id redirects |
| The backfill | Resumable; a gone id keeps the old store's fields |
| `subjects.base` | Each prefix, nested `Re: Fwd: AW:`, bracket tags, RFC 2047, `[fwd: …]` |
| `thread_index` | A real-shaped header gives its GUID and depth; garbage gives none |

UI tests (vitest) for each component:
- each state renders;
- the auto-reply is collapsed and not counted;
- confidence is in words;
- no address is shown unmasked without a reveal;
- the conversation view's actions are only the listed ones, and the draft is the only one that leaves jason (as a draft);
- a forward is never rendered as an answer;
- a handoff on jason's reading says so until a person confirms it;
- no `mail.google.com` iframe.

Guard: the existing docrefs guard covers the views. A new Python test asserts that the conversation routes' JSON has no unmasked address.

## Rollout

Each step ships behind the same `jason gmail --sync`, and every current caller keeps working.

| Step | Ships | Accepts when |
|---|---|---|
| 1. Headers and the catalog | The new fetch, the tables, `message`/`mailbox_copy`, drafts skipped, the backfill, `correspondence.json` as a view | The backfill completes and is resumable; every current test passes; drafts are gone from `in`; a sync test on a fake Gmail exists |
| 2. Threading | Edges, `subjects.base`, `thread.build`, conversations, redirects | A real store's split threads (one-message "Re:"/"Fwd:" threads) mostly join; no conversation spans unrelated subjects more than 60 days apart; the fixture table passes |
| 3. Sides and awaiting | `side`, `auto`, the new `awaiting`, `threads()` and `reply_needed` on the catalog, `ConversationPolicy` | Threads answered from another association mailbox or an officer's address no longer read "awaiting us"; an auto-reply never closes one; a lesson records the old rule's misses with its guard |
| 4. Forwards and handoffs | Detection, the body read for case 5, `forward` rows, links to originals; `handoff` and `handoff_event`, intents, the statuses, `HandoffRule`, the clock, `jason handoffs`, the outcome and intent writes | Every fixture forward kind is detected with its method; no body is stored (asserted); every handoff fixture lands in its status; a person's outcome and intent are logged with their name |
| 5. History and mailboxes | `history.list`, `gone`, labels, `Community.gmail_mailboxes()`, deduplication | A second mailbox adds no duplicate messages; a 404 falls back cleanly |
| 6. The console | The routes, the components, the Inbox tab, the conversation view, the previews, the design sync | The screens render from fixtures; masking holds; the Assigned filter shows stalled assignments first, and a forward never reads as an answer |

## Open questions

- **The follow-up days for each kind of assignee** (`HandoffRule`): from a retainer letter or a contract where one states a response time, else the manager's or the board's choice. Until then jason's 7-day default, said as jason's.
- **Whether a stalled assignment to counsel goes to the board's canvas on its own**, as a finding. Today the person chooses; the board may want every stalled legal assignment raised.
- **Whether board members' personal mail counts as the association's** (`board_counts`): the default is yes. The board may say otherwise, for record-keeping (personal accounts are a records risk under CIV 5200 practice; counsel can advise).
- **Which mailboxes jason reads:** [setup.md, jason's mailbox](setup.md#6-jasons-mailbox).
- **A body view of one message** (`gmail:` documents in the viewer, [documents.md](console/documents.md#gmail-messages)) is its own step after these, with its sanitizing and blocked remote images.
