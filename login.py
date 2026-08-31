"""有头登录知网 + 超级鹰过滑块 + 自动保存 cookie。

用法：set ACQ_BROWSER_CHANNEL=msedge & python login.py
检索页滑块走超级鹰 9602（与采集线同一套求解器）。
默认热启动：加载现有 cookies.json。批次间禁止冷启动。
仅首次没有 cookie 时：set ACQ_ALLOW_COLD_LOGIN=1
过验证后才覆盖写入；验证页中途不改文件。无需个人知网账号。
"""
import json
import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from config import COOKIES_FILE, CNKI_SEARCH_URL

_SOLVE_RETRY_SEC = 20
_MAX_AUTO_SOLVE = 2  # 防止刷新后找不到手柄时反复扣超级鹰分

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def apply_login_credentials() -> None:
    """灌入 .env 里的 CJY_* / ACQ_PROXY，供超级鹰与机构代理使用。"""
    from acq.cli_support import apply_credentials, load_credentials, resolve_root
    apply_credentials(load_credentials(resolve_root()))


def try_auto_solve_login_captcha(page) -> bool:
    """复用采集线 wait_for_captcha。缺超级鹰则返回 False，交给手拖。"""
    apply_login_credentials()
    from captcha import _captcha_present
    from scraper import wait_for_captcha

    pages = []
    try:
        pages = list(page.context.pages)
    except Exception:
        pages = [page]
    if page not in pages:
        pages.insert(0, page)
    try:
        for p in pages:
            wait_for_captcha(p)
    except RuntimeError as e:
        print(f"[login] 超级鹰未就绪，请手拖滑块：{e}")
        return False
    except Exception as e:
        print(f"[login] 自动解异常，请手拖滑块：{e}")
        return False
    try:
        return not _captcha_present(page)
    except Exception:
        return False


def _still_on_captcha(page, url: str) -> bool:
    if ("verify" in url) or ("captcha" in url.lower()):
        return True
    try:
        from captcha import _captcha_present
        return _captcha_present(page)
    except Exception:
        return False


def load_existing_session(context) -> int:
    """灌入现有 cookies.json。没有或为空则拒绝启动（冷启动下不了全文）。

    仅首次建会话可设 ACQ_ALLOW_COLD_LOGIN=1；批次间重录必须带旧 cookie。
    """
    allow_cold = os.environ.get("ACQ_ALLOW_COLD_LOGIN", "").strip() == "1"
    if not COOKIES_FILE.exists():
        if allow_cold:
            print("[login] 警告：无 cookies.json，冷启动通常下不了全文。仅用于首次建会话。")
            return 0
        raise SystemExit("[login] 拒绝冷启动：没有 cookies.json，无法续机构会话。")
    try:
        cookies = json.loads(COOKIES_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        raise SystemExit(f"[login] 拒绝冷启动：cookies.json 无法解析（{e}）。")
    if not isinstance(cookies, list) or len(cookies) <= 0:
        if allow_cold:
            print("[login] 警告：cookies.json 为空，冷启动通常下不了全文。")
            return 0
        raise SystemExit("[login] 拒绝冷启动：cookies.json 为空。")
    context.add_cookies(cookies)
    print(f"[login] 已加载现有会话 {len(cookies)} 个 cookie（非冷启动）")
    return len(cookies)


def persist_warm_cookies(context, page) -> bool:
    """仅在已离开验证页时覆盖 cookies.json，避免把半截会话写进去。"""
    try:
        url = page.url
    except Exception:
        url = "?"
    if _still_on_captcha(page, url):
        print("[login] 仍在验证页，不覆盖 cookies.json")
        return False
    try:
        cookies = context.cookies()
        COOKIES_FILE.write_text(json.dumps(cookies, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[login] 已更新会话 {len(cookies)} 个 cookie")
        return True
    except Exception as e:
        print(f"[login] 保存失败: {e}")
        return False


def _context_kwargs() -> dict:
    kwargs = dict(
        viewport={"width": 1920, "height": 1080},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        accept_downloads=True,
    )
    proxy = (os.environ.get("ACQ_PROXY") or "").strip()
    if proxy:
        kwargs["proxy"] = {"server": proxy}
    return kwargs


def main() -> None:
    apply_login_credentials()
    pw = sync_playwright().start()
    channel = os.environ.get("ACQ_BROWSER_CHANNEL", "")
    launch = dict(
        headless=False,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--exclude-switches=enable-automation",
            "--disable-infobars",
            "--start-maximized",
        ],
    )
    if channel:
        launch["channel"] = channel
    browser = pw.chromium.launch(**launch)
    context = browser.new_context(**_context_kwargs())
    stealth = Path(__file__).resolve().parent / "libs" / "stealth.min.js"
    if stealth.is_file():
        context.add_init_script(path=str(stealth))
    load_existing_session(context)
    page = context.new_page()
    page.goto(CNKI_SEARCH_URL, wait_until="domcontentloaded", timeout=30000)
    time.sleep(2.5)

    print("[login] 已带现有机构会话打开知网（非冷启动）。有滑块则超级鹰自动解。")
    print("[login] 通过验证后才写入 cookies.json。完成后关闭浏览器窗口。")
    auto_rounds = 0
    if try_auto_solve_login_captcha(page):
        persist_warm_cookies(context, page)
    else:
        auto_rounds = 1
    last_solve = time.monotonic()
    stopped_auto = False

    saved_any = False
    for i in range(100):  # 100 * 3s = 5 分钟
        try:
            _ = context.cookies()
        except Exception:
            print("[login] 浏览器已关闭，停止。")
            break
        try:
            url = page.url
        except Exception:
            url = "?"
        on_verify = _still_on_captcha(page, url)
        if (
            on_verify
            and auto_rounds < _MAX_AUTO_SOLVE
            and (time.monotonic() - last_solve) >= _SOLVE_RETRY_SEC
        ):
            print("[login] 仍在验证页，再次尝试超级鹰…")
            auto_rounds += 1
            try_auto_solve_login_captcha(page)
            last_solve = time.monotonic()
            try:
                url = page.url
            except Exception:
                url = "?"
            on_verify = _still_on_captcha(page, url)
        elif on_verify and auto_rounds >= _MAX_AUTO_SOLVE and not stopped_auto:
            print("[login] 自动解已停，避免再扣超级鹰分。请手拖滑块，通过后会写入 cookie。")
            stopped_auto = True
        if not on_verify:
            saved_any = persist_warm_cookies(context, page) or saved_any
            if saved_any:
                print(f"[login] {i*3}s  会话已热更新")
                break
        else:
            print(f"[login] {i*3}s  仍在验证页，保留原 cookies.json")
        time.sleep(3)

    try:
        browser.close()
    except Exception:
        pass
    pw.stop()
    print(f"[login] 完成。共保存 cookie 到 {COOKIES_FILE}（saved={saved_any}）")


if __name__ == "__main__":
    main()
