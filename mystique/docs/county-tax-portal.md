# The county tax collector's payment portal, read from a capture

What the county's property tax site does when the association signs in, as read from a browser capture of 2026-09-27
(`county-taxes.net.har`, ignored by git; **it holds the session's live tokens**: see "Handling the capture"). It answers one
question for [the mail and payment attachments handoff](../../docs/console/handoff-mail-and-payment-attachments.md): when a
PayHOA payment goes to the county tax collector and no bill is attached, can a reader find the **bill** and the **receipt**?
The answer is yes for both, behind a sign-in a person makes. Nothing is built from this yet. No parcel number, address, name,
amount, or token from the capture is written here.

## What the site is

The county's tax site is Grant Street Group's payment platform, served in two layers:
- **The public site** (`county-taxes.net`): a page per saved parcel, shown in an iframe under `/iframe-taxsys/<site>/govhub/property-tax/<item id>`.
- **GovHub** (`govhub.com/svc/...`): the account's services (saved items, payables, payment history, carts, scheduled payments,
  e-billing). The public site's page calls them with a bearer token.

The same platform serves other counties' tax collectors, so a reader written for it is a platform adapter with a per-county site
name (here the county's own slug), not Sacramento-specific code. [../../docs/adapters.md](../../docs/adapters.md) lists adapters;
this one would be declared there before any general doc names the platform.

## Signing in

- GovHub signs in with **OpenID Connect and PKCE**. The identity provider is a hosted login (Okta) that a person uses in a browser;
  the capture holds no password field because the person was already signed in there.
- The exchange: `GET /svc/login/oidc/auth` (state, `code_challenge`) → the provider → `POST /svc/login/oidc/callback` →
  `POST /svc/login/oidc/token` (authorization code + `code_verifier` + `client_id`) → `access_token`, `id_token`, `refresh_token`.
- A later call `POST /svc/login/oidc/token` with `grant_type=refresh_token`, `client_id`, and `scope` returns a fresh access token.
  So **one interactive sign-in at a terminal can feed an unattended reader**, the way jason's Google and Keeper sign-ins work:
  the person signs in, the refresh token goes to the vault (never `.env`, never a log), and a scheduled read refreshes it.
  Whether the refresh token expires, rotates, or is bound to the browser is **not in the capture** and must be tried once with a
  person present before a cadence is adopted (`jason cadence` runs a source only after a person adopts it).
- The capture strips `Authorization` and cookies, so how the bearer token is attached to each call, and how the iframe's
  session is made (`/callback`, then a `cookie_id` in each `update-actions` form post), is read from the shapes, not seen.

## What it exposes (all reads)

| Call | Gives | Use for jason |
|---|---|---|
| `GET /svc/mythings/api/v2/items/<client>/<site>` | The account's saved items: a list of item paths, one per saved parcel (ten in the capture) | Which parcels the account follows; compare with the profile's parcel list |
| `POST /svc/payables/v0/retrieve` (body: a list of item paths) | The items' payables, signed | The amounts due |
| `GET /svc/payables/v0/<url-encoded item path>` | One parcel: `display_name` (account number and situs), `external_id` (the APN), `description` (ownership dates), `amount`, `due_at`, payment choices and restrictions | The parcel's amount and due date |
| `GET <public site>/iframe-taxsys/.../property-tax/<item id>` | The parcel's page: its bills and the print options (`print_without_names`, `print_with_names`, `request_mailed`) | The bill list and each bill's uuid |
| `GET <public site>/.../bills/<uuid>` | One bill's page | Installments and balances |
| `GET <public site>/.../bills/<uuid>/print` | **The bill as a PDF**, filed by the site as `<County>-Property-Tax-<APN>-<year>-secured-bill.pdf` | **The attachment PayHOA is missing** |
| `GET /svc/payment-history/api/v2/receipts?page=&perPage=&client=&site=` | The account's receipts (a total; the capture's `perPage=0` returned the count only, so a real page size is needed) | The list of payments made through the site |
| `GET /svc/payment-history/api/v2/receipts/<confirmation>` | **One receipt**: confirmation number, posted time, the tender (bank account name and last four), the billing party, and each paid item with its amount | **Exact proof of payment**, with the confirmation number |

Not needed and never used by jason: the cart calls (`/svc/cart/.../vivify`, `get_tokens`), the card vault (`vault.county-taxes.com`),
scheduled payments, e-billing, and the telemetry hosts (the capture's gateway, Sentry, Algolia, LaunchDarkly, Google). **jason pays
nothing**: no call here moves money, and no cart is made.

## What it gives the investigation

For a county payment with no attached bill (the case study in the handoff):
1. **The receipt** matches the PayHOA payment by amount, date, and the tender's bank last four; its confirmation number and items
   say *which bill* was paid. That is better than a bank notice in Gmail: it is the county's own record, with the parcel.
2. **The bill PDF** is the document to attach, for the bill the receipt names.
3. The two together answer the treasurer's open question: the bill is attached and the receipt is its proof, with no guess.

The existing `jason sync-tax` already stores the bill values and PDFs it reads from the county's other site. The portal adds the
**receipts** (what was paid, when, by which account) and the account's own saved-parcel list; the bill PDF is the same document
from a second source, so a reader can cross-check the two.

## Privacy

- A receipt carries the billing party's name, address, phone, and email, and the bank account's name and last four. The reader keeps
  the confirmation number, the posted time, the paid items and amounts, and the **last four only**; it drops the rest. An APN is
  shown by its last four in lists.
- A receipt and a bill are P1 (amounts, payees); the tender's bank detail is P2. The investigation card follows its existing rule.
- The refresh token is a secret (P4): it lives in the vault at a path like `county-tax-portal/refresh-token`, never in the
  repository, a log, or the console.

## If it is built

Two parts, in this order, each read only:
1. **A receipts reader** (`jason county-tax --receipts`): sign in once at a terminal, keep the refresh token in the vault, list the
   receipts, keep the trimmed fields in `data/tax/receipts.json` with their age. The investigation reads that file offline, so a
   county payment finds its receipt without a network call when a page opens.
2. **A bill reader** (the print route per bill, filed by APN and year), which makes a county-tax `BillSource` over the stored PDFs
   and `TaxStore`; the attach engine then treats a county payment like any other.

Both are declared as an adapter (`jason.community.adapters`, [../../docs/adapters.md](../../docs/adapters.md)) naming the platform,
take the county's site name from the profile, and refuse to run without a person's sign-in.

## Handling the capture

The HAR is 67 MB and holds the session's `access_token`, `id_token`, and `refresh_token` in the `/svc/login/oidc/token` response
bodies, plus a receipt with the billing contact and the bank account. It is ignored by git (`*.HAR`), but it sits in the working
folder. After its use: sign out of the county site everywhere, delete the file or move it out of the repository, and do not attach
or share it. The sign-out revokes the session only if the platform honors it; the safest course is to treat the tokens as spent.

## What is not known

- Whether the refresh token lasts and is usable without the browser (it must be tried once, with the person present).
- How the public site's iframe session is made for the print route outside a browser.
- Whether a public (no sign-in) bill lookup by APN exists; the capture is of a signed-in account only.
- The receipts list's page size limit.
