import { useState } from "react";
import { OfficeLens } from "jason-ui";

// The offices a profile names; the vice president's is vacant. Made-up holders counts.
const OFFICES = ["president", "vice president", "secretary", "treasurer", "director", "manager"].map((office) => ({
  office, vacant: office === "vice president", holders: office === "vice president" ? 0 : 1,
}));

/** The select is controlled: a cell wraps it in state, as the Today page does with the URL's lens. */
const Lens = ({ start, mine }: { start: string; mine: string[] }) => {
  const [value, setValue] = useState(start);
  return <OfficeLens offices={OFFICES} mine={mine} value={value} onChange={setValue} />;
};

/** The viewer's own offices, the default: "My offices" names the office the signed-in person holds. */
export const MyOffices = () => <Lens start="" mine={["secretary"]} />;

/** A person who holds two offices reads the union of both under "My offices". */
export const TwoOffices = () => <Lens start="" mine={["secretary", "treasurer"]} />;

/** Reading another office: the select shows that office, and nothing is written by choosing it. */
export const ReadingTreasurer = () => <Lens start="treasurer" mine={["secretary"]} />;

/** A vacant office is marked in the select, so the viewer knows no one is there to do what waits. */
export const VacantOffice = () => <Lens start="vice president" mine={["secretary"]} />;
