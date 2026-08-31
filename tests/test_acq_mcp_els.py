"""legacy MCP：Elsevier 工具注册与签名。

生产入口已迁至 gleaner_cli.py；本文件仅保留 acq_mcp 注册回归。
"""
import inspect

import pytest

pytest.importorskip("mcp")
import acq_mcp


def test_els_collect_registered():
    assert hasattr(acq_mcp, "els_collect")


def test_els_collect_no_return_annotation():
    assert inspect.signature(acq_mcp.els_collect).return_annotation is inspect.Signature.empty


def test_els_collect_params_annotated():
    params = inspect.signature(acq_mcp.els_collect).parameters
    assert params["query"].annotation is str
    assert params["tier"].annotation is str
    assert "year_from" in params and "per_journal" in params
    assert "sort" in params and "scope" in params
