# jason

HOA virtual agent. Orchestrates **payhoa**, **smud**, **idoxs**, Keeper (`keepersdk`), `jason.google`, and `jason.zoom`. PayHOA HTTP lives in the payhoa package; jason decides when to call it.

Workflows and skill-level “do not”s: **[SKILLS.md](SKILLS.md)**. Human setup: **[README.md](README.md)**.

## Design goals

jason is a reusable agent for California common interest developments. One association is a **profile**: the data that makes jason serve that association. Code, general docs, and base templates are written once for any association. Nothing about one association goes into them. ([docs/profiles.md](docs/profiles.md) has the full design and the phases still open.)

### Layout

| Where | What | Checked in |
|---|---|---|
| `src/jason/` | The implementation: the `Community` interface, models, readers, tasks, commands, and MCP tools. It names no association, street, vendor, folder, or id. | yes |
| `docs/`, `AGENTS.md`, `README.md`, `SKILLS.md` | General documentation. It says "the association" or "the specification", never the profile's facts. | yes |
| `mystique/` | The `mystique` profile, a `Community` subclass and its rule rows (`mystique/*.py`). | yes |
| `mystique/docs/` | This association's setup: its Drive map, vendors, phases, and why each rule row exists. | yes |
| `mystique/notes/` | This association's findings: owners, parties, matters, figures, and review results. | **no** |
| `data/spec/<name>.json` | The profile's private facts: people, contacts, and account numbers. | **no** |
| `data/` | Stores, caches, and generated pages. | **no** |
| `tests/fixtures/spec` | Made-up private facts, so the tests give the same results on any checkout. | yes |

### Rules

- **Dependencies point one way.**
  - A profile imports jason; jason never imports a profile.
  - Code reaches the active profile through `jason.community.community()` and `JASON_PROFILE` (default `mystique`). Another association means another profile, not a change to jason.
  - `mystique()` is the older name for the same call. New code calls `community()`. Code never imports `mystique` or `jason_mystique` directly.
- **The interface is `Community`.**
  - A task reads the association only through `Community` methods and records.
  - When a task needs a new fact, add a method to `Community` with an empty default (`()`, `None`, `""`), then implement it in the profile. A missing fact is then a miss, not a crash, for every other profile.
  - Do not read a profile's private attributes, its module constants (`spec_module` is being phased out), or attributes that only one profile has.
- **Importing jason loads no profile.** Settings that come from the profile are read when first asked for. A default argument never evaluates the profile.
- **Facts are data.**
  - A fact goes in the profile. It does not go in a task, a regex, a default argument, `config.py`, or a docstring example.
  - Examples in help text, tool descriptions, and docs are plainly fake ("123 Main St", "24CV000123").
- **The boundary is tested.** `tests/test_profile.py` loads a second, throwaway profile beside `mystique`. It also checks that no general doc names the profile's facts: its names, streets, vendors, banks, case numbers, group addresses, Drive ids, and org id.
  - A code pointer (`mystique/meetings.py`) is allowed.
  - A cleared term is removed from the ratchet with `python -m jason.community.boundary --update`.
- **Regional sources and vendor formats are adapters.**
  - The Sacramento County recorder, assessor, and tax sources, the City's permits, SMUD, and one vendor's invoice or portal layout are reusable readers.
  - Which of them an association uses is profile data.
- **Templates are written once.** A notice, letter, form, or packet is a general base template. A profile renders it with its own name, letterhead, contacts, and rules. A community-specific copy is generated from the base, not edited by hand.

### Inside a profile

Keep three layers apart. The specification is data. The implementation is reusable helpers. A task only applies a result.

