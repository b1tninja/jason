"""The local AI stack as jason depends on it: Ollama and its GPU, the models loaded, AnythingLLM, and Windows' memory.

jason's readers, classifier, and OCR, and AnythingLLM's chat, share one model on one card (``DEFAULT_MODEL`` in
``jason.community.ollama_extractor``). Three things have gone wrong on this machine, each silently:

- after a GPU driver change Ollama keeps running on the CPU until it is restarted, because it looks for GPUs only when
  it starts (September 30, 2026: the 9B model ran at 12.7 tokens a second instead of 136);
- a model held in video memory still counts against Windows' commit limit (RAM plus the page files), so two models at
  once can exhaust it and the model server dies mid-request (``std::bad_alloc``);
- a page file set in System Properties applies only at the next boot, so the limit stays where it was.

``status`` reads each (Ollama's API and its server log, AnythingLLM's ping and its model settings, the kernel's commit
figures and active page files, the registry's configured ones, and the holders of jason's locks) and ``findings`` says
what is wrong and what fixes it. ``preflight`` is the same check before a job that needs a model: it raises
``LocalAIUnavailable`` rather than let the job land on the CPU or run the machine out of memory. ``restart_ollama``
and ``unload`` act, and only when a person asks (``jason local-ai --restart-ollama --yes``). jason changes no setting
of Ollama, AnythingLLM, the driver, or Windows.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from jason.community.ollama_extractor import DEFAULT_MODEL, OLLAMA_URL
from jason.locks import Resource, hold, holders

ANYTHINGLLM_URL = "http://localhost:3001"
GB = 1 << 30
COMMIT_MARGIN = 4 * GB           # headroom to keep free beyond a model about to load
ANYTHINGLLM_KEYS = ("LLM_PROVIDER", "OLLAMA_MODEL_PREF", "OLLAMA_MODEL_TOKEN_LIMIT", "EMBEDDING_ENGINE", "EMBEDDING_MODEL_PREF")


class LocalAIUnavailable(RuntimeError):
    """The model server is down, running on the CPU, or would run the machine out of memory; nothing was sent."""


def _get(url: str, timeout: float = 5) -> dict[str, Any]:
    with urlopen(Request(url), timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8") or "{}")


def _post(url: str, body: dict[str, Any], timeout: float = 60) -> dict[str, Any]:
    request = Request(url, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8") or "{}")


def _ollama_log() -> Path:
    return Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "Ollama" / "server.log"


def gpu_discovery(log: Path | None = None) -> list[dict[str, str]]:
    """The devices Ollama found when it last started (its server log's "inference compute" lines after the last
    "server config"): library (CUDA, Vulkan, cpu), description, driver, and total memory."""
    path = log or _ollama_log()
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    start = max((k for k, line in enumerate(lines) if 'msg="server config"' in line), default=0)
    found = []
    for line in lines[start:]:
        if 'msg="inference compute"' in line:
            fields = dict(re.findall(r'(\w+)=("[^"]*"|\S+)', line))
            found.append({k: fields.get(k, "").strip('"') for k in ("library", "description", "driver", "total", "available")})
    return found


def _windows_memory() -> dict[str, Any]:
    """Commit limit and use, and the active page files, from the kernel; the configured page files from the registry."""
    if sys.platform != "win32":
        return {}
    import ctypes
    from ctypes import wintypes

    class PerformanceInformation(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("CommitTotal", ctypes.c_size_t), ("CommitLimit", ctypes.c_size_t),
                    ("CommitPeak", ctypes.c_size_t), ("PhysicalTotal", ctypes.c_size_t), ("PhysicalAvailable", ctypes.c_size_t),
                    ("SystemCache", ctypes.c_size_t), ("KernelTotal", ctypes.c_size_t), ("KernelPaged", ctypes.c_size_t),
                    ("KernelNonpaged", ctypes.c_size_t), ("PageSize", ctypes.c_size_t), ("HandleCount", wintypes.DWORD),
                    ("ProcessCount", wintypes.DWORD), ("ThreadCount", wintypes.DWORD)]

    info = PerformanceInformation()
    info.cb = ctypes.sizeof(info)
    out: dict[str, Any] = {}
    if ctypes.windll.psapi.GetPerformanceInfo(ctypes.byref(info), info.cb):
        page = info.PageSize
        out.update(commitLimit=info.CommitLimit * page, committed=info.CommitTotal * page, ram=info.PhysicalTotal * page,
                   ramFree=info.PhysicalAvailable * page)
    active = []
    size = 1 << 16
    buffer = ctypes.create_string_buffer(size)
    returned = wintypes.ULONG()
    if ctypes.windll.ntdll.NtQuerySystemInformation(18, buffer, size, ctypes.byref(returned)) == 0:
        offset = 0
        pointer = ctypes.sizeof(ctypes.c_void_p)
        while True:
            base = ctypes.addressof(buffer) + offset
            nxt, total, used = (ctypes.c_uint32.from_address(base + k).value for k in (0, 4, 8))
            length = ctypes.c_uint16.from_address(base + 16).value
            name_at = ctypes.c_void_p.from_address(base + 16 + pointer).value
            name = ctypes.wstring_at(name_at, length // 2) if name_at else ""
            active.append({"file": name.replace("\\??\\", ""), "size": total * 4096, "used": used * 4096})
            if not nxt:
                break
            offset += nxt
    out["pageFiles"] = active
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management") as key:
            out["pageFilesConfigured"] = list(winreg.QueryValueEx(key, "PagingFiles")[0])
            try:
                out["pagefileOnOsVolume"] = int(winreg.QueryValueEx(key, "PagefileOnOsVolume")[0])
            except OSError:
                out["pagefileOnOsVolume"] = 0
            try:
                out["tempPageFile"] = int(winreg.QueryValueEx(key, "TempPageFile")[0])
            except OSError:
                out["tempPageFile"] = 0
    except OSError:
        out["pageFilesConfigured"] = []
    return out


def _processes() -> list[dict[str, Any]]:
    """Every process's id, parent id, and image name (Windows' process snapshot)."""
    if sys.platform != "win32":
        return []
    import ctypes
    from ctypes import wintypes

    class ProcessEntry(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                    ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                    ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", ctypes.c_long), ("dwFlags", wintypes.DWORD),
                    ("szExeFile", ctypes.c_wchar * 260)]

    kernel = ctypes.windll.kernel32
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    snap = kernel.CreateToolhelp32Snapshot(0x2, 0)
    out = []
    entry = ProcessEntry()
    entry.dwSize = ctypes.sizeof(entry)
    ok = kernel.Process32FirstW(snap, ctypes.byref(entry))
    while ok:
        out.append({"pid": entry.th32ProcessID, "parent": entry.th32ParentProcessID, "name": entry.szExeFile})
        ok = kernel.Process32NextW(snap, ctypes.byref(entry))
    kernel.CloseHandle(snap)
    return out


def orphan_servers(procs: list[dict[str, Any]] | None = None) -> list[int]:
    """Model servers (llama-server.exe) whose Ollama is gone: nothing can reach them, and each keeps its model's memory."""
    procs = _processes() if procs is None else procs
    ollama = {p["pid"] for p in procs if p["name"].lower() == "ollama.exe"}
    return [p["pid"] for p in procs if p["name"].lower() == "llama-server.exe" and p["parent"] not in ollama]


