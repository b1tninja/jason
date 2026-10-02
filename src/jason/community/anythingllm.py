"""AnythingLLM as the polished front end: its workspaces hold the documents, jason-mcp gives it the tools.

AnythingLLM Desktop runs on this machine, has the governing documents in a
workspace, embeds them, and chats over them with a local model through
Ollama. Two joins make it useful here. Its developer API lets jason ask a
workspace a question in ``query`` mode and get the answer with the source
chunks, which is a retriever with a better ranker than BM25; and its
agent can load jason-mcp's tools from ``anythingllm_mcp_servers.json``,
so a person chatting in AnythingLLM can ask for a unit brief or a solar
standing and get the stores' answer. The API key comes from
``ANYTHINGLLM_API_KEY`` (generated in the app under API Keys); without it
the client fails fast and sends nothing. Nothing an answer says is pinned.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

BASE_URL = "http://localhost:3001/api/v1"
SERVER_NAME = "jason"

# Retrieval for every catalog workspace. The chat model's window (64k on
# the local Ollama) holds far more than the app's default four passages,
# and a policy's declarations page loses to its forms at four.
WORKSPACE_SETTINGS: dict[str, Any] = {"topN": 12, "similarityThreshold": 0.25}

# A reasoning model's thinking, which the app returns inside the answer.
THINKING = re.compile(r"<think>.*?</think>\s*", re.DOTALL)


class AnythingLLMUnavailable(RuntimeError):
    """No key, or the app is not answering."""


class AnythingLLMError(RuntimeError):
    """The app answered with an error; the message is the app's own (its ``error`` or ``message`` field)."""


class AnythingLLMModelError(AnythingLLMError):
    """The workspace's chat model failed (it would not load, or it stopped); retrieval still works."""


@dataclass(frozen=True)
class Source:
    title: str
    text: str
    score: float | None = None


@dataclass(frozen=True)
class Answer:
    workspace: str
    question: str
    text: str
    sources: tuple[Source, ...]


