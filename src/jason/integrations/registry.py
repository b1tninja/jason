"""The integrations jason knows, in code: one ``Integration`` per kind of connection (docs/integrations-design.md).

Each carries its scope (the installation's, or each community's own), how it signs in, its capabilities (each a
separate switch, the scopes or permissions it asks for in the provider's own names, writes marked), the provider's
published rate limit (with where and when it was read) or "none published", the setup dialog's steps
(docs/console/handoff-instance-and-integrations.md), and its **sources**: one ``Cadence`` a refresh command, with the
default cadence, the floor (the fastest an administrator may set), and ``stale_after``, which the Status screen reads
to say current or stale (``jason.web.extra.status``).

Every figure in a cadence is a default for the board or the administrator to adopt (integrations-design.md, "Defaults
from rate limits", open decision 6); a row the design's table does not give is marked ``proposed``.

General code: no association's facts. A signed-in vendor portal is one integration whose instances are the profile's
portal rows (``Community.vendor_portals()``); the utilities' readers are the sibling packages (``smud``, ``i-doxs``)
and which of them a community uses is its settings; county sources are asspy's, whichever county.

Pure data: importing it loads no profile, reads no setting, and calls nothing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import timedelta
from enum import Enum

READ_ON = "2026-10-05"                  # the day the published figures below were read


class Scope(Enum):
    """Whose integration it is: the installation's, or each community's own."""

    INSTANCE = "instance"
    COMMUNITY = "community"


class AuthMethod(Enum):
    OAUTH_WEB = "oauth-web"             # an OAuth Web application client; a person consents in a browser
    S2S_OAUTH = "s2s-oauth"             # a server-to-server app: account id, client id, secret; no refresh token
    PASSWORD_TOTP = "password+totp"     # a member's sign-in with an authenticator's seed
    PASSWORD = "password"               # a username and password (some add security questions)
    API_KEY = "api-key"
    NONE = "none"                       # nothing to connect; jason checks it answers


class ConnectionState(Enum):
    """A connection's five states (docs/console/handoff-instance-and-integrations.md, ``ConnectionChip``)."""

    NOT_SET_UP = "not set up"
    NEEDS_SIGN_IN = "needs sign-in"
    CONNECTED = "connected"
    FAILING = "failing"
    PAUSED = "paused"


@dataclass(frozen=True)
class Capability:
    """One switch: what it lets jason do, the scopes or permissions it asks for (the provider's own names), and
    whether it writes. A write capability is off until a person turns it on."""

    key: str
    label: str
    scopes: tuple[str, ...] = ()
    writes: bool = False
    note: str = ""


@dataclass(frozen=True)
class Step:
    """One step of the setup dialog: what the administrator does (in the provider's console, in words), and what jason
    checks afterwards ("" when only the administrator can confirm it)."""

    title: str
    admin_does: str
    jason_checks: str = ""


@dataclass(frozen=True)
class RateLimit:
    """The provider's published limit, where it is published, and when it was read; or "none published", read
    politely (one request at a time, about a second apart, ``Retry-After`` honored)."""

    published: str
    source: str = ""
    read_on: str = ""

    @property
    def polite(self) -> bool:
        return not self.source


NONE_PUBLISHED = RateLimit("none published")

_DURATION = re.compile(r"^(\d+)\s*(m|h|d)$")
_UNIT = {"m": "minutes", "h": "hours", "d": "days"}


def duration(text: str) -> timedelta | None:
    """``"10m"``, ``"2h"``, ``"9d"`` as a timedelta; "" is None. Anything else raises ``ValueError``."""
    if not text:
        return None
    hit = _DURATION.match(text.strip())
    if not hit:
        raise ValueError(f"{text!r} is not a duration like 10m, 2h, or 9d")
    return timedelta(**{_UNIT[hit.group(2)]: int(hit.group(1))})


def _cron_period(cron: str) -> timedelta:
    """The longest gap between a five-field cron's runs, near enough to hold a floor and a stale threshold against: a
    weekday or a day of the month and a weekday (cron runs on either) is a week, a day of the month alone a month, a
    fixed hour a day, otherwise an hour."""
    fields = cron.split()
    if len(fields) != 5:
        raise ValueError(f"{cron!r} is not a five-field cron")
    _minute, hour, dom, _month, dow = fields
    if dow != "*":
        return timedelta(days=7)
    if dom != "*":
        return timedelta(days=31)
    if hour != "*" and not hour.startswith("*/"):
        return timedelta(days=1)
    return timedelta(hours=1)


