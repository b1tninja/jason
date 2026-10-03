import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TemplatesView } from "./TemplatesView";

afterEach(() => vi.unstubAllGlobals());

const row = { kind: "hearing-notice", title: "Notice of Hearing", driveId: "1DocIdHearing", folderId: "", authority: "CIV 5855", optional: ["CC_LINE"], linkTokens: [], tokens: ["OWNER_NAME", "HEARING_DATE", "CC_LINE", "ASSOCIATION_NAME"], lint: { profile: ["ASSOCIATION_NAME"], general: [], run: ["OWNER_NAME", "HEARING_DATE", "CC_LINE"] } };

describe("TemplatesView", () => {
  it("lists templates, fills one, previews it, shows the command, and keeps it on a canvas", async () => {
    const posts: unknown[] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      if (init?.method === "POST") { posts.push([url, JSON.parse(String(init.body))]); return new Response("{}", { status: 200 }); }
      if (url.startsWith("/api/canvases")) return new Response(JSON.stringify({ found: true, count: 1, statuses: [], canvases: [{ key: "unit-12-hearing", title: "Unit 12 hearing", status: "preparing" }] }), { status: 200 });
      if (url.includes("kind=")) {
        const p = new URLSearchParams(url.split("?")[1]);
        const owner = p.get("V_OWNER_NAME");
        return new Response(JSON.stringify({ found: true, kind: "hearing-notice", title: "Notice of Hearing", driveId: "1DocIdHearing", markdown: `# Notice of Hearing\n\nTo ${owner ?? "[owner name]"}`, tokens: row.tokens, open: owner ? ["HEARING_DATE"] : ["OWNER_NAME", "HEARING_DATE"], command: `jason letter --template hearing-notice --name 'Notice of Hearing draft'${owner ? ` --set 'OWNER_NAME=${owner}'` : ""} --yes` }), { status: 200 });
      }
      return new Response(JSON.stringify({ found: true, templates: [row] }), { status: 200 });
    }));
    render(<TemplatesView />);
    expect(await screen.findByText("Notice of Hearing")).toBeInTheDocument();
    expect(screen.getByText("owner name")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Fill" }));
    expect(await screen.findByText(/Still open: owner name, hearing date/)).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText(/^owner name/), "J. Doe");
    await waitFor(() => expect(screen.getByText("To J. Doe")).toBeInTheDocument(), { timeout: 3000 });
    expect(screen.getByText(/--set 'OWNER_NAME=J. Doe' --yes/)).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText("Canvas"), "unit-12-hearing");
    await userEvent.click(screen.getByRole("button", { name: "Keep" }));
    await waitFor(() => expect(posts).toHaveLength(1));
    expect((posts[0] as unknown[])[0]).toBe("/api/canvases/unit-12-hearing");
    expect(((posts[0] as unknown[])[1] as { clip: { source: string; text: string } }).clip.source).toBe("template: hearing-notice");
  });
});
