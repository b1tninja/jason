# Cross-connection control and annual backflow testing

A property that takes water from a public system may have backflow prevention assemblies on its service lines: on the domestic line, the irrigation line, and the fire line. The assemblies protect the public water supply, and the law has the owner keep them tested. The state sets the standard. The water supplier, or the county that runs the program for it, sets the cycle, the tester, the tag, the report, and the deadline. So the requirement is statewide in source and local in practice, and each place has its own letters, portal, and dates.

Read this page with [the profile's page](../mystique/docs/backflow-program.md) for one association's assemblies, account, and history.

## What the law says

Each quotation below is the operative text as read on October 4, 2026. A reading of what it means is marked as one.

**The state.**

- HSC 116407(a) (the Legislature's text, `data/authorities/HSC/HSC-116407.md`): "On or before January 1, 2020, the state board shall adopt standards for backflow protection and cross-connection control." Subdivision (c)(1) makes the older regulations, Title 17 of the California Code of Regulations, sections 7583 to 7605, "inoperative" when the State Water Board's policy handbook takes effect and repeals them 90 days later. **Do not cite Title 17 for the annual test.** The handbook took effect July 1, 2024.
- The State Water Board's Cross-Connection Control Policy Handbook (adopted December 19, 2023, effective July 1, 2024, amended April 21, 2026), section 3.3.3(b): "BPAs must be field tested at least annually." Section 3.3.3(a): "All required field testing must be performed by certified backflow prevention assembly testers." Section 3.3.3(e): "PWS must ensure that BPAs that fail the field test are repaired or replaced within 30 days of notification of the failure." A local program may be stricter. A reading: the handbook puts the duty on the public water system, and the owner's duty comes from the local ordinance and from HSC 116800.
- HSC 116800 (`data/authorities/HSC/HSC-116800-116820.md`): "Water users shall comply with all orders, instructions, regulations, and notices from the local health officer with respect to the installation, testing, and maintenance of backflow prevention devices."
- HSC 116810: a local health officer may certify testers, and "The certification standards shall be consistent with standards adopted by the state board pursuant to Section 116407."
- HSC 116820: a person who "violates any order of the local health officer pursuant to this article, or knowingly files a false statement or report required by the local health officer" is guilty of a misdemeanor punishable by a fine up to $500, and "Each day of a violation ... beyond the time stated for compliance of the order shall be a separate offense."

**City of Sacramento** (the water supplier for properties inside the City).

- Its notices cite "California Health and Safety Code, Section 116407, City of Sacramento Code 13.04.240, and the Cross Connection Control Policy Section 9". The City's repair notice adds that failure to comply "may result in Water Service Termination ... per City Code 13.04.245".
- City Code 13.04.240, as the Council's 2024 ordinance packet reads it: "Any customer shall comply with all provisions of the city's cross-connection control standards. The violation of any provision of those standards constitutes an infraction." The same section lets the director or "a Sacramento County environmental health officer" find a violation and discontinue service under 13.04.245. The packet's adoption date is blank: confirm the codified text at the American Legal site.
- City Code 13.04.245 (service discontinuance): a written notice of violation mailed "not less than 30 days prior to the proposed discontinuance", a request for an extension within 15 days of the mailed notice, a posted final notice 48 hours before shutoff, and (F) the customer's liability for contamination through "an improperly installed, maintained, or repaired backflow assembly device".
- **Not found:** the City's cross-connection control standards, the resolution that 13.04.240 has the Council adopt. The annual test, the City-registered tester, the 15 days to repair, and the report in the City's portal are in the City's notices, so the notices are what we quote for them, and the standards are a question for the City's office.

**Sacramento County.** The County's Environmental Management Department ran the program for the City's customers in 2024 and 2025 and still lists the City as water purveyor on its notices. Its notices cite Sacramento County Code chapter 6.30 (section 6.30.110 for the annual test, as the County's own FAQ words it: "at least annually"). The text of section 6.30.110 itself was not read. Its notices ask for a test by an EMD registered tester, an EMD tag with the tag number on the report, passing reports filed electronically within 20 calendar days, and a failed report filed within 5. HSC 116820's fine is up to $500 a violation, each day a separate offense, and the County's FAQ describes civil penalties up to $1,000 a violation for each day.

## The cycle, as an owner meets it

1. A reminder letter arrives, one a year, and in the City's case one for each assembly.
2. The owner gives the letter to the tester, with the assembly list and IDs on it. The tester needs them to find each assembly in the program's system.
3. A certified, program-registered tester tests each assembly, tags the ones that pass, and files the report in the portal.
4. A failed assembly is repaired or replaced and retested within the days the notice gives (15 in the City's notices), then tagged and reported again.
5. The owner keeps each report and tag number.

## How jason keeps it

- The deadline is an obligation row (`Backflow assembly test`), with the authorities above in its text.
- The statutes are on the authorities shelf (`jason cite "HSC 116407"`, `jason cite "HSC 116800"`).
- The notices, test reports, and tester correspondence are inspection reports and notices in the library, and the test reports are filed by system in Drive.
- `jason backflow` prints the program from the profile: each assembly with the id every source gives it, each notice's clock counted from every date it could run from (none chosen), where two sources disagree on a count, and whether the tester is on the published lists. `jason backflow --fetch-testers` keeps the lists as a dated snapshot under `data/backflow` (names, ids, and businesses; no phone numbers or emails).
- **The approved tester lists.** The County and the City each publish a list of certified testers (the County's carries each tester's ID, updated September 1, 2026; the City's July 2026 list has no ID or date). They answer one question: is the tester we hire certified and listed? Check it before the test each year, on both lists, by the tester who will sign the report. They do not show a tester's registration for the year or an expiry, and a tester can be listed under a person's own name on one list and under the company's on the other, so match on the tester's name and not the business. Keep the lists as a dated snapshot under `data/`, not in git: they hold individuals' phone numbers and emails.

## What to check each year

- The assemblies on the letter against the assemblies on the water account and the last year's reports.
- The tester against both lists.
- Each report's tag number, final result, and the portal's receipt.
- A repair notice's date against its postmark: a notice dated early and mailed late shortens the days to comply.
- A failed assembly's repair against the notice's days.

## Open questions

- The City's cross-connection control standards (text).
- The codified text of City Code 13.04.030, 13.04.240, and 13.04.245, and County Code 6.30.110.
- Which agency's list the City reads for "registered": the City's own, or the County's.
- Whether the fire-line assemblies are tested under the same cycle in every program. The handbook's text says "BPAs" and does not exempt them, and the notices here include them.
