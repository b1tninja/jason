# The words, and readings of them

**Status:** built, October 4, 2026: step 4 of [ingestion-and-review.md](ingestion-and-review.md) and the authorities part of item 3 in [rag-roadmap.md](rag-roadmap.md). No reading is recorded yet; the profile's are for a person to add. The words in force on an earlier day ([below](#the-words-in-force-on-a-day)) are built too; the earlier versions come onto the disk when a person runs `jason law-history --versions`.

jason keeps the body of authorities (the words) apart from readings of them (what someone takes the words to mean). A reading is tied to a digest of the exact words it read. When the words change, the reading is stale, and it is never shown in place of the words.

The axioms behind it are in [AGENTS.md](../AGENTS.md): "Recite the rule; label the reading" and "Read the law to give it effect". The canons are in [interpretation.md](interpretation.md).

## The words

### A section's digest

A statute's section is the body under its `## CITATION` heading on a page of `data/authorities`, split as `context_pack.law_corpus` splits it.

- **Its words** are that body with line endings and trailing spaces normalized, less jason's own `- History:` note. The note comes from the law history, not from the Legislature.
- **Its digest** is the SHA-256 of those words (`jason.community.law_text.words_digest`).
- **The page's header is outside every section.** A new session label, a new reason jason holds the page, or a new History note changes no digest. Only the words do.
- **The manifest records them.** Each page row carries `digests`: `[citation, digest]` for each section, in the page's order. `jason export-authorities` writes them; `jason export-authorities --digests` writes them for the pages already on disk without asking lawlibrary.

### History

`jason export-authorities` overwrites the pages. Before it does, it reads every section on the shelf; after, it compares, all under the shelf's store lock.

- **A section whose words changed keeps its replaced words:** `data/authorities/history/<citation>/<digest>.md`, with the source line and session it carried.
- **The change is logged:** a row in `data/authorities/changes.json` with the citation, the old and new digests, the day, and the old and new source lines.
- **A section that leaves the shelf is kept the same way,** with no new digest.
- **The history is not searched as the law.** The passage index leaves `history/*/*` out.
- **The same folder holds a section's earlier versions,** each with the range it was in force ([The words in force on a day](#the-words-in-force-on-a-day)).

Two files share a name. `data/authorities/changes.json` is jason's log of its own shelf. `data/authorities/history/changes.json` is the Act's amendment history from lawlibrary (`jason law-history`). The first says when jason's copy changed; the second says when the law did.

`data/` is not in git. Back up `data/authorities/history` (with its `versions.json`) and `changes.json` with it.

### Reading the words

| Function (`jason.community.law_text`) | Gives |
|---|---|
| `section_digest(citation, data_dir)` | the digest of the words on disk now, or `None` |
| `law_text(citation, data_dir, digest=None)` | the current words, or with `digest` the words that have it: current, else from the history |
| `law_text(citation, data_dir, as_of=day)` | the words in force on that day, or `None` when the disk does not show which they were |
| `in_force(citation, data_dir, day)` | the same, with how it is known, the deciding words, and the caveats |
| `versions(citation, data_dir)` | every text the shelf holds under the citation |
| `history_texts(citation, data_dir)` | the words the history holds: those exports replaced, and the earlier versions, each with its range where one is recorded |
| `version_ledger(data_dir, citation)` | what `jason law-history --versions` recorded for the section |
| `own_operative(words)` | the operative days a section's own words state, each with its sentence |
| `changes(data_dir, citation="")` | the shelf's change log |

These read the disk only. A section that is not on the shelf is a miss; nothing is fetched.

### Two versions under one number

The Legislature's publication prints some sections twice under one number: one version in effect until a day, the other operative from it. The shelf holds both, and the backfill lists them (six sections on October 4, 2026).

