# Vendor portals: this association

The general page is `docs/vendor-portals.md`. The portal rows are `mystique/vendors.py`.

## Pest control: ProActive Pest Control (key `proactive`)

ProActive (Pro Active North, Roseville) runs on FieldRoutes' customer portal, `proactive.fieldportals.com` (`company=proactive`). The association's account there is a commercial master account with a service plan. The client was captured from `proactive.fieldportals.com.har`; that HAR holds the portal password in plain text, so it stays out of git and is never shared.

- Stores: `data/vendors/proactive/<customer id>/`, and the verification at `data/vendors/proactive/verification.json`.
- Invoices: the ProActive row in `jason.community.invoice_formats` (FieldRoutes' printed invoice).
- Commands: `jason vendors --sync`, `jason vendors --verify`, `jason pests --fetch`; the MCP tools `vendor_portal` and `pest_program` default to this key.
- Findings: `mystique/notes/vendor-portals.md`.

## Fire alarm: Signal Service (key `signalservice`)

Signal Service's billing portal is a Django site (`portal.signalserviceinc.com`, `jason.signalservice`): invoices, work orders, `jason vendors --sync --key signalservice`. Its inspection reports are a separate public portal on Firenspec (`VendorPortal.reports`): the QR code on each report names the association's portal, and `jason vendors --reports --key signalservice` keeps every report it lists under `data/vendors/signalservice/reports/`. On October 3, 2026 the portal listed 15 reports (Buildings 3 and 8, from July 2022 to March 2026, and a 2023 Record of Completion for Building 8); the library held the two of September 19, 2025. The portal was not password protected. File the rest with `jason ingest data/vendors/signalservice/reports --apply`.
