# Plan: base templates rendered per profile

Status: **phases 1-4 done for the letter templates** (October 2, 2026); the rest is the plan. The goal is to put the effort into one set of general templates (letters, notices, forms, packets) written for any California common interest development. A profile ([profiles.md](profiles.md)) then supplies its identity, letterhead, governing-document citations, and values, and jason *generates* that association's versions. A community-specific copy is an output, never a hand-edited source.

## What exists today

jason already has most of the machinery. What is missing is the layer between the template and the profile.

- **Five template forms:**
  1. Python block bodies (`BODIES` in `jason.community.templates`: letterhead letter, hearing notice, decision notice, agenda).
  2. Drive template Docs built from those bodies, whose ids are pasted into the profile.
  3. Markdown and HTML packet parts in the profile's `packet_templates/` folder: the annual budget report (5300), the policy statement (5310), the 4041 owner-information cover, the flood notice, and the master insurance notice.
  4. `FormTemplate` definitions for the 4041 owner-information form, the IDR request, and the records request. Each renders to a Google Form, paper, a fillable PDF, and a PayHOA form.
  5. Markdown drafts in `data/drafts/`, which are not checked in. One source becomes an email, a letterhead Doc, and a PDF.
- **One token syntax and several special forms.**
  - `{UPPER_SNAKE}` is jason's fill at build time.
  - `[UPPER FIELD]` is left for a person.
  - Lower-case `{first name}` and `{unit address}` are PayHOA's per-recipient merge. Only those two are confirmed. PayHOA fills nothing else, and nothing in a PDF, including a Mailroom letter.
  - `{QR:KEY}`, `{HELP:key}`, and `{HELP_STEPS:key}` are links.
- **Packet values come in layers:** the packet's standing values, then computed ones (fiscal year, unit count, mailing date), then statute passages, then a per-run `values.json`.
- **Statute structure is already data.**
  - `NoticeRule` (4040 individual and 4045 general delivery).
  - `Packet`, `Part`, and `PartSource`.
  - `statutory_terms` (deadlines tied to the text).
  - The models' checklists. For example, the eight pre-lien notice elements of 5660 are in `models/legal_collections.py`.

**What blocks reuse:**

1. **No profile-to-token layer.** The association's name, corporate name, mailing address, official email, website, designated recipient, signature block, time zone, meeting platform, and management arrangement are hand-typed into packet values, read from profile module constants (`spec_module("templates")`), or passed as CLI flags.
2. **The "generic" bodies contain one association's text.** `community/templates.py` signs the closing with the association's name. The hearing notice cites that association's bylaws and declaration sections. `tasks/board_items.py` prints its name and a bylaws section. The HTML packet parts sign with the name, and the insurance notice hardcodes the flood zone, building count, and deductibles.
3. **The letterhead is three unrelated things:**
   - a Drive Doc that is copied (its footer word `LETTERHEAD` is swapped for the address);
   - a logo PNG at `data/brand/letterhead-logo.png` that every profile shares;
   - email constants.
4. **Base files live in the profile.** `tasks/packets.py` hardcodes `mystique/packet_templates` whatever the active profile is.
5. **Generated Doc ids are pasted into Python.** The policy that "the Doc is the original" after the first build conflicts with "the base is the source".
6. **One notice, three texts.** The hearing notice exists as `BODIES`, `zoom/models.notice_text`, and `drafts.hearing_draft`. The decision notice is the same.
7. **PayHOA wording is fixed in generic code.** The form-return preamble and QR labels say "PayHOA".

## The catalog: what a California association must send

Statute research (Civil Code 4000-6150, against the exported statute pages) found 56 kinds of documents. They group as follows; Must = statutory, Custom = customary.

