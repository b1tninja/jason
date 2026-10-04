import { Glyph } from "./Glyph";
import { ROLE_GLYPH, UNASSIGNED, isResolved, norm, roleWords, type RoutingOwner } from "../lib/marks";

export interface RoutingTagProps {
  /** The owner the server resolved from the roster or the profile's assignments (a dock deadline's `owners` row, an
   * `Officer`). Missing, null, or with an empty role, the tag reads "unassigned": jason picks no one, and never reads an
   * owner out of a thing's words. */
  owner?: RoutingOwner | null;
}

/** Whose desk a thing is on: the office's mark and its name, and the person when one holds it. It says nothing about
 * whether the thing is late or done. "The board" is a vote at a meeting, never a single approver. The words are the
 * tag's text; the glyph is decoration. */
export function RoutingTag({ owner }: RoutingTagProps) {
  if (!isResolved(owner)) {
    return (
      <span className="routing-tag routing-unassigned" data-role="">
        <Glyph name="for-review" size="14px" />
        <span className="visually-hidden">Routed to no one: </span>{UNASSIGNED}
        <span className="visually-hidden">, waiting for a person to take it</span>
      </span>
    );
  }
  const role = norm(owner.role);
  const glyph = ROLE_GLYPH[role];
  const proposed = owner.adoption && norm(owner.adoption) !== "adopted" ? norm(owner.adoption) : "";
  return (
    <span className={`routing-tag routing-${role.replace(/[^a-z]+/g, "-")}`} data-role={role}>
      {glyph && <Glyph name={glyph} size="14px" />}
      <span className="visually-hidden">Routed to </span>{roleWords(role)}
      {role === "board" && <span className="visually-hidden">, a vote at a meeting</span>}
      {owner.name && <span className="routing-name"> · {owner.name}</span>}
      {proposed && <span className="routing-adoption"> ({proposed})</span>}
    </span>
  );
}

/** Several owners. `owners` missing (an older server) renders nothing; an empty list is one "unassigned" tag. */
export function RoutingTags({ owners }: { owners?: readonly RoutingOwner[] | null }) {
  if (!owners) return null;
  if (owners.length === 0) return <RoutingTag owner={null} />;
  return <span className="routing-tags">{owners.map((o, i) => <RoutingTag key={`${o.role}-${o.name ?? ""}-${i}`} owner={o} />)}</span>;
}
