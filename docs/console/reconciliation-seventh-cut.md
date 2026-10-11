# The console handoff's seventh cut, reconciled with what is built

The design agent's seventh cut (2026-10-10, `Jason UI7.zip`) adds five prototype pages on made-up data, each for a spec that had no design: draft an email from an item (`draft-from-item/DraftFromItem.dc.html`), forms and follow-ups (`follow-ups/FollowUps.dc.html`), the form library (`form-library/FormLibrary.dc.html`), limits (`limits/Limits.dc.html`, a visual pass over a built screen), and the administrator's components (`admin-components/AdminComponents.dc.html`). Its note is `jason-console/SEVENTH-CUT.md`.

How this was read: three readers read each page as text (markup, styles, script, copy) beside its spec, the repo, and the statutes on disk (`data/authorities`). Nothing was opened or run. The package stays outside the repository (it names the profile and its domain, and carries sample data that mirrors real records); what comes back is general. The format is [reconciliation-sixth-cut.md](reconciliation-sixth-cut.md)'s: verdicts **matches**, **adopt** (the design is better), **keep** (the build is better), **decide** (a conflict that needs the user). The recurring faults are those of [handoff-reconciliation-5.md](handoff-reconciliation-5.md); the specs are [handoff-draft-from-item.md](handoff-draft-from-item.md), [handoff-followups.md](handoff-followups.md), [handoff-form-library.md](handoff-form-library.md), [screens/limits.md](screens/limits.md), and [handoff-admin-components.md](handoff-admin-components.md).

## In one paragraph

The layouts, the copy, the state words, and the patterns are the best the design has produced and nearly all can be adopted: provenance you can see and hear, a regenerate that never overwrites, a funnel that keeps "how asked" and "how answered" apart from the stages, a follow-up band with chips that differ by border and weight, a form that shows its clock before its questions, a dot per connection with one banner for a shared failure, and a command block that says it is not a button. What the cut gets wrong is what earlier cuts got wrong: **statute text that is paraphrased or wrong** (6 sections), **clocks shown as the law's that are proposed numbers**, **a registry, a command list, and vault paths that do not exist**, **writes the web layer cannot make**, and **hard-coded people, dates, and the profile's name**. It also gets one thing right that the specs had wrong: the funnel's outstanding count (below).

## 1. The open item: what "outstanding" counts

The cut flags that its sample counts outstanding as owners less answered less unreachable (107 − 47 − 2 = 58), not asked minus answered as its prose says. **The prose is right and the sample is wrong, and the spec's sample is wrong too.**
- The build counts outstanding as owners **sent a personal copy**, less those with an answer, less the unreachable ([campaign_funnel.py](../../src/jason/tasks/campaign_funnel.py), [response_outstanding.py](../../src/jason/tasks/response_outstanding.py)). An owner never sent a copy is a separate `neverAsked` count and list.
- 107 − 47 − 2 = 58 folds the 17 owners never sent a copy into the outstanding. It also inflates the reminder ("remind 107" where only the owners who can be reminded are 40), and it lists the 17 among the outstanding.
- The funnel's "asked" counts copies, not owners, and "answered" counts every arrival of the request (a separate `neverAskedAnswered` counts answers from owners never asked). So even the prose is loose.
- **Fix for the design:** show outstanding (owners sent a copy, with no answer, not unreachable), "never sent a copy" as its own line with its own action, and unreachable apart. **Fix for the spec:** [handoff-followups.md](handoff-followups.md)'s sample (90 / 47 / 58 / 17) is corrected to numbers that add.

## 2. Draft an email

