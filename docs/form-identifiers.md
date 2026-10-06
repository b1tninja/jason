# Form identifiers: markers on what jason sends

A form jason sends can carry a **marker**: a short code saying which campaign it belongs to and, when copies differ, which copy it is. A marker is a **hint**. It is never what the reading depends on:

- **The form** is recognized from its own printed lines (`form_reader.identify_form`), so a page whose marker is missing or smudged is still the owner form.
- **Every answer** is read from the page itself, the same way with or without a marker.
- **A marker that reads back** only names the campaign or the copy, so the answers can be compared with what was sent (`owner_prefill.compare`). A marker that fails changes nothing but that.

The code is `jason.community.form_refs`. The record of what was sent is `jason.tasks.form_references` (`data/forms/references.json`: ids and hashes, never an address or an email). Each delivery engine decides which kind of marker it uses (`jason.tasks.delivery_engines`).

**The campaign record: a reference exists only if a handler does.** A marker is made only for a form whose campaign a person has opened (`jason campaigns --open FORM --channel C --cycle-year Y --by NAME`; `jason.tasks.campaigns`). The record, one row for each campaign code (`NP27E`), is `data/forms/campaigns.json` (ids and words, no address, no owner), keeps the form and its library version and as-of day, its authority (empty for a form tied to no law), the handler and its options, the procedure, the cycle (opened, return-by), the channel, who chose it and when, and open or closed. A form with an authority takes the process handler its authority names; a form with none takes a general handler a person chooses from the fixed list. The generators (`jason owner-info --email-batch`, `--mail-batch`, `--prefill --emailed`) call `campaigns.gate` first and refuse, as `jason: <reason>`, a form that is not offered, has no registered handler or procedure, has the wrong handler for its authority, or has no open campaign; a dry run says the same. Each sent copy's entry in `references.json` then carries `campaign` and `formVersion` (`campaigns.stamp`), so an arrival with a reference is routed to its handler by one lookup (`SentCopy.campaign`, `.handler`). A cycle that was running before the record is adopted from the profile's response requests (`jason campaigns --adopt`, or the first real send), and an older entry with no `campaign` is read as belonging to the campaign its marker's prefix names; no entry is rewritten. The PayHOA form's `P` marker is not stamped by jason, so no gate sits there yet.

