# Split document

`#/setup/split` (drafts and entry points), `#/setup/split/<id>` (one draft), `#/setup/split/demo` (a made-up draft with no server) in Setup · built (phases 2 and 3 of [../../pdf-splitter.md](../../pdf-splitter.md), except the model pass and the joins) · loaders `GET /api/split-sessions`, `GET /api/split-session?id=`, pictures `GET /api/split/thumb?id=&page=&size=`, writer `POST /api/write/split/<id or new>` (`jason.web.extra.split`, `jason.web.split`) · design: [../../pdf-splitter.md](../../pdf-splitter.md), sections 3, 5, 7 and 9.4

## In the console

`SplitView` (`ui/src/views/SplitView.tsx`) reads the hash: no id is the start screen, `demo` the demo, anything else a draft. Board only (officers, managers, administrators); not in `ownerScreens.json`, and the server refuses the owner view. A file's name is never in a route.

- **Start.** Open a PDF from this computer (a file chooser, base64 up to `upload.max_bytes`) or by library id: **Check the file** is the dry run of `open` and shows pages, size and the limit's words; **Open it** keeps a copy and a draft. A Drive file is not taken yet (put it in the library or upload it). Below, the drafts with their status in words (draft, confirmed, applied, stale, declined) and a link to each; a confidential file's label is masked as the server sent it.
- **Views** (`1` to `4`, `V`): **Album** (windowed grid of 200 px pictures with a size slider), **Filmstrip** (the current page large, a strip of 96 px pictures, the slider), **Scroll** (one page at a time, down or across), **List** (the segments and open suggestions, windowed; the phone default). **Compare** opens beside any view: the page, the page before, and the first page of the segment before, with Fit, 800 px and an enlarged zoom.
- **Marking.** Tap or click toggles a page as the first page of a segment; Shift-click selects a range without marking; a long press (touch, 500 ms) or right click or `L` opens the page menu (start, nested start, remove, accept or reject, why, show larger, every Nth page or mark each or merge in a selection, reload the picture); the grip on a start drags it to another page (the grid scrolls at its edge); `[` and `]` move it a page. Page 1 is locked and says why.
- **Suggestions.** Dashed start with "Suggested, High" (a word and dash weight, never colour alone); the rail lists them with their reason; accept, reject, accept all at High, or at Medium or better (one undo step each); never automatic. Show rejected is a toggle.
- **Bulk.** Every Nth page (with the count first), split on blank pages (stay before, stay after, or leave out; the duplex warning when over a quarter are blank), split at page-number restarts, clear all my marks (a confirm).
- **Saving.** A change shows at once and is sent in order with its version. The state is a word in the summary line: saving, saved with the time, offline (marks held on this device, retry, and sent when the browser is back online), not saved after a server error (kept, retry). A server refusal puts the page back and shows the server's words. A 409 shows both copies with **Keep mine**, **Keep theirs**, **Merge boundaries**. Undo and redo are the server's stack.
- **Review.** **Review and split** (enabled once saving has finished) opens the review: counts that must add up, the first page of each part (loaded only while on screen), a title field per part, the pages to leave out (blank pages, a checkbox), collisions and duplicates in words. **Preview the split** is the dry run; the one confirm is labelled "Write N files as NAME". The result lists filled, held, skipped, failed.
- **Keys.** Arrows, Space and Enter, `N` `P`, `A` `X`, `M`, `[` `]`, `L`, `G` or `/`, `V`, `1`-`4`, `+` `-`, `Z` `Shift+Z` `Y` `Ctrl+Z`, `?`, `Esc`, Home, End, Page Up and Down.

## Performance

Cells have a fixed size, so the scroll length is arithmetic (`splitWindow.ts`); only the rows in view plus two screens either side exist (about 30 to 60 cells for a 3,000-page file). No cell holds React state: one set of handlers sits on the grid, a cell is memoised on primitives, and a picture arrives by the loader setting `img.src` (`splitThumbs.ts`), so a load costs no render. The loader asks nearest the view first and ahead of the scroll, holds six requests, aborts a request when its cell leaves, in a fast scroll asks for 96 px only and asks for the rest 120 ms after the scroll settles, and keeps at most 150 tiny, 60 small and 3 large pictures (half on a phone or a device with 2 GB or less), never dropping one on screen. A placeholder is drawn from the page's 16 by 16 facts picture as a BMP data URL, with no canvas. Facts come in chunks of 300 as the window reaches them.

## Try it with no server

`#/setup/split/demo` is a made-up 120-page draft answered from memory (`splitDemo.ts`): the same acts, words and refusals as the server, pictures drawn as SVG, suggestions from the same kinds of signals. `#/setup/split/demo?pages=3000` makes a long one to feel the scrolling. Reload to start over. Nothing is sent anywhere.

## Not built here

The model pass, the joins from the library menu and record slots, slot assignment per part, the vector compare pane, the marquee and pinch gestures, the 1,600 px picture, Drive as a source, "Remove page pictures" (no route), and a live save when two people edit. Section 9 of the design lists them.

## Tests

`ui/src/views/splitwindow.test.ts` (the windowing math on 3,000 pages, the loader's order, aborts, fast mode and budget, segments and the bulk acts) and `ui/src/views/split.test.tsx` (the start screen and its refusals, the route, marking, selecting, keys, the menu and long press, suggestions, views, go to, compare, bulk acts, the review and apply, a 3,000-page grid's live cells and requests, and the queue's conflict, offline, refusal and 5xx paths). Fixtures are made up.
