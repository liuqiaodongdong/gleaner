"""CNKI tianai 多缺口滑块自动解 —— 超级鹰 9602（已端到端验证）。

ddddocr 对多缺口干扰滑块不可靠（必选错缺口），已弃用；改用超级鹰人力众包。
"""
import hashlib
import os
import random
import time

import requests
from playwright.sync_api import Page

from config import CHAOJIYING_USER, CHAOJIYING_PASS, CHAOJIYING_SOFTID

_CJY_URL = "https://upload.chaojiying.net/Upload/Processing.php"
_CJY_REPORT = "https://upload.chaojiying.net/Upload/ReportError.php"
_CJY_SCORE = "https://upload.chaojiying.net/Upload/GetScore.php"


def _cjy_user() -> str:
    return (os.environ.get("CJY_USER") or CHAOJIYING_USER or "").strip()


def _cjy_pass_raw() -> str:
    return (os.environ.get("CJY_PASS") or CHAOJIYING_PASS or "").strip()


def _cjy_softid() -> str:
    return (os.environ.get("CJY_SOFTID") or CHAOJIYING_SOFTID or "").strip()


def _require_cjy():
    if not (_cjy_user() and _cjy_pass_raw() and _cjy_softid()):
        raise RuntimeError(
            "超级鹰账号未配置：请设置环境变量 CJY_USER / CJY_PASS / CJY_SOFTID"
            "（见 README 或 .env.example）"
        )


def _cjy_pass() -> str:
    _require_cjy()
    return hashlib.md5(_cjy_pass_raw().encode()).hexdigest()


def _cjy_solve(img_bytes: bytes, codetype: int = 9602) -> dict:
    _require_cjy()
    data = {"user": _cjy_user(), "pass2": _cjy_pass(),
            "softid": _cjy_softid(), "codetype": str(codetype)}
    files = {"userfile": ("a.jpg", img_bytes)}
    r = requests.post(_CJY_URL, data=data, files=files, timeout=60)
    return r.json()


def _cjy_report(pic_id: str) -> None:
    """识别错误 3 分钟内报错返分（省积分）。"""
    if not pic_id:
        return
    try:
        requests.post(_CJY_REPORT, data={"user": _cjy_user(), "pass2": _cjy_pass(),
                                          "softid": _cjy_softid(), "id": pic_id}, timeout=30)
    except Exception as e:
        print(f"[captcha] 报错返分失败: {e}")


def chaojiying_score() -> str:
    """查超级鹰积分余额。"""
    try:
        _require_cjy()
        r = requests.post(_CJY_SCORE, data={"user": _cjy_user(), "pass2": _cjy_pass()}, timeout=30)
        return r.text
    except Exception as e:
        return f"score err: {e}"


def _page_url(page: Page) -> str:
    try:
        return page.url or ""
    except Exception:
        return ""


def _page_title(page: Page) -> str:
    try:
        return page.title() or ""
    except Exception:
        return ""


def _has_pass_signal(page: Page) -> bool:
    """检索框已出、或下载页写了「验证完成」——URL 还带 /verify 也算过了。"""
    try:
        body = page.inner_text("body", timeout=1000) or ""
        if "验证完成" in body or "已进入下载" in body:
            return True
    except Exception:
        pass
    try:
        el = page.query_selector("input.search-input, input#txt_SearchText")
        if el and el.is_visible():
            return True
    except Exception:
        pass
    return False


def _captcha_url_hint(page: Page) -> bool:
    u = _page_url(page).lower()
    t = _page_title(page)
    if "verify" in u or "captcha" in u or "bar.cnki.net" in u:
        return True
    return t == "安全验证" or "拼图校验" in t


def _captcha_present(page: Page) -> bool:
    """是否还像验证码页。通过信号优先；URL 带 /verify 只表示「可能要解」，不表示失败。"""
    if _has_pass_signal(page):
        return False
    if _captcha_url_hint(page):
        return True
    for sel in (
        ".verify-img-panel",
        "#verify-bar-box",
        ".verifybox",
        ".verify-mask",
        ".slide-verify",
        ".captcha-slider",
        "[class*='slide'][class*='verify']",
    ):
        el = page.query_selector(sel)
        if el:
            try:
                if el.is_visible():
                    return True
            except Exception:
                pass
    return False