- **Specification.** The association's facts are its profile's `Community` class, `Mystique` in **[mystique](mystique/README.md)**: buildings, transaction rules, sync rules, known files, PayHOA folders, Drive roots, site pages, and governing documents. Add a fact as a class attribute there. Do not add a JSON spec, and do not hardcode the fact in a task, a default argument, or `config.py`. Use `KnownFile`, `PayhoaFolder`, and `SitePage`. A governing document is a `GoverningDocument` bound to a Drive id. An amendment is an `Amendment` mixin on `Document` and records the sections it changes. Do not add one `KnownFile` member per amendment. An association record is an `AssociationRecord` from Civil Code 5200, pinned on the Drive sync rule, library folder, or known file that holds it. A document the subdivider had to deliver is a `DeveloperDelivery`. `pin()` is the 5200 record. `deliver()` is the map, plan, common-area deed, public report, or plan set that is not one of those records. `developer_file()` groups the pins. An empty group is a missing document. A folder with no pin is unclassified. A document's `DocumentKind` says what it is, and `DocumentCategory` is the shelf; `documents.PROFILE` maps each kind to its shelf and its Civil Code 5200 record. `classify_document` applies the profile's kind rules in order, by name, PayHOA folder, and library path. A name that matches none goes to the phrase rules in `jason.community.content`, then to a local model; a miss after all three stays a miss. The association's bank accounts and which is the reserve are `BankAccount` rows in `mystique/banking.py`. A letter template is a `DocumentTemplate` row in `mystique/templates.py`: a Drive Doc with `{VARIABLE}` tokens; a letter is a filled copy. The association's Google Groups are `GoogleGroup` rows in `mystique/groups.py` with a `GroupPurpose`; the Gmail sync keeps the groups each message came through and reads a group-rewritten sender from `X-Original-From` ([docs/gmail.md](docs/gmail.md)).
- **Private facts stay out of the specification.** People's names, emails, and phone numbers; which unit an owner rents; account numbers; settlement figures; and counsel's direct contact go in `data/spec/<name>.json`, which is never checked in. The specification merges them in through `jason.community.private.facts(name)`, and a missing file means none. Tests read made-up ones from `tests/fixtures/spec` (`conftest.py` sets `JASON_SPEC_DIR`), so they give the same results on any checkout. Facts the board keeps up to date belong in a register (docs/registers.md).
- **Implementation.** `jason.community.Community` is the abstract base. `jason.community.profile` loads the active profile's class. Shared matchers (`assign_building`, `first_utility`) classify. They do not call PayHOA, Google, or Keeper.
- **Use.** Task code asks `Jason.community` and acts on the classification. A new decision is a new rule row, not a new function with one association's id inside it. Match order is part of the rule. A miss stays a miss.

Prefer classes, structured records, and enums over string tokens. JSON may store the word; the loader must turn it into a symbol before a task sees it. Closed sets already defined: `Building`, `Street`, `Parity`, `DocumentRule`, `Utility`. `BuildingRange` and `TransactionRule` are the records. Reach for those members (`Building.BLDG_2`, `Utility.SMUD`) instead of `"2"` or `"smud"`. `Building`, `Street`, `KnownFile`, `PayhoaFolder`, `SitePage`, and `PublicDrive` still hold one association's members in `jason.community.symbols`; they are moving into the profile (phase 3 in [docs/profiles.md](docs/profiles.md)). Do not add members for another association to them, and do not name their members in general code.

