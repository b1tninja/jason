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

An item is **present** when every check passes, **partial** when some do, and **missing** when none does or nothing in jason holds it yet. The evidence gives counts and keys only, never a private value. A missing item is a place to look, not a finding that the record does not exist: the association may keep it outside jason. Items marked `[person]` have no command that can read them.

## From the checklist to the first profile

1. **Ask.** Send `jason onboard --request` to the prior manager, and the other sources' lists to the board, counsel, and the agent. Paper records come in boxes with a contents list for each.
2. **Keep what is private apart.** People, account numbers, codes, and figures go in `data/spec/<name>.json` or the profile's `notes/`. Passwords and codes go in the vault, never in a document or an email.
3. **Write the profile.** A new `Community` subclass in its own package (profiles.md). Start with the facts the checklist marks as the board's: buildings and units, the board rule, the meeting schedule, the fiscal year, bank accounts by purpose and last digits, insurance policies, utility accounts, the obligations, and the schedule's assignments.
4. **Map the documents.** Pin the library folders and Drive roots to the Civil Code 5200 records, add the kind rules, and map each governing document into its book.
5. **Fetch.** Run the commands the checklist names (`jason sync-catalog`, `jason library`, `jason outlines --fetch`, the county and utility syncs).
6. **Check again.** `jason onboard --checklist` until what is missing is only what a person still has to supply, and each of those has an owner in the schedule.

When an item turns out to be needed that the checklist does not have, add a row to `ITEMS`: what it is, why, where it comes from, what it fills, and how to check it.

This association: the request and response from its own takeover are in its private notes (`mystique/notes/onboarding/`).
