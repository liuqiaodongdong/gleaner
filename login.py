"""有头登录知网 + 超级鹰过滑块 + 立刻保存 cookie。

用法：set ACQ_BROWSER_CHANNEL=msedge & python login.py
校外机构登录：python login.py --institution（等待人工登录成功后自动保存）
检索页滑块走超级鹰 9602（与采集线同一套求解器）。
默认热启动：加载现有 cookies.json。批次间禁止冷启动。
仅首次没有 cookie 时：set ACQ_ALLOW_COLD_LOGIN=1

过验证（拼图消失或检索框出现）立刻覆盖 cookies.json 并退出。
URL 仍带 /verify 不算失败。没有拼图面板绝不送超级鹰。
无需个人知网账号。Agent 不要自己用浏览器工具抠 cookie。
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

from config import COOKIES_FILE, CNKI_SEARCH_URL

_MAX_AUTO_SOLVE = 2  # 看得见拼图时最多打码两轮
_WIDGET_WAIT_SEC = 5
_MANUAL_WAIT_SEC = 90
CNKI_INSTITUTION_URL = "https://fsso.cnki.net/"
CNKI_HOME_URL = "https://www.cnki.net/"

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
        from acq.cnki_session import clear_session_marker
        clear_session_marker(COOKIES_FILE.parent)
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


def iter_context_pages(page):
    try:
        pages = list(page.context.pages)
        if page not in pages:
            pages.insert(0, page)
        return pages
    except Exception:
        return [page]


def wait_for_widget(page, timeout_sec: float = _WIDGET_WAIT_SEC):
    """出现拼图则返回那一页（含新标签）；没有则 None。"""
    from captcha import _captcha_widget_visible, _has_pass_signal

    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        for p in iter_context_pages(page):
            if _captcha_widget_visible(p):
                return p
        if any(_has_pass_signal(p) for p in iter_context_pages(page)):
            return None
        time.sleep(0.4)
    for p in iter_context_pages(page):
        if _captcha_widget_visible(p):
            return p
    return None


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
    parser = argparse.ArgumentParser(description="知网会话录入与刷新")
    parser.add_argument("--institution", action="store_true", help="打开官方校外入口，等待用户完成机构登录")
    parser.add_argument("--timeout", type=int, default=1800, help="机构登录等待秒数，默认 1800")
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout 必须大于 0")
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
    if args.institution:
        # 显式机构登录使用独立会话，避免旧机构身份触发提前保存。
        # 原文件只在新机构登录通过后替换，无需设置冷启动开关。
        saved = False
        try:
            page = context.new_page()
            page.goto(CNKI_INSTITUTION_URL, wait_until="domcontentloaded", timeout=30000)
            page.bring_to_front()
            saved = wait_for_institution_login(context, page, args.timeout)
        except Exception as exc:
            print(f"[login] 机构录入中止，保留原会话（{type(exc).__name__}）", flush=True)
        finally:
            try:
                browser.close()
            finally:
                pw.stop()
        print(f"[login] 完成。saved={saved} path={COOKIES_FILE}", flush=True)
        if not saved:
            raise SystemExit(1)
        return
    load_existing_session(context)
    page = context.new_page()
    page.goto(CNKI_SEARCH_URL, wait_until="domcontentloaded", timeout=30000)
    time.sleep(2.0)

    print("[login] 已打开知网。有拼图才打码；过验证立刻写 cookies.json 并退出。")
    saved = False
    try:
        target = wait_for_widget(page)
        if target:
            print("[login] 检测到拼图，超级鹰最多试 2 次（无面板不打码）")
            try_auto_solve_login_captcha(target)
            if not _still_on_captcha(target, getattr(target, "url", "") or ""):
                saved = persist_after_pass(context, target)
            if not saved:
                saved = wait_for_manual_pass(context, target)
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
