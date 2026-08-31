"""legacy MCP：CNKI 工具注册与 prepare/分级解析。

生产入口已迁至 gleaner_cli.py；本文件仅保留 acq_mcp 分发与注册的回归。
"""
from __future__ import annotations

import inspect
import json
from pathlib import Path
from unittest import mock

import acq_mcp


def test_cnki_prepare_registered():
    assert hasattr(acq_mcp, "cnki_prepare")
    assert hasattr(acq_mcp, "cnki_collect")
    assert hasattr(acq_mcp, "cnki_list")


def test_cnki_prepare_params():
    params = inspect.signature(acq_mcp.cnki_prepare).parameters
    assert params["topic"].annotation is str
    assert params["concept_groups"].annotation is str
    assert "year_from" in params


def test_cnki_collect_has_level_params():
    params = inspect.signature(acq_mcp.cnki_collect).parameters
    for name in ("level", "search_md", "topic", "range_label", "query", "num"):
        assert name in params


def test_cnki_prepare_end_to_end(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(acq_mcp, "PROJECT_ROOT", tmp_path)
    raw = acq_mcp.cnki_prepare(
        topic="数字经济",
        concept_groups=json.dumps(
            [{"name": "数字经济", "keywords": ["数字经济", "数字化", "数据要素"]}],
            ensure_ascii=False,
        ),
        year_from="2020",
        num=15,
    )
    data = json.loads(raw)
    assert data["ok"] is True
    assert Path(data["search_md"]).is_file()
    assert "LY = (" in data["levels"]["L1"]
    assert data["tier_counts"]["tier1"] >= 1


def test_cnki_dispatch_tiered_calls_run_collect(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(acq_mcp, "PROJECT_ROOT", tmp_path)
    raw = acq_mcp.cnki_prepare(
        topic="tfp",
        concept_groups='[{"name":"tfp","keywords":["全要素生产率"]}]',
        year_from="2015",
    )
    smd = json.loads(raw)["search_md"]

    captured = {}

    def fake_run(query, num=20, pro=False, out_name="", script="run_batch.py", extra=None):
        captured.update(query=query, num=num, pro=pro, out_name=out_name, script=script, extra=extra)
        return {"ok": True, "titles": []}

    monkeypatch.setattr(acq_mcp, "_run_collect", fake_run)
    out = acq_mcp._cnki_dispatch(
        query="", num=12, pro=False, out_name="", script="run_batch.py",
        level="L1", search_md=smd,
    )
    assert out["ok"] is True
    assert captured["pro"] is True
    assert "LY =" in captured["query"]
    assert captured["num"] == 12
    assert captured["extra"]["level"] == "L1"


def test_cnki_dispatch_requires_query_without_level():
    try:
        acq_mcp._cnki_dispatch("", 10, False, "", "run_batch.py")
        assert False, "should raise"
    except ValueError as e:
        assert "query" in str(e)
