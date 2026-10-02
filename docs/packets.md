# Packets: several documents delivered as one PDF

The annual budget report and annual policy statement (Civil Code 5300, 5310, 5320) are one packet. It is a cover and
two reports from template Docs, plus enclosures that live elsewhere. The 25-26 packet was one Google Doc
("Annual Disclosures") with four `[ INSERT ]` pages spliced in by hand. `jason packet` does the splicing.

```bash
jason packet annual-disclosures --year 2027                       # plan: parts found or missing, tokens open, gaps
jason packet annual-disclosures --year 2027 --values              # data/packets/annual-disclosures-2027/values.json
jason packet annual-disclosures --year 2027 --make-templates --yes # make or rewrite the template Docs (replaces their text)
jason packet annual-disclosures --year 2027 --build --draft --yes  # assemble building-1.pdf ... building-8.pdf
jason packet annual-disclosures --year 2027 --building 4            # one building's plan (and --build, its PDF)
jason packet owner-information --year 2027 --build --yes            # the 4041 mailing: cover letter and fillable form
```

## The parts

`mystique/packets.py` lists the parts in order. Each part says where this year's copy is found, never which file it
is:

| Source | Found by |
|---|---|
| template | a Google Doc with `{TOKENS}` (the cover and Part A; Part B), copied into My Drive/<packet title>/<year> and filled |
| library | the newest PayHOA library file whose path matches the pattern. `{year}` is the fiscal year, `{prior}` the year before, and `{term}` the insurance term ending in it (`26-27`). Examples: the budget, the reserve study, the policies, the certificate of insurance. |
| drive | the newest Drive file whose path matches |
| generated | a page jason writes, printed to PDF by the installed Chrome or Edge on the letterhead. The insurance summary uses only the terms in force on the first day of the fiscal year, so a term not on file is a gap, never last year's figures. The FHA and VA statements each get their own page. `letter:<file>` is an HTML letter in `mystique/packet_templates/` with `{TOKENS}`: the master insurance notice, each building's flood notice, and the owner-information cover letter. |
| addendum | pages for some recipients only |

## Only the pages that matter

Each page costs about 20 cents per owner, double-sided, as the Mailroom's bills for past packets show. A found file
can list its `pages`. When
page numbers vary from file to file, a part chooses its pages by what they say instead:

- `keep`: only the pages whose text matches the pattern;
- `drop`: leaves out the pages whose text matches.

A rule that matches no page keeps every page and says so, so a part is never empty.

- Each flood policy PDF is the agent's cover letter, a claims page, the declarations, and a privacy notice. The
  packet keeps the declarations page only (`INSURED NAME(S) AND MAILING ADDRESS`). The flood notice covers what to do
  after a flood.
- The master package is about 150 pages. The packet keeps its declarations: the policy period and the
  coverages-and-limits pages, three pages in the 25-26 package. The schedule of forms also names the declarations,
  so the rule keys on the period and the limits headings.
- The 7-page custom-certificate guide stays in PayHOA. The master notice lists the steps and points to the guide.

Some pages cannot share paper. The FHA and VA statements must each be "on a separate piece of paper" (Civil Code
5300(b)(10), (11)), so their parts are `own_sheet`. Each starts on a front page, and a blank back is added, so a
double-sided print puts nothing else on its sheet.

## Linked documents

A year's `values.json` can stub any part in from a Google Doc or Drive link. The build exports the Doc as it stands
(or downloads the file):

```json
"_links": {"Disclosure regarding pending litigation": "https://docs.google.com/document/d/<id>/edit"}
```

A part in `mystique/packets.py` can also be pinned to a link (`PartSource(SourceKind.DRIVE, ref="<link>")`). A link
naming a part the packet does not have is listed as a gap.

## One packet per building