@dataclass(frozen=True)
class Cadence:
    """How often one source is read by default: the refresh command (``argv``, as the job queue stores it), ``every``
    (``15m``, ``1h``) or a five-field ``cron``, the hours it runs in the community's time zone (``window``, ``07-22``)
    and how often outside them (``outside``), the ``floor``, ``stale_after``, the published ``limit`` it is held
    under, and a ``note``. ``proposed`` marks a default the design's table does not give; ``manual`` says why the
    scheduler cannot run the command by itself (a person must)."""

    source_key: str
    argv: tuple[str, ...]
    every: str = ""
    cron: str = ""
    window: str = ""
    outside: str = ""
    floor: str = ""
    stale_after: str = ""
    limit: str = ""
    note: str = ""
    proposed: bool = False
    manual: str = ""

    @property
    def period(self) -> timedelta:
        """The longest gap between two runs by default (outside the window, where that is longer)."""
        base = duration(self.every) if self.every else _cron_period(self.cron)
        assert base is not None
        out = duration(self.outside)
        return max(base, out) if out else base

    @property
    def floor_delta(self) -> timedelta | None:
        return duration(self.floor)

    @property
    def stale_delta(self) -> timedelta | None:
        return duration(self.stale_after)

    @property
    def stale_after_days(self) -> float | None:
        d = self.stale_delta
        return d.total_seconds() / 86400 if d else None

    def words(self) -> str:
        """The cadence in words: ``every 10m 07-22 (1h outside), floor 2m, stale after 1h``."""
        when = f"every {self.every}" if self.every else f"cron {self.cron}"
        if self.window:
            when += f" {self.window}"
        if self.outside:
            when += f" ({self.outside} outside)"
        parts = [when]
        if self.floor:
            parts.append(f"floor {self.floor}")
        if self.stale_after:
            parts.append(f"stale after {self.stale_after}")
        if self.proposed:
            parts.append("proposed")
        if self.manual:
            parts.append("a person runs it")
        return ", ".join(parts)


@dataclass(frozen=True)
class Integration:
    """One kind of connection. ``credential`` says in words what the vault holds for it (never a value);
    ``vault_names`` are the names under its vault prefix (``jason/<scope>/<community>/<key>/<name>``); ``check`` says
    what the read that proves it works reads; ``instances`` says where its instances come from when it has several
    (the profile's portal rows)."""

    key: str
    name: str
    scope: Scope
    auth: AuthMethod
    capabilities: tuple[Capability, ...] = ()
    rate_limit: RateLimit = NONE_PUBLISHED
    setup_steps: tuple[Step, ...] = ()
    sources: tuple[Cadence, ...] = ()
    credential: str = ""
    vault_names: tuple[str, ...] = ()
    check: str = ""
    instances: str = ""

    def default_capabilities(self) -> tuple[str, ...]:
        """The capabilities on until a person changes them: every read, no write."""
        return tuple(c.key for c in self.capabilities if not c.writes)


# --- the integrations --------------------------------------------------------------------------------------------------

_G = "https://www.googleapis.com/auth/"
_POLITE = ("Read politely: one request at a time, about a second apart with jitter, Retry-After honored, backoff on "
           "429 and 5xx.")
_WEEKLY_AND_5TH = "0 4 5 * 1"           # Mondays and the 5th of each month (cron runs on either day)

