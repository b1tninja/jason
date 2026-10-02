# Letters from templates

The association's letters are Google Docs on its letterhead. jason keeps a set of **template Docs** with `{VARIABLE}` tokens where a letter's facts go, and makes each letter by copying a template and filling the tokens. The copy keeps the template's logo, header, footer, fonts, headings, and bullets.

## The templates

The templates are in **My Drive/Templates**. Each is a row in the specification, `mystique/templates.py` (`DocumentTemplate`), with its Drive id, its tokens, the optional ones, the folder its letters go in, and the authority it serves.

| Template | Tokens | Authority | Letters go in |
|---|---|---|---|
| Letter on Letterhead | `{DATE}`, `{RECIPIENT_NAME}`, `{RECIPIENT_ADDRESS}`, `{RECIPIENT_CITY_STATE_ZIP}`, `{SUBJECT}`, `{BODY}` | | the folder you give |
| Notice of Hearing | `{DATE}`, `{OWNER_NAME}`, `{ADDRESS}`, `{CITY_STATE_ZIP}`, `{DELIVERY_METHOD}`, `{HEARING_DATE}`, `{HEARING_TIME}`, `{ZOOM_LINK}`, `{ZOOM_MEETING_ID}`, `{ZOOM_PASSCODE}`, `{ZOOM_DIAL_IN}`, `{VIOLATION}`, `{GOVERNING_SECTIONS}`, `{POSSIBLE_DISCIPLINE}`, `{CURE}` (optional), `{CONTACT}` | CIV 5855, 5850(c)-(e), 4935(b); Corp 7341 with `--suspension` | Disciplinary |
| Notice of Decision | `{DATE}`, `{OWNER_NAME}`, `{ADDRESS}`, `{CITY_STATE_ZIP}`, `{DELIVERY_METHOD}`, `{HEARING_DATE}`, `{NOTICE_DATE}`, `{VIOLATION}`, `{FINDINGS}`, `{DECISION}`, `{GOVERNING_SECTIONS}`, `{PAYMENT_OR_CURE}`, `{CONTACT}` | CIV 5855(f), 5910 | Disciplinary |
| Board Meeting Agenda | `{MEETING_KIND}`, `{MEETING_DATE}`, `{MEETING_TIME}`, `{ZOOM_LINK}`, `{ZOOM_MEETING_ID}`, `{ZOOM_PHONE}`, `{TECH_CONTACT}`, `{AGENDA_ITEMS}` | CIV 4920, 4926(a), 4930, 4935(a) | Meetings/<year> ([board-agenda.md](board-agenda.md)) |

`jason templates` lists them with their tokens.

**How they were built.** `jason templates --build --yes` built them from **My Drive/Letterhead**, which is left unchanged. For each template it:
1. copies the Letterhead;
2. writes the template's body (`BODIES` in `jason.community.templates`) in place of the sample text;
3. removes the "LETTERHEAD" sample title under the association's name;
4. replaces the footer's "LETTERHEAD" with the mailing address.

**The house style.** The Google Docs are the originals; the PDFs in PayHOA and email are exports of them. The Docs API cannot change a Doc's named styles, so jason writes each paragraph in the house style as it writes the body (`jason.google.docs_markdown`):
- headings dark and bold, kept with the text after them, instead of the Letterhead's pale grey heading style;
- field labels bold ("**Date:**", "**Time:**"), and a blank line between a filled token and the legal text after it;
- the signature block kept on one page;
- a header on the pages after the first, small and right-aligned ("Notice of Hearing · {ADDRESS} · {DATE}"; `CONTINUATION` in `jason.community.templates`), since the logo header is on the first page only;
- the association's name bold in every footer, as the first page's footer sets it.

`jason templates --rewrite <kind> --yes` writes a built template's body and page furniture again in place (same Doc id; Drive's version history keeps the old one). Check first that no one has edited the template's text since it was built.

The wording in the bodies is the statute's; the facts are the board's. To change a template, edit the Doc in Drive. Its tokens are whatever `{...}` it holds, and the specification's list of tokens is only the starting set.

## Tokens

A token is `{` + upper-case letters, digits, or `_` + `}`. Filling a letter replaces each token everywhere in the copy: body, headers, and footers.
- **A token with no value stays visible** in the copy for whoever edits it, and the result lists it as `unfilled`.
- **An optional token with no value is removed.**
- **A link token** (`{ZOOM_LINK}`) becomes a link to its own value.

## Making a letter

