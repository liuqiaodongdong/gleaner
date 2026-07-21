import csv
from pathlib import Path
import run_els_batch as R


def csv_rows(p):
    with open(p, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _fake_md_download(session, doi, out_md, out_xml, *, timeout=90):
    Path(out_md).parent.mkdir(parents=True, exist_ok=True)
    Path(out_md).write_text("# md " + doi, encoding="utf-8")
    Path(out_xml).write_bytes(b"<xml/>")
    return True


def test_run_dedupes_and_writes_csv(tmp_path, monkeypatch):
    # 两刊各返回，含一个重复 DOI
    def fake_search(session, *, qs, pub, date, count, sort="date", timeout=50):
        if "Public" in pub:
            return [{"doi": "10.1016/a", "title": "A", "journal": pub, "year": "2024",
                     "openaccess": False, "pii": "", "authors": "X"}]
        return [{"doi": "10.1016/a", "title": "A", "journal": pub, "year": "2024",
                 "openaccess": False, "pii": "", "authors": "X"},
                {"doi": "10.1016/b", "title": "B", "journal": pub, "year": "2023",
                 "openaccess": False, "pii": "", "authors": "Y"}]

    monkeypatch.setattr(R.els, "search_journal", fake_search)
    monkeypatch.setattr(R.els, "download_els", _fake_md_download)
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
    assert all(r["source"] == "elsevier" and r["file_type"] == "MD" for r in rows)
    assert all(r["file_path"].endswith(".md") for r in rows)
    assert (out / "search.md").exists()


def test_run_drops_sibling_journal(tmp_path, monkeypatch):
    # pub 子串匹配会带回兄弟刊；精确按刊名过滤应剔除 "World Development Perspectives"
    def fake_search(session, *, qs, pub, date, count, sort="date", timeout=50):
        return [{"doi": "10.1016/wd", "title": "Real", "journal": "World Development",
                 "year": "2024", "openaccess": False, "pii": "", "authors": ""},
                {"doi": "10.1016/wdp", "title": "Sibling", "journal": "World Development Perspectives",
                 "year": "2024", "openaccess": False, "pii": "", "authors": ""}]

    monkeypatch.setattr(R.els, "search_journal", fake_search)
    monkeypatch.setattr(R.els, "download_els", _fake_md_download)
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
    def fake_search(session, *, qs, pub, date, count, sort="date", timeout=50):
        return [{"doi": "10.1016/new", "title": "N", "journal": pub, "year": "2024",
                 "openaccess": False, "pii": "", "authors": ""}]
    monkeypatch.setattr(R.els, "search_journal", fake_search)
    monkeypatch.setattr(R.els, "download_els", _fake_md_download)
    monkeypatch.setattr(R, "_sleep", lambda *a, **k: None)
    out = tmp_path / "reuse"; papers = out / "papers"; papers.mkdir(parents=True)
    (papers / "10.1016_old.pdf").write_bytes(b"%PDF stale")
    (papers / "10.1016_old.md").write_text("stale", encoding="utf-8")
    params = {"qs": "x", "date_from": "2015", "num": 5, "per_journal": 5,
              "journals": [{"name": "Aa", "issn": "1", "level": "L", "tier": 1}], "out": str(out)}
    R.run(params, session=object())
    names = {p.name for p in papers.glob("*")}
    assert "10.1016_old.pdf" not in names and "10.1016_old.md" not in names
    assert "10.1016_new.md" in names


def test_norm_title_strips_country_suffix():
    assert R._norm_title("Omega (United Kingdom)") == "omega"
    assert R._norm_title("World Development") != R._norm_title("World Development Perspectives")


def test_run_respects_num_cap(tmp_path, monkeypatch):
    def fake_search(session, *, qs, pub, date, count, sort="date", timeout=50):
        return [{"doi": f"10.1016/{pub[:2]}{i}", "title": "T", "journal": pub,
                 "year": "2024", "openaccess": False, "pii": "", "authors": ""}
                for i in range(20)]

    monkeypatch.setattr(R.els, "search_journal", fake_search)
    monkeypatch.setattr(R.els, "download_els", _fake_md_download)
    monkeypatch.setattr(R, "_sleep", lambda *a, **k: None)
    out = tmp_path / "b2"
    params = {"qs": "x", "date_from": "2015", "num": 5, "per_journal": 25,
              "journals": [{"name": "Aa", "issn": "1", "level": "L", "tier": 1},
                           {"name": "Bb", "issn": "2", "level": "L", "tier": 1}],
              "out": str(out)}
    res = R.run(params, session=object())
    assert res["downloaded"] == 5     # 命中 num 上限即停
