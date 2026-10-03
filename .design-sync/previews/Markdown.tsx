import { Markdown } from "jason-ui";

/** Notes as a person writes them on a canvas: headings, emphasis, a list, a table, a link. */
export const Notes = () => (
  <Markdown text={`# Reserve loan: restore by March

The ledger shows a **$10,000.00** transfer from the reserve on 2025-03-01 (tx 77, memo "roof").

- Notice of intent to borrow: on the 2025-02 agenda
- Minutes with the finding: DRAFT only
- Resolution: not found

| Step | Due | Standing |
|---|---|---|
| Restore to the reserve | 2026-03-01 | outstanding $6,000.00 |
| Noticed finding if late | 2026-03-01 | needed (CIV 5515(d)) |

Read [the statute](https://leginfo.legislature.ca.gov/) before the meeting. A match is a lead, not a finding.`} />
);

const svg = "<svg xmlns='http://www.w3.org/2000/svg' width='320' height='120'><rect width='320' height='120' fill='#dde1e7'/><text x='160' y='66' text-anchor='middle' font-family='system-ui' font-size='16' fill='#5f6b7a'>photo</text></svg>";
const photo = URL.createObjectURL(new Blob([svg], { type: "image/svg+xml" }));

/** A code fence, inline code, and a photo inline: on a canvas the image path is /api/file?path=photos/<album>/<file>. */
export const CodeAndImage = () => (
  <Markdown text={`## Where the photo is

Kept under \`data/photos/east-bed/\`; the canvas shows it with

\`\`\`
![before](/api/file?path=photos/east-bed/a.jpg)
\`\`\`

![before](${photo})

A \`\`\`mermaid fence draws a diagram when the page can reach the diagram library.`} />
);

/** A quote and a nested list, as a clip reads once kept. */
export const Clip = () => (
  <Markdown text={`> **the loan** 2025-03-01 $10,000.00 outstanding
> from \`reserve_transfers\` on 2026-10-03

1. Read the 2025-02 agenda
   - item 6, notice of intent
2. Ask the secretary for the signed minutes`} />
);
