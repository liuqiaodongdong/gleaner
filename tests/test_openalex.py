import inspect
import pytest
from acq.sources.openalex import _parse_work, _iter_works, search

SAMPLE = {
    "doi": "https://doi.org/10.1093/qje/qjag031",
    "title": "What Jobs Come to Mind?",
    "publication_year": 2026,
    "open_access": {"is_oa": True, "oa_status": "hybrid", "oa_url": "https://doi.org/10.1093/qje/qjag031"},
    "primary_location": {"source": {"display_name": "The Quarterly Journal of Economics",
                                    "issn": ["0033-5533"]}, "pdf_url": None},
    "authorships": [{"author": {"display_name": "John J. Conlon"},
                     "institutions": [{"display_name": "Carnegie Mellon University"}]}],
}

def test_parse_work():
    w = _parse_work(SAMPLE)
    assert w["doi"] == "10.1093/qje/qjag031"      # 去 doi.org 前缀
    assert w["journal"].startswith("The Quarterly")
    assert w["is_oa"] is True and w["oa_status"] == "hybrid"
    assert w["authors"] == ["John J. Conlon"]

# --- fix: _iter_works 签名对齐规格 (params dict) ---

def test_iter_works_signature():
    """_iter_works 签名必须是 (params, num, mailto)，而非拆散的 filters/search str。"""
    sig = inspect.signature(_iter_works)
    names = list(sig.parameters.keys())
    assert names == ["params", "num", "mailto"], (
        f"签名不符合规格，实际: {names}"
    )

# --- fix: json.JSONDecodeError 在 _iter_works 内被捕获 ---

def test_iter_works_handles_html_body(monkeypatch):
    """OpenAlex 返回 HTML 错误页（CDN 429 / 服务降级）时，_iter_works 应优雅终止，
    不抛 json.JSONDecodeError，返回已收集结果（本例为空列表）。"""
    import acq.net as net_mod
    monkeypatch.setattr(net_mod, "get", lambda url, **kw: (200, {}, b"<html>CDN Error</html>"))
    results = list(_iter_works({}, 5, "test@example.com"))
    assert results == []

def test_iter_works_handles_http_error(monkeypatch):
    """HTTPError（如真实 429）时也应优雅终止，返回空列表。"""
    import urllib.error
    import acq.net as net_mod
    def raise_http(*a, **kw):
        raise urllib.error.HTTPError(None, 429, "Too Many Requests", {}, None)
    monkeypatch.setattr(net_mod, "get", raise_http)
    results = list(_iter_works({}, 5, "test@example.com"))
    assert results == []

# --- fix: search() 无 mailto 时抛 ValueError 而非静默降级 ---

def test_search_raises_without_mailto(monkeypatch):
    """未传 mailto 且无环境变量时，search() 必须抛 ValueError，不能静默用匿名池。"""
    monkeypatch.delenv("OPENALEX_MAILTO", raising=False)
    with pytest.raises(ValueError, match="mailto"):
        search("minimum wage")
