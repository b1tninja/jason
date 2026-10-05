"""Where jason reads and writes, and how much room each drive has (``jason storage``).

A rebuilt index, OCR page images, and a model's files are large. The system drive is often the small one, so this lists
each place jason keeps something: its path, its drive, the drive's free space, and the size of what jason keeps there.
``problems`` names what would fill a drive: a place on a drive short of room, scratch (the temp folder) landing on the
small drive when ``JASON_TEMP_DIR`` is unset, and a ``JASON_TEMP_DIR`` that cannot be used. It reads only, and it reads
no file's contents: the secrets folder and the Keeper config are named by path and drive.

The free-space function is a parameter, so a test can say a drive is full.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

GB = 1024 ** 3
DEFAULT_MIN_FREE_GB = 20.0

# The data directory's big subfolders, as (label, path inside the data directory).
DATA_FOLDERS: tuple[tuple[str, str], ...] = (
    ("retrieval index (index.db)", "retrieval/index.db"),
    ("retrieval vectors", "retrieval/vectors"),
    ("library", "library"),
    ("mail", "mail"),
    ("gmail files", "gmail"),
    ("cases", "cases"),
    ("reports", "reports"),
    ("drive", "drive"),
    ("authorities", "authorities"),
)


@dataclass
class Place:
    """One place jason reads or writes."""

    name: str
    path: str
    drive: str
    free: int | None            # bytes free on its drive; None when the drive cannot be read
    size: int | None = None     # bytes jason keeps there; None when not measured
    note: str = ""
    exists: bool = True

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def drive_of(path: Path | str) -> str:
    """The drive (``D:``) or share a path is on; ``/`` on a system with neither."""
    p = Path(path)
    return p.drive or p.anchor or "/"


def free_bytes(path: Path | str) -> int | None:
    """Free bytes on the drive holding ``path`` (its nearest folder that exists); None when it cannot be read."""
    p = Path(path)
    for candidate in (p, *p.parents):
        try:
            if candidate.exists():
                return shutil.disk_usage(candidate).free
        except OSError:
            continue
    return None


def folder_size(path: Path | str) -> int:
    """Bytes in a file or in every file below a folder; an entry that cannot be read counts as nothing."""
    p = Path(path)
    try:
        if p.is_file():
            return p.stat().st_size
    except OSError:
        return 0
    total = 0
    stack = [str(p)]
    while stack:
        try:
            with os.scandir(stack.pop()) as entries:
                for entry in entries:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
                        elif entry.is_file(follow_symlinks=False):
                            total += entry.stat(follow_symlinks=False).st_size
                    except OSError:
                        continue
        except OSError:
            continue
    return total


def _env_path(name: str, default: Path) -> Path:
    value = (os.environ.get(name) or "").strip().strip('"')
    return Path(value) if value else default


def _asspy_home() -> Path | None:
    try:
        from asspy.paths import home

        from jason import asspy_home

        asspy_home.apply()
        return home()
    except Exception:  # noqa: BLE001 - asspy not installed: nothing to report
        return None


def report(data_dir: Path, *, env_file: str | Path | None = None, sizes: bool = True,
           free: Callable[[Path], int | None] | None = None, min_free_gb: float = DEFAULT_MIN_FREE_GB) -> dict[str, Any]:
    """Every place jason keeps something, the temp setting, and the problems found, as a dict (``lines`` prints it)."""
    from jason import config
    from jason.locks import lock_dir

    free_of = free or free_bytes
    data_dir = Path(data_dir)

    def place(name: str, path: Path, *, measure: bool = False, note: str = "") -> Place:
        return Place(name=name, path=str(path), drive=drive_of(path), free=free_of(path),
                     size=folder_size(path) if measure and sizes and path.exists() else None, note=note, exists=path.exists())

    # The temp folder: the one JASON_TEMP_DIR names, else the system's.
    setting = config.temp_dir_setting(env_file)
    temp_error = ""
    configured: Path | None = None
    if setting:
        configured = config.resolve_temp_dir(setting)
        temp_error = config.temp_dir_problem(configured)
    system = config.system_temp()
    if configured is not None and not temp_error:
        temp = place("temp (JASON_TEMP_DIR)", configured, measure=True, note="scratch, OCR page images, SQLite spill, pytest")
    elif configured is not None:
        temp = place("temp (JASON_TEMP_DIR, unusable)", configured, note=temp_error)
    else:
        temp = place("temp (system)", system, measure=True, note="JASON_TEMP_DIR is unset")

    places: list[Place] = [place("data directory", data_dir, measure=True)]
    for label, rel in DATA_FOLDERS:
        places.append(place(f"  {label}", data_dir / rel, measure=True))
    places.append(temp)
    asspy = _asspy_home()
    if asspy is not None:
        places.append(place("ASSPY_HOME (county index cache)", asspy, measure=True))
    places.append(place("Ollama models (OLLAMA_MODELS)", _env_path("OLLAMA_MODELS", Path.home() / ".ollama" / "models"), measure=True))
    hf = _env_path("HF_HOME", Path(os.environ.get("HF_HUB_CACHE") or Path.home() / ".cache" / "huggingface"))
    places.append(place("Hugging Face cache (HF_HOME)", hf, measure=True))
    places.append(place("locks", lock_dir(), note="held while a model or a store is in use"))
    try:
        from jason.config import Settings

        settings = Settings.load(env_file)
        token = Path(settings.google_oauth_token_file).resolve()
        places.append(place("Google token", token, note="path and drive only"))
        places.append(place("Keeper config", Path(settings.keeper_config), note="path and drive only"))
    except Exception:  # noqa: BLE001 - settings that cannot be read leave these two out
        pass

    out: dict[str, Any] = {
        "places": [p.as_dict() for p in places],
        "temp": {"configured": bool(setting), "setting": setting, "path": temp.path, "systemTemp": str(system),
                 "systemTempDrive": drive_of(system), "systemTempFree": free_of(system), "error": temp_error},
        "minFreeGb": min_free_gb,
    }
    out["problems"] = problems(out, free_of(data_dir), drive_of(data_dir), min_free_gb)
    return out


def problems(rep: dict[str, Any], data_free: int | None, data_drive: str, min_free_gb: float = DEFAULT_MIN_FREE_GB) -> list[str]:
    """What would fill a drive, one line each; nothing when the places are all roomy."""
    floor = min_free_gb * GB
    found: list[str] = []
    temp = rep["temp"]
    if temp["error"]:
        found.append(temp["error"])
    low: dict[str, tuple[int, list[str]]] = {}
    for p in rep["places"]:
        if p["free"] is not None and p["free"] < floor:
            low.setdefault(p["drive"], (p["free"], []))[1].append(p["name"].strip())
    for drive, (avail, names) in low.items():
        found.append(f"{drive} has {avail / GB:.1f} GB free, under {min_free_gb:g} GB, and jason keeps {', '.join(names)} there")
    if not temp["configured"]:
        sys_drive, sys_free = temp["systemTempDrive"], temp["systemTempFree"]
        if sys_drive == data_drive and data_free is not None and data_free < floor:
            found.append(f"the system temp folder ({temp['systemTemp']}) is on {sys_drive}, the data directory's drive, "
                         f"which has {data_free / GB:.1f} GB free: scratch and the index build's sorts fill it. "
                         "Set JASON_TEMP_DIR to a folder on a roomier drive")
        if sys_free is not None and data_free is not None and sys_free < data_free:
            found.append(f"JASON_TEMP_DIR is unset, and the system temp folder ({temp['systemTemp']}) is on {sys_drive} with "
                         f"{sys_free / GB:.1f} GB free, less than the data directory's drive {data_drive} "
                         f"({data_free / GB:.1f} GB free). Set JASON_TEMP_DIR (docs/setup.md, Where jason writes)")
    return found


def _size(n: int | None) -> str:
    return "" if n is None else f"{n / GB:.2f} GB" if n >= GB / 10 else f"{n / 1024 ** 2:.1f} MB"


def lines(rep: dict[str, Any]) -> list[str]:
    """The report as text: a place a line, its drive, the drive's free space, and what jason keeps there."""
    out = []
    for p in rep["places"]:
        free = "free ?" if p["free"] is None else f"free {p['free'] / GB:.1f} GB"
        size = f"  holds {_size(p['size'])}" if p["size"] is not None else ""
        gone = "" if p["exists"] else "  (not there yet)"
        note = f"  [{p['note']}]" if p["note"] else ""
        out.append(f"{p['name']}\n    {p['path']}   {p['drive']}  {free}{size}{gone}{note}")
    out.append("")
    out += [f"! {m}" for m in rep["problems"]] or [f"every place has at least {rep['minFreeGb']:g} GB free"]
    return out
