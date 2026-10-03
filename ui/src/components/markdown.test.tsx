import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Embed, embedUrls, googleId } from "./Embed";
import { Markdown } from "./Markdown";

describe("Markdown", () => {
  it("renders markdown, sanitizes script, opens links in a new tab, keeps a mermaid fence as a diagram slot", () => {
    render(<Markdown text={"# Reserve loan\n\n- restore by **March**\n\n[agenda](https://x.example)\n\n<script>alert(1)</script>\n\n```mermaid\ngraph TD; A-->B\n```\n\nafter"} />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Reserve loan");
    expect(screen.getByText("March").tagName).toBe("STRONG");
    expect(screen.getByRole("link", { name: "agenda" })).toHaveAttribute("target", "_blank");
    expect(document.querySelector("script")).toBeNull();
    expect(screen.getByText("after")).toBeInTheDocument();
    expect(document.querySelector(".mermaid, .notice-error")).not.toBeNull();
  });
});

describe("Embed", () => {
  it("maps kinds to preview urls and extracts Google ids", () => {
    expect(googleId("https://docs.google.com/document/d/1AbCdEfGhIjKlMnOpQ/edit#x")).toBe("1AbCdEfGhIjKlMnOpQ");
    expect(googleId("https://drive.google.com/open?id=1AbCdEfGhIjKlMnOpQ")).toBe("1AbCdEfGhIjKlMnOpQ");
    expect(googleId("1AbCdEfGhIjKlMnOpQ")).toBe("1AbCdEfGhIjKlMnOpQ");
    expect(embedUrls({ kind: "sheet", ref: "1AbCdEfGhIjKlMnOpQ" }).frame).toBe("https://docs.google.com/spreadsheets/d/1AbCdEfGhIjKlMnOpQ/preview");
    expect(embedUrls({ kind: "form", ref: "1AbCdEfGhIjKlMnOpQ" }).frame).toContain("viewform?embedded=true");
    expect(embedUrls({ kind: "image", ref: "photos/east bed.jpg" }).frame).toBe("/api/file?path=photos%2Feast%20bed.jpg");
    expect(embedUrls({ kind: "pdf", ref: "https://h/x.pdf" }).frame).toBe("https://h/x.pdf");
  });
  it("renders an image as img and a doc as an iframe", () => {
    const { rerender } = render(<Embed a={{ kind: "image", ref: "photos/a.jpg", title: "before" }} />);
    expect(screen.getByRole("img", { name: "before" })).toHaveAttribute("src", "/api/file?path=photos%2Fa.jpg");
    rerender(<Embed a={{ kind: "doc", ref: "1AbCdEfGhIjKlMnOpQ", title: "Minutes" }} />);
    expect(document.querySelector("iframe")).toHaveAttribute("src", "https://docs.google.com/document/d/1AbCdEfGhIjKlMnOpQ/preview");
    expect(screen.getByRole("link", { name: "open" })).toHaveAttribute("href", "https://docs.google.com/document/d/1AbCdEfGhIjKlMnOpQ/edit");
  });
});
