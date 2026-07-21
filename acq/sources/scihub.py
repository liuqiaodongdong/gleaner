# acq/sources/scihub.py
import logging
import re
from urllib.parse import quote, urljoin, urldefrag
from pathlib import Path
from acq import net
from acq.pdfcheck import is_plausible_pdf_url, response_looks_pdf, write_pdf_atomic

log = logging.getLogger(__name__)

DEFAULT_MIRRORS = [
    "https://sci-hub.usualwant.com",  # 实测唯一稳定出 PDF（2026-06-29）
    "https://sci-hub.st", "https://sci-hub.ru", "https://sci-hub.se",
]
# BBAN CDN 基础 URL，DOI 需经 quote(doi, safe='/') 后再拼接
BBAN_CDN_BASE = "https://sci.bban.top/pdf"
_NOT_FOUND = ("article not found", "статья не найдена", "не найден")
_META_RE = re.compile(r'citation_pdf_url"[^>]*content="([^"]+)"', re.I)
_META_RE2 = re.compile(r'content="([^"]+)"[^>]*name="citation_pdf_url"', re.I)
_SRC_RE = re.compile(r'(?:src|href)=["\']([^"\']+)["\']', re.I)


def _clean_raw(raw: str) -> str:
    """清洗落地页抽出的原始链接：①反斜杠转义的斜杠(JS/JSON 内联 \\/ )→正常斜杠；
    ②若内嵌 sci.bban.top CDN 绝对地址则直接抽出(避免 urljoin 误拼成相对路径)，
      并还原被双/单重编码的 DOI 斜杠(%252F/%2F→/)，bban CDN 期望字面斜杠。"""
    raw = raw.replace("\\/", "/")
    m = re.search(r"(?:https?:)?//sci\.bban\.top/\S+?\.pdf", raw)
    if m:
        u = m.group(0)
        u = "https:" + u if u.startswith("//") else u
        return u.replace("%252F", "/").replace("%2F", "/")
    return raw


def _norm_url(u: str) -> str:
    """折叠 path 里误拼出的连续斜杠(保留 scheme 的 ://)。"""
    return re.sub(r"(?<!:)//+", "/", u)


def extract_pdf_url_from_html(html: str, base_url: str) -> str | None:
    for rx in (_META_RE, _META_RE2):
        m = rx.search(html)
        if m:
            url, _ = urldefrag(urljoin(base_url, _clean_raw(m.group(1))))
            return _norm_url(url)
    for m in _SRC_RE.finditer(html):
        u, _ = urldefrag(urljoin(base_url, _clean_raw(m.group(1))))
        u = _norm_url(u)
        if is_plausible_pdf_url(u):
            return u
    return None


def _parse_cookies(response) -> dict:
    """从 HTTP 响应的 Set-Cookie 头提取 {name: value} 字典，用于跟随落地页 cookies。"""
    cookies: dict = {}
    set_cookie_hdrs = response.headers.get_all("Set-Cookie") or []
    for sc in set_cookie_hdrs:
        part = sc.split(";")[0].strip()
        if "=" in part:
            k, v = part.split("=", 1)
            cookies[k.strip()] = v.strip()
    return cookies


def _dl(url: str, out_path: Path, cookies: dict | None = None) -> bool:
    """下载 PDF 直链；cookies 为落地页返回的 Set-Cookie，填入请求头以通过 CDN 鉴权。"""
    try:
        headers: dict = {}
        if cookies:
            headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in cookies.items())
        r = net.get_stream(url, headers=headers, insecure=True)
        first = r.read(8192)
        if not response_looks_pdf(first, r.headers.get("Content-Type", "")):
            r.close()
            log.debug("_dl: 非 PDF 响应 url=%s", url)
            return False
        def _it():
            yield first
            while True:
                c = r.read(65536)
                if not c:
                    break
                yield c
        ok = write_pdf_atomic(_it(), out_path)
        r.close()
        if not ok:
            log.warning("_dl: write_pdf_atomic 失败 url=%s", url)
        return ok
    except Exception as exc:
        log.debug("_dl: 网络异常 url=%s err=%s", url, exc)
        return False


def download_scihub(doi: str, out_path: Path, *, mirrors=None) -> bool:
    # 先试 CDN 直链（实测最快命中）；DOI URL 编码避免括号等特殊字符导致 URL 畸形
    cdn_url = f"{BBAN_CDN_BASE}/{quote(doi, safe='/')}.pdf"
    if _dl(cdn_url, out_path):
        log.debug("download_scihub: CDN 命中 doi=%s", doi)
        return True
    for domain in (mirrors or DEFAULT_MIRRORS):
        url = f"{domain.rstrip('/')}/{quote(doi, safe='/')}"
        r = None
        try:
            r = net.get_stream(url, insecure=True)
            first = r.read(8192)
            ctype = r.headers.get("Content-Type", "")
            if response_looks_pdf(first, ctype):       # 落地页直接是 PDF
                def _it():
                    yield first
                    while True:
                        c = r.read(65536)
                        if not c:
                            break
                        yield c
                if write_pdf_atomic(_it(), out_path):
                    log.debug("download_scihub: mirror 直出 PDF domain=%s doi=%s", domain, doi)
                    return True
                log.warning("download_scihub: write_pdf_atomic 失败 domain=%s doi=%s", domain, doi)
                continue
            # 提取落地页 cookies，跟随到 PDF 直链下载（规格：取直链带落地页 cookies）
            landing_cookies = _parse_cookies(r)
            body = (first + r.read(512_000)).decode("utf-8", "ignore")
            low = body[:5000].lower()
            if "captcha" in low or "turnstile" in low:
                log.debug("download_scihub: 验证码墙 domain=%s doi=%s", domain, doi)
                continue
            if any(s in body.lower() for s in _NOT_FOUND):
                log.debug("download_scihub: 文章未找到 domain=%s doi=%s", domain, doi)
                continue
            pdf_url = extract_pdf_url_from_html(body, url)
            if pdf_url:
                if _dl(pdf_url, out_path, cookies=landing_cookies):
                    log.debug("download_scihub: 带 cookies 下载成功 domain=%s doi=%s", domain, doi)
                    return True
                log.warning("download_scihub: PDF 下载失败 pdf_url=%s doi=%s", pdf_url, doi)
            else:
                log.debug("download_scihub: 未提取到 PDF URL domain=%s doi=%s", domain, doi)
        except Exception as exc:
            log.debug("download_scihub: 异常 domain=%s doi=%s err=%s", domain, doi, exc)
            continue
        finally:
            # 统一关闭响应，避免异常路径 fd 泄漏（write_pdf_atomic 已消费完生成器后再关闭也安全）
            if r is not None:
                try:
                    r.close()
                except Exception:
                    pass
    log.warning("download_scihub: 所有镜像均失败 doi=%s", doi)
    return False
