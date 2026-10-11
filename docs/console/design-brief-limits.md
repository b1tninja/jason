# Design brief: Instance > Limits and Setup > Limits

A brief to the design project, written 2026-10-10 after the sixth cut returned no Limits screen ([reconciliation-sixth-cut.md](reconciliation-sixth-cut.md), section 1, "Limits"). It asks for one pass: draw the two screens in the prototype style of the earlier cuts, on made-up data, board-only, with every write through `Confirm`. The screen is already built; this brief says what is built so the design starts from it, what data it may assume, the rules that no drawing may break, the states to draw, and what to send back. It follows the pattern of [design-brief-forms.md](design-brief-forms.md) and the handoffs ([handoff-record-intake.md](handoff-record-intake.md), [handoff-citations.md](handoff-citations.md)).

The design project may use the association's real details. What comes back into the repository is general: no association's name, street, vendor, bank, case number, or private fact, and made-up samples only ("Example Village HOA", `example`, "A. Operator", "A. Admin").

## 1. The idea, and why a screen at all

A **limit** is a number or a switch with a reason, a floor, and a ceiling: how big, how many, how often, how long, how much. The code sets the default and the outer bounds; the instance operator narrows them for an installation; a community's administrator narrows them again for itself; a person with a reason may pass one limit once, never past its ceiling. A limit applies to new acts and never removes or hides what exists. A limit is not an association's rule (that is a rule row in the profile), not a policy the board adopts, and not a secret. The full design is [../instance-limits.md](../instance-limits.md); the built screen's notes are [screens/limits.md](screens/limits.md).

Two screens, one component family:

| Screen | Route | Who sees it | Who changes a limit |
|---|---|---|---|
| **Setup > Limits** | `#/setup/limits` | officers, managers, administrators; never the owner view, never a person with no office | the community's administrator; everyone else reads |
| **Instance > Limits** | `#/instance/limits` | one of jason's admins signed in as themselves; refused to anyone else and to an admin viewing as someone else | that same person, as the instance operator |

The person's question on either screen is the same: **"Why is it this number, who can change it, and what happens when it is hit?"** Draw for that question first, and for editing second.

## 2. What is already built

Read [screens/limits.md](screens/limits.md) and `ui/src/views/LimitsView.tsx` for the detail. In short, so a drawing does not reinvent it:

