import json
import os
from pathlib import Path

import pytest

from acq import cli_support as cs


def test_resolve_root_prefers_cli_over_env(tmp_path, monkeypatch):
    monkeypatch.setenv("GLEANER_ROOT", str(tmp_path / "env_root"))
    (tmp_path / "env_root").mkdir()
    cli = tmp_path / "cli_root"
    cli.mkdir()
    assert cs.resolve_root(str(cli)) == cli.resolve()


def test_resolve_root_uses_env(tmp_path, monkeypatch):
    r = tmp_path / "from_env"
    r.mkdir()
    monkeypatch.setenv("GLEANER_ROOT", str(r))
    assert cs.resolve_root(None) == r.resolve()


def test_load_credentials_from_dotenv(tmp_path):
    (tmp_path / ".env").write_text(
        "CJY_USER=u1\nCJY_PASS=secret\nACQ_PROXY=http://127.0.0.1:9\n# comment\n",
        encoding="utf-8",
    )
    creds = cs.load_credentials(tmp_path)
    assert creds["CJY_USER"] == "u1"
    assert creds["CJY_PASS"] == "secret"
    assert creds["ACQ_PROXY"] == "http://127.0.0.1:9"


def test_load_credentials_from_mcp_json_env(tmp_path):
    mcp = {
        "mcpServers": {
            "gleaner": {
                "env": {"CJY_SOFTID": "978958", "ACQ_PROXY": "http://127.0.0.1:10808"}
            }
        }
    }
    (tmp_path / ".mcp.json").write_text(json.dumps(mcp), encoding="utf-8")
    creds = cs.load_credentials(tmp_path)
    assert creds["CJY_SOFTID"] == "978958"
    assert "http://127.0.0.1:10808" in creds["ACQ_PROXY"]


def test_load_credentials_dotenv_wins_over_mcp_json(tmp_path):
    """同键时 .env 优先，.mcp.json 仅补缺。"""
    (tmp_path / ".env").write_text(
        "ACQ_PROXY=http://from-dotenv:1\nCJY_USER=from_env\n",
        encoding="utf-8",
    )
    mcp = {
        "mcpServers": {
            "gleaner": {
                "env": {
                    "ACQ_PROXY": "http://from-mcp:9",
                    "CJY_USER": "from_mcp",
                    "CJY_SOFTID": "only_mcp",
                }
            }
        }
    }
    (tmp_path / ".mcp.json").write_text(json.dumps(mcp), encoding="utf-8")
    creds = cs.load_credentials(tmp_path)
    assert creds["ACQ_PROXY"] == "http://from-dotenv:1"
    assert creds["CJY_USER"] == "from_env"
    assert creds["CJY_SOFTID"] == "only_mcp"


def test_run_logged_default_no_timeout(tmp_path, monkeypatch):
    """确保调用 subprocess 时 timeout 为 None（除非显式传入）。"""
    calls = {}

    class FakePopen:
        def __init__(self, *a, **k):
            calls["kwargs"] = k
            self.stdout = iter(["hello\n"])
            self.stderr = iter([])
            self.returncode = 0

        def wait(self, timeout=None):
            calls["wait_timeout"] = timeout
            return 0

    monkeypatch.setattr(cs.subprocess, "Popen", FakePopen)
    log = tmp_path / "t.log"
    code = cs.run_logged(
        ["echo"], cwd=tmp_path, log_path=log, env=dict(os.environ), timeout=None
    )
    assert code == 0
    # Popen 本身不应带 timeout；wait 可用 None
    assert calls["kwargs"].get("timeout") is None
    assert log.read_text(encoding="utf-8")


def test_summarize_batch_counts(tmp_path):
    out = tmp_path / "batch"
    papers = out / "papers"
    papers.mkdir(parents=True)
    (out / "metadata.csv").write_text(
        "title,authors\n甲,A\n乙,B\n", encoding="utf-8-sig"
    )
    (papers / "a.pdf").write_bytes(b"%PDF")
    (papers / "b.pdf").write_bytes(b"%PDF")
    s = cs.summarize_batch(out, file_glob="*.pdf")
    assert s["metadata_rows"] == 2
    assert s["downloaded_files"] == 2
    assert s["titles"] == ["甲", "乙"]


_MIN_SEARCH_MD = """# CNKI Search: 主题A

## L1 — top

```text
(SU %= 'a') AND LY = ('经济研究') AND YE >= '2020'
```

## L2 — core

```text
(SU %= 'a' OR SU %= 'b') AND LY = ('管理世界') AND YE >= '2020'
```
"""


def test_resolve_tiered_expression_from_search_md(tmp_path):
    smd = tmp_path / "search.md"
    smd.write_text(_MIN_SEARCH_MD, encoding="utf-8")
    expr, path, level = cs.resolve_tiered_expression(
        tmp_path, "L1", search_md=str(smd)
    )
    assert level == "L1"
    assert path == str(smd)
    assert "LY = (" in expr
    assert "经济研究" in expr


def test_resolve_tiered_expression_from_topic(tmp_path):
    topic = "主题A"
    d = tmp_path / "keyword_workspace" / topic / "2020_2026"
    d.mkdir(parents=True)
    (d / "search.md").write_text(_MIN_SEARCH_MD, encoding="utf-8")
    expr, path, level = cs.resolve_tiered_expression(
        tmp_path, "l2", topic=topic
    )
    assert level == "L2"
    assert "管理世界" in expr
    assert path.endswith("search.md")


def test_resolve_tiered_expression_invalid_level(tmp_path):
    with pytest.raises(ValueError, match="level"):
        cs.resolve_tiered_expression(tmp_path, "L9", search_md="x")


def test_resolve_tiered_expression_requires_search_or_topic(tmp_path):
    with pytest.raises(ValueError, match="search_md"):
        cs.resolve_tiered_expression(tmp_path, "L1")
