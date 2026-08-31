import re
import time
from pathlib import Path
from playwright.sync_api import Page
from config import PAPERS_DIR


def _sanitize_filename(name: str) -> str:
    """Replace illegal filename characters with underscore."""
    return re.sub(r'[\\/*?:"<>|\n\r\t]', '_', name).strip()[:100]


def is_already_downloaded(title: str, output_dir: Path | None = None) -> bool:
    """Check if a paper with the given title has already been downloaded."""
    save_dir = output_dir if output_dir else PAPERS_DIR
    safe_title = _sanitize_filename(title)
    for ext in ("pdf", "caj"):
        existing = save_dir / f"{safe_title}.{ext}"
        if existing.exists() and existing.stat().st_size > 0:
            return True
    return False


def download_paper(page: Page, title: str, output_dir: Path | None = None) -> tuple[str, str]:
    """Download full-text from the current detail page.

    Tries PDF first, falls back to CAJ.
    Returns (file_path, file_type) or ("", "") if download fails.
    """
    save_dir = output_dir if output_dir else PAPERS_DIR
    save_dir.mkdir(parents=True, exist_ok=True)
    safe_title = _sanitize_filename(title)

    # Skip if already downloaded
    for ext in ("pdf", "caj"):
        existing = save_dir / f"{safe_title}.{ext}"
        if existing.exists() and existing.stat().st_size > 0:
            print(f"  [download] already exists, skipped: {existing.name}")
            rel_path = str(existing)
            return (rel_path, ext.upper())

    # Try PDF download first (multiple selector strategies)
    pdf_btn = page.query_selector(
        "a#pdfDown, a.btn-dlpdf, a[id*='pdfDown'], "
        ".btn-dlpdf a, a[href*='pdfdown'], a[onclick*='pdf']"
    )
    if not pdf_btn:
        # New CNKI UI: match by text
        pdf_btn = page.query_selector("a:has-text('PDF下载'), a:has-text('PDF 下载')")
    if pdf_btn:
        result = _do_download(page, pdf_btn, save_dir, safe_title, "pdf")
        if result:
            return result

    # Fallback to CAJ
    caj_btn = page.query_selector(
        "a#cajDown, a.btn-dlcaj, a[id*='cajDown'], "
        ".btn-dlcaj a, a[href*='cajdown']"
    )
    if not caj_btn:
        caj_btn = page.query_selector("a:has-text('CAJ下载'), a:has-text('CAJ 下载')")
    if caj_btn:
        result = _do_download(page, caj_btn, save_dir, safe_title, "caj")
        if result:
            return result

    print(f"  [download] no download button found for: {title[:40]}")
    page.screenshot(path="debug_download_fail.png")
    print(f"  [debug] screenshot saved to debug_download_fail.png, URL={page.url[:80]}")
    return ("", "")


def _save_download_event(download, file_path: Path, ext: str, via: str) -> tuple[str, str]:
    download.save_as(str(file_path))
    print(f"  [download] saved {ext.upper()}{via}: {file_path.name}")
    return (str(file_path), ext.upper())


def _maybe_solve_captcha_on_pages(context, pages) -> bool:
    """新标签若是拼图/滑块验证码，在主流程走超级鹰（勿在 page 回调里打码，防死锁）。"""
    try:
        from captcha import solve_slider_captcha, _captcha_present
    except Exception as e:
        print(f"  [download] captcha import fail: {e}")
        return False
    solved_any = False
    for p in pages:
        try:
            if p.is_closed():
                continue
            if _captcha_present(p):
                print(f"  [download] 验证码页 title={(p.title() or '')[:40]!r}，超级鹰解码...")
                if solve_slider_captcha(p):
                    solved_any = True
                    print("  [download] 验证码已通过")
                    try:
                        from browser import save_cookies_after_captcha
                        save_cookies_after_captcha(context)
                    except Exception:
                        pass
        except Exception as e:
            print(f"  [download] captcha solve err: {e}")
    try:
        if getattr(context, "_acq_pending_captcha", False):
            context._acq_pending_captcha = False  # type: ignore[attr-defined]
    except Exception:
        pass
    return solved_any