- `versions` gives each, with its own digest, in the publication's order. That is not the order they operate in: for one of the six the version printed first is the one not yet operative.
- `law_text` and `section_digest` give the first.
- `authority_text` (and through it `jason cite`, the packets, and the notices) quotes the version in force today where the versions' own words say which; where they do not, the first.
- `recite` with no day gives every version, with a caveat.
- `recite` with a day picks by the versions' own words, where they state them, and quotes the sentences that decide it: "This section shall remain in effect only until January 1, 2031, and as of that date is repealed" against "This section shall be operative January 1, 2031". The other version is named in a caveat with its digest.
- Only a sentence whose subject is the section is read. "The amendments made to this section ... shall become operative on" speaks of an amendment and decides nothing.
- Where the versions' own words state no day, both are recited and nothing is picked. jason never picks by position.

## The words in force on a day

A review of an older letter recites the words in force on the letter's day (AGENTS.md, "Recite the version that governs"). The shelf holds one edition, so the earlier words are kept beside it, each with the range it was in force.

### What lawlibrary holds (found October 4, 2026)

lawlibrary keeps the Legislature's session publications on its own disk, one per two-year session. No internet is used: the fetch reads that local shelf.

| Question | Answer |
|---|---|
| A section's earlier words | Yes, for every California code the shelf holds, as each session publication from 2011 printed it: 2011, 2013, 2015, 2017, 2019, 2021, 2023, and 2025. |
| Before the 2011 publication | No. The publications from 1989 to 2009 carry bills, not code sections. The 2011 one shows the words as last amended before it, with that act's day when the note names one. |
| Operative days | Yes. Each row carries the Legislature's history note: the act, "Effective", "Operative", "Repealed as of", "Inoperative", "Superseded on". lawlibrary reads the note into days. |
| Two versions in one publication | Yes, both rows, each with its own note. |
| A version by a named act | Only as far as a publication printed it. A note names the latest act, so an act a later one overwrote between two publications is not there. |
| The chaptered bill's own text | Not as a section. lawlibrary indexes bills only for the 1989 to 2009 sessions, as whole measures; from 2011 it reads the code tables. Nothing extracts one section's text from a chaptered bill. |
| A repeal | It leaves no note. The section is absent from the next publication. The day is known only where the Act's history names the repealing act (the 2014 recodification). |

### The version store

`jason law-history --versions` (`jason.tasks.statute_fetch.prior_versions`) asks lawlibrary once for every row each publication prints for the sections named, and keeps what it finds under the shelf's store lock.

- **An earlier version is a history file:** `data/authorities/history/<citation>/<digest>.md`, beside the words exports replaced. Its header gives the source (which publications printed it), the act that made it, the Legislature's note, `From`, `Until`, and what ended it.
- **Words an export replaced keep their file.** The fetch records the range on it and leaves the header it carried.
- **The current words are not written again.** The day they came into force goes in the ledger, `data/authorities/history/versions.json`, with every version's digest, act, and range.
- **Rows with the same words are one version.** Its digest is taken over the same words a shelf page holds, so the newest version's digest is the shelf's.
- **Nothing is written for a section no publication prints.** That is a miss with its reason.

### The range

| Line | Where it comes from |
|---|---|
| `From` | The latest of the note's effective day, its operative day, and the operative day the section's own words name. An amendment is not in force before its act takes effect. |
| `From: not recorded` | The note names no day ("Enacted 1872"). When the act is older than the first publication on the shelf and that publication printed the words, `Printed by` gives the first day of its session: the publications show the words as the section's by then. |
| `Until` | The day the next version came into force: the earliest later `From` among the versions the next publication prints. |
| `Until`, sooner | The version's own end: "Repealed as of", "Inoperative", "Superseded on" in the note, or its own words. |
| `Until`, before `From` | The words never operated: an act took effect before their operative day. They are kept and never picked. |
| `Until: not recorded` | The next publication prints the section under the same act with other words (a reprint or correction); or the section is absent from it and no repeal day is known; or the next notes name no later day. |

A day that is not recorded stays not recorded. jason infers none.

