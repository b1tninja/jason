import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { toneOf } from "../lib/tones";
import { DueDate } from "./DueDate";

describe("tones for the conversation, connection, follow-up, and arrival words", () => {
  it("never reads a missing required policy or a stalled handoff as an accusation", () => {
    expect(toneOf("required and missing")).toBe("warn");
    expect(toneOf("stalled")).toBe("warn");
    expect(toneOf("replied")).toBe("good");
  });

  it("reads the connection states by the registry's own words", () => {
    expect(toneOf("needs sign-in")).toBe("warn");
    expect(toneOf("needs_sign_in")).toBe("warn");
    expect(toneOf("failing")).toBe("bad");
    expect(toneOf("connected")).toBe("good");
    expect(toneOf("not set up")).toBe("neutral");
  });

  it("leaves a word it does not know neutral", () => {
    expect(toneOf("received")).toBe("neutral");
  });
});

describe("DueDate", () => {
  const today = new Date("2026-10-04T12:00:00");
  it("shows a settled deadline's date alone, never as overdue", () => {
    const { container } = render(<DueDate iso="2026-10-01" today={today} settled />);
    expect(container.textContent).toBe("2026-10-01");
    expect(container.textContent).not.toMatch(/overdue/);
  });
});
