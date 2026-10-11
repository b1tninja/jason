import { Glyph } from "./Glyph";
import type { RosterCheckData, RosterOffice } from "../lib/controls";

const list = (xs: readonly RosterOffice[]) => xs.map((x) => `${x.office}: ${x.count}`).join("; ");

/** Can the roster satisfy the control: what it needs and what is seated, by office and count. Never a name, an email,
 * or a phone: only the office word and a number are read from the data, so a field a loader added by mistake is not
 * shown. A shortfall says which office is missing, in the loader's sentence. One person who holds two offices counts
 * once in each office; no name says so. */
export function RosterCheck({ roster }: { roster: RosterCheckData }) {
  if (!roster.read)
    return <p className="muted"><Glyph name="minus" size="1em" /> The roster could not be read, so this check was skipped. Nothing is assumed about who is seated.</p>;
  const short = roster.missing.length > 0 || !!roster.lacks;
  return (
    <div className="roster-check" data-satisfied={short ? "no" : "yes"}>
      <dl className="roster-lines">
        <dt>Needs</dt>
        <dd>{roster.needs.length ? list(roster.needs) : "no office in particular"}</dd>
        <dt>Seated</dt>
        <dd>{roster.seated.length ? list(roster.seated) : "no office is seated"}</dd>
        {roster.missing.length > 0 && (
          <>
            <dt>Missing</dt>
            <dd>{roster.missing.map((m) => m.office).join("; ")}</dd>
          </>
        )}
      </dl>
      {short ? (
        <p className="roster-verdict roster-short"><Glyph name="user-x" size="1em" /> <strong>The roster cannot satisfy it.</strong> {roster.lacks}</p>
      ) : (
        <p className="roster-verdict"><Glyph name="shield-check" size="1em" /> <strong>The roster can satisfy it.</strong></p>
      )}
    </div>
  );
}
