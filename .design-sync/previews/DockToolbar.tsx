import { DockToolbar } from "jason-ui";

/** The board's four pills, none open, with red overdue counts on Deadlines and Tasks. */
export const BoardCounts = () => <DockToolbar open={null} onToggle={() => {}} counts={{ deadlines: 2, tasks: 1 }} audience="board" />;

/** Tasks open: its pill filled in ink while the others stay quiet; the counts still show. */
export const TasksOpen = () => <DockToolbar open="tasks" onToggle={() => {}} counts={{ deadlines: 2, tasks: 1 }} audience="board" />;

/** Nothing overdue: no counts at all, Scratchpad open. */
export const Quiet = () => <DockToolbar open="notes" onToggle={() => {}} counts={{ deadlines: 0, tasks: 0 }} audience="board" />;

/** The owner view: only Ask, the one drawer owners may open. */
export const Owner = () => <DockToolbar open={null} onToggle={() => {}} counts={{ deadlines: 2, tasks: 1 }} audience="owner" />;

/** Counts over nine still fit: Deadlines and Tasks carry red counts beside their glyphs, scoped to the signed-in person. */
export const BigCounts = () => <DockToolbar open="deadlines" onToggle={() => {}} counts={{ deadlines: 12, tasks: 9, scope: "mine", who: "Pat" }} audience="board" />;

/** Nobody signed in: counts are everyone's, and the toolbar says so beside the pills. */
export const EveryonesCounts = () => <DockToolbar open="ask" onToggle={() => {}} counts={{ deadlines: 3, tasks: 0, scope: "everyone" }} audience="board" />;
