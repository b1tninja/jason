import { Loading } from "jason-ui";

/** The default label while a view waits on the API. */
export const Default = () => <Loading />;

/** A label naming what is being read, for a slower store. */
export const CustomLabel = () => <Loading label="Reading the PayHOA ledger…" />;

/** As it sits inside a view: the one line where the data will appear, nothing else moves. */
export const InPlace = () => (
  <div style={{ display: "grid", gap: 8 }}>
    <h2 style={{ margin: 0, fontSize: "1.05rem" }}>Delinquent accounts</h2>
    <Loading label="Loading the delinquency sheet…" />
  </div>
);
