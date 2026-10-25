import csv
from pathlib import Path
import run_els_batch as R


def csv_rows(p):
    with open(p, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _fake_pdf_download(session, doi, out_pdf, out_xml, *, timeout=90):
    Path(out_pdf).parent.mkdir(parents=True, exist_ok=True)
    Path(out_pdf).write_bytes(b"%PDF test stub")
    Path(out_xml).write_bytes(b"<xml/>")
    return {"ok": True, "pdf_ok": True, "xml_ok": True, "error": "",
            "pdf_pages": 2, "expected_pdf_pages": 2, "pdf_page_count_verified": True}


def test_run_dedupes_and_writes_csv(tmp_path, monkeypatch):
    # 两刊各返回，含一个重复 DOI
    def fake_search(session, *, qs, pub, date, count, sort="relevance", scope="title", timeout=50):
        if "Public" in pub:
            return [{"doi": "10.1016/a", "title": "A", "journal": pub, "year": "2024",
                     "openaccess": False, "pii": "", "authors": "X"}]
        return [{"doi": "10.1016/a", "title": "A", "journal": pub, "year": "2024",
                 "openaccess": False, "pii": "", "authors": "X"},
                {"doi": "10.1016/b", "title": "B", "journal": pub, "year": "2023",
                 "openaccess": False, "pii": "", "authors": "Y"}]

    monkeypatch.setattr(R.els, "search_journal", fake_search)
    monkeypatch.setattr(R.els, "download_els", _fake_pdf_download)
    monkeypatch.setattr(R, "_sleep", lambda *a, **k: None)

    out = tmp_path / "batch1"
    params = {"qs": "tax", "date_from": "2015",
              "journals": [{"name": "Journal of Public Economics", "issn": "0047-2727",
                            "level": "A++类期刊", "tier": 1},
                           {"name": "World Development", "issn": "0305-750X",
                            "level": "A+类期刊", "tier": 2}],
              "per_journal": 25, "num": 10, "out": str(out)}
    res = R.run(params, session=object())
    assert res["found"] == 2          # a,b 去重后 2 篇
    assert res["downloaded"] == 2
    rows = csv_rows(out / "metadata.csv")
    assert {r["doi"] for r in rows} == {"10.1016/a", "10.1016/b"}
    assert all(r["source"] == "elsevier" and r["file_type"] == "PDF" for r in rows)
    assert all(r["file_path"].endswith(".pdf") for r in rows)
    assert (out / "search.md").exists()


def test_run_drops_sibling_journal(tmp_path, monkeypatch):
    # pub 子串匹配会带回兄弟刊；精确按刊名过滤应剔除 "World Development Perspectives"
    def fake_search(session, *, qs, pub, date, count, sort="relevance", scope="title", timeout=50):
        return [{"doi": "10.1016/wd", "title": "Real", "journal": "World Development",
                 "year": "2024", "openaccess": False, "pii": "", "authors": ""},
                {"doi": "10.1016/wdp", "title": "Sibling", "journal": "World Development Perspectives",
                 "year": "2024", "openaccess": False, "pii": "", "authors": ""}]

    monkeypatch.setattr(R.els, "search_journal", fake_search)
    monkeypatch.setattr(R.els, "download_els", _fake_pdf_download)
    monkeypatch.setattr(R, "_sleep", lambda *a, **k: None)
    out = tmp_path / "wd"
    params = {"qs": "x", "date_from": "2015", "num": 10, "per_journal": 25,
              "journals": [{"name": "World Development", "issn": "0305-750X",
                            "level": "A+类期刊", "tier": 2}], "out": str(out)}
    res = R.run(params, session=object())
    assert res["found"] == 1
    rows = csv_rows(out / "metadata.csv")
    assert [r["doi"] for r in rows] == ["10.1016/wd"]


def test_run_clears_stale_artifacts(tmp_path, monkeypatch):
    # 重跑同名目录：上一版残留的 pdf/md/xml 应被清掉，只剩本次产物
    def fake_search(session, *, qs, pub, date, count, sort="relevance", scope="title", timeout=50):
        return [{"doi": "10.1016/new", "title": "N", "journal": pub, "year": "2024",
                 "openaccess": False, "pii": "", "authors": ""}]
    monkeypatch.setattr(R.els, "search_journal", fake_search)
    monkeypatch.setattr(R.els, "download_els", _fake_pdf_download)
    monkeypatch.setattr(R, "_sleep", lambda *a, **k: None)
    out = tmp_path / "reuse"; papers = out / "papers"; papers.mkdir(parents=True)
    (papers / "10.1016_old.pdf").write_bytes(b"%PDF stale")
    (papers / "10.1016_old.md").write_text("stale", encoding="utf-8")
    params = {"qs": "x", "date_from": "2015", "num": 5, "per_journal": 5,
              "journals": [{"name": "Aa", "issn": "1", "level": "L", "tier": 1}], "out": str(out)}
    R.run(params, session=object())
    names = {p.name for p in papers.glob("*")}
    assert "10.1016_old.pdf" not in names and "10.1016_old.md" not in names
    assert "10.1016_new.pdf" in names
    assert "10.1016_new.xml" in names
    assert "10.1016_new.md" not in names


def test_norm_title_strips_country_suffix():
    assert R._norm_title("Omega (United Kingdom)") == "omega"
    assert R._norm_title("World Development") != R._norm_title("World Development Perspectives")


def test_run_respects_num_cap(tmp_path, monkeypatch):
    def fake_search(session, *, qs, pub, date, count, sort="relevance", scope="title", timeout=50):
        return [{"doi": f"10.1016/{pub[:2]}{i}", "title": "T", "journal": pub,
                 "year": "2024", "openaccess": False, "pii": "", "authors": ""}
                for i in range(20)]

    monkeypatch.setattr(R.els, "search_journal", fake_search)
    monkeypatch.setattr(R.els, "download_els", _fake_pdf_download)
    monkeypatch.setattr(R, "_sleep", lambda *a, **k: None)
    out = tmp_path / "b2"
    params = {"qs": "x", "date_from": "2015", "num": 5, "per_journal": 25,
              "journals": [{"name": "Aa", "issn": "1", "level": "L", "tier": 1},
                           {"name": "Bb", "issn": "2", "level": "L", "tier": 1}],
              "out": str(out)}
    res = R.run(params, session=object())
    assert res["downloaded"] == 5     # 命中 num 上限即停
    dois = [r["doi"] for r in csv_rows(out / "metadata.csv")]
    # 轮询：不应被第一本刊的 20 篇占满
    assert any(d.startswith("10.1016/Aa") for d in dois)
    assert any(d.startswith("10.1016/Bb") for d in dois)


def test_round_robin_pick_interleaves():
    a = [{"doi": "a1"}, {"doi": "a2"}, {"doi": "a3"}]
    b = [{"doi": "b1"}, {"doi": "b2"}]
    assert [r["doi"] for r in R._round_robin_pick([a, b], 4)] == ["a1", "b1", "a2", "b2"]


def test_partial_pdf_failure_preserves_xml_and_continues(tmp_path, monkeypatch):
    def search(*args, **kwargs):
        return [{"doi": f"10.1016/{name}", "title": name, "journal": "J"} for name in ("failed", "success")]
    def download(session, doi, pdf, xml):
        result = _fake_pdf_download(session, doi, pdf, xml)
        if doi.endswith("failed"):
            Path(pdf).unlink()
            result.update(ok=False, pdf_ok=False, pdf_pages=None, error="pdf_http_403")
        return result
    monkeypatch.setattr(R.els, "search_journal", search)
    monkeypatch.setattr(R.els, "download_els", download)
    monkeypatch.setattr(R, "_sleep", lambda *a: None)
    result = R.run({"out": str(tmp_path), "qs": "x", "num": 2, "journals": [{"name": "J"}]}, object())
    assert result == {"ok": False, "found": 2, "downloaded": 1, "downloaded_xml": 2, "failed_downloads": 1}
    failed, success = csv_rows(tmp_path / "metadata.csv")
    assert failed["download_status"] == "xml_only" and failed["download_error"] == "pdf_http_403"
    assert failed["file_path"] == "" and Path(failed["file_xml"]).exists()
    assert success["download_status"] == "complete" and Path(success["file_path"]).exists()


def test_empty_batch_is_not_success(tmp_path, monkeypatch):
    monkeypatch.setattr(R.els, "search_journal", lambda *a, **k: [])
    monkeypatch.setattr(R, "_sleep", lambda *a: None)
    result = R.run({"out": str(tmp_path), "qs": "x", "journals": [{"name": "J"}]}, object())
    assert result["ok"] is False and result["downloaded"] == 0


def test_main_propagates_incomplete_batch_exit(monkeypatch, tmp_path):
    import json
    params = tmp_path / "params.json"
    params.write_text(json.dumps({}), encoding="utf-8")
    monkeypatch.setattr(R.sys, "argv", ["run_els_batch.py", str(params)])
    monkeypatch.setattr(R, "get_api_key", lambda: "test-only")
    monkeypatch.setattr(R.els, "make_session", lambda key: object())
    monkeypatch.setattr(R, "run", lambda *a: {"ok": False, "found": 2, "downloaded": 1})
    assert R.main() == 1
