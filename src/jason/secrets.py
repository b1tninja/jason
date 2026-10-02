"""Keeper vault access via Commander Python SDK (keepersdk)."""

from __future__ import annotations

import base64
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from cryptography.hazmat.primitives.hashes import SHA1, SHA256, SHA512
from cryptography.hazmat.primitives.twofactor.totp import TOTP

from jason.config import (
    DEFAULT_PAYHOA_RECORD_UID,
    Settings,
    default_keeper_config_path,
)

PAYHOA_RECORD_UID = DEFAULT_PAYHOA_RECORD_UID


class KeeperAuthRequired(RuntimeError):
    """Non-interactive Keeper auth cannot proceed (password/MFA/device approval)."""


@dataclass(frozen=True)
class LoginCredentials:
    login: str
    password: str
    totp_code: str | None = None


@dataclass(frozen=True)
class PayhoaCredentials:
    email: str
    password: str
    totp_code: str


@dataclass(frozen=True)
class IdoxsCredentials:
    username: str
    password: str
    # Custom-field label (word in the security question) -> answer
    security_answers: dict[str, str] = field(default_factory=dict)


def keeper_config_path(path: str | Path | None = None) -> Path:
    """Resolve persistent Keeper config (default: ~/.keeper/keeper-config.json)."""
    if path is not None:
        p = Path(path)
        # Bare filename → prefer existing home config over a missing CWD file.
        if not p.is_absolute() and p.name == p.as_posix() and not p.is_file():
            home = default_keeper_config_path()
            if home.is_file():
                return home
        return p.expanduser()
    env = os.environ.get("KEEPER_CONFIG_PATH")
    if env:
        return Path(env).expanduser()
    return default_keeper_config_path()


def totp_code_from_uri(uri: str) -> str:
    """Generate a current TOTP code from an otpauth:// URI or bare secret."""
    secret = uri.strip()
    digits = 6
    period = 30
    algorithm = SHA1()

    if secret.startswith("otpauth://"):
        parsed = urlparse(secret)
        qs = parse_qs(parsed.query)
        if "secret" not in qs or not qs["secret"][0]:
            raise ValueError("otpauth URI missing secret")
        secret = qs["secret"][0]
        if qs.get("digits"):
            digits = int(qs["digits"][0])
        if qs.get("period"):
            period = int(qs["period"][0])
        algo_name = (qs.get("algorithm") or ["SHA1"])[0].upper()
        algorithm = {"SHA1": SHA1(), "SHA256": SHA256(), "SHA512": SHA512()}.get(
            algo_name, SHA1()
        )

    padded = secret.upper()
    padded += "=" * ((8 - len(padded) % 8) % 8)
    key = base64.b32decode(padded, casefold=True)
    code = TOTP(key, digits, algorithm, period, enforce_key_length=False).generate(
        time.time()
    )
    return code.decode("ascii") if isinstance(code, bytes) else str(code)


def _field_value(record: Any, field_type: str) -> str:
    from keepersdk.vault.vault_record import PasswordRecord, TypedRecord

    if isinstance(record, TypedRecord):
        field = record.get_typed_field(field_type)
        if field is None:
            return ""
        value = field.get_default_value(str)
        return value or ""
    if isinstance(record, PasswordRecord):
        if field_type == "login":
            return record.login or ""
        if field_type == "password":
            return record.password or ""
        if field_type == "oneTimeCode":
            return record.totp or ""
    return ""


def extract_login_fields(record: Any) -> tuple[str, str, str]:
    """Return (login, password, otpauth_uri) from a vault record."""
    return (
        _field_value(record, "login"),
        _field_value(record, "password"),
        _field_value(record, "oneTimeCode"),
    )


def _field_text_value(field: Any) -> str:
    if hasattr(field, "get_default_value"):
        val = field.get_default_value(str)
        if val:
            return str(val)
    for vattr in ("value", "values"):
        raw = getattr(field, vattr, None)
        if isinstance(raw, list) and raw:
            return str(raw[0])
        if raw:
            return str(raw)
    return ""


