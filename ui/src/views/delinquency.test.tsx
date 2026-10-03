import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DelinquencyView } from "./DelinquencyView";

afterEach(() => vi.unstubAllGlobals());

const STEPS = ["release recorded", "payment plan offered", "pre-lien notice sent (CIV 5660)", "lien recorded (CIV 5673, open session roll call)", "handed to collection agency", "foreclosure authorized (CIV 5720)", "written off"];
const data = {
  found: true, counts: { OWED_NO_LIEN: 1, RELEASE_DUE: 1 }, pastDueCents: 123400, steps: STEPS, lienStep: STEPS[3],
  rollCall: "A lien is recorded only after a majority of the board votes for it in an open meeting, by roll call, recorded in the minutes (Civil Code 5673).",
  rows: [
    { apn: "000-0000-001", address: "123 Main St #12", owners: ["Owner Twelve"], standing: "OWED_NO_LIEN", meaning: "past due, no lien", balanceCents: 123400, pastDueCents: 123400, lien: "", nextStep: "pre-lien notice (CIV 5660)", steps: [], latestStep: null },
    { apn: "000-0000-002", address: "123 Main St #7", owners: ["Owner Seven"], standing: "RELEASE_DUE", meaning: "paid; lien of record", balanceCents: 0, pastDueCents: 0, lien: "2024-0000123", lienStatus: "open", lienDays: 900, nextStep: "record the release (CIV 5685)",
      steps: [{ step: "payment plan offered", decidedOn: "2026-06-01", by: "Treasurer", vote: "", note: "", recorded: "2026-06-01T10:00:00+00:00", history: [] }], latestStep: { step: "payment plan offered", decidedOn: "2026-06-01", by: "Treasurer", vote: "", note: "", recorded: "2026-06-01T10:00:00+00:00", history: [] } },
  ],
  caveats: ["jason records the board's step; it submits, records, and forecloses nothing."],
};

describe("DelinquencyView", () => {
  it("renders the accounts with the statute's next step and the latest recorded step", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(data), { status: 200 })));
    render(<DelinquencyView />);
    expect(await screen.findByText("123 Main St #12")).toBeInTheDocument();
    expect(screen.getByText(/Executive session \(CIV 4935\)/)).toBeInTheDocument();
    expect(screen.getByText("pre-lien notice (CIV 5660)")).toBeInTheDocument();
    expect(screen.getByText("payment plan offered")).toBeInTheDocument();
    expect(screen.getByText("none")).toBeInTheDocument();
    expect(screen.getByText("release due")).toBeInTheDocument();
    expect(screen.getByText("jason records the board's step; it submits, records, and forecloses nothing.")).toBeInTheDocument();
  });

  it("opens an account and records a step through a confirm, posting to the apn", async () => {
    const posts: unknown[] = [];
    const saved = { apn: "000-0000-001", steps: [{ step: STEPS[3], decidedOn: "2026-10-20", by: "Secretary", vote: "3-0", note: "unit 12", recorded: "2026-10-20T20:00:00+00:00", history: [] }], latest: null as unknown };
    saved.latest = saved.steps[0];
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      if (init?.method === "POST") { posts.push([url, JSON.parse(String(init.body))]); return new Response(JSON.stringify(saved), { status: 200 }); }
      return new Response(JSON.stringify(data), { status: 200 });
    }));
    render(<DelinquencyView />);
    const user = userEvent.setup();
    await user.click((await screen.findAllByRole("button", { name: "Open" }))[0]);
    expect(screen.getByText("No step recorded yet.")).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Step"), STEPS[3]);
    expect(screen.getByText(/by roll call/)).toBeInTheDocument();
    const date = screen.getByLabelText("Decided on");
    await user.clear(date);
    await user.type(date, "2026-10-20");
    await user.type(screen.getByLabelText("Recorded by"), "Secretary");
    await user.type(screen.getByLabelText("Vote (ayes-noes)"), "3-0");
    await user.type(screen.getByLabelText("Note"), "unit 12");
    await user.click(screen.getByRole("button", { name: "Record the step" }));
    expect(screen.getByRole("group", { name: "Confirm" })).toHaveTextContent("vote 3-0");
    await user.click(screen.getByRole("button", { name: "Yes, do it" }));
    await waitFor(() => expect(posts).toHaveLength(1));
    expect((posts[0] as unknown[])[0]).toBe("/api/write/delinquency/000-0000-001");
    expect((posts[0] as unknown[])[1]).toEqual({ step: STEPS[3], decidedOn: "2026-10-20", by: "Secretary", vote: "3-0", note: "unit 12" });
    expect(await screen.findByRole("list", { name: "recorded steps" })).toHaveTextContent("lien recorded (CIV 5673, open session roll call) on 2026-10-20 · vote 3-0 · by Secretary");
  });

  it("keeps the confirm back until a name is given and the vote is a tally", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(data), { status: 200 })));
    render(<DelinquencyView />);
    const user = userEvent.setup();
    await user.click((await screen.findAllByRole("button", { name: "Open" }))[0]);
    expect(screen.queryByRole("button", { name: "Record the step" })).not.toBeInTheDocument();
    await user.type(screen.getByLabelText("Recorded by"), "Secretary");
    expect(screen.getByRole("button", { name: "Record the step" })).toBeInTheDocument();
    await user.type(screen.getByLabelText("Vote (ayes-noes)"), "all");
    expect(screen.queryByRole("button", { name: "Record the step" })).not.toBeInTheDocument();
  });
});
