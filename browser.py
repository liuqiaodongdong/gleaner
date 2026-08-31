import json
import time
from playwright.sync_api import sync_playwright, BrowserContext, Page
from config import COOKIES_FILE


def _save_cookies(context: BrowserContext) -> None:
    cookies = context.cookies()
    COOKIES_FILE.write_text(json.dumps(cookies, ensure_ascii=False, indent=2))
    print(f"[browser] cookies saved to {COOKIES_FILE}")


def _load_cookies(context: BrowserContext) -> None:
    cookies = json.loads(COOKIES_FILE.read_text())
    context.add_cookies(cookies)
    print(f"[browser] cookies loaded from {COOKIES_FILE}")


def _on_new_page(new_page: Page) -> None:
    """新窗口/标签页打开时检测是否为验证码页。

    注意：Playwright 同步模式下本回调在主线程串行执行，绝不能在此长时间 sleep/打码，
    否则会与 expect_download / expect_page 死锁（曾因 5min 等手动 + 超长超级鹰导致卡死）。
    策略：
      - 下载场景的 bar.cnki 拼图：只标记、不关窗、不在此打码 → 由 downloader 主流程超级鹰解码
      - 搜索页 tianai 滑块：短时超级鹰（与历史行为一致）
      - ACQ_MANUAL_CAPTCHA=1：拼图窗保持打开供手拖
    """
    try:
        new_page.wait_for_load_state("domcontentloaded", timeout=8000)
    except Exception:
        return
    try:
        url = new_page.url
        title = new_page.title() or ""
    except Exception:
        return
    is_captcha = (
        "verify" in url
        or "captcha" in url.lower()
        or "bar.cnki.net" in url
        or title == "安全验证"
        or "拼图校验" in title
    )
    if not is_captcha:
        return
    print(f"[browser] 检测到验证码窗口: url={url[:80]} title={title}")
    is_puzzle = "bar.cnki.net" in url or "拼图校验" in title
    if is_puzzle:
        import os as _os
        if _os.environ.get("ACQ_MANUAL_CAPTCHA") == "1":
            print("[browser] 拼图校验：请在弹出窗口手动拖动解决(手动模式,不自动关窗)")
            return
        # 不关窗、不在回调里打码：留给 downloader._maybe_solve_captcha_on_pages
        print("[browser] 拼图校验：交由下载主流程超级鹰解码（回调不阻塞）")
        try:
            new_page.context._acq_pending_captcha = True  # type: ignore[attr-defined]
        except Exception:
            pass
        return
    # 其它(搜索页 tianai 滑块)：短时自动解
    try:
        from captcha import solve_slider_captcha
        if solve_slider_captcha(new_page):
            print("[browser] 验证码自动解决")
            try:
                _save_cookies(new_page.context)
            except Exception:
                pass
        else:
            print("[browser] 验证码自动解失败")
    except Exception as e:
        print(f"[browser] 自动解码异常: {e}")


def launch_browser():
    """Launch Playwright browser with stealth and return (pw, browser, context, page).

    If cookies.json exists, load it to skip CAPTCHA verification.
    """
    pw = sync_playwright().start()
    import os
    # 无头/浏览器内核可由环境变量切换：MCP 无头跑默认 ACQ_HEADLESS=1 + 系统 Edge
    _headless = os.environ.get("ACQ_HEADLESS", "0") == "1"
    _channel = os.environ.get("ACQ_BROWSER_CHANNEL", "")  # "msedge"/"chrome"=系统浏览器; ""=playwright 自带 chromium
    _launch = dict(
        headless=_headless,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--exclude-switches=enable-automation",
            "--disable-infobars",
            "--no-first-run",
            "--no-default-browser-check",
            "--start-maximized",
        ],
    )
    if _channel:
        _launch["channel"] = _channel
    browser = pw.chromium.launch(**_launch)
    _ctx_kwargs = dict(
        viewport={"width": 1920, "height": 1080},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        accept_downloads=True,
    )
    # 代理：知网机构权限（Playwright 默认不吃系统代理，需显式传）。
    # ACQ_PROXY 示例 http://127.0.0.1:PORT（端口以本机代理软件为准）；不设则直连。
    _proxy = os.environ.get("ACQ_PROXY", "")
    if _proxy:
        _ctx_kwargs["proxy"] = {"server": _proxy}
    context = browser.new_context(**_ctx_kwargs)
    from pathlib import Path
    stealth_path = str(Path(__file__).parent / "libs" / "stealth.min.js")
    context.add_init_script(path=stealth_path)

    # 监听新窗口/标签页打开 — CNKI 滑块在新窗口里弹
    context.on("page", _on_new_page)

    if COOKIES_FILE.exists():
        _load_cookies(context)

    page = context.new_page()
    return pw, browser, context, page


def save_cookies_after_captcha(context: BrowserContext) -> None:
    """Save cookies after user manually solves CAPTCHA."""
    _save_cookies(context)


def close_browser(pw, browser) -> None:
    browser.close()
    pw.stop()
