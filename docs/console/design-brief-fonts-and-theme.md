# Decision memo: web fonts and theme presets in the console

Written 2026-10-10. The design's sixth cut ([reconciliation-sixth-cut.md](reconciliation-sixth-cut.md), section 5) offers theme presets that use **six web fonts from a font service**, and the question it left is whether the console may load them or the presets are limited to system fonts. This memo gives the options, what each costs in privacy, performance, and licensing, a checklist, and a recommendation. It is general: it names no association, and the examples are made up. The decision is the user's.

## 1. What is true today

The console already makes one third-party font request, and the answer to this memo should account for it.

- `ui/src/styles.css` begins with an `@import` of a stylesheet from a font service for one serif family, used for what is read, with Georgia as the fallback while it loads or offline. Every viewer's browser asks that service for the stylesheet, and then for the font files it names.
- `GET /api/theme` may give the active profile's own font stylesheet URL (`fontUrl`), and `ui/src/lib/theme.ts` adds it as a `<link rel="stylesheet">` when a theme is found. A profile that sets one makes the same kind of request.
- [security-and-privacy.md](security-and-privacy.md#outside-resources) records both as exceptions ("None of them sends member data: they load a library, a font, or a public frame") and says a Content-Security-Policy for the bundle would name exactly these origins. [mvp.md](mvp.md) open decision 9 asks whether to self-host the font and Mermaid and set that policy; its recommendation is yes, and it has not been taken.
- The server serves the built bundle from `ui/dist`: files under `assets/` are content-hashed and sent `public, max-age=31536000, immutable`; the page itself is `no-cache, no-store` because it carries the process's token. There is no CSP header on the bundle today.

So the question is not "whether to start loading fonts from a service" but "whether to stop, and what to do with six more".

## 2. The theme presets in short

A theme preset is a set of design tokens (colors by scheme, a surface layer, and a font stack) the profile can choose. The tokens are data: `themeCss` writes them as custom properties scoped to the community. Colors and radii cost nothing to serve. Only the font family needs a file, and six presets that each want a different family means up to six families, each in several weights and styles, each a licensed work.

## 3. Options

### A. Keep loading from the font service

What it is: the presets name families by the service's stylesheet URL, as `fontUrl` does today.

- Privacy: each viewer's browser contacts a third party on first use of each family. That request carries the viewer's IP address, the page that asked (subject to the referrer policy), and the browser's headers. It carries no member data from jason, but it tells the service that this address opened this console. Under the privacy laws that treat an IP address as personal data (GDPR-type regimes; California's CCPA/CPRA treats an IP address as a possible identifier), a disclosure to a third party is something the association would have to be able to describe, and some courts and regulators outside California have found embedding a font service without consent unlawful. For a board-only console on a private network the exposure is small; for the owners' pages it is larger.
- Performance: one extra DNS lookup, TLS handshake, and stylesheet fetch before text can settle; a flash of fallback text or of invisible text if not handled. Offline or behind a filtering network, the fonts do not load and the fallback shows.
- License: the service hosts families under open licenses; the license obligations are the font's own (typically the SIL Open Font License), and the service handles distribution.
- Operations: nothing to ship; a service outage or a change by the service changes the console.
- Verdict: simplest, and the weakest on privacy. Six presets multiplies the requests.

### B. Self-host the licensed files under the console's static folder

What it is: ship the font files with the bundle (built from `ui/`), served by jason's own server from `assets/`, with `@font-face` rules the build emits, and no request leaves the viewer's machine.

- Privacy: no third-party request. This also allows a Content-Security-Policy that names no font origin (`font-src 'self'`), which is the policy the earlier open decision asks for. It matches the console's stance that a board's browser contacts jason and the public frames a screen names, and nothing else.
- Performance: the files come from the same origin on the same connection. They are content-hashed under `assets/`, so they get `public, max-age=31536000, immutable` already, and a font is downloaded once per version. Use WOFF2 only, subset to the scripts the console needs (Latin and Latin Extended), and a variable font where the family has one. Preload only the face used above the fold. Use `font-display: swap` (or `optional` for a decorative face) so text is never invisible. A subset text face is typically tens of kilobytes; the cost grows with the number of families, weights, and italics, so ship only the presets' faces and load a preset's files only when the community's theme names that preset.
- License: this option makes the association the distributor of the font files, so the license matters (checklist in section 5). Open licenses allow bundling; commercial licenses often limit web embedding by page views or domains, so the licensed set is a deliberate list.
- Operations: the build owns the files. A new preset is a new commit with its license file; the lockfile of fonts is part of review. Updating a family is a rebuild.
- Verdict: best on privacy and reliability; more work once, and a license duty that has to be kept.

