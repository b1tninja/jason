import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { resetServerSession } from "../lib/api";
import { TemplatesView } from "./TemplatesView";

afterEach(() => { vi.unstubAllGlobals(); resetServerSession(); });

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

describe("TemplatesView: the Doc column", () => {
  const evidence = {
    found: true, address: "drive:1DocIdHearing", label: "Notice of Hearing", kind: "drive", changed: true, changedNote: "",
    link: "https://docs.google.com/document/d/1DocIdHearing/edit", refresh: [], caveats: [], note: "",
    refreshable: { system: "Google Drive", what: "Export this file again from Drive" },
    sources: [{ name: "Copy from Drive", readAt: "2026-10-03T15:00:00+00:00", digest: "", fields: [], text: "", citation: "", caveat: "", note: "" }],
    documents: [{ id: "pdf", name: "Notice of Hearing.pdf", kind: "pdf", size: 2048, readAt: "2026-10-03T15:00:00+00:00", note: "" }],
  };
  const unbuilt = { ...row, kind: "fine-notice", title: "Notice of Fine", driveId: "" };

  function serve(session: object) {
    const posts: [string, unknown][] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      if (init?.method === "POST") posts.push([url, JSON.parse(String(init.body))]);
      const body = url.startsWith("/api/session") ? session
        : url.startsWith("/api/evidence?") ? evidence
        : url === "/api/evidence/view" ? { kind: "pdf", name: "Notice of Hearing.pdf", readAt: "2026-10-03T15:00:00+00:00", url: "/api/evidence/document/tok", expires: "", caveats: ["Unmasked: shown because A Manager asked; this view is logged."] }
        : url === "/api/evidence/refresh" ? { ...evidence, changed: false, refreshed: { at: "x", by: "A Manager", system: "Google Drive" } }
        : url === "/api/evidence/refresh-many" ? { by: "A Manager", at: "x", refreshed: ["drive:1DocIdHearing"], failed: [], skipped: 0 }
        : { found: true, templates: [row, unbuilt] };
      return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
    }));
    return posts;
  }
  const IN = { token: "t", signedIn: { name: "A Manager" }, signIn: { configured: true, start: "/auth/google" } };

  it("shows jason's thumbnail, the copy's age, and Changed in Drive; an unbuilt one says so", async () => {
    serve(IN);
    render(<TemplatesView />);
    const img = await screen.findByRole("img", { name: "Notice of Hearing" });
    expect(img.getAttribute("src")).toBe(`/api/drive/thumb/1DocIdHearing?v=${encodeURIComponent("2026-10-03T15:00:00+00:00")}`);
    fireEvent.load(img);
    expect(screen.getByText(/copy from/)).toBeInTheDocument();
    expect(screen.getByText("Changed in Drive since this copy")).toBeInTheDocument();
    expect(screen.getByText("not built")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Open in Google/ })).toHaveAttribute("href", "https://docs.google.com/document/d/1DocIdHearing/edit");
  });

  it("Preview posts a view and opens the viewer; Read from Drive posts a refresh", async () => {
    const posts = serve(IN);
    render(<TemplatesView />);
    const preview = await screen.findByRole("button", { name: "Preview Notice of Hearing" });
    await waitFor(() => expect(preview).not.toHaveAttribute("aria-disabled"));
    await userEvent.click(preview);
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByRole("heading", { name: "Notice of Hearing.pdf" })).toBeInTheDocument();
    expect(posts[0]).toEqual(["/api/evidence/view", { address: "drive:1DocIdHearing", document: "pdf", by: "A Manager" }]);
    await userEvent.click(within(dialog).getByRole("button", { name: "Close" }));
    await userEvent.click(screen.getByRole("button", { name: "Read Notice of Hearing from Drive" }));
    await waitFor(() => expect(posts.map((p) => p[0])).toContain("/api/evidence/refresh"));
    expect(posts.find((p) => p[0] === "/api/evidence/refresh")?.[1]).toEqual({ address: "drive:1DocIdHearing", by: "A Manager" });
  });

  it("reads every template from Drive in one batch, then refetches the cells", async () => {
    const posts = serve(IN);
    render(<TemplatesView />);
    const all = await screen.findByRole("button", { name: "Read every template from Drive" });
    await waitFor(() => expect(all).not.toHaveAttribute("aria-disabled"));
    const before = (fetch as unknown as { mock: { calls: [string][] } }).mock.calls.filter(([u]) => u.startsWith("/api/evidence?")).length;
    await userEvent.click(all);
    expect(await screen.findByText("Read 1 template from Google Drive just now by A Manager.")).toBeInTheDocument();
    expect(posts).toEqual([["/api/evidence/refresh-many", { addresses: ["drive:1DocIdHearing"], by: "A Manager", batch: "templates" }]]);
    await waitFor(() => expect((fetch as unknown as { mock: { calls: [string][] } }).mock.calls.filter(([u]) => u.startsWith("/api/evidence?")).length).toBeGreaterThan(before));
  });

  it("signed out: placeholders that ask for a sign-in, no thumbnails, and the batch off", async () => {
    serve({ token: "t", signIn: { configured: true, start: "/auth/google" } });
    render(<TemplatesView />);
    expect(await screen.findByText("Sign in to see previews")).toBeInTheDocument();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Read every template from Drive" })).toHaveAttribute("aria-disabled", "true");
    expect(screen.getByRole("button", { name: "Read Notice of Hearing from Drive" })).toHaveAttribute("aria-disabled", "true");
  });
});
