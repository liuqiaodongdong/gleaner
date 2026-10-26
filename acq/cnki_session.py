"""区分机构会话与旧刷新流程；标记仅保存在当前 worktree 的忽略目录。"""
import hashlib
import json
import time
from pathlib import Path


def session_path(root: Path) -> Path:
    return Path(root) / "acq" / "cookies" / "cnki" / "session.json"


def mark_institution_session(root: Path, cookie_file: Path) -> None:
    path = session_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"mode": "institution", "cookies_sha256": hashlib.sha256(cookie_file.read_bytes()).hexdigest()}
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def clear_session_marker(root: Path) -> None:
    session_path(root).unlink(missing_ok=True)


def resolve_session_mode(root: Path, requested: str = "auto") -> str:
    if requested not in {"auto", "institution"}:
        raise ValueError("未知会话模式")
    path = session_path(root)
    if not path.exists():
        return "institution"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        cookies = Path(root) / "cookies.json"
        if data.get("mode") != "institution" or data.get("cookies_sha256") != hashlib.sha256(cookies.read_bytes()).hexdigest():
            raise ValueError("机构会话标记与 cookies 不匹配")
    except (OSError, ValueError, AttributeError) as exc:
        raise ValueError("机构会话不可用；保留当前文件，请主动运行 python login.py --institution 重新登录") from exc
    return "institution"


def wait_for_institution_identity(page, timeout_sec: float = 8) -> bool:
    """登录身份尚未加载时短暂等待；不能把缺少机构身份当成已获全文权限。"""
    from login import institution_name

    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        if institution_name(page):
            return True
        page.wait_for_timeout(500)
    return False
