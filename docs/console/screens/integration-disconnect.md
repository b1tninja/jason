# Disconnect an integration

A flow, not a route: the `DisconnectConfirm` dialog opened from an `IntegrationCard` on `#/setup/integrations` (a community's own) and on the Instance screens ([../handoff-instance-and-integrations.md](../handoff-instance-and-integrations.md)) · phase 4, after the setup dialogs · CLI: `jason integrations disconnect KEY --community C --yes --by NAME` (to add)

## In the console

None. The card shows a connection's state and next step; the setup dialogs (`ConnectDialog`, `StepCheck`, `SecretDrop`, `FileDrop`) and `DisconnectConfirm` are proposed and not built. The Instance routes `instance-service`, `instance-integrations`, and `instance-schedules` are built and read only.

**This spec is the whole flow, as proposed.** Verified in the repo on 2026-10-11:

| Needed | State |
|---|---|
| `jason integrations` | built: `list` and `check [--live --by]` only. `import`, `connect`, and `disconnect` do not exist |
| The connections store (`integrations.json`, `Connection`, `ConnectionState`, `save` under the store lock) | built (`jason.integrations.connections`) |
| Pause a schedule with a reason and a name | built (`jason.scheduler.pause`, `jason cadence --pause SOURCE --why --by`); a sign-in pause is a different kind and clears itself on a good check |
| Delete a vault entry | built in the interface (`SecretStore.delete(path)`; Keeper's `delete` removes the record); no command calls it for a disconnect |
| Revoke a provider's token | **not built**. Nothing in the repo calls a provider's revoke; [../../google-workspace-setup.md](../../google-workspace-setup.md) tells a person to remove the app in Google's account page or Admin console |
| A log of connection acts | **not built** (a connection holds `note`, `connected_by`, `last_check` only) |
| `integration-connect` run, step `disconnect` | designed ([../../workflows/mail-and-platform.md](../../workflows/mail-and-platform.md), 2.5), "designed, not built"; the run library is built, no definition is registered |

## Purpose and personas

Ending a connection is as visible as making one ([../../integrations-design.md](../../integrations-design.md): "Revoking and rotating are as visible as connecting"). The administrator reads, before anything happens, exactly what stops, what stays, and what a person must still do outside jason, and then confirms by name.

- **Administrator:** the only actor. One of jason's admins signed in as themselves (`status.require_admin`: 401 with no sign-in, 403 for anyone else and while viewing as someone else). Holds no office and approves nothing for the board.
- **Manager, officers, directors:** never see the dialog or the run. They see the connection's state on Status and Setup (a word and a date), the same for a director as for an officer.
- **Counsel, reviewer, owner:** no access.

## Data

| Part | Source |
|---|---|
| The connection | `connections.load(community)`: account, capabilities, vault path, state, `connected_by`, `connected_at`, `last_check`, overrides |
| What it reads | the registry row: `capabilities`, `sources` (cadences), `vault_names`, `auth` |
| The schedules to pause | `jason cadence --json` rows for the integration (key, cadence, last read, next run, paused or not) |
| The credential, by path | the vault path as a name, and "set" or "not set"; never a value. Under `jason-web --dev` only, the vault is asked for names |
| Other holders of the same credential | the legacy `.env` record key the resolver still falls back to (`resolver.LEGACY`), and a local token file the layered Google store may hold (`LayeredTokenStore`) |
| The log | `integration-acts.jsonl` beside the community's `integrations.json` (to add), append only, under the connection store's lock |

A log line: `{at, by, community, integration, act, outcome, detail}`. `act` is `disconnect-planned`, `schedules-paused`, `provider-revoked`, `provider-revoke-by-hand`, `entry-deleted`, `disconnected`, `failed`. `detail` holds counts, names of schedules, and vault paths; never a value, a token, or an account's password.

## Layout: the dialog

```
+------------------------------------------------------------------------------------------+
| Disconnect Zoom for Example Village HOA                                       [Cancel]   |
| Connected since Mar 2, 2099 by A. Admin · account: example-meetings · last check ok      |
+------------------------------------------------------------------------------------------+
| WHAT HAPPENS, IN THIS ORDER                                                              |
| 1 jason  pauses 3 schedules: zoom-meetings (daily 03:00), zoom-recordings, ...           |
|          Paused by A. Admin: "disconnected". A later good check does not restart them.   |
| 2 jason  tries to revoke the grant at the provider.    [Zoom: jason cannot; see below]   |
| 3 jason  deletes the vault entry jason/community/example/zoom/app (account id, client    |
|          id, secret). Whether the backend keeps a copy is the backend's.                 |
| 4 jason  writes 4 lines to the log, in your name, and sets the state to "not set up".    |
+------------------------------------------------------------------------------------------+
| WHAT STOPS                                                                               |
| Meetings, recordings, and summaries are no longer read. Status shows them stale after    |
| their stale-after time. 1 queued job and 0 planned approvals name this integration:      |
| they will fail, and are not cancelled.                                                   |
+------------------------------------------------------------------------------------------+
| WHAT A PERSON STILL DOES OUTSIDE JASON                                                   |
| Deactivate the app in Zoom's Marketplace (jason cannot). Until you do, the app's grant   |
| may still work for anyone who holds the secret (not verified).                         [PersonSteps]       |
| A record named in .env (ZOOM_RECORD_UID) still holds a copy: jason does not edit .env    |
| or that record; the integration will still resolve from it until a person removes it.    |
+------------------------------------------------------------------------------------------+
| WHAT IT NEVER DOES                                                                       |
| Delete data jason already read (meetings, transcripts, and files stay where they are).   |
| Touch any other integration, or any other community. Change an office, the roster, a    |
| rule, or a decision. Cancel a job or an approval. Resume anything on its own.            |
+------------------------------------------------------------------------------------------+
| To undo: reconnect from the start. A new consent gives a new credential; the deleted one |
| cannot be restored from jason.                                                           |
+------------------------------------------------------------------------------------------+
| Type "zoom example" to confirm:  [____________]        [Pause instead]  [Disconnect]     |
+------------------------------------------------------------------------------------------+
```

The **result** replaces the body: each of the four steps with `done`, `person must`, `already done`, or `failed: REASON`, a `Seal` for what jason did, and the log lines written. "Disconnected" appears only when step 3 is done. A failure stops the sequence and says which steps had happened; running it again finds the done steps and continues (every step safe to run twice).

## Components

Built (checked in `ui/src/components`): `Confirm`, `Command`, `Card`, `Pill`, `Glyph`, `Seal`, `Findings`, `Caveats`, `Timeline`, `DataTable`. Proposed in the handoffs and not in the folder: `IntegrationCard`, `ConnectionChip`, `PauseBanner`, `TerminalStep`, `PersonSteps`, `DisconnectConfirm`. To add here: `DisconnectPlan` (the four lists above, from one loader), `DisconnectResult`, `TypedConfirm` (a `Confirm` that enables only on the typed words).

## Actions

| Control | Does | Approval? | CLI |
|---|---|---|---|
| Open the dialog | Reads the plan; writes nothing. Never opens from a URL | No | `jason integrations disconnect KEY --community C` (prints the plan) |
| Pause instead | Pauses the integration's schedules, keeps the credential | No: a signed record | `jason cadence --pause SOURCE --why TEXT --by NAME` (built) |
| Disconnect | The four steps, in order, in the signed-in name | No: the administrator's own act, behind `TypedConfirm` | `jason integrations disconnect KEY --community C --yes --by NAME` |
| Revoke by hand, recorded | After a person revoked at the provider, records `provider-revoke-by-hand` with the day and what they did | No | `--revoked-by-hand --by NAME` |
| Delete without revoking | If the revoke fails, delete anyway: a second typed line, "I will revoke it at the provider" | No | `--without-revoke --reason TEXT` |

Revoke, by integration (the design's words; none is built):

| Integration | jason revokes? | A person |
|---|---|---|
| Google Workspace | not yet: a call to Google's revoke is the build's, and a refresh token is revoked before its entry is deleted, since the entry is the only copy | removes the app in Google's account page or Admin console |
| Zoom (server-to-server) | no refresh token exists; there is nothing to revoke from jason | deactivates the app in Zoom's Marketplace |
| PayHOA, utilities, signed-in portals | no | changes the password if the grant should end |
| PostScanMail | no | revokes the key at the provider (not verified how) |
| Console sign-in, vault, law library, models, county caches | refused here (below) | |

**Refused, with a sentence:** an instance-scoped integration ("This belongs to the installation, not a community"); the vault ("jason would lose the way to every credential"); an integration with nothing to connect ("Nothing to disconnect"); the console sign-in ("Disconnecting it removes the way people sign in; do it at a terminal").

## States

- **Not connected:** "Nothing to disconnect: this connection is not set up."
- **Already disconnected:** shows the log and "Disconnected on DAY by NAME".
- **Vault will not answer** (Keeper needs `jason login`): the plan shows "step 3 cannot run until the vault answers" with the command; nothing is paused first.
- **A local file token exists** (the installation's, shared): listed, not deleted: "This file is the installation's and may serve another community. `jason vault migrate` retires it once the vault holds the same token."
- **Failure partway:** the result names what happened and what did not; state stays "paused".
- **Admin viewing as someone else, or not an admin:** "Viewing as NAME (admin view): go back to yourself first." / 403.

## Privacy

- Administrator only. The log is the administrator's; the card to others shows the state word and the date.
- No secret appears in the dialog, the result, the log, a URL, a toast, or an error. The vault path is a name. The account label is shown as recorded.
- A confirmed-and-failed attempt is logged with the error's class, never its text if it could carry a value.

## Decisions for the user

1. **Console or terminal on this PC.** Recommended: the dialog shows the plan and the command; `--yes` runs at a terminal, as `check --live` does; the console writes only when hosted.
2. **Pause kind.** Recommended: a person's pause, so a later good check cannot silently restart reads.
3. **Revoke before delete.** Recommended, with `--without-revoke` as an explicit second step.
4. **Whether officers see the administrator's name** on a disconnect, or only the date (recommended: date only).
5. **The sign-in client** refused in the console (recommended).
6. **`.env` fallback:** whether disconnect also offers to remove the named `.env` key (recommended: no).
7. **The log's home:** a new file beside `integrations.json` (recommended), or `data/access/`.

## Acceptance criteria

1. Opening the plan writes nothing; the dialog cannot open from a URL.
2. The four steps run in order; a failure stops and reports; a second run continues without repeating.
3. "Disconnected" shows only after the vault entry is gone; the state becomes "not set up" and the schedules stay paused.
4. No other integration, community, store of data already read, `.env`, or office is changed (tested with two integrations).
5. The dialog lists each schedule it pauses, each thing a person must still do, and each place a copy of the credential may remain.
6. The confirm button stays disabled until the typed words match.
7. A body `by` naming someone else is a 403; an admin viewing as someone else cannot act.
8. No log line, response, or page holds a secret; a test scans them.
9. A reconnect is a full setup; nothing restores the deleted credential.
10. A director sees the same state word an officer sees; nobody but the administrator sees the dialog or the log.
