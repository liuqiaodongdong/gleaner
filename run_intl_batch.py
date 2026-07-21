# run_intl_batch.py — 国际论文批量采集入口（发现→去重→分层下载→统一CSV）
import csv, json, sys
from pathlib import Path
from acq.guard import RateGuard
from acq.cookie_store import CookieStore
from acq.identifiers import normalize_doi_unicode
from acq.sources import openalex
from acq import intl_downloader

FIELDS = ["source", "doi", "oa_status", "title", "authors", "journal",
          "year", "pdf_url", "url", "file_path", "file_type"]
STATE_DIR = Path(__file__).parent / "acq" / "guard_state"


def unified_fields():
    return list(FIELDS)


def dedup_by_doi(rows):
    out, seen = [], set()
    for row in rows:
        d = (row.get("doi") or "").lower()
        if d and d in seen:
            continue
        if d:
            seen.add(d)
        out.append(row)
    return out


def save_csv(rows, out_dir):
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "metadata.csv"
    tmp = out_dir / "metadata.csv.tmp"
    with open(tmp, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow(row)
    tmp.replace(path)


def main():
    pf = sys.argv[1] if len(sys.argv) > 1 else "intl_params.json"
    p = json.loads(Path(pf).read_text(encoding="utf-8"))
    query, num = p.get("query", ""), int(p.get("num", 25))
    out_dir = Path(p.get("out", "out_intl")); papers = out_dir / "papers"
    sources = p.get("sources", ["oa", "nber", "scihub"])
    email = p.get("email", "Libby_Stantoncsc@writeme.com")
    scihub_on = "scihub" in sources

    guards = {
        "oa": RateGuard("oa", min_interval=2, max_per_day=10000, state_dir=STATE_DIR),
        "nber": RateGuard("nber", min_interval=2, max_per_day=10000, state_dir=STATE_DIR),
        "scihub": RateGuard("scihub", min_interval=10, max_per_day=100, state_dir=STATE_DIR),
        "carsi": RateGuard("carsi", min_interval=15, max_per_day=50, state_dir=STATE_DIR),
    }
    nber_on = "nber" in sources
    carsi_on = "carsi" in sources
    cfg = json.loads((Path(__file__).parent / "acq" / "data" / "publisher_carsi.json").read_text("utf-8"))
    store = CookieStore(Path(__file__).parent / "acq" / "cookies" / "carsi")
    # 注意：openalex.search 的 mailto 为强制参数(无默认)，必须显式传，否则 raise
    # 先规范化 DOI（修全角连字符等 Unicode 变体），再去重，确保去重以规范化后的值比较
    raw_metas = openalex.search(query, num, year_from=p.get("year_from"),
                                issn=p.get("issn"), mailto=email)
    for m in raw_metas:
        m["doi"] = normalize_doi_unicode(m.get("doi") or "") or m.get("doi", "")
    metas = dedup_by_doi(raw_metas)
    rows = []
    for m in metas:
        # DOI 已在 dedup 前规范化，无需再次处理
        fp, src = intl_downloader.download(
            m, papers, guards, email=email, scihub_enabled=scihub_on,
            nber_enabled=nber_on, carsi_enabled=carsi_on, carsi_store=store, carsi_cfg=cfg)
        rows.append({"source": src or "", "doi": m.get("doi", ""), "oa_status": m.get("oa_status", ""),
                     "title": m.get("title", ""), "authors": "; ".join(m.get("authors", [])),
                     "journal": m.get("journal", ""), "year": m.get("year", ""),
                     "pdf_url": m.get("oa_url", ""), "url": f"https://doi.org/{m.get('doi','')}",
                     "file_path": fp, "file_type": "PDF" if fp else ""})
    save_csv(rows, out_dir)
    print(json.dumps({"query": query, "found": len(metas),
                      "downloaded": sum(1 for r in rows if r["file_path"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
