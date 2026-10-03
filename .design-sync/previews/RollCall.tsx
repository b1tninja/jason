import { useState } from "react";
import { RollCall, tally } from "jason-ui";

const directors = ["Alvarez (President)", "Chen (Treasurer)", "Okafor (Secretary)", "Patel", "Reyes"];

function Controlled({ initial }: { initial: Record<string, string> }) {
  const [votes, setVotes] = useState(initial);
  const t = tally(votes);
  return (
    <div>
      <RollCall directors={directors} votes={votes} onChange={setVotes} />
      <p className="muted">
        {t.aye} aye · {t.no} no · {t.abstain} abstain · {t.absent} absent
      </p>
    </div>
  );
}

/** Five directors with no votes marked yet: every radio empty, the tally all zeros. */
export const Open = () => <Controlled initial={{}} />;

/** A motion that carried four to one, with the tally line the decision card prints under the table. */
export const Carried = () => (
  <Controlled initial={{ "Alvarez (President)": "aye", "Chen (Treasurer)": "aye", "Okafor (Secretary)": "no", Patel: "aye", Reyes: "aye" }} />
);

/** One director absent and one abstaining: the words each have a column. */
export const Mixed = () => (
  <Controlled initial={{ "Alvarez (President)": "aye", "Chen (Treasurer)": "abstain", "Okafor (Secretary)": "aye", Patel: "absent", Reyes: "no" }} />
);

/** Read only, as a recorded decision shows it: no onChange, so every radio is disabled. */
export const Recorded = () => (
  <RollCall directors={directors.slice(0, 3)} votes={{ "Alvarez (President)": "aye", "Chen (Treasurer)": "aye", "Okafor (Secretary)": "aye" }} />
);