| Element | Verdict |
|---|---|
| Source card pinned, collapses under 720 px | adopt; "stale" must show whenever the source changed since composing, not only in the saved-earlier view |
| Provenance switch, off by default; record underlined, template dotted, person shaded, blocked inset; each also a hidden word; focus shows the evidence and level | adopt |
| Editing a paragraph makes the whole paragraph one "person" sentence and drops its evidence | decide: keep per-sentence origin through an edit |
| Regenerate shows "Yours" beside "Fresh" per paragraph; never overwrites | adopt; the author's name comes from the session |
| Gate, asking wording: "This email asks. It commits the association to nothing." | adopt, reworded: jason cannot know what typed words commit to; say "jason reads this purpose as a request" |
| Gate, held wording | adopt with `HeldNote`; the recorded decision (meeting, motion) is loaded and must cover this source and purpose, not a global flag |
| P1 sentence with a vendor chosen blocks that recipient ("Take it out") | adopt |
| P3 to counsel: acknowledge to continue | adopt; compute it from the recipient and the sentences, not a static reminder |
| Non-renewal links out to Draft letter with the window and the clause recited | adopt; the dates and the clause come from the contract-terms reading |
| Trail (drafted, saved, sent, follow-up) | adopt; add reply received, withdrawn (a draft that is gone: `DraftNotFound`), follow-up past |
| Page with a drawer variant that expands | adopt; the built `Drawer` is the dock's, so a general one is new |
| Recipient picker with reasons, nothing pre-selected; reminders | adopt |

**Faults.**
- **Statute text.** The source card recites "CIV 4935(a): a litigation matter may be heard in executive session". The stored text is "The board may adjourn to, or meet solely in, executive session to consider litigation, matters relating to the formation of contracts with third parties, member discipline, personnel matters, or to meet with a member, upon the member's request, regarding the member's payment of assessments, as specified in Section 5665." Show the citation, or recite it whole.
- **Jason's characterizations sent as the association's:** "The association keeps these systems under 19 CCR 904.1(a)" is a summary in an outgoing email; the real draft gives the citation only. A summary of the notice window sits in an email to counsel as a "record" sentence.
- **A clause shown as a stored recitation** is sample words with a Drive address, no "sample" label.
- **"From the template"** is claimed for facts a base template cannot know (a unit's dripping head).
- **The Accept purpose composes "The board accepts your estimate"** under a note that the email cannot accept. Disable the committing text until a recorded decision exists.
- **Typed text** inherits its paragraph's level and is never scanned for names or units, so the owner-PII rule holds only for the sentences jason wrote.
- **P3 shown without the private view:** the executive source shows the claim file and counsel's address. Counsel's contact is a private fact; P3 opens only in the private view.
- **Command and writes:** `jason draft --item … --purpose …` has neither flag (the real `jason draft` takes `--proposal-request`, `--hearing`, `--meeting-notice`, and one `--to`, no `--cc`). The web layer has no Gmail writer; "Save" is a `Confirm` on local state and sets a dock follow-up in the same click (a second write). Until a draft approvals kind exists, Save is a `TerminalStep`.
- **Hard-coded:** the profile's name (a letter's sign-off), people, claim and policy numbers (use "26-0000"), dates, "41 days", the whole trail.

**The build must add:** a `DraftPurpose` row set (a `Community` method with an empty default) and a composer returning sentences with origin, evidence, level, and citation (`proposal_request.draft` returns flat text today); `GET /api/drafts/purposes`, `POST /api/drafts/compose`, a Gmail write with `by` and a dry run; cc and thread support in `jason draft`; a trail store that reads sent and reply from the headers; follow-ups through `followups.add_manual`.

## 3. Follow-ups

