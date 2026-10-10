"""docs/instance-limits.md, test plan 2: two communities in one interpreter read their own limits. ``alpha`` and ``beta`` are made-up
slugs with a made-up value each; the sentinel reason stands for text a community wrote."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from jason import limits

MB = 1024 * 1024
KEY = "upload.max_bytes"
ALPHA, BETA = SimpleNamespace(slug="alpha", limits=dict), SimpleNamespace(slug="beta", limits=dict)


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setenv("JASON_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("JASON_LIMITS_FILE", str(tmp_path / "home" / "limits.json"))
    monkeypatch.delenv("JASON_LIMIT_UPLOAD_MAX_BYTES", raising=False)
    return tmp_path


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "absent"


def _set(community, value, reason="r"):
    return limits.set_limits({KEY: value}, scope="community", reason=reason, by="A. Person", dry_run=False, community=community)


def test_each_community_reads_its_own_value_in_one_process_and_a_write_changes_only_its_own(world):
    beta_folder = world / "data" / "beta"
    _set(ALPHA, "30MB", reason="SENT-alpha reason")
    _set(BETA, "60MB", reason="SENT-beta reason")
    for _ in range(2):                                                     # alpha, beta, alpha, beta
        assert limits.value(KEY, community=ALPHA) == 30 * MB
        assert limits.value(KEY, community=BETA) == 60 * MB
    beta_before = {p.name: _digest(p) for p in beta_folder.iterdir()}
    _set(ALPHA, "40MB", reason="SENT-alpha again")
    assert {p.name: _digest(p) for p in beta_folder.iterdir()} == beta_before        # byte-identical
    assert limits.value(KEY, community=ALPHA) == 40 * MB and limits.value(KEY, community=BETA) == 60 * MB
    assert limits.effective(KEY, community=BETA).set["reason"] == "SENT-beta reason"


def test_a_communitys_reasons_stay_in_its_own_trail(world):
    _set(ALPHA, "30MB", reason="SENT-alpha reason")
    limits.set_limits({KEY: "50MB"}, scope="instance", reason="the operator's reason", by="Op", dry_run=False)
    assert "SENT-alpha" not in json.dumps(limits.read_log("community", community=BETA))
    assert "SENT-alpha" not in json.dumps(limits.read_log("instance"))
    assert "SENT-alpha" not in json.dumps(limits.listing(community=BETA)) + json.dumps(limits.instance_listing())
    assert "SENT-alpha" in json.dumps(limits.read_log("community", community=ALPHA))


def test_the_instance_ceiling_binds_both_and_the_value_is_each_communitys_own(world):
    limits.set_limits({KEY: "50MB"}, scope="instance", ceiling="80MB", reason="r", by="Op", dry_run=False)
    _set(ALPHA, "70MB")
    with pytest.raises(limits.LimitRefused):
        _set(BETA, "90MB")
    assert limits.value(KEY, community=ALPHA) == 70 * MB and limits.value(KEY, community=BETA) == 50 * MB


def test_separate_processes_read_the_same_answers(world):
    _set(ALPHA, "30MB")
    _set(BETA, "60MB")
    code = ("import json; from types import SimpleNamespace as S; from jason import limits; "
            "print(json.dumps([limits.value('upload.max_bytes', community=S(slug=k, limits=dict)) for k in ('alpha', 'beta')]))")
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src"))
    got = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, check=True).stdout
    assert json.loads(got) == [30 * MB, 60 * MB]