GOOGLE_WORKSPACE = Integration(
    "google-workspace", "Google Workspace", Scope.COMMUNITY, AuthMethod.OAUTH_WEB,
    capabilities=(
        Capability("drive-read", "Read Drive", (_G + "drive.readonly",)),
        Capability("drive-history", "Read who changed Drive files, and Drive labels",
                   (_G + "drive.activity.readonly", _G + "drive.labels.readonly")),
        Capability("docs-sheets-read", "Read Docs and Sheets", (_G + "documents.readonly", _G + "spreadsheets.readonly")),
        Capability("gmail-read", "Read Gmail", (_G + "gmail.readonly",)),
        Capability("calendar-read", "Read Calendar", (_G + "calendar.events.readonly",)),
        Capability("forms-read", "Read Forms responses", (_G + "forms.responses.readonly",)),
        Capability("tasks-read", "Read Tasks", (_G + "tasks.readonly",), note="a token of its own"),
        Capability("vault-read", "Read Vault matters and holds", (_G + "ediscovery.readonly",),
                   note="a token of its own"),
        Capability("photos-pick", "Read the photos a person picks", (_G + "photospicker.mediaitems.readonly",),
                   note="a token of its own"),
        Capability("drive-file", "File and move documents in Drive", (_G + "drive",), writes=True),
        Capability("docs-sheets-edit", "Edit Docs and Sheets", (_G + "documents", _G + "spreadsheets"), writes=True),
        Capability("gmail-draft", "Draft in Gmail", (_G + "gmail.compose",), writes=True,
                   note="Google has no drafts-only scope; jason only drafts, and a person sends"),
        Capability("calendar-write", "Put meetings and deadlines on Calendar", (_G + "calendar.events",), writes=True),
        Capability("forms-edit", "Build and edit Forms", (_G + "forms.body",), writes=True),
        Capability("tasks-write", "Keep the board's Tasks", (_G + "tasks",), writes=True, note="a token of its own"),
        Capability("photos-albums", "Keep jason's own photo albums",
                   (_G + "photoslibrary.appendonly", _G + "photoslibrary.readonly.appcreateddata",
                    _G + "photoslibrary.edit.appcreateddata"), writes=True, note="a token of its own"),
    ),
    rate_limit=RateLimit("per API, per minute, per user and per project (Drive and Gmail in quota units since May 1, "
                         "2026); each source's figure is on its cadence",
                         "Google's Drive, Gmail, Calendar, Sheets, Docs, Tasks, and Vault usage-limit pages", READ_ON),
    setup_steps=(
        Step("The project", "Google Cloud Console: create a project inside the community's Workspace organization. A "
                            "community needs Google Workspace; a consumer Gmail account is not supported."),
        Step("The APIs", "APIs & Services, Library: enable the API for each capability switched on (Drive, Docs, Sheets, "
                         "Gmail, Calendar, Drive Activity, Forms, Tasks, Photos Picker and Library, Vault). Enabling an "
                         "API grants nothing; scopes are granted at sign-in.",
             "at sign-in, a call to each; a disabled API names itself"),
        Step("Branding", "Google Auth Platform, Branding: the app name (jason, or the community's choice) and a support "
                         "email at the community's domain; the logo is optional."),
        Step("Audience", "User type Internal: only the organization's accounts can sign in, and Google asks no "
                         "verification. Never Testing for Drive or Gmail: those tokens die in seven days.",
             "the token's domain is the community's"),
        Step("Data access", "Add the scopes the capabilities switched on ask for, read-only first.",
             "the scopes granted against those asked"),
        Step("The client", "Clients, Create client, Web application: paste the redirect URI the dialog shows "
                           "(/auth/google/callback); leave JavaScript origins empty; download the JSON (newer projects "
                           "show the secret only then). A new redirect URI can take five minutes to a few hours to take "
                           "effect."),
        Step("Into the vault", "At the terminal: jason sign-in --import-client FILE (it puts the client at the community's "
                               "vault path and never prints it; delete the downloaded file after). A later release adds "
                               "the console's write-only file drop; the file is not kept and its contents are never shown.",
             "the vault entry is set"),
        Step("Sign in", "Sign in with Google as the account jason reads with: its own mailbox (recommended), or the "
                        "signed-in officer.",
             "a Drive list and the Gmail profile read"),
        Step("jason's mailbox", "Add the account to every Google Group with Each email delivery; aliases as groups "
                                "(docs/setup.md, jason's mailbox).",
             "the groups the mailbox is in"),
    ),
    sources=(
        Cadence("drive", ("drive", "--sync"), every="15m", window="07-22", outside="1h", floor="5m", stale_after="2h",
                limit="325,000 quota units a minute per user; 1,000,000 per project (a full list costs 100 units)",
                note="a full reconcile weekly; changes.list from a saved token once incremental reads are built"),
        Cadence("gmail", ("gmail", "--sync"), every="10m", window="07-22", outside="1h", floor="2m", stale_after="1h",
                limit="6,000 quota units a minute per user; 1,200,000 per project (history.list costs 2 units)"),
        Cadence("calendar", ("schedule", "--read-google"), every="30m", floor="5m", stale_after="3h",
                limit="600 requests a minute per user; 10,000 per project",
                note="the same command reads Calendar and Tasks today (data/schedule/google-read.json)"),
        Cadence("tasks", ("schedule", "--read-google"), every="1h", floor="15m", stale_after="1d",
                limit="50,000 requests a day per project",
                note="the same command reads Calendar and Tasks today (data/schedule/google-read.json)"),
        Cadence("responses-gmail", ("responses", "--check", "--channel", "gmail", "--channel", "mail", "--channel",
                                    "forms", "--by", "scheduler"),
                every="1h", window="07-22", outside="4h", floor="15m", stale_after="1d", proposed=True,
                limit="6,000 quota units a minute per user (headers and attachment names only; nothing is downloaded)",
                note="has anyone answered a request: replies in Gmail, scans from the mail service, and saved Google "
                     "Form responses, kept in data/responses; a check reads and keeps, and records nothing in PayHOA"),
    ),
    credential="the OAuth Web client, and one refresh token per account jason reads with",
    vault_names=("oauth-client", "token/<account>"),
    check="lists the Drive root and reads the Gmail profile",
)

