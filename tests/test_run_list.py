# tests/test_run_list.py —— 题录采集离线单测，不依赖 live CNKI / 备用机 / playwright
import os, sys, csv, json
# 让 `python tests/test_run_list.py` 与 `python -m pytest` 两种方式都能 import 仓库根模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import run_list as r
import pytest


# ---- 假页面：模拟"翻页 N 次、每页若干题录"的列表页，喂进 harvest 循环 ----
class FakePage:
    """每次 extract 返回当前页题录，next 翻到下一页，模拟分页结果集。"""
    def __init__(self, pages):
        self.pages = pages          # list[list[dict]]
        self.idx = 0

    def extract(self, _page=None):
        return self.pages[self.idx] if self.idx < len(self.pages) else []

    def next(self, _page=None):
        if self.idx + 1 < len(self.pages):
            self.idx += 1
            return True
        return False


def _rec(title, cite="0"):
    return {"title": title, "url": "u/" + title, "authors": "张三;李四",
            "journal": "经济研究", "pub_date": "2024-01-01",
            "cite_count": cite, "download_count": "10"}


def test_load_params_keyword(tmp_path):
    pf = tmp_path / "p.json"
    pf.write_text(json.dumps({"keyword": "数字经济", "num": 50, "out": "b1"},
                             ensure_ascii=False), encoding="utf-8")
    p = r.load_params(pf)
    assert p["pro"] is False
    assert p["keyword"] == "数字经济"
    assert p["expression"] == "数字经济"   # 关键词模式下 expression 回落到 keyword
    assert p["num"] == 50 and p["out"] == "b1"


def test_load_params_pro(tmp_path):
    pf = tmp_path / "p.json"
    pf.write_text(json.dumps({"pro": True, "expression": "SU=数字 AND LY=经济研究",
                              "num": 200}, ensure_ascii=False), encoding="utf-8")
    p = r.load_params(pf)
    assert p["pro"] is True
    assert p["expression"] == "SU=数字 AND LY=经济研究"
    assert p["num"] == 200


def test_harvest_paginates_and_stops_at_no_next():
    fp = FakePage([[_rec("A"), _rec("B")], [_rec("C")]])
    recs = r.harvest(fp, num=100, extract_fn=fp.extract, next_fn=fp.next, log=lambda *a: None)
    assert [x["title"] for x in recs] == ["A", "B", "C"]   # 跨 2 页累积，没有下一页即止
    # 只保留约定的 7 列，不含 abstract/doi 等详情字段
    assert set(recs[0].keys()) == set(r.FIELDS)


def test_harvest_caps_at_num():
    fp = FakePage([[_rec("A"), _rec("B"), _rec("C")], [_rec("D")]])
    recs = r.harvest(fp, num=2, extract_fn=fp.extract, next_fn=fp.next, log=lambda *a: None)
    assert len(recs) == 2
    assert [x["title"] for x in recs] == ["A", "B"]
    assert fp.idx == 0   # 达标即停，不应翻页


def test_harvest_dedups_by_title():
    fp = FakePage([[_rec("A"), _rec("A")], [_rec("A"), _rec("B")]])
    recs = r.harvest(fp, num=100, extract_fn=fp.extract, next_fn=fp.next, log=lambda *a: None)
    assert [x["title"] for x in recs] == ["A", "B"]   # 同名只取一次


def test_save_csv_columns_and_rows(tmp_path):
    rows = [_rec("甲文", "12"), _rec("乙文", "3")]
    path = r.save_csv(rows, tmp_path)
    assert path.exists()
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == r.FIELDS              # 列顺序严格匹配
        got = list(reader)
    assert {row["title"] for row in got} == {"甲文", "乙文"}
    assert got[0]["journal"] == "经济研究"


def test_save_csv_merges_by_title(tmp_path):
    r.save_csv([_rec("甲文", "1")], tmp_path)
    r.save_csv([_rec("甲文", "99"), _rec("丙文", "5")], tmp_path)   # 同名覆盖更新
    with open(tmp_path / "metadata.csv", encoding="utf-8-sig", newline="") as f:
        rows = {row["title"]: row for row in csv.DictReader(f)}
    assert set(rows) == {"甲文", "丙文"}
    assert rows["甲文"]["cite_count"] == "99"        # 后写覆盖先写