def extract_custom_fields(record: Any) -> dict[str, str]:
    """Return label -> value for custom/hidden fields on a Keeper record.

    For i-doxs, labels are words that appear in the portal security question.
    """
    out: dict[str, str] = {}

    def _ingest(field: Any) -> None:
        label = (
            getattr(field, "label", None)
            or (field.get("label") if isinstance(field, dict) else None)
            or ""
        )
        label = str(label).strip()
        if not label:
            return
        if isinstance(field, dict):
            vals = field.get("value") or field.get("values") or []
            if isinstance(vals, list) and vals:
                out[label] = str(vals[0])
            elif vals:
                out[label] = str(vals)
            return
        text = _field_text_value(field)
        if text:
            out[label] = text

    # Prefer custom/hidden fields only (not standard login/password).
    for attr in ("custom", "custom_fields"):
        value = getattr(record, attr, None)
        if value:
            for field in value:
                _ingest(field)

    # Also take labeled entries from fields[] (hidden custom often live there).
    for field in getattr(record, "fields", None) or []:
        label = getattr(field, "label", None)
        if not label:
            continue
        ftype = str(
            getattr(field, "type", None) or getattr(field, "field_type", "") or ""
        ).lower()
        if ftype in {"login", "password", "onetimecode", "url", "host"}:
            continue
        _ingest(field)

    rec_dict = getattr(record, "dict", None)
    if callable(rec_dict):
        try:
            rec_dict = rec_dict()
        except TypeError:
            rec_dict = None
    if isinstance(rec_dict, dict):
        for field in rec_dict.get("custom") or []:
            _ingest(field)
        for field in rec_dict.get("fields") or []:
            if not isinstance(field, dict):
                continue
            if not field.get("label"):
                continue
            ftype = str(field.get("type") or "").lower()
            if ftype in {"login", "password", "onetimecode", "url", "host"}:
                continue
            _ingest(field)
    return out


def _custom_field_value(record: Any, *labels: str) -> str:
    """Best-effort custom field lookup by label (case-insensitive)."""
    custom = extract_custom_fields(record)
    wanted = {label.lower() for label in labels}
    for label, value in custom.items():
        if label.lower() in wanted:
            return value
    return ""


def answer_for_security_question(
    question: str, answers: dict[str, str]
) -> str | None:
    """Pick an answer whose label appears as a word/substring in the question.

    Prefers the longest matching label to avoid short false positives.
    """
    if not question or not answers:
        return None
    q = question.lower()
    matches: list[tuple[int, str]] = []
    for label, answer in answers.items():
        token = label.strip()
        if not token or not answer:
            continue
        if token.lower() in q:
            matches.append((len(token), answer))
    if not matches:
        return None
    matches.sort(key=lambda item: item[0], reverse=True)
    return matches[0][1]


# Back-compat alias
extract_payhoa_fields = extract_login_fields


def credentials_from_record(
    record: Any, *, require_totp: bool = False
) -> LoginCredentials:
    login, password, totp_uri = extract_login_fields(record)
    if not login or not password:
        raise ValueError("Record missing login or password")
    totp_code: str | None = None
    if totp_uri:
        totp_code = totp_code_from_uri(totp_uri)
    elif require_totp:
        raise ValueError("Record missing oneTimeCode (TOTP)")
    return LoginCredentials(login=login, password=password, totp_code=totp_code)


def _persist_user_password(
    storage: Any, username: str, password: str, server: str | None
) -> None:
    """Store master password in persistent config for non-interactive reuse."""
    from keepersdk.authentication import configuration

    cfg = storage.get()
    existing = cfg.users().get(username)
    if existing:
        uc = configuration.UserConfiguration(existing)
    else:
        uc = configuration.UserConfiguration(username)
        if server:
            uc.server = server
    uc.password = password
    cfg.users().put(uc)
    storage.put(cfg)


def enable_persistent_login(auth: Any) -> None:
    """Enable Stay Logged In and register device data key (passwordless resume)."""
    from keepersdk.authentication import keeper_auth

    keeper_auth.set_user_setting(auth, "persistent_login", "1")
    keeper_auth.register_data_key_for_device(auth)
    # 30-day inactivity timer (minutes)
    keeper_auth.set_user_setting(auth, "logout_timer", str(60 * 24 * 30))


