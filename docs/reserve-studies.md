# Reserve studies

A reserve study drives two budget lines: the transfer to reserves, and the reserve analyst's fee. It also carries the Assessment and Reserve Funding Disclosure Summary (Civil Code 5570), which goes to members with the budget. Civil Code 5550 requires a site visit at least every three years and a review every year.

## The model

`jason.community.reserve_study` reads a study PDF into a `ReserveStudy`:

- **Who and when:** preparer, date prepared, fiscal year, level, and unit count. The level is a full study, an update with a site visit, or an update without one.
- **Disclosure:** a `ReserveDisclosure` with the statute's figures. These are the monthly assessment, whether the 30-year plan is sufficient, the amount required and the projected balance at year end, percent funded, the five-year table, and the interest and inflation assumptions.
- **Funding plan:** the beginning balance, the required monthly contribution, and the assumed yearly increase.
- **Projection:** a `ProjectionYear` for each of 30 years, with current cost, contribution, interest, expenditures, ending balance, fully funded balance, and percent funded.
- **Components:** a `StudyComponent` for each line of the component funding summary, with future cost, useful and remaining life, balance distribution, contribution, liability, and fully funded share.
- **Expenditures:** a `PlannedExpenditure` for each year's scheduled replacements, at inflated cost.

Every preparer prints the disclosure in the statute's words, so `read_disclosure` reads it from any study. Each preparer lays out the rest in its own way, so each preparer is a `StudyReader`. `CaliforniaBuilderServices` reads the whole study, and its component sums and yearly schedule reconcile with the study's own totals. `HelsingGroup` reads the 30-year projection in its disclosure notes and its Detailed Component List, whose sum matches the study's grand total to within rounding.

The `HelsingGroup` reader's Estimated Expenditure Schedule prints its columns out of order in the text layer. `read_study` hands every reader the words with their positions (`read_layout`), and `schedule_expenditures` rebuilds the table:

- A line is the words within two points of each other vertically.
- A name sits at the left margin, and its amounts may spill onto the line under it.
- An amount belongs to the year whose header starts nearest its left edge.
- A year is kept only when its items add to the page's Grand Total, within the whole-dollar rounding of its items.

`BrowningReserveGroup` reads Section IV's 30-year funding plan, Section VII's tabular listing (checked against its total current replacement cost to the dollar), and the "Expenditures by Year" schedule (each year checked against its total).

`read_disclosure` also reads the rates and the 30-year answer in any preparer's words. That covers the `HelsingGroup` reader's "2.00% per year was the assumed long-term interest rate" and its "Answer: Yes". Any other preparer yields its disclosure, date, level, and units. A new preparer's tables are a new reader.

## Sources

`jason reserves` reads every library document classified as a reserve study. It also reads the PDFs in `data/reserve-studies/`, where the updates that arrive by email are kept. The same file is read once.

## The brief

The brief shows the latest study's plan for next year: contribution per year, month, and unit, planned expenditures, ending balance, and percent funded. It shows this year's plan beside the budget's "Transfer to Reserves" line and the reserve accounts, which are the reserve account and the reserve CD named in `mystique/banking.py`. It lists the studies over time and when the next site visit and review are due. Its checks cover:

- a unit count that is not the association's;
- a study whose beginning balance copies the previous study's projection to the dollar, instead of the bank balance;
- a study whose beginning balance is far from the previous study's projection;
- a PayHOA account whose name reads as reserve money but that the specification does not name, with its last interest;
- a budget transfer that is not the plan.

The brief also reads each month's treasurer's report from the library, the association's own record of its reserve accounts, including a CD PayHOA cannot see. It checks each study's starting balance against the report for the December before the study's fiscal year.

This association's findings are in its private notes (mystique/notes/reserve-studies.md).

The figures are the preparer's estimates. The board adopts the funding plan and the budget.
