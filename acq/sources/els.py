# acq/sources/els.py —— Elsevier/ScienceDirect 官方 API 客户端
# Search API V2 (PUT) 专业检索 + Article Retrieval API 取全文 XML。
# 鉴权：X-ELS-APIKey（见 acq.els_config.get_api_key）；主力机本地跑；entitlement 端点不用。
import json
from pathlib import Path
import requests
from acq.sources.els_xml2md import xml_to_md

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
SEARCH_URL = "https://api.elsevier.com/content/search/sciencedirect"
ARTICLE_URL = "https://api.elsevier.com/content/article/doi/{doi}?view=FULL"


def make_session(api_key: str) -> requests.Session:
    s = requests.Session()
    s.trust_env = False  # 绕 Clash 直连铁律
    s.headers.update({"X-ELS-APIKey": api_key, "User-Agent": UA})
    return s


def search_journal(session, *, qs, pub, date, count=25, sort="date", timeout=50) -> list:
    """SD Search API V2：qs 布尔 + pub 精确刊名 + date 年份范围。
    sort: 'date'(新→旧) 或 'relevance'(相关性,窄题更对题)。返回结果 dict 列表。"""
    body = {"qs": qs, "pub": pub, "date": date,
            "display": {"show": int(count), "sortBy": sort}}
    try:
        r = session.put(SEARCH_URL, headers={"Content-Type": "application/json",
                                             "Accept": "application/json"},
                        data=json.dumps(body), timeout=timeout)
        if r.status_code != 200:
            return []
        results = r.json().get("results", []) or []
    except Exception:
        return []
    rows = []
    for it in results:
        doi = it.get("doi")
        if not doi:
            continue
        pubdate = it.get("publicationDate") or it.get("loadDate") or ""
        authors = it.get("authors") or []
        names = "; ".join(a.get("name", "") for a in authors) if isinstance(authors, list) else ""
        rows.append({"doi": doi, "title": it.get("title", ""),
                     "journal": it.get("sourceTitle", ""),
                     "year": pubdate[:4], "openaccess": bool(it.get("openAccess")),
                     "pii": it.get("pii", ""), "authors": names})
    return rows


def retrieve_fulltext_xml(session, doi, *, timeout=90):
    """取全文 XML。返回 (status_code, content_bytes)。"""
    try:
        r = session.get(ARTICLE_URL.format(doi=doi),
                        headers={"Accept": "text/xml"}, timeout=timeout)
        return r.status_code, r.content
    except Exception:
        return 0, b""


def download_els(session, doi, out_md, out_xml, *, timeout=90) -> bool:
    """取全文 XML → 转干净 MD，写 .md + .xml（留底）。成功返回 True。

    为何走 XML 不走 PDF（2026-06-29 实测浙工商权限）：订阅(非OA)文章的 Article Retrieval
    PDF 端点只返回 **1 页封面预览**(仅 OA 文章给完整 PDF)，网站 pdfft 又被 Cloudflare 403。
    而全文 XML 是**完整正文**(每节每段+表格转文本)、有机构权限、且比 PDF→MinerU 更干净(无 OCR 错)。
    代价=无图，但综述/抽取用的是文本，缺图不影响正文完整性。
    """
    st, body = retrieve_fulltext_xml(session, doi, timeout=timeout)
    if st != 200 or not body:
        return False
    try:
        md = xml_to_md(body)
    except Exception:
        return False
    if not md or len(md) < 50:   # 没拿到正经正文（可能只有题录）
        return False
    out_md = Path(out_md); out_xml = Path(out_xml)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_xml.write_bytes(body)
    out_md.write_text(md, encoding="utf-8")
    return True
