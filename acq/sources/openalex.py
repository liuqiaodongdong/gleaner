import json
import os
import urllib.error
from urllib.parse import urlencode
from acq import net
from acq.identifiers import normalize_doi

BASE = "https://api.openalex.org/works"
ECON_CONCEPT = "C162324750"


def _parse_work(w: dict) -> dict:
    oa = w.get("open_access") or {}
    src = (w.get("primary_location") or {}).get("source") or {}
    auths = w.get("authorships") or []
    return {
        "doi": normalize_doi(w.get("doi") or "") or "",
        "title": w.get("title") or "",
        "year": w.get("publication_year"),
        "journal": src.get("display_name") or "",
        "is_oa": bool(oa.get("is_oa")),
        "oa_status": oa.get("oa_status") or "",
        "oa_url": oa.get("oa_url") or (w.get("primary_location") or {}).get("pdf_url") or "",
        "authors": [a.get("author", {}).get("display_name", "") for a in auths],
        "institutions": [i.get("display_name", "")
                         for a in auths for i in (a.get("institutions") or [])],
    }


def _iter_works(params: dict, num: int, mailto: str):
    # urllib 的 HTTPErrorProcessor 对 4xx/5xx 直接抛 HTTPError，不会返回非 200 状态码。
    # CDN 层 429/服务降级可能返回 HTML body，json.loads 会抛 JSONDecodeError。
    # 两者都需要捕获，才能优雅终止分页循环而不让 search() 整体崩溃。
    got, cursor = 0, "*"
    while got < num and cursor:
        page_params = {"per-page": min(200, num - got), "cursor": cursor, "mailto": mailto}
        page_params.update(params)
        try:
            _, _, body = net.get(f"{BASE}?{urlencode(page_params)}")
            data = json.loads(body)
        except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError):
            break
        results = data.get("results", [])
        if not results:
            break
        for w in results:
            yield w
            got += 1
            if got >= num:
                return
        cursor = (data.get("meta") or {}).get("next_cursor")


def search(query, num=25, *, econ_only=True, year_from=None, issn=None,
           mailto=None) -> list:
    # mailto=None 时读环境变量 OPENALEX_MAILTO；仍为空则抛 ValueError（不静默降级匿名池）。
    # OpenAlex polite pool 要求 mailto，但个人邮箱不应硬编码进库代码（多用户/多环境复用困难）。
    if not mailto:
        mailto = os.environ.get("OPENALEX_MAILTO", "")
    if not mailto:
        raise ValueError(
            "openalex.search: 必须提供 mailto（传 mailto= 参数或设 OPENALEX_MAILTO 环境变量）。"
            "匿名池限速严格，漏传会静默踩限速且无报错，故改为强制报错。"
        )
    params: dict = {}
    fil = []
    if econ_only:
        fil.append(f"concepts.id:{ECON_CONCEPT}")
    if year_from:
        fil.append(f"from_publication_date:{year_from}")
    if issn:
        fil.append(f"primary_location.source.issn:{issn}")
    fil.append("has_doi:true")
    if fil:
        params["filter"] = ",".join(fil)
    if query:
        params["search"] = query
    return [_parse_work(w) for w in _iter_works(params, num, mailto)]
