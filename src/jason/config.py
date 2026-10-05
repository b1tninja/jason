"""Jason settings loaded from .env and environment variables."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

def _default_payhoa_org_id() -> int:
    """Org id from the active profile."""
    from jason.community import community

    return community().org_id


# Keeper record UIDs come from .env (payhoa_record_uid, idoxs_record_uid); none is built in.
DEFAULT_PAYHOA_RECORD_UID = ""
DEFAULT_IDOXS_RECORD_UID = ""


def _utility_category(utility: object) -> int | None:
    """The PayHOA category the profile's transaction rules give a utility; None when no rule names one."""
    from jason.community import community

    for rule in community().transaction_rules():
        if rule.utility is utility and rule.category_id is not None:
            return rule.category_id
    return None


def _default_smud_category_id() -> int | None:
    from jason.community import Utility

    return _utility_category(Utility.SMUD)


def _default_idoxs_category_id() -> int | None:
    from jason.community import Utility

    return _utility_category(Utility.CITY_OF_SACRAMENTO)


# The profile's defaults are read when first asked for, so importing this module loads no profile.
_PROFILE_DEFAULTS = {
    "DEFAULT_PAYHOA_ORG_ID": _default_payhoa_org_id,
    "DEFAULT_SMUD_CATEGORY_ID": _default_smud_category_id,
    "DEFAULT_IDOXS_CATEGORY_ID": _default_idoxs_category_id,
}


def __getattr__(name: str):
    if name in _PROFILE_DEFAULTS:
        return _PROFILE_DEFAULTS[name]()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def user_config_path() -> Path:
    """jason's user config: ``JASON_CONFIG`` when set, else ``~/.jason/.env``. It need not exist. It sits in the home
    folder, outside AppData, so a terminal, an agent's shell, the worker, and a scheduled task all read the same file
    whatever their working directory; a program's AppData view can differ from another's. It holds the settings of the
    machine (where scratch, caches, and data live); a project's own .env, nearer, overrides it."""
    named = os.environ.get("JASON_CONFIG", "").strip()
    return Path(named).expanduser() if named else Path.home() / ".jason" / ".env"


def env_file_values(env_file: str | Path | None = None) -> dict[str, str | None]:
    """The settings the .env files give: the user config (``user_config_path``) as the base and the project's .env
    (``resolve_env_path``) over it, each key as written. An unreadable file gives nothing."""
    values: dict[str, str | None] = {}
    try:
        from dotenv import dotenv_values
    except Exception:  # noqa: BLE001 - no dotenv: no files
        return values
    for path in (user_config_path(), resolve_env_path(env_file)):
        try:
            if path.is_file():
                values.update(dotenv_values(path))
        except Exception:  # noqa: BLE001 - an unreadable .env sets nothing
            continue
    return values


def _env_value(key: str, env_file: str | Path | None = None) -> str:
    """``key`` from the environment, else from the project's .env (``resolve_env_path``), else from the user config
    (``user_config_path``), else ""."""
    value = os.environ.get(key, "").strip()
    if value:
        return _strip_quotes(value)
    values = env_file_values(env_file)
    for k, v in values.items():
        if k.upper() == key and v:
            return _strip_quotes(str(v))
    return ""


def data_root() -> Path:
    """The data root: ``JASON_DATA_DIR`` (environment or .env) when set, else ``data/`` beside this checkout. It is the
    default profile's data folder, the parent of every other profile's, and the home of the private facts
    (``<root>/spec``). Code asks ``data_dir()`` or ``default_data_dir()`` for a profile's folder; this is the one place
    the folder is named."""
    explicit = _env_value("JASON_DATA_DIR")
    if explicit:
        return Path(explicit)
    return Path(__file__).resolve().parents[2] / "data"


def _is_default_profile(profile: str = "") -> bool:
    """Whether ``profile`` (the active one by default) is the default profile. Reading the name loads no profile; a name
    that is not a profile's counts as the default, as ``default_data_dir`` reads it."""
    try:
        from jason.community.profile import DEFAULT_PROFILE, profile_name

        return (profile or profile_name()) == DEFAULT_PROFILE
    except Exception:  # noqa: BLE001
        return True


def default_data_dir(profile: str = "") -> Path:
    """The data folder when ``PAYHOA_CATALOG`` does not name one: ``data/`` for the default profile, ``data/<profile>/``
    for any other, so a second association never reads the first one's stores (phase 5 of docs/profiles.md).
    ``profile`` defaults to the active one; reading its name loads no profile."""
    root = data_root()
    try:
        from jason.community.profile import DEFAULT_PROFILE, profile_name

        name = profile or profile_name()
    except Exception:  # noqa: BLE001 - a name that is not a profile's leaves the first profile's folder
        return root
    return root if name == DEFAULT_PROFILE else root / name


