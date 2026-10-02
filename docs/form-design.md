# Form design: a layout that guards against poor data entry

A paper form can make a person's writing easier to read before any reader sees it. It can show where to write, how
large, and where one answer ends and the next begins. It can also keep handwriting off its own printed words.

`jason form-lab` (`jason.tasks.form_lab`) tests that:
- **Layouts:** it draws the same questions in many layouts.
- **Responders:** a model of how people respond to each layout fills them in.
- **Scans:** the filled pages are scanned badly.
- **Reading:** they're read back by Tesseract, the reading hints, and local vision models.
- **Search:** a coordinate descent looks for the layout that comes back best.

The answers are made up, and nothing is sent. Mystique's findings are in the private notes (mystique/notes/form-design.md).

## What the research says

| Source | Finding |
|---|---|
| NIST's study of three redesigned IRS forms (Garris and Dimmick, *Form Design for High Accuracy Optical Character Recognition*, IEEE PAMI 1996; [PDF](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=906484)) | Separately spaced boxes, one per character, read best. Characters wrong: 11% in one long box, 9% in boxes that share their sides (the SSN field), 6% in boxes spaced apart. Two guide ovals in each box cut errors to 3%, but writers found them much harder to fill. Writers' own habits (crossing out, writing over) were the main source of errors, and form design reduced them. The forms were drawn in blue drop-out ink, with a black registration mark in each corner. |
| [Accusoft on ICR form design](https://www.accusoft.com/resources/blog/improving-intelligent-character-recognition-icr-accuracy-better-form-design/) and [Parascript on boxes and combs](https://www.parascript.com/blog/handprint-recognition-beyond-boxes-combs/) | Make character boxes square: a tall box makes people squeeze letters. Leave space between boxes. Comb ticks are rarely followed one letter per space. |
| [ABS Forms Design Standards](https://www.abs.gov.au/ausstats/abs@.nsf/Latestproducts/3774DB8F1D6BDB15CA2576B3001270C4) and [Pyramid Solutions' paper form practices](https://pyramidsolutions.com/wp-content/uploads/2017/09/Best-Practices-for-Paper-Based-Form-Design.pdf) | About 8 mm (23 pt) for an answer space and for each line. A quarter inch (18 pt) between handwritten lines is usual, and a fifth (14 pt) is the least for average handwriting. Lines about 1 pt. |
| [Drop-out ink](https://en.wikipedia.org/wiki/Drop-out_ink) and [ABBYY on drop-out forms](https://help.abbyy.com/en-us/flexicapture/12/standalone_administrator/ap_mrf_types_color/) | The form is printed in a pale color the scanner's filter removes, leaving only what was written. Red or orange suits blue and black pens; blue doesn't suit a blue pen. It needs a color scan, and an owner's home scanner or phone won't filter it. |

jason's reader already drops the form out by subtracting the blank page ([form-reader.md](form-reader.md)), so drop-out ink matters less here. A pale line still helps that subtraction, which the search tests through the `tone` setting.

## The responder

How a person writes depends on what the space tells them. That's the perception the lab models, and it's stated in `form_lab` so it can be argued with and tuned against real returns. It's a model, not a measurement.

**What each kind of space tells the writer:**

| Space | What the writer does | Affordance (how plainly it says "write here, this big") |
|---|---|---|
| Line beneath | Writes on the line at their own size; tails cross it; a long answer runs past its end | 0.6 |
| Box | Shrinks writing to fit, to about three quarters of their size; a box too short makes them write over its edges | 0.85 |
| Shaded band | Like a box, with no edge to cross | 0.75 |
| Box for each character | Keeps letters apart, as NIST found; a long answer runs out of boxes | 0.9 |
| Comb | Followed half the time | 0.7 |
| Nothing | The baseline wanders | 0.3 |

**How much an edge is noticed (salience):** a heavier, darker edge is noticed more. The chance a writer keeps inside a space is their care × (½ + ½ × affordance × salience).

**The writers:**

| Writer | Fonts | Size | Wander | Turn | Care |
|---|---|---|---|---|---|
| Neat print | Segoe Print, Ink Free | 11 pt | 0.5 pt | 1° | 0.95 |
| Hurried print | MV Boli, Ink Free, Comic Sans | 13 pt | 1.6 pt | 3° | 0.6 |
| Cursive | Lucida Handwriting, Bradley Hand, Segoe Script | 12 pt | 1 pt | 2° | 0.75 |

Typed answers are the fourth responder.

**Writing over the form:** each word's box is checked against the page's printed words (labels, help) and against its own space. That gives the share written over print and the share written outside its space.

## The battery and the score

**The battery:** every layout gets the same 12 trials, so layouts are compared on identical work.
- Each responder (three writers and typed) appears three times.
- The scans are office (200 dpi), home (150 dpi), and phone (120 dpi, dark), from [form-fuzzer.md](form-fuzzer.md).
- The answers come in the fuzzer's styles: names, a unit address, often a mailing address, an email, a phone number, two check boxes, and a three-way choice.

**Readability:** each answer is read back and given credit, after the reading hints, compared as jason compares answers:
- 1 for the same answer;
- otherwise half its likeness to the answer.

**The objective:**
- readability;
- less 0.1 × the share written on printed text;
- less 0.05 × the share written outside its space;
- less 0.1 × the questions' height as a share of 600 points, so a layout can't win by being enormous.

**The priced objective** (`--priced`, `form_lab.Costs`) puts that last term in money, so space and readability trade in one unit:
- **Paper:** the Mailroom's price a page (`payhoa.pricing`: 20¢ a printed page, two-sided or not) spread over a page's writing height. That's 0.029¢ a point, so the whole difference between 14-point and 28-point spaces (84 points) is 2.5¢ a letter.
- **Misreads:** each answer read wrong costs a person's follow-up (`--misread-cents`, default 150¢), on the letters that come back on paper (`--returned`, default half). With 7 answers, one point of readability is worth about 5¢ a letter.
- **The objective:** readability, less the spill terms, less the paper's cents as a share of what all the answers' follow-ups would cost. `Evaluation.cents` is the same in cents a mailed letter.
- **Two answers a line** (`columns 2, pairs "every"`, the 2024 Resident Registration form's layout: name beside unit address, email beside phone, the mailing address whole). Each answer has its own region on the page (`Drawn.fields`, the reader's `read_area`), so a line can hold two without the readings mixing. Priced, 12 trials, October 1, 2026:

  | Layout | Readable | Written answers | On print | Height | ¢ a letter |
  |---|---|---|---|---|---|
  | One a line, 17 pt (the lab's current) | 0.616 | 0.442 | 0 | 420 | 214 |
  | One a line, 28 pt | 0.628 | 0.466 | 0 | 486 | 210 |
  | Two a line, labels above, 22 pt | **0.636** | 0.422 | 0 | **314** | **200** |
  | Two a line, labels above, 28 pt | 0.573 | 0.360 | 0 | 338 | 234 |
  | Two a line, labels below, 22 pt | 0.557 | 0.329 | 0.17 | 269 | 241 |
  | Two a line, labels below, 28 pt | 0.565 | 0.346 | 0.17 | 293 | 237 |

  - Labels under the line draw writing onto them: 17% of the handwriting landed on printed text, which the reader then has to separate. Keep labels above.
  - With labels above, two a line read as well as one a line in about two-thirds of the height. The spread between 22 and 28 points is within this battery's noise; run more trials before choosing between them.
- **What it says:** at these prices readability dominates. Space is close to free until it adds a page, so check the real form's page count (`jason mailroom --pdf` prints it) rather than shaving points.
  - A page is $0.20 a letter.
  - The sixth billed page (the address page counts) adds $2.25 of postage a letter.
  - A 4-page PDF is the most before that step.

**The search** is a coordinate descent from the current owner form's style (a thin black line beneath, labels and help above, Helvetica 11):
- Each setting is tried at each of its values with the rest held.
- A change is kept only if it gains more than 0.01, which is within the battery's noise.
- A pass that changes nothing ends it.

**The settings:**

| Setting | Values tried |
|---|---|
| The space's style | each of the six |
| The email's own style, and the phone's | each of the six, or none |
| Line weight | 0.5, 1, 1.5, 2.5 pt |
| Line tone | black, 35% gray, 60% gray |
| Height | 14, 17, 22, 28 pt |
| Label | above, left |
| Help | above, below, none |
| Gap between questions | 6, 12, 18 pt |
| Label typeface | Helvetica, Times, Courier, Arial, Verdana, Georgia |
| Label size | 9, 11, 13 pt |
| Typed answer size | 8, 10, 12 pt |
| Check box size | 8, 11, 14 pt |
| Check box spacing | three spacings |

## Results

October 1, 2026. Every evaluation is a line in `data/forms/lab/search-2026-10-01.jsonl` (44 layouts), and the best is in `data/forms/lab/best.json`.

**The search converged in two passes.** Of the current form's style, only the answer space changed: **no printed line** (objective 0.563 against 0.520). No other setting gained more than the 0.01 noise threshold.

**The near misses** (each with no printed line):

| Change | Objective | Readable | Written answers | On print | Outside | Height used |
|---|---|---|---|---|---|---|
| None (kept) | 0.563 | 0.641 | 0.491 | 0.02 | 0.12 | 420 pt |
| Heavier check box outlines (1.5 pt; with no line the weight only draws the boxes) | 0.572 | 0.650 | 0.528 | 0.02 | 0.12 | 420 pt |
| The email in a shaded band | 0.569 | 0.647 | 0.501 | 0.02 | 0.11 | 420 pt |
| Taller spaces (22 pt) | 0.569 | 0.646 | 0.501 | **0.00** | **0.05** | 450 pt |
| No help text | 0.565 | 0.635 | 0.479 | 0.05 | 0.12 | 355 pt |

**What hurt:**

| Layout | Objective | Readable | Written answers | On print | Outside |
|---|---|---|---|---|---|
| The current form (thin black line) | 0.520 | 0.598 | 0.408 | 0.00 | 0.17 |
| Short spaces (14 pt) | 0.520 | 0.617 | 0.444 | **0.13** | **0.33** |
| 13 pt labels | 0.512 | 0.598 | 0.429 | 0.06 | 0.12 |
| A box | 0.509 | 0.596 | 0.404 | 0.09 | 0.16 |
| 2.5 pt outlines | 0.499 | 0.578 | 0.449 | 0.02 | 0.12 |
| Courier labels | 0.408 | 0.490 | 0.320 | 0.05 | 0.12 |
| A comb | 0.404 | 0.495 | 0.231 | 0.00 | 0.42 |
| A box for each character | 0.397 | 0.477 | 0.215 | 0.00 | 0.19 |

Reading character boxes along their boxes (`read_cells`) raised them only to 0.422.

**What it means for the Tesseract path:**
- **Any printed edge costs readability.** What the drop-out leaves of a line confuses OCR, which is why no line wins even though the responder model has writers wander more without one.
- **Space height is the containment setting.**
  - At 14 pt, a third of the writing leaves its space and 13% lands on printed text.
  - At 22 pt, nothing lands on print and 5% leaves its space, for 30 more points of page.
  - This agrees with the forms standards' 8 mm (23 pt).
- **The label typeface matters through alignment.** The reader aligns a scan by reading its printed lines. It reads Courier poorly, and those pages fail.
- **A box makes people write over the labels** (9% of words): to keep inside, they write smaller and higher.
- **Character boxes do worst here**, the opposite of NIST. Tesseract can't be told the boxes are the segmentation, and long answers (emails, full addresses) run out of boxes.
- **Phone-quality scans** fail alignment for every layout and pull every score down. That's the registration-mark problem, not a layout one.

**A recommendation**, weighing the vision results below, where every layout reads alike:
- Choose the layout for the people writing on it, keeping in mind the responder model is still an assumption.
- That means 22 pt answer spaces, with a pale or no line, and Helvetica labels at 11 pt.
- Read handwriting with a vision model.

## The readers

The same 12 trials on each layout, read by each reader. The score is the mean credit on the written answers (1 for the same answer, half the likeness otherwise). Results are in `data/forms/lab/benchmark-<date>.json`.

| Layout | Tesseract | Tesseract and hints | qwen3.5:9b | glm-ocr | deepseek-ocr:3b |
|---|---|---|---|---|---|
| The current form (thin line) | 0.379 | 0.408 | 0.947 | 0.966 | 0.351 |
| A box | 0.411 | 0.404 | 0.947 | 0.957 | 0.373 |
| A shaded band | 0.440 | 0.440 | 0.948 | 0.967 | 0.419 |
| **No line** | 0.460 | 0.491 | **0.966** | **0.978** | 0.369 |
| A comb | 0.227 | 0.231 | 0.818 | 0.834 | 0.213 |
| A box for each character | 0.233 | 0.223 | 0.794 | 0.705 | 0.112 |
| The phone in character boxes | 0.388 | 0.420 | 0.947 | 0.872 | 0.362 |

qwen3.6:27b wasn't loaded for any layout: it needs about 25 GB of commit, and 12–14 GB was free.

**Speed:**
- **qwen3.5:9b:** about 1.6 s a page once loaded.
- **glm-ocr:** about 1 s a page. It looped and was cut off at the 4-minute cap on 2 of the 84 pages (one comb page, one with the phone in boxes).

**By responder, on the current form:**

| Reader | Neat print | Hurried print | Cursive | Typed |
|---|---|---|---|---|
| Tesseract and hints | 0.40 | 0.37 | 0.30 | 0.56 |
| qwen3.5:9b | 0.87 | 1.00 | 0.91 | 1.00 |

qwen3.5:9b takes about 4 seconds a page.

**What it means:**
- **The reader matters far more than the layout.** A vision model reads simulated handwriting at 0.95 to 0.98 on plain layouts: a line, a box, a band, or no line, with no line best for every reader.
- **Combs and character boxes hurt the vision models too** (0.70 to 0.83). They break a word into pieces the model then has to put back together, and a long answer runs out of boxes.
- **It needs no alignment**, so it reads the phone scans the Tesseract path can't place.
- **glm-ocr does well on this task.** It was rejected for recorded deeds because it loops on a full page. Here, given the scan reader's prompt and JSON schema, it answered every page, at 2.2 GB.
- **deepseek-ocr doesn't do well** with the schema prompt.
- **Layout still matters** for the Tesseract path and for keeping writing off the printed text. Choose the layout for the people writing on it, then read with a vision model.

## Applied to the owner form

The findings are `FormStyle` (`mystique/forms.py`): **22 pt writing space, 60% gray lines, typed answers at 10 pt**. They apply to the template Doc's writing and signature lines, the HTML form, and the fillable fields ([forms.md](forms.md), "Formats").

**The line, at a 22 pt space** (the lab battery; Tesseract and hints / qwen3.5:9b, credit on written answers):

| Line | Tesseract and hints | qwen3.5:9b | Neat print, qwen3.5:9b |
|---|---|---|---|
| Black, 0.5 pt (today's color) | 0.373 | 0.878 | 0.58 |
| 35% gray, 0.75 pt | 0.418 | 0.958 | 0.92 |
| **60% gray, 0.5 pt (chosen)** | **0.497** | **0.969** | 0.92 |
| None | 0.501 | 0.968 | 0.91 |

A black line hurts even the vision model: neat print, written close to the line, loses its letters' feet. A 60% gray line reads as well as no line, and still tells people where to write.

**The real owner form, both ways** (built locally from the HTML version, made fillable, linted, and the same 30 fuzz cases, October 1, 2026):

| | Old (17 pt, black lines, 8 pt multi-line typing) | New (22 pt, 60% gray, 10 pt typing) |
|---|---|---|
| Typed answers right, with hints | 90.2% | 90.9% to 93.9% (two runs) |
| Handwritten answers right, with hints | 34.6% | 42.3% |
| Handwriting likeness | 0.661 | 0.721 |
| Pages | 2 | 2 |
| Lint | — | clean |

The phone-quality scans failed alignment in both, the registration-mark problem.

The template Doc in Drive still has the old style until it's rewritten and the packet rebuilt (`jason packet owner-information --make-templates --yes`, then `--build --yes`); both write to Drive.

## Where the label goes

October 1, 2026. The lab's form was drawn six ways at the owner form's style (22 pt, 60% gray lines), with `Layout.label` and `Layout.columns`. The same 16 trials each: office, home, and phone scans, and four responders. Samples and scores are on the comparison page `data/owner-info/preview/layout-strategies.html`.

| Strategy | Written answers, Tesseract and hints | Vision model (qwen3.5:9b) | Writing on printed text | Height |
|---|---|---|---|---|
| Labels above (today) | 0.590 | 0.978 | 0% | 450 pt |
| **Labels above, short answers side by side** (email and phone in one row) | **0.594** | 0.970 | **0%** | **382 pt** |
| Cell captions (a small label in each ruled cell's corner) | 0.538 | 0.970 | 0% | 358 pt |
| Tabular (labels in a left column, wrapped) | 0.546 | 0.920 | 19% | 375 pt |
| Caption below the line | 0.490 | 0.977 | 22% | 375 pt |
| Caption below, side by side | 0.488 | 0.945 | 21% | 322 pt |

**Findings:**
- **Nothing printed goes right under a writing line.**
  - A caption under the line, or tabular help printed under the line, catches the tails and slips of a fifth of the handwriting.
  - The scan reader then has printed text inside the writing to drop out.
  - Labels and help go above the space.
- **Side by side for short related answers.** An email and a phone on one row read as well as on separate rows, take 15% less height, and keep the reading order.
  - Long answers (addresses, names of several people) keep the full width.
- **Cell captions** are the most compact, with no writing on the print, but OCR reads them less well, and the dense ruled grid feels like a tax form. They suit a form filled by staff better than one an owner fills at home.
- **Tabular** looks orderly and scans well by eye, but its spaces are narrower, long labels wrap, and the vision model reads it worst.

**Recommendation for the owner form:**
- Keep labels and help above each space.
- Put short related answers side by side: the representative's email and phone.
- Keep addresses and names full width.

The paper form is a Google Doc. A row of two answers there needs a two-column table, which the Docs renderer doesn't make yet.

## Telling the model the form's rules

Does knowing the template and its rules help a vision model read? `jason form-lab --prompts MODEL ...` (`form_lab.prompt_trial`) tests it. Each model reads the same handwritten and typed scans (12 trials) three times:

1. **plain:** the scan reader's prompt, the fields and their titles;
2. **rules:** plus what each answer looks like, in the prompt and as JSON-schema descriptions (one email with no spaces; a 10-digit phone; a unit address on one of the community's streets, with its city, state, and ZIP), and "if what is written does not fit, write it exactly as written; do not correct it";
3. **rules+sent:** plus the answers the copy was mailed with, and "the person may have written different ones; report what is on the page now".

**The three sets:**
- **As written:** the answers as sent.
- **Edited:** two answers changed from what was sent, 24 changed fields in all.
- **Malformed:** an email with its "@" written as "at" or a dot left out, and a phone a digit short, 19 broken fields.

Results are in `data/forms/lab/prompts-2026-10-01.json`.

| Model | Set | plain | rules | rules+sent |
|---|---|---|---|---|
| glm-ocr | as written | 0.957 | 0.957 | 0.989 |
| glm-ocr | edited | 0.962 | 0.962 | 0.821 |
| glm-ocr | malformed | 0.914 | 0.914 | 0.784 |
| qwen3.5:9b | as written | 0.956 | 0.956 | 1.000 |
| qwen3.5:9b | edited | 0.960 | 0.960 | 0.969 |
| qwen3.5:9b | malformed | 0.968 | 0.978 | 0.978 |

**The traps:**

| Model | Changed answers read as the old value it was told (of 24) | Broken answers "corrected" to the valid one (of 19): plain / rules / rules+sent |
|---|---|---|
| glm-ocr | 13 with rules+sent; 0 otherwise | 6 / 5 / 17 |
| qwen3.5:9b | 0 | 0 / 0 / 2 |

**What it means:**
- **The rules didn't help.** Format descriptions changed neither model's reading of what is written. A model reads the writing it sees, and a rule doesn't make a letter clearer.
- **What was sent looks like help, and is copying.**
  - On untouched copies it lifts the score to 0.99 and 1.00, but that's the model repeating the list.
  - glm-ocr reported the old value for more than half of the owners' changes.
  - It "corrected" 17 of 19 broken answers back to what was sent.
  - Either way, the owner's update is lost and nothing shows it.
- **glm-ocr also "corrects" without being told:** 6 of 19 broken emails and phone numbers came back valid with the plain prompt. A reader that fixes what it reads hides the owner's mistake, which a person should see.
- **qwen3.5:9b stayed faithful:** no old values, and 2 corrections only when told what was sent.

**This understates the risk.** Here an edited copy shows only the new answer. On a real pre-filled copy the old answer is printed on the page and the owner crosses it out, which makes copying the old value easier.

**So:**
- **Never put what a copy was sent with in a model's prompt.** Compare afterward in code, where `form_hints` keeps a reading as what was sent only when OCR could have read it either way, and marks it.
- **Keep the prompt plain.** Put the format rules after the reading, in `form_hints`, where every repair is marked "+hint" and a person sees it.
- **Prefer qwen3.5:9b over glm-ocr for owner answers.** glm-ocr scores about 0.01 higher, but it changes what people wrote.

**Caveats:**
- The handwriting is fonts with jitter, not people.
- A vision model may read a handwriting font more easily than real writing.
- Confirm on a few real filled and scanned copies before relying on these numbers.
