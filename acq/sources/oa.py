# acq/sources/oa.py
import json
from urllib.parse import quote
from pathlib import Path
from acq import net
from acq.pdfcheck import is_plausible_pdf_url, response_looks_pdf, write_pdf_atomic

def _dedup(seq):
    out, seen = [], set()
    for x in seq:
        if x and x not in seen:
            seen.add(x); out.append(x)
    return out

def _unpaywall_candidates(data: dict) -> list[str]:
    repo, pub = [], []
    best = data.get("best_oa_location") or {}
    locs = data.get("oa_locations") or []
    for loc in ([best] if best else []) + locs:
        u = loc.get("url_for_pdf")
        if not u:
            continue
        (repo if loc.get("host_type") == "repository" else pub).append(u)
    return _dedup(repo + pub)

def _crossref_candidates(data: dict) -> list[str]:
    msg = data.get("message") or {}
    return _dedup(l.get("URL") for l in (msg.get("link") or [])
                  if (l.get("content-type") or "").lower() == "application/pdf")

def _doaj_candidates(data: dict) -> list[str]:
    """从 DOAJ API 响应中提取 fulltext/pdf 链接。"""
    results = data.get("results") or []
    out = []
    for article in results:
        bib = article.get("bibjson") or {}
        for link in (bib.get("link") or []):
            url = link.get("url")
            if url and link.get("type") in ("fulltext", "pdf"):
                out.append(url)
    return _dedup(out)

def _openalex_candidates(data: dict) -> list[str]:
    """扫 OpenAlex 的 oa_url + best_oa_location + 全部 locations[].pdf_url。
    关键：很多 green OA(NBER/EconStor/仓库镜像)只出现在 locations[] 里，
    只看 best_oa_location/oa_url 会漏掉一大批(尤其近年顶刊的工作论文版)。"""
    out = []
    oa = data.get("open_access") or {}
    if oa.get("oa_url"):
        out.append(oa["oa_url"])
    best = data.get("best_oa_location") or {}
    if best.get("pdf_url"):
        out.append(best["pdf_url"])
    for loc in (data.get("locations") or []):
        if loc.get("pdf_url"):
            out.append(loc["pdf_url"])
    return _dedup(out)

def resolve_oa_pdf_urls(doi: str, *, email: str) -> list[str]:
    """按 Unpaywall→OpenAlex→Crossref→DOAJ 顺序收集候选 PDF 直链，repo 优先于 publisher。"""
    cands = []
    try:  # Unpaywall
        s, _, b = net.get(f"https://api.unpaywall.org/v2/{quote(doi)}?email={email}")
        if s == 200:
            cands += _unpaywall_candidates(json.loads(b))
    except Exception:
        pass
    try:  # OpenAlex（扫 oa_url + best + 全部 locations[].pdf_url，含 green OA 镜像如 NBER/EconStor）
        s, _, b = net.get(f"https://api.openalex.org/works/doi:{quote(doi)}?mailto={email}")
        if s == 200:
            cands += _openalex_candidates(json.loads(b))
    except Exception:
        pass
    try:  # Crossref
        s, _, b = net.get(f"https://api.crossref.org/works/{quote(doi)}")
        if s == 200:
            cands += _crossref_candidates(json.loads(b))
    except Exception:
        pass
    try:  # DOAJ
        s, _, b = net.get(f"https://doaj.org/api/search/articles/doi:{quote(doi)}?pageSize=1")
        if s == 200:
            cands += _doaj_candidates(json.loads(b))
    except Exception:
        pass
    return [u for u in _dedup(cands) if is_plausible_pdf_url(u)]

def download_oa(doi: str, out_path: Path, *, email: str) -> bool:
    for url in resolve_oa_pdf_urls(doi, email=email):
        try:
            r = net.get_stream(url)
            try:
                first = r.read(8192)
                if not response_looks_pdf(first, r.headers.get("Content-Type", "")):
                    continue
                def _it():
                    yield first
                    while True:
                        c = r.read(65536)
                        if not c:
                            break
                        yield c
                ok = write_pdf_atomic(_it(), out_path)
                if ok:
                    return True
            finally:
                r.close()
        except Exception:
            continue
    return False