SIGN_IN = Integration(
    "sign-in", "Console sign-in (the community's)", Scope.COMMUNITY, AuthMethod.OAUTH_WEB,
    capabilities=(Capability("sign-in", "Sign people in to the console", ("openid", "email", "profile")),),
    setup_steps=(
        Step("The client", "In the community's Cloud project (the Workspace project may carry it): Clients, Create "
                           "client, Web application, scopes openid email profile only, the redirect URI the dialog "
                           "shows (/auth/google/callback)."),
        Step("Into the vault", "jason sign-in --import-client FILE --yes --delete-file (the secret goes from the file to "
                               "the vault; the file is deleted).",
             "the client is named in the community's sign-in file"),
        Step("Domains and label", "The email domains it accepts and the button's words."),
        Step("The roster", "Who may sign in: the officers and the portfolio managers (People, read-only).",
             "the roster's count, and how many have an address to sign in with"),
    ),
    credential="the OAuth Web client (openid email profile)",
    vault_names=("oauth-client",),
    check="the client is named in the community's sign-in file",
)

PAYHOA = Integration(
    "payhoa", "PayHOA", Scope.COMMUNITY, AuthMethod.PASSWORD_TOTP,
    capabilities=(
        Capability("read", "Read the catalog, transactions, ledger, budget, reconciliations, reports, and meetings",
                   ("what the member account can see",)),
        Capability("bulk-writes", "Bulk writes (owner information, broadcasts)", ("what the member account can change",),
                   writes=True, note="each still needs a person's --yes, and keeps its own pace (batches.Pace)"),
    ),
    rate_limit=RateLimit("none published; jason uses PayHOA's own web endpoints with a member's sign-in, and bulk "
                         "writes read PayHOA's x-ratelimit-remaining"),
    setup_steps=(
        Step("A sign-in", "A PayHOA member account jason signs in with. Who it is matters: what it can see is what jason "
                          "can read."),
        Step("Into the vault", "The username, the password, and the authenticator's setup key (TOTP seed), in one entry."),
        Step("The organization", "The organization id from the profile, confirmed.",
             "jason signs in and finds the organization"),
        Step("Writes", "Bulk writes (owner information, broadcasts) stay off unless switched on, and each still needs a "
                       "person's --yes."),
    ),
    sources=(
        Cadence("payhoa-catalog", ("sync-catalog",), cron="0 2 * * *", floor="6h", stale_after="2d",
                note="units, people, requests, violations, and documents"),
        Cadence("payhoa-transactions", ("invoices", "--fetch"), cron="10 2 * * *", floor="6h", stale_after="2d"),
        Cadence("payhoa-notices", ("meetings", "--sync"), cron="20 2 * * *", floor="6h", stale_after="2d",
                note="the command also syncs Zoom"),
        Cadence("payhoa-ledger", ("books", "--sync"), cron=_WEEKLY_AND_5TH, floor="1d", stale_after="9d",
                note="weekly, and the 5th of each month"),
        Cadence("payhoa-budget", ("budget",), cron="15 4 5 * 1", floor="1d", stale_after="9d",
                note="weekly, and the 5th of each month"),
        Cadence("payhoa-reconciliations", ("reconcile", "--fetch"), cron="30 4 5 * 1", floor="1d", stale_after="9d",
                note="weekly, and the 5th of each month"),
        Cadence("payhoa-reports", ("ledger", "--fetch"), cron="45 4 5 * 1", floor="1d", stale_after="9d",
                note="weekly, and the 5th of each month"),
        Cadence("utility-payments", ("utilities", "--payments", "--fetch"), cron="0 5 * * 1", floor="1d",
                stale_after="9d", note="PayHOA's utility payments and their bills; weekly, as the utilities"),
        Cadence("responses-payhoa", ("responses", "--check", "--channel", "payhoa", "--by", "scheduler"),
                every="2h", window="07-22", floor="1h", stale_after="1d", proposed=True,
                note="has anyone answered a request: the owner-information form's submissions, kept in data/responses; "
                     "a check reads and keeps, and records nothing in PayHOA"),
    ),
    credential="the member's username, password, and TOTP seed, in one entry",
    vault_names=("login",),
    check="signs in and finds the organization among those the account sees",
)

