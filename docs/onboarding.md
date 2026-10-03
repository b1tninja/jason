# Onboarding a new association

Bringing an association into jason is the same work a management company does when it takes one over: gather the association's records and information, then set up the systems that use them. jason writes that work down once, as a checklist any California common interest development shares (`jason.community.onboarding`), and checks it against a profile.

## The checklist

Each item is an `OnboardingItem`:

| Field | What it says |
|---|---|
| `title` | what the item is |
| `why` | the statute that requires the association to keep or give it, or what jason uses it for |
| `sources` | where it usually comes from: the prior manager, the board, the county recorder or assessor, the Secretary of State, the developer, the city, the bank, the insurance agent, the accountant, the reserve specialist, a utility, a vendor, counsel, the owners, the management software |
| `fills` | the `Community` method, record, book, or store it fills |
| `checks` | how jason tells it is there (below) |
| `origins` | where the item came from (below) |
| `fetch` | the jason command that reads it once access is set up; with none, a person supplies it |
| `private` | it names people or accounts: it goes in the private facts (`data/spec/<name>.json`) or the profile's notes, never the specification |

The items fall into fifteen groups, in the order a takeover usually needs them: governing documents and amendments; recorded instruments (maps, plans, deeds, the developer's file); corporate and tax filings; the board, officers, committees, and manager; members, units, and occupants; finances; insurance; contracts and vendors; maintenance, utilities, and life safety; meetings; elections; enforcement; architectural review; records, retention, and pending matters; and system access.

An item's `origins`:

- **law**: a statute requires it. The text is on disk (`jason export-authorities`): records (Civil Code 5200), the annual budget report and policy statement (5300, 5310), the buyer's disclosures (4525, 4528), reserve studies (5550, 5565), balcony inspections (5551), owner information (4041), the managing agent (5375, 5380), insurance (5800-5810), and the statement of information (5405).
- **profile**: jason's own design needs it: a `Community` method, a book (`jason.community.books`), or a store.
- **request**: an incoming manager's transition request list asked for it. A typical list has three parts: what is needed at once to set the association up in the manager's systems; what to send after each month's late fees post until the handover (receivables, updates to the collections list and the owner roster); and what comes on the transition date (records, keys, and property; ledgers; the year's 1099s).
- **follow-up**: the incoming manager asked for it during the transition, after the list: bank signers, start-up funds, how utilities are charged, the board's access to the old portal.
- **handoff**: the board's own knowledge-transfer document for a new manager carried it: templates, manuals, the calendar, building plans, the parking and towing record, keys and codes.

A typical takeover list leaves out items the law or jason needs: the reserve study, the balcony inspection report, the statement of information, the loans, the maps and plans, and the policy statement's addresses. The checklist adds them.

## Checking a profile

```bash
jason onboard                             # the session: progress, the stage gates, the next questions (below)
jason onboard --checklist                 # every item: present, partial, or missing, with the evidence
jason onboard --checklist --group finance --status missing
jason onboard --checklist --write         # keep the report in data/onboarding/ (private)
jason onboard --items                     # the checklist itself
jason onboard --request                   # the items to ask the prior manager for, as a list to send
jason onboard --request "county recorder"
```

The command reads only the profile and the data on disk. It writes nothing to PayHOA, Google, or the mail. Each check is one of:

| Check | Passes when |
|---|---|
| `Method` | a `Community` method or property answers with rows (optionally rows naming some words, or one field set) |
| `Kinds` | the classified library (`jason library`) holds files of those document kinds |
| `Record` | the Civil Code 5200 records inventory pins a holder for the record and finds files in it |
| `InBook` | the profile maps a document into the book (`Community.book_entries()`) |
| `Store` | a store under the data folder has rows, files, or entries |
| `Private` | a private fact file has entries |
| `Setting` | a setting is set (a Keeper record UID) |
| `Fact` | a person's answer for the item is in the profile's private facts, or the note that it is kept in Keeper |
| `Settled` | no intake question of some kinds is open (a stage gate's check) |
| `Verified` | each governing instrument's recorded copy is matched in the county index, and none is read without a stamp (a stage gate's check) |

An item is **present** when every check passes, **partial** when some do, and **missing** when none does or nothing in jason holds it yet. The evidence gives counts and keys only, never a private value. A missing item is a place to look, not a finding that the record does not exist: the association may keep it outside jason. Items marked `[person]` have no command that can read them.

## The session

Taking documents in and answering questions are one guided flow. `jason onboard`, with no flags, is that session. It reads the profile and the data on disk, and writes nothing:

```bash
jason onboard                                  # progress, the stage gates, and the next 5 questions
jason onboard --questions --group finance      # more questions (--stage S, --limit N)
jason onboard --scan                           # park the onboarding questions in the intake queue
jason onboard --answer ID "TEXT" --by NAME     # answer one (a choice's number, or words; "dismiss")
jason onboard --confirm ID --by OTHER          # a second person, for a high-stakes answer
jason onboard --apply                          # answers into records (--replace for a changed private fact)
```

