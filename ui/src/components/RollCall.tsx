import { Badge } from "./Badge";

export type VoteWord = "aye" | "no" | "abstain" | "absent";
export const VOTE_WORDS: VoteWord[] = ["aye", "no", "abstain", "absent"];
/** The answers in a roll call by name (required for a meeting held entirely by teleconference, CIV 4926(a)(3)); absence is
 * attendance, not a vote. */
const ROLL_WORDS: VoteWord[] = ["aye", "no", "abstain"];

export type Threshold = "majority" | "two-thirds";
/** What carries a motion, as the bylaws or counsel's reading set it (`BoardRule.vote_basis`). */
export type VoteBasis = "majority-present" | "majority-in-office";

/** What the room says where neither the bylaws' words nor counsel's reading is on file. Never filled in with a default. */
export const NOT_ON_FILE = "not on file; ask counsel";
/** What the room says where the board has adopted no speaking limit (CIV 4925(b)). Never a default number. */
export const NO_FORUM_LIMIT = "No limit on record; the board sets it (CIV 4925(b)).";

export interface OutcomeOptions {
  /** The directors in the meeting; drives the quorum line and who must answer. Defaults to everyone who voted. */
  present?: readonly string[];
  /** Directors who disclosed an interest (the secretary records each; nothing here infers one). They do not vote. */
  recused?: readonly string[];
  /** Whether a recused director counts toward the quorum and among the directors present: the bylaws' rule or counsel's
   * reading. `null` or absent: not on file, so the vote is worked both ways and a vote they decide differently is held. */
  interested?: boolean | null;
  /** The quorum, to check each reading against. */
  quorum?: number;
  /** The vote rule on file; absent, a majority of the directors present (the room labels that as a reading). */
  basis?: VoteBasis;
  /** A majority, or two-thirds of the directors present for an off-agenda emergency item (CIV 4930(d)(2)). */
  threshold?: Threshold;
  /** Seats on the board: under CIV 4930(d)(2), fewer than two-thirds of them present means every director present must agree. */
  seats?: number;
}

export interface Reading { needs: number; quorum: boolean; state: "open" | "carries" | "fails" }

export interface Outcome {
  yes: number; no: number; abstain: number; recused: number;
  /** The directors who may vote: present and not recused. */
  voters: string[];
  needs: number;
  /** Every voter has answered. */
  answered: boolean;
  /** "held": the two readings of the recusal question decide the vote differently, and neither is on file. */
  state: "open" | "carries" | "fails" | "held";
  /** Each reading, when a director is recused: counted among those present, and not. */
  readings?: { counted: Reading; notCounted: Reading };
  /** "Yes 3 · No 0 · Abstain 0 · Recused 0. Needs 3 yes. Carries." */
  line: string;
}

function needsFor(base: number, opts: OutcomeOptions): number {
  if (base <= 0) return 0;
  if (opts.threshold === "two-thirds") {
    const enoughOfBoard = !opts.seats || base >= Math.ceil((2 * opts.seats) / 3);
    return enoughOfBoard ? Math.ceil((2 * base) / 3) : base;
  }
  if (opts.basis === "majority-in-office" && opts.seats) return Math.floor(opts.seats / 2) + 1;
  return Math.floor(base / 2) + 1;
}

