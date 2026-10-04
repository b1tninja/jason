import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { GLYPHS, GLYPH_META, Glyph, JASON_GLYPH_NAMES, LUCIDE_VERSION, hasGlyph, strokeFor, type GlyphName } from "./Glyph";
import { RoutingTag, RoutingTags } from "./RoutingTag";
import { Seal } from "./Seal";
import { Stamp } from "./Stamp";
import { NOT_A_MARK, ROLE_GLYPH, SEAL_WORDS, STAMP_WORDS, isSealWord, isStampWord, markTokens, type SealWord } from "../lib/marks";

afterEach(() => vi.restoreAllMocks());

describe("Glyph", () => {
  it("bundles the Lucide subset and jason's own, and every catalog row names a glyph in the set", () => {
    expect(LUCIDE_VERSION).toBe("1.51.0");
    expect(Object.keys(GLYPHS).length).toBe(312);
    expect(JASON_GLYPH_NAMES.length).toBe(51);
    expect(GLYPH_META.filter((m) => !hasGlyph(m.name))).toEqual([]);
    for (const name of Object.keys(GLYPHS)) expect(GLYPHS[name as GlyphName]).toMatch(/^<(path|circle|rect|line|polyline|polygon|ellipse|g)\b/);
  });

  it("is decoration beside its word by default: hidden from screen readers, not focusable", () => {
    const { container } = render(<p><Glyph name="gavel" size="16px" /> Motion</p>);
    const svg = container.querySelector("svg")!;
    expect(svg).toHaveAttribute("aria-hidden", "true");
    expect(svg).toHaveAttribute("focusable", "false");
    expect(svg).not.toHaveAttribute("role");
    expect(svg).toHaveAttribute("data-glyph", "gavel");
    expect(svg.getAttribute("stroke-width")).toBe("2");
    expect(svg.innerHTML).toContain("<path");
    expect(screen.queryByRole("img")).toBeNull();
  });

  it("is named when it stands alone", () => {
    render(<button type="button"><Glyph name="x" size={20} label="Close" /></button>);
    expect(screen.getByRole("img", { name: "Close" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Close" })).toBeInTheDocument();
  });

  it("renders nothing for a name not in the set, and logs it once", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const { container } = render(<><Glyph name={"no-such-glyph" as GlyphName} /><Glyph name={"no-such-glyph" as GlyphName} /></>);
    expect(container.querySelector("svg")).toBeNull();
    expect(warn).toHaveBeenCalledTimes(1);
  });

  it("thins the stroke as it grows", () => {
    expect(strokeFor("16px")).toBe(2);
    expect(strokeFor(20)).toBe(1.75);
    expect(strokeFor("32px")).toBe(1.5);
    expect(strokeFor("1em")).toBe(1.75);
  });
});

describe("the two vocabularies", () => {
  it("never share a word: not a key, not a word of a label", () => {
    const stamps = markTokens(STAMP_WORDS);
    const seals = markTokens(SEAL_WORDS);
    expect([...stamps].filter((t) => seals.has(t))).toEqual([]);
    expect(Object.keys(STAMP_WORDS).filter((k) => k in SEAL_WORDS)).toEqual([]);
  });

  it("makes filed a seal, never a stamp", () => {
    expect(isSealWord("filed")).toBe(true);
    expect(isStampWord("filed")).toBe(false);
    expect(SEAL_WORDS.filed.state).toBe("done");
  });

  it("has no recorded, draft, or confidential in either: a county filing is the read seal, a draft the drafted seal, confidential the P3 chip", () => {
    for (const w of NOT_A_MARK) {
      expect(isSealWord(w)).toBe(false);
      expect(isStampWord(w)).toBe(false);
    }
    expect(isSealWord("recorded")).toBe(false);
    expect(isSealWord("read")).toBe(true);
    expect(isSealWord("drafted")).toBe(true);
  });

  it("gives every office mark a glyph in the set", () => {
    for (const g of Object.values(ROLE_GLYPH)) expect(hasGlyph(g)).toBe(true);
  });
});

describe("Stamp", () => {
  it("shows a person's decision in its word, with who and when, as one named image", () => {
    const { container } = render(<Stamp word="approved" by="R. Lind, secretary" date="2026-10-21" />);
    expect(screen.getByRole("img", { name: "Approved, R. Lind, secretary · 2026-10-21" })).toBeInTheDocument();
    const el = container.querySelector(".stamp")!;
    expect(el).toHaveClass("stamp-good");
    expect(el).toHaveClass("stamp-has-sub");
    expect((el as HTMLElement).style.getPropertyValue("--stamp-tilt")).toBe("-6deg");
  });

  it("lies flat in a table and takes each tone from its word", () => {
    const { container } = render(<><Stamp word="denied" tilt={0} /><Stamp word="Tabled" /><Stamp word="withdrawn" /></>);
    const [denied, tabled, withdrawn] = container.querySelectorAll(".stamp");
    expect((denied as HTMLElement).style.getPropertyValue("--stamp-tilt")).toBe("0deg");
    expect(denied).toHaveClass("stamp-bad");
    expect(tabled).toHaveClass("stamp-warn");
    expect(withdrawn).toHaveClass("stamp-neutral");
    expect(screen.getByRole("img", { name: "Tabled" })).toBeInTheDocument();
  });

  it("keeps a motion's own word it does not know, in the neutral tone, so the record is never lost", () => {
    const { container } = render(<Stamp word="Postponed" />);
    expect(screen.getByRole("img", { name: "Postponed" })).toBeInTheDocument();
    expect(container.querySelector(".stamp")).toHaveClass("stamp-neutral");
  });

  it("refuses a seal's word, and draft, confidential, and recorded", () => {
    vi.spyOn(console, "warn").mockImplementation(() => {});
    for (const w of [...Object.keys(SEAL_WORDS), ...NOT_A_MARK]) {
      const { container, unmount } = render(<Stamp word={w} />);
      expect(container.innerHTML).toBe("");
      unmount();
    }
  });

  it("stamps sent only with the record of the sending, never on a click", () => {
    vi.spyOn(console, "warn").mockImplementation(() => {});
    const bare = render(<Stamp word="sent" date="2026-10-01" />);
    expect(bare.container.innerHTML).toBe("");
    bare.unmount();
    const { container } = render(<Stamp word="sent" date="2026-10-01" sentRef="comm-123" />);
    expect(screen.getByRole("img", { name: "Sent, 2026-10-01, record comm-123" })).toBeInTheDocument();
    expect(container.querySelector(".stamp")).toHaveAttribute("data-sent-ref", "comm-123");
  });
});

describe("Seal", () => {
  it("marks a county filing as jason's read, with its instrument number and the state in words", () => {
    render(<Seal word="read" instrument="2024-0001234" date="2026-10-03" />);
    expect(screen.getByRole("img", { name: "jason read, instrument 2024-0001234 · 2026-10-03, done" })).toBeInTheDocument();
  });

  it("names each seal with its label and its state", () => {
    for (const [w, def] of Object.entries(SEAL_WORDS)) {
      const { container, unmount } = render(<Seal word={w as SealWord} />);
      const el = container.querySelector(".seal")!;
      expect(el).toHaveClass(`seal-${def.state}`);
      expect(el.getAttribute("role")).toBe("img");
      expect(el.getAttribute("aria-label")).toMatch(new RegExp(`^${def.label}, `));
      expect(el.querySelector(".seal-eave")).not.toBeNull();
      unmount();
    }
  });

  it("files as a seal: filed renders, done", () => {
    render(<Seal word="filed" detail="Drive: Minutes" />);
    expect(screen.getByRole("img", { name: "jason filed, Drive: Minutes, done" })).toBeInTheDocument();
  });

  it("refuses recorded and every stamp's word", () => {
    vi.spyOn(console, "warn").mockImplementation(() => {});
    for (const w of ["recorded", ...Object.keys(STAMP_WORDS)]) {
      const { container, unmount } = render(<Seal word={w as SealWord} />);
      expect(container.innerHTML).toBe("");
      unmount();
    }
  });

  it("sits on one line in a table cell", () => {
    const { container } = render(<Seal word="could-not-confirm" inline />);
    expect(screen.getByRole("img", { name: "not confirmed, unresolved" })).toBeInTheDocument();
    expect(container.querySelector(".seal")).toHaveClass("seal-inline");
    expect(container.querySelector(".seal-eave")).toBeNull();
  });
});

describe("RoutingTag", () => {
  it("names the office the server resolved, and the person who holds it", () => {
    const { container } = render(<RoutingTag owner={{ role: "treasurer", name: "Jane Example" }} />);
    const tag = container.querySelector(".routing-tag")!;
    expect(tag.textContent).toBe("Routed to the treasurer · Jane Example");
    expect(tag.querySelector('[data-glyph="for-treasurer"]')).toHaveAttribute("aria-hidden", "true");
  });

  it("says an assignment the board has not adopted, and that the board is a vote at a meeting", () => {
    const { container } = render(<><RoutingTag owner={{ role: "treasurer", adoption: "proposed" }} /><RoutingTag owner={{ role: "board" }} /></>);
    const [t, b] = container.querySelectorAll(".routing-tag");
    expect(t.textContent).toBe("Routed to the treasurer (proposed)");
    expect(b.textContent).toBe("Routed to the board, a vote at a meeting");
  });

  it("reads unassigned when nothing resolved, and never reads an owner out of words", () => {
    for (const owner of [null, undefined, { role: "" }, { role: "  ", name: "Treasurer's report" }]) {
      const { container, unmount } = render(<RoutingTag owner={owner} />);
      const tag = container.querySelector(".routing-tag")!;
      expect(tag).toHaveClass("routing-unassigned");
      expect(tag.textContent).toBe("Routed to no one: unassigned, waiting for a person to take it");
      unmount();
    }
  });

  it("names an office without a mark of its own, with no glyph", () => {
    const { container } = render(<RoutingTag owner={{ role: "inspector of elections" }} />);
    expect(container.textContent).toBe("Routed to the inspector of elections");
    expect(container.querySelector("svg")).toBeNull();
  });

  it("lists several owners; an empty list is unassigned and a missing one is nothing", () => {
    const many = render(<RoutingTags owners={[{ role: "president" }, { role: "secretary" }]} />);
    expect(many.container.querySelectorAll(".routing-tag")).toHaveLength(2);
    many.unmount();
    const none = render(<RoutingTags owners={[]} />);
    expect(none.container.textContent).toContain("unassigned");
    none.unmount();
    const older = render(<RoutingTags />);
    expect(older.container.innerHTML).toBe("");
  });
});
