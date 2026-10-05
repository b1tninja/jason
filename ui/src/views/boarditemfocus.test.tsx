import { describe, expect, it } from "vitest";
import { boardItemHref, focusedItem } from "./BoardItemsView";

describe("linking to one board item", () => {
  it("builds the link a plan's held item uses, and reads it back from the address", () => {
    expect(boardItemHref("rule-change 4/15")).toBe("#/actions?item=rule-change%204%2F15");
    expect(focusedItem("#/actions?item=rule-change%204%2F15")).toBe("rule-change 4/15");
    expect(focusedItem("#/actions")).toBe("");
    expect(focusedItem("#/actions?closed=1")).toBe("");
  });
});
