import { ErrorNotice } from "jason-ui";

/** The API failed and the person can try again: message on the left, Retry on the right. */
export const WithRetry = () => <ErrorNotice error="Could not reach jason-mcp: connection refused (127.0.0.1:8765)." onRetry={() => {}} />;

/** No retry: the error is in the data, not the fetch, so trying again would not help. */
export const WithoutRetry = () => <ErrorNotice error="The reserve study on disk is from 2019; the three-year refresh under Civil Code 5550 is overdue." />;

/** A longer message wraps; the Retry button keeps its own column. */
export const LongMessage = () => (
  <ErrorNotice
    error="Keeper is not signed in (KeeperAuthRequired). This run is non-interactive, so jason stopped before opening a browser. Run `jason login` in a terminal, then retry."
    onRetry={() => {}}
  />
);
