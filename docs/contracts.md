# Contracts: what one is, and how jason reviews one

A contract, like a governing document, says who must do what, for how much, for how long, and what happens when
someone does not. jason reads the association's contracts to find those duties and deadlines. jason is not a lawyer: it
recites the words, labels its readings, and leaves a question of meaning to the board and counsel ("Read the law to give
it effect" in [AGENTS.md](../AGENTS.md)).

The statutes quoted here are on disk (`jason export-authorities`, `data/authorities/CIV`, `data/authorities/CCP`). The
association's own contracts and findings are in its private notes (mystique/notes/contracts.md).

## What a contract is

> "A contract is an agreement to do or not to do a certain thing." (Civil Code 1549)

> "It is essential to the existence of a contract that there should be: 1. Parties capable of contracting; 2. Their
> consent; 3. A lawful object; and, 4. A sufficient cause or consideration." (Civil Code 1550)

> "The consent of the parties to a contract must be: 1. Free; 2. Mutual; and, 3. Communicated by each to the other."
> (Civil Code 1565)

The "valuable exchange" is consideration:

> "Any benefit conferred, or agreed to be conferred, upon the promisor, by any other person, to which the promisor is not
> lawfully entitled, or any prejudice suffered, or agreed to be suffered, by such person, ... as an inducement to the
> promisor, is a good consideration for a promise." (Civil Code 1605)

> "A contract is either express or implied." (Civil Code 1619) "All contracts may be oral, except such as are specially
> required by statute to be in writing." (Civil Code 1622)

**jason's reading:** a signed agreement, an accepted proposal, a signed quote, a vendor's portal checkbox, and an engagement
letter can each be a contract. A proposal nobody accepted is an offer, not a contract. A contract the board makes is an
association record:

> "Executed contracts not otherwise privileged under law." (Civil Code 5200(a)(4))

## How a contract is read

> "A contract must be so interpreted as to give effect to the mutual intention of the parties as it existed at the time
> of contracting, so far as the same is ascertainable and lawful." (Civil Code 1636)

> "The language of a contract is to govern its interpretation, if the language is clear and explicit, and does not
> involve an absurdity." (Civil Code 1638)

> "The whole of a contract is to be taken together, so as to give effect to every part, if reasonably practicable, each
> clause helping to interpret the other." (Civil Code 1641)

> "In cases of uncertainty not removed by the preceding rules, the language of a contract should be interpreted most
> strongly against the party who caused the uncertainty to exist." (Civil Code 1654)

A vendor's printed form is the vendor's words, so an uncertainty left after the other rules is read against the vendor
(1654). Harmonize the clauses before calling them a conflict (1641; [interpretation.md](interpretation.md)).

## What the law limits

> "All contracts which have for their object, directly or indirectly, to exempt any one from responsibility for his own
> fraud, or willful injury to the person or property of another, or violation of law, whether willful or negligent, are
> against the policy of the law." (Civil Code 1668)

> "If the court as a matter of law finds the contract or any clause of the contract to have been unconscionable at the
> time it was made the court may refuse to enforce the contract, or it may enforce the remainder of the contract without
> the unconscionable clause, or it may so limit the application of any unconscionable clause as to avoid any
> unconscionable result." (Civil Code 1670.5(a))

> "... a provision in a contract liquidating the damages for the breach of the contract is valid unless the party seeking
> to invalidate the provision establishes that the provision was unreasonable under the circumstances existing at the
> time the contract was made." (Civil Code 1671(b))

> "In any action on a contract, where the contract specifically provides that attorney's fees and costs, which are
> incurred to enforce that contract, shall be awarded either to one of the parties or to the prevailing party, then the
> party who is determined to be the party prevailing on the contract, whether he or she is the party specified in the
> contract or not, shall be entitled to reasonable attorney's fees in addition to other costs." (Civil Code 1717(a))

> "A written agreement to submit to arbitration an existing controversy or a controversy thereafter arising is valid,
> enforceable and irrevocable, save upon such grounds as exist for the revocation of any contract." (Code of Civil
> Procedure 1281)

> "Within four years: (a) An action upon any contract, obligation or liability founded upon an instrument in writing
> ..." (Code of Civil Procedure 337)

**jason's reading:** whether a particular clause is unconscionable, whether a liquidated sum is reasonable, and whether a
contract may shorten the time to sue are questions for counsel. jason notes the clause and the statute beside it.

