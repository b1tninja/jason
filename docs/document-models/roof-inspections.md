# Roof inspections

The roof record: what governs the roofs, and the reader for the roof inspection reports. Set beside the repair invoices, the minutes, and the ledger, the reports show where the roofs leak and what the inspections left unpriced. That is a lead for the board, not a determination.

## What governs the roofs

- **The declaration.** Its maintenance article says who maintains, repairs, and replaces the roof coverings, roof structures, gutters, and downspouts; how often the common area is inspected for leaks and moisture; and who bears water damage inside a unit from a roof leak.
- **No statute** sets a roof inspection cycle. The reserve study (Civil Code 5550) carries each roof's remaining life. The roofing contractor needs a CSLB license, and its number belongs on every bid and contract (B&P 7030.5).
- **The master policy** usually does not pay for rain damage inside a unit unless a covered cause first damaged the roof, and its deductible applies.

## The reader

`jason.community.models.inspections_roof.RoofInspectionModel` (kind `inspection_report`, model `roofchecks-roof-inspection`) reads RoofChecks' estimate. It sorts ahead of the general inspection reader.

- **Layouts.** It reads two:
  - 2023 (NAHS): a roof info block and a subtotal for each building;
  - 2026 (Good Life): one roof info block, findings and repairs for each building, and one subtotal.
- **Change orders.** A change order in the same form ("Building 3: Replace ...") reads as a report with `change_order` set.
- **Fields.**
  - Report-level: firm, license, job ID, date, inspector, whether the inspection was by drone, and the total in cents.
  - For each building: covering, layers, stated age, stated life remaining, and pitch; the findings and repairs; the subtotal; tiles replaced and reset, joints sealed, and valleys cleaned; and flags for no inspection under the solar panels, debris or birds, and a referral to a metal roof specialist.
- **Checks.**
  - The stated age is set beside the building's public report (`Mystique.public_reports`).
  - The stated life remaining is set beside the reserve study's tile component for the building's phase: phases 1–2 are `PHASE_1_AND_2`, and phases 3–8 are `PHASE_3_TO_8`.
  - It flags a report with no license number, the drone's limits, roof not inspected under the solar panels, debris at the flashings, and metal sections referred out and never priced.
- **Kind rules.** `mystique/documents.py` names "Roof Inspection - * Report*" and "*Roof Inspection*Repairs*" as inspection reports. "NAHS Roof Inspection Report - 2023.pdf" already matched `*inspection report*`.
- **OCR.** The 2023 PDFs' text layer is scrambled font codes, so they need OCR (`PyMuPdfTesseract`).
- **Tests.** `tests/test_models_roof.py`.

## What the reports show

An inspector's stated age and life remaining are the inspector's, not the reserve study's; the checks set them side by side. A drone inspection cannot see under solar panels, and a section referred to a specialist stays unpriced until someone prices it. A lender may ask for a roof certification, which is a separate document from the report.

Mystique's findings are in the private notes (mystique/notes/document-models/roof-inspections.md).
