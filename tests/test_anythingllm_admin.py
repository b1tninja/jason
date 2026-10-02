"""Managing AnythingLLM: its settings against jason's, the workspaces' inventory, snapshots, and a re-embed that
resumes; and the CLI's guards on anything that changes the app."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from jason import anythingllm_admin as admin
from jason.community.anythingllm import WORKSPACE_SETTINGS, AnythingLLM
from jason.tasks.anythingllm_sync import Catalog


class App:
    """A stand-in for the app's developer API: settings, workspaces with their embedded docpaths, and the store."""

    def __init__(self, settings: dict, spaces: dict[str, list[str]], stored: list[str], retrieval: dict | None = None) -> None:
        self.settings = dict(settings)
        self.spaces = {k: list(v) for k, v in spaces.items()}
        self.stored = stored
        self.retrieval = {k: dict(retrieval or WORKSPACE_SETTINGS) for k in spaces}
        self.calls: list[tuple[str, str, dict | None]] = []

    def __call__(self, method: str, url: str, payload: dict | None):
        path = url.split("/api/v1", 1)[-1]
        self.calls.append((method, path, payload))
        if path == "/system":
            return {"settings": self.settings}
        if path == "/system/update-env":
            self.settings.update(payload or {})
            return {"success": True}
        if path == "/workspaces":
            return {"workspaces": [{"slug": s, "name": s.replace("-", " ").title()} for s in self.spaces]}
        if path == "/documents":
            folders: dict[str, list] = {}
            for p in self.stored:
                folder, name = p.split("/", 1)
                folders.setdefault(folder, []).append({"type": "file", "name": name, "title": name})
            return {"localFiles": {"items": [{"type": "folder", "name": f, "items": items} for f, items in folders.items()]}}
        slug = path.split("/")[2]
        if path.endswith("/update-embeddings"):
            have = self.spaces[slug]
            have += [d for d in payload.get("adds", []) if d not in have]
            self.spaces[slug] = [d for d in have if d not in payload.get("deletes", [])]
            return {"workspace": {}}
        if path.endswith("/update"):
            self.retrieval[slug].update(payload or {})
            return {"workspace": {"slug": slug}}
        return {"workspace": {"slug": slug, **self.retrieval[slug], "documents": [{"docpath": d} for d in self.spaces[slug]]}}


GOOD = {**admin.PROFILE.chat, **admin.PROFILE.embedder}


def _client(app: App) -> AnythingLLM:
    return AnythingLLM(api_key="k", fetch=app)


def test_drift_names_each_setting_and_apply_leaves_the_embedder_alone() -> None:
    app = App({**GOOD, "OllamaLLMModelPref": "qwen3-vl:4b-instruct", "OllamaLLMTokenLimit": "4096",
               "EmbeddingModelPref": "Xenova/all-MiniLM-L6-v2", "EmbeddingEngine": "native"}, {"authorities": []}, [],
              retrieval={"topN": 4, "similarityThreshold": 0.25})
    client = _client(app)
    assert {d["key"] for d in admin.drift(admin.settings(client))} == {
        "OllamaLLMModelPref", "OllamaLLMTokenLimit", "EmbeddingModelPref", "EmbeddingEngine"}
    done = admin.apply(client)
    assert done["changed"] == {"OllamaLLMModelPref": admin.PROFILE.chat["OllamaLLMModelPref"],
                               "OllamaLLMTokenLimit": admin.PROFILE.chat["OllamaLLMTokenLimit"]}
    assert set(done["heldBack"]) == {"EmbeddingModelPref", "EmbeddingEngine"} and done["retrieval"] == ["authorities"]
    assert app.settings["EmbeddingModelPref"] == "Xenova/all-MiniLM-L6-v2" and app.retrieval["authorities"]["topN"] == 12
    assert admin.apply(client, embedder=True)["changed"]["EmbeddingModelPref"] == "qwen3-embedding:8b"
    assert admin.drift(admin.settings(client)) == []


