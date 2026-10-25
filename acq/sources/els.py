# acq/sources/els.py —— Elsevier/ScienceDirect 官方 API 客户端
# Search API V2 检索 + Article Retrieval 取 XML + Object Retrieval 取完整 PDF。
# 鉴权：X-ELS-APIKey（见 acq.els_config.get_api_key）；主力机本地跑；entitlement 端点不用。
import json
import io
import re
import time
import unicodedata
from pathlib import Path
from urllib.parse import quote
import requests
from lxml import etree
from pypdf import PdfReader
from acq.sources.els_query import clamp_show

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
SEARCH_URL = "https://api.elsevier.com/content/search/sciencedirect"
ARTICLE_URL = "https://api.elsevier.com/content/article/doi/{doi}?view=FULL"
OBJECT_URL = "https://api.elsevier.com/content/object"


def make_session(api_key: str) -> requests.Session:
    s = requests.Session()
    s.trust_env = False  # Elsevier 官方 API 直连，不走环境代理
    s.headers.update({"X-ELS-APIKey": api_key, "User-Agent": UA})
    return s


def search_journal(session, *, qs, pub, date, count=10, sort="relevance",
                   scope="title", timeout=50) -> list:
    """SD Search API V2 PUT：默认把布尔式放进 title（题名），按 relevance 排序。

    scope='title'：题名检索，对应知网 SU / 接近 Scopus TITLE，避免全文 qs 下歪。
    scope='qs'：全文（除参考文献），仅用户显式要求高召回时用。
    sort: relevance（官方默认）| date。
    count 会被收成 10/25/50/100。
    """
    field = "qs" if (scope or "").lower() == "qs" else "title"
    sort_by = sort if sort in ("relevance", "date") else "relevance"
    body = {field: qs, "date": date,
            "display": {"show": clamp_show(count), "sortBy": sort_by}}
    if pub:
        body["pub"] = pub
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


def _get_bytes(session, url, accept, timeout):
    """临时错误最多重试一次；禁止携带 API key 自动跳往其它域名。"""
    for attempt in range(2):
        try:
            r = session.get(url, headers={"Accept": accept}, timeout=timeout,
                            allow_redirects=False)
        except requests.RequestException:
            if attempt == 0:
                time.sleep(1)
                continue
            return 0, b""
        if attempt == 0 and r.status_code in (429, 500, 502, 503, 504):
            delay = r.headers.get("Retry-After", "1")
            # 较长或日期形式的限流等待交给下一批，避免提前重试。
            if not delay.isdigit() or int(delay) > 30:
                return r.status_code, r.content
            time.sleep(max(1, int(delay)))
            continue
        return r.status_code, r.content


def retrieve_fulltext_xml(session, doi, *, timeout=90):
    """取全文 XML。返回 (status_code, content_bytes)。"""
    return _get_bytes(session, ARTICLE_URL.format(doi=quote(doi, safe="/")),
                      "text/xml", timeout)


def _xml_metadata(body, doi):
    parser = etree.XMLParser(resolve_entities=False, no_network=True)
    root = etree.fromstring(body, parser=parser)
    core = root.xpath('./*[local-name()="coredata"]')
    if not core:
        raise ValueError("xml_missing_metadata")
    def field(name):
        nodes = core[0].xpath('./*[local-name()=$name]', name=name)
        return "".join(nodes[0].itertext()).strip() if nodes else ""
    actual_doi = field("doi")
    if actual_doi and actual_doi.lower() != doi.strip().lower():
        raise ValueError("xml_doi_mismatch")
    original = root.xpath('//*[local-name()="originalText"]')
    if not original or len("".join(original[0].itertext()).strip()) < 50:
        raise ValueError("xml_missing_fulltext")
    counts = root.xpath('//*[local-name()="web-pdf-page-count"]/text()')
    count = counts[0].strip() if counts else ""
    return {"title": field("title"), "pii": re.sub(r"[^A-Za-z0-9]", "", field("pii")),
            "expected_pdf_pages": int(count) if count.isdigit() and int(count) > 0 else None}


