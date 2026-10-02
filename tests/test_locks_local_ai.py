import subprocess
import sys
import textwrap
from datetime import date

import pytest

from jason import local_ai
from jason.locks import Resource, ResourceBusy, hold, holders


def test_a_lock_is_exclusive_across_processes_and_reentrant_within_one(tmp_path, monkeypatch):
    held, release = tmp_path / "held", tmp_path / "release"
    script = textwrap.dedent(f"""
        import time
        from pathlib import Path
        from jason.locks import Resource, hold
        with hold(Resource.GPU, purpose="other process"):
            Path(r"{held}").write_text("x")
            for _ in range(300):
                if Path(r"{release}").exists():
                    break
                time.sleep(0.05)
    """)
    other = subprocess.Popen([sys.executable, "-c", script])
    try:
        for _ in range(100):
            if held.exists():
                break
            __import__("time").sleep(0.1)
        assert held.exists()
        with pytest.raises(ResourceBusy, match="other process"):
            with hold(Resource.GPU, timeout=0.5):
                pass
        assert [h["lock"] for h in holders()] == ["gpu"]
    finally:
        release.write_text("x")
        other.wait(timeout=30)
    # The other process is gone: its lock is free, and its note is cleared.
    assert holders() == []
    with hold(Resource.STORE, "board-items"):
        with hold(Resource.STORE, "board-items", timeout=0.1):     # the same process may take it again
            assert [h["lock"] for h in holders()] == ["store-board-items"]
    assert holders() == []


def test_board_writers_hold_the_store(tmp_path):
    from jason.community.board_items import BoardItem, ItemCategory, Priority
    from jason.tasks.board_items import load, propose

    item = BoardItem("a", title="Title", summary="Summary.", ask="Decide it.", category=ItemCategory.GOVERNANCE, priority=Priority.NORMAL)
    result = propose(tmp_path, [item], today=date(2026, 9, 30))       # propose calls upsert and set_fields under one lock
    assert result["proposed"] == ["a"] and load(tmp_path)[0].status.value == "proposed"


LOG = """time=1 level=INFO msg="server config" env="map[]"
time=2 level=INFO msg="inference compute" id=cpu library=cpu compute="" name=cpu description=cpu libdirs=ollama driver="" total="61.6 GiB"
time=3 level=INFO msg="server config" env="map[]"
time=4 level=INFO msg="inference compute" id=0 library=CUDA compute=12.0 name=CUDA0 description="NVIDIA GeForce RTX 5090" libdirs=ollama,cuda_v13 driver=13.4 total="31.8 GiB" available="30.2 GiB"
"""


def test_gpu_discovery_reads_the_last_start(tmp_path):
    log = tmp_path / "server.log"
    log.write_text(LOG, encoding="utf-8")
    assert local_ai.gpu_discovery(log) == [{"library": "CUDA", "description": "NVIDIA GeForce RTX 5090", "driver": "13.4",
                                             "total": "31.8 GiB", "available": "30.2 GiB"}]


GB = 1 << 30


def test_findings_name_each_problem_and_its_fix():
    status = {
        "jasonModel": "qwen3.6:27b",
        "ollama": {"up": True, "devices": [{"library": "cpu", "description": "cpu"}], "orphans": [29744],
                   "loaded": [{"name": "qwen3.6:27b", "size": 20 * GB, "vram": 0}, {"name": "qwen3.5:9b", "size": 8 * GB, "vram": 8 * GB}]},
        "anythingllm": {"up": True, "settings": {"OLLAMA_MODEL_PREF": "qwen3.6:27b", "EMBEDDING_MODEL_PREF": "qwen3-embedding:8b"}},
        "memory": {"commitLimit": 66 * GB, "committed": 62 * GB, "pageFiles": [{"file": "C:\\pagefile.sys", "size": 5 * GB}],
                   "pageFilesConfigured": ["d:\\pagefile.sys 32768 65535"]},
    }
    text = "\n".join(local_ai.findings(status))
    for expected in ("found no GPU", "--restart-ollama", "qwen3.6:27b is 100% on the CPU", "process 29744",
                     "loaded outside the plan: qwen3.5:9b", "commit is nearly full", "d:\\pagefile.sys", "next restart"):
        assert expected in text
    healthy = {"jasonModel": "m", "ollama": {"up": True, "devices": [{"library": "CUDA"}], "loaded": [{"name": "m", "size": 1, "vram": 1}]},
               "anythingllm": {"up": True, "settings": {"OLLAMA_MODEL_PREF": "m"}},
               "memory": {"commitLimit": 90 * GB, "committed": 40 * GB, "pageFiles": [{"file": "D:\\pagefile.sys"}],
                          "pageFilesConfigured": ["d:\\pagefile.sys 32768 65535"]}}
    assert local_ai.findings(healthy) == []


def test_a_page_file_kept_off_its_drive_by_pagefile_on_os_volume():
    status = {"ollama": {"up": True}, "memory": {"commitLimit": 90 * GB, "committed": 10 * GB, "pagefileOnOsVolume": 1,
                                                 "pageFiles": [{"file": "C:\\pagefile.sys"}], "pageFilesConfigured": ["d:\\pagefile.sys 0 0"]}}
    text = "\n".join(local_ai.findings(status))
    assert "PagefileOnOsVolume is 1" in text and r"Session Manager\Memory Management" in text and "not in use" not in text
    status["memory"]["pagefileOnOsVolume"] = 0
    assert "applies at the next restart" in "\n".join(local_ai.findings(status))


def test_orphan_servers():
    procs = [{"pid": 1, "parent": 0, "name": "ollama.exe"}, {"pid": 2, "parent": 1, "name": "llama-server.exe"},
             {"pid": 3, "parent": 99, "name": "llama-server.exe"}]
    assert local_ai.orphan_servers(procs) == [3]


def test_preflight_refuses_cpu_missing_models_and_short_memory(monkeypatch):
    replies = {"/api/tags": {"models": [{"name": "qwen3.6:27b", "size": 17 * GB}]}, "/api/ps": {"models": []}}
    monkeypatch.setattr(local_ai, "_get", lambda url, timeout=5: replies[url[url.index("/api"):]])
    monkeypatch.setattr(local_ai, "gpu_discovery", lambda log=None: [{"library": "CUDA"}])
    monkeypatch.setattr(local_ai, "_windows_memory", lambda: {"commitLimit": 90 * GB, "committed": 40 * GB})
    local_ai.preflight("qwen3.6:27b")
    with pytest.raises(local_ai.LocalAIUnavailable, match="ollama pull"):
        local_ai.preflight("llama3:70b")
    monkeypatch.setattr(local_ai, "_windows_memory", lambda: {"commitLimit": 66 * GB, "committed": 50 * GB})
    with pytest.raises(local_ai.LocalAIUnavailable, match="commit"):
        local_ai.preflight("qwen3.6:27b")
    replies["/api/ps"] = {"models": [{"name": "qwen3.6:27b"}]}              # already loaded: nothing more to commit
    local_ai.preflight("qwen3.6:27b")
    monkeypatch.setattr(local_ai, "gpu_discovery", lambda log=None: [{"library": "cpu"}])
    with pytest.raises(local_ai.LocalAIUnavailable, match="without the GPU"):
        local_ai.preflight("qwen3.6:27b")
    local_ai.preflight("qwen3.6:27b", allow_cpu=True)
