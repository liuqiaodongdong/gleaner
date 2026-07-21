# tests/test_guard.py
from pathlib import Path
from acq.guard import RateGuard

def test_quota_and_circuit(tmp_path):
    g = RateGuard("test", min_interval=0, max_per_day=2, state_dir=tmp_path)
    assert g.can_download()
    g.record(ok=True); g.record(ok=True)
    assert not g.can_download()          # 配额用完
    assert g.remaining() == 0

def test_trip(tmp_path):
    g = RateGuard("test", min_interval=0, max_per_day=99, state_dir=tmp_path)
    assert not g.tripped()
    g.trip("403")
    assert g.tripped() and not g.can_download()

def test_persist_same_day(tmp_path):
    g1 = RateGuard("sd", min_interval=0, max_per_day=5, state_dir=tmp_path)
    g1.record(ok=True)
    g2 = RateGuard("sd", min_interval=0, max_per_day=5, state_dir=tmp_path)
    assert g2.remaining() == 4           # 跨实例同日持久化

def test_record_ok_false_tracks_fail_count(tmp_path):
    """record(ok=False) 应累计 fail_count；record(ok=True) 应清零；consecutive_fails() 公开可读。"""
    g = RateGuard("fc", min_interval=0, max_per_day=99, state_dir=tmp_path)
    g.record(ok=False)
    g.record(ok=False)
    assert g.consecutive_fails() == 2   # 连续失败 2 次（使用公开 getter）
    g.record(ok=True)
    assert g.consecutive_fails() == 0   # 成功后清零

def test_cross_day_reset(tmp_path):
    """跨天清零：注入 _now_fn 模拟日期切换，验证配额归零、旧 tripped 清除（新实例）。"""
    # Day 1：用尽配额并熔断
    g1 = RateGuard("xd", min_interval=0, max_per_day=2, state_dir=tmp_path,
                   _now_fn=lambda: "2099-01-01")
    g1.record(ok=True); g1.record(ok=True)
    g1.trip("test")
    assert not g1.can_download()

    # Day 2：换日期重建实例，配额与熔断全部清零
    g2 = RateGuard("xd", min_interval=0, max_per_day=2, state_dir=tmp_path,
                   _now_fn=lambda: "2099-01-02")
    assert g2.remaining() == 2           # 新日配额已清零
    assert not g2.tripped()             # 熔断已清零
    assert g2.can_download()            # 可以下载

def test_same_instance_cross_day_reset(tmp_path):
    """同一实例跨天：熔断后日期切换，can_download() 应自动清除熔断并恢复配额。"""
    day = ["2099-02-01"]  # 可变容器，用于模拟日期推进

    g = RateGuard("si", min_interval=0, max_per_day=2, state_dir=tmp_path,
                  _now_fn=lambda: day[0])
    # Day 1：用完配额并熔断
    g.record(ok=True); g.record(ok=True)
    g.trip("captcha")
    assert not g.can_download()          # 熔断生效

    # 模拟跨天：同一实例，切换日期
    day[0] = "2099-02-02"
    assert g.can_download()              # 跨天后 can_download() 应清零熔断并返回 True
    assert not g.tripped()              # tripped() 已清除
    assert g.remaining() == 2           # 配额已归零

def test_record_cross_day_counts_today(tmp_path):
    """跨天后首次调用 record() 应写入新日期 state，而非昨天的条目。"""
    day = ["2099-03-01"]

    g = RateGuard("rc", min_interval=0, max_per_day=5, state_dir=tmp_path,
                  _now_fn=lambda: day[0])
    g.record(ok=True)                    # Day 1：count=1

    day[0] = "2099-03-02"               # 切换到 Day 2
    g.record(ok=True)                   # 应写入新 state
    assert g._state["day"] == "2099-03-02"
    assert g._state["count"] == 1       # 今天只 record 了 1 次，不是累计 2
