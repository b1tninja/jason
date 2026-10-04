import { Day } from "jason-ui";

/** A recording date in the console's form inside a `<time>` carrying the ISO day. */
export const RecordingDate = () => <Day iso="2001-03-08" />;

/** A full timestamp shows its day only. */
export const FromTimestamp = () => <Day iso="2026-10-03T16:20:00+00:00" />;

/** In running text, as the key documents list uses it. */
export const InASentence = () => (
  <p>
    The first amendment, recorded <Day iso="2010-02-01" />, amends the restated declaration of <Day iso="2001-03-08" />.
  </p>
);
