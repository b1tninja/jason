import type { Move, Role } from "../components/ConsoleShell";

const ROLES: readonly Role[] = ["officer", "manager", "administrator", "owner"];

/** The role class the server derived (`GET /api/session`'s `roleClass`), or undefined for none or a word it does not know:
 * the console then filters nothing and shows no strip, as it did before roles. */
export function roleOf(roleClass: string | null | undefined): Role | undefined {
  return ROLES.find((r) => r === roleClass);
}

/** The numbers the strip is made of: the dock's counts (this person's, or everyone's when nobody is signed in) and the
 * approvals waiting on anyone. */
export interface MoveCounts { approvals?: number | null; pending: number; tasks: number; deadlines: number }

/** What is waiting on this role, as the strip's links: an officer's approvals, tasks, and deadlines; the manager's tasks
 * and deadlines; the administrator's everything waiting on anyone. Each count opens the screen or drawer it is about. A
 * zero stays in the strip, muted: "nothing waiting" is information. The owner has none. */
export function roleMoves(role: Role, c: MoveCounts, act: { go: (id: string) => void; openDrawer: (id: string) => void }): Move[] {
  const tasks: Move = { n: c.tasks, label: role === "administrator" ? "overdue tasks (everyone's)" : "of your tasks overdue", go: () => act.openDrawer("tasks") };
  const deadlines: Move = { n: c.deadlines, label: role === "administrator" ? "overdue deadlines (everyone's)" : "overdue deadlines", go: () => act.openDrawer("deadlines") };
  if (role === "officer") return [{ n: c.approvals ?? 0, label: "waiting for your approval", go: () => act.go("approvals") }, tasks, deadlines];
  if (role === "manager") return [tasks, deadlines];
  if (role === "administrator") return [{ n: c.pending, label: "approvals waiting on anyone", go: () => act.go("approvals") }, tasks, deadlines];
  return [];
}
