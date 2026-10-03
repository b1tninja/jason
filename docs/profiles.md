# Profiles

jason is the implementation. A **profile** is one association: its buildings, units, rules, folders, documents, vendors, and accounts, as a `Community` subclass in its own package. The first profile is `mystique` (`mystique/`). Another association is a new profile, not a change to jason.

## Choosing a profile

`JASON_PROFILE` (environment or `.env`) names the active profile; it defaults to `mystique`. `jason.community.community()` returns it, loaded once. (`mystique()` is the older name for the same call.) The package is found, in order, at:

1. `JASON_PROFILE_DIR`, a folder with an `__init__.py`;
2. `profiles/<name>/` or `<name>/` in a folder above jason's source;
3. an installed package registered under the `jason.profiles` entry point group:

```toml
[project.entry-points."jason.profiles"]
oakview = "jason_oakview"
```

It is imported as `jason_<name>`. Its `PROFILE` attribute names the `Community` class. `spec_module("forms")` reads one module of the active profile.

Importing jason loads no profile. The settings that come from it (`payhoa_org_id`, the utility categories) are read when first asked for, so a profile with no SMUD rule has no SMUD category instead of failing.

The tests run against `mystique` whatever `.env` says (`tests/conftest.py`). `tests/test_profile.py` also builds a small second profile and loads it next to the first one.

## The three tiers of documentation

| Tier | Where | Checked in | What it holds |
|---|---|---|---|
| General | `docs/`, `AGENTS.md`, `README.md`, `SKILLS.md` | yes | How jason works for any California common interest development: the models, rules, statutes, and commands. The general docs say "the specification" or "the association". |
| Instance | the profile's `docs/` folder (`mystique/docs/`) | yes | This association's setup: the Drive folder map, vendors and portals, phases and annexations, meeting habits, and why each rule row exists. |
| Private | the profile's `notes/` folder (`mystique/notes/`) | no | Owners, parties, matters, figures, and review findings. |

A general page that has instance detail ends with one pointer line, for example "This association: `mystique/docs/meetings.md`."

`tests/test_profile.py` keeps the boundary. `jason.community.boundary` collects the profile's own facts:

- its names;
- its streets;
- its vendors, developers, and banks;
- its case numbers;
- its group addresses and domain;
- its Drive ids;
- its PayHOA org id.

It then lists the general documents that name any of them. Adding a fact to the profile extends the check. A code span that points into the profile (`mystique/meetings.py`) is allowed. The association's name in prose is not.

**Themes are profile data.** The association's brand for the console and its public owner page is one `Theme` row (`jason.community.base.Theme`) returned by `Community.theme()`: the accent and the text that sits on it, a second accent, the brand font with its weight, case, and tracking, the hero surface, dark-scheme overrides by the same keys, the surface layer the public page opts into with `data-reach="full"`, and a font stylesheet URL. The console reads it from `GET /api/theme` (`jason.web.extra.theme`) and scopes it to `[data-community="<slug>"]` (`ui/src/lib/theme.ts`); jason's data views take the brand layer only. No color, font, or wordmark appears in `src/jason/`, `ui/src/`, or these docs; a profile without a theme answers `found: false` and the console keeps its neutral look. The public page's facts come the same way, from `GET /api/community-profile` (`jason.web.extra.community_profile`), which reads `Community` methods alone and shows nothing for a method left at its empty default. This association: `mystique/docs/theme.md`.

`tests/fixtures/docs_boundary.json` is a ratchet. It records what each document names today. A new term fails the test, and so does a cleared term that the baseline still lists. Run `python -m jason.community.boundary` to see where things stand, and `--update` to rewrite the baseline after a cleanup.

## Making jason reusable: the phases

The coupling was surveyed on October 2, 2026. jason hardcodes no Drive ids or PayHOA ids, and most models and tasks already take a `community` argument. What remains is listed below in the order to do it.

1. **Choosing a profile (done).**
   - Done:
     - `jason.community.profile`;
     - lazy settings;
     - `kind_rules()` and `classify_document()` on the base class;
     - `sync_rules` on the base class;
     - the records inventory reading the library through the interface;
     - the boundary test.
   - Still to do: about 170 call sites still say `mystique()`. Renaming them to `community()` is mechanical and can wait for a quiet tree.
2. **Module constants become interface.** The `templates` reads are done (`identity()`, `letterhead()`, `drive_home()`); the `forms` reads remain.
   - `spec_module("forms")` (owner information, form templates, test memberships) and `spec_module("templates")` (letterhead, folders, city line) are read around the `Community` class, at 28 sites.
   - Each becomes a method or a typed record on `Community`, with an empty default.
3. **Instance enums leave the general package.**
   - `jason.community.symbols` defines `Street`, `Building`, `PublicDrive`, `KnownFile`, `PayhoaFolder`, `SitePage`, `MembershipTab`, `DocumentRule`, and two `CostCenter` enums whose members are one association's.
   - They move into the profile.
   - jason keeps the record types and takes the members from the profile, for example `community.streets()` and `community.buildings()`.
   - About 12 places name a member directly. They become rule rows.
   - `Building(int(x))` currently caps an association at eight buildings.
4. **Literals become profile data.**
   - About 65 places in about 30 files hold literals:
     - the association's name in regexes and default arguments (`index_cache`, `sources`, `models/*`);
     - the street pattern in `incidents`, `scans`, and `models/invoices`;
     - the county map book and page;
     - the city and ZIP line;
     - the maintenance request groups in `request_sheet`;
     - the prose in `board_packet`.
   - Each one reads `community.name`, `community.corporate_name`, `community.unit_city_state_zip()`, or a new profile field.
5. **Data per profile.**
   - Every store derives `data/` from `Settings.payhoa_catalog.parent`, so all profiles share one folder.
   - The fix is a `data_dir` setting: `JASON_DATA_DIR`, else `data/` for the first profile and `data/<profile>/` for any other.
   - It also needs a check that a store's recorded org id matches the profile's.
6. **Regions.**
   - These sources are Sacramento's:
     - the recorder index, copy orders, the assessor, and the secured roll;
     - county-taxes.net;
     - the City's Accela permits;
     - SMUD and the City's utility bills.
   - They move behind a region adapter that the profile names (`region = "ca/sacramento"`).
   - Another county is a new adapter.
   - The `smud` and `idoxs` packages become optional extras.
7. **Vendor formats as plug-ins.**
   - About 15 readers are written for specific vendors' layouts: a bank's statements, a manager's reports, a roof inspector, a pest portal, a law firm's letters, and a reserve preparer's studies.
   - The format readers stay in jason as a library.
   - Which vendor the association uses, and the vendors' names, is profile data.
8. **The profile becomes its own package.**
   - With phases 2-7 done, `mystique/` holds everything specific to the association: its spec, `docs/`, and `notes/`.
   - It can move to its own repository and be installed with the entry point above.

A fictional second profile to prove the phases is planned in [sample-profile-plan.md](sample-profile-plan.md). Base templates rendered per profile are planned in [base-templates.md](base-templates.md).
