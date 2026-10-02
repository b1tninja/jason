# Utility bills

A utility bill is not a vendor invoice. SMUD and the City of Sacramento bill on published tariffs, jason downloads the bills itself (the `smud` and `i-doxs` packages), and each bill states its own period, meters, usage, rates, and amount due. So jason reads a bill into structure and checks it: the charges must add to the total, and SMUD's charges must follow from the usage at the tariff's prices. The document kind is `DocumentKind.UTILITY_BILL` (financial, an enhanced association record), kept apart from `INVOICE`.

## The model

`jason.community.utility` holds the parts every utility shares:

- `Service`: electric, domestic water, irrigation water, fire service, storm drainage, street sweeping, sewer, garbage.
- `Charge`: one line, with its service, kind (usage, fixed, demand, tax, surcharge, adjustment), quantity, unit, rate, period, and amount in cents.
- `MeterRead`: one register of one meter, with the reads, multiplier, size, and register ("kW Maximum").
- `UtilityBill`: the document. It holds the provider, account, bill date, period, charges, reads, service address, parcel, source PDF, and the amount due. The amount due is the current charges plus any past balance, less any credit.
- `Tariff` and `Price`: a rate schedule's prices by effective date, marked provisional where the utility says "subject to change".
- `UtilityProvider`: what a utility implements. `Smud` is in `smud_utility.py`, and `SacramentoUtilities` is in `city_utility.py`.

The bill's own text is the record. A file name can be wrong: see the misfiled check below.

## Sources and the store

`jason utilities` parses every PDF under `Settings.smud_bills_dir` and `Settings.idoxs_bills_dir` into `data/utilities.db`. The sync is incremental, keyed by path, size, and modification time. `--full` re-reads everything. The PDFs attached to PayHOA transactions join the same store when the payment audit reads them. A copy of a bill the portal also delivered is kept once, and the portal file wins.

## The specification

`mystique/utilities.py` names only what a bill cannot say:

- `UTILITY_ACCOUNTS`: each account's purpose, taken from the board's utility sheet, such as "Building 3 house meter", "Pump room", or "ACA 5".
- `UTILITY_BUDGET_LINES`: the PayHOA expense category each service is budgeted and split under.

Meters, sizes, service addresses, and parcels come from the bills (`service_points`). The brief notes a replaced meter, an account the specification does not name, and an account with no recent bill.

## Tariffs

- **SMUD CITS-0** (C&I Time-of-Day Secondary, 0 to 20 kW), Resolution No. 25-06-15. Prices take effect May 1, 2025, January 1, 2026, and January 1, 2027. The 2028 prices are provisional. A bill that crosses a price change or a season boundary is prorated by days. SMUD itself splits the kWh by the meter's interval data, so an estimate lands within a dollar of the bill.
- **City water**: Exhibit A, the column effective July 1, 2019, which the bills still charge. The City has proposed increases from July 2027 but has not adopted them. A forecast applies one only as a named scenario (`--water-increase 0.1`). Storm drainage and street sweeping grow at the rate their own bills show.

## Abnormal usage

Usage is compared per day, against the same period in earlier years. Without an earlier year, it is compared against the median of the last six bills with a reading. A bill is flagged when its usage per day is well above that baseline:

| Service | Ratio | And at least |
| --- | --- | --- |
| Electric | 1.4 times | 3 kWh a day more |
| Domestic water | 1.35 times | 150 cubic feet a day more |
| Irrigation | 1.5 times | 300 cubic feet a day more |

A bill with no usage on a meter that always has some is flagged as a possible stopped meter or unread register. A large read after such bills is judged over the whole stretch. When the stretch is normal, the flag reads as a catch-up read, not a leak. An anomaly is a reason to look at the meter, not a finding.

## Forecast

The forecast predicts usage and prices it. It is not a sum of past bills or payments. A payment's month shows when the treasurer paid, and a bill's period straddles two months. So a sum of last year's bills carries last year's timing forward: a late payment, a catch-up read, a month a credit zeroed.