def data_dir(env_file: str | Path | None = None) -> Path:
    """The active profile's data folder as the commands read it: the folder of the PayHOA catalog
    (``Settings.payhoa_catalog.parent``, so ``PAYHOA_CATALOG`` in .env moves it), else ``default_data_dir()`` when the
    settings cannot be read. Called when a path is needed, never as a default argument's value."""
    try:
        return Settings.load(env_file).payhoa_catalog.parent
    except Exception:  # noqa: BLE001 - a .env that cannot be read leaves the profile's own folder
        return default_data_dir()


def default_keeper_config_path() -> Path:
    """Persistent device config (Commander/SDK default location)."""
    return Path.home() / ".keeper" / "keeper-config.json"


DEFAULT_KEEPER_CONFIG = str(default_keeper_config_path())


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        return value[1:-1]
    return value


def _get(
    values: dict[str, str | None],
    *keys: str,
    default: str = "",
) -> str:
    for key in keys:
        if key in values and values[key]:
            return _strip_quotes(str(values[key]))
        env = os.environ.get(key) or os.environ.get(key.upper())
        if env:
            return _strip_quotes(env)
    return default


def _record_uids(values: dict[str, str | None]) -> dict[str, str]:
    """Every ``*_record_uid`` setting, environment first overridden by .env, keys lower-cased."""
    found = {k.lower(): _strip_quotes(v) for k, v in os.environ.items() if k.lower().endswith("_record_uid") and v}
    found.update({k.lower(): _strip_quotes(str(v)) for k, v in values.items() if k.lower().endswith("_record_uid") and v})
    return found


def _anchored(value: str | Path) -> Path:
    """A path setting as an absolute path: a relative one is taken from this checkout's folder, never from the working
    directory, so a command finds the same file wherever it is started (name an absolute path in the user config to put
    it on another drive)."""
    path = Path(value).expanduser()
    return path if path.is_absolute() else (Path(__file__).resolve().parents[2] / path).resolve()


def resolve_env_path(path: str | Path | None = None) -> Path:
    if path is not None:
        return Path(path)
    env = os.environ.get("JASON_ENV")
    if env:
        return Path(env)
    cwd = Path.cwd() / ".env"
    if cwd.is_file():
        return cwd
    # jason package lives at .../jason/src/jason/config.py → repo root is parents[2]
    repo_env = Path(__file__).resolve().parents[2] / ".env"
    if repo_env.is_file():
        return repo_env
    return cwd


def _default_smud_db() -> Path:
    """The ``smud`` checkout's own store beside jason for the default profile (it holds that association's accounts),
    else ``smud.db`` in the profile's data folder: another profile never reads the first one's utility store."""
    sibling = Path(__file__).resolve().parents[3] / "smud" / "data" / "smud.db"
    if sibling.is_file() and _is_default_profile():
        return sibling
    return default_data_dir() / "smud.db"


def _default_idoxs_db() -> Path:
    """As ``_default_smud_db``, for the ``i-doxs`` checkout's store."""
    sibling = Path(__file__).resolve().parents[3] / "i-doxs" / "data" / "idoxs.db"
    if sibling.is_file() and _is_default_profile():
        return sibling
    return default_data_dir() / "idoxs.db"


def _in_data(name: str):
    """A dataclass default: ``name`` in the active profile's data folder, found when a ``Settings`` is built (never at
    import, so importing jason reads no profile)."""
    return field(default_factory=lambda: default_data_dir() / name)


