# tests/test_bootstrap.py —— 安装 skill 时能找到或 clone 仓库
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_BOOT = ROOT / "skill" / "gleaner" / "scripts" / "bootstrap.py"


def _load():
    spec = importlib.util.spec_from_file_location("gleaner_bootstrap", _BOOT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_find_existing_cli_from_env(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "gleaner_cli.py").write_text("# stub\n", encoding="utf-8")
    monkeypatch.setenv("GLEANER_ROOT", str(repo))
    monkeypatch.chdir(tmp_path)
    mod = _load()
    assert mod.find_existing_cli() == repo / "gleaner_cli.py"


def test_find_existing_cli_from_cwd(tmp_path, monkeypatch):
    (tmp_path / "gleaner_cli.py").write_text("# stub\n", encoding="utf-8")
    monkeypatch.delenv("GLEANER_ROOT", raising=False)
    monkeypatch.chdir(tmp_path)
    mod = _load()
    # 模块里的 Path(__file__) 仍指向仓库内 bootstrap，marker 可能存在；
    # cwd 有 cli 时应能找到（env 已清空）
    found = mod.find_existing_cli()
    assert found is not None
    assert found.name == "gleaner_cli.py"


def test_clone_repo_skips_when_cli_exists(tmp_path, monkeypatch):
    dest = tmp_path / "gleaner"
    dest.mkdir()
    (dest / "gleaner_cli.py").write_text("# stub\n", encoding="utf-8")
    mod = _load()
    monkeypatch.setattr(
        mod.subprocess,
        "check_call",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("不应 clone")),
    )
    assert mod.clone_repo(dest) == dest.resolve()


def test_clone_repo_calls_git(tmp_path, monkeypatch):
    dest = tmp_path / "newrepo"
    calls = []

    def fake_call(cmd, *a, **k):
        calls.append(cmd)
        dest.mkdir()
        (dest / "gleaner_cli.py").write_text("# stub\n", encoding="utf-8")
        return 0

    mod = _load()
    monkeypatch.setattr(mod.subprocess, "check_call", fake_call)
    root = mod.clone_repo(dest)
    assert root == dest.resolve()
    assert calls and "clone" in calls[0]
    assert mod.REPO_URL in calls[0]
