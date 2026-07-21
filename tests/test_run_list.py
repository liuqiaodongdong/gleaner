# tests/test_run_list.py —— 题录采集离线单测，不依赖 live CNKI / 备用机 / playwright
import os, sys, csv, json
# 让 `python tests/test_run_list.py` 与 `python -m pytest` 两种方式都能 import 仓库根模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import run_list as r


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
