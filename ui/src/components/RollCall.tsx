import { Badge } from "./Badge";

export type VoteWord = "aye" | "no" | "abstain" | "absent";
export const VOTE_WORDS: VoteWord[] = ["aye", "no", "abstain", "absent"];
/** The answers in a roll call by name (CIV 4926(a)(3)); absence is attendance, not a vote. */
const ROLL_WORDS: VoteWord[] = ["aye", "no", "abstain"];

export type Threshold = "majority" | "two-thirds";

export interface OutcomeOptions {
  /** The directors in the meeting; drives the quorum line and who must answer. Defaults to everyone who voted. */
  present?: readonly string[];
  /** Interested directors: shown "recused", counted toward the quorum, never toward the vote (Corp. Code 7233; CIV 5350). */
  recused?: readonly string[];
  /** A majority of the directors present, or two-thirds of them for an off-agenda emergency item (CIV 4930(d)(2)). */
  threshold?: Threshold;
  /** Seats on the board: under CIV 4930(d)(2), fewer than two-thirds of them present means every director present must agree. */
  seats?: number;
}

export interface Outcome {
  yes: number; no: number; abstain: number; recused: number;
  /** The directors who may vote: present and not recused. */
  voters: string[];
  needs: number;
  /** Every voter has answered. */
  answered: boolean;
  state: "open" | "carries" | "fails";
  /** "Yes 3 · No 0 · Abstain 0 · Recused 1. Needs 3 yes. Carries." */
  line: string;
}

/** The roll call as it stands, by the rules above. Pure: the same votes and options always give the same answer. */
export function outcome(votes: Record<string, string>, opts: OutcomeOptions = {}): Outcome {
  const recusedAll = opts.recused ?? [];
  const present = opts.present ?? Object.keys(votes);
  const recused = recusedAll.filter((n) => present.includes(n));
  const voters = present.filter((n) => !recused.includes(n));
  const count = (w: VoteWord) => voters.filter((n) => votes[n] === w).length;
  const yes = count("aye"), no = count("no"), abstain = count("abstain");
  // Counted against the directors present (Corp. Code 7211): a recused director is present and casts no vote (7233), so the
  // motion must carry without them.
  let needs = present.length ? Math.floor(present.length / 2) + 1 : 0;
  if (opts.threshold === "two-thirds" && present.length) {
    const enoughOfBoard = !opts.seats || present.length >= Math.ceil((2 * opts.seats) / 3);
    needs = enoughOfBoard ? Math.ceil((2 * present.length) / 3) : present.length;
  }
  const answered = voters.length > 0 && voters.every((n) => ROLL_WORDS.includes(votes[n] as VoteWord));
  const state: Outcome["state"] = !answered ? "open" : yes >= needs ? "carries" : "fails";
  const line = `Yes ${yes} · No ${no} · Abstain ${abstain} · Recused ${recused.length}. Needs ${needs} yes. ${{ open: "Vote open.", carries: "Carries.", fails: "Fails." }[state]}`;
  return { yes, no, abstain, recused: recused.length, voters, needs, answered, state, line };
}

/** Each director's vote, one row per director; unmarked rows count as nothing until marked.
 * With `present`, `recused`, or `threshold` given it is a roll call by name: a recused director's row reads "recused" with
 * its radios off, an absent director's reads "absent", and a tally line says what the motion needs and whether it carries.
 * Without them it renders exactly as before. */
export function RollCall({ directors, votes, onChange, present, recused, threshold, seats }: {
  directors: readonly string[]; votes: Record<string, string>; onChange?: (next: Record<string, string>) => void;
  present?: readonly string[]; recused?: readonly string[]; threshold?: Threshold; seats?: number;
}) {
  const extended = present !== undefined || recused !== undefined || threshold !== undefined;
  const names = [...new Set([...directors, ...Object.keys(votes)])];
  const words = extended ? ROLL_WORDS : VOTE_WORDS;
  const here = present ?? names;
  const isRecused = (n: string) => (recused ?? []).includes(n);
  const isAbsent = (n: string) => extended && present !== undefined && !present.includes(n);
  const result = extended ? outcome(votes, { present: here, recused, threshold, seats }) : null;
  const table = (
      <table className="rollcall">
        <thead><tr><th>Director</th>{words.map((w) => <th key={w}>{w}</th>)}{extended && <th />}</tr></thead>
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
                {extended && <td>{isRecused(n) ? <Badge tone="warn">recused</Badge> : isAbsent(n) ? <span className="muted">absent</span> : null}</td>}
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
    </div>
  );
}

export function tally(votes: Record<string, string>): Record<VoteWord, number> {
  const t: Record<VoteWord, number> = { aye: 0, no: 0, abstain: 0, absent: 0 };
  for (const v of Object.values(votes)) if (v in t) t[v as VoteWord] += 1;
  return t;
}
