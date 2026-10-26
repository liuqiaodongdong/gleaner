"""Gleanera：在知网官方机构入口登录并安全保存已确认的学校会话。"""
import argparse
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

from config import COOKIES_FILE, CNKI_SEARCH_URL

CNKI_INSTITUTION_URL = "https://fsso.cnki.net/"
CNKI_HOME_URL = "https://www.cnki.net/"

_MAX_AUTO_SOLVE = 2  # 看得见拼图时最多打码两轮
_WIDGET_WAIT_SEC = 15
_MANUAL_WAIT_SEC = 90

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def apply_login_credentials() -> None:
    """灌入 .env 里的 CJY_* / ACQ_PROXY，供超级鹰与机构代理使用。"""
    from acq.cli_support import apply_credentials, load_credentials
    apply_credentials(load_credentials(Path(__file__).resolve().parent))




















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
    from acq.network_config import proxy_server
    proxy = proxy_server()
    if proxy:
        kwargs["proxy"] = {"server": proxy}
    return kwargs


def is_cnki_url(url: str) -> bool:
    """只允许知网域名，防止认证跳转页面被误判为登录成功。"""
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and (host == "cnki.net" or host.endswith(".cnki.net"))


def institution_name(page) -> str:
    """使用知网官方顶部登录组件的机构名称，个人登录不算机构登录。"""
    if not is_cnki_url(page.url):
        return ""
    try:
        for element in page.locator(".ecp_header_unitName").all():
            if element.is_visible():
                name = element.inner_text(timeout=1000).strip()
                if name and name not in {"机构登录", "机构名称"}:
                    return name
    except Exception:
        # 登录重定向时执行上下文会销毁，等待下一轮检查即可。
        pass
    return ""


def _visible_in_viewport(element, page) -> bool:
    """DOM 中保留的离屏或透明验证码容器不算正在显示的验证。"""
    if not element.is_visible():
        return False
    box = element.bounding_box()
    viewport = page.viewport_size or page.evaluate("({width: innerWidth, height: innerHeight})")
    if not box or box["width"] <= 0 or box["height"] <= 0:
        return False
    if (box["x"] + box["width"] <= 0 or box["y"] + box["height"] <= 0
            or box["x"] >= viewport["width"] or box["y"] >= viewport["height"]):
        return False
    return element.evaluate("""element => {
        for (let node = element; node; node = node.parentElement) {
            const style = getComputedStyle(node);
            if (style.display === 'none' || style.visibility === 'hidden' || Number(style.opacity) === 0)
                return false;
        }
        return true;
    }""")


def institution_captcha_visible(page) -> bool:
    """机构登录仅拦截实际展示的验证面板，不以预加载控件作为阻塞。"""
    parsed = urlsplit(page.url)
    if parsed.hostname == "bar.cnki.net" or any(word in parsed.path.lower() for word in ("/verify", "/captcha")):
        return True
    from captcha import _PANEL_SELECTORS
    for frame in page.frames:
        ancestor = frame
        while ancestor.parent_frame is not None:
            if not _visible_in_viewport(ancestor.frame_element(), page):
                break
            ancestor = ancestor.parent_frame
        else:
            for selector in _PANEL_SELECTORS:
                for element in frame.locator(selector).all():
                    if _visible_in_viewport(element, page):
                        return True
    return False


