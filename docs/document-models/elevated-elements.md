# Exterior elevated elements (SB 326) report

Model: `sb326-report` in `jason.community.models.elevated_elements`, for `elevated_element_inspection`. It is also registered for `inspection_report`, where it returns nothing unless the text is a balcony report.

## The law (CIV 5551)

- **Who inspects, and when.** At least every nine years, a licensed structural or civil engineer or architect visually inspects a random, statistically significant sample of the exterior elevated elements (5551(b)). The first inspection was due by January 1, 2025 (5551(i)).
- **The random list.** Before the first inspection, the inspector generates a random list of element locations and gives it to the association. Later inspections continue down that list (5551(c), (h)).
- **The report's content.** The report covers the components, their condition and any immediate threat, their expected performance and remaining life, and recommendations (5551(e)(1)-(4)).
- **The first page.** It gives the inspection date, the units in the project, the units with elevated elements, the elevated elements in all and inspected, those posing an immediate threat and the units affected, and a certification of a statistically significant sample (5551(e)(5)).
- **Signing and filing.** The report is stamped or signed by the inspector, presented to the board, and incorporated into the reserve study (5551(f)). An immediate threat goes to code enforcement within 15 days, and the association bars access (5551(g)).
- **Retention.** Reports are kept for two inspection cycles (5551(i)).

## Whether the inspection applies

The obligation's scope is a condition over three facts about the property (`applicability.ELEVATED_ELEMENTS_INSPECTION`), each from the section's own words. A test checks the words against the statute on disk.

| Fact | The words | Closed set or number |
| --- | --- | --- |
| the kind of development | "the board of an association of a condominium project" (5551(b)(1)) | `CommonInterest`: the condition holds for `condominium` |
| the elements | "exterior elevated elements for which the association has maintenance or repair responsibility" (5551(b)(1)), as 5551(a)(2) and (3) define them | `ElevatedElements`: `association_responsible`, `none` |
| the buildings | "This section shall only apply to buildings containing three or more attached multifamily dwelling units" (5551(l)) | `attached_units`, the most in one building: at least 3 |

- **Asked of the association, not of a system.** The row tests no system fact, so `life_safety.applicable` asks it once of the association. The section puts the duty on the board of the project, for a sample across it and one report. A system record for the balconies would make an association that has not listed them read as "reaches no listed system" where it should be a question.
- **Three answers.** `jason applies --all` shows the row under the association: applies, does not apply with the fact that decided it, or undetermined.
- **A missing fact is a question.** A profile states the facts in `Community.applicability_facts()`. Where it does not, each is a question under `applies:association` (`jason applies --questions`; [intake.md](../intake.md#what-asks)). The elements fact is entered with the record that states it, such as the declaration's maintenance section.
- **Not inferred.** A report on file, or a reserve component for balconies, is evidence for the person who answers. jason does not read the fact from it.
- **What the condition leaves out.** Two provisions change when, not whether, and stay as prose:
  - the first inspection by January 1, 2025 and every nine years after (5551(i));
  - a building whose permit application was submitted on or after January 1, 2020 is inspected within six years of its certificate of occupancy (5551(k)).
- **Per building.** Which buildings the section reaches is the inspector's list (5551(c)). An association with buildings on both sides of the three-unit line would need a record per building; that is not built.

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
