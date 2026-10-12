# The PDF splitter: a pre-mortem, and how it recovers

Status: design (2026-10-11). A pre-mortem of the splitter as built through [pdf-splitter.md](pdf-splitter.md) section 9.7, and the recovery it still needs: an undo of an apply, an apply that survives a crash, a repair command, a draft that survives a closed tab, and a render worker with a ceiling. General for any association: no slot, vendor, folder, or id here belongs to one; samples are "Example Village HOA" and "123 Main St". Built since (2026-10-11, marked in section 9 and described in [pdf-splitter.md](pdf-splitter.md) 6.7): durable writes and the session backup, exclusive session creation, the plan fingerprint, the apply journal with finish and roll back, the purge and sweep guards, and `jason split --doctor`. The rest of this page is not built; the code it describes is read, and every statement about code names where. A statement marked **unverified** was not run or could not be confirmed from the source on this checkout.

Three sentences carry it, and they extend the splitter's own three. **A failure is said in words, once, with the way out.** **A crash leaves a state that can be named, and a person chooses between finishing and undoing.** **The file is data: jason never runs what a PDF asks it to run, and one bad page does not take the server down.**

## 0. How to read this page

### The scales

| Mark | Meaning |
|---|---|
| **S1** | A record is wrong or lost, or a private page or its text reaches someone who may not see it |
| **S2** | Work is blocked, or a wrong filing a person must find and repair |
| **S3** | A delay, a waste, or a confusing message; nothing is wrong afterwards |
| **L1** | Rare: a few times in the life of an install |
| **L2** | Occasional: about once a year in one community |
| **L3** | Expected: every few sessions, or any time a person does the ordinary thing on a bad day |

### The entry