def persist_institution_cookies(context, page) -> bool:
    """确认机构登录后原子保存；旧文件备份到已被 Git 忽略的目录。"""
    if not institution_name(page):
        print("[login] 机构状态正在切换，继续等待。", flush=True)
        return False
    # 首页轮播控件也可能包含 slider/btn，不能套用检索页的泛化滑块判断。
    # 机构已显示时，只检查真正的验证码图片面板及安全验证页面。
    if institution_captcha_visible(page):
        print("[login] 机构已显示，仍有安全验证，等待验证完成后保存。", flush=True)
        return False
    # 不保存学校统一认证站的 cookies，采集器只需要知网会话。
    cookies = [
        cookie for cookie in context.cookies()
        if (cookie.get("domain", "").lstrip(".").lower() == "cnki.net"
            or cookie.get("domain", "").lstrip(".").lower().endswith(".cnki.net"))
    ]
    if not cookies:
        print("[login] 知网会话尚未写入，继续等待。", flush=True)
        return False
    import shutil
    import tempfile

    temporary = None
    backup = None
    replaced = False
    from acq.cnki_session import session_path
    marker = session_path(COOKIES_FILE.parent)
    previous_marker = marker.read_bytes() if marker.exists() else None
    try:
        if COOKIES_FILE.exists():
            backups = COOKIES_FILE.parent / "acq" / "cookies" / "cnki"
            backups.mkdir(parents=True, exist_ok=True)
            backup = backups / f"cookies-{time.time_ns()}.json"
            shutil.copy2(COOKIES_FILE, backup)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=COOKIES_FILE.parent,
            prefix=".institution-cookies-", suffix=".tmp", delete=False,
        ) as stream:
            temporary = Path(stream.name)
            json.dump(cookies, stream, ensure_ascii=False, indent=2)
        temporary.replace(COOKIES_FILE)
        replaced = True
        from acq.cnki_session import mark_institution_session
        mark_institution_session(COOKIES_FILE.parent, COOKIES_FILE)
        print(f"[login] 机构登录已确认，已更新会话 {len(cookies)} 个 cookie", flush=True)
        return True
    except Exception as exc:
        if replaced:
            try:
                if backup is not None:
                    shutil.copy2(backup, COOKIES_FILE)
                else:
                    COOKIES_FILE.unlink(missing_ok=True)
                if previous_marker is None:
                    marker.unlink(missing_ok=True)
                else:
                    marker.write_bytes(previous_marker)
            except OSError:
                print("[login] 回退保存失败，请保留窗口和会话文件排查。", flush=True)
                return False
        print(f"[login] 保存失败，保留原会话（{type(exc).__name__}）", flush=True)
        return False
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def wait_for_institution_login(context, page, timeout_sec: int = 1800) -> bool:
    """前台由用户认证，后台定期用知网首页确认同一会话的机构身份。"""
    print("[login] 请在浏览器选择学校并完成校外登录。正在等待机构身份，尚未覆盖旧 cookies。", flush=True)
    deadline = time.monotonic() + timeout_sec
    probe = None
    next_probe = time.monotonic() + 8
    stable_page = None
    stable_since = 0.0
    while time.monotonic() < deadline:
        pages = [p for p in context.pages if not p.is_closed()]
        # 只剩后台检查页表示用户关闭了登录窗口，按取消处理。
        if not pages or (probe is not None and pages == [probe]):
            print("[login] 登录窗口已关闭，保留原 cookies。", flush=True)
            return False
        for candidate in pages:
            if institution_name(candidate):
                if stable_page is not candidate:
                    stable_page, stable_since = candidate, time.monotonic()
                # 等回跳及跨域写入稳定，避免在认证响应尚未结束时退出。
                if time.monotonic() - stable_since >= 3:
                    if persist_institution_cookies(context, candidate):
                        return True
                    # 检查未通过不代表用户取消，必须保持窗口和会话继续等待。
                    stable_since = time.monotonic()
                break
        else:
            stable_page = None
        if time.monotonic() >= next_probe and stable_page is None:
            try:
                if probe is None or probe.is_closed():
                    probe = context.new_page()
                    # 新标签不能遮住用户正在输入的认证页面。
                    pages[-1].bring_to_front()
                probe.goto(CNKI_HOME_URL, wait_until="domcontentloaded", timeout=15000)
            except Exception:
                # 网络中断或回跳尚未完成不能成为覆盖旧文件的理由。
                pass
            next_probe = time.monotonic() + 10
        # Playwright 的等待会处理新标签、导航等事件。
        active = next((p for p in pages if not p.is_closed()), None)
        if active is not None:
            try:
                active.wait_for_timeout(500)
            except Exception:
                pass
    print("[login] 等待机构登录超时，保留原 cookies。", flush=True)
    return False


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Gleanera 校外学校机构登录")
    parser.add_argument("--institution", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--timeout", type=int, default=1800, help="等待用户完成机构认证的秒数")
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        parser.error("--timeout 必须大于 0")
    apply_login_credentials()
    try:
        options = _context_kwargs()
    except ValueError as exc:
        print(f"[login] {exc}")
        return 1
    pw = sync_playwright().start()
    browser = None
    saved = False
    try:
        launch = dict(headless=False, args=["--start-maximized"])
        if "proxy" not in options:
            launch["args"].append("--no-proxy-server")
        channel = (os.environ.get("ACQ_BROWSER_CHANNEL") or ("msedge" if os.name == "nt" else "")).strip()
        if channel:
            launch["channel"] = channel
        browser = pw.chromium.launch(**launch)
        context = browser.new_context(**options)
        page = context.new_page()
        page.goto(CNKI_INSTITUTION_URL, wait_until="domcontentloaded", timeout=30000)
        page.bring_to_front()
        saved = wait_for_institution_login(context, page, args.timeout)
    except Exception as exc:
        print(f"[login] 机构录入中止，保留原会话（{type(exc).__name__}）", flush=True)
    finally:
        try:
            if browser is not None:
                browser.close()
        finally:
            pw.stop()
    print(json.dumps({"ok": saved, "stage": "institution_login", "cookies_saved": saved}, ensure_ascii=False))
    return 0 if saved else 1


if __name__ == "__main__":
    sys.exit(main())