### Which words `recite` gives for a day

`in_force` decides, from the disk only, in this order:

1. **An earlier version whose recorded range holds the day** (`prior`). It is recited with its range, the act that made it, what ended it, and its source, and a caveat that these are not the words on the shelf now.
2. **The words on the shelf now** (`current`), where a record places them in force by that day: the ledger's day, the section's own operative words, or, for a day on or after the export, the publication itself.
3. **Of two versions under one number, the one their own words pick** (`own_words`).
4. **Otherwise nothing is picked** (`not_shown`). The words on the shelf now are recited, the recital says plainly that they are not shown to be the words of that day, and the caveats say what is missing and what would bring it. `Recital.in_force` is false and `law_text(as_of=)` is `None`.

- **Identical words under two credits are one.** The publications print some sections twice with the same words, each added by its own act ("See identical section added by ..."). Either is recited, with a caveat.
- **Two different versions whose ranges both hold the day** are not chosen between. Both are named for a person to read.
- **A reading is checked against the words of that day.** A reading of the earlier words applies on a day in their range, and is stale against the shelf now.
- **`jason cite` uses the same decision.** `CIV 5855@2022-03-01` gives the words of that day, or the miss `edition_not_held` with what would bring them.

### A version added by hand

A person adds a version the publications do not hold: the words from an official source, with the citation a reader can check.

```bash
jason law-history --add-version words.txt --citation CIV-9901 --source "Statutes of 2009, chapter 1, section 2" \
    --by "A. Person" --from 2010-01-01 --until 2012-01-01 --act "Stats. 2009, Ch. 1, Sec. 2"
```

- The file holds the section's words only, as the source prints them.
- `--source` and `--by` are required. A day left out is not recorded, and a version with no recorded end is never picked.
- The file may also be written by hand into the section's history folder, under any name ending `.md`: the header lines `- Source:`, `- From:`, `- Until:`, `- Act:`, `- Added by hand:`, then `## CITATION` and the words.
- A recital of a hand-added version says so, with who added it and when.

### The gap (October 4, 2026)

What the disk still cannot show, and what would fill it:

| Missing | Why | What fills it |
|---|---|---|
| Words in force before the 2011 publication's | lawlibrary's earlier publications carry bills, not code sections | A person adds the version by hand from the Statutes or the Legislature's site |
| An act a later one overwrote between two publications | A note names only the latest act | The same, or a reader in lawlibrary that takes a section's text from the chaptered bill |
| The day a reprint under the same act replaced an earlier print | Both prints credit the same act | Nothing on the shelf; the prints differ in a credit line or a space |
| The day a section was repealed, outside the 2014 recodification | A repeal leaves no note | A person records `Until` in the file's header |
| Regulations and federal law | lawlibrary's California shelf holds the codes only | A person adds the version by hand |

When a recital's day falls after the last publication that printed the words and before the next act jason knows, it carries a caveat: an act between the two would not show.

## A reading

A `LawReading` (`jason.community.law_readings`) is one answer to one question about the words.

| Part | What it holds |
|---|---|
| `key` | its name |
| `provisions` | each provision it reads, as `Provision(citation, digest)`: the digest of the words it read |
| `question` | what was asked of the words |
| `standing` | `PLAIN`, `READING`, or `TWO_READINGS` |
| `reading` | the reading in a sentence; empty for `PLAIN` and `TWO_READINGS` |
| `canon`, `authority` | the rule of construction (`Canon`, each with its statute) or the authority it rests on |
| `whose`, `dated` | `BOARD`, `COUNSEL`, or `JASON` (a lead only), and the day |
| `alternatives` | for `TWO_READINGS`, both readings; the record prefers neither |
| `quote` | the words that answer, verbatim from a provision it reads |
| `board_item` | the board item that follows it |