### C. System font stacks only

What it is: presets choose among stacks of fonts already on the viewer's machine (a humanist sans, a neutral grotesque, a transitional serif, a monospace, a slab-like serif, a rounded sans) by name with sensible fallbacks, and load nothing.

- Privacy: none to discuss. Fully offline.
- Performance: the best; no download, no layout shift from a swap.
- License: no files, no duty.
- Cost: presets look different on different operating systems; the six distinct faces the design drew become six stacks that resolve differently on each system. Georgia as the current fallback is such a stack. A preset's character is weaker, and a printed or exported page does not match the screen.
- Verdict: the safe floor. Every option below includes it as the fallback.

### D. Per-community optional fonts, under Limits

What it is: the default is C (system stacks) or B (a small self-hosted set). A community's administrator may turn on additional preset families in Setup, as a **switch** in the limits registry (a switch only turns a convenience or a cost on or off; it never turns a safety check off), or the instance operator may allow them for every community. The setting is a `switch` row, for example `theme.extra_fonts`, with a `why` ("Extra font files add download size and need a license check") and a `whenHit`. The preset picker shows only what the setting allows.

- Privacy: if the extra families are self-hosted (B), nothing leaves the machine whether the switch is on or off. If the switch ever enabled a third-party service, the setting would have to say so in words and be off by default, and that is the one form of this option this memo does not recommend.
- Performance: a community that does not turn it on pays nothing; one that does downloads only its own preset's files.
- License: the shipped set is the same under B; the switch controls exposure, not the license.
- Cost: one more row in the registry, the preset picker, and a test; the limit screens already draw the switch. It does not solve the license or the privacy question on its own; it narrows who pays the cost.
- Verdict: a good way to ship B without making every community carry six families; weak as a replacement for B.

## 4. Privacy implications, in one place

- **No third-party request from a board's browser.** After B, C, or D-over-B, a viewer's browser asks only jason's server, and the public frames (the association's published calendar, a Zoom share page, a map) a screen names and a person clicks. That is the console's rule and is the position [security-and-privacy.md](security-and-privacy.md) already takes everywhere else.
- **GDPR- and CCPA-type concerns.** An IP address sent to a font service is the common example regulators and courts have used for "personal data disclosed to a third party without a legal basis" and for the duty to tell people about third-party processors. An association in California is under the CCPA/CPRA only if it meets that law's thresholds, and many do not; owners or board members elsewhere (for example a part-time resident abroad) can still bring a GDPR-type claim. The memo does not say the current request is unlawful, and it is not legal advice. It says self-hosting removes the question, and counsel may be asked if the board prefers to keep a service.
- **Referrer and header leakage.** A stylesheet request names the page that asked unless a referrer policy removes it. Self-hosting avoids the leak without relying on that setting.
- **Cookies and fingerprints.** A font service's response may set no cookies, but a request is still a fingerprinting signal; the board's rule of "no outside script or identifier unless a person clicks" is easier to keep with no request.
- **A theme file is data from the profile.** `fontUrl` takes a URL from a profile; if the console moves to B, the field should stop accepting an outside URL (or ignore it) so a profile cannot reintroduce the request. The font set is chosen from a closed list of presets, and a preset is a symbol, not a free string, as the project prefers elsewhere.

## 5. License checklist for any font file jason ships

Before a family enters the repository:

