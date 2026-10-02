# Reading returned forms, and their markers

Owners return the owner-information form three ways: signed in through PayHOA, as the emailed PDF typed into, or on paper (scanned or photographed). The PayHOA answers and the typed PDF are read field by field (`fillable.read_answers`). Paper goes through the form-aware reader below. Every reading is evidence for a person to confirm, never an answer recorded on its own.

## The layout

`form_layout.read_layout` reads the blank fillable PDF:
- **every field's box:** each text field, check box, and radio button, with the option it stands for;
- **every printed line and word,** with its position.

The fields are the reading targets. The printed lines and words anchor the alignment.

## The reader (`form_reader.read_scan`)

1. **Align.** OCR (Tesseract through PyMuPDF) reads the cleaned scan. A 3-pixel median takes out speckle.
   - A rough affine comes from the printed lines matched by their words.
   - A precise one comes from the printed words matched near where the rough fit puts them. There are hundreds, all over the page, and the outliers are dropped.
   - On the test scans the error is under a point.
2. **Drop the form out.** The blank form is drawn onto the scan through that transform, widened by a few pixels, and taken away. What's left is what the person added.
3. **Boxes.** A box is marked when the added ink covers more than 7% of it, at its best within 1.5 points. On the test scans marked boxes read 8 to 17% and empty ones 0 to 5%. In a radio group the most-marked box wins, and it must clearly beat the next.
4. **Writing.** Each text field's area of the added ink is cleaned of slivers of the writing line and dust, then read by OCR. With `VisionReader`, the page goes to the local vision model (`qwen3.6:27b`, thinking off) with the text fields as a JSON schema. That's for handwriting, and the model's words are kept where OCR read none.
5. **The marker**, if any, is found in the OCR text by `form_refs.parse` and in the bar mark by `form_marks.read` (`find_marker`). It is a hint and changes nothing in the reading.

Since the first fuzz runs ([form-fuzzer.md](form-fuzzer.md)):
- The blank page's own words are taken out of each field before it's read.
- OCR reads the scan's gray around the person's ink.
- A page fed upside down is tried turned round.
- An alignment more than 4 points off reads nothing.
- A box is measured in its middle.

The reading hints (`form_hints`) then put OCR's misreads right from what each answer holds and, for a pre-filled copy, what was sent.

**Which form a page is** comes from its printed lines (`form_reader.identify_form`), never from a marker.

## Testing (`tasks/form_scans`)

`simulate` turns a filled PDF into a scan: flattened, rendered at 150 dpi, turned, scaled, shifted, speckled, and saved as an image-only PDF. `score` compares a reading with what was filled in.

**Results, October 1, 2026:**
- With test values on the owner form, every box read right at 0.3°, 1.2°, and −2°.
- Text came back right in substance; at 150 dpi, OCR misreads some letters ("Aaent" for "Agent").
- The test suite runs the whole path on a simulated scan (`tests/test_form_reader.py`).

**Not yet tried:** the vision model on these scans. Windows had too little commit free to load the 27B model. Add a row to the model trials in [document-tools.md](document-tools.md) when it runs. Real handwriting needs a person to print, fill, and scan a copy.

## Markers (`form_refs`)

Each copy jason sends carries a marker. An emailed copy's marker names that copy (`NP27E-4RK9T-C7`). The mailed letter, the same for everyone, carries the campaign's marker (`NP27M-…`). The format, the alphabet, and the scan trials behind them are in [form-identifiers.md](form-identifiers.md).

**What's kept:** once a copy is sent, `form_references.record` keeps the form, cycle, owner and unit ids, the send dates, and the fingerprints of what was pre-filled in `data/forms/references.json`. That's ids and hashes, no address or email. `form_references.lookup` finds the copy from any text: a reply's subject or body, or a scan's OCR. If a marker fails its check, it's taken to the one sent marker a single character away, if there is exactly one. The return is then compared with exactly what that owner was sent (`owner_prefill.compare`).
