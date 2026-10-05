import { EmptyState } from "jason-ui";

/** The default line when a list has no rows. */
export const Default = () => <EmptyState />;

/** The tool's own note, passed through: it says which store is empty and how to fill it. */
export const CustomChildren = () => <EmptyState>No violations open. Run `jason violations` after the next walk-through to refresh this list.</EmptyState>;

/** A note with a hint and emphasis; children are any node, not just a string. */
export const RichChildren = () => (
  <EmptyState>
    No board digest on disk yet. <strong>jason digest</strong> writes one from the stores; until then this page stays blank.
  </EmptyState>
);

/** The screen's own glyph at 32px, muted, above the words: a receipts screen with none yet. */
export const WithGlyph = () => <EmptyState glyph="receipt">No receipts on file for this month. Attach one from the payment's row.</EmptyState>;

/** Another screen, another glyph: nothing is waiting for approval. */
export const ApprovalsGlyph = () => <EmptyState glyph="stamp">Nothing is waiting for your approval.</EmptyState>;
