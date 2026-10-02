# Vendor portals: this association

The general page is `docs/vendor-portals.md`. The portal rows are `mystique/vendors.py`.

## Pest control: ProActive Pest Control (key `proactive`)

ProActive (Pro Active North, Roseville) runs on FieldRoutes' customer portal, `proactive.fieldportals.com` (`company=proactive`). The association's account there is a commercial master account with a service plan. The client was captured from `proactive.fieldportals.com.har`; that HAR holds the portal password in plain text, so it stays out of git and is never shared.

- Stores: `data/vendors/proactive/<customer id>/`, and the verification at `data/vendors/proactive/verification.json`.
- Invoices: the ProActive row in `jason.community.invoice_formats` (FieldRoutes' printed invoice).
- Commands: `jason vendors --sync`, `jason vendors --verify`, `jason pests --fetch`; the MCP tools `vendor_portal` and `pest_program` default to this key.
- Findings: `mystique/notes/vendor-portals.md`.