**A hearing notice.** `jason hearing --address A --violation "..." --doc --owner "Name" --matter "Trash Cans" --yes`:
- fills the Notice of Hearing from the hearing plan: the dates, the Zoom details once the meeting is scheduled, and the violation in the board's words;
- files it in `Disciplinary/<address> - <matter> <M-D-YY>/`, the board's own folder convention;
- keeps the Doc's id in `data/zoom/hearings.json`.

The owner's name, the delivery method, the governing sections, and the contact come from a person (`--owner`, `--delivery`, `--sections`, `--contact`). jason does not look up owners or quote CC&Rs.

**Any template.** `jason letter --template decision-notice --name "Notice of Decision - <address>" --set OWNER_NAME="..." --set DECISION="..." --yes` fills a copy into the template's folder, or into `--folder`. `\n` in a value makes a new line.

**A guide or notice written in Markdown.** `jason letter --markdown data/drafts/GUIDE.md --name "Guide - ..." --yes`
sets the file on a copy of the Letterhead (logo header, address footer) in the house style
(`jason.google.docs_markdown`, `--style report` or `letter`), in My Drive/Templates or `--folder`. Later runs rewrite the
same Doc in place; its id is kept in `docs.json` beside the file. This is the way to make an owner-facing page
(for the website, or to attach to an email as the Doc's PDF); Drive's HTML import gives a plainer page with no
letterhead.
- `![alt](file){width=620}` on its own line is a picture, centred, put in after the text from a short-lived PayHOA
  upload link (Docs keeps its own copy); the file sits beside the Markdown.
- A bare email address becomes a `mailto:` link; `[text](mailto:...?subject=...)` keeps its subject.
- Edits belong in the Markdown: a rewrite replaces the Doc's text, so edits made in the Doc are lost on the next run.
- `--pdf OUT` also saves the Doc's PDF. The same Markdown can be an email body: see "Owner-facing documents: one
  Markdown source" in [drafts-and-forms.md](drafts-and-forms.md).

**What jason does not do:**
- send, share, or export the letter;
- change the template or the Letterhead.

A person reviews the Doc, fills what is left, prints or exports it, and delivers it (Civil Code 4040).

## What the notices say, and why

The hearing and decision templates follow the statutes as amended by AB 130 (Stats. 2025, ch. 22, effective June 30, 2025):

| Clause | Source |
|---|---|
| Date, time, place; nature of the violation; right to attend and address the board | CIV 5855(b) |
| Executive session on request, and the member may attend | CIV 5855(b), 4935(b) |
| The right to cure before the hearing, or give a financial commitment to cure | CIV 5855(c) (2025) |
| The $100-per-violation cap, the health-and-safety exception with its open-meeting written finding, and no late charge or interest on a fine | CIV 5850(c)–(e) (2025) |
| Internal dispute resolution at no cost | CIV 5855(d), 5910(g) |
| Reasonable accommodation, including assistance animals | FEHA; *Auburn Woods I HOA v. FEHC* (2004) 121 Cal.App.4th 1578 |
| The written decision within 14 days after the board acts | CIV 5855(f) |
| On the decision: a fine is not an assessment and cannot become a lien | CIV 5725(b) |
| `--suspension`: 15 days' notice when suspension of membership rights is possible | Corp. Code 7341(c); no case applies it to an association, so satisfy both 7341 and 5855 |

**The association's own procedure.** An association enforcing its governing documents must show it followed its own procedures (*Ironwood Owners Assn. IX v. Solomon* (1986) 178 Cal.App.3d 766, 772), so a right its bylaws or enforcement policy grant, such as presenting evidence and questioning witnesses, stays in the notice even where no statute requires it. Where the documents carry an older period (15 days, from former Civil Code 1363), the statute's 14 days satisfies both.

**Continuing fines.** A notice does not say the board may impose further fines "without further hearing": 5855(g) makes discipline ineffective without a hearing. It says the board may consider further fines for a continuing violation and that the member will be notified before any is imposed.

**Possible discipline.** The notice names it in `{POSSIBLE_DISCIPLINE}`, from the schedule in effect at the time of the violation, rather than reprinting a fine schedule that may exceed the 5850(c) cap. *Ironwood* does not require findings, but the decision template's Findings section states the facts the board found and why.

This is research, not legal advice; counsel's reading governs. Mystique's findings are in the private notes (mystique/notes/letters.md).


## Limits

- **Dates are text.** The Docs API cannot insert date chips or smart chips.
- **Multi-line values are plain text.** A value with line breaks becomes plain paragraphs; a quoted CC&R section takes its headings from the person who edits the Doc.
- **Style follows the token.** A replaced token takes the text style of the token it replaced.
