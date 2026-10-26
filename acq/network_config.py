"""CNKI 默认直连；仅使用用户明确指定且格式有效的代理。"""
import os
from urllib.parse import urlsplit


def proxy_server():
    value = (os.environ.get("ACQ_PROXY") or "").strip()
    if not value:
        return None
    message = "ACQ_PROXY 格式无效：请填写正在运行的 http/https/socks5 代理及数字端口；无需代理时删除该配置。PORT 是占位符。"
    try:
        parsed = urlsplit(value)
        if (parsed.scheme not in {"http", "https", "socks5"} or not parsed.hostname
                or parsed.port is None or parsed.port <= 0 or parsed.path not in {"", "/"}
                or parsed.query or parsed.fragment or parsed.username or parsed.password
                or any(c.isspace() for c in value)):
            raise ValueError(message)
    except ValueError:
        raise ValueError(message) from None
    return value


def proxy_status():
    try:
        server = proxy_server()
    except ValueError as exc:
        return {"ok": False, "mode": "invalid", "configured": True, "detail": str(exc)}
    return {"ok": True, "mode": "proxy" if server else "direct", "configured": bool(server),
            "detail": ("已显式配置 ACQ_PROXY；此处仅校验格式，连通性由实际访问确认。" if server
                       else "默认直连，不读取系统代理；校园网或 VPN 的系统路由仍正常生效。")}
