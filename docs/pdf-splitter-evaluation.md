# The PDF splitter: how to measure it, calibrate it, test its use, and roll it out

Status: design (2026-10-11). Nothing here is built. This is a plan for finding out whether [the splitter](pdf-splitter.md) and its suggestions work on a real archive, **without any agent or any tracked file ever holding the archive's content**. General for any association: no name, street, vendor, or id here belongs to one. Every example is made up ("Example Village HOA", "123 Main St", "scan-0042").

## The situation this plan is written for

A person holds a private archive: about 270 PDFs and about 6,000 pages in all, a median of 4 pages a file, a few files over 140 pages. The paper was scanned in stacks, in order, and combined into PDFs. Its content is private. **No agent reads it, and nothing derived from its content is checked in.** The person splits it themselves, in the splitter, and the only ground truth that will ever exist is **the boundaries that person confirms**.

Three consequences shape everything below:

1. **Measurement can use numbers and enumerated words only.** No file name, no text, no picture, no hash that identifies a document (section 1.3).
2. **The truth is a person's confirmation, and a person can be led by what is shown.** A suggestion the person accepts looks like a hit whether or not it was right. Section 2.2 builds the correction into the design (a blind pass on a sample of files) instead of hoping it away.
3. **The sample is small and lumpy.** Planning figure: 6,000 pages at a median document of 4 pages is at most about 1,500 documents, so at most about 1,200 confirmed internal boundaries, and the mean file (about 22 pages) is five times its median: a few large files will hold a large share of the boundaries, and their boundaries are not independent. Every interval below is computed by file, not by page (2.4).

What this plan does not do: it does not tune the suggestions on the private archive in any way that puts a fact from it into code. A number (a weight, a threshold) may change in a reviewed code change, with the **aggregate** evidence in the lesson that explains it; a fact about a document never does ([AGENTS.md](../AGENTS.md), "Facts are data").

## 1. Measurement without exposing content

### 1.1 What is recorded, and the rule that governs it

When a person confirms splits, the console can write a **local stats log**: counts, page numbers, durations, and words from closed lists. The rule is one sentence, and the code enforces it:

> An event holds integers, booleans, and values from a closed list. It holds no string that a person or a file supplied.

So: no file name, no title, no page text, no thumbnail, no hash of the file, no Drive or library id, no free-text comment. A page is a number. A signal is its key from the cue table (`page-one`, `dpi-change`: names of rules, not of anything in a document). The person is a small integer (`p1`, `p2`) assigned by the install, never a name or an email.

### 1.2 Where it lives, who may turn it on, and how it goes away

| Question | Answer |
|---|---|
| Where | `data/split/stats/events-YYYY-MM.jsonl`, one JSON object a line, append only. `data/` is git-ignored, and `PATH_RULES` already places `split/*` at P3, so `/api/file` cannot serve it ([pdf-splitter.md](pdf-splitter.md), 9.4). It is never in a log line, a URL, a history line, or an MCP result |
| Who writes | the console, in batches of at most 50 events, to `POST /api/write/split/stats` on page hide and every 30 seconds. The server **validates every event against the allowlist** (1.4) and drops, with a count, any event that does not fit. A client cannot widen the schema |
| Opt-in | off until switched on. A switch `split.stats` (kind: switch, default **off**), shown on the Setup > Split screen in words: "Keep counts of how splitting goes on this computer. No file names, no text, no pictures. You can see them and delete them at any time." Turning it on is a person's act, recorded as an event (`stats.on`). A second, per-person choice (`p1` may decline while `p2` agrees) is kept with the person's pseudonym |
| Retention | `split.stats_days` (count, default 365, 30 to 1,825). The sweep that removes old drafts removes old months |
| Purge | `jason split --stats --purge --yes` deletes every event file **and the install's salt** (1.3), so even a copy of an old export cannot be tied to a file again. The Setup > Split screen has the same button behind a `Confirm` that says how many events go |
| Export | `jason split --stats --export FILE --yes` writes the aggregates (and, with `--rows`, the per-page rows of 1.5) to a file the person chooses. Sharing it with anyone is that person's act. jason never sends it anywhere |
| Not a record of work habits | times are kept per install, not per name; the dashboard (section 6) shows a person only their own pseudonym's numbers unless an administrator turns the group view on |

Registered the way the other limits are ([instance-limits.md](instance-limits.md)): `split.stats` as a switch and `split.stats_days` as a count, each with its reason and refusal words. A switch that turns a safety check off does not exist, and this is not one: it turns a measurement off.

### 1.3 Identifiers without identity

| Id | What it is | Why it is safe |
|---|---|---|
| `s` | the session id the splitter already makes (random, not derived from a file) | links the events of one sitting; says nothing about the file |
| `f` | `HMAC(install_salt, source_sha256)` truncated to 8 hex characters | lets two sessions on the same bytes be recognised as one file, which the holdout in 2.5 needs. It cannot be reversed to a document or compared with any other install. The salt is random, kept in `data/split/stats/salt`, and deleted by the purge |
| `p` | a small integer per person on this install | groups a person's sessions for the learning curve; no name |
| `g` | an optional batch label, a small integer the person chooses ("box 3" is `3`) | lets the holdout leave out a whole scanning batch, the real source of correlation between files |

The text of a batch label is never stored: `g` is a number the person typed, and the screen says what it is for.

### 1.4 The event schema

Every event has the envelope `{"v":1,"t":<epoch ms>,"s":"<session id>","e":"<kind>", ...fields}`. Fields are listed per kind. A field not listed is rejected. A string field takes one of the listed words and nothing else. Integers have bounds (a page is 1 to `split.max_pages`; a duration is 0 to 86,400,000).

Closed lists used below: `view` = `album | filmstrip | scroll | list | loupe | compare | corner`; `input` = `key | pointer | touch`; `band` = `high | medium | low`; `reader` = `rules | model | rules+model`; `act` = `accept | reject | edit | add | remove | move | level | undo | redo`; `refusal` and `error` codes are the registry's keys (`split.max_pages`, `split.client_render_max_pages`, `no-renderer`, `unreadable`, `conflict`, `stale`, `offline`, `save-failed`, `render-failed`); `flag` = the keys of `split_flags` (`blankOnly`, `nearDuplicate`, `sideways`, `overPartLimit`, `slotFilled`, `mayHoldMore`).

