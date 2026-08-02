"""Jason settings loaded from .env and environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_PAYHOA_ORG_ID = 27889
DEFAULT_PAYHOA_RECORD_UID = ""
DEFAULT_IDOXS_RECORD_UID = ""
DEFAULT_SMUD_CATEGORY_ID = 1245405  # Electricity (SMUD) from HAR
DEFAULT_IDOXS_CATEGORY_ID = 1245485  # City of Sacramento Utilities from HAR


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
    sibling = Path(__file__).resolve().parents[3] / "smud" / "data" / "smud.db"
    if sibling.is_file():
        return sibling
    return Path("data") / "smud.db"


def _default_idoxs_db() -> Path:
    sibling = Path(__file__).resolve().parents[3] / "i-doxs" / "data" / "idoxs.db"
    if sibling.is_file():
        return sibling
    return Path("data") / "idoxs.db"


@dataclass(frozen=True)
class Settings:
    keeper_username: str
    payhoa_record_uid: str
    smud_record_uid: str
    idoxs_record_uid: str
    keeper_password: str = ""
    keeper_config: Path = Path(DEFAULT_KEEPER_CONFIG)
    payhoa_org_id: int = DEFAULT_PAYHOA_ORG_ID
    smud_db: Path = Path("data/smud.db")
    smud_bills_dir: Path = Path("data/bills")
    smud_category_id: int | None = DEFAULT_SMUD_CATEGORY_ID
    idoxs_db: Path = Path("data/idoxs.db")
    idoxs_bills_dir: Path = Path("data/idoxs-bills")
    idoxs_category_id: int | None = DEFAULT_IDOXS_CATEGORY_ID
    env_path: Path | None = None

    @classmethod
    def load(cls, path: str | Path | None = None) -> Settings:
        from dotenv import dotenv_values

        env_path = resolve_env_path(path)
        values: dict[str, str | None] = {}
        if env_path.is_file():
            values = dict(dotenv_values(env_path))

        keeper_username = _get(
            values, "keeper_username", "KEEPER_USERNAME", default=""
        )
        payhoa_record_uid = _get(
            values,
            "payhoa_record_uid",
            "PAYHOA_RECORD_UID",
            default=DEFAULT_PAYHOA_RECORD_UID,
        )
        smud_record_uid = _get(
            values, "smud_record_uid", "SMUD_RECORD_UID", default=""
        )
        idoxs_record_uid = _get(
            values,
            "idoxs_record_uid",
            "IDOXS_RECORD_UID",
            default=DEFAULT_IDOXS_RECORD_UID,
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
            default=str(DEFAULT_PAYHOA_ORG_ID),
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
            default=str(DEFAULT_SMUD_CATEGORY_ID),
        )
        smud_category_id: int | None
        try:
            smud_category_id = int(cat_raw) if cat_raw else None
        except ValueError:
            smud_category_id = DEFAULT_SMUD_CATEGORY_ID

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
            default=str(DEFAULT_IDOXS_CATEGORY_ID),
        )
        idoxs_category_id: int | None
        try:
            idoxs_category_id = int(idoxs_cat_raw) if idoxs_cat_raw else None
        except ValueError:
            idoxs_category_id = DEFAULT_IDOXS_CATEGORY_ID

        return cls(
            keeper_username=keeper_username,
            payhoa_record_uid=payhoa_record_uid,
            smud_record_uid=smud_record_uid,
            idoxs_record_uid=idoxs_record_uid,
            keeper_password=keeper_password,
            keeper_config=keeper_config,
            payhoa_org_id=int(org_raw),
            smud_db=smud_db,
            smud_bills_dir=smud_bills_dir,
            smud_category_id=smud_category_id,
            idoxs_db=idoxs_db,
            idoxs_bills_dir=idoxs_bills_dir,
            idoxs_category_id=idoxs_category_id,
            env_path=env_path if env_path.is_file() else None,
        )