- **A table per kind**, in this order: Size, Counts, Rates, Time, At once, Switches, Cost. Each group is a collapsible `details`, open by itself when a value was changed or a stored value was held to its range. The group header is its name and "N limits".
- **Columns:** the limit (a plain description, with the key small under it so a command line matches), what is in effect in words, where it comes from, the allowed range with the ceiling, the last change (who and the date), and actions. On a phone the table becomes a stacked list with each column's name beside its value.
- **Where it comes from** is one word with a glyph. Setup: built in, this machine's setting, the operator, this community. Instance: built in (not set) or the operator.
- **Why** opens the registry's two lines, "Why this limit exists" and "What happens when it is reached", the reason given for the last change, the reason for the value in force when it differs, and, where a once-only override exists, its maximum.
- **The states built:**
  - **Clamped.** A stored value was held to its range. The row shows the server's note under the source ("set to 500 MB here; the operator's limit is 200 MB").
  - **Unreadable file.** A warning above the table names the file that could not be read, and says the built-in values apply there. The server gives the stricter of the built-in value and any layer it could read, never the looser.
  - **Host free space.** A line above the table: "Room on the drive jason writes to: N GB free. A size limit never lifts the machine's own guard."
  - **Refusal with the nearest value.** The server's words in an alert, nothing changed, and a button that fills the field with the nearest allowed value ("Use 200 MB"). The person still previews and confirms.
  - **Read only.** A row that cannot be edited says why in its own words (only the operator, only the code, only the community's administrator). An officer or manager sees no Change or Reset button.
  - **Changed just now.** After a confirm the table reloads and the row is marked.
- **The editor** opens under the row: the value in the unit's own words (a size takes "50 MB", a switch is On or Off), the allowed range beside it, on Instance an optional "ceiling for communities", and a required reason. **Preview the change** is a dry run and shows the server's words for each change and who will be recorded. The one confirm button is labelled with the change ("Set largest file you can upload to 50 MB"). Editing any field after a preview discards the preview, so what is confirmed is what was previewed.
- **Reset to default** on a row that has a value in this layer: the same reason, preview, and confirm. It removes the layer's value; it never sets the built-in value as if the layer chose it.

What the design is asked to improve is its look and its reading order, not its behavior. Where a drawing needs a behavior that is not here, mark it **proposed** (section 7).

## 3. The data it may assume

All three are built. The shapes are the console's own (camelCase, words already made by the server). The sample is plainly fake. A screen never builds a sentence the server did not send; it chooses where the server's sentence sits.

### `GET /api/limits` (Setup > Limits) and `GET /api/instance-limits` (Instance > Limits)

Both return a page of the same family. Fields marked (S) are on the Setup page only, (I) on the Instance page only.

```json
{
  "asOf": "2099-10-10T16:30:00+00:00",
  "scope": "community",
  "community": "example",
  "canChange": true,
  "role": "community administrator",
  "host": {"drive": "D:", "free": 214748364800, "freeWords": "200 GB"},
  "unreadable": [],
  "groups": [
    {"kind": "size", "name": "Size", "keys": ["upload.max_bytes", "fetch.max_bytes"], "open": true},
    {"kind": "switch", "name": "Switches", "keys": ["split.auto_read"], "open": false}
  ],
  "limits": [
    {
      "key": "upload.max_bytes", "kind": "size", "unit": "bytes",
      "description": "Largest file you can upload",
      "value": 52428800, "words": "50 MB",
      "source": "community", "sourceWords": "this community",
      "default": 104857600, "defaultWords": "100 MB",
      "minimum": 1048576, "maximum": 524288000,
      "ceiling": 209715200, "ceilingWords": "200 MB",
      "rangeWords": "1 MB to 200 MB",
      "scopes": ["instance", "community"],
      "clamped": false, "note": "",
      "set": {"by": "A. Admin", "at": "2099-10-02T15:00:00+00:00", "reason": "The disk is small"},
      "lastChange": {"kind": "set", "at": "2099-10-02T15:00:00+00:00", "by": "A. Admin",
                     "reason": "The disk is small", "role": "community administrator", "from": 104857600, "to": 52428800},
      "why": "Large uploads fill the disk and make the reading of a scan very slow.",
      "whenHit": "The file is not saved. You are told its size and the limit, and may split it or ask an administrator to allow this one file.",
      "restart": false,
      "override": true, "overrideMaxWords": "250 MB",
      "editable": true, "readOnlyWhy": ""
    }
  ],
  "caveats": [
    "These are the limits in force. A limit is changed by a person, in this console or with `jason limits --set`, never by jason on its own.",
    "A limit applies to new acts. It never removes or hides what already exists."
  ]
}
```

- (S) `source` is `default`, `env`, `instance`, or `community`; `sourceWords` is the server's phrase for it; `clamped` and `note` say a stored value was held to its range; `ceiling` is the highest this community may set.
- (I) the row has `top` and `topWords` (the highest the code allows), `communitiesMayGoUpTo` (the instance's ceiling for communities), `value` of `null` when the layer sets nothing, and a `set` of who set the layer's value. It never carries a community's values or reasons.
- `lastChange` is `{}` when the layer never changed the limit. `unreadable` lists the limits files that could not be read, as the server names them (draw them as given, never as a path of your own).
- `canChange` is false for an officer or a manager; every row then has `editable: false` and a `readOnlyWhy`.
- `host.free` is `null` and `freeWords` empty when the drive cannot be read: draw no line, not a zero.
- Refused: a person with no office, the owner view (Setup), anyone but an admin viewing as themselves (Instance). The refusal is the server's sentence in the console's usual not-yours notice.

### `POST /api/write/limits/<instance|community>`

```json
{"act": "set", "changes": {"upload.max_bytes": "50MB"}, "ceiling": "", "reason": "The disk is small", "by": "A. Admin", "dryRun": true}
{"act": "reset", "keys": ["upload.max_bytes"], "reason": "Back to the operator's value", "by": "A. Admin", "dryRun": true}
```

A dry run is the default; nothing is written unless `dryRun` is `false`. The answer:

```json
{"ok": true, "dryRun": true, "note": "Nothing was written.",
 "recordedAs": {"by": "A. Admin", "role": "community administrator"},
 "changes": [{"key": "upload.max_bytes", "words": "Largest file you can upload: 100 MB (built in) to 50 MB (this community).", "now": 104857600, "to": 52428800}],
 "caveats": []}
```

A refusal is a 400 whose `error` names the limit in words, says "Nothing was changed.", and, when one exists, ends "The nearest allowed value is 200 MB." The design draws the sentence it is given and the nearest-value button; it does not parse more out of it. A different `by` than the signed-in person is refused; an officer, manager, owner, or an admin viewing as someone else gets a 403.

## 4. The rules no drawing may break

Each is in [../instance-limits.md](../instance-limits.md); a screen that breaks one is wrong.

- **No invented numbers.** Every figure shown comes from the registry through the loader: the value, the range, the ceiling, the override maximum, the host's free space. The earlier cut's "up to 25 MB" in the upload tab was an invented figure and is not to be repeated; the build shows the registry's own words ("the largest file jason accepts"). In the prototype, sample figures are plainly fake and the page says so.
- **A limit never overrides a guard.** The temp-drive guard, the preflight, the store lock, and the machine's own checks come first. A limit can only make jason do less than the guards allow. The host free-space line sits beside any size limit so a high number is never read as room that exists, and no state anywhere suggests that raising a limit makes space.
- **Instance ceiling against community.** The operator's ceiling binds communities, not the operator. A community may tighten freely and loosen only inside the ceiling; a community value above the ceiling is not used and is shown as held, never silently honored and never silently dropped. A safety ceiling (what spends money or reaches members without a person reading it first) is lower-only: nothing in the editor may offer to raise it.
- **A reason is required** for a change, a reset, and an override. It is the person's own text, kept in the record, with the warning "no names". The confirm is unavailable until it is written, and the screen says why.
- **The role is shown.** The screen says who the signed-in person is acting as ("You can change these limits as community administrator") and the preview says who will be recorded. A manager serving several communities holds no limit rights in a community unless it makes them its administrator.
- **Preview, then one confirm labelled with the change.** Never "OK". Cancel writes nothing. What is confirmed is what was previewed.
- **No content.** A row, a reason, or a refusal carries no file name, path, unit, owner, or id. The instance screen shows numbers and who set them; never a community's values or reasons.
- **jason proposes; a person acts.** The screen never changes a limit by itself and offers no "fix it for me". A repeated refusal may become a finding for the administrator (counts and sizes, no button); that finding is proposed, not built (section 7).
- **A missing fact is a miss.** A file that cannot be read says so and shows the stricter value. A host that cannot be read draws no free-space line.
- **Every state is a word and a glyph,** never color alone; the attention ladder and line language of the foundations apply (a value someone changed is the "yours to act on" fill; a held value is a clock-free notice, not a deadline color). Glyphs come from the pinned set; if a source glyph (built in, this machine, the operator, this community) needs a new mark, name it and the meaning it carries.
- **No named association** in any sample: "Example Village HOA", "A. Operator", "A. Admin", "123 Main St" if an address is needed at all.

## 5. The screens and states to draw

Draw each on made-up data in the same prototype style as the earlier cuts: a standalone page, a tweaks panel for the states, light and dark, no server.

1. **Setup > Limits, desktop (about 1200 px).** The header and summary, the "you can change these limits as ..." line, the host line, the groups (Size open, one more open because of a change, the rest closed), and the table with all six columns. Show one row changed in this community, one at the operator's value, one built in, one clamped with its note, one with a once-only override, and one switch.
2. **Setup > Limits, phone (375 px).** The stacked list: each row a card with the column names beside the values; the actions as full-width buttons; the Why disclosure inside the card. Show how the groups collapse.
3. **The expanded row.** Why this limit exists, what happens when it is reached, the reason for the last change, the reason for the value in force, and the once-only override line ("An administrator may allow one act up to 250 MB, with a reason"). Include the long-reason case.
4. **The editor and the preview.** A size ("50 MB"), a time ("30 minutes"), a count, a switch (On/Off), the allowed range as the field's description, the required reason with its "no names" note, **Preview the change**, the preview ("What will change", the server's words, "Recorded as A. Admin, community administrator"), and the confirm labelled with the change. Show the state where the reason is empty (the button's reason in words), and the state where a preview was discarded because a field changed.
5. **A refusal with the nearest value.** The alert in the server's words, nothing changed, "Use 200 MB" filling the field. Also a refusal with no nearest value (a lower-only safety ceiling raised).
6. **Reset to default.** The row action, the same reason and preview, the confirm labelled "Reset ... to the layer above" (Setup) or "to the built-in 100 MB" (Instance), and the row after the reset.
7. **Instance > Limits, desktop.** The operator's table: the value or "not set; communities use 100 MB", the allowed range with "Communities may go up to ...", the optional **ceiling for communities** field in the editor, and the line "A community's own values and reasons are not shown here." Show a ceiling that is lower than the highest the code allows.
8. **Read-only views.** An officer or manager on Setup (no Change or Reset, the reason in words on each row) and the page header line that says so. An admin viewing as someone else on Instance (the refusal).
9. **The honest failures.** An unreadable limits file (the warning above the table, which layer, "the built-in values apply there"); a stored value held to its range (clamped, in both scopes); the host line absent; the loader's own refusal; loading and the "Changed just now" mark.
10. **The per-act override note.** Where a limit has a once-only override, the Why detail says so in words. The override itself is made at the refusal on the upload screen, not here: draw only the note and a pointer ("Asked for at the refusal, by the administrator, with a reason"), and tell the design that the record slot's upload dialog is where the act lives ([screens/records.md](screens/records.md)).
11. **Retention "remove" typed confirmation, for later. Mark it proposed.** A retention limit is the one limit that can delete a copy jason made. The design says it is never confirmed in the screen that sets it without a delete preview (a count and a size, never a name) and a typed word, "remove", and that the deletion is a separate logged job. Draw that dialog as a proposal so the later build has its look; nothing in the build calls it yet.

## 6. What to deliver

- One standalone prototype page for each screen (or one page with a scope switch), on made-up data, with a tweaks panel for: scope, role (administrator, officer, manager, operator, admin as someone else), the states in section 5, light and dark, and 375 / 768 / 1200 px.
- A short note, in the shape of the earlier cuts' notes: what changed from the built screen, what is proposed and not built, and each decision you took where this brief was silent.
- The glyphs and tokens used, by name, with any new glyph and the one meaning it carries (one meaning per glyph).
- A list of the invented sample numbers, so the repository can confirm none is mistaken for a registry value.
- Nothing that names an association, a street, a vendor, a bank, or a person. Rename anything that does before it comes back.

## 7. Proposed, not built

These are fair to draw, marked proposed:

- **Findings for repeated refusals** ("In the last 30 days, 9 uploads were over the limit of 100 MB; the largest was 140 MB. The administrator may raise the limit up to the operator's 200 MB, or leave it.") as data on the screen and one line in the board's digest.
- **The instance's per-community column group** (portal: how many communities use the instance value, which have set a lower one; names and values, no content).
- **A limit currently holding something back** (a rate limit delaying a read, a queue at its depth) as a state on Status, in the registry's words.
- **The retention keys, the sweeper, and the typed "remove" confirmation** (section 5, item 11).
- **Announcing a lowered ceiling** to a community's administrator on the Limits screen and in the next digest.

## 8. Decisions that are the design's

1. Whether the editor opens under the row (built) or in a side panel on a wide screen; and its place on a phone.
2. How the six-column table reads at 768 px: keep the table, or stack early.
3. The glyph for each source (built in, this machine's setting, the operator, this community). The built set is `circle-dashed`, `settings-2`, `landmark`, `pencil`; propose a replacement only if one is unclear.
4. How a held (clamped) value reads without alarm: it is a lead for the administrator, not an error.
5. Whether the Instance screen shows the ceiling and the value as one range bar or as two plain lines.
6. How "Changed just now" fades: a mark that stays until the next reload, or a timed notice.
7. How the host free-space line sits beside size limits on a phone.

## 9. Where it goes

| Part | File |
|---|---|
| The screen | `ui/src/views/LimitsView.tsx`, `ui/src/views/limits.css`, tests in `ui/src/views/limits.test.tsx` |
| The loaders and the writer | `src/jason/web/extra/limits_view.py` |
| The registry, resolver, and trail | `src/jason/limits.py`; `jason limits` |
| The design | [../instance-limits.md](../instance-limits.md), section 4 and the decisions at its end |
| Roles and the sign-in guard | [handoff-instance-and-integrations.md](handoff-instance-and-integrations.md), [security-and-privacy.md](security-and-privacy.md) |
| The words (plain language, no id, a next step) | [content/style.md](content/style.md) |

## 10. Not part of this pass

- The record slot's upload dialog and its override form (drawn with the record checklist).
- Quotas on the data volume as a whole, and billing between an operator and a community.
- Any per-person limit (there is none by design).
- The fonts and theme question the sixth cut raised: [design-brief-fonts-and-theme.md](design-brief-fonts-and-theme.md).
