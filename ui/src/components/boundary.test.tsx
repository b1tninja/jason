import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { RemoteView } from "./Remote";

type Data = { found?: boolean; total: number; items: { name: string }[] };
const data: Data = { total: 42, items: [{ name: "alpha" }, { name: "beta" }] };
const ready = { status: "ready" as const, data, reload: () => {} };

function Broken(): never {
  throw new Error("boom: items.map is not a function");
}

describe("RemoteView error boundary", () => {
  let spy: ReturnType<typeof vi.spyOn>;
  beforeEach(() => {
    // React logs the caught error; keep the test output clean.
    spy = vi.spyOn(console, "error").mockImplementation(() => {});
  });
  afterEach(() => spy.mockRestore());

  it("shows the notice, the DigestView fallback, and the raw JSON when the view throws", () => {
    render(<RemoteView r={ready}>{() => <Broken />}</RemoteView>);
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent(/could not render this data/);
    expect(alert).toHaveTextContent(/boom: items.map is not a function/);
    // DigestView: the scalar becomes a stat, the list a table.
    expect(screen.getByText("Total")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.getByText("alpha")).toBeInTheDocument();
    // Raw JSON in a details element.
    expect(screen.getByText("Raw JSON")).toBeInTheDocument();
    expect(screen.getByText(/"total": 42/)).toBeInTheDocument();
  });

  it("renders a view that does not throw normally", () => {
    render(<RemoteView r={ready}>{(d) => <p>Total is {d.total}</p>}</RemoteView>);
    expect(screen.getByText("Total is 42")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.queryByText("Raw JSON")).not.toBeInTheDocument();
  });

  it("keeps loading, error, and found:false behavior", () => {
    const { rerender } = render(<RemoteView r={{ status: "loading", reload: () => {} }}>{() => <p>x</p>}</RemoteView>);
    expect(screen.getByRole("status")).toHaveTextContent("Loading…");
    rerender(<RemoteView r={{ status: "error", error: "nope", reload: () => {} }}>{() => <p>x</p>}</RemoteView>);
    expect(screen.getByRole("alert")).toHaveTextContent("nope");
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
    rerender(
      <RemoteView r={{ status: "ready", data: { found: false, note: "no store" } as Data & { note: string }, reload: () => {} }}>
        {() => <p>x</p>}
      </RemoteView>,
    );
    expect(screen.getByText("no store")).toBeInTheDocument();
  });
});
