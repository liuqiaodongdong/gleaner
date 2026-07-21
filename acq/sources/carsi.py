# acq/sources/carsi.py — 订阅库 CARSI headless 下载
import re
from urllib.parse import urlparse
from pathlib import Path

_KICK = re.compile(r"(wayf|shibboleth|saml|/idp|/cas|/login)", re.I)


def detect_publisher(url_or_doi: str, cfg: dict):
    """按域名匹配出版商 key；无匹配返回 None。
    注：仅做域名匹配，裸 DOI（如 10.1016/...）因 netloc='' 始终返回 None。
    """
    host = urlparse(url_or_doi).netloc.lower()
    for key, c in cfg.items():
        if any(d in host for d in c.get("domains", [])):
            return key
    return None


def session_alive(state: dict, probe_url: str) -> bool:
    """简化离线判据：probe_url 自身像登录/wayf 页即视为死会话。"""
    return not bool(_KICK.search(probe_url or ""))


def download_subscription(doi, out_path, *, store, cfg, guard) -> bool:
    """Playwright headless + storage_state 下载订阅库 PDF。

    优先监听 response 抓 PDF，兜底1 pdf_pattern 直链，兜底2 页面点击 PDF 链接。
    """
    from playwright.sync_api import sync_playwright
    from acq.pdfcheck import is_pdf_file

    state = store.load_state()
    if not state:
        return False
    if not guard.can_download():
        return False
    guard.wait()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)  # 保证父目录存在，防止 write_bytes 静默失败
    landing = f"https://doi.org/{doi}"
    got = {"ok": False}

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(storage_state=state, accept_downloads=True)
        page = ctx.new_page()

        def on_resp(resp):
            try:
                ct = (resp.headers or {}).get("content-type", "")
                if "application/pdf" in ct.lower() and not got["ok"]:
                    body = resp.body()
                    if body[:5] == b"%PDF-":
                        out_path.write_bytes(body)
                        got["ok"] = is_pdf_file(out_path)
            except Exception:
                pass

        page.on("response", on_resp)
        try:
            page.goto(landing, wait_until="domcontentloaded", timeout=45000)
            # 会话回踢检测
            if not session_alive(state, page.url):
                # 被踢回 WAYF/登录页 = 会话失效（系统性信号）→ 熔断该源，避免继续撞墙被盯上
                # （record/close 由 finally 块统一负责，避免双重调用）
                guard.trip("session dead: 被踢回 WAYF/登录页")
                return False
            page.wait_for_timeout(3000)
            # 兜底1：pdf_pattern 直链
            # 注：仅用实际落地页 URL 匹配出版商，landing=doi.org 的 netloc 不在任何 domains 中，
            # detect_publisher(landing, cfg) 恒为 None，已移除该死代码分支。
            if not got["ok"]:
                key = detect_publisher(page.url, cfg)
                pat = (cfg.get(key) or {}).get("pdf_pattern") if key else ""
                if pat and "{doi}" in pat:
                    page.goto(pat.format(doi=doi), wait_until="load", timeout=45000)
                    page.wait_for_timeout(2000)
            # 兜底2：页面里点 a[href*=pdf]（可能开新标签）
            # 新标签由 ctx.expect_page() 捕获后，对其注册同一 on_resp 回调，
            # 避免新标签的 PDF response 事件在原 page 上静默丢失。
            if not got["ok"]:
                link = page.query_selector("a[href*='pdf'], a[href*='pdfft']")
                if link:
                    try:
                        # 短超时：点击可能同标签导航而不开新标签，避免空等默认 30s
                        with ctx.expect_page(timeout=8000) as new_page_info:
                            link.click()
                        new_page = new_page_info.value
                        new_page.on("response", on_resp)
                        new_page.wait_for_load_state("domcontentloaded", timeout=30000)
                        page.wait_for_timeout(3000)
                    except Exception:
                        # 未开新标签（同标签内导航/直接下载）——PDF response 已由 page 的 on_resp 捕获
                        page.wait_for_timeout(3000)
        except Exception:
            pass
        finally:
            guard.record(ok=got["ok"])
            ctx.close()
            browser.close()

    return got["ok"]