def _anythingllm_settings() -> dict[str, str]:
    """AnythingLLM desktop's model choices from its settings file; only the keys named here are read (the file also
    holds keys and secrets)."""
    path = Path(os.environ.get("APPDATA") or Path.home()) / "anythingllm-desktop" / "storage" / ".env"
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    found = {}
    for key in ANYTHINGLLM_KEYS:
        m = re.search(rf"^{key}=['\"]?([^'\"\r\n]*)", text, re.M)
        if m:
            found[key] = m.group(1)
    return found


def status(*, ollama_url: str = OLLAMA_URL, anythingllm_url: str = ANYTHINGLLM_URL) -> dict[str, Any]:
    out: dict[str, Any] = {"ollama": {"url": ollama_url, "up": False}, "anythingllm": {"url": anythingllm_url, "up": False}}
    try:
        out["ollama"]["version"] = _get(f"{ollama_url}/api/version").get("version", "")
        out["ollama"]["up"] = True
        out["ollama"]["loaded"] = [{"name": m["name"], "size": m.get("size", 0), "vram": m.get("size_vram", 0),
                                    "expires": m.get("expires_at", "")} for m in _get(f"{ollama_url}/api/ps").get("models", [])]
        out["ollama"]["installed"] = {m["name"]: m.get("size", 0) for m in _get(f"{ollama_url}/api/tags").get("models", [])}
    except (OSError, ValueError):
        pass
    out["ollama"]["devices"] = gpu_discovery()
    try:
        out["anythingllm"]["up"] = bool(_get(f"{anythingllm_url}/api/ping").get("online"))
    except (OSError, ValueError):
        pass
    out["anythingllm"]["settings"] = _anythingllm_settings()
    out["jasonModel"] = DEFAULT_MODEL
    out["memory"] = _windows_memory()
    out["ollama"]["orphans"] = orphan_servers()
    out["locks"] = holders()
    out["findings"] = findings(out)
    return out


def _gb(n: float) -> str:
    return f"{n / GB:.1f} GB"


