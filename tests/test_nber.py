# tests/test_nber.py
import json
from acq.sources import nber


def test_norm_title():
    assert nber._norm_title("Global  Value-Chain!") == "global value chain"


def test_title_match():
    assert nber._title_match("Global Sourcing", "Global Sourcing")
    # NBER WP 带副标题，应匹配
    assert nber._title_match("Global Sourcing", "Global Sourcing: Theory and Evidence")
    # 不相关标题不匹配
    assert not nber._title_match("Global Sourcing", "Monetary Policy in Production Networks")
    # 太短不匹配（避免误命中）
    assert not nber._title_match("Trade", "Trade")


def test_parse_search():
    sample = {"results": [
        {"title": "Some Paper", "url": "/papers/w33000"},
        {"title": "Not A Paper", "url": "/people/john"},   # 非 w 号，丢弃
    ]}
    r = nber._parse_search(sample)
    assert len(r) == 1
    assert r[0]["number"] == "w33000"
    assert r[0]["pdf_url"] == "https://www.nber.org/system/files/working_papers/w33000/w33000.pdf"


def test_search_nber_monkeypatched(monkeypatch):
    sample = {"results": [{"title": "X Paper", "url": "/papers/w1"}]}
    monkeypatch.setattr(nber.net, "get", lambda url: (200, {}, json.dumps(sample).encode()))
    r = nber.search_nber("X Paper")
    assert r and r[0]["number"] == "w1" and r[0]["pdf_url"].endswith("/w1/w1.pdf")
