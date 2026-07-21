# acq/normalize_corpus.py — 跨源 corpus 归一 + DOI 去重，喂 0131 消费侧
import csv
from pathlib import Path

# 统一列，与 run_intl_batch.py 的 FIELDS 保持一致
FIELDS = ["source", "doi", "oa_status", "title", "authors", "journal",
          "year", "pdf_url", "url", "file_path", "file_type"]


def _norm_doi(doi: str) -> str:
    """DOI 规范化：去首尾空格、转小写，用于去重比较。"""
    return doi.strip().lower()


def _read_batch_csv(path: Path) -> list[dict]:
    """读单个 metadata.csv，补齐缺失列为空串。"""
    rows = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            normed = {field: row.get(field, "") for field in FIELDS}
            rows.append(normed)
    return rows


def merge_corpus(corpus_dir: Path) -> Path:
    """扫 corpus_dir 下所有 */metadata.csv，补列、DOI 去重，输出 merged_metadata.csv。

    去重策略：DOI 小写比较；无 DOI 的行退而用 title 小写去重。
    返回 merged_metadata.csv 的路径。
    """
    corpus_dir = Path(corpus_dir)
    all_rows: list[dict] = []
    for csv_path in sorted(corpus_dir.glob("*/metadata.csv")):
        all_rows.extend(_read_batch_csv(csv_path))

    # 按 DOI（无则 title）去重
    seen: set[str] = set()
    deduped: list[dict] = []
    for row in all_rows:
        doi = _norm_doi(row.get("doi", ""))
        if doi:
            key = doi
        else:
            key = row.get("title", "").strip().lower()
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        deduped.append(row)

    out_path = corpus_dir / "merged_metadata.csv"
    tmp_path = corpus_dir / "merged_metadata.csv.tmp"
    with open(tmp_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(deduped)
    tmp_path.replace(out_path)
    return out_path