def test_details_exact_columns_pagination_and_checkpoint(tmp_path):
    fp = FakePage([[_rec("甲"), _rec("甲")], [_rec("乙")]])
    visited = []

    def detail(item):
        visited.append(item["title"])
        return {"abstract": "摘要", "keywords": "数字经济;创新", "institution": "某大学",
                "fund": "", "doi": "不得输出", "title": "不得覆盖"}

    records = r.harvest(
        fp, 2, extract_fn=fp.extract, next_fn=fp.next, detail_fn=detail,
        save_fn=lambda rows: r.save_csv(rows, tmp_path, r.DETAIL_FIELDS),
    )
    assert visited == ["甲", "乙"]
    with (tmp_path / "metadata.csv").open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == [
            "title", "authors", "abstract", "keywords", "journal", "pub_date",
            "institution", "fund", "cite_count", "download_count", "url",
        ]
        assert list(reader) == records
    assert records[0]["title"] == "甲"
    assert records[0]["abstract"] == "摘要"
    assert records[0]["fund"] == ""
    assert records[0]["cite_count"] == "0"
    assert not (tmp_path / "papers").exists()


def test_detail_failure_preserves_completed_rows(tmp_path):
    fp = FakePage([[_rec("甲"), _rec("乙")]])

    def detail(item):
        if item["title"] == "乙":
            raise RuntimeError("详情失败")
        return {"abstract": "已完成"}

    with pytest.raises(RuntimeError, match="详情失败"):
        r.harvest(
            fp, 2, extract_fn=fp.extract, next_fn=fp.next, detail_fn=detail,
            save_fn=lambda rows: r.save_csv(rows, tmp_path, r.DETAIL_FIELDS),
        )
    with (tmp_path / "metadata.csv").open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    assert [row["title"] for row in rows] == ["甲"]
    assert rows[0]["abstract"] == "已完成"


def test_schema_upgrade_and_reject_destructive_reuse(tmp_path):
    r.save_csv([_rec("甲")], tmp_path)
    r.save_csv([{**_rec("甲"), "abstract": "摘要"}], tmp_path, r.DETAIL_FIELDS)
    before = (tmp_path / "metadata.csv").read_bytes()
    with pytest.raises(ValueError, match="out-name"):
        r.save_csv([_rec("乙")], tmp_path)
    assert (tmp_path / "metadata.csv").read_bytes() == before
    fulltext = tmp_path / "full"
    fulltext.mkdir()
    path = fulltext / "metadata.csv"
    path.write_text("title,file_path\n甲,papers/a.pdf\n", encoding="utf-8-sig")
    before = path.read_bytes()
    with pytest.raises(ValueError, match="out-name"):
        r.save_csv([], fulltext, r.DETAIL_FIELDS)
    assert path.read_bytes() == before


@pytest.mark.parametrize("fails", [False, True])
def test_collect_detail_closes_page_and_uses_strict_mode(monkeypatch, fails):
    from unittest.mock import Mock
    import scraper

    context = Mock()
    page = context.new_page.return_value
    extract = Mock(return_value={"abstract": "摘要"})
    if fails:
        extract.side_effect = RuntimeError("失败")
    monkeypatch.setattr(scraper, "extract_detail_metadata", extract)
    monkeypatch.setattr(scraper, "_random_delay", lambda _: None)
    if fails:
        with pytest.raises(RuntimeError):
            r.collect_detail(context, _rec("甲"))
    else:
        assert r.collect_detail(context, _rec("甲")) == {"abstract": "摘要"}
    extract.assert_called_once_with(page, "u/甲", strict=True)
    page.close.assert_called_once()


