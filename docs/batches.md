# Bulk writes: batches

A batch is many PayHOA writes a person confirmed together, such as the 89 emailed owner-information copies. `jason.batches` sends them one at a time and slowly, and keeps a ledger (`data/batches.db`), so a run can stop anywhere and the next run picks up where it left off.

## How a run behaves

| What happens | What jason does |
|---|---|
| Between items | waits `Pace.interval` plus a random `Pace.jitter` (8 s plus up to 4 s); inside one item (upload, then send) `Pace.step` (2 s) |
| PayHOA's own allowance | each response says how many requests are left (`x-ratelimit-limit` 600, `x-ratelimit-remaining`); under 50 left, the run waits a minute before the next item |
| Before each request | marks the item **sending** |
| After success | marks it **sent** with its result (the uploaded file id, PayHOA's batch id) |
| 429, or 503 with Retry-After | waits the server's Retry-After (or 30 s, doubling) and tries the same item again; this is not counted as an attempt. A wait over 15 minutes, or a 7th wait for one item, pauses the batch |
| Timeout, dropped connection, 5xx | the outcome is unknown, so the item is **uncertain**: jason checks PayHOA before sending again, and gives up after 3 attempts |
| Can't tell whether it was sent | leaves it **uncertain** for a person (`jason batches --resolve ID KEY --sent` or `--not-sent`). It is never resent blind |
| Other 4xx | the item **failed**; the run goes on |
| 401, 403, 419 (the session) | puts the item back to **pending** and pauses the batch: sign in again (`jason login`) and resume |
| 3 failures in a row | pauses the batch (a circuit breaker) |
| Ctrl-C or a crash | the item in flight is **sending**; the next run treats it as **uncertain** and checks it |

Resume by running the same command again. Creating a batch twice adds only the items it lacks, so nothing that was sent is sent again. One run at a time holds the PayHOA lock. A step inside an item that a retry should reuse (an uploaded file) is checkpointed, so a retry doesn't upload it twice.

## Commands

```bash
jason owner-info --send-plan
```

`--send-plan` writes what each owner will be sent and what each copy carries, without addresses (`data/owner-info/send-plan-<date>.md`).

```bash
jason owner-info --email-batch
```

This is a dry run: the count, the time it will take, and the first owners.

```bash
jason owner-info --email-batch --only me --yes --confirmed-by "NAME"        # me: payhoa_my_unit_id in .env
```

`--only` sends to one unit first, as a test. The full run skips anything already sent.

```bash
jason owner-info --email-batch --yes --confirmed-by "NAME" --limit 10
```

`--limit` sends the next 10 and stops.

```bash
jason owner-info --mail-batch
```

This is the letters' dry run: one Mailroom send per building, and the count PayHOA says each reaches. Add `--yes --confirmed-by "NAME"` to mail them. A send is confirmed when the Mailroom shows a batch that wasn't there when the item's send began (checkpointed first).

What's mailed is `packet-mailed.pdf`: the packet with the campaign's marker stamped on it (see [form-identifiers.md](form-identifiers.md)).

## Delivery engines

Each channel is an engine in `jason.tasks.delivery_engines`. An engine supplies:
- its batch id;
- its pace;
- how the send plan becomes batch items;
- the handler that sends one item;
- its marker's identity.

Email gives each owner their own copy, with a copy marker, every 8 to 12 seconds. The Mailroom sends one letter per building, with a campaign marker, every 20 to 30 seconds. A new channel, such as PayHOA's own form or a broadcast, is a new engine. `jason.batches` runs every engine the same way.

```bash
jason batches --show owner-info-2027-email
```

`--show` gives each item's status and the latest events.

`jason batches --retry-failed ID` puts failed items back to pending after a person looks at why. `jason batches --cancel ID --yes` skips what's left.

## Checking whether an email went out

An owner's PayHOA communications log lists each email with its attachments. A copy was sent when an email to that owner carries the file the item uploaded. With no upload recorded, it wasn't sent, because the upload comes first. The ledger holds ids, statuses, and errors, never an address: each copy is made from PayHOA when it's sent.

## Delivery and follow-ups

A batch going out is not the notice arriving. `jason notices` keeps every attempt to reach each member, and reads what became of it from PayHOA (`jason.tasks.notice_ledger`, `data/notices/deliveries.db`):

```bash
jason notices owner-info-2027 --sync
jason notices meeting-2026-09-15 --sync --subject "Regular Meeting of the Board of Directors" --since 2026-09-10 --general
jason notices owner-info-2027
```

- **Email.** PayHOA's communications log carries each message's status and events. SendGrid reports delivered, opened, and bounced, with the receiving server's words. PayHOA reports a message it skipped for no email on file, and fails one with no delivery event after 24 hours. A jason copy is found by the reference in its subject; a notice sent from PayHOA's own screens, by `--subject`.
- **Letter.** The same log carries each Mailroom letter, and the Mailroom's Lob events say whether it was mailed, returned, or forwarded.

Each outcome is weighed by `FOLLOW_UPS`, one row per case with its force (the statute, or the association's practice) and authority:

| Outcome | Follow-up | Authority |
|---|---|---|
| Email bounced | resend by first-class mail; ask for a working email | CIV 4041(e), 4040(a)(2) |
| Email skipped (no email on file) | make sure a letter went | CIV 4040(a)(2), 4041(c) |
| Email not shown delivered after 24 hours | resend by mail, as for a bounce | practice |
| Letter never mailed | send it again | CIV 4050(b) |
| Letter returned | send to the elected email or secondary address; ask for a mailing address | CIV 4050(b), 4041(c) |
| Letter forwarded | ask the member to confirm the address | practice |

A member another delivery reached owes no resend. A bounce or a returned letter still asks for the address. 4041(e) counts any "bounce or other error notification", so a full mailbox (SMTP 4xx) is a bounce; jason marks it temporary.

**General notices.** A meeting notice is a general notice (CIV 4045). If it was also posted where the annual policy statement designates, the posting delivered it: pass `--general`, and a failed message is noted rather than resent, except to a member who asked for individual delivery (4045(b)). If it was not posted, the messages were the delivery: leave `--general` off.

**Sending a follow-up** is a person's step through the commands that guard every send. For the owner-information letter, `jason owner-info --mail-batch --only UNIT --resend --yes --confirmed-by NAME` makes a `-resend-` batch that starts with the notice's key, so the next `--sync` reads it in (a `-test-` batch is never part of the notice). Sync the day after a notice, again after 24 hours, and a week on for letters; `jason sop notice-delivery` is the procedure.
