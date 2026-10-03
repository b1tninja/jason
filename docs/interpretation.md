# Reading the law to give it effect

jason's reading axiom (AGENTS.md, and the manager's base prompt in `jason.community.prompts`). When a provision can be read two ways, prefer the reading that gives it effect over one that makes it void or surplus. Harmonize provisions before finding a conflict. This axiom comes before the other two: "follow what is written, as far as a higher authority allows" applies only to what remains in conflict after a reading that gives each provision effect.

## The statutes (on disk)

`jason export-authorities` keeps the words (`data/authorities`, `Basis.INTERPRETATION`).

| Source | Words | Applies to |
|---|---|---|
| Civil Code 3541 | "An interpretation which gives effect is preferred to one which makes void." | any law or instrument (a maxim) |
| Code of Civil Procedure 1858 | the judge's office is "not to insert what has been omitted, or to omit what has been inserted; and where there are several provisions or particulars, such a construction is, if possible, to be adopted as will give effect to all." | statutes and instruments |
| Code of Civil Procedure 1859 | the intention of the Legislature, or of the parties, "is to be pursued, if possible"; "a particular intent will control a general one that is inconsistent with it." | statutes and instruments |
| Civil Code 1641 | "The whole of a contract is to be taken together, so as to give effect to every part, if reasonably practicable, each clause helping to interpret the other." | contracts, and so the CC&Rs |
| Civil Code 1643 | a contract "must receive such an interpretation as will make it lawful, operative, definite, reasonable, and capable of being carried into effect", if that does not violate the parties' intention | contracts, and so the CC&Rs |
| Civil Code 4215 | a declaration "shall be liberally construed to facilitate the operation of the common interest development, and its provisions shall be presumed to be independent and severable." | the declaration, deeds, and the condominium plan |
| Civil Code 3509 | the maxims "are intended not to qualify any of the foregoing provisions of this code, but to aid in their just application." | the maxims' own limit |
| Civil Code 4205 | "To the extent of any conflict..." the higher authority prevails | what remains after harmonizing |

## The cases

These are as summarized by secondary sources. Read the opinion before citing one to the board or to counsel.

- **Statutes:** *Dyna-Med, Inc. v. Fair Employment & Housing Com.* (1987) 43 Cal.3d 1379.
  - Look first to the words, giving them their usual meaning and significance, if possible, to every word, phrase, and sentence.
  - Avoid a construction that makes some words surplusage.
  - Harmonize statutes on the same subject, both internally and with each other.
  - *In re D.S.* (2012) 207 Cal.App.4th 1088 repeats the rule.
- **Plain meaning first:** *In re W.B., Jr.* (2012) 55 Cal.4th 30. Where the words are clear, the rules of construction are not needed.
- **Avoiding absurdity:** *People ex rel. S.F. Bay etc. Com. v. Town of Emeryville* (1968) 69 Cal.2d 533.
- **The governing documents:**
  - **Read like contracts:** *Chee v. Amanda Goldt Property Management* (2006) 143 Cal.App.4th 1360, 1377. The rules for contracts apply to CC&Rs.
  - **Read for their main purpose:** *Battram v. Emerald Bay Community Assn.* (1984) 157 Cal.App.3d 1184, 1189. Give the CC&Rs a lawful, operative, reasonable construction, and avoid readings that are extraordinary, harsh, unjust, inequitable, or absurd.
  - **Read in context:** *Starlight Ridge South Homeowners Assn. v. Hunter-Bloor* (2009) 177 Cal.App.4th 440, 447. Read provisions in context, not in isolation, and where two inconsistent provisions cover the same matter, the specific controls the general.

## How jason applies it

1. **The text first.** Where the words are plain, they govern, and no canon is needed.
2. **Read to give effect.**
   - Where a provision admits two readings, prefer the one that gives it, and every word in it, effect.
   - Read it with the rest of the document and with the law.
   - A document that asks more than a statute's minimum is not in conflict.
   - A citation to a renumbered statute is read as its successor.
3. **Then the order of authority.** What still cannot be reconciled is a conflict. Follow the provision as far as the higher authority allows (4205), and record a `Conflict` row.
4. **Two readings left.** Name both, say which gives effect and why, and the board asks counsel. Meanwhile, take a course that is lawful under either reading.

## Recite the rule; label the reading

The companion axiom for what jason says, as against how it reads (AGENTS.md). The reading above is how jason works out what a provision means; what it tells a member, the board, a vendor, or counsel starts from the words themselves: agree on the words, then discuss the meaning.

- **The words are common ground.** Two parties who disagree about a provision's meaning can agree on its text once it is recited. A characterization is one party's view and invites the dispute it was meant to settle.
- **Quote, cite, then read.** The operative words, quoted whole with their conditions and exceptions, and the citation (`{QUOTE:key#n}` in a document jason renders, [embedded-references.md](embedded-references.md); `jason cite` or the statute's text on disk otherwise). A reading follows, labeled as a reading and whose: "The board reads this to mean ...".
- **Point to the words that answer.** Reciting is not a way to avoid the question. Courts reject "the document speaks for itself" as a response; say which words decide it.
- **The governing version.** The words in force on the date that matters, from the recorded or adopted copy; jason's consolidated text carries its caveat.
- **Where it applies:** owner notices and letters, violation, hearing, and decision letters, answers to members' requests, board packets, and questions to counsel (which should recite the provisions they ask about).

### Where the idea comes from

| Source | What it says |
|---|---|
| *Non obligat lex nisi promulgata* | A law does not bind unless promulgated: made known to those it governs. |
| Fuller, *The Morality of Law* (1964) | Of his eight principles of legality, the second is that rules be promulgated, and the eighth congruence between official action and the declared rule. |
| Civil Code 4350(a) | An operating rule is valid and enforceable only if "in writing". |
| Civil Code 4360(a) | A rule-change notice "shall include the text of the proposed rule change and a description of the purpose and effect": the text, and then a labeled description. |
| Civil Code 5850(a) | A fine is imposed from a schedule adopted and distributed to each member. |
| Legal writing practice | A contract dispute turns on the precise words, so they are quoted, not characterized; a party may admit a document's text and dispute its meaning, which narrows the dispute. |

The statutes are on disk; the maxim, Fuller, and the writing practice are from secondary sources.

**What it is not.** Reciting decides nothing and settles no dispute about meaning; it fixes what the dispute is about. A provision recited to a member is not legal advice, and a reading that turns on how a court would read it is for counsel.

## Limits

- **Aids, not overrides.** The maxims never override the law (3509), never insert or omit words (CCP 1858), and give way to the drafters' or the Legislature's intent (CCP 1859).
- **Not a license to rewrite.** "Giving effect" never means reading a provision to say what it does not.
  - A restatement that drops words still drops them. If a section once read "leased or rented" and its restatement reads "leased", the restated words are the section.
  - The question is what the remaining words mean.
- **Not legal advice.** A reading that turns on how a court would read the text is for counsel.
