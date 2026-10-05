# Where documents are filed, by kind

The Drive filing table (`EMAIL_FILING` in [vendors.py](../vendors.py)) files an email attachment by its **kind** first and its
sender second, so each record sits where its inspection period runs. This page records the rows added on October 4, 2026, who
chose them, and the library paths that match.

## Rows added

| Kind | Drive folder | Why |
|---|---|---|
| `utility_bill` | `Financials/{year}/Invoices/{vendor}` | The Drive already holds the SMUD bills there, filed with the invoices. A bill is paid and read like an invoice. CIV 5210(a)(1) makes the current and two previous fiscal years inspectable, so the fiscal-year folder is the inspection window. |
| `tax_return` | `Financials/Tax Returns` | The preparer's package for a year arrives the next year, so a `{year}` folder would file a 2025 return under 2026. One folder, with the tax year in each file's name. These are CIV 5200(a)(6) records. The Drive's older returns sit in their tax-year folder (`Financials/2022`); they are not moved. |
| `security_report` | `Reports/Security Patrol` | The Drive already holds the patrol's daily reports there. |

## Library paths

An ingest asks which library folder a file goes in. Answered the same way as the Drive, so a path means the same in both:

| Kind | Library folder |
|---|---|
| `utility_bill` | `Financials/{year}/Invoices/SMUD/` |
| `tax_return` | `Financials/Tax Returns/` |
| `security_report` | `Reports/Security Patrol/` |

These are not `LibraryFolder` rows. A `LibraryFolder` is a PayHOA folder with its id, and PayHOA has no folder for these, so
creating one would be a write to PayHOA that no one has asked for. The library keeps the path as the filed file's own folder
(`jason ingest ... --apply`), and the next ingest of another file of the kind finds those files and offers their folder. If the
association later makes PayHOA folders for them, a `LibraryFolder` row with the same path pins them.

## Chosen by

Claude, on Justin Capella's instruction to choose the best names and Drive locations (October 4, 2026). Its answers are recorded in
the intake queue as "Claude, delegated by Justin Capella". A person may rename a folder: change the row here, and move the files.

## Not done

- **A developer-era bill is filed with the association's.** One SMUD bill in the sample (issued September 2021) is addressed to the
  subdivider, not the association, and sits in `Financials/2021/Invoices/SMUD/`. It is the subdivider's record; a person may move
  it to a developer's folder.
- **`resale_disclosure`** has no file in any store searched: the association's own resale certificate is not kept apart from the
  documents it encloses. A title company's request for it is an `escrow_request`.
