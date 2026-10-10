"""Mystique's backflow prevention program: the six assemblies at 3000 Macon Dr, the notices with clocks, and the tester.

Read October 4, 2026 from the County's reminder letters (the assembly lists), the City's notices of April 16 and June 2,
2026, and LeDoux's test reports of May 1 and June 18, 2026 (mystique/docs/backflow-program.md has the table and the
sources). The City's account is 1456067188; its bills carry the domestic meter 70226482 and the irrigation meter
34049156, which the reports print, and the fire assemblies have no meter.
"""

from jason.community.backflow import (AssemblyType, BackflowAssembly, BackflowProgram, ProgramNotice, Service, Standing,
                                      TesterList, TesterRef, WatchEntry)

ACCOUNT = "1456067188"
COUNTY = "County assembly id"
CITY = "City backflow id"

ASSEMBLIES: tuple[BackflowAssembly, ...] = (
    BackflowAssembly(Service.IRRIGATION, AssemblyType.RP, 2, "2554857", "planter, east property line",
                     ids=((COUNTY, "BD0023117"), (CITY, "143926")), account=ACCOUNT, meter="34049156",
                     test_due="2027-05-31", last_passed="2026-05-01", last_failed="2015-06-03",
                     history=(("2026-05-01", "passed", "3000 Macon Dr Test Reports 05-01-26.pdf"),)),
    BackflowAssembly(Service.DOMESTIC, AssemblyType.RP, 4, "CC0135", "planter, east property line",
                     ids=((COUNTY, "BD0023113"), (CITY, "148995")), account=ACCOUNT, meter="70226482",
                     test_due="2027-05-31", last_passed="2026-06-18", last_failed="2026-05-05", tag="CS000767",
                     history=(("2026-05-05", "failed", "3000 Macon Dr Test Reports 05-01-26.pdf"),
                              ("2026-06-18", "passed", "3000 Macon Dr REPAIR SN CC0135 Test Report 06-18-26.pdf"))),
    BackflowAssembly(Service.FIRE, AssemblyType.DC, 8, "152583", "north property line, on Macon Dr",
                     ids=((COUNTY, "BD0023114"), (CITY, "142280")), account=ACCOUNT, test_due="2027-05-31",
                     last_passed="2026-05-01", last_failed="2018-05-31",
                     history=(("2026-05-01", "passed", "3000 Macon Dr Test Reports 05-01-26.pdf"),)),
    BackflowAssembly(Service.FIRE, AssemblyType.DC, 6, "153188", "near building 3",
                     ids=((COUNTY, "BD0028085"), (CITY, "142303")), account=ACCOUNT, test_due="2027-05-31",
                     last_passed="2026-05-01", last_failed="2024-06-20",
                     history=(("2026-05-01", "passed", "3000 Macon Dr Test Reports 05-01-26.pdf"),)),
    BackflowAssembly(Service.FIRE, AssemblyType.DC, 8, "153493", "south property line, on Picasso Cir",
                     ids=((COUNTY, "BD0023115"), (CITY, "142315")), account=ACCOUNT, test_due="2027-05-31",
                     last_passed="2026-05-01",
                     history=(("2026-05-01", "passed", "3000 Macon Dr Test Reports 05-01-26.pdf"),)),
    BackflowAssembly(Service.FIRE, AssemblyType.DC, 6, "152933", "southeast corner of the property",
                     ids=((COUNTY, "BD0023116"), (CITY, "142294")), account=ACCOUNT, test_due="2027-05-31",
                     last_passed="2026-05-01", last_failed="2019-06-06",
                     history=(("2026-05-01", "passed", "3000 Macon Dr Test Reports 05-01-26.pdf"),)),
)

NOTICES: tuple[ProgramNotice, ...] = (
    ProgramNotice(
        "City of Sacramento cross-connection program",
        "the City's repair notice of June 2, 2026: \"you are hereby directed to correct the following violation(s) within "
        "15 days of the date of this Notice\"",
        15, (("failed test", "2026-05-05"), ("dated", "2026-06-02"), ("postmarked", "2026-06-11"), ("scanned", "2026-07-03")),
        settled_on="2026-06-18", document="City-of-Sacramento-Department-of-Utilities_Envelope-122412.pdf"),
    ProgramNotice(
        "Sacramento County cross-connection program",
        "the County's Notice of Non-Compliance of June 30, 2025: \"directed to correct one or more of the following "
        "violation(s) within fifteen (15) days of the date of this Notice\"",
        15, (("dated", "2025-06-30"), ("scanned", "2025-09-22")),
        document="Envelope-116508.pdf",
        caveat="No record shows what answered this notice. The test was done on June 25, 2025, before it, and whether the "
               "County had the report is not on file. Which date counts is the program's to say."),
)

