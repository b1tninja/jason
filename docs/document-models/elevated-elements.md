# Exterior elevated elements (SB 326) report

Model: `sb326-report` in `jason.community.models.elevated_elements`, for `elevated_element_inspection`. It is also registered for `inspection_report`, where it returns nothing unless the text is a balcony report.

## The law (CIV 5551)

- **Who inspects, and when.** At least every nine years, a licensed structural or civil engineer or architect visually inspects a random, statistically significant sample of the exterior elevated elements (5551(b)). The first inspection was due by January 1, 2025 (5551(i)).
- **The random list.** Before the first inspection, the inspector generates a random list of element locations and gives it to the association. Later inspections continue down that list (5551(c), (h)).
- **The report's content.** The report covers the components, their condition and any immediate threat, their expected performance and remaining life, and recommendations (5551(e)(1)-(4)).
- **The first page.** It gives the inspection date, the units in the project, the units with elevated elements, the elevated elements in all and inspected, those posing an immediate threat and the units affected, and a certification of a statistically significant sample (5551(e)(5)).
- **Signing and filing.** The report is stamped or signed by the inspector, presented to the board, and incorporated into the reserve study (5551(f)). An immediate threat goes to code enforcement within 15 days, and the association bars access (5551(g)).
- **Retention.** Reports are kept for two inspection cycles (5551(i)).

## Record

`ElevatedElementReport` has these fields:

- **Inspector:** `inspector_firm`, `inspector_license`, `signer`, `signer_title`, `signer_license`.
- **Dates and order:** `inspection_date`, `report_date`, `order`.
- **Site:** `site_name`, `site_address`, `property_owner`, `units`, `buildings`, `stories`, `construction`.
- **Elements:** `units_with_elements`, `element_types` (total, non-EEE, EEE, and inspected per type), `elements_total`, `elements_inspected`.
- **Threats:** `immediate_threats`, `units_affected`.
- **Certification:** `certifies_statistical_sample`, `random_list`.
- **Next inspection:** `reinspection`, `next_inspection`, where nine years count from the report date when the report says so.
- **Inspection rows:** `inspected` (building, unit, description, immediate hazard) and `photos`.

## The association's report

A report kept in Drive rather than the PayHOA library is not read by `jason models` until it is added; `jason models --file <copy> --kind elevated_element_inspection` reads a local copy. An inspector's license number in a stamp image is not in the text; confirm it with the licensing board. Keep each report for two inspection cycles, and check that the reserve study incorporates it (5551(f), (i)).

This association's findings are in its private notes (mystique/notes/document-models/elevated-elements.md).
