# The form library: forms built in for a state, forms from a community's documents, and forms a community writes

Status: design (2026-10-05); build step 1 is built (2026-10-05): the mechanism in `src/jason/community/form_library/`, `Community.forms()`, `jason form-library`, and the generic request-to-meet-and-confer and records-request forms as the first California definitions (`records-request`, `idr-request`). Deviations from this page: (1) a recital is a statute citation (`CIV 5205(f)`), read from the shelf by `jason.community.law_text`; a governing-document recital (`ccrs#4.15`) goes through `DiskResolver`, which does not read statutes; (2) the recitals are checked and shown but not yet rendered into a form's preamble (no renderer fills a statute token); (3) a required item may carry `deferred`, a gap the definition names and the check reports without failing the form, so the two moved forms stay as they were while the full forms (build step 2) close the gaps; (4) the handler table is `form_library/handlers.py`, with the process handler `response-clock` standing for `jason respond` until the registry exists; (5) `FormKey` is still the closed set `idr`, `records`, `owner-info`, so a form of step 2 adds a member; (6) a form that fails the check for a recital or a required item is still made (`forms()` leaves out only a form not offered or one with no registered handler or procedure). It layers the forms of [form-templates.md](form-templates.md) so that the ones the law requires are **built into jason once for every community under that law**, the ones a community's documents create are **a standard structure the community fills with its own provisions**, and the rest are **the community's own**. [form-templates/](form-templates/README.md) holds each form's design; this page is how they are held, combined, kept current, and checked.

## Why layers

Three kinds of form differ in who owns the words:

| Kind | Who owns the words | What changes between communities | What must not change |
|---|---|---|---|
| **State** | the law (the Act, the Civil Code, the Government Code) | the name, the return address, the contacts, the fee schedule, the letterhead | what the law says the form must carry, and the law's clocks |
| **Family** | a common structure, with the documents' provisions in it | which section creates it, its clocks, its decider, what it may ask | what the law bars it from asking or requires it to say |
| **Custom** | the community | everything | nothing in the law reaches it; it has a handler chosen when it is made |

If the law's forms live in each community's profile, every association copies them, and each copy drifts (the records form recites a subdivision the section has since moved). Built in, a form is fixed once when the law changes, tested once, and every community gets the fix at its next campaign. That is the same rule that governs the code: nothing about one association goes in a form the law wrote.

## The jurisdiction chain

A **jurisdiction** is a body of law with its forms, notices, and clocks. A community declares an ordered chain, most general first. Today every profile is `("US", "CA")`:

- **US:** forms that federal law reaches in every state (the reasonable accommodation request; fair housing).
- **CA:** the Davis-Stirling Act and the related codes the authorities shelf holds. The forms in [form-templates.md](form-templates.md) are this pack.
- **a locality** (optional, later): a county or city (a permit a local agency requires for a change the association approves).

A pack is a package of definitions and nothing else: `jason.community.form_library.us`, `.ca`. Another state is another pack; no pack imports another. The shelf of statutes, the notice catalog, and the form library are the same jurisdiction's three parts, so they are versioned and updated together.

## The forms in each tier

**State forms** (the law requires the association to accept, or prescribes what the form carries): the nineteen in [form-templates.md](form-templates.md), by their keys (`records-request`, `adr-request`, `resale-documents`, `payment-plan`, `architectural-application`, `ev-charger`, `delivery-change`, `secondary-address`, `candidate-nomination`, and the rest). Each carries its `authority` and its `required_content`; a profile cannot remove either.

**Family forms** (the documents create the request; the structure is common): `rental-application` (with the exception and rehearing requests), `variance-request`, `registration`, `permit`, and the architectural application where the documents require approval. A family form has **slots for the documents' provisions**: the section that creates it, the decider, each clock, what the section requires on the form, and what the section forbids asking. A community cannot offer it until it binds those slots; a form unbound is "not offered", and the library says which slot is missing.

