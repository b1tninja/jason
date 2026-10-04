import { RoutingTag } from "jason-ui";

const row = { display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" } as const;

/** Each office's mark and its name, as the server resolved it from the roster. */
export const Offices = () => (
  <div style={row}>
    {["president", "vice president", "secretary", "treasurer", "director", "manager", "counsel", "board", "owners"].map((role) => <RoutingTag key={role} owner={{ role }} />)}
  </div>
);

/** With the person who holds the office, and an assignment the board has not adopted yet. */
export const WithPerson = () => (
  <div style={row}>
    <RoutingTag owner={{ role: "treasurer", name: "Jane Example" }} />
    <RoutingTag owner={{ role: "secretary", name: "Owner A" }} />
    <RoutingTag owner={{ role: "manager", adoption: "proposed" }} />
  </div>
);

/** Nothing resolved: unassigned, waiting for a person to take it. jason picks no one. */
export const Unassigned = () => <div style={row}><RoutingTag owner={null} /></div>;

/** In a line of a list, beside the title and the statute. */
export const InALine = () => (
  <p style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", margin: 0 }}>
    <strong>Budget report to members</strong><span className="muted">CIV 5300</span><RoutingTag owner={{ role: "treasurer", adoption: "proposed" }} />
  </p>
);
