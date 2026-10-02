"""Managing AnythingLLM Desktop as jason depends on it: the app, its model settings, its workspaces, and their embeddings.

``jason.tasks.anythingllm_sync`` puts the catalogs into the app; this module keeps the app itself fit to hold them:

- **The app.** ``start``, ``stop``, and ``restart`` run the Windows app (``AnythingLLM.exe``), only when a person asks.
- **The settings.** ``PROFILE`` is what jason expects: chat and embeddings on the one system Ollama, the chat model the
  same as jason's readers (``DEFAULT_MODEL``) at the same window, so one load serves both. ``drift`` compares the app's
  ``/system`` settings with it; ``apply`` writes the chat settings (``POST /system/update-env``) and the embedder only
  when asked, because a new embedder empties every workspace.
- **The workspaces.** ``inventory`` counts each workspace's embedded documents and reads its retrieval settings beside
  ``WORKSPACE_SETTINGS``, and names the catalogs with no workspace and the stored documents no workspace embeds.
- **The embeddings.** ``snapshot`` saves each workspace's document list (``data/anythingllm/snapshots``); ``reembed``
  puts a snapshot back, workspace by workspace in batches, and resumes: a document already embedded is skipped. With
  ``reset`` it first removes every embedding and clears the app's vector cache, the way to re-embed after the embedder
  changed. Each batch holds jason's GPU lock, since the app embeds on the same Ollama.

Nothing here reads an API key or a secret out of the app's settings, and nothing changes a document's text.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from urllib.request import Request, urlopen

from jason.community.anythingllm import WORKSPACE_SETTINGS, AnythingLLM
from jason.tasks.anythingllm_sync import COMBINED_WORKSPACE
from jason.community.ollama_extractor import DEFAULT_CONTEXT, DEFAULT_MODEL
from jason.locks import Resource, hold

APP_URL = "http://localhost:3001"
OLLAMA_BASE = "http://127.0.0.1:11434"
SNAPSHOTS = Path("anythingllm") / "snapshots"
# Workspaces the app keeps for itself, not a catalog's.
APP_WORKSPACES = ("assistant-chats",)


class AnythingLLMAdminError(RuntimeError):
    """The app could not be started, stopped, or reached; or a change was refused."""


@dataclass(frozen=True)
class Profile:
    """The settings jason expects, as ``POST /system/update-env`` names them."""

    chat: dict[str, str]
    embedder: dict[str, str]


PROFILE = Profile(
    chat={"LLMProvider": "ollama", "OllamaLLMBasePath": OLLAMA_BASE, "OllamaLLMModelPref": DEFAULT_MODEL,
          "OllamaLLMTokenLimit": str(DEFAULT_CONTEXT)},
    # qwen3-embedding:8b on the same Ollama (September 30, 2026): with the app's MiniLM, the master policy's deductible
    # question drew only policy forms.
    embedder={"EmbeddingEngine": "ollama", "EmbeddingBasePath": OLLAMA_BASE, "EmbeddingModelPref": "qwen3-embedding:8b"},
)


# --- the app ------------------------------------------------------------------------------------------------------------

def app_path() -> Path:
    return Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "Programs" / "AnythingLLM" / "AnythingLLM.exe"


def online(url: str = APP_URL, timeout: float = 3) -> bool:
    try:
        with urlopen(Request(f"{url}/api/ping"), timeout=timeout) as response:
            return bool(json.loads(response.read().decode("utf-8") or "{}").get("online"))
    except (OSError, ValueError):
        return False


def start(*, wait: float = 120, url: str = APP_URL) -> dict[str, Any]:
    """Start the app unless it answers already, and wait for its API."""
    if online(url):
        return {"started": False, "online": True}
    if sys.platform != "win32":
        raise AnythingLLMAdminError("starting AnythingLLM is written for the Windows desktop app")
    app = app_path()
    if not app.is_file():
        raise AnythingLLMAdminError(f"the AnythingLLM app is not at {app}")
    subprocess.Popen([str(app)], creationflags=getattr(subprocess, "DETACHED_PROCESS", 0), close_fds=True)
    deadline = time.monotonic() + wait
    while time.monotonic() < deadline:
        if online(url):
            return {"started": True, "online": True}
        time.sleep(2)
    raise AnythingLLMAdminError(f"AnythingLLM did not answer within {wait:.0f} seconds of starting")


def stop(*, wait: float = 30, url: str = APP_URL) -> dict[str, Any]:
    """Close the app: asked to close first, then ended if it lingers."""
    if sys.platform != "win32":
        raise AnythingLLMAdminError("stopping AnythingLLM is written for the Windows desktop app")
    subprocess.run(["taskkill", "/IM", "AnythingLLM.exe", "/T"], capture_output=True)
    deadline = time.monotonic() + wait
    while time.monotonic() < deadline and online(url, timeout=1):
        time.sleep(1)
    if online(url, timeout=1):
        subprocess.run(["taskkill", "/IM", "AnythingLLM.exe", "/T", "/F"], capture_output=True)
        time.sleep(2)
    return {"stopped": not online(url, timeout=1)}


def restart(*, url: str = APP_URL) -> dict[str, Any]:
    stop(url=url)
    return start(url=url)


# --- the settings -------------------------------------------------------------------------------------------------------

def settings(client: AnythingLLM) -> dict[str, Any]:
    """The app's model and embedding settings; key-bearing values are left out."""
    raw = client._call("GET", "/system").get("settings") or {}
    wanted = set(PROFILE.chat) | set(PROFILE.embedder) | {"LLMModel", "HasExistingEmbeddings", "TextSplitterChunkSize",
                                                           "TextSplitterChunkOverlap", "EmbeddingModelMaxChunkLength"}
    return {k: raw.get(k) for k in sorted(wanted) if "key" not in k.lower() or k.endswith("Pref")}


