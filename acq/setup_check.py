"""Gleanera 的本地机构会话检查；不以代理或外部 API Key 作为必需条件。"""
import json
from pathlib import Path
import os
from acq.network_config import proxy_status
from acq.credential_checks import configured_value
from acq.cnki_session import resolve_session_mode, session_path

ROOT = Path(__file__).resolve().parent.parent
COOKIES_FILE = ROOT / "cookies.json"

def _chaojiying() -> dict:
    user = (os.environ.get("CJY_USER") or "").strip()
    pwd = (os.environ.get("CJY_PASS") or "").strip()
    soft = (os.environ.get("CJY_SOFTID") or "").strip()
    missing = [k for k, v in [("CJY_USER", user), ("CJY_PASS", pwd), ("CJY_SOFTID", soft)] if not configured_value(v)]
    if soft and (not soft.isdigit() or int(soft) <= 0) and "CJY_SOFTID" not in missing:
        missing.append("CJY_SOFTID")
    if missing:
        return {
            "ok": False,
            "status": "missing_env",
            "missing": missing,
            "apply_url": "https://www.chaojiying.com/",
            "hint": (
                "CNKI 验证码需要超级鹰。请注册并充值积分，创建软件 ID(softid)，"
                "把 CJY_USER / CJY_PASS / CJY_SOFTID 写入 GLEANERA_ROOT/.env（见 .env.example），"
                "勿写入仓库。验证码类型使用 9602（水平滑块）。"
            ),
        }
    return {
        "ok": True,
        "status": "env_set",
        "user_set": True,
        "softid_set": True,
        "hint": "超级鹰环境变量已配置（未校验账号是否有效；可用 python gleanera_cli.py score 查积分）",
    }



def _cnki_cookies():
    result = {"ok": False, "status": "missing", "path": str(COOKIES_FILE),
              "hint": "运行 python login.py，在知网官方机构入口选择学校并完成登录。"}
    try:
        cookies = json.loads(COOKIES_FILE.read_text(encoding="utf-8"))
        if not isinstance(cookies, list) or not cookies:
            result["status"] = "empty"
            return result
        if not session_path(ROOT).is_file():
            result["status"] = "institution_identity_unconfirmed"
            return result
        resolve_session_mode(ROOT, "institution")
    except (OSError, ValueError, TypeError) as exc:
        result["status"] = "session_invalid" if COOKIES_FILE.exists() else "missing"
        return result
    result.update(ok=True, status="present", cookie_count=len(cookies),
                  hint="本地机构会话匹配；实际有效性在访问时确认，下载期间不覆盖或自动重录。")
    return result


def check_setup():
    proxy = proxy_status()
    cookies = _cnki_cookies()
    ready = cookies["ok"] and proxy["ok"]
    cjy = _chaojiying()
    cjy["optional"] = True
    cjy["hint"] = "可选：采集中出现验证码时使用；首次学校机构登录由用户在浏览器完成。"
    cnki = {"ready": ready, "cnki_collect_ready": ready, "cnki_list_ready": ready,
            "cnki_ready": ready, "cookies": cookies, "proxy": proxy, "chaojiying": cjy,
            "tools": ["cnki", "cnki-list"], "agent_note": "只复用已确认的学校机构会话；失效即停止并提示登录。"}
    blockers = []
    if not cookies["ok"]:
        blockers.append({"id": "institution_session", "severity": "cnki", "title": "完成学校机构登录",
                         "action": "python login.py；用户在浏览器完成认证后脚本自动保存会话。"})
    if not proxy["ok"]:
        blockers.append({"id": "proxy", "severity": "cnki", "title": "修正可选代理配置", "action": proxy["detail"]})
    return {"ok": ready, "ready_any_line": ready, "project_root": str(ROOT), "session_mode": "institution",
            "lines": {"cnki": cnki}, "blockers": blockers,
            "next_steps_for_user": [b["action"] for b in blockers] or ["机构会话配置已就绪，可运行 cnki-list / cnki。"]}


def preflight(line):
    if line not in {"cnki", "cnki_collect", "cnki-list", "cnki_list"}:
        return {"ok": False, "error": "unknown_line", "line": line}
    status = check_setup()
    if status["ok"]:
        return None
    return {"ok": False, "error": "setup_incomplete", "line": line,
            "message": "机构会话未就绪或显式代理配置无效；请按提示完成登录或修正配置。",
            "setup": status["lines"]["cnki"], "next_steps_for_user": status["next_steps_for_user"]}
