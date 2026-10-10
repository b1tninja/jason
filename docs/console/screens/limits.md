# Limits

`#/setup/limits` in Setup · `#/instance/limits` in Instance · built · loaders `GET /api/limits` and `GET /api/instance-limits`, writer `POST /api/write/limits/<instance|community>` (`jason.web.extra.limits_view`) · design: [instance-limits.md](../../instance-limits.md), section 4

## In the console

One component, `LimitsView` (`ui/src/views/LimitsView.tsx`), in two scopes.

| Screen | Route | Who sees it | Who changes a limit |
|---|---|---|---|
| **Setup > Limits** | `#/setup/limits` | officers, managers, administrators (`roles` on the screen; never the owner view) | the community's administrator; everyone else reads |
| **Instance > Limits** | `#/instance/limits` | one of jason's admins signed in as themselves (`admin: true`, as Status; the server refuses anyone else and an admin viewing as someone else) | the same person, as the instance operator |

The two routes have two segments, so the console resolves a hash by the whole path first and then by its first segment (`findScreen` in `App.tsx`); the screen ids are the routes. The nav gets two groups, **Setup** and **Instance**.

- **The table.** One table per kind (Size, Counts, Rates, Time, At once, Switches, Cost), each group collapsible and open when a value was changed or held to its range. Columns: the limit (its description, with the key small under it), what is in effect in words, where it comes from (a word and a glyph: built in, this machine's setting, the operator, this community), the allowed range with the ceiling, the last change (who and the date), and actions. On a phone the table becomes a stacked list with each column's name beside its value.
- **Why and when it is hit.** A row's **Why** button opens the registry's `why` and `whenHit`, the reason given for the last change, and (where a once-only override exists) its maximum.
- **Clamped and unreadable.** A stored value held to its range shows the server's note under the source. A limits file that could not be read shows a warning above the table naming it; the built-in values apply there.
- **The host line.** "Room on the drive jason writes to: N GB free" from `host`, with the reminder that a size limit never lifts the machine's own guard.
- **Change, preview, confirm.** **Change** opens an editor under the row: the value in the unit's own words (a switch is On or Off), the allowed range beside it, on Instance an optional ceiling for communities, and a required reason. **Preview the change** is the dry run (`dryRun: true`, the writer's default) and shows the server's words for each change and who will be recorded. The one confirm button is labelled with the change ("Set largest file you can upload to 50 MB"). Editing any field after a preview discards the preview, so what is confirmed is what was previewed. A confirmed change reloads the table and marks the row "Changed just now".
- **Reset to default.** A row that has a value in this layer has **Reset**, with the same reason, preview, and confirm. It removes the layer's value.
- **Refusals.** The server's `error` is shown as it said it, in an alert, with nothing changed. When it names a nearest allowed value, a **Use 200 MB** button fills the field with it; the person still previews and confirms.
- **Read only.** A row that cannot be edited says why in its own words (`readOnlyWhy`): only the operator, only the code, or only the community's administrator. An officer or manager sees no Change or Reset button.
- **Accessibility.** Native `details` for the groups; labelled fields with the range as the description; focus goes to the value field on opening and to the preview when it appears; the refusal is `role="alert"`; the confirm is an ordinary button; colors are tokens only, and every state is a word with a glyph.

## Data

Both loaders read disk only. `GET /api/limits` is the community's table (the owner view and a person with no office are refused). `GET /api/instance-limits` is the instance layer and never a community's values or reasons. The writer takes `{act: "set"|"reset", changes | keys, ceiling?, reason, by, dryRun}`; `by` is the signed-in name, and a different name is refused. See [instance-limits.md](../../instance-limits.md) for the registry and the trail.

## Tests

`ui/src/views/limits.test.tsx`: the table in words, why and when hit, read-only reasons, the dry run then the confirm, a refusal with its nearest value, the reset, the officer's read-only view, the unreadable warning, the Instance ceiling, and the two routes and their roles. Fixtures are made up and `fetch` is stubbed, as in the other screens' tests.