def findings(s: dict[str, Any]) -> list[str]:
    """What is wrong in a ``status``, each with what fixes it."""
    out = []
    ollama = s.get("ollama", {})
    if not ollama.get("up"):
        out.append("Ollama is not answering: start the Ollama app")
    devices = ollama.get("devices") or []
    if ollama.get("up") and devices and not any(d.get("library") in ("CUDA", "ROCm") for d in devices):
        out.append("Ollama found no GPU when it started (running on " + ", ".join(d.get("description") or d.get("library", "")
                   for d in devices) + "): after a driver change, restart it (jason local-ai --restart-ollama --yes); "
                   "if the GPU is still missing, check it in Device Manager")
    for m in ollama.get("loaded") or []:
        if m["size"] and m["vram"] < m["size"] * 0.95:
            out.append(f"{m['name']} is {100 - round(100 * m['vram'] / m['size'])}% on the CPU: it does not fit beside what "
                       "else is loaded, or Ollama is not using the GPU")
    if ollama.get("orphans"):
        out.append(f"model servers left running by an Ollama that is gone (process {', '.join(map(str, ollama['orphans']))}): "
                   "each holds its model's memory; restart Ollama (jason local-ai --restart-ollama --yes), which stops them")
    names = [m["name"] for m in ollama.get("loaded") or []]
    settings = s.get("anythingllm", {}).get("settings") or {}
    chat = settings.get("OLLAMA_MODEL_PREF", "")
    if chat and s.get("jasonModel") and chat != s["jasonModel"]:
        out.append(f"AnythingLLM chats with {chat} and jason reads with {s['jasonModel']}: the two swap in and out of the GPU; "
                   "set them to the same model")
    extra = [n for n in names if n not in (s.get("jasonModel"), chat, settings.get("EMBEDDING_MODEL_PREF", ""))]
    if extra:
        out.append(f"loaded outside the plan: {', '.join(extra)} (unload with jason local-ai --unload NAME --yes)")
    mem = s.get("memory") or {}
    if mem.get("commitLimit"):
        free = mem["commitLimit"] - mem["committed"]
        if free < 8 * GB:
            out.append(f"Windows commit is nearly full ({_gb(free)} of {_gb(mem['commitLimit'])} free); a model loading now "
                       "may crash the model server: raise the page file, or unload a model")
        active = {p["file"].lower() for p in mem.get("pageFiles") or []}
        configured = {c.split()[0].lower() for c in mem.get("pageFilesConfigured") or [] if c.split() and not c.startswith("?:")}
        missing = sorted(c for c in configured if c not in active)
        off_os = [c for c in missing if not c.startswith(os.environ.get("SystemDrive", "C:").lower())]
        if off_os and mem.get("pagefileOnOsVolume"):
            # September 30, 2026: PagefileOnOsVolume=1 kept Windows from creating a page file on D: or M: at every boot;
            # it made a temporary one on C: instead and showed "Windows created a temporary paging file".
            out.append(f"page file set on {', '.join(off_os)} but PagefileOnOsVolume is 1, which keeps Windows from creating it "
                       r"at boot: set HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management "
                       "PagefileOnOsVolume to 0 (as an administrator) and restart")
        elif missing:
            out.append(f"page file set but not in use: {', '.join(missing)}; a page file setting applies at the next restart"
                       + (" (Windows made a temporary page file at the last boot)" if mem.get("tempPageFile") else ""))
    if s.get("anythingllm") and not s["anythingllm"].get("up"):
        out.append("AnythingLLM is not answering: jason anythingllm --start --yes")
    return out


def preflight(model: str = DEFAULT_MODEL, *, allow_cpu: bool = False, ollama_url: str = OLLAMA_URL) -> None:
    """Refuse, before sending anything, a model job that would fail or crawl: Ollama down, no GPU, the model not
    pulled, or not enough commit left to load it."""
    try:
        installed = {m["name"]: m.get("size", 0) for m in _get(f"{ollama_url}/api/tags").get("models", [])}
        loaded = {m["name"] for m in _get(f"{ollama_url}/api/ps").get("models", [])}
    except (OSError, ValueError) as exc:
        raise LocalAIUnavailable(f"Ollama at {ollama_url} is not answering ({exc}); start the Ollama app") from exc
    name = next((n for n in installed if n == model or n.startswith(model + ":") or n.split(":")[0] == model), "")
    if not name:
        raise LocalAIUnavailable(f"{model} is not pulled; run: ollama pull {model}")
    devices = gpu_discovery()
    if not allow_cpu and devices and not any(d.get("library") in ("CUDA", "ROCm") for d in devices):
        raise LocalAIUnavailable("Ollama is running without the GPU; restart it after a driver change "
                                 "(jason local-ai --restart-ollama --yes)")
    mem = _windows_memory()
    if name not in loaded and mem.get("commitLimit"):
        free = mem["commitLimit"] - mem["committed"]
        need = int(installed[name] * 1.3) + COMMIT_MARGIN     # weights plus the context cache and the loader's working set
        if free < need:
            raise LocalAIUnavailable(f"loading {name} needs about {_gb(need)} of Windows commit and {_gb(free)} is free; "
                                     "unload a model (jason local-ai --unload NAME --yes) or raise the page file")