ZOOM = Integration(
    "zoom", "Zoom", Scope.COMMUNITY, AuthMethod.S2S_OAUTH,
    capabilities=(
        Capability("meetings-read", "Read meetings",
                   ("list meetings", "past meeting", "past meeting instances"), note="the :admin granular scopes; Zoom "
                                                                                     "renames them, so they are listed by "
                                                                                     "purpose"),
        Capability("participants-read", "Read who attended", ("past meeting participants",), note="needs a paid plan"),
        Capability("recordings-read", "Read recordings and transcripts", ("list user recordings", "recording content")),
        Capability("summaries-read", "Read AI Companion summaries", ("list meeting summaries", "meeting summary"),
                   note="needs a paid plan"),
        Capability("meetings-write", "Create meetings (hearings)", ("write meeting",), writes=True),
    ),
    rate_limit=RateLimit("by plan: Pro 30, 20, and 10 requests a second for light, medium, and heavy APIs; 10 a minute "
                         "for resource-intensive ones; 30,000 a day for heavy", "Zoom's API rate limits page", READ_ON),
    setup_steps=(
        Step("The app", "App Marketplace, Develop, Build app, Server-to-Server OAuth, by the account owner or an admin "
                        "with the permission. It cannot be published and needs no review."),
        Step("Scopes", "The :admin granular scopes for the capabilities on, by purpose: meetings, past meetings and "
                       "instances, participants; recordings and their content; meeting summaries; write meeting only for "
                       "hearings.",
             "the token's scopes against those asked"),
        Step("Activate", "Activate the app."),
        Step("Into the vault", "The account id, client id, and client secret: jason zoom --store-app --account-id A "
                               "--client-id C puts the app at the community's vault path (create only), and the secret goes "
                               "in the record's password field in Keeper. A later release adds the console's secure entry.",
             "a token is issued and one meeting is listed; which capabilities the plan allows"),
    ),
    sources=(
        Cadence("zoom", ("zoom",), cron="0 3 * * *", floor="1h", stale_after="2d",
                limit="the plan's per-second limits; 30,000 heavy requests a day",
                note="also two hours after each scheduled board meeting"),
    ),
    credential="the app's account id, client id, and client secret; one-hour tokens, no refresh token",
    vault_names=("app",),
    check="asks for a token and lists one meeting",
)

POSTSCANMAIL = Integration(
    "postscanmail", "PostScanMail", Scope.COMMUNITY, AuthMethod.API_KEY,
    capabilities=(Capability("mail-read", "Read the scanned mail", ("the API key's mailbox",)),),
    setup_steps=(
        Step("Into the vault", "The mailbox's API key, at a hidden prompt or the dialog's secure entry; a key file is "
                               "moved into the vault and deleted.",
             "the vault entry is set"),
        Step("A read", "Nothing more to do.", "the mailbox's newest items are listed"),
    ),
    sources=(
        Cadence("mail", ("mail",), cron="0 8 * * *", floor="1h", stale_after="3d", proposed=True, note=_POLITE),
    ),
    credential="the API key",
    vault_names=("api-key",),
)