def _wait_for_download(collected: list, timeout_s: float = 60.0):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if collected:
            return collected[0]
        time.sleep(0.3)
    return None


def _close_quiet(pages) -> None:
    for p in pages:
        try:
            if p and not p.is_closed():
                p.close()
        except Exception:
            pass


def _do_download(page: Page, btn, save_dir: Path, safe_title: str, ext: str) -> tuple[str, str] | None:
    """Click download button and save the file. Handles both direct download and new-tab download."""
    file_path = save_dir / f"{safe_title}.{ext}"
    context = page.context
    # 必须在第一次 click 前记录，否则策略1超时后拼图窗已存在会被漏掉
    pages_before = {id(p) for p in context.pages}

    # Strategy 1: 直链下载（历史路径，52/56 篇靠它成功）
    try:
        with page.expect_download(timeout=20000) as download_info:
            btn.click()
        return _save_download_event(download_info.value, file_path, ext, "")
    except Exception as e:
        print(f"  [download] direct expect_download: {type(e).__name__}: {e}")

    # Strategy 2: 新标签（拼图校验 / PDF 预览）+ 超级鹰
    collected: list = []

    def _on_dl(download) -> None:
        collected.append(download)

    context.on("download", _on_dl)
    new_pages: list = []
    try:
        # 策略1 的 click 可能已弹出拼图窗
        new_pages = [p for p in context.pages if id(p) not in pages_before and not p.is_closed()]
        # 兜底：标题/URL 像验证码的页（含残留）
        if not new_pages:
            for p in context.pages:
                if p.is_closed() or p == page:
                    continue
                try:
                    t, u = p.title() or "", p.url or ""
                except Exception:
                    continue
                if "拼图" in t or "安全验证" in t or "bar.cnki" in u or "verify" in u:
                    new_pages.append(p)
        if not new_pages:
            try:
                with context.expect_page(timeout=20000) as page_info:
                    btn.click()
                np = page_info.value
                try:
                    np.wait_for_load_state("domcontentloaded", timeout=15000)
                except Exception:
                    pass
                new_pages = [np]
            except Exception as e:
                print(f"  [download] expect_page: {type(e).__name__}: {e}")
                new_pages = [
                    p for p in context.pages
                    if id(p) not in pages_before and not p.is_closed()
                ]

        for p in new_pages:
            try:
                print(
                    f"  [download] new tab url={(p.url or '')[:80]!r} "
                    f"title={(p.title() or '')[:40]!r}"
                )
            except Exception:
                pass

        # 拼图/滑块：主流程超级鹰（回调里只标记不打码）
        _maybe_solve_captcha_on_pages(context, list(new_pages) + [page])

        dl = _wait_for_download(collected, timeout_s=60.0)
        if dl:
            _close_quiet(new_pages)
            return _save_download_event(dl, file_path, ext, " (via captcha/new tab)")

        # PDF 预览 URL 直取
        for new_page in new_pages:
            if new_page.is_closed():
                continue
            new_url = new_page.url or ""
            if "pdf" in new_url.lower() or new_url.endswith(".pdf"):
                import requests
                cookies = {c["name"]: c["value"] for c in context.cookies()}
                resp = requests.get(new_url, cookies=cookies, timeout=30, stream=True)
                if resp.status_code == 200 and len(resp.content) > 1000:
                    file_path.write_bytes(resp.content)
                    print(f"  [download] saved {ext.upper()} (via URL): {file_path.name}")
                    _close_quiet([new_page])
                    return (str(file_path), ext.upper())
        _close_quiet(new_pages)
    except Exception as e:
        print(f"  [download] {ext.upper()} new-tab strategy failed: {e}")
        _close_quiet(new_pages)
    finally:
        try:
            context.remove_listener("download", _on_dl)
        except Exception:
            pass

    print(f"  [download] {ext.upper()} download failed")
    return None
