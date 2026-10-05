import { describe, expect, it, vi } from "vitest";
import { roleMoves, roleOf } from "./roles";

describe("roleOf", () => {
  it("takes the four classes and nothing else", () => {
    expect(roleOf("officer")).toBe("officer");
    expect(roleOf("manager")).toBe("manager");
    expect(roleOf("administrator")).toBe("administrator");
    expect(roleOf("owner")).toBe("owner");
    expect(roleOf("")).toBeUndefined();
    expect(roleOf("president")).toBeUndefined();   // an office is not a class; the server derives the class
    expect(roleOf(undefined)).toBeUndefined();
  });
});

describe("roleMoves", () => {
  const counts = { approvals: 2, pending: 5, tasks: 3, deadlines: 0 };
  const act = () => ({ go: vi.fn(), openDrawer: vi.fn() });

  it("an officer's moves are their approvals, tasks, and deadlines, and each opens its screen or drawer", () => {
    const a = act();
    const moves = roleMoves("officer", counts, a);
    expect(moves.map((m) => [m.n, m.label])).toEqual([[2, "waiting for your approval"], [3, "of your tasks overdue"], [0, "overdue deadlines"]]);
    moves[0].go(); moves[1].go(); moves[2].go();
    expect(a.go).toHaveBeenCalledWith("approvals");
    expect(a.openDrawer).toHaveBeenNthCalledWith(1, "tasks");
    expect(a.openDrawer).toHaveBeenNthCalledWith(2, "deadlines");
  });

  it("the manager's are their tasks and deadlines; the administrator's are everyone's", () => {
    expect(roleMoves("manager", counts, act()).map((m) => m.label)).toEqual(["of your tasks overdue", "overdue deadlines"]);
    expect(roleMoves("administrator", counts, act()).map((m) => [m.n, m.label])).toEqual(
      [[5, "approvals waiting on anyone"], [3, "overdue tasks (everyone's)"], [0, "overdue deadlines (everyone's)"]]);
  });

  it("an officer with no count from the server shows zero, not nothing; an owner has none", () => {
    expect(roleMoves("officer", { ...counts, approvals: null }, act())[0].n).toBe(0);
    expect(roleMoves("owner", counts, act())).toEqual([]);
  });
});