| Element | Verdict |
|---|---|
| Funnel, four cumulative stages, bars, source ages | matches; take the ages from `ages` (the cut hard-codes "6 h old"); the per-channel ages are hover-only and must show |
| "How asked" and "How answered" under a dashed rule, "two separate facts, not stages" | adopt (answers a spec decision) |
| Unreachable as its own line and card | adopt |
| 30-day strip | adopt; remove the claim that the dock carries these (it does not) |
| Bands with sticky headings; "Acted on today" | matches; "acted on today" needs a second read (`state=done`) because a done item leaves the list at once |
| Basis chips differ by border and weight (Required solid, Proposed dashed, the board's rule a heavy left edge, Yours shaded) | adopt; the build's bases are `law`, `documents`, `proposed policy`, `person`; "the board's rule" has no producer yet |
| Deferred rows sit at the new date with "moved from …" | adopt; the build keeps `due` and puts the new day in `deferredTo`, hidden until then, so the loader must include them |
| Kind glyphs (bell, calendar, printer, eye, flag; user-x for unreachable) | adopt; the build also uses `resend` for "ask the member for an address", which the printer mislabels |
| Card "Next:" opens Follow-ups for its campaign | matches |
| Director sees counts only | **dropped (2026-10-11):** directors and officers have the same access to information; no director-only view |
| Done, Defer, Drop, Add through `Confirm` | the build has no writer; each is a `TerminalStep` (`jason followups --done/--defer/--drop/--add … --by NAME`) until one exists; "leaves the list tomorrow" is false (it leaves at once) |

**Faults.**
- **Civil Code 4041(e).** The cut recites "resend … by first-class mail" and says "the law mails them". The stored text: the association "shall resend the notice to a mailing or email address identified by the member pursuant to Section 4040". "By mail" is a reading and needs a label.
- **Civil Code 5210(b), shown as the law's clock for acknowledging a request.** The statute sets the response clocks (10 business days for records prepared in the current fiscal year, 30 calendar days for the previous two); acknowledging within a number of days is the build's **proposed** number. The statutory clocks are not in the follow-up kinds, so they produce no follow-up. This is the proposed-as-law fault.
- **Civil Code 5300:** "30 to 90 days before the fiscal year"; the stored text says "before the end of its fiscal year".
- **Invented controls and commands:** `jason notices --resend --campaign`, `jason responses --confirm|--read --campaign` (the build takes an id and `--by`), `jason requests --acknowledge`, `jason owner-info --record`, `jason disclosures --annual`, `jason pool-keys`. The item's own `command` field is the command.
- **Arithmetic:** a row "3 days after Sep 30" shows Oct 4 (Oct 3). "Due soon" is within 5 days in the build, not 3.
- **Hard-coded:** `TODAY`, "as of Oct 5, 4:30 PM", the person in every summary.

**The build must add:** writers (or `TerminalStep`s) for the four acts; a role-aware loader that returns counts alone to a director; the `deferred` view at `deferredTo` and done-today; a `neverAsked` list on the campaign page; a copies-sent table (resolve `answeredBy` to channel and date); pills for new words.

## 4. The form library

| Element | Verdict |
|---|---|
| The form in four channels (portal, paper and PDF, PayHOA, the emailed copy) | matches; the build has six (adds the fillable PDF and the Google Form) |
| PayHOA with a 255-character help count | adopt; the limit is real (`DESCRIPTION_MAX`, refused when over), "up to 255", not "under"; the build puts sections in as dividers and the preamble in the HTML description, so a "heading text block" is unbuilt; the sample silently drops two questions |
| QR placeholder and a short link | keep the placeholder; the short link is invented (the build has a QR helper, no short-link service) |
| The recital shows the operative sentence and expands to the clock's section | adopt the layout; the loader returns citations, not words, so a `recitalWords` field is new |
| Error summary, linked; "already on file" | adopt; the build has no dedupe store or window |
| "Ask the association": groups by need, search, "Write to us" last | decide: no `Community` method holds the groups or their wording; the "when" lines are unbased (below) |
| My requests with a reference lookup | decide: only `records-requests` has an owner loader, and owner sign-in is undecided |
| Library tier glyphs (scale, book-open, house) | adopt |
| The adjustment diff, with a refused change and its finding | adopt the shape; the build has only `applied` and `refused` strings, so a before/after, who, and why are new; **a refused change makes the form `failing`, not `adjusted`** |

**Faults.**
- **Civil Code 5210 in plain words:** "10 business days for this year's and last year's records" is wrong (10 business days is the current fiscal year only; the previous two years are 30 calendar days), and the receipt applies the 10-day clock to a 2025 budget and June minutes, which fall under the 30-day clock. A partial recital without an ellipsis.
- **Civil Code 5205:** the quotation is cut short with a period, and the PayHOA copy ends in an invented ellipsis; §5205(b) is cited for "how you want them" and §5205(e) for "the law asks you to identify them", neither of which is what those subdivisions say.
- **Civil Code 5915 as an unconditional right:** it applies where the association has no dispute procedure of its own; the stored remedy for withheld records is §5235, which the build's records form requires and the design omits. The records form also lacks the items the build checks (the cost notice, redaction, the electronic option, the withholding explanation, the use limit).
- **Civil Code 5225 "amended 2026-01-01":** the stored section was added in 2012 and never amended, and its words differ; the 2026 amendments are to §5200 and §5210. The "stale" example is fabricated, and `stale` is not a library status (it is a failing recitals finding that starts "stale:").
- **Civil Code 5935:** the required item is a paraphrase; the stored (a)(3): "required to respond within 30 days of receipt or the request will be deemed rejected".
- **"Ask the association" clocks:** EV charger "45 days" (the statute says 60); dispute a charge and meet and confer "15 days" (the build proposes 30); the architectural "45 days" is policy, not law (Civil Code 4765(a)(1) asks the procedure to state a maximum); a payment plan "decided at the next meeting" (stored 5665(b): within 45 days of the postmark, on the stated conditions); EV and solar "or it is approved" omits "unless that delay is the result of a reasonable request for additional information".
- **Library data:** `arch-request` is shown as Family where the build's `architectural-application` is State (the fifth cut's error, repeated); `rental-application` and `pool-keys` are not in the library; the owner-information form is Custom in the build, shown as State; the tier words are state, family, custom (not "standard", "association"); the handler names are the registry's (`owner-information`, `response-clock`, and the general handlers), not "ADR clock", "board review"; the seven checks are required content, recitals, slots, adjustments, handler, marker codes, forbidden asks (the cut's "other words", "clock names basis", "fits channel" are not checks, and "all pass" is hard-coded).
- **Reference formats** do not fit [form-identifiers.md](../form-identifiers.md): a code lacks the channel letter, uses letters outside the alphabet, and campaign codes whose channel is not E, M, or P.
- **Commands that do not exist:** `jason forms --diff|--make|--check|--why`. The real ones are `jason form-library --check|--show`.

