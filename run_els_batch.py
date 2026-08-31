# run_els_batch.py —— Elsevier 订阅线批量入口（主力机本地，官方 API + API key）
# 读 JSON {qs, journals[], date_from, per_journal, num, out} → 逐刊检索→去重→取全文转MD→CSV+search.md
import csv, datetime, json, random, re, sys, time
from pathlib import Path
from acq.sources import els
from acq.els_config import get_api_key
from acq.sources.els_query import normalize_els_query

FIELDS = ["source", "doi", "title", "authors", "journal", "year", "level", "tier",
          "openaccess", "url", "file_path", "file_type", "file_xml"]


def _sleep(a, b):
    time.sleep(random.uniform(a, b))


def _norm_title(s: str) -> str:
    """刊名归一：小写、去尾部括号限定(如 (United Kingdom))、压空白。用于精确匹配白名单刊。"""
    s = (s or "").lower().strip()
    s = re.sub(r"\s*\([^)]*\)\s*$", "", s)
    return re.sub(r"\s+", " ", s)


def _write_search_md(out_dir: Path, params: dict, journals: list):
    lines = ["# Elsevier 检索记录", "",
             f"- title/qs 布尔式: `{params.get('qs','')}`",
             f"- scope: `{params.get('scope', 'title')}`（title=题名；qs=全文，易下歪）",
             f"- sort: `{params.get('sort', 'relevance')}`",
             f"- date_from: {params.get('date_from','')}",
             f"- num cap: {params.get('num')}  per_journal: {params.get('per_journal')}",
             f"- 选刊: 相关度轮询（每刊最多 per_journal，避免名单前几本占满额度）",
             f"- 检索刊数: {len(journals)}", "", "## 检索的期刊"]
    for j in journals:
        lines.append(f"- [tier{j.get('tier')}] {j.get('name')} ({j.get('issn')}) {j.get('level','')}")
    (out_dir / "search.md").write_text("\n".join(lines), encoding="utf-8")


def _round_robin_pick(buckets: list, num: int) -> list:
    """各刊相关度列表轮询取篇，避免白名单前几本先填满 num。"""
    seen, picked = set(), []
    queues = [list(rows) for rows in buckets]
    while len(picked) < num and any(queues):
        progressed = False
        for rows in queues:
            if not rows or len(picked) >= num:
                continue
            r = rows.pop(0)
            doi = r.get("doi")
            if not doi or doi in seen:
                continue
            seen.add(doi)
            picked.append(r)
            progressed = True
        if not progressed:
            break
    return picked


def run(params: dict, session) -> dict:
    out_dir = Path(params["out"]); papers = out_dir / "papers"
    papers.mkdir(parents=True, exist_ok=True)
    for old in papers.glob("*"):  # 清旧批残留：重跑同名目录时避免混入上一版(不同论文)的 pdf/md/xml
        if old.suffix.lower() in (".pdf", ".md", ".xml"):
            old.unlink()
    qs = normalize_els_query(params["qs"])
    params["qs"] = qs
    date = f"{params.get('date_from', '2015')}-{datetime.date.today().year}"
    per_journal = int(params.get("per_journal", 10))
    num = int(params.get("num", 25))
    sort = params.get("sort", "relevance")
    scope = params.get("scope", "title")
    params["sort"] = sort
    params["scope"] = scope
    journals = params.get("journals", [])

    # 1) 逐刊题名相关度检索，凑够候选再轮询取篇（避免名单前几本占满，也不扫完全部刊）
    min_journals = min(len(journals), max(6, num))
    buckets = []
    for j in journals:
        rows = els.search_journal(
            session, qs=qs, pub=j["name"], date=date,
            count=per_journal, sort=sort, scope=scope,
        )
        # pub 是子串匹配——精确按刊名过滤，剔除同前缀的兄弟刊(如 World Development Perspectives)
        jn = _norm_title(j["name"])
        rows = [r for r in rows if _norm_title(r.get("journal", "")) == jn]
        for r in rows:
            r["level"] = j.get("level", "")
            r["tier"] = j.get("tier", "")
        buckets.append(rows)
        _sleep(0.5, 1.2)
        n_hits = sum(len(b) for b in buckets)
        if len(buckets) >= min_journals and n_hits >= num:
            break
    picked = _round_robin_pick(buckets, num)

    # 2) 取全文→MD
    rows_out = []
    for r in picked:
        doi = r["doi"]
        stem = doi.replace("/", "_")
        md = papers / f"{stem}.md"; xmlp = papers / f"{stem}.xml"
        ok = els.download_els(session, doi, md, xmlp)
        rows_out.append({
            "source": "elsevier", "doi": doi, "title": r.get("title", ""),
            "authors": r.get("authors", ""), "journal": r.get("journal", ""),
            "year": r.get("year", ""), "level": r.get("level", ""), "tier": r.get("tier", ""),
            "openaccess": r.get("openaccess", ""),
            "url": f"https://doi.org/{doi}",
            "file_path": str(md) if ok else "", "file_type": "MD" if ok else "",
            "file_xml": str(xmlp) if ok else "",
        })
        if ok:
            _sleep(0.8, 1.8)

    # 3) CSV + search.md
    tmp = out_dir / "metadata.csv.tmp"
    with open(tmp, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        for row in rows_out:
            w.writerow(row)
    tmp.replace(out_dir / "metadata.csv")
    _write_search_md(out_dir, params, journals)
    return {"found": len(picked), "downloaded": sum(1 for r in rows_out if r["file_path"])}


def main():
    pf = sys.argv[1] if len(sys.argv) > 1 else "els_params.json"
    params = json.loads(Path(pf).read_text(encoding="utf-8"))
    session = els.make_session(get_api_key())
    res = run(params, session)
    print(json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    main()