def test_the_inventory_names_empty_unowned_and_loose() -> None:
    app = App(GOOD, {"authorities": ["authorities/a.json"], "mystique": ["authorities/a.json"], "my-workspace": ["x/b.json"],
                     "mail": [], "assistant-chats": []}, ["authorities/a.json", "x/b.json", "custom-documents/c.json"])
    catalogs = (Catalog("authorities", "authorities", "Authorities", "", "", ()), Catalog("mail", "mail", "Mail", "", "", ()),
                Catalog("jason-pages", "jason-pages", "Jason Pages", "", "", ()))
    inv = admin.inventory(_client(app), catalogs)
    assert inv["catalogsWithoutWorkspace"] == ["jason-pages"] and inv["workspacesNoCatalogOwns"] == ["my-workspace"]
    assert inv["notEmbedded"] == ["custom-documents/c.json"] and inv["storedDocuments"] == 3
    found = admin.findings(admin.settings(_client(app)), inv)
    assert any("workspace mail embeds no documents" in f for f in found)
    assert not any("assistant-chats" in f for f in found)
    assert any("no catalog owns: my-workspace" in f for f in found)


def test_a_snapshot_is_put_back_and_a_second_run_adds_nothing(tmp_path: Path, monkeypatch) -> None:
    app = App(GOOD, {"authorities": ["authorities/a.json", "authorities/b.json"], "mystique": ["authorities/a.json"]}, [])
    client = _client(app)
    snap = admin.snapshot(client, tmp_path)
    assert admin.latest_snapshot(tmp_path) == snap
    assert json.loads(snap.read_text(encoding="utf-8"))["workspaces"]["authorities"] == ["authorities/a.json", "authorities/b.json"]
    app.spaces["authorities"] = ["authorities/a.json"]               # a run cut off partway
    first = admin.reembed(client, snap)
    assert first.workspaces["authorities"] == {"wanted": 2, "added": 1, "failed": 0, "embedded": 2}
    assert admin.reembed(client, snap).workspaces["authorities"]["added"] == 0
    # The shared workspace goes last, and the other session's flat {slug: [docpaths]} file is read too.
    order = [p.split("/")[2] for m, p, body in app.calls if p.endswith("/update-embeddings")]
    assert order == ["authorities"]
    flat = tmp_path / "flat.json"
    flat.write_text(json.dumps({"mystique": ["authorities/a.json", "authorities/b.json"]}), encoding="utf-8")
    assert admin.reembed(client, flat).workspaces["mystique"]["added"] == 1


def test_a_reset_removes_every_embedding_and_clears_the_vector_cache(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path))
    cache = tmp_path / "anythingllm-desktop" / "storage" / "vector-cache"
    cache.mkdir(parents=True)
    (cache / "old.json").write_text("{}", encoding="utf-8")
    app = App(GOOD, {"authorities": ["authorities/a.json"]}, [])
    snap = admin.snapshot(_client(app), tmp_path)
    report = admin.reembed(_client(app), snap, reset=True)
    deletes = [body for m, p, body in app.calls if p.endswith("/update-embeddings") and body.get("deletes")]
    assert deletes and not any(cache.iterdir()) and report.workspaces["authorities"]["embedded"] == 1


def _args(**given) -> argparse.Namespace:
    base = dict(start=False, stop=False, restart=False, apply=False, reembed=False, status=False, snapshot=False,
                embedder=False, reset=False, yes=False, only=None, from_snapshot="", json=False, env=None)
    return argparse.Namespace(**{**base, **given})


def test_the_cli_asks_for_yes_and_refuses_an_embedder_change_without_a_reembed(capsys) -> None:
    from jason.cli import _anythingllm_admin

    assert _anythingllm_admin(_args()) is None
    assert _anythingllm_admin(_args(apply=True)) == 2 and "--yes" in capsys.readouterr().err
    assert _anythingllm_admin(_args(apply=True, embedder=True, yes=True)) == 2
    assert "empties every workspace" in capsys.readouterr().err