## 5. Limits

| Element | Verdict |
|---|---|
| One native `details` per kind, collapsed unless a value is changed or clamped | matches; adopt the "N limits · M changed" summary |
| Source as a word, a glyph, and a border | matches the words (the server's `SOURCE_WORDS`) |
| Columns: Limit, In effect, From, Allowed, Last change, Actions | matches |
| Why panel with a "Takes effect" row | adopt: the build shows "Takes effect after a restart" for **every** row because it reads the server's `restart` string as a boolean (`LimitsView.tsx:118`); the server's words are "at once", "from the next job", "after the next start" |
| Clamped note; read-only reasons | matches; the text is the server's `note`; adopt the server's "this is the lowest allowed" case |
| Editor: unit beside the field; On/Off radios for a switch | adopt (the build uses a select and free text; keep sending the string, "50MB") |
| Reason field | keep the build's "no names" caution; adopt "recorded with your name" |
| Preview takes focus; "Recorded as" role | adopt; the role is the server's `recordedAs`, with its `note` |
| Confirm named for the change; refusal with "Use N" | matches; the refusal text is the server's |
| Unreadable-file warning | keep the build's form: no path, a warn notice, shown on Instance too |

**Faults.**
- **The registry:** the real registry has nine keys (`upload.max_bytes`, `fetch.max_bytes`, `split.auto_read`, `split.thumbnail_cache_bytes`, `split.max_pages`, `split.max_parts`, `split.ocr_queue_max`, `split.suggest_enabled`, `split.draft_days`). The cut's seven others (OCR pages per job, batch items, Drive reads per hour, session idle minutes, temp retention days, hosted models, the mailroom cost ceiling) are not registered; they are [instance-limits.md](../instance-limits.md)'s "not built" list, so the Rates and Cost groups and their numbers are invented. "Minutes" is not a unit (the units are bytes, count, per hour, seconds, days, cents, switch).
- **Wrong numbers on real keys:** `fetch.max_bytes` is shown as default 50 MB, maximum 250 MB (it is 100 MB and 500 MB); the once-only upload override is shown as 500 MB (250 MB), so "never past its ceiling" is wrong.
- **The `whenHit` sentences** are invented; the registry's are templates with `{amount}`, `{limit}`, `{ceiling}`, `{override_max}`.
- **The unreadable warning** names a path and a line number; the server returns only "this community's limits file". It says "built-in values apply"; the rule is the stricter of the default and the readable layers.
- **Glyphs** all exist, but several break one glyph, one meaning (`building`, `wrench`, `eye`, `archive`, `triangle-alert` are assigned to other ideas): decide, probably keep the build's set.
- **Missing states:** loading, 401/403, a network error, a busy preview, and the Instance unreadable state.

**The build must add:** a short `label` on each registry limit (the Limit column and the confirm text use the sentence today), the filled `whenHit`, the `restart` words in `LimitRow` (fixing the bug above), an `unreadable` list on the instance read, and a "may only be lowered" note.

## 6. The administrator's components

| Element | Verdict |
|---|---|
| A strip of communities, a dot per connection and a summary | adopt, with a list role and a title per dot; the loader reads one community, so the build must read every community's states |
| The five words as a legend; `why` always shown | matches `ConnectionState` |
| Cards: scope, account, `CredentialLine`, capabilities collapsed with disabled switches and a "writes" chip | matches; no reveal control, no value |
| Rate note with links | decide: the registry's `RateLimit.source` is a page title, not a URL |
| One PayHOA banner over the group | matches; the pause-by-person variant is not drawn |
| Terminal block: "It is not a button" | adopt |
| Schedules table, lead words, floor and editor | matches the `held` kinds; missing "paused by NAME", never seeded, misfire |
| Service panel: parts, lanes, next runs | partly: no `draining`, no refused, failed, or ended part; the stale threshold (90 s, beat every 30) is never shown |
| Vault panel: names only, `MigrationPlan` | matches; needs a route |
| "failing" uses the cable glyph | the claim holds (`unlink` is not in the bundle), but `cable` means "Utilities" on the same page; `plug` is free: decide |

**Faults.**
- **Commands that do not exist or are wrong:** `jason integrations setup …` (only `list` and `check` exist); `integrations check … --instance …`; `jason cadence SRC --default --by …` (the real one is `--restore SOURCE --by NAME`, and "Adopt" composes `--every`, which replaces a cron default); `jason daemon stop --community …` (the flag is `--profile`); `jason serve --install-task` (a dry run without `--yes`); `jason vendors --reports NAME` (`--reports` takes no value); and top-level commands that have no parser (`payhoa --ledger`, `county --recorder`, `owners --workbook`, `fax --sync`, `ocr --read`).
- **Vault paths:** a vendor portal is `jason/community/<c>/vendor-portal/<portal-key>`, not `…/portal-…/login`; Google Workspace's client is community-scoped (`…/google-workspace/oauth-client`), not under `instance/signin`.
- **Invented capabilities and sources:** Google scopes `gmail.metadata` and `calendar.readonly` (the registry's are `gmail.readonly` and `calendar.events.readonly`, and it has 16 capabilities, not 4); PayHOA's card omits "Bulk writes"; a `payhoa-owners` source and "7 schedules paused"; per-portal sources (the registry has the single `vendor-portals` source); `county-recorder`, `owner-workbook`, `mailroom-send`, `fax-inbox`, and a retired row.
- **Wrong cadences and floors:** Drive is "every 2h, floor 15m" (every 15 minutes 07-22, hourly outside, floor 5m); Calendar every 1h (30m); the PayHOA ledger "every 6h, floor 1h" (weekly and on the 5th, floor 1d).
- **Heartbeat and service:** `draining` is missing; "stopped after a drain request by NAME", "started by Task Scheduler", and "waiting: another community's job" are not in the data (the loader is disk-only; the GPU lock records a pid and a time); the 6:00 AM failure is a scheduled run, but the card calls it "Last checked", and a check is a person's act.
- **The vault's default state, "not asked"** is not drawn. `?vault=1` makes the console ask Keeper for names, non-interactively: built, but a console-initiated call to Keeper. Decided: dev only (section 8).
- **Clean:** no secret is shown or taken, there is no connect or OAuth flow in the browser, no start or stop button, no live-check button.

**The build must add:** a per-community integration read for the dots; a vault JSON route (names, owner groups, the migration plan's states); draining and the other part states; a queued-GPU-job read for "waiting"; a never-seeded state for schedules; a rate-limit URL field if the link stays; and the Integrations, Service, and Vault views (none exist in `ui/src`; only the three loaders do).

## 7. Corrections for the design agent, in one list

1. **Statute text:** recite from the stored copy or cite only. Fix 4041(e), 5210(b), 5205, 5225, 5300, 5915/5235, 5935, 4935(a) as above; never present a proposed number (acknowledge in a number of days, 15 or 30 for a dispute, 45 for an architectural review) as the law's.
2. **Commands, keys, vault paths, and the registry:** use only those in the build (the tables above); the item's own `command` is the command.
3. **Vocabulary:** follow-up states upcoming, due, overdue, done, deferred, dropped; bases `law`, `documents`, `proposed policy`, `person`; library statuses ready, adjusted, not offered, failing (a stale recital is a failing finding); tiers state, family, custom; the five connection states; the five heartbeat states.
4. **Form keys:** `architectural-application` is State; no `rental-application` or `pool-keys` until the library has them; the owner-information form is Custom.
5. **Reference formats** follow [form-identifiers.md](../form-identifiers.md).
6. **No write in a template.** Each act is a `TerminalStep` with the real command until its writer exists.
7. **Nothing hard-coded:** no "today", "just now", names, claim numbers, the profile's name or domain; plainly fake values ("123 Main St", "26-0000").
8. **Glyphs:** one glyph, one meaning (`GLYPH_META`); `plug` for failing.

## 8. Decisions for you

1. **The vault's names: decided.** The vault (Keeper) is the development environment's store, so the console asks it only under `jason-web --dev`; elsewhere the vault panel says it was not asked and why, and a production installation reads its credentials from its own secret store, chosen when it is hosted ([integrations-design.md](../integrations-design.md)). The design draws three states: asked and answered, asked and could not be answered, and not asked (not in dev).
2. **A director's view of follow-ups:** answered 2026-10-11: none; a director reads what an officer reads.
3. **Draft an email: decided (October 10, 2026): yes, through an approvals kind, never sent.** The console may create a Gmail draft, only as the approvals kind `gmail-drafts` ([approval-workflow.md](approval-workflow.md)): a person approves one planned email, and the applier saves it as a draft in the signed-in Gmail account. The kind covers the three cases `jason draft` composes (a proposal request, a hearing notice, a meeting notice) with the recipient the person chooses; jason has no send method, and the person sends the draft from Gmail. The free-text composer in [handoff-draft-from-item.md](handoff-draft-from-item.md) (purposes, `cc` and thread support, regenerate) is still unbuilt, and the prototype's "Save" stays a `TerminalStep` until it is.
4. **Which glyphs** break one-glyph-one-meaning in Limits and the admin page: keep the build's set, or give the new meanings new glyphs?
5. **Owner sign-in** for "My requests" and the reference lookup (still the board's decision).

## 9. What to adopt as is

The provenance layer and hidden words; the regenerate diff; the source card's phone collapse; the recipient and reminder layouts; the funnel with its dashed rule and the unreachable block; the 30-day strip, bands, chips, and kind glyphs; the form in four channels with its clock above its questions; the error summary; the tier glyphs; the group summary, unit-beside fields, On/Off radios, and the named confirm in Limits; the dots-and-summary strip, the legend, the single banner, and the "not a button" command block in the administrator's components.
