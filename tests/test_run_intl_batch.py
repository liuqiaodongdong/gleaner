# tests/test_run_intl_batch.py
from pathlib import Path
import run_intl_batch as r

def test_dedup_by_doi():
    rows = [{"doi": "10.1/a", "title": "A"}, {"doi": "10.1/A", "title": "A dup"}, {"doi": "", "title": "X"}]
    out = r.dedup_by_doi(rows)
    assert len(out) == 2   # 10.1/a 与 10.1/A 视同一(小写)，空 DOI 保留
    dois = [row["doi"] for row in out]
    titles = [row["title"] for row in out]
    assert "10.1/a" in dois      # 首个出现的 DOI 保留
    assert "10.1/A" not in dois  # 大写重复项丢弃
    assert "X" in titles         # 空 DOI 行始终保留

def test_save_csv_unified(tmp_path):
    rows = [{"source": "oa", "doi": "10.1/a", "title": "T", "file_type": "PDF"}]
    r.save_csv(rows, tmp_path)
    txt = (tmp_path / "metadata.csv").read_text("utf-8-sig")
    assert "source" in txt and "oa_status" in txt and "10.1/a" in txt
