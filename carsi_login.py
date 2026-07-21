# carsi_login.py —— 有头人工登录一次：过 CAS + 把目标库各点一遍 → 存 storage_state
import os
import time
from pathlib import Path
os.environ["ACQ_HEADLESS"] = "0"
os.environ["ACQ_BROWSER_CHANNEL"] = ""   # 用自带 chromium，避开系统 Clash 代理
from browser import launch_browser       # 复用现有浏览器层
from acq.cookie_store import CookieStore

CARSI_PORTAL = "https://ds.carsi.edu.cn/ds/index.html"
TARGETS = ["ScienceDirect", "Springer", "EBSCO", "Emerald", "ProQuest"]
STORE = CookieStore(Path(__file__).parent / "acq" / "cookies" / "carsi")

def main():
    pw, browser, context, page = launch_browser()  # 见 browser.launch_browser 返回签名（实施时核对）
    try:
        page.goto(CARSI_PORTAL)
        print("=" * 60)
        print("请在浏览器里：1) 选『浙江工商大学』 2) 完成统一身份认证(CAS)")
        print(f"   3) 把这些库各点开一次(种 cookie)：{', '.join(TARGETS)}")
        print("   每库进到已认证主页即可，无需下载。关闭浏览器或等待10分钟后脚本自动保存退出。")
        print("=" * 60)
        # 每 5s 自动存一次 storage_state，最长 10 分钟，关窗即停
        deadline = time.time() + 600
        while time.time() < deadline:
            try:
                STORE.save_state(context.storage_state())
            except Exception:
                break  # 用户关闭浏览器，context 已失效，退出循环
            time.sleep(5)
        # 超时正常退出时补存一次；若 context 已关闭则静默跳过（最后一次周期保存已落盘）
        try:
            STORE.save_state(context.storage_state())
        except Exception:
            pass
        print(f"已保存 storage_state → {STORE.state_path()}")
    finally:
        try:
            context.close(); browser.close(); pw.stop()
        except Exception:
            pass

if __name__ == "__main__":
    main()
