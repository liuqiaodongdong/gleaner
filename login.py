"""有头登录知网 + 自动持续保存 cookie（无需手动按 Enter）。

用法（主力机）：set ACQ_BROWSER_CHANNEL=msedge & python login.py
在弹出的浏览器里：1) 滑动过验证码 2) 若有账号点右上角登录。
脚本每 3 秒自动保存一次 cookie，完成后直接关闭浏览器窗口即可。
"""
import json
import os
import sys
import time
from playwright.sync_api import sync_playwright
from config import COOKIES_FILE, CNKI_SEARCH_URL

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

pw = sync_playwright().start()
_channel = os.environ.get("ACQ_BROWSER_CHANNEL", "")  # 系统 Edge: msedge
_launch = dict(
    headless=False,
    args=[
        "--disable-blink-features=AutomationControlled",
        "--exclude-switches=enable-automation",
        "--disable-infobars",
        "--start-maximized",
    ],
)
if _channel:
    _launch["channel"] = _channel
browser = pw.chromium.launch(**_launch)
context = browser.new_context(
    viewport={"width": 1920, "height": 1080},
    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    accept_downloads=True,
)
context.add_init_script(path="libs/stealth.min.js")
page = context.new_page()
page.goto(CNKI_SEARCH_URL, wait_until="domcontentloaded", timeout=30000)

print("[login] 浏览器已打开知网。请：1) 滑动过验证码  2) 若有账号点右上角登录。")
print("[login] 脚本每 3 秒自动保存一次 cookie，最多 5 分钟。完成后直接关闭浏览器窗口。")

last_n = -1
saved_any = False
for i in range(100):  # 100 * 3s = 5 分钟
    try:
        cookies = context.cookies()
    except Exception:
        print("[login] 浏览器已关闭，停止。")
        break
    try:
        COOKIES_FILE.write_text(json.dumps(cookies, ensure_ascii=False, indent=2))
        saved_any = True
    except Exception as e:
        print(f"[login] 保存失败: {e}")
    try:
        url = page.url
    except Exception:
        url = "?"
    on_verify = ("verify" in url) or ("captcha" in url.lower())
    if len(cookies) != last_n:
        flag = "  [仍在验证页]" if on_verify else "  [已过验证/搜索页]"
        print(f"[login] {i*3}s  已存 {len(cookies)} 个 cookie{flag}")
        last_n = len(cookies)
    time.sleep(3)

try:
    browser.close()
except Exception:
    pass
pw.stop()
print(f"[login] 完成。共保存 cookie 到 {COOKIES_FILE}（saved={saved_any}）")
