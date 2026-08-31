"""有头登录知网 + 超级鹰过滑块 + 立刻保存 cookie。

用法：set ACQ_BROWSER_CHANNEL=msedge & python login.py
检索页滑块走超级鹰 9602（与采集线同一套求解器）。
默认热启动：加载现有 cookies.json。批次间禁止冷启动。
仅首次没有 cookie 时：set ACQ_ALLOW_COLD_LOGIN=1

过验证（拼图消失或检索框出现）立刻覆盖 cookies.json 并退出。
URL 仍带 /verify 不算失败。没有拼图面板绝不送超级鹰。
无需个人知网账号。Agent 不要自己用浏览器工具抠 cookie。
"""
import json
import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from config import COOKIES_FILE, CNKI_SEARCH_URL

_MAX_AUTO_SOLVE = 2  # 看得见拼图时最多打码两轮
_WIDGET_WAIT_SEC = 5
_MANUAL_WAIT_SEC = 90

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def apply_login_credentials() -> None:
    """灌入 .env 里的 CJY_* / ACQ_PROXY，供超级鹰与机构代理使用。"""
    from acq.cli_support import apply_credentials, load_credentials, resolve_root
    apply_credentials(load_credentials(resolve_root()))


def _still_on_captcha(page, url: str) -> bool:
    """还有可拖的拼图才算卡在验证。URL 带 /verify 不算。"""
    try:
        from captcha import captcha_blocks_cookie_write
        return bool(captcha_blocks_cookie_write(page))
    except Exception:
        return False


def try_auto_solve_login_captcha(page, max_attempts: int = _MAX_AUTO_SOLVE) -> bool:
    """只解当前页；最多 max_attempts 次。无拼图返回 True。"""
    apply_login_credentials()
    from captcha import solve_slider_captcha

    try:
        return bool(solve_slider_captcha(page, max_attempts=max_attempts))
    except RuntimeError as e:
        print(f"[login] 超级鹰未就绪，请手拖滑块：{e}")
        return False
    except Exception as e:
        print(f"[login] 自动解异常，请手拖滑块：{e}")
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
    """拼图还在时不覆盖；过了就立刻写盘。URL 带 /verify 不阻止写入。"""
    try:
        url = page.url
    except Exception:
        url = "?"
    if _still_on_captcha(page, url):
        print("[login] 拼图还在，不覆盖 cookies.json")
        return False
    try:
        cookies = context.cookies()
        COOKIES_FILE.write_text(
            json.dumps(cookies, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"[login] 已更新会话 {len(cookies)} 个 cookie")
        return True
    except Exception as e:
        print(f"[login] 保存失败: {e}")
        return False


def leave_verify_if_passed(page) -> None:
    """过了滑块但地址还停在 /verify 时，跳回检索页再落一次 cookie。"""
    try:
        url = page.url or ""
    except Exception:
        return
    if "verify" not in url.lower() and "captcha" not in url.lower():
        return
    if _still_on_captcha(page, url):
        return
    print("[login] 已过验证但仍停在验证 URL，跳回检索页")
    try:
        page.goto(CNKI_SEARCH_URL, wait_until="domcontentloaded", timeout=20000)
        time.sleep(1.0)
    except Exception as e:
        print(f"[login] 跳回检索页失败: {e}")


def wait_for_widget(page, timeout_sec: float = _WIDGET_WAIT_SEC) -> bool:
    from captcha import _captcha_widget_visible, _has_pass_signal

    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        if _captcha_widget_visible(page):
            return True
        if _has_pass_signal(page):
            return False
        time.sleep(0.4)
    try:
        from captcha import _captcha_widget_visible
        return bool(_captcha_widget_visible(page))
    except Exception:
        return False


def wait_for_manual_pass(context, page, timeout_sec: int = _MANUAL_WAIT_SEC) -> bool:
    """自动解失败后等人手拖；拼图一消失立刻写盘。不再打码。"""
    print("[login] 请手拖滑块。通过后立刻写入 cookie，不会再扣超级鹰分。")
    deadline = time.monotonic() + timeout_sec
    last_note = 0.0
    while time.monotonic() < deadline:
        try:
            _ = context.cookies()
        except Exception:
            print("[login] 浏览器已关闭，停止等待。")
            return False
        try:
            url = page.url
        except Exception:
            url = "?"
        if not _still_on_captcha(page, url):
            leave_verify_if_passed(page)
            return persist_warm_cookies(context, page)
        now = time.monotonic()
        if now - last_note >= 8:
            print("[login] 仍在等手拖滑块…")
            last_note = now
        time.sleep(0.8)
    print("[login] 等待手拖超时，未写入。")
    return False


def persist_after_pass(context, page) -> bool:
    leave_verify_if_passed(page)
    return persist_warm_cookies(context, page)


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
    time.sleep(2.0)

    print("[login] 已打开知网。有拼图才打码；过验证立刻写 cookies.json 并退出。")
    saved = False
    try:
        appeared = wait_for_widget(page)
        if appeared:
            print("[login] 检测到拼图，超级鹰最多试 2 次（无面板不打码）")
            try_auto_solve_login_captcha(page)
            if not _still_on_captcha(page, getattr(page, "url", "") or ""):
                saved = persist_after_pass(context, page)
            if not saved:
                saved = wait_for_manual_pass(context, page)
        else:
            print("[login] 未出现拼图，直接保存当前会话")
            saved = persist_after_pass(context, page)
    except Exception as e:
        print(f"[login] 过程异常: {e}")
        try:
            saved = persist_warm_cookies(context, page) or saved
        except Exception:
            pass

    try:
        browser.close()
    except Exception:
        pass
    pw.stop()
    print(f"[login] 完成。saved={saved} path={COOKIES_FILE}")


if __name__ == "__main__":
    main()