def _main_pdf_eid(body, pii):
    # 只接受正文对象，排除补充材料；已知 PII 时要求对象属于当前文章。
    candidates = re.findall(rb'\b1-s2\.0-([A-Za-z0-9]+)-main\.pdf\b', body)
    for candidate in candidates:
        value = candidate.decode("ascii")
        if not pii or value.lower() == pii.lower():
            return f"1-s2.0-{value}-main.pdf"
    return ""


def _validate_pdf(body, doi, metadata):
    if not body.startswith(b"%PDF-") or b"%%EOF" not in body[-2048:]:
        raise ValueError("pdf_invalid_signature_or_eof")
    reader = PdfReader(io.BytesIO(body))
    pages = len(reader.pages)
    if pages == 0:
        raise ValueError("pdf_empty")
    expected = metadata["expected_pdf_pages"]
    if expected is not None and pages != expected:
        raise ValueError("pdf_page_count_mismatch")
    if expected is None and pages == 1:
        raise ValueError("pdf_single_page_unverified")
    text = "\n".join(page.extract_text() or "" for page in reader.pages[:2])
    normalize = lambda value: "".join(c for c in unicodedata.normalize("NFKC", value).casefold() if c.isalnum())
    title = normalize(metadata["title"])
    doi_match = doi.lower() in re.sub(r"\s+", "", text.lower())
    title_match = len(title) >= 12 and title in normalize(text)
    if not (doi_match or title_match):
        raise ValueError("pdf_identity_mismatch")
    if not (reader.pages[-1].extract_text() or "").strip():
        raise ValueError("pdf_last_page_unreadable")
    return {"pdf_pages": pages, "pdf_page_count_verified": expected is not None,
            "pdf_doi_match": doi_match, "pdf_title_match": title_match}


def _write_atomic(path, body):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_suffix(path.suffix + ".part")
    try:
        part.write_bytes(body)
        part.replace(path)
    finally:
        part.unlink(missing_ok=True)


def download_els(session, doi, out_pdf, out_xml, *, timeout=90) -> dict:
    """保存完整 PDF + XML；PDF 失败时保留有效 XML，并返回逐文件状态。"""
    result = {"ok": False, "xml_ok": False, "pdf_ok": False, "error": "",
              "pdf_pages": None, "expected_pdf_pages": None,
              "pdf_page_count_verified": False}
    st, body = retrieve_fulltext_xml(session, doi, timeout=timeout)
    if st != 200 or not body:
        result["error"] = f"xml_http_{st}"
        return result
    try:
        metadata = _xml_metadata(body, doi)
    except ValueError as exc:
        result["error"] = str(exc)
        return result
    except etree.XMLSyntaxError:
        result["error"] = "xml_invalid"
        return result
    result["expected_pdf_pages"] = metadata["expected_pdf_pages"]
    try:
        _write_atomic(out_xml, body)
    except OSError:
        result["error"] = "xml_write_failed"
        return result
    result["xml_ok"] = True
    eid = _main_pdf_eid(body, metadata["pii"])
    if not eid:
        st, objects = _get_bytes(session, f"{OBJECT_URL}/doi/{quote(doi, safe='/')}",
                                 "application/json", timeout)
        if st != 200:
            result["error"] = f"object_list_http_{st}"
            return result
        eid = _main_pdf_eid(objects, metadata["pii"])
    if not eid:
        result["error"] = "main_pdf_object_missing"
        return result
    st, pdf = _get_bytes(session, f"{OBJECT_URL}/eid/{quote(eid, safe='')}?httpAccept=application/pdf",
                         "application/pdf", timeout)
    if st != 200:
        result["error"] = f"pdf_http_{st}"
        return result
    try:
        result.update(_validate_pdf(pdf, doi, metadata))
    except ValueError as exc:
        result["error"] = str(exc) if str(exc).startswith("pdf_") else "pdf_parse_failed"
        return result
    except Exception:
        result["error"] = "pdf_parse_failed"
        return result
    try:
        _write_atomic(out_pdf, pdf)
    except OSError:
        result["error"] = "pdf_write_failed"
        return result
    result.update(ok=True, pdf_ok=True)
    return result
