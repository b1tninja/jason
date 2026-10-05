# Rule authority: who may make the association's rules

This page is the profile's note for `jason rules` ([docs/rule-authority.md](../../docs/rule-authority.md): the method and its measurements). It says which of this association's documents were read, what the grants are by section, and how the subjects stand against the rules on file. It names no owner, party, or figure. The words recited, the table of rules by section, and the findings for the board are in `mystique/notes/rule-authority.md`, which git ignores.

## What was read

- **The grants and limits** were searched in the CC&Rs (outline key `ccrs`), the Bylaws (`bylaws`), the second and third amendments, the Owner's Manual (`owners-manual`), the parking rules, the Election Rules, the Enforcement Policy, the Collection Policy, and the ALPR policy. Resolutions and annexations were not (they record acts, not powers).
- **The rules on file** are the sections of those that state a norm. In the Owner's Manual only the parts `jason manual` classifies as rules and policies count (`mystique/manual.py`: the rules book, the discipline book, the collection book, the architectural book); the guide's own words never count. When a document-segmentation reader exists, its parts replace the manual rows as the source of `RulePart`.
- **The readers:** the rules' reading, and qwen3.5:9b on the local Ollama (October 5, 2026), over 83 candidate sentences. Measured on 82 labeled candidates: grants found by the rules alone P 1.00, R 0.74; the model P 0.84, R 0.84; the readings both made were all right (23 of 23).

## The grants, by section

| Where | Holder | Subjects | Read by |
|---|---|---|---|
| CC&Rs 2.5 | board | general (management and operation); its scope sentence lists the common area, signs, refuse, maintenance standards, parking, leasing, pets | both |
| Bylaws 8.2 | board | general (administration, management, operation, use, occupancy) | both |
| CC&Rs 3.3(a) | board | common area (guests, hours, group activities, parking) | both |
| CC&Rs 4.5 | board | unpowered wheeled equipment | both |
| CC&Rs 4.8 | board | signs | both |
| CC&Rs 4.10(b) | board | trash containers | both |
| CC&Rs 4.11(a)(i) | board | temporary use and parking of otherwise prohibited vehicles | both |
| CC&Rs 4.11(g) | board | vehicles and parking | both |
| CC&Rs 4.14(c) | board | pets | both |
| CC&Rs 4.16 | board | personal property on a porch or patio | both |
| CC&Rs 10.6 | board or a committee it appoints | disciplinary procedures | both |
| Bylaws 8.2(d) | board | emergency rule changes | both |
| Election Rules 7 | board | amending the Election Rules | both |
| Owner's Manual B-7(a) | board | amending the barbecue regulation | both |
| Bylaws 8.5(a) | board | fines (a power to establish and impose them under a schedule the board adopts) | model only |
| Election Rules 2.2 | board | the polling period for other votes | model only |

Delegations the rules cannot find and the model found only in part: the number of pets (CC&Rs 4.14(a)) and the time limit for speaking (Bylaws 4.4, 7.7) were read as no by the model, and are in the private notes as findings for the board. The limits are Bylaws 8.2(a) to (j), which repeat the statute's notice, decision, delivery, emergency, and reversal steps, with a 30-day notice where the statute says 28.

## The subjects

- **Authority named, rules on file:** common area, separate interest (porch and patio), parking, vehicles, pets, trash, signs, discipline, elections, insurance (the barbecue regulation), leasing (named only in the scope sentence of CC&Rs 2.5), and, by Bylaws 8.5(a), fines.
- **General power only, rules on file:** registration, architecture, noise, assessments, disputes, meetings, maintenance.
- **General power only, no rules on file:** records.
- **A subject with a named grant and no rule found that uses it:** unpowered wheeled equipment; a determination of the number of pets; a time limit for speaking; the polling period.

## Civil Code 4355, as a labeled reading

Listed: common area, separate interest, architecture (and the review procedure), fines, discipline, disputes, elections. Depends on whether the rule governs the common area or a unit, so two readings remain and counsel reads them: parking, vehicles, pets, noise, trash, signs, registration. Leasing: two readings. Not listed: meetings, records, insurance. Maintenance of the common area is out of 4360 and 4365 by 4355(b)(1). The Bylaws repeat 4355(a)'s seven subjects as the matters their rule-change procedure covers (8.2(i)).

## For the board

1. Read the findings in the private notes and confirm or reject each reading (`jason rules --review ID`).
2. Decide whether to write the determinations the documents delegate to the board: the number of pets, the speaking time limit, the polling period, and whether unpowered wheeled equipment needs a rule. A determination on a subject 4355(a) lists takes `jason rule-change`.
3. Ask counsel the two open readings: whether the Bylaws' reversal procedure carries 4365(a)'s five percent, and which side of 4355(a) each depends-on-use subject falls.
4. The manual's guide says 28 days' notice of a proposed rule change; the Bylaws say 30. The guide is guidance and does not change the Bylaws; it should say which it follows.

## Follow-ups for the profile (not made here)

- The collector reads the Owner's Manual and the parking rules document separately, so a parking rule appears under both. When the segmentation reader maps the parking rules document as a part of the manual, the duplicate folds.
- No profile row was added: the grants are readings in `data/rules/authority.json`, and a person's confirmation is the only path to a rule row.