| Group | Templates | Have | Missing |
|---|---|---|---|
| Annual disclosures (Must) | budget report Part A, pro forma budget, reserve summary and the 5570 form, insurance summary, FHA/VA statements, 4528 charges form, policy statement Part B, collection policy with the 5730 notice, fine schedule, ADR summary | the packet; Part A and Part B as tokenized Markdown; insurance, FHA, and VA generated | the 5570 form and the 4528 form are rendered from data, not pulled in as library PDFs; the collection policy and fine schedule as bases |
| Owner contact (Must) | 4041 owner information and delivery preference | form, cover letter, packet, sends | — |
| Meetings (Must) | board notice and agenda (4920), executive-session-only notice (2 days), emergency notice, minutes (4950), member meeting notice | agenda template and generator, minutes sections | the executive-session-only, emergency, and member meeting notices |
| Rules (Must) | proposed rule notice (4360(a)), adoption notice (4360(c)) | generators (`rule_change.py`) | move them onto the base system |
| Enforcement (Must and Custom) | courtesy or violation notice, notice of hearing (5855), notice of decision (5855(f)) | hearing and decision letters | the courtesy notice; one hearing text instead of three |
| Collections (Must) | assessment increase / special assessment (5605-5615), pre-lien notice (5660, built from its 8-element checklist), payment-plan reply (5665), lien release or rescission (5685/5690) | delivery rules and checklists only | **all bodies** |
| Elections (Must) | nomination procedure (5115(a)), pre-ballot notice (5115(b)), acclamation notices (5103), results (5120(b)) | terms and readers only | **all bodies** (jason drafts notices; the inspector runs the election) |
| Member requests (Must) | records request reply with cost estimate and withholding basis (5205-5215), architectural decision (4765), IDR written resolution (5915), ADR request for resolution (5935) | the intake forms | **the board's replies** |
| Resale (Must) | escrow/resale package and the 4528 estimate (4525-4530) | reader, brief, deadline clock | **the package** |
| Occasional (Must when it occurs) | insurance change (5810), litigation-reserve use (5520), pest relocation (4785), construction-defect notices (6150/6100), reserve-transfer finding (5515) | insurance notices | the rest |
| Customary | welcome letter, general letter, board resolution, legal hold notice | letterhead letter, legal hold notices | welcome letter, resolution |

Delivery rules (`NoticeRule`) exist for ten notices. Elections, the 5305 reviewed statement, the records reply, the architectural decision, the 4785 relocation, and 6150 have none yet.

**PayHOA's side.** Only broadcast email templates are reachable through the API: list, save, render a sample, and send. There are eight of them today. Of those, the 5810 insurance notices, the 5310 annual disclosures, and the meeting notice are general bases in all but their facts. Violation header, message, and footer templates, statement and reminder emails, and ballots exist only in PayHOA's own screens, and no API calls for them have been captured. A Mailroom letter is a PDF that jason renders and merges in full.

## Design

### 1. Base templates live in jason

`src/jason/templates/` holds one file per template. Each is a Markdown or HTML body (the dialect `docs_markdown` and `markdown_html` already read) with front matter:

```yaml
key: notice-of-hearing
title: Notice of Hearing
kind: letter                # letter | notice | form | packet-part | email
authority: [CIV 5855, CIV 4935(b), CIV 5850]
notice: hearing             # the NoticeRule kind that delivers it
tokens: {required: [HEARING_DATE, VIOLATION], optional: [CURE]}
version: 1
```

A base names no association, statute figure, or governing-document section of its own. Where a sentence cites the association's documents, it uses a citation token (below). Bases are checked by the boundary test like the general docs.

### 2. The profile supplies identity, letterhead, citations, and policy

New `Community` methods, each with an empty default:

- **`identity()`** returns an `Identity` record:
  - name, corporate name;
  - mailing address lines, the unit city line;
  - official email, website, posting location;
  - designated recipient;
  - signature block ("Board of Directors, {name}");
  - time zone, meeting platform, management;
  - the owner portal and its help articles.
- **`letterhead()`** returns a `LetterheadSpec` record:
  - an optional Doc id;
  - a logo path or URL kept in the profile's `assets/`;
  - the name line, font, footer, and continuation style.

  A profile with no Doc gets a generated header from its name and logo. One record feeds `markdown_doc`, `build_template`, the packet's `page_html`, `form_pdf`, and the email `Letterhead`.
- **`citations()`** maps a purpose to the association's own governing-document section. Examples of purposes: `hearing-procedure`, `enforcement-policy`, `fine-schedule`, `architectural-review`, `election-rules`, `agenda-order`. A missing purpose renders the general wording ("the association's governing documents") rather than a guess.
- **`template_overrides()`** names a base the profile replaces or extends by key, with the reason. An override is the exception and is listed in `mystique/docs/`.
- **`software()`** names the management software (`payhoa`) and selects the return instructions and help links, so a base says "your owner portal" and the profile says which portal.

### 3. One token namespace and one resolver

Values resolve in layers, later winning:

1. `profile.*` from `identity()`;
2. `cite.*` from `citations()`;
3. computed (`year.*`, unit count, dates);
4. statute passages;
5. the packet's standing values;
6. the run's values (the recipient, the hearing, the matter).

Today's names stay as aliases, so `{FISCAL_YEAR}` keeps working. The existing open-token check becomes a lint: it lists each base's tokens that no layer supplies for a given profile. PayHOA's lower-case merge fields and `[FIELDS]` pass through untouched.

### 4. Renderers stay as they are