| Kind (`e`) | Fields | Written when |
|---|---|---|
| `session.open` | `f`, `p`, `g?`, `pages`, `size_mb` (a bucket: 1, 5, 20, 50, 100, 200, 400+), `src` (`library | drive | upload | path`), `text_layer` (`none | partial | full`), `mode` (`normal | blind`, 2.2), `n_sug` (suggestions made), `n_sug_high`, `n_sug_med`, `n_sug_low` | a session opens or resumes |
| `suggestion.shown` | `page`, `conf` (rounded to 0.01), `band`, `reader`, `sig` (list of up to 6 `[key, weight]`), `seen` (true when it was in view 300 ms or its reason was opened) | once per suggestion, when it first appears on screen (batched) |
| `suggestion.act` | `page`, `act` (`accept | reject | edit`), `to?` (the page an edit moved it to), `ms` (time from first seen to the act), `input`, `view` | an act on a suggestion |
| `mark` | `page`, `act` (`add | remove | move | level`), `to?`, `input`, `view`, `blind` (true when no suggestion was visible to influence it) | a person's own boundary change |
| `bulk` | `kind` (`nth | blank | restarts | accept_high | accept_medium | reject_below | clear`), `count`, `undone` (filled in later) | a bulk act |
| `undo` / `redo` | `n` (steps), `input` | undo or redo |
| `view` | `from`, `to`, `input` | a change of view |
| `focus` | `ms` in each `view` since the last event, as a map `{view: ms}` | every 10 s of active time and on page hide |
| `active` | `ms` (active milliseconds in the last bucket), `segment_ord?` (the ordinal of the segment the centred page falls in, so time per document can be assigned) | every 10 s while there is input; idle gaps over 30 s are not active |
| `flag.open` | `flag`, `segment_ord`, `acted` (true if the person then changed a boundary) | a flag dialog is opened |
| `loupe` | `mode` (`hover | key | touch`), `zoom` (2 to 6), `dwell_ms`, `sharp_ms?` (from the 150 ms dwell to the sharp picture swapped in, null if never), `sharp_src` (`server | browser | none`), `ok` | each time the magnifier shows a sharp picture or gives up |
| `thumb.timing` | `first_ms` (open to first tiny picture), `first_screen_ms` (open to the whole first screen drawn), once per session; and per 60 s: `req` (picture requests), `aborted`, `long_tasks`, `p95_frame_ms` | the console's own counters |
| `rotate` | `n` (pages turned), `fix` (how many used the measured fix), `input` | a rotation chosen |
| `refuse` | `code` | a limit or a refusal in words reached |
| `error` | `code`, `page?` | an error shown |
| `review` | `segments`, `drops`, `collisions`, `duplicates`, `ms` (time in the review drawer) | the review opened |
| `session.confirm` | `segments`, `boundaries` (list of the confirmed start pages, page 1 first), `n_accepted`, `n_edited`, `n_rejected` (explicit), `n_implicit_rejected` (open at confirm and not boundaries), `n_added` (the person's own, not from a suggestion), `n_blind_added`, `active_ms`, `wall_ms`, `undo`, `redo` | confirm |
| `session.end` | `reason` (`applied | declined | left | stale`), `active_ms`, `wall_ms` | the session closes |
| `page.row` | `page`, `sig` (list of `[key, weight]` that fired on that page, from the engine, including below the floor), `truth` (1 if a confirmed start), `how` (`accepted | edited | own | none`) | at confirm, **sparse**: only pages where a signal fired or the truth is 1. A page with neither is an implicit negative, counted by `pages` in `session.open` |
| `stats.on` / `stats.off` | `p` | the switch |

Example lines (made up):

```
{"v":1,"t":1760203200123,"s":"k3x9","e":"session.open","f":"a41c09de","p":1,"g":3,"pages":40,"size_mb":5,"src":"upload","text_layer":"full","mode":"normal","n_sug":7,"n_sug_high":4,"n_sug_med":2,"n_sug_low":1}
{"v":1,"t":1760203201900,"s":"k3x9","e":"suggestion.act","page":12,"act":"accept","ms":2100,"input":"key","view":"album"}
{"v":1,"t":1760203240000,"s":"k3x9","e":"loupe","mode":"hover","zoom":3,"dwell_ms":150,"sharp_ms":230,"sharp_src":"server","ok":true}
{"v":1,"t":1760203600000,"s":"k3x9","e":"session.confirm","segments":8,"boundaries":[1,5,12,19,22,27,31,36],"n_accepted":5,"n_edited":1,"n_rejected":1,"n_implicit_rejected":0,"n_added":2,"n_blind_added":0,"active_ms":312000,"wall_ms":420000,"undo":3,"redo":1}
```

The **validator** (`jason.community.split_stats.validate`, pure) takes an event and returns it or a refusal word. A test feeds it a made-up file name, a page's text, a data URL, and an over-long list in every field, and asserts that each is refused; a second test asserts that a schema change which adds a string field outside a closed list fails the build. That test is the guard that keeps "no content" true as the code grows.

### 1.5 What each number answers

| Question | Computed from |
|---|---|
| Are suggestions right? | `suggestion.shown`, `suggestion.act`, `session.confirm.boundaries` (precision by signal and band, 2.1) |
| What do they miss? | `page.row` with `truth=1` and no signal, or `how=own` (recall; which starts have no signal at all) |
| Which signal helps or hurts? | `page.row.sig` against `truth` (2.6) |
| Does a suggestion save work? | `n_added` against boundaries; time per accepted, rejected, and added boundary (2.7) |
| How long does a document take? | `active` with `segment_ord`; `session.confirm.active_ms` over `segments` |
| Which view and input work? | `mark.view`, `mark.input`, `focus`, `view` |
| Do flags earn their place? | `flag.open.acted` |
| Is it fast enough on this machine? | `thumb.timing`, `loupe.sharp_ms` against the budgets (section 4) |
| Is the person struggling? | `undo`, `redo`, `bulk.undone`, `refuse`, `error`, a long `review.ms` |

### 1.6 `jason split --stats`

```
jason split --stats                      aggregates for everything kept (text)
jason split --stats --since 2026-10-01   a window
jason split --stats --person p1          one pseudonym (default: all)
jason split --stats --json               the same as JSON
jason split --stats --rows --export FILE the per-page rows for scripts/split_fuzz.py (numbers only)
jason split --stats --on | --off         the switch (a person's act, logged as an event)
jason split --stats --purge --yes        delete the events and the salt
```

Made-up output:

```
Split statistics (events kept: 4,812; from 2026-10-02; 31 sessions, 28 files, 1,106 pages)
Time      active 6 h 12 m; median per session 9 m; median per document 2 m 40 s (n 214)
Suggest   shown 187: high 96 (accepted 91, edited 2, rejected 3), medium 61 (36, 9, 16), low 30 (6, 5, 19)
Own       boundaries added without a suggestion: 58 of 330 confirmed (18%)
View      album 61% | filmstrip 14% | scroll 9% | list 12% | compare 4% | magnifier on 22% of sessions
Input     key 44% | pointer 51% | touch 5%   (of marks)
Flags     opened 17; boundary changed after 9
Loupe     opened 143; sharp picture p50 240 ms, p95 610 ms; never arrived 3
Undo      0.9 per session; bulk acts undone 1 of 12
Refusals  split.max_pages 0 | render-failed 2 | save-failed 1
Blind     6 of 28 files; boundaries found blind 41 of 47 (87%)
Calibration and signals: run  python scripts/split_fuzz.py calibrate --rows FILE
```

A cell with fewer than 5 observations prints `n<5` instead of a rate.

## 2. Calibration: from confirmed splits to trustworthy confidence

### 2.1 Definitions

For each file, **truth** is the set `T` of confirmed start pages after page 1 (page 1 always starts a segment and is not a guess). The engine's output at a chosen threshold `θ` is the set `S_θ` of suggested pages whose confidence is at least `θ`. Counting is on pages after page 1.

- `TP = |S ∩ T|`, `FP = |S \ T|`, `FN = |T \ S|`.
- Precision `P = TP / (TP + FP)`, recall `R = TP / (TP + FN)`, `F1 = 2PR / (P + R)`. By band: restrict `S` to suggestions whose confidence is in the band, and score precision only (recall by band is not meaningful: a missed start has no band).
- **Tolerance.** A suggestion one page off the confirmed start (an edit) is a miss at tolerance 0 and a hit at tolerance 1. Both are reported; tolerance 0 is the headline (the person had to move it, which costs a tap), tolerance 1 says whether the engine is close.
- **File-level false alarm rate.** Among files with `T = {}` (a single document: likely most of a median-4-page archive), the share where the engine suggested at least one start at Medium or better. A single-document file is where the engine cannot score recall and can only be wrong in one way, so it is reported on its own.

What counts as a rejection matters. A suggestion that is not a final boundary counts as **rejected** only if the person could have seen it: `seen` true, or the review drawer was opened at confirm (the review lists every start, so a suggestion it omits was passed over). Unseen and unreviewed suggestions are excluded from precision and reported as a count; they are not evidence of anything.

### 2.2 The honest-truth problem, and the blind pass

If a person sees "Suggested start, High" on a page, they accept more often than they would have found it alone. Precision measured from accepted suggestions is therefore biased upward, and recall measured against a truth that includes accepted suggestions is biased upward too. A paper on label bias in assisted annotation would call this anchoring; the plan treats it as a design problem:

- **Blind mode** (`mode: blind`). For a random sample of files (default 1 in 5, chosen by the install and recorded in `session.open`), the person marks first with suggestions **hidden**. When they press *Done marking*, the suggestions appear as ghosts beside their marks, and the person may then add, move, or remove marks. The blind marks are tagged (`blind: true` on `mark`; `n_blind_added`). The truth for a blind file is the **first-pass** set `T_blind`, not the confirmed set after seeing the suggestions; the final set is kept as `T_final` and the two are compared.
- **What the blind sample gives.** An anchoring-free estimate of precision and recall: `P_blind`, `R_blind` against `T_blind`. The gap between the headline precision (from unblind sessions) and `P_blind` is the estimate of how much the screen leads the person. If the gap is over 0.05, headline numbers are quoted with the blind figure beside them.
- **Cost.** A blind file takes longer (the person does the whole task unaided). At 1 file in 5, about 55 of 270 files; the median file is 4 pages, so most of the cost is the few long files. The setting is `split.blind_share` (a share, default 0.2, 0 to 0.5), and the person can decline a blind file once per session ("Skip blind for this file"), recorded as an event so a skewed sample is visible.
- **Large files are blind by choice, not by draw.** A 226-page stack costs an hour; the share applies by file for files up to 60 pages, and for longer files the person picks a stretch (a contiguous block of 40 pages, with suggestions hidden for it). The `blind` flag is then per page range, and `page.row` carries it.

### 2.3 Intervals for small samples

A proportion from `k` successes in `n` trials gets the **Wilson score interval** at 95%:

```
centre = (k + z^2/2) / (n + z^2)
half   = z * sqrt( k(n-k)/n + z^2/4 ) / (n + z^2)         z = 1.96
interval = [centre - half, centre + half]
```

Never the normal approximation (it gives intervals past 1 and a zero-width interval at 0 or n). With zero failures in `n` trials the 95% upper bound on the failure rate is about `3/n` ("rule of three"): 59 correct High suggestions in a row are needed before it is fair to say the failure rate is under 5%.

How wide the interval is at each sample, for a true rate near 0.9 (approximate; the script prints exact ones):

| n | observed 0.90 | Wilson 95% | half-width |
|---|---|---|---|
| 20 | 18 | 0.70 to 0.97 | 0.13 |
| 40 | 36 | 0.77 to 0.96 | 0.10 |
| 100 | 90 | 0.83 to 0.94 | 0.06 |
| 400 | 360 | 0.87 to 0.93 | 0.03 |

**Files are the unit of independence, not pages or boundaries.** Boundaries inside one file share a scanner, a letterhead style, and a person's habit that day. For F1, Pk, WindowDiff, and the lift of a signal, the interval is a **cluster bootstrap**: resample files with replacement 2,000 times, recompute the statistic, take the 2.5th and 97.5th percentiles. Wilson on a proportion is used only for the band-level precisions when a band's suggestions come from many files (at least 10); with fewer, the cluster bootstrap is used there too. The script prints the number of files behind every interval.

### 2.4 Reliability diagram and the confidence

The engine's confidence is `1 / (1 + exp(-3 (score - 0.6)))` of the summed signal weights and is, today, **not calibrated** ([pdf-splitter.md](pdf-splitter.md), 9.4, point 4). Calibration is checked, then fitted.

- **The diagram.** Sort suggestions by confidence and cut into **equal-count bins** (not equal-width: a small sample puts nearly all suggestions in two bins), with at least 20 suggestions a bin, so 3 to 8 bins. For each bin, plot the mean confidence (x) against the observed share that were confirmed starts (y), with the Wilson interval as a vertical bar, and the diagonal. Below the plot, a table twin (bin, n, mean confidence, observed, interval), because a chart alone is not accessible. A bin whose interval excludes the diagonal is a calibration failure and is named in words ("suggestions around 0.85 are right 0.7 of the time").
- **Scores.** Brier score `B = (1/N) Σ (p_i − y_i)^2` and expected calibration error `ECE = Σ_b (n_b / N) |acc_b − conf_b|`, both on the held-out folds (2.5). A model that always says the base rate is the reference: report `B` as a skill score `1 − B / B_ref`, so a number below zero means the confidence is worse than guessing.
- **Recalibration.** With a few hundred suggestions, fit two parameters, not a curve: `p = σ(a · score + b)` by logistic regression on the summed weight (Platt scaling), which replaces `STEEPNESS` and `MIDPOINT` (`a = STEEPNESS`, `b = −STEEPNESS · MIDPOINT`). Isotonic regression is not used below roughly 1,000 suggestions: it overfits a step per observation. The fitted `a` and `b`, their intervals, and the folds' scores are the evidence for a reviewed change to those two constants. They are numbers; no fact about a document is in them.

### 2.5 The holdout is across files, never within one

- **Unit of split:** the **file** (`f`); when the person labels batches (`g`), the **batch**. Pages and boundaries of one file never straddle a fit set and a test set.
- **Folds:** grouped K-fold with K = 5 over files (K = number of batches if there are 3 to 6 and they differ), stratified so each fold has some long files and some single-document files. Rotate: fit on four, score on the fifth, five times, and report the pooled held-out predictions.
- **A final, untouched holdout:** the last 20% of files by the order the person works through them are set aside before any threshold is chosen. They are scored **once**, after the thresholds are frozen, and the result is reported as it is. This guards against the failure recorded in [document-segmentation.md](document-segmentation.md) (Measured): held-out files whose errors were read and then used to change the rules are no longer held out. When a held-out file is looked at to fix a rule, it moves to the fit set and the report says so.
- **Cue changes are not tuned on what they are scored on.** Adding a signal or changing a weight is a fit-set change, evaluated on a fold that was not used to propose it.
- **What the person's earlier files teach later ones inside a session** ([pdf-splitter.md](pdf-splitter.md), 4.6) is a per-session effect and is **switched off** in evaluation sessions (`mode` records it), so the measured engine is the one that will be shipped, not the engine plus the person's own marks.

### 2.6 Does a signal help or hurt

For each signal key `k` (a cue-table row, or `dpi-change`, `colour-change`, `blank-before`, `size-change`), from the `page.row` table (every page where it fired, plus the truth):

| Statistic | Meaning | Computed |
|---|---|---|
| Firings `n_k` and precision `P_k` | of pages where `k` fired, the share that are confirmed starts | Wilson (cluster bootstrap if under 10 files) |
| Base rate `b` | the share of all pages (after page 1) that are confirmed starts | counted |
| Lift `L_k = P_k / b` | how much more likely a start is when `k` fires; 1 means no information | cluster bootstrap |
| Recall contribution `C_k` | the share of confirmed starts where `k` fired | counted |
| Alone-precision | precision among pages where `k` was the only signal | counted |
| Leave-one-out `ΔF1_k` | change in start F1 at Medium or better when `k` is removed and the rest re-scored | replay (below), paired by file, cluster bootstrap |
| Fitted weight `w_k` | a logistic regression of `truth` on the signal indicators with an L2 penalty, compared with the hand weight | grouped folds |

**Replay.** `page.row` holds the signals that fired on each page and their weights, so a signal can be removed and every page re-scored offline (`score = Σ w` over the remaining signals, `confidence = σ(a · score + b)`) without the document. Only pages with at least one signal are kept in the log, which is exactly the pages whose score can matter.

**Verdicts, in words** (the dashboard prints the word, never a colour):

- **Helps:** `L_k` lower bound above 1.5, and `ΔF1_k` interval wholly below 0 (removing it makes things worse).
- **Hurts:** `P_k` interval wholly below the base rate or below 0.3, or `ΔF1_k` interval wholly above 0 (removing it makes things better).
- **Neutral:** intervals that contain 0 or 1 with enough data.
- **Not enough yet:** fewer than 30 firings, or fewer than 10 files in which it fired, or fewer than 10 hits and 10 misses.

**Combinations.** The new signals are weak alone (0.35) and matter in company. Report the precision of each **pair** that fired together at least 30 times; if a pair is far better than its parts, the weights add as designed.

### 2.7 Minimum sample sizes

| Question | Minimum before it is answered | Why |
|---|---|---|
| A band's precision, to within ±0.10 at 0.9 | 40 suggestions from 10 files | 2.3 |
| A claim "High precision is at least 0.95" | 59 consecutive correct, or 150 with at most 6 wrong, from 15 files | the Wilson lower bound clears 0.90 only near there |
| A signal's lift | 30 firings in 10 files | 2.6 |
| Leave-one-out for a signal | the signal fired in 20 files | the paired bootstrap is empty otherwise |
| Reliability bin | 20 suggestions | 2.4 |
| Recalibration (a, b) | 150 suggestions, 40 of them real | two parameters |
| Blind-versus-unblind gap | 30 blind boundaries and 100 unblind | 2.2 |
| Single-document false alarm rate | 40 single-document files | a rate near 0.05 needs that to be seen |

Below a minimum the report prints "not enough yet (n = 23)", and nothing downstream (a threshold, a verdict, a weight) uses the number.

### 2.8 Choosing the High, Medium, and Low thresholds

The bands are at 0.85 and 0.60 today by definition, not by evidence. Replace them with thresholds chosen on cost and checked on held-out folds.

1. **Measure the costs from the log** (median active seconds): `c_acc`, accepting a correct suggestion (a glance and a key); `c_rej`, rejecting a wrong one (a glance, a look at the neighbours, a key); `c_add`, finding and marking a start with no suggestion (scanning, then a mark). `c_add` is the larger by a wide margin, and the point of the engine is the gap.
2. **A suggestion is worth listing** when its probability `p` of being right satisfies `p · (c_add − c_acc) > (1 − p) · c_rej`, so the lowest listed confidence is `θ_low = c_rej / (c_rej + c_add − c_acc)`. With a reject costing 6 s and an add 25 s and an accept 2 s, `θ_low` is about 0.21: low suggestions are worth showing if the person is willing to reject them. That is a **time** argument, so it is paired with a **trust** one: a Low band that is mostly wrong teaches the person to ignore the engine. Low is listed only when the person widens the filter (as designed).
3. **High is for "accept all".** A bulk accept must be safe without looking. Choose `θ_high` as the **lowest confidence at which the lower 95% bound on precision of all suggestions at or above it is at least 0.95** on the pooled held-out predictions (and the blind sample, when it differs). If no threshold meets it with the data in hand, High is empty and the screen says "not enough evidence for a safe bulk accept yet": the bulk button stays, labelled with the count and not the word.
4. **Medium is "look at this one"**: from the lowest confidence where the lower bound on precision is at least 0.70 (so about two in three are worth keeping) up to `θ_high`.
5. **Freeze.** Thresholds are chosen on the fit folds, reported on the held-out folds, and **frozen for a whole batch** of the rollout (section 5); they change only between batches, in a reviewed change, with the numbers in the lesson. Changing them mid-batch confounds the next measurement.
6. **Per kind of file.** Image-only scans (no text layer) have no words to read and only weak signals; report their calibration separately (`text_layer: none`) and let them have their own `θ`. A pooled threshold that is right on average and wrong for scans is the usual failure.

### 2.9 Page-stream-segmentation metrics adapted from the literature

Page stream segmentation (cutting a stream of pages into documents) has been scored three ways in the literature: as a **boundary detection** problem (precision, recall, F1 of the cut points, as above), with the **windowed disagreement** measures from text segmentation (Beeferman et al.'s `Pk`, and Pevzner and Hearst's `WindowDiff`), and as an **exact document** match. The splitter reports all three, because they disagree in useful ways: F1 punishes a boundary one page off as an error and a miss; `Pk` and `WindowDiff` give a near miss partial credit; exact match asks whether whole documents came out right, which is what a person filing them cares about.

Let a file have `N` pages. A segmentation is the set of start pages; `same_ref(i, j)` is true if pages `i` and `j` are in one reference segment, `same_hyp(i, j)` the same for the hypothesis (the engine's suggestions at `θ`, or the person's blind first pass against the final truth). `b_ref(i, j)` is the number of reference boundaries between `i` and `j`.

```
k      = round( N / (2 * number_of_reference_segments) ), at least 2     (half the mean reference segment length)

Pk          = 1/(N-k) * sum_{i=1..N-k}  [ same_ref(i, i+k)  !=  same_hyp(i, i+k) ]

WindowDiff  = 1/(N-k) * sum_{i=1..N-k}  [ b_ref(i, i+k)     !=  b_hyp(i, i+k) ]

Document exact match  EM = |{ reference segments [s, e] that also appear as a hypothesis segment [s, e] }|
                           / |reference segments|
```

- `Pk` and `WindowDiff` are error rates: **lower is better**. `Pk` is blind to a hypothesis that adds boundaries in a window (it only asks whether the two pages are in one segment); `WindowDiff` counts the boundaries and so penalises both an extra and a missing one. Report both, and report `WindowDiff` as the headline.
- With a median document of 4 pages `k` is often 2; for a file with one reference segment `k` is at least 2 and both measures are 0 if the hypothesis has no boundary, else the share of windows with a false boundary: which is the single-document false-alarm rate in another form.
- A file with fewer than `k + 2` pages is skipped for `Pk` and `WindowDiff` (the window does not fit) and still counts for F1 and exact match.
- **Micro and macro.** Report the micro average (every page counts) and the macro average over files (every file counts equally). A 226-page stack dominates the micro; the median file dominates the macro; both are printed, with the cluster-bootstrap interval, and the ratio between them is itself a finding.
- **Document exact match** is also reported as a **page-weighted** version (share of pages that sit in an exactly matched document), because the person's cost scales with pages.
- **Taps left**, the measure already in `split_gold.taps_saved`: `FP + FN` taps with the suggestions accepted as shown, against `|T|` taps from nothing. On the real log it is measured as the person's actual adds + rejects + moves for the file.

### 2.10 The extension `scripts/split_fuzz.py report` needs

Today the script has `gold`, `variants`, `recover`, `score`, `report` on the made-up set only, with precision, recall, F1, taps, and a pooled, uninterpreted calibration table ([the script](../scripts/split_fuzz.py), [the gold set](../src/jason/community/split_gold.py)). Add, in this order, each a small function over files, so it tests on the made-up set and runs on the private rows alike:

| Subcommand or flag | Does |
|---|---|
| `report --intervals` | Wilson on proportions and a cluster bootstrap (files as clusters, 2,000 resamples, seed fixed and printed) on F1, `Pk`, `WindowDiff`; counts of files behind each |
| `metrics` (in `split_gold`: `pk`, `window_diff`, `exact_match`, `wilson`, `bootstrap_files`) | the formulas of 2.9 and 2.3, with unit tests on hand-worked examples (including the degenerate files) |
| `rows --from FILE` | read a `jason split --stats --rows` export (numbers only) instead of a gold directory; the same scoring runs on both, so the made-up set is a regression test for the code the private run uses |
| `calibrate --rows FILE` | the reliability table (equal-count bins, Wilson bars), Brier skill, ECE, a Platt fit with intervals, and the recommended `θ_low`, Medium, `θ_high` of 2.8 with the sample sizes that justify them, or "not enough yet" |
| `signals --rows FILE` | per signal: firings, precision, lift, recall contribution, leave-one-out `ΔF1`, fitted weight, the verdict word; the pair table |
| `holdout --rows FILE --by file|batch` | the grouped folds, the frozen final holdout, and a guard that refuses to score a holdout file that was also in a fit set |
| `blind --rows FILE` | `P_blind`, `R_blind`, and the gap to the unblind figures |
| `single --rows FILE` | the false-alarm rate on single-document files |
| `report --out FILE.md` | all of the above as Markdown with a table twin for every chart, and the standing caveats ("a made-up set" or "a private set: counts and pages only") |

An SVG reliability chart uses the optional `charts` extra (matplotlib) like the other reports and falls back to the table when it is not installed. The output of a run on private rows is written to `data/split/stats/reports/`, never into the repository; the made-up report may be checked in. A test runs the whole pipeline on a made-up row export and asserts that no string in the output came from anywhere but the closed lists.

## 3. Usability protocol

### 3.1 Who and how

| Stage | Who | What it can tell | What it cannot |
|---|---|---|---|
| A. The one user | the person who owns the archive, over their real work | a learning curve, the cost per document, where they slow down, which view they settle on | anything about other people. One person's habits are not a population: report every number as "this user" |
| B. A small group | five board members, later (see below) | the problems that block a first-time user; whether the explanations are understood | speed on the archive; it is not the archive |

**A is built into the work.** The user is not asked to perform tasks; the log (section 1) records the sittings, and a **short debrief of five minutes** at the end of each sitting is optional (3.5). The tasks below are for stage B, and for stage A on **made-up files** the user can run when they want to try a change.

**B uses made-up files only.** Five people is the usual size for a usability test because the often-cited estimate that each participant finds about a third of the problems puts five at around 85% of those a larger test would find. It is an estimate for problems that affect many users; it is not a statistical test. Run two or three rounds of five with fixes between them rather than fifteen people at once.

### 3.2 Tasks (stage B and the user's trials)

Each task has a made-up file from the generator (section 4.2), a starting state, a success criterion, and what is collected. The participant is told the goal, never the route.

| # | Task | File | Success | Collected |
|---|---|---|---|---|
| T1 | **Split a 40-page stack** into its documents | 40 pages, 9 documents, text layer, three "Page n of N" documents | the confirmed boundaries equal the answer key (exact), the files exist, the page totals add | time to first mark; active time; taps (inputs) per final boundary; errors (a wrong confirmed boundary, a boundary changed after review); views used; suggestions accepted, rejected, edited; whether the review drawer was read (time in it) |
| T2 | **Split a 226-page stack** over two sittings (stop at about 100 pages, leave, return) | 226 pages, 41 documents, a blank-separator run, a uniform-letterhead run, 4 sideways pages | exact match on at least 95% of the documents, no lost page, the draft resumed correctly | active time and per-document time over the sitting; recovery after the break (time to find where they were); fatigue (time per document in the first and last quarter); errors |
| T3 | **Fix a wrong suggestion** | a file where two High suggestions are wrong and one start has none | both wrong ones rejected or moved, the missed one added | time to notice; whether the reason was opened; the path (key, menu, drag); whether they trusted a wrong suggestion |
| T4 | **Find the sideways pages** | 60 pages, 5 sideways (text layer) and 2 sideways image-only | the five are rotated in the new files, the two are found by eye and rotated, none rotated that were upright | whether the Pages menu was found; time; pages missed; pages wrongly turned; the understanding that rotation applies to the new files only (asked) |
| T5 | **Use the magnifier on a stamp** | a page with a small stamp line and a date | the participant reads the stamp's made-up number aloud correctly | time to find the control; hover-to-sharp as perceived; keyboard and touch variants; whether they could mark while the lens was on |
| T6 | **Choose a file and recover from a refusal** | a file over the page limit and a damaged file | the participant says what happened and what to do next in their own words | whether the words were enough; no stalled screen |

Each task is run on desktop pointer and keyboard; T1, T3 and T5 also on a tablet and a phone width. A facilitator times with the same clock the log uses (the console's) and writes down only: the task, the success, the help given, and the severity-rated problems (3.6).

### 3.3 Numbers to collect

| Measure | Definition | Source |
|---|---|---|
| Time per document | active time attributed to a segment (`active.segment_ord`), median and 90th percentile | log |
| Time to first mark | `session.open` to the first `mark` or `suggestion.act` | log |
| Errors | confirmed boundaries not in the answer key (made-up files), plus boundaries changed after the review opened (the person's own correction signal on real files) | log + key |
| Taps per boundary | inputs (`mark`, `suggestion.act`, `undo`, menu opens) divided by final boundaries, by `input` | log |
| Undo rate | `undo` + `redo` per 100 marks | log |
| Suggestion trust | share of High suggestions accepted without a look at the reason or neighbours (accept `ms` under 1.5 s) and, on T3, whether a wrong one was accepted | log |
| Hover-to-sharp latency, **measured** | `loupe.sharp_ms`: from the 150 ms dwell to the swap; p50 and p95 | log |
| Hover-to-sharp latency, **perceived** | asked after T5: "The sharp picture appeared: (1) far too late (2) late (3) about right (4) instantly"; compare with the measured value so that a budget is set on what is noticed, not on what is measured | questionnaire |
| Success | pass/fail per task criterion | facilitator |
| Help needed | number of prompts given | facilitator |
| Completion confidence | 1 to 5, "I am sure these files are cut where I meant" | questionnaire |

Report medians and ranges, never means of five. State how many of five succeeded, not a percentage.

### 3.4 Think-aloud prompts

Use a short set; do not lead.

- "Say what you are looking at and what you expect to happen."
- "What would you do next? Why?" / "What did you expect that to do?"
- When they stall for 10 seconds: "What are you thinking?" (never "Did you try the menu?")
- On a suggestion: "What do you make of this one?"
- On a wrong suggestion they accepted: after the task, "Tell me about this one." (no blame)
- On the magnifier: "Show me how you would read the small print on this page."
- On the review: "Is this what you meant to do? What will happen when you press the button?"
- At the end: "What was the hardest part? What would you change first?"

The facilitator does not demonstrate, correct, or reassure during a task. A recording of voice or screen is not made; notes are taken by hand, in a file that names the participant by number.

### 3.5 One-page post-session questionnaire

Adapted from the System Usability Scale (ten statements, five points from "strongly disagree" to "strongly agree", alternating positive and negative), reworded for this tool, plus four specific items. Print on one page; no names; the participant number only.

Standard ten (adapted):

1. I think I would like to use the splitter often.
2. I found the splitter more complicated than it needs to be.
3. I thought the splitter was easy to use.
4. I think I would need help from a technical person to use the splitter.
5. I found the various parts of the splitter (the views, the lists, the menus) fit together well.
6. I thought there was too much inconsistency in the splitter.
7. I would imagine most people would learn to use the splitter very quickly.
8. I found the splitter very awkward to use.
9. I felt very confident using the splitter.
10. I needed to learn a lot of things before I could get going with the splitter.

Scoring: odd items contribute `(answer − 1)`, even items `(5 − answer)`; the sum times 2.5 is a score from 0 to 100. A score is a rough ordering tool: SUS is usually read as about 68 being average across many products, but five people give a range, not a number to compare with a published figure. Report the individual scores and the median.

Four specific items, same five points:

11. The suggestions saved me work.
12. I could tell why a page was suggested.
13. I trusted what was shown in the review before I pressed the button.
14. The magnifier showed the detail when I wanted it.

Two free lines: "The one thing that confused me:" and "The one thing I liked:". A third box: "I was working on: desktop / tablet / phone." The free text stays on paper and is entered, if at all, as a severity-rated finding without the participant's words about a document (made-up files have none).

### 3.6 Severity rubric

Each problem observed (by the facilitator, or inferred from the log) is rated on this scale. It follows the common 0 to 4 rating of usability problems, with a data-risk reading added because a mistake here can put a page in the wrong file.

| Severity | Meaning | Example | Action |
|---|---|---|---|
| 4 Blocker | the participant cannot finish, or a file is wrong **and nothing warned them** | a confirm that lets pages go missing; a page filed in the wrong part with no flag | stop the round; fix before anyone else sees it; a lesson with a guard |
| 3 Major | finishes only with help, or with a long detour; or an error that the review would catch but the participant did not read | cannot find how to move a start; does not see the review | fix before the next round |
| 2 Minor | slows the participant but they recover alone | the magnifier key not discovered until hinted | fix when convenient; track the count |
| 1 Cosmetic | noticed, no effect on the task | label wording | note only |
| 0 Not a problem | disagreed on, no evidence | | none |

Rate by **frequency** (how many of the participants), **impact** (the scale above), and **persistence** (does it go away once known). A severity 3 or 4 seen by two of five is acted on; a 2 seen by one is noted.

### 3.7 From findings to lessons and spec changes

The findings go into the same machinery jason uses for everything else ([AGENTS.md](../AGENTS.md), "Lessons and procedures"), and are **proposed here, not written here**:

1. **One finding, one row**: what happened (the task, what the participant did, in words that name no document), the severity, how many saw it, why (the cause in the design or the code), what changed or must change, status (fixed, open, a decision for a person).
2. **A lesson** (`src/jason/community/lessons.py`, area `pdf-splitter`) for anything severity 3 or 4, or any finding the log shows repeatedly (for example, "Medium suggestions accepted at 0.9 and wrong a third of the time"). A fixed lesson names its **guard**: the test, the validator, the budget in the Playwright suite, or the limit that now stops it. A lesson with no guard stays open.
3. **A procedure step** (`src/jason/community/procedures.py`): the sitting's checklist gains the step the lesson says was missing (for example, "open the review and read the page totals before pressing the button"), naming the lesson.
4. **A spec change** where the finding is about the engine's numbers: the proposal is a reviewed change to a weight, a threshold, or a constant, with the aggregate evidence (the report's table) in the lesson. A finding about wording becomes a change to the words in [pdf-splitter.md](pdf-splitter.md) and the console content.
5. **Tell the person** which lessons were added and which are open, as every lesson does.

## 4. Performance acceptance tests on real-world-like synthetic archives

The budgets in [pdf-splitter.md](pdf-splitter.md), 5.9, are asserted today on a 2,000-page made-up file. This section widens the files to look like the archive's trouble, without any real scan, and adds the browser measurements the budgets need to be proved rather than hoped for.

### 4.1 Budgets

| Measure | Budget | How it is measured |
|---|---|---|
| Time to first picture | first tiny picture in a cell: under **0.5 s** warm, **1.5 s** cold; the first screen (tiny and small) drawn: under **1.0 s** warm, **2.5 s** cold for a 400 MB file ([5.9](pdf-splitter.md)) | the console's `thumb.timing` and a `PerformanceObserver` mark from the click to the first `img.decode()` |
| Page count and the empty grid | under 150 ms | a mark at the grid's first paint |
| Scroll frame time, 2,000 pages | 95th-percentile frame under **20 ms** on the desktop profile; no long task over **50 ms**; zero layout shift after the page count is known | a scripted wheel scroll, 10 s, sampling `requestAnimationFrame` deltas; `PerformanceObserver` for `longtask` and `layout-shift` |
| Fast scroll or slider drag | in-flight picture requests drop to the final viewport's within 100 ms | the request log |
| Tap to marker | under **100 ms** | `performance.mark` on click and on the marker's paint |
| Memory | decoded pictures **under 40 MB** (desktop profile) and **under 20 MB** (the throttled phone profile) at any time; JS heap growth under 60 MB over a 2,000-page scroll; no whole-PDF bytes in the tab when the server is the source | live `<img>` count times width times height times 4, from the DOM; `performance.memory` (Chromium with `--enable-precise-memory-info`); a heap snapshot is not taken (it would hold the pictures) |
| Requests per minute | steady state with no input: **0**; autosave: no more than **40** a minute at the busiest typing; scrubbing the whole 2,000 pages end to end: no more than **60** picture requests a second at the peak and **none** after it settles for 1 s; the total for a full top-to-bottom album pass under 700 | `page.on('request')` counted per interval |
| Upload time | for a file chosen on this computer: the preview (page count, first screen) under **3 s** after choosing, whatever the size, **while the upload goes on in the background**; the upload's throughput at least **80%** of a raw transfer measured the same run; the screen is never blocked during it | clock from choose to preview; bytes over time |
| Magnifier | dwell to sharp picture under **400 ms** p95 for the server's 1600 px picture on the desktop profile; the lens follows the pointer within one frame | `loupe` marks |
| Server | the rule pass on 2,000 pages under 5 s; a render under 150 MB per worker | existing pytest |

Budgets are reported as **p50 and p95 over five runs**, and fail on the p95. They are for the desktop profile; the phone profile is a CPU slowdown of 4 (CDP `Emulation.setCPUThrottlingRate`) with a throttled network (`Network.emulateNetworkConditions`), and its budgets are the desktop ones multiplied by 2 for time (the multiple is an open decision, section 7) and the stricter memory above. A real phone has not been measured ([pdf-splitter-client-side.md](pdf-splitter-client-side.md) says so); the throttle is a stand-in, labelled.

### 4.2 The synthetic generator

A made-up generator, `scripts/split_perf_make.py` (a later script; the gold set in `split_gold.py` is its seed), builds files from nothing with a fixed random seed and writes a sidecar `answer.json` (`starts`, `pages`, `rotation`, `blank`, `duplicates`, `note`) beside each PDF. It extends the existing `scripts/client_pdf_make.py`, which already writes CCITT G4, DCT, Flate, and JPEG 2000 pages. Everything is in a scratch folder outside the repository (`JASON_TEMP_DIR`), never in `data/`, never checked in; only the generator is.

| Archetype (file) | Pages | What it exercises | Answer key |
|---|---|---|---|
| `mixed-dpi` | 120 | runs at 150, 200, 300, 400 dpi, grey, colour, bilevel; a change at about a third of the starts and at none of the others | starts; the engine must not read every change as a start |
| `rotated` | 90 | pages with `/Rotate 90`, upright pages whose image is turned (a sideways scan), with and without a text layer; a handful at 180 | which are sideways and the fix; a scan with no text layer is never called sideways |
| `blank-separators` | 150 | a blank sheet between some documents; elsewhere a duplex run where every back is blank | starts; blanks are separators only where rare |
| `uniform-letterhead` | 226 | forty-one short documents, all on one letterhead with one footer, no page numbers; the hard case, where a reading by cues alone fails | starts; expected: low recall, and the engine must say so (Low) rather than be sure |
| `image-only` | 200 | no text layer: CCITT G4, JPEG, JPEG 2000 in the proportions of an office scanner; speckle and skew added | starts; the signal set is the scan's own (size, dpi, colour, blank) |
| `duplicate-pages` | 80 | an exact duplicate page, a scanned-twice page (pixels differ), a form printed twice (kept apart by the splitter, flagged near-duplicate) | the duplicate pairs |
| `oddsize` | 60 | letter, A4, legal, a landscape fold-out | starts at the size changes |
| `stack-40` | 40 | the T1 file: 9 documents, three with "Page n of N" | starts |
| `stack-226` | 226 | the T2 file, with the uniform run, blanks, and 4 sideways | starts and rotations |
| `big-2000` | 2,000 | 93 MB of bilevel scans in 41 runs, the budget file | starts |
| `big-mixed-400mb` | 1,100 | colour JPEG at 300 dpi, about 400 MB: the cold-open case | starts |
| `damaged` | 30 | a truncated file; an encrypted file with a password | the refusal words |
| `single` x 40 | 1 to 6 | single documents, text and image-only, for the false-alarm rate | no starts |

The generator also makes **a stack of 267 files with the archive's shape** (a median of 4 pages, a long tail with a few over 140, about 6,000 pages), from a fixed seed, so the whole rollout can be rehearsed on made-up data (section 5.1) and the log's reports checked end to end.

### 4.3 Running them in Playwright with tracing

The console already has an end-to-end suite (`e2e/`, [its README](../e2e/README.md)) with `console.spec.ts`, `layout.spec.ts`, and `magnifier.spec.ts`. The performance suite is a project beside them, `e2e/tests/perf.spec.ts`, run by `npx playwright test --project=perf`, nightly and on demand, not on every commit.

- **Fixtures.** A `globalSetup` runs the generator into a scratch folder and starts the console against it (`serve_e2e.py`), so the files are the server's or "chosen on this computer", as the test says.
- **Counters in the page.** A small, test-only hook installs `PerformanceObserver`s for `longtask`, `layout-shift`, and `event`; wraps `fetch` to count picture requests and aborts per second; samples `requestAnimationFrame` deltas during a scroll; counts live `img` elements and sums their decoded pixels from `naturalWidth` and `naturalHeight`. The hook is in the test, not in the product.
- **Chromium only for the budgets** (it exposes the CDP throttling and `performance.memory`); the other browsers run the functional suite.
- **Profiles.** `desktop` (no throttle), `tablet` (viewport 768 by 1024, CPU x2), `phone` (375 by 812, touch, CPU x4, network "Fast 4G"), each a Playwright project.
- **Tracing.** `trace: 'retain-on-failure'` for the suite. Traces record DOM snapshots and screenshots, which for the synthetic files are harmless and for a real archive would hold private pages: **the suite refuses to start unless every input path is under the scratch folder the generator wrote** (a check on the path, and a `ARCHIVE_GUARD` environment value that the user's own archive folder sets, whose presence aborts the run). A real-archive session is never traced; its only record is the stats log of section 1.
- **Chrome performance trace.** For a failing budget, `browser.startTracing(page, { categories: ['devtools.timeline', 'v8'] })` writes a trace file to the scratch folder for the Performance panel, again on made-up files only.
- **Repeat and judge.** Each scenario runs five times; the spec computes p50 and p95 and asserts the p95 against the budget of 4.1. The numbers are written to `test-results/perf.json` and, with the commit, to a table in [pdf-splitter.md](pdf-splitter.md) ("measured") by a reviewed change when a budget moves.
- **What each scenario does** (named so a failing line says what broke): `open-2000-cold` (clear the picture cache, open, mark first-picture and first-screen); `scroll-2000` (10 s of wheel, 5 s of a slider drag, count requests, frames, long tasks, shift); `mark-latency` (200 taps, tap to paint); `upload-93mb` (choose, mark preview, bytes over time); `loupe-dwell` (hover 50 pages, time to sharp); `memory-soak` (scroll the whole file twice and back, check decoded pixels and heap); `refusals` (the over-limit and damaged files give words, no stall).

Server tests stay in pytest ([pdf-splitter.md](pdf-splitter.md), 9.2). Where a budget is a server one (a render under 150 MB), it is asserted there.

## 5. Rollout

The rule for every stage: **the original is never touched, nothing is deleted, and the next stage starts only when the checkpoint passes.** Filing is `held` throughout the dry run and the first box (`--filing held`, no OCR): the pieces are made and kept in jason's store, and putting them in slots or the library is a separate decision made later with everything in view ([pdf-splitter.md](pdf-splitter.md), 9.5).

### 5.0 Before any stage

- A **read-only copy of the archive** on a second drive, with a hash manifest (file, size, SHA-256), made by the person and stored with the copy. The splitter works from its own copy under `data/split/sources/`, so the person's folder is read once.
- `jason storage --check`: the scratch and data drives have room for the sources, the pictures, and the pieces. Planning figure: a copy of the archive (a few GB), plus about 20 MB of pictures for a 2,000-page file (6,000 pages: about 60 MB), plus the new files (about the size of the archive again).
- The stats switch on, with `split.blind_share` 0.2, the sweep set, and `split.draft_days` at 60.
- A rehearsal of the **whole procedure on the made-up 267-file archive** of 4.2, so the commands, the report, and the recovery steps are known before they matter.
- The performance suite (section 4) green on the build in use.

### 5.1 Stage 1: a dry run on a copy of ten files

**Choose ten files that look like the whole**, stratified by the person (not by an agent): three small single-document files, three of 5 to 30 pages, two of 30 to 140 pages, one over 140, one image-only. Copy those ten to a scratch folder and open the **copies**.

- Work as usual. One of the ten is blind.
- `--filing held`; apply is allowed; the pieces stay in jason's store.
- Run the verification below on every file.

**Verification per file** (a checklist, ticked by the person): the page totals add (pages in pieces + pages left out = pages in the source); each piece opens; the first and last page of each piece are what the person expects (the review's first-page previews); the original copy's hash equals the manifest; no page is in two pieces.

**Checkpoint C1** (a person looks at `jason split --stats` and the made-up-run comparison):

- zero hash mismatches and zero page-total failures;
- no severity 4 problem; at most one severity 3, with its fix;
- the log has the events the report needs (an empty `page.row` set means something is not recorded);
- the person's time per document is within 3 times the made-up-run median (a sanity check that the real archive is not a different problem entirely);
- the person says they would continue.

**Stop** if any original differs from its manifest, if pages go missing, if the validator drops events (the schema is wrong), or if the person has a bad experience (a fix first).

### 5.2 Stage 2: a box

A **box** is what the person defines: one physical box, one scanning batch, one folder; about 25 to 40 files (about a tenth of the archive). Label it `g` in the session.

- Thresholds are **frozen** for the box (the defaults at that time).
- One in five of the box's files is blind.
- Same filing (`held`); same verification per file.
- At the end, **the audit pass**: the report lists, by file number only, a random 10% of the pieces and a random sample of 30 "non-boundary" pages; the person re-looks at each (the first page, and the page before it for a piece; the page, and the next, for a non-boundary) and records whether the confirmed boundary was right. This is how the truth itself is tested: an estimate of the person's own error rate with a Wilson interval. A confirmed truth that is 3% wrong caps every precision figure at about that.

**Checkpoint C2:**

- everything in C1 still holds;
- the audit error rate's upper bound is under 5%;
- first calibration: `calibrate`, `signals`, `single`, `blind` run on the box with their "not enough yet" lines honoured; the report is read, and any threshold change is **written down as a proposal for the next batch**, not applied;
- the dashboard (section 6) shows a stable time per document (no upward drift, which would mean fatigue or a confusing screen);
- the time the whole archive would take at this rate is computed and accepted by the person (if it is 60 hours, say so now).

**Stop** if the High-band precision's lower bound is under 0.85 on 40 or more High suggestions (the engine is confusing the person: switch bulk accept off for the rest and review), if the audit error rate's upper bound is over 10%, if the blind gap is over 0.15 (the screen leads too much: show suggestions after marking for every file), if more than 3 problems of severity 3, or if the person asks to stop.

### 5.3 Stage 3: the archive

Batches of one box (25 to 40 files). Per batch:

1. Thresholds are the ones frozen at the last checkpoint (changed only between batches, by a reviewed change, with the numbers).
2. Work, verify each file, one in five blind.
3. **Checkpoint C3 (every batch):** manifest hashes unchanged for every original touched; page totals reconciled for the batch (a single line: files, pages in, pieces, pages left out, pages in pieces, difference 0); the stats report; the audit pass at 5% of pieces; the proposed threshold or weight changes, if any, with their evidence; a go for the next batch.
4. Every third batch, rerun the performance suite (the data grew: more drafts, more pictures in the cache) and check `jason storage --check`.
5. After the last batch, the **final untouched holdout** (2.5) is scored once and the calibration report is written to `data/split/stats/reports/`.

**Stop conditions at any batch:** an original's hash differs from the manifest; the page totals do not reconcile; the validator drops events (a schema regression); two severity 4 findings; the disk is short; the person is losing accuracy (the audit error's upper bound rises over two batches); or a decision that belongs to the board arises (something the person finds that nobody has a rule for becomes a finding for the board, not a guess).

### 5.4 What to do with the held copies and the drafts

| Object | Where it is | After the batch is verified | Rule |
|---|---|---|---|
| The archive's originals | the person's folders and the read-only copy | **untouched.** If the person later retires the paper stack or the old PDFs, that is the person's act, outside jason, after the pieces are filed and a backup exists | jason never moves, renames, or deletes an original |
| The splitter's source copy | `data/split/sources/<sha>.pdf` | purge when the batch's pieces are filed or have been verified and the session is `applied` (`jason split --purge ID --yes`) | a copy, rebuilt on demand; deleting it loses nothing |
| Page pictures | `data/split/thumbs/...` | purge with the source copy; the cache bound also limits it | rebuilt from the file |
| Drafts | `data/split/sessions/<id>.json` | an `applied` session's record stays (the provenance of its pieces); a `declined` or `stale` draft is swept after `split.draft_days` | never delete a draft the person is still working in |
| The pieces ("held copies") | the intake store, kept as **held uploads** | stay until filed. Filing them (to the library by classification, or to slots) is a separate step after the batch, with the held list and the library's kind rules in view; a piece the library cannot classify stays held and listed. Nothing is filed by guess | the held list is the work queue, not a trash |
| The stats log | `data/split/stats/` | kept for the evaluation; exported aggregates are the person's to share; the purge removes the log and the salt | opt-in; deletable at any moment |
| Reports | `data/split/stats/reports/` | kept with the batch they describe | not checked in |

If a piece is wrong after filing (a boundary found to be off by a page), the fix is a **new split from the original** with the corrected boundaries; the wrong piece is not edited in place. The provenance fields (`splitFrom`, `pages`) say which pages it came from, so the correction is a redo of one segment, not of the file.

## 6. The metrics dashboard sketch: Setup > Split > Measures

Aggregates only. Nothing on the screen is a file, a page's content, or a person's name; it shows the install's pseudonyms only when the person looks at their own numbers or an administrator has turned the group view on. Every chart has a table twin; every verdict is a word; a cell with fewer than 5 observations shows `n<5`.

```
Setup > Split > Measures                         [stats on]  [Export]  [Delete all counts]
----------------------------------------------------------------------------------------
Progress    files done 112 of 267    pages 2,480 of 6,000    pieces made 640
            this batch (box 3): 31 of 38 files    est. remaining 21 h at the recent rate

Time        active per document (median)   2 m 40 s    90th percentile 9 m
            by sitting:  | 4:10 | 3:50 | 3:00 | 2:55 | 2:40 |   (a sparkline, with its table)
            blind files cost  x1.8 the active time of unblind (n 6 and 22)

Suggestions                       shown    accepted   edited  rejected   precision (95%)
            High  (0.88 and up)      96       91         2       3       0.95  (0.89 to 0.98)
            Medium                    61       36         9      16       0.59  (0.46 to 0.70)
            Low                       30        6         5      19       0.20  (0.09 to 0.38)
            not seen                  12  (not counted)
            Your own marks: 58 of 330 starts (18%) had no suggestion.   Taps saved: 41%

Reliability  [diagram: mean confidence against observed, bars = 95% interval]
            High   -  predicted 0.91  observed 0.95        calibrated
            Medium -  predicted 0.72  observed 0.59        over-confident
            Brier skill 0.31     ECE 0.06     Suggested thresholds: not enough yet (n 187)

Signals     signal           fired   precision   lift   verdict
            page-one           64     0.97        6.1   helps
            title-block        88     0.81        5.0   helps
            dpi-change         52     0.15        1.0   neutral
            colour-change      19     (n<30)      -     not enough yet
            blank-before       23     0.74        4.6   helps
            size-change        14     (n<30)      -     not enough yet

Blind       files 6 of 28; first-pass boundaries found 41 of 47; engine precision on blind files 0.88
            gap from unblind: 0.07  -> "the screen leads you a little: read the blind figure"

Single-document files   false alarms at Medium or better: 2 of 37 (5%)

How you work   views: album 61 | filmstrip 14 | scroll 9 | list 12 | compare 4  (share of marks)
               keyboard 44% | pointer 51% | touch 5%      undo 0.9 a sitting
               flags opened 17, boundary changed after 9      magnifier: p50 240 ms, p95 610 ms to sharp

Health      refusals 0    render failures 2    save failures 1    dropped events 0
            performance (last test): first screen 0.8 s | frame p95 14 ms | memory 31 MB   [open the report]
----------------------------------------------------------------------------------------
Findings    [Add a finding]  (severity, task or "real use", one sentence, no file names)
```

Components follow [console/components.md](console/components.md) (tokens, not hues; each state a word). A finding added here is a stub for a lesson (3.7) and holds a severity, a count, and a sentence typed by the person; the box is labelled "Do not type file names or text from a document."

## 7. Open decisions

| # | Decision | Options | Recommendation |
|---|---|---|---|
| 1 | Is the stats log on by default? | off until chosen; on with a notice | **Off, opt-in** (1.2). The user's archive is private, and the log is only useful if the person trusts it |
| 2 | Does `page.row` (the signals fired on each page and the truth) go in the log? | yes; no, suggestions only | **Yes.** It is numbers and keys, it is the only way to replay a signal without the document, and without it a missed start leaves no trace. Sparse, so small |
| 3 | The blind share | 0, 0.1, 0.2, 0.3 | **0.2** by file up to 60 pages, a 40-page stretch in longer files; the person may skip one file a session |
| 4 | Target precision for High (bulk accept) | lower bound 0.90; 0.95; 0.98 | **0.95** on the held-out folds, and empty (bulk labelled with a count, not the word) until the data supports it |
| 5 | Boundary tolerance for the headline | exact; plus or minus 1 | **Exact** headline, tolerance 1 beside it |
| 6 | Which metric is the headline | F1; WindowDiff; exact match | **WindowDiff** for the engine, **taps left** for the person, F1 for comparison with the literature |
| 7 | Is a batch label `g` asked for | no; optional | **Optional, a number** the person types; the holdout uses it when present |
| 8 | Who sees the group view | nobody; an administrator; every member | **An administrator, off by default.** A person always sees their own numbers. Time per person is sensitive among volunteers |
| 9 | Phone budgets | the same as desktop; times 2 on the throttled profile; a real phone | **Times 2 on the throttle** now; a real mid-range phone measured once before the group stage, and the multiple replaced by what it gives |
| 10 | How many files in the dry run | 5; 10; 20 | **10**, stratified by the person |
| 11 | Size of a box | 25; 40; a physical box | **What the person calls a box**, at most 40, so a checkpoint is never more than a few days |
| 12 | The audit pass share | 5%; 10% | **10% of pieces and 30 non-boundaries in the first box; 5% after**; raised if the error bound is over 5% |
| 13 | Use the log to change weights | by a reviewed change; by an automatic refit | **Reviewed change only**, per the rule that the cue table changes by code after a measured trial; the fit proposes, a person decides, and the lesson records the numbers |
| 14 | Group study participants | board members only; others | **Board members, five per round, made-up files only**; no real archive file in any group session |
| 15 | Should a screen recording be allowed in the group study | never; only on made-up files | **Never** while real files might appear; a hand-written note instead. The Playwright traces are on synthetic files only |
| 16 | Keep the stats log after the archive is done | delete; keep a year | **Keep for `split.stats_days`**, then sweep; the person may purge earlier |
| 17 | The 400 MB cold-open budget | 2.5 s; 5 s | **2.5 s** as designed, measured on the made-up 400 MB file; relaxed only with the measurement in hand |
| 18 | An ablation of the model pass | include; leave for later | **Later.** The model pass is not built; when it is, the same `page.row` rows get a `model` signal and the same verdicts apply |

## Where this lands, and what it does not do

- **New code (not written here):** `jason.community.split_stats` (the schema, the validator, the pure aggregates and metrics), `jason.tasks.split_stats` (the store, the sweep, the purge), `jason.commands.split` (`--stats`), `jason.web.extra.split` (the batched writer), a Measures tab in the console, `scripts/split_fuzz.py` (the subcommands of 2.10), `scripts/split_perf_make.py`, and `e2e/tests/perf.spec.ts`. Limits: `split.stats`, `split.stats_days`, `split.blind_share`.
- **Documents to update when it is built:** [pdf-splitter.md](pdf-splitter.md) (4.7, 9.1, a "measured" section), [instance-limits.md](instance-limits.md) (the three rows), [cli.md](cli.md) (regenerated), and the lessons and procedures this plan proposes.
- **Not in this plan:** a hosted telemetry service (nothing leaves the machine), a way to learn across communities, any use of the private archive's content by an agent, and an automatic change to a weight or a threshold.