- **Plain words need no reading.** A `PLAIN` record carries no reading text. It quotes the words that answer.
- **A reading names what it rests on.** A `READING` without a canon or an authority is refused.
- **Two readings stay two.** The board asks counsel.
- **A provision is a statute's section or a governing document's.** "CIV 5855", or the document's key and section as a reference names it, "bylaws#7.2". A governing section's words and digest come from the same reader `{QUOTE:key#n}` uses, so its digest is the one `jason cite` shows.
- **A digest may be shortened.** Its first 12 characters or more are enough.

### Whose readings

- **The board's and counsel's readings are profile data:** `Community.law_readings()`, empty by default.
- **jason never makes a reading up.** It records one a person gave. A row whose `whose` is `JASON` is a lead for a person to confirm or reject, and is labeled so wherever it is shown.

### The staleness rule

`status(reading, data_dir)` compares each provision's digest with the words on disk.

| State | When | Applied |
|---|---|---|
| current | every provision's digest matches the words on disk | yes, as a reading |
| stale | a provision's words changed; the status names it, with the digest read and the digest now | no |
| missing | a provision is not on the shelf | no |
| misquoted | the words the record quotes are not in a provision it reads | no |

A stored reading gets no deference. It is checked each time it is used. A stale reading is redone or confirmed by a person against the words now on disk, and its row then carries the new digest.

## Reciting

`recite(citation, data_dir, readings, as_of=None)` is what a review or an answer calls.

1. **The words first:** verbatim from the shelf, with their source line and digest.
2. **Then each current reading,** labeled with whose it is, its standing, and its date: "The board reads this to mean ...".
3. **Stale ones apart,** as stale, never as the reading.

With no reading stored, the words stand alone.

With `as_of`:

- **A reading dated later is set apart.**
- **A statute's words are the words in force on that day,** where the disk shows which they were ([Which words `recite` gives for a day](#which-words-recite-gives-for-a-day)). The recital says "In force on DAY:" with the range, the act, and the source.
- **Where the disk does not show it,** the words on the shelf now are recited under "Not shown to be in force on DAY:", with what is missing. `Recital.in_force` is false. Nothing is guessed.
- **A governing document's section** is its words on that day when the document is kept as amended, as before.

`recite` returns a `Recital`. `Recital.lines()` is the text, and `as_dict()` the same as data (`inForce`: whether shown, how decided, the basis, and the deciding words).

## Checking an answer's quotations

A search returns passages, and the client writes the answer. `jason.community.quote_check.check(answer, data_dir, sources="", include_confidential=False)` reads the answer and says whether each quotation is the stored words. The MCP tool is `verify_quotes`; the command is `jason verify-quotes FILE`.

**What it reads as a quotation.** Text in double quotation marks, straight or curly, and a block quote (lines that open with `>`). One shorter than four words is listed and not checked. Single quotation marks are not read.

**The verdict for each quotation:**

| Verdict | When |
|---|---|
| `FOUND` | the words are in a stored text: `exact` (character for character) or `normalized` (the same after folding) |
| `ALTERED` | no stored text has the words, and one has nearly those words; the stored words are shown beside the quoted ones, each difference marked `[[so]]` |
| `MISATTRIBUTED` | the answer attributes the quotation to one section, and the words are stored only somewhere else |
| `NOT FOUND` | no stored text has the words or nearly the words |

