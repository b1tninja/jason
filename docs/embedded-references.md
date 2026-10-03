# Embedded references

A notice that copies a section of the declaration is right on the day it is written and wrong the day an amendment
changes the section. jason's own documents can carry a reference instead of the copy, filled from the document kept as
amended ([living-documents.md](living-documents.md)) each time they are rendered. A detector finds the copies already
out there, says who owns each one and what may be done about it, and a compiled guide gives agents an index of every
section with where it is copied.

Code: `jason.community.section_refs` (tokens and rendering), `jason.community.embedded_copies` (the detector),
`jason.tasks.section_refs` (the documents on disk, the scan, the patches, the guide), `jason section-refs` (the
command).

## Where a reference belongs, and where it does not

| Material | A token? | What is done with a copy |
|---|---|---|
| jason's documents rendered for members or the board: owner notices, guides, and letters in Markdown (`data/drafts/`), the base and profile packet templates | yes | a whole-section copy may be replaced with `{QUOTE:...}` by a person (`--patch`, then `--apply PATH --yes`) |
| Reference material agents read: `docs/`, the profile's docs, `AGENTS.md`, `SKILLS.md`, notes, canvases | **never** | the words stay where an agent reads them; a stale quote is corrected by hand |
| Adopted documents: bylaws, rules, policies, resolutions (their Docs and PDFs) | no | reported only: a finding for the document's next revision; a stale copy is a conflict lead, not a `Conflict` row |
| Templates jason does not own (the vendor's, Drive's) | no | reported only: update the template where it lives |
| Letters, notices, agendas, and minutes as sent | no | history: never rewritten ([letters.md](letters.md)) |
| Recorded instruments and public records | no | never touched |
| The document itself (its copies, exports, and its own amendments) | no | listed as whole copies; an amendment shows the words it replaced, so its "stale" text is expected |

## The tokens

```
{QUOTE:ccrs#4.2(b)}                     the section's current words, its citation, and who set them
{QUOTE:ccrs#4.2(b) as-of=2025-01-01}    the words in force on a date
{CITE:ccrs#4.2(b)}                      the citation alone: "CC&Rs Section 4.2(b)"
```

The target is written as `jason.community.references` names a section of a known document (`key#number`); a setting
follows the target as it does in `{REPORT:key setting=value}`. The key is any document the profile keeps:
`Community.living_documents()` (as-of works), else `Community.citable_documents()` with an outline on disk (the
current text only). A citation uses `CitableDocument.cite_as` (else the title): "Section 4.2(b)", "Article 8" for a
top-level section the document heads ARTICLE, and a lettered rule's own label ("Rules R-3(a)").

A quote on a line of its own renders as a block quote: the caption in bold, the words, then the citation and
provenance ("as amended by the Second Amendment, recorded ..., in force from ..."). A quote inside a sentence renders
as the words in quotation marks with the citation after. A document that quotes ends with the caveat: jason's copy is
kept from the instruments' own words; it is not an official restatement, and the recorded and adopted documents
control.

**Fails loudly.** An unknown document, an unknown or ambiguous section, a section an amendment removed, an as-of on a
document not kept as amended, or an unknown setting raises `SectionRefError`, every failure in the document at once,
and nothing is rendered.

**Records.** Each filled reference is an `Embedded` record: the token, the citation, the instrument that set the words
and its date, the as-of, and a digest of the words. `jason section-refs --render FILE` writes them beside the output
(`OUT.refs.json`), so a sent document says what it quoted and from what.

**Typesetting.** A base read by OCR runs words together. When the working copy kept by hand has exactly the same
letters and digits for the section, its spacing and punctuation are used (an editorial change, as a spacing
correction is). When the letters differ, the consolidated words are used and the record carries a note to check them
before sending; `jason intake` takes the corrections.

The references are filled wherever jason renders its documents: `markdown_html.message_html` (the broadcast and
owner-information emails), `draft_docs.push_markdown` (a Markdown source set on the letterhead), `packets.fill_letter`
(an HTML packet letter), and `packets.template_markdown` (a Markdown packet part). Text with no token is untouched and
reads nothing.

## Finding the copies