@dataclass(frozen=True)
class Settings:
    keeper_username: str
    payhoa_record_uid: str
    smud_record_uid: str
    idoxs_record_uid: str
    accela_record_uid: str = ""
    # an unprivileged PayHOA owner account kept for testing forms from an owner's side (its Keeper login record)
    payhoa_test_record_uid: str = ""
    # PayHOA memberships kept for testing: their submissions are never an owner's answer, and a real send skips them
    payhoa_test_membership_ids: tuple[int, ...] = ()
    # the operator's own PayHOA membership and unit: a test sent to "me" (kept out of code and fixtures)
    payhoa_my_membership_id: int | None = None
    payhoa_my_unit_id: int | None = None
    keeper_password: str = ""
    keeper_config: Path = Path(DEFAULT_KEEPER_CONFIG)
    payhoa_org_id: int = field(default_factory=_default_payhoa_org_id)
    smud_db: Path = _in_data("smud.db")
    smud_bills_dir: Path = _in_data("bills")
    smud_category_id: int | None = field(default_factory=_default_smud_category_id)
    idoxs_db: Path = _in_data("idoxs.db")
    idoxs_bills_dir: Path = _in_data("idoxs-bills")
    idoxs_category_id: int | None = field(default_factory=_default_idoxs_category_id)
    payhoa_catalog: Path = _in_data("payhoa.db")
    ownership_db: Path = _in_data("ownership.db")
    tax_db: Path = _in_data("tax.db")
    tax_bills_dir: Path = _in_data("tax-bills")
    secured_db: Path = _in_data("secured.db")
    characteristics_db: Path = _in_data("characteristics.db")
    google_oauth_record_uid: str = ""
    google_oauth_client_file: Path | None = None
    google_oauth_token_file: Path = Path("secrets/google-token.json")
    google_notebook_url: str = ""
    google_sheets_spreadsheet_id: str = ""
    lawlibrary_home: Path = Path("../lawlibrary")
    # JASON_TEMP_DIR: where scratch, temp files, and rebuilt-index spill go ("" leaves the system's temp alone);
    # apply_temp_dir() puts it into effect.
    temp_dir: str = ""
    env_path: Path | None = None
    # Every "<name>_record_uid" in .env or the environment, by lower-case key: a vendor portal's Keeper record.
    record_uids: dict[str, str] = field(default_factory=dict)

    def record_uid(self, name: str) -> str:
        """The Keeper record UID set as ``<name>_record_uid``, or an empty string."""
        return self.record_uids.get(f"{name.lower()}_record_uid", "")

    @classmethod
    def load(cls, path: str | Path | None = None) -> Settings:
        env_path = resolve_env_path(path)
        values = env_file_values(path)

        keeper_username = _get(
            values, "keeper_username", "KEEPER_USERNAME", default=""
        )
        payhoa_record_uid = _get(
            values,
            "payhoa_record_uid",
            "PAYHOA_RECORD_UID",
            default=DEFAULT_PAYHOA_RECORD_UID,
        )
        payhoa_test_record_uid = _get(
            values, "payhoa_test_record_uid", "PAYHOA_TEST_RECORD_UID", default=""
        )
        smud_record_uid = _get(
            values, "smud_record_uid", "SMUD_RECORD_UID", default=""
        )
        test_memberships = tuple(int(x) for x in _get(
            values, "payhoa_test_membership_ids", "PAYHOA_TEST_MEMBERSHIP_IDS", default="").replace(",", " ").split())
        my_membership = _get(values, "payhoa_my_membership_id", "PAYHOA_MY_MEMBERSHIP_ID", default="")
        my_unit = _get(values, "payhoa_my_unit_id", "PAYHOA_MY_UNIT_ID", default="")
        idoxs_record_uid = _get(
            values,
            "idoxs_record_uid",
            "IDOXS_RECORD_UID",
            default=DEFAULT_IDOXS_RECORD_UID,
        )
        accela_record_uid = _get(
            values,
            "accela_record_uid",
            "ACCELA_RECORD_UID",
            default="",
        )
        keeper_password = _get(
            values, "keeper_password", "KEEPER_PASSWORD", default=""
        )
        keeper_config_raw = _get(
            values,
            "keeper_config",
            "KEEPER_CONFIG_PATH",
            default="",
        )
        keeper_config = (
            Path(keeper_config_raw)
            if keeper_config_raw
            else default_keeper_config_path()
        )
        org_raw = _get(
            values,
            "payhoa_org_id",
            "PAYHOA_ORG_ID",
            default=str(_default_payhoa_org_id()),
        )
        smud_db_raw = _get(values, "smud_db", "SMUD_DB_PATH", default="")
        smud_db = Path(smud_db_raw) if smud_db_raw else _default_smud_db()
        bills_raw = _get(values, "smud_bills_dir", "SMUD_BILLS_DIR", default="")
        if bills_raw:
            smud_bills_dir = Path(bills_raw)
        else:
            smud_bills_dir = smud_db.parent / "bills"

        cat_raw = _get(
            values,
            "smud_category_id",
            "SMUD_CATEGORY_ID",
            default=str(_default_smud_category_id() or ""),
        )
        smud_category_id: int | None
        try:
            smud_category_id = int(cat_raw) if cat_raw else None
        except ValueError:
            smud_category_id = _default_smud_category_id()

        idoxs_db_raw = _get(values, "idoxs_db", "IDOXS_DB_PATH", default="")
        idoxs_db = Path(idoxs_db_raw) if idoxs_db_raw else _default_idoxs_db()
        idoxs_bills_raw = _get(
            values, "idoxs_bills_dir", "IDOXS_BILLS_DIR", default=""
        )
        if idoxs_bills_raw:
            idoxs_bills_dir = Path(idoxs_bills_raw)
        else:
            idoxs_bills_dir = idoxs_db.parent / "bills"

        idoxs_cat_raw = _get(
            values,
            "idoxs_category_id",
            "IDOXS_CATEGORY_ID",
            default=str(_default_idoxs_category_id() or ""),
        )
        idoxs_category_id: int | None
        try:
            idoxs_category_id = int(idoxs_cat_raw) if idoxs_cat_raw else None
        except ValueError:
            idoxs_category_id = _default_idoxs_category_id()

        catalog_raw = _get(
            values, "payhoa_catalog", "PAYHOA_CATALOG", default=""
        )
        payhoa_catalog = Path(catalog_raw) if catalog_raw else default_data_dir() / "payhoa.db"
        google_oauth_record_uid = _get(
            values,
            "google_oauth_record_uid",
            "GOOGLE_OAUTH_RECORD_UID",
            default="",
        )
        google_notebook_url = _get(
            values,
            "google_notebook_url",
            "GOOGLE_NOTEBOOK_URL",
            default="",
        )
        google_client_raw = _get(
            values,
            "google_oauth_client_file",
            "GOOGLE_OAUTH_CLIENT_FILE",
            default="",
        )
        google_token_raw = _get(
            values,
            "google_oauth_token_file",
            "GOOGLE_OAUTH_TOKEN_FILE",
            default="",
        )
        google_sheets_spreadsheet_id = _get(
            values,
            "google_sheets_spreadsheet_id",
            "GOOGLE_SHEETS_SPREADSHEET_ID",
            default="",
        )
        lawlibrary_home = _get(
            values,
            "lawlibrary_home",
            "LAWLIBRARY_HOME",
            default="../lawlibrary",
        )

        return cls(
            keeper_username=keeper_username,
            payhoa_record_uid=payhoa_record_uid,
            smud_record_uid=smud_record_uid,
            idoxs_record_uid=idoxs_record_uid,
            accela_record_uid=accela_record_uid,
            payhoa_test_record_uid=payhoa_test_record_uid,
            payhoa_test_membership_ids=test_memberships,
            payhoa_my_membership_id=int(my_membership) if my_membership else None,
            payhoa_my_unit_id=int(my_unit) if my_unit else None,
            keeper_password=keeper_password,
            keeper_config=keeper_config,
            payhoa_org_id=int(org_raw),
            smud_db=smud_db,
            smud_bills_dir=smud_bills_dir,
            smud_category_id=smud_category_id,
            idoxs_db=idoxs_db,
            idoxs_bills_dir=idoxs_bills_dir,
            idoxs_category_id=idoxs_category_id,
            payhoa_catalog=payhoa_catalog,
            ownership_db=payhoa_catalog.parent / "ownership.db",
            tax_db=payhoa_catalog.parent / "tax.db",
            tax_bills_dir=payhoa_catalog.parent / "tax-bills",
            secured_db=payhoa_catalog.parent / "secured.db",
            characteristics_db=payhoa_catalog.parent / "characteristics.db",
            google_oauth_record_uid=google_oauth_record_uid,
            google_oauth_client_file=(
                Path(google_client_raw) if google_client_raw else None
            ),
            google_notebook_url=google_notebook_url,
            google_oauth_token_file=_anchored(google_token_raw or "secrets/google-token.json"),
            google_sheets_spreadsheet_id=google_sheets_spreadsheet_id,
            lawlibrary_home=_anchored(lawlibrary_home),
            temp_dir=_get(values, "jason_temp_dir", "JASON_TEMP_DIR", default="") or _env_value("JASON_TEMP_DIR", env_path),
            env_path=env_path if env_path.is_file() else None,
            record_uids=_record_uids(values),
        )