def login_to_vault(
    *,
    username: str | None = None,
    password: str | None = None,
    totp_code: str | None = None,
    config: str | Path | None = None,
    resume_session: bool = True,
    interactive: bool = False,
    tfa_duration: Any = None,
    persist_password: bool = True,
):
    """Authenticate to Keeper and return (KeeperAuth, LoginAuth).

    Non-interactive mode (default) never calls input()/getpass(). It uses the
    persistent config at ~/.keeper/keeper-config.json (device + optional stored
    password). If more input is required, raises KeeperAuthRequired — run
    ``jason login`` in a real terminal window.
    """
    from keepersdk.authentication.configuration import JsonConfigurationStorage
    from keepersdk.authentication.endpoint import KeeperEndpoint
    from keepersdk.authentication.login_auth import (
        DeviceApprovalChannel,
        LoginAuth,
        LoginStepConnected,
        LoginStepDeviceApproval,
        LoginStepError,
        LoginStepPassword,
        LoginStepTwoFactor,
        TwoFactorChannel,
        TwoFactorDuration,
    )

    # Forever maximizes chance of passwordless resume on later runs.
    if tfa_duration is None:
        tfa_duration = (
            TwoFactorDuration.Forever
            if interactive
            else TwoFactorDuration.Every30Days
        )

    config_path = keeper_config_path(config)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    storage = JsonConfigurationStorage.from_file(str(config_path))
    endpoint = KeeperEndpoint(storage)
    login = LoginAuth(endpoint)
    login.resume_session = resume_session

    stored = storage.get()
    username = (
        username
        or os.environ.get("KEEPER_USERNAME")
        or stored.last_login
        or ""
    )
    password = password or os.environ.get("KEEPER_PASSWORD") or ""
    totp_code = totp_code or os.environ.get("KEEPER_TOTP") or ""

    # Password saved in persistent config (if any).
    if not password and username:
        uc = stored.users().get(username)
        if uc and uc.password:
            password = uc.password

    if interactive and not username:
        username = input("Keeper username (email): ").strip()
    if not username:
        raise KeeperAuthRequired(
            "Keeper username required. Set keeper_username in .env or run "
            "`jason login` in a terminal."
        )

    passwords: list[str] = []
    if password:
        passwords.append(password)

    login.login(username, *passwords)
    used_password: str | None = password or None

    for _ in range(20):
        step = login.login_step

        if isinstance(step, LoginStepConnected):
            auth = step.take_keeper_auth()
            # Stay Logged In: required for clone_code resume without password.
            try:
                enable_persistent_login(auth)
            except Exception:
                if interactive:
                    print(
                        "Warning: could not enable persistent_login; "
                        "non-interactive resume may still need a password."
                    )
            if (
                interactive
                and persist_password
                and used_password
                and username
            ):
                _persist_user_password(
                    storage,
                    username,
                    used_password,
                    stored.last_server or endpoint.server,
                )
            return auth, login

        if isinstance(step, LoginStepError):
            raise RuntimeError(
                f"Keeper login failed: {step.code}: {step.message}"
            )

        if isinstance(step, LoginStepPassword):
            pwd = password
            if not pwd and login.context and login.context.passwords:
                pwd = login.context.passwords[0]
            if interactive and not pwd:
                import getpass

                pwd = getpass.getpass("Keeper master password: ")
            if not pwd:
                raise KeeperAuthRequired(
                    f"Keeper passwordless session not active (config: {config_path}). "
                    "In a terminal run: jason login"
                    "  (enables Stay Logged In + device data-key registration). "
                    "Or set keeper_password in .env."
                )
            used_password = pwd
            step.verify_password(pwd)
            continue

        if isinstance(step, LoginStepTwoFactor):
            channels = list(step.get_channels())
            auth_channel = next(
                (
                    c
                    for c in channels
                    if c.channel_type == TwoFactorChannel.Authenticator
                ),
                channels[0] if channels else None,
            )
            if auth_channel is None:
                raise RuntimeError(
                    "Keeper login requires 2FA but no channels available"
                )

            code = totp_code
            if interactive and not code:
                code = input(
                    f"Keeper 2FA code ({auth_channel.channel_type.name}): "
                ).strip()
            if not code:
                raise KeeperAuthRequired(
                    "Keeper 2FA code required. Run `jason login` in a terminal "
                    "or set KEEPER_TOTP."
                )
            step.duration = tfa_duration
            step.send_code(auth_channel.channel_uid, code)
            continue

        if isinstance(step, LoginStepDeviceApproval):
            if not interactive:
                raise KeeperAuthRequired(
                    "Keeper device approval required. Run `jason login` in a "
                    f"terminal window (config: {config_path})."
                )
            print("Device approval required.")
            print("  1) Approve in the Keeper mobile/desktop app, then press Enter")
            print("  2) Or enter an email/2FA code when prompted")
            try:
                step.send_push(DeviceApprovalChannel.KeeperPush)
                print("Sent Keeper Push approval request.")
            except Exception:
                pass
            choice = input(
                "Press Enter after approving, or type a code to submit: "
            ).strip()
            if choice:
                for channel in (
                    DeviceApprovalChannel.TwoFactor,
                    DeviceApprovalChannel.Email,
                ):
                    try:
                        step.send_code(channel, choice)
                        break
                    except Exception:
                        continue
            else:
                step.resume()
            continue

        time.sleep(0.25)

    raise RuntimeError("Keeper login did not complete")