`jason section-refs --scan` looks for every version of every section of the documents kept as amended (or
`--document KEY ...`): the current words, the words each earlier period had (the text built as of the day before each
amendment took effect), and a draft's proposed words. The versions are built once from the saved sources and cached in
`data/section-refs/versions-KEY.json` until a source, a transcription, the specification row, or the consolidating
code changes (`--refresh` rebuilds).

Each version is read as one stream of its letters and digits, spaces and punctuation dropped, and cut into
overlapping runs of 30 characters. The stream is what makes OCR on either side tolerable: "Notmore than" and "Not
more than" are the same letters, and a misread letter breaks only the runs across it. A host (every outline, the
library's extracts, jason's sources, the reference material) is looked up every three characters. Shared runs that
advance together in the host and the section are a copy; a lone shared phrase at a cluster's edge is dropped. Then:

- **coverage**: how much of the section the copy holds; **fidelity**: how much of the copy is the section's words.
- **kind**: verbatim (all of it, word for word), near-verbatim (most of it; OCR or an edit), excerpt (at least about
  twenty-five words and a tenth of the section), or paraphrase (a paragraph holding most of a section's rare words; a
  lead to read, not a finding).
- **currency**: which version shares the most runs: current, stale (an earlier period's words), draft, unamended (the
  section was never amended), or undecided (the copy does not reach the words the amendment changed).

Boilerplate is left out twice: a run in more than three sections, and a run in more than eight documents that are not
the document itself (a notary's acknowledgment a base read by OCR runs into its last section). A host holding a
quarter of a document's sections is reported as a whole copy, with the sections where it reads as superseded words: a
working copy kept by hand that still carries an amended section's old words shows up here. Two sections with the same
words at one place are one copy naming both.

`copies.md` and `copies.json` in `data/section-refs/` list each host with its owner, what to do, and each copy's
section, kind, currency, coverage, fidelity, and span. The governance tools can serve the same read-only view:
`jason.tasks.section_refs.embedded_copies(key=, host=, owner=, stale_only=)`.

**What it does not find.** A paraphrase that shares neither runs nor most of a section's rare words. A statute's text
two documents both quote is found as a copy of whichever governing-document section quotes it (a statutory notice in a
rule book matches the declaration section that carries the same notice); the statutes themselves are not targets yet.

### Measured

On a real profile's library, outlines, and sources: every copy outside the document's own
copies was read by hand beside its section. All were true matches of the section's words; about one in six was a
statutory notice both documents quote rather than a copy of the declaration's own drafting. The checks that got it
there: dropping lone edge runs (spans that started in unrelated text), the boilerplate filter, and the excerpt's
coverage floor (each removed a class of false matches the hand check found).

## Replacing a copy in jason's own sources

`jason section-refs --patch` scans jason's own sources and prints a diff for each whole-section copy (verbatim or
near-verbatim, most of the section): the copy, its quotation marks, and an `<em>` or block-quote line around it become
`{QUOTE:key#n}`. An excerpt is not replaced, since a quote of the whole section would say more than the copy did; cite
it beside the words instead. Two sections with the same words are not replaced (the reference would be a guess).
`--apply PATH --yes` writes one file's proposal and keeps the old text as `.bak`; it refuses a file changed since the
scan. Apply it to a base template or a draft not yet sent: a notice already sent stays as sent, and the base that
generates the next one is what changes.

## The guide for agents

`jason section-refs --guide [KEY ...]` compiles `data/section-refs/guide/KEY.md` and an index: an agent's map of each
governing document. Each section has its citation, caption, and an excerpt of its words; **Amended** sections name the
instrument that set the words and the command for the earlier words; and each lists the statutes it cites and what
cites it (`data/outlines/references.json`), the `Conflict` rows that name it, the notice clauses read from it
(`Community.notice_provisions()`), the duties read from it (`data/duties/`), and where it is copied (the last scan).
The header stamps the sources and the date, the drafts not in effect, the whole copies, and the conflicts on the
document as a whole.

The guide is profile data and stays in `data/`; it is generated, never edited: run the command again. It is an index:
read the section itself before relying on it (`jason section-refs --show KEY#N`, or the governance tool
`living_document`). Agent reference material keeps its own quoted words; the guide is where an agent finds the
current ones.
