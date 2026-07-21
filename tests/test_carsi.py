# tests/test_carsi.py
import json
from pathlib import Path
from acq.sources.carsi import detect_publisher, session_alive

CFG = json.loads((Path(__file__).parents[1] / "acq/data/publisher_carsi.json").read_text("utf-8"))

def test_detect_publisher():
    assert detect_publisher("https://www.sciencedirect.com/science/article/pii/X", CFG) == "sciencedirect"
    assert detect_publisher("https://www.emerald.com/insight/content/doi/10.1/full", CFG) == "emerald"
    assert detect_publisher("https://unknown.com/x", CFG) is None

def test_session_alive():
    assert session_alive({}, "https://www.sciencedirect.com/article/x") is True  # 未回踢
    assert session_alive({}, "https://idp.zjsu.edu.cn/cas/login?...") is False    # 回踢登录页
