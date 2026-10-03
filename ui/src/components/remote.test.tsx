import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { RemoteView } from "./Remote";

describe("RemoteView", () => {
  it("catches a render function that throws while computing its JSX", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    const r = { status: "ready" as const, data: { count: 3, rows: [] as { x: number }[] }, reload: () => {} };
    render(<RemoteView r={r}>{(d) => <p>{(d.rows[0] as { x: number }).x}</p>}</RemoteView>);
    expect(screen.getByRole("alert")).toHaveTextContent(/could not render/i);
    expect(screen.getByText("Count")).toBeInTheDocument();
    spy.mockRestore();
  });
});