**Custom forms** (the community's own: a survey, a sign-up, an RSVP): no authority; the handler is chosen when the form is made from the fixed list of general handlers ([arrivals-design.md](arrivals-design.md#the-handler-is-chosen-when-the-form-is-made)). A community may also offer a **template** the library ships (a survey, a volunteer list) with a default handler, and change its questions.

## How a profile uses the library

A profile does not write the forms the law requires. It gives the library what is its own:

```python
class ThisCommunity(Community):
    def jurisdictions(self):    return ("US", "CA")                       # the default
    def form_slots(self):       return FORM_SLOTS                          # the name, return address, contacts, fee schedule, letterhead
    def form_adjustments(self): return (Adjust("records-request", clocks=(...)),    # a clock the documents make stricter
                                        Add("architectural-application", question=...))  # a question the documents require
    def form_bindings(self):    return (Bind("rental-application", section="ccrs#4.15", ...),)  # the documents' provisions
    def custom_forms(self):     return (VOLUNTEER_LIST,)                   # the community's own
```

`Community.forms()` returns the **resolved** set: the library's forms for the chain, each with the profile's slots, adjustments, and bindings applied, then the custom ones. Everything that makes or reads a form (`jason forms`, `jason packet`, the responses inbox, `jason owner-info`) asks `forms()`, never a profile module's constant (`spec_module` is being phased out).

**What an adjustment may do.** Add a question the documents require; add a preamble paragraph; make a clock stricter where a document asks more than the statute (the stricter clock governs, as in the notice catalog); set the channels and the return method; set the marker code's cycle. It may **not** remove or reword a required item, lengthen a statutory clock, drop a recital, or add a question the law or a document bars. The check below refuses it.

## What the library checks

`jason form-library --check` (and the build of any form) runs, per community:

1. **Required content:** every `required_content` item is carried by a question or a preamble; the item points at the question that carries it.
2. **Recitals resolve:** every `{QUOTE:...}` token resolves from the statutes on disk, the cited subdivision exists, and the as-of is the shelf's. A subdivision that moved fails the build, naming the form.
3. **Slots are filled:** every `{SLOT}` a form uses has a value; a family form's bindings are complete, or the form is "not offered" with the missing slot named.
4. **Adjustments are lawful:** none removes, rewords, or lengthens a required item or a statutory clock; a document clock that is stricter is recorded as the governing one with its section.
5. **A handler exists:** the form's handler and procedure are registered, or the form is not made.
6. **Marker codes are unique** across the resolved set and the campaigns on disk.
7. **Nothing bars what it asks:** a question a binding forbids (the rental application's "who are the tenants") is not on the form.

The output is a table by tier and form: ready, adjusted (what), not offered (why), failing (what).

## Versions: a form follows the law

A built-in form has a **version** and an **as-of** (the day of the law it recites). When a section it cites is amended, the shelf's text changes and the form's check fails until a person reads the amendment, updates the definition, and bumps the version with a note of what changed and when it is effective. A **campaign** records the form version it used, so a return is read against the form that was sent, and an old campaign keeps its words. `jason conflicts --leads` and `jason law-history` already find the amended sections; the library lists each form against them (a form whose citation changed since its as-of is "stale: read the amendment").

A community pins nothing: it gets the current version at its next campaign. A mid-cycle change in the law is the board's decision, not jason's.

## Where it lives

```text
src/jason/community/form_library/
  __init__.py     the registry, Jurisdiction, Tier, FormDefinition, Slot, Adjust, Add, Bind
  resolve.py      the chain, the slots, the adjustments, the bindings -> the resolved forms
  check.py        the seven checks
  us/             the federal pack (accommodation)
  ca/             the California pack: one module a form (records.py, idr.py, adr.py ...)
  custom/         templates the library ships for a community's own forms (survey, volunteer list)
```

A definition extends today's `FormTemplate` (`key`, `title`, `authority`, `description`, `questions`, `signature`, `dated`, `preamble`, `attestation`, `code`, `style`) with `tier`, `jurisdiction`, `version`, `as_of`, `required_content`, `recitals`, `member_clock`, `association_clocks`, `acknowledgment`, `procedure`, `handler`, `channels`, and `slots` (the fields in [form-templates.md](form-templates.md#anatomy-of-a-template)). The profile's `FORM_TEMPLATES` constants move into the library or into the profile's `custom_forms()`.

## Rules this keeps

- **A fact is data and the law is code.** The law's forms are general code, tested once; a community's facts are slots.
- **A new decision is a new row.** A new state form is a definition and a test, a new community clock is an adjustment, a new community form is a custom form.
- **A reference exists only if a handler does** ([arrivals-design.md](arrivals-design.md)): the check refuses a form with no handler.
- **The boundary is tested:** the library names no association; `tests/test_profile.py` loads a second, throwaway profile with its own slots and adjustments.

## Build order

1. The mechanism: `Tier`, `Jurisdiction`, `FormDefinition`, the resolver, the seven checks, `Community.forms()`, and the command `jason form-library`; the two existing generic forms (the records request and the request to meet and confer) move into the California pack as the first definitions, and their three consumers (`jason forms`, `jason packet`, the packets task) read `forms()`.
2. The California forms in [form-templates.md](form-templates.md)'s order of work: the request for resolution and the resale documents request first (the Act says exactly what they carry), then records, architectural, the delivery forms.
3. The family forms and their bindings, starting with the rental application (held until the board takes up its rental approvals).
4. The US pack, the custom templates, and the library's screen in the console ([console/handoff-form-library.md](console/handoff-form-library.md)).

## Open decisions

- Whether a locality tier is needed before a second community in another county uses jason.
- Whether a community may pin a form version for a campaign already begun (the proposal: yes, until it ends).
- Who reads an amendment and bumps a form: the administrator, with the law-review procedure each January (`jason sop law-review`).
