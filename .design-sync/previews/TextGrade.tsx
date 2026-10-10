import { TextGrade } from "jason-ui";

/** The Legislature's text: where the words came from, not an endorsement. */
export const Legislature = () => <TextGrade grade="legislature" />;

/** A regulation or handbook read in full. */
export const Official = () => <TextGrade grade="official" />;

/** A digest: "confirm at the source" is always visible text beside the grade. */
export const Digest = () => <TextGrade grade="digest" />;

/** Quoted by a notice. */
export const QuotedByNotice = () => <TextGrade grade="quoted by a notice" />;

/** Nothing found: nothing is quoted. */
export const NotFound = () => <TextGrade grade="not found" />;