1. Each metered service's usage is spread over the days its bills cover. A read after bills with no usage is spread over the whole unread stretch.
2. Each calendar month's usage per day is the median of that month over its last three years with at least 80% coverage.
3. SMUD months are priced with the CITS-0 estimator: each month's own time-of-day mix, its typical maximum kW, the fixed charge, tax, and surcharge.
4. City water is priced at the per-cubic-foot rate in force. The base, fire, storm, and sweeping charges are monthly rates from each active account's latest bill. Prorated pieces of one line, such as "(for 28 days)" and "(for 1 days)", are summed back together. An account with no bill in the last 75 days is treated as closed.

The brief carries a backtest: this year's finished months predicted from the bills before this year, against what those months cost. Each month's cost is the bills' charges prorated by day.

## Attaching bills to PayHOA transactions

Each month the bank feed brings unreviewed SMUD and City of Sacramento charges with no PDF. `jason sync-bills` lists those PayHOA transactions, syncs only the portals that have a pending match, and attaches the bill when the amount and date line up.

```bash
jason sync-bills --dry-run
jason sync-bills
jason sync-bills --source smud
jason sync-bills --skip-sync      # attach from the local cache only
```

The matching rules:
1. **The queue:** unreviewed PayHOA transactions (`reviewed=false`).
2. **The provider,** from the transaction text, not the vendor list:
   - **SMUD:** the transaction rule is "SMUD", "SMUD" is in the description, or the category is Electricity (SMUD);
   - **City of Sacramento:** the rule or description carries the City's utilities text (including the truncated ACH `CITY OF SACRAMEN`), or the category is City of Sacramento Utilities.
3. **Skip** a transaction that already has an attachment.
4. **Match** the exact amount in cents, with the bill date or due date within seven days, in the utility cache.
5. **Unique only:** an ambiguous match or no match is reported and skipped.
6. **Download lazily:** the PDF is downloaded from the portal only when a transaction needs it.

The lower-level commands:

```bash
jason fetch-bills                          # new bills from both portals into the store; nothing goes to PayHOA
jason fetch-bills --source smud --account ACCOUNT
jason sync-smud --account ACCOUNT --full   # SMUD bills, payments, and usage
jason sync-idoxs                           # City bills (Bills.aspx ACCOUNT=ALL, metadata only)
jason upload-smud-bills --dry-run
jason upload-idoxs-bills --dry-run
jason attach-bills                         # attach without a portal sync
jason probe-transactions --interactive     # live probes: server search against the client filter
jason dump-transactions --out data/payhoa_txs.jsonl
```

## The payment audit

`jason utilities --payments --fetch` reads every PayHOA transaction and keeps the SMUD and City payments. It downloads the attachments the portal files do not already cover into `data/payhoa/attachments/`. Then it checks each payment. PayHOA shows a split payment as child rows that share a hidden parent, and the audit treats those rows as one payment.

- **Bills paid.** The bill whose amount due is the payment wins, with the attached bill first. Next comes the set of unpaid bills, one per account, that sums to it (the City's combined web payment). Last come consecutive bills of one account (a late payment of two months).
- **Attachment.** The audit checks for a missing attachment, one that is not that provider's bill, and a bill the payment did not pay.
- **Split.** The payment's categories are compared with the bills' charges by budget line. The audit reports "not split", a wrong single category, or a split that differs. When the payment is an amount due after a credit or balance, only the lines are compared.
- **Paid twice.** This is an unmatched payment with the same amount as a matched one a few days before it. It is confirmed only when the next bill shows a credit that covers it.

The audit writes `data/payhoa/utility-audit.json`. The `utility_payments` MCP tool reads it. Jason changes nothing in PayHOA. The treasurer applies any split or recategorization.

## Misfiled downloads

The brief lists every PDF whose name dates a different bill than the one inside. A portal can deliver an older bill under a new month's name; the true bill for that month is missing until it is downloaded again.

This association's findings are in its private notes (mystique/notes/utility-bills.md).