def _human_like_drag(page: Page, slider, distance: float) -> None:
    """人形拖拽：缓出曲线 + y 抖动 + 过冲回正（已验证可过 tianai 轨迹校验）。"""
    box = slider.bounding_box()
    if not box:
        print("[captcha] 滑块无 bounding box")
        return
    start_x = box["x"] + box["width"] / 2
    start_y = box["y"] + box["height"] / 2
    page.mouse.move(start_x, start_y)
    time.sleep(random.uniform(0.1, 0.3))
    page.mouse.down()
    time.sleep(random.uniform(0.1, 0.2))
    steps = random.randint(30, 50)
    current_x = start_x
    for i in range(steps):
        progress = (i + 1) / steps
        eased = 1 - (1 - progress) ** 2          # 先快后慢
        target_x = start_x + distance * eased
        move_x = target_x - current_x
        jitter_y = random.uniform(-2, 2)
        page.mouse.move(current_x + move_x, start_y + jitter_y)
        current_x += move_x
        time.sleep(random.uniform(0.01, 0.04))
    overshoot = random.uniform(2, 6)             # 过冲后回正
    page.mouse.move(current_x + overshoot, start_y + random.uniform(-1, 1))
    time.sleep(random.uniform(0.05, 0.15))
    page.mouse.move(current_x, start_y)
    time.sleep(random.uniform(0.1, 0.3))
    page.mouse.up()
    time.sleep(1)


_PANEL_SELECTORS = (
    ".tencent-captcha-dy__image-area",  # bar.cnki 2026 腾讯拼图背景区
    ".tencent-captcha-dy__verify-bg-img",
    ".verify-img-panel",
    ".slide-verify-block",
    ".captcha_image",
    ".captcha-img",
    "#captcha-box img",
    ".verifybox-bottom .verify-img-panel",
    "canvas.verify-img",
    ".nc_scale",  # 少数阿里系滑块底图容器
)

_HANDLE_SELECTORS = (
    ".tencent-captcha-dy__slider-block",  # bar.cnki 2026 腾讯拼图滑块
    ".verify-move-block",
    ".verify-bar-area .verify-move-block",
    "#verify-bar-box .verify-move-block",
    ".verify-left-bar",
    ".slider-btn",
    ".slide-verify-slider-mask-item",
    ".btn_slide",
    ".nc_iconfont.btn_slide",
    "[class*='slider'][class*='btn']",
    "[class*='verify-move']",
    ".verify-slide-block",
)


def _find_first(page: Page, selectors: tuple[str, ...]):
    for sel in selectors:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                return el
        except Exception:
            continue
    return None


def _find_panel_in_frames(page: Page):
    """主文档 + iframe 里找拼图面板（bar.cnki 偶发嵌 frame）。"""
    panel = _find_first(page, _PANEL_SELECTORS)
    if panel:
        return page, panel
    for frame in page.frames:
        if frame == page.main_frame:
            continue
        for sel in _PANEL_SELECTORS:
            try:
                el = frame.query_selector(sel)
                if el and el.is_visible():
                    return frame, el
            except Exception:
                continue
    return page, None


def _handle_visible(el) -> bool:
    if not el:
        return False
    try:
        return bool(el.is_visible())
    except Exception:
        return True


def _find_handle_in_frames(page: Page, preferred_host=None):
    """主文档 + 全部 iframe 里找滑块手柄（刷新后常落到别的 frame）。"""
    hosts = []
    if preferred_host is not None:
        hosts.append(preferred_host)
    hosts.append(page)
    try:
        hosts.extend(page.frames)
    except Exception:
        pass
    seen: set[int] = set()
    for host in hosts:
        hid = id(host)
        if hid in seen:
            continue
        seen.add(hid)
        for sel in _HANDLE_SELECTORS:
            try:
                el = host.query_selector(sel)
            except Exception:
                continue
            if _handle_visible(el):
                return el
    return _find_first(page, _HANDLE_SELECTORS)