def test_detail_main_never_downloads(tmp_path, monkeypatch):
    from unittest.mock import Mock
    import browser
    import scraper
    import downloader

    def forbidden(*args, **kwargs):
        pytest.fail("题录模式不得调用下载器")

    monkeypatch.setattr(downloader, "download_paper", forbidden)
    monkeypatch.setattr(downloader, "is_already_downloaded", forbidden)
    context, page = Mock(), Mock()
    monkeypatch.setattr(browser, "launch_browser", lambda: (None, None, context, page))
    close = Mock()
    monkeypatch.setattr(browser, "close_browser", close)
    monkeypatch.setattr(browser, "save_cookies_after_captcha", lambda _: None)
    monkeypatch.setattr(scraper, "search_keyword", lambda *args: None)
    monkeypatch.setattr(scraper, "get_total_results", lambda _: 1)
    monkeypatch.setattr(scraper, "extract_list_items", lambda _: [_rec("甲")])
    monkeypatch.setattr(scraper, "extract_detail_metadata", lambda *args, **kw: {"abstract": "摘要"})
    monkeypatch.setattr(scraper, "_random_delay", lambda _: None)
    monkeypatch.setattr(r, "sort_by_citations", lambda _: None)
    params = tmp_path / "params.json"
    out = tmp_path / "out"
    params.write_text(json.dumps({"keyword": "测试", "num": 1, "details": True, "out": str(out)}),
                      encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["run_list.py", str(params)])
    r.main()
    close.assert_called_once()
    assert sorted(p.name for p in out.iterdir()) == ["metadata.csv"]
    with (out / "metadata.csv").open(encoding="utf-8-sig", newline="") as f:
        assert list(csv.DictReader(f))[0]["abstract"] == "摘要"


@pytest.mark.parametrize("strict", [False, True])
def test_detail_extraction_retry_exhaustion(monkeypatch, strict):
    from unittest.mock import Mock
    import scraper

    page = Mock()
    page.goto.side_effect = RuntimeError("加载失败")
    monkeypatch.setattr(scraper, "_check_captcha", lambda _: False)
    monkeypatch.setattr(scraper, "_random_delay", lambda _: None)
    monkeypatch.setattr(scraper, "MAX_RETRIES", 2)
    if strict:
        with pytest.raises(RuntimeError, match="论文详情采集失败"):
            scraper.extract_detail_metadata(page, "https://example.test/paper", strict=True)
    else:
        result = scraper.extract_detail_metadata(page, "https://example.test/paper")
        assert result["abstract"] == ""
    assert page.goto.call_count == 2


def test_strict_detail_rejects_generic_heading(monkeypatch):
    from unittest.mock import Mock
    import scraper

    page = Mock()
    # 拦截页也可能有 h1，不能仅凭 h1 判为论文详情。
    page.query_selector.side_effect = lambda selector: Mock() if "h1" in selector else None
    monkeypatch.setattr(scraper, "wait_for_captcha", lambda _: None)
    monkeypatch.setattr(scraper.time, "sleep", lambda _: None)
    monkeypatch.setattr(scraper, "_random_delay", lambda _: None)
    monkeypatch.setattr(scraper, "MAX_RETRIES", 1)
    with pytest.raises(RuntimeError, match="论文详情采集失败"):
        scraper.extract_detail_metadata(page, "https://example.test/paper", strict=True)


if __name__ == "__main__":
    # 无 pytest 时的兜底跑法：自建临时目录跑一遍断言
    import tempfile
    from pathlib import Path
    failures = 0
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        for fn in [test_load_params_keyword, test_load_params_pro,
                   test_harvest_paginates_and_stops_at_no_next, test_harvest_caps_at_num,
                   test_harvest_dedups_by_title, test_save_csv_columns_and_rows,
                   test_save_csv_merges_by_title]:
            try:
                # 给需要 tmp_path 的用例传子目录，其余无参
                if "tmp_path" in fn.__code__.co_varnames[:fn.__code__.co_argcount]:
                    sub = tmp / fn.__name__
                    sub.mkdir()
                    fn(sub)
                else:
                    fn()
                print(f"PASS {fn.__name__}")
            except AssertionError as e:
                failures += 1
                print(f"FAIL {fn.__name__}: {e}")
    sys.exit(1 if failures else 0)