A resolved template renders through the existing writers:

- Doc on the letterhead (`letters.markdown_doc` / `fill_letter`);
- PDF (packet `page_html`);
- email HTML (`markdown_html`, with PayHOA placeholders kept);
- Gmail draft (`drafts`);
- the PayHOA broadcast Doc mirror (`template_docs`);
- paper or fillable form (`form_render`).

The hearing notice's three texts collapse into one base rendered three ways.

### 5. Generation, drift, and which copy wins

`jason templates --generate` renders every base for the active profile:

- Docs go into the profile's Templates folder.
- PDFs and email HTML go under `data/<profile>/templates/`.
- Each output is recorded in `data/<profile>/templates.json` (base key, base version, values hash, Doc id, output hash), not in Python.

**The base wins.** Regenerating overwrites a generated Doc, unless the Doc was edited since it was generated. Then jason reports the drift, the same way `template_docs` reports conflicts today, and a person chooses one of two things:

- fold the edit into the base, if it applies to any association;
- record it as a profile override, if it applies to this association only.

This replaces today's rule that "the Doc is the original" for templates. A filled letter is still its own document once sent.

### 6. PayHOA templates are outputs too

A base of kind `email` can be saved to a PayHOA broadcast template (`--save-template`, which exists) and kept in sync through the Doc mirror. Violation and statement templates stay in PayHOA's screens until their calls are captured. Capturing them is a HAR task, listed below.

## Phases

Each phase is one reviewable change. Stop after each one.

1. **Identity and letterhead (done).** `jason.community.identity` holds `Identity`, `LetterheadSpec`, and `DriveHome`; `Community.identity()`, `letterhead()`, and `drive_home()` default to the name alone, and `email_letterhead()` derives from `letterhead()`. The commands read the folders, letterhead Doc, footer, logo, and city line through them, and no general code reads `spec_module("templates")` (a test holds it). The logo still lives at `data/brand/letterhead-logo.png` until a profile sets its own. Originally:
   - Add `Identity`, `LetterheadSpec`, and `Community.identity()` / `letterhead()`, with the profile's values moved out of `mystique/templates.py` constants and `packets.py` standing values.
   - Move the logo into the profile's `assets/`.
   - Feed the letterhead record to the five consumers.
   - Retire the `spec_module("templates")` reads (phase 2 of [profiles.md](profiles.md)).
2. **The resolver and the lint (done).** `jason.community.template_values`: `Layer`, `resolve` (later layers win; an empty value never overrides), `profile_values` (identity, then `{CITE_<PURPOSE>}` from `Community.citations()`, keyed by `CitationPurpose`, with general wording for a purpose the profile does not cite). Letters take the profile's values as `fill_letter(defaults=...)` (not reported as ignored); packets take them as their first layer. `jason templates --lint` sorts each template's tokens into profile, general wording, and left for the letter. Today every letter token is the letter's own, because the bodies still carry the first profile's text; phase 3 tokenizes them. Originally: Add the layered token resolver and the `profile.*` and `cite.*` namespaces with aliases, plus `jason templates --lint` (tokens no layer supplies, by base and profile).
3. **First bases from what exists (mostly done).**
   - Done:
     - The letter `BODIES` name no association. `{ASSOCIATION_NAME}`, `{SIGNER}`, `{TIME_ZONE}`, `{MEETING_PLATFORM}`, and `{CITE_CONTINUING_FINES}` / `{CITE_HEARING_EVIDENCE}` / `{CITE_FINES_NOT_LIENS}` are filled by the profile. The first profile's letters render word for word as before (checked against the old text).
     - The budget report, the policy statement, and the flood notice are base files in `src/jason/templates/packets/`. The budget report's "where documents are online" is the `{DOCUMENTS_ONLINE}` identity field.
     - The packet builder reads the profile's `packet_templates/` first, then the base (`tasks.packets.template_file`).
     - The board's draft agenda takes the name and the quorum citation from the profile.
     - The Markdown hearing draft (`zoom.models.notice_text`) renders the same body as the notice Doc (`templates.body_markdown`). The email that sends it is a cover message, not a copy, and stays.
     - The base folder is in the boundary test.
     - **The 5810 insurance notice is generated, not edited.** `tasks/insurance_notice.py` compares each annual-budget-report policy's term in force with the term before it. The changes 5810 names are significant: a reduced limit, a higher deductible, and a lapse the record states (a policy marked canceled or not renewed). Other changes (a raised limit, a new insurer) are listed but do not by themselves call for the notice.
       - The base `insurance-change-notice.html` lists the changes and the policies, and cites `{CITE_OWNER_INSURANCE}` for what owners must carry.
       - Coverage the association does not carry is `Community.coverages_not_carried()`. The insurance summary no longer hardcodes the earthquake line.
       - A term missing from the records is a gap ("read the renewed declarations"), never a lapse. The first run on real records found the 2026-27 package not yet read, and would otherwise have reported four false lapses.
       - When nothing on file is a named change, the gaps say so, and sending is the board's call.
     - **Past notices stay as sent.** The 2026-27 renewal letter (`packet_templates/master-insurance-notice.html`) is the first profile's record and is not tokenized. It is an example of the content a generated notice should reach, not a template.
   - Left:
     - The first profile's annual packet still encloses the sent 2026-27 letter as its insurance notice part. Switching that part to `letter:insurance-change-notice.html` is the board's decision about what owners receive. The packet planner already fills the new notice's values when a packet names it.
     - The owner-information cover names PayHOA; it waits for `software()`.

