# Zoom: the meeting history and disciplinary hearings

The association holds its meetings on Zoom. The account's history holds the association's meetings, cloud-recording transcripts, chats, and AI Companion summaries. jason reads that history to disk. It also schedules a disciplinary hearing, but only when a person asks. The board's meeting schedule is `MEETING_SCHEDULE` in the specification; Mystique's findings are in the private notes (mystique/notes/zoom.md).

## Setup

1. In the Zoom App Marketplace, the account owner creates a **Server-to-Server OAuth** app. No person signs in, and no browser opens.
2. Add these scopes. The names are Zoom's granular scopes; a Server-to-Server app uses the `:admin` variants. Check the names in the Marketplace, because Zoom renames them.
   - list meetings, past meeting, past meeting instances, past meeting participants;
   - list user recordings, and the recording content (for downloads);
   - list meeting summaries, and meeting summary;
   - write meeting (only for `jason hearing --create`).
3. Run `jason zoom --store-app --account-id A --client-id C`. It creates a Keeper login record with `account_id` and `client_id` as custom fields and prints its UID; set `zoom_record_uid` in `.env`. Put the client secret in the record's password field in Keeper. A `client_secret` custom field also works, and wins.

A call the app has no scope for fails with its HTTP status and asks whether the scope is set. Participants need a paid plan; without one, the sync leaves them out.

## The sync: `jason zoom`

The sync reads from `zoom_history_since` in the specification (`mystique/zoom.py`), the day the meetings moved to Zoom. After the first run, it reads from two weeks before the last sync, because a recording or a summary can appear days after the meeting. `--full` reads the whole history again, and `--since` sets the start.

It gathers every occurrence from three sources:
- the past instances of each meeting id the host has (the board's recurring meeting keeps one id);
- the cloud recordings, asked a month at a time;
- the AI Companion summaries.

Each occurrence is one folder, `data/zoom/meetings/<date>-<key>/`:

| File | What it is |
|---|---|
| `transcript.vtt` | Zoom's WebVTT transcript |
| `transcript.txt` | the same as speaker turns with times |
| `chat.txt` | the meeting chat |
| `summary.json`, `summary.md` | the AI Companion summary; the host's edits win over Zoom's draft |
| `participants.json` | who joined, and when they joined and left |

Audio and video are downloaded only with `--media`. The index is `data/zoom/meetings.json`.

### Kinds of meeting

`classify_meeting` reads the topic against `ZOOM_MEETING_RULES`, in order: hearing, executive session, annual meeting, committee, then board meeting. A hearing or an executive session outranks "board meeting" in the same topic.

A meeting that no rule names but that started on the schedule's day, within two hours of the schedule's hour, is a board meeting "by the schedule". Anything else stays "other".

### The brief

`jason zoom` (MCP `zoom_meetings`) lists every meeting with its kind, length, head count, the files held, and the summary's next steps.

It also lists the **schedule gaps**: each of the schedule's meeting days in the synced window with no Zoom meeting that day. The board meets monthly in practice, so every month is checked. A gap may be a cancelled meeting, one held on another account, or one that was never recorded. It is a reason to look, not a finding.

`jason zoom --meeting <date|uuid>` (MCP `zoom_meeting`) prints one meeting: the summary, words by speaker, attendees, chat, and transcript.

### Caveats

- **The AI summary is not the minutes.** It records no roll call, motion, or vote, as [board-agenda.md](board-agenda.md) notes for the minutes that append it.
- **The transcript is speech recognition.** Names and numbers can be wrong.
- **Recordings can include the executive session.** A board meeting's recording can run on into the executive session that follows it.
- **Confidential kinds are held back.** An executive session's or a hearing's transcript, summary, and next steps are held back unless asked for (Civil Code 4935).

## Disciplinary hearings: `jason hearing`

`jason hearing --address A --violation "..."` plans a hearing and drafts its notice. It changes nothing in Zoom.

**The date.** By default, the hearing is the schedule's first meeting day at least 10 days after today, or after `--notice-on`. It starts at the schedule's hour unless `--time` is given. The address must be one of the association's; any other address is refused.

**The deadlines**, from the statute:

| Deadline | Rule |
|---|---|
| Notice to the member at least 10 days before, by personal delivery or individual delivery | CIV 5855(a), 4040 |
| A mailed notice is delivered when it is deposited | CIV 4050(b) |
| If the meeting is held solely in executive session, notice of its time and place to the members 2 days before | CIV 4920(b)(2) |
| The decision in writing within 14 days after the board acts | CIV 5855(f) |
| Discipline is not effective otherwise | CIV 5855(g) |

A notice delivered too late is a problem. The plan says so and names the first date that works, and `--create` refuses to schedule.

**The notice draft** is saved to `data/zoom/hearings/<date>-<address>.md`. It carries what 5855(b) requires:
- the date, time, and place (the Zoom link, meeting ID, passcode, and dial-in, once scheduled);
- the nature of the alleged violation, in the board's words;
- the member's right to attend and address the board;
- the member's right to ask for executive session and attend it (4935(b)).

It adds the right to cure before the hearing (5855(c)), internal dispute resolution (5910), and the 14-day written decision. The owner's name, the delivery method, and the signature are left for the secretary.

**Scheduling.** `--create --yes` creates the Zoom meeting under `HEARING_POLICY` (`mystique/zoom.py`):
- 30 minutes;
- a waiting room, so the board admits the member and can deliberate apart;
- not recorded;
- a topic that names no owner or address.

Zoom's answer includes the host's `start_url`, which signs its holder in as the host. It is dropped and never written.

**The record.** `data/zoom/hearings.json` keeps each plan. `jason hearing --list` (MCP `hearings`) shows where each one stands: notice due, notice overdue with no delivery recorded, or held with the decision due.

**The notice as a Google Doc.** `--doc --owner "Name" --matter "..." --yes` fills the Notice of Hearing template on the letterhead and files it in the matter's Disciplinary folder ([letters.md](letters.md)).

**What jason does not do:**
- send the notice;
- decide the discipline;
- write the decision;
- move or cancel a meeting in Zoom. A person does that in Zoom and plans again.