## What to read in every contract

| Part | What to find | Watch for |
|---|---|---|
| Parties and authority | Who signs for each side, and the association's exact legal name | A contract in the manager's name, not the association's; a misnamed association; an unsigned copy filed as executed |
| Consideration and price | Every fee: base, per-unit, hourly, per-incident, set-up, and exit | A fee schedule incorporated "as amended" or "then-current," which the vendor can change without the board signing |
| Scope | What is included, and what costs extra | "Services not specifically identified are not included" |
| Term and renewal | Start date, length, and how it renews | A start date left blank; automatic renewal |
| Termination | With cause, without cause, and in the first term | A cure period; a fee or "liquidated damages" for ending early |
| Notice | Who gets it, how it is delivered, and when (see below) | A window with two edges; magic words a notice must contain |
| Money handling | Spending limits, who signs, transfers between accounts | Transfers "without regard to dollar amount" |
| Indemnity and liability | Who protects whom, and caps on what the vendor owes | One-way indemnity; a cap of a few months' fees; no consequential damages |
| Insurance | What each side carries, and who is named | A required broker or program; the vendor as additional insured |
| Dispute resolution | Negotiation, mediation, arbitration, court; governing law and venue | Another state's law; a short deadline to bring a claim; fee shifting |
| Assignment | Whether either side can hand the contract to someone else | "Fully assignable without consent" |
| Restrictive terms | No-hire, exclusivity, confidentiality | A sum owed for hiring the vendor's staff |
| Transition | What the vendor delivers at the end, and by when | Offsets against association funds; records kept as "proprietary" |
| Survival | Which clauses outlive the contract | Indemnity, confidentiality, and no-hire clauses that survive |

## Management agreements: what the Act adds

A managing agent's agreement is a contract with extra statutory duties. The model's checks are in
[document-models/contracts.md](document-models/contracts.md), and the duties sit beside the others in
[community-manager.md](community-manager.md).

- **The statement before signing.** "A prospective managing agent of a common interest development shall provide a
  written statement to the board as soon as practicable, but in no event more than 90 days, before entering into a
  management agreement ..." (Civil Code 5375). It lists owners and officers, licenses, certifications, businesses it has
  an interest in, and referral fees, subdivisions (a) to (e).
- **Conflicts when bidding.** A manager "shall disclose, in writing, any potential conflict of interest when presenting a
  bid for service to an association's board of directors," including referral fees and "ownership interests or
  profit-sharing arrangements with service providers recommended to, or used by, the association." (Civil Code 5375.5)
- **Trust funds and transfers.** "Transfers of funds out of the association's reserve or operating accounts shall not be
  authorized without prior written approval from the board of the association unless the amount of the transfer is less
  than" the thresholds in Civil Code 5380(b)(6). That subdivision applies to an account opened "at the written request of
  the board" under 5380(b). Which account a transfer came from is a fact to find before the statute is applied.

## Notice

Most disputes about leaving a contract are about notice. For every notice clause, write down:

- **The event.** Non-renewal, termination without cause, termination for cause, or a notice of breach that starts a cure
  period.
- **The window.** Count back from the term's end. "At least 60 days but no more than 120 days" has two edges, and a
  notice outside either edge may not count.
- **The delivery.** Personal delivery, overnight courier, certified mail, or mail "with proof of delivery." An email may
  not be the delivery the clause names.
- **The words.** Some forms require a notice to contain stated words ("Written Notice of Breach") before a cure period
  runs.
- **The address.** The notice address in the contract, or the latest one the other side gave in writing.

Keep the notice and its proof of delivery together, as an association record. The lesson is
`notice-window-has-two-edges` (`jason lessons --area contracts`).

## How jason reads a contract

