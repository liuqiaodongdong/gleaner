# acq/guard.py
import json
import os
import random
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

_CST = timezone(timedelta(hours=8))  # 北京时区

def _today() -> str:
    return datetime.now(_CST).strftime("%Y-%m-%d")

class RateGuard:
    def __init__(self, source, min_interval, max_per_day, state_dir, _now_fn=None):
        self.source = source
        self.min_interval = float(min_interval)
        self.max_per_day = int(max_per_day)
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self._path = self.state_dir / f"guard_{source}.json"
        self._last = 0.0
        self._now_fn = _now_fn or _today  # 注入点：测试可传 lambda 控制日期
        self._state = self._load()

    def _load(self):
        if self._path.exists():
            try:
                s = json.loads(self._path.read_text("utf-8"))
            except Exception:
                s = {}
        else:
            s = {}
        if s.get("day") != self._now_fn():           # 跨天清零
            s = {"day": self._now_fn(), "count": 0, "fail_count": 0,
                 "tripped": False, "reason": ""}
            self._save(s)
        return s

    def _save(self, s=None):
        # 显式区分"传入空 dict"和"未传参"，避免 falsy 短路写入错误数据或静默跳过
        data = s if s is not None else self._state
        # 原子写：temp→os.replace，防进程崩溃截断 JSON 致 _load 兜底归零、配额被重置(超 max_per_day)
        tmp = self._path.with_name(self._path.name + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), "utf-8")
        os.replace(tmp, self._path)

    def remaining(self) -> int:
        if self._state.get("day") != self._now_fn():
            self._state = self._load()
        return max(0, self.max_per_day - self._state.get("count", 0))

    def tripped(self) -> bool:
        return bool(self._state.get("tripped"))

    def consecutive_fails(self) -> int:
        """返回当前连续失败次数（公开 getter）。"""
        return self._state.get("fail_count", 0)

    def can_download(self) -> bool:
        # 先调 remaining() 触发跨天 _load() / 清零熔断，再检查 tripped()
        # 若先调 tripped() 短路，跨天后熔断状态永远不会被清除
        r = self.remaining()
        return (not self.tripped()) and r > 0

    def wait(self):
        if self.min_interval <= 0:
            return
        delta = time.monotonic() - self._last
        jitter = self.min_interval * random.uniform(0.8, 1.2)
        if delta < jitter:
            time.sleep(jitter - delta)
        self._last = time.monotonic()

    def record(self, ok: bool):
        # 跨午夜后首次 record() 应先清零 state，避免把当天计数写进昨天条目
        if self._state.get("day") != self._now_fn():
            self._state = self._load()
        self._state["count"] = self._state.get("count", 0) + 1
        if ok:
            self._state["fail_count"] = 0                                    # 成功：连续失败计数清零
        else:
            self._state["fail_count"] = self._state.get("fail_count", 0) + 1  # 失败：连续失败累计
        self._save()

    def trip(self, reason: str):
        self._state["tripped"] = True
        self._state["reason"] = reason
        self._save()