**Improvements found while doing phase 3 (to schedule):**

- **The policy record keeps one deductible per term.** The 2026 notice's trigger, the general liability deductible rising while the property deductible stayed, cannot be seen in it. The `jason policies` model needs a deductible per coverage (property, liability, crime, D&O) so the 5810 check can see that kind of change.
- **A lapse needs evidence.** Policies have no status. Reading carrier notices of cancellation and nonrenewal (the mail sort already finds them, `docs/mail.md`) into a policy status would let 5810's lapse and nonrenewal duties ("immediately notify ... if replacement coverage will not be in effect") be checked, not just the changes.
- **The sent letter's other content.** These parts of the 2026-27 letter can be generated from profile data:
  - the walls-in coverage basis;
  - lender certificate instructions;
  - the recommended loss assessment limit;
  - flood zone context.

  They need profile fields, such as `insurance_guidance()`. It would hold the coverage basis, the certificate service, and the recommended owner limits, each with its source document.
   - **A person refreshes the Drive template Docs.** They were built from the old bodies, so they still read the same as the filled text. `jason templates --rewrite <kind> --yes` rewrites each from the new body. Until then, filling works as before.
4. **Generation and drift (done for the letter templates).** `jason.tasks.template_gen` compares each base body's hash and its Doc's text hash with what jason last wrote. The record is in `data/templates/<profile>.json`.
   - **The actions:**
     - create, when there is no Doc;
     - adopt, for a Doc the profile names that was built before the bases; the plan says whether it still reads as built or may have been edited;
     - update, when the base changed;
     - edited, when a person changed the Doc; it is left alone, and the person either folds the edit into the base or keeps it as the profile's own;
     - conflict, when both changed;
     - unchanged.
   - **The command:** `jason templates --generate` prints the plan, reading Drive only. `--yes` writes and records the ids.
   - **Filling uses the generated Doc.** The hearing, letter, and agenda commands fill the generated Doc when one is recorded (`template_gen.template_for`).
   - **First run on the first profile:** all four Docs are adopt steps, "unchanged since" they were built.
   - **Left:**
     - The profile's pasted Doc ids stay as the fallback until a person runs `--generate --yes`.
     - The packet Markdown Docs (budget report, policy statement) still use `jason packet --make-templates` and the ids in `mystique/packets.py`; they come next.
5. **New bases, by statutory weight:**
   - collections: the assessment increase notice, the pre-lien notice (rendered from the 5660 checklist), the payment-plan reply, and lien release;
   - the replies to members: the records request, the architectural decision, and the IDR resolution;
   - election notices;
   - the escrow/resale package and the 4528 form;
   - the 5570 form computed from reserve data;
   - the rest of the occasional notices.

   Each new base needs a `NoticeRule` if it is delivered.
6. **PayHOA captures (HAR tasks).** Capture the violation template endpoints and their fields, the composer's full field menu, creating a new email template, and mailing invoices, violations, and ballots.

## Guardrails

- **jason drafts; a person sends.** A generated notice is a draft until a person sends it, as today (`--send --yes`, the Mailroom rules, and Gmail drafts that never send).
- **Statutory text is not paraphrased.** A form the statute gives verbatim (5570, the 5730 notice, the FHA/VA statements, 4528) is carried word for word from the exported statute text, with its section and the session it was read from.
- **No legal advice in a base.** The board and counsel decide; a base states what the statute requires a notice to contain.
- **Fake examples only** in bases, front matter, and tests ("123 Main St", "Example Commons Owners Association").
- **Start small.** Phases 1-3 first, using the templates that already exist. Write no new bases before the resolver and the generation step work for the first profile and the planned example profile ([sample-profile-plan.md](sample-profile-plan.md)).