**Finding the copy.** `jason.tasks.recognize` is the one place that reads a reference in order of cost (the subject, an attachment's text layer, the hidden `reference` field, the bar mark and printed marker on a scan, then the form by its layout and the cited authority when no marker survives) and ends in the sent-copy catalog above: the form, cycle, owner and unit as sent. A reference one character off is taken to the one sent reference it is near; one whose check holds that was never sent is flagged. The corpus and its measured counts are in `tests/test_recognize.py`; the design is [arrivals-design.md](arrivals-design.md) ("Recognition is the crux").

## Campaign or copy

| Engine | What goes out | Identity | Marker |
|---|---|---|---|
| Mailroom (`MailroomEngine`) | the same blank letter to every owner | campaign | `NP27M-H3` |
| Email (`EmailEngine`) | each owner's own pre-filled copy | copy | `NP27E-4RK9T-C7` |
| PayHOA's form (next) | the online form | campaign | `NP27P-…` |

Knowing the campaign is often enough. A mailed letter is blank, so the copy says nothing the owner doesn't write on it. The unit address the owner writes places the return, and the campaign marker says which mailing it answers. A pre-filled copy is different: the copy marker names the owner and unit it was filled for, so the return is compared field by field with exactly what was filled in.

## The format

`NP27E-4RK9T-C7`:

- **`NP`** is the form's code (`FormTemplate.code`; the owner-information form is "notice preferences").
- **`27`** is the cycle's year.
- **`E`** is the channel: `E` email, `M` mail, `P` PayHOA. `NP27E` together is the campaign.
- **`4RK9T`** is the copy: five characters from a SHA-256 of the campaign, membership id, and unit id. It is left out for a campaign marker. The same copy always gets the same marker, so a resend doesn't change it, and it says nothing about the owner.
- **`C7`** is two check characters: the body's values summed with weights *i* and *i*², each modulo 23. Because 23 is prime and larger than the body, every single misread character and every swap of two neighbors changes the check (`tests/test_form_reader.py` tries them all).

**The alphabet** is 23 characters OCR keeps apart: `0-9 A C E F H K M N P R T V X`. When OCR returns a look-alike, it is read as the character it stands for:

| Read as | Look-alikes |
|---|---|
| `0` | O, D, Q |
| `1` | I, J, L |
| `2` | Z |
| `5` | S |
| `6` | G |
| `8` | B |
| `V` | U, Y |

**Reading it back.**
- `parse` tries every position, so a label run into the marker (`RefNP27E…`) can't hide it.
- It allows up to three separators (spaces, hyphens, dots) between characters.
- It reads each position both with a copy part and without, so `NP27M-H3 Owner` isn't swallowed into a longer reading.
- It keeps only markers whose check holds.
- **The two checks also repair one misread character** (`correct`, `repaired`). They work as syndromes. A single error of size *d* at position *p* leaves (*p*+1)·*d* in the first check and (*p*+1)²·*d* in the second. Their ratio names the position, and the first gives the size. An error in a check character leaves the other check at zero. Two errors can look like one put right somewhere else, so a repaired marker is a hint to confirm against what was sent or against a second reading. The reader says so ("text (put right)").
- `closest` handles a marker that fails its check. If it differs in one character from exactly one marker that was really sent, it's taken to that marker. With two or more candidates, it returns nothing: it never guesses.

**Where it appears** (`fillable.stamp_reference`):
- printed at 9 points, near black, at each page's top right;
- again as a **bar mark** in gray at each page's top left (below);
- in a hidden read-only form field (`reference`) and the PDF's keywords, for a returned PDF;
- in an emailed copy's subject (`[Ref …]`) and message, for a reply.

Lob prints its address page first, so the top right of our own pages is clear of the address window.

## Why not a QR code, and what else was tried

**No QR code.** A QR code invites the recipient to scan it, and this mark is for jason, not the owner. QR codes were left out on purpose.

The designs below were tried on simulated scans of the real owner form, ten trials per design per level (`form_scans`-style simulation: rendered at the given resolution, turned, blurred, speckled, and JPEG-compressed).

**First round: Crockford base 32 with an `OI27` prefix.** It failed in ways that shaped the final design:
- The prefix's own `O` and `I` were misread.
- OCR read `J` as `I`, `5` as `S`, `B` as `8`, and `0` as `@`.
- A machine-readable typeface (OCR-A) read worst of all, because Tesseract isn't trained on it.
- Text under 8 points was lost at 150 dpi.

**Second round: the 23-character alphabet.**

| Design | Clean, 300 dpi | Office, 200 dpi | Home, 150 dpi | Phone or fax, 120 dpi |
|---|---|---|---|---|
| Text, Helvetica 8 pt | 10/10 | 10/10 | 10/10 | 0/10 |
| Text, Helvetica 10 pt | 10/10 | 10/10 | 10/10 | 0/10 |
| Text, Helvetica bold 10 pt | 10/10 | 10/10 | 10/10 | 0/10 |
| Text printed twice (top and bottom) | 10/10 | 10/10 | 10/10 | 0/10 |
| Text, with the near match against 100 sent | 10/10 | 10/10 | 10/10 | 0/10 |
| Bit grid (7 × 5 squares, 30 bits and parity) | 10/10 | 10/10 | 2/10 | 1/10 |

**The real stamp** (`stamp_reference`, 9 pt, dark gray), half copy markers and half campaign markers:

| Clean | Office | Home | Phone or fax |
|---|---|---|---|
| 10/10 | 10/10 | 9/10, and the 10th by near match | 0/10 |

**At 120 dpi no printed text reads.** Preparing the strip before OCR didn't change that. A threshold, a median and threshold, and a sharpen each read 0/10, and a ×2 upscale with sharpening read 2/10, so none was adopted. The bar mark below closes that gap.

## The bar mark (`form_marks`)

Postal barcodes are built for bad scans:
- **USPS's Intelligent Mail barcode** encodes 31 digits in 65 bars of four states (tracker, ascender, descender, full), with an 11-bit CRC that detects errors but doesn't correct them ([Wikipedia](https://en.wikipedia.org/wiki/Intelligent_Mail_barcode); the specification is USPS-B-3200).
- **Australia Post's 4-state code** adds twelve Reed-Solomon bars over GF(64) that correct errors ([Accusoft](https://help.accusoft.com/BarcodeXpress/v13.4/BxNodeJs/australia_post_4_state.html)).

A 4-state code is read from where the ink is, not by OCR, and no phone app offers to scan it.

The bar mark is jason's own 4-state code carrying the same marker. It is not a postal one: nothing on a page inside the envelope is for the sorting machines.
- **Each character** is three bars (4³ = 64 patterns ≥ 23 symbols).
- **The marker's check characters ride along.** A misread bar fails the check, and one misread character is repaired.
- **A frame** of a full bar and an ascender opens it, and a descender and a full bar close it. The full bars at the ends give the middle line however the page is turned. The mark is read both ways round, so a page fed upside down reads too.
- **Size:** bars 1.8 pt wide every 4 pt. The tracker is 3.6 pt tall and a full bar 10.8 pt. A copy's mark (12 characters) is 40 bars and 160 pt long; a campaign's is 25 bars and 100 pt.
- **Color:** gray (35%), like a watermark, at the top left, clear of Lob's address block (3.15″ × 2″, 0.6″ from the left and 0.84″ from the top of a first page; [Lob letter specs](https://help.lob.com/print-and-mail/designing-mail-creatives/mail-piece-design-specs/letters)). The PayHOA Mailroom inserts its own address page anyway.

**Reading it** needs no page alignment:
- Columns of ink a bar's width form the bars, and a run of bars at the pitch forms a row.
- Each bar's top and bottom against the middle line (through the two end bars) give its state.
- The region is tried at a few cuts: plain ink, two lighter cuts for a faint copy, and Otsu's split of its own grays. The check keeps any wrong reading out.

**Trials**, ten per level, beside the printed marker:

| Scan | Printed marker | Bars, black | Bars, 50% gray |
|---|---|---|---|
| Clean, 300 dpi | 10/10 | 10/10 | 10/10 |
| Office, 200 dpi | 10/10 | 10/10 | 10/10 |
| Home, 150 dpi | 10/10 | 10/10 | 10/10 |
| Phone or fax, 120 dpi | 0/10 | 10/10 | 10/10 |
| Fax, 100 dpi, turned 3° | 0/10 | 8/10 | 9/10 |
| Upside down, 150 dpi | 0/10 | 10/10 | 10/10 |

No reading named a wrong marker.

The fuzzer's fax profile is also a faint copy (gamma 1.3). There, 50% gray read 0/12 and 35% gray read 8/12 with the lighter cuts, so the stamp uses 35%.

**In the fuzzer's 60 cases** ([form-fuzzer.md](form-fuzzer.md)), the marker read on 59:

| How it read | Cases |
|---|---|
| Printed text and bars, agreeing | 45 |
| Bars alone (fax, phone, upside down) | 12 |
| Printed text repaired by its checks | 2 |

The reader keeps a reading only when its check holds. If the printed marker and the bar mark both read and name different markers, it keeps neither and notes the disagreement (`form_reader.find_marker`).

**Considered and not tried:**
- **A 1D barcode** (Code 39 or Code 128). It survives low resolution with wide bars, but it looks like something to scan, the same objection as QR, and it needs another decoder. The 4-state bar mark gets the same tolerance without that look.
- **Hidden marks** (micro-dots, yellow dots, altered word spacing). These are fragile under scanning and compression, a person can't read them, and they are opaque to the owner. Rejected.

**What identifies a return without any marker:**
- **The form's printed lines** (`identify_form`): which form, and which of its pages.
- **The channel and its timing:** a reply in the email's Gmail thread, a PostScanMail scan after the mailing, a PayHOA form submission.
- **What the owner writes:** the unit address places the return. On a pre-filled copy, the filled values themselves match their fingerprints in `references.json`.

## Rules for a new marker

- Use the 23-character alphabet and `form_refs.make`; don't make a new scheme.
- Print it at 9 points or larger, near black, in plain Helvetica, never in an OCR typeface, with its bar mark beside it.
- Keep the marker's two places clear on every page. `jason form-fuzz --lint` checks them.
- Give a form its own two-letter code (`FormTemplate.code`), using letters of the alphabet.
- Use a campaign marker unless copies differ. A copy marker is for pre-filled copies only.
- Never let a reading depend on it.
