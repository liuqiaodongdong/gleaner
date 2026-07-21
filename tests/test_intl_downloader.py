# tests/test_intl_downloader.py
from pathlib import Path
from acq import intl_downloader as dl
from acq.guard import RateGuard

def test_oa_first(tmp_path, monkeypatch):
    monkeypatch.setattr(dl.oa, "download_oa", lambda doi, p, **k: Path(p).write_bytes(b"%PDF-"+b"x"*2000+b"%%EOF") or True)
    monkeypatch.setattr(dl.scihub, "download_scihub", lambda *a, **k: (_ for _ in ()).throw(AssertionError("不该走 Sci-Hub")))
    guards = {"oa": RateGuard("oa", 0, 99, tmp_path), "scihub": RateGuard("scihub", 0, 99, tmp_path)}
    path, src = dl.download({"doi": "10.1/x", "title": "T", "is_oa": True}, tmp_path, guards, email="e@x.com")
    assert src == "oa" and path.endswith(".pdf")

def test_scihub_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(dl.oa, "download_oa", lambda *a, **k: False)
    monkeypatch.setattr(dl.scihub, "download_scihub", lambda doi, p, **k: Path(p).write_bytes(b"%PDF-"+b"x"*2000+b"%%EOF") or True)
    guards = {"oa": RateGuard("oa", 0, 99, tmp_path), "scihub": RateGuard("scihub", 0, 99, tmp_path)}
    path, src = dl.download({"doi": "10.1/y", "title": "T2", "is_oa": False}, tmp_path, guards, email="e@x.com")
    assert src == "scihub"

def test_guard_blocks_scihub(tmp_path, monkeypatch):
    monkeypatch.setattr(dl.oa, "download_oa", lambda *a, **k: False)
    g = RateGuard("scihub", 0, 0, tmp_path)  # 配额=0
    guards = {"oa": RateGuard("oa", 0, 99, tmp_path), "scihub": g}
    path, src = dl.download({"doi": "10.1/z", "title": "T3", "is_oa": False}, tmp_path, guards, email="e@x.com")
    assert (path, src) == ("", "")