/** The roll call as it stands, by the rules above. Pure: the same votes and options always give the same answer. */
export function outcome(votes: Record<string, string>, opts: OutcomeOptions = {}): Outcome {
  const recusedAll = opts.recused ?? [];
  const present = opts.present ?? Object.keys(votes);
  const recused = recusedAll.filter((n) => present.includes(n));
  const voters = present.filter((n) => !recused.includes(n));
  const count = (w: VoteWord) => voters.filter((n) => votes[n] === w).length;
  const yes = count("aye"), no = count("no"), abstain = count("abstain");
  const answered = voters.length > 0 && voters.every((n) => ROLL_WORDS.includes(votes[n] as VoteWord));
  const reading = (base: number): Reading => {
    const needs = needsFor(base, opts);
    const quorum = opts.quorum === undefined || (opts.quorum > 0 && base >= opts.quorum);
    return { needs, quorum, state: !answered ? "open" : quorum && yes >= needs ? "carries" : "fails" };
  };
  const counted = reading(present.length), apart = reading(voters.length);
  const head = `Yes ${yes} · No ${no} · Abstain ${abstain} · Recused ${recused.length}. `;
  if (recused.length && (opts.interested === null || opts.interested === undefined)) {
    const held = answered && counted.state !== apart.state;
    const state: Outcome["state"] = held ? "held" : counted.state;
    const line = head + `Needs ${counted.needs} yes counting the recused director${recused.length > 1 ? "s" : ""} as present${counted.quorum ? "" : " (no quorum)"}, `
      + `${apart.needs} yes if not${apart.quorum ? "" : " (no quorum)"}. `
      + { open: "Vote open.", carries: "Carries under either reading.", fails: "Fails under either reading.", held: `Held: the readings differ, and whether a recused director counts is ${NOT_ON_FILE}.` }[state];
    return { yes, no, abstain, recused: recused.length, voters, needs: counted.needs, answered, state, readings: { counted, notCounted: apart }, line };
  }
  const chosen = recused.length && opts.interested === false ? apart : counted;
  const line = head + `Needs ${chosen.needs} yes${chosen.quorum || !answered ? "" : " (no quorum for this vote)"}. ` + { open: "Vote open.", carries: "Carries.", fails: "Fails." }[chosen.state];
  return { yes, no, abstain, recused: recused.length, voters, needs: chosen.needs, answered, state: chosen.state,
    readings: recused.length ? { counted, notCounted: apart } : undefined, line };
}

/** Each director's vote, one row per director; unmarked rows count as nothing until marked.
 * With `present`, `recused`, or `threshold` given it is a roll call by name: a recused director's row reads "recused" with
 * its radios off, an absent director's reads "absent", and a tally line says what the motion needs and whether it carries.
 * Without them it renders exactly as before. */
export function RollCall({ directors, votes, onChange, present, recused, threshold, seats, interested, quorum, basis }: {
  directors: readonly string[]; votes: Record<string, string>; onChange?: (next: Record<string, string>) => void;
  present?: readonly string[]; recused?: readonly string[]; threshold?: Threshold; seats?: number;
  interested?: boolean | null; quorum?: number; basis?: VoteBasis;
}) {
  const extended = present !== undefined || threshold !== undefined;
  const names = [...new Set([...directors, ...Object.keys(votes)])];
  const words = extended ? ROLL_WORDS : VOTE_WORDS;
  const here = present ?? names;
  const isRecused = (n: string) => (recused ?? []).includes(n);
  const isAbsent = (n: string) => extended && present !== undefined && !present.includes(n);
  const result = extended ? outcome(votes, { present: here, recused, threshold, seats, interested, quorum, basis }) : null;
  const onFile = interested !== null && interested !== undefined;
  // A recused row reads "recused" wherever one is recorded, roll call or not: never a vote, never "absent".
  const flagged = extended || (recused ?? []).length > 0;
  const table = (
      <table className="rollcall">
        <thead><tr><th>Director</th>{words.map((w) => <th key={w}>{w}</th>)}{flagged && <th />}</tr></thead>
        <tbody>
          {names.map((n) => {
            const off = isRecused(n) || isAbsent(n);
            return (
              <tr key={n} className={off ? "rollcall-off" : undefined}>
                <td>{n}</td>
                {words.map((w) => (
                  <td key={w} className="num">
                    <input type="radio" name={`vote-${n}`} aria-label={`${n}: ${w}`} checked={!off && votes[n] === w} disabled={!onChange || off} onChange={() => onChange?.({ ...votes, [n]: w })} />
                  </td>
                ))}
                {flagged && <td>{isRecused(n) ? <Badge tone="warn">recused</Badge> : isAbsent(n) ? <span className="muted">absent</span> : null}</td>}
              </tr>
            );
          })}
        </tbody>
      </table>
  );
  if (!result) return table;
  return (
    <div className="rollcall-wrap">
      {table}
      <p className="rollcall-tally" aria-live="polite">
        {result.line}
        {threshold === "two-thirds" && <span className="muted"> Two-thirds of the directors present, or every one of them when fewer than two-thirds of the board is present (CIV 4930(d)(2)).</span>}
      </p>
      {result.recused > 0 && !onFile && (
        <p className="limit">Whether a recused director counts toward the quorum and among the directors present is {NOT_ON_FILE}. The tally is worked both ways; a vote the two readings decide differently is held.</p>
      )}
    </div>
  );
}

export function tally(votes: Record<string, string>): Record<VoteWord, number> {
  const t: Record<VoteWord, number> = { aye: 0, no: 0, abstain: 0, absent: 0 };
  for (const v of Object.values(votes)) if (v in t) t[v as VoteWord] += 1;
  return t;
}