def drift(current: dict[str, Any], profile: Profile = PROFILE) -> list[dict[str, str]]:
    """Each setting that differs from the profile: key, part (chat or embedder), what the app has, what jason wants."""
    out = []
    for part, wanted in (("chat", profile.chat), ("embedder", profile.embedder)):
        for key, want in wanted.items():
            have = "" if current.get(key) is None else str(current.get(key))
            if have.rstrip("/") != want.rstrip("/"):
                out.append({"key": key, "part": part, "have": have, "want": want})
    return out


def apply(client: AnythingLLM, *, embedder: bool = False, profile: Profile = PROFILE) -> dict[str, Any]:
    """Write the chat settings that drifted, and the embedder's only with ``embedder``, and set each workspace's
    retrieval to ``WORKSPACE_SETTINGS`` where it differs; return what changed."""
    differing = drift(settings(client), profile)
    change = {d["key"]: d["want"] for d in differing if d["part"] == "chat" or embedder}
    if change:
        client._call("POST", "/system/update-env", change)
    held_back = [d["key"] for d in differing if d["part"] == "embedder" and not embedder]
    retrieval = []
    for space in client.workspaces():
        slug = str(space.get("slug") or "")
        detail = _detail(client, slug)
        if any(detail.get(k) != want for k, want in WORKSPACE_SETTINGS.items()):
            client.configure_workspace(slug)
            retrieval.append(slug)
    return {"changed": change, "heldBack": held_back, "retrieval": retrieval}


# --- the workspaces -----------------------------------------------------------------------------------------------------

def _detail(client: AnythingLLM, slug: str) -> dict[str, Any]:
    detail = client._call("GET", f"/workspace/{slug}").get("workspace") or {}
    return detail[0] if isinstance(detail, list) and detail else detail if isinstance(detail, dict) else {}


def embedded(client: AnythingLLM, slug: str) -> list[str]:
    """The docpaths a workspace embeds."""
    return sorted({d["docpath"] for d in _detail(client, slug).get("documents") or [] if d.get("docpath")})


def inventory(client: AnythingLLM, catalogs: tuple = ()) -> dict[str, Any]:
    """Each workspace with its embedded documents and retrieval settings, the catalogs with no workspace, and the stored
    documents no workspace embeds."""
    spaces = []
    held: set[str] = set()
    for space in client.workspaces():
        slug = str(space.get("slug") or "")
        detail = _detail(client, slug)
        docs = {d["docpath"] for d in detail.get("documents") or [] if d.get("docpath")}
        held |= docs
        off = {k: detail.get(k) for k, want in WORKSPACE_SETTINGS.items() if detail.get(k) != want}
        spaces.append({"slug": slug, "name": space.get("name", ""), "documents": len(docs), "retrievalOff": off})
    names = {s["name"].lower() for s in spaces} | {s["slug"].lower() for s in spaces}
    missing = [c.name for c in catalogs if c.workspace.lower() not in names]
    owned = {c.workspace.lower() for c in catalogs} | {COMBINED_WORKSPACE.lower(), *APP_WORKSPACES}
    unowned = [s["slug"] for s in spaces if s["name"].lower() not in owned and s["slug"].lower() not in owned] if catalogs else []
    stored = [f"{d.get('folder')}/{d.get('name')}" for d in client.documents() if d.get("folder") and d.get("name")]
    loose = sorted(p for p in stored if p not in held)
    return {"workspaces": spaces, "catalogsWithoutWorkspace": missing, "workspacesNoCatalogOwns": unowned,
            "storedDocuments": len(stored), "notEmbedded": loose}


