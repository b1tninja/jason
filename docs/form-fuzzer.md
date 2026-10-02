# Fuzzing the paper form and its reader

`jason form-fuzz` tests the owner form the way it will come back:
- It makes up answers and fills them in the ways owners fill a form.
- It prints and scans them badly, reads them back, and scores the reading.

The aim is to improve three things, judged by what comes back:
- **the form's design:** writing space, boxes, where the marker goes;
- **the reader:** `form_reader`;
- **the reading hints:** `form_hints`.

No owner's information is used, and nothing is sent. The code is `jason.tasks.form_fuzz`.

```bash
jason form-fuzz --lint
```

`--lint` checks the generated form without scanning it:
- tokens left unfilled (`[FORM LINK]`, `{RETURN_BY}`);
- the bar mark's and printed marker's places clear of ink on every page;
- text inside Lob's 1/16-inch print margin;
- writing space under 14 points;
- boxes under 8 points;
- a question's label on a different page from its answer.

```bash
jason form-fuzz --cases 60 --seed 1
```

That runs 60 cases and writes `data/forms/fuzz/owner-info/report-<date>.md`. Failing cases join `corpus.json`, and `jason form-fuzz --replay` runs them again after a fix. `--fills`, `--styles`, and `--profiles` narrow a run.

## A case

Each case is drawn from a seed, so any case can be made again.

**Answers** are made up from the form's own questions and what each answer holds (`FormQuestion.reads_as`: name, address, contact, email). They come in a style:

| Style | What it tests |
|---|---|
| plain | ordinary names and addresses |
| long | two owners, "Drive" spelled out, apartment lines |
| lookalike | letters OCR confuses: Lilli, Ollila, emails with `l1` and `0o` |
| punctuation | O'Neil, Smith-Lowell, St. John, A. J. |
| accents | José, Muñoz, Siobhán |
| caps | the same, in capitals |

Emails use the `example` domains (RFC 2606).

**Fills:**

| Fill | How the form is filled |
|---|---|
| typed | typed into the PDF's fields |
| hand | written on the printed page in a print-style handwriting font (Ink Free, Segoe Print, MV Boli, Comic Sans), each word a little off the line and turned, black or blue ink, boxes marked with an X or a check |
| cursive | the same in cursive (Lucida Handwriting, Bradley Hand, Segoe Script) |
| prefilled | the emailed pre-filled copy (`owner_prefill.fill_pdf`, marked with its copy marker), sent back untouched |
| edited | the same with one answer changed |

**Scans** (`form_scans.simulate`): the page is rasterized, turned, scaled, shifted, blurred, speckled, made faint or dark, and JPEG-compressed.

| Profile | dpi | Turn | Other |
|---|---|---|---|
| clean | 300 | 0.3° | |
| office | 200 | 1° | |
| home | 150 | 1.8° | |
| phone | 120 | 2.5° | dark |
| fax | 100 | 3° | faint |
| upside-down | 150 | 181.5° | |
| random | drawn per case | | |

**Scoring:**
- Each answer is scored the way jason compares answers (`owner_prefill.normalize`). It is scored twice: by the reader alone (raw), then with the reading hints (hinted).
- A pre-filled copy is also scored by `owner_prefill.compare`, as a real return is. An untouched copy must read as unchanged, and an edited one as exactly its change.
- The report counts the changes the hints swallowed. That count must stay zero.

## What the first runs found, and what changed

October 1, 2026, owner form.

| Finding | Fix |
|---|---|
| Question titles read as answers ("1. Uwrier nares"): the drop-out leaves a soft scan's label fringe | Every printed word of the blank page is placed on the scan and taken out before a field is read; a word centered above or below the field, or under 4.5 points tall, is dropped |
| Typed text lost its letters' feet: the drop-out takes what touches the writing line | OCR reads the scan's own gray within 3 pixels of the person's ink (`form_reader.GROW`), not a black-and-white mask |
| An upside-down page never aligned | The reader tries the page turned round |
| Phone scans "aligned" 11 to 23 points off and read the next question as the answer | An alignment with a mean error over 4 points reads nothing (`MAX_RESIDUAL`) |
| An empty radio button read as marked: a filled PDF redraws its empty buttons, and the outline's difference survives the drop-out | A box is measured in its middle (inset 20%), which an X, a check, or a dot crosses and an outline does not |
| An email's dot read as a space | The email hint joins the words of an email |
| "15B" read as "158" by the number hint | Only four or more characters that would be all digits are taken as a house number or ZIP |
| "St. John" and "St John" compared as different answers | `normalize` drops a period that ends a word; an email keeps its dots |
| The gray bar mark was lost on a faint fax | 35% gray and lighter cuts (8/12; 0/12 before) |

**Typed answers after the fixes** (typed, pre-filled, and edited; raw → hinted):
- Clean scans: 86% → 91% of answers right.
- Office scans: 82% → 91% to 100%.
- Home scans: 68% → 77%.
- Upside-down pages: 82% → 100%.
- Every box and the occupancy question: 100%.
- Untouched pre-filled copies: false changes fell from 22 to 13 with the hints, and no real change was swallowed.

**Still open:**
- **Fax-quality pages** (100 dpi, faint) don't align. OCR reads 0 to 2 of the printed lines. Contrast and sharpening don't help. The marker still reads from the bar mark.
  - **Proposal:** printed registration marks (solid squares in the page corners, as OMR forms use) would align a page without OCR. Then the boxes, the 4041 answers that matter most, would read from a fax.
  - It's a visible change to the letter, so it waits for a decision.
- **Phone scans** align half the time.
- **Handwriting** reads 5 to 15% right by OCR. That is the vision model's work (`VisionReader`), and that trial waits on free memory ([document-tools.md](document-tools.md)).
- **Pre-filled answers in a home scan:** the remaining misreads are single characters ("Naniel" for "Daniel"). The hints rightly don't treat these as unchanged, because D and N aren't look-alikes. A larger type size for the pre-filled values would help, as would a person confirming "nearly what was sent".
- **The membership-list choice** is missed on some pages. Its second button sits at the far right, where the fit is weakest.

## Reading hints (`form_hints`)

A hint works on what OCR returned and marks every change ("+hint").

| Hint | What it does |
|---|---|
| **What was sent** | A pre-filled copy's value, re-made from PayHOA when the return is read and never kept. The reading counts as that value only when OCR could have read it either way: look-alikes folded together, spacing and punctuation dropped. Anything else is the owner's change and stays as read. |
| **What the answer holds** | An email loses its spaces, gets its "@" back, and has a near-miss domain put right. A phone number becomes digits. In an address, a near-miss street name or USPS word becomes the word, and a house number or ZIP gets its digits back. |
| **Vocabulary** | The community's street names (`symbols.Street`) and the USPS words (`postal`). |

What an answer holds is data on the question (`FormQuestion.reads`, a `ReadAs`), set in `mystique/forms.py`.
