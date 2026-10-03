import { useState } from "react";
import { SearchBox } from "jason-ui";

/** The filter box above a table, with the default label and nothing typed. */
export const EmptyFilter = () => {
  const [value, setValue] = useState("");
  return <SearchBox value={value} onChange={setValue} />;
};

/** A filter in progress: an owner search typed into the ledger table. */
export const WithValue = () => {
  const [value, setValue] = useState("unit 207");
  return <SearchBox value={value} onChange={setValue} />;
};

/** A custom label becomes the placeholder and the accessible name. */
export const CustomLabel = () => {
  const [value, setValue] = useState("");
  return <SearchBox value={value} onChange={setValue} label="Search recorded instruments" />;
};

/** Live: typing shows the matching obligations below. */
export const Filtering = () => {
  const [value, setValue] = useState("notice");
  const rows = [
    "Annual budget report mailed (CIV 5300)",
    "Pre-lien notice (CIV 5660)",
    "Hearing notice, 10 days (CIV 5855)",
    "Reserve study update (CIV 5550)",
    "Notice of assessment increase (CIV 5615)",
  ];
  const shown = rows.filter((r) => r.toLowerCase().includes(value.toLowerCase()));
  return (
    <div>
      <SearchBox value={value} onChange={setValue} label="Filter obligations" />
      <ul style={{ margin: 0, paddingLeft: "1.2rem" }}>
        {shown.map((r) => (
          <li key={r}>{r}</li>
        ))}
      </ul>
    </div>
  );
};
