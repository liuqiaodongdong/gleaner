# acq/els_config.py —— Elsevier API key 读取（机密，不进 git，不打印）
import os
from pathlib import Path

_KEY_FILE = Path(__file__).resolve().parent / "data" / ".elsevier_key"


def get_api_key() -> str:
    """env ELSEVIER_API_KEY 优先；否则读 acq/data/.elsevier_key；都没有抛错。"""
    k = os.environ.get("ELSEVIER_API_KEY")
    if k and k.strip():
        return k.strip()
    if _KEY_FILE.exists():
        v = _KEY_FILE.read_text(encoding="utf-8").strip()
        if v:
            return v
    raise RuntimeError(
        "Elsevier API key 缺失：请申请官方 Key（https://dev.elsevier.com/apikey/manage），"
        "设置环境变量 ELSEVIER_API_KEY 或写入 acq/data/.elsevier_key。"
        "完整步骤见 docs/ELSEVIER_API.md（禁止使用第三方 Key/网页爬取代替）")