class VaultSession:
    """Lazy Keeper vault session: one login/sync, multiple record loads."""

    def __init__(
        self,
        *,
        username: str | None = None,
        password: str | None = None,
        totp_code: str | None = None,
        config: str | Path | None = None,
        interactive: bool = False,
    ) -> None:
        self._username = username
        self._password = password
        self._totp_code = totp_code
        self._config = config
        self._interactive = interactive
        self._auth: Any = None
        self._login: Any = None
        self._vault: Any = None

    @classmethod
    def from_settings(
        cls, settings: Settings, *, interactive: bool = False
    ) -> VaultSession:
        return cls(
            username=settings.keeper_username or None,
            password=settings.keeper_password or None,
            config=settings.keeper_config,
            interactive=interactive,
        )

    def open(self) -> None:
        if self._vault is not None:
            return
        from keepersdk.vault.memory_storage import InMemoryVaultStorage
        from keepersdk.vault.vault_online import get_vault_online

        self._auth, self._login = login_to_vault(
            username=self._username,
            password=self._password,
            totp_code=self._totp_code,
            config=self._config,
            interactive=self._interactive,
        )
        self._vault = get_vault_online(self._auth, InMemoryVaultStorage())
        self._vault.auto_sync = False
        self._vault.sync_down()

    def load_record(self, record_uid: str) -> Any:
        self.open()
        record = self._vault.vault_data.load_record(record_uid)
        if record is None:
            raise LookupError(f"No Keeper record for UID {record_uid}")
        return record

    def get_credentials(
        self, record_uid: str, *, require_totp: bool = False
    ) -> LoginCredentials:
        return credentials_from_record(
            self.load_record(record_uid), require_totp=require_totp
        )

    def get_secret(self, record_uid: str) -> str:
        """The password field of a record, which is where an API key is kept."""
        return _field_value(self.load_record(record_uid), "password")

    def create_login_record(
        self,
        title: str,
        *,
        password: str,
        login: str = "",
        url: str = "",
        notes: str = "",
        folder_uid: str | None = None,
        custom: dict[str, str] | None = None,
    ) -> str:
        """Create a typed login record in the vault and return its UID.

        The secret goes in the password field, so ``get_secret`` reads it
        back the same way for every service. The value is never logged.
        ``custom`` adds labeled text fields (an app's account id, client id).
        """
        from keepersdk.vault.record_management import add_record_to_folder
        from keepersdk.vault.vault_record import TypedField, TypedRecord

        self.open()
        record = TypedRecord()
        record.record_type = "login"
        record.title = title
        record.notes = notes
        for field_type, value in (("login", login), ("password", password), ("url", url)):
            field = TypedField.create_field(field_type)
            field.value = [value] if value else []
            record.fields.append(field)
        for label, value in (custom or {}).items():
            field = TypedField.create_field("text", label)
            field.value = [value] if value else []
            record.custom.append(field)
        return add_record_to_folder(self._vault, record, folder_uid)

    def close(self) -> None:
        if self._vault is not None:
            self._vault.close()
            self._vault = None
        if self._auth is not None:
            self._auth.close()
            self._auth = None
        if self._login is not None:
            self._login.close()
            self._login = None

    def __enter__(self) -> VaultSession:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def load_vault_record(
    record_uid: str,
    *,
    username: str | None = None,
    password: str | None = None,
    totp_code: str | None = None,
    config: str | Path | None = None,
    interactive: bool = False,
):
    """Login, sync vault, load a record, and close the session."""
    with VaultSession(
        username=username,
        password=password,
        totp_code=totp_code,
        config=config,
        interactive=interactive,
    ) as session:
        return session.load_record(record_uid)


