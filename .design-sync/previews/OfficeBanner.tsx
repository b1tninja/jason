import { OfficeBanner } from "jason-ui";

// OfficeBanner renders nothing on the viewer's own lens, so each cell reads another office's page.
const back = () => {};
const wide = { maxWidth: 820 } as const;

/** Reading the treasurer's page as the secretary: whose page it is, who the viewer is, and the way back. */
export const ReadingAnotherOffice = () => (
  <div style={wide}><OfficeBanner data={{ office: "treasurer", ownOffice: false, mine: ["secretary"], vacant: false }} onBack={back} /></div>
);

/** A viewer who holds two offices: both are named, joined as a sentence. */
export const ViewerHoldsTwoOffices = () => (
  <div style={wide}><OfficeBanner data={{ office: "president", ownOffice: false, mine: ["secretary", "treasurer"], vacant: false }} onBack={back} /></div>
);

/** A vacant office: a pill says no one holds it, and the bands show what waits with no one to do it. */
export const VacantOffice = () => (
  <div style={wide}><OfficeBanner data={{ office: "vice president", ownOffice: false, mine: ["secretary"], vacant: true }} onBack={back} /></div>
);

/** A viewer who holds no office at all (a manager's delegate, say) still reads another office's page, said plainly. */
export const ViewerHoldsNoOffice = () => (
  <div style={wide}><OfficeBanner data={{ office: "treasurer", ownOffice: false, mine: [], vacant: false }} onBack={back} /></div>
);
