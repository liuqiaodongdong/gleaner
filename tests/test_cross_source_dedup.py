# tests/test_cross_source_dedup.py
from pathlib import Path
import csv
from acq.normalize_corpus import merge_corpus

def test_merge_dedup(tmp_path):
    b1 = tmp_path / "cnki_b1"; b1.mkdir()
    with open(b1 / "metadata.csv", "w", encoding="utf-8-sig", newline="") as f:
        csv.writer(f).writerows([["title", "doi"], ["中文标题", "10.1/x"]])
    b2 = tmp_path / "intl_b2"; b2.mkdir()
    with open(b2 / "metadata.csv", "w", encoding="utf-8-sig", newline="") as f:
        csv.writer(f).writerows([["title", "doi", "source"], ["English Title", "10.1/X", "oa"]])
    out = merge_corpus(tmp_path)
    rows = list(csv.DictReader(open(out, encoding="utf-8-sig")))
    assert len(rows) == 1   # 10.1/x == 10.1/X 跨源去重
