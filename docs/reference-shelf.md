# The reference shelf

A fourth catalog, beside the law, the association's record, and Jason's own pages. It holds published guides that explain how a process runs. A guide is quality material to learn from. It is not the law and not the association's record, and nothing on it is quoted as either.

| Catalog (a source of the passage index) | What it holds | How far its words bind |
|---|---|---|
| `authorities` | statute text from lawlibrary and agency publications that are authority (the Commissioner's regulations, reserve study guidelines) | quote it |
| `records` | the association's governing documents, annexations, policies, resolutions, public reports | quote it, as the record |
| `reference` | guides that explain a process (standing `reference`) | learn from it; check a cited section against `authorities` |
| `pages` | pages Jason generated and its instructions | a summary, never quoted |

## What goes on it

A work belongs here when it is written to explain, by someone who is neither the Legislature nor the association, and Jason would otherwise have to guess at the process it describes. A work that is itself authority (a regulation, an agency's required form or its own guideline) goes on `authorities` as a `Publication`. A document an association adopted goes on the record shelf.

Each work is a `ReferenceWork` in `jason.community.reference_shelf` with its author, publisher, year, what it covers, and **how far to trust it**: what it is good for and where it is out of date. That caveat is written into the note that titles the file, so a retriever's source carries it.

## Commands

```bash
jason reference                                   # the works, and whether each is on disk
jason reference --fetch                           # download the missing ones into data/reference
jason reference --page ResidentialSubdivisionsGuide.pdf 62   # one page of the text
jason reference --cites ResidentialSubdivisionsGuide.pdf   # the statutes it cites, and which the shelf lacks
jason index --build --catalog reference           # cut the shelf into the passage index
jason index --search "public report" --standing reference   # search it, by standing
```

`jason reference --cites WORK` reads the statutes a work cites and places each against the authorities shelf and lawlibrary (exit 1 when the shelf lacks some), prints the proposal, and keeps the survey under `data/citations` for the MCP tools `document_citations` and `citation_gaps`. [citations.md](citations.md#what-other-documents-cite-and-whether-the-shelf-holds-it) says who owns each part. A work's citations are a lead for the shelf; the work itself is never the source of a quoted section.

`--fetch` writes the PDF, a note (`<file>.pdf.md`, whose heading titles it), and the text by page (`<file>.txt`, with a `<<PAGE n>>` marker before each page). A page counts PDF pages, which can differ from a printed number. A file already on disk is kept. Nothing is rewritten. `data/reference/` is not checked in.

## In the console

Four read-only loaders serve the board's console from disk (`jason.web.extra.citations`): `GET /api/reference-works`, `/api/citations?source=&file=&limit=`, `/api/citation-gaps?limit=`, and `/api/reference-page?work=&page=`. The owner view never answers them. The design for the components that render them is [console/handoff-citations.md](console/handoff-citations.md).

## On the shelf

- *A Guide to Understanding Residential Subdivisions in California* (Esquivel and Alvayay, DRE and CSU Sacramento, 2014). Read in [subdivision-process.md](subdivision-process.md). It predates later changes to the Davis-Stirling Act, the Commissioner's regulations, and the Subdivided Lands Act; read a section it cites from `authorities`.

## Adding a work

Add a `ReferenceWork` row to `REFERENCE_WORKS`, run `jason reference --fetch`, write a page like [subdivision-process.md](subdivision-process.md) if it explains a process Jason applies, and index both in [README.md](README.md). Give the work a real caveat; a work with none is not yet read.