- **Folding** is the normalization `prompts.verify` uses (`questions._norm`: whitespace, quote marks, capitalization), with two additions: a hyphen between letters (a word broken at a line's end) and Markdown's emphasis marks are dropped.
- **An ellipsis is allowed** when each part is found, in order, in one passage or section. Parts stored in separate places are `ALTERED`: the quotation joins them.
- **A near match** shares at least three quarters of the quotation's words in order (`NEAR`).

**Where it was found matters.** Each place names its file, section, passage, catalog, and standing.

- **A page or a reference is not the record or the law.** Words found only in a page jason generated, or only on the reference shelf, carry a warning.
- **A confidential file is held back.** It is reported as confidential, without its name or its words, unless `include_confidential`. A case catalog's files are named only when the sources name the catalog or a file in it. This is `document_search`'s rule.
- **Sources narrow nothing and flag one thing.** With `sources` (the hits the answer was written from), a quotation found only outside them is flagged.

**Citations.** The citations are read by the grammar the outlines use (`jason.community.cite.located_targets`).

- **A statute's section:** whether it is on the shelf, its digest, and each version when the shelf holds two under one number.
- **A governing document's section:** its words and digest, from the reader `jason cite` uses.
- **Each quotation attributed to a citation:** whether it is in that provision's words. A quotation is attributed to the citation that introduces it in its sentence, or follows it directly.
- **A whole document named beside a quotation** can confirm it and never makes it `MISATTRIBUTED`: jason's copy of the document is one copy among several.

## Commands

```bash
jason export-authorities --digests     # record the digests of the pages on disk; no fetch
jason readings                         # each reading with its status
jason readings --stale                 # only those not current
jason readings --citation CIV-5855     # the readings of one provision
jason readings --recite CIV-5855       # the words, then the readings
jason readings --recite "rules#1.1" --as-of 2099-01-01
jason readings --recite CIV-5855 --as-of 2022-03-01    # the words in force that day, where the disk shows them
jason law-history --versions                           # earlier versions of the sections the documents cite
jason law-history --versions --since 2025              # and of those the Act's history says changed since
jason law-history --versions --citation CIV-5855       # of one section (may be given more than once)
jason law-history --versions --shelf                   # and of every section on the shelf
jason law-history --add-version FILE --citation CIV-9901 --source "..." --by "..." --from DAY --until DAY
jason verify-quotes answer.txt         # each quotation: found, altered, misattributed, or not found
jason verify-quotes - --sources hits.json --json    # the answer from standard input, against the hits it was written from
```

`jason readings` and `jason verify-quotes` only read. `--json` prints the same as data. `jason verify-quotes` exits 0 when every quotation checked is found, and 1 when one is not.

`jason law-history --versions` and `--add-version` write `data/authorities/history`. A person runs them; no reader does. `--versions` reads lawlibrary's local shelf and nothing on the internet, and it may be run again: a file already there is left as it is or has its range brought up to date.

- **After `jason export-authorities`, run `--versions` again** for the sections whose words changed. Until then the replaced words are held with no range, and a recital for an earlier day says so.
- **A section the shelf does not hold** gets its earlier versions and no current page. `jason cite` brings the current words down.

## Limits

- **A digest says the words changed, not what the change means.** A person reads the new words.
- **The digest is of the whole section.** A reading of one subdivision goes stale when another subdivision changes. That errs toward checking.
- **A governing document's digest follows jason's copy,** which is not an official restatement. A corrected OCR slip changes the digest as an amendment does.
- **Reciting decides nothing.** A reading is one party's view, labeled as one.
- **A range is as good as the Legislature's notes.** `Until` is the next act the publications show; [The gap](#the-gap-october-4-2026) lists what they cannot.
- **An earlier version's digest covers its credit line too,** as a shelf page's does. Two prints that differ only in the credit line have two digests and the same law.
- **The publication's words are the source.** A session publication is the Legislature's own file, read with lawlibrary; it is not the chaptered act. Where the exact enacted text matters, counsel reads the Statutes.
- **The quotation check reads words, not meaning.** `FOUND` does not say the answer reads the words rightly, that they answer the question, or that they were in force on a given day.
- **It checks only what is quoted.** A paraphrase, a figure, or a date outside quotation marks is not checked.
- **It checks against jason's copies.** A scan's OCR can misread, so a true quotation of the paper can be `ALTERED` against the scan. The stored words shown beside it say which.
- **An attribution is read from position.** A sentence that names one section and quotes another can be `MISATTRIBUTED` wrongly. Read the sentence.
- **A quotation that runs across the place a file with no headings was cut** can be missed when it is longer than the overlap between the two passages.
