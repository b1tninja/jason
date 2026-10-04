# Conversations: threads, replies, and forwards in the association's mail

How jason should know which messages belong together, who answered whom, and what was forwarded to or from the board. It covers:
- what the Gmail sync does today and where it falls short;
- what the Gmail API and the mail standards offer;
- a local conversation catalog;
- a table of the signals that detect a reply or a forward, with how far each can be trusted;
- the order to build it.

The sync as built is [gmail.md](gmail.md). The build spec is [conversations-design.md](conversations-design.md). This page is a proposal, researched 2026-10-04. Sources are cited inline; a claim marked *unconfirmed* is observed behavior with no official source.

## What jason does today

The sync (`tasks/gmail.py`, `google/gmail.py`) lists one mailbox's messages in a rolling window and fetches each new one's headers once. A thread is Gmail's `threadId`, and nothing else:
- `tasks/threads.py` groups by `threadId`;
- `replies.reply_needed`, `party.open_items`, `email_intents`, and `thread_topics` build on that grouping.

The gaps:

| Gap | Effect |
|---|---|
| No `Message-ID`, `In-Reply-To`, or `References` is stored | A conversation Gmail split, by a subject edit or a reply from another client, can't be rejoined. Many one-message threads in a real store start with "Re:" or "Fwd:" |
| Direction comes only from this mailbox's `SENT` label | An answer from another association mailbox, a group post by an officer, or a director's personal account counts as inbound, so the thread reads "awaiting us" when it was answered |
| Drafts are listed with the rest | A draft (jason's own reply drafts included) probably counts as an inbound message. Labels aren't stored, so this can't be checked |
| No forward detection | A member forwarding a letter to the board's group is a new thread from the member. The original sender, date, and attachments' types are lost; a forward attached as a message isn't seen |
| Parties are a set with no roles | Who wrote to whom can't be rebuilt |
| No auto-reply flags | An out-of-office reply can count as an answer |
| The store never prunes or updates | Deleted or relabeled messages stay as first read; a window over the fetch cap drops the oldest silently |
| One mailbox | Mail that only reached another association account or a group member is invisible |

## What Gmail and the standards give

**Gmail's threads are per mailbox, and a hint.**
- Gmail groups replies into a conversation and breaks it "when the subject line changes, or the conversation gets to more than 100 emails" ([Gmail Help](https://support.google.com/mail/answer/5900)).
- Since 2019 an incoming message's References header must name earlier ids to thread ([Workspace Updates](https://workspaceupdates.googleblog.com/2019/03/threading-changes-in-gmail-conversation-view.html)).
- Message and thread ids are per mailbox (*unconfirmed*, widely observed). The same conversation in two mailboxes has two `threadId`s.
- The key shared across mailboxes is the RFC 822 `Message-ID`. Vault calls it "the same for the receiver's and sender's messages" ([Vault](https://knowledge.workspace.google.com/vault/exports/vault-export-contents)), and Gmail search finds it with `rfc822msgid:` ([search operators](https://support.google.com/mail/answer/7190)).

**The standard headers are the real links.**
- RFC 5322 §3.6.4: a reply SHOULD carry `In-Reply-To` (its parent's `Message-ID`) and `References` (the parent's References plus its id) ([RFC 5322](https://www.rfc-editor.org/rfc/rfc5322#section-3.6.4)).
- `Resent-*` blocks mark a redirect, not a reply (§3.6.6).
- Outlook adds `Thread-Index`: a 22-byte header holding a per-conversation GUID, plus 5 bytes for each reply level ([MS-OXOMSG](https://learn.microsoft.com/en-us/openspecs/exchange_server_protocols/ms-oxomsg/9e994fbb-b839-495f-84e3-2c8c02c7dd9b)). It links Outlook mail even where References was stripped.

**Rebuilding conversations is a solved problem.**
- RFC 5256's REFERENCES algorithm, after Zawinski's (JWZ), links messages through References, else In-Reply-To. It uses placeholders for ids not seen, prunes them, and merges roots by base subject only when one side is a placeholder, or a reply or forward meets a non-reply ([RFC 5256](https://www.rfc-editor.org/rfc/rfc5256)).
- Its base subject strips `Re:`, `Fw:`, `Fwd:`, list tags, and `[fwd: …]`, but not the translated prefixes (`AW:`, `WG:`, `SV:`, `RV:`, `TR:`, `Antw:`). jason adds those.
- JMAP treats a thread id as derived and re-derives it when threads merge ([RFC 8621 §3](https://www.rfc-editor.org/rfc/rfc8621#section-3)). jason does the same: the message key is stable; the conversation id is computed.

**Forwards come in four kinds:**
1. **An attached message** (`message/rfc822`, Gmail's "Forward as attachment" `.eml`; [RFC 2046 §5.2.1](https://www.rfc-editor.org/rfc/rfc2046#section-5.2.1)). The inner headers, its `Message-ID` included, are exact. An Outlook `.msg` attachment is the same fact in a binary format.
2. **An inline block.** Gmail's "---------- Forwarded message ---------", Outlook's From/Sent/To/Subject block (localized), Apple Mail's "Begin forwarded message:" (all *unconfirmed* as formats). The original sender and date are approximate: display names, the forwarder's time zone, localized labels.
3. **A server forward.** `X-Forwarded-To`/`X-Forwarded-For` ([Gmail Help](https://support.google.com/mail/answer/175365)), `X-Gm-Original-To`, and a chain of `Delivered-To` ([RFC 9228](https://www.rfc-editor.org/rfc/rfc9228)). This is a rule's act, not a person's.
4. **A redirect** (`Resent-*`).

**Google Groups.**
- A group adds `List-Id` ([RFC 2919](https://www.rfc-editor.org/rfc/rfc2919)).
- Under DMARC, the From becomes "Name via Group" with the group's address ([Gmail Help](https://support.google.com/mail/answer/1311182)), and the author moves to `X-Original-From` (*unconfirmed*, consistent). So the author is X-Original-From, then Reply-To, then X-Original-Sender, then From.
- The Gmail API can't read a group's own archive, and the Groups Migration API only inserts ([reference](https://developers.google.com/workspace/admin/groups-migration/v1/reference)). jason sees group mail only through a mailbox subscribed to the group.

**Automatic replies are not answers.**
- `Auto-Submitted` other than `no` ([RFC 3834](https://www.rfc-editor.org/rfc/rfc3834)) marks one;
- so do `X-Autoreply`, `Precedence: auto_reply|bulk|junk|list`, a `multipart/report` (bounces and read receipts), an empty `Return-Path`, and the subjects "Automatic reply:" and "Auto:".

  An auto-reply SHOULD carry In-Reply-To, so by its headers it looks like a reply.

**Incremental sync.**
- `history.list` costs 2 quota units and gives messages added and deleted and labels added and removed since a `historyId` ([reference](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.history/list)).
- A `historyId` lasts "at least a week" but sometimes hours. A 404 means a full sync ([sync guide](https://developers.google.com/workspace/gmail/api/guides/sync)).
- Push (`users.watch`) needs a Pub/Sub topic. A local-first jason polls history instead.

## The catalog

A SQLite store, `data/gmail/catalog.db` (P2: senders, recipients, subjects; never bodies). Today's `correspondence.json` becomes a view built from it, so every current caller keeps working.

```
message        msg_key PK (Message-ID; "<gmail:MAILBOX:ID>" when absent or duplicated)
               subject, base_subject, author, author_source (from | x-original-from | reply-to | x-original-sender)
               side (association | board | member | vendor | other: from the roster and the parties)
               to[], cc[], date_header, first_seen, list_id, auto (bool), auto_reason,
               in_reply_to, references[], thread_index_guid, thread_index_depth, attachment_types[]
mailbox_copy   (mailbox, gmail_id) PK, msg_key, gmail_thread_id, labels[], internal_date, delivered_to[], via_group
edge           src msg_key, dst msg_key or placeholder, kind (reply | forward | resend | attached),
               evidence (in_reply_to | references | rfc822_part | inline_block | subject_prefix | resent_block |
                         thread_index | gmail_thread), confidence
forward        msg_key, forwarder, method (rfc822 | msg_file | inline_gmail | inline_outlook | inline_apple | server),
               original msg_key or null, original_from, original_date, original_subject, parse_confidence
conversation   conv_id (derived), root, base_subject, last_outside, last_association, awaiting (association | other | none)
sync_state     mailbox, history_id, last_full_sync
```

**Building conversations:**
- Run RFC 5256 REFERENCES over every mailbox's messages, deduplicated by `msg_key`.
- Merge on base subject only by its step-5 rule.
- A shared Gmail `threadId` within one mailbox, or a shared Thread-Index GUID, breaks ties. It never overrides the headers.

**Who answered whom:**
- **The side of a message is its author's,** not the mailbox's label. Any association address, a group post whose author is an officer, or an officer's known personal address (`Officer.email` and the private roster) counts for the association.
- **A conversation awaits the association** when its last non-automatic message is from outside, with no later association reply or forward.
- **A forward to counsel or a vendor** counts as acting on it, not as answering the member. The conversation shows "forwarded to counsel, Oct 3", and the member's question stays open until someone writes back to the member. Whether a forward counts as an answer is a policy question for the board (AGENTS.md, "Where the law is silent").

## Detection rules

| Signal | What it shows | Trust |
|---|---|---|
| `In-Reply-To` names a known Message-ID | A reply to that message (or an auto-reply: check the auto flags) | High |
| `References` names a known id | The same conversation; its last id is the parent | High |
| `message/rfc822` part | A forward as an attachment; the inner headers are exact | High |
| `.msg` attachment | An Outlook forward as an attachment | High for the fact; reading it needs an OLE parser |
| `Resent-*` block | A redirect by `Resent-From` | High; rare |
| `X-Forwarded-To`/`-For`, several `Delivered-To` | A server or filter forward, not a person's act | High for the fact |
| `Auto-Submitted` ≠ no, `multipart/report` | Not a person's answer | High |
| `X-Autoreply`, `Precedence: auto_reply/bulk/list`, "Automatic reply:" | Probably not a person's answer | Medium |
| Same Outlook `Thread-Index` GUID | The same Outlook conversation; its length gives the depth | Medium-high where present |
| Same Gmail `threadId` in one mailbox | Gmail grouped them | Medium: per mailbox; splits at 100 and on a subject edit |
| Inline forward block | A forward; the original's sender and date are approximate | Medium: localized, display names, time zones |
| `Fwd:`/`Fw:`/localized prefix | Someone meant to forward | Low-medium alone |
| `List-Id`; `X-Original-From`; "via" in From | It came through a group; the author is X-Original-From | `List-Id` high; X-Original-* consistent but undocumented |
| Equal base subject, no ids | Perhaps the same topic | Low: merge only by RFC 5256 step 5 |

## Changes to the sync

1. **Fetch the threading headers:** `Message-ID`, `In-Reply-To`, `References`, `Reply-To`, `Delivered-To`, `Auto-Submitted`, `X-Autoreply`, `Precedence`, `Return-Path`, `Thread-Index`, `X-Forwarded-To`, `X-Forwarded-For`, `Resent-From`, `Resent-Date`, `Resent-Message-ID`, beside today's headers. Keep the `Date` header, the labels, and every part's MIME type, at any depth (the `fields` mask stops at three levels today).
2. **Leave out drafts** (`-in:drafts`, and skip a `DRAFT` label), so a draft never counts as mail.
3. **Incremental by history.** Keep `historyId` per mailbox and poll `history.list`: added messages are fetched, deleted ones marked gone, label changes applied. A 404 falls back to a full sync. The window cap says when it drops messages, instead of dropping them silently.
4. **More than one mailbox, by Message-ID.** Each mailbox's copy is a `mailbox_copy` row of one `message`. Which mailboxes jason reads is profile data: an association mailbox subscribed to each group sees every post.
5. **Read a body only for a forward.** Only a message with a forward signal (a prefix, an inline-forward subject, an rfc822 part) gets its body read, through the existing signature reader's patterns (`community/signatures.py`). Only the parsed block (sender, date, subject) and a hash are kept; the body is not stored. An attached message's inner headers are read from the part.
6. **One subject normalizer.** It replaces the three regexes in `responses`, `request_links`, and `legal_hold`: RFC 5256's base subject plus the translated prefixes and `[EXTERNAL]`-style tags.

## Build order

1. **Headers and the catalog.** Fetch the headers, store `message` and `mailbox_copy`, leave out drafts, and rebuild `correspondence.json` as a view. Tests: the sync on a fake Gmail (it has none today), drafts, labels, the deep MIME types.
2. **Edges and conversations.** Reply and references edges, RFC 5256 threading with placeholders, the subject normalizer. `threads()` reads conversations; `threadId` is a hint. Tests: a split thread rejoined, a reply from another client, an auto-reply that is not an answer.
3. **Sides and "awaiting".** The author's side from the roster and the parties; `reply_needed` and `open_items` on the new rule. A lesson records the old rule's misses.
4. **Forwards.** rfc822 and `.msg` parts, server-forward headers, inline blocks with a confidence score; the forward record and its link to the original when it's in the store. The console shows "forwarded to counsel on Oct 3" in a conversation.
5. **History and more mailboxes.** `history.list` polling, deletions and label changes, a second mailbox deduplicated by Message-ID.
6. **The console.** A conversation view: the messages in order with their sides, the edges in words ("replied to", "forwarded to"), the auto-replies set apart, and each message and attachment as a `Doc` once `gmail:` documents land ([documents.md](console/documents.md#gmail-messages)).

## Open questions

- **Which mailboxes jason reads,** and whether an association mailbox is subscribed to each group. The setup steps for a new community are [setup.md, jason's mailbox](setup.md#6-jasons-mailbox): a Workspace account of jason's own, a member of every group and alias. Onboarding asks it as `jason-mailbox`.
- **Whether a forward to counsel, a vendor, or the manager counts as acting on a member's message.** It is a written policy for the board (AGENTS.md), not a default in code.
- **Reading bodies for forwards** is P2 and stays on this machine; only the parsed block and a hash are kept. If that is acceptable, it should be stated in [security-and-privacy.md](console/security-and-privacy.md) when it is built.
