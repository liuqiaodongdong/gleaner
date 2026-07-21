# acq/cookie_store.py — 多域 cookie/storage_state 持久化
import json
import time
from pathlib import Path


class CookieStore:
    def __init__(self, base_dir):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def state_path(self) -> Path:
        return self.base_dir / "state.json"

    def save_state(self, storage_state: dict):
        self.state_path().write_text(json.dumps(storage_state, ensure_ascii=False), "utf-8")

    def load_state(self) -> "dict | None":
        p = self.state_path()
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text("utf-8"))
        except Exception:
            return None

    def age_hours(self) -> "float | None":
        """返回 state.json 距今小时数；不存在则返回 None。"""
        p = self.state_path()
        if not p.exists():
            return None
        return (time.time() - p.stat().st_mtime) / 3600.0
