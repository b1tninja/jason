# Vendor-format adapters

jason reads the layouts particular vendors print: a bank's statement, a carrier's declarations page, an inspector's report, a vendor's invoice. A reader of one vendor's layout is an **adapter**. This page lists every adapter jason has, and says how an adapter differs from a general reader that names a counterparty, which is a bug.

## Three kinds of name in general code

| What the code names | Example | Rule |
|---|---|---|
| **An association's counterparty, in a general reader.** A reader for a kind of document (a pre-lien notice, a legal letter, a reserve study) that recognizes one association's law firm, manager, or vendor by a name in its pattern. | "the sender is the attorney when the head names this firm" | A bug. The reader asks the profile's sender directory instead: `sources.sender_in(text, senders, kind)` and `sources.sender_name(text, community, kind)`. A counterparty the directory does not list is a miss. |
| **A vendor, in an adapter for that vendor's layout.** The module reads the layout that vendor prints, and the name is the layout's own signature. It is the same for every association the vendor serves. | a bank's statement reader that looks for the bank's name on the page | Allowed, once the adapter is **declared** (below). Which adapters an association uses is profile data: its senders, its accounts, its policies. |
| **A public source or a platform.** The State, a county, a city, a federal program, a public utility district, and a platform jason runs on. | the Secretary of State, a county recorder, the NFIP, PayHOA, Google, Zoom | Not an association's fact. The boundary takes no terms from them. |

The boundary check (`python -m jason.community.boundary`, `tests/test_profile.py`) takes its terms from the profile: every counterparty in the sender directory (`Community.senders()`) gives its name and the words that recognize it. The check cannot tell the first two rows apart from the code alone. The declaration is what tells them apart.

## Declaring an adapter

An adapter is a row of `ADAPTERS` in `jason.community.adapters`:

```python
Adapter("src/jason/community/models/example_bank.py", "Example Bank", "business checking statements (`example-statement`)",
        signature=("Example Bank, N.A.",))
```

- `module` is the module that reads the layout.
- `vendor` is the vendor's name as the layout prints it.
- `reads` says what the layout is.
- `signature` holds other names the layout prints for the same vendor.

A vendor's invoice layout is declared by its `InvoiceFormat` row in `jason.community.invoice_formats`. `adapters.adapters()` takes those rows too, so an invoice layout needs no second row.

What a declaration does:

- **In code.** `boundary.scan_code` does not count that vendor's name in that module's patterns, word lists, and defaults. It counts the name in every other module, and it counts every other term in the adapter's module.
- **In documents.** `boundary.scan` lets a general document name the vendor inside a code span, as it would point at a module. The name in prose is still found.

What keeps a declaration honest:

- **It is listed here.** A declared adapter that this page does not list fails the check (`boundary.adapter_problems`). `python -m jason.community.adapters` prints the table.
- **It is not stale.** A row whose module is gone, or no longer names the vendor, fails the check. Remove the row.
- **It is narrow.** A row allows one vendor in one module. It does not allow the association's name, a street, or another vendor, and it does not allow the vendor anywhere else.
- **It is a reader of a layout.** Before adding a row, ask what the module reads. If it reads a kind of document from any sender and only wants to know who sent it, it is a general reader: use the sender directory. If it reads the fields of one vendor's printed layout, it is an adapter.

A baseline entry is not a declaration. `tests/fixtures/code_boundary.json` and `tests/fixtures/docs_boundary.json` hold what was there before the check; they only shrink.

## The adapters

| Vendor | Module | Reads |
|---|---|---|
| `JPMorgan Chase` | `src/jason/community/models/financial_bank.py` | business checking and savings statements (`chase-statement`) |
| `Manufacturers Alliance Insurance Company` | `src/jason/community/models/contracts_ins_package.py` | commercial crime policy declarations in a carrier's packet (`crime-declarations`) |
| `Arden Insurance Services` | `src/jason/community/models/contracts_ins_package.py` | the master package policy's declarations in a program's packet (`package-declarations`) |
| `McGowan Program Administrators` | `src/jason/community/models/contracts_ins_package.py` | an umbrella's evidence of insurance and purchasing group membership (`umbrella-evidence`) |
| `Philadelphia Indemnity Insurance Company` | `src/jason/community/models/invoices.py` | NFIP flood renewal notice and new-application invoice (`flood-premium-notice`) |
| `California Deck Inspection` | `src/jason/community/models/elevated_elements.py` | exterior elevated elements inspection report (`sb326-report`) |
| `Good Life Inspections` | `src/jason/community/models/inspections_roof.py` | per-building roof inspection estimate (`roofchecks-roof-inspection`) |
| `North American Home Services` | `src/jason/community/models/contracts_agreements.py` | per-building roof estimate, as a contract and as a proposal (`nahs-roof-estimate`) |
| `Signal Service` | `src/jason/community/models/legal_inspections.py` | NFPA 72 fire alarm inspection report (`signal-service-fire-alarm`) |
| `Pro Elections` | `src/jason/community/models/meetings_elections.py` | an inspector of elections' results page, secret ballot, and pre-ballot notice (`election-results`) |
| `CiraConnect` | `src/jason/community/models/financial_annual.py` | a management platform's fund budget and resident budget package |
| `California Builder Services` | `src/jason/community/reserve_study.py` | reserve analysis report |
| `The Helsing Group` | `src/jason/community/reserve_study.py` | reserve funding update (the disclosure and its 30-year plan) |
| `Browning Reserve Group` | `src/jason/community/reserve_study.py` | reserve study (expenditures by year) |
| `Signal Service` | `src/jason/signalservice/client.py` | the customer portal's invoices and work orders |