Each failure has an id (stage letter and number), then **Now** (what the system and the person get today, with the code), **Should** (what they should get), **Say** (the message, in the splitter's voice: what happened, what was kept, what to do), **Recover**, **Test** (a named test that should exist), and **Guard** (the code, limit, or lock). "Now" cites files under `src/jason/` unless a path says otherwise. Messages follow the limits registry's rule: they say what was and was not changed, and never contain a file name, a Drive id, or a page's text ([pdf-splitter.md](pdf-splitter.md) section 8).

### The stages

A choose file · B fetch and ingest · C open the session · D measure and suggest · E mark, autosave, conflict · F review · G apply · H filing · I queued work (read-back, OCR) · J undo and redo · K purge and sweep · L pictures and the browser · M the hostile file · N the web layer.

### What is already right

So the list below is read in proportion. The original is only read (`split_session._ingest` copies; nothing writes to a source). A password-protected, damaged, or empty file is refused in words before anything is kept (`_read_pdf`, `split_session.py:236`). A file over `split.max_pages` leaves no copy (`open_session` checks before `_ingest`). A draft write carries a `version`, and a second writer is told, not overwritten (`act`, `SplitConflict`). Apply is a dry run until a person confirms, and it is idempotent by part within a session (`done` in `apply`). A part that cannot be written stops the rest and is reported, and nothing is deleted. Identical bytes are not written twice (`_keep` addresses by hash). The browser is hardened (`splitPdfjs.ts:27`: `isEvalSupported: false`, `enableXfa: false`). The write guard checks Host, Origin, and a token on every write (`web/guard.py`).

## 1. The ten risks to fix first

Ranked by severity, then likelihood, then how many other failures they make worse. The full entries follow in section 2; the backlog (section 9) puts them in build order.

| # | Risk | Id | S, L |
|---|---|---|---|
| 1 | A confidential file's **page text** (title, running lines, date, a suggestion's reason, a segment's guessed title) is returned to anyone at the board's level: only the pictures need the private view | N-1 | S1, L3 |
| 2 | The confidential flag **fails open**: when the library's database cannot be read, the session's flag from the day it opened is used, and a flag set later is lost | N-2 | S1, L2 |
| 3 | **Apply is not crash-safe.** A part is written and pinned before the session records it; a kill between them leaves a pin the session does not know, and the re-run reports that pin as a *collision* with itself. No file or session write is flushed to disk | G-3, G-4 | S1, L2 |
| 4 | **Apply races the draft and the slots.** The plan is built before the lock is taken; apply takes no `version` or plan fingerprint; the slot is not re-checked when the pin is appended | G-1, G-2 | S1, L2 |
| 5 | **Untrusted PDFs are parsed and drawn inside the web process** with no time, memory, or concurrency ceiling, and no rate limit on the picture route | M-1 to M-4, N-5 | S1 (availability), L2 |
| 6 | **There is no undo of an apply.** A wrong boundary found the next day means hand-unpinning and hand-finding held files | J-1 | S2, L3 |
| 7 | **Duplicate detection turns itself off without a word** when the library's database is busy (`_known_hashes` swallows the error), so a duplicate is filed | H-6 | S2, L2 |
| 8 | **A reload on the local route loses the marks** made before the draft exists; the unsaved-marks copy is per tab and keeps only the final starts | E-4, E-5 | S2, L3 |
| 9 | **Apply holds the session's lock for its whole run** and re-reads the full source once per part, twice (review and write): a 500-part, 400 MB file blocks autosave for a long time, and the person sees a server error | G-6, G-7 | S2, L2 |
| 10 | **Purge, the sweep, and a clock jump are unguarded.** The sweep is cut by the wall clock; purge takes no lock and can remove a copy an open is about to use; a half-applied (`confirmed`) draft is never swept and never surfaced | K-1 to K-4 | S1, L1 |

Runners-up: a Drive file is not checked against its checksum (B-3); a long file whose facts job failed is never re-queued on the next open (D-2); two people opening the same new bytes at once get two sessions (C-4); a session id is 32 bits and a collision overwrites a draft (C-5); the cache's size is recomputed by walking the whole tree on every write (L-4); a browser without `deviceMemory` gets the large memory budget (L-6).

## 2. The failures, by stage

### A. Choose a file

**A-1 The file chosen is not a PDF (an image, a Word file, a renamed file).** S3 · L2.
*Now:* an upload is checked by name and first bytes (`record_upload.check`, `_resolve` upload branch); a Drive file by its MIME type (`_fetch_drive`); a `path` (command line only) and a library file are not checked by their first bytes, and `pymupdf.open` also opens images and other formats as documents, so `_read_pdf` can accept a one-page "document" that is not a PDF. *Should:* every source passes the same `%PDF-` check within the first 1 KB (a PDF may have junk before the header; accept what the readers accept, no more) before any engine opens it. *Say:* "That is not a PDF (it begins as a picture file). Nothing was opened. Export it as a PDF and open that." *Recover:* none needed. *Test:* `test_every_source_refuses_a_non_pdf_by_its_first_bytes`. *Guard:* one `looks_like_pdf(path_or_bytes)` in the ingest step.

**A-2 A very large file is chosen on this computer.** S2 · L2.
*Now:* the console sends the file as base64 JSON; the server holds the base64 text, the parsed JSON body, and the decoded bytes at once (`_resolve`, upload branch; `web/extra/split.py`), about 2.7 times the file, and `_peek_pages` writes a second copy to the temp folder. The cap is `upload.max_bytes`, checked on the base64 length. Flask's body ceiling (`MAX_CONTENT_LENGTH`) is not set in `jason.web` (searched; **unverified** that nothing else sets it). *Should:* a streamed multipart upload to a temp file, hashed as it arrives, never held whole in memory; the length header refused first. *Say:* the registry's `upload.max_bytes` words. *Test:* `test_an_upload_is_streamed_and_its_peak_memory_is_bounded`. *Guard:* stream to the temp drive; `MAX_CONTENT_LENGTH` set to the limit plus overhead.

### B. Upload and fetch

**B-1 The Drive token is expired or Drive is not connected.** S3 · L3.
*Now:* verified and good: `drive_choose.open_client` raises `DriveUnavailable`, the console returns `{found: false, driveConnected: false, why, command}` and never opens a browser (`web/extra/split.py`, open branch). *Should:* the same, plus the draft screen keeps working (a session already open reads its own copy and needs no Drive). *Say:* the existing words. *Test:* `test_drive_not_connected_leaves_open_sessions_working` (new). *Guard:* the splitter never refetches a source after open.

**B-2 The Drive file is deleted, moved, or its permission revoked between the check and the open.** S3 · L2.
*Now:* the metadata call and the download are separate; a Google refusal on either is turned into jason's words by `dc.refusal_words` (`_fetch_drive`), so the message is right; nothing is kept because the copy is made only after the bytes arrive. *Should:* the same; say which of the two it was only when Google says so. *Say:* "jason can no longer open this file in Drive (it may have been moved or sharing changed). Nothing was opened." *Test:* `test_a_drive_file_gone_after_the_check_keeps_nothing` (a fake Drive that answers the metadata and fails the download). *Guard:* `_ingest` runs only after the whole body is in hand and checked.

**B-3 The Drive file changed between the metadata read and the download.** S2 · L1.
*Now:* `FIELDS` (`drive_choose.py:40`) has size and modified time but no checksum or version; the bytes are checked against `fetch.max_bytes` only. The copy is hashed after the fact, so the session is faithful to the bytes it holds, but the person is told nothing if they differ from what the chooser showed. *Should:* ask for `md5Checksum` and `version` in the fields, compare after the download, and refuse (or note) a mismatch. A Google-native file has no checksum; those are refused earlier as non-PDF. *Say:* "This file changed in Drive while it was being read. Nothing was opened; choose it again." *Test:* `test_a_drive_file_that_changes_during_the_read_is_not_opened`. *Guard:* checksum compare in `_fetch_drive` and `drive_pick._one`.

**B-4 The held copy from the Picker was purged, or never expires.** S3 · L2.
*Now:* an open of a purged held id answers in words (`_resolve`, held branch). There is no retention: held copies stay until `python -m jason.tasks.drive_pick --purge` ([google-picker.md](google-picker.md), open decision 1), so private files accumulate on disk. *Should:* a registered retention (`pick.held_days`, 30) swept with the splitter's sweep; a held copy that a draft still needs is kept as long as the draft. *Test:* `test_held_copies_expire_unless_a_draft_needs_them`. *Guard:* one sweep for both.

**B-5 The disk fills during the copy.** S2 · L2.
*Now:* `storage.require_room` runs before the copy; the copy goes through a `.part` temp file that is removed on any exception (`_ingest`). A drive that fills after the check ends in `OSError`, which propagates out of `open_session`; the person sees the raw error (**unverified** how the console words an uncaught `OSError`). *Should:* catch `OSError` with `errno.ENOSPC` at the three write points (copy, session save, picture) and answer with the drive-short words. *Say:* "The drive that holds jason's files is full. Nothing was opened. Ask your community's administrator to free space." *Test:* `test_a_full_disk_during_the_copy_leaves_no_partial_file` (a patched `write` that raises `ENOSPC`). *Guard:* `storage.DriveShort` raised from a shared `durable_write` helper (section 6).

### C. Open the session

**C-1 A corrupt or truncated PDF.** S3 · L3.
*Now:* an unreadable file is refused in words (`_read_pdf`). A file that the engine **repairs** (a missing cross-reference table, a truncated tail) opens with fewer pages than the person expects and no warning. *Should:* ask the engine whether it repaired the file (`doc.is_repaired` in PyMuPDF; the equivalent in pypdfium2 is **unverified**) and put "This file was damaged and repaired when opened; N pages could be read" in the session's notes and above the grid. *Say:* that sentence, and the count. *Recover:* the person compares the count with the original and opens a better copy. *Test:* `test_a_repaired_file_says_so_and_counts_the_pages_it_read`. *Guard:* a `repaired` fact on `Source`.

**C-2 A password-protected (encrypted) PDF.** S3 · L3.
*Now:* verified: refused with remove-the-password words (`_read_pdf`). A PDF encrypted with an empty user password opens in PyMuPDF (`needs_pass` false, `is_encrypted` true) and is refused by the same test, which is stricter than necessary. *Should:* the same refusal for a password; a file that opens with the empty password may open if the cut tool can also read it (pypdf needs `decrypt("")`), otherwise refuse with the same words. *Test:* `test_an_owner_password_only_pdf_is_read_or_refused_consistently` (the three tools agree). *Guard:* the probe runs all three readers once (in the render worker, section 8).

**C-3 A PDF with zero pages, mixed page sizes and rotations, or a huge page.** S3 · L2.
*Now:* zero pages is refused (`_read_pdf`). Mixed sizes and rotations are measured per page (`PageFact.width/height/rotation`, `turn`); the grid uses each page's own aspect ratio. A page far larger than any paper (a drawing, or a hostile MediaBox) is drawn by scale to the longest side, so the output is bounded; the source decode is the cost (M-2). *Should:* the same, plus a fact `oversize` (any side above 200 inches) that the grid labels "very large page" and that the render worker draws with a longer allowance. *Test:* `test_mixed_size_and_rotated_pages_keep_their_own_shapes`, `test_an_oversize_page_is_drawn_at_the_size_asked_and_flagged`. *Guard:* the page-size cap in the worker.

**C-4 The same bytes are opened twice at once.** S3 · L2.
*Now:* `open_session` is not under any lock; `find_resumable` and the `save` of a new session are separate steps, so two simultaneous opens of new bytes make two drafts on one hash (`split_session.py:503-511`). Later opens resume the first. *Should:* hold `Resource.STORE` `split-open-<sha>` from the `find_resumable` to the first `save`. *Say:* nothing; the second open resumes ("Resumed your draft"). *Test:* `test_two_simultaneous_opens_of_the_same_bytes_make_one_draft` (two threads). *Guard:* the lock.

**C-5 The session id collides.** S1 · L1.
*Now:* `new_id` is 8 hex digits (`split_session.py:213`) and `save` writes `sessions/<id>.json` without checking that it is new, so a collision silently replaces another draft. At a few hundred sessions the chance is small and not zero. *Should:* create with exclusive open (`"x"` mode) and retry with a new id; widen to 12 digits. *Test:* `test_a_colliding_session_id_never_overwrites_a_draft`. *Guard:* exclusive create.

**C-6 The library file is replaced after the session opened (a hash mismatch).** S2 · L2.
*Now:* the session works on its own copy, so nothing shown or cut is wrong. `_check_not_stale` compares `size:mtime_ns` of the library file with the stamp taken at open, and a difference makes the session `stale` permanently and refuses every further act and the apply (`split_session.py:706`). A restore from backup or a copy that resets the modification time makes a file that has not changed look changed; and a draft marked stale cannot be applied to the copy it was made from. The library row already carries a SHA-256. *Should:* compare the row's hash with `Source.sha256` when the row has one, and the stamp only as a fallback; offer the three ways out in words. *Say:* "The library's file changed after you started (it has different pages now). Your marks are for the file as you opened it. [Carry my marks to the new file] [Keep working on the old copy, to look at it] [Start again]." *Recover:* "carry my marks" is allowed only when the page counts match, and shows the first page of each part again. *Test:* `test_a_library_file_with_the_same_bytes_but_a_new_time_is_not_stale`, `test_a_replaced_library_file_offers_carrying_the_marks`. *Guard:* hash compare; `stale` stops an apply, not a view.

**C-7 A Drive or held file changed in the original after the copy.** S3 · L2.
*Now:* nothing notices, by design: the session reads its copy. *Should:* nothing more; the page says "The copy you opened on 10 October" under the header so the person knows. *Test:* `test_the_session_names_the_day_of_its_copy`.

### D. Measure pages and suggest

**D-1 One page cannot be measured or drawn.** S3 · L2.
*Now:* the light pass wraps the thumbnail and rotation reads in `except Exception` and continues with blanks (`scan`, `split_session.py:353-362`), so one bad page gives empty facts and the others stand. The picture route answers 422 for that page. *Should:* the same, plus a fact `unreadable` so the grid says "This page could not be read" on the card before the person asks for its picture, and the doctor counts them. *Test:* `test_a_page_that_cannot_be_measured_does_not_stop_the_others`. *Guard:* a per-page `try` in the worker.

**D-2 The facts job never runs, or runs and dies.** S3 · L3.
*Now:* a file over 60 pages queues a job at open (`queue_facts`) only when `factsPending` is set, which the *resumed* branch never sets (`open_session` returns early with `resumed: True`). If the first job failed, or no worker was running, every later open of that file shows "Measuring…" forever. The job runs `jason split ID --facts` as a separate process (`jobs.run_job`) with no timeout (`job.timeout_seconds` is a documented limit with no row; searched). The job is a write and is never retried (`jobs.add`: writes means `max_attempts` 1). *Should:* an open of a draft whose facts are short re-queues the job unless one is queued or running for it; the screen says "Pages measured: 420 of 1,800 (waiting for the background worker)" and, if no worker holds `jobs.worker_guard`, "The background worker is not running; ask the person who runs jason to start it, or measure here (slower)". *Say:* those. *Recover:* `jason split ID --facts --yes` runs it by hand. *Test:* `test_reopening_a_draft_with_missing_facts_requeues_once`, `test_the_screen_names_a_stopped_worker`. *Guard:* a job is idempotent by session id (like `library_ocr._pending`); a job timeout limit (section 8).

**D-3 The suggestion engine's input is hostile or odd.** S3 · L2.
*Now:* titles are cut to 90 characters and running lines to 80 (`split_suggest.facts_from_pages`); a label "Page 3 of 9999999999" parses to integers and is stored. *Should:* keep the caps and add: a printed total above the page count is ignored for the "run restarts" cue, and a text layer of more than a set size per page is cut before it reaches the cue table. *Test:* `test_absurd_page_numbers_and_long_text_layers_cannot_slow_or_skew_the_pass`. **Unverified:** the cue table's cost on a 3,000-page file with a 5 MB text layer per page.

**D-4 The model pass.** Not built. When it is, it must hold the GPU lock and run `jason.local_ai.preflight` first, fail fast with the preflight's words, and be cancellable; a cancelled pass keeps what finished ([pdf-splitter.md](pdf-splitter.md) 4.4). *Test (when built):* `test_the_model_pass_fails_fast_when_the_machine_is_short_and_keeps_partial_results`.

### E. Mark, autosave, conflict

**E-1 Two people edit one draft.** S2 · L2.
*Now:* verified: every draft act can carry the draft's `version`; a draft that moved on raises `SplitConflict` and the console answers 409 with the server's copy; nothing is saved (`act`). The screen shows a comparison with *Keep mine*, *Keep theirs*, *Merge* ([pdf-splitter.md](pdf-splitter.md) 5.10). Two things are missing: **apply and review carry no version** (G-1), and the screen does not say *who* is editing. *Should:* the session keeps a presence note (`editor`: name, time, last act), refreshed on each act and shown as "Jane Example changed this draft 2 minutes ago"; the merge is three-way against the version the person started from (section 7). *Test:* `test_a_second_writer_sees_who_changed_the_draft`, `test_the_merge_keeps_marks_both_sides_added_and_lists_real_conflicts`. *Guard:* version on every write.

**E-2 Autosave fails (server error, offline).** S2 · L3.
*Now:* verified in `splitStore.ts`: a failed send keeps the ops queued, shows a save state ("Not saved"), and persists the derived starts to `sessionStorage`; offline is detected and worded; a 5xx holds the ops for retry; a 4xx refusal drops the op and re-reads the draft. *Should:* the same, and the held copy moves to durable storage (section 7). *Test:* `splitStore.test.ts: holds ops across a 500 and replays them in order` (**unverified** whether it exists; the behaviour is in the source).

**E-3 The browser crashes or the tab is closed mid-edit.** S2 · L2.
*Now:* marks sent to the server are safe (the debounce is 1.5 seconds, so up to that much is at risk). Marks not yet sent live in the store's op queue and, only after a failed send, in `sessionStorage` under `UNSAVED + id`. A tab closed before a failed send holds nothing; `sessionStorage` is dropped when the tab closes in most browsers (**unverified** across a crash-restore). *Should:* section 7: every op written to IndexedDB before it is sent, and a send on page hide with `fetch(..., {keepalive: true})`. *Say:* "Restored 3 marks you made at 10:41 that were not saved." *Test:* `e2e: a killed tab restores its unsent marks`. *Guard:* write-ahead of the queue.

**E-4 A reload on the local route (the file lives in the tab).** S2 · L3.
*Now:* a file chosen on this computer is held as a `File` in the tab; the upload and the server's open run in the background; marks made before the draft exists are held in the editor's queue ([pdf-splitter.md](pdf-splitter.md) 9.7). A reload on `#/setup/split/local` drops the `File`, the queue, and the marks; if the upload had not finished there is no draft to come back to. *Should:* the queue and the marks are persisted (section 7); the route, on reload with no file, says "Choose the same file again to continue (it is not kept in the browser)" and matches the file by size and hash, then replays. A browser that allows it (File System Access) can keep a handle and offer the file without choosing. *Say:* that sentence. *Test:* `e2e: reload on the local route before the draft exists offers the same file and replays its marks`.

**E-5 The unsaved-marks copy keeps only the final starts and only for the same version.** S2 · L2.
*Now:* `persist` stores `{version, starts}`; `load` offers it only if `saved.version === a.version` and the starts differ (`splitStore.ts:85-95`). If the server moved on in the meantime, the copy is ignored, silently, and the person's marks are lost. *Should:* keep the base version and the base starts with it so a three-way merge (section 7) can run; never discard silently. *Test:* `splitStore.test.ts: unsaved marks over a moved-on draft are merged, not dropped`.

**E-6 Time zone and clock skew in the version checks.** S3 · L1.
*Now:* the version is a counter, not a time; stale detection compares `size:mtime_ns` for equality (C-6). Times shown are the server's UTC strings turned to local time in the browser. Skew cannot reorder versions. The one clock-sensitive piece is the sweep (K-2). *Should:* nothing in the version path; keep it a counter. *Test:* `test_versions_do_not_depend_on_the_clock`.

**E-7 A very long label or an absurd number of marks.** S3 · L2.
*Now:* a person's label is cut at 200 characters (`split_session.py:443`); history is capped at 200 entries (`HISTORY_CAP`); `split.max_parts` is checked at review (`review`). The session JSON is rewritten whole on every act. *Should:* the same, plus a hard ceiling on boundaries (the page count) and on payload size at the route (the 20 KB budget of 5.9, refused above ten times that). *Test:* `test_a_draft_payload_over_the_ceiling_is_refused_in_words`.

**E-8 The session file is corrupt.** S1 · L1.
*Now:* `load` turns any `OSError` or `ValueError` into `KeyError`, which the console answers "No such split."; `sessions()` silently skips an unreadable file, so the draft disappears from the list and nothing says why (`split_session.py:80-99`). The write is `os.replace` of a pid-named temp file, with no flush to disk (`_write_json`), so a power loss can leave a zero-length file on some file systems (**unverified** on this machine's NTFS settings). *Should:* keep the previous good copy (`<id>.json.bak`, as `record_slots._write_store` does for `records.json`); on a parse error, load the `.bak` and note "Restored from the previous save; your last change may be missing"; list an unreadable session with a "damaged" status and the doctor's id. *Say:* that note. *Test:* `test_a_zero_length_session_file_loads_from_its_backup_and_says_so`. *Guard:* `durable_write` (fsync the file, replace, fsync the folder where the platform allows).

### F. Review

**F-1 The review is stale when the person presses confirm.** S2 · L2. See G-1; the review has no fingerprint today.

**F-2 The review is slow or large for a big file.** S3 · L2.
*Now:* with `hashes` on, `review` cuts every part in memory to hash it (`split_session.py:905-908`), each cut re-parses the source; it runs in the web request. For 500 parts of a 400 MB file this is minutes (**unverified**; the cost is O(parts × file) by the code). *Should:* the review returns at once with part counts and flags, then a *job* hashes the parts and fills in duplicates, the way facts fill in; the confirm button waits for it ("Checking for files jason already holds: 140 of 500"). *Test:* `test_review_returns_before_hashing_and_the_duplicate_check_fills_in`. *Guard:* one parse of the source per review (a single reader, pages added in ranges), not one per part.

**F-3 The duplicate check cannot run.** See H-6.

### G. Apply

**G-1 The plan was built before the lock; apply is not tied to what the person reviewed.** S1 · L2.
*Now:* `apply` calls `review(...)` (a full plan) **outside** the lock (`split_session.py:958`), then takes the lock and reloads the session (`:971`); the console's apply carries no `version` and no plan identity (`web/extra/split.py`: `version` is used only by draft acts). Between the review the person read and the write, another tab or person can change the boundaries; the files written follow the plan built at the start of the apply, while `session.confirmed["boundaries"]` records the boundaries read later (`:985`), so the provenance on the pins can disagree with the files. *Should:* the review returns a **plan fingerprint** (a hash of the session version, the boundary list, the labels, the filing choices, the drops, the rotations, and the source hash); apply requires it and recomputes the plan *inside* the lock; any difference refuses with the new review. *Say:* "The draft changed after you reviewed it (Jane Example moved the start of part 4). Nothing was written. Review again." *Recover:* the review reopens with the changes marked. *Test:* `test_apply_refuses_a_plan_the_draft_has_moved_past`, `test_provenance_boundaries_equal_the_boundaries_the_files_were_cut_from`. *Guard:* fingerprint + plan inside the lock.

**G-2 A slot that was free at review is taken at apply.** S1 · L2.
*Now:* `plan_parts` computes collisions from `rs.compute` once per apply (`:915`), and `write_part` appends the pin with no second check (`record_upload.py:315-335`: `_write_store(... d["pins"].append(row))`). A person pinning that slot between the plan and the append makes **two pins in a slot that holds one**, which the record screens call "two holders". Each part's cut takes seconds to minutes, so the window is real for a large file. *Should:* the append is a compare-and-append inside the slot store's lock: re-evaluate the slot's holders in the same `_write_store` change function; if busy, return `collided` and keep the part held. The result says it differs from the review. *Say:* "The slot for part 3 was filled by Sam Example while this was being written; part 3 was kept as a held file instead." *Test:* `test_a_slot_taken_during_the_apply_is_a_collision_not_a_second_pin`. *Guard:* the check inside `rs._write_store`.

**G-3 The process is killed between writing a part and recording it.** S1 · L2.
*Now:* the order inside the loop is: cut, `write_part` (files `_keep`, then pin appended to `records.json`), `made.append`, then `session.applied = {...}; save` (`:1012-1024`). A kill after the pin and before the `save` leaves a pin the session does not know. The re-run takes the plan afresh, finds the slot **held by that pin**, and records the part as a `collision` with a slot that holds *its own* earlier output (`:997-1000`): the pin is orphaned from the session, the result says "collision", and the part is never read back. *Should:* the two-phase journal of section 5: a pre-allocated pin id and an intent record, so the re-run recognises its own pin and finishes the record. *Say* (at next open): "An apply that started at 10:42 did not finish: 3 of 7 files were written. [Finish it] [Undo it] [Leave it]". *Test:* `test_a_kill_after_the_pin_before_the_session_save_is_resumed_without_a_collision` (fault injection at each of the points in section 5.5). *Guard:* the journal.

**G-4 Nothing is flushed to disk.** S1 · L2.
*Now:* no `fsync` in the splitter or record-slot writers (searched `src/jason`; it appears in `controls/store.py`, `limits.py`, and `workflows/store.py` only). `os.replace` makes the swap atomic, not durable: after a power loss the new name can point at an empty file. A part's PDF, the pin store, the session, and the facts are all affected. *Should:* a shared `durable_write(path, data)` (write a temp file in the same folder, flush, `fsync`, `os.replace`, and `fsync` the folder where the platform has it); retry `PermissionError` on replace three times (antivirus and indexers hold files on Windows). The record-slot store keeps its `.bak`. *Test:* `test_durable_write_flushes_before_it_renames` (a spy on `os.fsync` and `os.replace` records the order). *Guard:* one helper used by every splitter write.

**G-5 The disk fills during the apply.** S2 · L2.
*Now:* there is no check of total room: `_keep` checks `require_room` for each part as it goes, so the third part can fail after two were written; the result is a retryable partial state (`failed`, `partial: True`). *Should:* before the first write, require room for the sum of the parts plus margin, in one check; a failure mid-way is the same journalled partial. *Say:* "The drive is too full for these 7 files (they need about 310 MB; 120 MB is free). Nothing was written." *Test:* `test_apply_checks_room_for_all_parts_before_writing_any`. *Guard:* `storage.require_room(root, total)`.

**G-6 Apply holds the session's lock for its whole run.** S2 · L2.
*Now:* `_locked(root, sid)` (`timeout=60` to *acquire*) wraps the entire loop, including cuts, the library intake, and the read-back queueing. Another request for the same session (an autosave, a picture's `view_of` is not locked, but `act` is) waits up to 60 seconds and then raises `ResourceBusy`; how the console words that is **unverified**. A person with the editor open sees "Not saved" for the length of the apply. *Should:* apply sets the session `applying` under the lock, releases it, and does the work under an apply-only lock; draft acts on an `applying` session are refused at once in words. *Say:* "This split is being written (file 4 of 7). You can look, not change." *Test:* `test_an_act_during_an_apply_is_refused_at_once_not_after_sixty_seconds`. *Guard:* a status and two locks, ordered (section 5.6).

**G-7 The source is re-read once per part, twice.** S2 · L2.
*Now:* `record_upload.cut_pages` builds a `PdfReader` of the whole source per call; the review calls it per part to hash, the apply again to write. `for_library` keeps every library part's bytes in memory until the end (`:1010`). A 400 MB source with 500 parts parses 400 MB a thousand times (**unverified timing**; the structure is in the code). *Should:* one reader per apply, pages added per range; library parts staged to disk, not held in a list. *Test:* `test_apply_opens_the_source_once` (a spy counts `PdfReader` constructions). *Guard:* a `PartCutter` that holds the reader for the apply and releases it after.

**G-8 One bad part stops the rest.** S3 · L2.
*Now:* any exception from a part's cut or write is caught, reported, and the loop `break`s (`:1020-1022`). A single page pypdf cannot copy stops parts that would have written fine. *Should:* keep going for independent parts (no part depends on another); the result lists each failure; `done` makes the re-run write only what failed. Order does not matter to correctness. *Say:* "6 of 7 files were written; part 5 could not be (page 61 could not be copied). The others stand; fix or drop that page and apply again." *Test:* `test_a_bad_part_does_not_stop_the_independent_parts`. *Guard:* continue-on-error with a failure cap of 5.

**G-9 A reload or a second click during an apply.** S2 · L3.
*Now:* a second apply with `confirm` while the first holds the lock waits, then sees `confirmed`/`applied` and either resumes or refuses "applied already" (`:973`), which is right; an apply that was killed leaves `confirmed` with `partial: True` that the screen does not name (K-3). *Should:* the status line "Writing file 4 of 7" from the journal, with a button disabled; on `applied`, "Done at 10:44: 7 files". *Test:* `test_a_double_click_writes_once`. *Guard:* the idempotency key (the apply id).

**G-10 Collisions and duplicates reported at review but different at apply.** S3 · L2. See G-1 and G-2; the result lists the difference.

### H. Filing: slots, library, held

**H-1 The library intake cannot file a part.** S3 · L3.
*Now:* verified and good: the part is kept held with the reason, never lost (`_into_library`). A scan with no text usually comes back held with "no kind" (`pdf-splitter.md` 9.5). *Should:* the held part appears on the held-uploads shelf with its reason and a *Classify and file* act; the review warns before apply ("These 3 parts have no text and will be held"). *Test:* `test_a_part_the_library_refuses_is_held_with_its_reason_and_listed`.

**H-2 The library intake dies mid-way.** S2 · L1.
*Now:* parts are staged in a `TemporaryDirectory` and passed to `ingest.run(... apply_files=True)`; an exception is caught and every part is held with "could not run" (`_file_to_library`). A *kill* leaves the staged folder in the temp drive (`jason-split-*`) and may leave some parts already filed in the library with the session unaware. A re-run files nothing twice (the library recognises the hash, "already in the library") and the part is held with that reason, which reads as a failure when it is a success. *Should:* the journal records `library-intent` per part with its hash; on resume, a part whose hash the library already holds is recorded as `library` with that id. *Test:* `test_a_killed_library_intake_resumes_and_adopts_the_parts_it_filed`. *Guard:* the journal; the doctor sweeps `jason-split-*` older than a day.

**H-3 A pin is half-written.** S1 · L1.
*Now:* the pin row is appended to `records.json` whole under the store lock with a `.bak` copy first (`record_slots._write_store`), so a half-written pin cannot exist within one file; the file for the pin (`_keep`, a `.part` then replace) is written first, so a pin never points at a missing file. A key-document slot goes through `kd.upload`, a different writer (**unverified** crash behaviour). The gap is the unknown order in G-3. *Test:* `test_a_pin_never_refers_to_a_file_that_is_not_there` (a kill after the pin append and before the file is not possible by order; assert the order).

**H-4 The record-slot store (`records.json`) is unreadable or locked.** S2 · L1.
*Now:* an invalid file is refused with "is not valid JSON; fix it by hand" (`_write_store`); the store lock waits 120 seconds then raises `ResourceBusy`. *Should:* apply checks the store is readable and writable in the pre-flight and says so before it cuts a single part. *Test:* `test_apply_checks_the_slot_store_before_cutting`.

**H-5 The held store already has a different file under the address.** S3 · L1. *Now:* `_keep` refuses ("a different file is already kept under that address"), verified; the address is the first 16 hex digits of the hash plus the name, so this means damage. *Should:* the doctor reports it; the apply names the part. *Test:* existing.

**H-6 The library's database is locked or unreadable, and duplicates are not found.** S2 · L2.
*Now:* `_known_hashes` catches `sqlite3.Error` and returns what it has (`split_session.py:852`); `_library_row` returns `None` on error (`:128`), which `_resolve` words as "the library holds no file with that id". So a locked database makes the duplicate check pass silently (the person is told nothing; `hashes: false` is not reported) and an open of a real library file fail with a wrong reason. SQLite's default wait on a read is five seconds. *Should:* a distinct `LibraryBusy` raised from both; the review shows "The library is busy; jason could not check for duplicates. [Try again]" and the confirm is blocked until the check ran or the person chooses *Skip the duplicate check*, recorded in the result. *Say:* that sentence; for an open, "The library is busy right now (another job is writing to it). Try again in a minute." *Recover:* retry. *Test:* `test_a_locked_library_blocks_the_duplicate_check_visibly`, `test_a_locked_library_is_not_reported_as_a_missing_file`. *Guard:* a typed error and a `duplicatesChecked` field on the review.

**H-7 The slot is hidden, a series has no period, a number repeats.** S3 · L2. *Now:* `plan_parts` raises in words before any write ("is hidden by the profile", "is a series: name the part's period"). Verified. *Test:* existing in `test_split_apply.py`.

**H-8 The same split applied twice (once per session on the same bytes).** S2 · L1. *Now:* two sessions on the same bytes (C-4) can each be applied; the second finds identical parts (duplicate by hash, skipped) or collisions. *Should:* the first apply marks the *hash* as split, and the second session's review says "These pages were already split in session ab12cd34 on 10 October". *Test:* `test_a_second_session_on_applied_bytes_is_told_so`.

### I. Queued work: read-back and OCR

**I-1 No worker is running.** S3 · L3. See D-2. *Now:* read-back jobs and OCR jobs are added with `jobs.add` and wait for `jason worker`; nothing shows how long they have waited. *Should:* every place that says "queued" reads the queue: "Queued 25 minutes ago; no worker is running." *Test:* `test_a_stopped_worker_is_named_where_a_job_is_queued`.

**I-2 Jobs outlive the files they were queued for.** S2 · L2.
*Now:* there is no rollback, so today this only happens if a person unpins or a purge removes something. When undo apply exists (section 4) it will. `library_ocr.run` re-checks the row (`needs_ocr`) and fails fast for a missing library file, so a job for a removed file ends with a clear failure; but a job that **is running** when the file is removed writes `<id>.txt` and `<id>.json` into the text cache for a document that is gone, and writes them non-atomically (two `write_text` calls; `library_ocr.py:150-155`). The read-back job (`records --read SLOT --pin P`) is **unverified** for an unpinned pin. *Should:* undo cancels queued jobs (`jobs.cancel`), and every job re-checks its subject under the store lock before it writes; the OCR writer writes both files atomically and only if the row still exists and the hash matches. *Test:* `test_ocr_for_a_removed_file_writes_nothing`, `test_a_read_back_for_an_unpinned_pin_ends_cleanly`. *Guard:* subject re-check under `hold(Resource.STORE, "library")`.

**I-3 The OCR engine is missing.** S3 · L2. *Now:* verified: `run` raises `RuntimeError("no OCR engine runs on this machine ...")` and the job fails (exit 1) with the install words; the apply has already queued it. *Should:* apply checks `ocr.local_engines()` when the dry run is computed and says "OCR is not installed here; 5 parts with no text will be filed unread" before the person confirms. *Test:* `test_the_dry_run_names_a_missing_ocr_engine`.

**I-4 The OCR job runs for hours.** S3 · L2. *Now:* no timeout on a job process (D-2); one stuck OCR holds the local lane. *Should:* `job.timeout_seconds` registered (default 3,600, 60 to 21,600) and enforced by the worker killing the child; the failure is worded. *Test:* `test_a_job_over_its_timeout_is_ended_and_says_so`. *Guard:* the limit row.

**I-5 Queue flooding.** S3 · L1. *Now:* `split.ocr_queue_max` (25) bounds OCR jobs per apply; read-back jobs per apply are bounded by the parts (`split.max_parts`, 500); a queue-depth limit (`jobs.queue_depth`) is documented, not registered (**unverified**). *Should:* register it. *Test:* `test_the_queue_depth_limit_refuses_in_words`.

### J. Undo and redo

**J-1 Undo of the draft survives a reload; undo of an apply does not exist.** See section 4.

**J-2 The undo stack is capped.** S3 · L2. *Now:* `HISTORY_CAP = 200` and older entries fold into a snapshot (`split_session.py:27`); the stack is saved with the draft. *Should:* the screen says when the cap is reached ("Older changes can no longer be undone"). *Test:* `test_undo_past_the_cap_says_so`.

**J-3 Undo while another person has changed the draft.** S3 · L2. *Now:* undo is a draft act and carries a `version` like the others; the stack is shared, so one person can undo the other's change. *Should:* undo undoes the *person's own* last change when the draft has moved on, or asks. *Decision needed:* open decision 5 (section 10).

### K. Purge and the sweep

**K-1 Purge and the sweep take no lock and can race an open.** S2 · L1.
*Now:* `purge` unlinks session files and then `_unreferenced(root, set())` removes every source, facts file, and picture folder that no `draft` or `confirmed` session needs (`split_session.py:1134-1172`), without any lock. An `open_session` that has just run `_ingest` (the copy exists) but not yet `save`d its session can have its copy removed in between; the session is then created for a missing copy, and every picture 404s ("The copy of this file was removed"). Likewise `purge` on a `confirmed` session mid-apply (it only spares `applied`) unlinks the session file the apply is about to rewrite. *Should:* `purge` and the sweep hold the same open lock family (`split-open-<sha>`, `split-<sid>`), skip a session `applying`, and never remove a copy younger than an hour. *Test:* `test_purge_cannot_remove_a_copy_an_open_is_about_to_use`, `test_purge_refuses_an_applying_session`. *Guard:* locks and an age floor.

**K-2 The clock jumps.** S1 · L1.
*Now:* the sweep removes a draft whose `updated` is older than `split.draft_days` before `datetime.now(utc)` (`sweep`); a machine whose clock is set far ahead (a dead clock battery, a wrong restore, a virtual machine resumed) sweeps every draft at the next run. Nothing runs the sweep yet (the doc says so), but the first scheduler to call it inherits this. *Should:* the sweep refuses to run when `now` is earlier than the newest timestamp it has seen, or later than it by more than a day since the last sweep (a high-water mark in `split/sweep.json`); and a swept draft is **moved to `split/trash/` for 7 days** before it is deleted. *Say:* "The clock looks wrong (it is 14 months ahead of the last record). The sweep did nothing." *Test:* `test_the_sweep_refuses_a_clock_that_jumped`, `test_a_swept_draft_can_be_restored_for_seven_days`. *Guard:* high-water mark and trash.

**K-3 A half-applied (`confirmed`) draft is never swept and not surfaced.** S2 · L2.
*Now:* the sweep takes only `draft`, `stale`, and `declined` (`:1190`); `_unreferenced` keeps the copy for `confirmed` sessions; the list shows the status only. *Should:* the list says "Unfinished apply, started 10 October by Jane Example" with the three choices of G-3, and the doctor lists it. *Test:* `test_the_list_names_an_unfinished_apply`.

**K-4 An applied session keeps nothing but its record.** S3 · L3. *Now:* after apply the copy and pictures go at the next purge or sweep (they are unreferenced); an *undo* (section 4) needs the copy to cut again, but not to reverse. *Should:* the copy of an applied session is kept `split.applied_copy_days` (14) so a person can look again or redo the split; then dropped. *Test:* `test_an_applied_sessions_copy_is_kept_for_the_grace_days`.

### L. Pictures and the browser

**L-1 The thumbnail cache evicts a picture that is on screen.** S3 · L2.
*Now:* the design says eviction "never [removes] one the open session is viewing" ([pdf-splitter.md](pdf-splitter.md) 3.3); `_evict` orders other files' pictures before the open file's own and by modification time, but has no notion of the pages in view (`split_thumbs.py:_evict`). A picture on screen that is the oldest is removed and drawn again on the next request. The browser holds its own copy meanwhile. *Should:* the route accepts a `keep` hint (the window's page range) or the cache keeps the most recent N per session; or the doc's sentence is corrected. *Test:* `test_eviction_prefers_pictures_outside_the_recent_window`.

**L-2 A page renders slowly or fails on the server.** S3 · L2. *Now:* `PageUnreadable` → 422 "This page could not be drawn" (`web/split.py`); the grid shows a card with Retry. There is no time limit (M-1) and no negative cache, so a page that takes a minute to fail is retried on every scroll. *Should:* section 8: a deadline, a worker restart, and a ten-minute negative entry. *Test:* `test_a_page_that_times_out_is_not_retried_on_every_scroll`.

**L-3 The client render fails on one page, or draws white.** S3 · L2. *Now:* verified in [pdf-splitter.md](pdf-splitter.md) 9.7: a failed or all-white browser page falls back to the server's picture; a self-test at start turns browser drawing off for the visit when a codec fails. *Should:* the same; the fallback is counted and shown once ("5 pages were drawn by the server"). *Test:* existing in `splitClient.test.ts`.

**L-4 The cache's size is found by walking the tree on every write.** S3 · L3.
*Now:* `store()` calls `usage(root)` after each new picture, and `usage` scans every file under the cache with `os.scandir` (`split_thumbs.py:usage`, `_files`). With the 100,000 pictures a 512 MB cache holds at 5 KB each, every cache miss costs a full walk (**unverified timing**; the structure is in the code), which slows exactly the fast-scroll case. The `index.json` the design promised (3.3) was not built. *Should:* keep a running byte count in memory with a periodic reconciliation (every 500 writes or 5 minutes), and a per-hash `index.json`. *Test:* `test_a_cache_write_does_not_scan_the_whole_cache`.

**L-5 The cache folder is deleted while a picture is being written.** S3 · L1. *Now:* `store` writes a pid-named temp then `os.replace`; a missing folder is recreated by `mkdir(parents=True)`; a purge during a write can leave a picture for a purged hash (harmless, swept as orphan). *Test:* `test_a_purge_during_a_render_leaves_no_error`.

**L-6 Memory pressure on a phone.** S2 · L2.
*Now:* the budgets are windowed and halved on a viewport under 480 px or `deviceMemory <= 2` (`splitWindow.ts:240`). Safari does not expose `navigator.deviceMemory`, so it is `undefined`, and a tablet or a large phone on Safari gets the large budget (128 MB of decoded pixels) (`splitWindow.ts:246`); a tab killed by the system loses the unsaved marks (E-3). *Should:* treat an unknown device memory as small on a touch device (`(pointer: coarse)`), and listen for the `pagehide`/`visibilitychange` to persist marks. *Test:* `splitwindow.test.ts: an unknown deviceMemory on a coarse pointer gets the small budget`.

**L-7 `jason-web` is restarted while a page is open.** S3 · L2.
*Now:* the write guard's token is per process (`web/guard.py`), so after a restart every write is refused until the page is reloaded; the picture routes need only the sign-in cookie. The refusal arrives as a 403 on an autosave. *Should:* the UI recognises the guard's "token" refusal as "jason was restarted; reload to continue", keeps the queued marks (they are in IndexedDB), and reloads itself once the person agrees. *Say:* "jason was restarted. Your marks are kept. [Reload and continue]". *Test:* `e2e: a restart mid-edit keeps the marks and reloads on request`. **Unverified:** whether sign-in survives a restart (a signing key per process would not).

### M. The file is hostile

The rule: **the document is untrusted data.** jason does not execute anything in it, does not follow its links or fetch its resources, and does not let it set how much of the machine it may use. The current state, by what each tool does:

| Content | Behaviour today | Verified |
|---|---|---|
| JavaScript, actions, `Launch` | the renderers used (`pypdfium2` with forms off, `render(... may_draw_forms=False)`; PyMuPDF) run no script in the standard builds; pdf.js has scripting off (`splitPdfjs.ts`: `isEvalSupported: false`, `enableXfa: false`) | partly: the options are in the source; the builds' lack of a script engine is **unverified** |
| XFA forms | not drawn; pdf.js XFA off | source |
| Embedded files and attachments | not extracted by any splitter code | source (no `embfile` use in the splitter) |
| Page-level actions and annotations in a *part* | `pypdf` `add_page` copies the page object **with its annotations and additional actions** into the new file, so a hostile action travels into the library | **unverified** for the installed version; by pypdf's design |
| External references (links, `URI`, remote images) | not fetched | source |
| Decompression bomb (a small stream that expands) | decoded by the renderer in the web process: bounded only by the machine | no limit in code |
| Huge image dimensions | decoded in full by the renderer to scale down | no limit in code |
| Recursion (a page tree or form XObject loop; nested outlines) | engine-specific; `pypdf` can raise `RecursionError`, caught per part as `Exception` | partly |
| A crash in the native renderer (a segmentation fault) | **kills the web process** (the renderer is imported and called in-process: `render_page`) | by construction |

**M-1 No time limit on any parse, draw, or cut.** S1 (availability) · L2. *Now:* `render_page`, `scan`, `_read_pdf`, `_peek_pages`, and `cut_pages` run in the caller's thread and process (the web server for a picture, an open, a review, and an apply; a job process for `--facts`). A pathological page can hold a request thread for minutes; in a threaded server this starves the others (**unverified** whether the server is threaded). *Should:* section 8. *Say:* "This page took too long to draw and was stopped. You can still mark it." *Test:* `test_a_page_that_never_finishes_drawing_is_stopped_and_the_server_stays_up`. *Guard:* a deadline in the render worker.

**M-2 No memory ceiling.** S1 (availability) · L2. *Now:* none. A page with a 40,000-by-40,000 one-bit image decodes to hundreds of megabytes or more before it is scaled; a Flate bomb expands without a limit. The web process (which also holds the Keeper and Google sessions) is the one that runs out. *Should:* a worker with a memory ceiling, a pixel cap checked before decode where the engine allows it, and a pixel ceiling on the output. *Test:* `test_a_decompression_bomb_kills_the_worker_not_the_server`. *Guard:* the Job Object or `RLIMIT_AS`.

**M-3 A native crash.** S1 (availability) · L1. *Now:* a fault in MuPDF or PDFium ends the web process, losing every open request and the in-memory state. *Should:* the worker dies and is respawned; the request answers 422 for that page; the page is recorded `unrenderable` after two crashes. *Test:* `test_a_worker_crash_is_one_unreadable_page`.

**M-4 Hostile content copied into new files.** S2 · L1. *Now:* see the table: annotations and actions on a copied page. *Should:* a **sanitise on cut** option, on by default: remove `/AA` from pages and annotations and any action of type `JavaScript`, `Launch`, `ImportData`, `SubmitForm`, `GoToR`, and `Rendition`; keep internal `GoTo` links and `URI` links; count what was removed and say so in the review ("3 pages carried actions that were removed from the new files"). This changes bytes, so the part's hash differs from the straight copy and the determinism test must cover it. *Say:* that sentence. *Test:* `test_a_cut_part_carries_no_script_launch_or_submit_action`. *Guard:* a `sanitise` step in `cut_pages`. **Decision 6.**

**M-5 A text layer that lies.** S3 · L2. *Now:* suggestions and the title guesses read the file's own text layer; a hostile or merely wrong layer yields wrong suggestions, which a person disposes of. The title is cut to 90 characters and drawn as text (React escapes it). *Should:* nothing more; the alt text of a confidential file is the page number only (verified in the design). *Test:* `test_a_title_with_markup_is_drawn_as_text`.

**M-6 The file makes jason fetch something.** S1 · L1. *Now:* nothing in the splitter dereferences a URL from the file. *Should:* an assertion: the worker runs with no network (no inherited socket handles; on Windows, a Job Object cannot cut the network, so this is a convention and a test of the worker's code, not a sandbox). *Test:* `test_the_worker_imports_no_network_module` (static check on the worker's imports).

### N. The web layer

**N-1 A confidential file's page text reaches the board level.** S1 · L3.
*Now:* the picture route requires the private view for a confidential file (`web/split.py`: P3), but `GET /api/split-session` is gated at P2 (`_gate`) and returns, for a confidential file: `facts` with each page's `title`, `header`, `footer`, `date`, and `label` (only `lqip` is withheld; `facts_view`, `split_session.py:407`); `suggestions` with their `why` sentences built from the signals; `segments[].labels` with a guessed title; and `applied.parts` with kind guesses (`SplitSession.view`, `split_session.py:555`). `view(mask=True)` blanks only `source.ref`. The listing masks the label. This is the largest hole in the design's own rule ("a confidential file's pictures and pages are served only when the signed-in person may see confidential files"). **The UI's handling is unverified**; the server is what must refuse. *Should:* `view_of`, `facts_view`, `review`, `flags`, and the suggestion `why` are masked to **counts and numbers** for a confidential file below P3: no title, header, footer, date, or sentence derived from text; the screen draws the cards with numbers and glyphs. At P3 (private view open) they show. *Say:* "This file is confidential. Page text is shown only in the private view." *Test:* `test_a_confidential_session_withholds_every_page_derived_text_below_the_private_view` (a walk over every field of every payload, with a canary string in the made-up PDF's first line that must not appear), `test_the_canary_is_found_in_the_private_view`. *Guard:* one `mask_for(viewer, session)` applied at the single place payloads are built; a test that fails if a new field is added without a mask decision.

**N-2 The confidential flag fails open and is cached for a year.** S1 · L2.
*Now:* `is_confidential` asks the library row each time, but if the row cannot be read (`_library_row` returns `None` on any `sqlite3.Error`) it falls back to the flag from the day the session opened (`split_session.py:256-263`): a flag **set since** is not seen while the database is busy, and pictures are then served with `Cache-Control: private, max-age=31536000, immutable`, which the browser keeps for a year (`web/split.py`: `IMMUTABLE`). A flag set after pictures were first served never reaches the copies already in a browser cache. Confidentiality should never go down. *Should:* (a) take the stricter of the stored flag and the row's; on an unreadable row, treat the session as confidential until it can be read (fail closed, and say so); (b) for a library or Drive source use `private, no-cache` (revalidate each time; the 304 path already checks access before it answers) or a short `max-age=300` so a changed flag takes effect in minutes; the cost is one conditional request per cell. *Say:* "jason could not check whether this file is confidential just now, so its pages are hidden. Try again in a minute." *Test:* `test_an_unreadable_library_row_hides_the_pictures`, `test_a_flag_set_after_open_applies_within_the_cache_window`. *Decision 3.*

**N-3 Names in URLs, titles, tooltips, thumbnails, test screens.** S1 · L2.
*Now:* routes carry a session id and a page number; history lines carry ids and counts; the Drive refusal words never include Google's text; `access.log_or_refuse` logs `split/<sid>` and the page (`web/split.py`). Not verified: the browser tab title and `<title>`, the page-cell `title`/tooltip attributes, the e2e screenshots and recordings under `e2e/` and any `screens/` folder, and the pdf.js document title (a PDF's `Title` metadata can be a person's name and is shown by pdf.js's own UI if its viewer were used; the splitter draws its own). *Should:* a check that walks the rendered DOM and the document title for a canary in the file's name and metadata (made-up file named `Example Owner Notice.pdf` with `Title` metadata and a canary first line) and finds none for a confidential file in any view, including the print stylesheet and the magnifier; and the e2e suite uses made-up files only, with the canary check as a step. *Test:* `e2e: a confidential file's name, metadata and text appear nowhere in the document, its title, attributes, or network paths`. *Guard:* the canary test.

**N-4 CSRF and Origin edge cases.** S2 · L1.
*Now:* writes require a matching `Origin`, a Host check, and the token (`web/guard.py`); a missing or `null` Origin is refused. The picture route is a `GET` that reads and draws: it changes no record, but it spends CPU and disk (N-5). A `GET` that writes the cache is reachable by an image tag on another origin if the person is signed in (the cookie rides along) but the response is not readable by that origin and `Content-Security-Policy: sandbox` is set, so the result is a CPU cost, not a leak. *Should:* require `Sec-Fetch-Site: same-origin` (or absent) on the picture route and refuse `cross-site`, and cap renders per person (N-5). *Test:* `test_a_cross_site_request_for_a_picture_is_refused`.

**N-5 Rate abuse: a script or a bug asks for everything.** S2 · L2.
*Now:* `web.requests_per_minute` is a documented limit with no registered row (**unverified**; searched `web/`). Every cache miss draws a page in the request thread; five sizes of 3,000 pages is 15,000 draws. A scrolling person, a stuck retry loop in the client, or another signed-in script can occupy every thread. *Should:* a per-person token bucket on render misses (default 600 a minute with a burst of 120; cache hits and 304s counted separately at a looser cap), a bounded render queue (M-1, section 8) that answers `503` with `Retry-After` when full, and client backoff on 429/503. *Say:* "jason is busy drawing pages. They will appear in a moment." *Test:* `test_a_flood_of_picture_requests_is_throttled_and_the_server_still_answers_other_routes`. *Guard:* `split.render_requests_per_minute` and `split.render_queue_max`.

**N-6 An error message carries a name, an id, or a path.** S1 · L2.
*Now:* `PageUnreadable` carries the exception type only (`render_page`); `_read_pdf` the type; `_fetch_drive` maps Google's refusal to words. `_resolve` words and `ValueError`s are jason's own. The `ResourceBusy` message carries a lock name and a process id (`locks.hold`), which reach the console if uncaught. *Should:* the console's error mapper turns `ResourceBusy` and `OSError` into fixed words (no path, no pid). *Test:* `test_no_error_answer_contains_a_path_a_pid_or_an_id` (provoke each exception class).

## 3. The states a crash can leave, named

So the journal (section 5) and the doctor (section 6) speak one vocabulary.

| State | What is on disk | How it arose |
|---|---|---|
| **S-open** | a copy with no session | a kill between `_ingest` and `save` |
| **S-session-damaged** | a session file that does not parse | a kill during an unflushed write, or disk damage |
| **S-confirmed-partial** | `confirmed`, `applied.partial: true`, some parts written | a failed part or a kill in the loop |
| **S-orphan-pin** | a pin with `splitFrom: session:<id>` that the session's `applied.parts` lacks | a kill between the pin and the session save (G-3) |
| **S-orphan-part** | a file under the held store with no pin and no session record | a kill between `_keep` and the pin; or a hand-copied file |
| **S-pin-no-file** | a pin whose `ref` file is missing | a file removed by hand; a restore of the data folder from different times |
| **S-library-adopted** | a library document whose hash a session's part has but whose record says held | a kill during the library intake (H-2) |
| **S-job-orphan** | a queued or running job whose subject (pin, library id, session) is gone | an undo, a purge, or a kill after queueing |
| **S-cache-orphan** | pictures, facts, or a copy for no session | purge races, an aborted open |
| **S-stage** | `_incoming/*.part`, `jason-split-*` temp folders, `.tmp` files | a kill during a copy, a library staging, or a write |

## 4. Undo apply: a signed, journalled reversal

### 4.1 What a person gets

A button on an applied split, *Undo this split*, and `jason split ID --unapply [--part s2,s3] [--whole] --reason TEXT --by NAME [--yes]` (a dry run without `--yes`). It exists because the commonest real mistake is found after the fact: a start one page off, a wrong filing choice, a split of the wrong file. The old way (find each pin and each held file by hand) loses a day.

It is a **reversal of what the apply wrote**, not a deletion of history. It never touches the original. It never removes anything a person has since used (4.3).

### 4.2 What it removes

Per part, by what the journal says the apply created (section 5), never by guessing from a name:

| Part was | Reversal | Kept |
|---|---|---|
| **held** (in jason's store, no slot) | the file moves to `split/trash/<apply-id>/` for `split.trash_days` (14), then goes; the held-shelf entry is retired | the part's hash and the journal line |
| **filled into a slot** | the pin is marked `unpinned` with who, when, and the reason (as record intake's *Unpin* does: [record-intake.md](record-intake.md), the pick table); its file moves to the trash as above | the pin row (marked), the history |
| **filed in the library** | the library's own retire act, if the library has one for a document filed by this apply (a dependency; **unverified** that `jason library` exposes it). Without it, the part is **refused** with "remove it in the library; its id is X" | the library row |
| **a duplicate or a collision** | nothing: it wrote nothing | |
| **queued jobs** for the parts | queued ones are cancelled (`jobs.cancel`); a running one finishes and re-checks its subject (I-2) | the job rows |
| **the session** | goes back to `draft`, version raised, with the confirmed boundaries restored as the draft; the old `applied` moves to `applications[]` | the whole record |

Nothing is hard-deleted by the reversal itself. The trash is the delete, after a delay, by the sweep. This follows the splitter's rule that nothing is deleted on failure, and makes undo of an undo possible for two weeks (`--restore`).

### 4.3 What it refuses

A part is **blocked** (and the whole is refused under `--whole`) when something has been done with it since the apply. Each of these is a fact the journal and the stores can show, and each is listed with who and when:

| Blocker | Why |
|---|---|
| a person **read it back and confirmed or kept** the reading (the read-back's "kept" mark) | a person's decision rests on it |
| the pin was **replaced, marked current, acknowledged, or cited** (a packet, an agenda item, a letter, a key-documents link) | other records point at it |
| the file's hash appears in **another pin or another session's parts** | it is shared |
| the library document has been **reclassified, moved, edited, or linked** since | the library's record has become a person's |
| a **second apply** or an unapply of the same session is running | one at a time |
| the **journal says the apply did not finish** (use Finish or Undo from the recovery prompt instead) | different path (5.7) |

A blocked part is not an error: the dry run says "Parts 2, 3, 5 can be undone. Part 4 cannot: Sam Example confirmed its reading on 12 October. Part 6 cannot: it is cited in the packet for the October meeting." The person can undo the reversible ones (`--part`), or ask whoever confirmed to release theirs.

A part merely **opened, viewed, or read without a decision** does not block: "read" in the sense of the machine's automatic read-back is not a person's decision. The test is a recorded person's act, not a read.

### 4.4 Who may, and the signature

Any person who may apply may unapply an apply **they made**, within `split.unapply_hours` (72); after that, or for another person's apply, an officer or the administrator, with a reason. The reason is required and is kept in the journal, **not** in the history line (the history line holds ids and counts). Where the board has adopted two-person approval for writes of this kind, unapply uses the same approval path (`approvals` kind `split-unapply`); that is a decision (section 10).

### 4.5 How history records it

Two additions, both append-only:

- `records/history.jsonl` gets `act: split-unapply` with the session id, the apply id, counts (`parts`, `reversed`, `blocked`), and `by`. The original `split-apply` line is **not** edited.
- The session's `applications[]` keeps, for each apply, its journal path, and `reversals[]` lists each undo with `by`, `at`, `reason`, and per-part outcomes.

### 4.6 The words

> Undo split ab12cd34? This removes the 7 files it wrote (3 held, 4 filed to slots) and returns the draft to where you confirmed it, with your marks. Nothing in Drive or in the library's original files changes. 5 files can be undone now. 2 cannot: part 4 (Sam Example confirmed its reading on 12 October), part 6 (it is cited in the October packet). [Undo the 5] [Cancel]

### 4.7 Tests

`test_unapply_reverses_held_and_slot_parts_and_restores_the_draft`; `test_unapply_refuses_a_part_whose_reading_a_person_kept`; `test_unapply_refuses_a_part_cited_elsewhere`; `test_unapply_leaves_the_original_and_other_pins_alone`; `test_unapply_is_a_dry_run_without_yes`; `test_unapply_writes_a_history_line_with_no_reason_text`; `test_unapply_can_itself_be_restored_from_the_trash`; `test_unapply_cancels_queued_jobs_and_a_running_ocr_writes_nothing` (I-2); `test_unapply_resumes_after_a_kill_midway` (it is journalled as well, 5.8).

## 5. Apply as a two-phase journal

### 5.1 The aim

An apply is a series of writes to four places (the part files, the slot store, the library, the session), and then queued work. No ordinary file system makes that atomic. The aim is smaller and achievable: **at any instant, a crash leaves a state that a person can finish or undo, and the stores never point at what is not there.** The journal is the memory that lets the next open tell which.

It follows the pattern already in the tree: `jason.workflows.store`, an append-only JSONL file with a hash chain, an `fsync` after each line, a torn last line cut off on the next read, and an expected sequence number so a second process fails loudly ([workflows/store.py](../src/jason/workflows/store.py)). The splitter journal reuses its writer and reader; it adds no new format.

### 5.2 The journal

`<data>/split/journal/<session>.jsonl`, one file per session, events in order. Each event: `n`, `prev` (hash of the previous line), `at`, `kind`, `by`, `apply` (the apply id), and a `detail`.

| Event | Written | Detail |
|---|---|---|
| `intent` | phase 0, first | the **plan fingerprint** (G-1), the session version, the source hash, the filing choices, the rotations and drops, and for every part: `ordinal`, `segment`, pages, planned action, and a **pre-allocated pin id** (`p-xxxxxxxx`) for a slot part |
| `staged` | phase 1, per part | `ordinal`, SHA-256, size, page count, the staging name |
| `placed` | phase 2, per part | `ordinal`, final relative address, hash |
| `pinned` | phase 2, per slot part | `ordinal`, the pin id, or `collided` with the reason |
| `library` | phase 2, per library part | `ordinal`, the library id and kind, or the reason it was held |
| `commit` | phase 3 | counts, the session version written |
| `queued` | after commit | the read-back and OCR job ids |
| `abort` | on a roll back | the reason |

### 5.3 The phases

**Phase 0, prepare** (under the session lock, briefly). Re-run the review inside the lock; compare its fingerprint with the one the person confirmed; verify the source hash; check the slot store reads and writes; check room for **all** parts plus margin in one call; set the session `applying`; write `intent`. Release the session lock. Nothing outside jason's own folders has changed, and the `intent` is the person's signed confirmation: its fingerprint is what they saw.

**Phase 1, stage.** Cut each part with one open reader to `split/staging/<apply-id>/<ordinal>.pdf` (the staging folder on the temp drive, per `jason.config.apply_temp_dir`), `fsync`, **verify** by reopening (page count equals the range count, the hash is stable), write `staged`. Staging is invisible to every other store. A kill here leaves only the staging folder and an `intent`: **roll back is automatic and safe** (delete the staging folder, write `abort`).

**Phase 2, place.** Under the apply-only lock and, per part, the stores' own locks in a fixed order (session, then record slots, then library; never the reverse):
1. Copy the staged file to `<final>.part` in the destination folder (the staging drive may differ from the data drive, so a rename across volumes is not available), `fsync`, `os.replace` to the content-addressed final name, write `placed`. A file already at that address with the same hash is success.
2. For a slot part: **compare-and-append** the pin with the pre-allocated id inside `record_slots._write_store`'s change function, re-checking the slot's holders in the same lock (G-2). If the id already exists, do nothing (idempotent). If busy, write `pinned: collided`; the placed file stays as a held part.
3. For a library part: hand the staged files to the intake, then `library` with what it did.

**Phase 3, commit.** Write the session whole through `durable_write` (`applied`, version raised, status `applied`); write `commit`; write the history line. **Then** queue read-backs and OCR (`queued`). Jobs are queued after the commit, so no job ever refers to a part that a roll back could remove, and a kill after the commit loses only the queueing, which resume and the doctor redo.

The order of visible effects is: file, pin, session, history line, jobs. Each step is idempotent on its own key (hash, pin id, apply id), so a re-run of any step is safe.

### 5.4 Resume or roll back at the next open

On `open`, `act`, the list, and `--doctor`, `recover(sid)` reads the journal's tail:

| Last event | State | Automatic? | The person is offered |
|---|---|---|---|
| none, or `commit` or `queued` | clean | yes (re-queue anything missing after a `commit`) | nothing |
| `intent` or `staged` only | nothing visible written | **roll back automatically** (staging is jason's scratch) | nothing; a note in the session |
| `placed`, `pinned`, or `library` without `commit` | partly visible | **no**: a person decides | *Finish it* (re-run phases 2 and 3 from the journal, same plan, same pin ids), *Undo it* (the unapply path for the parts placed), *Leave it* (stays `S-confirmed-partial`, shown on the list) |
| `abort` | rolled back | yes | nothing |

*Finish it* needs no new confirmation: it completes the intent the person signed, with the same fingerprint, and refuses if the source hash or any destination changed since (then it offers *Undo*). *Leave it* is allowed and visible. A background job never finishes or undoes an apply: **jason proposes; a person acts**. Automatic roll back is limited to staging, which has no outside visibility.

### 5.5 Kill points, for the tests

Fault injection (`JASON_FAULT=split.apply:<point>`, read only when set, and only in tests and the doctor's drill) raises at each point; the test then runs `recover` and asserts the state and the offered choices. Points: `after_intent`, `after_stage:<n>`, `after_place:<n>`, `after_pin:<n>`, `after_library:<n>`, `before_session_save`, `after_session_save`, `after_commit`, `after_history`, `after_queue:<n>`. Expected: no point loses a part, duplicates a pin, or leaves a pin to a missing file; `after_place` and `after_pin` offer Finish or Undo; `after_session_save` and later resume to clean without asking.

### 5.6 Locks, ordered

`split-open-<sha>` (open) → `split-<sid>` (draft writes, phase 0 and 3, briefly) → `split-apply-<sid>` (phase 1 and 2, long) → `record-slots-<profile>` (each pin) → `library` (the intake). Draft acts on an `applying` session are refused at once in words (G-6). Purge, sweep, and the doctor's fixes take the same locks and skip an `applying` session. A model job never overlaps: apply takes neither the GPU lock nor `local_ai.preflight`.

### 5.7 Windows and the temp drive

`os.replace` can raise `PermissionError` while an antivirus scan or an indexer holds a file: retry three times at 50, 150, and 400 ms, then fail the part (G-8). Folder `fsync` is not available on Windows; the file `fsync` before the replace is. The staging folder follows `JASON_TEMP_DIR` (AGENTS.md), so a full system drive is not touched; `tempfile` creates it, and the doctor sweeps what a kill leaves (`S-stage`).

### 5.8 Undo is journalled the same way

`--unapply` writes `intent` (kind `unapply`), moves each file to the trash (a rename within the volume, atomic), writes `unpinned` per pin, and `commit`. A kill resumes with the same offer: *Finish the undo* or *Leave*.

### 5.9 Tests

The kill-point matrix of 5.5, one test per point; `test_the_plan_is_recomputed_inside_the_lock_and_a_moved_draft_is_refused` (G-1); `test_a_pinned_id_is_reused_on_resume`; `test_staging_is_removed_on_rollback`; `test_resume_refuses_a_changed_destination`; `test_jobs_are_queued_only_after_commit`; `test_a_second_apply_on_a_session_that_is_applying_is_refused`.

## 6. `jason split --doctor`: list the inconsistent states, and fix the safe ones

### 6.1 The command

```
jason split --doctor [ID]                  list findings (read-only; the default)
jason split --doctor --json                the findings as data
jason split --doctor --fix F-3 --yes --by NAME     apply one finding's fix (a dry run without --yes)
jason split --doctor --fix safe --yes --by NAME    apply every fix of class A and B
```

Read-only by default: no write lock is taken, nothing is changed, and it runs while the server is up. It exits 0 clean, 1 with findings, 2 on an error of its own. A finding has an id (stable for the same state), a class, what it is, why it matters, and the command that fixes it. It prints no file name and no page text.

### 6.2 Classes of fix

| Class | Meaning | Who |
|---|---|---|
| **A** | derived or scratch, rebuildable: stale staging, `.tmp`, `.part`, orphan pictures, unreferenced facts, orphan copies older than a day | `--fix safe` |
| **B** | re-queue derived work: missing facts job, missing read-back, missing OCR | `--fix safe` |
| **C** | touches a record: an orphan pin, an orphan part, a pin with no file, a session restored from `.bak`, an unfinished apply | one finding at a time, named, by a person; each writes a journal event and a history line `split-doctor` |
| **D** | cannot be fixed by jason: a damaged source copy, a library document in an odd state | reported with what to do |

### 6.3 What it checks

| Id | Check | Class |
|---|---|---|
| DR-01 | a session file that does not parse; restore from `.bak` available? | C |
| DR-02 | a draft or confirmed session whose source copy is missing | D (reopen the file) |
| DR-03 | a copy with no session, older than a day | A |
| DR-04 | a copy whose size or hash differs from its session's `source` | D |
| DR-05 | facts missing, a lower version, or a page count that differs from the session's | B |
| DR-06 | `sources/_incoming/*.part`, `.tmp` files, `jason-split-*` and `split-peek-*` temp folders older than a day | A |
| DR-07 | pictures for a hash no session names; a cache over its bound; a `.tmp` picture | A |
| DR-08 | an applied session's part whose file is missing or whose hash differs | D |
| DR-09 | a pin with `splitFrom: session:<id>` that no session lists, or that the session lists as a collision (**S-orphan-pin**, G-3): *adopt it* (record it in the session) | C |
| DR-10 | a part file in the held store with no pin and no session record, **only when** it carries the splitter's sidecar (new parts will; older ones are reported as "unattributed" and left) (**S-orphan-part**) | C (retire to trash) |
| DR-11 | a pin whose file is missing (**S-pin-no-file**) | D |
| DR-12 | a queued or running job whose subject is gone: read-back for a missing or unpinned pin; OCR for a missing library id; facts for a missing session | B (cancel) |
| DR-13 | a job queued for more than an hour with no worker holding `jobs.worker_guard` | report |
| DR-14 | `confirmed` with a partial `applied`, or a journal with `intent` and no `commit` (**S-confirmed-partial**) | C: Finish, Undo, Leave |
| DR-15 | `applying` with its lock free (the process died) | C (as DR-14) |
| DR-16 | two live drafts on one hash | report; offer to merge or decline one |
| DR-17 | a library document filed by a split part whose session says held (**S-library-adopted**) | C (adopt) |
| DR-18 | the sweep's high-water mark is ahead of the clock | report |
| DR-19 | lock notes whose holder is gone | A (`locks.holders` already clears them) |
| DR-20 | the registry's split limits are outside their range (clamped silently today) | report |

### 6.4 Cost and safety

It lists with directory scans and one read of each small JSON file; it hashes a source copy only with `--deep` (and says it will take time). It never deletes a copy, a part, or a pin: class A files go to the trash like everything else the splitter removes, with the 14-day delay; class C acts are journalled and reversible. Every `--fix` leaves a history line with ids and counts. The console gets the same list read-only (`GET /api/split-doctor`, the board's) and shows a badge on the splits list when there are findings; the fixing stays on the command line, where a person types `--by`.

### 6.5 Tests

One test per check, each building the state by fault injection or by hand and asserting the finding id and its class; `test_the_doctor_changes_nothing_by_default` (a snapshot of the data folder before and after); `test_fix_safe_touches_only_class_a_and_b`; `test_adopting_an_orphan_pin_links_it_to_its_session`; `test_the_doctor_prints_no_file_name_or_page_text`.

## 7. Draft recovery: the experience

### 7.1 What goes wrong today, in one line each

A reload on the local route loses the file and the queued marks (E-4). A tab that dies before a *failed* save holds nothing (E-3). The saved copy is per tab, keyed to one version, and ignored when the draft moved on (E-5). A restart of the server needs a reload and says nothing (L-7). Two tabs on one draft race each other with no warning.

### 7.2 The design

**Write-ahead.** Every op is written to IndexedDB (`jason-split-recovery`, one object store, key `<user>:<session>`) *before* it is sent. The row holds: the base version, the base starts, the ordered ops, the derived starts, the time of each op, and a device id. It holds **page numbers and short structural labels only**: no file name, no page text, no title for a confidential file, and no bytes of any PDF. It is removed when the server acknowledges the last op, and after `split.draft_days`. A different signed-in person on the same browser uses a different key and never reads another's. Sign-out clears it.

**Send on leaving.** On `pagehide` and `visibilitychange` to hidden, the store sends the queue with `fetch(url, {keepalive: true, headers})` (the guard needs a header, which `sendBeacon` cannot set; the payload is under the 20 KB budget).

**One tab.** `navigator.locks.request("jason-split-<id>")` marks the tab that edits; a second tab on the same draft opens read-only with "This draft is open in another tab of this browser. [Take over]". Across browsers and people the server's version and the editor note (E-1) say who.

**The three-way merge.** On open, compare the stored row with the server:

| Case | What the person sees |
|---|---|
| The server's version equals the row's base | A bar: "Restored 3 marks from 10:41 that were not saved. [Keep] [Discard]" (default: kept, applied locally and sent) |
| The server moved on | A comparison of three columns: *when you started* / *yours* / *the draft now*. Per page: mine changed it and theirs did not, or the reverse, or both did the same: **merged without asking**. Both changed it differently: listed, defaulting to *the draft now*. |
| The draft is gone (purged, swept, or never created because the upload had not finished) | "This draft is no longer on the server. Your N marks are kept here. [Choose the file again to keep working]" and, for the local route, E-4's match by size and hash |

**The local route.** The row is keyed by the file's size and a prefix hash until the draft exists, then by the session. On reload with no file: "Choose the same file again to continue. It is not kept in the browser." The match shows the page count and the first page as proof. A browser that offers a persistent file handle can offer the file without choosing it; that is an enhancement, not the design.

**Sign of life.** The save line is always one of: *Saved 10:42* · *Saving…* · *Not saved: offline. Your marks are kept on this device.* · *Not saved: jason is restarting. Your marks are kept.* · *Conflict* · *Restored from this device*. Never silence.

**Server-side.** The session's `.bak` (E-8) and the `editor` note.

### 7.3 Tests

`splitStore.test.ts` for write-ahead order, the merge cases, and the cleared-on-ack row; `e2e/tests/recovery.spec.ts`: kill the tab after three marks; reload on the local route before the draft exists; a second tab; a restart of the server; the confidential file's recovery row holds no text.

## 8. Rendering isolation: a render worker with a ceiling

### 8.1 What it protects

Any parse of an untrusted PDF in the web process: drawing a page, the page count and encryption probe, the facts pass, the cut. The web process holds the sign-in, the write guard's token, the Drive and Keeper clients, and every open request. A native renderer that crashes, loops, or allocates without limit takes all of that down. The worker puts the parsing in a process that can be killed.

### 8.2 The design

**Process.** A pool of `split.render_workers` (default 2; 1 to 8) long-lived child processes, started by `subprocess.Popen([python, "-m", "jason.tasks.split_render_worker"])` (not `fork`; Windows has none), each with its own pipes. The worker is a small program with one loop: read a length-prefixed request from stdin, do it, write a length-prefixed answer to stdout. It imports the renderers and `pypdf` and **nothing else of jason** (no config, no stores, no network clients, no profile), so a hostile file has no jason state to reach even if it takes over the worker.

**Operations.** `probe(path)` (page count, encrypted, repaired, oversize pages, the number of nodes in the page tree up to a cap), `render(path, page, size, rotate)` (the encoded picture), `facts(path, from, to)` (the batch the scan makes), `cut(path, ranges, rotate, sanitise, out_path)` (writes a staged part). The parent builds `path` from the session's hash; **a request never carries a path from the outside**.

**Clean room.** The child runs with a scrubbed environment (no `ANTHROPIC_*`, Keeper, Google, or AWS variables; only `PATH`, `TEMP`), the temp folder as its working directory, `stdin`/`stdout` as the only handles (`close_fds`; on Windows `CREATE_NO_WINDOW` and handle inheritance off), and read access to the sources folder only by convention (a stronger sandbox is 8.5).

**Ceilings.**

| Ceiling | How | Default |
|---|---|---|
| **Time** per request | the parent waits with a deadline; on expiry it kills the child and starts another; the request answers "took too long" | `split.render_timeout_seconds`: 10 for a picture, 60 for `facts` and `cut` per 50 pages (time, 2 to 300) |
| **Memory** | Windows: a Job Object with `JOB_OBJECT_LIMIT_PROCESS_MEMORY` and `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`, set through `ctypes` or `pywin32` (**unverified** which is installed here; `ctypes` needs no dependency). POSIX: `resource.setrlimit(RLIMIT_AS)` set in the child at start (`RLIMIT_CPU` too) | `split.render_memory_mb`: 1,024 (size, 256 MB to 4 GB) |
| **Pixels** | the worker reads the page's image dimensions before drawing (the page object, not the stream) and refuses a decode over a pixel cap; the output is at most 1600 px | `split.render_max_pixels`: 400 million (count) |
| **Output** | the parent refuses an answer over `4 × 1600 × 1600` bytes or with a bad header | fixed |
| **Lifetime** | recycled after 200 requests or when its working set passes 60% of the ceiling (leaks in native code) | fixed |
| **Queue** | a bounded queue per pool; full answers 503 with `Retry-After` and the client backs off | `split.render_queue_max`: 64 (count) |
| **Per person** | a token bucket on render misses (N-5), a concurrency cap of 4 in-flight per person so one person cannot take the pool | `split.render_requests_per_minute`: 600 |

All of these are registry rows ([instance-limits.md](instance-limits.md)), read at one point each, with the registry's words when hit. None has a per-act override. A timeout is not a limit that can be set to zero.

**Failure handling.** A timeout, a memory kill, or a crash is: the child is replaced; the request answers 422 for that page ("This page could not be drawn safely"); a **negative cache** entry `(sha, page, size)` lives ten minutes in memory so a scroll does not retry-storm; after two failures the page is recorded `unrenderable` in the facts, drawn as a card, and still markable. If the pool cannot start at all, the route answers 503 with the install words; it does **not** fall back to in-process rendering in production.

**Probe on open.** `open_session` calls `probe` in the worker, so a hostile file's first parse never happens in the web process; the file is refused in words if the probe times out ("This file took too long to open and was stopped. It may be damaged or unusual.").

**Cut in the worker.** Apply's phase 1 runs `cut` in the worker (one open reader per apply), which also bounds pypdf's memory and recursion; a worker death is a failed part (G-8), not a dead server. `sanitise` (M-4) lives here.

**Tests and development.** `JASON_SPLIT_RENDER=inprocess` runs the same operations in-process, for unit tests and machines without the pool; the production default is `worker`, and a startup line says which is in use. The worker protocol is tested with a fake child.

### 8.3 What it does not do

It does not execute anything from the file: no renderer here runs script. It is not a security sandbox on its own: a native-code exploit in the renderer still runs as the user. It bounds the *damage of failure* (time, memory, a crash) and removes jason's secrets from the worker's reach. Treat the worker's answers as data, never as code; the parent decodes nothing but a length-prefixed byte string.

### 8.4 Where else the same rule applies

The facts job (`jason split ID --facts`) already runs as its own process under the worker lane; it gets the same ceilings by calling the worker. The browser's pdf.js draw of a file chosen on this computer runs in the person's own browser, inside the page's origin, with scripting, XFA, and eval off; add `maxImageSize` and a canvas area cap to its options (**unverified** the option names for the pinned `pdfjs-dist` 5.4.149). Library OCR (`library_ocr.run`) reads library files with Docling or Tesseract in the worker lane's process; it needs the job timeout (I-4), not this pool.

### 8.5 Stronger options, named and not chosen

| Option | Gain | Cost | Verdict |
|---|---|---|---|
| Windows AppContainer or a low-integrity token for the worker | no file access beyond what is granted | substantial `ctypes` work, hard to test, differs by Windows edition | later, if the threat model asks |
| A container or a separate user for the worker | real isolation | needs the operator to set it up; not general | document as a deployment option |
| Rendering in WebAssembly (pdf.js server-side, PDFium wasm) | a memory-safe sandbox in a runtime | slower, a new dependency, a different output | revisit with open decision 1 of [pdf-splitter.md](pdf-splitter.md) |
| Drawing everything in the browser | no server parse | the PDF would go to the browser, a rule the design keeps off ([pdf-splitter.md](pdf-splitter.md) 9.7) | no |

### 8.6 Tests

`test_a_page_that_never_finishes_is_killed_and_the_pool_recovers`; `test_a_memory_bomb_is_killed_at_the_ceiling` (a made-up PDF with a huge declared image); `test_a_crashing_child_is_one_unreadable_page`; `test_the_child_environment_holds_no_secrets`; `test_a_request_never_carries_a_path`; `test_the_queue_full_answers_503_with_retry_after`; `test_the_negative_cache_stops_a_retry_storm`; `test_the_worker_imports_nothing_of_jason_beyond_its_protocol`; `test_inprocess_mode_is_off_by_default_in_production`.

## 9. The hardening backlog

Value is the harm avoided (severity times likelihood, counting the failures it also fixes); effort is the build. S = a day or less, M = a few days, L = a week or more.

| # | Item | Fixes | Value | Effort | Notes |
|---|---|---|---|---|---|
| 1 | Mask page-derived text for a confidential file below the private view; the canary test | N-1, N-3 | very high | S | **Built 2026-10-11** (`split_mask`, `tests/test_split_confidential.py`). The server is what must refuse. One mask function at the payload builders |
| 2 | Confidential flag fails closed; short cache for library and Drive sources | N-2 | very high | S | **Built 2026-10-11**: `private, no-cache` with the standing in the ETag (revalidation, not a `max-age`). Decision 3 on the cache lifetime stands for a later `max-age` |
| 3 | `durable_write` (flush, fsync, replace, retry) and session `.bak` | G-4, E-8, B-5 | high | S | One helper, used everywhere the splitter writes. **Built 2026-10-11**: `jason.durable` (`durable_write`, `durable_append`, `durable_create`) for the session, facts, held parts, `records.json` (with its `.bak`), the history line, and the journal; the session keeps `<id>.json.bak`. The full-disk wording of B-5 is not built |
| 4 | Apply: plan inside the lock; fingerprint and `version` required; compare-and-append in the slot store | G-1, G-2, F-1 | high | M | The smallest change that makes apply honest, before the journal. **Built 2026-10-11**: the lock first and the plan inside it, `planFingerprint` from `review`, `expect` on `apply` (`PlanChanged`, 409 in the console), and the pin as a compare-and-append (`record_upload.write_part`: a slot that now holds a file is a collision kept as a held file). The room check for all parts is built (`storage.require_room` on the sum) |
| 5 | The apply journal, staging, resume or roll back | G-3, H-2, I-2, K-3, G-9 | high | L | Builds on 3 and 4; the largest item. **Built 2026-10-11 without a staging area**: the journal (`intent`, `placing`, `part`, `failed`, `library`, `commit`, `queued`, `abort`), pre-allocated pin ids, finish and roll back (`recover`, `--finish`, `--rollback`), an orphan pin adopted on resume, library parts adopted by hash on resume, jobs queued after the commit. Parts are written straight to their final content-addressed names through a temporary file; there is no `split/staging/` copy and no `applying` status (G-6 and G-7 stay open) |
| 6 | Typed `LibraryBusy`; the duplicate check visible; open not misreported | H-6 | high | S | **Built 2026-10-11**: refusal for apply and open, a visible `duplicateCheck` note on the review; the "skip the check" choice is not built |
| 7 | The doctor, read-only first | section 6 | high | M | Class A and B fixes after; class C after the journal exists. **Built 2026-10-11** (CLI only): `jason split --doctor [--fix IDS\|safe --yes --by NAME]`, checks DR-01 to DR-06, DR-08 to DR-12, DR-14, DR-16, DR-18, DR-19; the console's read-only list and DR-07, DR-13, DR-15, DR-17, DR-20 are not built |
| 8 | The render worker: time, memory, queue, per-person bucket, negative cache | M-1 to M-3, L-2, N-5 | high | L | Probe on open first (smallest slice); then render; then cut |
| 9 | Undo apply | J-1 | high | M | Needs 5 and the trash; the library retire dependency |
| 10 | Draft recovery: write-ahead to IndexedDB, three-way merge, one-tab lock, keepalive send | E-3 to E-5, L-7 | high | M | A `splitStore` change and a screen |
| 11 | Apply splits locks (`applying` status); one reader per apply; continue past a bad part | G-6 to G-8 | medium | M | Mostly inside 5 |
| 12 | Purge and sweep locks; age floor; clock high-water mark; trash | K-1, K-2 | medium | S | Cheap and removes a rare catastrophe. **Built 2026-10-11** except the trash: locks, an hour's age floor on a copy no session names, the clock check against `split/sweep.json`, and a share guard (more than half of the drafts, from five). A swept draft is deleted, not moved to `split/trash/` |
| 13 | Re-queue facts on open; name a stopped worker; job timeout limit | D-2, I-1, I-4 | medium | S | |
| 14 | Sanitise on cut | M-4 | medium | M | Decision 6 |
| 15 | Session id exclusive create; open lock | C-4, C-5 | medium | S | **Built 2026-10-11**: 16 hex ids, an `O_EXCL` create with a retry, and the open lock on the file's bytes |
| 16 | Stale test by hash; carry marks to a new file | C-6 | medium | M | |
| 17 | Drive checksum compare; held-copy retention | B-3, B-4 | low | S | |
| 18 | Cache byte counter instead of a tree walk; eviction by window | L-1, L-4 | low | S | A speed item for huge files |
| 19 | Streamed upload, `MAX_CONTENT_LENGTH` | A-2 | low | M | Touches the console's upload |
| 20 | Unknown `deviceMemory` means small on touch | L-6 | low | S | |
| 21 | Review returns first, hashing as a job | F-2 | low | M | |
| 22 | `Sec-Fetch-Site` check on the picture route; error mapper that strips pids and paths | N-4, N-6 | low | S | |

Suggested order: 1, 2, 3, 6, 12, 15 (a week of small, high-value changes); then 4; then 8's probe slice and 13; then 5 with 7 and 11; then 9, 10, 8's rest, 14.

## 10. Decisions needed

| # | Decision | Options | Recommendation |
|---|---|---|---|
| 1 | Is the **render worker required** in production, or optional? | required; optional with in-process fallback; later | **Required** for `render`, `probe`, and `cut`; in-process only under `JASON_SPLIT_RENDER=inprocess` for tests. A fallback that disables the ceiling disables the protection |
| 2 | The **memory ceiling mechanism** on Windows | Job Object via `ctypes`; `pywin32`; polling the child's working set and killing | **Job Object through `ctypes`** (no dependency); polling as a fallback where the Job Object cannot be created |
| 3 | **Cache lifetime for pictures of a library or Drive file** | immutable for a year (today); revalidate each time; five minutes | **`private, no-cache`** for a library or Drive source (one conditional request per cell, answered `304` after the access check); keep `immutable` for an upload from this computer, where the session owns the bytes. Measure the request cost at 3,000 pages first |
| 4 | Does **undo apply** need the library's **retire** act? | add `jason library --retire ID` first; refuse library parts in undo until it exists | **Refuse library parts** in the first release of undo, with the document's id in the message; build the retire act when the library's owner wants it |
| 5 | **Whose change does undo undo** when two people edit one draft? | the shared stack; the person's own last change; ask | **The person's own last change**, with the stack shared for display only; ask when it would conflict |
| 6 | **Sanitise on cut**: on by default? | on; off; ask in the review | **On**, with the count shown in the review and an administrator-only switch to turn it off per apply. It changes a part's bytes, so the "same pages, same bytes" promise reads "same pages, same sanitised bytes" |
| 7 | **Two-person approval for unapply** | same as apply; officer only; none | Follow whatever the board adopts for apply; until then, **the applier within 72 hours, an officer after** |
| 8 | **Retention of the trash and of an applied session's copy** | 7/14/30 days | **14 days** for both (`split.trash_days`, `split.applied_copy_days`), a registry row each |
| 9 | **Finish an unfinished apply without asking again**? | finish on the person's next open; always ask; finish by a worker | **Ask once** (the prompt of 5.4); never a background job: the intent is the confirmation, the *act* of resuming is a person's |
| 10 | **Fail-open or fail-closed when the library cannot be read** for the duplicate check | block until read; skip with a recorded choice | **Block**, with *Skip the duplicate check* as a recorded choice (H-6) |
| 11 | Should the **stale** state stop viewing as well as applying? | stop all; stop apply only | **Stop apply only**; the copy is the person's evidence of what they marked |
| 12 | **Rate defaults** | 300 / 600 / 1,200 renders a minute | **600**, from a scroll of 40 pictures a second at the extreme; adjust on a measured session |

## 11. Lessons and procedure steps to add

For the person who owns `lessons.py` and `procedures.py` (not edited here). Each names the guard that would make it fixed; none is fixed yet, so all start **open**.

| Lesson (area `split`) | Guard it needs | Procedure step |
|---|---|---|
| A confidential file's page text left through the session payload while only its pictures were guarded | the mask function and the canary test (backlog 1) | in the splitter's SOP, "before a release, run the canary test over every payload" |
| A flag read from a database that can be busy must fail closed | typed `LibraryBusy`, stricter-of rule (backlog 2, 6) | the SOP for any new "is it confidential" reader |
| A write that is atomic is not durable | `durable_write` (backlog 3) | the code review checklist: no bare `os.replace` for a store |
| A multi-store write needs an intent, an idempotency key, and a place to resume | the apply journal (backlog 5) | the SOP for an apply that spans stores |
| An untrusted parser belongs in a process that can be killed | the render worker (backlog 8) | the SOP for adding any new reader of a file a person gives |
| A background job that is never retried needs a visible "queued, no worker" | backlog 13 | the SOP for any command that queues a job |

## 12. How this joins the documents

- [pdf-splitter.md](pdf-splitter.md): sections 3.3 (the eviction sentence, L-1), 6.1 ("atomic": G-3, G-4), 8 (the confidentiality sentence, N-1, N-2), and 9.4 (the sweep, K-2) are the ones this page asks to change when the work lands; the status lines there are not edited here.
- [record-intake.md](record-intake.md): the pin, unpin, and held-copy language that undo apply reuses; the compare-and-append in `write_part` (G-2) fixes `split` as well as the splitter.
- [google-picker.md](google-picker.md): held-copy retention (B-4) is its open decision 1.
- [instance-limits.md](instance-limits.md): the new rows (`split.render_workers`, `split.render_timeout_seconds`, `split.render_memory_mb`, `split.render_max_pixels`, `split.render_queue_max`, `split.render_requests_per_minute`, `split.trash_days`, `split.applied_copy_days`, `split.unapply_hours`, `job.timeout_seconds`, `jobs.queue_depth`, `pick.held_days`) each need their documented line before their registry row.
- [pdf-splitter-client-side.md](pdf-splitter-client-side.md): the browser-side options in 8.4 and the recovery store in section 7.
- [console/security-and-privacy.md](console/security-and-privacy.md): the confidential masking rule that N-1 and N-3 make testable.
