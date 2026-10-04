import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { resetServerSession } from "../lib/api";
import { Markdown } from "./Markdown";
import { apiFilePath, slotFileImages } from "./Markdown";

afterEach(() => { vi.unstubAllGlobals(); resetServerSession(); });

const signedOut = () => vi.stubGlobal("fetch", vi.fn(async (url: string) => new Response(
  JSON.stringify(String(url).startsWith("/api/session") ? { signedIn: null, signIn: { configured: true, start: "/auth/google" } } : { found: false, address: "", documents: [] }),
  { status: 200 })));

describe("Markdown's images of files under data/", () => {
  it("a markdown image of /api/file?path= is a Doc card of file:<path>, never a raw image", async () => {
    signedOut();
    render(<Markdown text={"Before the work:\n\n![East bed](/api/file?path=photos%2Feast-bed.pdf)\n\nafter"} />);
    expect(document.querySelector('img[src*="/api/file"]')).toBeNull();
    expect(await screen.findByText("Sign in to see previews")).toBeInTheDocument();     // the state's words
    expect(screen.getByRole("button", { name: "Preview East bed, file on disk" })).toBeInTheDocument();
    expect(screen.getByText("after")).toBeInTheDocument();
  });

  it("an HTML img of /api/file is slotted after sanitizing: no handler survives, and other images stay", () => {
    signedOut();
    render(<Markdown text={'<img src="/api/file?path=mail/1/scan.png" onerror="alert(1)" alt="scan"> ![a](data:image/svg+xml;utf8,%3Csvg%3E)'} />);
    expect(document.querySelector('img[src*="/api/file"]')).toBeNull();
    expect(document.querySelector("[onerror]")).toBeNull();
    expect(screen.getByRole("img", { name: "a" })).toHaveAttribute("src", "data:image/svg+xml;utf8,%3Csvg%3E");
    expect(document.querySelector('[data-doc-file="mail/1/scan.png"]')).not.toBeNull();
  });

  it("a path that tries to break out of the placeholder stays text", () => {
    const html = slotFileImages('<img src="/api/file?path=a%22%3E%3Cscript%3Ealert(1)%3C%2Fscript%3E" alt="x">');
    expect(html).not.toContain("<script");
    expect(html).toContain('data-doc-file="a&quot;&gt;&lt;script&gt;alert(1)&lt;/script&gt;"');
  });

  it("knows a relative or same-origin /api/file source, and nothing else", () => {
    expect(apiFilePath("/api/file?path=photos%2Fa.jpg")).toBe("photos/a.jpg");
    expect(apiFilePath(`${window.location.origin}/api/file?path=a.pdf`)).toBe("a.pdf");
    expect(apiFilePath("https://elsewhere.example/api/file?path=a.pdf")).toBeNull();
    expect(apiFilePath("/api/thumb?path=a.pdf")).toBeNull();
  });
});