- **Progress:** present, partial, and missing by checklist group.
- **The stage gates** (`Stage`, `GATES` in `jason.community.onboarding`), in the order a takeover opens. Each is open when its items are present and its own checks pass:

  | Stage | Open once |
  |---|---|
  | start | the units, the management software, the Drive, and the vault are present |
  | ingest | the records map, minutes, budget reports, financial statements, contracts, and insurance policies are present, and no library file waits for a kind (`Settled`) |
  | establish | the declaration with its amendments and annexations, the bylaws, and the articles are present; each recorded copy is matched in the county index and none is read without a stamp (`Verified`); and no question is open about which text is in force (`Settled` on the governing documents: standing, readings differ, before differs, drift) |
  | operate | the board rule and roster, the signers, the bank accounts, the assessments, the fiscal year, the meeting schedule, the notice rules, the schedule's assignments, and the utility accounts are present |
  | adopt | the operating rules, election rules, policies and resolutions, collection and enforcement policies, the architectural procedure, the governing set, and the conflicts are present |

- **The next questions**, ranked by what each answer unblocks ([intake.md](intake.md#the-session)), each with its evidence, its choices, jason's suggestion where it has a lead, and what it unblocks.

### Questions the checklist asks

- **`FACT`:** a fact the checklist needs and no document holds. An item a person supplies carries a `FactAsk`: the question, where the answer goes, whether it is high stakes, the legal clock it sets (the fiscal year's end sets the annual reports' windows), and the library document kinds that may hold a lead. A missing or partial item with a `FactAsk` is asked. A lead pattern (the employer identification number's shape) suggests an answer from those files' text.
- **`MAP`:** which book or Civil Code 5200 record a document fills. jason asks for a book a checklist item looks for that no document fills, where the outlines or the library hold a candidate. It also asks for a 5200 record held in classified files that no folder is pinned to hold, suggesting the folder that holds most of them.

### Where an answer goes

| The answer is | It becomes |
|---|---|
| a private fact (people, account numbers, the tax ID) | an entry under `facts` in `data/spec/<profile>.json`, keyed by the checklist item, with who answered and when. The file is copied to `data/spec/backups/` first, the change is shown as a diff, and a different answer already there is refused unless `--replace` is given. The item's `Fact` check then passes, and only that it is recorded is reported. |
| a secret (keys and codes, a portal's sign-in) | a record that it is kept in Keeper, under the record the person named, with no value. An answer that looks like a secret (a password, a PIN or code given with its digits, a key or token with its value, a long token) is refused when it is given and is never stored. |
| a profile fact (a book mapping, a pinned folder, the board's seats) | a proposed change under `data/onboarding/proposals/`. Where jason can write the row (a `BookEntry`, a record pinned on an existing library folder row) it is a `.patch` against the profile's own file, for `git apply`. Otherwise it is a `.md` with the answer and the `Community` method it fills, for a person to write. jason never edits the profile. The row names the question and the day, never the person. |

- **A second person.** A high-stakes answer waits for a second person's `--confirm` before `--apply` takes it: which text is in force, whether an instrument was recorded, or a fact marked high stakes (the bank signers). The one confirming is not the one who answered. A new answer clears the confirmation.
- **Every answer is signed.** Who answered and when, and who confirmed and when.
- **The same queue.** Answering, confirming, and applying use the intake queue's own paths (`jason intake`). `jason intake --scan` also parks these questions, and the governance MCP's `answer_intake_question` answers them once parked. `onboarding_status` and `next_questions` read the session ([mcp.md](mcp.md)).

## From the checklist to the first profile

1. **Ask.** Send `jason onboard --request` to the prior manager, and the other sources' lists to the board, counsel, and the agent. Paper records come in boxes with a contents list for each.
2. **Keep what is private apart.** People, account numbers, codes, and figures go in `data/spec/<name>.json` or the profile's `notes/`. Passwords and codes go in the vault, never in a document or an email.
3. **Write the profile.** A new `Community` subclass in its own package (profiles.md). Start with the facts the checklist marks as the board's: buildings and units, the board rule, the meeting schedule, the fiscal year, bank accounts by purpose and last digits, insurance policies, utility accounts, the obligations, and the schedule's assignments.
4. **Map the documents.** Pin the library folders and Drive roots to the Civil Code 5200 records, add the kind rules, and map each governing document into its book.
5. **Fetch.** Run the commands the checklist names (`jason sync-catalog`, `jason library`, `jason outlines --fetch`, the county and utility syncs).
6. **Check again.** `jason onboard` until what is missing is only what a person still has to supply, and each of those has an owner in the schedule. Answer the questions in the order the session gives them.

When an item turns out to be needed that the checklist does not have, add a row to `ITEMS`: what it is, why, where it comes from, what it fills, and how to check it.

This association: the request and response from its own takeover are in its private notes (`mystique/notes/onboarding/`).