PROGRAM = BackflowProgram(
    program="Annual backflow assembly testing",
    supplier="City of Sacramento Department of Utilities",
    assemblies=ASSEMBLIES,
    notices=NOTICES,
    tester=TesterRef("Yianni John Lenakakis", business="LeDoux Backflow Testing Services", certificate="14989"),
    lists=(TesterList("City of Sacramento", "https://www.cityofsacramento.gov/content/dam/portal/dou/utilities/water/documents/Backflow%20Tester%20List%207.2026.pdf"),
           TesterList("Sacramento County", "https://emd.saccounty.gov/content/dam/emd/docs/environmental-protection/cross-connection/Sacramento%20County%20Certified%20Backflow%20Prevention%20Assembly%20Testers.pdf")),
    # The reserve study lists fire backflow preventers as two on the sprinklers and three on hydrants.
    counts=(("the reserve study", "fire", 5, "reserves.py: Fire Sprinkler Water Backflow Preventors x 2; Fire Hydrant Water Backflow Preventors x 3"),),
)

WATCH: tuple[WatchEntry, ...] = (
    WatchEntry("Fire sprinkler annual inspection", obligation="Fire sprinkler annual inspection and test",
               evidence=("AES 2.1 - 03-14-2023 Annual Fire Sprinkler Inspection Report.pdf",),
               changes="an AES 2.1 report dated after March 14, 2023", searched="the library, Drive, and Gmail by name and subject"),
    WatchEntry("Fire alarm inspection (semi-annual)", obligation="Fire alarm inspection and test",
               evidence=("2026-03-11 Mystique Community Association -Bldg. 3 - Fire Alarm System - NFPA 72 (2013).pdf",
                         "2026-03-11 Mystique Community Association -Bldg. 8 - Fire Alarm System - NFPA 72 (2013).pdf"),
               changes="Signal Service's report of a visit after March 11, 2026",
               searched="the library, Drive, Gmail, and Signal Service's public report portal"),
    WatchEntry("Backflow test", obligation="Backflow assembly test",
               evidence=("3000 Macon Dr Test Reports 05-01-26.pdf", "3000 Macon Dr REPAIR SN CC0135 Test Report 06-18-26.pdf"),
               changes="the 2027 test round", searched="the library, Drive, Gmail, and the mail store"),
    WatchEntry("City Fire Prevention correction notice of July 1, 2021", Standing.PARTLY_ANSWERED,
               evidence=("FIRE PREVENTION CORRECTION LIST.pdf",),
               changes="a record that the fire lane was renamed, the units re-addressed, the stencils and signs placed, "
                       "and the missing hydrant caps replaced, or the Fire Department's re-inspection",
               searched="Gmail by subject and Drive by file name; the red-curb striping of 2024 is on file"),
    WatchEntry("The City's annual fire inspection of the property", Standing.UNKNOWN,
               changes="the Fire Prevention office's answer whether the parcels hold an operational permit",
               searched="Gmail by subject and Drive by file name"),
    WatchEntry("Private hydrants and fire mains", Standing.UNKNOWN,
               changes="an annual inspection or flow-test record, or the Fire Department's answer",
               searched="Gmail by subject and Drive by file name"),
    WatchEntry("Portable fire extinguishers", Standing.UNKNOWN,
               changes="a service tag or record, or a note that none are placed in the common areas",
               searched="Gmail by subject and Drive by file name"),
    WatchEntry("False fire alarms", Standing.PARTLY_ANSWERED,
               evidence=("Request for Determination regarding False Fire Alarms.pdf", "False Alarm Appeal Request.pdf"),
               changes="the hearing's decision in writing", searched="Gmail by subject and Drive by file name"),
    WatchEntry("Unit smoke and carbon monoxide alarms", Standing.UNKNOWN,
               changes="counsel's reading of who \"the owner\" is in HSC 13113.7(d)",
               searched="the statute's text; no record of a policy was looked for"),
)
