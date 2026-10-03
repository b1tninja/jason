import { Badge, ScreenHeader } from "jason-ui";

/** Title and the one-line muted summary. */
export const TitleSummary = () => <ScreenHeader title="Liens and delinquency" summary="Every lien in order, with the next step and who owes it." />;

/** Actions at the right: a badge and two buttons. */
export const WithActions = () => (
  <ScreenHeader
    title="Approvals"
    summary="Letters jason drafted, waiting on a person. Nothing is sent without approval."
    actions={
      <>
        <Badge tone="warn">2 waiting</Badge>
        <button>Refresh</button>
        <button className="primary">Draft a letter</button>
      </>
    }
  />
);

/** Title alone. */
export const TitleOnly = () => <ScreenHeader title="Board digest" />;