The annual packet goes to every owner with the insurance section in full (the board's choice, October 1, 2026):

- the 5300(b)(9) summary;
- the master insurance notice (5810) and the master policy's declarations pages;
- the certificate of insurance, the custom-certificate guide, and the parcel map;
- the owner's own building's flood notice and flood declarations.

The packet's `variants` are the eight buildings. A part that names `{building}` in its title or pattern, or a letter
with a building's tokens, differs between them. The build makes every other part once and assembles
`building-<n>.pdf` for each building, with its own manifest (`building-<n>.json`). Mail each owner their building's PDF.

The flood notice's tokens come from the newest flood term on file for the building (`flood_values`):

- the policy number, term, carrier, and deductible;
- the limit, with "N units at $250,000 each" only when the limit is exactly that;
- whether the policy is renewed, in force, or ends before the fiscal year with no renewal on file;
- what changed from the term before.

A pending renewal is said as pending; the current declarations are enclosed and the gap is listed. A lower limit or a
higher deductible is listed as a Civil Code 5810 notice to every member.

## The tokens

A template's tokens are filled from four places, each overriding the one before:

1. The packet's standing values: the designated recipient, the addresses, the posting location, the minutes.
2. The year's computed values: `FISCAL_YEAR` and `UNIT_COUNT`.
3. The statutory passages, cut from the law on hand (`jason.community.statute_passages`):
   - the 5730 notice;
   - the 5965 sentence;
   - the 5300(b)(9) insurance statement;
   - the FHA and VA forms.

   When the law changes, `jason export-authorities` brings the new words, and the next packet prints them.
4. The year's `values.json`, where a person records what only the board can say: the deferral, special assessment,
   and funding statements, the assessment, and the mailing date.

A token still empty after all four is a decision still open. The plan lists each one, and so does the filled Doc.

## Building

The build fills the templates as Doc copies. It sets the 5730 notice in 12-point type, as 5730(a) requires.
It downloads the library files (only the pages a part lists), prints the generated pages, and merges everything in
order with `merge`: a bookmark per part, and "Page n of N" at the foot of every page. `manifest.json` records each
part's source, pages, and SHA-256, so the mailed packet can be shown later.

Without `--draft`, a missing required part or an open token stops the build.

## The owner information form (Civil Code 4041)

Each year the association must ask every owner for four things: their preferred delivery method, a secondary one,
their legal representative, and whether the unit is owner-occupied or rented. It must enter the answers at least 30
days before the budget report and policy statement go out. The request must also say that an email address is
optional, and give a simple way to change the preference.

One definition, `forms.OWNER_INFO` in `mystique/forms.py`, makes every version, so the paper and online forms cannot
differ:

- the paper form (`form_render.paper_markdown`), a template part (`form:owner-info`) at the end of the annual packet,
  where it is the solicitation for the next cycle;
- the fillable PDF (`fillable.make_fillable`, on the field primitives in `pdf_fields`; see docs/drafts-and-forms.md), laid over the printed form:
  - a "check one" question is one radio group, so a second choice clears the first;
  - a "check all that apply" question keeps a check box per option;
  - each answer line is a text field.

  `read_fillable` reads a returned form back by question;
- the `owner-information` packet, which mails it on its own;
- the build sheet for PayHOA's form builder (`form_render.payhoa_sheet`; `data/packets/owner-information-<year>/payhoa-form-build-sheet.md`);
- a Google Form if wanted (`jason forms --create owner-info`).

The answers belong in PayHOA, the association's books. jason stores no owner's address.

## What a year's packet still needs

`jason packet annual-disclosures --year N` lists the parts not found, the tokens still open, and the gaps. Before
anything else comes the owner delivery-preference solicitation (4041): the answers must be entered at least 30 days
before the packet goes out.

This association's findings are in its private notes (mystique/notes/packets.md).

## QR codes

A letter template (`letter:<file>`) can place a QR code for a link with `{QR:TOKEN}`. It prints the code for the link
in `values[TOKEN]`, about an inch square, with the link written beside it and a label from `QR_LABELS` in
`tasks/packets.py` (for example, "Scan to answer online in PayHOA"). A code is a shortcut, never the only way, so the
link is always printed too.

A token with no link yet (the owner form's "[FORM LINK]") prints a visible marker and is listed as open, so a draft
never hides a missing link. The owner-information cover letter places `{QR:OWNER_FORM_LINK}` under its three ways to
answer. `jason forms --pdf` fills `{QR:...}` in a form's preamble the same way.

Codes are made by `jason.community.qr` (segno: `pip install -e ".[qr]"`) with error correction M and a four-module
quiet zone, so a code still reads when printed small or photocopied. Only links are encoded (`https://`, `mailto:`,
`tel:`). Email gets the link itself: the reader is already on a screen, and mail clients block inline images.
Pictures for an email body (screenshots of where to click) are uploaded to PayHOA when the batch sends
(`email_html.host_images`): a draft's `<img src="local.png">` becomes the upload's `viewUrl`, as PayHOA's editor
does with a pasted image. That S3 link dies with its session token within a day, but PayHOA's mailer rewrites it
on sending to `core.payhoa.com/email-image/{key}?signature=...`, which has no expiry (read from a delivered email,
October 2026). Some mail clients still hold images back until the reader allows them, so the steps are written out
beside each picture.
`jason qr LINK` writes a PNG or SVG to paste into a Google Doc, a slide, or a notice posted on the bulletin board.
