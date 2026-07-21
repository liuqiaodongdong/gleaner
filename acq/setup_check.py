# acq/setup_check.py —— 部署/凭据就绪检查（不打印密钥内容）
"""供 MCP setup_status 与 agent 首次引导使用。"""
from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COOKIES_FILE = ROOT / "cookies.json"
ELS_KEY_FILE = ROOT / "acq" / "data" / ".elsevier_key"
CARSI_STATE = ROOT / "acq" / "cookies" / "carsi" / "state.json"


def _proxy_detected() -> tuple[bool, str]:
    """返回 (是否有代理, 说明)。"""
    v = (os.environ.get("ACQ_PROXY") or "").strip()
    if v:
        return True, f"ACQ_PROXY={v}"
    try:
        import winreg
        k = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
        )
        enable, _ = winreg.QueryValueEx(k, "ProxyEnable")
        if not enable:
            return False, "系统代理未开启，且未设 ACQ_PROXY"
        server, _ = winreg.QueryValueEx(k, "ProxyServer")
        if not server:
            return False, "系统代理开关开着但 ProxyServer 为空"
        return True, f"Windows 系统代理: {server}"
    except Exception:
        return False, "未检测到 ACQ_PROXY / 系统代理（非 Windows 或读注册表失败）"


def _cnki_cookies() -> dict:
    if not COOKIES_FILE.exists():
        return {
            "ok": False,
            "status": "missing",
            "path": str(COOKIES_FILE),
            "hint": "尚无 cookies.json。请在本机项目目录运行: python login.py（建议 set ACQ_BROWSER_CHANNEL=msedge）",
        }
    try:
        data = json.loads(COOKIES_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        return {
            "ok": False,
            "status": "invalid",
            "path": str(COOKIES_FILE),
            "hint": f"cookies.json 无法解析: {e}。请删除后重跑 python login.py",
        }
    n = len(data) if isinstance(data, list) else 0
    if n <= 0:
        return {
            "ok": False,
            "status": "empty",
            "path": str(COOKIES_FILE),
            "hint": "cookies.json 为空。请重跑 python login.py 完成机构访问后保存",
        }
    return {
        "ok": True,
        "status": "present",
        "path": str(COOKIES_FILE),
        "cookie_count": n,
        "hint": "已有 CNKI cookies（换网络/代理后可能失效，失效时重跑 login.py）",
    }


def _chaojiying() -> dict:
    user = (os.environ.get("CJY_USER") or "").strip()
    pwd = (os.environ.get("CJY_PASS") or "").strip()
    soft = (os.environ.get("CJY_SOFTID") or "").strip()
    missing = [k for k, v in [("CJY_USER", user), ("CJY_PASS", pwd), ("CJY_SOFTID", soft)] if not v]
    if missing:
        return {
            "ok": False,
            "status": "missing_env",
            "missing": missing,
            "apply_url": "https://www.chaojiying.com/",
            "hint": (
                "CNKI 验证码需要超级鹰。请注册并充值积分，创建软件 ID(softid)，"
                "把 CJY_USER / CJY_PASS / CJY_SOFTID 写入 MCP 配置的 env（见 .mcp.json.example），"
                "勿写入仓库。验证码类型使用 9602（水平滑块）。"
            ),
        }
    return {
        "ok": True,
        "status": "env_set",
        "user_set": True,
        "softid_set": True,
        "hint": "超级鹰环境变量已配置（未校验账号是否有效；可用 chaojiying_score 查积分）",
    }


# Agent 引导文案：只认官方 Developer Portal，禁止误导向第三方/爬站
ELSEVIER_APPLY = {
    "portal": "https://dev.elsevier.com/",
    "create_key": "https://dev.elsevier.com/apikey/manage",
    "quotas": "https://dev.elsevier.com/api_key_settings.html",
    "account": "https://account.elsevier.com/",
    "guide_in_repo": "docs/ELSEVIER_API.md",
    "steps": [
        "用学校/机构邮箱注册或登录 Elsevier 账号：https://account.elsevier.com/",
        "打开官方 Developer Portal：https://dev.elsevier.com/",
        "进入 My API Key / Create API Key：https://dev.elsevier.com/apikey/manage",
        "填写 Label（如 gleaner-local）；Website URL 本地可用 http://localhost（以页面校验为准）",
        "复制生成的 API Key，配置到 MCP env 的 ELSEVIER_API_KEY，或单行写入 acq/data/.elsevier_key",
        "再调用 setup_status，确认 lines.elsevier.ready=true",
    ],
    "agent_rules": [
        "只引导用户申请 Elsevier 官方 API Key（dev.elsevier.com），不要推荐第三方 Key/镜像/破解",
        "不要让用户用浏览器爬 science direct 网页代替本项目的官方 API",
        "API Key 主要用于鉴权与配额；订阅全文仍依赖机构权益，未订刊可能下不到全文",
        "不要回显完整 API Key；不要让用户把 Key 提交到 git",
    ],
}


def _elsevier() -> dict:
    env = (os.environ.get("ELSEVIER_API_KEY") or "").strip()
    file_ok = False
    if ELS_KEY_FILE.exists():
        try:
            file_ok = bool(ELS_KEY_FILE.read_text(encoding="utf-8").strip())
        except Exception:
            file_ok = False
    if env or file_ok:
        return {
            "ok": True,
            "status": "configured",
            "via": "env" if env else "file",
            "hint": "Elsevier API key 已配置（不回显密钥内容）",
            "guide": str(ROOT / "docs" / "ELSEVIER_API.md"),
        }
    return {
        "ok": False,
        "status": "missing",
        "apply_url": ELSEVIER_APPLY["create_key"],
        "portal": ELSEVIER_APPLY["portal"],
        "key_file": str(ELS_KEY_FILE),
        "guide": str(ROOT / "docs" / "ELSEVIER_API.md"),
        "apply_steps": ELSEVIER_APPLY["steps"],
        "agent_rules": ELSEVIER_APPLY["agent_rules"],
        "hint": (
            "缺少 Elsevier 官方 API Key。"
            "请严格按官方流程：https://dev.elsevier.com/ → "
            "https://dev.elsevier.com/apikey/manage 创建 Key；"
            "建议学校邮箱；配到 ELSEVIER_API_KEY 或 acq/data/.elsevier_key。"
            "完整步骤见 docs/ELSEVIER_API.md。禁止引导第三方 Key 或网页爬取。"
        ),
    }


def _carsi() -> dict:
    if CARSI_STATE.exists() and CARSI_STATE.stat().st_size > 10:
        return {
            "ok": True,
            "status": "present",
            "path": str(CARSI_STATE),
            "hint": "CARSI cookie 状态文件存在（intl_collect 的 carsi 源可用）",
        }
    return {
        "ok": False,
        "status": "missing",
        "required_for": "intl_collect(sources 含 carsi) 时需要",
        "hint": "可选。默认 OA/NBER/Sci-Hub 不需要。若要用机构库 CARSI，需在本机完成浏览器 SSO 登录并保存 acq/cookies/carsi/state.json",
    }


def check_setup() -> dict:
    """检查本机部署就绪状态。返回可 JSON 序列化的结构（不含密钥明文）。"""
    proxy_ok, proxy_detail = _proxy_detected()
    cnki_ck = _cnki_cookies()
    cjy = _chaojiying()
    els = _elsevier()
    carsi = _carsi()

    cnki_collect_ready = bool(cjy["ok"] and proxy_ok)
    cnki_list_ready = bool(proxy_ok)
    lines = {
        "cnki": {
            "ready": cnki_collect_ready,
            "cnki_collect_ready": cnki_collect_ready,
            "cnki_list_ready": cnki_list_ready,
            "cookies": cnki_ck,
            "chaojiying": cjy,
            "proxy": {"ok": proxy_ok, "detail": proxy_detail},
            "tools": ["cnki_collect", "cnki_list"],
            "agent_note": (
                "CNKI 全文(cnki_collect)：代理 + 超级鹰 为硬门槛；cookies(login.py) 强烈推荐。"
                "题录(cnki_list)：主要需要代理/机构网。"
            ),
        },
        "elsevier": {
            "ready": bool(els["ok"]),
            "api_key": els,
            "tools": ["els_collect"],
            "agent_note": "仅需 Elsevier API key；无需浏览器/cookies。",
        },
        "intl": {
            "ready": True,
            "carsi_optional": carsi,
            "tools": ["intl_collect"],
            "agent_note": "默认 OA/NBER/Sci-Hub 无需额外密钥；CARSI 可选。",
        },
    }

    blockers = []
    if not cjy["ok"]:
        blockers.append({
            "id": "chaojiying",
            "severity": "cnki",
            "title": "申请并配置超级鹰账号",
            "url": "https://www.chaojiying.com/",
            "action": "注册→充值→创建软件得 softid→设置 CJY_USER/CJY_PASS/CJY_SOFTID 到 MCP env",
        })
    if not proxy_ok:
        blockers.append({
            "id": "proxy",
            "severity": "cnki",
            "title": "配置可访问知网机构库的代理或校园网",
            "action": "设置 ACQ_PROXY=http://host:port，或开启 Windows 系统代理（与浏览器一致）",
        })
    if not cnki_ck["ok"]:
        blockers.append({
            "id": "cnki_cookies",
            "severity": "cnki",
            "optional": True,
            "title": "录入 CNKI cookies（推荐）",
            "action": "在项目目录执行: set ACQ_BROWSER_CHANNEL=msedge && python login.py ，完成后生成 cookies.json",
        })
    if not els["ok"]:
        blockers.append({
            "id": "elsevier_key",
            "severity": "elsevier",
            "title": "申请 Elsevier 官方 API Key（仅 dev.elsevier.com）",
            "url": ELSEVIER_APPLY["create_key"],
            "portal": ELSEVIER_APPLY["portal"],
            "guide": "docs/ELSEVIER_API.md",
            "apply_steps": ELSEVIER_APPLY["steps"],
            "agent_rules": ELSEVIER_APPLY["agent_rules"],
            "action": (
                "学校邮箱登录 https://dev.elsevier.com/apikey/manage → Create API Key → "
                "填 ELSEVIER_API_KEY 或 acq/data/.elsevier_key；详见 docs/ELSEVIER_API.md"
            ),
        })

    ready_any = cnki_collect_ready or lines["elsevier"]["ready"] or lines["intl"]["ready"]
    ready_all_core = cnki_collect_ready and lines["elsevier"]["ready"]

    next_steps = []
    for b in blockers:
        if b.get("optional"):
            continue
        step = f"[{b['severity']}] {b['title']}"
        if b.get("url"):
            step += f" → {b['url']}"
        step += f"。{b['action']}"
        next_steps.append(step)
    for b in blockers:
        if b.get("optional"):
            next_steps.append(f"[可选/{b['severity']}] {b['title']}。{b['action']}")

    if not next_steps:
        next_steps.append("核心凭据已就绪。可调用 cnki_collect / els_collect / intl_collect。")
    else:
        next_steps.insert(
            0,
            "【给 Agent】请把下列缺失项用清单展示给用户，协助申请/填写；"
            "在对应线 ready=false 时不要强行采集该线，先完成配置再重跑 setup_status。",
        )

    return {
        "ok": ready_all_core,
        "ready_any_line": ready_any,
        "project_root": str(ROOT),
        "lines": lines,
        "blockers": blockers,
        "next_steps_for_user": next_steps,
        "how_to_configure_mcp": {
            "template": str(ROOT / ".mcp.json.example"),
            "env_example": str(ROOT / ".env.example"),
            "readme": str(ROOT / "README.md"),
            "note": "密钥只放 MCP env 或本机 gitignore 文件，不要写进仓库、不要回显密钥明文。",
        },
    }


def preflight(line: str) -> dict | None:
    """采集前检查。ready 则返回 None；否则返回应直接给用户/agent 的 dict。"""
    s = check_setup()
    line = (line or "").lower().strip()
    if line in ("cnki", "cnki_collect"):
        L = s["lines"]["cnki"]
        if L["cnki_collect_ready"]:
            return None
        return {
            "error": "setup_incomplete",
            "line": "cnki_collect",
            "message": "CNKI 全文线尚未就绪，请先完成部署引导（超级鹰 + 机构代理）。",
            "setup": {
                "chaojiying": L["chaojiying"],
                "proxy": L["proxy"],
                "cookies": L["cookies"],
            },
            "next_steps_for_user": s["next_steps_for_user"],
            "hint": "请先调用 setup_status，按 next_steps_for_user 引导用户配置后再试 cnki_collect。",
        }
    if line == "cnki_list":
        L = s["lines"]["cnki"]
        if L["cnki_list_ready"]:
            return None
        return {
            "error": "setup_incomplete",
            "line": "cnki_list",
            "message": "CNKI 题录线需要可访问知网的代理/机构网。",
            "setup": {"proxy": L["proxy"], "cookies": L["cookies"]},
            "next_steps_for_user": s["next_steps_for_user"],
            "hint": "请先配置 ACQ_PROXY 或系统代理，再调用 setup_status 确认。",
        }
    if line in ("els", "elsevier", "els_collect"):
        L = s["lines"]["elsevier"]
        if L["ready"]:
            return None
        return {
            "error": "setup_incomplete",
            "line": "elsevier",
            "message": "Elsevier 线尚未就绪：缺少 API key。",
            "setup": {"api_key": L["api_key"]},
            "next_steps_for_user": s["next_steps_for_user"],
            "hint": "请先调用 setup_status，引导用户申请 Elsevier API key 后再试 els_collect。",
        }
    return None