def findings(current: dict[str, Any], inv: dict[str, Any]) -> list[str]:
    out = []
    for d in drift(current):
        out.append(f"{d['part']} setting {d['key']} is {d['have'] or '(unset)'}, jason expects {d['want']}"
                   + ("; jason anythingllm --apply --yes" if d["part"] == "chat" else
                      "; changing the embedder empties every workspace: --apply --embedder --reembed --yes"))
    for space in inv["workspaces"]:
        if not space["documents"] and space["slug"] not in APP_WORKSPACES:
            out.append(f"workspace {space['slug']} embeds no documents; jason anythingllm --reembed --yes puts the last snapshot back")
        if space["retrievalOff"]:
            out.append(f"workspace {space['slug']} retrieval {space['retrievalOff']} differs from {WORKSPACE_SETTINGS}; "
                       "jason anythingllm --apply --yes")
    if inv.get("workspacesNoCatalogOwns"):
        out.append("workspaces no catalog owns: " + ", ".join(inv["workspacesNoCatalogOwns"]) + " (a first pass or a person's "
                   "own; jason deletes no workspace, so remove one in the app if it is not wanted)")
    if inv["catalogsWithoutWorkspace"]:
        out.append("catalogs with no workspace: " + ", ".join(inv["catalogsWithoutWorkspace"]) + "; jason anythingllm --sync")
    if inv["notEmbedded"]:
        out.append(f"{len(inv['notEmbedded'])} stored documents are in no workspace (uploaded and never embedded, or left "
                   "by a catalog that moved on)")
    return out


# --- the embeddings -----------------------------------------------------------------------------------------------------

@dataclass
class ReembedReport:
    snapshot: str = ""
    workspaces: dict[str, dict[str, int]] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def lines(self) -> list[str]:
        out = [f"snapshot {self.snapshot}"]
        for slug, n in self.workspaces.items():
            out.append(f"  {slug}: {n['embedded']}/{n['wanted']} embedded ({n['added']} added, {n['failed']} in failed batches)")
        out += [f"  error: {e}" for e in self.errors]
        return out


def snapshot(client: AnythingLLM, data_dir: Path, *, label: str = "") -> Path:
    """Save each workspace's document list, and the app's embedder, to ``data/anythingllm/snapshots``."""
    lists = {str(s.get("slug")): embedded(client, str(s.get("slug"))) for s in client.workspaces() if s.get("slug")}
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = Path(data_dir) / SNAPSHOTS / f"{stamp}{'-' + label if label else ''}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"taken": datetime.now().isoformat(timespec="seconds"), "embedder": settings(client).get(
        "EmbeddingModelPref"), "workspaces": lists}, indent=1), encoding="utf-8")
    return path


def latest_snapshot(data_dir: Path) -> Path | None:
    found = sorted((Path(data_dir) / SNAPSHOTS).glob("*.json"))
    return found[-1] if found else None


def _vector_cache() -> Path:
    return Path(os.environ.get("APPDATA") or Path.home()) / "anythingllm-desktop" / "storage" / "vector-cache"


def reembed(client: AnythingLLM, snapshot_path: Path, *, only: tuple[str, ...] = (), reset: bool = False, batch: int = 20,
            log: Callable[[str], None] | None = None) -> ReembedReport:
    """Put a snapshot's documents back into their workspaces. What a workspace already embeds is skipped, so a run cut
    off partway resumes; ``reset`` first removes every embedding and the app's vector cache. The shared workspace goes
    last, since each of its documents is embedded again for it."""
    say = log or (lambda _m: None)
    data = json.loads(Path(snapshot_path).read_text(encoding="utf-8"))
    lists: dict[str, list[str]] = data.get("workspaces", data)
    report = ReembedReport(snapshot=str(snapshot_path))
    order = sorted(lists, key=lambda slug: (slug == "mystique", slug))
    order = [s for s in order if not only or s in only]
    if reset:
        for slug in order:
            held = tuple(embedded(client, slug))
            for i in range(0, len(held), 50):
                client.update_embeddings(slug, deletes=held[i:i + 50])
            say(f"{slug}: removed {len(held)}")
        cache = _vector_cache()
        if cache.is_dir():
            for item in cache.iterdir():
                shutil.rmtree(item) if item.is_dir() else item.unlink()
            say("vector cache cleared")
    for slug in order:
        wanted = lists[slug]
        have = set(embedded(client, slug))
        todo = [d for d in wanted if d not in have]
        failed = 0
        for i in range(0, len(todo), batch):
            part = tuple(todo[i:i + batch])
            try:
                with hold(Resource.GPU, timeout=900, purpose=f"anythingllm re-embed {slug}"):
                    client.update_embeddings(slug, adds=part)
            except Exception as exc:  # one refused batch does not stop the workspace; it is reported
                failed += len(part)
                report.errors.append(f"{slug} batch {i // batch}: {str(exc)[:160]}")
        now = len(embedded(client, slug))
        report.workspaces[slug] = {"wanted": len(wanted), "added": len(todo) - failed, "failed": failed, "embedded": now}
        say(f"{slug}: {now}/{len(wanted)} embedded")
    return report


__all__ = ["PROFILE", "Profile", "AnythingLLMAdminError", "apply", "drift", "embedded", "findings", "inventory",
           "latest_snapshot", "online", "reembed", "restart", "settings", "snapshot", "start", "stop"]
