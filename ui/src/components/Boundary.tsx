import { Component, type ReactNode } from "react";
import { DigestView } from "../DigestView";
import { ErrorNotice } from "./States";

type Props = { data: unknown; children: ReactNode };
type State = { error: Error | null };

/**
 * Catches a view that throws while rendering a tool result. The typed views were written against
 * inferred shapes; when real data does not fit, the person still sees what the tool returned:
 * a notice naming the error, the generic DigestView, and the raw JSON. Key it on the data so it resets.
 */
export class ViewBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;
    const { data } = this.props;
    const digest = data && typeof data === "object" && !Array.isArray(data) ? (data as Record<string, unknown>) : { value: data };
    let raw: string;
    try {
      raw = JSON.stringify(data, null, 2) ?? String(data);
    } catch (e) {
      raw = `(not serializable: ${(e as Error).message})`;
    }
    return (
      <div className="stack">
        <ErrorNotice error={`This view could not render this data: ${error.message || String(error)}. Showing the raw result instead.`} />
        <DigestView digest={digest} />
        <details>
          <summary>Raw JSON</summary>
          <pre>{raw}</pre>
        </details>
      </div>
    );
  }
}