Several of these modules are also the general reader for their kind of document: they read the vendor's layout first and the usual labels from any other vendor after it. The declaration covers the vendor's name only.

### Invoice layouts

One `InvoiceFormat` row each, in `src/jason/community/invoice_formats.py`. The layouts themselves are described in [document-models/invoices.md](document-models/invoices.md).

`ProActive Pest Control`, `E&R Landscaping`, `Philadelphia Indemnity Insurance Company`, `Farmers Insurance`, `LaBarre/Oksnee Insurance Agency, LLC`, `Arden Insurance Services`, `CAIS`, `Signal Service Inc`, `Amazon`, `Zoom`, `Adobe`, `PayHOA`, `Twilio`, `Berding & Weil LLP`, `Newman Certified Public Accountant, PC`, `LeDoux Backflow Testing Services`, `California Builder Services`, `GoodLife Construction Inc.`, `Sacramento County Tax Collector`, `Post Scan Mail`, `Aero-Lite Plastics`.

## Public sources and platforms

These are adapters too, but not for an association's counterparty, so they need no row:

- **Sibling packages.** PayHOA (`payhoa`), SMUD (`smud`), the City's bill portal (`idoxs`), and the county assessor and clerk-recorder (`asspy`).
- **Bill sources.** `jason.sources` routes a payment to the utility's bill (`BillSource`).
- **Platforms.** The mail scanning service (`jason.postscanmail`), the pest control portal platform (`jason.fieldportals`), Google (`jason.google`), and Zoom (`jason.zoom`).
- **Government forms.** The NFIP's declarations, a county's secured tax bill, the DRE's public report and budget worksheet, and the ACORD certificate.

## What the check reads

`boundary.code_sites` reads three places where a fact hides in code:

- **A pattern, wherever it is handed over.** To `re`; to a reader helper (`first`, `date_after`, `amount_after` in `jason.community.document_models`); or to a module's own function that passes its parameter on as a pattern (`_after(label, text)`). `boundary.pattern_parameters` finds those functions. A module knows its own functions and the ones it imports by name, so a function of the same name in a module it does not import is not taken for one.
- **A word list.** `"a b c".split()`.
- **A default argument.**

A reader that needs a counterparty takes it from the profile:

| The reader wants | It asks |
|---|---|
| the law firm, manager, vendor, insurer, bank, or title company a text names | `sources.sender_in(text, senders, kind)`, or `sources.first_sender_in` where the text names two of a kind and the order matters |
| a claim paper's carrier | a policy's carrier or program in `Community.insurance()`, then the sender directory |
| a subdivider | `Community.developers()` |
| the other side of a legal matter | `LegalCase.opposing` in `Community.legal_cases()` |
| the association's own name | `Community.name` with `base.name_regex`, and `Community.name_pattern()` for the name word as letters print it |

One the profile does not list is a miss: the reading lacks the value until a person adds the counterparty to the profile.

## What the check does not see

The check does not read a plain string, a message, or a module's own table: a tuple, list, set, or dict of names, words, or records.

**The wide reading** reads the tables, and a class's own. `python -m jason.community.boundary --wide` lists what they name beyond the check, and `scan_code(..., wide=True)` is the same in code. It is a report, not part of the check: the tables below still hold one association's facts, and a baseline never gains an entry.

What the wide reading finds on October 4, 2026:

- **Counterparties, in two modules.** `OPTIONS` in `src/jason/tasks/board_packet.py` (the options and motions for one association's board items) and `GROUPS` in `src/jason/tasks/request_sheet.py` (request ids with their vendors). Each is a table of one association's facts and belongs in the profile. `tests/test_profile.py` holds the set to these two, so a counterparty in any other module's table fails the test.
- **The association's name word, in eight modules.**
  - A stop word in four word sets: `tasks/agenda_items.py`, `tasks/intents.py`, `tasks/request_links.py`, and `tasks/paid_vs_approved.py`.
  - The profile's folder in `tasks/law_sweep.py`.
  - A vendor's name for the property in one `InvoiceFormat` row.
  - Pointers into the profile in `community/lessons.py` and `community/procedures.py`.

Neither reading sees a plain string. Known on the same day:

- `src/jason/community/models/developer_security.py`: the name word in a check's comparison.
- `src/jason/postscanmail/client.py` and `src/jason/zoom/client.py`: the association's name in the user agent each sends.
- `src/jason/tasks/developer_security.py`: a note that names an escrow holder.
- `src/jason/community/models/insurance_claims.py`: two program contractors by name in a pattern. They are in no profile, so they are no term yet.
