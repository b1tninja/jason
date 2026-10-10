/** Made-up data for the inspections components: the handoff's sample data, plus the states around it. Plainly fake
 * (Example Village HOA, Example Alarm Co., 2030 dates). Used by the previews and the tests. */
import type {
  Assembly, DocRefData, DocumentCode, Discrepancy, FilingPlan, NotOurs, NoticeClockData, ReportPortal, TesterCheck, WatchItem,
} from "./inspections";

export const portal: ReportPortal = {
  key: "00000000-0000-0000-0000-00000000000a", vendor: "Example Alarm Co.", customer: "Example Village HOA",
  protected: false, readFrom: ["Bldg. 1 inspection report 9.19.29.pdf"], fetched: "2030-10-04T05:43:00Z",
  counts: { listed: 3, onDisk: 3, inLibrary: 2, notFiled: 1 },
  reports: [
    { urlUuid: "r3", day: "2030-03-11", site: "Example Village HOA, Bldg. 1", template: "Fire Alarm System - NFPA 72 (2013)",
      inspector: "Inspector A", kind: "inspection", held: "not filed", holdings: [{ place: "portal", where: "viewReport?id=r3", identical: true }] },
    { urlUuid: "r2", day: "2029-09-19", site: "Example Village HOA, Bldg. 1", template: "Fire Alarm System - NFPA 72 (2013)",
      inspector: "Inspector B", kind: "inspection", held: "library and drive",
      holdings: [{ place: "library", where: "Email Attachments/…", identical: true }, { place: "drive", where: "My Drive/Reports/Fire Protection/Fire Alarm", identical: true }] },
    { urlUuid: "r1", day: "2027-01-12", site: "Example Village HOA, Bldg. 1", template: "Fire Alarm System - Record of Completion NFPA 72 (2016)",
      inspector: "Inspector C", kind: "record of completion", held: "library only", holdings: [{ place: "library", where: "Email Attachments/…", identical: true }] },
  ],
};

export const portalSynced: ReportPortal = portal;
/** Found from a document's code and not synced yet: no reports, no fetch time. */
export const portalFoundNotSynced: ReportPortal = {
  ...portal, fetched: "", reports: [], counts: { listed: 0, onDisk: 0, inLibrary: 0, notFiled: 0 },
};
export const portalProtected: ReportPortal = { ...portal, protected: true, fetched: "", reports: [], counts: { listed: 0, onDisk: 0, inLibrary: 0, notFiled: 0 } };
export const portalSameCustomer: ReportPortal = { ...portal, key: "00000000-0000-0000-0000-00000000000b", sameCustomerAs: portal.key, reports: [], counts: { listed: 0, onDisk: 0, inLibrary: 0, notFiled: 0 } };
export const portalUnreachable: ReportPortal = { ...portal, fetched: "", reports: [], counts: { listed: 0, onDisk: 0, inLibrary: 0, notFiled: 0 }, note: "The portal did not answer: connection timed out." };
export const portalRefused: ReportPortal = {
  ...portal,
  reports: [{ ...portal.reports[0], refused: "its text does not name the site", held: "not filed" }, ...portal.reports.slice(1)],
};
export const portalCommand = "jason vendors --reports example-alarm --sync";
export const findCommand = "jason vendors --reports example-alarm --find";

