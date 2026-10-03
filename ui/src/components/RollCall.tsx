export type VoteWord = "aye" | "no" | "abstain" | "absent";
export const VOTE_WORDS: VoteWord[] = ["aye", "no", "abstain", "absent"];

/** Each director's vote, one row per director; unmarked rows count as nothing until marked. */
export function RollCall({ directors, votes, onChange }: { directors: readonly string[]; votes: Record<string, string>; onChange?: (next: Record<string, string>) => void }) {
  const names = [...new Set([...directors, ...Object.keys(votes)])];
  return (
    <table className="rollcall">
      <thead><tr><th>Director</th>{VOTE_WORDS.map((w) => <th key={w}>{w}</th>)}</tr></thead>
      <tbody>
        {names.map((n) => (
          <tr key={n}>
            <td>{n}</td>
            {VOTE_WORDS.map((w) => (
              <td key={w} className="num">
                <input type="radio" name={`vote-${n}`} aria-label={`${n}: ${w}`} checked={votes[n] === w} disabled={!onChange} onChange={() => onChange?.({ ...votes, [n]: w })} />
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function tally(votes: Record<string, string>): Record<VoteWord, number> {
  const t: Record<VoteWord, number> = { aye: 0, no: 0, abstain: 0, absent: 0 };
  for (const v of Object.values(votes)) if (v in t) t[v as VoteWord] += 1;
  return t;
}