def _captcha_widget_visible(page: Page) -> bool:
    """看得见拼图面板或滑块手柄才值得打码。"""
    try:
        _, panel = _find_panel_in_frames(page)
        if panel:
            return True
    except Exception:
        pass
    try:
        if _find_handle_in_frames(page):
            return True
    except Exception:
        pass
    return False


def captcha_blocks_cookie_write(page: Page) -> bool:
    """还有可拖的拼图才禁止写 cookie。URL 带 /verify 不算。"""
    if _has_pass_signal(page):
        return False
    return _captcha_widget_visible(page)


def solve_slider_captcha(page: Page, max_attempts: int = 4) -> bool:
    """检测并用超级鹰 9602 解 CNKI 滑块/拼图校验。无验证码返回 True。"""
    if not _captcha_present(page):
        return True
    for attempt in range(max_attempts):
        if _has_pass_signal(page) or not _captcha_present(page):
            print("[captcha] 验证码已消失 ✓")
            return True
        # 等面板出现（主文档或 iframe）
        panel = None
        host = page
        for _wait in range(8):
            host, panel = _find_panel_in_frames(page)
            if panel:
                break
            if _has_pass_signal(page):
                print("[captcha] 验证码已消失（等待中）✓")
                return True
            time.sleep(0.5)
        if not panel:
            # 无面板绝不整页送超级鹰：过验证后 URL 常仍带 /verify，整页打码就是空烧
            try:
                page.screenshot(path="debug_captcha_nopanel.png", full_page=False)
                print("[captcha] 无拼图面板，不送超级鹰。诊断图 debug_captcha_nopanel.png")
            except Exception:
                print("[captcha] 找不到拼图面板，不送超级鹰（避免空烧）")
            return bool(_has_pass_signal(page))
        print(f"[captcha] 超级鹰识别中 (尝试 {attempt + 1}/{max_attempts})...")
        try:
            img = panel.screenshot(type="jpeg")
        except Exception as e:
            print(f"[captcha] 面板截图失败: {e}")
            time.sleep(1)
            continue
        res = _cjy_solve(img, 9602)
        print(f"[captcha] 超级鹰: err_no={res.get('err_no')} pic_str={res.get('pic_str')}")
        if res.get("err_no") != 0:
            time.sleep(2)
            continue
        pic_id = res.get("pic_id", "")
        try:
            p1, p2 = res.get("pic_str", "").split("|")
            x1 = float(p1.split(",")[0])
            x2 = float(p2.split(",")[0])
            distance = abs(x2 - x1)
        except Exception as e:
            print(f"[captcha] 解析坐标失败: {e}")
            _cjy_report(pic_id)
            time.sleep(1)
            continue
        if distance <= 5:
            print(f"[captcha] 距离异常 {distance}")
            _cjy_report(pic_id)
            continue
        handle = None
        for _wait in range(8):
            handle = _find_handle_in_frames(page, host)
            if handle:
                break
            time.sleep(0.4)
        if not handle:
            print("[captcha] 找不到滑块手柄")
            _cjy_report(pic_id)
            time.sleep(2)
            continue
        print(f"[captcha] 拖拽距离 {distance:.0f}px")
        _human_like_drag(page, handle, distance)
        time.sleep(2.5)
        # 过了之后 URL 经常还停在 /verify，不能再用 URL 判断失败
        if _has_pass_signal(page) or not _captcha_widget_visible(page):
            print("[captcha] 验证通过 ✓")
            return True
        print("[captcha] 拖动后拼图还在，报错返分 + 刷新重试")
        _cjy_report(pic_id)
        rb = page.query_selector(".verify-refresh, [class*='refresh']")
        if not rb:
            try:
                rb = host.query_selector(".verify-refresh, [class*='refresh']")
            except Exception:
                rb = None
        if rb:
            try:
                rb.click()
            except Exception:
                pass
        time.sleep(2)
    print("[captcha] 超级鹰多次失败")
    try:
        page.screenshot(path="debug_captcha_fail.png", full_page=False)
        print("[captcha] 失败截图已保存 debug_captcha_fail.png URL=" + (page.url or "")[:80])
    except Exception as e:
        print(f"[captcha] 失败截图保存失败: {e}")
    return False