export const filingPlan: FilingPlan = {
  vendor: "Example Alarm Co.",
  counts: { file: 8, move: 2, copy: 5, "in drive": 3, "filed before": 1, held: 1 },
  rows: [
    { name: "Fire Alarm 2030-03-11.pdf", action: "file", destination: "My Drive/Reports/Fire Protection/Fire Alarm", kind: "inspection",
      why: "Rule: an inspection report of a fire alarm system goes in the fire alarm folder. The report's template names NFPA 72." },
    { name: "Fire Alarm 2029-09-19.pdf", action: "copy", destination: "My Drive/Reports/Fire Protection/Fire Alarm", kind: "inspection",
      original: "Email Attachments/Fire Alarm 2029-09-19.pdf",
      why: "Rule: the library copy is the same content as the portal's, and Drive has none." },
    { name: "Record of Completion 2027-01-12.pdf", action: "move", destination: "My Drive/Reports/Fire Protection/Records of Completion", kind: "record of completion",
      why: "Rule: a record of completion goes with the installation records. It sits in the Reports folder today." },
    { name: "Fire Alarm 2028-09-20.pdf", action: "in drive", destination: "My Drive/Reports/Fire Protection/Fire Alarm", kind: "inspection", why: "A file with the same content is already at the destination." },
    { name: "Fire Alarm 2027-09-21.pdf", action: "filed before", destination: "My Drive/Reports/Fire Protection/Fire Alarm", kind: "inspection", why: "The run of 2030-09-01 filed it." },
    { name: "Unnamed scan 2030-04-02.pdf", action: "held", destination: "My Drive/Reports/Fire Protection/Fire Alarm", kind: "inspection",
      why: "Its text does not name the site; a person verifies it first." },
  ],
  command: "jason vendors --reports example-alarm --drive --yes",
};
export const filingPlanEmpty: FilingPlan = {
  vendor: "Example Alarm Co.", counts: { file: 0, move: 0, copy: 0, "in drive": 3, "filed before": 1, held: 0 },
  rows: filingPlan.rows.filter((r) => r.action === "in drive" || r.action === "filed before"), command: filingPlan.command,
};

export const codeLink: DocumentCode = { text: "https://reports.example.com/r/abc123", format: "QR Code", page: 1, link: true, host: "reports.example.com", masked: false };
export const codePortal: DocumentCode = {
  text: "https://reports.example.com/portal/00000000-0000-0000-0000-00000000000a", format: "QR Code", page: 2, link: true, host: "reports.example.com", masked: false,
  portal: { platform: "firenspec", host: "reports.example.com", key: portal.key },
};
export const codeMeetingRecorded: DocumentCode = {
  text: "https://zoom.example.com/j/123456789?pwd=***", format: "QR Code", page: 1, link: true, host: "zoom.example.com", masked: true,
  meeting: { platform: "zoom", host: "zoom.example.com", id: "123456789", recorded: true },
};
export const codeMeetingUnrecorded: DocumentCode = {
  ...codeMeetingRecorded, meeting: { platform: "zoom", host: "zoom.example.com", id: "987654321", recorded: false },
};
export const codeMasked: DocumentCode = { text: "https://share.example.com/f/xyz?passcode=***", format: "MicroQRCode", page: 3, link: true, host: "share.example.com", masked: true };
export const codeText: DocumentCode = { text: "UNIT 12 / BLDG 3 / TAG 0042", format: "QR Code", page: 1, link: false, host: "", masked: false };
export const installCommand = 'pip install -e ".[qr]"';

export const deadline: NoticeClockData = {
  program: "Example City cross-connection program", basis: "the City's notice of 2030-06-02: \"within 15 days of the date of this Notice\"", days: 15,
  runsFrom: [
    { label: "failed test", date: "2030-05-05", elapsed: 44, met: false },
    { label: "dated", date: "2030-06-02", elapsed: 16, met: false },
    { label: "postmarked", date: "2030-06-11", elapsed: 7, met: true },
    { label: "scanned", date: "2030-07-03", elapsed: 0, met: null },
  ],
  standing: "unknown", caveat: "Which date counts is the program's to say.",
};
export const deadlineStatute: NoticeClockData = {
  program: "Example Code", basis: "EX Code 123(a)", days: 30, statute: true,
  runsFrom: [{ label: "dated", date: "2030-06-02", elapsed: 16, met: null }],
  standing: "running", caveat: "The statute names the day the clock starts; read it at the source.",
};