def test_memberships(env_file: str | Path | None = None) -> set[int]:
    """The PayHOA memberships kept for testing (``payhoa_test_membership_ids`` in .env, plus any the specification's
    ``TEST_MEMBERSHIPS`` still names): their submissions are never an owner's answer, and a real send skips them."""
    from jason.community.spec import spec_module

    try:
        ids = set(Settings.load(env_file).payhoa_test_membership_ids)
    except Exception:  # no .env (a test run): only what the specification names
        ids = set()
    try:
        ids |= {int(k) for k in getattr(spec_module("forms"), "TEST_MEMBERSHIPS", {}) or {}}
    except Exception:
        pass
    return ids


# ----- where scratch goes (JASON_TEMP_DIR) -----

# The variables that name the temp folder for this process and every program it starts (Windows reads TEMP and TMP,
# POSIX TMPDIR, SQLite's own spill files SQLITE_TMPDIR where the platform honors it, and pytest's tmp_path
# PYTEST_DEBUG_TEMPROOT).
TEMP_ENV_VARS = ("TEMP", "TMP", "TMPDIR", "SQLITE_TMPDIR", "PYTEST_DEBUG_TEMPROOT")

_SYSTEM_TEMP: str | None = None   # the temp folder the process started with, noted before apply_temp_dir changes it


