# Attending meetings: how jason could take notes, keep the record, and answer questions

Research notes, October 2026. They describe what Zoom's platform offers an association's agent, what the
Server-to-Server OAuth app jason already holds can do with it, and what would take a second app. Zoom renames scopes
and moves features between app types often; check the Marketplace before building. Not legal advice.

The association's meetings are on Zoom. [zoom.md](zoom.md) covers what jason does today: it reads the account's
meeting history (recordings, transcripts, chats, AI Companion summaries) to disk after the fact, and it schedules a
disciplinary hearing when a person asks. This note is about the meeting itself: being there, hearing it, writing the
record as it happens, and answering what the board or a member asks, without jason ever running the meeting.

## 1. What the Server-to-Server app can reach

A Server-to-Server OAuth app is the account acting on its own, with no person signed in. It covers REST calls and
event subscriptions (webhooks). It cannot be in a meeting: no audio, no live transcript, no chat, no panel.

**Before the meeting.**
- Create or update the meeting (`POST /users/{userId}/meetings`): topic, start, duration, cloud recording on, waiting
  room on, alternative hosts. The answer carries the join URL and dial-in numbers the Civil Code 4926 notice needs.
  jason already does this for hearings; a board meeting would be the same call behind `Confirm`.
- Create polls on a scheduled meeting (`POST /meetings/{meetingId}/polls`). The host launches them in the meeting;
  the API cannot. Polls are member input, never a board vote.
- Read the closed-caption token (`GET /meetings/{meetingId}/token?type=closed_caption_token`, scope
  `meeting:read:admin`). See "speaking as captions" below.

**During the meeting.**
- Webhooks: `meeting.started`, `meeting.ended`, `meeting.participant_joined`, `meeting.participant_left` (names and
  times, enough to suggest the roll call and attendance for a person to confirm), `meeting.sharing_started`.
  `meeting.chat_message_sent` exists but is gated: the account needs Zoom's in-meeting chat DLP feature and the event
  enabled by support, and developers report it not firing. Treat live chat as unreadable without a bot.
- In-meeting controls (`PATCH /live_meetings/{meetingId}/events`): `recording.start`, `recording.pause`,
  `recording.resume`, `recording.stop`, `participant.invite`, the waiting-room message, and starting or stopping AI
  Companion. The caller must be the meeting's host or an alternative host, so the app acts for that user. Nothing
  here mutes, admits, removes, or opens breakout rooms. Pausing the recording for an executive session is the one
  control the meeting room could offer, behind `Confirm`, with the host's name on it.
- Speaking as captions. With "Allow use of caption API token" on in the host's settings, the caption token is a URL;
  `POST` plain text to it with `seq` incremented each time and `lang=en-US`, and the text appears in every
  participant's captions. It is a broadcast: anything jason writes there is seen by all. It is text only, and nothing
  comes back.

