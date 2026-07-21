# run_els_batch.py —— Elsevier 订阅线批量入口（主力机本地，官方 API + API key）
# 读 JSON {qs, journals[], date_from, per_journal, num, out} → 逐刊检索→去重→取全文转MD→CSV+search.md
import csv, datetime, json, random, re, sys, time
from pathlib import Path
from acq.sources import els
from acq.els_config import get_api_key

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
             f"- qs: `{params.get('qs','')}`",
             f"- date_from: {params.get('date_from','')}",
             f"- num cap: {params.get('num')}  per_journal: {params.get('per_journal')}",
             f"- 检索刊数: {len(journals)}", "", "## 检索的期刊"]
    for j in journals:
        lines.append(f"- [tier{j.get('tier')}] {j.get('name')} ({j.get('issn')}) {j.get('level','')}")
    (out_dir / "search.md").write_text("\n".join(lines), encoding="utf-8")


def run(params: dict, session) -> dict:
    out_dir = Path(params["out"]); papers = out_dir / "papers"
    papers.mkdir(parents=True, exist_ok=True)
    for old in papers.glob("*"):  # 清旧批残留：重跑同名目录时避免混入上一版(不同论文)的 pdf/md/xml
        if old.suffix.lower() in (".pdf", ".md", ".xml"):
            old.unlink()
    qs = params["qs"]
    date = f"{params.get('date_from', '2015')}-{datetime.date.today().year}"
    per_journal = int(params.get("per_journal", 25))
    num = int(params.get("num", 25))
    sort = params.get("sort", "date")          # 窄题可传 "relevance"
    journals = params.get("journals", [])

    # 1) 逐刊检索 + 全局去重（DOI）
    seen, picked = set(), []
    for j in journals:
        if len(picked) >= num:
            break
        rows = els.search_journal(session, qs=qs, pub=j["name"], date=date, count=per_journal, sort=sort)
        # pub 是子串匹配——精确按刊名过滤，剔除同前缀的兄弟刊(如 World Development Perspectives)
        jn = _norm_title(j["name"])
        rows = [r for r in rows if _norm_title(r.get("journal", "")) == jn]
        for r in rows:
            if r["doi"] in seen:
                continue
            seen.add(r["doi"])
            r["level"] = j.get("level", ""); r["tier"] = j.get("tier", "")
            picked.append(r)
        _sleep(0.5, 1.2)
    picked = picked[:num]

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