- `jason library` classifies a file as a `contract` or `proposal`; `jason models` reads it into a `Contract` record
  (vendor, signatures, term, renewal, notice, prices, spending limit, and the manager's statement), with findings such as
  `auto-renewal`, `manager-statement-incomplete`, and `transfers-without-approval`.
- MCP: `document_models` with `kind="contract"`, and `library_text` for the words.
- A reading is a lead. A typed fill-in can sit on its own line in a PDF's text, so a start date can read as blank
  (`contract-fill-in-date-misread`). Check a term or notice finding against the page before acting on it.

## Contract terms in the ingestion pipeline

Every contract and proposal that comes through `jason ingest` is read for its terms as soon as it is classified. The same
reader runs on its own as `jason contract-terms`.

```bash
jason contract-terms FILE_OR_DRIVE_LINK                 # the grammar only: fast, on this machine
jason contract-terms --library                          # every contract and proposal in the library
jason contract-terms FILE --model ollama                # a local model reviews the grammar's reading
jason contract-terms FILE --model bedrock --region us-west-2    # Claude on Amazon Bedrock (pip install -e ".[bedrock]")
jason contract-terms --list                             # the saved readings
jason ingest SOURCE --terms-model ollama                # the same review inside ingest
```

**How it reads** (`jason.community.contract_terms`):

1. **Unwrap and split.** A PDF's line wraps are joined so a sentence is one line, and the text is cut at its numbered
   headings ("3.4 Log", "10(b)", a numbered list inside a section).
2. **Parties.** The contract's own definitions name each side ("... (hereinafter "MANAGER")", "(the "Association")"),
   so "Contractor shall" and "Manager shall" both read as the counterparty.
3. **Terms.** The phrase grammar (`jason.community.deontic`, the same one the governing documents use) reads each
   section's duties, prohibitions, permissions, rights, and conditions, with their deadlines, recurrences, and
   conditions. A sentence with no "shall" is kept when its words name a key topic: the term, renewal, the governing law,
   dispute resolution, a fee.
4. **Topics.** `TOPIC_RULES` rows, in order, put each term on a shelf of the checklist above. A new kind of clause is a
   new row.
5. **Particulars and deliverables.** Amounts in cents, a notice window's two edges, and the delivery a notice names. A
   duty the counterparty bears that produces something the association can ask to see (a log, a report, a statement, an
   agenda, records at the end, a certificate) or that has a clock is a **deliverable**.
6. **Findings.** `notice-window`, `notice-delivery`, `no-dispute-clause`, `arbitration` (CCP 1281),
   `shortened-limitations` (CCP 337), `fee-shifting` (CIV 1717), `one-way-indemnity`, `liability-cap` (CIV 1668),
   `liquidated-damages` (CIV 1671), `transfers-without-limit` (CIV 5380(b)(6)), and `one-side-may-change`.

**The model's review** (`jason.community.term_model`). A model reads the sections beside the grammar's candidates. For each
candidate it says whether it is a term, and gives its kind, party, topic, and whether it is a deliverable. It then lists
the terms the grammar missed, such as a "will" sentence or a list item with no verb. Nothing it says is kept unless its
quote is in the text. The prompt names kinds and topics, never a party, a section, or a figure. Two backends answer to
one shape:

- **Ollama** (`--model ollama`): on this machine, under the GPU lock, after `jason.local_ai.preflight`, which fails fast
  when the model will not fit. The default model is jason's (`jason local-ai`); `--model-name` picks another.
- **Bedrock** (`--model bedrock`): Claude through the Mantle client (`anthropic[bedrock]`). The model is
  `anthropic.claude-opus-5-5` unless `--model-name` or `JASON_BEDROCK_MODEL` says otherwise. The region is `--region`,
  `JASON_BEDROCK_REGION`, or `AWS_REGION`. Credentials come from the AWS chain (`--aws-profile`, `JASON_BEDROCK_PROFILE`,
  the environment, or an instance role). jason stores no AWS secret.
  - **It sends the contract's words to AWS.** A person chooses it for a run, and a file the library or ingest marks
    confidential is refused unless `--allow-remote-confidential` is given for that run.
  - A declined request (`stop_reason` "refusal") stops the run with the reason. It is not retried on another model.

**The store.** Each reading is `data/contracts/terms/KEY.json`: the parties, every term with its quote and offsets, the
deliverables, the findings, and what the model dropped and why. It is private, because it quotes the contracts. The
ingest report's "Contract terms" table summarizes each file.

**How far the model is trusted** (`--model-trust`):
- **`fill`** (the default) keeps the grammar's kind, topic, and deliverable flag for every term it read. The model only:
  - adds the terms it found that the grammar missed, each grounded in the text;
  - fills a party the grammar left unstated;
  - drops a sentence without "shall" that it calls no term.
- **`full`** lets the model's kind, party, topic, and deliverable verdicts replace the grammar's, and drop any candidate.
  It is for a model that has measured better than the grammar.
- A batch whose answer is not JSON is asked once more, then keeps the grammar's reading.

**Measured so far** (docs/document-tools.md, Model trials):
- The grammar alone reads a 14-page management agreement in under a second.
- `qwen3.5:9b` took 7 minutes 35 seconds on the same agreement.
  - It added a few real terms the grammar missed.
  - It invented 20 clauses that are not in the contract, every one dropped by the quote check.
  - Its edits to the grammar's fields were right and wrong about equally, hence `fill`.
- Claude on Bedrock and the 27B local model have not been tried yet.

## Parties and licenses

**Who the parties are** (`contract_terms.defined_parties`, `counterparty_name`):
- **Defined terms.** "... (hereinafter "MANAGER")" names a side. A name is cut at the parties clause and any sentence
  run into it ("Extra Work. Owner agrees to pay Example Company" is "Example Company").
- **"We" and "you".** A form written to the reader reads its own definition ("'we,' 'us' and 'our' mean ..."). Where
  there is none, "we" is the vendor whose form it is and "you" the association.
- **Short forms.** A firm's initials ("T.E.S.C." for "The Example Sprinkler Company") and its distinctive first word
  are its words too, when the text uses them. A common word ("North", "Pacific") is never taken alone.
- **"Will".** In a contract, "<party> will ..." is a promise and "<party> will not ..." a prohibition, when the subject
  is one of the parties. "This proposal will expire" promises nothing. The governing documents keep the grammar's
  narrower rule.
- **The counterparty's name, best evidence first:** the holder of a license the document prints; a defined party's
  company name; a labeled blank ("Contractor: ..."); the letterhead. The letterhead is the first business name in the
  opening, or a short title-case line followed by an address.
  - Skipped: the association, a customer ("Bill To", "c/o"), a form word ("Initial", "President"), an insurer or surety,
    and a service the contract names ("arbitration conducted by Example Dispute Resolution Services, Inc.").
- **Repeats.** A document that carries the contract twice (a copy and the signed copy) gives each term once.
- **Role and passive readings** apply only in the counterparty's own form, one where no side is defined as the
  association. Each is labeled on the term as a reading for a person to confirm.
  - A sentence about the counterparty's service ("the inspection will comply with ...", "All inspections will be
    performed ...") is the counterparty's. One about a person at the customer's premises ("a responsible adult must be
    present") is the association's.
  - A passive duty ("System(s) shall be inspected ...", "Debris will be removed ...") is the counterparty's work.
  - A party as the subject of a passive is acted on, not promising: "Contractor will be paid" binds no one to anything.
- **Other names** (`party_aliases`): a dba ("Example Holdings Inc. dba Example Home Services"), a parenthetical short
  form ("(EHS)"), and a role label alone on its line ("CUSTOMER:", "EXAMPLE CAMERAS:") are the party's words too. A
  company suffix's period ("Inc.") does not end the subject of a "will" sentence.
- **Role labels.** The lines under a label belong to its party: a term read there with no party takes the label's, and
  an order with no subject ("Provide access to each location.") is that party's duty. A line that opens with "If",
  "When", or its own subject is read by its own words.
- **Column artifacts.** A section number a two-column layout drops between two lowercase words ("including our 3.1. yard
  signs") is removed, not read as a heading. A cited number ("under Section 3.1") is kept.
- **Page noise** (`page_noise.strip_noise`) is removed before reading: an e-signature audit trail, page numbers, and
  running headers and footers (kept once). The reading records what was removed. Licenses are read from the whole text.
- **Statutory notices** (`statutory_notices`): the mechanics lien warning, the CSLB information, the right to cancel,
  and the other notices BPC 7159 makes a home improvement contract print. Terms inside one go on the statutory notice
  topic as the Legislature's words, never a promise or a deliverable. A `statutory-notice` finding names each one with
  its authority.
- **Title 19 deliverables** (`fire_protection`): in a fire protection contract, one that names sprinklers, a fire alarm
  or pump, a standpipe, NFPA 25, or Title 19, a duty matching the State Fire Marshal's rules is the vendor's
  deliverable, with the rule's authority on the term. The rules cover the report to the owner and the fire authority,
  the forms, the itemized invoice, an estimate before repairs, and the tag. A passive one ("shall be properly tagged")
  is the vendor's, because the regulation, not the sentence, names who does it.

**Qualifiers on a term.** Each is a table of rows in its own module. A term's reading names which row matched.
- **Topic phrases** (`topic_phrases`) come before the word rules. "materially breaches this Agreement" is breach and
  cure, and "made this ___ day of" names the parties. A veto row keeps a word from its usual topic: "trees ... breach
  the safety height" is not breach and cure.
- **Exemptions** (`exemptions`) are their own kind. "not obligated", "not responsible", "no warranty", "as is", "limited
  to", and "excluded" release a party; they are not prohibitions. A sentence that releases one thing and binds another
  ("..., but Contractor shall keep the site clean") stays a duty. The items under an "Exclusions:" heading are listed
  on the reading. A counterparty's release is a `counterparty-exemption` finding.
- **Discretion** (`discretion`) is the room a term leaves its holder.
  - The degrees: unfettered ("sole discretion"), bounded ("reasonable discretion"), and judgment ("deems").
  - Approval-gated, and permission without duty ("may, but is not obligated to").
  - An effort standard ("best efforts", "endeavor"), a quality standard ("workmanlike"), and a one-side or mutual
    change.
  - The findings: `vendor-one-side-change` for a counterparty's change to the price, fees, scope, or terms, or ending
    at will. `vendor-unfettered` for its sole discretion over price, fees, or scope. `effort-standard` for an effort
    promised in place of a result.
- **Incorporated standards** (`incorporated_standards`): a code brought in by a cue ("in accordance with NFPA 25",
  "per Title 19"). The work is measured against it, so the edition matters (`incorporates-standard`). A bare name with
  no cue is a mention, not an incorporation, and a city's "Title 19" is not the state's.
- **Checked options** (`checked_options`): the options a proposal offers and whether its own line marks each one. A
  mark that the text layer puts elsewhere belongs to an option only by its place on the page. Such an option is left
  unread (`options-not-read`), never guessed. A signature block's blank ("(print name)") is not an option.

**Licenses** (`jason.community.licenses`, `jason licenses`):

| Board | What it reads | Where to check |
|---|---|---|
| Contractors State License Board | "Contractor's License #", "CA State License #", "CSLB #", a class first ("C-10 123456"), a class after ("123456-B") | the license's own CSLB page |
| Another state | "AZ ROC Lic. CR-11 #123456" | that state's board |
| Bureau of Security and Investigative Services | an alarm company operator ("ACO 1234"), a private patrol operator ("PPO") | DCA license search |
| Structural Pest Control Board | "License PR1234", "OPR" | DCA license search |
| Department of Real Estate | "DRE License #01234567" (seven or eight digits; a bank line's "DRE 703 ..." is not one) | the license's own DRE page |
| Department of Insurance, State Bar, NMLS, DFPI | an agent's license, a Bar number, an NMLS id, an escrow license | each board's search |
| Accountancy, engineers, architects | a CPA or firm license, "R.C.E. 12345", an architect's "C-12345" | DCA license search |
| Department of Industrial Relations | a public works contractor registration ("DIR #1000012345") | DIR's registration search |
| Notary, certification | a notary's commission, a CCAM or CMCA registration | kept apart: they name people |
| No board named | "License #123456" | likely CSLB; resolved when the same number is printed with its board elsewhere |

- **The holder** is the business named beside the mention, on its own page. A name before the mention can be some
  distance up (a letterhead), and one after it only on the same or the next line.
  - A name given as the customer anywhere in the text is never the holder.
  - With nothing near, the page's letterhead is used.
  - A packet (a month's report with its invoices, kept as pages) never lends one page's name to another, and a long
    packet with no page breaks lends none.
  - A number whose holder is only in a logo stays unattributed.
- **Each reading** carries its licenses: the contract's Parties section, a `license-printed` finding with the board's
  page, and `license-holder-differs` when a license sits beside someone other than the counterparty (a subcontractor,
  an affiliate, or a misread).
- **The register.** `jason licenses --library` sweeps every library file into `data/parties/licenses.json`: each license
  with its holder, board, class, jurisdiction, documents, and where to check it. Ingest's `licenses` reader lists each
  new file's licenses.
- jason reads the number. Whether the license is current, its classes, its bond, and its discipline are the board's
  record, checked on its page.

## What jason does not do

- jason does not sign, accept, renew, or end a contract, and does not send a notice. A person does, on the board's
  decision.
- jason does not give legal advice. It recites the contract and the statute, labels its reading, and names the question
  for counsel.
