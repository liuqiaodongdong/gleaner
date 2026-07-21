# acq/sources/nber.py — NBER 工作论文源
# 付费墙顶刊(尤其近年 2022+ Sci-Hub 断供)的免费合法"内容版"：按标题搜 NBER → 拿 w 号 → 直链下 WP PDF。
# 纯 curl/Python、零 key、无闭源。配方源自 academic-paper-search / nber-working-papers-api skill。
import json
import re
from urllib.parse import urlencode
from pathlib import Path
from acq import net
from acq.pdfcheck import response_looks_pdf, write_pdf_atomic

SEARCH = ("https://www.nber.org/api/v1/working_page_listing"
          "/contentType/working_paper/_/_/search")
PDF_TMPL = "https://www.nber.org/system/files/working_papers/{n}/{n}.pdf"


def _norm_title(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()


def _title_match(t1: str, t2: str) -> bool:
    """标题高度一致(相等/前缀/包含)才算同一篇——NBER WP 常带副标题，published 版可能省略。
    太短的标题不匹配，避免误命中无关 WP。"""
    a, b = _norm_title(t1), _norm_title(t2)
    if len(a) < 10 or len(b) < 10:
        return False
    return a == b or a in b or b in a


def _parse_search(data: dict) -> list:
    """从 NBER 搜索响应解析出 [{number, title, pdf_url}]，只保留 w 号工作论文。"""
    out = []
    for it in data.get("results", []):
        u = it.get("url") or ""
        num = u.rsplit("/", 1)[-1] if u else ""
        if not num.startswith("w"):
            continue
        out.append({"number": num, "title": it.get("title", ""),
                    "pdf_url": PDF_TMPL.format(n=num)})
    return out


def search_nber(title: str, n: int = 5) -> list:
    """按标题搜 NBER 工作论文。"""
    url = SEARCH + "?" + urlencode({"page": 1, "perPage": n, "q": title})
    try:
        s, _, b = net.get(url)
        if s != 200:
            return []
        return _parse_search(json.loads(b))
    except Exception:
        return []


def download_nber(meta: dict, out_path) -> bool:
    """按标题找 NBER WP 版并下全文(过 PDF 三层校验)。标题需高度匹配，避免下错论文。"""
    title = meta.get("title") or ""
    if len(_norm_title(title)) < 10:
        return False
    out_path = Path(out_path)
    for cand in search_nber(title, n=5):
        if not _title_match(title, cand["title"]):
            continue
        try:
            r = net.get_stream(cand["pdf_url"])
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
                if write_pdf_atomic(_it(), out_path):
                    return True
            finally:
                r.close()
        except Exception:
            continue
    return False
