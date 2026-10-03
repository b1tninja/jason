# The living CC&Rs: this association's readings

The general method is [docs/living-documents.md](../../docs/living-documents.md). This page records the trials on the association's own instruments.

## Re-reading the recorded base

**The CC&Rs, October 2, 2026** (the county's recorded copy, 56 pages; `jason living ccrs --reread cli --numbering text`, the numbering the transcriptions were keyed under):

| Reading | WER | CER |
|---|---:|---:|
| PyMuPDF page OCR, as cached | 8.55% | 1.18% |
| the same, with its 531 transcriptions | 5.01% | 0.84% |
| Tesseract's tool, as read | 2.18% | 0.45% |
| the tool, with the 57 carried | 1.85% | 0.41% |
| the tool, if the 16 re-keyed questions are accepted as suggested | 1.75% | 0.38% |

- **The transcriptions.** Of 531, 448 are no longer needed, 57 are carried (9 under a number the tool reads differently), 16 are re-keyed, 2 are unplaced (behind a second section of the same number), and 8 were stale already.
- **The open OCR questions.** Of 176, 98 would no longer be asked; in 83 of them the tool no longer has the words in question. The scan would ask 41 new ones (8 likely).
- **Section numbers.** The tool reads 394 numbered sections against 365, but it misreads some labels the original read right ("1.10" as "1.40").
- **Under the label grammar** (`--numbering labels`, the builds' default that day), the grammar read 402 sections in the original reading and only 245 in the tool's ("16(a)" and its like for whole articles), so 426 transcriptions came out unplaced. The tool's reading needs the grammar's attention before a switch, and the switch refuses a dry run numbered otherwise than the builds.
