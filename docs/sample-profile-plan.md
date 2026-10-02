# Plan: a fictional sample profile

Status: **not started**. This is a brief for an agent to pick up later. The goal is a second, made-up association that jason can load as a profile ([profiles.md](profiles.md)). It lets the tests, the demos, and the reusability phases run without one real association's facts.

## What exists (researched October 2, 2026)

No public, fake California common interest development dataset was found, meaning one with governing documents, a ledger, deeds, minutes, and mail together. What does exist:

| Kind | Examples | Use to us |
|---|---|---|
| Commercial HOA registries | [Warren Group](https://datarade.ai/data-products/us-national-homeowner-association-data-49m-hoa-records-h-the-warren-group), [ATTOM](https://www.attomdata.com/data/property-data/hoa/), [Common Elements](https://commonelements.com/developers) | Only association-level rows (name, county, standing). Real associations, so not for fixtures. They show which fields a registry carries. |
| Published sample documents | a [sample condominium reserve study](https://www.gabvalue.com/pdf/2015/2015%20Condominium%20Reserve%20Study%20Sample.pdf), a [sample audit report](https://hoacpa.com/wp-content/uploads/2018/09/sample-audit-report-jeopardy-program.pdf), a [sample pool-of-funds study](https://jrfrazer.com/wp-content/uploads/2024/04/Sample-HOA-Pool-of-Funds.pdf) | Layout references for the readers. They are copyrighted, so read their structure and do not copy them into the repo. |
| Open-source HOA and property apps with demo seeds | [SimpleHOA-Legacy](https://github.com/SimpleHOA-Legacy/SimpleHOALegacy) (`seeder.js`), [hausverwaltung](https://github.com/manueljpconde/hausverwaltung) (`db:seed`), [Tendenci](https://github.com/tendenci/tendenci) | Show what members, dues, and work tickets look like. Their seeds are thin and not California-specific. Check each license before reusing anything. |
| California public forms and law | the Davis-Stirling Act (lawlibrary), the Secretary of State's Statement by Common Interest Development (SI-CID), DRE public report formats, the Civil Code 5300 annual budget report and 5310 policy statement contents | The statutes define what a complete record set is, so a fictional association can be complete by construction. |

Conclusion: generate the fictional profile ourselves. jason already does this in a small way: `tests/fixtures/spec` holds made-up private facts.

## The fictional association

- **The profile.** Name `example`, at `profiles/example/`. The association is "Example Commons Owners Association", 24 units in 3 buildings, with two phases and one annexation. That shape exercises the same cases the first profile does, at about a tenth the size.
- **Everything is plainly fake:**
  - email domains are `example.org` (reserved, RFC 2606);
  - phone numbers are 555-01xx;
  - parcel numbers use a prefix no county uses;
  - Drive ids look like `example-drive-...`;
  - PayHOA ids are below 1000;
  - people get generated names that are not checked against anyone.
- **Region.** A fake `region = "example"` adapter with a small recorder index, tax roll, and permit list on disk. This is phase 6 in [profiles.md](profiles.md); until that phase lands, the profile has no county sources and their tools say so.

## Work, in order (each step is one reviewable change)

1. **A profile that loads.** A `Community` subclass with buildings, units, streets, library folders, kind rules, sync rules, and transaction rules. Done when `JASON_PROFILE=example jason --help` and `pytest tests/test_profile.py` pass with it.
2. **Generated documents.** A script (`scripts/make_example.py`, seeded, deterministic) writes:
   - the declaration and bylaws as short PDFs with real section structure and fictional text;
   - two years of minutes and agendas;
   - a budget and a reserve study in the layout the reserve reader expects;
   - monthly treasurer's reports in a board version and a member version;
   - invoices from three fictional vendors;
   - a handful of scanned-looking letters.
3. **A ledger and a catalog.** A `data/example/` set: `payhoa.db` rows (units, owners, charges, payments, two delinquencies, one lien), mail items, and email headers. It needs phase 5 (data per profile) first, or a `JASON_DATA_DIR` for the demo.
4. **Known answers.** Each generated record notes what jason should conclude: a missing 5200 record, a late minutes posting, a reserve borrowing without its resolution, an invoice paid twice. These become tests that run the real tasks against the example profile. That is the measure of reusability.
5. **The boundary both ways.** The docs boundary test runs once per profile, so the general docs name neither association.

## Guardrails

- **Don't get carried away.** Stop after step 1 and review before generating documents.
- **Nothing real goes into the example profile.** It gets no first-profile facts, no real people, no real vendors, and no copied published document text.
- **Keep it small.** The example exists to exercise code paths, not to be realistic in volume. Prefer 24 units over 240.
- **Generated files are reproducible from the script.** Check in the script and small fixtures, not large PDFs.