def unload(model: str, *, ollama_url: str = OLLAMA_URL) -> list[str]:
    """Unload ``model`` (or every loaded model, for "all") from Ollama now."""
    names = [m["name"] for m in _get(f"{ollama_url}/api/ps").get("models", [])] if model == "all" else [model]
    for name in names:
        _post(f"{ollama_url}/api/generate", {"model": name, "keep_alive": 0}, timeout=60)
    return names


def restart_ollama(*, ollama_url: str = OLLAMA_URL, wait: float = 60) -> dict[str, Any]:
    """Stop and start the Ollama app (Windows), so it looks for GPUs again, holding the GPU lock so no jason request is
    cut off. Anything else using Ollama (AnythingLLM) sees it drop for a few seconds."""
    if sys.platform != "win32":
        raise LocalAIUnavailable("restarting Ollama is written for the Windows app")
    app = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "Programs" / "Ollama" / "ollama app.exe"
    if not app.is_file():
        raise LocalAIUnavailable(f"the Ollama app is not at {app}")
    with hold(Resource.GPU, timeout=600, purpose="restart Ollama"):
        # The model servers too: stopping ollama.exe leaves its llama-server.exe running, holding the model's memory
        # where nothing can reach it (September 30, 2026: 24 GB of commit).
        for image in ("ollama app.exe", "ollama.exe", "llama-server.exe"):
            subprocess.run(["taskkill", "/IM", image, "/F"], capture_output=True)
        time.sleep(2)
        subprocess.Popen([str(app)], creationflags=getattr(subprocess, "DETACHED_PROCESS", 0), close_fds=True)
        deadline = time.monotonic() + wait
        while time.monotonic() < deadline:
            try:
                version = _get(f"{ollama_url}/api/version", timeout=2).get("version", "")
                time.sleep(3)                      # let it finish looking for GPUs before reading its log
                return {"version": version, "devices": gpu_discovery()}
            except (OSError, ValueError):
                time.sleep(1)
    raise LocalAIUnavailable(f"Ollama did not come back within {wait:.0f} seconds")


def status_lines(s: dict[str, Any]) -> list[str]:
    o, a, mem = s["ollama"], s["anythingllm"], s.get("memory") or {}
    out = [f"Ollama {o.get('version', '')} at {o['url']}: {'up' if o['up'] else 'NOT ANSWERING'}"]
    for d in o.get("devices") or []:
        out.append(f"  device: {d['library']} {d['description']} (driver {d.get('driver') or '-'}, {d.get('total') or '-'})")
    for m in o.get("loaded") or []:
        where = "all on the GPU" if m["vram"] >= m["size"] * 0.95 else f"{_gb(m['vram'])} on the GPU, the rest on the CPU"
        out.append(f"  loaded: {m['name']} {_gb(m['size'])}, {where}")
    out.append(f"AnythingLLM at {a['url']}: {'up' if a['up'] else 'NOT ANSWERING'}; chat "
               f"{a['settings'].get('OLLAMA_MODEL_PREF', '?')}, embedder {a['settings'].get('EMBEDDING_MODEL_PREF', '?')}")
    out.append(f"jason's model: {s['jasonModel']}")
    if mem.get("commitLimit"):
        out.append(f"Windows commit: {_gb(mem['committed'])} of {_gb(mem['commitLimit'])} used; RAM {_gb(mem['ram'])}")
        out.append("  page files in use: " + (", ".join(f"{p['file']} {_gb(p['size'])}" for p in mem.get("pageFiles") or []) or "none"))
        out.append("  page files set: " + ("; ".join(mem.get("pageFilesConfigured") or []) or "-"))
    for lock in s.get("locks") or []:
        out.append(f"lock {lock['lock']}: process {lock.get('pid')} ({lock.get('purpose') or lock.get('command', '')}) since {lock.get('since')}")
    out.append("")
    out += [f"! {f}" for f in s["findings"]] or ["no problems found"]
    return out


__all__ = ["LocalAIUnavailable", "status", "findings", "preflight", "unload", "restart_ollama", "status_lines", "gpu_discovery",
           "orphan_servers"]