## Commands

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -U pip
pip install -e D:\code\payhoa
pip install -e D:\code\smud
pip install -e D:\code\i-doxs
pip install -e ".[dev]"
# Optional local catalog MCP (disk only):
pip install -e ".[mcp]"
# Optional SVG charts for the Markdown reports (matplotlib):
pip install -e ".[charts]"
# Optional model reader for scanned instruments (anthropic; needs ANTHROPIC_API_KEY):
pip install -e ".[models]"
# Optional QR codes for links in printed letters and notices (segno):
pip install -e ".[qr]"
```

```bash
pytest
jason login                    # interactive terminal only; once for Keeper
jason sync-bills --dry-run
jason-mcp                      # stdio; local catalog only
```

Copy `.env.example` → `.env` and fill Keeper record UIDs (never commit `.env`).

## Boundaries

- Amounts are **integer cents** (`6120` = $61.20).
- Non-interactive runs use `interactive=False` and **fail fast** (`KeeperAuthRequired`, `GoogleAuthRequired`). Do not open a browser unless a person passed `interactive=True`.
- Do not approve, deny, or assign requests. One exception, the board's of October 1, 2026: once `jason owner-info --apply --payhoa --yes` has recorded an owner's PayHOA owner-information answer in full (its tags written and nothing left for a person to enter), it marks that request complete with `OWNER_INFO_COMPLETED_COMMENT` (`mystique/forms.py`), emailed to the owner. An answer needing a person stays open. jason never deletes or edits an owner's submission.
- Do not submit delinquent accounts to a collection agency (sheet/CSV handoff only).
- In a live Zoom meeting, jason pauses or resumes the recording and posts a caption only from `jason zoom --recording … --yes` or `jason zoom --caption … --yes` run by a person, as the host, logged under the meeting id (`data/zoom/live-acts.json`). A caption is a broadcast to every participant: it carries an answer a person chose, prefixed `jason:`, never jason's own initiative. jason never admits, mutes, removes, polls, or ends a meeting.
- Do not mail a letter on jason's own initiative. PayHOA's Mailroom (`jason mailroom`; USPS through Lob) prints, mails, and charges the association: `--pdf` with `--units` previews and lists the recipients; only `--send --yes` from a person mails it, and `--cancel ID --yes` cancels a letter still processing. Each sending is logged in `data/mailroom/sent.jsonl` with its letters and their communication ids. `--letters KIND`, `--events COMMUNICATION`, `--months YEAR`, and `--prices` only read. Billing is by printed page with PayHOA's address page counted (`payhoa.pricing`), and a sixth billed page adds $2.25 of postage a letter, so a PDF letter is four pages at most unless a person chooses otherwise.
- Never delete a live PayHOA form. Once a letter, QR code, or email links to a form, it is locked in `data/payhoa/forms.json` (`payhoa_forms.lock`): change it in place with `jason forms --payhoa KEY --update`, which keeps each question's id and answers. `--replace` refuses a locked form, and each owner-information send first checks that the form it links to is in PayHOA and on (`payhoa_forms.live_problem`).
- Do not invent CC&R quotes from file names; quote document body text only when you have the file.
- A request that runs a local model holds the GPU lock, and a store jason reads, changes, and writes back holds its store lock (`jason.locks`). A model job runs `jason.local_ai.preflight` first and fails fast on the CPU or short of commit. `jason local-ai` reports the stack; see [docs/document-tools.md](docs/document-tools.md).
- Drive text watermarks (e.g. diagonal DRAFT) **cannot** be removed via the Docs API; remove them in the Docs editor before export.
- Do not commit HARs, `.env`, or `secrets/google-token.json`.

## jason-mcp

`jason-mcp` is a stdio MCP server over the stores already on disk. It does **not** call PayHOA, Google, or Keeper. `jason-mcp --profile board` (or `JASON_MCP_PROFILE=board`) serves the board's thirty-eight tools, starting with `board_digest`; AnythingLLM is registered with that profile. Each tool carries its caveats; repeat them. A confidential file is held back unless asked, and a reading or a hit is evidence, not a pin. Every tool and its caveat: [docs/mcp.md](docs/mcp.md).

## Deeper docs

Every document is indexed in [docs/README.md](docs/README.md). Start with:

- [SKILLS.md](SKILLS.md) — use cases and agent workflows
- [README.md](README.md) — what jason is and the CLI list
- [docs/setup.md](docs/setup.md) — setup: Google, Keeper, and the optional tools
- [docs/profiles.md](docs/profiles.md) — one association as a profile, the documentation tiers, and the phases to make jason reusable
- [docs/cli.md](docs/cli.md) — the commands
- [docs/mcp.md](docs/mcp.md) — the MCP tools, profiles, and caveats
- [docs/registers.md](docs/registers.md) — registers in Google Sheets, Forms, and Tasks, and what stays jason only

The profile's own docs start at [mystique/docs/README.md](mystique/docs/README.md). Its notes (ownership history, the two unit numberings, the loose ends, and each review's findings) live in `mystique/notes/`, which git ignores because they name owners and parties. Keep them out of commits, and never edit them to scrub them: they are the association's records.