const doc = (address: string, name: string): DocRefData => ({ address, name, kind: "pdf", level: "P0", source: "Drive copy" });
export const assemblies: Assembly[] = [
  { service: "fire", type: "DC", sizeIn: 4, serial: "SN-0001", ids: [{ source: "County", id: "A-100" }, { source: "City", id: "B-200" }], location: "Bldg. 1 riser room",
    account: "Account 0001", meter: "Meter 77", lastPassed: "2029-09-19", testDue: "2030-09-19", tag: "Tag 0042",
    history: [{ date: "2029-09-19", result: "passed", document: doc("drive:ExampleDoc01", "Backflow test 2029-09-19.pdf") }] },
  { service: "irrigation", type: "RP", sizeIn: 1.5, serial: "SN-0002", ids: [{ source: "County", id: "A-101" }, { source: "City", id: "B-201" }], location: "Front entrance",
    lastPassed: "2028-09-20", lastFailed: "2030-05-05", testDue: "2030-06-20",
    history: [
      { date: "2030-05-05", result: "failed", document: doc("drive:ExampleDoc02", "Backflow test 2030-05-05.pdf") },
      { date: "2029-09-20", result: "not read", document: doc("drive:ExampleDoc03", "Backflow test 2029-09-20.pdf") },
    ] },
  { service: "domestic", type: "PVB", sizeIn: 1, serial: "SN-0003", ids: [{ source: "City", id: "B-202" }], location: "Pool house", testDue: "2030-10-01", history: [] },
];
export const discrepancy: Discrepancy = {
  subject: "Devices on the fire service",
  sources: [
    { source: "County", says: "four on the fire service" },
    { source: "City", says: "four on the fire service" },
    { source: "Reserve study", says: "five on the fire service", doc: doc("drive:ExampleDoc04", "Reserve study 2029.pdf") },
  ],
  next: "jason backflow --reconcile --service fire",
};
export const discrepancyQuestion: Discrepancy = { ...discrepancy, next: "Which source lists the fifth device, and where is it?" };

export const testerListed: TesterCheck = {
  tester: "Tester A", certificate: "CERT-0000 (as printed)", contactsMasked: true,
  lists: [{ name: "Example County tester list", dated: "2030-09-01", found: "listed", id: "T-1" }, { name: "Example City tester list", dated: "2030-08-15", found: "listed", id: "T-9" }],
};
export const testerOne: TesterCheck = { ...testerListed, lists: [testerListed.lists[0], { name: "Example City tester list", dated: "2030-08-15", found: "not listed" }] };
export const testerOtherBusiness: TesterCheck = { ...testerListed, lists: [{ name: "Example County tester list", dated: "2030-09-01", found: "listed under another business", id: "T-5" }] };
export const testerNotListed: TesterCheck = { ...testerListed, lists: [{ name: "Example County tester list", dated: "2030-09-01", found: "not listed" }] };
export const testerOld: TesterCheck = { ...testerListed, lists: [{ name: "Example County tester list", dated: "2025-06-01", found: "listed", id: "T-1" }] };
export const testerNotFetched: TesterCheck = { ...testerListed, lists: [{ name: "Example County tester list", found: "not fetched" }] };

export const watchItems: WatchItem[] = [
  { item: "Annual fire alarm inspection", standing: "current", evidence: [doc("drive:ExampleDoc05", "Fire Alarm 2029-09-19.pdf")], changes: "A year after the report's date, with no newer report.", searched: "by email subject and Drive file name" },
  { item: "Fire extinguisher service tags", standing: "unknown", evidence: [], changes: "A record of the service, under any name, found or entered by a person.", searched: "by email subject and Drive file name" },
  { item: "Annual backflow test", standing: "overdue", evidence: [doc("drive:ExampleDoc02", "Backflow test 2030-05-05.pdf")], changes: "A passed test report, or the City's written extension.", searched: "by Drive file name" },
  { item: "Sprinkler five-year inspection", standing: "partly answered", evidence: [doc("drive:ExampleDoc06", "Sprinkler 2028.pdf")], changes: "The report for the remaining buildings.", searched: "by email subject" },
  { item: "Elevator permit", standing: "not applicable", evidence: [], changes: "A building with an elevator.", searched: "by Drive file name" },
];

export const notOurs: NotOurs = {
  subject: "Mail", addressee: "another party at the shared address", visible: ["Addressed to a business, not the association", "Return address: a collection letter sender"],
};
export const notOursMarked: NotOurs = { ...notOurs, marked: { by: "Jane Example", on: "2030-10-04" } };
