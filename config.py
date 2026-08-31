from pathlib import Path
import os as _os

# Project paths
BASE_DIR = Path(__file__).parent
COOKIES_FILE = BASE_DIR / "cookies.json"
PAPERS_DIR = BASE_DIR / "output" / "papers"

# Scraping parameters
# 无头批量任务可显式设置 ACQ_FAST=1，缩短外层节流等待；详情页内部仍保留
# DOM/元数据加载等待，默认模式继续使用保守间隔。
_FAST_MODE = _os.environ.get("ACQ_FAST", "0") == "1"
DELAY_PAGE = (0.3, 1.0) if _FAST_MODE else (2, 5)
DELAY_DETAIL = (0.3, 1.0) if _FAST_MODE else (3, 8)
MAX_RETRIES = 3           # network retry count

# CNKI URLs
CNKI_SEARCH_URL = "https://kns.cnki.net/kns8s/defaultresult/index"
CNKI_ADVANCED_URL = "https://kns.cnki.net/kns8s/AdvSearch?type=expert"  # 专业检索页（直接进入）

# 超级鹰打码（验证码求解）—— 仅从环境变量读取，勿在仓库写入账号密码
# 设置：CJY_USER / CJY_PASS / CJY_SOFTID（可写在 MCP env 或系统环境变量）
CHAOJIYING_USER = _os.environ.get("CJY_USER", "")
CHAOJIYING_PASS = _os.environ.get("CJY_PASS", "")
CHAOJIYING_SOFTID = _os.environ.get("CJY_SOFTID", "")