def get_login_credentials(
    record_uid: str,
    *,
    settings: Settings | None = None,
    username: str | None = None,
    password: str | None = None,
    totp_code: str | None = None,
    config: str | Path | None = None,
    interactive: bool = False,
    require_totp: bool = False,
) -> LoginCredentials:
    if settings is not None:
        username = username or settings.keeper_username or None
        password = password or settings.keeper_password or None
        config = config or settings.keeper_config
    with VaultSession(
        username=username,
        password=password,
        totp_code=totp_code,
        config=config,
        interactive=interactive,
    ) as session:
        return session.get_credentials(record_uid, require_totp=require_totp)


def get_payhoa_credentials(
    *,
    config: str | Path | None = None,
    record_uid: str = PAYHOA_RECORD_UID,
    username: str | None = None,
    password: str | None = None,
    totp_code: str | None = None,
    interactive: bool = False,
    settings: Settings | None = None,
) -> PayhoaCredentials:
    """Load PayHOA email, password, and a fresh TOTP code from the vault."""
    if settings is not None:
        record_uid = settings.payhoa_record_uid
        username = username or settings.keeper_username or None
        password = password or settings.keeper_password or None
        config = config or settings.keeper_config
    if not record_uid:
        raise ValueError("payhoa_record_uid is not set; put the PayHOA login's Keeper record UID in .env")
    creds = get_login_credentials(
        record_uid,
        username=username,
        password=password,
        totp_code=totp_code,
        config=config,
        interactive=interactive,
        require_totp=True,
    )
    assert creds.totp_code is not None
    return PayhoaCredentials(
        email=creds.login,
        password=creds.password,
        totp_code=creds.totp_code,
    )


def get_accela_credentials(
    *,
    config: str | Path | None = None,
    record_uid: str | None = None,
    username: str | None = None,
    password: str | None = None,
    totp_code: str | None = None,
    interactive: bool = False,
    settings: Settings | None = None,
) -> LoginCredentials:
    """Load Sacramento Citizen Access login and password from Keeper."""
    if settings is not None:
        record_uid = record_uid or settings.accela_record_uid
        username = username or settings.keeper_username or None
        password = password or settings.keeper_password or None
        config = config or settings.keeper_config
    if not record_uid:
        raise LookupError("accela_record_uid is not set")
    return get_login_credentials(
        record_uid,
        username=username,
        password=password,
        totp_code=totp_code,
        config=config,
        interactive=interactive,
    )


def get_vendor_credentials(
    key: str,
    *,
    settings: Settings,
    interactive: bool = False,
) -> LoginCredentials:
    """A vendor portal's login from the Keeper record set as ``<key>_record_uid``."""
    record_uid = settings.record_uid(key)
    if not record_uid:
        raise LookupError(f"{key}_record_uid is not set in .env")
    return get_login_credentials(
        record_uid,
        username=settings.keeper_username or None,
        password=settings.keeper_password or None,
        config=settings.keeper_config,
        interactive=interactive,
    )


def get_idoxs_credentials(
    *,
    config: str | Path | None = None,
    record_uid: str | None = None,
    username: str | None = None,
    password: str | None = None,
    totp_code: str | None = None,
    interactive: bool = False,
    settings: Settings | None = None,
) -> IdoxsCredentials:
    """Load City of Sacramento i-doxs portal credentials from Keeper."""
    from jason.config import DEFAULT_IDOXS_RECORD_UID

    if settings is not None:
        record_uid = record_uid or settings.idoxs_record_uid
        username = username or settings.keeper_username or None
        password = password or settings.keeper_password or None
        config = config or settings.keeper_config
    record_uid = record_uid or DEFAULT_IDOXS_RECORD_UID
    if not record_uid:
        raise ValueError("idoxs_record_uid is not set; put the i-doxs login's Keeper record UID in .env")

    if settings is not None:
        username = username or settings.keeper_username or None
        password = password or settings.keeper_password or None
        config = config or settings.keeper_config

    with VaultSession(
        username=username,
        password=password,
        totp_code=totp_code,
        config=config,
        interactive=interactive,
    ) as session:
        record = session.load_record(record_uid)
        creds = credentials_from_record(record, require_totp=False)
        answers = extract_custom_fields(record)
        # Drop empty values
        answers = {k: v for k, v in answers.items() if k and v}
        return IdoxsCredentials(
            username=creds.login,
            password=creds.password,
            security_answers=answers,
        )