UTILITIES = Integration(
    "utilities", "Utility billing portals", Scope.COMMUNITY, AuthMethod.PASSWORD,
    capabilities=(Capability("bills-read", "Read bills, payments, and usage", ("the account holder's portal",)),),
    setup_steps=(
        Step("Into the vault", "One entry a portal: the username and password (a portal that asks security questions "
                               "keeps their answers in the same entry).",
             "the vault entry is set"),
        Step("A read", "Nothing more to do.", "the portal's accounts are listed"),
    ),
    sources=(
        Cadence("smud", ("sync-smud",), cron="0 6 * * 1", floor="1d", stale_after="9d", note="and near each bill date"),
        Cadence("idoxs", ("sync-idoxs",), cron="15 6 * * 1", floor="1d", stale_after="9d",
                note="and near each bill date"),
    ),
    credential="a username and password a portal",
    vault_names=("login/<portal>",),
    instances="the utility readers whose login is set (smud, i-doxs)",
)

ACCELA = Integration(
    "accela", "Permit portal (Citizen Access)", Scope.COMMUNITY, AuthMethod.PASSWORD,
    capabilities=(Capability("permits-read", "Read the association's permits", ("the account's collection",)),),
    setup_steps=(
        Step("Into the vault", "The portal account's username and password.", "the vault entry is set"),
        Step("A read", "Nothing more to do.", "the account's collection is read"),
    ),
    sources=(
        Cadence("permits", ("permit-status", "--sync"), cron="0 7 * * 2", floor="1d", stale_after="9d", proposed=True,
                note=_POLITE),
    ),
    credential="the portal account's username and password",
    vault_names=("login",),
)

VENDOR_PORTALS = Integration(
    "vendor-portals", "Vendor portals (signed in)", Scope.COMMUNITY, AuthMethod.PASSWORD,
    capabilities=(Capability("portal-read", "Read invoices, visits, products, and files", ("the customer account",)),),
    setup_steps=(
        Step("Into the vault", "One entry a portal, named by the profile's portal row: the username and password.",
             "the vault entry is set"),
        Step("A read", "Nothing more to do.", "the portal's properties are listed"),
    ),
    sources=(
        Cadence("vendor-portals", ("vendors", "--sync"), cron="30 6 * * 1", floor="1d", stale_after="9d",
                note="and near each bill date"),
    ),
    credential="a username and password a portal",
    vault_names=("<portal key>",),
    instances="the profile's portal rows (Community.vendor_portals())",
)

# --- the installation's ------------------------------------------------------------------------------------------------

VAULT = Integration(
    "vault", "Credential vault", Scope.INSTANCE, AuthMethod.PASSWORD_TOTP,
    capabilities=(Capability("secrets", "Hold every connection's credential", ("the vault's own login",)),),
    setup_steps=(
        Step("Sign in", "jason login, at a terminal: the master password, the device approval, and the second factor. "
                        "The login lasts while it is used; Keeper ends it after 30 days idle.",
             "the vault's login is on this machine"),
    ),
    credential="the vault's own login (Keeper on this PC)",
    check="the vault's login is on this machine",
)

INSTANCE_SIGN_IN = Integration(
    "instance-sign-in", "Console sign-in (the installation's)", Scope.INSTANCE, AuthMethod.OAUTH_WEB,
    capabilities=(Capability("sign-in", "Sign in admins and managers whose accounts are in no community's Workspace",
                             ("openid", "email", "profile")),),
    setup_steps=(
        Step("The client", "A Web application client, scopes openid email profile only, the redirect URI the dialog "
                           "shows (/auth/google/callback)."),
        Step("Into the vault", "jason sign-in --import-client FILE --for jason --yes --delete-file.",
             "the client is named in the installation's sign-in file"),
    ),
    credential="the OAuth Web client (openid email profile)",
    vault_names=("oauth-client",),
    check="the client is named in the installation's sign-in file",
)

LAW_LIBRARY = Integration(
    "law-library", "Law library", Scope.INSTANCE, AuthMethod.NONE,
    capabilities=(Capability("statutes-read", "Read the statutes on disk"),),
    setup_steps=(Step("The checkout", "The lawlibrary checkout beside jason (lawlibrary_home).", "its folder is there"),),
    check="its folder is there",
)

