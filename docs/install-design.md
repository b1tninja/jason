# Installing jason: a first-run guide that checks the install and fetches its assets

Status: proposal, scoped to **one PC in a development environment serving one community**, shaped so it can grow into a
platform that serves many.

**Out of scope for now: secrets and password management.** Keeper, the Google client, and the vendor logins keep working exactly as
[setup.md](setup.md) describes. The guide *reports* whether each is in place and points at setup.md; it does not collect, store,
move, or rotate a secret. A better answer (a service account, a per-community vault, a hosted secret store) is a later phase that
plugs into the requirement rows below without changing them.

Today a new install follows setup.md by hand, and [onboarding.md](onboarding.md) then brings an association's facts in. Nothing
checks the machine in between or fetches the downloaded assets. This page is that layer.

## What the guide does, now

1. **Checks** the machine and the install, read-only, and prints one page: working, degraded and why, missing and the fix.
2. **Fetches assets** the active profile needs (the paint catalog first), records each in a manifest, and keeps them fresh.
3. **Points** at the existing commands for the rest (`jason login`, `jason sign-in`, `jason local-ai`, `jason onboard --new`).

## One registry of requirements

Everything the guide knows is a `Requirement` row in code, so the check, the fetch, and later the console read one list:

- `key`, a title, and *why* (the feature that needs it, in a sentence)
- `kind`: **service** (Python extras, Ollama and the GPU, Tesseract, Node), **asset** (fetched data), or **credential** (reported only)
- `scope`: **installation** (the same for every community) or **community** (one profile's)
- `check`: read-only; returns present, partial, missing, or stale, with evidence, never a secret's value
- `provision`: for a service, the one command or installer (jason never runs one that needs administrator rights); for an asset,
  a fetch function run with `--yes`; for a credential, a pointer to setup.md
- `needs` and `optional`: what must come first, and what stops working without it

Requirements are **derived from the active profile**, so a community is asked only for what it uses: a paint schedule needs the color
catalog; the profile's county needs that county's index cache. The derivation reads existing `Community` methods
(`paint_schedules()`, and so on), so nothing about one association is written into the registry.

## Assets and their manifest

One row per asset: key, scope, source URL, fetched date, bytes, SHA-256, freshness rule, licence note. Kept in
`data/assets/manifest.json` for installation-wide assets and in the profile's data folder for community ones.

| Asset | Scope | Source | Freshness |
|---|---|---|---|
| Paint catalog (Sherwin-Williams colors) | installation | one open API call, about 1.5 MB | a week |
| Statute text | installation | the lawlibrary checkout (`jason export-authorities`) | the legislative calendar |
| OCR language data | installation | Tesseract's data | none |
| Local model weights | installation | `ollama pull` | none |
| County index cache | by county (shared by communities in it) | asspy | its own sampling |
| A community's documents, stores, and notes | community | the community's own sources | n/a |

Rules:

- **Fetched on the install, not committed.** A third party's data stays out of the repository unless its terms allow it. The paint
  catalog is served without a login, but its terms are unclear, so each install fetches its own copy.
- **Freshness is per asset.** A stale asset is used with a warning, not refused, unless the feature needs it exact.
- **Offline is a mode.** A present asset is used with the network off; a missing one makes its feature say what to fetch.
- **A changed refetch is shown.** For the catalog: colors added, renamed, or discontinued. A drift in an input is a finding for the
  board, not a silent overwrite.

## Designing toward many communities

Nothing here is built for more than one, but each choice avoids a later rewrite:

- **Two scopes from the start.** Every requirement and asset says whether it is installation-wide or one community's. The paint
  catalog, statutes, OCR data, and models are fetched once and shared; a profile's stores, notes, and documents are not. The data
  layout already points this way (`<data root>/<profile>/` per community, one shared `spec/`, sign-in clients per community and per
  installation).
- **Everything keyed by profile.** The check and the manifest take a profile name; nothing reads "the" community. With one profile
  installed that is the default, and with several the check runs once per profile and the shared parts once.
- **Shared assets, per-community choices.** A community that uses a different paint maker, or none, simply derives no catalog
  requirement. The catalog is not a property of the install.
- **Tenant boundary on the data root.** A community's data folder is the unit that could move to its own machine or storage later.
  An asset a community depends on is recorded in that community's manifest even when the file itself is shared.
- **Credentials stay behind one door.** A requirement of kind credential only reports state. When the credentials design is done,
  per-community secrets slot in behind that check, and no other row changes.
- **No cross-tenant reads.** A task for one community never opens another's folder; the shared assets hold no community's facts.

## Surfaces

- **CLI** first: `jason setup --check` (read-only report), `jason setup --assets` (the manifest with ages), `--refresh KEY --yes`,
  `--only KEY`, `--profile NAME`. Non-interactive runs fail fast and never open a browser.
- **Console later**: a view in `jason-web` over the same registry (the report, a Fetch button per stale asset). The browser may fetch
  an open catalog itself for entry-time autocomplete, with jason's copy as the fallback; the server re-reads any code against its own
  asset. Coordinate with whoever is building the console.

## Safety rules

- Check is read-only. A fetch needs `--yes` and lists the URL first.
- Nothing is sent to a third party except the fetch the asset names.
- Nothing is installed with administrator rights; the guide names the installer and re-checks afterward.
- A failed step leaves the earlier ones in place and the report names the next.

## Phases

1. **Registry and `jason setup --check`** for what setup.md describes (extras, Ollama and commit, Tesseract, Keeper and Google
   *reported*, the data folders), with the two scopes in the row from day one.
2. **Assets and the manifest**, starting with the paint catalog (a reader and cache exist) and statute text.
3. **Profile-derived requirements**, as `Community` hooks grow.
4. **Console view**, once the registry is stable.
5. **Later, separately**: credentials and a second community (per-community secrets, a shared-asset store, service accounts).

## Open decisions (for the person)

- Should the first release also report on the sibling packages (`payhoa`, `smud`, `asspy`) by version, or only that they import?
- Is statute text an asset the guide fetches, or does the lawlibrary checkout stay a manual prerequisite for now?
- Where do shared assets live on one PC: under the data root's `assets/`, or beside the checkout?