1. **Name the license** and record it with the file (an `OFL.txt` or equivalent beside the files, and a line in the third-party notices).
2. **Web embedding is allowed.** The license permits self-hosting and serving the file to the public over the web; check any limit by page views, domains, or number of users.
3. **Redistribution and modification are allowed,** because subsetting and converting to WOFF2 is a modification. Some licenses forbid a reserved name when modified: if the license has a reserved font name, the subset must be renamed or the unmodified file shipped.
4. **Attribution and notice duties** are met where the license requires them.
5. **No fee that scales** (per-seat, per-page-view, per-site) that the association cannot predict; a one-time purchase is recorded with its receipt, not in the repository.
6. **Provenance:** the source URL, the version, the date, and a checksum of the original and of the subset, in a file beside the font.
7. **Glyph coverage:** the Latin and Latin Extended ranges the console uses, tabular figures (the console uses them for numbers), and the currency and typographic marks it shows; otherwise the fallback shows for those marks.
8. **Style set:** only the weights and styles a preset uses; no unused italics or optical sizes.
9. **No script, font-loader library, or tracker** comes with the family.
10. **A fallback stack** is declared for every family, and the layout works with the fallback (the console's tabular figures and widths do not depend on the web font).
11. **Cache headers:** under `assets/` so the hashed filename gets the long immutable cache, and a changed file gets a new name.
12. **Review:** a font is added by a pull request that shows the license file and the size, like any dependency.

## 6. Performance budget

- Load no font above the fold except the one the first paint needs. Use `font-display: swap` for text, with a fallback of similar metrics (a size-adjusted fallback face) to avoid layout shift.
- Cap the shipped set by size: a suggested ceiling of about 150 KB of font files for the default theme, and the same again for each extra preset that a community turns on. Measure it in the build and fail the build above the cap.
- A preset that the community has not chosen downloads nothing.
- Pages served to a phone on a weak connection show the fallback first; the content never waits for a font.

## 7. Recommendation

1. **Take mvp.md open decision 9 for fonts: self-host.** Replace the current `@import` with a self-hosted face (option B) and add `font-src 'self'` to the Content-Security-Policy the earlier decision proposes. This removes the one outside request the console makes today and answers the privacy question for the presets at once.
2. **Ship system stacks as the floor (C)** and as the fallback of every preset, so a preset degrades to something close to its look.
3. **Ship the presets as tokens plus a closed list of self-hosted font faces (B), loaded only for the community that chooses one.** Keep the shipped set small (the one serif the console already uses, plus a sans and a mono if the presets need them); do not ship six families because six were drawn. Ask the design which three or four carry the presets' character and draw the rest as stacks.
4. **Add the optional-fonts switch under Limits (D) only if more than a few extra families are shipped.** A single `switch` row keeps a community from carrying faces it does not use. If the extra set stays small, skip the row.
5. **Retire `fontUrl` as a free URL from a profile:** keep the field for compatibility, ignore an outside URL, and warn in the profile check. A preset is chosen by key.
6. **Do the license check (section 5) before any family is committed,** and keep the license files with the fonts.
7. **Leave Mermaid and the other exceptions to their own decisions.** This memo covers fonts and theme presets only.

## 8. Decisions for the user

1. Take the recommendation (self-host, system stacks as the floor), or keep the font service for the one family and limit presets to system stacks?
2. Which presets, if any, justify a shipped family, and which are drawn as stacks? (The design chooses; the build ships what the license check clears.)
3. Is the Content-Security-Policy to be set now with `font-src 'self'`, or after Mermaid is also self-hosted?
4. Does the board want counsel to read the privacy point before the change, or is removing the request enough?
5. Whether `fontUrl` stays as a profile field (ignored when it points outside) or is removed.
6. Whether the optional-fonts switch under Limits is wanted (section 3, option D).

## 9. What to ask the design

- Which faces carry each preset's character, and which can be a stack without losing it.
- Draw each preset once with its web face and once with its fallback stack, at the console's sizes, with tabular figures and the long numbers it shows, so the fallback is a visible, acceptable look.
- Name the weights and styles each preset needs, so the build ships only those.
- Keep sample names plainly fake and rename any preset that carries an association's name before it enters the repository.

## 10. Where it goes if taken

| Part | File |
|---|---|
| The font and theme loading | `ui/src/styles.css`, `ui/src/lib/theme.ts`, `ui/index.html`, the Vite build |
| The bundle's headers and CSP | `src/jason/web/app.py` |
| The theme loader | `GET /api/theme` (`src/jason/web/extra/community_record.py`) |
| The record of the exceptions | [security-and-privacy.md](security-and-privacy.md#outside-resources), [mvp.md](mvp.md) open decision 9 |
| An optional-fonts switch | `src/jason/limits.py` registry; shown by [design-brief-limits.md](design-brief-limits.md) |