class TempDirError(RuntimeError):
    """``JASON_TEMP_DIR`` names a folder that cannot be used (its drive is missing or it cannot be written to)."""


def system_temp() -> Path:
    """The system's temp folder as the process found it, before ``apply_temp_dir`` moved it."""
    return Path(_SYSTEM_TEMP) if _SYSTEM_TEMP else Path(tempfile.gettempdir())


def temp_dir_setting(env_file: str | Path | None = None) -> str:
    """``JASON_TEMP_DIR`` from the environment or .env ("" when unset). Reads no profile."""
    return _env_value("JASON_TEMP_DIR", env_file)


def resolve_temp_dir(value: str) -> Path:
    """The folder ``value`` names: ``~`` expanded, a relative one taken from the data root's parent (the checkout)."""
    path = Path(os.path.expandvars(value)).expanduser()
    if not path.is_absolute():
        path = data_root().parent / path
    return path


def temp_dir_problem(path: Path) -> str:
    """Why ``path`` cannot be a temp folder, read without creating anything: its drive is missing, or no folder on the way
    to it can be written to. "" when it can."""
    if any(ord(c) < 32 for c in str(path)):
        return ("JASON_TEMP_DIR holds a control character: a backslash path in double quotes in .env is read as escapes "
                r"(\t, \n). Write it without quotes or with forward slashes (D:/scratch/jason/tmp).")
    anchor = path.anchor
    if anchor and not Path(anchor).exists():
        return (f"JASON_TEMP_DIR is {path}, but the drive {anchor} does not exist. Connect it or change JASON_TEMP_DIR "
                "in .env; jason will not fall back to the system temp folder.")
    nearest = next((p for p in (path, *path.parents) if p.exists()), None)
    if nearest is None or not nearest.is_dir() or not os.access(nearest, os.W_OK):
        return (f"JASON_TEMP_DIR is {path}, which cannot be created or written to. Change it in .env; jason will not "
                "fall back to the system temp folder.")
    return ""


def check_temp_dir(path: Path) -> Path:
    """Create ``path`` and prove it can be written to, or raise ``TempDirError`` saying why. A missing drive is an error,
    never a quiet fallback to the system drive."""
    problem = temp_dir_problem(path)
    if problem:
        raise TempDirError(problem)
    try:
        path.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryFile(dir=path):
            pass
    except OSError as exc:
        raise TempDirError(f"JASON_TEMP_DIR is {path}, which cannot be created or written to ({exc}). Change it in .env; "
                           "jason will not fall back to the system temp folder.") from exc
    return path


def apply_temp_dir(env_file: str | Path | None = None) -> Path | None:
    """Put ``JASON_TEMP_DIR`` into effect for this process and every program it starts: ``tempfile.tempdir`` and
    ``TEMP_ENV_VARS``. Unset changes nothing and returns None. Safe to call again. Called when a command, a server, or a
    script starts, never at import. Raises ``TempDirError`` when the folder cannot be used."""
    global _SYSTEM_TEMP
    value = temp_dir_setting(env_file)
    if not value:
        return None
    if _SYSTEM_TEMP is None:
        _SYSTEM_TEMP = tempfile.gettempdir()
    path = check_temp_dir(resolve_temp_dir(value))
    text = str(path)
    tempfile.tempdir = text
    for name in TEMP_ENV_VARS:
        os.environ[name] = text
    return path


def apply_temp_dir_or_exit(env_file: str | Path | None = None) -> Path | None:
    """``apply_temp_dir`` for a program's start (a server or a script): a folder that cannot be used ends it with the
    reason on standard error and exit code 2, not a traceback."""
    import sys

    try:
        return apply_temp_dir(env_file)
    except TempDirError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