LOCAL_MODELS = Integration(
    "local-models", "Local models", Scope.INSTANCE, AuthMethod.NONE,
    capabilities=(Capability("models", "Read documents with the local model server"),),
    setup_steps=(Step("The model server", "Ollama on this machine, with jason's models pulled (jason local-ai).",
                      "the server answers and its models are listed"),),
    check="the model server answers (jason local-ai)",
)

COUNTY = Integration(
    "county", "County sources", Scope.INSTANCE, AuthMethod.NONE,
    capabilities=(Capability("county-read", "Read the county's tax bills, rolls, and recorder index (asspy)"),),
    setup_steps=(Step("The county", "The county adapter the profile names (asspy); nothing to sign in to.",
                      "the county's stores have a last read"),),
    sources=(
        Cadence("county-tax", ("sync-tax",), cron="0 5 1 * *", floor="1d", stale_after="35d",
                note="daily during the installment windows"),
        Cadence("county-secured", ("sync-secured",), cron="30 5 1 * *", floor="1d", stale_after="35d",
                manual="it reads the secured roll's workbook, which a person downloads and names"),
        Cadence("county-land", ("land-sync", "--units"), cron="0 6 * * *", floor="6h", stale_after="3d",
                note="the map's transfers since the last read, new plans and maps, the new owners' deeds in associations' "
                     "footprints, and the recorder watch's liens, defaults, and annexations (the first read of the deeds takes hours)"),
        Cadence("county-land-full", ("land-sync", "--full", "--no-watch"), cron="0 3 * * 0", floor="3d", stale_after="9d",
                note="every parcel, so a retired or split parcel is found"),
    ),
    instances="the county the profile names; the stores are each community's",
)

PUBLIC_VENDOR_PORTALS = Integration(
    "public-vendor-portals", "Vendor report portals (public)", Scope.INSTANCE, AuthMethod.NONE,
    capabilities=(Capability("reports-read", "Read a vendor's published reports (the portal a report's QR code names)"),),
    setup_steps=(Step("Nothing to connect", "The profile's portal rows name them.", "the portal answers"),),
)

BEDROCK = Integration(
    "bedrock", "Claude on Amazon Bedrock", Scope.INSTANCE, AuthMethod.API_KEY,
    capabilities=(Capability("model-calls", "Read contract terms with a hosted model", ("bedrock:InvokeModel",)),),
    setup_steps=(Step("AWS credentials", "The operator's AWS credentials in the AWS chain (a profile or the instance "
                                         "role); optional."),),
    credential="the operator's AWS credentials (the AWS chain)",
)

REGISTRY: tuple[Integration, ...] = (
    GOOGLE_WORKSPACE, SIGN_IN, PAYHOA, ZOOM, POSTSCANMAIL, UTILITIES, ACCELA, VENDOR_PORTALS,
    VAULT, INSTANCE_SIGN_IN, LAW_LIBRARY, LOCAL_MODELS, COUNTY, PUBLIC_VENDOR_PORTALS, BEDROCK,
)


def integration(key: str) -> Integration:
    """The integration ``key``; ``KeyError`` naming the known ones."""
    for i in REGISTRY:
        if i.key == key:
            return i
    raise KeyError(f"no integration {key!r}; known: {', '.join(i.key for i in REGISTRY)}")


def cadences(scope: Scope | None = None) -> tuple[Cadence, ...]:
    """Every source's default cadence, or only those of ``scope``'s integrations."""
    return tuple(c for i in REGISTRY if scope is None or i.scope is scope for c in i.sources)


def cadence_for(source_key: str) -> Cadence | None:
    """The cadence of the source ``source_key`` (a Status source's key), or None."""
    return next((c for c in cadences() if c.source_key == source_key), None)


def integration_of(source_key: str) -> Integration | None:
    """The integration whose source ``source_key`` is, or None."""
    return next((i for i in REGISTRY if any(c.source_key == source_key for c in i.sources)), None)


__all__ = ["READ_ON", "REGISTRY", "AuthMethod", "Cadence", "Capability", "ConnectionState", "Integration",
           "NONE_PUBLISHED", "RateLimit", "Scope", "Step", "cadence_for", "cadences", "duration", "integration",
           "integration_of"]