**After the meeting.**
- `recording.completed` and `recording.transcript_completed` announce the cloud recording's files: video, audio, the
  VTT transcript, the chat file, poll results. `meeting.summary_completed` announces the AI Companion summary;
  `GET /meetings/{meetingId}/meeting_summary` reads it (scope names for summaries have changed more than once, and
  developers report the admin variant refusing calls; the sync's current scopes are in zoom.md).
- `GET /report/meetings/{meetingId}/qa` returns the questions and answers when the meeting had Q&A on; Q&A on a
  meeting is set by the host, not created by the API. `GET /report/meetings/{meetingId}/participants` gives who was
  there.

This is where jason stands today, and it already covers "keep the record" after the fact. Built since this note was
written: `jason zoom --create-board-meeting`, `--recording pause|resume|start|stop`, and `--caption`, each behind
`--yes` and logged ([zoom.md](zoom.md)).

## 2. The three ways to be in the meeting

All three need a **General App** (OAuth, account-level, authorized once by the account's admin). The Server-to-Server
app cannot hold any of them. One General App can carry all three features.

### A. Realtime Media Streams (RTMS): hear it, no bot tile

RTMS is a WebSocket stream from Zoom's servers of the meeting as it happens: audio per participant and mixed,
video, the transcript with speaker-change events, chat messages, and participant events. There is no participant in
the gallery. The account's admin enables RTMS and allows apps to access meeting content; the host approves the stream
(or the app is set to auto-start for the host, which Zoom added in January 2026); participants are shown a
disclosure and cannot opt out individually; the host can pause or stop it at any time. Clients need 6.5.5 or newer.
It is read-only: an RTMS app cannot speak, chat, or post.

Flow: Zoom sends `meeting.rtms_started` to the app's webhook; the app opens the signaling socket, then the media
socket; Zoom's RTMS SDKs for Node.js and Python do the handshake. The open-source Attendee project runs this as a
self-hosted service (one Docker image, Postgres and Redis) if jason should not hold the sockets itself.

This is Zoom's intended path for note-takers, and it fits "take notes": the live transcript becomes the suggestions in
the meeting room's Minutes tab (typed in today), the speaker events become the attendance suggestions, and the chat
stream becomes the questions asked in chat.

### B. A Meeting SDK bot: a visible participant that can also write

The Meeting SDK for Linux joins as a participant ("jason, notes"), receives raw audio and video once the host grants
recording permission, and can send in-meeting chat (`SendChatMsgTo`). It needs the General App's Meeting SDK
feature and the raw-data entitlement, a headless Linux host with a virtual display, and Zoom's bot rules: the host's
consent before any media is accessed, and the standard "This meeting is being recorded" disclaimer. Zoom now steers
note-takers to RTMS; the bot is the only way to answer in the meeting's chat.

### C. A Zoom App: the console inside the client

A Zoom App runs the console in the meeting's side panel (`zoomapp:inmeeting`), and the Layers API puts a page on
the main stage in immersive Presentation mode. Only the host can switch to immersive, one app instance at a time,
and the host's instance invites the others. This is the handoff's meeting stage and host panel inside Zoom. The app
hears nothing by itself; pair it with RTMS in the same General App.

### Also: Team Chat and AI Companion

- A Team Chat chatbot (the General App's Chatbot feature) answers questions outside meetings. The Chatbot and Team
  Chat features are not available to Server-to-Server apps.
- "Zoom as MCP client": with the Custom AI Companion add-on, the account connects a remote MCP server, and its tools
  become available to AI Companion and custom agents, including when a person asks AI Companion in a meeting.
  jason's MCP server (`jason-mcp`, the board profile) is a read-only, caveat-carrying tool set over the stores on
  disk; served over HTTPS it would let AI Companion answer from the association's records. It needs a Workplace Pro
  plan and the add-on, and the answers are Zoom's model's, so each tool's caveat must travel with its result.

## 3. What jason would do with it, and what it would not

The rules do not move: the chair runs the meeting, the board decides, jason records. A person is named on every
write, and nothing goes out to members on jason's own initiative.

**Attend.** An RTMS session auto-started for the host's meetings that match the board schedule or a planned hearing.
The transcript lines land in `data/zoom/live/<date>/` as they arrive, each with its speaker and time; the meeting
room reads them as suggestions, never as minutes. A hearing or an executive session is held back the same way the
synced history is (Civil Code 4935, 5215): when the host pauses the stream or a person records
`executive_start`, the live notes from then on are confidential until a person says otherwise.

**Keep the record.** Three records, kept apart: the meeting room's log (attendance, motions by name, votes, the
CIV 4930 paths, executive session, adjournment) as the person records them; the live transcript as evidence; and,
after the meeting, the cloud recording's transcript, chat, and AI summary from the sync. The draft minutes quote the
log and cite the transcript. The AI summary is not the minutes.

**Answer questions.** In order of how little jason speaks:
1. In the console, to the person running it: the Ask drawer answers from sourced material or routes the question,
   and the host panel shows the facts for the item on the floor. The chair reads it out. This exists.
2. As captions, when a person asks for it: an answer the person chose in the console is posted to the caption URL,
   prefixed "jason:", behind `Confirm`, because every participant sees it. Text only, no voice.
3. In the meeting's chat, only with a Meeting SDK bot, and only to a question a person forwarded. Deferred: the bot
   costs the most and Zoom steers away from it.
4. Through AI Companion, when the account has the add-on: jason serves tools; Zoom's model answers. jason adds
   nothing of its own.

jason does not admit, mute, or remove anyone, start a recording, run a poll, end a meeting, or record a vote on its
own. The in-meeting controls it could offer (pause and resume the recording for an executive session) carry the
host's name and a `Confirm`.

## 4. What it takes

| Piece | Needs |
|---|---|
| Keep the sync and hearing scheduling | the Server-to-Server app, as today |
| Live transcript and events (RTMS) | a General App with RTMS, the admin's enablement, a public HTTPS webhook receiver, a socket client (or Attendee) |
| The console in the client, the stage | the same General App with the Zoom App feature; the console served over HTTPS, not loopback |
| Captions as jason's voice | the host's caption-API setting, `meeting:read:admin`, a `seq` counter per meeting |
| Chat answers | the Meeting SDK feature, the raw-data entitlement, a headless Linux host, Zoom's bot disclosure |
| AI Companion answering from the records | the Custom AI Companion add-on, `jason-mcp` served remotely |

`jason-web` binds to loopback with no sign-in; a webhook receiver and a Zoom App both need a reachable HTTPS
address and authentication first. That is the prerequisite for everything in section 2.

## 5. Open

1. Where the webhook and RTMS receiver runs (the association's own host, or Attendee self-hosted).
2. Retention of the live transcript beside the cloud recording, and whether the full recording is kept.
3. Whether a visible bot is ever wanted, or captions and the console are enough.
4. The handoff's `ZOOM-INTEGRATION.md` assumed RTMS on the association's account; that holds, but it needs the
   General App, not the Server-to-Server app the account already has.

## Sources

- RTMS: [SDKs](https://developers.zoom.us/docs/rtms/sdk/), [working with streams](https://developers.zoom.us/docs/rtms/meetings/work-with-streams/), [host and admin controls](https://developers.zoom.us/docs/rtms/meetings/ux-host-admin-tools-ctrls/), [auto-start for a host (changelog, January 2026)](https://developers.zoom.us/changelog/rtms/january-18-2026), [enabling RTMS for an account (forum)](https://devforum.zoom.us/t/how-to-enable-rtms-for-my-account/142626), [Attendee and RTMS (Zoom blog)](https://developers.zoom.us/blog/realtime-media-streams-attendee/), [attendee-labs/attendee](https://github.com/attendee-labs/attendee), [zoom/rtms](https://github.com/zoom/rtms), [what is RTMS (Recall)](https://www.recall.ai/blog/what-is-zoom-rtms).
- Meeting SDK bots: [Meeting SDK for Linux](https://developers.zoom.us/docs/meeting-sdk/linux/), [in-meeting chat](https://developers.zoom.us/docs/meeting-sdk/linux/custom-ui/basic-features/in-meeting-chat/), [raw-data entitlement (forum)](https://devforum.zoom.us/t/enable-raw-data-entitlement-for-meeting-sdk-linux/145544), [bot requirements (Recall)](https://docs.recall.ai/docs/zoom-bot-requirements), [recording consent (Recall)](https://docs.recall.ai/docs/zoom-recording-consent).
- Zoom Apps: [Layers API](https://developers.zoom.us/docs/zoom-apps/guides/layers-using-api/).
- REST and webhooks: [in-meeting controls (forum)](https://devforum.zoom.us/t/what-in-meeting-features-are-controllable-by-the-in-meeting-controls-endpoint-live-meetings-meetingid-events/74001), [caption token endpoint](https://developers.qodex.ai/zoom-public/zoom-meeting-api/meetings-meetingid-token/get-meeting-s-token), [caption POST format (forum)](https://devforum.zoom.us/t/closed-caption-via-rest-api/84155), [polls via API (forum)](https://devforum.zoom.us/t/can-i-launch-a-meeting-poll-through-api/19277), [meeting summary scopes (forum)](https://devforum.zoom.us/t/cannot-retrieve-ai-companion-meeting-summary-body-via-api-missing-meetingsummary-master-scope/142967), [transcript and summary events (forum)](https://devforum.zoom.us/t/summary-and-transcript-events-not-triggering-in-event-subscription/124209), [in-meeting chat webhook (forum)](https://devforum.zoom.us/t/missing-meeting-chat-message-sent-in-event-types-list-for-oauth-app/72654), [live chat not available by API (forum)](https://devforum.zoom.us/t/api-endpoint-to-retrive-live-chat-messages/74161), [meeting Q&A report](https://devforum.zoom.us/t/how-to-enable-q-a-on-api-created-meetings/111735).
- AI Companion and MCP: [MCP at Zoom](https://developers.zoom.us/docs/mcp/), [Zoom as MCP client](https://developers.zoom.us/docs/mcp/delete-mcp-client/), [Custom AI Companion overview](https://library.zoom.com/zoom-workplace/ai-companion/custom-ai-companion-explainer/overview), [AI Companion 3.0](https://news.zoom.com/ai-companion-3-0-and-zoom-workplace/).
- Team Chat: [Team Chat apps (forum)](https://devforum.zoom.us/c/team-chat/78.md).