class AnythingLLM:
    def __init__(self, *, base_url: str = BASE_URL, api_key: str | None = None, fetch=None, timeout: int = 300) -> None:
        self.base_url = base_url.rstrip("/")
        self._key = api_key if api_key is not None else _configured_key()
        self._fetch = fetch
        self.timeout = timeout

    def _call(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self._key:
            raise AnythingLLMUnavailable("no ANYTHINGLLM_API_KEY; generate one in AnythingLLM under Settings, API Keys")
        if self._fetch is not None:
            return self._fetch(method, f"{self.base_url}{path}", payload)
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = Request(f"{self.base_url}{path}", data=body, method=method, headers={"Authorization": f"Bearer {self._key}", "Content-Type": "application/json", "Accept": "application/json"})
        with urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8") or "{}")

    def online(self) -> bool:
        try:
            self._call("GET", "/auth")
        except AnythingLLMUnavailable:
            raise
        except Exception:
            return False
        return True

    def workspaces(self) -> tuple[dict[str, Any], ...]:
        data = self._call("GET", "/workspaces")
        return tuple(data.get("workspaces") or [])

    def documents(self) -> tuple[dict[str, Any], ...]:
        """Every document AnythingLLM has parsed, flattened out of its folder tree."""
        data = self._call("GET", "/documents")
        found: list[dict[str, Any]] = []

        def walk(node: dict[str, Any], folder: str) -> None:
            for item in node.get("items") or []:
                if item.get("type") == "folder":
                    walk(item, str(item.get("name") or ""))
                else:
                    found.append({**item, "folder": folder})

        walk(data.get("localFiles") or {}, "")
        return tuple(found)

    def folders(self) -> tuple[str, ...]:
        data = self._call("GET", "/documents")
        return tuple(str(item.get("name") or "") for item in (data.get("localFiles") or {}).get("items") or [] if item.get("type") == "folder")

    def create_folder(self, name: str) -> bool:
        """Make a document-store folder; one that already exists is not an error."""
        try:
            data = self._call("POST", "/document/create-folder", {"name": name})
        except HTTPError as exc:
            if exc.code == 500 and "exists" in (exc.read().decode("utf-8", "ignore") if hasattr(exc, "read") else ""):
                return True
            raise
        return bool(data.get("success")) or "exists" in str(data.get("message") or "")

    def move(self, moves: dict[str, str]) -> bool:
        """Move parsed documents between folders; keys and values are docpaths (``folder/name.json``)."""
        if not moves:
            return True
        try:
            data = self._call("POST", "/document/move-files", {"files": [{"from": src, "to": dst} for src, dst in moves.items()]})
        except HTTPError as exc:
            if exc.code == 500:
                return False
            raise
        # The store answers success with "n/n files not moved" when a file is still embedded somewhere.
        return bool(data.get("success")) and "not moved" not in str(data.get("message") or "")

    def remove_documents(self, names: tuple[str, ...]) -> bool:
        """Delete parsed documents (docpaths, ``folder/name.json``) from the store and every workspace's embeddings."""
        if not names:
            return True
        data = self._call("DELETE", "/system/remove-documents", {"names": list(names)})
        return bool(data.get("success"))

    def create_workspace(self, name: str) -> str:
        """Make a workspace and return its slug."""
        data = self._call("POST", "/workspace/new", {"name": name})
        space = data.get("workspace") if isinstance(data.get("workspace"), dict) else data
        return str(space.get("slug") or "")

    def configure_workspace(self, slug: str, settings: dict[str, Any] | None = None) -> bool:
        """Set a workspace's retrieval (``WORKSPACE_SETTINGS`` unless given)."""
        data = self._call("POST", f"/workspace/{slug}/update", dict(WORKSPACE_SETTINGS if settings is None else settings))
        return bool(data.get("workspace") or data.get("success"))

    def workspace_slug(self, name: str) -> str:
        """The slug of the workspace with this name or slug, or empty."""
        wanted = " ".join(name.lower().split())
        for space in self.workspaces():
            if str(space.get("slug") or "").lower() == wanted or " ".join(str(space.get("name") or "").lower().split()) == wanted:
                return str(space.get("slug") or "")
        return ""

    def query(self, workspace: str, question: str, *, mode: str = "query") -> Answer:
        """Ask a workspace. ``query`` answers only from the documents; ``chat`` keeps a thread."""
        try:
            data = self._call("POST", f"/workspace/{workspace}/chat", {"message": question, "mode": mode})
        except HTTPError as exc:
            text = _error_text(exc)
            if "getChatCompletion" in text or "ollama" in text.lower() or "llama-server" in text:
                raise AnythingLLMModelError(text) from exc
            raise AnythingLLMError(f"HTTP {exc.code} from the chat: {text}") from exc
        if data.get("error") and not data.get("textResponse"):
            raise AnythingLLMModelError(str(data["error"]))
        sources = tuple(
            Source(str(s.get("title") or s.get("docTitle") or ""), str(s.get("text") or s.get("chunk") or ""), s.get("score"))
            for s in data.get("sources") or []
        )
        return Answer(workspace, question, THINKING.sub("", str(data.get("textResponse") or "")).strip(), sources)

    def search(self, workspace: str, question: str, *, top_n: int = 4, threshold: float = 0.25) -> tuple[Source, ...]:
        """The workspace's nearest passages by embedding alone, with no chat model."""
        data = self._call("POST", f"/workspace/{workspace}/vector-search", {"query": question, "topN": top_n, "scoreThreshold": threshold})
        return tuple(
            Source(str((r.get("metadata") or {}).get("title") or ""), str(r.get("text") or ""), r.get("score"))
            for r in data.get("results") or []
        )

    def upload(self, path: Path, *, workspace: str = "", title: str = "", description: str = "", folder: str = "", author: str = "") -> dict[str, Any]:
        """Upload one file for parsing and embedding; with ``workspace`` (slugs, comma-separated) it is added at once.

        ``folder`` is the document-store folder that keeps one catalog apart
        from another; ``author`` is the docAuthor the store shows.
        """
        if not self._key:
            raise AnythingLLMUnavailable("no ANYTHINGLLM_API_KEY; generate one in AnythingLLM under Settings, API Keys")
        fields: dict[str, str] = {}
        if workspace:
            fields["addToWorkspaces"] = workspace
        metadata = {k: v for k, v in (("title", title or path.name), ("description", description), ("docAuthor", author), ("docSource", "jason")) if v}
        fields["metadata"] = json.dumps(metadata)
        route = f"/document/upload/{quote(folder)}" if folder else "/document/upload"
        if self._fetch is not None:
            return self._fetch("POST", f"{self.base_url}{route}", {"file": str(path), **fields})
        body, content_type = _multipart(fields, "file", path)
        request = Request(f"{self.base_url}{route}", data=body, method="POST", headers={"Authorization": f"Bearer {self._key}", "Content-Type": content_type, "Accept": "application/json"})
        with urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8") or "{}")

    def raw_text(self, text: str, *, title: str, workspace: str = "", description: str = "") -> dict[str, Any]:
        """Create a document from text (a generated report page) and, with ``workspace``, add it to that workspace."""
        payload: dict[str, Any] = {"textContent": text, "metadata": {"title": title, "docSource": "jason", **({"description": description} if description else {})}}
        if workspace:
            payload["addToWorkspaces"] = workspace
        return self._call("POST", "/document/raw-text", payload)

    def update_embeddings(self, workspace: str, *, adds: tuple[str, ...] = (), deletes: tuple[str, ...] = ()) -> dict[str, Any]:
        """Add or remove parsed documents (by their ``docpath``) in a workspace's embeddings."""
        return self._call("POST", f"/workspace/{workspace}/update-embeddings", {"adds": list(adds), "deletes": list(deletes)})


def _multipart(fields: dict[str, str], file_field: str, path: Path) -> tuple[bytes, str]:
    """A multipart/form-data body with the fields and one file, built without a third-party package."""
    import mimetypes
    import uuid

    boundary = f"----jason{uuid.uuid4().hex}"
    lines: list[bytes] = []
    for name, value in fields.items():
        lines += [f"--{boundary}".encode(), f'Content-Disposition: form-data; name="{name}"'.encode(), b"", str(value).encode("utf-8")]
    kind = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    lines += [
        f"--{boundary}".encode(),
        f'Content-Disposition: form-data; name="{file_field}"; filename="{path.name}"'.encode("utf-8"),
        f"Content-Type: {kind}".encode(), b"", path.read_bytes(),
        f"--{boundary}--".encode(), b"",
    ]
    return b"\r\n".join(lines), f"multipart/form-data; boundary={boundary}"


def _error_text(exc: HTTPError) -> str:
    """The app's own words for a failed call: the JSON body's ``error`` or ``message``, else the status reason."""
    try:
        body = json.loads(exc.read().decode("utf-8", errors="replace") or "{}")
    except (ValueError, OSError):
        return str(exc.reason)
    if isinstance(body, dict):
        return str(body.get("error") or body.get("message") or exc.reason)
    return str(exc.reason)


def _configured_key() -> str:
    """The key from the environment, else from the project's ``.env`` (``anythingllm_api_key``), never committed."""
    found = os.environ.get("ANYTHINGLLM_API_KEY", "")
    if found:
        return found
    try:
        from jason.config import Settings

        return Settings.load().anythingllm_api_key
    except Exception:
        return ""


def mcp_server_entry(command: str, *, cwd: str = "", profile: str = "board") -> dict[str, Any]:
    """The entry that registers jason-mcp as an agent tool set in AnythingLLM.

    ``profile`` defaults to the board set: AnythingLLM's local model picks
    better among nineteen tools than sixty. "all" serves every tool.
    """
    args = [] if profile in ("", "all") else ["--profile", profile]
    entry: dict[str, Any] = {"command": command, "args": args, "env": {}, "anythingllm": {"autoStart": False}}
    if cwd:
        entry["env"]["JASON_CWD"] = cwd
    return {SERVER_NAME: entry}


def mcp_servers_path() -> Path:
    """Where AnythingLLM Desktop keeps its MCP server list on Windows."""
    return Path(os.environ.get("APPDATA", "")) / "anythingllm-desktop" / "storage" / "plugins" / "anythingllm_mcp_servers.json"


def merged_mcp_config(existing: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any]:
    """The config with jason added or replaced, everything else kept."""
    servers = dict(existing.get("mcpServers") or {})
    servers.update(entry)
    return {**existing, "mcpServers": servers}
