# Backflow testing: this association's assemblies

The law and the cycle are in [docs/cross-connection-control.md](../../docs/cross-connection-control.md). This page is what is particular to the association. The deadline is the obligation row `Backflow assembly test` (`mystique/obligations.py`), the system is `backflow` in `mystique/life_safety.py`, and the tester is LeDoux Backflow Testing Services (`mystique/senders.py`). Read October 4, 2026 from the association's own letters, test reports, and email.

## The six assemblies

The City's water account is 1456067188 (the test reports call it the Customer ID; the City's June 2026 repair notice calls it the Account #). Its bills carry two metered services, and the reports' meter numbers match them: the 4-inch domestic meter 70226482 and the 2-inch irrigation meter 34049156. The fire-line assemblies have no meter. The County's list (facility FA0044473, notice reference OW0045313) and the City's reports name the same six.

| Service | Type and size | Serial | County assembly ID | City backflow ID | Where |
|---|---|---|---|---|---|
| Irrigation | RP, 2 in, Wilkins 975XL | 2554857 | BD0023117 | 143926 | planter, east property line |
| Domestic | RP, 4 in, Wilkins 375AXL | CC0135 | BD0023113 | 148995 | planter, east property line |
| Fire | DC, 8 in, Ames 2000SS | 152583 | BD0023114 | 142280 | north property line, on Macon Dr |
| Fire | DC, 6 in, Ames 2000SS | 153188 | BD0028085 | 142303 | near building 3 |
| Fire | DC, 8 in, Ames 2000SS | 153493 | BD0023115 | 142315 | south property line, on Picasso Cir |
| Fire | DC, 6 in, Ames 2000SS | 152933 | BD0023116 | 142294 | southeast corner |

The records count them differently. The reserve study lists fire backflow preventers as two on the sprinklers and three on hydrants, five in all, beside separate domestic and irrigation rows; the County and City lists have four on the fire service. A person reconciles the reserve study against the lists. The fire protection notes' "five on the fire service" is the same discrepancy.

## What happened, by year

| Year | The letter | The test | What followed |
|---|---|---|---|
| 2024 | County EMD reminder dated May 15 (scanned May 24), due June 1 | June 20 to 22; the assembly near building 3 failed June 20 and passed July 8 after repair | A County notice of July 2 on the failed assembly (15 days to correct) |
| 2025 | County EMD reminder dated May 15 (scanned May 17), due June 1; LeDoux's own letter the same day | June 25 | A County Notice of Non-Compliance dated June 30, "we have not received a test report", scanned September 22 |
| 2026 | City notices dated April 16, one an assembly (scanned May 1), due May 31 | May 1 for five assemblies; the domestic RP failed May 5 ("RV FAILED TO OPEN") | The City's repair notice dated June 2 (15 days), postmarked June 11, scanned July 3; the repair estimate June 8; the retest and repair June 18 |

In 2026 the notices came from the City, with its own portal, where in 2024 and 2025 they came from the County; why is not on file. The City's 2026 notices each cite the same three authorities, and the County's cite County Code 6.30.110 (see the general page).

Three things in the 2026 record that a person reads against the notices:

- **The days.** The City's April notice gives 15 days "of the initial test" to repair a failed assembly. The domestic RP failed May 5 and its repair report is June 18, 44 days later. The repair notice is dated June 2 (15 days is June 17) and was postmarked June 11. No shutoff followed. Whether the days ran from the test, the notice's date, or its receipt is for the City's office.
- **The June 18 report.** Its readings pass (the relief valve opened at 2.8 PSID, the first check closed at 7.2) and it carries a tag number and a due date of May 31, 2027, but its "Final Test" block and "Final Tag #" are blank. Ask the tester whether the City's portal holds a passing final report.
- **The 2025 notice.** The County had no report on June 30 for a test done June 25. Whether the report was late, lost, or filed after the notice is not on file: ask the tester for the portal's receipt each year.

## Forwarding the letter

The tester needs the reminder to schedule: it lists each assembly with its ID and due date. The association did forward it each year (the 2024 notice on May 20, 2024; the County's notice and LeDoux's letter on May 16, 2025; the City's April notice on April 22, 2026). The 2026 forward carried one City letter, for the irrigation assembly, when the City mails one for each. So forward every page of every letter, and ask for the portal's receipt and each tag number once the tester files. jason proposes this as a step of the board's inspections assignment (`mystique/schedule.py`); the board adopts it.

## Not Mystique's

Two City notices dated July 17, 2026, due August 31, 2026, for assemblies on other streets, were in this association's mail. They name another association at the same management address (see `mystique/notes/backflow-program-findings.md`). They are not this association's assemblies, so they are not counted here: return them to the manager.

## Sources

The County letters are mail ids 107528, 115672, and 116508 and the failed-test notice 109891; the City's are 121438 (April 2026), 122412 (June 2026), and 123311 and 123312 (not ours). The test reports of May 1 and June 18, 2026 and June 25, 2025 are in Drive under `Reports/Fire Protection/Backflow`.
