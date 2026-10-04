# The words, and readings of them

**Status:** built, October 4, 2026: step 4 of [ingestion-and-review.md](ingestion-and-review.md) and the authorities part of item 3 in [rag-roadmap.md](rag-roadmap.md). No reading is recorded yet; the profile's are for a person to add.

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

Two files share a name. `data/authorities/changes.json` is jason's log of its own shelf. `data/authorities/history/changes.json` is the Act's amendment history from lawlibrary (`jason law-history`). The first says when jason's copy changed; the second says when the law did.

`data/` is not in git. Back up `data/authorities/history` and `changes.json` with it.

### Reading the words

| Function (`jason.community.law_text`) | Gives |
|---|---|
| `section_digest(citation, data_dir)` | the digest of the words on disk now, or `None` |
| `law_text(citation, data_dir, digest=None)` | the current words, or with `digest` the words that have it: current, else replaced |
| `versions(citation, data_dir)` | every text the shelf holds under the citation |
| `history_texts(citation, data_dir)` | the words exports replaced |
| `changes(data_dir, citation="")` | the shelf's change log |

These read the disk only. A section that is not on the shelf is a miss; nothing is fetched.

### Two versions under one number

The Legislature's publication prints some sections twice under one number. The shelf holds both, and the backfill lists them.

- `versions` gives each, with its own digest.
- `law_text` and `section_digest` give the first, which is the one `authority_text` quotes.
- `recite` gives every version, with a caveat. jason does not say which is in force on a given day.

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

With no reading stored, the words stand alone. With `as_of`, a reading dated later is set apart, and the words carry a caveat when jason knows they changed after that day. jason holds one edition of the law, so it does not give the words in force on an earlier day; it says the words on disk may differ.

`recite` returns a `Recital`. `Recital.lines()` is the text, and `as_dict()` the same as data.

## Commands

```bash
jason export-authorities --digests     # record the digests of the pages on disk; no fetch
jason readings                         # each reading with its status
jason readings --stale                 # only those not current
jason readings --citation CIV-5855     # the readings of one provision
jason readings --recite CIV-5855       # the words, then the readings
jason readings --recite "rules#1.1" --as-of 2099-01-01
```

`jason readings` only reads. `--json` prints the same as data.

## Limits

- **A digest says the words changed, not what the change means.** A person reads the new words.
- **The digest is of the whole section.** A reading of one subdivision goes stale when another subdivision changes. That errs toward checking.
- **A governing document's digest follows jason's copy,** which is not an official restatement. A corrected OCR slip changes the digest as an amendment does.
- **Reciting decides nothing.** A reading is one party's view, labeled as one.
